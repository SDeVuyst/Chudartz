from django.conf import settings
from django_hosts import patterns, host

host_patterns = patterns(
    '',
    host(r'pokemon', 'pokemon.urls', name='pokemon'),
    host(r'',  settings.ROOT_URLCONF, name='darts')
)