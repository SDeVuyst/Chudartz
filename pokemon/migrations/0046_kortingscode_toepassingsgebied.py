# Generated manually for kortingscode toepassingsgebied

import django.db.models.functions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0045_standhouder_tafel_borg"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalkortingscode",
            name="toepassingsgebied",
            field=models.CharField(
                choices=[("tickets", "Tickets"), ("standhouders", "Standhouders")],
                default="tickets",
                help_text="Geldt deze code voor ticketverkoop of standhouder-inschrijvingen?",
                max_length=20,
                verbose_name="Toepassingsgebied",
            ),
        ),
        migrations.AddField(
            model_name="kortingscode",
            name="toepassingsgebied",
            field=models.CharField(
                choices=[("tickets", "Tickets"), ("standhouders", "Standhouders")],
                default="tickets",
                help_text="Geldt deze code voor ticketverkoop of standhouder-inschrijvingen?",
                max_length=20,
                verbose_name="Toepassingsgebied",
            ),
        ),
        migrations.AlterField(
            model_name="historicalkortingscode",
            name="code",
            field=models.CharField(
                db_index=True,
                help_text=(
                    "Zelfde code mag twee keer bestaan: één voor tickets en één voor standhouders."
                ),
                max_length=50,
                verbose_name="Code",
            ),
        ),
        migrations.AlterField(
            model_name="kortingscode",
            name="code",
            field=models.CharField(
                help_text=(
                    "Zelfde code mag twee keer bestaan: één voor tickets en één voor standhouders."
                ),
                max_length=50,
                verbose_name="Code",
            ),
        ),
        migrations.AlterField(
            model_name="kortingscode",
            name="tickets",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Alleen relevant bij toepassingsgebied Tickets. "
                    "Leeg = geldig voor alle tickettypes."
                ),
                to="pokemon.ticket",
                verbose_name="Tickets",
            ),
        ),
        migrations.AddConstraint(
            model_name="kortingscode",
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower("code"),
                "toepassingsgebied",
                name="pokemon_kortingscode_code_toepassingsgebied_ci_uniq",
            ),
        ),
    ]
