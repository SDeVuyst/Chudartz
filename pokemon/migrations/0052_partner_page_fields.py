import ckeditor.fields
from django.db import migrations, models


def add_partner_page_fields(apps, schema_editor):
    connection = schema_editor.connection
    table = "pokemon_partner"

    with connection.cursor() as cursor:
        existing = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table)
        }

        if "info" not in existing:
            cursor.execute(
                f'ALTER TABLE "{table}" ADD COLUMN "info" text NOT NULL DEFAULT \'\''
            )
        if "toon_knop" not in existing:
            cursor.execute(
                f'ALTER TABLE "{table}" ADD COLUMN "toon_knop" boolean NOT NULL DEFAULT true'
            )
        if "toon_op_pagina" not in existing:
            cursor.execute(
                f'ALTER TABLE "{table}" '
                f'ADD COLUMN "toon_op_pagina" boolean NOT NULL DEFAULT true'
            )
        if "volgorde" not in existing:
            cursor.execute(
                f'ALTER TABLE "{table}" '
                f'ADD COLUMN "volgorde" smallint NOT NULL DEFAULT 0'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0051_evenement_latitude_longitude"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="partner",
                    name="info",
                    field=ckeditor.fields.RichTextField(
                        blank=True,
                        verbose_name="Info over Partner",
                    ),
                ),
                migrations.AddField(
                    model_name="partner",
                    name="toon_knop",
                    field=models.BooleanField(
                        default=True,
                        verbose_name="Toon knop op partnerpagina",
                    ),
                ),
                migrations.AddField(
                    model_name="partner",
                    name="toon_op_pagina",
                    field=models.BooleanField(
                        default=True,
                        verbose_name="Toon op partnerpagina",
                    ),
                ),
                migrations.AddField(
                    model_name="partner",
                    name="volgorde",
                    field=models.SmallIntegerField(
                        default=0,
                        verbose_name="Volgorde op pagina",
                    ),
                ),
                migrations.AlterModelOptions(
                    name="partner",
                    options={
                        "ordering": ["volgorde", "name"],
                        "verbose_name": "Partner",
                        "verbose_name_plural": "Partners",
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(add_partner_page_fields, noop_reverse),
            ],
        ),
    ]
