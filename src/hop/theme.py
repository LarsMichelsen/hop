"""Resolve a user theme preference to a concrete Textual theme name."""

from collections.abc import Mapping

DEFAULT_THEME = "ansi-dark"

# Themes that adapt to the terminal's ANSI palette. Textual renamed
# "textual-ansi" to "ansi-dark"/"ansi-light" in 8.2.5; we list both so users
# on either side of that change get a terminal-adapting default.
TERMINAL_THEME_FALLBACKS: tuple[str, ...] = ("ansi-dark", "textual-ansi", "textual-dark")

# Theme names we accept in config; not all are registered on every Textual
# version, so the UI validates against App.available_themes at mount time.
VALID_THEMES: frozenset[str] = frozenset(
    {
        "textual-dark",
        "textual-light",
        "textual-ansi",
        "ansi-dark",
        "ansi-light",
        "nord",
        "gruvbox",
        "dracula",
        "monokai",
        "tokyo-night",
        "flexoki",
        "catppuccin-mocha",
        "catppuccin-latte",
        "solarized-light",
    }
)

ALIASES: dict[str, str] = {
    "dark": "textual-dark",
    "light": "textual-light",
}


def _normalize(value: str) -> str | None:
    name = ALIASES.get(value, value)
    return name if name in VALID_THEMES else None


def resolve_theme(setting: str, env: Mapping[str, str]) -> str:
    """Resolve a config setting + environment into a Textual theme name.

    Priority (only when ``setting == "auto"``):
      1. ``HOP_THEME`` env var override
      2. ``DEFAULT_THEME`` (ansi-dark, adapts to the terminal palette)

    A non-"auto" ``setting`` is used directly (with alias resolution); unknown
    values fall back to ``DEFAULT_THEME``. The caller must still verify the
    returned name against ``App.available_themes`` (see
    ``pick_terminal_fallback``) because Textual's catalog changes by version.
    """
    if setting != "auto":
        return _normalize(setting) or DEFAULT_THEME

    override = env.get("HOP_THEME", "").strip()
    if override:
        return _normalize(override) or DEFAULT_THEME

    return DEFAULT_THEME


def toggle_dark_light(current: str) -> str:
    """Flip between dark and light variants of the Textual default theme."""
    return "textual-light" if current == "textual-dark" else "textual-dark"


def pick_terminal_fallback(available: frozenset[str]) -> str:
    """Pick the best terminal-adapting theme that is registered.

    Walks ``TERMINAL_THEME_FALLBACKS`` in order. Returns ``"textual-dark"`` as
    the last resort; Textual ships it in every released version.
    """
    for name in TERMINAL_THEME_FALLBACKS:
        if name in available:
            return name
    return "textual-dark"
