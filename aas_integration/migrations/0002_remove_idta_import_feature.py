from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def delete_imported_templates(apps, schema_editor):
    """
    Delete templates that were created via JSON import (have idta_json set).
    Built-in templates have idta_json=None, so they are preserved.
    """
    SubmodelTemplate = apps.get_model('aas_integration', 'SubmodelTemplate')

    deleted = SubmodelTemplate.objects.filter(
        models.Q(idta_json__isnull=False) | models.Q(source_type='IMPORTED')
    ).delete()

    if deleted[0] > 0:
        print(f"Migration 0002: Deleted {deleted[0]} imported template(s)")


class Migration(migrations.Migration):

    dependencies = [
        ('aas_integration', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(delete_imported_templates, migrations.RunPython.noop),

        migrations.RemoveField(
            model_name='submodeltemplate',
            name='idta_json',
        ),

        migrations.AlterField(
            model_name='submodeltemplate',
            name='source_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('IDTA', _('IDTA Standard')),
                    ('CUSTOM', _('Custom Definition')),
                ],
                default='CUSTOM',
                help_text=_('Source of this template definition'),
            ),
        ),
    ]
