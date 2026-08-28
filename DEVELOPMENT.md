# Development Guide

This guide provides detailed information for developers contributing to
the NetBox AAS Integration Plugin.

## Architecture

The plugin uses a **database-driven configuration system** for maximum flexibility:

### Core Models

1. **SubmodelTemplate**: Stores submodel definitions (Nameplate, TechnicalData, RackUsage, etc.)
   - Each template has a unique identifier (e.g., `https://admin-shell.io/idta-02003-2-0`)
   - Defines the structure and semantic meaning of the submodel

2. **SubmodelElement**: Defines elements within templates (properties, collections, etc.)
   - Nested structure supports complex hierarchies
   - Each element has a semantic ID for AAS compliance

3. **SubmodelConfiguration**: Enables/disables submodels per entity type and connection
   - Controls which submodels are created for Devices, Racks, etc.
   - Per-connection configuration for multi-tenant scenarios

4. **FieldMapping**: Maps NetBox fields to AAS elements using JSONPath expressions
   - Example: `$.device_type.manufacturer.name` extracts the manufacturer name
   - Supports complex expressions for nested data

### How It Works

The `AASShellBuilder` reads these configurations at runtime to dynamically build AAS shells without hardcoded logic.
When a NetBox object is created or updated:

1. Django signals detect the change
2. The builder queries active SubmodelConfigurations for that entity type
3. Field mappings are applied to extract data from the NetBox object
4. An AAS shell is constructed with the configured submodels
5. The shell is synchronized to BaSyx via the REST API

This design allows administrators to customize AAS structure through the admin interface without code changes.

## Development Environment Setup

A complete development environment is provided via Docker Compose in the `dev-environment/` directory.

### Starting the Environment

```bash
cd dev-environment/
docker compose up
```

This will start and configure:

- **Keycloak** (OAuth2/OIDC provider)
- **Eclipse BaSyx** components (Go-based AAS Environment, Registry, Discovery)
- **NetBox** with the plugin pre-installed
- **PostgreSQL** database

### Service Access

Once all containers report healthy status, access the services at:

- **Keycloak**: <http://keycloak.localhost:8080>
  - Admin credentials: `admin:admin`
  - Pre-configured realm: `basyx-dev`
  
- **NetBox**: <http://localhost:8085>
  - Admin credentials: `admin:admin`
  - Plugin pre-installed and configured for development
  
- **AAS UI**: <http://localhost:3000>
  - Web interface for viewing AAS shells

### Keycloak Configuration

The Keycloak instance is pre-configured via a PostgreSQL database dump (`dev-environment/postgres/10-keycloak.sql`).
The `basyx-dev` realm and `netbox` client are ready to use.

To configure the NetBox AAS integration with the development environment:

| Parameter              | Value                                  |
|------------------------|----------------------------------------|
| AAS API URL            | <http://aas.localhost:8081>            |
| Registry API URL       | <http://aas.localhost:8082>            |
| Discovery API URL      | <http://aas.localhost:8084>            |
| Keycloak Server URL    | <http://keycloak.localhost:8080>       |
| Keycloak Realm         | basyx-dev                              |
| Keycloak Client ID     | netbox                                 |
| Keycloak Client Secret | *(see Keycloak admin → Credentials)*   |

⚠️ **Note**: The development environment is configured to permit insecure HTTP connections.
This setting is for development purposes only — **do not use in production**.

## Running Tests

### Install Test Dependencies

```bash
pip install -e '.[test]'
```

### Run Unit Tests

```bash
# Run all unit tests
pytest aas_integration/tests/unit/ -v

# Run specific test file
pytest aas_integration/tests/unit/test_aas_shell_builder.py -v

# Run with coverage report
pytest aas_integration/tests/unit/ --cov=aas_integration --cov-report=term-missing -v

# Generate HTML coverage report
pytest aas_integration/tests/unit/ --cov=aas_integration --cov-report=html -v
```

### CI/CD Test Execution

For continuous integration with XML reports and JUnit output:

```bash
pytest aas_integration/tests/unit/ \
  --cov=aas_integration \
  --cov-report=xml \
  --junitxml=junit.xml \
  -v
```

## Security Implementation

### Encrypted Client Secrets

Keycloak client secrets are automatically encrypted at rest using **Fernet symmetric encryption**.
The encryption is transparent to users and happens automatically when saving AAS connections.

**How It Works:**

1. The encryption key is derived from Django's `SECRET_KEY`
2. When an AAS connection is saved, the client secret is encrypted using `EncryptedCharField`
3. When the secret is accessed, it is automatically decrypted
4. The encrypted value is stored in the database

**Key Rotation:**

If Django's `SECRET_KEY` changes, existing encrypted secrets become unreadable. To re-encrypt with a new key:

```bash
python manage.py rotate_aas_encryption_key --old-key "old-key-value"
```

This command:

1. Decrypts all secrets using the old key
2. Re-encrypts them using the new key (from current `SECRET_KEY`)
3. Updates all records in the database

**Critical Requirements:**

1. **Protect Django's SECRET_KEY**
   - Store in environment variables
   - Never commit to version control
   - Use unique values for each environment

2. **Backup Before Key Changes**
   - Always backup your database before changing `SECRET_KEY`
   - Test key rotation in staging first

3. **Development/Testing**
   - If you drop and recreate the database (e.g., via `reset-for-tests.sh`), no key rotation is needed
   - The key should remain consistent across development sessions

## Project Structure

```text
aas_integration/
├── models.py              # Core data models (AASConnection, SubmodelTemplate, etc.)
├── builders/
│   ├── aas_shell_builder.py   # Main AAS shell construction logic
│   └── submodel_builder.py    # Individual submodel builders
├── converters/
│   └── netbox_to_dict.py      # NetBox object to dict conversion
├── fields.py              # Custom Django fields (EncryptedCharField)
├── signals.py             # Django signals for auto-sync
├── admin.py               # Admin interface configuration
├── views.py               # API views
├── migrations/            # Database migrations
├── templates/             # HTML templates
└── tests/
    ├── unit/              # Unit tests
    └── integration/       # Integration tests (if any)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines, including:

- Code style standards
- Testing requirements
- Pull request process
- Commit message conventions (use conventional commits)
