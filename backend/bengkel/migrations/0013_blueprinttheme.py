from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bengkel', '0012_spafpainpoint_spafproblemstatement_spafriskanalysis_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlueprintTheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('urutan', models.PositiveIntegerField(default=0)),
                ('tema', models.CharField(max_length=300)),
                ('penerangan', models.TextField()),
                ('kata_kunci', models.TextField(blank=True)),
                ('frequency', models.PositiveIntegerField(default=1)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('bengkel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blueprint_themes',
                    to='bengkel.bengkel',
                )),
            ],
            options={
                'verbose_name': 'Blueprint \u2014 Tema',
                'verbose_name_plural': 'Blueprint \u2014 Tema',
                'ordering': ['urutan', 'id'],
            },
        ),
    ]
