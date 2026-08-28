# NetBox AAS Integration Plugin

[![REUSE status](https://api.reuse.software/badge/github.com/Immersive-Data-Center-Management/aas-plugin-for-netbox)](https://api.reuse.software/info/github.com/Immersive-Data-Center-Management/aas-plugin-for-netbox)

## About this project

NetBox plugin for Asset Administration Shell (AAS) integration with Eclipse BaSyx.
This plugin enables automatic synchronization between NetBox infrastructure data and AAS digital twins,
bridging the gap between network/datacenter management and Industry 4.0 digital twin standards.

## Features

- **Dynamic Submodel Configuration**: Database-driven system for configuring which submodels to create for different
  NetBox objects
- **Built-in IDTA Templates**: Includes Nameplate (IDTA 02006), TechnicalData (IDTA 02003), and custom RackUsage
  submodels
- **Flexible Field Mapping**: JSONPath-based expressions map NetBox fields to AAS elements
- **Automatic Synchronization**: Django signals trigger AAS updates when NetBox objects change
- **Multi-tenant Support**: Multiple AAS connections with per-connection submodel configurations

## Requirements and Setup

### Requirements

**This plugin requires Eclipse BaSyx 2.0 with Keycloak authentication:**

- NetBox 4.0 or later
- Python 3.12 or later
- Eclipse BaSyx 2.0 (AAS Environment, Registry, Discovery services)
- Keycloak for OAuth2/OIDC authentication
- All AAS connections must use Keycloak (no other auth methods supported)

### Installation

Install the plugin via pip:

```bash
pip install netbox-aas-integration
```

Add to NetBox's `configuration.py`:

```python
PLUGINS = [
    'aas_integration',
]
```

Run database migrations:

```bash
python manage.py migrate
```

### Configuration

1. Navigate to **Plugins → AAS Integration** in the NetBox admin interface
2. Create an AAS Connection with your BaSyx and Keycloak details:
   - AAS API URL (e.g., `http://aas-server:8081`)
   - Registry API URL
   - Discovery API URL
   - Keycloak Server URL, Realm, Client ID, and Client Secret
3. Configure Submodel Templates for your entity types (Device, Rack, etc.)
4. Set up Field Mappings to define how NetBox data maps to AAS properties
5. NetBox objects will automatically sync to AAS when created or updated

### Security

Client secrets are **automatically encrypted at rest** using Fernet symmetric encryption derived from Django's `SECRET_KEY`.

⚠️ **Important**: If you change Django's `SECRET_KEY`, you must re-encrypt existing secrets using:

```bash
python manage.py rotate_aas_encryption_key --old-key "old-key-value"
```

Always backup your database before changing `SECRET_KEY`.

## Development

For detailed information about the plugin architecture, development environment setup, and testing,
see [DEVELOPMENT.md](DEVELOPMENT.md).

Quick start for development:

```bash
# Navigate to deploy directory
cd dev-environment/

# Start development environment
docker compose up

# Access services:
# - Keycloak: http://keycloak.localhost:8080 (admin:admin)
# - NetBox: http://localhost:8085 (admin:admin)
# - AAS UI: http://localhost:3000
```

## Support, Feedback, Contributing

This project is open to feature requests/suggestions, bug reports etc. via
[GitHub issues](https://github.com/Immersive-Data-Center-Management/aas-plugin-for-netbox/issues).
Contribution and feedback are encouraged and always welcome. For more information about how to contribute,
the project structure, as well as additional contribution information, see our [Contribution Guidelines](CONTRIBUTING.md).

## Security / Disclosure

If you find any bug that may be a security problem, please follow our instructions at
[in our security policy](https://github.com/Immersive-Data-Center-Management/aas-plugin-for-netbox/security/policy)
on how to report it. Please do not create GitHub issues for security-related doubts or problems.

## Code of Conduct

We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience
for everyone. By participating in this project, you agree to abide by its
[Code of Conduct](https://github.com/Immersive-Data-Center-Management/.github/blob/main/CODE_OF_CONDUCT.md) at all times.

## Licensing

Copyright 2026 SAP SE or an SAP affiliate company and aas-plugin-for-netbox contributors.
Please see our [LICENSE](LICENSE) for copyright and license information.
Detailed information including third-party components and their licensing/copyright information is available
[via the REUSE tool](https://api.reuse.software/info/github.com/Immersive-Data-Center-Management/aas-plugin-for-netbox).
