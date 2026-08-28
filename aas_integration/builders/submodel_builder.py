"""
Submodel builder that constructs AAS submodels from database configuration.
Uses SubmodelTemplate, SubmodelElement, and FieldMapping models to build submodels at runtime.
"""
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, replace

from basyx.aas import model as aas_model
from django.db import models as django_models
from dcim.models import DeviceBay
from ..models import SubmodelConfiguration, SubmodelElement, FieldMapping, SubmodelTemplate, AASConnection
from ..services.mapping_resolver import MappingResolver, MappingValidationError
from ..services.utils import create_aas_id, get_entity_type, get_entity_type_singular, get_object_name, sanitize_name_for_urn
from ..converters import netbox_obj_to_dict
from ..logging_utils import sanitize_for_log
from ..defaults import URN_NAMESPACE_DEFAULT


logger = logging.getLogger(__name__)

@dataclass
class AASHierarchyAttributes:
    has_parent: bool
    has_children: bool
    archetype: str
    hierarchy_id: str = None
    archetype_desc: dict  = None
    part_relationship: str  = None #HasPart IsPartOf SameAs
    entry_node_desc: dict  = None
    parent_node_id_short_seed: str = None
    parent_node_desc: dict = None
    children_node_id_short_seed: str  = None #For constructing ID_Shorts
    children_part_id_short_seed: str  = None #For constructing ID_Shorts
    children_node_desc: dict  = None
    parent_part_id_short_seed: str = None 

@dataclass
class AASHierarchySeed:
    obj: django_models.Model
    entity_type: str
    connection: AASConnection
    urn_namespace: str = URN_NAMESPACE_DEFAULT
    hierarchy_id: str = None
    parent: django_models.Model = None
    children: list[django_models.Model] = None

@dataclass
class AASHierarchyLevel:
    node: aas_model.Entity
    relationship: aas_model.RelationshipElement


class HierarchyException(Exception):
    pass

