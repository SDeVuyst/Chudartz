from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _
from django.urls import include, path
from . import views

urlpatterns = i18n_patterns(

    path('admin/', admin.site.urls),
    path('', views.index, name="index"),
    path(_('over-ons'), views.over_ons, name="over_ons"),
    path(_('contact'), views.contact, name='contact'),

    path(_('evenementen'), views.evenementen, name="evenementen"),
    path(_('evenement/<slug:slug>/'), views.evenement, name='evenement'),

    path(_('algemene_voorwaarden/'), views.algemene_voorwaarden, name='algemene_voorwaarden'),
    path(_('privacybeleid/'), views.privacybeleid, name='privacybeleid'),
    path(_('disclaimer/'), views.disclaimer, name='disclaimer'),
    path(_('faq/'), views.faq, name='faq'),

    path('i18n/', include('django.conf.urls.i18n')),
)