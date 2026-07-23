import django.db.models.deletion
from decimal import Decimal

import darts.validators.image_validator
import djmoney.models.fields
from django.conf import settings
from django.db import migrations, models


def migrate_ticket_data_to_kamp(apps, schema_editor):
    Dartskamp = apps.get_model("darts", "Dartskamp")
    Ticket = apps.get_model("darts", "Ticket")
    Participant = apps.get_model("darts", "Participant")

    for kamp in Dartskamp.objects.all():
        first_ticket = Ticket.objects.filter(event_id=kamp.pk).order_by("pk").first()
        if first_ticket is not None:
            kamp.prijs = first_ticket.price
            kamp.prijs_currency = getattr(first_ticket, "price_currency", None) or "EUR"
            kamp.save(update_fields=["prijs", "prijs_currency"])

    for participant in Participant.objects.all().iterator():
        ticket = Ticket.objects.filter(pk=participant.ticket_id).first()
        if ticket is not None:
            participant.dartskamp_id = ticket.event_id
            participant.save(update_fields=["dartskamp_id"])

    # Orphan participants without a resolvable ticket cannot keep a non-null FK
    Participant.objects.filter(dartskamp_id__isnull=True).delete()


def migrate_indexfoto_category(apps, schema_editor):
    IndexFoto = apps.get_model("darts", "IndexFoto")
    IndexFoto.objects.filter(category="toernooi").update(category="dartskamp")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("darts", "0042_ticket_toegang_times"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name="ToernooiHeaderGroep", new_name="DartskampHeaderGroep"),
        migrations.RenameModel(old_name="Toernooi", new_name="Dartskamp"),
        migrations.RenameModel(old_name="HistoricalToernooi", new_name="HistoricalDartskamp"),
        migrations.RenameModel(old_name="ToernooiFoto", new_name="DartskampFoto"),
        migrations.AlterModelOptions(
            name="dartskampheadergroep",
            options={
                "verbose_name": "Dartskamp Header Groep",
                "verbose_name_plural": "Dartskamp Header Groepen",
            },
        ),
        migrations.AlterModelOptions(
            name="dartskamp",
            options={
                "get_latest_by": "start_datum",
                "ordering": ["-start_datum"],
                "verbose_name": "Dartskamp",
                "verbose_name_plural": "Dartskampen",
            },
        ),
        migrations.AlterModelOptions(
            name="historicaldartskamp",
            options={
                "get_latest_by": ("history_date", "history_id"),
                "ordering": ("-history_date", "-history_id"),
                "verbose_name": "Geschiedenis",
                "verbose_name_plural": "historical Dartskampen",
            },
        ),
        migrations.AlterModelOptions(
            name="dartskampfoto",
            options={
                "ordering": ["volgorde", "id"],
                "verbose_name": "Dartskamp Foto",
                "verbose_name_plural": "Dartskamp Foto's",
            },
        ),
        migrations.RenameField(
            model_name="dartskampfoto",
            old_name="toernooi",
            new_name="dartskamp",
        ),
        migrations.AlterField(
            model_name="dartskampfoto",
            name="afbeelding",
            field=models.ImageField(
                upload_to="dartskamp_fotos",
                validators=[darts.validators.image_validator.validate_image_max_size],
                verbose_name="Foto",
            ),
        ),
        migrations.AlterField(
            model_name="dartskampfoto",
            name="dartskamp",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="fotos",
                to="darts.dartskamp",
                verbose_name="Dartskamp",
            ),
        ),
        migrations.AlterField(
            model_name="dartskamp",
            name="header_groepen",
            field=models.ManyToManyField(
                blank=True,
                related_name="dartskampen",
                to="darts.dartskampheadergroep",
                verbose_name="Groepen in header",
            ),
        ),
        migrations.AddField(
            model_name="dartskamp",
            name="prijs_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="historicaldartskamp",
            name="prijs_currency",
            field=djmoney.models.fields.CurrencyField(
                default="EUR",
                editable=False,
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="dartskamp",
            name="prijs",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                max_digits=10,
                verbose_name="Prijs",
            ),
        ),
        migrations.AddField(
            model_name="historicaldartskamp",
            name="prijs",
            field=djmoney.models.fields.MoneyField(
                decimal_places=2,
                default=Decimal("0"),
                default_currency="EUR",
                max_digits=10,
                verbose_name="Prijs",
            ),
        ),
        migrations.AddField(
            model_name="participant",
            name="dartskamp",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="deelnemers",
                to="darts.dartskamp",
                verbose_name="Dartskamp",
            ),
        ),
        migrations.AddField(
            model_name="historicalparticipant",
            name="dartskamp",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="darts.dartskamp",
                verbose_name="Dartskamp",
            ),
        ),
        migrations.RunPython(migrate_ticket_data_to_kamp, noop_reverse),
        migrations.AlterField(
            model_name="participant",
            name="dartskamp",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="deelnemers",
                to="darts.dartskamp",
                verbose_name="Dartskamp",
            ),
        ),
        migrations.RemoveField(model_name="participant", name="ticket"),
        migrations.RemoveField(model_name="participant", name="attended"),
        migrations.RemoveField(model_name="participant", name="random_seed"),
        migrations.RemoveField(model_name="historicalparticipant", name="ticket"),
        migrations.RemoveField(model_name="historicalparticipant", name="attended"),
        migrations.RemoveField(model_name="historicalparticipant", name="random_seed"),
        migrations.DeleteModel(name="HistoricalTicket"),
        migrations.DeleteModel(name="Ticket"),
        migrations.RunPython(migrate_indexfoto_category, noop_reverse),
        migrations.AlterField(
            model_name="indexfoto",
            name="category",
            field=models.CharField(
                choices=[
                    ("dartschool", "Dartschool"),
                    ("dartskamp", "Dartskamp"),
                    ("andere", "Andere"),
                ],
                default="dartschool",
                max_length=10,
                verbose_name="Categorie",
            ),
        ),
    ]
