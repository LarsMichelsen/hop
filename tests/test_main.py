"""Tests for main module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from hop.git import BranchInfo
from hop.main import main
from tests.fakes import FakeGitClient


def test_main_exits_when_branch_listing_raises_runtime_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeGitClient()
    client.get_branches_error = RuntimeError("Git error")

    with pytest.raises(SystemExit) as exc_info:
        main(client=client)

    assert exc_info.value.code == 1
    assert "Git error" in capsys.readouterr().err


def test_main_exits_when_interactive_ui_raises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeGitClient(
        branches=[
            BranchInfo(
                name="main",
                creator_date=datetime(2025, 1, 1),
                last_commit_message="initial",
            )
        ]
    )

    with (
        patch("hop.main.run_interactive_ui", side_effect=Exception("UI error")),
        pytest.raises(SystemExit) as exc_info,
    ):
        main(client=client)

    assert exc_info.value.code == 1
    assert "UI error" in capsys.readouterr().err
