# Generated manually for ticket wizard + kortingscodes

import djmoney.models.fields
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0029_standhouder_mollie_betaling"),
    ]

    operations = [
        migrations.CreateModel(
            name="Kortingscode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True, verbose_name="Code")),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("percent", "Percentage"), ("fixed", "Vast bedrag")],
                        default="percent",
                        max_length=10,
                        verbose_name="Type korting",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Percentage (0-100) of vast bedrag in euro.",
                        max_digits=10,
                        verbose_name="Waarde",
                    ),
                ),
                ("geldig_van", models.DateTimeField(blank=True, null=True, verbose_name="Geldig vanaf")),
                ("geldig_tot", models.DateTimeField(blank=True, null=True, verbose_name="Geldig tot")),
                (
                    "max_gebruik",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Leeg = onbeperkt.",
                        null=True,
                        verbose_name="Max. aantal keer te gebruiken",
                    ),
                ),
                ("aantal_gebruikt", models.PositiveIntegerField(default=0, verbose_name="Aantal keer gebruikt")),
                ("actief", models.BooleanField(default=True, verbose_name="Actief")),
                (
                    "min_bedrag_currency",
                    djmoney.models.fields.CurrencyField(
                        choices=[("EUR", "Euro")],
                        default="EUR",
                        editable=False,
                        max_length=3,
                        null=True,
                    ),
                ),
                (
                    "min_bedrag",
                    djmoney.models.fields.MoneyField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Minimum bestelbedrag",
                    ),
                ),
                ("evenementen", models.ManyToManyField(blank=True, help_text="Leeg = geldig voor alle evenementen.", to="pokemon.evenement", verbose_name="Evenementen")),
                ("tickets", models.ManyToManyField(blank=True, help_text="Leeg = geldig voor alle tickettypes.", to="pokemon.ticket", verbose_name="Tickets")),
            ],
            options={
                "verbose_name": "Kortingscode",
                "verbose_name_plural": "Kortingscodes",
            },
        ),
        migrations.CreateModel(
            name="HistoricalKortingscode",
            fields=[
                ("id", models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=50, verbose_name="Code")),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("percent", "Percentage"), ("fixed", "Vast bedrag")],
                        default="percent",
                        max_length=10,
                        verbose_name="Type korting",
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Percentage (0-100) of vast bedrag in euro.",
                        max_digits=10,
                        verbose_name="Waarde",
                    ),
                ),
                ("geldig_van", models.DateTimeField(blank=True, null=True, verbose_name="Geldig vanaf")),
                ("geldig_tot", models.DateTimeField(blank=True, null=True, verbose_name="Geldig tot")),
                (
                    "max_gebruik",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Leeg = onbeperkt.",
                        null=True,
                        verbose_name="Max. aantal keer te gebruiken",
                    ),
                ),
                ("aantal_gebruikt", models.PositiveIntegerField(default=0, verbose_name="Aantal keer gebruikt")),
                ("actief", models.BooleanField(default=True, verbose_name="Actief")),
                (
                    "min_bedrag_currency",
                    djmoney.models.fields.CurrencyField(
                        choices=[("EUR", "Euro")],
                        default="EUR",
                        editable=False,
                        max_length=3,
                        null=True,
                    ),
                ),
                (
                    "min_bedrag",
                    djmoney.models.fields.MoneyField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Minimum bestelbedrag",
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical Kortingscode",
                "verbose_name_plural": "historical Kortingscodes",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddField(
            model_name="payment",
            name="korting_bedrag",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                max_digits=10,
                verbose_name="Korting",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="korting_bedrag_currency",
            field=djmoney.models.fields.CurrencyField(
                choices=[("EUR", "Euro")],
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="subtotaal",
            field=djmoney.models.fields.MoneyField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name="Subtotaal",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="subtotaal_currency",
            field=djmoney.models.fields.CurrencyField(
                choices=[("EUR", "Euro")],
                default="EUR",
                editable=False,
                max_length=3,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="kortingscode",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="betalingen",
                to="pokemon.kortingscode",
                verbose_name="Kortingscode",
            ),
        ),
        migrations.AddField(
            model_name="historicalpayment",
            name="korting_bedrag",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                max_digits=10,
                verbose_name="Korting",
            ),
        ),
        migrations.AddField(
            model_name="historicalpayment",
            name="korting_bedrag_currency",
            field=djmoney.models.fields.CurrencyField(
                choices=[("EUR", "Euro")],
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="historicalpayment",
            name="subtotaal",
            field=djmoney.models.fields.MoneyField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name="Subtotaal",
            ),
        ),
        migrations.AddField(
            model_name="historicalpayment",
            name="subtotaal_currency",
            field=djmoney.models.fields.CurrencyField(
                choices=[("EUR", "Euro")],
                default="EUR",
                editable=False,
                max_length=3,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="historicalpayment",
            name="kortingscode",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="pokemon.kortingscode",
                verbose_name="Kortingscode",
            ),
        ),
    ]
