import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from hop.theme import is_known_theme


@dataclass
class Config:
    branch_prefixes: dict[str, str]
    default_branch_prefix: str
    theme: str = "auto"


class ConfigError(RuntimeError):
    """The config file exists but cannot be read, parsed, or used."""


def get_config_path() -> Path:
    return Path.home() / ".config" / "hop" / "config.toml"


def get_example_config() -> str:
    """Return the bundled example config that ships inside the package."""
    return (files("hop") / "config.toml.example").read_text(encoding="utf-8")


def install_example_config(config_path: Path | None = None, *, force: bool = False) -> Path:
    """Write the bundled example config to ``config_path``.

    Refuses to clobber an existing file unless ``force`` is set, raising
    ``FileExistsError`` so callers can surface a clear message.
    """
    if config_path is None:
        config_path = get_config_path()

    if config_path.exists() and not force:
        raise FileExistsError(config_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(get_example_config(), encoding="utf-8")
    return config_path


def load_config(config_path: Path | None = None) -> Config:
    """Load the user config; a missing file yields the defaults.

    A file that exists but cannot be read, parsed, or holds values of the
    wrong type raises ConfigError instead: silently falling back to defaults
    would disable the user's settings without any hint that a typo did it.
    """
    if config_path is None:
        config_path = get_config_path()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return Config(branch_prefixes={}, default_branch_prefix="")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid config {config_path}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Could not read config {config_path}: {e}") from e

    branch_prefixes: dict[str, str] = {}
    for name, prefix in _table(data, "branch_prefixes", config_path).items():
        if not isinstance(prefix, str):
            raise ConfigError(
                f"Invalid config {config_path}: [branch_prefixes] {name} must be a string"
            )
        branch_prefixes[name] = prefix

    theme = _string(_table(data, "ui", config_path), "ui", "theme", "auto", config_path)
    if theme != "auto" and not is_known_theme(theme):
        raise ConfigError(f"Invalid config {config_path}: unknown theme {theme!r}")

    return Config(
        branch_prefixes=branch_prefixes,
        default_branch_prefix=_string(
            _table(data, "defaults", config_path), "defaults", "branch_prefix", "", config_path
        ),
        theme=theme,
    )


def _table(data: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    section = data.get(key, {})
    if not isinstance(section, dict):
        raise ConfigError(f"Invalid config {path}: [{key}] must be a table")
    # tomllib guarantees string keys; isinstance can only narrow to dict[Unknown, Unknown].
    return cast(dict[str, Any], section)


def _string(section: dict[str, Any], section_name: str, key: str, default: str, path: Path) -> str:
    value = section.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"Invalid config {path}: [{section_name}] {key} must be a string")
    return value


def get_prefix_for_branch(branch_name: str, config: Config) -> str:
    return config.branch_prefixes.get(branch_name, config.default_branch_prefix)
