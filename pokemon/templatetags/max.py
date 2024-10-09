from django import template

register = template.Library()

@register.filter
def max_value(value, arg):
    """Returns the minimum of value and arg"""
    return min(value, arg)