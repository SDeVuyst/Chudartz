"""Shared evenement choices for admin filters and gate config."""

from __future__ import annotations

from django.db.models import Case, DateTimeField, F, IntegerField, Value, When
from django.utils import timezone
from django.utils.translation import gettext as _

from pokemon.models import Evenement, Ticket

GROUP_UPCOMING = "upcoming"
GROUP_PAST = "past"


def _format_event_label(event: Evenement) -> str:
    start = timezone.localtime(event.start_datum).strftime("%d/%m/%Y")
    return f"{event.titel} — {start}"


def evenement_choice_options(*, now=None) -> list[dict]:
    """
    Return evenement options ordered upcoming-first, then past.

    Upcoming/running: einde_datum >= now, ordered by start_datum ASC.
    Past: einde_datum < now, ordered by start_datum DESC (most recent first).
    """
    if now is None:
        now = timezone.now()

    events = (
        Evenement.objects.annotate(
            is_voorbij=Case(
                When(einde_datum__lt=now, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            aankomend_datum=Case(
                When(einde_datum__gte=now, then=F("start_datum")),
                output_field=DateTimeField(),
            ),
            voorbij_datum=Case(
                When(einde_datum__lt=now, then=F("start_datum")),
                output_field=DateTimeField(),
            ),
        )
        .order_by(
            "is_voorbij",
            "aankomend_datum",
            F("voorbij_datum").desc(nulls_last=True),
            "pk",
        )
    )

    options = []
    for event in events:
        options.append(
            {
                "id": event.pk,
                "label": _format_event_label(event),
                "group": GROUP_PAST if event.is_voorbij else GROUP_UPCOMING,
            }
        )
    return options


def evenement_admin_lookups(*, now=None) -> list:
    """
    Optgroup-style lookups for Unfold DropdownFilter / ChoiceField.

    Returns:
        [
            ("Aankomend", [(id, label), ...]),
            ("Voorbij", [(id, label), ...]),
        ]
    """
    upcoming = []
    past = []
    for option in evenement_choice_options(now=now):
        entry = (option["id"], option["label"])
        if option["group"] == GROUP_PAST:
            past.append(entry)
        else:
            upcoming.append(entry)

    lookups = []
    if upcoming:
        lookups.append((_("Aankomend"), upcoming))
    if past:
        lookups.append((_("Voorbij"), past))
    return lookups


def tickets_by_event_options() -> dict[str, list[dict]]:
    """
    Map event id (as string) -> ticket options for cascading admin filters.

    Keys are strings so the map is JSON- and JS-friendly.
    """
    tickets_by_event: dict[str, list[dict]] = {}
    for ticket in Ticket.objects.order_by("titel"):
        key = str(ticket.event_id)
        tickets_by_event.setdefault(key, []).append(
            {
                "id": ticket.pk,
                "label": str(ticket),
            }
        )
    return tickets_by_event
