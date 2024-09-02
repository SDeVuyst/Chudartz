from django_hosts import patterns, host

host_patterns = patterns(
    '',
    host(r'pokemon', 'pokemon.urls', name='pokemon'),
    host(r'', 'darts.urls', name='darts')
)