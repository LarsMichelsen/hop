"""System-level tests: drive main() against a real git repo in tmp_path."""

import subprocess
from pathlib import Path

import pytest

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
        main()

    assert exc.value.code == 1
    assert "Not a git repository" in capsys.readouterr().err


def test_main_exits_with_error_when_repository_has_no_branches(
    empty_git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "No branches" in capsys.readouterr().err
