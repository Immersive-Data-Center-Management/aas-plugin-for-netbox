from urllib.parse import urlsplit
import uuid
import logging

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from .fields import EncryptedCharField
from .logging_utils import sanitize_for_log
from netbox.plugins import get_plugin_config

logger = logging.getLogger(__name__)


# Supported entity types for AAS synchronization
ENTITY_TYPE_CHOICES = [
    ('devices', _('Devices')),
    ('racks', _('Racks')),
]

# Set of valid entity type keys (for validation in views)
VALID_ENTITY_TYPES = frozenset(key for key, _ in ENTITY_TYPE_CHOICES)
class AASSyncModes:
    MERGE = "M"
    OVERWRITE = "O"

    SYNC_MODE_DESC = [{"value": MERGE, "label": 'Merge', "description": "For existing shells only missing submodels are added." },
            {"value": OVERWRITE, "label": 'Overwrite', "description": "The content of existing shells in the AAS is fully replaced by the Netbox content " }]

class AASConnection(models.Model):
    """Model for storing AAS connection credentials and configuration"""

    scheme = 'HTTP' if get_plugin_config('aas_integration', 'insecure_connections') is True else 'HTTPS'

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_('Unique name for this AAS connection')
    )

    description = models.TextField(
        blank=True,
        help_text=_('Description of this AAS environment')
    )

    aas_api_url = models.CharField(
        max_length=255,
        verbose_name=_('AAS API URL'),
        help_text=_('%(scheme)s URL of the AAS Environment API') % {"scheme": scheme}
    )

    registry_api_url = models.CharField(
        max_length=255,
        verbose_name=_('Registry API URL'),
        help_text=_('%(scheme)s URL of the AAS Registry') % {"scheme": scheme}
    )

    discovery_api_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Discovery API URL'),
        help_text=_('%(scheme)s URL of the AAS Discovery Service. Leave empty to skip discovery registration.') % {"scheme": scheme}
    )

    # Keycloak OAuth2 Configuration (required for BaSyx 2.0)
    keycloak_server_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Keycloak Server URL'),
        help_text=_('Keycloak server %(scheme)s URL') % {"scheme": scheme}
    )

    keycloak_realm = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Keycloak Realm'),
        help_text=_('Keycloak realm name (e.g., BaSyx-Test)')
    )

    keycloak_client_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Keycloak Client ID'),
        help_text=_('Keycloak client ID for authentication')
    )

    keycloak_client_secret = EncryptedCharField(
        blank=True,
        help_text=_('Keycloak client secret (encrypted)')
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this connection is enabled')
    )

    auto_sync_enabled = models.BooleanField(
        default=True,
        help_text=_('Automatically sync device changes to AAS in real-time')
    )

    auto_delete_enabled = models.BooleanField(
        default=False,
        help_text=_('Automatically delete AAS shells when devices are deleted from NetBox')
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_('Use this connection for automatic synchronization operations')
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created')
    )

    last_modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Modified')
    )

    last_tested = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Tested')
    )

    aas_id_field = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('AAS ID Field'),
        help_text=_('Custom field where the assets AAS ID should be stored')
    )

    aas_link = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('AAS link'),
        help_text=_('Custom field where the link to the AAS should be stored')
    )

    aas_ui_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('AAS UI URL'),
        help_text=_('HTTPS URL of the AAS Environment UI')
    )


    class Meta:
        verbose_name = _('AAS Connection')
        verbose_name_plural = _('AAS Connections')
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        """
        Validate that all URLs use the correct protocol.
        HTTPS is required unless the 'insecure_connections' plugin config is enabled,
        in which case HTTP is also accepted (for development/testing purposes).
        """
        super().clean()

        # Disable https checks if config parameter is set
        insecure_connection = get_plugin_config("aas_integration", "insecure_connections")
       
        https_validator = URLValidator(schemes=['https'])
        
        url_fields = [
            ('aas_api_url', self.aas_api_url),
            ('registry_api_url', self.registry_api_url),
        ]
        
        if self.discovery_api_url:
            url_fields.append(('discovery_api_url', self.discovery_api_url))
        
        if self.keycloak_server_url:
            url_fields.append(('keycloak_server_url', self.keycloak_server_url))
        
        if self.aas_ui_url:
            url_fields.append(('aas_ui_url', self.aas_ui_url))
        
        errors = {}
        for field_name, url in url_fields:
            if not url:
                continue
            try:
                if not insecure_connection:
                    https_validator(url)
                parts = urlsplit(url)
                if not parts.netloc.strip():
                    errors[field_name] = ValidationError(_('URL must include a host'), code='invalid_host')
                    continue
            except ValidationError:
                errors[field_name] = ValidationError(
                    _('Only valid HTTPS URLs with a host are allowed. Please use https:// with a valid domain.'),
                    code='invalid_protocol',
                )
        
        if errors:
            raise ValidationError(errors)

    def get_auth_headers(self):
        """Returns authentication headers for AAS API requests (Keycloak OAuth2 only)"""
        
        headers = {}
        token = self._acquire_keycloak_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            logger.error(f"Failed to acquire Keycloak token for connection {sanitize_for_log(self.name)}")

        return headers

    def _acquire_keycloak_token(self):
        """
        Acquire an OAuth2 access token from Keycloak using client credentials flow.
        
        Returns:
            str: Access token if successful, None otherwise
        """
        import requests
        
        
        if not all([self.keycloak_server_url, self.keycloak_realm,
                   self.keycloak_client_id, self.keycloak_client_secret]):
            logger.error(f"Incomplete Keycloak configuration for {sanitize_for_log(self.name)}")
            return None

        try:
            token_url = f"{self.keycloak_server_url}/realms/{self.keycloak_realm}/protocol/openid-connect/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.keycloak_client_id,
                'client_secret': self.keycloak_client_secret
            }

            response = requests.post(
                token_url,
                data=data,
                timeout=10
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                if access_token:
                    logger.info(f"Successfully acquired Keycloak token for {sanitize_for_log(self.name)}")
                    return access_token
                else:
                    logger.error(f"No access_token in Keycloak response for {sanitize_for_log(self.name)}")
                    return None
            else:
                logger.error(f"Keycloak token request failed for {sanitize_for_log(self.name)}: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException:
            logger.error(f"Network error acquiring Keycloak token for {sanitize_for_log(self.name)}")
            return None
        except Exception:
            logger.exception(f"Unexpected error acquiring Keycloak token for {sanitize_for_log(self.name)}")
            return None


class SubmodelTemplate(models.Model):
    """
    Template definition for an AAS Submodel.
    Can be imported from IDTA JSON specs or defined as custom.
    """
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idta_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('IDTA Number'),
        help_text=_('IDTA specification number (e.g., "IDTA 02006-3-0")')
    )
    template_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Template ID'),
        help_text=_('Unique template identifier (e.g., "https://admin-shell.io/idta-02003-2-0")')
    )

    # Metadata
    id_short = models.CharField(
        max_length=128,
        verbose_name=_('ID Short'),
        help_text=_('Short identifier used in AAS (e.g., "TechnicalData")')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Name'),
        help_text=_('Human-readable name')
    )
    description = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Multi-language description: {"en": "...", "de": "..."}')
    )

    # Versioning
    version = models.CharField(
        max_length=20,
        default="1.0",
        verbose_name=_('Version')
    )
    revision = models.CharField(
        max_length=20,
        default="0",
        verbose_name=_('Revision')
    )

    # Semantic Information
    semantic_id = models.CharField(
        max_length=255,
        verbose_name=_('Semantic ID'),
        help_text=_('Primary semantic ID (e.g., "0173-1#01-AHX837#002")')
    )
    supplemental_semantic_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Supplemental Semantic IDs'),
        help_text=_('List of supplemental semantic ID URLs')
    )

    # AAS Kind
    kind = models.CharField(
        max_length=20,
        choices=[
            ('Template', _('Template')),
            ('Instance', _('Instance'))
        ],
        default='Template',
        verbose_name=_('Kind'),
        help_text=_('AAS kind: Template for definitions, Instance for actual data')
    )

    # Note: The following IDTA fields are not currently implemented:
    # - extensions: AAS extensions (could be added as JSONField if needed)
    # - embeddedDataSpecifications: Full IEC 61360 data specifications
    #   (we store qualifiers in SubmodelElement but not complete data specs)

    # Template Source
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('IDTA', _('IDTA Standard')),
            ('CUSTOM', _('Custom Definition'))        ],
        default='CUSTOM',
        verbose_name=_('Source Type')
    )

    # Applicability
    applicable_entity_types = models.JSONField(
        default=list,
        verbose_name=_('Applicable Entity Types'),
        help_text=_('List of entity types this can apply to: ["devices", "racks", "cables", ...]')
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this template is active')
    )
    is_built_in = models.BooleanField(
        default=False,
        verbose_name=_('Is Built-in'),
        help_text=_('Built-in templates cannot be deleted')
    )

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created')
    )
    last_modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Modified')
    )

    class Meta:
        ordering = ['id_short', 'version']
        verbose_name = _('Submodel Template')
        verbose_name_plural = _('Submodel Templates')

    def __str__(self):
        if self.idta_number:
            return f"{self.id_short} ({self.idta_number})"
        return f"{self.id_short} (Custom)"


