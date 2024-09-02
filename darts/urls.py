from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns
from . import views


urlpatterns = i18n_patterns(
    path('', views.index, name="index"),

    path(_('dartschool/'), views.dartschool, name="dartschool"),
    path(_('dartschool/gratis-proefles/'), views.gratis_proefles, name='gratis_proefles'),
    path(_('dartschool/reserveren/'), views.reserveren_dartschool, name='reserveren_dartschool'),
    path(_('dartschool/beurtkaart-kopen/'), views.beurtkaart_kopen, name='beurtkaart_kopen'),
    path(_('dartschool/beurtkaart-kopen/success/'), views.beurtkaart_kopen_success, name='beurtkaart_kopen_success'),
    path(_('dartschool/lidgeld/'), views.dartschool_lidgeld, name='dartschool_lidgeld'),
    path(_('dartschool/lidgeld/success/'), views.dartschool_lidgeld_success, name='dartschool_lidgeld_success'),

    path(_('tornooien/'), views.tornooien, name="tornooien"),
    path(_('tornooien/<slug:slug>/'), views.tornooi, name='tornooi'),
    path(_('tornooien/<slug:slug>/inschrijven/'), views.inschrijven_tornooi, name='inschrijven_tornooi'),
    path(_('tornooien/<slug:slug>/inschrijven/success/'), views.inschrijven_tornooi_success, name='inschrijven_tornooi_success'),

    path(_('teambuildings-en-workshops/'), views.teambuildings_en_workshops, name="teambuildings_en_workshops"),
    path(_('over-ons/'), views.over_ons, name="over_ons"),
    path(_('algemene-voorwaarden/'), views.algemene_voorwaarden, name="algemene_voorwaarden"),
    path(_('reglement-tornooien/'), views.reglement_tornooien, name="reglement_tornooien"),
    path(_('disclaimer/'), views.disclaimer, name="disclaimer"),
    path(_('contact/'), views.contact, name='contact'),
    path(_('sponsors/'), views.sponsors, name='sponsors'),

    path(_('darts/scanner/'), views.scanner),
    path('mollie-webhook/', views.mollie_webhook),
    path('cal-webhook/', views.cal_webhook),

    path('leerling/<int:code>/', views.leerling),
    path('code/<int:code>/', views.code_bestaat, name="code_bestaat"),

    path('admin/', admin.site.urls),

    path('i18n/', include('django.conf.urls.i18n')),
)