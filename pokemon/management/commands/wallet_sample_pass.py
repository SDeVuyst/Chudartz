from datetime import datetime
from decimal import Decimal

import pytz
from django.core.management.base import BaseCommand, CommandError
from djmoney.money import Money

from pokemon.models import Evenement, Participant, Ticket
from pokemon.services import wallet, wallet_apple, wallet_google

BRUSSELS = pytz.timezone("Europe/Brussels")


def _demo_participant():
    evenement = Evenement(
        pk=0,
        titel="Pokébeurs Demo",
        slug="pokebeurs-demo",
        start_datum=BRUSSELS.localize(datetime(2030, 7, 6, 10, 0)),
        einde_datum=BRUSSELS.localize(datetime(2030, 7, 6, 17, 0)),
        locatie_kort="Brugge",
        locatie_lang="Beurshal Brugge\nBeursplein 1, 8000 Brugge",
        latitude=Decimal("51.209348"),
        longitude=Decimal("3.224700"),
    )
    ticket = Ticket(pk=0, titel="Standaard ticket", price=Money(8, "EUR"), event=evenement)
    return Participant(pk=0, random_seed="DEMO000000", ticket=ticket)


class Command(BaseCommand):
    help = "Write a sample Apple Wallet pass and print a Google Wallet save link, using the wallet env vars."

    def add_arguments(self, parser):
        parser.add_argument("--participant", type=int, help="Participant pk (omit for an unsaved demo ticket).")
        parser.add_argument("--out", default="sample.pkpass", help="Where to write the .pkpass file.")

    def handle(self, *args, **options):
        if options["participant"] is not None:
            try:
                participant = Participant.objects.select_related("ticket__event", "payment").get(
                    pk=options["participant"]
                )
            except Participant.DoesNotExist:
                raise CommandError(f"Participant {options['participant']} does not exist")
        else:
            participant = _demo_participant()

        apple = wallet.apple_config()
        if apple:
            with open(options["out"], "wb") as handle:
                handle.write(wallet_apple.build_pkpass(participant, apple))
            self.stdout.write(self.style.SUCCESS(f"Apple pass written to {options['out']}"))
        else:
            self.stdout.write(self.style.WARNING("Apple Wallet env vars missing or invalid; skipped."))

        google = wallet.google_config()
        if google:
            self.stdout.write(self.style.SUCCESS("Google Wallet save link:"))
            self.stdout.write(wallet_google.save_url([participant], google))
        else:
            self.stdout.write(self.style.WARNING("Google Wallet env vars missing or invalid; skipped."))
