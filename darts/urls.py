from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns
from . import views


urlpatterns = i18n_patterns(
    path('', views.index, name="index"),

    path(_('dartschool/'), views.dartschool, name="dartschool"),
    path(_('dartschool/meer-info/'), views.dartschool_meer_info, name="dartschool_meer_info"),    
    path(_('dartschool/werkwijze/'), views.dartschool_werkwijze, name="dartschool_werkwijze"),    
    path(_('dartschool/gratis-proefles/'), views.gratis_proefles, name='gratis_proefles'),
    path(_('dartschool/reserveren/'), views.reserveren_dartschool, name='reserveren_dartschool'),
    path(_('dartschool/beurtenkaart-kopen/'), views.beurtkaart_kopen, name='beurtkaart_kopen'),
    path(_('dartschool/beurtenkaart-kopen/success/'), views.beurtkaart_kopen_success, name='beurtkaart_kopen_success'),
    path(_('dartschool/lidgeld/'), views.dartschool_lidgeld, name='dartschool_lidgeld'),
    path(_('dartschool/lidgeld/success/'), views.dartschool_lidgeld_success, name='dartschool_lidgeld_success'),

    path(_('toernooien/'), views.toernooien, name="toernooien"),
    path(_('toernooien/<slug:slug>/'), views.toernooi, name='toernooi'),
    path(_('toernooien/<slug:slug>/inschrijven/'), views.inschrijven_toernooi, name='inschrijven_toernooi'),
    path(_('toernooien/<slug:slug>/inschrijven/success/'), views.inschrijven_toernooi_success, name='inschrijven_toernooi_success'),
    path(_('toernooien/resultaten'), views.resultaten, name="resultaten"),
    path(_('toernooien/<slug:slug>/resultaat'), views.toernooi_resultaat, name='toernooi_resultaat'),
    path("darts/set-attendance/", views.set_attendance),
    
    path(_('priveles'), views.priveles, name='priveles'),


    path(_('teambuildings-en-workshops/'), views.teambuildings_en_workshops, name="teambuildings_en_workshops"),
    path(_('over-ons/'), views.over_ons, name="over_ons"),
    path(_('algemene-voorwaarden/'), views.algemene_voorwaarden, name="algemene_voorwaarden"),
    path(_('privacybeleid/'), views.privacybeleid, name="privacybeleid"),
    path(_('reglement-toernooien/'), views.reglement_toernooien, name="reglement_toernooien"),
    path(_('disclaimer/'), views.disclaimer, name="disclaimer"),
    path(_('contact/'), views.contact, name='contact'),
    path(_('sponsors/'), views.sponsors, name='sponsors'),
    path(_('faq/'), views.faq, name='faq'),

    path(_('darts/scanner/'), views.scanner),
    path('mollie-webhook/', views.mollie_webhook),
    path('cal-webhook/', views.cal_webhook),

    path('leerling/<int:code>/', views.leerling),
    path('code/<int:code>/', views.code_bestaat, name="code_bestaat"),

    path('admin/', admin.site.urls),

    path('i18n/', include('django.conf.urls.i18n')),
)