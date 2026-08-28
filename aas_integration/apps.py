from netbox.plugins import PluginConfig

try:
    from importlib.metadata import version
    __version__ = version("netbox-aas-integration")
except Exception:
    __version__ = "0.1.0"


def create_aas_custom_fields(sender, **kwargs):
    """Create AAS custom fields after all migrations have completed."""
    from django.contrib.contenttypes.models import ContentType
    from extras.models import CustomField

    # Get content types for rack and device
    try:
        rack_ct = ContentType.objects.get(app_label='dcim', model='rack')
        device_ct = ContentType.objects.get(app_label='dcim', model='device')
    except ContentType.DoesNotExist:
        return  # DCIM not ready yet

    # Create aas_id_1 custom field
    cf_id, created = CustomField.objects.get_or_create(
        name='aas_id_1',
        defaults={
            'type': 'text',
            'label': 'AAS ID',
            'description': 'Asset Administration Shell ID',
            'required': False,
        }
    )
    if created or not cf_id.object_types.filter(pk=rack_ct.pk).exists():
        cf_id.object_types.add(rack_ct, device_ct)

    # Create aas_link_1 custom field
    cf_link, created = CustomField.objects.get_or_create(
        name='aas_link_1',
        defaults={
            'type': 'url',
            'label': 'AAS Link',
            'description': 'Link to AAS viewer',
            'required': False,
        }
    )
    if created or not cf_link.object_types.filter(pk=rack_ct.pk).exists():
        cf_link.object_types.add(rack_ct, device_ct)


class AASIntegrationConfig(PluginConfig):
    name = 'aas_integration'
    verbose_name = 'AAS Integration'
    description = 'NetBox plugin for Asset Administration Shell (AAS) integration'
    version = __version__
    min_version = '4.0'
    author = 'BaSyx Team'
    author_email = 'basyx@example.com'
    base_url = 'aas-integration'
    release_track = 'dev'
    required_settings = []
    default_settings = {
        'insecure_connections': False
    }

    def ready(self):
        super().ready()

        # Import signals to register them
        from . import signals

        from .navigation import menu_items
        from netbox.plugins.registration import register_menu_items
        register_menu_items(self.verbose_name, menu_items)

        # Register post_migrate handler to create custom fields
        from django.db.models.signals import post_migrate
        post_migrate.connect(create_aas_custom_fields, sender=self)

