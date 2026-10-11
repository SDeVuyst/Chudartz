# Generated manually for the Ons Team page (groups, members and card content)

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import darts.validators.image_validator


KAART_TYPES = [
    ("dart", "Dart"),
    ("electric", "Elektrisch"),
    ("fire", "Vuur"),
    ("water", "Water"),
    ("grass", "Gras"),
    ("psychic", "Psychisch"),
    ("fighting", "Vecht"),
    ("darkness", "Duister"),
    ("metal", "Metaal"),
    ("colorless", "Kleurloos"),
]

SOCIAL_PLATFORMS = [
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
    ("twitter-x", "X / Twitter"),
    ("linkedin", "LinkedIn"),
    ("envelope-fill", "E-mail"),
    ("globe", "Website"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0048_evenement_aanbod_beschrijving"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeamGroep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("naam", models.CharField(max_length=80, verbose_name="Naam")),
                ("beschrijving", models.TextField(blank=True, verbose_name="Beschrijving")),
                ("zichtbaar", models.BooleanField(default=True, verbose_name="Zichtbaar op de site")),
                ("volgorde", models.PositiveIntegerField(default=0, verbose_name="Volgorde")),
            ],
            options={
                "verbose_name": "Teamgroep",
                "verbose_name_plural": "Teamgroepen",
                "ordering": ["volgorde", "pk"],
            },
        ),
        migrations.CreateModel(
            name="TeamLid",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("volgorde", models.PositiveIntegerField(default=0, verbose_name="Volgorde in groep")),
                ("zichtbaar", models.BooleanField(default=True, verbose_name="Zichtbaar op de site")),
                ("naam", models.CharField(max_length=60, verbose_name="Naam")),
                ("slug", models.SlugField(max_length=70, unique=True, verbose_name="Slug")),
                ("rol", models.CharField(blank=True, max_length=80, verbose_name="Rol")),
                (
                    "bio",
                    models.TextField(
                        blank=True,
                        help_text="Eén of twee zinnen, onder de kaart en bovenaan het detailvenster.",
                        verbose_name="Korte bio",
                    ),
                ),
                (
                    "kaart_type",
                    models.CharField(choices=KAART_TYPES, default="dart", max_length=20, verbose_name="Kaarttype"),
                ),
                (
                    "hp",
                    models.PositiveSmallIntegerField(
                        default=100,
                        validators=[django.core.validators.MaxValueValidator(999)],
                        verbose_name="HP",
                    ),
                ),
                ("fase", models.CharField(default="Basis Teamlid", max_length=40, verbose_name="Fase")),
                (
                    "foto",
                    models.ImageField(
                        blank=True,
                        help_text="Liggend formaat werkt het best (ongeveer 3:2).",
                        upload_to="team/",
                        validators=[darts.validators.image_validator.validate_image_max_size],
                        verbose_name="Foto",
                    ),
                ),
                (
                    "soort",
                    models.CharField(
                        blank=True,
                        help_text="De kleine regel onder de foto, bv. 'Organisator-Pokémon · Lengte 1,85 m'.",
                        max_length=120,
                        verbose_name="Soortregel",
                    ),
                ),
                ("ability_naam", models.CharField(blank=True, max_length=40, verbose_name="Ability naam")),
                ("ability_tekst", models.TextField(blank=True, verbose_name="Ability tekst")),
                (
                    "zwakte",
                    models.CharField(blank=True, choices=KAART_TYPES, max_length=20, verbose_name="Zwakte"),
                ),
                (
                    "zwakte_waarde",
                    models.CharField(blank=True, default="×2", max_length=10, verbose_name="Zwakte waarde"),
                ),
                (
                    "resistentie",
                    models.CharField(blank=True, choices=KAART_TYPES, max_length=20, verbose_name="Resistentie"),
                ),
                (
                    "resistentie_waarde",
                    models.CharField(blank=True, default="-30", max_length=10, verbose_name="Resistentie waarde"),
                ),
                (
                    "terugtrek",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[django.core.validators.MaxValueValidator(5)],
                        verbose_name="Terugtrekkosten",
                    ),
                ),
                ("flavor", models.TextField(blank=True, verbose_name="Flavortekst")),
                (
                    "illustrator",
                    models.CharField(blank=True, default="ChudartZ", max_length=40, verbose_name="Illustrator"),
                ),
                (
                    "slab_label",
                    models.CharField(blank=True, default="GEM MT", max_length=20, verbose_name="Grade label"),
                ),
                ("slab_grade", models.CharField(blank=True, default="10", max_length=4, verbose_name="Grade")),
                (
                    "over",
                    models.TextField(
                        blank=True,
                        help_text="Langere tekst in het detailvenster. Laat een lege regel tussen alinea's.",
                        verbose_name="Over",
                    ),
                ),
                ("quote", models.CharField(blank=True, max_length=200, verbose_name="Quote")),
                (
                    "groep",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="leden",
                        to="pokemon.teamgroep",
                        verbose_name="Groep",
                    ),
                ),
            ],
            options={
                "verbose_name": "Teamlid",
                "verbose_name_plural": "Teamleden",
                "ordering": ["groep__volgorde", "groep_id", "volgorde", "pk"],
            },
        ),
        migrations.CreateModel(
            name="TeamLidAanval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("naam", models.CharField(max_length=40, verbose_name="Naam")),
                (
                    "kost",
                    models.CharField(
                        blank=True,
                        help_text="Kommagescheiden kaarttypes.",
                        max_length=120,
                        verbose_name="Energiekosten",
                    ),
                ),
                ("schade", models.CharField(blank=True, max_length=10, verbose_name="Schade")),
                ("tekst", models.TextField(blank=True, verbose_name="Tekst")),
                ("volgorde", models.PositiveIntegerField(default=0, verbose_name="Volgorde")),
                (
                    "teamlid",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aanvallen",
                        to="pokemon.teamlid",
                    ),
                ),
            ],
            options={
                "verbose_name": "Aanval",
                "verbose_name_plural": "Aanvallen",
                "ordering": ["volgorde", "pk"],
            },
        ),
        migrations.CreateModel(
            name="TeamLidWeetje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=40, verbose_name="Label")),
                ("waarde", models.CharField(max_length=120, verbose_name="Waarde")),
                ("volgorde", models.PositiveIntegerField(default=0, verbose_name="Volgorde")),
                (
                    "teamlid",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weetjes",
                        to="pokemon.teamlid",
                    ),
                ),
            ],
            options={
                "verbose_name": "Kaartgegeven",
                "verbose_name_plural": "Kaartgegevens",
                "ordering": ["volgorde", "pk"],
            },
        ),
        migrations.CreateModel(
            name="TeamLidSocial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=SOCIAL_PLATFORMS, max_length=20, verbose_name="Platform")),
                (
                    "url",
                    models.CharField(
                        help_text="Volledige URL, of een e-mailadres bij E-mail.",
                        max_length=300,
                        verbose_name="Link",
                    ),
                ),
                ("volgorde", models.PositiveIntegerField(default=0, verbose_name="Volgorde")),
                (
                    "teamlid",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="socials",
                        to="pokemon.teamlid",
                    ),
                ),
            ],
            options={
                "verbose_name": "Social link",
                "verbose_name_plural": "Social links",
                "ordering": ["volgorde", "pk"],
            },
        ),
    ]
