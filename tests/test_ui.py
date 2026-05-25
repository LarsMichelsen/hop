"""Tests for UI module."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from rich.text import Text
from textual.widgets import Static

from hop.git import BranchInfo
from hop.ui import (
    BranchList,
    BranchNameInputScreen,
    ConfirmDeleteScreen,
    HelpScreen,
    HopApp,
    run_interactive_ui,
)
from tests.fakes import FakeGitClient


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
        # Branch name is now a Text object for current branch
        assert isinstance(call_args[2], Text)
        assert call_args[2].plain == "* main"  # branch name with current marker
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
    client = FakeGitClient(branches=branches)
    app = HopApp(branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1

    def remove_side_effect(idx: int) -> None:
        branches.pop(idx)

    mock_branch_list.remove_branch = Mock(side_effect=remove_side_effect)

    status_messages: list[str] = []

    def capture_status(msg: str) -> None:
        status_messages.append(msg)

    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock(side_effect=capture_status)  # type: ignore[method-assign]

    app.action_delete()

    assert client.delete_calls == ["feature"]
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
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == [sample_branches[0].name]
    app.refresh_branches.assert_called_once()


def test_hop_app_action_checkout_error(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with error."""
    client = FakeGitClient(branches=sample_branches)
    client.checkout_error = RuntimeError("Checkout failed")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_checkout()

    app.show_status.assert_called_once_with("Error: Checkout failed")
    app.refresh_branches.assert_not_called()


def test_hop_app_action_checkout_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with invalid cursor position."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == []


def test_hop_app_action_checkout_cursor_out_of_range(sample_branches: list[BranchInfo]) -> None:
    """Test checkout action with cursor out of range."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 99
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == []


def test_hop_app_action_rebase_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful rebase action."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_rebase()

    assert client.rebase_calls == [sample_branches[1].name]
    app.refresh_branches.assert_called_once()


def test_hop_app_action_rebase_error(sample_branches: list[BranchInfo]) -> None:
    """Test rebase action with error."""
    client = FakeGitClient(branches=sample_branches)
    client.rebase_error = RuntimeError("Rebase failed")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_rebase()

    app.show_status.assert_called_once_with("Error: Rebase failed")
    app.refresh_branches.assert_not_called()


def test_hop_app_action_rebase_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test rebase action with invalid cursor position."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -5
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_rebase()

    assert client.rebase_calls == []


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
    client = FakeGitClient(branches=branches)
    app = HopApp(branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1

    def remove_side_effect(idx: int) -> None:
        branches.pop(idx)

    mock_branch_list.remove_branch = Mock(side_effect=remove_side_effect)
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    app.action_delete()

    assert client.delete_calls == ["feature"]
    mock_branch_list.remove_branch.assert_called_once_with(1)
    app.show_status.assert_called_once()
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
    synced_branch = BranchInfo(
        name="feature",
        creator_date=sample_branches[1].creator_date,
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status="=",
        is_loading=False,
    )
    branches = [sample_branches[0], synced_branch]
    client = FakeGitClient(branches=branches)
    client.delete_error = RuntimeError("Delete failed")
    app = HopApp(branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    mock_branch_list.remove_branch = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    app.action_delete()

    app.show_status.assert_called_once_with("Error: Delete failed")
    mock_branch_list.remove_branch.assert_not_called()
    assert len(app.branches) == 2


def test_hop_app_action_delete_invalid_cursor(sample_branches: list[BranchInfo]) -> None:
    """Test delete action with invalid cursor position."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 100
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_delete()

    assert client.delete_calls == []
    app.push_screen.assert_not_called()


