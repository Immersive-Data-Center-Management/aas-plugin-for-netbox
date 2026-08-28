"""
Integration test fixtures for AAS Integration plugin.

Provides fixtures for test BaSyx and Keycloak configuration.
"""
import os
import pytest


@pytest.fixture(scope='session')
def test_basyx_urls():
    """BaSyx service URLs for test environment"""
    return {
        'aas_env': os.getenv('TEST_AAS_API_URL', 'http://aas-env-test:8081'),
        'aas_registry': os.getenv('TEST_AAS_REGISTRY_URL', 'http://aas-registry-test:8080'),
        'sm_registry': os.getenv('TEST_SM_REGISTRY_URL', 'http://sm-registry-test:8080'),
        'discovery': os.getenv('TEST_DISCOVERY_API_URL', 'http://aas-discovery-test:8080'),
    }


@pytest.fixture
def test_aas_connection(db, test_basyx_urls):
    """
    Create a test AAS connection using Django model.

    This uses the plugin's actual credential handling (encryption, etc.)
    The client secret is overridden in postgres/01-keycloak-test.sql to be
    obviously test-only and different from dev credentials.
    """
    from aas_integration.models import AASConnection

    # Test-only secret set in postgres/01-keycloak-test.sql
    # Clearly fake to avoid confusion with production-like credentials
    keycloak_client_secret = 'test-secret-do-not-use-in-production-00000000'

    connection = AASConnection.objects.create(
        name='Test BaSyx Environment',
        aas_api_url=test_basyx_urls['aas_env'],
        registry_api_url=test_basyx_urls['aas_registry'],
        discovery_api_url=test_basyx_urls['discovery'],
        keycloak_server_url=os.getenv('TEST_KEYCLOAK_URL', 'http://keycloak-test:8080'),
        keycloak_realm=os.getenv('TEST_KEYCLOAK_REALM', 'basyx-dev'),
        keycloak_client_id=os.getenv('TEST_KEYCLOAK_CLIENT_ID', 'netbox'),
        keycloak_client_secret=keycloak_client_secret,  # Gets encrypted by model
        is_active=True,
        is_default=True,
        auto_sync_enabled=False,  # Disable auto-sync for tests
    )

    yield connection

    # Cleanup
    connection.delete()
