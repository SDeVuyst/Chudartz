from django import template

register = template.Library()

@register.filter
def has_to_show_nieuws_index(nieuws):
    return any(artikel.active for artikel in nieuws)