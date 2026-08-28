"""
Management command to re-encrypt AAS connection secrets after Django SECRET_KEY rotation.

Usage:
    python manage.py rotate_aas_encryption_key --old-key "old-secret-key-value"

This command:
1. Decrypts all secrets using the old SECRET_KEY
2. Re-encrypts them using the new SECRET_KEY
3. Saves the re-encrypted values back to the database

IMPORTANT: Only run this after changing Django's SECRET_KEY in settings.
"""
import base64
import hashlib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from cryptography.fernet import Fernet, InvalidToken

from aas_integration.models import AASConnection


class Command(BaseCommand):
    help = 'Re-encrypt AAS connection secrets after SECRET_KEY rotation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--old-key',
            type=str,
            required=True,
            help='The old Django SECRET_KEY value used to encrypt existing secrets'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test decryption without saving changes'
        )

    def _get_cipher_for_key(self, secret_key_value):
        """Create Fernet cipher from a SECRET_KEY value."""
        secret_key_bytes = secret_key_value.encode('utf-8')
        key_material = hashlib.sha256(secret_key_bytes).digest()
        fernet_key = base64.urlsafe_b64encode(key_material)
        return Fernet(fernet_key)

    def handle(self, *args, **options):
        old_secret_key = options['old_key']
        dry_run = options['dry_run']

        if old_secret_key == settings.SECRET_KEY:
            raise CommandError(
                'Old key is the same as current SECRET_KEY. '
                'This command is only needed after SECRET_KEY rotation.'
            )

        old_cipher = self._get_cipher_for_key(old_secret_key)
        new_cipher = self._get_cipher_for_key(settings.SECRET_KEY)

        # Find all connections with encrypted secrets
        connections = AASConnection.objects.exclude(keycloak_client_secret='')
        total_connections = connections.count()

        if total_connections == 0:
            self.stdout.write(self.style.WARNING('No connections with secrets found.'))
            return

        self.stdout.write(f'Found {total_connections} connection(s) with secrets.')

        if dry_run:
            self.stdout.write(self.style.NOTICE('DRY RUN MODE - No changes will be saved'))

        # Process each connection
        success_count = 0
        error_count = 0

        with transaction.atomic():
            for connection in connections:
                try:
                    # Decrypt with old key
                    encrypted_bytes = connection.keycloak_client_secret.encode('utf-8')
                    plaintext_bytes = old_cipher.decrypt(encrypted_bytes)

                    if dry_run:
                        self.stdout.write(
                            f'{connection.name}: Successfully decrypted with old key'
                        )
                    else:
                        new_encrypted_bytes = new_cipher.encrypt(plaintext_bytes)
                        connection.keycloak_client_secret = new_encrypted_bytes.decode('utf-8')
                        connection.save(update_fields=['keycloak_client_secret'])

                        self.stdout.write(
                            self.style.SUCCESS(f'{connection.name}: Re-encrypted successfully')
                        )

                    success_count += 1

                except InvalidToken:
                    self.stdout.write(
                        self.style.ERROR(
                            f'{connection.name}: Failed to decrypt - invalid token '
                            '(secret may not be encrypted or wrong old key)'
                        )
                    )
                    error_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'{connection.name}: Error - {type(e).__name__}')
                    )
                    error_count += 1

            # Rollback if dry run or if any errors
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.NOTICE('\nDry run complete - no changes saved'))
            elif error_count > 0:
                transaction.set_rollback(True)
                raise CommandError(
                    f'\nEncryption failed for {error_count} connection(s). '
                    'Transaction rolled back. No changes were saved.'
                )

        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'Dry run successful: {success_count}/{total_connections} secrets validated')
            )
            self.stdout.write('\nRun without --dry-run to apply changes.')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully re-encrypted {success_count}/{total_connections} secret(s)'
                )
            )

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'{error_count} connection(s) had errors')
            )
