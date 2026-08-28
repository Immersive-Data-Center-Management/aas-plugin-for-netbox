# Complete initial migration for aas_integration plugin
# Includes models, built-in templates, and default configurations

import uuid
import django.db.models.deletion
from django.db import migrations, models


def create_builtin_templates_and_configurations(apps, schema_editor):
    """Create built-in Nameplate, TechnicalData, and RackUsage templates with default configurations"""
    SubmodelTemplate = apps.get_model('aas_integration', 'SubmodelTemplate')
    SubmodelElement = apps.get_model('aas_integration', 'SubmodelElement')
    AASConnection = apps.get_model('aas_integration', 'AASConnection')
    SubmodelConfiguration = apps.get_model('aas_integration', 'SubmodelConfiguration')
    FieldMapping = apps.get_model('aas_integration', 'FieldMapping')

    nameplate = SubmodelTemplate.objects.create(
        idta_number='IDTA 02006-3-0',
        template_id='https://admin-shell.io/idta/SubmodelTemplate/DigitalNameplate/3/0',
        id_short='Nameplate',
        name='Digital Nameplate',
        description={'en': 'Contains the nameplate information attached to the product according to IDTA 02006-3-0-1'},
        version='3',
        revision='0',
        semantic_id='https://admin-shell.io/idta/nameplate/3/0/Nameplate',
        source_type='IDTA',
        applicable_entity_types=['devices', 'racks'],
        is_active=True,
        is_built_in=True,
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=nameplate, id_short='URIOfTheProduct', element_type='Property',
                       value_type='xs:anyURI', semantic_id='0112/2///61987#ABN590#002',
                       cardinality='One', order=10),
        SubmodelElement(template=nameplate, id_short='ManufacturerName', element_type='MultiLanguageProperty',
                       semantic_id='0112/2///61987#ABA565#009', cardinality='One', order=20),
        SubmodelElement(template=nameplate, id_short='ManufacturerProductDesignation', element_type='MultiLanguageProperty',
                       semantic_id='0112/2///61987#ABA567#009', cardinality='One', order=30),
        SubmodelElement(template=nameplate, id_short='AddressInformation', element_type='SubmodelElementCollection',
                       semantic_id='https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation',
                       cardinality='One', order=40),
        SubmodelElement(template=nameplate, id_short='ManufacturerProductRoot', element_type='MultiLanguageProperty',
                       semantic_id='0112/2///61360_7#AAS011#001', cardinality='ZeroToOne', order=50),
        SubmodelElement(template=nameplate, id_short='ManufacturerProductFamily', element_type='MultiLanguageProperty',
                       semantic_id='0112/2///61987#ABP464#002', cardinality='ZeroToOne', order=60),
        SubmodelElement(template=nameplate, id_short='ManufacturerProductType', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA300#008',
                       cardinality='ZeroToOne', order=70),
        SubmodelElement(template=nameplate, id_short='OrderCodeOfManufacturer', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA950#008',
                       cardinality='One', order=80),
        SubmodelElement(template=nameplate, id_short='ProductArticleNumberOfManufacturer', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA581#007',
                       cardinality='ZeroToOne', order=90),
        SubmodelElement(template=nameplate, id_short='SerialNumber', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA951#009',
                       cardinality='ZeroToOne', order=100),
        SubmodelElement(template=nameplate, id_short='YearOfConstruction', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABP000#002',
                       cardinality='ZeroToOne', order=110),
        SubmodelElement(template=nameplate, id_short='DateOfManufacture', element_type='Property',
                       value_type='xs:date', semantic_id='0112/2///61987#ABB757#007',
                       cardinality='ZeroToOne', order=120),
        SubmodelElement(template=nameplate, id_short='HardwareVersion', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA926#008',
                       cardinality='ZeroToOne', order=130),
        SubmodelElement(template=nameplate, id_short='FirmwareVersion', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA302#006',
                       cardinality='ZeroToOne', order=140),
        SubmodelElement(template=nameplate, id_short='SoftwareVersion', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABA601#008',
                       cardinality='ZeroToOne', order=150),
        SubmodelElement(template=nameplate, id_short='CountryOfOrigin', element_type='Property',
                       value_type='xs:string', semantic_id='0112/2///61987#ABP462#001',
                       cardinality='ZeroToOne', order=160),
        SubmodelElement(template=nameplate, id_short='UniqueFacilityIdentifier', element_type='Property',
                       value_type='xs:string', semantic_id='https://admin-shell.io/idta/nameplate/3/0/UniqueFacilityIdentifier',
                       cardinality='ZeroToOne', order=170),
        SubmodelElement(template=nameplate, id_short='CompanyLogo', element_type='File',
                       semantic_id='0112/2///61987#ABP463#001', cardinality='ZeroToOne', order=180),
        SubmodelElement(template=nameplate, id_short='Markings', element_type='SubmodelElementList',
                       semantic_id='0112/2///61360_7#AAS006#001', cardinality='ZeroToOne', order=190),
        SubmodelElement(template=nameplate, id_short='AssetSpecificProperties', element_type='SubmodelElementCollection',
                       semantic_id='0173-1#02-ABI218#003/0173-1#01-AGZ672#004',
                       cardinality='ZeroToOne', order=200),
    ])

    address_info = SubmodelElement.objects.get(template=nameplate, id_short='AddressInformation')
    SubmodelElement.objects.bulk_create([
        # Other properties ignored, as documentation of the nameplate submodel only makes thos required.
        SubmodelElement(template=nameplate, parent_element=address_info, id_short='Street',
                       element_type='Property', value_type='xs:string',
                       semantic_id='https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/Street',
                       cardinality='ZeroToOne', order=10),
        SubmodelElement(template=nameplate, parent_element=address_info, id_short='Zipcode',
                       element_type='Property', value_type='xs:string',
                       semantic_id='https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/Zipcode',
                       cardinality='ZeroToOne', order=20),
        SubmodelElement(template=nameplate, parent_element=address_info, id_short='CityTown',
                       element_type='Property', value_type='xs:string',
                       semantic_id='https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/CityTown',
                       cardinality='ZeroToOne', order=30),
        SubmodelElement(template=nameplate, parent_element=address_info, id_short='NationalCode',
                       element_type='Property', value_type='xs:string',
                       semantic_id='https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/NationalCode',
                       cardinality='ZeroToOne', order=50),
    ])

    # Add child element template for Markings list (SubmodelElementCollection that will be repeated)
    markings_list = SubmodelElement.objects.get(template=nameplate, id_short='Markings')
    marking_collection = SubmodelElement.objects.create(
        template=nameplate, parent_element=markings_list, id_short='Marking',
        element_type='SubmodelElementCollection',
        semantic_id='0112/2///61360_7#AAS007#001',
        cardinality='ZeroToMany', order=10
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='MarkingName',
                       element_type='Property', value_type='xs:string',
                       semantic_id='0112/2///61360_7#AAS008#001',
                       cardinality='One', order=10),
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='DesignationOfCertificateOrApproval',
                       element_type='Property', value_type='xs:string',
                       semantic_id='0112/2///61987#ABP467#001',
                       cardinality='ZeroToOne', order=20),
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='IssueDate',
                       element_type='Property', value_type='xs:date',
                       semantic_id='0112/2///61987#ABP468#001',
                       cardinality='ZeroToOne', order=30),
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='ExpiryDate',
                       element_type='Property', value_type='xs:date',
                       semantic_id='0112/2///61987#ABP469#001',
                       cardinality='ZeroToOne', order=40),
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='MarkingFile',
                       element_type='File',
                       semantic_id='0112/2///61360_7#AAS009#001',
                       cardinality='One', order=50),
        SubmodelElement(template=nameplate, parent_element=marking_collection, id_short='MarkingAdditionalText',
                       element_type='Property', value_type='xs:string',
                       semantic_id='0112/2///61987#ABP470#001',
                       cardinality='ZeroToMany', order=60),
    ])

    # Create TechnicalData template (IDTA 02003-1-2)
    tech_data = SubmodelTemplate.objects.create(
        idta_number='IDTA 02003-1-2',
        template_id='https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2',
        id_short='TechnicalData',
        name='Technical Data',
        description={'en': 'Technical specifications and product images'},
        version='1',
        revision='2',
        semantic_id='https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2',
        source_type='IDTA',
        applicable_entity_types=['devices'],
        is_active=True,
        is_built_in=True,
    )

    general_info = SubmodelElement.objects.create(
        template=tech_data, id_short='GeneralInformation', element_type='SubmodelElementCollection',
        semantic_id='0173-1#02-ABK161#002/0173-1#01-AHX838#002', cardinality='One',
        display_name={'en': 'General information', 'de': 'Allgemeine Informationen'}, order=10
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=tech_data, parent_element=general_info, id_short='ManufacturerName',
                       element_type='Property', value_type='xs:string', semantic_id='0173-1#02-AAO677#004',
                       cardinality='One', display_name={'en': 'Manufacturer name', 'de': 'Herstellername'},
                       category='PARAMETER', order=10),
        SubmodelElement(template=tech_data, parent_element=general_info, id_short='ManufacturerProductDesignation',
                       element_type='MultiLanguageProperty', semantic_id='0173-1#02-AAW338#003', cardinality='One',
                       display_name={'en': 'Manufacturer product designation', 'de': 'Herstellerproduktbezeichnung'},
                       category='PARAMETER', order=20),
        SubmodelElement(template=tech_data, parent_element=general_info, id_short='ManufacturerArticleNumber',
                       element_type='Property', value_type='xs:string', semantic_id='0173-1#02-AAO676#005',
                       cardinality='One', display_name={'en': 'Manufacturer article number', 'de': 'Herstellerartikelnummer'},
                       category='PARAMETER', order=30),
    ])

    product_images = SubmodelElement.objects.create(
        template=tech_data, parent_element=general_info, id_short='ProductImages',
        element_type='SubmodelElementList', semantic_id='0173-1#02-ABM220#001', cardinality='ZeroToMany',
        display_name={'en': 'Product images', 'de': 'Produktbilder'}, order=40
    )

    product_image_coll = SubmodelElement.objects.create(
        template=tech_data, parent_element=product_images, id_short='ProductImage',
        element_type='SubmodelElementCollection', semantic_id='0173-1#02-ABM220#001/0173-1#01-AHY911#001',
        cardinality='ZeroToMany', display_name={'en': 'Product image', 'de': 'Produktbild'}, order=10
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=tech_data, parent_element=product_image_coll, id_short='ImageFile',
                       element_type='Blob', semantic_id='0173-1#02-ABK291#002', cardinality='One',
                       display_name={'en': 'Product image', 'de': 'Bildname Sachaufnahme'}, order=10),
        SubmodelElement(template=tech_data, parent_element=product_image_coll, id_short='ImageNote',
                       element_type='MultiLanguageProperty', semantic_id='0173-1#02-ABL423#001', cardinality='ZeroToOne',
                       display_name={'en': 'Image note', 'de': 'Bildhinweis'}, order=20),
    ])

    # Create RackUsage template (custom)
    rack_usage = SubmodelTemplate.objects.create(
        template_id='https://apeirora.eu/aas/submodels/RackUsage/1/0',
        id_short='RackUsage',
        name='Rack Usage',
        description={'en': 'Rack occupancy and installed components tracking', 'de': 'Rack-Belegung und installierte Komponenten'},
        version='1',
        revision='0',
        semantic_id='https://apeirora.eu/aas/submodels/RackUsage',
        source_type='CUSTOM',
        applicable_entity_types=['racks'],
        is_active=True,
        is_built_in=True,
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=rack_usage, id_short='UsedUnits', element_type='Property', value_type='xs:int',
                       semantic_id='https://apeirora.eu/aas/submodels/RackUsage/UsedUnits', cardinality='One',
                       display_name={'en': 'Number of rack units currently occupied by installed devices',
                                   'de': 'Anzahl der derzeit von installierten Geräten belegten Rack-Einheiten'}, order=10),
        SubmodelElement(template=rack_usage, id_short='TotalUnits', element_type='Property', value_type='xs:int',
                       semantic_id='https://apeirora.eu/aas/submodels/RackUsage/TotalUnits', cardinality='One',
                       display_name={'en': 'Total capacity of the rack in rack units (U)',
                                   'de': 'Gesamtkapazität des Racks in Rack-Einheiten (HE)'}, order=20),
    ])

    installed_comp = SubmodelElement.objects.create(
        template=rack_usage, id_short='InstalledComponents', element_type='SubmodelElementCollection',
        semantic_id='https://apeirora.eu/aas/submodels/RackUsage/InstalledComponents', cardinality='ZeroToMany',
        display_name={'en': 'List of installed components in the rack', 'de': 'Liste der im Rack verbauten Komponenten'}, order=30
    )

    device_comp = SubmodelElement.objects.create(
        template=rack_usage, parent_element=installed_comp, id_short='DeviceComponent',
        element_type='SubmodelElementCollection', semantic_id='https://apeirora.eu/aas/submodels/RackUsage/DeviceComponent',
        cardinality='ZeroToMany', display_name={'en': 'Installed component in the rack', 'de': 'Verbaute Komponente im Rack'}, order=10
    )

    SubmodelElement.objects.bulk_create([
        SubmodelElement(template=rack_usage, parent_element=device_comp, id_short='PositionFrom', element_type='Property',
                       value_type='xs:int', semantic_id='https://apeirora.eu/aas/submodels/RackUsage/PositionFrom',
                       cardinality='ZeroToOne', order=10),
        SubmodelElement(template=rack_usage, parent_element=device_comp, id_short='HeightUnits', element_type='Property',
                       value_type='xs:int', semantic_id='https://apeirora.eu/aas/submodels/RackUsage/HeightUnits',
                       cardinality='One', order=20),
        SubmodelElement(template=rack_usage, parent_element=device_comp, id_short='DeviceReference', element_type='Entity',
                       semantic_id='https://apeirora.eu/aas/submodels/RackUsage/DeviceReference', cardinality='One', order=30),
    ])

    # Create default global configurations (connection=None)
    # These apply to all connections unless overridden

    # Nameplate for devices (global default)
    config_nameplate_dev = SubmodelConfiguration.objects.create(
        connection=None,
        entity_type='devices',
        template=nameplate,
        is_enabled=True,
        priority=100
    )
    FieldMapping.objects.bulk_create([
        FieldMapping(configuration=config_nameplate_dev, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='URIOfTheProduct'),
                   default_value='http://netbox.local/device/',
                   is_multilanguage=False, order=5),
        FieldMapping(configuration=config_nameplate_dev, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='ManufacturerName'),
                   jsonpath_expression='$.device_type.manufacturer.name',
                   is_multilanguage=True, language_code='en', order=10),
        FieldMapping(configuration=config_nameplate_dev, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='ManufacturerProductDesignation'),
                   jsonpath_expression='$.device_type.model',
                   is_multilanguage=True, language_code='en', order=20),
        FieldMapping(configuration=config_nameplate_dev, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='OrderCodeOfManufacturer'),
                   jsonpath_expression='$.device_type.part_number',
                   default_value='N/A',  # Fallback for devices without part number
                   is_multilanguage=False, order=25),
        FieldMapping(configuration=config_nameplate_dev, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='SerialNumber'),
                   jsonpath_expression='$.serial',
                   is_multilanguage=False, order=30),
    ], ignore_conflicts=True)

    # Nameplate for racks (global default)
    config_nameplate_rack = SubmodelConfiguration.objects.create(
        connection=None,
        entity_type='racks',
        template=nameplate,
        is_enabled=True,
        priority=100
    )
    FieldMapping.objects.bulk_create([
        FieldMapping(configuration=config_nameplate_rack, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='URIOfTheProduct'),
                   default_value='http://netbox.local/rack/',
                   is_multilanguage=False, order=5),
        FieldMapping(configuration=config_nameplate_rack, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='ManufacturerName'),
                   jsonpath_expression='$.rack_type.manufacturer.name',
                   default_value='Unknown',  # Fallback for racks without manufacturer
                   is_multilanguage=True, language_code='en', order=10),
        FieldMapping(configuration=config_nameplate_rack, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='ManufacturerProductDesignation'),
                   jsonpath_expression='$.rack_type.model',
                   default_value='Rack',  # Fallback for racks without model
                   is_multilanguage=True, language_code='en', order=20),
        FieldMapping(configuration=config_nameplate_rack, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='OrderCodeOfManufacturer'),
                   jsonpath_expression='$.rack_type.part_number',
                   default_value='N/A',  # Fallback for racks without part number
                   is_multilanguage=False, order=25),
        FieldMapping(configuration=config_nameplate_rack, submodel_element=SubmodelElement.objects.get(template=nameplate, id_short='SerialNumber'),
                   jsonpath_expression='$.serial',
                   is_multilanguage=False, order=30),
    ], ignore_conflicts=True)

    # TechnicalData for devices (global default)
    config_tech_dev = SubmodelConfiguration.objects.create(
        connection=None,
        entity_type='devices',
        template=tech_data,
        is_enabled=True,
        priority=200
    )
    FieldMapping.objects.bulk_create([
        FieldMapping(configuration=config_tech_dev, submodel_element=SubmodelElement.objects.get(template=tech_data, parent_element=general_info, id_short='ManufacturerName'),
                   jsonpath_expression='$.device_type.manufacturer.name',
                   is_multilanguage=False, language_code='en', order=10),
        FieldMapping(configuration=config_tech_dev, submodel_element=SubmodelElement.objects.get(template=tech_data, parent_element=general_info, id_short='ManufacturerProductDesignation'),
                   jsonpath_expression='$.device_type.model',
                   is_multilanguage=True, language_code='en', order=20),
        FieldMapping(configuration=config_tech_dev, submodel_element=SubmodelElement.objects.get(template=tech_data, parent_element=general_info, id_short='ManufacturerArticleNumber'),
                   jsonpath_expression='$.device_type.part_number',
                   is_multilanguage=False, language_code='en', order=30),
    ], ignore_conflicts=True)

    # RackUsage for racks (global default)
    config_rack_usage = SubmodelConfiguration.objects.create(
        connection=None,
        entity_type='racks',
        template=rack_usage,
        is_enabled=True,
        priority=200
    )
    FieldMapping.objects.create(
        configuration=config_rack_usage,
        submodel_element=SubmodelElement.objects.get(template=rack_usage, id_short='TotalUnits'),
        jsonpath_expression='$.u_height',
        is_multilanguage=False,
        order=10
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '__first__'),
    ]

    operations = [
        # Create AASConnection model
        migrations.CreateModel(
            name='AASConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Unique name for this AAS connection', max_length=100, unique=True)),
                ('description', models.TextField(blank=True, help_text='Description of this AAS environment')),
                ('aas_api_url', models.CharField(help_text='Base URL of the AAS Environment API (e.g., http://aas-env:8081)', max_length=255, verbose_name='AAS API URL')),
                ('registry_api_url', models.CharField(help_text='URL of the AAS Registry (e.g., http://aas-registry:8080)', max_length=255, verbose_name='Registry API URL')),
                ('discovery_api_url', models.CharField(blank=True, help_text='URL of the AAS Discovery Service (e.g., http://aas-discovery:8085). Leave empty to skip discovery registration.', max_length=255, verbose_name='Discovery API URL')),
                ('keycloak_server_url', models.CharField(blank=True, help_text='Keycloak server URL (e.g., http://keycloak:8080)', max_length=255, verbose_name='Keycloak Server URL')),
                ('keycloak_realm', models.CharField(blank=True, help_text='Keycloak realm name (e.g., BaSyx-Test)', max_length=100, verbose_name='Keycloak Realm')),
                ('keycloak_client_id', models.CharField(blank=True, help_text='Keycloak client ID for authentication', max_length=255, verbose_name='Keycloak Client ID')),
                ('keycloak_client_secret', models.TextField(blank=True, help_text='Keycloak client secret (encrypted at rest using Fernet symmetric encryption)', verbose_name='Keycloak Client Secret')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this connection is enabled')),
                ('auto_sync_enabled', models.BooleanField(default=True, help_text='Automatically sync device changes to AAS in real-time')),
                ('auto_delete_enabled', models.BooleanField(default=False, help_text='Automatically delete AAS shells when devices are deleted from NetBox')),
                ('is_default', models.BooleanField(default=False, help_text='Use this connection for automatic synchronization operations')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='Last Modified')),
                ('last_tested', models.DateTimeField(blank=True, null=True, verbose_name='Last Tested')),
            ],
            options={
                'verbose_name': 'AAS Connection',
                'verbose_name_plural': 'AAS Connections',
                'ordering': ['name'],
            },
        ),

        # Create SubmodelTemplate model
        migrations.CreateModel(
            name='SubmodelTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('idta_number', models.CharField(blank=True, help_text='IDTA specification number (e.g., "IDTA 02006-3-0")', max_length=50, verbose_name='IDTA Number')),
                ('template_id', models.CharField(help_text='Unique template identifier (e.g., "https://admin-shell.io/idta-02003-2-0")', max_length=255, unique=True, verbose_name='Template ID')),
                ('id_short', models.CharField(help_text='Short identifier used in AAS (e.g., "TechnicalData")', max_length=128, verbose_name='ID Short')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.JSONField(blank=True, default=dict, help_text='Multi-language description: {"en": "...", "de": "..."}', verbose_name='Description')),
                ('version', models.CharField(default='1.0', max_length=20, verbose_name='Version')),
                ('revision', models.CharField(default='0', max_length=20, verbose_name='Revision')),
                ('semantic_id', models.CharField(help_text='Primary semantic ID (e.g., "0173-1#01-AHX837#002")', max_length=255, verbose_name='Semantic ID')),
                ('supplemental_semantic_ids', models.JSONField(blank=True, default=list, help_text='List of supplemental semantic ID URLs', verbose_name='Supplemental Semantic IDs')),
                ('kind', models.CharField(choices=[('Template', 'Template'), ('Instance', 'Instance')], default='Template', help_text='AAS kind: Template for definitions, Instance for actual data', max_length=20, verbose_name='Kind')),
                ('source_type', models.CharField(choices=[('IDTA', 'IDTA Standard'), ('CUSTOM', 'Custom Definition'), ('IMPORTED', 'Imported from External Source')], default='CUSTOM', max_length=20, verbose_name='Source Type')),
                ('idta_json', models.JSONField(blank=True, help_text='Original IDTA JSON template (if imported)', null=True, verbose_name='IDTA JSON')),
                ('applicable_entity_types', models.JSONField(default=list, help_text='List of entity types this can apply to: ["devices", "racks", "cables", ...]', verbose_name='Applicable Entity Types')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this template is active', verbose_name='Is Active')),
                ('is_built_in', models.BooleanField(default=False, help_text='Built-in templates cannot be deleted', verbose_name='Is Built-in')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='Last Modified')),
            ],
            options={
                'verbose_name': 'Submodel Template',
                'verbose_name_plural': 'Submodel Templates',
                'ordering': ['id_short', 'version'],
            },
        ),

        # Create SubmodelElement model
        migrations.CreateModel(
            name='SubmodelElement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('id_short', models.CharField(help_text='Short identifier (e.g., "ManufacturerName")', max_length=128, verbose_name='ID Short')),
                ('element_type', models.CharField(choices=[('Property', 'Property'), ('MultiLanguageProperty', 'Multi-Language Property'), ('Range', 'Range'), ('Blob', 'Blob'), ('File', 'File'), ('ReferenceElement', 'Reference Element'), ('SubmodelElementCollection', 'Collection'), ('SubmodelElementList', 'List'), ('Entity', 'Entity'), ('Operation', 'Operation'), ('Capability', 'Capability')], help_text='AAS element type', max_length=50, verbose_name='Element Type')),
                ('display_name', models.JSONField(blank=True, default=dict, help_text='Multi-language display names: {"en": "...", "de": "..."}', verbose_name='Display Name')),
                ('description', models.JSONField(blank=True, default=dict, help_text='Multi-language descriptions', verbose_name='Description')),
                ('semantic_id', models.CharField(blank=True, help_text='Semantic ID (e.g., "0173-1#02-AAO677#004")', max_length=255, verbose_name='Semantic ID')),
                ('supplemental_semantic_ids', models.JSONField(blank=True, default=list, verbose_name='Supplemental Semantic IDs')),
                ('value_type', models.CharField(blank=True, choices=[('xs:string', 'String'), ('xs:int', 'Integer'), ('xs:double', 'Double'), ('xs:boolean', 'Boolean'), ('xs:dateTime', 'DateTime'), ('xs:anyURI', 'Any URI')], help_text='Data type for Property elements', max_length=50, verbose_name='Value Type')),
                ('cardinality', models.CharField(choices=[('One', 'Exactly One (1)'), ('ZeroToOne', 'Zero or One (0..1)'), ('OneToMany', 'One or More (1..*)'), ('ZeroToMany', 'Zero or More (0..*)')], default='One', help_text='Cardinality constraint', max_length=20, verbose_name='Cardinality')),
                ('category', models.CharField(blank=True, choices=[('CONSTANT', 'Constant'), ('PARAMETER', 'Parameter'), ('VARIABLE', 'Variable')], max_length=20, verbose_name='Category')),
                ('qualifiers', models.JSONField(blank=True, default=list, help_text='AAS qualifiers as JSON array', verbose_name='Qualifiers')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Order')),
                ('parent_element', models.ForeignKey(blank=True, help_text='Parent element if nested in a Collection or List', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='child_elements', to='aas_integration.submodelelement', verbose_name='Parent Element')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='aas_integration.submodeltemplate', verbose_name='Template')),
            ],
            options={
                'verbose_name': 'Submodel Element',
                'verbose_name_plural': 'Submodel Elements',
                'ordering': ['template', 'parent_element', 'order', 'id_short'],
            },
        ),

        # Create SubmodelConfiguration model
        migrations.CreateModel(
            name='SubmodelConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_type', models.CharField(choices=[('devices', 'Devices'), ('racks', 'Racks'), ('cables', 'Cables'), ('circuits', 'Circuits')], help_text='NetBox model type (e.g., "devices")', max_length=50, verbose_name='Entity Type')),
                ('is_enabled', models.BooleanField(default=True, help_text='Whether this submodel is active for sync', verbose_name='Is Enabled')),
                ('priority', models.PositiveIntegerField(default=100, help_text='Build order (lower = earlier). Important for dependencies like RackUsage.', verbose_name='Priority')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='Last Modified')),
                ('connection', models.ForeignKey(blank=True, null=True, help_text='AAS connection this configuration applies to. Leave empty for global defaults.', on_delete=django.db.models.deletion.CASCADE, related_name='submodel_configs', to='aas_integration.aasconnection', verbose_name='Connection')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='configurations', to='aas_integration.submodeltemplate', verbose_name='Template')),
            ],
            options={
                'verbose_name': 'Submodel Mapping Configuration',
                'verbose_name_plural': 'Submodel Mapping Configurations',
                'ordering': ['connection', 'entity_type', 'priority'],
            },
        ),

        # Create FieldMapping model
        migrations.CreateModel(
            name='FieldMapping',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('jsonpath_expression', models.TextField(blank=True, help_text='JSONPath expression for field access (e.g., "$.device_type.manufacturer.name")', verbose_name='JSONPath Expression')),
                ('default_value', models.CharField(blank=True, help_text='Default value if field is None/empty', max_length=255, verbose_name='Default Value')),
                ('transform_function', models.CharField(blank=True, choices=[('', 'None'), ('uppercase', 'Convert to Uppercase'), ('lowercase', 'Convert to Lowercase'), ('strip_protocol', 'Strip URL Protocol'), ('sanitize_urn', 'Sanitize for URN'), ('format_uri', 'Format as URI')], help_text='Built-in transformation to apply', max_length=100, verbose_name='Transform Function')),
                ('is_multilanguage', models.BooleanField(default=False, help_text='Whether this mapping produces multi-language text', verbose_name='Is Multilanguage')),
                ('language_code', models.CharField(default='en', help_text='Language code for multilanguage properties', max_length=5, verbose_name='Language Code')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Order')),
                ('configuration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_mappings', to='aas_integration.submodelconfiguration', verbose_name='Configuration')),
                ('submodel_element', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_mappings', to='aas_integration.submodelelement', verbose_name='Submodel Element')),
            ],
            options={
                'verbose_name': 'Field Mapping',
                'verbose_name_plural': 'Field Mappings',
                'ordering': ['configuration', 'submodel_element', 'order'],
            },
        ),

        # Create EntityTypeConfiguration model
        migrations.CreateModel(
            name='EntityTypeConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_type_label', models.CharField(help_text='Label used in configurations (e.g., "devices", "racks")', max_length=50, verbose_name='Entity Type Label')),
                ('is_enabled', models.BooleanField(default=True, help_text='Whether sync is enabled for this model type', verbose_name='Is Enabled')),
                ('builder_class', models.CharField(blank=True, help_text='Optional custom builder class (defaults to AASShellBuilder)', max_length=255, verbose_name='Builder Class')),
                ('select_related_fields', models.JSONField(default=list, help_text='List of related fields to prefetch (e.g., ["device_type", "site"])', verbose_name='Select Related Fields')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('last_modified', models.DateTimeField(auto_now=True, verbose_name='Last Modified')),
                ('connection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entity_type_configs', to='aas_integration.aasconnection', verbose_name='Connection')),
                ('content_type', models.ForeignKey(help_text='Django model to sync (e.g., Device, Rack, Cable)', on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='Content Type')),
            ],
            options={
                'verbose_name': 'Entity Type Configuration',
                'verbose_name_plural': 'Entity Type Configurations',
                'ordering': ['connection', 'entity_type_label'],
            },
        ),

        # Add constraints
        migrations.AddConstraint(
            model_name='submodelconfiguration',
            constraint=models.UniqueConstraint(fields=('connection', 'entity_type', 'template'), name='aas_integration_submodelconfiguration_unique_config'),
        ),
        migrations.AddConstraint(
            model_name='entitytypeconfiguration',
            constraint=models.UniqueConstraint(fields=('connection', 'content_type'), name='aas_integration_entitytypeconfiguration_unique_type'),
        ),

        # Create built-in templates and default configurations
        migrations.RunPython(create_builtin_templates_and_configurations, migrations.RunPython.noop),
    ]
