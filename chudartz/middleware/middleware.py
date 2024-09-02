from django.http import HttpResponseNotFound

class DomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        
        if host == 'chudartz.com':
            request.urlconf = 'darts.urls'
        elif host == 'chudartz-collectibles.com':
            request.urlconf = 'pokemon.urls'
        else:
            return HttpResponseNotFound('Domain not recognized')
        
        response = self.get_response(request)
        return response
