import tempfile
from pathlib import Path
from unittest.mock import patch

from hop.config import Config, get_config_path, get_prefix_for_branch, load_config


def test_get_config_path() -> None:
    path = get_config_path()
    assert path == Path.home() / ".config" / "hop" / "config.toml"


def test_load_config_missing_file() -> None:
    with patch("hop.config.get_config_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/config.toml")
        config = load_config()
        assert config.branch_prefixes == {}
        assert config.default_branch_prefix == ""


def test_load_config_valid() -> None:
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


def test_load_config_missing_defaults_section() -> None:
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


def test_load_config_missing_branch_prefixes_section() -> None:
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


def test_load_config_empty_file() -> None:
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


def test_load_config_invalid_toml() -> None:
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


def test_get_prefix_for_branch_found() -> None:
    config = Config(
        branch_prefixes={"main": "feature/", "develop": "dev/"},
        default_branch_prefix="hotfix/",
    )
    assert get_prefix_for_branch("main", config) == "feature/"
    assert get_prefix_for_branch("develop", config) == "dev/"


def test_get_prefix_for_branch_default() -> None:
    config = Config(
        branch_prefixes={"main": "feature/"},
        default_branch_prefix="hotfix/",
    )
    assert get_prefix_for_branch("unknown", config) == "hotfix/"
    assert get_prefix_for_branch("staging", config) == "hotfix/"


def test_get_prefix_for_branch_empty_default() -> None:
    config = Config(
        branch_prefixes={"main": "feature/"},
        default_branch_prefix="",
    )
    assert get_prefix_for_branch("unknown", config) == ""


def test_load_config_with_special_branch_names() -> None:
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
