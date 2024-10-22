import random
import secrets
import string
from email.utils import formataddr
from io import BytesIO

from django.forms import ValidationError
import pytz
import qrcode
from ckeditor.fields import RichTextField
from django.conf import settings
from django.utils.translation import pgettext_lazy
from django.contrib.staticfiles import finders
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from simple_history.models import HistoricalRecords
from phonenumber_field.modelfields import PhoneNumberField

from .templatetags import dutch_date
from .utils import helpers


class ToernooiHeaderGroep(models.Model):
    def __str__(self) -> str:
        return self.naam
    
    class Meta:
        verbose_name = "Toernooi Header Groep"
        verbose_name_plural = "Toernooi Header Groepen"

    naam = models.CharField(verbose_name=_("Naam"))
    active = models.BooleanField(verbose_name=_("Actief"), default=True)
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)


class Toernooi(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        get_latest_by = "start_datum"
        ordering = ['-start_datum']
        verbose_name = "Toernooi"
        verbose_name_plural = "Toernooien"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    slug = models.SlugField(unique=True)
    beschrijving = RichTextField(verbose_name=_("Beschrijving"))
    vereisten = models.TextField(verbose_name=_("Vereisten (Elk op een nieuwe lijn)"))
    start_datum = models.DateTimeField(verbose_name=_("Start Datum"))
    einde_datum = models.DateTimeField(verbose_name=_("Eind Datum"))
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    locatie_kort = models.CharField(max_length=25, verbose_name=_("Locatie (kort)"))
    locatie_lang = models.TextField(verbose_name=_("Locatie (lang)"))
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="darts")
    afbeeldingen_download_url = models.URLField(verbose_name=_("Download afbeeldingen URL"), blank=True, null=True)
    vereist_voogd_toestemming = models.BooleanField(verbose_name=_("Toestemming van voogd vereist"), default=False)
    toon_op_site = models.BooleanField(verbose_name=_("Toon op site"), default=False)

    enable_inschrijvingen = models.BooleanField(verbose_name=_("Inschrijvingen Inschakelen"), default=False)

    header_groepen = models.ManyToManyField(ToernooiHeaderGroep, verbose_name=_("Groepen in header"), related_name='toernooien', blank=True, null=True)
    naam_in_header = models.CharField(max_length=25, verbose_name=_("Naam in header"), blank=True, null=True)   

    resultaten = RichTextField(verbose_name=_("Resultaten"), blank=True, null=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    # make tz aware
    def save(self, *args, **kwargs):
        # Get the Brussels timezone
        brussels_tz = pytz.timezone('Europe/Brussels')

        # Convert the fields to the Brussels timezone before saving
        if self.start_datum and timezone.is_naive(self.start_datum):
            self.start_datum = timezone.make_aware(self.start_datum, brussels_tz)

        if self.einde_datum and timezone.is_naive(self.einde_datum):
            self.einde_datum = timezone.make_aware(self.einde_datum, brussels_tz)

        super().save(*args, **kwargs)

    @property
    def is_in_future(self):
        brussels_tz = pytz.timezone('Europe/Brussels')
        now = timezone.now().astimezone(brussels_tz)
        start_datum_brussels = self.start_datum.astimezone(brussels_tz)
        return now < start_datum_brussels
    
    @property
    def is_bezig(self):
        brussels_tz = pytz.timezone('Europe/Brussels')
        now = timezone.now().astimezone(brussels_tz)
        einde_datum_brussels = self.einde_datum.astimezone(brussels_tz)
        return (not self.is_in_future) and (now < einde_datum_brussels)
    
    @property
    def is_same_day(self):
        return self.start_datum.strftime("%d/%m/%Y") == self.einde_datum.strftime("%d/%m/%Y")
    
    @property
    def is_sold_out(self):
        # Total participants limit exceeded
        event_sold_out = self.participants_count >= self.max_deelnemers

        # All tickets have their max participants limit exceeded
        tickets_are_sold_out = all(ticket.is_sold_out for ticket in self.ticket_set.all())

        return tickets_are_sold_out or event_sold_out

    @property
    def remaining_tickets(self):
        return self.max_deelnemers - self.participants_count
    
    @property
    def participants_count(self):
        return sum(ticket.participants_count for ticket in self.ticket_set.all())
    
    def get_absolute_url(self):
        return f'https://chudartz.com/nl/toernooien/{str(self.slug)}/'
    
    @property
    def vereisten_lijst(self):
        return self.vereisten.split('\n')


class Ticket(models.Model):

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self) -> str:
        return f"{self.titel} - {self.price}"
    
    titel = models.CharField(max_length=100, verbose_name=_("titel"))
    price = MoneyField(verbose_name="Price", default_currency="EUR", max_digits=10, decimal_places=2)
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    event = models.ForeignKey(Toernooi, verbose_name=_("Evenement"), on_delete=models.RESTRICT)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    @property 
    def is_sold_out(self):
        amount_of_participants_with_this_as_ticket = Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()
        return amount_of_participants_with_this_as_ticket >= self.max_deelnemers
    
    @property
    def remaining_tickets(self):
        amount_of_participants_with_this_as_ticket = Participant.objects.filter(ticket_id=self.pk).count()
        return self.max_deelnemers - amount_of_participants_with_this_as_ticket
    
    @property
    def participants_count(self):
        return Participant.objects.filter(ticket_id=self.pk).filter(
            Q(payment__status=PaymentStatus.PAID) | 
            Q(payment__status=PaymentStatus.OPEN)
        ).count()



