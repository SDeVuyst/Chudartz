from email.utils import formataddr

from django.forms import ValidationError
import pytz
from ckeditor.fields import RichTextField
from django.conf import settings
from django.utils.translation import pgettext_lazy
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from simple_history.models import HistoricalRecords
from phonenumber_field.modelfields import PhoneNumberField

from darts.validators.image_validator import validate_image_max_size

from .utils import helpers


class DartskampHeaderGroep(models.Model):
    def __str__(self) -> str:
        return self.naam
    
    class Meta:
        verbose_name = "Dartskamp Header Groep"
        verbose_name_plural = "Dartskamp Header Groepen"

    naam = models.CharField(verbose_name=_("Naam"))
    active = models.BooleanField(verbose_name=_("Actief"), default=True)
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)


class Dartskamp(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        get_latest_by = "start_datum"
        ordering = ['-start_datum']
        verbose_name = "Dartskamp"
        verbose_name_plural = "Dartskampen"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    slug = models.SlugField(unique=True)
    beschrijving = RichTextField(verbose_name=_("Beschrijving"))
    vereisten = models.TextField(verbose_name=_("Vereisten (Elk op een nieuwe lijn)"))
    start_datum = models.DateTimeField(verbose_name=_("Start Datum"))
    einde_datum = models.DateTimeField(verbose_name=_("Eind Datum"))
    max_deelnemers = models.IntegerField(verbose_name=_("Max Deelnemers"))
    prijs = MoneyField(
        verbose_name=_("Prijs"),
        default_currency="EUR",
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    locatie_kort = models.CharField(max_length=25, verbose_name=_("Locatie (kort)"))
    locatie_lang = models.TextField(verbose_name=_("Locatie (lang)"))
    afbeelding = models.ImageField(verbose_name=_("afbeelding"), upload_to="darts")
    afbeeldingen_download_url = models.URLField(verbose_name=_("Download afbeeldingen URL"), blank=True, null=True)
    vereist_voogd_toestemming = models.BooleanField(verbose_name=_("Toestemming van voogd vereist"), default=False)
    toon_op_site = models.BooleanField(verbose_name=_("Toon op site"), default=False)

    enable_inschrijvingen = models.BooleanField(verbose_name=_("Inschrijvingen Inschakelen"), default=False)

    header_groepen = models.ManyToManyField(
        DartskampHeaderGroep,
        verbose_name=_("Groepen in header"),
        related_name='dartskampen',
        blank=True,
    )
    naam_in_header = models.CharField(max_length=25, verbose_name=_("Naam in header"), blank=True, null=True)   

    resultaten = RichTextField(verbose_name=_("Resultaten"), blank=True, null=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    def save(self, *args, **kwargs):
        brussels_tz = pytz.timezone('Europe/Brussels')

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
        return self.participants_count >= self.max_deelnemers

    @property
    def remaining_plaatsen(self):
        return max(self.max_deelnemers - self.participants_count, 0)

    # Backwards-compatible alias used in some templates
    @property
    def remaining_tickets(self):
        return self.remaining_plaatsen
    
    @property
    def participants_count(self):
        return self.deelnemers.filter(
            Q(payment__status=PaymentStatus.PAID) |
            Q(payment__status=PaymentStatus.OPEN)
        ).count()
    
    def get_absolute_url(self):
        return f'https://chudartz.com/nl/dartskampen/{str(self.slug)}/'
    
    @property
    def vereisten_lijst(self):
        return self.vereisten.split('\n')


class PaymentStatus:
    PAID = "paid"
    AUTHORIZED = "authorized"
    OPEN = "open"
    CANCELED = "canceled"
    EXPIRED = "expired"
    FAILED = "failed"
    REFUNDED = "refunded"


    CHOICES = [
        (PAID, pgettext_lazy("payment status", "Betaald")),
        (OPEN, pgettext_lazy("payment status", "Open")),
        (CANCELED, pgettext_lazy("payment status", "Geannuleerd")),
        (EXPIRED, pgettext_lazy("payment status", "Verlopen")),
        (FAILED, pgettext_lazy("payment status", "Gefaald")),
        (REFUNDED, pgettext_lazy("payment status", "Teruggestort"))
    ]


class Payment(models.Model):

    def __str__(self) -> str:
        return f"{self.mollie_id} | {self.first_name} {self.last_name}" 

    class Meta:
        verbose_name = "Betaling"
        verbose_name_plural = "Betalingen"
    
    def save(self, *args, **kwargs):
        
        # instantie bestaat al
        if self.pk:
            # check als de betaling reeds betaald is.
            previous = Payment.objects.get(pk=self.pk)
            status_changed_to_paid = (previous.status != PaymentStatus.PAID) and (self.status == PaymentStatus.PAID)
        else:
            # Nieuwe instantie
            status_changed_to_paid = self.status == PaymentStatus.PAID


        if status_changed_to_paid:

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

        print("Payment update received: mollie id ({self.mollie_id}) with status {self.status}")


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



# Deelnemer van dartskamp
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
    gsm = PhoneNumberField(verbose_name=_("GSM"), null=False, blank=False)
    
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT, verbose_name="Payment", blank=True, null=True)
    beschrijving = models.TextField(blank=True, null=True, verbose_name=_("beschrijving"))
    dartskamp = models.ForeignKey(
        Dartskamp,
        verbose_name=_("Dartskamp"),
        on_delete=models.RESTRICT,
        related_name="deelnemers",
    )
    
    history = HistoricalRecords(verbose_name=_("History"))

    def send_mail(self):
        event = self.dartskamp
        
        email_body = render_to_string('email/confirmation-mail-participant.html', {
            'event': event,
            'participant': self,
        })

        email = EmailMessage(
            'ChudartZ | Bevestiging',
            email_body,
            formataddr(('Dartskampen | Chudartz', settings.EMAIL_HOST_USER)),
            [self.email],
            bcc=[settings.EMAIL_HOST_USER]
        )
        email.content_subtype = 'html'

        helpers.attach_image(email, "logo-black")
        email.send()


class Sponsor(models.Model):
    naam = models.CharField(max_length=50, verbose_name=_("Naam"))
    website_url = models.URLField(verbose_name=_("Website URL"))
    info = RichTextField(verbose_name=_("Info over Sponsor"))
    toon_op_index = models.BooleanField(verbose_name=_("Toon Op Voorpagina"), default=True)
    toon_in_footer = models.BooleanField(verbose_name=_("Toon in footer"), default=True)
    toon_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon op sponsor pagina"), default=True)
    toon_knop_op_sponsors_pagina = models.BooleanField(verbose_name=_("Toon knop op sponsors pagina"), default=True)
    volgorde_footer = models.SmallIntegerField(verbose_name=_("Volgorde in footer"), default=0)
    volgorde_pagina = models.SmallIntegerField(verbose_name=_("Volgorde op pagina"), default=0)
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

    def clean(self):
        super().clean()  # Call the parent class's clean method first
        if not self.link and not self.artikel_bestand:
            raise ValidationError("At least one of link or artikel_bestand must be provided.")
    
    def save(self, *args, **kwargs):
        self.full_clean()  # Call full_clean to ensure clean method runs before saving
        super().save(*args, **kwargs)


    titel = models.CharField(verbose_name=_("Titel"), max_length=120)
    naam_website = models.CharField(verbose_name=_("Naam Website"), max_length=50)
    link = models.URLField(verbose_name=_("Artikel URL"), null=True, blank=True)
    artikel_bestand = models.FileField(verbose_name=_("Artikel Bestand"), null=True, blank=True, upload_to="artikels")
    icon = models.CharField(max_length=40, verbose_name=_("Bootstrap Icon"))
    active = models.BooleanField(verbose_name=_("Actief"))

    history = HistoricalRecords(verbose_name=_("History"))


class Trainer(models.Model):
    def __str__(self):
        return self.naam
    
    class Meta:
        verbose_name = 'Trainer'
        verbose_name_plural = 'Trainers'

    naam = models.CharField(max_length=50, verbose_name=_("Naam"))
    titel = models.CharField(max_length=50, verbose_name=_("Titel"))
    extra_info = models.CharField(max_length=256, verbose_name=_("Extra Info"))
    afbeelding = models.ImageField(verbose_name=_("Afbeelding"), upload_to="trainers")
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)
    active = models.BooleanField(verbose_name=_("Actief"))

    history = HistoricalRecords(verbose_name=_("History"))


class Locatie(models.Model):

    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        verbose_name = "Locatie"
        verbose_name_plural = "Locaties"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    afbeelding = models.ImageField(verbose_name=_("Hoofdafbeelding"), upload_to="locaties")
    # TODO meerdere fotos?
    locatie = models.CharField(max_length=100, verbose_name=_("Locatie"))
    adres = models.CharField(max_length=100, verbose_name=_("Adres"))
    lesuren = RichTextField(verbose_name=_("Lesuren"))
    extra_info = RichTextField(verbose_name=_("Extra Info"))
    slug = models.SlugField(unique=True)
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)
    active = models.BooleanField(verbose_name=_("Actief"), default=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))


