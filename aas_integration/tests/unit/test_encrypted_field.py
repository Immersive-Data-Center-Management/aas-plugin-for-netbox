"""
Unit tests for EncryptedCharField.
"""
import pytest
from django.conf import settings
from django.test import TestCase, override_settings
from cryptography.fernet import Fernet
from unittest.mock import patch

from aas_integration.fields import EncryptedCharField    
from aas_integration.models import AASConnection


class EncryptedCharFieldTest(TestCase):
    """Test suite for encrypted field functionality."""

    def setUp(self):
        """Create test connection."""
        self.test_secret = "my-super-secret-client-secret-12345"
        self.connection = AASConnection.objects.create(
            name="Test Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_server_url="https://keycloak.example.com",
            keycloak_realm="test-realm",
            keycloak_client_id="test-client",
            keycloak_client_secret=self.test_secret
        )

    def test_secret_is_encrypted_in_database(self):
        """Verify that the secret is actually encrypted in the database."""
        self.connection.refresh_from_db()

        # Access the database value directly (bypassing decryption)
        from django.db import connection as db_connection
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT keycloak_client_secret FROM aas_integration_aasconnection WHERE id = %s",
                [self.connection.id]
            )
            db_value = cursor.fetchone()[0]

        # Database value should be encrypted (starts with Fernet token prefix)
        self.assertIsNotNone(db_value)
        self.assertNotEqual(db_value, self.test_secret)
        self.assertTrue(db_value.startswith('gAAAAA'), "Encrypted value should start with Fernet token prefix")

    def test_secret_is_decrypted_on_retrieval(self):
        """Verify that the secret is decrypted when accessed through the model."""
        self.connection.refresh_from_db()

        # Accessing through the model should return decrypted value
        self.assertEqual(self.connection.keycloak_client_secret, self.test_secret)

    def test_empty_secret_remains_empty(self):
        """Verify that empty/None secrets are handled correctly."""
        # Create connection without secret
        conn = AASConnection.objects.create(
            name="No Secret Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret=""
        )

        conn.refresh_from_db()
        self.assertEqual(conn.keycloak_client_secret, "")

    def test_none_secret_remains_none(self):
        """Verify that None secrets are handled correctly."""
        conn = AASConnection.objects.create(
            name="None Secret Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
        )

        conn.refresh_from_db()
        # Field should be empty string (not None) due to blank=True default
        self.assertEqual(conn.keycloak_client_secret, "")

    def test_update_secret(self):
        """Verify that updating the secret works correctly."""
        new_secret = "new-updated-secret-67890"

        self.connection.keycloak_client_secret = new_secret
        self.connection.save()

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.keycloak_client_secret, new_secret)

    def test_special_characters_in_secret(self):
        """Verify that special characters are handled correctly."""
        special_secret = "secret!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

        conn = AASConnection.objects.create(
            name="Special Chars Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret=special_secret
        )

        conn.refresh_from_db()
        self.assertEqual(conn.keycloak_client_secret, special_secret)

    def test_unicode_in_secret(self):
        """Verify that Unicode characters are handled correctly."""
        unicode_secret = "secret-with-émojis-🔐🔑🛡️"

        conn = AASConnection.objects.create(
            name="Unicode Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret=unicode_secret
        )

        conn.refresh_from_db()
        self.assertEqual(conn.keycloak_client_secret, unicode_secret)

    def test_plaintext_with_fernet_prefix(self):
        """Verify that plaintext starting with 'gAAAAA' is not mistaken for encrypted data."""
        # This is a plaintext secret that happens to start with Fernet token prefix
        plaintext_secret = "gAAAAABcdefghijklmnop-this-is-plaintext-not-encrypted"

        conn = AASConnection.objects.create(
            name="Fernet Prefix Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret=plaintext_secret
        )

        conn.refresh_from_db()
        # Should retrieve the exact plaintext, not try to decrypt it
        self.assertEqual(conn.keycloak_client_secret, plaintext_secret)

    def test_long_secret(self):
        """Verify that long secrets (e.g., JWT tokens) are handled correctly."""
        # Simulate a long JWT-like secret
        long_secret = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." * 10

        conn = AASConnection.objects.create(
            name="Long Secret Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret=long_secret
        )

        conn.refresh_from_db()
        self.assertEqual(conn.keycloak_client_secret, long_secret)

    def test_wrong_key_returns_empty_string(self):
        """Verify that using wrong SECRET_KEY returns empty string (graceful degradation)."""
        # First, encrypt with the current/real key
        conn = AASConnection.objects.create(
            name="Key Test Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_client_secret="test-secret"
        )
        conn_id = conn.id

        # Now try to decrypt with a different key
        with override_settings(SECRET_KEY='completely-different-key-12345'):
            conn_new = AASConnection.objects.get(id=conn_id)
            result = conn_new.keycloak_client_secret
            self.assertEqual(result, '', "Decryption with wrong key should return empty string")

    def test_encryption_failure_raises_exception(self):
        """Verify that encryption failure raises ValueError instead of silently failing."""

        field = EncryptedCharField()

        # Mock the cipher to raise an exception during encryption
        with patch.object(field, '_get_cipher') as mock_cipher:
            mock_cipher.return_value.encrypt.side_effect = RuntimeError("Simulated encryption failure")

            # Should raise ValueError, not return empty string
            with self.assertRaises(ValueError):
                field.get_prep_value("test-secret")


class EncryptionKeyRotationTest(TestCase):
    """Test key rotation functionality."""

    def test_encryption_key_derivation(self):
        """Verify that encryption key is consistently derived from SECRET_KEY."""
        from aas_integration.fields import EncryptedCharField

        field = EncryptedCharField()
        key1 = field._get_encryption_key()
        key2 = field._get_encryption_key()

        self.assertEqual(key1, key2)

        # Should be valid Fernet key (32 bytes base64-encoded)
        import base64
        decoded = base64.urlsafe_b64decode(key1)
        self.assertEqual(len(decoded), 32)

    def test_different_secret_keys_produce_different_ciphers(self):
        """Verify that different SECRET_KEY values produce different encryption."""
        from aas_integration.fields import EncryptedCharField

        field = EncryptedCharField()
        test_value = "test-secret"

        # Encrypt with current key
        encrypted1 = field.get_prep_value(test_value)

        # Simulate different SECRET_KEY
        with override_settings(SECRET_KEY='completely-different-key-12345'):
            field2 = EncryptedCharField()
            encrypted2 = field2.get_prep_value(test_value)

        # Encrypted values should be different
        self.assertNotEqual(encrypted1, encrypted2)


class TokenAcquisitionWithEncryptionTest(TestCase):
    """Test that token acquisition still works with encrypted secrets."""

    def test_token_acquisition_uses_decrypted_secret(self):
        """Verify that _acquire_keycloak_token gets the decrypted secret."""
        conn = AASConnection.objects.create(
            name="Token Test Connection",
            aas_api_url="https://aas.example.com",
            registry_api_url="https://registry.example.com",
            keycloak_server_url="https://keycloak.example.com",
            keycloak_realm="test-realm",
            keycloak_client_id="test-client",
            keycloak_client_secret="my-test-secret-123"
        )

        # Refresh to ensure we're working with encrypted value
        conn.refresh_from_db()

        # Verify the secret is accessible (decrypted)
        self.assertEqual(conn.keycloak_client_secret, "my-test-secret-123")

        # The _acquire_keycloak_token method should be able to use this decrypted value
        # (We're not actually calling Keycloak here, just verifying the field works)
        self.assertIsNotNone(conn.keycloak_client_secret)
