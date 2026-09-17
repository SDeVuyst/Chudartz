# Generated manually for standhouder BTW label rename

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0042_standhouder_vraag_multiselect"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalstandhouderinschrijving",
            name="btw_of_kvk_nummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="BTW-nummer",
            ),
        ),
        migrations.AlterField(
            model_name="standhouderinschrijving",
            name="btw_of_kvk_nummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="BTW-nummer",
            ),
        ),
    ]