class League(models.Model):

    def __str__(self) -> str:
        return self.titel

    def get_absolute_url(self):
        return f'https://chudartz.com/nl/dartschool/leagues/{self.slug}/'

    class Meta:
        verbose_name = "League"
        verbose_name_plural = "Leagues"
        ordering = ['-jaar', '-volgorde']

    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    slug = models.SlugField(unique=True)
    locatie = models.ForeignKey(
        Locatie,
        on_delete=models.CASCADE,
        related_name='leagues',
        null=True,
        blank=True,
        verbose_name=_("Locatie"),
    )
    jaar = models.PositiveSmallIntegerField(verbose_name=_("Jaar"))
    historisch = models.BooleanField(
        verbose_name=_("Historisch"),
        default=False,
        help_text=_(
            "Historische leagues verschijnen niet op het leagues-overzicht, "
            "maar wel via de locatiepagina."
        ),
    )
    active = models.BooleanField(verbose_name=_("Actief"), default=True)
    volgorde = models.SmallIntegerField(verbose_name=_("Volgorde"), default=0)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    @property
    def is_superleague(self):
        return self.locatie_id is None


class LeagueDivisie(models.Model):

    def __str__(self) -> str:
        return f"{self.league.titel} — {self.naam}"

    class Meta:
        verbose_name = "League Divisie"
        verbose_name_plural = "League Divisies"
        ordering = ['volgorde', 'id']

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='divisies',
        verbose_name=_("League"),
    )
    naam = models.CharField(max_length=100, verbose_name=_("Naam"))
    volgorde = models.PositiveSmallIntegerField(verbose_name=_("Volgorde"), default=0)
    uitslagen = RichTextField(
        config_name='league_table',
        verbose_name=_("Uitslagen"),
        blank=True,
    )
    stand = RichTextField(
        config_name='league_table',
        verbose_name=_("Stand"),
        blank=True,
    )
    toelichting = RichTextField(verbose_name=_("Toelichting"), blank=True)

    history = HistoricalRecords(verbose_name=_("Geschiedenis"))

    def save(self, *args, **kwargs):
        from .utils.league_tables import blank_if_default

        self.uitslagen = blank_if_default(self.uitslagen, 'uitslagen')
        self.stand = blank_if_default(self.stand, 'stand')
        super().save(*args, **kwargs)