def test_hop_app_action_new_branch_success(sample_branches: list[BranchInfo]) -> None:
    """Test successful new branch creation action."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.load_config") as mock_config:
        mock_config.return_value = Mock(branch_prefixes={}, default_branch_prefix="")
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
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app._handle_new_branch_input("new-feature")  # type: ignore[reportPrivateUsage]

    assert client.create_calls == [(sample_branches[0].name, "new-feature")]
    assert client.checkout_calls == ["new-feature"]
    app.show_status.assert_called_once()
    app.refresh_branches.assert_called_once_with(focus_branch_name="new-feature")


def test_hop_app_handle_new_branch_input_cancelled(sample_branches: list[BranchInfo]) -> None:
    """Test handling cancelled branch name input."""
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    app._handle_new_branch_input(None)  # type: ignore[reportPrivateUsage]

    assert client.create_calls == []
    app.show_status.assert_not_called()


def test_hop_app_handle_new_branch_input_error(sample_branches: list[BranchInfo]) -> None:
    """Test handling error during branch creation."""
    client = FakeGitClient(branches=sample_branches)
    client.create_error = RuntimeError("Branch already exists")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app._handle_new_branch_input("existing-branch")  # type: ignore[reportPrivateUsage]

    app.show_status.assert_called_once_with("Error: Branch already exists")
    assert client.checkout_calls == []
    app.refresh_branches.assert_not_called()


def test_hop_app_handle_new_branch_input_checkout_error(
    sample_branches: list[BranchInfo],
) -> None:
    """Test handling error during branch checkout."""
    client = FakeGitClient(branches=sample_branches)
    client.checkout_error = RuntimeError("Checkout failed")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app._handle_new_branch_input("new-feature")  # type: ignore[reportPrivateUsage]

    assert len(client.create_calls) == 1
    app.show_status.assert_called_once_with("Error: Checkout failed")
    app.refresh_branches.assert_not_called()


def test_hop_app_refresh_branches(sample_branches: list[BranchInfo]) -> None:
    """Test refreshing the branch list."""
    new_branch = BranchInfo(
        name="new-feature",
        creator_date=sample_branches[0].creator_date,
        last_commit_message="New feature",
    )
    updated_branches = sample_branches + [new_branch]

    client = FakeGitClient(branches=updated_branches)
    app = HopApp(sample_branches, client=client)

    mock_old_branch_list = Mock()
    mock_old_branch_list.remove = Mock()
    mock_old_branch_list.cursor_row = 1
    mock_old_branch_list.focus = Mock()

    app.query_one = Mock(return_value=mock_old_branch_list)  # type: ignore[method-assign]
    app.mount = Mock()  # type: ignore[method-assign]
    app.load_metadata = Mock()  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    mock_worker = Mock()
    app.metadata_workers = [mock_worker]

    mock_new_branch_list = Mock()
    mock_new_branch_list.focus = Mock()

    with patch("hop.ui.BranchList", return_value=mock_new_branch_list):
        app.refresh_branches()

    mock_worker.cancel.assert_called_once()
    mock_old_branch_list.remove.assert_called_once()
    app.mount.assert_called_once()
    mock_new_branch_list.focus.assert_called_once()
    app.load_metadata.assert_called_once()
    assert len(app.branches) == 3


def test_run_interactive_ui(sample_branches: list[BranchInfo]) -> None:
    """Test running the interactive UI."""
    client = FakeGitClient(branches=sample_branches)

    with patch("hop.ui.HopApp") as mock_app_class:
        mock_app_instance = Mock()
        mock_app_class.return_value = mock_app_instance

        run_interactive_ui(sample_branches, client)

        mock_app_class.assert_called_once_with(sample_branches, client)
        mock_app_instance.run.assert_called_once()


def test_hop_app_action_new_branch_with_prefix(sample_branches: list[BranchInfo]) -> None:
    """Test new branch action with configured prefix."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.load_config") as mock_config:
        mock_config.return_value = Mock(
            branch_prefixes={"main": "feature/"}, default_branch_prefix=""
        )
        app.action_new_branch()

        # Should show input dialog
        app.push_screen.assert_called_once()
        # Verify it's calling BranchNameInputScreen with correct prefix
        args, _ = app.push_screen.call_args
        assert args[0].source_branch == "main"
        assert args[0].prefix == "feature/"


def test_hop_app_action_new_branch_with_default_prefix(
    sample_branches: list[BranchInfo],
) -> None:
    """Test new branch action with default prefix."""
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    with patch("hop.ui.load_config") as mock_config:
        mock_config.return_value = Mock(
            branch_prefixes={"main": "feature/"}, default_branch_prefix="hotfix/"
        )
        app.action_new_branch()

        # Should show input dialog
        app.push_screen.assert_called_once()
        # Verify it's using default prefix for 'feature' branch
        args, _ = app.push_screen.call_args
        assert args[0].source_branch == "feature"
        assert args[0].prefix == "hotfix/"


def test_help_screen_button_press() -> None:
    """Test HelpScreen button press dismisses screen."""
    screen = HelpScreen()
    screen.dismiss = Mock()  # type: ignore[method-assign]

    # Create a mock button event
    mock_button = Mock()
    mock_button.id = "close"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once()


def test_confirm_delete_screen_confirm_button() -> None:
    """Test ConfirmDeleteScreen confirm button dismisses with True."""
    screen = ConfirmDeleteScreen("test-branch", "=", True)
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "confirm"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(True)


def test_confirm_delete_screen_cancel_button() -> None:
    """Test ConfirmDeleteScreen cancel button dismisses with False."""
    screen = ConfirmDeleteScreen("test-branch", "=", True)
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "cancel"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(False)


def test_branch_name_input_screen_create_button_with_name() -> None:
    """Test BranchNameInputScreen create button with valid name."""
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    # Mock input field
    mock_input = Mock()
    mock_input.value = "new-branch"
    screen.query_one = Mock(return_value=mock_input)  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "create"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with("new-branch")


def test_branch_name_input_screen_create_button_empty_name() -> None:
    """Test BranchNameInputScreen create button with empty name."""
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    # Mock input field with empty value
    mock_input = Mock()
    mock_input.value = "   "
    screen.query_one = Mock(return_value=mock_input)  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "create"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    # Should not dismiss if empty
    screen.dismiss.assert_not_called()
    # Should refocus input
    mock_input.focus.assert_called_once()


def test_branch_name_input_screen_cancel_button() -> None:
    """Test BranchNameInputScreen cancel button."""
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "cancel"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(None)


