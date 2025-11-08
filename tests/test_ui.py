"""Tests for UI module."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from rich.text import Text
from textual.widgets import Static

from hop.git import BranchInfo
from hop.ui import BranchList, HopApp, run_interactive_ui


@pytest.fixture
def sample_branches() -> list[BranchInfo]:
    """Create sample branches for testing."""
    return [
        BranchInfo(
            name="main",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Initial commit",
        ),
        BranchInfo(
            name="feature",
            creator_date=datetime(2025, 1, 2),
            last_commit_message="Add feature",
            upstream="origin/feature",
            track_status="=",
            is_loading=False,
        ),
    ]


def test_branch_list_init(sample_branches: list[BranchInfo]) -> None:
    """Test BranchList initialization."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        assert branch_list.branches == sample_branches
        assert branch_list.current_branch == "main"


def test_branch_list_init_no_current_branch(sample_branches: list[BranchInfo]) -> None:
    """Test BranchList initialization when get_current_branch fails."""
    with patch("hop.ui.get_current_branch", side_effect=RuntimeError("Not in a repo")):
        branch_list = BranchList(sample_branches)
        assert branch_list.branches == sample_branches
        assert branch_list.current_branch == ""


def test_branch_list_add_branch_row(sample_branches: list[BranchInfo]) -> None:
    """Test adding a branch row."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        # Mock the add_row method
        branch_list.add_row = Mock()  # type: ignore[method-assign]

        branch_list._add_branch_row(sample_branches[0])  # pyright: ignore[reportPrivateUsage]

        # Should call add_row with formatted data
        branch_list.add_row.assert_called_once()
        call_args = branch_list.add_row.call_args[0]
        assert call_args[0] == "2025-01-01"  # date
        # Status is now a Text object
        assert isinstance(call_args[1], Text)
        assert call_args[1].plain == "--"  # status (loading)
        assert call_args[2] == "* main"  # branch name with current marker
        assert call_args[3] == "Initial commit"  # commit message


def test_branch_list_add_branch_row_not_current(sample_branches: list[BranchInfo]) -> None:
    """Test adding a branch row for non-current branch."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        branch_list.add_row = Mock()  # type: ignore[method-assign]

        branch_list._add_branch_row(sample_branches[1])  # pyright: ignore[reportPrivateUsage]

        call_args = branch_list.add_row.call_args[0]
        assert call_args[2] == "feature"  # no current marker


def test_branch_list_add_branch_row_with_status(sample_branches: list[BranchInfo]) -> None:
    """Test adding a branch row with status."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        branch_list.add_row = Mock()  # type: ignore[method-assign]

        # Use the feature branch which has status
        branch_list._add_branch_row(sample_branches[1])  # pyright: ignore[reportPrivateUsage]

        call_args = branch_list.add_row.call_args[0]
        # Status is now a Text object with green color
        assert isinstance(call_args[1], Text)
        assert call_args[1].plain == "="  # track status


def test_branch_list_update_branch(sample_branches: list[BranchInfo]) -> None:
    """Test updating a branch row."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        branch_list.update_cell_at = Mock()  # type: ignore[method-assign]

        updated_branch = BranchInfo(
            name="main",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Updated commit",
            upstream="origin/main",
            track_status="<",
            is_loading=False,
        )

        branch_list.update_branch(updated_branch, 0)

        # Should update the branch in the list
        assert branch_list.branches[0] == updated_branch

        # Should update cells
        assert branch_list.update_cell_at.call_count == 4


def test_branch_list_update_branch_out_of_range(sample_branches: list[BranchInfo]) -> None:
    """Test updating a branch row with invalid index."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch_list = BranchList(sample_branches)
        branch_list.update_cell_at = Mock()  # type: ignore[method-assign]

        updated_branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Test",
        )

        # Should not crash
        branch_list.update_branch(updated_branch, 99)

        # Should not update any cells
        branch_list.update_cell_at.assert_not_called()


def test_hop_app_init(sample_branches: list[BranchInfo]) -> None:
    """Test HopApp initialization."""
    app = HopApp(sample_branches)
    assert app.branches == sample_branches
    assert app.metadata_workers == []


def test_hop_app_show_status(sample_branches: list[BranchInfo]) -> None:
    """Test showing status message."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock Static widget
    mock_static = Mock()
    app.query_one = Mock(return_value=mock_static)  # type: ignore[method-assign]

    app.show_status("Test message")

    # Should query for status widget and update it
    app.query_one.assert_called_once_with("#status", Static)
    mock_static.update.assert_called_once_with("Test message")


