# Generated manually for standhouder tafel borg

from decimal import Decimal

import djmoney.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0044_ticket_subtitel_deur"),
    ]

    operations = [
        migrations.AddField(
            model_name="evenement",
            name="standhouder_borg_per_tafel",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                help_text=(
                    "Enkel zonder zaalplan. Deel van de prijs per tafel dat niet "
                    "wordt terugbetaald bij annulatie. 0 = geen borg."
                ),
                max_digits=10,
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost per tafel",
            ),
        ),
        migrations.AddField(
            model_name="evenement",
            name="standhouder_borg_per_tafel_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="standhouder_borg_per_tafel",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                help_text=(
                    "Enkel zonder zaalplan. Deel van de prijs per tafel dat niet "
                    "wordt terugbetaald bij annulatie. 0 = geen borg."
                ),
                max_digits=10,
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost per tafel",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="standhouder_borg_per_tafel_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="zaalplancel",
            name="borg",
            field=djmoney.models.fields.MoneyField(
                blank=True,
                decimal_places=2,
                default_currency="EUR",
                help_text=(
                    "Deel van de tafelprijs dat niet wordt terugbetaald bij annulatie. "
                    "Leeg = geen borg."
                ),
                max_digits=10,
                null=True,
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost",
            ),
        ),
        migrations.AddField(
            model_name="zaalplancel",
            name="borg_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalzaalplancel",
            name="borg",
            field=djmoney.models.fields.MoneyField(
                blank=True,
                decimal_places=2,
                default_currency="EUR",
                help_text=(
                    "Deel van de tafelprijs dat niet wordt terugbetaald bij annulatie. "
                    "Leeg = geen borg."
                ),
                max_digits=10,
                null=True,
                verbose_name="Niet-terugbetaalbare reservatie- en administratiekost",
            ),
        ),
        migrations.AddField(
            model_name="historicalzaalplancel",
            name="borg_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
                null=True,
            ),
        ),
    ]
