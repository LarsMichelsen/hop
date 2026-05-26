"""Resolve a user theme preference to a concrete Textual theme name."""

from collections.abc import Mapping

DEFAULT_THEME = "textual-ansi"

# Textual ships these themes; see App.available_themes.
VALID_THEMES: frozenset[str] = frozenset(
    {
        "textual-dark",
        "textual-light",
        "textual-ansi",
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
      2. ``DEFAULT_THEME`` (terminal-ansi, adapts to the terminal palette)

    A non-"auto" ``setting`` is used directly (with alias resolution); unknown
    values fall back to ``DEFAULT_THEME``.
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
