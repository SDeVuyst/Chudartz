from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from pokemon.models import PaymentStatus, StandhouderInschrijving, StandhouderInschrijvingStatus


class Command(BaseCommand):
    help = (
        "Ruim oude concept-inschrijvingen op en zet verlopen standhouder-betalingen "
        "op status 'verlopen'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Verwijder concept-inschrijvingen ouder dan dit aantal dagen.",
        )
        parser.add_argument(
            "--payment-hours",
            type=int,
            default=24,
            help="Markeer wacht-op-betaling inschrijvingen met verlopen betaling na dit aantal uren.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        concept_qs = StandhouderInschrijving.objects.filter(
            status=StandhouderInschrijvingStatus.CONCEPT,
            aangemaakt_op__lt=cutoff,
        )
        concept_count = concept_qs.count()
        concept_qs.delete()

        payment_cutoff = timezone.now() - timedelta(hours=options["payment_hours"])
        expired_qs = StandhouderInschrijving.objects.filter(
            status=StandhouderInschrijvingStatus.WACHT_OP_BETALING,
            payment__status__in=(
                PaymentStatus.EXPIRED,
                PaymentStatus.CANCELED,
                PaymentStatus.FAILED,
            ),
            aangemaakt_op__lt=payment_cutoff,
        )
        expired_count = expired_qs.update(status=StandhouderInschrijvingStatus.VERLOPEN)

        self.stdout.write(
            self.style.SUCCESS(
                f"{concept_count} concept-inschrijving(en) verwijderd, "
                f"{expired_count} verlopen betaling(en) opgeschoond."
            )
        )
