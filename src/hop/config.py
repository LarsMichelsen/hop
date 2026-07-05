import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass
class Config:
    branch_prefixes: dict[str, str]
    default_branch_prefix: str
    theme: str = "auto"


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
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        return Config(branch_prefixes={}, default_branch_prefix="")

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        branch_prefixes = data.get("branch_prefixes", {})
        default_branch_prefix = data.get("defaults", {}).get("branch_prefix", "")
        theme = data.get("ui", {}).get("theme", "auto")

        return Config(
            branch_prefixes=branch_prefixes,
            default_branch_prefix=default_branch_prefix,
            theme=theme,
        )
    except (tomllib.TOMLDecodeError, OSError):
        return Config(branch_prefixes={}, default_branch_prefix="")


def get_prefix_for_branch(branch_name: str, config: Config) -> str:
    return config.branch_prefixes.get(branch_name, config.default_branch_prefix)
