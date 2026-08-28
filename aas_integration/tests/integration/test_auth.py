"""
Simple integration test: OAuth2 authentication with Keycloak and BaSyx.

This test validates the most critical integration point:
1. Use AASConnection model to acquire OAuth2 token from Keycloak
2. Use token to authenticate against BaSyx AAS Environment API
3. Verify ABAC authorization allows access

If this passes, it proves:
- Keycloak is running and configured correctly
- BaSyx OIDC trustlist is configured correctly
- BaSyx ABAC rules allow authenticated access
- Plugin's credential encryption/handling works
- Network connectivity between services works
"""
import pytest
import requests


@pytest.mark.django_db
def test_aas_connection_token_acquisition(test_aas_connection):
    """
    Test that AASConnection can acquire an OAuth2 token from Keycloak.

    This validates:
    - AASConnection model's _acquire_keycloak_token() method works
    - Keycloak is reachable
    - Realm and client exist
    - Client secret is correct
    - Credential encryption/decryption works
    """
    # Use the plugin's actual token acquisition method
    token = test_aas_connection._acquire_keycloak_token()

    assert token is not None, "Failed to acquire token"
    assert len(token) > 0, "Token is empty"
    assert isinstance(token, str), "Token should be a string"


@pytest.mark.django_db
def test_aas_connection_auth_headers(test_aas_connection):
    """
    Test that AASConnection can generate authentication headers.

    This validates the get_auth_headers() method which is used
    throughout the plugin for authenticated API calls.
    """
    headers = test_aas_connection.get_auth_headers()

    assert 'Authorization' in headers, "Missing Authorization header"
    assert headers['Authorization'].startswith('Bearer '), "Authorization should use Bearer token"

    # Extract token part
    token = headers['Authorization'].split(' ')[1]
    assert len(token) > 0, "Token is empty"


@pytest.mark.django_db
def test_basyx_authenticated_access(test_aas_connection, test_basyx_urls):
    """
    Test that AASConnection token works for authenticated BaSyx API access.

    This validates:
    - BaSyx OIDC trustlist accepts tokens from Keycloak
    - BaSyx ABAC rules allow authenticated access
    - Plugin's auth flow works end-to-end
    - Network connectivity between NetBox → BaSyx works
    """
    # Get auth headers using plugin's method
    headers = test_aas_connection.get_auth_headers()

    # Call BaSyx API with token
    aas_env_url = test_basyx_urls['aas_env']

    response = requests.get(
        f"{aas_env_url}/shells",
        headers=headers,
        timeout=10
    )

    # Success: 200 (has shells) or 404 (no shells yet, but auth worked)
    assert response.status_code in [200, 404], \
        f"BaSyx API call failed: {response.status_code} - {response.text}"

    # If we got 200, verify response structure
    if response.status_code == 200:
        data = response.json()
        assert 'result' in data or isinstance(data, list), "Unexpected BaSyx response format"


@pytest.mark.django_db
def test_basyx_unauthenticated_access_denied(test_basyx_urls):
    """
    Test that BaSyx denies access without authentication.

    This validates that ABAC is enforcing authorization (not just accepting everything).
    """
    aas_env_url = test_basyx_urls['aas_env']

    # Try to access without token
    response = requests.get(
        f"{aas_env_url}/shells",
        timeout=10
    )

    # Should be denied (401 Unauthorized or 403 Forbidden)
    assert response.status_code in [401, 403], \
        f"BaSyx should deny unauthenticated access, got: {response.status_code}"
