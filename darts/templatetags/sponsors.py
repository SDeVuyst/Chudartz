from django import template

register = template.Library()

@register.filter
def has_to_show_sponsors_footer(sponsors):
    if not sponsors:
        return False
    return any(sponsor.toon_in_footer for sponsor in sponsors)

@register.filter
def has_to_show_sponsors_index(sponsors):
    if not sponsors:
        return False
    return any(sponsor.toon_op_index for sponsor in sponsors)