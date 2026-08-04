# Generated manually for standhouder factuur fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0035_standhouder_vraag_borg_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalstandhouderinschrijving",
            name="btw_of_kvk_nummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="BTW-nummer of KVK-nummer",
            ),
        ),
        migrations.AddField(
            model_name="historicalstandhouderinschrijving",
            name="bedrijfsnummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="Bedrijfsnummer",
            ),
        ),
        migrations.AddField(
            model_name="standhouderinschrijving",
            name="btw_of_kvk_nummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="BTW-nummer of KVK-nummer",
            ),
        ),
        migrations.AddField(
            model_name="standhouderinschrijving",
            name="bedrijfsnummer",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="Bedrijfsnummer",
            ),
        ),
    ]
