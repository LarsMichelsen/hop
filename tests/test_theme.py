"""Tests for theme resolution."""

import pytest

from hop.theme import DEFAULT_THEME, next_theme, pick_terminal_fallback, resolve_theme


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


def test_next_theme_toggles_within_the_default_dark_light_pair() -> None:
    assert next_theme("textual-dark", home="textual-dark") == "textual-light"
    assert next_theme("textual-light", home="textual-dark") == "textual-dark"


@pytest.mark.parametrize(
    "home,counterpart",
    [
        pytest.param("ansi-dark", "ansi-light", id="ansi"),
        pytest.param("catppuccin-mocha", "catppuccin-latte", id="catppuccin"),
    ],
)
def test_next_theme_toggles_a_paired_home_theme_both_ways(home: str, counterpart: str) -> None:
    assert next_theme(home, home=home) == counterpart
    assert next_theme(counterpart, home=home) == home


def test_next_theme_cycles_an_unpaired_home_theme_back_to_itself() -> None:
    assert next_theme("nord", home="nord") == "textual-dark"
    assert next_theme("textual-dark", home="nord") == "textual-light"
    assert next_theme("textual-light", home="nord") == "nord"


def test_next_theme_recovers_home_when_current_is_outside_the_cycle() -> None:
    assert next_theme("dracula", home="nord") == "nord"


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
