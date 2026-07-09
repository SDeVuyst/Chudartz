from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pokemon', '0030_kortingscode_ticket_wizard'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalticket',
            name='toegang_einde',
            field=models.DateTimeField(
                blank=True,
                help_text='Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket.',
                null=True,
                verbose_name='Toegang tot',
            ),
        ),
        migrations.AddField(
            model_name='historicalticket',
            name='toegang_start',
            field=models.DateTimeField(
                blank=True,
                help_text='Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket.',
                null=True,
                verbose_name='Toegang vanaf',
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='toegang_einde',
            field=models.DateTimeField(
                blank=True,
                help_text='Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket.',
                null=True,
                verbose_name='Toegang tot',
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='toegang_start',
            field=models.DateTimeField(
                blank=True,
                help_text='Laat leeg om de evenementtijden te gebruiken. Alleen zichtbaar op het ticket.',
                null=True,
                verbose_name='Toegang vanaf',
            ),
        ),
    ]
