from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0043_standhouder_btw_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalticket",
            name="subtitel",
            field=models.CharField(
                blank=True,
                help_text="Optionele korte regel onder de titel op de ticketkaart.",
                max_length=150,
                verbose_name="subtitel",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="subtitel",
            field=models.CharField(
                blank=True,
                help_text="Optionele korte regel onder de titel op de ticketkaart.",
                max_length=150,
                verbose_name="subtitel",
            ),
        ),
        migrations.AlterField(
            model_name="historicalticket",
            name="enkel_inkom",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Niet online te koop. Bezoekers zien het ticket wel, met de melding "
                    "dat het ticket aan de deur verkrijgbaar is. Combineer met 'Gratis' "
                    "voor een gratis deurticket."
                ),
                verbose_name="Ticket aan de deur",
            ),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="enkel_inkom",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Niet online te koop. Bezoekers zien het ticket wel, met de melding "
                    "dat het ticket aan de deur verkrijgbaar is. Combineer met 'Gratis' "
                    "voor een gratis deurticket."
                ),
                verbose_name="Ticket aan de deur",
            ),
        ),
    ]
