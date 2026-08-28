--
-- NetBox Demo Data - Rack Types Patch
--
-- The NetBox 4.6 demo data doesn't include rack types (added in later versions).
-- This script creates basic rack types and assigns them to existing racks.
--
-- Usage:
--   docker exec -i postgres psql -U netbox -d netbox < netbox-demo-racktypes-patch.sql
--

-- Create a default manufacturer for rack types if needed
INSERT INTO dcim_manufacturer (
    name,
    slug,
    description,
    created,
    last_updated,
    custom_field_data,
    comments
) VALUES (
    'Generic Racks',
    'generic-racks',
    'Generic manufacturer for standard rack types',
    NOW(),
    NOW(),
    '{}',
    ''
) ON CONFLICT (slug) DO NOTHING;

-- Get the manufacturer ID for use in rack types
DO $$
DECLARE
    manufacturer_id_var bigint;
BEGIN
    SELECT id INTO manufacturer_id_var FROM dcim_manufacturer WHERE slug = 'generic-racks';

    -- Create rack types
    INSERT INTO dcim_racktype (
        model,
        slug,
        description,
        form_factor,
        width,
        u_height,
        desc_units,
        comments,
        created,
        last_updated,
        custom_field_data,
        manufacturer_id,
        starting_unit,
        rack_count
    ) VALUES
        ('Wall Cabinet 12U', 'wall-cabinet-12u', '12U wall-mounted equipment cabinet', 'wall-cabinet', 19, 12, false, '', NOW(), NOW(), '{}', manufacturer_id_var, 1, 0),
        ('Standard Rack 42U', 'standard-rack-42u', '42U standard 4-post server rack', '4-post-cabinet', 19, 42, false, '', NOW(), NOW(), '{}', manufacturer_id_var, 1, 0),
        ('2-Post Frame 42U', '2-post-frame-42u', '42U 2-post open frame rack', '2-post-frame', 19, 42, false, '', NOW(), NOW(), '{}', manufacturer_id_var, 1, 0)
    ON CONFLICT (manufacturer_id, slug) DO NOTHING;
END $$;

-- Assign rack types to existing racks based on their form_factor
-- Wall cabinets (12U) -> Wall Cabinet type
UPDATE dcim_rack
SET rack_type_id = 1
WHERE form_factor = 'wall-cabinet' AND u_height = 12 AND rack_type_id IS NULL;

-- 4-post cabinets -> Standard Rack type
UPDATE dcim_rack
SET rack_type_id = 2
WHERE form_factor = '4-post-cabinet' AND rack_type_id IS NULL;

-- 2-post frames -> 2-Post Frame type
UPDATE dcim_rack
SET rack_type_id = 3
WHERE form_factor = '2-post-frame' AND rack_type_id IS NULL;

-- For any remaining racks without types, assign Standard Rack as default
UPDATE dcim_rack
SET rack_type_id = 2
WHERE rack_type_id IS NULL;

-- Update sequences
SELECT setval('dcim_manufacturer_id_seq', (SELECT MAX(id) FROM dcim_manufacturer));
SELECT setval('dcim_racktype_id_seq', (SELECT MAX(id) FROM dcim_racktype));

-- Display summary
SELECT
    'Total racks' as metric,
    COUNT(*) as count
FROM dcim_rack
UNION ALL
SELECT
    'Racks with type assigned' as metric,
    COUNT(*) as count
FROM dcim_rack
WHERE rack_type_id IS NOT NULL
UNION ALL
SELECT
    'Rack types available' as metric,
    COUNT(*) as count
FROM dcim_racktype;

\echo ''
\echo '✓ Rack types created and assigned to all racks'
\echo ''
