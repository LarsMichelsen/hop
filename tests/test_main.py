"""Tests for main module."""

from unittest.mock import Mock, patch

import pytest

from hop.main import main


def test_main_not_in_git_repo() -> None:
    """Test that main exits when not in a git repository."""
    with patch("hop.main.is_git_repo", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_get_branches_fails() -> None:
    """Test that main exits when get_branches_fast fails."""
    with (
        patch("hop.main.is_git_repo", return_value=True),
        patch("hop.main.get_branches_fast", side_effect=RuntimeError("Git error")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_no_branches() -> None:
    """Test that main exits when there are no branches."""
    with (
        patch("hop.main.is_git_repo", return_value=True),
        patch("hop.main.get_branches_fast", return_value=[]),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_ui_exception() -> None:
    """Test that main exits when UI raises an exception."""
    mock_branch = Mock()
    with (
        patch("hop.main.is_git_repo", return_value=True),
        patch("hop.main.get_branches_fast", return_value=[mock_branch]),
        patch("hop.main.run_interactive_ui", side_effect=Exception("UI error")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
