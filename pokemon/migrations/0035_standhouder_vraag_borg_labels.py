# Generated manually for cosmetic label rename

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0034_standhouder_prijs_excl_btw"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalstandhoudervraag",
            name="is_borg",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Markeer als niet-terugbetaalbare reservatie- en administratiekost: "
                    "bij een positief antwoord verschijnt op het overzicht een melding "
                    "dat dit bedrag niet wordt terugbetaald bij annulatie."
                ),
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost",
            ),
        ),
        migrations.AlterField(
            model_name="standhoudervraag",
            name="is_borg",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Markeer als niet-terugbetaalbare reservatie- en administratiekost: "
                    "bij een positief antwoord verschijnt op het overzicht een melding "
                    "dat dit bedrag niet wordt terugbetaald bij annulatie."
                ),
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost",
            ),
        ),
    ]