class PaymentStatus:
    PAID = "paid"
    AUTHORIZED = "authorized"
    OPEN = "open"
    CANCELED = "canceled"
    EXPIRED = "expired"
    FAILED = "failed"


    CHOICES = [
        (PAID, pgettext_lazy("payment status", "Betaald")),
        (OPEN, pgettext_lazy("payment status", "Open")),
        (CANCELED, pgettext_lazy("payment status", "Geannuleerd")),
        (EXPIRED, pgettext_lazy("payment status", "Verlopen")),
        (FAILED, pgettext_lazy("payment status", "Gefaald"))
    ]


class Payment(models.Model):

    class Meta:
        verbose_name = "Betaling"
        verbose_name_plural = "Betalingen"
    
    def save(self, *args, **kwargs):
        # Check if payment is received
        if self.status == PaymentStatus.PAID:

            # betaling van participant
            try:
                p = Participant.objects.get(payment=self)
                p.send_mail()
            except:
                pass

            # betaling van beurtenkaart
            try:
                b = BeurtkaartBetaling.objects.get(betaling=self)
                b.add_uses_to_student()
                b.send_mail()
            except:
                pass

            # betaling van lidgeld
            try:
                l = Leerling.objects.get(payment=self)
                l.send_mail()
            except:
                pass

        super().save(*args, **kwargs)

    mollie_id = models.CharField(verbose_name=_("Mollie id"), blank=True, null=True)
    first_name = models.CharField(max_length=50, verbose_name=_("Voornaam"), blank=True, null=True)
    last_name = models.CharField(max_length=50, verbose_name=_("Achternaam"), blank=True, null=True)
    mail = models.EmailField(verbose_name=_("Email"), max_length=254, blank=True, null=True)
    status = models.CharField(max_length=10, choices=PaymentStatus.CHOICES, default=PaymentStatus.OPEN)
    amount = MoneyField(verbose_name="Prijs", default_currency="EUR", max_digits=10, decimal_places=2, blank=True, null=True)
    description = models.TextField(verbose_name=_("Beschrijving"), blank=True, null=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))


class SkillLevel:
    BEGINNER = "beginner"
    GEMIDDELD  = "gemiddeld"
    GEOEFEND = "geoefend"

    CHOICES = [
        (BEGINNER, pgettext_lazy("skill level", "Beginner")),
        (GEMIDDELD, pgettext_lazy("skill level", "Gemiddeld")),
        (GEOEFEND, pgettext_lazy("skill level", "Geoefend")),
    ]



