# Generated manually for standhouder BTW settings

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0033_gatedevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="evenement",
            name="standhouder_prijs_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: de prijs per tafel is exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Prijs per tafel exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="evenement",
            name="standhouder_prijs_btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage (prijs per tafel)",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="standhouder_prijs_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: de prijs per tafel is exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Prijs per tafel exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="historicalevenement",
            name="standhouder_prijs_btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage (prijs per tafel)",
            ),
        ),
        migrations.AddField(
            model_name="zaalplan",
            name="prijs_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: standaardprijs en prijs-overrides zijn exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Tafelprijzen exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="zaalplan",
            name="btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage",
            ),
        ),
        migrations.AddField(
            model_name="historicalzaalplan",
            name="prijs_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: standaardprijs en prijs-overrides zijn exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Tafelprijzen exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="historicalzaalplan",
            name="btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage",
            ),
        ),
        migrations.AddField(
            model_name="standhoudervraag",
            name="prijs_toeslag_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: de toeslag is exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Toeslag exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="standhoudervraag",
            name="prijs_toeslag_btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage (toeslag)",
            ),
        ),
        migrations.AddField(
            model_name="historicalstandhoudervraag",
            name="prijs_toeslag_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text="Aan: de toeslag is exclusief BTW; het BTW-percentage wordt achteraf bij het totaal opgeteld.",
                verbose_name="Toeslag exclusief BTW",
            ),
        ),
        migrations.AddField(
            model_name="historicalstandhoudervraag",
            name="prijs_toeslag_btw_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("21.00"),
                help_text="Standaard 21%. Alleen gebruikt als 'exclusief BTW' aan staat.",
                max_digits=5,
                verbose_name="BTW-percentage (toeslag)",
            ),
        ),
    ]
