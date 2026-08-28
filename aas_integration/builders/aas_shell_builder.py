"""
AAS Shell Builder that constructs complete AAS shells with submodels.
Entry point for the dynamic submodel building system.
"""
import logging
from typing import List, Optional, Tuple

from basyx.aas import model as aas_model
from django.db import models as django_models

from ..models import AASConnection
from ..defaults import BASE_URL_DEFAULT, URN_NAMESPACE_DEFAULT
from ..services.utils import sanitize_name_for_urn, strip_url_protocol
from .submodel_builder import build_submodels_for_entity

logger = logging.getLogger(__name__)


class AASShellBuilder:
    """
    Builder for creating AAS shells with dynamically configured submodels.

    This builder queries SubmodelConfiguration records from the database and builds
    all enabled submodels for a given entity type.

    Usage:
        builder = AASShellBuilder()
        aas, submodels = builder.build_aas_for_entity(
            obj=device,
            entity_type='devices',
            connection=aas_connection,
            base_url='netbox.local',
            urn_namespace='apeirora.eu'
        )
    """

    def build_aas_for_entity(
        self,
        obj: django_models.Model,
        entity_type: str,
        connection: AASConnection,
        base_url: str = BASE_URL_DEFAULT,
        urn_namespace: str = URN_NAMESPACE_DEFAULT
    ) -> Tuple[Optional[aas_model.AssetAdministrationShell], List[aas_model.Submodel]]:
        """
        Build complete AAS shell with all configured submodels for an entity.

        Args:
            obj: NetBox model instance (Device, Rack, Cable, etc.)
            entity_type: Entity type label ('devices', 'racks', 'cables', etc.)
            connection: AASConnection instance for configuration lookup
            base_url: Base URL for URI generation (default: 'netbox.local')
            urn_namespace: URN namespace for AAS IDs (default: 'apeirora.eu')

        Returns:
            Tuple of (AAS shell, list of Submodels)
            Returns (None, []) if entity cannot be processed

        Example:
            builder = AASShellBuilder()
            aas, submodels = builder.build_aas_for_entity(device, 'devices', connection)
        """
        # Sanitize base_url
        base_url = strip_url_protocol(base_url)

        # Generate unique name for this entity
        unique_name = self._generate_unique_name(obj, entity_type)

        # Generate AAS ID
        aas_id = f"urn:{urn_namespace}:aas:{entity_type}:{unique_name}"

        # Build all enabled submodels for this entity
        submodels = build_submodels_for_entity(
            obj=obj,
            entity_type=entity_type,
            connection=connection,
            base_url=base_url,
            urn_namespace=urn_namespace
        )

        # Create submodel references
        submodel_refs = set()
        for submodel in submodels:
            submodel_refs.add(aas_model.ModelReference.from_referable(submodel))

        # Create AAS shell
        aas = aas_model.AssetAdministrationShell(
            id_=aas_id,
            id_short=unique_name,
            asset_information=aas_model.AssetInformation(
                asset_kind=aas_model.AssetKind.INSTANCE,
                global_asset_id=aas_id
            ),
            submodel=submodel_refs
        )

        logger.info(
            f"Built AAS for {entity_type} '{obj}' with {len(submodels)} submodels: "
            f"{[s.id_short for s in submodels]}"
        )

        return aas, submodels

    def _generate_unique_name(self, obj: django_models.Model, entity_type: str) -> str:
        """
        Generate unique identifier for an entity.

        Args:
            obj: NetBox model instance
            entity_type: Entity type label

        Returns:
            Sanitized unique name suitable for URN/ID generation
        """
        obj_name = getattr(obj, 'name', None) or str(obj)
        obj_id = obj.pk

        sanitized_name = sanitize_name_for_urn(obj_name, entity_type, obj_id)
        return f"{sanitized_name}_{obj_id}"
