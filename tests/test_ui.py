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
    format_branch_name,
    format_status,
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


def test_branch_list_falls_back_to_empty_current_branch_when_get_current_branch_raises(
    sample_branches: list[BranchInfo],
) -> None:
    with patch("hop.ui.get_current_branch", side_effect=RuntimeError("Not in a repo")):
        branch_list = BranchList(sample_branches)
        assert branch_list.branches == sample_branches
        assert branch_list.current_branch == ""


def test_format_branch_name_marks_current_branch() -> None:
    result = format_branch_name("main", is_current=True)
    assert isinstance(result, Text)
    assert result.plain == "* main"


def test_format_branch_name_returns_plain_name_for_other_branches() -> None:
    result = format_branch_name("feature", is_current=False)
    assert result == "feature"


def test_update_branch_replaces_entry_and_redraws_all_four_cells(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_update_branch_does_nothing_when_index_is_out_of_range(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_show_status_writes_message_into_status_widget(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_cursor_down_forwards_to_branch_list(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_cursor_down()

    # Should call action_cursor_down on BranchList
    mock_branch_list.action_cursor_down.assert_called_once()


def test_action_cursor_up_forwards_to_branch_list(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList
    mock_branch_list = Mock()
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_cursor_up()

    # Should call action_cursor_up on BranchList
    mock_branch_list.action_cursor_up.assert_called_once()


def test_action_checkout_invokes_client_and_refreshes(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == [sample_branches[0].name]
    app.refresh_branches.assert_called_once()


def test_action_checkout_shows_error_status_and_skips_refresh_on_checkout_failure(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_checkout_is_noop_for_negative_cursor(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == []


def test_action_checkout_is_noop_when_cursor_past_end(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 99
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_checkout()

    assert client.checkout_calls == []


def test_action_rebase_invokes_client_and_refreshes(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.action_rebase()

    assert client.rebase_calls == [sample_branches[1].name]
    app.refresh_branches.assert_called_once()


def test_action_rebase_shows_error_status_and_skips_refresh_on_rebase_failure(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_rebase_is_noop_for_negative_cursor(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -5
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]

    app.action_rebase()

    assert client.rebase_calls == []


def test_action_delete_deletes_synced_branch_without_confirmation_prompt(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_delete_shows_confirmation_screen_for_ahead_branch(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_delete_shows_error_status_and_keeps_branch_on_delete_failure(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_delete_is_noop_when_cursor_past_end(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 100
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_delete()

    assert client.delete_calls == []
    app.push_screen.assert_not_called()


def test_action_new_branch_pushes_input_screen_with_source_branch_name(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_new_branch_is_noop_for_negative_cursor(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches)

    # Mock query_one to return a mock BranchList with invalid cursor
    mock_branch_list = Mock()
    mock_branch_list.cursor_row = -1
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.push_screen = Mock()  # type: ignore[method-assign]

    app.action_new_branch()

    # Should not show input dialog
    app.push_screen.assert_not_called()


def test_handle_new_branch_input_creates_then_checks_out_and_refreshes(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.handle_new_branch_input("new-feature")

    assert client.create_calls == [(sample_branches[0].name, "new-feature")]
    assert client.checkout_calls == ["new-feature"]
    app.show_status.assert_called_once()
    app.refresh_branches.assert_called_once_with(focus_branch_name="new-feature")


def test_handle_new_branch_input_does_nothing_when_input_is_none(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]

    app.handle_new_branch_input(None)

    assert client.create_calls == []
    app.show_status.assert_not_called()


def test_handle_new_branch_input_shows_error_and_skips_checkout_on_create_failure(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.create_error = RuntimeError("Branch already exists")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.handle_new_branch_input("existing-branch")

    app.show_status.assert_called_once_with("Error: Branch already exists")
    assert client.checkout_calls == []
    app.refresh_branches.assert_not_called()


def test_handle_new_branch_input_shows_error_when_checkout_fails_after_create(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.checkout_error = RuntimeError("Checkout failed")
    app = HopApp(sample_branches, client=client)

    mock_branch_list = Mock()
    mock_branch_list.cursor_row = 0
    app.query_one = Mock(return_value=mock_branch_list)  # type: ignore[method-assign]
    app.show_status = Mock()  # type: ignore[method-assign]
    app.refresh_branches = Mock()  # type: ignore[method-assign]

    app.handle_new_branch_input("new-feature")

    assert len(client.create_calls) == 1
    app.show_status.assert_called_once_with("Error: Checkout failed")
    app.refresh_branches.assert_not_called()


def test_refresh_branches_remounts_branch_list_with_updated_branches(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_run_interactive_ui_constructs_HopApp_with_branches_and_client_and_runs_it(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)

    with patch("hop.ui.HopApp") as mock_app_class:
        mock_app_instance = Mock()
        mock_app_class.return_value = mock_app_instance

        run_interactive_ui(sample_branches, client)

        mock_app_class.assert_called_once_with(sample_branches, client)
        mock_app_instance.run.assert_called_once()


def test_action_new_branch_uses_configured_prefix_for_source_branch(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_action_new_branch_uses_default_prefix_when_branch_has_no_configured_prefix(
    sample_branches: list[BranchInfo],
) -> None:
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


def test_help_screen_close_button_dismisses_the_screen() -> None:
    screen = HelpScreen()
    screen.dismiss = Mock()  # type: ignore[method-assign]

    # Create a mock button event
    mock_button = Mock()
    mock_button.id = "close"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once()


def test_confirm_delete_screen_confirm_button_dismisses_with_true() -> None:
    screen = ConfirmDeleteScreen("test-branch", "=", True)
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "confirm"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(True)


def test_confirm_delete_screen_cancel_button_dismisses_with_false() -> None:
    screen = ConfirmDeleteScreen("test-branch", "=", True)
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "cancel"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(False)


def test_branch_name_input_create_button_dismisses_with_entered_name() -> None:
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


def test_branch_name_input_create_button_refocuses_field_when_name_is_blank() -> None:
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


def test_branch_name_input_cancel_button_dismisses_with_none() -> None:
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_button = Mock()
    mock_button.id = "cancel"
    mock_event = Mock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(None)


def test_branch_name_input_enter_key_dismisses_with_entered_name() -> None:
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_event = Mock()
    mock_event.value = "new-branch"

    screen.on_input_submitted(mock_event)
    screen.dismiss.assert_called_once_with("new-branch")


def test_branch_name_input_enter_key_does_nothing_when_name_is_blank() -> None:
    screen = BranchNameInputScreen("main")
    screen.dismiss = Mock()  # type: ignore[method-assign]

    mock_event = Mock()
    mock_event.value = "   "

    screen.on_input_submitted(mock_event)
    # Should not dismiss if empty
    screen.dismiss.assert_not_called()


def _status_branch(track_status: str) -> BranchInfo:
    return BranchInfo(
        name="test",
        creator_date=datetime(2025, 1, 1),
        last_commit_message="Test",
        track_status=track_status,
        is_loading=False,
    )


def test_format_status_for_behind_branch_renders_yellow_marker() -> None:
    status = format_status(_status_branch("<"))
    assert isinstance(status, Text)
    assert status.plain == "<"
    assert str(status.style) == "bright_yellow"


def test_format_status_for_ahead_branch_renders_cyan_marker() -> None:
    status = format_status(_status_branch(">"))
    assert isinstance(status, Text)
    assert status.plain == ">"
    assert str(status.style) == "bright_cyan"


def test_format_status_for_diverged_branch_renders_red_marker() -> None:
    status = format_status(_status_branch("<>"))
    assert isinstance(status, Text)
    assert status.plain == "<>"
    assert str(status.style) == "bright_red"


def test_format_status_for_branch_without_upstream_renders_dim_blank() -> None:
    status = format_status(_status_branch(""))
    assert isinstance(status, Text)
    assert status.plain == "  "
    assert str(status.style) == "dim white"


def test_remove_branch_is_noop_for_out_of_range_indices() -> None:
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


def test_action_help_pushes_help_screen(sample_branches: list[BranchInfo]) -> None:
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


def test_update_branch_redraws_current_branch_with_marker() -> None:
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
