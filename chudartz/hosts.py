from django_hosts import patterns, host

host_patterns = patterns(
    '',
    host(r'www', 'chudartz.urls', name='www'),
    host(r'pokemon', 'pokemon.urls', name='pokemon'),
)