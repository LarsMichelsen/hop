"""Tests for theme resolution."""

import pytest

from hop.theme import DEFAULT_THEME, pick_terminal_fallback, resolve_theme, toggle_dark_light


@pytest.mark.parametrize(
    "setting,expected",
    [
        pytest.param("dark", "textual-dark", id="dark alias"),
        pytest.param("light", "textual-light", id="light alias"),
        pytest.param("textual-dark", "textual-dark", id="explicit dark"),
        pytest.param("textual-light", "textual-light", id="explicit light"),
        pytest.param("nord", "nord", id="named theme"),
        pytest.param("dracula", "dracula", id="named theme dracula"),
    ],
)
def test_resolve_theme_uses_setting_when_not_auto(setting: str, expected: str) -> None:
    assert resolve_theme(setting, env={}) == expected


def test_resolve_theme_falls_back_to_default_for_unknown_setting() -> None:
    assert resolve_theme("does-not-exist", env={}) == DEFAULT_THEME


def test_resolve_theme_auto_with_empty_env_returns_default() -> None:
    assert resolve_theme("auto", env={}) == DEFAULT_THEME


def test_resolve_theme_auto_honours_hop_theme_env_alias() -> None:
    assert resolve_theme("auto", env={"HOP_THEME": "light"}) == "textual-light"


def test_resolve_theme_auto_honours_hop_theme_env_explicit_name() -> None:
    assert resolve_theme("auto", env={"HOP_THEME": "nord"}) == "nord"


def test_resolve_theme_auto_ignores_blank_hop_theme_env() -> None:
    assert resolve_theme("auto", env={"HOP_THEME": "   "}) == DEFAULT_THEME


def test_resolve_theme_auto_falls_back_when_hop_theme_env_unknown() -> None:
    assert resolve_theme("auto", env={"HOP_THEME": "bogus"}) == DEFAULT_THEME


def test_toggle_dark_light_flips_dark_to_light() -> None:
    assert toggle_dark_light("textual-dark") == "textual-light"


def test_toggle_dark_light_flips_anything_else_back_to_dark() -> None:
    assert toggle_dark_light("textual-light") == "textual-dark"
    assert toggle_dark_light("nord") == "textual-dark"


def test_pick_terminal_fallback_prefers_ansi_dark_when_available() -> None:
    assert pick_terminal_fallback(frozenset({"ansi-dark", "textual-ansi", "textual-dark"})) == (
        "ansi-dark"
    )


def test_pick_terminal_fallback_falls_back_to_textual_ansi_on_older_textual() -> None:
    assert pick_terminal_fallback(frozenset({"textual-ansi", "textual-dark"})) == "textual-ansi"


def test_pick_terminal_fallback_returns_textual_dark_as_last_resort() -> None:
    assert pick_terminal_fallback(frozenset({"textual-dark", "nord"})) == "textual-dark"


def test_pick_terminal_fallback_returns_textual_dark_when_nothing_matches() -> None:
    assert pick_terminal_fallback(frozenset()) == "textual-dark"
