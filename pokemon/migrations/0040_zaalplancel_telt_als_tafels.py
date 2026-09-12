import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pokemon', '0039_gatedevice_remote_debug'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalzaalplancel',
            name='telt_als_tafels',
            field=models.PositiveSmallIntegerField(default=1, help_text='Voor hoeveel tafels dit verkoopbare object meetelt bij het maximum aantal tafels per standhouder. Samengevoegde cellen zijn standaard één tafel; zet dit hoger als het object als meerdere tafels telt.', validators=[django.core.validators.MinValueValidator(1)], verbose_name='Telt als aantal tafels'),
        ),
        migrations.AddField(
            model_name='zaalplancel',
            name='telt_als_tafels',
            field=models.PositiveSmallIntegerField(default=1, help_text='Voor hoeveel tafels dit verkoopbare object meetelt bij het maximum aantal tafels per standhouder. Samengevoegde cellen zijn standaard één tafel; zet dit hoger als het object als meerdere tafels telt.', validators=[django.core.validators.MinValueValidator(1)], verbose_name='Telt als aantal tafels'),
        ),
    ]
