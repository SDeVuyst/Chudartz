from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from pokemon.models import Evenement, GateDevice, GateScanLog, Participant, Ticket

FEED_LIMIT = 30
SCAN_PAGE_SIZE = 50


class GateConfigError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def log_gate_scan(device, participant_id, success: bool, message: str) -> GateScanLog:
    """Record a scan attempt so the admin monitor can show live status and history."""
    try:
        raw_id = int(participant_id)
    except (TypeError, ValueError):
        raw_id = None

    participant = None
    if raw_id is not None:
        participant = Participant.objects.filter(pk=raw_id).first()

    return GateScanLog.objects.create(
        device=device,
        success=success,
        message=message[:255],
        participant=participant,
        participant_id_raw=raw_id,
    )


def _today_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def _today_stats_by_device() -> dict:
    """Scan counts for today per device id."""
    rows = (
        GateScanLog.objects.filter(created_at__gte=_today_start())
        .values("device_id")
        .annotate(total=Count("id"), success=Count("id", filter=Q(success=True)))
    )
    return {row["device_id"]: row for row in rows}


def scan_filters_from_params(params) -> dict:
    outcome = params.get("outcome", "")
    datum = params.get("datum", "")
    zoek = (params.get("q") or "").strip()
    page = params.get("page", "1")
    try:
        page_num = max(1, int(page))
    except (TypeError, ValueError):
        page_num = 1
    return {
        "outcome": outcome,
        "datum": datum,
        "q": zoek,
        "page": page_num,
    }


def filtered_scan_queryset(device: GateDevice, filters: dict):
    logs = device.scan_logs.select_related("device")
    outcome = filters.get("outcome", "")
    datum = filters.get("datum", "")
    zoek = filters.get("q", "")

    if outcome == "success":
        logs = logs.filter(success=True)
    elif outcome == "fail":
        logs = logs.filter(success=False)
    if datum:
        parsed = parse_date(datum)
        if parsed:
            logs = logs.filter(created_at__date=parsed)
    if zoek:
        q_filters = Q(message__icontains=zoek)
        if zoek.isdigit():
            q_filters |= Q(participant_id_raw=int(zoek))
        logs = logs.filter(q_filters)
    return logs


def serialize_scan(log: GateScanLog) -> dict:
    local_created = timezone.localtime(log.created_at)
    participant_admin_url = None
    if log.participant_id:
        participant_admin_url = reverse(
            "admin:pokemon_participant_change", args=[log.participant_id]
        )
    return {
        "id": log.id,
        "device_id": log.device_id,
        "device_name": log.device.name,
        "created_at": local_created.isoformat(),
        "time": local_created.strftime("%H:%M:%S"),
        "created_at_display": local_created.strftime("%d/%m/%Y %H:%M:%S"),
        "success": log.success,
        "message": log.message,
        "participant_id": log.participant_id_raw,
        "participant_admin_url": participant_admin_url,
    }


def serialize_device_config(device: GateDevice) -> dict:
    remote_event = device.remote_event
    remote_ticket = device.remote_ticket
    reported = device._reported_ids()

    reported_event_label = None
    reported_ticket_label = None
    if reported["event_id"]:
        ev = Evenement.objects.filter(pk=reported["event_id"]).first()
        if ev:
            reported_event_label = ev.titel
    if reported["ticket_id"]:
        ticket = Ticket.objects.filter(pk=reported["ticket_id"]).first()
        if ticket:
            reported_ticket_label = ticket.titel

    return {
        "status": device.config_sync_status(),
        "remote_event_id": device.remote_event_id,
        "remote_event_label": remote_event.titel if remote_event else None,
        "remote_ticket_id": device.remote_ticket_id,
        "remote_ticket_label": remote_ticket.titel if remote_ticket else None,
        "reported_event_id": reported["event_id"],
        "reported_ticket_id": reported["ticket_id"],
        "reported_event_label": reported_event_label,
        "reported_ticket_label": reported_ticket_label,
    }


def serialize_device(device: GateDevice, stats: dict | None = None) -> dict:
    stats = stats or {}
    last_scan = device.scan_logs.first()
    heartbeat = device.last_heartbeat_at
    return {
        "id": device.id,
        "name": device.name,
        "is_active": device.is_active,
        "online": device.is_online,
        "last_status": device.last_status,
        "last_heartbeat_at": (
            timezone.localtime(heartbeat).isoformat() if heartbeat else None
        ),
        "last_used_at": (
            timezone.localtime(device.last_used_at).isoformat()
            if device.last_used_at
            else None
        ),
        "today_total": stats.get("total", 0),
        "today_success": stats.get("success", 0),
        "today_fail": stats.get("total", 0) - stats.get("success", 0),
        "last_scan": serialize_scan(last_scan) if last_scan else None,
        "config": serialize_device_config(device),
    }


