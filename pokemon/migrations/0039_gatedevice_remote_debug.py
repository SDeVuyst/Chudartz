from django.db import migrations, models


def init_remote_debug_from_reported(apps, schema_editor):
    GateDevice = apps.get_model("pokemon", "GateDevice")
    for device in GateDevice.objects.exclude(remote_config_at__isnull=True):
        reported = device.reported_config or {}
        device.remote_debug = bool(reported.get("debug"))
        device.save(update_fields=["remote_debug"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0038_gatedevice_remote_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="gatedevice",
            name="remote_debug",
            field=models.BooleanField(
                default=False,
                help_text="Desired debug mode pushed to the device via heartbeat.",
                verbose_name="Remote debug mode",
            ),
        ),
        migrations.RunPython(init_remote_debug_from_reported, noop_reverse),
    ]
