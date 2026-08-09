from pathlib import Path

import pytest

from hop.config import (
    Config,
    ConfigError,
    get_config_path,
    get_example_config,
    get_prefix_for_branch,
    install_example_config,
    load_config,
)


def test_get_config_path_points_at_xdg_config_hop_dir() -> None:
    path = get_config_path()
    assert path == Path.home() / ".config" / "hop" / "config.toml"


def test_load_config_returns_empty_config_when_file_does_not_exist(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.toml")

    assert config.branch_prefixes == {}
    assert config.default_branch_prefix == ""
    assert config.theme == "auto"


def test_load_config_reads_defaults_and_branch_prefixes_from_valid_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
branch_prefix = "feat/"

[branch_prefixes]
main = "feature/"
develop = "dev/"
"""
    )

    config = load_config(config_file)

    assert config.default_branch_prefix == "feat/"
    assert config.branch_prefixes == {"main": "feature/", "develop": "dev/"}


def test_load_config_uses_empty_default_prefix_when_defaults_section_is_missing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[branch_prefixes]
main = "feature/"
"""
    )

    config = load_config(config_file)

    assert config.default_branch_prefix == ""
    assert config.branch_prefixes == {"main": "feature/"}


def test_load_config_uses_empty_branch_prefixes_when_section_is_missing(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
branch_prefix = "feat/"
"""
    )

    config = load_config(config_file)

    assert config.default_branch_prefix == "feat/"
    assert config.branch_prefixes == {}


def test_load_config_uses_conventional_base_branches_by_default(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.toml")

    assert config.base_branches == ("main", "master", "develop", "development")


def test_load_config_reads_base_branches_in_configured_order(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
base_branches = ["2.5.0", "2.4.0", "master"]
"""
    )

    config = load_config(config_file)

    assert config.base_branches == ("2.5.0", "2.4.0", "master")


def test_load_config_rejects_base_branches_that_is_not_an_array(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
base_branches = "main"
"""
    )

    with pytest.raises(ConfigError, match=r"base_branches must be an array of strings"):
        load_config(config_file)


def test_load_config_rejects_base_branches_with_a_non_string_entry(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
base_branches = ["main", 5]
"""
    )

    with pytest.raises(ConfigError, match=r"base_branches must be an array of strings"):
        load_config(config_file)


def test_load_config_returns_empty_config_when_file_is_empty(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    config = load_config(config_file)

    assert config.default_branch_prefix == ""
    assert config.branch_prefixes == {}


def test_load_config_rejects_invalid_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("invalid toml content [[[")

    with pytest.raises(ConfigError, match="Invalid config"):
        load_config(config_file)


def test_load_config_rejects_an_unreadable_config_file(tmp_path: Path) -> None:
    # A directory at the config path triggers the same OSError path as a
    # permission problem, portably.
    with pytest.raises(ConfigError, match="Could not read config"):
        load_config(tmp_path)


def test_load_config_rejects_a_section_that_is_not_a_table(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text('defaults = "feat/"')

    with pytest.raises(ConfigError, match=r"\[defaults\] must be a table"):
        load_config(config_file)


def test_load_config_explains_how_to_quote_a_dotted_branch_name(tmp_path: Path) -> None:
    # Unquoted, TOML reads `2.5.0` as nested tables {"2": {"5": {"0": ...}}};
    # the error must reconstruct the intended name and show the quoted fix.
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[branch_prefixes]
master = "sandbox/lm/3.0/"
2.5.0 = "sandbox/lm/2.5/"
"""
    )

    with pytest.raises(ConfigError, match=r'quote the branch name: "2\.5\.0"'):
        load_config(config_file)


def test_load_config_rejects_a_non_string_branch_prefix(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[branch_prefixes]
main = 5
"""
    )

    with pytest.raises(ConfigError, match="main must be a string"):
        load_config(config_file)


def test_load_config_rejects_a_non_string_theme(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[ui]
theme = 5
"""
    )

    with pytest.raises(ConfigError, match="theme must be a string"):
        load_config(config_file)


def test_load_config_rejects_an_unknown_theme_name(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[ui]
theme = "nrod"
"""
    )

    with pytest.raises(ConfigError, match="unknown theme 'nrod'"):
        load_config(config_file)


def test_get_prefix_for_branch_returns_configured_prefix_when_branch_is_present() -> None:
    config = Config(
        branch_prefixes={"main": "feature/", "develop": "dev/"},
        default_branch_prefix="hotfix/",
    )
    assert get_prefix_for_branch("main", config) == "feature/"
    assert get_prefix_for_branch("develop", config) == "dev/"


def test_get_prefix_for_branch_returns_default_when_branch_is_absent() -> None:
    config = Config(
        branch_prefixes={"main": "feature/"},
        default_branch_prefix="hotfix/",
    )
    assert get_prefix_for_branch("unknown", config) == "hotfix/"
    assert get_prefix_for_branch("staging", config) == "hotfix/"


def test_get_prefix_for_branch_returns_empty_string_when_default_is_empty() -> None:
    config = Config(
        branch_prefixes={"main": "feature/"},
        default_branch_prefix="",
    )
    assert get_prefix_for_branch("unknown", config) == ""


def test_load_config_reads_ui_theme_setting(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[ui]
theme = "light"
"""
    )

    config = load_config(config_file)

    assert config.theme == "light"


def test_load_config_defaults_theme_to_auto_when_ui_section_missing(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[defaults]
branch_prefix = "feat/"
"""
    )

    config = load_config(config_file)

    assert config.theme == "auto"


def test_get_example_config_contains_documented_sections() -> None:
    text = get_example_config()

    assert "[ui]" in text
    assert "[branch_prefixes]" in text
    assert 'theme = "auto"' in text


def test_install_example_config_writes_bundled_example_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "config.toml"

    written = install_example_config(target)

    assert written == target
    assert target.read_text(encoding="utf-8") == get_example_config()


def test_install_example_config_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("keep me")

    with pytest.raises(FileExistsError):
        install_example_config(target)

    assert target.read_text() == "keep me"


def test_install_example_config_overwrites_with_force(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old contents")

    install_example_config(target, force=True)

    assert target.read_text(encoding="utf-8") == get_example_config()


def test_load_config_preserves_quoted_branch_keys_with_special_characters(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[branch_prefixes]
"release/v1.0" = "bugfix/"
"feature/new-ui" = "sub/"
"""
    )

    config = load_config(config_file)

    assert config.branch_prefixes == {
        "release/v1.0": "bugfix/",
        "feature/new-ui": "sub/",
    }
