from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0037_gate_scan_log_and_heartbeat"),
    ]

    operations = [
        migrations.AddField(
            model_name="gatedevice",
            name="remote_config_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When set, the device receives config updates via heartbeat.",
                null=True,
                verbose_name="Remote config updated at",
            ),
        ),
        migrations.AddField(
            model_name="gatedevice",
            name="remote_event",
            field=models.ForeignKey(
                blank=True,
                help_text="Desired event filter pushed to the device via heartbeat.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gate_devices",
                to="pokemon.evenement",
                verbose_name="Remote event filter",
            ),
        ),
        migrations.AddField(
            model_name="gatedevice",
            name="remote_ticket",
            field=models.ForeignKey(
                blank=True,
                help_text="Desired ticket filter pushed to the device via heartbeat.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gate_devices",
                to="pokemon.ticket",
                verbose_name="Remote ticket filter",
            ),
        ),
    ]