class SubmodelBuilder:
    """
    Builds AAS Submodels dynamically from database configuration.

    Takes a SubmodelConfiguration with associated FieldMappings and constructs
    a complete AAS Submodel with all elements populated from the NetBox object.

    Supports:
    - Property and MultiLanguageProperty elements
    - SubmodelElementCollections (nested structures)
    - Conditional element inclusion
    - Value transformations
    - Cardinality validation
    """

    def __init__(self):
        self.resolver = MappingResolver()

    def build_submodel(
        self,
        obj: django_models.Model,
        config: SubmodelConfiguration,
        base_url: str,
        urn_namespace: str = URN_NAMESPACE_DEFAULT,
        unique_name: Optional[str] = None
    ) -> Optional[aas_model.Submodel]:
        """
        Build a complete AAS Submodel from configuration.

        Args:
            obj: NetBox model instance (Device, Rack, etc.)
            config: SubmodelConfiguration specifying template and mappings
            base_url: Base URL for URI generation
            urn_namespace: URN namespace for submodel ID
            unique_name: Unique identifier for this entity (if None, derived from obj)

        Returns:
            Populated AAS Submodel or None if build fails

        Raises:
            MappingValidationError: If required mapping fails
        """
        template = config.template

        # Generate unique name if not provided
        if not unique_name:
            unique_name = self._generate_unique_name(obj)

        # Generate submodel ID
        submodel_id = f"urn:{urn_namespace}:sm:{unique_name}_{template.id_short}"

        # Create submodel instance
        submodel = aas_model.Submodel(
            id_=submodel_id,
            id_short=template.id_short,
            semantic_id=self._create_semantic_reference(template.semantic_id) if template.semantic_id else None,
            description=self._create_langstring_set(template.description) if template.description else None
        )

        # Convert NetBox object to dict once for all mappings (performance optimization)
        obj_dict = netbox_obj_to_dict(obj)

        # Get all root-level elements (no parent_element)
        root_elements = template.elements.filter(parent_element__isnull=True).order_by('order', 'id_short')

        # Build each root element
        for element_def in root_elements:
            try:
                aas_element = self._build_element(obj, obj_dict, element_def, config)
                if aas_element is not None:
                    submodel.submodel_element.add(aas_element)
            except MappingValidationError:
                logger.error(f"Required mapping failed for {element_def.id_short}")
                if config.is_enabled:
                    raise
            except Exception:
                logger.warning(f"Failed to build element {element_def.id_short}", exc_info=True)

        return submodel

    def _build_element(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        config: SubmodelConfiguration
    ) -> Optional[aas_model.SubmodelElement]:
        """
        Build a single AAS SubmodelElement from definition.

        Args:
            obj: NetBox model instance
            obj_dict: Dictionary representation for JSONPath
            element_def: SubmodelElement definition
            config: Parent SubmodelConfiguration

        Returns:
            AAS SubmodelElement instance or None if element should be skipped
        """
        # Get field mapping for this element (if any)
        mapping = self._get_mapping(config, element_def)

        # Handle different element types
        if element_def.element_type == 'Property':
            return self._build_property(obj, obj_dict, element_def, mapping)

        elif element_def.element_type == 'MultiLanguageProperty':
            return self._build_multilanguage_property(obj, obj_dict, element_def, mapping)

        elif element_def.element_type == 'SubmodelElementCollection':
            return self._build_collection(obj, obj_dict, element_def, config)

        elif element_def.element_type == 'SubmodelElementList':
            return self._build_list(obj, obj_dict, element_def, config)

        elif element_def.element_type == 'ReferenceElement':
            return self._build_reference(obj, obj_dict, element_def, mapping)

        elif element_def.element_type in ('Blob', 'File'):
            # File/Blob support deferred to future implementation
            logger.debug(f"Element type {element_def.element_type} not yet supported, skipping {element_def.id_short}")
            return None

        else:
            logger.warning(f"Unsupported element type: {element_def.element_type}")
            return None

    def _build_property(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        mapping: Optional[FieldMapping]
    ) -> Optional[aas_model.Property]:
        """Build an AAS Property element."""
        # Resolve value from mapping
        if mapping:
            value = self.resolver.resolve(obj, mapping, obj_dict)
        else:
            # No mapping defined - check cardinality
            if element_def.cardinality == 'One':
                logger.warning(f"Required element {element_def.id_short} has no mapping")
            return None

        # Skip if value is None and element is optional
        if value is None:
            if element_def.cardinality == 'One':
                raise MappingValidationError(f"Required element {element_def.id_short} resolved to None")
            return None

        # Convert value_type string to BaSyx datatype
        value_type = self._get_aas_datatype(element_def.value_type)

        # Create property
        prop = aas_model.Property(
            id_short=element_def.id_short,
            value_type=value_type,
            value=value,
            semantic_id=self._create_semantic_reference(element_def.semantic_id) if element_def.semantic_id else None,
            description=self._create_langstring_set(element_def.description) if element_def.description else None,
        )

        return prop

    def _build_multilanguage_property(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        mapping: Optional[FieldMapping]
    ) -> Optional[aas_model.MultiLanguageProperty]:
        """Build an AAS MultiLanguageProperty element."""
        # Resolve value from mapping
        if mapping:
            value = self.resolver.resolve(obj, mapping, obj_dict)
        else:
            if element_def.cardinality == 'One':
                logger.warning(f"Required multilanguage element {element_def.id_short} has no mapping")
            return None

        # Skip if value is None and element is optional
        if value is None:
            if element_def.cardinality == 'One':
                raise MappingValidationError(f"Required element {element_def.id_short} resolved to None")
            return None

        # Value should be a dict like {'en': 'text', 'de': 'Text'}
        if not isinstance(value, dict):
            # If resolver didn't convert to multilanguage dict, log warning
            logger.warning(f"MultiLanguageProperty {element_def.id_short} got non-dict value: {type(value)}")
            value = {'en': str(value)}

        # Create MultiLanguageProperty
        ml_prop = aas_model.MultiLanguageProperty(
            id_short=element_def.id_short,
            value=aas_model.MultiLanguageTextType(value),
            semantic_id=self._create_semantic_reference(element_def.semantic_id) if element_def.semantic_id else None,
            description=self._create_langstring_set(element_def.description) if element_def.description else None,
        )

        return ml_prop

    def _build_collection(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        config: SubmodelConfiguration
    ) -> Optional[aas_model.SubmodelElementCollection]:
        """Build an AAS SubmodelElementCollection with nested child elements."""
        # Create collection
        collection = aas_model.SubmodelElementCollection(
            id_short=element_def.id_short,
            semantic_id=self._create_semantic_reference(element_def.semantic_id) if element_def.semantic_id else None,
            description=self._create_langstring_set(element_def.description) if element_def.description else None,
        )

        # Get child elements
        child_elements = element_def.child_elements.order_by('order', 'id_short')

        # Build each child element recursively
        for child_def in child_elements:
            try:
                child_aas = self._build_element(obj, obj_dict, child_def, config)
                if child_aas is not None:
                    collection.value.add(child_aas)
            except Exception:
                logger.warning(f"Failed to build child element {child_def.id_short}")

        # Return collection based on cardinality:
        # - If cardinality='One' (required), always return the collection even if empty
        # - If cardinality='ZeroToOne' or 'ZeroToMany' (optional), only return if it has children
        return collection if element_def.cardinality == 'One' or len(collection.value) > 0 else None

    def _build_list(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        config: SubmodelConfiguration
    ) -> Optional[aas_model.SubmodelElementList]:
        """
        Build an AAS SubmodelElementList.

        Similar to collections, lists can be required (cardinality='One') or optional.
        Required lists are created even if empty, optional lists only if they have content.
        """
        list_elem = aas_model.SubmodelElementList(
            id_short=element_def.id_short,
            type_value_list_element=aas_model.SubmodelElementCollection,  # Default to Collection
            semantic_id=self._create_semantic_reference(element_def.semantic_id) if element_def.semantic_id else None,
            description=self._create_langstring_set(element_def.description) if element_def.description else None,
        )

        if element_def.cardinality == 'One':
            return list_elem
        else:
            return None

    def _build_reference(
        self,
        obj: django_models.Model,
        obj_dict: Dict[str, Any],
        element_def: SubmodelElement,
        mapping: Optional[FieldMapping]
    ) -> Optional[aas_model.ReferenceElement]:
        """Build an AAS ReferenceElement."""
        # Resolve value from mapping
        if mapping:
            value = self.resolver.resolve(obj, mapping, obj_dict)
        else:
            return None

        if value is None:
            return None

        # Value should be a reference string (AAS ID)
        ref_elem = aas_model.ReferenceElement(
            id_short=element_def.id_short,
            value=aas_model.ModelReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.SUBMODEL,
                    value=str(value)
                ),)
            ),
            semantic_id=self._create_semantic_reference(element_def.semantic_id) if element_def.semantic_id else None,
        )

        return ref_elem

    def _get_mapping(self, config: SubmodelConfiguration, element_def: SubmodelElement) -> Optional[FieldMapping]:
        """Get the FieldMapping for an element (if any)."""
        try:
            return config.field_mappings.get(submodel_element=element_def)
        except FieldMapping.DoesNotExist:
            return None
        except FieldMapping.MultipleObjectsReturned:
            # Multiple mappings for same element - use first one
            logger.warning(f"Multiple mappings found for element {element_def.id_short}, using first")
            return config.field_mappings.filter(submodel_element=element_def).first()

    def _generate_unique_name(self, obj: django_models.Model) -> str:
        """Generate unique identifier for object."""
        model_name = obj._meta.model_name
        obj_name = getattr(obj, 'name', None) or str(obj)
        obj_id = obj.pk

        sanitized_name = sanitize_name_for_urn(obj_name, model_name, obj_id)
        return f"{sanitized_name}_{obj_id}"

    def _create_semantic_reference(self, semantic_id: str) -> aas_model.ExternalReference:
        """Create an AAS ExternalReference from semantic ID string."""
        return aas_model.ExternalReference(
            (aas_model.Key(
                type_=aas_model.KeyTypes.GLOBAL_REFERENCE,
                value=semantic_id
            ),)
        )

    def _create_langstring_set(self, description: Dict[str, str], use_text_type: bool = True) -> aas_model.MultiLanguageTextType:
        """
        Create AAS LangStringSet from description dict.

        Args:
            description: Dict like {'en': 'English text', 'de': 'Deutscher Text'}
            use_text_type: If True, use MultiLanguageTextType (unlimited length), otherwise use MultiLanguageNameType (max 64 chars)

        Returns:
            MultiLanguageTextType or MultiLanguageNameType for AAS description field
        """
        if not description or not isinstance(description, dict):
            return None

        if use_text_type:
            return aas_model.MultiLanguageTextType(description)
        else:
            return aas_model.MultiLanguageNameType(description)

    def _get_aas_datatype(self, value_type: str) -> type:
        """
        Convert value_type string to BaSyx AAS datatype.

        Args:
            value_type: String like 'xs:string', 'xs:int', 'xs:double'

        Returns:
            BaSyx datatype class
        """
        type_mapping = {
            'xs:string': aas_model.datatypes.String,
            'xs:int': aas_model.datatypes.Int,
            'xs:integer': aas_model.datatypes.Integer,
            'xs:long': aas_model.datatypes.Long,
            'xs:double': aas_model.datatypes.Double,
            'xs:float': aas_model.datatypes.Float,
            'xs:boolean': aas_model.datatypes.Boolean,
            'xs:dateTime': aas_model.datatypes.DateTime,
            'xs:date': aas_model.datatypes.Date,
            'xs:time': aas_model.datatypes.Time,
            'xs:anyURI': aas_model.datatypes.AnyURI,
        }

        return type_mapping.get(value_type, aas_model.datatypes.String)


