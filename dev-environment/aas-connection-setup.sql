--
-- AAS Integration Plugin - Test Connection Setup
--
-- This script creates a pre-configured AAS Connection for the local development environment.
-- Run this after importing the NetBox demo data and running migrations.
--
-- Usage:
--   docker exec -i postgres psql -U netbox -d netbox < aas-connection-setup.sql
--

-- Insert AAS Connection
INSERT INTO aas_integration_aasconnection (
    id,
    name,
    description,
    aas_api_url,
    registry_api_url,
    discovery_api_url,
    keycloak_server_url,
    keycloak_realm,
    keycloak_client_id,
    keycloak_client_secret,
    is_active,
    auto_sync_enabled,
    auto_delete_enabled,
    is_default,
    created,
    last_modified,
    aas_id_field,
    aas_link,
    aas_ui_url
) VALUES (
    1,
    'Local BaSyx Dev',
    'Local development environment with BaSyx 2.0 components',
    'http://aas-env:8081',
    'http://aas-registry:8080',
    'http://aas-discovery:8080',
    'http://keycloak:8080',
    'basyx-dev',
    'netbox',
    'gAAAAABqkAy6eeQRvZW2CHx08pjEwOXYaBwzFpvsyIf9u9eB8nSXQvv7F0iNKi6aZP73M7QSRmYXkceBnZwFpOJVUhGa0TyZWCqGVJ9HjQcF9Cv8DadqIsksYCjckdL_744zBf_B8Ng_',
    true,
    true,
    false,
    true,
    NOW(),
    NOW(),
    'name',
    'aas_link',
    'http://localhost:3000'
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    aas_api_url = EXCLUDED.aas_api_url,
    registry_api_url = EXCLUDED.registry_api_url,
    discovery_api_url = EXCLUDED.discovery_api_url,
    keycloak_server_url = EXCLUDED.keycloak_server_url,
    keycloak_realm = EXCLUDED.keycloak_realm,
    keycloak_client_id = EXCLUDED.keycloak_client_id,
    keycloak_client_secret = EXCLUDED.keycloak_client_secret,
    is_active = EXCLUDED.is_active,
    auto_sync_enabled = EXCLUDED.auto_sync_enabled,
    auto_delete_enabled = EXCLUDED.auto_delete_enabled,
    is_default = EXCLUDED.is_default,
    aas_id_field = EXCLUDED.aas_id_field,
    aas_link = EXCLUDED.aas_link,
    aas_ui_url = EXCLUDED.aas_ui_url,
    last_modified = NOW();

-- Enable device syncing
INSERT INTO aas_integration_entitytypeconfiguration (
    id,
    connection_id,
    content_type_id,
    entity_type_label,
    is_enabled,
    builder_class,
    select_related_fields,
    created,
    last_modified
) VALUES (
    gen_random_uuid(),
    1,
    (SELECT id FROM django_content_type WHERE app_label = 'dcim' AND model = 'device'),
    'devices',
    true,
    'aas_integration.builders.device_builder.DeviceAASBuilder',
    '["device_type", "device_type__manufacturer", "site", "rack"]',
    NOW(),
    NOW()
) ON CONFLICT (connection_id, content_type_id) DO UPDATE SET
    is_enabled = EXCLUDED.is_enabled,
    last_modified = NOW();

-- Optional: Enable rack syncing
INSERT INTO aas_integration_entitytypeconfiguration (
    id,
    connection_id,
    content_type_id,
    entity_type_label,
    is_enabled,
    builder_class,
    select_related_fields,
    created,
    last_modified
) VALUES (
    gen_random_uuid(),
    1,
    (SELECT id FROM django_content_type WHERE app_label = 'dcim' AND model = 'rack'),
    'racks',
    true,
    'aas_integration.builders.rack_builder.RackAASBuilder',
    '["rack_type", "rack_type__manufacturer", "site", "location"]',
    NOW(),
    NOW()
) ON CONFLICT (connection_id, content_type_id) DO UPDATE SET
    is_enabled = EXCLUDED.is_enabled,
    last_modified = NOW();

-- Update sequence if needed
SELECT setval('aas_integration_aasconnection_id_seq', (SELECT MAX(id) FROM aas_integration_aasconnection));

-- Display result
SELECT
    id,
    name,
    aas_api_url,
    is_active,
    auto_sync_enabled
FROM aas_integration_aasconnection
WHERE id = 1;

\echo ''
\echo '✓ AAS Connection created successfully!'
\echo ''
\echo 'Connection Details:'
\echo '  Name: Local BaSyx Dev'
\echo '  AAS Environment: http://aas-env:8081'
\echo '  Registry: http://aas-registry:8080'
\echo '  Discovery: http://aas-discovery:8080'
\echo '  Keycloak: http://keycloak:8080 (realm: basyx-dev)'
\echo ''
\echo 'Access NetBox at: http://localhost:8085'
\echo 'Navigate to: Plugins → AAS Integration → Connections'
\echo ''
