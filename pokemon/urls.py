from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _
from django.urls import include, path
from . import views

urlpatterns = i18n_patterns(
    path('', views.index, name="index"),
    path(_('contact'), views.contact, name='contact'),

    path('i18n/', include('django.conf.urls.i18n')),
)