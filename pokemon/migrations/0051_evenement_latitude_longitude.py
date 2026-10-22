from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0050_indexfoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="evenement",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Breedtegraad van de locatie, bijvoorbeeld 51.209348. "
                    "Samen met longitude verschijnt er een pin op de kaart van de evenementenpagina. "
                    "Leeg laten = geen pin."
                ),
                max_digits=9,
                null=True,
                validators=[
                    MinValueValidator(Decimal("-90")),
                    MaxValueValidator(Decimal("90")),
                ],
                verbose_name="Latitude",
            ),
        ),
        migrations.AddField(
            model_name="evenement",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Lengtegraad van de locatie, bijvoorbeeld 3.224700. "
                    "Beide velden zijn nodig voor een pin."
                ),
                max_digits=9,
                null=True,
                validators=[
                    MinValueValidator(Decimal("-180")),
                    MaxValueValidator(Decimal("180")),
                ],
                verbose_name="Longitude",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Breedtegraad van de locatie, bijvoorbeeld 51.209348. "
                    "Samen met longitude verschijnt er een pin op de kaart van de evenementenpagina. "
                    "Leeg laten = geen pin."
                ),
                max_digits=9,
                null=True,
                validators=[
                    MinValueValidator(Decimal("-90")),
                    MaxValueValidator(Decimal("90")),
                ],
                verbose_name="Latitude",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text=(
                    "Lengtegraad van de locatie, bijvoorbeeld 3.224700. "
                    "Beide velden zijn nodig voor een pin."
                ),
                max_digits=9,
                null=True,
                validators=[
                    MinValueValidator(Decimal("-180")),
                    MaxValueValidator(Decimal("180")),
                ],
                verbose_name="Longitude",
            ),
        ),
    ]
