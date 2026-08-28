from django.db import migrations


def create_hierarchy_template(apps, schema_editor):
    """
    Create the built-in Hierarchical Structures BoM submodel template.
    IDTA 02011-1-1: HierarchicalStructuresEnablingBoM
    """

    SubmodelTemplate = apps.get_model('aas_integration', 'SubmodelTemplate')
    SubmodelElement = apps.get_model('aas_integration', 'SubmodelElement')

    # -------------------------------------------------------------------------
    # Create the SubmodelTemplate
    # Applicable to both racks and devices
    # -------------------------------------------------------------------------
    hierarchy = SubmodelTemplate.objects.create(
        idta_number='IDTA 02011-1-1',
        template_id='https://admin-shell.io/idta/SubmodelTemplate/HierarchicalStructuresBoM/1/1',
        id_short='HierarchicalStructures',
        name='Hierarchical Structures Enabling BoM',
        description={
            'en': 'Enables the description of hierarchical structures between assets '
                  '(Bill of Materials) according to IDTA 02011-1-1. '
        },
        version='1',
        revision='1',
        semantic_id='https://admin-shell.io/idta/SubmodelTemplate/HierarchicalStructuresBoM/1/1',
        source_type='IDTA',
        applicable_entity_types=['racks', 'devices'],
        is_active=True,
        is_built_in=True,
    )

    SubmodelElement.objects.create(
        template=hierarchy,
        id_short='ArcheType',
        element_type='Property',
        value_type='xs:string',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/ArcheType/1/0',
        cardinality='One',
        order=10,
        display_name={'en': 'Archetype'},
        description={'en': 'Hierarchy archetype: Full, OneDown, OneUp' },
    )

    entry_node = SubmodelElement.objects.create(
        template=hierarchy,
        id_short='EntryNode',
        element_type='Entity',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/EntryNode/1/0',
        cardinality='One',
        order=20,
        display_name={'en': 'Entry Node'},
        description={'en': 'Root entity of the hierarchy tree'},
    )

    node = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=entry_node,
        id_short='Node',
        element_type='Entity',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/Node/1/0',
        cardinality='One',
        order=10,
        display_name={'en': 'Node'},
        description={'en': 'A child asset entity within the hierarchy'},
    )

    has_part = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=entry_node,
        id_short='HasPart',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/HasPart/1/0',
        cardinality='ZeroToMany',
        order=10,
        display_name={'en': 'Has Part'},
        description={'en': 'Has Part'},
    )

    is_part_of = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=entry_node,
        id_short='IsPartOf',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/IsPartOf/1/0',
        cardinality='ZeroToMany',
        order=20,
        display_name={'en': 'Is Part Of'},
        description={'en': 'Is Part Of'},
    )
    
    same_as = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=entry_node,
        id_short='SameAs',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/SameAs/1/0',
        cardinality='ZeroToMany',
        order=20,
        display_name={'en': 'Same as'},
        description={'en': 'Same as'},
     )
    
    nested_node = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=node,
        id_short='NestedNode',
        element_type='Entity',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/Node/1/0',
        cardinality='ZeroToMany',
        order=10,
        display_name={'en': 'Nested Node'},
        description={'en': 'Nested Node'},
    )

    nested_node_2 = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=nested_node,
        id_short='NestedNode_2',
        element_type='Entity',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/Node/1/0',
        cardinality='ZeroToMany',
        order=10,
        display_name={'en': 'Nested Node'},
        description={'en': 'Nested Node'},
    )

    has_part_2 = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=nested_node,
        id_short='HasPart',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/HasPart/1/0',
        cardinality='ZeroToMany',
        order=10,
        display_name={'en': 'Has Part'},
        description={'en': 'Has Part'},
    )

    is_part_of_2 = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=nested_node,
        id_short='IsPartOf',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/IsPartOf/1/0',
        cardinality='ZeroToMany',
        order=20,
        display_name={'en': 'Is Part Of'},
        description={'en': 'Is Part Of'},    
    )
    
    same_as_2 = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=nested_node,
        id_short='SameAs',
        element_type='RelationshipElement',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/SameAs/1/0',
        cardinality='ZeroToMany',
        order=20,
        display_name={'en': 'Same as'},
        description={'en': 'Same as'},
    )

    bulk_count = SubmodelElement.objects.create(
        template=hierarchy,
        parent_element=nested_node,
        id_short='BulkCount',
        element_type='Property',
        value_type='xs:unsignedLong',
        semantic_id='https://admin-shell.io/idta/HierarchicalStructures/BulkCount/1/0',
        cardinality='ZeroToOne',
        order=20,
        display_name={'en': 'Bulk Count'},
        description={'en': 'Bulk Count'},
    )

def delete_hierarchy_template(apps, schema_editor):
    SubmodelTemplate = apps.get_model('aas_integration', 'SubmodelTemplate')
    SubmodelTemplate.objects.filter(template_id='https://admin-shell.io/idta/SubmodelTemplate/HierarchicalStructuresBoM/1/1').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('aas_integration', '0003_aas_connection_custom_fields'),
    ]

    operations = [
        migrations.RunPython(
            create_hierarchy_template,
            delete_hierarchy_template
        ),
    ]
