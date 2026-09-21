# Generated manually for optional aanbod description

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0047_aanbod_item_evenement_aanbod"),
    ]

    operations = [
        migrations.AddField(
            model_name="evenement",
            name="aanbod_beschrijving",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Optionele korte tekst onder de titel 'Wat kan je vinden'. "
                    "Leeg laten = niet tonen."
                ),
                verbose_name="Aanbod-beschrijving",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="aanbod_beschrijving",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Optionele korte tekst onder de titel 'Wat kan je vinden'. "
                    "Leeg laten = niet tonen."
                ),
                verbose_name="Aanbod-beschrijving",
            ),
        ),
    ]
