from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pokemon', '0031_ticket_toegang_times'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evenement',
            name='standhouder_max_tafels',
            field=models.PositiveIntegerField(
                default=3,
                help_text=(
                    'Maximum aantal tafels dat één standhouder mag kiezen of opgeven, '
                    'ongeacht of het zaalplan aan of uit staat.'
                ),
                verbose_name='Max. aantal tafels per standhouder',
            ),
        ),
        migrations.AlterField(
            model_name='historicalevenement',
            name='standhouder_max_tafels',
            field=models.PositiveIntegerField(
                default=3,
                help_text=(
                    'Maximum aantal tafels dat één standhouder mag kiezen of opgeven, '
                    'ongeacht of het zaalplan aan of uit staat.'
                ),
                verbose_name='Max. aantal tafels per standhouder',
            ),
        ),
    ]
