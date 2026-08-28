"""
Test-only Django app configuration that doesn't require NetBox.
"""
from django.apps import AppConfig


class AASIntegrationTestConfig(AppConfig):
    """Test Django app configuration for aas_integration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aas_integration'
    verbose_name = 'AAS Integration (Test)'