class SubmodelElement(models.Model):
    """
    Definition of a single element within a Submodel.
    Can be nested within collections.
    """
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        SubmodelTemplate,
        on_delete=models.CASCADE,
        related_name='elements',
        verbose_name=_('Template')
    )

    # Hierarchy
    parent_element = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='child_elements',
        verbose_name=_('Parent Element'),
        help_text=_('Parent element if nested in a Collection or List')
    )

    # Element Definition
    id_short = models.CharField(
        max_length=128,
        verbose_name=_('ID Short'),
        help_text=_('Short identifier (e.g., "ManufacturerName")')
    )
    element_type = models.CharField(
        max_length=50,
        choices=[
            ('Property', _('Property')),
            ('MultiLanguageProperty', _('Multi-Language Property')),
            ('Range', _('Range')),
            ('Blob', _('Blob')),
            ('File', _('File')),
            ('ReferenceElement', _('Reference Element')),
            ('SubmodelElementCollection', _('Collection')),
            ('SubmodelElementList', _('List')),
            ('Entity', _('Entity')),
            ('Operation', _('Operation')),
            ('Capability', _('Capability')),
        ],
        verbose_name=_('Element Type'),
        help_text=_('AAS element type')
    )

    # Display Information
    display_name = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Display Name'),
        help_text=_('Multi-language display names: {"en": "...", "de": "..."}')
    )
    description = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Multi-language descriptions')
    )

    # Semantic Information
    semantic_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Semantic ID'),
        help_text=_('Semantic ID (e.g., "0173-1#02-AAO677#004")')
    )
    supplemental_semantic_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Supplemental Semantic IDs')
    )

    # Value Type (for Property, Range)
    value_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('xs:string', _('String')),
            ('xs:int', _('Integer')),
            ('xs:double', _('Double')),
            ('xs:boolean', _('Boolean')),
            ('xs:dateTime', _('DateTime')),
            ('xs:anyURI', _('Any URI')),
        ],
        verbose_name=_('Value Type'),
        help_text=_('Data type for Property elements')
    )

    # Cardinality/Multiplicity
    cardinality = models.CharField(
        max_length=20,
        choices=[
            ('One', _('Exactly One (1)')),
            ('ZeroToOne', _('Zero or One (0..1)')),
            ('OneToMany', _('One or More (1..*)')),
            ('ZeroToMany', _('Zero or More (0..*)')),
        ],
        default='One',
        verbose_name=_('Cardinality'),
        help_text=_('Cardinality constraint')
    )

    # Category (CONSTANT, PARAMETER, VARIABLE)
    category = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('CONSTANT', _('Constant')),
            ('PARAMETER', _('Parameter')),
            ('VARIABLE', _('Variable')),
        ],
        verbose_name=_('Category')
    )

    # Additional Configuration (JSON for flexibility)
    qualifiers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Qualifiers'),
        help_text=_('AAS qualifiers as JSON array')
    )

    # Ordering within parent
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order')
    )

    class Meta:
        ordering = ['template', 'order', 'id_short']
        verbose_name = _('Submodel Element')
        verbose_name_plural = _('Submodel Elements')

    def __str__(self):
        return f"{self.template.id_short}.{self.id_short} ({self.element_type})"