# Deelnemer van toernooi
class Participant(models.Model):

    def __str__(self) -> str:
        return f"{self.voornaam} {self.achternaam}" 
    
    class Meta:
        get_latest_by = "pk"
        verbose_name = "Deelnemer"
        verbose_name_plural = "Deelnemers"
    
    voornaam = models.CharField(max_length=50, verbose_name=_("Voornaam"))
    achternaam = models.CharField(max_length=50, verbose_name=_("Achternaam"))
    geboortejaar = models.PositiveSmallIntegerField(verbose_name=_("Geboortejaar"))
    email = models.EmailField(verbose_name=_("Email"), max_length=254)
    straatnaam = models.CharField(verbose_name=_("Straatnaam"), max_length=100)
    nummer = models.CharField(verbose_name=_("Nummer"), max_length=6)
    postcode = models.IntegerField(verbose_name=_("Postcode"))
    stad = models.CharField(verbose_name=_("Stad"), max_length=40)
    # niveau = models.CharField(max_length=10, choices=SkillLevel.CHOICES, default=SkillLevel.GEMIDDELD)
    gsm = PhoneNumberField(verbose_name=_("GSM"), null=False, blank=False)
    
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT, verbose_name="Payment", blank=True, null=True)
    attended = models.BooleanField(verbose_name=_("Attended"), default=False)
    beschrijving = models.TextField(blank=True, null=True, verbose_name=_("beschrijving"))
    ticket = models.ForeignKey(Ticket, verbose_name=_("Ticket"), on_delete=models.RESTRICT)

    # seed for the QR codes
    random_seed = models.CharField(max_length=10, verbose_name="Random Seed", editable=False)
    
    history = HistoricalRecords(verbose_name=_("History"))


    def save(self, *args, **kwargs):
        if not self.random_seed:
            self.random_seed = self._generate_random_seed()
        super().save(*args, **kwargs)

    def _generate_random_seed(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(10))
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f'participant_id:{self.pk}')
        qr.add_data(f'seed:{self.random_seed}')

        qr.make(fit=True)

        return qr.make_image(fill='black', back_color='white')
    

    def generate_ticket(self, return_as_http=True):
        # Create a buffer to hold the PDF data
        buffer = BytesIO()

        # Create a canvas object
        p = canvas.Canvas(buffer, pagesize=letter)

        qr_img = self.generate_qr_code()

        # Save the QR code afbeelding to a BytesIO object
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        qr_afbeelding = Image.open(qr_buffer)
        temp_path = "/tmp/qr_code.png"
        qr_afbeelding.save(temp_path)

        # Draw the QR code afbeelding onto the PDF
        p.drawImage(temp_path, 400, 590, 170, 170)

        # Add  logo
        logo_path = finders.find('img/logo-black.png')
        p.drawImage(logo_path, 75, 715, 906 * 0.15, 345 * 0.15)

        # get info about event
        event = self.ticket.event
        if dutch_date.dutch_date(event.start_datum) == dutch_date.dutch_date(event.einde_datum):
            formatted_date = f"{dutch_date.dutch_datetime(event.start_datum)} - {dutch_date.dutch_time(event.einde_datum)}"
        else:
            formatted_date = f"{dutch_date.dutch_datetime(event.start_datum)} - {dutch_date.dutch_datetime(event.einde_datum)}"

        # Add ticket details
        # Set correct font for titel
        font_path = finders.find('fonts/outfit/Outfit-Bold.ttf')
        pdfmetrics.registerFont(TTFont('Outfit', font_path))
        p.setFont("Outfit", 18)
        if len(str(event)) > 30:
            p.drawString(75, 690, f"{str(event)[:28]}...")
        else:
            p.drawString(75, 690, str(event))

        # Set correct font for beschrijving
        font_path = finders.find('fonts/outfit/Outfit-Regular.ttf')
        pdfmetrics.registerFont(TTFont('Outfit', font_path))
        p.setFont("Outfit", 14)

        p.drawString(75, 660, formatted_date)
        p.drawString(75, 635, str(self.ticket))
        p.drawString(75, 610, strip_tags(event.locatie_kort))

        # Finalize the PDF
        p.save()

        # Get the value of the BytesIO buffer and write it to the response
        buffer.seek(0)

        if not return_as_http:
            return buffer
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ticket-{self.pk}.pdf"'

        return response
    
    def send_mail(self):
        event = self.ticket.event
        
        email_body = render_to_string('email/confirmation-mail-participant.html', {
            'event': event,
            'participant': self,
        })

        # Generate tickets PDF
        tickets_pdf = self.generate_ticket()

        email = EmailMessage(
            'ChudartZ | Bevestiging',
            email_body,
            formataddr(('Toernooien | Chudartz', settings.EMAIL_HOST_USER)),
            [self.email],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        # add tickets as attachment
        email.attach(f'ticket.pdf', tickets_pdf.getvalue(), 'application/pdf')

        helpers.attach_image(email, "logo-black")

        # Send the email
        email.send()


class Sponsor(models.Model):
    naam = models.CharField(max_length=50, verbose_name=_("Naam"))
    website_url = models.URLField(verbose_name=_("Website URL"))
    info = RichTextField(verbose_name=_("Info over Sponsor"))
    toon_op_index = models.BooleanField(verbose_name=_("Toon Op Voorpagina"), default=True)
    toon_in_footer = models.BooleanField(verbose_name=_("Toon in footer"), default=True)
    toon_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon op sponsor pagina"), default=True)
    toon_knop_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon knop op sponsors pagina"), default=True)
    logo = models.ImageField(verbose_name=_("Logo"), upload_to="sponsor")
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="sponsor")

    history = HistoricalRecords(verbose_name=_("History"))

    def __str__(self):
        return self.naam
    
    class Meta:
        verbose_name = "Sponsor"
        verbose_name_plural = "Sponsors"