class AASHierarchyBuilder:
    """
    Builds AAS HierarchicalStructures submodels for NetBox entities (devices and racks).

    The AAS HierarchicalStructures submodel template models parent/child relationships
    between assets using ``Entity`` nodes and ``RelationshipElement`` elements (``HasPart``
    / ``IsPartOf``).  This builder supports two hierarchy archetypes:

    - ``OneUp``  – the entry node points to its single parent (e.g. device → rack, or
      device → parent device via device bay).
    - ``OneDown`` – the entry node lists its direct children (e.g. rack → devices, or
      device → installed devices).
 
    The concrete hierarchy variant to build for a given object is determined by
    ``build_hierarchy_submodels``, which inspects the entity type and the relationships
    present in NetBox to decide which submodels are relevant.

    Template element definitions (semantic IDs, value types, …) are loaded once from the
    database during ``__init__`` so they are reused across all hierarchy submodels built
    by the same instance.
    """
    def __init__(self,connection: AASConnection = None, urn_namespace : str = URN_NAMESPACE_DEFAULT):
        self.submodel_builder = SubmodelBuilder()
        self.connection = connection
        self.urn_namespace = urn_namespace
        self.occupied_bays = self._fetch_occupied_bays()
        #template definitions:
        try:
            self.template = SubmodelTemplate.objects.get(template_id = 'https://admin-shell.io/idta/SubmodelTemplate/HierarchicalStructuresBoM/1/1')
            self._def_archetype = self.template.elements.get(id_short='ArcheType')
            self._archetype_value_type = self.submodel_builder._get_aas_datatype(self._def_archetype.value_type)
            self._def_entrynode = self.template.elements.get(id_short='EntryNode')
            self._def_node = self.template.elements.get(id_short='Node', parent_element=self._def_entrynode)
            self._def_rel_haspart = self.template.elements.get(id_short="HasPart", parent_element=self._def_entrynode)
            self._def_rel_ispartof = self.template.elements.get(id_short="IsPartOf", parent_element=self._def_entrynode)
        except Exception as e:
            raise HierarchyException("Failed to load AAS hierarchy template") from e
    
    def _fetch_occupied_bays(self) -> dict:
        """Fetch parent bays from DB"""
        return {
            _bay.installed_device.pk: {"Installed": _bay.installed_device, "Host": _bay.device}
            for _bay in DeviceBay.objects.filter(installed_device__isnull=False) 
        }

    def _get_hierachy_attributes(self, seed: AASHierarchySeed) -> AASHierarchyAttributes:
        """Return the pre-defined ``AASHierarchyAttributes`` for the given hierarchy identifier."""

        match seed.hierarchy_id:
            case 'hier_device2rack':
                return AASHierarchyAttributes(
                    archetype_desc = {'en' : 'To Parent Rack'},
                    entry_node_desc= {'en': f"Device: {get_object_name(obj=seed.obj)}"},
                    archetype='OneUp',
                    has_children=False,
                    has_parent=True,
                    hierarchy_id=seed.hierarchy_id,
                    parent_node_desc={'en':'Rack Description'},
                    part_relationship='IsPartOf',
                    parent_part_id_short_seed="IsPartOf_Rack_",
                    parent_node_id_short_seed='Rack_'
                    )
        
            case 'hier_rack2devices':
                return AASHierarchyAttributes(
                    archetype_desc = {'en' : 'To Child Devices'},
                    entry_node_desc= {'en': f"Rack: {get_object_name(obj=seed.obj)}"},
                    archetype='OneDown',
                    has_children=True,
                    has_parent=False,
                    hierarchy_id=seed.hierarchy_id,
                    part_relationship='HasPart',
                    children_node_id_short_seed='Device_',
                    children_part_id_short_seed='HasPart_Device_',
                    children_node_desc = {'en':'Device Description'}
                    )

            case 'hier_device2device_up':
                return AASHierarchyAttributes(
                    archetype_desc = {'en' : 'To Parent Device'},
                    entry_node_desc= {'en': f"Device: {get_object_name(obj=seed.obj)}"},
                    archetype='OneUp',
                    has_children=False,
                    has_parent=True,
                    hierarchy_id=seed.hierarchy_id,
                    parent_node_desc={'en':'Device Description'},
                    part_relationship='IsPartOf',
                    parent_part_id_short_seed="IsPartOf_Device_",
                    parent_node_id_short_seed='Device_'
                    )

            case 'hier_device2device_down':
                return AASHierarchyAttributes(
                    archetype_desc = {'en' : 'To Child Devices'},
                    entry_node_desc= {'en': f"Device: {get_object_name(obj=seed.obj)}"},
                    archetype='OneDown',
                    has_children=True,
                    has_parent=False,
                    hierarchy_id=seed.hierarchy_id,
                    part_relationship='HasPart',
                    children_node_id_short_seed='Device_',
                    children_part_id_short_seed='HasPart_Device_',
                    children_node_desc = {'en':'Device Description'}
                    )

            case _:
                raise HierarchyException(f"Hierarchy {seed.hierarchy_id} not implemented")

    def _get_aas_id(self, obj: django_models.Model) -> str:
        """Return the AAS ID for *obj*, reading it from the configured custom field when available and falling back to ``create_aas_id``."""

        try:
            _aas_id_field = None
            if self.connection is not None:
                _aas_id_field = self.connection.aas_id_field
            if _aas_id_field:
                _result = obj.cf.get(_aas_id_field)
                if _result:
                    return _result
        except Exception:
            logger.warning("Custom fields for AAS ID not set")
            
        #ID not available from connection, create new one:
        return create_aas_id(obj)

    def _get_archetype(self, value: str, desc: dict) -> aas_model.Property:
        """Build the ``ArcheType`` property element with the given archetype value and description."""
        try:
            return aas_model.Property(
                id_short=self._def_archetype.id_short,
                value_type=self._archetype_value_type,
                value=value,
                semantic_id=self.submodel_builder._create_semantic_reference(self._def_archetype.semantic_id),
                description=self.submodel_builder._create_langstring_set(desc)
            )
        except Exception as e:
            raise HierarchyException("Error when creating ArcheType Submodel element") from e
        
    def _get_entry_node(self, host_obj: django_models.Model, desc: dict) -> aas_model.Entity:
        """Build the ``EntryNode`` entity element that represents *host_obj* as the root of the hierarchy submodel."""
        try:
            _aas_id = self._get_aas_id(host_obj)
            return aas_model.Entity(
                id_short=self._def_entrynode.id_short,
                entity_type=aas_model.EntityType.SELF_MANAGED_ENTITY,
                global_asset_id=_aas_id,
                semantic_id=self.submodel_builder._create_semantic_reference(self._def_entrynode.semantic_id),
                description=self.submodel_builder._create_langstring_set(desc)
            )
        except Exception as e:
            raise HierarchyException("Error when creating EntryNode Submodel element") from e

    
    def _get_relationship_semantic_id(self, rel: str):
        match rel:
            case "HasPart":
                return self._def_rel_haspart.semantic_id
            case "IsPartOf":
                return self._def_rel_ispartof.semantic_id
            case _:
                raise HierarchyException("Unexpected hierarchy relationship")

    def _get_level_elements(self, obj: django_models.Model, host_obj: django_models.Model, rel: str) -> AASHierarchyLevel:
        """Build the ``Node`` entity and the corresponding ``HasPart``/``IsPartOf`` relationship element for *obj* relative to *host_obj*."""

        try:
            _rel_semantic_id = self._get_relationship_semantic_id(rel)
            _obj_entity_type = get_entity_type(obj)
            _obj_entity_type_singular = get_entity_type_singular(obj)
            _obj_name = get_object_name(obj)
            _host_aas_id = self._get_aas_id(host_obj)
            _obj_aas_id = self._get_aas_id(obj)

            _obj_name_safe = sanitize_name_for_urn(_obj_name,_obj_entity_type,obj.pk)            
            _node = aas_model.Entity(
                id_short=f"{_obj_entity_type_singular.capitalize()}_{_obj_name_safe}",
                entity_type=aas_model.EntityType.SELF_MANAGED_ENTITY,
                global_asset_id=_obj_aas_id,
                semantic_id=self.submodel_builder._create_semantic_reference(self._def_node.semantic_id),
                description=self.submodel_builder._create_langstring_set({'en': f"{_obj_entity_type_singular.capitalize()}: {_obj_name}" })
            )
            _ref_host = aas_model.ModelReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.ASSET_ADMINISTRATION_SHELL,
                    value=_host_aas_id),),
                type_=aas_model.AssetAdministrationShell,
            )
            _ref_obj = aas_model.ModelReference(
                (aas_model.Key(
                    type_=aas_model.KeyTypes.ASSET_ADMINISTRATION_SHELL,
                    value=_obj_aas_id),),
                type_=aas_model.AssetAdministrationShell,
            )
            _rel = aas_model.RelationshipElement(
                id_short = f"{rel}_{obj._meta.verbose_name.capitalize()}_{_obj_name_safe}",
                first=_ref_host,
                second=_ref_obj,
                semantic_id=self.submodel_builder._create_semantic_reference(_rel_semantic_id),
            )
            return AASHierarchyLevel(node=_node,relationship=_rel)
        
        except HierarchyException:
            raise
        except Exception as e:
            raise HierarchyException("Error while creating level elements") from e


    def _get_hierarchy_submodel(
            self,
            seed: AASHierarchySeed,
            ) -> aas_model.Submodel:
        """Build a single ``OneUp`` or ``OneDown`` hierarchy submodel from the provided seed data.""" 

        try:
            _attributes = self._get_hierachy_attributes(seed)

            if _attributes.archetype != "OneUp" and  _attributes.archetype != "OneDown":
                raise HierarchyException(f"Unexpected Archetype value for one-level hierarchy: {_attributes.archetype}")
            _obj_name = get_object_name(seed.obj)
            _unique_name = f"{sanitize_name_for_urn(_obj_name, seed.entity_type, seed.obj.pk)}_{seed.obj.pk}"
            _submodel_id = f"urn:{self.urn_namespace}:sm:{_unique_name}_{seed.hierarchy_id}"

            # Create submodel instance
            _submodel = aas_model.Submodel(
                id_=_submodel_id,
                id_short=seed.hierarchy_id,
                semantic_id=self.submodel_builder._create_semantic_reference(self.template.semantic_id) if self.template.semantic_id else None,
                description=self.submodel_builder._create_langstring_set(self.template.description) if self.template.description else None
            )

            _archetype = self._get_archetype(value=_attributes.archetype,desc=_attributes.archetype_desc)
            _entry_node = self._get_entry_node(host_obj=seed.obj,desc=_attributes.entry_node_desc)

            if _attributes.has_parent:
                _level_elements = self._get_level_elements(host_obj=seed.obj,obj=seed.parent,rel=_attributes.part_relationship)
                _entry_node.statement.add(_level_elements.node)
                _entry_node.statement.add(_level_elements.relationship)

            if _attributes.has_children:
                for _child in seed.children:
                    _level_elements = self._get_level_elements(host_obj=seed.obj,obj=_child,rel=_attributes.part_relationship)
                    _entry_node.statement.add(_level_elements.node)
                    _entry_node.statement.add(_level_elements.relationship)

            _submodel.submodel_element.add(_archetype)
            _submodel.submodel_element.add(_entry_node)
            return _submodel
        
        except HierarchyException:
            raise
        except Exception as e:
            raise HierarchyException("Error while creating hierarchy submodel") from e
    
    def _get_device_hierarchies(
            self,
            obj: django_models.Model
            ) -> list[aas_model.Submodel]:
        """Build device-to-device hierarchy submodels (upward to parent bay device and/or downward to installed devices) for *obj*."""

        try:
            _result = []
            _entity_type = get_entity_type(obj)
            if _entity_type != 'devices':
                return _result
            
            _seed = AASHierarchySeed(obj=obj,entity_type=_entity_type, connection=self.connection)

            #1Up possible relationships:
            if obj.position is not None:
                _seed_device2rack = replace(_seed, hierarchy_id='hier_device2rack', parent=obj.rack)
                if _seed_device2rack.parent is None:
                    raise HierarchyException ("Unexpected empty rack field for installed device")
                _result.append(self._get_hierarchy_submodel(_seed_device2rack))
            else:
                _parent_bay = self.occupied_bays.get(obj.pk)
                if _parent_bay is not None:
                    _seed_device2device_up = replace(_seed, hierarchy_id='hier_device2device_up', parent=_parent_bay["Host"])
                    _result.append(self._get_hierarchy_submodel(_seed_device2device_up))

            #1Down relationships:
            _installed_devices = [ bay.installed_device 
                                  for bay in obj.devicebays.filter(installed_device__isnull=False).select_related('installed_device')]
            if _installed_devices:
                _seed_down = replace(_seed, hierarchy_id='hier_device2device_down', children=_installed_devices)
                _result.append(self._get_hierarchy_submodel(_seed_down))
            return _result
        
        except HierarchyException:
            raise
        except Exception as e:
            raise HierarchyException("Error while creating the device2device hierarchy") from e

    def _get_hier_submodel_id(self, obj: django_models.Model, hierarchy_id: str) -> str:
        """Construct the URN submodel ID for a hierarchy submodel of *obj* with the given *hierarchy_id*."""

        try:
            _obj_name = get_object_name(obj)
            _entity_type = get_entity_type(obj)
            _unique_name = f"{sanitize_name_for_urn(_obj_name, _entity_type, obj.pk)}_{obj.pk}"
            return f"urn:{self.urn_namespace}:sm:{_unique_name}_{hierarchy_id}"
        except HierarchyException:
            raise
        except Exception as e:
            raise HierarchyException("Error while constructing the hierarchy submodel ID") from e

    def _get_top_level_devices(self, all_devices: list[django_models.Model])->list[django_models.Model]:
        """
        Given all devices belonging to a rack, returns only the top level installed devices: devices that are installed directly 
        within the rack and not via another device
        """
        try:
            _result = []
            for _device in all_devices:
                if _device.position is None:
                    # device not directly installed (either 
                    # 'Non-racked device' or installed in another 
                    # device via device bay), skipping
                    continue 
                _result.append(_device)
            return _result
        except Exception as e:
            raise HierarchyException("Error while creating top level elements of the full rack hierarchy submodel") from e

    def _get_rack_hierarchies(
            self,
            obj: django_models.Model
            ) -> list[aas_model.Submodel]:
        """
        Build rack hierarchies
        """

        _result = []
        try:
            _entity_type = get_entity_type(obj)
            if _entity_type != 'racks':
                return _result
            _all_devices = obj.devices.all()
            if _all_devices is None:
                return _result
            _top_level_devices = self._get_top_level_devices(all_devices=_all_devices)
            if not _top_level_devices:
                return _result #No hierarchy submodel for racks without installed devices
            _seed = AASHierarchySeed(obj=obj,
                                     entity_type=_entity_type, 
                                     connection=self.connection,
                                     hierarchy_id='hier_rack2devices',
                                     children=_top_level_devices)
            _result.append(self._get_hierarchy_submodel(_seed))
            return _result
        except HierarchyException:
            raise
        except Exception as e:
            raise HierarchyException("Error while creating full rack hierarchy") from e

    def build_hierarchy_submodels(
            self,
            obj: django_models.Model
            ) -> list[aas_model.Submodel]:
        """
        Build all relevant AAS HierarchicalStructures submodels for the given NetBox object.

        The method inspects the entity type of *obj* and produces the appropriate set of
        hierarchy submodels:

        **Devices**
        - ``hier_device2rack`` (``OneUp``) – created when the device is directly
         installed in a rack via an ``IsPartOf`` relationship.
        - ``hier_device2device_up`` (``OneUp``) – created when the device is installed
          inside a device bay, pointing up to the parent device.
        - ``hier_device2device_down`` (``OneDown``) – created when the device has device
          bays with installed child devices, listing those children via ``HasPart``.

        **Racks**
        - ``hier_rack2devices`` (``OneDown``) – lists all devices
          directly mounted in the rack via ``HasPart``.
        
        Args:
            obj: NetBox model instance (``Device``, ``Rack``, …).

        Returns:
            A list of populated ``aas_model.Submodel`` instances.
        """

        _result = []
        _entity_type = get_entity_type(obj)

        match _entity_type:
            case 'devices':
                _result.extend(self._get_device_hierarchies(obj))
            case 'racks':
                _result.extend(self._get_rack_hierarchies(obj))
        return _result

