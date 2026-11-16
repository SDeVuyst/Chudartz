from django.contrib.sitemaps import Sitemap
from django.db.models import Q
from django.urls import reverse

from .models import Dartskamp


class _BaseSitemap(Sitemap):
    protocol = "https"
    i18n = True
    alternates = True
    x_default = True


class StaticViewSitemap(_BaseSitemap):
    changefreq = "monthly"

    PRIORITIES = {
        "index": 1.0,
        "dartskampen": 0.9,
        "dartschool": 0.9,
    }

    def items(self):
        return [
            "index",
            "dartskampen",
            "resultaten",
            "doelen",
            "dartschool",
            "locaties",
            "leagues",
            "dartschool_meer_info",
            "dartschool_aanbod",
            "dartschool_werkwijze",
            "reserveren_dartschool",
            "beurtkaart_kopen",
            "priveles",
            "workshops",
            "over_ons",
            "trainers",
            "sponsors",
            "sponsor_worden",
            "contact",
            "faq",
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PRIORITIES.get(item, 0.6)


class DartskampSitemap(_BaseSitemap):
    changefreq = "weekly"

    def items(self):
        return Dartskamp.objects.filter(toon_op_site=True).order_by("-start_datum")

    def location(self, kamp):
        return reverse("dartskamp", kwargs={"slug": kamp.slug})

    def priority(self, kamp):
        return 0.8 if kamp.is_in_future else 0.5


class DartskampResultaatSitemap(_BaseSitemap):
    changefreq = "yearly"
    priority = 0.4

    def items(self):
        return (
            Dartskamp.objects.filter(toon_op_site=True)
            .exclude(Q(resultaten__isnull=True) | Q(resultaten__exact=""))
            .order_by("-start_datum")
        )

    def location(self, kamp):
        return reverse("dartskamp_resultaat", kwargs={"slug": kamp.slug})


sitemaps = {
    "pages": StaticViewSitemap,
    "dartskampen": DartskampSitemap,
    "resultaten": DartskampResultaatSitemap,
}
