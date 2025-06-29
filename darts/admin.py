from django.contrib import messages
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import DropdownFilter, RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from .models import *


# INLINES #
class TicketInline(StackedInline):
    model = Ticket
    verbose_name = _("Evenement Ticket")
    verbose_name_plural = _("Evenement Tickets")

class ToernooiFotoInline(StackedInline):
    model = ToernooiFoto
    extra = 1
    verbose_name = _("Toernooi Foto")
    verbose_name_plural = _("Toernooi Foto's")

# FILTERS #
class ToernooiFilter(DropdownFilter):
    title = 'Toernooi'  # Display name of the filter in the admin
    parameter_name = 'toernooi'  # URL parameter name used for filtering

    def lookups(self, request, model_admin):
        # Provide options for filtering based on distinct events
        events = Toernooi.objects.all()
        return [(event.pk, event.titel) for event in events]

    def queryset(self, request, queryset):
        # Filter the queryset of Participants based on the selected event
        if self.value():
            return queryset.filter(ticket__event__pk=self.value())
        return queryset


# MODELS #
@admin.register(ToernooiHeaderGroep)
class ToernooiHeaderGroepAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('naam', 'active', )


@admin.register(Toernooi)
class ToernooiAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('display_header', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    exclude = ('tickets',)

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')
    inlines = [
        TicketInline,
        ToernooiFotoInline,
    ]

    actions_detail = ["generate_qr_code",]

    @display(description=_("Titel"), header=True)
    def display_header(self, instance: Toernooi):
        return [
            instance.titel,
            None,
            instance.titel,
            {
                "path": instance.afbeelding.url,
                "height": 24,
                "width": 24,
                "borderless": True,
                "squared": True,
            },
        ]
    
    @display(
        description=_("Uitverkocht"),
        label={
            True: "danger",
            False: "success"
        }
    )
    def is_sold_out(self, obj):
        label = _("Sold out!") if obj.is_sold_out else _("Available")
        return obj.is_sold_out, label

    def view_on_site(self, obj):
        return obj.get_absolute_url()
    
    @action(description=_("Genereer QR Code"))
    def generate_qr_code(modeladmin, request, object_id: int):
        toernooi = get_object_or_404(Toernooi, pk=object_id)

        url = request.build_absolute_uri(toernooi.get_absolute_url())
        qr = qrcode.make(url)

        # Save the QR code to an in-memory file
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Create an HTTP response with the image
        response = HttpResponse(buffer, content_type="image/png")
        response['Content-Disposition'] = f'attachment; filename=qr_{toernooi.titel}.png'
        return response         


@admin.register(Participant)
class ParticipantAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = ['voornaam', 'achternaam', 'evenement', 'payment_status', 'attendance']
    ordering = ('id',)

    @display(
        description=_('Status van Betaling'), 
        label={
            PaymentStatus.PAID: "success",
            PaymentStatus.OPEN: "warning",
            PaymentStatus.CANCELED: "danger",
            PaymentStatus.EXPIRED: "danger",
            PaymentStatus.FAILED: "danger",
            PaymentStatus.REFUNDED: "warning",
        },
        header=True,
    )
    def payment_status(self, obj):
        if obj.payment is None: return PaymentStatus.OPEN

        return obj.payment.status
    
    @display(
        description=_("Attended"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def attendance(self, obj):
        label = _("Yes") if obj.attended else _("No")
        return obj.attended, label

    @display(description=_("Evenement"))
    def evenement(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(
            reverse("admin:darts_toernooi_change", args=(obj.ticket.event.pk,)),
            obj.ticket.event.titel
        ))
    

    search_fields = ('voornaam', 'achternaam', 'email')
    list_filter = (
        ToernooiFilter,
        ('attended', admin.BooleanFieldListFilter),
        ('ticket', RelatedDropdownFilter),
    )

    list_filter_submit = True
    actions_detail = ["generate_ticket", "send_confirmation_mail"]
    
    @action(description=_("Genereer Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        participant = get_object_or_404(Participant, pk=object_id)

        return participant.generate_ticket()

    @action(description=_("Stuur bevestiging mail"))
    def send_confirmation_mail(modeladmin, request, object_id: int):
        participant = get_object_or_404(Participant, pk=object_id)

        try:
            participant.send_mail()
            messages.success(request, _("Bevestigings mail is verstuurd!"))
        
        except Exception as e:
            messages.error(request, _("Bevestigings mail versturen mislukt. Error: ") + str(e))
        

        return redirect(reverse('admin:darts_participant_change', args=[participant.pk]))




@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin, ModelAdmin):
    actions_detail = ["generate_ticket",]

    @action(description=_("Generate Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        p = get_object_or_404(Payment, pk=object_id)

        return p.generate_ticket()


@admin.register(Ticket)
class TicketAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'price', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ("id",)

    search_fields = ('titel', 'beschrijving')

    @display(
        description=_("Sold out"),
        label={
            True: "danger",
            False: "success"
        }
    )
    def is_sold_out(self, obj):
        label = _("Sold out!") if obj.is_sold_out else _("Available")
        return obj.is_sold_out, label
    

@admin.register(Sponsor)
class SponsorAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = ('display_header', 'toon_op_voorpagina', 'toon_in_footer_display', 'toon_op_sponsor_pg_display')
    ordering = ('id',)

    search_fields = ('naam', 'info', )

    @display(description=_("Naam"), header=True)
    def display_header(self, instance: Sponsor):
        return [
            instance.naam,
            None,
            instance.naam,
            {
                "path": instance.logo.url,
                "height": 24,
                "width": 24,
                "borderless": True,
                "squared": True,
            },
        ]
    
    @display(
        description=_("Toon op voorpagina"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def toon_op_voorpagina(self, obj: Sponsor):
        label = _("Ja") if obj.toon_op_index else _("Nee")
        return obj.toon_op_index, label
    
    @display(
        description=_("Toon in footer"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def toon_in_footer_display(self, obj: Sponsor):
        label = _("Ja") if obj.toon_in_footer else _("Nee")
        return obj.toon_in_footer, label
    
    @display(
        description=_("Toon op sponsors pagina"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def toon_op_sponsor_pg_display(self, obj: Sponsor):
        label = _("Ja") if obj.toon_op_sponsors_pagina else _("Nee")
        return obj.toon_op_sponsors_pagina, label


@admin.register(Leerling)
class LeerlingAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = ('voornaam', 'achternaam', 'resterende_beurten', 'payment_status', 'code')
    readonly_fields=('code',)
    ordering = ('voornaam', 'achternaam')

    search_fields = ('voornaam', 'achternaam', 'extra_info')

    @display(
        description=_('Status van Betaling'), 
        label={
            PaymentStatus.PAID: "success",
            PaymentStatus.OPEN: "warning",
            PaymentStatus.CANCELED: "danger",
            PaymentStatus.EXPIRED: "danger",
            PaymentStatus.FAILED: "danger",
        },
        header=True,
    )
    def payment_status(self, obj):
        if obj.payment is None: return PaymentStatus.OPEN

        return obj.payment.status


@admin.register(Beurtkaart)
class BeurtkaartAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('naam', 'aantal_beurten', 'prijs')
    ordering = ('-aantal_beurten',)

    search_fields = ('naam', 'aantal_beurten', 'prijs')


@admin.register(Nieuws)
class NieuwsAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    list_display = ('titel', 'naam_website', 'is_active')

    search_fields = ('naam', 'naam_website')

    @display(
        description=_("Actief"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def is_active(self, obj):
        label = _("Ja") if obj.active else _("Nee")
        return obj.active, label
    

@admin.register(Trainer)
class TrainerAdmin(SimpleHistoryAdmin, ModelAdmin):
    
    list_display = ('display_header', 'titel', 'is_active')
    search_fields = ('naam', 'titel')

    @display(description=_("Trainer"), header=True)
    def display_header(self, instance: Trainer):
        return [
            instance.naam,
            None,
            instance.naam,
            {
                "path": instance.afbeelding.url,
                "height": 24,
                "width": 24,
                "borderless": True,
                # "squared": True,
            },
        ]
        
    @display(
        description=_("Actief"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def is_active(self, obj):
        label = _("Ja") if obj.active else _("Nee")
        return obj.active, label


@admin.register(Locatie)
class LocatieAdmin(SimpleHistoryAdmin, ModelAdmin):
    
    list_display = ('display_header', 'is_active')
    search_fields = ('titel',)

    @display(description=_("Titel"), header=True)
    def display_header(self, instance: Locatie):
        return [
            instance.titel,
            None,
            instance.titel,
            {
                "path": instance.afbeelding.url,
                "height": 24,
                "width": 24,
                "borderless": True,
                "squared": True,
            },
        ]
    
    @display(
        description=_("Actief"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def is_active(self, obj):
        label = _("Ja") if obj.active else _("Nee")
        return obj.active, label
    
    def get_readonly_fields(self, request, obj: Locatie=None):
        # Make 'slug' field read-only for non-superusers
        if not request.user.is_superuser:
            return ('slug',) + self.readonly_fields
        return self.readonly_fields  # Superusers can edit all fields
    

@admin.register(IndexFoto)
class IndexFotoAdmin(ModelAdmin):
    list_display = ('display_header', 'category', 'is_active')
    search_fields = ('titel',)
    list_filter = (
        ('category', admin.ChoicesFieldListFilter),
    )

    @display(description=_("Titel"), header=True)
    def display_header(self, instance: IndexFoto):
        return [
            instance.titel,
            None,
            instance.titel,
            {
                "path": instance.afbeelding.url,
                "height": 72,
                "width": 72,
                "borderless": True,
                "squared": True,
            },
        ]
    
    @display(
        description=_("Actief"),
        label={
            True: "success",
            False: "danger"
        }
    )
    def is_active(self, obj):
        label = _("Ja") if obj.active else _("Nee")
        return obj.active, label