"""Shared TCG-card dicts for the Ons Team page and the admin live preview."""

from __future__ import annotations

import base64
from typing import Any

from django.db.models import QuerySet

from pokemon.models import TeamKaartType, TeamLid, TeamSocialPlatform

KAART_TYPES = list(TeamKaartType.values)


def split_over(tekst: str) -> list[str]:
    return [p.strip() for p in (tekst or "").split("\n\n") if p.strip()]


def parse_kost(waarde: str) -> list[str]:
    return [k for k in (s.strip() for s in (waarde or "").split(",")) if k in KAART_TYPES]


def _foto_url(lid: TeamLid) -> str:
    if not lid.foto:
        return ""
    try:
        return lid.foto.url
    except ValueError:
        return ""


def _social_href(platform: str, url: str) -> str:
    if platform == TeamSocialPlatform.EMAIL and url and not url.startswith("mailto:"):
        return f"mailto:{url}"
    return url


def lid_to_kaart(lid: TeamLid, *, nummer: str, totaal: str) -> dict[str, Any]:
    ability = None
    if lid.ability_naam or lid.ability_tekst:
        ability = {"naam": lid.ability_naam, "tekst": lid.ability_tekst}

    return {
        "slug": lid.slug,
        "nummer": nummer,
        "naam": lid.naam,
        "rol": lid.rol,
        "type": lid.kaart_type,
        "hp": lid.hp,
        "fase": lid.fase or "Basis Teamlid",
        "afbeelding": _foto_url(lid),
        "soort": lid.soort,
        "ability": ability,
        "aanvallen": [
            {
                "naam": aanval.naam,
                "kost": aanval.kost_lijst,
                "schade": aanval.schade,
                "tekst": aanval.tekst,
            }
            for aanval in lid.aanvallen.all()
        ],
        "zwakte": lid.zwakte or None,
        "zwakte_waarde": lid.zwakte_waarde or "×2",
        "resistentie": lid.resistentie or None,
        "resistentie_waarde": lid.resistentie_waarde or "-30",
        "terugtrek": int(lid.terugtrek or 0),
        "bio": lid.bio,
        "flavor": lid.flavor,
        "illustrator": lid.illustrator or "ChudartZ",
        "slab_label": lid.slab_label or "GEM MT",
        "slab_grade": lid.slab_grade or "10",
        "over": split_over(lid.over),
        "quote": lid.quote,
        "weetjes": [
            {"label": weetje.label, "waarde": weetje.waarde}
            for weetje in lid.weetjes.all()
        ],
        "socials": [
            {"icoon": social.platform, "url": social.href}
            for social in lid.socials.all()
        ],
    }


def team_voor_site() -> QuerySet[TeamLid]:
    return (
        TeamLid.objects.filter(zichtbaar=True, groep__zichtbaar=True)
        .select_related("groep")
        .prefetch_related("aanvallen", "weetjes", "socials")
    )


def groepen_voor_site() -> list[dict[str, Any]]:
    leden = list(team_voor_site())
    totaal = f"{len(leden):03d}"
    groepen: list[dict[str, Any]] = []
    index: dict[int, dict[str, Any]] = {}

    for i, lid in enumerate(leden, start=1):
        groep = index.get(lid.groep_id)
        if groep is None:
            groep = {"groep": lid.groep, "leden": []}
            index[lid.groep_id] = groep
            groepen.append(groep)
        groep["leden"].append(lid.as_kaart(nummer=f"{i:03d}", totaal=totaal))

    return groepen


