from django.contrib import messages
from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import DropdownFilter, RelatedDropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from .forms import LeagueDivisieForm
from .models import *

# INLINES #
class DartskampFotoInline(StackedInline):
    model = DartskampFoto
    extra = 1
    verbose_name = _("Dartskamp Foto")
    verbose_name_plural = _("Dartskamp Foto's")

class LeagueDivisieInline(StackedInline):
    model = LeagueDivisie
    form = LeagueDivisieForm
    extra = 0
    ordering = ('volgorde',)
    fields = ('naam', 'volgorde', 'uitslagen', 'stand', 'toelichting')
    verbose_name = _("Divisie")
    verbose_name_plural = _("Divisies")

class LeagueInline(TabularInline):
    model = League
    extra = 0
    fields = ('titel', 'jaar', 'slug', 'historisch', 'active', 'volgorde')
    show_change_link = True
    verbose_name = _("League")
    verbose_name_plural = _("Leagues")

# FILTERS #
class DartskampFilter(DropdownFilter):
    title = 'Dartskamp'
    parameter_name = 'dartskamp'

    def lookups(self, request, model_admin):
        events = Dartskamp.objects.all()
        return [(event.pk, event.titel) for event in events]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(dartskamp__pk=self.value())
        return queryset


# MODELS #
@admin.register(DartskampHeaderGroep)
class DartskampHeaderGroepAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('naam', 'active', )


@admin.register(Dartskamp)
class DartskampAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('display_header', 'prijs', 'participants_count', 'remaining_plaatsen', 'is_sold_out')
    ordering = ('id',)

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')
    inlines = [
        DartskampFotoInline,
    ]

    @display(description=_("Titel"), header=True)
    def display_header(self, instance: Dartskamp):
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


@admin.register(Participant)
class ParticipantAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = ['voornaam', 'achternaam', 'evenement', 'payment_status']
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

    @display(description=_("Dartskamp"))
    def evenement(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(
            reverse("admin:darts_dartskamp_change", args=(obj.dartskamp.pk,)),
            obj.dartskamp.titel
        ))
    

    search_fields = ('voornaam', 'achternaam', 'email')
    list_filter = (
        DartskampFilter,
        ('dartskamp', RelatedDropdownFilter),
    )

    list_filter_submit = True
    actions_detail = ["send_confirmation_mail"]

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
    list_display = ('mollie_id', 'first_name', 'last_name', 'status', 'amount')
    search_fields = ('mollie_id', 'first_name', 'last_name', 'mail')


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
    inlines = [LeagueInline]

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
    

@admin.register(League)
class LeagueAdmin(SimpleHistoryAdmin, ModelAdmin):

    list_display = ('titel', 'jaar', 'display_locatie', 'divisie_count', 'display_historisch', 'is_active')
    list_filter = ('active', 'historisch', 'jaar', 'locatie')
    search_fields = ('titel',)
    ordering = ('-jaar', '-volgorde')
    prepopulated_fields = {'slug': ('titel',)}
    inlines = [LeagueDivisieInline]
    fieldsets = (
        (None, {
            'fields': ('titel', 'slug', 'locatie', 'jaar', 'historisch', 'active', 'volgorde'),
        }),
    )

    @display(description=_("Locatie"))
    def display_locatie(self, obj):
        if obj.locatie_id is None:
            return _("Superleague")
        return obj.locatie.titel

    @display(description=_("Divisies"))
    def divisie_count(self, obj):
        return obj.divisies.count()

    @display(
        description=_("Historisch"),
        label={
            True: "warning",
            False: "success",
        },
    )
    def display_historisch(self, obj):
        label = _("Ja") if obj.historisch else _("Nee")
        return obj.historisch, label

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

    def view_on_site(self, obj):
        return obj.get_absolute_url()


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
