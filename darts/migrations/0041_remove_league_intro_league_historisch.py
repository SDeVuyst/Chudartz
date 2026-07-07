from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('darts', '0040_league_leaguedivisie'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalleague',
            name='intro',
        ),
        migrations.RemoveField(
            model_name='league',
            name='intro',
        ),
        migrations.AddField(
            model_name='historicalleague',
            name='historisch',
            field=models.BooleanField(
                default=False,
                help_text='Historische leagues verschijnen niet op het leagues-overzicht, maar wel via de locatiepagina.',
                verbose_name='Historisch',
            ),
        ),
        migrations.AddField(
            model_name='league',
            name='historisch',
            field=models.BooleanField(
                default=False,
                help_text='Historische leagues verschijnen niet op het leagues-overzicht, maar wel via de locatiepagina.',
                verbose_name='Historisch',
            ),
        ),
    ]
