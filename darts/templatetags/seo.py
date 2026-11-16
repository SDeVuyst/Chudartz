from django import template
from django.conf import settings
from django.urls import translate_url
from django.utils.html import format_html, format_html_join

from darts.services.kamp_seo import absolute_url

register = template.Library()


@register.simple_tag(takes_context=True)
def seo_links(context, keep_page=False):
    """Canonical + hreflang-links voor de huidige pagina.

    Met keep_page=True blijft ?page=N (N > 1) in de canonical staan, zodat
    gepagineerde overzichten niet allemaal naar pagina 1 canonicaliseren.
    """
    request = context.get("request")
    if request is None:
        return ""

    path = request.path
    query = ""
    if keep_page:
        page = request.GET.get("page", "")
        if page.isdigit() and int(page) > 1:
            query = f"?page={page}"

    alternates = [
        (code, absolute_url(translate_url(path, code)) + query)
        for code, _name in settings.LANGUAGES
    ]
    default_url = absolute_url(translate_url(path, settings.LANGUAGE_CODE)) + query

    canonical = format_html('<link rel="canonical" href="{}">', absolute_url(path) + query)
    links = format_html_join(
        "\n", '<link rel="alternate" hreflang="{}" href="{}">', alternates
    )
    x_default = format_html('<link rel="alternate" hreflang="x-default" href="{}">', default_url)
    return format_html("{}\n{}\n{}", canonical, links, x_default)


@register.simple_tag(takes_context=True)
def canonical_url(context):
    request = context.get("request")
    return absolute_url(request.path) if request is not None else ""


@register.simple_tag
def absolute_static(path):
    from django.templatetags.static import static

    return absolute_url(static(path))
