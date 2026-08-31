from django.contrib import messages
from django.contrib import admin
from django import forms
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
import json
from io import BytesIO
import qrcode
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RelatedDropdownFilter, DropdownFilter
from unfold.contrib.inlines.admin import StackedInline
from unfold.decorators import action, display
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm


from .models import *
from pokemon.standhouder_wizard import (
    clear_studio_preview_inschrijving,
    serialize_standhouder_vraag,
    serialize_zaalplan_grid,
)
from pokemon.standhouder_studio import (
    build_preview_step_context,
    handle_preview_post,
    preview_steps_for,
)
from pokemon.services.gate import device_payload, monitor_payload
from pokemon.models import VraagType
from decimal import Decimal, InvalidOperation
from djmoney.money import Money

# INLINES #
class TicketInline(StackedInline):
    model = Ticket
    extra = 0
    verbose_name = _("Evenement Ticket")
    verbose_name_plural = _("Evenement Tickets")
    fields = (
        "titel",
        "price",
        "icon",
        "max_deelnemers",
        "disable_ticket",
        "toegang_start",
        "toegang_einde",
    )

class EvenementFotoInline(StackedInline):
    model = EvenementFoto
    extra = 1
    verbose_name = _("Evenement Foto")
    verbose_name_plural = _("Evenement Foto's")


class StandhouderVraagInline(StackedInline):
    model = StandhouderVraag
    extra = 0
    classes = ["collapse"]
    verbose_name = _("Standhouder vraag")
    verbose_name_plural = _("Standhouder vragen (legacy — gebruik Standhouder studio)")
    ordering = ("volgorde",)
    fields = (
        "tekst",
        "vraag_type",
        "opties",
        "verplicht",
        "volgorde",
        "prijs_toeslag",
        "prijs_toeslag_excl_btw",
        "prijs_toeslag_btw_percentage",
        "is_borg",
        "min_tafels",
        "max_tafels",
    )


# FILTERS #
class EvenementFilter(DropdownFilter):
    title = 'Evenement'
    parameter_name = 'evenement'

    def lookups(self, request, model_admin):
        events = Evenement.objects.all()
        return [(event.pk, event.titel) for event in events]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(ticket__event__pk=self.value())
        return queryset


class StandhouderEvenementFilter(DropdownFilter):
    title = 'Evenement'
    parameter_name = 'evenement'

    def lookups(self, request, model_admin):
        events = Evenement.objects.all()
        return [(event.pk, event.titel) for event in events]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(evenement__pk=self.value())
        return queryset


class StandhouderStatusFilter(DropdownFilter):
    title = _('Status')
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('actief', _('Actieve inschrijvingen')),
            ('concept', _('Concept')),
            ('ingediend', _('Ingediend')),
            ('all', _('Alle statussen')),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'concept':
            return queryset.filter(status=StandhouderInschrijvingStatus.CONCEPT)
        if value == 'ingediend':
            return queryset.filter(status=StandhouderInschrijvingStatus.INGEDIEND)
        if value == 'all':
            return queryset
        return queryset.exclude(status=StandhouderInschrijvingStatus.CONCEPT)


