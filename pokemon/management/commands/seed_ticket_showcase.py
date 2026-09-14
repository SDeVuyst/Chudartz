from datetime import datetime
from decimal import Decimal

import pytz
from django.core.management.base import BaseCommand
from djmoney.money import Money

from pokemon.models import Evenement, Ticket

BRUSSELS = pytz.timezone("Europe/Brussels")
IMAGE = "darts/test.png"

STANDHOUDER_INBEGREPEN = "Stoel\nTafel"
STANDHOUDER_PRIJZEN = "1 tafel: 50 euro"

EVENTS = [
    {
        "slug": "ticket-demo-overzicht",
        "titel": "Tickettypes — overzicht",
        "titel_sectie_a": "Alle tickettypes",
        "intro": "Demo-evenement met alle tickettypes naast elkaar: online, gratis, aan de inkom en gratis inkomticket.",
        "tekst": (
            "<p>Dit evenement toont de vier tickettypes op één pagina. "
            "Gebruik het om de kaarten, knoppen en de ticketwizard te vergelijken.</p>"
        ),
        "start": datetime(2026, 10, 18, 10, 0),
        "einde": datetime(2026, 10, 18, 17, 0),
        "volgorde": 10,
        "tickets": [
            {
                "titel": "Standaard ticket",
                "price": Decimal("8.00"),
                "icon": "ticket-perforated",
                "is_gratis": False,
                "enkel_inkom": False,
                "voordelen_tekst": "Online te koop\nToegang tot de beurs\nQR-ticket per e-mail",
                "nadelen_tekst": "",
            },
            {
                "titel": "Gratis ticket",
                "price": Decimal("0.00"),
                "icon": "gift",
                "is_gratis": True,
                "enkel_inkom": False,
                "voordelen_tekst": "Gratis reservatie\nOnline reserveren\nQR-ticket per e-mail",
                "nadelen_tekst": "",
            },
            {
                "titel": "Ticket aan de inkom",
                "price": Decimal("10.00"),
                "icon": "door-open",
                "is_gratis": False,
                "enkel_inkom": True,
                "voordelen_tekst": "Te koop aan de kassa\nToegang tot de beurs",
                "nadelen_tekst": "Niet online te koop",
            },
            {
                "titel": "Gratis inkomticket",
                "price": Decimal("0.00"),
                "icon": "ticket",
                "is_gratis": True,
                "enkel_inkom": True,
                "voordelen_tekst": "Gratis aan de inkom\nGeen reservatie nodig",
                "nadelen_tekst": "Niet online te reserveren",
            },
        ],
    },
    {
        "slug": "ticket-demo-gratis",
        "titel": "Tickettypes — gratis",
        "titel_sectie_a": "Gratis tickets",
        "intro": "Demo-evenement met enkel een gratis ticket dat online gereserveerd kan worden.",
        "tekst": (
            "<p>Dit ticket is gratis (prijs €0,00). Bezoekers reserveren het online "
            "en krijgen een QR-ticket zonder betaling.</p>"
        ),
        "start": datetime(2026, 10, 19, 10, 0),
        "einde": datetime(2026, 10, 19, 17, 0),
        "volgorde": 20,
        "tickets": [
            {
                "titel": "Gratis toegang",
                "price": Decimal("0.00"),
                "icon": "gift",
                "is_gratis": True,
                "enkel_inkom": False,
                "voordelen_tekst": "Gratis reservatie\nOnline reserveren\nQR-ticket per e-mail",
                "nadelen_tekst": "",
            },
        ],
    },
    {
        "slug": "ticket-demo-inkom",
        "titel": "Tickettypes — aan de inkom",
        "titel_sectie_a": "Enkel aan de inkom",
        "intro": "Demo-evenement met een ticket dat enkel aan de inkom te koop is.",
        "tekst": (
            "<p>Dit ticket is niet online te koop. Bezoekers zien de prijs op de site "
            "en kopen het aan de kassa.</p>"
        ),
        "start": datetime(2026, 10, 20, 10, 0),
        "einde": datetime(2026, 10, 20, 17, 0),
        "volgorde": 30,
        "tickets": [
            {
                "titel": "Dagticket aan de kassa",
                "price": Decimal("12.00"),
                "icon": "door-open",
                "is_gratis": False,
                "enkel_inkom": True,
                "voordelen_tekst": "Te koop aan de inkom\nToegang tot de beurs\nContant of kaart",
                "nadelen_tekst": "Niet online te koop",
            },
        ],
    },
    {
        "slug": "ticket-demo-gratis-inkom",
        "titel": "Tickettypes — gratis aan de inkom",
        "titel_sectie_a": "Gratis inkomticket",
        "intro": "Demo-evenement met een gratis ticket dat enkel aan de inkom verkrijgbaar is.",
        "tekst": (
            "<p>Gratis én enkel aan de inkom. De site toont “Gratis” en “Aan de inkom”; "
            "er is geen online reservatie.</p>"
        ),
        "start": datetime(2026, 10, 21, 10, 0),
        "einde": datetime(2026, 10, 21, 17, 0),
        "volgorde": 40,
        "tickets": [
            {
                "titel": "Gratis inkomticket",
                "price": Decimal("0.00"),
                "icon": "ticket",
                "is_gratis": True,
                "enkel_inkom": True,
                "voordelen_tekst": "Gratis aan de inkom\nGeen reservatie nodig",
                "nadelen_tekst": "Niet online te reserveren",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Maak demo-evenementen aan die de nieuwe tickettypes tonen."

    def handle(self, *args, **options):
        created_events = 0
        updated_events = 0

        for spec in EVENTS:
            evenement, created = Evenement.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "titel": spec["titel"],
                    "intro_op_index": spec["intro"],
                    "titel_sectie_a": spec["titel_sectie_a"],
                    "tekst_sectie_a": spec["tekst"],
                    "start_datum": BRUSSELS.localize(spec["start"]),
                    "einde_datum": BRUSSELS.localize(spec["einde"]),
                    "max_deelnemers": 200,
                    "locatie_kort": "Testhal",
                    "locatie_lang": "Testhal, Teststraat 1",
                    "afbeelding": IMAGE,
                    "standhouder_inbegrepen": STANDHOUDER_INBEGREPEN,
                    "standhouder_prijzen": STANDHOUDER_PRIJZEN,
                    "enable_standhouder": False,
                    "enable_inschrijvingen": True,
                    "toon_op_site": True,
                    "highlight_event": spec["slug"] == "ticket-demo-overzicht",
                    "volgorde": spec["volgorde"],
                },
            )
            if created:
                created_events += 1
            else:
                updated_events += 1

            evenement.ticket_set.all().delete()
            for ticket_spec in spec["tickets"]:
                Ticket.objects.create(
                    event=evenement,
                    titel=ticket_spec["titel"],
                    price=Money(ticket_spec["price"], "EUR"),
                    icon=ticket_spec["icon"],
                    max_deelnemers=100,
                    disable_ticket=False,
                    is_gratis=ticket_spec["is_gratis"],
                    enkel_inkom=ticket_spec["enkel_inkom"],
                    voordelen_tekst=ticket_spec["voordelen_tekst"],
                    nadelen_tekst=ticket_spec["nadelen_tekst"],
                )

            self.stdout.write(
                f"{'Aangemaakt' if created else 'Bijgewerkt'}: {evenement.titel} "
                f"({evenement.ticket_set.count()} tickets)"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Klaar: {created_events} nieuw, {updated_events} bijgewerkt."
        ))
