from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from chudartz.services.calcom import get_upcoming_bookings
from chudartz.services.mollie_stats import MOLLIE_DASHBOARD_URL, get_mollie_stats
from darts.models import Dartskamp, Leerling, Participant as DartsParticipant, PaymentStatus as DartsPaymentStatus
from pokemon.models import (
    Evenement,
    Participant as PokemonParticipant,
    PaymentStatus as PokemonPaymentStatus,
    StandhouderInschrijving,
    StandhouderInschrijvingStatus,
    Ticket,
)

DASHBOARD_VIEWS = ("darts", "collectibles")

EXTERNAL_LINKS = [
    {
        "title": "Mollie",
        "icon": "payments",
        "url": "https://my.mollie.com/dashboard/org_19161509/home",
    },
    {
        "title": "Analytics",
        "icon": "query_stats",
        "url": "https://analytics.google.com/",
    },
    {
        "title": "Cal.com",
        "icon": "calendar_month",
        "url": "https://app.cal.com/bookings/upcoming",
    },
]


@dataclass
class ActivityItem:
    sort_key: datetime
    type_label: str
    label: str
    detail: str
    url: str


def _resolve_view(request):
    view = request.GET.get("view", "darts")
    if view not in DASHBOARD_VIEWS:
        return "darts"
    return view


def _upcoming_evenementen():
    now = timezone.now()
    return (
        Evenement.objects.filter(start_datum__gte=now)
        .prefetch_related(
            Prefetch(
                "ticket_set",
                queryset=Ticket.objects.annotate(
                    deelnemers_count=Count(
                        "participant",
                        filter=Q(
                            participant__payment__status__in=[
                                PokemonPaymentStatus.PAID,
                                PokemonPaymentStatus.OPEN,
                            ]
                        ),
                    )
                ),
            )
        )
        .order_by("start_datum")[:8]
    )


def _evenement_participants_count(evenement):
    return sum(ticket.deelnemers_count for ticket in evenement.ticket_set.all())


def _upcoming_dartskampen():
    now = timezone.now()
    return (
        Dartskamp.objects.filter(start_datum__gte=now)
        .annotate(
            deelnemers_count=Count(
                "deelnemers",
                filter=Q(
                    deelnemers__payment__status__in=[
                        DartsPaymentStatus.PAID,
                        DartsPaymentStatus.OPEN,
                    ]
                ),
            )
        )
        .order_by("start_datum")[:8]
    )


def _pending_standhouders():
    return (
        StandhouderInschrijving.objects.filter(
            status=StandhouderInschrijvingStatus.INGEDIEND
        )
        .select_related("evenement")
        .order_by("-aangemaakt_op")[:10]
    )


def _leerlingen_waarschuwing():
    return Leerling.objects.filter(resterende_beurten__lte=2).order_by(
        "resterende_beurten", "achternaam"
    )[:10]


def _history_date(obj):
    record = obj.history.order_by("history_date").first()
    return record.history_date if record else timezone.now()


def _darts_recent_activity():
    items = []
    for participant in (
        DartsParticipant.objects.select_related("dartskamp", "payment")
        .order_by("-pk")[:15]
    ):
        items.append(
            ActivityItem(
                sort_key=_history_date(participant),
                type_label="Dartskamp",
                label=f"{participant.voornaam} {participant.achternaam}",
                detail=participant.dartskamp.titel,
                url=reverse("admin:darts_participant_change", args=[participant.pk]),
            )
        )
    items.sort(key=lambda item: item.sort_key, reverse=True)
    return items[:15]


def _collectibles_recent_activity():
    items = []

    for participant in (
        PokemonParticipant.objects.select_related("ticket__event", "payment")
        .order_by("-pk")[:10]
    ):
        items.append(
            ActivityItem(
                sort_key=_history_date(participant),
                type_label="Evenement",
                label=participant.mail or "Deelnemer",
                detail=participant.ticket.event.titel,
                url=reverse("admin:pokemon_participant_change", args=[participant.pk]),
            )
        )

    for inschrijving in (
        StandhouderInschrijving.objects.select_related("evenement")
        .order_by("-aangemaakt_op")[:10]
    ):
        items.append(
            ActivityItem(
                sort_key=inschrijving.aangemaakt_op,
                type_label="Standhouder",
                label=inschrijving.bedrijfsnaam or inschrijving.naam,
                detail=inschrijving.evenement.titel,
                url=reverse(
                    "admin:pokemon_standhouderinschrijving_change",
                    args=[inschrijving.pk],
                ),
            )
        )

    items.sort(key=lambda item: item.sort_key, reverse=True)
    return items[:15]


def _gate_stats():
    """Summary of gate activity for the dashboard card."""
    from pokemon.services.gate import monitor_payload

    payload = monitor_payload()
    return {
        "aggregate": payload["aggregate"],
        "devices": payload["devices"],
        "monitor_url": reverse("admin:pokemon_gate_monitor"),
    }


def mollie_stats_api(request):
    """Async JSON endpoint for the Mollie KPI card on the admin dashboard."""
    account = request.GET.get("account", "darts")
    if account not in DASHBOARD_VIEWS:
        return JsonResponse(
            {"ok": False, "error": "Ongeldig account", "totals": None},
            status=400,
        )
    return JsonResponse(get_mollie_stats(account))


def dashboard_callback(request, context):
    view = _resolve_view(request)

    context.update(
        {
            "dashboard_view": view,
            "dashboard_tabs": [
                {"id": "darts", "label": "Darts", "icon": "target"},
                {"id": "collectibles", "label": "Collectibles", "icon": "festival"},
            ],
            "external_links": EXTERNAL_LINKS,
            "mollie_account": view,
            "mollie_url": MOLLIE_DASHBOARD_URL,
            "mollie_stats_url": reverse("admin_dashboard_mollie_stats"),
        }
    )

    if view == "darts":
        context.update(
            {
                "dartskampen": _upcoming_dartskampen(),
                "leerlingen_waarschuwing": _leerlingen_waarschuwing(),
                "calcom_bookings": get_upcoming_bookings(),
                "recent_activity": _darts_recent_activity(),
            }
        )
    else:
        evenementen = list(_upcoming_evenementen())
        for evenement in evenementen:
            evenement.dashboard_participants = _evenement_participants_count(evenement)

        context.update(
            {
                "evenementen": evenementen,
                "standhouders": _pending_standhouders(),
                "recent_activity": _collectibles_recent_activity(),
                "gate_stats": _gate_stats(),
            }
        )

    return context
