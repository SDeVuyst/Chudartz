# Generated manually for AanbodItem / EvenementAanbod

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0046_kortingscode_toepassingsgebied"),
    ]

    operations = [
        migrations.CreateModel(
            name="AanbodItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("naam", models.CharField(max_length=80, verbose_name="Naam")),
                ("icoon", models.ImageField(blank=True, null=True, upload_to="aanbod_iconen/", verbose_name="Icoon / logo")),
                ("actief", models.BooleanField(default=True, verbose_name="Actief")),
            ],
            options={
                "verbose_name": "Aanbod-item",
                "verbose_name_plural": "Aanbod-items",
                "ordering": ["naam"],
            },
        ),
        migrations.CreateModel(
            name="EvenementAanbod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("volgorde", models.PositiveSmallIntegerField(default=0, verbose_name="Volgorde")),
                (
                    "evenement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aanbod_links",
                        to="pokemon.evenement",
                        verbose_name="Evenement",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evenement_links",
                        to="pokemon.aanboditem",
                        verbose_name="Aanbod-item",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evenement-aanbod",
                "verbose_name_plural": "Evenement-aanbod",
                "ordering": ["volgorde", "pk"],
                "unique_together": {("evenement", "item")},
            },
        ),
        migrations.AddField(
            model_name="evenement",
            name="aanbod",
            field=models.ManyToManyField(
                blank=True,
                related_name="evenementen",
                through="pokemon.EvenementAanbod",
                to="pokemon.aanboditem",
                verbose_name="Wat kan je vinden",
            ),
        ),
    ]
