"""
Custom Django field for encrypting sensitive data at rest.

Uses Fernet symmetric encryption (AES-128 in CBC mode with HMAC for authentication).
The encryption key is derived from Django's SECRET_KEY.
"""
import base64
import hashlib
import logging

from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet, InvalidToken


class EncryptedCharField(models.TextField):
    """
    Django field that automatically encrypts data before storing and decrypts on retrieval.

    Uses Fernet (symmetric encryption) with a key derived from Django's SECRET_KEY.
    Stored as base64-encoded encrypted text in the database.

    Security notes:
    - Encryption key is derived from Django SECRET_KEY (must be kept secure)
    - Uses authenticated encryption (HMAC) to prevent tampering
    - Encrypted values are longer than plaintext (base64 overhead + IV + HMAC)

    Usage:
        class MyModel(models.Model):
            secret = EncryptedCharField(max_length=255, blank=True)
    """

    description = "Encrypted text field"

    def __init__(self, *args, **kwargs):
        # Note: max_length in kwargs is ignored for TextField base
        # but we accept it for compatibility
        kwargs.pop('max_length', None)
        super().__init__(*args, **kwargs)

    def _get_encryption_key(self):
        """
        Derive a Fernet-compatible encryption key from Django's SECRET_KEY.

        Uses PBKDF2-HMAC-SHA256 with 600,000 iterations for proper key derivation.
        This provides resistance against brute-force attacks on weak SECRET_KEY values.

        Returns:
            bytes: 32-byte URL-safe base64-encoded key for Fernet
        """
        secret_key = settings.SECRET_KEY.encode('utf-8')

        key_material = hashlib.pbkdf2_hmac(
            'sha256',
            secret_key,
            b'netbox_aas_integration_encryption_key',  # Application-specific salt
            iterations=600_000,  # OWASP recommendation for PBKDF2-HMAC-SHA256
            dklen=32  # 32 bytes for Fernet
        )

        # Fernet expects URL-safe base64-encoded 32-byte key
        return base64.urlsafe_b64encode(key_material)

    def _get_cipher(self):
        """Get Fernet cipher instance."""
        return Fernet(self._get_encryption_key())

    def from_db_value(self, value, expression, connection):
        """
        Decrypt value when loading from database.

        Args:
            value: Encrypted value from database (or None)
            expression: Query expression
            connection: Database connection

        Returns:
            Decrypted plaintext string or None
        """
        if value is None or value == '':
            return value

        try:
            cipher = self._get_cipher()
            # Value is stored as base64-encoded encrypted bytes
            encrypted_bytes = value.encode('utf-8')
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except (InvalidToken, ValueError, UnicodeDecodeError) as e:
            # Log error but don't crash - return empty string
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to decrypt field value: {type(e).__name__}")
            return ''

    def get_prep_value(self, value):
        """
        Encrypt value before saving to database.

        Args:
            value: Plaintext value to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            ValueError: If encryption fails for any reason
        """
        if value is None or value == '':
            return value

        logger = logging.getLogger(__name__)

        try:
            cipher = self._get_cipher()
            # Encrypt and encode as UTF-8 string for storage
            plaintext_bytes = value.encode('utf-8')
            encrypted_bytes = cipher.encrypt(plaintext_bytes)
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encrypt field value: {type(e).__name__}")
            raise ValueError(f"Encryption failed: {type(e).__name__}") from e

    def to_python(self, value):
        """
        Convert value to Python string.

        This handles form input and deserialization. Form fields always receive
        plaintext, so we simply pass through the value. Decryption is handled
        exclusively by from_db_value().

        Args:
            value: Input value (always plaintext from forms)

        Returns:
            String value or None
        """
        if value is None:
            return value
        return str(value)

    def deconstruct(self):
        """
        Return field definition for migrations.
        """
        name, path, args, kwargs = super().deconstruct()
        # Change path to TextField for migration files
        return name, 'django.db.models.TextField', args, kwargs
