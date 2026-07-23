from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0032_standhouder_max_tafels_per_standhouder"),
    ]

    operations = [
        migrations.CreateModel(
            name="GateDevice",
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
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                (
                    "api_key_prefix",
                    models.CharField(
                        editable=False,
                        help_text="First 8 characters of the key, for identification.",
                        max_length=8,
                        verbose_name="API key prefix",
                    ),
                ),
                (
                    "api_key_hash",
                    models.CharField(
                        editable=False, max_length=255, verbose_name="API key hash"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Created at"
                    ),
                ),
                (
                    "last_used_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Last used at"
                    ),
                ),
            ],
            options={
                "verbose_name": "Gate device",
                "verbose_name_plural": "Gate devices",
            },
        ),
    ]
