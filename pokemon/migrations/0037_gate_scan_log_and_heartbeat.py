import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0036_standhouder_factuur_velden"),
    ]

    operations = [
        migrations.AddField(
            model_name="gatedevice",
            name="last_heartbeat_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Last heartbeat at"
            ),
        ),
        migrations.AddField(
            model_name="gatedevice",
            name="last_status",
            field=models.CharField(
                choices=[
                    ("idle", "Idle"),
                    ("checking", "Checking"),
                    ("success", "Success"),
                    ("fail", "Failed"),
                ],
                default="idle",
                max_length=20,
                verbose_name="Last status",
            ),
        ),
        migrations.AddField(
            model_name="gatedevice",
            name="reported_config",
            field=models.JSONField(
                blank=True,
                help_text="Configuration snapshot as reported by the device.",
                null=True,
                verbose_name="Reported config",
            ),
        ),
        migrations.CreateModel(
            name="GateScanLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Scanned at"),
                ),
                ("success", models.BooleanField(verbose_name="Accepted")),
                (
                    "message",
                    models.CharField(blank=True, max_length=255, verbose_name="Message"),
                ),
                (
                    "participant_id_raw",
                    models.IntegerField(
                        blank=True,
                        help_text="Raw ID from the QR code, also kept when no participant was found.",
                        null=True,
                        verbose_name="Scanned participant ID",
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scan_logs",
                        to="pokemon.gatedevice",
                        verbose_name="Gate device",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gate_scans",
                        to="pokemon.participant",
                        verbose_name="Participant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Gate scan",
                "verbose_name_plural": "Gate scans",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="gatescanlog",
            index=models.Index(
                fields=["device", "-created_at"], name="pokemon_gat_device__c5b29f_idx"
            ),
        ),
    ]