class EvenementEinddatumFilter(DropdownFilter):
    title = _('Einddatum')
    parameter_name = 'einddatum'

    def lookups(self, request, model_admin):
        return [
            ('future', _('In de toekomst')),
            ('past', _('Verlopen')),
            ('all', _('Alle')),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        value = self.value()

        if value == 'past':
            return queryset.filter(einde_datum__lt=now)
        if value == 'all':
            return queryset
        if value == 'future':
            return queryset.filter(einde_datum__gte=now)
        return queryset
    
# MODELS #
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
    

@admin.register(Partner)
class PartnerAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = ('display_header',)
    ordering = ('id',)

    search_fields = ('name', )

    @display(description=_("Naam"), header=True)
    def display_header(self, instance: Partner):
        return [
            instance.name,
            None,
            instance.name,
            {
                "path": instance.logo.url,
                "height": 24,
                "width": 24,
                "borderless": True,
                "squared": True,
            },
        ]


@admin.register(Participant)
class ParticipantAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    list_display = ['mail', 'evenement', 'payment_status', 'attendance']
    ordering = ('id',)

    @display(description=_("Evenement"))
    def evenement(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(
            reverse("admin:pokemon_evenement_change", args=(obj.ticket.event.pk,)),
            obj.ticket.event.titel
        ))
    
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
    

    search_fields = ('mail',)
    list_filter = (
        EvenementFilter,
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
            participant.payment.send_mail()
            messages.success(request, _("Bevestigings mail is verstuurd!"))
        
        except Exception as e:
            messages.error(request, _("Bevestigings mail versturen mislukt. Error: ") + str(e))
        

        return redirect(reverse('admin:pokemon_participant_change', args=[participant.pk]))


@admin.register(Kortingscode)
class KortingscodeAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ("code", "discount_type", "amount", "actief", "aantal_gebruikt", "max_gebruik", "geldig_tot")
    list_filter = ("actief", "discount_type")
    search_fields = ("code",)
    filter_horizontal = ("evenementen", "tickets")
    fieldsets = (
        (None, {
            "fields": ("code", "discount_type", "amount", "actief"),
        }),
        (_("Geldigheid"), {
            "fields": ("geldig_van", "geldig_tot", "max_gebruik", "aantal_gebruikt"),
        }),
        (_("Voorwaarden"), {
            "fields": ("min_bedrag", "evenementen", "tickets"),
        }),
    )
    readonly_fields = ("aantal_gebruikt",)


@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ("mollie_id", "mail", "amount", "korting_bedrag", "kortingscode", "status")
    list_filter = ("status",)
    actions_detail = ["generate_ticket",]

    @action(description=_("Generate Ticket"))
    def generate_ticket(modeladmin, request, object_id: int):
        p = get_object_or_404(Payment, pk=object_id)

        return p.generate_ticket()


@admin.register(Evenement)
class EvenementAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('display_header', 'participants_count', 'remaining_tickets', 'is_sold_out')
    ordering = ('id',)
    inlines = [
        StandhouderVraagInline,
        TicketInline,
        EvenementFotoInline,
    ]
    actions_detail = ["generate_qr_code", "beheer_zaalplan", "standhouder_studio"]
    list_filter = (EvenementEinddatumFilter,)
    list_filter_submit = True

    search_fields = ('titel', 'beschrijving', 'start_datum', 'einde_datum', 'locatie_lang')

    fieldsets = (
        (_("Algemeen"), {
            "fields": ("titel", "slug", "afbeelding", "intro_op_index"),
        }),
        (_("Pagina-inhoud"), {
            "fields": ("titel_sectie_a", "tekst_sectie_a"),
        }),
        (_("Datum & locatie"), {
            "fields": ("start_datum", "einde_datum", "max_deelnemers", "locatie_kort", "locatie_lang"),
        }),
        (_("Weergave op de site"), {
            "fields": ("toon_op_site", "highlight_event", "volgorde", "partners"),
        }),
        (_("Bezoekers · tickets"), {
            "fields": ("enable_inschrijvingen",),
            "description": _("Ticketverkoop voor bezoekers. Tickets beheer je via de sectie 'Evenement Tickets' onderaan."),
        }),
        (_("Standhouders · algemeen"), {
            "fields": ("enable_standhouder", "standhouder_inbegrepen", "standhouder_prijzen"),
            "description": _(
                "Vragen en live voorvertoning beheer je via de knop 'Standhouder studio' bovenaan. "
                "Zaalplan via 'Zaalplan beheren'."
            ),
        }),
        (_("Standhouders · tafels & prijzen"), {
            "fields": (
                "standhouder_zaalplan_actief",
                "standhouder_max_tafels",
                "standhouder_prijs_per_tafel",
                "standhouder_prijs_excl_btw",
                "standhouder_prijs_btw_percentage",
                "standhouder_betaling_verplicht",
            ),
            "description": _(
                "Het maximum aantal tafels per standhouder geldt altijd, met of zonder zaalplan. "
                "Staat het zaalplan aan, dan kiezen standhouders hun tafel op de plattegrond "
                "(beheer via de knop 'Zaalplan beheren' bovenaan; BTW stel je daar ook in). "
                "Staat het uit, dan geven ze enkel een aantal tafels op tegen de prijs per tafel. "
                "Zet 'exclusief BTW' aan als de ingevoerde prijs zonder btw is; het percentage "
                "wordt dan achteraf bij het te betalen totaal opgeteld."
            ),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        from djmoney.forms.widgets import MoneyWidget

        if db_field.name in ("standhouder_prijs_per_tafel", "prijs_toeslag"):
            kwargs["widget"] = MoneyWidget(
                amount_widget=forms.NumberInput(attrs={"step": "0.01"}),
                choices=[("EUR", "Euro")],
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/zaalplan/',
                self.admin_site.admin_view(self.zaalplan_editor_view),
                name='pokemon_zaalplan_editor',
            ),
            path(
                '<int:object_id>/zaalplan/settings/',
                self.admin_site.admin_view(self.zaalplan_settings_view),
                name='pokemon_zaalplan_settings',
            ),
            path(
                '<int:object_id>/zaalplan/generate/',
                self.admin_site.admin_view(self.zaalplan_generate_view),
                name='pokemon_zaalplan_generate',
            ),
            path(
                '<int:object_id>/zaalplan/cel/',
                self.admin_site.admin_view(self.zaalplan_save_cel_view),
                name='pokemon_zaalplan_save_cel',
            ),
            path(
                '<int:object_id>/zaalplan/merge/',
                self.admin_site.admin_view(self.zaalplan_merge_view),
                name='pokemon_zaalplan_merge',
            ),
            path(
                '<int:object_id>/zaalplan/split/',
                self.admin_site.admin_view(self.zaalplan_split_view),
                name='pokemon_zaalplan_split',
            ),
            path(
                '<int:object_id>/standhouder-studio/',
                self.admin_site.admin_view(self.standhouder_studio_view),
                name='pokemon_standhouder_studio',
            ),
            path(
                '<int:object_id>/standhouder-studio/preview/',
                self.admin_site.admin_view(self.standhouder_studio_preview_view),
                name='pokemon_standhouder_studio_preview',
            ),
            path(
                '<int:object_id>/standhouder-studio/vragen/',
                self.admin_site.admin_view(self.standhouder_studio_vragen_list_view),
                name='pokemon_standhouder_studio_vragen',
            ),
            path(
                '<int:object_id>/standhouder-studio/vragen/save/',
                self.admin_site.admin_view(self.standhouder_studio_vraag_save_view),
                name='pokemon_standhouder_studio_vraag_save',
            ),
            path(
                '<int:object_id>/standhouder-studio/vragen/delete/',
                self.admin_site.admin_view(self.standhouder_studio_vraag_delete_view),
                name='pokemon_standhouder_studio_vraag_delete',
            ),
            path(
                '<int:object_id>/standhouder-studio/vragen/reorder/',
                self.admin_site.admin_view(self.standhouder_studio_vragen_reorder_view),
                name='pokemon_standhouder_studio_vragen_reorder',
            ),
            path(
                '<int:object_id>/standhouder-studio/copy/',
                self.admin_site.admin_view(self.standhouder_studio_copy_save_view),
                name='pokemon_standhouder_studio_copy',
            ),
        ]
        return custom_urls + urls

    def _get_or_create_zaalplan(self, evenement):
        zaalplan, _ = Zaalplan.objects.get_or_create(evenement=evenement)
        return zaalplan

    def zaalplan_editor_view(self, request, object_id):
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        if zaalplan.cellen.count() == 0:
            zaalplan.genereer_rooster()
        grid = serialize_zaalplan_grid(zaalplan)
        return render(request, 'admin/pokemon/zaalplan_editor.html', {
            'evenement': evenement,
            'zaalplan': zaalplan,
            'grid_json': json.dumps(grid),
            'title': _('Zaalplan beheren'),
        })

    def zaalplan_settings_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        try:
            data = json.loads(request.body)
            zaalplan.rijen = int(data.get('rijen', zaalplan.rijen))
            zaalplan.kolommen = int(data.get('kolommen', zaalplan.kolommen))
            zaalplan.standaard_prijs = data.get('standaard_prijs', zaalplan.standaard_prijs.amount)
            if 'prijs_excl_btw' in data:
                zaalplan.prijs_excl_btw = bool(data['prijs_excl_btw'])
            if data.get('btw_percentage') is not None and data.get('btw_percentage') != '':
                zaalplan.btw_percentage = data['btw_percentage']
            zaalplan.save()
            zaalplan.genereer_rooster()
            return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def zaalplan_generate_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        try:
            data = json.loads(request.body)
            zaalplan.rijen = int(data.get('rijen', zaalplan.rijen))
            zaalplan.kolommen = int(data.get('kolommen', zaalplan.kolommen))
            if data.get('standaard_prijs') is not None:
                zaalplan.standaard_prijs = data['standaard_prijs']
            if 'prijs_excl_btw' in data:
                zaalplan.prijs_excl_btw = bool(data['prijs_excl_btw'])
            if data.get('btw_percentage') is not None and data.get('btw_percentage') != '':
                zaalplan.btw_percentage = data['btw_percentage']
            zaalplan.save()
            zaalplan.genereer_rooster()
            return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def zaalplan_save_cel_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        try:
            data = json.loads(request.body)
            cel = get_object_or_404(ZaalplanCel, pk=data['cel_id'], zaalplan=zaalplan)

            if cel.is_bezet():
                return JsonResponse({'success': False, 'error': _('Deze cel heeft een echte boeking en kan niet gewijzigd worden.')}, status=400)

            # Rechtermuisklik: cel volledig leegmaken (ontgroepen, type leeg, reset)
            if data.get('leegmaken'):
                if cel.groep:
                    cel.ontgroepeer()
                cel.refresh_from_db()
                cel.cel_type = CelType.LEEG
                cel.label = ''
                cel.prijs = None
                cel.gereserveerd = False
                cel.save()
                return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})

            primary = cel.primary_cel()

            # Type toepassen op de hele groep zodat een samengevoegde entiteit consistent blijft
            if 'cel_type' in data:
                cel.groepsleden().update(cel_type=data['cel_type'])

            # Reservatie geldt voor de hele entiteit (hoofdcel)
            if 'gereserveerd' in data:
                primary.refresh_from_db()
                primary.gereserveerd = bool(data['gereserveerd'])
                primary.save(update_fields=['gereserveerd'])

            # Label/prijs horen bij de hoofdcel van de groep
            primary.refresh_from_db()
            if 'label' in data:
                primary.label = data['label']
            if 'prijs' in data:
                primary.prijs = data['prijs'] if data['prijs'] not in (None, '') else None
            primary.save()

            return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def zaalplan_merge_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        try:
            data = json.loads(request.body)
            cel_ids = data.get('cel_ids', [])
            geselecteerd = list(ZaalplanCel.objects.filter(pk__in=cel_ids, zaalplan=zaalplan))
            if len(geselecteerd) < 2:
                return JsonResponse({'success': False, 'error': _('Selecteer minstens twee cellen om samen te voegen.')}, status=400)

            # Bestaande groepen die geraakt worden, volledig meenemen
            geraakte_groepen = {c.groep for c in geselecteerd if c.groep}
            cellen = list(geselecteerd)
            if geraakte_groepen:
                cellen += list(ZaalplanCel.objects.filter(zaalplan=zaalplan, groep__in=geraakte_groepen))
            cellen = {c.pk: c for c in cellen}.values()

            for cel in cellen:
                if cel.is_bezet():
                    return JsonResponse({'success': False, 'error': _('Een van de cellen is al bezet en kan niet samengevoegd worden.')}, status=400)

            # Nieuw groep-id
            hoogste = zaalplan.cellen.exclude(groep=None).order_by('-groep').values_list('groep', flat=True).first()
            nieuw_groep_id = (hoogste or 0) + 1

            cellen = sorted(cellen, key=lambda c: (c.rij, c.kolom))
            primary = cellen[0]
            # Houd het bestaande type aan; als alles leeg is, blijft het leeg (geen automatische tafel)
            bestaand_type = next((c.cel_type for c in cellen if c.cel_type != CelType.LEEG), CelType.LEEG)

            pks = [c.pk for c in cellen]
            ZaalplanCel.objects.filter(pk__in=pks).update(
                groep=nieuw_groep_id,
                cel_type=bestaand_type,
            )
            # Label van bestaande primary behouden, andere labels wissen
            ZaalplanCel.objects.filter(pk__in=pks).exclude(pk=primary.pk).update(label='', prijs=None)

            return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def zaalplan_split_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        zaalplan = self._get_or_create_zaalplan(evenement)
        try:
            data = json.loads(request.body)
            cel = get_object_or_404(ZaalplanCel, pk=data['cel_id'], zaalplan=zaalplan)
            if cel.is_bezet():
                return JsonResponse({'success': False, 'error': _('Deze cel is bezet en kan niet gewijzigd worden.')}, status=400)
            cel.ontgroepeer()
            return JsonResponse({'success': True, 'grid': serialize_zaalplan_grid(zaalplan)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    @action(description=_("Zaalplan beheren"))
    def beheer_zaalplan(self, request, object_id: int):
        return redirect(reverse('admin:pokemon_zaalplan_editor', args=[object_id]))

    @action(description=_("Standhouder studio"))
    def standhouder_studio(self, request, object_id: int):
        return redirect(reverse('admin:pokemon_standhouder_studio', args=[object_id]))

    def standhouder_studio_view(self, request, object_id):
        evenement = get_object_or_404(Evenement, pk=object_id)
        vragen = [
            serialize_standhouder_vraag(v)
            for v in StandhouderVraag.objects.filter(evenement=evenement).order_by("volgorde", "id")
        ]
        prijs = evenement.standhouder_prijs_per_tafel
        boot = {
            'previewUrl': reverse('admin:pokemon_standhouder_studio_preview', args=[object_id]),
            'previewSteps': preview_steps_for(evenement),
            'vragen': vragen,
            'vraagTypes': [{"value": c[0], "label": str(c[1])} for c in VraagType.CHOICES],
            'zaalplanActief': evenement.standhouder_zaalplan_actief,
            'csrfToken': request.META.get('CSRF_COOKIE') or '',
            'api': {
                'vragen': reverse('admin:pokemon_standhouder_studio_vragen', args=[object_id]),
                'vraagSave': reverse('admin:pokemon_standhouder_studio_vraag_save', args=[object_id]),
                'vraagDelete': reverse('admin:pokemon_standhouder_studio_vraag_delete', args=[object_id]),
                'vragenReorder': reverse('admin:pokemon_standhouder_studio_vragen_reorder', args=[object_id]),
                'copy': reverse('admin:pokemon_standhouder_studio_copy', args=[object_id]),
            },
            'copy': {
                'standhouder_inbegrepen': evenement.standhouder_inbegrepen or '',
                'standhouder_prijzen': evenement.standhouder_prijzen or '',
                'standhouder_prijs_per_tafel': str(prijs.amount) if prijs else '0',
                'standhouder_prijs_excl_btw': evenement.standhouder_prijs_excl_btw,
                'standhouder_prijs_btw_percentage': str(evenement.standhouder_prijs_btw_percentage),
                'standhouder_max_tafels': evenement.standhouder_max_tafels,
                'standhouder_zaalplan_actief': evenement.standhouder_zaalplan_actief,
            },
        }
        # Prefer form csrf token
        from django.middleware.csrf import get_token
        boot['csrfToken'] = get_token(request)

        return render(request, 'admin/pokemon/standhouder_studio.html', {
            'evenement': evenement,
            'title': _('Standhouder studio'),
            'boot_json': json.dumps(boot),
            'zaalplan_url': reverse('admin:pokemon_zaalplan_editor', args=[object_id]),
            'event_change_url': reverse('admin:pokemon_evenement_change', args=[object_id]),
        })

    def standhouder_studio_preview_view(self, request, object_id):
        evenement = get_object_or_404(Evenement, pk=object_id)
        step = request.GET.get('step') or request.POST.get('step') or ''

        if request.method == 'POST':
            from pokemon.standhouder_wizard import get_or_create_studio_preview_inschrijving
            inschrijving = get_or_create_studio_preview_inschrijving(request, evenement)
            next_step, err = handle_preview_post(request, evenement, step, inschrijving)
            if err is None:
                return redirect(
                    reverse('admin:pokemon_standhouder_studio_preview', args=[object_id])
                    + f'?step={next_step}'
                )
            context, template = build_preview_step_context(request, evenement, step)
            if hasattr(err, 'is_bound'):
                context['form'] = err
            else:
                context['error'] = str(err)
            return render(request, template, context)

        context, template = build_preview_step_context(request, evenement, step)
        return render(request, template, context)

    def standhouder_studio_vragen_list_view(self, request, object_id):
        evenement = get_object_or_404(Evenement, pk=object_id)
        vragen = [
            serialize_standhouder_vraag(v)
            for v in StandhouderVraag.objects.filter(evenement=evenement).order_by("volgorde", "id")
        ]
        return JsonResponse({'success': True, 'vragen': vragen})

    def _parse_vraag_payload(self, data, evenement, vraag=None):
        tekst = (data.get('tekst') or '').strip()
        if not tekst:
            raise ValueError(_('Vraagtekst is verplicht.'))
        vraag_type = data.get('vraag_type') or VraagType.BOOLEAN
        valid_types = {c[0] for c in VraagType.CHOICES}
        if vraag_type not in valid_types:
            raise ValueError(_('Ongeldig vraagtype.'))

        toeslag_raw = data.get('prijs_toeslag')
        toeslag = None
        if toeslag_raw not in (None, ''):
            try:
                toeslag = Money(Decimal(str(toeslag_raw)), 'EUR')
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(_('Ongeldige toeslag.')) from exc

        btw_pct = data.get('prijs_toeslag_btw_percentage')
        if btw_pct in (None, ''):
            btw_pct = Decimal('21.00')
        else:
            btw_pct = Decimal(str(btw_pct))

        def opt_int(key):
            val = data.get(key)
            if val in (None, ''):
                return None
            return int(val)

        fields = {
            'evenement': evenement,
            'tekst': tekst[:200],
            'vraag_type': vraag_type,
            'opties': data.get('opties') or '',
            'verplicht': bool(data.get('verplicht')),
            'volgorde': int(data.get('volgorde') or (vraag.volgorde if vraag else 0)),
            'prijs_toeslag': toeslag,
            'prijs_toeslag_excl_btw': bool(data.get('prijs_toeslag_excl_btw')),
            'prijs_toeslag_btw_percentage': btw_pct,
            'is_borg': bool(data.get('is_borg')),
            'min_tafels': opt_int('min_tafels'),
            'max_tafels': opt_int('max_tafels'),
        }
        return fields

    def standhouder_studio_vraag_save_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        try:
            data = json.loads(request.body)
            vraag_id = data.get('id')
            vraag = None
            if vraag_id:
                vraag = get_object_or_404(StandhouderVraag, pk=vraag_id, evenement=evenement)
            fields = self._parse_vraag_payload(data, evenement, vraag)
            if vraag:
                for key, value in fields.items():
                    if key == 'evenement':
                        continue
                    setattr(vraag, key, value)
                vraag.save()
            else:
                max_volgorde = (
                    StandhouderVraag.objects.filter(evenement=evenement)
                    .order_by('-volgorde')
                    .values_list('volgorde', flat=True)
                    .first()
                )
                if data.get('volgorde') in (None, ''):
                    fields['volgorde'] = (max_volgorde or 0) + 1
                vraag = StandhouderVraag.objects.create(**fields)
            return JsonResponse({'success': True, 'vraag': serialize_standhouder_vraag(vraag)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def standhouder_studio_vraag_delete_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        try:
            data = json.loads(request.body)
            vraag = get_object_or_404(StandhouderVraag, pk=data['id'], evenement=evenement)
            vraag.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def standhouder_studio_vragen_reorder_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        try:
            data = json.loads(request.body)
            order = data.get('order') or []
            for index, vraag_id in enumerate(order):
                StandhouderVraag.objects.filter(pk=vraag_id, evenement=evenement).update(volgorde=index)
            vragen = [
                serialize_standhouder_vraag(v)
                for v in StandhouderVraag.objects.filter(evenement=evenement).order_by("volgorde", "id")
            ]
            return JsonResponse({'success': True, 'vragen': vragen})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def standhouder_studio_copy_save_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
        evenement = get_object_or_404(Evenement, pk=object_id)
        try:
            data = json.loads(request.body)
            if 'standhouder_inbegrepen' in data:
                evenement.standhouder_inbegrepen = data['standhouder_inbegrepen'] or ''
            if 'standhouder_prijzen' in data:
                evenement.standhouder_prijzen = data['standhouder_prijzen'] or ''
            if not evenement.standhouder_zaalplan_actief:
                if data.get('standhouder_prijs_per_tafel') not in (None, ''):
                    evenement.standhouder_prijs_per_tafel = Money(
                        Decimal(str(data['standhouder_prijs_per_tafel'])), 'EUR'
                    )
                if 'standhouder_prijs_excl_btw' in data:
                    evenement.standhouder_prijs_excl_btw = bool(data['standhouder_prijs_excl_btw'])
                if data.get('standhouder_prijs_btw_percentage') not in (None, ''):
                    evenement.standhouder_prijs_btw_percentage = Decimal(
                        str(data['standhouder_prijs_btw_percentage'])
                    )
            if data.get('standhouder_max_tafels') not in (None, ''):
                evenement.standhouder_max_tafels = max(1, int(data['standhouder_max_tafels']))
            evenement.save()
            clear_studio_preview_inschrijving(request, evenement)
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get('q'):
            return qs

        einddatum = request.GET.get('einddatum')
        now = timezone.now()

        if einddatum == 'past':
            return qs.filter(einde_datum__lt=now)
        if einddatum == 'all':
            return qs
        return qs.filter(einde_datum__gte=now)

    def changelist_view(self, request, extra_context=None):
        if 'einddatum' not in request.GET and not request.GET.get('q'):
            query = request.GET.copy()
            query['einddatum'] = 'future'
            return redirect(f'{request.path}?{query.urlencode()}')
        return super().changelist_view(request, extra_context)

    @display(description=_("Titel"), header=True)
    def display_header(self, instance: Evenement):
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


@admin.register(TicketEigenschap)
class TicketEigenschapAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('tekst', )


@admin.register(StandhouderInschrijving)
class StandhouderInschrijvingAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = (
        'bedrijfsnaam', 'naam', 'evenement_link', 'status', 'betaling_status',
        'totaal_bedrag', 'tafels_display', 'aangemaakt_op',
    )
    list_filter = (StandhouderStatusFilter, StandhouderEvenementFilter)
    list_filter_submit = True
    search_fields = (
        'bedrijfsnaam', 'naam', 'email', 'telefoon',
        'btw_of_kvk_nummer', 'bedrijfsnummer',
    )
    readonly_fields = ('aangemaakt_op', 'bijgewerkt_op')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if "status" not in request.GET:
            return qs.exclude(status=StandhouderInschrijvingStatus.CONCEPT)
        return qs

    @display(description=_("Evenement"))
    def evenement_link(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(
            reverse("admin:pokemon_evenement_change", args=(obj.evenement.pk,)),
            obj.evenement.titel,
        ))

    @display(description=_("Tafels"))
    def tafels_display(self, obj):
        return ', '.join(c.display_label for c in obj.gekozen_tafels)

    @display(description=_("Betaling"))
    def betaling_status(self, obj):
        if not obj.payment_id:
            return "—"
        return obj.payment.get_status_display()


@admin.register(GateDevice)
class GateDeviceAdmin(ModelAdmin):
    list_display = (
        "name",
        "online_badge",
        "status_badge",
        "scans_today",
        "api_key_prefix",
        "is_active",
        "last_used_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "api_key_prefix")
    readonly_fields = (
        "api_key_prefix",
        "created_at",
        "last_used_at",
        "last_heartbeat_at",
        "last_status",
        "reported_config",
    )
    actions_list = ["open_monitor"]
    actions_detail = ["open_gate_dashboard"]

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("name", "is_active")
        return (
            "name",
            "is_active",
            "api_key_prefix",
            "created_at",
            "last_used_at",
            "last_heartbeat_at",
            "last_status",
            "reported_config",
        )

    def get_queryset(self, request):
        today_start = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return super().get_queryset(request).annotate(
            today_scans=Count(
                "scan_logs", filter=Q(scan_logs__created_at__gte=today_start)
            )
        )

    @display(description=_("Verbinding"), label=True)
    def online_badge(self, obj):
        return _("Online") if obj.is_online else _("Offline")

    @display(description=_("Status"))
    def status_badge(self, obj):
        return obj.get_last_status_display()

    @display(description=_("Scans vandaag"), ordering="today_scans")
    def scans_today(self, obj):
        return obj.today_scans

    def save_model(self, request, obj, form, change):
        if not change:
            raw_key = GateDevice.generate_api_key()
            obj.set_api_key(raw_key)
            messages.warning(
                request,
                _(
                    "API key (copy now — it will not be shown again): %(key)s"
                )
                % {"key": raw_key},
            )
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'monitor/',
                self.admin_site.admin_view(self.gate_monitor_view),
                name='pokemon_gate_monitor',
            ),
            path(
                'monitor/status/',
                self.admin_site.admin_view(self.gate_monitor_status_view),
                name='pokemon_gate_monitor_status',
            ),
            path(
                '<int:object_id>/dashboard/',
                self.admin_site.admin_view(self.gate_dashboard_view),
                name='pokemon_gate_dashboard',
            ),
            path(
                '<int:object_id>/dashboard/status/',
                self.admin_site.admin_view(self.gate_dashboard_status_view),
                name='pokemon_gate_dashboard_status',
            ),
        ]
        return custom_urls + urls

    @action(description=_("Gate monitor"))
    def open_monitor(self, request):
        return redirect(reverse('admin:pokemon_gate_monitor'))

    @action(description=_("Live dashboard"))
    def open_gate_dashboard(self, request, object_id: int):
        return redirect(reverse('admin:pokemon_gate_dashboard', args=[object_id]))

    def gate_monitor_view(self, request):
        payload = monitor_payload()
        return render(request, 'admin/pokemon/gate_monitor.html', {
            'title': _('Gate monitor'),
            'boot_json': json.dumps({
                'statusUrl': reverse('admin:pokemon_gate_monitor_status'),
                'detailUrlTemplate': reverse(
                    'admin:pokemon_gate_dashboard', args=[0]
                ).replace('/0/', '/__ID__/'),
                'pollMs': 2000,
                **payload,
            }),
        })

    def gate_monitor_status_view(self, request):
        return JsonResponse(monitor_payload(request.GET.get('since_scan_id')))

    def gate_dashboard_view(self, request, object_id):
        device = get_object_or_404(GateDevice, pk=object_id)
        payload = device_payload(device)
        history = self._scan_history(request, device)
        return render(request, 'admin/pokemon/gate_dashboard.html', {
            'title': _('Gate dashboard'),
            'device': device,
            'monitor_url': reverse('admin:pokemon_gate_monitor'),
            'reported_config': (device.reported_config or {}),
            'history': history['page'],
            'history_filters': history['filters'],
            'querystring_base': history['querystring_base'],
            'boot_json': json.dumps({
                'statusUrl': reverse(
                    'admin:pokemon_gate_dashboard_status', args=[object_id]
                ),
                'pollMs': 2000,
                **payload,
            }),
        })

    def gate_dashboard_status_view(self, request, object_id):
        device = get_object_or_404(GateDevice, pk=object_id)
        return JsonResponse(
            device_payload(device, request.GET.get('since_scan_id'))
        )

    def _scan_history(self, request, device):
        """Paginated, filterable scan history for the detail page."""
        outcome = request.GET.get('outcome', '')
        datum = request.GET.get('datum', '')
        zoek = request.GET.get('q', '').strip()

        logs = device.scan_logs.select_related('device')
        if outcome == 'success':
            logs = logs.filter(success=True)
        elif outcome == 'fail':
            logs = logs.filter(success=False)
        if datum:
            parsed = parse_date(datum)
            if parsed:
                logs = logs.filter(created_at__date=parsed)
        if zoek:
            filters = Q(message__icontains=zoek)
            if zoek.isdigit():
                filters |= Q(participant_id_raw=int(zoek))
            logs = logs.filter(filters)

        params = QueryDict(mutable=True)
        for key, value in (('outcome', outcome), ('datum', datum), ('q', zoek)):
            if value:
                params[key] = value
        querystring_base = params.urlencode()

        paginator = Paginator(logs, 50)
        return {
            'page': paginator.get_page(request.GET.get('page')),
            'filters': {'outcome': outcome, 'datum': datum, 'q': zoek},
            'querystring_base': f'{querystring_base}&' if querystring_base else '',
        }


@admin.register(GateScanLog)
class GateScanLogAdmin(ModelAdmin):
    list_display = ("created_at", "device", "outcome", "message", "participant_id_raw")
    list_filter = ("success", ("device", RelatedDropdownFilter))
    search_fields = ("message", "participant_id_raw")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @display(description=_("Resultaat"), label=True)
    def outcome(self, obj):
        return _("Toegelaten") if obj.success else _("Geweigerd")