class Leerling(models.Model):
    class Meta:
        verbose_name = "Leerling"
        verbose_name_plural = "Leerlingen"

    voornaam = models.CharField(max_length=50, verbose_name=_("Voornaam"))
    achternaam = models.CharField(max_length=50, verbose_name=_("Achternaam"))
    email = models.EmailField(verbose_name=_("Email"), max_length=254)
    extra_info = RichTextField(verbose_name=_("Extra Info"), blank=True, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT, verbose_name="Payment", blank=True, null=True)
    resterende_beurten = models.PositiveSmallIntegerField(verbose_name=_("Resterende Beurten"), default=0)

    code = models.CharField(max_length=6, verbose_name=_("Code"), unique=True)

    history = HistoricalRecords(verbose_name=_("History"))

    def __str__(self):
        return self.voornaam + " " + self.achternaam
    
    def generate_unique_code(self):
        while True:
            # Generate a random 6-digit code
            code = f'{random.randint(100000, 999999)}'
            # Check if the code is unique
            if not Leerling.objects.filter(code=code).exists():
                return code

    def save(self, *args, **kwargs):
        # Set code if it's not already set (e.g., on creation)
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def decrement_beurten(self):
        if self.resterende_beurten == 0:
            raise ValidationError(_("Geen resterende beurten meer!"))
        
        self.resterende_beurten -= 1
        self.save()

    def send_mail(self):
        
        email_body = render_to_string('email/confirmation-mail-leerling.html', {
            'leerling': self,
        })

        email = EmailMessage(
            'ChudartZ | Bevestiging',
            email_body,
            formataddr(('Chudartz', settings.EMAIL_HOST_USER)),
            [self.email],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        helpers.attach_image(email, "logo-black")

        # Send the email
        email.send()



class Beurtkaart(models.Model):
    class Meta:
        verbose_name = "Beurtenkaart"
        verbose_name_plural = "Beurtenkaarten"

    naam = models.CharField(verbose_name=_("Naam"))
    aantal_beurten = models.PositiveSmallIntegerField(verbose_name=_("Aantal Beurten"))
    prijs = MoneyField(verbose_name="Price", default_currency="EUR", max_digits=10, decimal_places=2)

    history = HistoricalRecords(verbose_name=_("History"))


class BeurtkaartBetaling(models.Model):
    beurtkaart = models.ForeignKey(Beurtkaart, verbose_name=_("Beurtkaart"), on_delete=models.CASCADE)
    betaling = models.ForeignKey(Payment, verbose_name=_("Betaling"), on_delete=models.CASCADE)
    leerling = models.ForeignKey(Leerling, verbose_name=_("Leerling"), on_delete=models.CASCADE)

    def add_uses_to_student(self):
        self.leerling.resterende_beurten += self.beurtkaart.aantal_beurten
        self.leerling.save()

    def send_mail(self):
        email_body = render_to_string('email/confirmation-mail-beurtkaart.html', {
            'leerling': self.leerling,
            'resterende_beurten': self.leerling.resterende_beurten
        })

        email = EmailMessage(
            'ChudartZ | Bevestiging',
            email_body,
            formataddr(('Chudartz', settings.EMAIL_HOST_USER)),
            [self.leerling.email],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        helpers.attach_image(email, "logo-black")

        # Send the email
        email.send()


class Nieuws(models.Model):
    def __str__(self):
        return self.titel
    
    class Meta:
        verbose_name = 'Nieuws'
        verbose_name_plural = 'Nieuws'


    titel = models.CharField(verbose_name=_("Titel"), max_length=120)
    naam_website = models.CharField(verbose_name=_("Naam Website"), max_length=50)
    link = models.URLField(verbose_name=_("Artikel URL"))
    icon = models.CharField(max_length=40, verbose_name=_("Bootstrap Icon"))
    active = models.BooleanField(verbose_name=_("Actief"))

    history = HistoricalRecords(verbose_name=_("History"))