class SubmodelConfiguration(models.Model):
    """
    Configuration specifying which submodels to use for which entity types.

    Supports a default/override pattern:
    - Global defaults: connection=None (applies to all connections by default)
    - Connection-specific overrides: connection=<specific> (overrides global for that connection)

    When syncing, the system checks connection-specific configs first,
    then falls back to global defaults if none exist.
    """
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Connection Context (Optional)
    connection = models.ForeignKey(
        'AASConnection',
        on_delete=models.CASCADE,
        related_name='submodel_configs',
        verbose_name=_('Connection'),
        help_text=_('AAS connection this configuration applies to. Leave empty for global defaults.'),
        null=True,
        blank=True
    )

    # Entity Type
    entity_type = models.CharField(
        max_length=50,
        choices=ENTITY_TYPE_CHOICES,
        verbose_name=_('Entity Type'),
        help_text=_('NetBox model type (e.g., "devices")')
    )

    # Submodel Selection
    template = models.ForeignKey(
        SubmodelTemplate,
        on_delete=models.CASCADE,
        related_name='configurations',
        verbose_name=_('Template')
    )

    # Enablement
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Is Enabled'),
        help_text=_('Whether this submodel is active for sync')
    )

    # Priority/Ordering
    priority = models.PositiveIntegerField(
        default=100,
        verbose_name=_('Priority'),
        help_text=_('Build order (lower = earlier). Important for dependencies like RackUsage.')
    )

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created')
    )
    last_modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Modified')
    )

    class Meta:
        ordering = ['connection', 'entity_type', 'priority']
        unique_together = [['connection', 'entity_type', 'template']]
        verbose_name = _('Submodel Mapping Configuration')
        verbose_name_plural = _('Submodel Mapping Configurations')

    def __str__(self):
        conn_name = self.connection.name if self.connection else "Global Default"
        return f"{conn_name} - {self.entity_type}: {self.template.id_short}"

    @classmethod
    def get_for_sync(cls, connection, entity_type):
        """
        Get enabled SubmodelConfigurations for syncing, with fallback logic.

        Priority order:
        1. Connection-specific configurations (if any exist and are enabled)
        2. Global default configurations (connection=None)

        Args:
            connection: AASConnection instance
            entity_type: Entity type label ('devices', 'racks', etc.)

        Returns:
            QuerySet of SubmodelConfiguration instances
        """
        # Try connection-specific configs first
        connection_configs = cls.objects.filter(
            connection=connection,
            entity_type=entity_type,
            is_enabled=True
        ).select_related('template').prefetch_related(
            'template__elements',
            'field_mappings',
            'field_mappings__submodel_element'
        ).order_by('priority')

        if connection_configs.exists():
            return connection_configs

        # Fall back to global defaults
        global_configs = cls.objects.filter(
            connection=None,
            entity_type=entity_type,
            is_enabled=True
        ).select_related('template').prefetch_related(
            'template__elements',
            'field_mappings',
            'field_mappings__submodel_element'
        ).order_by('priority')

        return global_configs