def test_branch_name_input_screen_submit_with_name() -> None:
    """Test BranchNameInputScreen input submission with valid name."""
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_event = Mock()
    mock_event.value = "new-branch"

    screen.on_input_submitted(mock_event)
    screen.dismiss.assert_called_once_with("new-branch")


def test_branch_name_input_screen_submit_empty_name() -> None:
    """Test BranchNameInputScreen input submission with empty name."""
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_event = Mock()
    mock_event.value = "   "

    screen.on_input_submitted(mock_event)
    # Should not dismiss if empty
    screen.dismiss.assert_not_called()


def test_branch_list_format_status_behind() -> None:
    """Test BranchList status formatting for behind status."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Test",
            track_status="<",
            is_loading=False,
        )
        branch_list = BranchList([branch])
        status = branch_list._format_status(branch)  # type: ignore[reportPrivateUsage]
        assert isinstance(status, Text)
        assert status.plain == "<"


def test_branch_list_format_status_ahead() -> None:
    """Test BranchList status formatting for ahead status."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Test",
            track_status=">",
            is_loading=False,
        )
        branch_list = BranchList([branch])
        status = branch_list._format_status(branch)  # type: ignore[reportPrivateUsage]
        assert isinstance(status, Text)
        assert status.plain == ">"


def test_branch_list_format_status_diverged() -> None:
    """Test BranchList status formatting for diverged status."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Test",
            track_status="<>",
            is_loading=False,
        )
        branch_list = BranchList([branch])
        status = branch_list._format_status(branch)  # type: ignore[reportPrivateUsage]
        assert isinstance(status, Text)
        assert status.plain == "<>"


def test_branch_list_format_status_no_upstream() -> None:
    """Test BranchList status formatting for no upstream."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Test",
            track_status="",
            is_loading=False,
        )
        branch_list = BranchList([branch])
        status = branch_list._format_status(branch)  # type: ignore[reportPrivateUsage]
        assert isinstance(status, Text)
        assert status.plain == "  "


def test_branch_list_remove_branch_invalid_index() -> None:
    """Test BranchList remove_branch with invalid index."""
    with patch("hop.ui.get_current_branch", return_value="main"):
        branches = [
            BranchInfo(
                name="test1",
                creator_date=datetime(2025, 1, 1),
                last_commit_message="Test 1",
            ),
            BranchInfo(
                name="test2",
                creator_date=datetime(2025, 1, 2),
                last_commit_message="Test 2",
            ),
        ]
        branch_list = BranchList(branches)

        # Try to remove with negative index
        branch_list.remove_branch(-1)
        assert len(branch_list.branches) == 2

        # Try to remove with out of range index
        branch_list.remove_branch(10)
        assert len(branch_list.branches) == 2


def test_hop_app_action_help(sample_branches: list[BranchInfo]) -> None:
    """Test help action shows help screen."""
    app = HopApp(sample_branches)
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_help()

    # Should push HelpScreen
    app.push_screen.assert_called_once()
    args, _ = app.push_screen.call_args
    assert isinstance(args[0], HelpScreen)


def test_help_screen_init() -> None:
    """Test HelpScreen initialization."""
    screen = HelpScreen()
    assert screen is not None


def test_confirm_delete_screen_init() -> None:
    """Test ConfirmDeleteScreen initialization."""
    screen = ConfirmDeleteScreen("test", ">", False)
    assert screen.branch_name == "test"
    assert screen.track_status == ">"
    assert screen.is_merged is False


def test_branch_name_input_screen_init() -> None:
    """Test BranchNameInputScreen initialization."""
    screen = BranchNameInputScreen("main", "feature/")
    assert screen.source_branch == "main"
    assert screen.prefix == "feature/"


def test_branch_name_input_screen_init_no_prefix() -> None:
    """Test BranchNameInputScreen initialization without prefix."""
    screen = BranchNameInputScreen("develop")
    assert screen.source_branch == "develop"
    assert screen.prefix == ""


def test_hop_app_compose(sample_branches: list[BranchInfo]) -> None:
    """Test HopApp initialization."""
    app = HopApp(sample_branches)
    # Just verify app can be created without errors
    assert app.branches == sample_branches


def test_hop_app_show_status_update(sample_branches: list[BranchInfo]) -> None:
    """Test HopApp show_status updates correctly."""
    app = HopApp(sample_branches)
    mock_static = Mock()
    app.query_one = Mock(return_value=mock_static)  # type: ignore[method-assign]

    app.show_status("Test message")

    mock_static.update.assert_called_once_with("Test message")


def test_branch_list_update_branch_current_branch() -> None:
    """Test updating a branch that is the current branch."""
    with patch("hop.ui.get_current_branch", return_value="test"):
        branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Original",
        )
        branch_list = BranchList([branch])
        branch_list.update_cell_at = Mock()  # type: ignore[method-assign]

        # Update with new metadata
        updated_branch = BranchInfo(
            name="test",
            creator_date=datetime(2025, 1, 1),
            last_commit_message="Updated",
            upstream="origin/test",
            track_status="=",
            is_loading=False,
        )

        branch_list.update_branch(updated_branch, 0)

        # Should update cells
        assert branch_list.update_cell_at.call_count == 4
