# Defer imports to avoid issues during test collection
# Import config only when actually needed by NetBox
try:
    from .apps import AASIntegrationConfig as config
except ImportError:
    # During test collection, netbox module may not be available yet
    config = None

try:
    from importlib.metadata import version
    __version__ = version("netbox-aas-integration")
except Exception:
    __version__ = "0.1.0"  # Fallback for development

default_app_config = 'aas_integration.apps.AASIntegrationConfig'
