# Development and Demo Environment

⚠️ **This directory contains a complete development and demonstration environment. It is NOT intended for production use.**

## What's Included

This setup provides:

- NetBox instance with the AAS Integration plugin pre-configured
- BaSyx 2.0 AAS infrastructure (Environment, Registry, Discovery services)
- Keycloak authentication server with pre-configured realm and users
- PostgreSQL database with initialized schemas
- BaSyx AAS Web UI for visualization

## Security Notice

**All credentials and secrets in these files are examples for local development only:**

- Database passwords (postgres/postgres, keycloak/keycloak, netbox/netbox, aas/aas)
- NetBox superuser (admin/admin)
- NetBox SECRET_KEY and API tokens
- Keycloak realm configuration in `postgres/10-keycloak.sql`

**⚠️ NEVER use these credentials in production environments.**

## Quick Start

```bash
cd dev-environment
docker-compose up -d
```

Wait for all services to become healthy (check with `docker-compose ps`), then access:

| Service | Development | Test (if running) |
|---------|-------------|-------------------|
| **NetBox UI** | http://localhost:8085 | http://localhost:9085 |
| **Keycloak** | http://localhost:8080 | http://localhost:9080 |
| **AAS Web UI** | http://localhost:3000 | - |
| **AAS Environment API** | http://localhost:8081 | http://localhost:9081 |
| **AAS Registry API** | http://localhost:8082 | http://localhost:9082 |
| **Submodel Registry API** | http://localhost:8083 | http://localhost:9083 |
| **AAS Discovery API** | http://localhost:8084 | http://localhost:9084 |

**Login:** admin / admin (both environments)

## Loading Test Data

The environment starts with an empty NetBox database. 
For comprehensive testing with netbox community [test data](https://github.com/netbox-community/netbox-demo-data) (100+ devices, multiple sites, racks, etc.):

```bash
./load-demo-data.sh download v4.6
./load-demo-data.sh load --source datasets/netbox-demo-v4.6.sql

# Or load from custom dataset
./load-demo-data.sh load --source /path/to/custom.sql
```

**Demo data includes:**

- 20+ Sites across multiple regions
- 10+ Manufacturers
- 10+ Device Types
- 70+ Devices
- Racks, Cables, IP Addresses, VLANs, etc.
- Complete realistic data hierarchy

**Login:** admin / admin

**Next Steps:** Navigate to Plugins → AAS Integration → Sync to synchronize devices to AAS.

### Cleaning Test Data

To remove loaded test data and reset to a clean state:

```bash
# Full database reset (removes everything)
./load-demo-data.sh clean full

# Keep plugin configuration, remove NetBox data only
./load-demo-data.sh clean preserve-plugin
```

## Files Overview

- `docker-compose.yml` - Main orchestration file for all services
- `basyx-infra.yml` - BaSyx infrastructure configuration for AAS Web UI
- `basyx/` - BaSyx security configuration (ABAC rules, OIDC trust list)
- `postgres/10-keycloak.sql` - Keycloak database initialization (6000+ lines of demo data)
- `netbox/plugins.py` - NetBox plugin configuration
- `dockerfiles/netbox.Dockerfile` - Custom NetBox image with plugin
- `TROUBLESHOOTING.md` - Common issues and solutions

## Keycloak Pre-Configuration

The `postgres/10-keycloak.sql` file contains a complete Keycloak database dump with:

- Pre-configured realm: `basyx-dev`
- Demo users and roles for testing
- OAuth2/OIDC client configurations for BaSyx services
- **This is development data only** - contains no real credentials or sensitive information

### Pre-configured Keycloak Clients

Two OAuth2 clients are available in the `basyx-dev` realm:

1. **aas-ui** - Used by BaSyx AAS Web UI (public client, authorization code flow)
2. **netbox** - Used by NetBox plugin for API authentication (confidential client, client credentials flow)
   - Client credentials are defined in `postgres/10-keycloak.sql` for local development only
   - Service Account: Enabled (authenticated as `service-account-netbox`)
   - Role: `sync` (satisfies ABAC authorization rules)

To configure an AAS Connection in NetBox to use Keycloak authentication:
1. Navigate to Plugins → AAS Integration → Connections in NetBox UI
2. Create or edit a connection and fill in the Keycloak fields:
   - Keycloak Server URL: `http://localhost:8080`
   - Keycloak Realm: `basyx-dev`
   - Keycloak Client ID: `netbox`
   - Keycloak Client Secret: (retrieve from `postgres/10-keycloak.sql`)
3. The plugin will automatically acquire OAuth2 tokens and include them in API requests

## Development Workflow

1. Start the environment: `docker-compose up -d`
2. Make changes to the plugin code in `../aas_integration/`
3. Restart NetBox to pick up changes: `docker-compose restart netbox netbox-worker`
4. View logs: `docker-compose logs -f netbox`

## Cleaning Up

```bash
# Stop all services
docker-compose down

# Remove all data volumes (fresh start)
docker-compose down -v
```

## Integration Test Environment

An isolated test environment is available for running integration tests without affecting the development environment.

### Running Tests

```bash
# Start test environment (dev environment not needed)
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Wait for all services to be healthy (takes ~60 seconds)
docker-compose -f docker-compose.yml -f docker-compose.test.yml ps

# Run integration tests
docker-compose -f docker-compose.yml -f docker-compose.test.yml exec netbox-test \
  bash -c "cd /opt/netbox/netbox && \
  pytest plugins/aas_integration/tests/integration/ -v --ds=netbox.settings"
```

**Note:** The `-f docker-compose.yml` is needed because `docker-compose.test.yml` is an overlay file that extends the
base configuration.

### Test Environment Details

The test profile creates parallel services on ports 9080-9085 with isolated databases:

- **Separate databases**: `netbox_test`, `keycloak_test`, `aas_test`
- **Isolated network**: `netbox-test` (no interference with dev)
- **Same architecture**: PostgreSQL storage, same Keycloak realm (`basyx-dev`)
- **No resource limits**: Optimized for test speed

Key differences from dev:
- Different ports (9xxx) - no conflicts
- Separate PostgreSQL instance (`postgres-test`)
- Test database users have `CREATEDB` permission (for Django test databases)
- No aas-web-ui (not needed for tests)
- No restart policy (ephemeral)

### Test Cleanup

```bash
# Stop test services only
docker-compose -f docker-compose.yml -f docker-compose.test.yml stop \
  postgres-test keycloak-test aas-env-test aas-registry-test \
  sm-registry-test aas-discovery-test netbox-test netbox-worker-test

# Remove test data volumes (preserves dev volumes)
docker-compose -f docker-compose.yml -f docker-compose.test.yml down -v
```

---

See `TROUBLESHOOTING.md` for common issues and solutions.