class FieldMapping(models.Model):
    """
    Mapping from NetBox model fields to AAS Submodel Elements.
    Uses JSONPath for field extraction (security-safe, no eval).
    """
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Context
    configuration = models.ForeignKey(
        SubmodelConfiguration,
        on_delete=models.CASCADE,
        related_name='field_mappings',
        verbose_name=_('Configuration')
    )

    # Target Element
    submodel_element = models.ForeignKey(
        SubmodelElement,
        on_delete=models.CASCADE,
        related_name='field_mappings',
        verbose_name=_('Submodel Element')
    )

    # Source Field Definition
    # JSONPath Expression (e.g., "$.device_type.manufacturer.name")
    jsonpath_expression = models.TextField(
        blank=True,
        verbose_name=_('JSONPath Expression'),
        help_text=_('JSONPath expression for field access (e.g., "$.device_type.manufacturer.name")')
    )

    # Default/Fallback
    default_value = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Default Value'),
        help_text=_('Default value if field is None/empty')
    )

    # Transformation
    transform_function = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('', _('None')),
            ('uppercase', _('Convert to Uppercase')),
            ('lowercase', _('Convert to Lowercase')),
            ('strip_protocol', _('Strip URL Protocol')),
            ('sanitize_urn', _('Sanitize for URN')),
            ('format_uri', _('Format as URI')),
        ],
        verbose_name=_('Transform Function'),
        help_text=_('Built-in transformation to apply')
    )

    # Multi-language Handling
    is_multilanguage = models.BooleanField(
        default=False,
        verbose_name=_('Is Multilanguage'),
        help_text=_('Whether this mapping produces multi-language text')
    )

    language_code = models.CharField(
        max_length=5,
        default='en',
        verbose_name=_('Language Code'),
        help_text=_('Language code for multilanguage properties')
    )

    # Ordering
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order')
    )

    class Meta:
        ordering = ['configuration', 'submodel_element', 'order']
        verbose_name = _('Field Mapping')
        verbose_name_plural = _('Field Mappings')

    def clean(self):
        """Validate that at least one of jsonpath_expression or default_value is set."""
        from django.core.exceptions import ValidationError
        if not self.jsonpath_expression and not self.default_value:
            raise ValidationError(
                'At least one of JSONPath Expression or Default Value must be provided.'
            )

    def __str__(self):
        expr = self.jsonpath_expression or self.default_value
        return f"{self.configuration.template.id_short}.{self.submodel_element.id_short} <- {expr[:50]}"


