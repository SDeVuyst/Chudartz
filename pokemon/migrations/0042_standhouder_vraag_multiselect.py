from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0041_ticket_gratis_inkom_eigenschappen"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalstandhoudervraag",
            name="max_selecties",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Alleen voor meervoudige keuze: maximum aantal te selecteren items.",
                null=True,
                verbose_name="Max. selecties",
            ),
        ),
        migrations.AddField(
            model_name="historicalstandhoudervraag",
            name="min_selecties",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Alleen voor meervoudige keuze: minimum aantal te selecteren items.",
                null=True,
                verbose_name="Min. selecties",
            ),
        ),
        migrations.AddField(
            model_name="standhoudervraag",
            name="max_selecties",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Alleen voor meervoudige keuze: maximum aantal te selecteren items.",
                null=True,
                verbose_name="Max. selecties",
            ),
        ),
        migrations.AddField(
            model_name="standhoudervraag",
            name="min_selecties",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Alleen voor meervoudige keuze: minimum aantal te selecteren items.",
                null=True,
                verbose_name="Min. selecties",
            ),
        ),
        migrations.AlterField(
            model_name="historicalstandhoudervraag",
            name="opties",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Voor keuzelijst: één label per regel. "
                    "Voor meervoudige keuze: JSON-lijst met label en optionele prijs."
                ),
                verbose_name="Opties (één per regel, voor keuzelijst)",
            ),
        ),
        migrations.AlterField(
            model_name="historicalstandhoudervraag",
            name="prijs_toeslag_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Aan: de toeslag is exclusief BTW; het BTW-percentage wordt "
                    "achteraf bij het totaal opgeteld. Voor meervoudige keuze geldt dit "
                    "voor alle optieprijzen."
                ),
                verbose_name="Toeslag exclusief BTW",
            ),
        ),
        migrations.AlterField(
            model_name="historicalstandhoudervraag",
            name="vraag_type",
            field=models.CharField(
                choices=[
                    ("tekst", "Tekst"),
                    ("textarea", "Lange tekst"),
                    ("boolean", "Ja/Nee"),
                    ("checkbox", "Checkbox"),
                    ("number", "Getal"),
                    ("select", "Keuzelijst"),
                    ("multiselect", "Meervoudige keuze"),
                ],
                default="boolean",
                max_length=15,
                verbose_name="Type",
            ),
        ),
        migrations.AlterField(
            model_name="standhoudervraag",
            name="opties",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Voor keuzelijst: één label per regel. "
                    "Voor meervoudige keuze: JSON-lijst met label en optionele prijs."
                ),
                verbose_name="Opties (één per regel, voor keuzelijst)",
            ),
        ),
        migrations.AlterField(
            model_name="standhoudervraag",
            name="prijs_toeslag_excl_btw",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Aan: de toeslag is exclusief BTW; het BTW-percentage wordt "
                    "achteraf bij het totaal opgeteld. Voor meervoudige keuze geldt dit "
                    "voor alle optieprijzen."
                ),
                verbose_name="Toeslag exclusief BTW",
            ),
        ),
        migrations.AlterField(
            model_name="standhoudervraag",
            name="vraag_type",
            field=models.CharField(
                choices=[
                    ("tekst", "Tekst"),
                    ("textarea", "Lange tekst"),
                    ("boolean", "Ja/Nee"),
                    ("checkbox", "Checkbox"),
                    ("number", "Getal"),
                    ("select", "Keuzelijst"),
                    ("multiselect", "Meervoudige keuze"),
                ],
                default="boolean",
                max_length=15,
                verbose_name="Type",
            ),
        ),
    ]
