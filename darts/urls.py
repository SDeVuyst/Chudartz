from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns
from . import views


urlpatterns = i18n_patterns(
    path('', views.index, name="index"),

    path(_('trainers/'), views.trainers, name="trainers"),

    path(_('dartschool/'), views.dartschool, name="dartschool"),
    path(_('dartschool/locaties/'), views.locaties, name="locaties"),
    path(_('dartschool/locaties/<slug:slug>/'), views.locatie_detail, name="locatie_detail"),
    path(_('dartschool/leagues/'), views.leagues, name="leagues"),
    path(_('dartschool/leagues/<slug:slug>/'), views.league_detail, name="league_detail"),
    path(_('dartschool/meer-info/'), views.dartschool_meer_info, name="dartschool_meer_info"),    
    path(_('dartschool/aanbod/'), views.dartschool_aanbod, name="dartschool_aanbod"),    
    path(_('dartschool/werkwijze/'), views.dartschool_werkwijze, name="dartschool_werkwijze"),    
    path(_('dartschool/gratis-proefles/'), views.gratis_proefles, name='gratis_proefles'),
    path(_('dartschool/reserveren/'), views.reserveren_dartschool, name='reserveren_dartschool'),
    path(_('dartschool/beurtenkaart-kopen/'), views.beurtkaart_kopen, name='beurtkaart_kopen'),
    path(_('dartschool/beurtenkaart-kopen/success/'), views.beurtkaart_kopen_success, name='beurtkaart_kopen_success'),
    path(_('dartschool/lidgeld/'), views.dartschool_lidgeld, name='dartschool_lidgeld'),
    path(_('dartschool/lidgeld/success/'), views.dartschool_lidgeld_success, name='dartschool_lidgeld_success'),

    path(_('dartskampen/'), views.dartskampen, name="dartskampen"),
    path(_('dartskampen/doelen/'), views.doelen, name="doelen"),
    path(_('dartskampen/<slug:slug>/'), views.dartskamp, name='dartskamp'),
    path(_('dartskampen/<slug:slug>/inschrijven/'), views.inschrijven_dartskamp, name='inschrijven_dartskamp'),
    path(_('dartskampen/<slug:slug>/inschrijven/overzicht/'), views.inschrijven_dartskamp_overzicht, name='inschrijven_dartskamp_overzicht'),
    path(_('dartskampen/<slug:slug>/inschrijven/betalen/'), views.inschrijven_dartskamp_betalen, name='inschrijven_dartskamp_betalen'),
    path(_('dartskampen/<slug:slug>/inschrijven/success/'), views.inschrijven_dartskamp_success, name='inschrijven_dartskamp_success'),
    path(_('dartskampen/resultaten'), views.resultaten, name="resultaten"),
    path(_('dartskampen/<slug:slug>/resultaat'), views.dartskamp_resultaat, name='dartskamp_resultaat'),
    
    path(_('priveles'), views.priveles, name='priveles'),

    path(_('workshops/'), views.workshops, name="workshops"),
    path(_('over-ons/'), views.over_ons, name="over_ons"),
    path(_('algemene-voorwaarden/'), views.algemene_voorwaarden, name="algemene_voorwaarden"),
    path(_('privacybeleid/'), views.privacybeleid, name="privacybeleid"),
    path(_('reglement-dartskampen/'), views.reglement_dartskampen, name="reglement_dartskampen"),
    path(_('sponsor-worden/'), views.sponsor_worden, name="sponsor_worden"),
    path(_('disclaimer/'), views.disclaimer, name="disclaimer"),
    path(_('contact/'), views.contact, name='contact'),
    path(_('sponsors/'), views.sponsors, name='sponsors'),
    path(_('faq/'), views.faq, name='faq'),

    path('mollie-webhook/', views.mollie_webhook),
    path('cal-webhook/', views.cal_webhook),

    path('leerling/<int:code>/', views.leerling),
    path('code/<int:code>/', views.code_bestaat, name="code_bestaat"),

    path('admin/', admin.site.urls),

    path('i18n/', include('django.conf.urls.i18n')),
)

handler404 = 'darts.views.error_404'
handler500 = 'darts.views.error_500'
