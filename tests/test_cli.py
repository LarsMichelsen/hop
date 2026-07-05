"""System-level tests: drive main() against a real git repo in tmp_path."""

import subprocess
from pathlib import Path

import pytest

from hop import __version__
from hop.config import get_example_config
from hop.main import main


@pytest.fixture
def empty_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def empty_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_main_exits_with_error_outside_a_git_repository(
    empty_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 1
    assert "Not a git repository" in capsys.readouterr().err


def test_main_exits_with_error_when_repository_has_no_branches(
    empty_git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 1
    assert "No branches" in capsys.readouterr().err


def test_version_flag_prints_version_and_exits_zero(
    empty_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"hop {__version__}"


def test_help_flag_prints_usage_and_exits_zero(
    empty_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    assert "usage: hop" in capsys.readouterr().out


def test_init_config_writes_example_to_default_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    main(["--init-config"])

    written = tmp_path / ".config" / "hop" / "config.toml"
    assert written.read_text(encoding="utf-8") == get_example_config()
    assert "Wrote example config" in capsys.readouterr().out


def test_init_config_refuses_to_overwrite_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    main(["--init-config"])

    with pytest.raises(SystemExit) as exc:
        main(["--init-config"])

    assert exc.value.code == 1
    assert "already exists" in capsys.readouterr().err


def test_init_config_force_overwrites_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    written = tmp_path / ".config" / "hop" / "config.toml"
    written.parent.mkdir(parents=True)
    written.write_text("stale")

    main(["--init-config", "--force"])

    assert written.read_text(encoding="utf-8") == get_example_config()
