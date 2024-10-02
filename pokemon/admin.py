from django.contrib import messages
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display

from .models import *

class TicketInline(StackedInline):
    model = Ticket
    verbose_name = _("Evenement Ticket")
    verbose_name_plural = _("Evenement Tickets")

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


@admin.register(Evenement)
class EvenementAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('titel', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    exclude = ('tickets',)
    inlines = [
        TicketInline
    ]
    actions_detail = ["generate_qr_code",]

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')

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
        evenement = get_object_or_404(Evenement, pk=object_id)

        url = request.build_absolute_uri(evenement.get_absolute_url())
        qr = qrcode.make(url)

        # Save the QR code to an in-memory file
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Create an HTTP response with the image
        response = HttpResponse(buffer, content_type="image/png")
        response['Content-Disposition'] = f'attachment; filename=qr_{evenement.titel}.png'
        return response      
    

@admin.register(TicketEigenschap)
class TicketEigenschapAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('tekst', )
