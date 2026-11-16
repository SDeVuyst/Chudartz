from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Evenement


class _BaseSitemap(Sitemap):
    protocol = "https"
    i18n = True
    alternates = True
    x_default = True


class StaticViewSitemap(_BaseSitemap):
    changefreq = "monthly"

    PRIORITIES = {
        "index": 1.0,
        "evenementen": 0.9,
    }

    def items(self):
        return [
            "index",
            "evenementen",
            "over_ons",
            "ons_team",
            "partners",
            "sponsors",
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PRIORITIES.get(item, 0.6)


class EvenementSitemap(_BaseSitemap):
    changefreq = "weekly"

    def items(self):
        return Evenement.objects.filter(toon_op_site=True).order_by("-start_datum")

    def location(self, evenement):
        return reverse("evenement", kwargs={"slug": evenement.slug})

    def priority(self, evenement):
        return 0.8 if evenement.is_in_future else 0.5


sitemaps = {
    "pages": StaticViewSitemap,
    "evenementen": EvenementSitemap,
}