def test_delete_shows_status_message(sample_branches: list[BranchInfo]) -> None:
    """Test that delete action shows status message."""
    # Create a synced branch (so no confirmation)
    synced_branch = BranchInfo(
        name="feature",
        creator_date=sample_branches[1].creator_date,
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status="=",
        is_loading=False,
    )
    branches = [sample_branches[0], synced_branch]
    app = HopApp(branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1

    def remove_side_effect(idx: int) -> None:
        branches.pop(idx)

    mock_branch_list.remove_branch = Mock(side_effect=remove_side_effect)

    # Track calls to show_status
    status_messages: list[str] = []

    def capture_status(msg: str) -> None:
        status_messages.append(msg)

    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock(side_effect=capture_status)  # type: ignore[method-assign]

    with patch("hop.ui.delete_branch"):
        app.action_delete()

    # Should show status message with branch name
    assert len(status_messages) == 1
    assert "Deleted branch: feature" in status_messages[0]


def test_hop_app_action_cursor_down(sample_branches: list[BranchInfo]) -> None:
    """Test cursor down action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_cursor_down()

    # Should call action_cursor_down on BranchList
    mock_branch_list.action_cursor_down.assert_called_once()


def test_hop_app_action_cursor_up(sample_branches: list[BranchInfo]) -> None:
    """Test cursor up action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_cursor_up()

    # Should call action_cursor_up on BranchList
    mock_branch_list.action_cursor_up.assert_called_once()


def test_hop_app_action_checkout_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful checkout action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.checkout_branch"):
        app.action_checkout()

        # Should refresh branches after successful checkout
        app.refresh_branches.assert_called_once()


def test_hop_app_action_checkout_error(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with error."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.checkout_branch", side_effect=RuntimeError("Checkout failed")):
        app.action_checkout()

        # Should show error status
        app.show_status.assert_called_once_with("Error: Checkout failed")
        # Should not refresh branches
        app.refresh_branches.assert_not_called()


def test_hop_app_action_checkout_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with invalid cursor position."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with invalid cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    with patch("hop.ui.checkout_branch") as mock_checkout:
        app.action_checkout()

        # Should not attempt checkout
        mock_checkout.assert_not_called()


def test_hop_app_action_checkout_cursor_out_of_range(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with cursor out of range."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with out of range cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 99
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    with patch("hop.ui.checkout_branch") as mock_checkout:
        app.action_checkout()

        # Should not attempt checkout
        mock_checkout.assert_not_called()


def test_hop_app_action_rebase_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful rebase action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.rebase_to_branch"):
        app.action_rebase()

        # Should refresh branches after successful rebase
        app.refresh_branches.assert_called_once()


def test_hop_app_action_rebase_error(sample_branches: list[BranchInfo]) -> None:
    """Test rebase action with error."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.rebase_to_branch", side_effect=RuntimeError("Rebase failed")):
        app.action_rebase()

        # Should show error status
        app.show_status.assert_called_once_with("Error: Rebase failed")
        # Should not refresh branches
        app.refresh_branches.assert_not_called()


def test_hop_app_action_rebase_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test rebase action with invalid cursor position."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with invalid cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -5
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    with patch("hop.ui.rebase_to_branch") as mock_rebase:
        app.action_rebase()

        # Should not attempt rebase
        mock_rebase.assert_not_called()


def test_hop_app_action_delete_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful delete action without confirmation (synced branch)."""
    # Create a branch that's synced with upstream (track_status == "=")
    synced_branch = BranchInfo(
        name="feature",
        creator_date=sample_branches[1].creator_date,
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status="=",
        is_loading=False,
    )
    branches = [sample_branches[0], synced_branch]
    app = HopApp(branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1

    # Make remove_branch actually delete from the list
    def remove_side_effect(idx: int) -> None:
        branches.pop(idx)

    mock_branch_list.remove_branch = Mock(side_effect=remove_side_effect)
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.delete_branch"):
        app.action_delete()

        # Should remove branch from list (no confirmation needed)
        mock_branch_list.remove_branch.assert_called_once_with(1)
        # Should show status
        app.show_status.assert_called_once()
        # Branch should be removed from app's list
        assert len(app.branches) == 1


def test_hop_app_action_delete_with_confirmation(sample_branches: list[BranchInfo]) -> None:
    """Test delete action that requires confirmation (unsynced branch)."""
    # Create a branch that's ahead of upstream (track_status == ">")
    ahead_branch = BranchInfo(
        name="feature",
        creator_date=sample_branches[1].creator_date,
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status=">",
        is_loading=False,
    )
    branches = [sample_branches[0], ahead_branch]
    app = HopApp(branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_delete()

    # Should show confirmation dialog (not delete immediately)
    app.push_screen.assert_called_once()


def test_hop_app_action_delete_error(sample_branches: list[BranchInfo]) -> None:
    """Test delete action with error."""
    # Create a synced branch (so no confirmation)
    synced_branch = BranchInfo(
        name="feature",
        creator_date=sample_branches[1].creator_date,
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status="=",
        is_loading=False,
    )
    branches = [sample_branches[0], synced_branch]
    app = HopApp(branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    mock_branch_list.remove_branch = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.delete_branch", side_effect=RuntimeError("Delete failed")):
        app.action_delete()

        # Should show error status
        app.show_status.assert_called_once_with("Error: Delete failed")
        # Should not remove branch from list
        mock_branch_list.remove_branch.assert_not_called()
        # Branch count should be unchanged
        assert len(app.branches) == 2


def test_hop_app_action_delete_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test delete action with invalid cursor position."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with invalid cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 100
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.delete_branch") as mock_delete:
        app.action_delete()

        # Should not attempt delete or show confirmation
        mock_delete.assert_not_called()
        app.push_screen.assert_not_called()


def test_hop_app_action_new_branch_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful new branch creation action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_new_branch()

    # Should show input dialog
    app.push_screen.assert_called_once()
    # Verify it's calling BranchNameInputScreen with correct source branch
    args, _ = app.push_screen.call_args
    assert args[0].source_branch == sample_branches[0].name


def test_hop_app_action_new_branch_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test new branch action with invalid cursor position."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with invalid cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_new_branch()

    # Should not show input dialog
    app.push_screen.assert_not_called()


def test_hop_app_handle_new_branch_input_success(sample_branches: list[BranchInfo]) -> None:
    """Test handling successful branch name input."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.create_branch"):
        app._handle_new_branch_input("new-feature")  # type: ignore[reportPrivateUsage]

        # Should show status and refresh branches after successful creation
        app.show_status.assert_called_once()
        app.refresh_branches.assert_called_once()


def test_hop_app_handle_new_branch_input_cancelled(sample_branches: list[BranchInfo]) -> None:
    """Test handling cancelled branch name input."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.create_branch") as mock_create:
        app._handle_new_branch_input(None)  # type: ignore[reportPrivateUsage]

        # Should not create branch
        mock_create.assert_not_called()
        # Should not show status
        app.show_status.assert_not_called()


def test_hop_app_handle_new_branch_input_error(sample_branches: list[BranchInfo]) -> None:
    """Test handling error during branch creation."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.create_branch", side_effect=RuntimeError("Branch already exists")):
        app._handle_new_branch_input("existing-branch")  # type: ignore[reportPrivateUsage]

        # Should show error status
        app.show_status.assert_called_once_with("Error: Branch already exists")
        # Should not refresh branches
        app.refresh_branches.assert_not_called()


def test_hop_app_refresh_branches(sample_branches: list[BranchInfo]) -> None:
    """Test refreshing the branch list."""
    app = HopApp(sample_branches)

    # Create a new branch to be returned by get_branches_fast
    new_branch = BranchInfo(
        name="new-feature",
        creator_date=sample_branches[0].creator_date,
        last_commit_message="New feature",
    )
    updated_branches = sample_branches + [new_branch]

    # Mock query_one to return a mock BranchList
    mock_old_branch_list = Mock()
    mock_old_branch_list.remove = Mock()
    mock_old_branch_list.cursor_row = 1  # Mock cursor at row 1
    mock_old_branch_list.focus = Mock()

    app.query_one = Mock(return_value=mock_old_branch_list)  # type: ignore[method-assign]
    app.mount = Mock()  # type: ignore[method-assign]
    app.load_metadata = Mock()  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    # Add a mock worker to be cancelled
    mock_worker = Mock()
    app.metadata_workers = [mock_worker]

    # Mock the new BranchList that will be created
    mock_new_branch_list = Mock()
    mock_new_branch_list.focus = Mock()

    with (
        patch("hop.git.get_branches_fast", return_value=updated_branches),
        patch("hop.ui.BranchList", return_value=mock_new_branch_list),
    ):
        app.refresh_branches()

        # Should cancel existing workers
        mock_worker.cancel.assert_called_once()
        # Should remove old branch list
        mock_old_branch_list.remove.assert_called_once()
        # Should mount new branch list
        app.mount.assert_called_once()
        # Should restore focus to new branch list
        mock_new_branch_list.focus.assert_called_once()
        # Should start loading metadata
        app.load_metadata.assert_called_once()
        # Should have updated branches
        assert len(app.branches) == 3


def test_run_interactive_ui(sample_branches: list[BranchInfo]) -> None:
    """Test running the interactive UI."""
    with patch("hop.ui.HopApp") as mock_app_class:
        mock_app_instance = Mock()
        mock_app_class.return_value = mock_app_instance

        run_interactive_ui(sample_branches)

        # Should create app with branches
        mock_app_class.assert_called_once_with(sample_branches)
        # Should run the app
        mock_app_instance.run.assert_called_once()