def _int(waarde, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    try:
        n = int(waarde)
    except (TypeError, ValueError):
        return default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _file_data_uri(uploaded) -> str:
    raw = uploaded.read()
    try:
        uploaded.seek(0)
    except Exception:
        pass
    if not raw:
        return ""
    content_type = getattr(uploaded, "content_type", "") or "image/jpeg"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _formset_prefix(post, *prefixes: str) -> str:
    for prefix in prefixes:
        if f"{prefix}-TOTAL_FORMS" in post:
            return prefix
    return prefixes[0]


def _formset_indexes(post, *prefixes: str) -> list[int]:
    prefix = _formset_prefix(post, *prefixes)
    try:
        total = int(post.get(f"{prefix}-TOTAL_FORMS") or 0)
    except (TypeError, ValueError):
        total = 0
    indexes = []
    for i in range(total):
        if post.get(f"{prefix}-{i}-DELETE"):
            continue
        indexes.append(i)
    return indexes, prefix


def _kaart_nummer(lid: TeamLid | None) -> tuple[str, str]:
    zichtbaar = list(
        TeamLid.objects.filter(zichtbaar=True, groep__zichtbaar=True).values_list("pk", flat=True)
    )
    if lid and lid.pk in zichtbaar:
        nummer = zichtbaar.index(lid.pk) + 1
        totaal = len(zichtbaar)
    else:
        nummer = len(zichtbaar) + 1
        totaal = len(zichtbaar) + 1
    return f"{nummer:03d}", f"{totaal:03d}"


def kaart_van_preview(post, files, lid: TeamLid | None = None) -> dict[str, Any]:
    nummer, totaal = _kaart_nummer(lid)

    afbeelding = _foto_url(lid) if lid else ""
    if post.get("foto-clear"):
        afbeelding = ""
    uploaded = files.get("foto") if files is not None else None
    if uploaded:
        afbeelding = _file_data_uri(uploaded) or afbeelding

    ability_naam = (post.get("ability_naam") or "").strip()
    ability_tekst = (post.get("ability_tekst") or "").strip()
    ability = None
    if ability_naam or ability_tekst:
        ability = {"naam": ability_naam, "tekst": ability_tekst}

    aanvallen = []
    aanval_indexes, aanval_prefix = _formset_indexes(post, "aanvallen", "teamlidaanval_set")
    for i in aanval_indexes:
        naam = (post.get(f"{aanval_prefix}-{i}-naam") or "").strip()
        if not naam:
            continue
        aanvallen.append(
            {
                "naam": naam,
                "kost": parse_kost(post.get(f"{aanval_prefix}-{i}-kost") or ""),
                "schade": (post.get(f"{aanval_prefix}-{i}-schade") or "").strip(),
                "tekst": (post.get(f"{aanval_prefix}-{i}-tekst") or "").strip(),
            }
        )

    weetjes = []
    weetje_indexes, weetje_prefix = _formset_indexes(post, "weetjes", "teamlidweetje_set")
    for i in weetje_indexes:
        label = (post.get(f"{weetje_prefix}-{i}-label") or "").strip()
        waarde = (post.get(f"{weetje_prefix}-{i}-waarde") or "").strip()
        if not label and not waarde:
            continue
        weetjes.append({"label": label, "waarde": waarde})

    socials = []
    social_indexes, social_prefix = _formset_indexes(post, "socials", "teamlidsocial_set")
    for i in social_indexes:
        platform = (post.get(f"{social_prefix}-{i}-platform") or "").strip()
        url = (post.get(f"{social_prefix}-{i}-url") or "").strip()
        if not platform or not url:
            continue
        socials.append({"icoon": platform, "url": _social_href(platform, url)})

    kaart_type = post.get("kaart_type") or TeamKaartType.DART
    if kaart_type not in KAART_TYPES:
        kaart_type = TeamKaartType.DART

    zwakte = post.get("zwakte") or ""
    resistentie = post.get("resistentie") or ""

    return {
        "slug": (post.get("slug") or "preview").strip() or "preview",
        "nummer": nummer,
        "naam": (post.get("naam") or "Naam").strip() or "Naam",
        "rol": (post.get("rol") or "").strip(),
        "type": kaart_type,
        "hp": _int(post.get("hp"), 100, lo=0, hi=999),
        "fase": (post.get("fase") or "Basis Teamlid").strip() or "Basis Teamlid",
        "afbeelding": afbeelding,
        "soort": (post.get("soort") or "").strip(),
        "ability": ability,
        "aanvallen": aanvallen,
        "zwakte": zwakte if zwakte in KAART_TYPES else None,
        "zwakte_waarde": (post.get("zwakte_waarde") or "×2").strip() or "×2",
        "resistentie": resistentie if resistentie in KAART_TYPES else None,
        "resistentie_waarde": (post.get("resistentie_waarde") or "-30").strip() or "-30",
        "terugtrek": _int(post.get("terugtrek"), 1, lo=0, hi=5),
        "bio": (post.get("bio") or "").strip(),
        "flavor": (post.get("flavor") or "").strip(),
        "illustrator": (post.get("illustrator") or "ChudartZ").strip() or "ChudartZ",
        "slab_label": (post.get("slab_label") or "GEM MT").strip() or "GEM MT",
        "slab_grade": (post.get("slab_grade") or "10").strip() or "10",
        "over": split_over(post.get("over") or ""),
        "quote": (post.get("quote") or "").strip(),
        "weetjes": weetjes,
        "socials": socials,
        "zichtbaar": post.get("zichtbaar") in ("on", "true", "1", "True"),
        "team_totaal": totaal,
    }
