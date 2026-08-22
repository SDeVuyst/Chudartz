from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('darts', '0043_toernooi_naar_dartskamp'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalleaguedivisie',
            name='stand_boven_uitslagen',
            field=models.BooleanField(
                default=False,
                help_text='Toon stand en uitslagen onder elkaar op volle breedte (stand eerst). Standaard staan ze naast elkaar.',
                verbose_name='Stand boven uitslagen',
            ),
        ),
        migrations.AddField(
            model_name='leaguedivisie',
            name='stand_boven_uitslagen',
            field=models.BooleanField(
                default=False,
                help_text='Toon stand en uitslagen onder elkaar op volle breedte (stand eerst). Standaard staan ze naast elkaar.',
                verbose_name='Stand boven uitslagen',
            ),
        ),
    ]
