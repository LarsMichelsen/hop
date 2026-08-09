"""Tests for main module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from hop.git import BranchInfo
from hop.main import main
from tests.fakes import FakeGitClient


def _client_with_a_branch() -> FakeGitClient:
    return FakeGitClient(
        branches=[
            BranchInfo(
                name="main",
                creator_date=datetime(2025, 1, 1),
                last_commit_message="initial",
            )
        ]
    )


def test_main_exits_when_the_config_file_is_broken(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text("invalid toml [[[")
    monkeypatch.setattr("hop.config.get_config_path", lambda: config_file)

    with pytest.raises(SystemExit) as exc_info:
        main([], client=_client_with_a_branch())

    assert exc_info.value.code == 1
    assert "Invalid config" in capsys.readouterr().err


def test_main_exits_when_branch_listing_raises_runtime_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeGitClient()
    client.get_branches_error = RuntimeError("Git error")

    with pytest.raises(SystemExit) as exc_info:
        main([], client=client)

    assert exc_info.value.code == 1
    assert "Git error" in capsys.readouterr().err


def test_main_exits_when_interactive_ui_raises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("hop.main.run_interactive_ui", side_effect=Exception("UI error")),
        pytest.raises(SystemExit) as exc_info,
    ):
        main([], client=_client_with_a_branch())

    assert exc_info.value.code == 1
    assert "UI error" in capsys.readouterr().err


def test_main_writes_the_jump_target_to_the_cd_file(tmp_path: Path) -> None:
    cd_file = tmp_path / "cd-target"

    with patch("hop.main.run_interactive_ui", return_value="/repos/wt-feature") as run_ui:
        main(["--cd-file", str(cd_file)], client=_client_with_a_branch())

    assert run_ui.call_args.kwargs["jump_enabled"] is True
    assert cd_file.read_text() == "/repos/wt-feature"


def test_main_does_not_touch_the_cd_file_when_the_user_just_quits(tmp_path: Path) -> None:
    cd_file = tmp_path / "cd-target"

    with patch("hop.main.run_interactive_ui", return_value=None):
        main(["--cd-file", str(cd_file)], client=_client_with_a_branch())

    assert not cd_file.exists()


def test_main_disables_jumping_without_a_cd_file() -> None:
    with patch("hop.main.run_interactive_ui", return_value=None) as run_ui:
        main([], client=_client_with_a_branch())

    assert run_ui.call_args.kwargs["jump_enabled"] is False


def test_main_exits_with_error_when_the_cd_file_is_not_writable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch("hop.main.run_interactive_ui", return_value="/repos/wt-feature"),
        pytest.raises(SystemExit) as exc_info,
    ):
        main(["--cd-file", str(tmp_path)], client=_client_with_a_branch())

    assert exc_info.value.code == 1
    assert "Could not write --cd-file" in capsys.readouterr().err
