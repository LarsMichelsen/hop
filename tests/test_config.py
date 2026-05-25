import tempfile
from pathlib import Path
from unittest.mock import patch

from hop.config import Config, get_config_path, get_prefix_for_branch, load_config


def test_get_config_path_points_at_xdg_config_hop_dir() -> None:
    path = get_config_path()
    assert path == Path.home() / ".config" / "hop" / "config.toml"


def test_load_config_returns_empty_config_when_file_does_not_exist() -> None:
    with patch("hop.config.get_config_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/config.toml")

        config = load_config()

        assert config.branch_prefixes == {}
        assert config.default_branch_prefix == ""
        assert config.theme == "auto"


def test_load_config_reads_defaults_and_branch_prefixes_from_valid_toml() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[defaults]
branch_prefix = "feat/"

[branch_prefixes]
main = "feature/"
develop = "dev/"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.default_branch_prefix == "feat/"
            assert config.branch_prefixes == {"main": "feature/", "develop": "dev/"}
    finally:
        temp_path.unlink()


def test_load_config_uses_empty_default_prefix_when_defaults_section_is_missing() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[branch_prefixes]
main = "feature/"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.default_branch_prefix == ""
            assert config.branch_prefixes == {"main": "feature/"}
    finally:
        temp_path.unlink()


def test_load_config_uses_empty_branch_prefixes_when_section_is_missing() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[defaults]
branch_prefix = "feat/"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.default_branch_prefix == "feat/"
            assert config.branch_prefixes == {}
    finally:
        temp_path.unlink()


def test_load_config_returns_empty_config_when_file_is_empty() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("")
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.default_branch_prefix == ""
            assert config.branch_prefixes == {}
    finally:
        temp_path.unlink()


def test_load_config_returns_empty_config_when_toml_is_invalid() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("invalid toml content [[[")
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.default_branch_prefix == ""
            assert config.branch_prefixes == {}
    finally:
        temp_path.unlink()


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


def test_load_config_reads_ui_theme_setting() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[ui]
theme = "light"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.theme == "light"
    finally:
        temp_path.unlink()


def test_load_config_defaults_theme_to_auto_when_ui_section_missing() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[defaults]
branch_prefix = "feat/"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.theme == "auto"
    finally:
        temp_path.unlink()


def test_load_config_preserves_quoted_branch_keys_with_special_characters() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(
            """
[branch_prefixes]
"release/v1.0" = "bugfix/"
"feature/new-ui" = "sub/"
"""
        )
        f.flush()
        temp_path = Path(f.name)

    try:
        with patch("hop.config.get_config_path") as mock_path:
            mock_path.return_value = temp_path

            config = load_config()

            assert config.branch_prefixes == {
                "release/v1.0": "bugfix/",
                "feature/new-ui": "sub/",
            }
    finally:
        temp_path.unlink()