class EntityTypeConfiguration(models.Model):
    """
    User-configurable registry of which NetBox models should sync to AAS.
    Allows future extensibility to support any NetBox model without code changes.
    """
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Connection Context
    connection = models.ForeignKey(
        'AASConnection',
        on_delete=models.CASCADE,
        related_name='entity_type_configs',
        verbose_name=_('Connection')
    )

    # Content Type (references Django model)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Content Type'),
        help_text=_('Django model to sync (e.g., Device, Rack, Cable)')
    )

    # Entity Type Label
    entity_type_label = models.CharField(
        max_length=50,
        verbose_name=_('Entity Type Label'),
        help_text=_('Label used in configurations (e.g., "devices", "racks")')
    )

    # Enablement
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Is Enabled'),
        help_text=_('Whether sync is enabled for this model type')
    )

    # Builder Configuration
    builder_class = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Builder Class'),
        help_text=_('Optional custom builder class (defaults to AASShellBuilder)')
    )

    # Query Optimization
    select_related_fields = models.JSONField(
        default=list,
        verbose_name=_('Select Related Fields'),
        help_text=_('List of related fields to prefetch (e.g., ["device_type", "site"])')
    )

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created')
    )
    last_modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Modified')
    )

    class Meta:
        ordering = ['connection', 'entity_type_label']
        unique_together = [['connection', 'content_type']]
        verbose_name = _('Entity Type Configuration')
        verbose_name_plural = _('Entity Type Configurations')

    def __str__(self):
        return f"{self.connection.name} - {self.entity_type_label}"