def _feed(queryset, since_scan_id):
    """Newest-first scans: everything after since_scan_id, or the latest batch."""
    if since_scan_id:
        try:
            since_id = int(since_scan_id)
        except (TypeError, ValueError):
            since_id = None
        if since_id:
            return list(queryset.filter(id__gt=since_id)[:200])
    return list(queryset[:FEED_LIMIT])


def _serialize_scans_page(queryset, page_num: int) -> dict:
    paginator = Paginator(queryset, SCAN_PAGE_SIZE)
    page = paginator.get_page(page_num)
    return {
        "items": [serialize_scan(log) for log in page.object_list],
        "page": page.number,
        "total_pages": paginator.num_pages,
        "has_previous": page.has_previous(),
        "has_next": page.has_next(),
    }


def monitor_payload(since_scan_id=None) -> dict:
    """Live state of every gate plus the unified scan feed."""
    stats = _today_stats_by_device()
    devices = [
        serialize_device(device, stats.get(device.id))
        for device in GateDevice.objects.select_related(
            "remote_event", "remote_ticket"
        ).order_by("name")
    ]
    scans = _feed(GateScanLog.objects.select_related("device"), since_scan_id)

    return {
        "aggregate": {
            "online_count": sum(1 for d in devices if d["online"]),
            "total_count": len(devices),
            "today_total": sum(d["today_total"] for d in devices),
            "today_success": sum(d["today_success"] for d in devices),
            "today_fail": sum(d["today_fail"] for d in devices),
        },
        "devices": devices,
        "recent_scans": [serialize_scan(log) for log in scans],
    }


def device_payload(
    device: GateDevice,
    since_scan_id=None,
    filters: dict | None = None,
) -> dict:
    """Live state and scan feed for a single gate."""
    stats = _today_stats_by_device().get(device.id)
    filters = filters or scan_filters_from_params({})
    page_num = filters.get("page", 1)
    queryset = filtered_scan_queryset(device, filters)

    if since_scan_id and page_num == 1:
        delta = _feed(queryset, since_scan_id)
        scans = {
            "items": [serialize_scan(log) for log in delta],
            "page": 1,
            "total_pages": Paginator(queryset, SCAN_PAGE_SIZE).num_pages,
            "has_previous": False,
            "has_next": Paginator(queryset, SCAN_PAGE_SIZE).num_pages > 1,
            "is_delta": True,
        }
    else:
        scans = _serialize_scans_page(queryset, page_num)
        scans["is_delta"] = False

    return {
        "device": serialize_device(device, stats),
        "scans": scans,
        "filters": {
            "outcome": filters.get("outcome", ""),
            "datum": filters.get("datum", ""),
            "q": filters.get("q", ""),
            "page": page_num,
        },
    }


def apply_remote_gate_config(
    device: GateDevice,
    event_id: int | None,
    ticket_id: int | None,
) -> GateDevice:
    if ticket_id is not None and event_id is None:
        raise GateConfigError("Tickettype vereist een evenement.")

    remote_event = None
    remote_ticket = None

    if event_id is not None:
        remote_event = Evenement.objects.filter(pk=event_id).first()
        if remote_event is None:
            raise GateConfigError("Evenement niet gevonden.")

    if ticket_id is not None:
        remote_ticket = Ticket.objects.filter(pk=ticket_id).first()
        if remote_ticket is None:
            raise GateConfigError("Tickettype niet gevonden.")
        if remote_ticket.event_id != event_id:
            raise GateConfigError("Tickettype hoort niet bij dit evenement.")

    device.remote_event = remote_event
    device.remote_ticket = remote_ticket
    device.remote_config_at = timezone.now()
    device.save(update_fields=["remote_event", "remote_ticket", "remote_config_at"])
    return device


def gate_config_options() -> dict:
    events_list = []
    for ev in Evenement.objects.order_by("-start_datum"):
        events_list.append(
            {
                "id": ev.id,
                "label": (
                    f"{ev.titel} — "
                    f"{timezone.localtime(ev.start_datum).strftime('%d/%m/%Y')}"
                ),
            }
        )

    tickets_by_event: dict[int, list] = {}
    for ticket in Ticket.objects.select_related("event").order_by("titel"):
        tickets_by_event.setdefault(ticket.event_id, []).append(
            {
                "id": ticket.id,
                "label": f"{ticket.titel} — {ticket.price}",
            }
        )

    return {"events": events_list, "tickets_by_event": tickets_by_event}