def build_submodels_for_entity(
    obj: django_models.Model,
    entity_type: str,
    connection: AASConnection,
    base_url: str,
    urn_namespace: str = URN_NAMESPACE_DEFAULT
) -> List[aas_model.Submodel]:
    """
    Build all enabled submodels for a NetBox entity.

    Args:
        obj: NetBox model instance (Device, Rack, etc.)
        entity_type: Entity type label ('devices', 'racks', etc.)
        connection: AASConnection instance
        base_url: Base URL for URI generation
        urn_namespace: URN namespace

    Returns:
        List of populated AAS Submodel instances
    """
    # Get enabled submodel configurations with fallback logic
    configs = SubmodelConfiguration.get_for_sync(connection=connection, entity_type=entity_type)

    builder = SubmodelBuilder()
    submodels = []

    for config in configs:
        try:
            submodel = builder.build_submodel(
                obj=obj,
                config=config,
                base_url=base_url,
                urn_namespace=urn_namespace
            )
            if submodel:
                submodels.append(submodel)
                logger.debug(f"Built submodel {sanitize_for_log(config.template.id_short)} for {sanitize_for_log(obj)}")
        except Exception:
            logger.error(f"Failed to build submodel {sanitize_for_log(config.template.id_short)} for {sanitize_for_log(obj)}", exc_info=True)

    #hierarchies:
    try:
        hierarchy_builder = AASHierarchyBuilder(connection=connection,urn_namespace=urn_namespace)
        hierarchies = hierarchy_builder.build_hierarchy_submodels(obj)
        if not hierarchies:
            return submodels
        submodels.extend(hierarchies)
    except HierarchyException as h_ex:
        logger.error(f"When creating hierarchies for object {sanitize_for_log(obj)} the following exception was raised: {str(h_ex)}")
    except Exception:
        logger.error(f"Unexpected error when creating hierarchies for object {sanitize_for_log(obj)}. Hierarchy submodels were not created")

    return submodels