class DartskampFoto(models.Model):
    dartskamp = models.ForeignKey(Dartskamp, on_delete=models.CASCADE, related_name="fotos", verbose_name=_("Dartskamp"))
    afbeelding = models.ImageField(upload_to="dartskamp_fotos", verbose_name=_("Foto"), validators=[validate_image_max_size])
    omschrijving = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Omschrijving"))
    volgorde = models.PositiveIntegerField(default=0, verbose_name=_("Volgorde"))

    class Meta:
        ordering = ["volgorde", "id"]
        verbose_name = "Dartskamp Foto"
        verbose_name_plural = "Dartskamp Foto's"

    def __str__(self):
        return f"Foto voor {self.dartskamp.titel} ({self.id})"


class IndexFotoCategory:
    DARTSCHOOL = "dartschool"
    DARTSKAMP = "dartskamp"
    ANDERE = "andere"

    CHOICES = [
        (DARTSCHOOL, pgettext_lazy("indexfoto category", "Dartschool")),
        (DARTSKAMP, pgettext_lazy("indexfoto category", "Dartskamp")),
        (ANDERE, pgettext_lazy("indexfoto category", "Andere")),
    ]

class IndexFoto(models.Model):
    def __str__(self) -> str:
        return self.titel
    
    class Meta:
        verbose_name = "Index Foto"
        verbose_name_plural = "Index Foto's"
    
    titel = models.CharField(max_length=100, verbose_name=_("Titel"))
    afbeelding = models.ImageField(verbose_name=_("Afbeelding"), upload_to="index_fotos", validators=[validate_image_max_size],)
    category = models.CharField(max_length=10, choices=IndexFotoCategory.CHOICES, default=IndexFotoCategory.DARTSCHOOL, verbose_name=_("Categorie"))
    active = models.BooleanField(verbose_name=_("Actief"), default=True)