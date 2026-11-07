from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

MARKS_DIR = Path(settings.BASE_DIR) / "pokemon" / "static" / "pokemon" / "img" / "marks"
IMAGE_SUFFIXES = {".svg", ".png", ".webp", ".jpg", ".jpeg"}


@register.simple_tag
def mark_assets():
    """Static URLs for every image dropped in pokemon/static/pokemon/img/marks/."""
    if not MARKS_DIR.is_dir():
        return []
    names = sorted(
        path.name
        for path in MARKS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and not path.name.startswith(".")
    )
    return [static(f"pokemon/img/marks/{name}") for name in names]
