"""Template context processors for the core app."""

from __future__ import annotations

from django.http import HttpRequest

VALID_THEMES = {"light", "dark", "auto"}
THEME_COOKIE = "controle_interno_theme"
DEFAULT_THEME = "auto"


def theme(request: HttpRequest) -> dict[str, str]:
    """Inject the current theme preference into every template."""

    raw = request.COOKIES.get(THEME_COOKIE, DEFAULT_THEME)
    current = raw if raw in VALID_THEMES else DEFAULT_THEME
    return {"theme": current}
