from django.db.models import Count, Q
from django.utils import timezone

from pokemon.models import GateDevice, GateScanLog, Participant

FEED_LIMIT = 30


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


def serialize_scan(log: GateScanLog) -> dict:
    return {
        "id": log.id,
        "device_id": log.device_id,
        "device_name": log.device.name,
        "created_at": timezone.localtime(log.created_at).isoformat(),
        "time": timezone.localtime(log.created_at).strftime("%H:%M:%S"),
        "success": log.success,
        "message": log.message,
        "participant_id": log.participant_id_raw,
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
    }


def _feed(queryset, since_scan_id):
    """Newest-first scans: everything after since_scan_id, or the latest batch."""
    if since_scan_id:
        return list(queryset.filter(id__gt=since_scan_id)[:200])
    return list(queryset[:FEED_LIMIT])


def monitor_payload(since_scan_id=None) -> dict:
    """Live state of every gate plus the unified scan feed."""
    stats = _today_stats_by_device()
    devices = [
        serialize_device(device, stats.get(device.id))
        for device in GateDevice.objects.order_by("name")
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


def device_payload(device: GateDevice, since_scan_id=None) -> dict:
    """Live state and scan feed for a single gate."""
    stats = _today_stats_by_device().get(device.id)
    scans = _feed(
        device.scan_logs.select_related("device"),
        since_scan_id,
    )
    return {
        "device": serialize_device(device, stats),
        "recent_scans": [serialize_scan(log) for log in scans],
    }
