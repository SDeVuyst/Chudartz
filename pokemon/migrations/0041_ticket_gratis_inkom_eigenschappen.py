from django.db import migrations, models


def copy_eigenschappen_naar_tekst(apps, schema_editor):
    Ticket = apps.get_model("pokemon", "Ticket")
    TicketEigenschap = apps.get_model("pokemon", "TicketEigenschap")

    for ticket in Ticket.objects.all():
        voordelen = list(
            TicketEigenschap.objects.filter(ticket=ticket, is_voordeel=True)
            .order_by("volgorde", "id")
            .values_list("tekst", flat=True)
        )
        nadelen = list(
            TicketEigenschap.objects.filter(ticket=ticket, is_voordeel=False)
            .order_by("volgorde", "id")
            .values_list("tekst", flat=True)
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            voordelen_tekst="\n".join(voordelen),
            nadelen_tekst="\n".join(nadelen),
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0040_zaalplancel_telt_als_tafels"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalticket",
            name="enkel_inkom",
            field=models.BooleanField(
                default=False,
                help_text="Niet online te koop. Bezoekers zien het ticket wel, met de melding dat het enkel aan de inkom verkrijgbaar is. Combineer met 'Gratis' voor een gratis inkomticket.",
                verbose_name="Enkel aan de inkom",
            ),
        ),
        migrations.AddField(
            model_name="historicalticket",
            name="is_gratis",
            field=models.BooleanField(
                default=False,
                help_text="Zet de prijs automatisch op €0,00 en toont 'Gratis' op de site.",
                verbose_name="Gratis",
            ),
        ),
        migrations.AddField(
            model_name="historicalticket",
            name="nadelen_tekst",
            field=models.TextField(
                blank=True,
                help_text="Eén nadeel per regel. Wordt doorgestreept getoond.",
                verbose_name="Nadelen",
            ),
        ),
        migrations.AddField(
            model_name="historicalticket",
            name="voordelen_tekst",
            field=models.TextField(
                blank=True,
                help_text="Eén voordeel per regel. Wordt getoond met een groen vinkje.",
                verbose_name="Voordelen",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="enkel_inkom",
            field=models.BooleanField(
                default=False,
                help_text="Niet online te koop. Bezoekers zien het ticket wel, met de melding dat het enkel aan de inkom verkrijgbaar is. Combineer met 'Gratis' voor een gratis inkomticket.",
                verbose_name="Enkel aan de inkom",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="is_gratis",
            field=models.BooleanField(
                default=False,
                help_text="Zet de prijs automatisch op €0,00 en toont 'Gratis' op de site.",
                verbose_name="Gratis",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="nadelen_tekst",
            field=models.TextField(
                blank=True,
                help_text="Eén nadeel per regel. Wordt doorgestreept getoond.",
                verbose_name="Nadelen",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="voordelen_tekst",
            field=models.TextField(
                blank=True,
                help_text="Eén voordeel per regel. Wordt getoond met een groen vinkje.",
                verbose_name="Voordelen",
            ),
        ),
        migrations.RunPython(copy_eigenschappen_naar_tekst, noop_reverse),
    ]
