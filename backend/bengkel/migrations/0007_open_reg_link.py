import uuid
from django.db import migrations, models


def populate_reg_tokens(apps, schema_editor):
    Bengkel = apps.get_model('bengkel', 'Bengkel')
    for b in Bengkel.objects.all():
        b.reg_token = uuid.uuid4()
        b.save(update_fields=['reg_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('bengkel', '0006_email_optional'),
    ]

    operations = [
        # Add as nullable first so existing rows can be populated
        migrations.AddField(
            model_name='bengkel',
            name='reg_token',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name='bengkel',
            name='reg_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='bengkel',
            name='reg_had',
            field=models.PositiveIntegerField(default=0),
        ),
        # Give each existing row a unique token
        migrations.RunPython(populate_reg_tokens, migrations.RunPython.noop),
        # Now make it not-null and unique
        migrations.AlterField(
            model_name='bengkel',
            name='reg_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
