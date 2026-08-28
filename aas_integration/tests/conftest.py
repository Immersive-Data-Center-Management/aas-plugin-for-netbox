"""
Root conftest for all tests.

Note: No sys.path manipulation needed since the package is installed via 'pip install -e .[test]'
"""
import pytest
import os
import django
import sys
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from unittest.mock import MagicMock

def mock_get_plugin_config(plugin_name: str, parameter: str, default=None):
    # Hacky fix for get_plugin_config, as netbox is not available in unit tests
    if plugin_name == "aas_integration" and parameter == "insecure_connections":
        return False
    
    raise ImproperlyConfigured("Netbox plugin configuration parameters are not available in unit tests!")

mock_netbox = MagicMock()
mock_netbox.plugins.get_plugin_config = mock_get_plugin_config

sys.modules.setdefault("netbox", mock_netbox)
sys.modules.setdefault("netbox.plugins", mock_netbox.plugins)

def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'aas_integration.tests.test_apps.AASIntegrationTestConfig',
            ],
            SECRET_KEY='test-secret-key-for-unit-tests',
            USE_TZ=True,
        )
        django.setup()
