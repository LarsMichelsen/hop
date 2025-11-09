"""Text-based UI for hop."""

import contextlib
from typing import ClassVar

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static
from textual.worker import Worker

from hop.config import get_prefix_for_branch, load_config
from hop.git import (
    BranchInfo,
    checkout_branch,
    create_branch,
    delete_branch,
    fetch_branch_metadata,
    get_current_branch,
    rebase_to_branch,
)


class HelpScreen(ModalScreen[None]):  # type: ignore[misc]
    """Modal screen showing keyboard shortcuts help."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-dialog {
        width: 60;
        height: 20;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #help-content {
        width: 100%;
        height: 1fr;
    }

    #help-title {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
    }

    #close-button-container {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the help dialog."""
        with Container(id="help-dialog"):
            yield Label("Keyboard Shortcuts", id="help-title")
            with VerticalScroll(id="help-content"):
                yield Static(
                    """
Navigation:
  ↑/k        Move cursor up
  ↓/j        Move cursor down

Actions:
  c          Checkout selected branch
  r          Rebase current branch to selected branch's upstream
  d          Delete selected branch (with confirmation)
  n          Create new branch from selected branch
  h          Show this help screen
  q          Quit application

Status Indicators:
  =          Branch synced with upstream (green)
  <          Branch behind upstream (yellow)
  >          Branch ahead of upstream (cyan)
  <>         Branch diverged from upstream (red)
  --         Loading metadata...
  *          Current branch marker
                    """
                )
            with Horizontal(id="close-button-container"):
                yield Button("Close", variant="primary", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.dismiss()


class ConfirmDeleteScreen(ModalScreen[bool]):  # type: ignore[misc]
    """Modal screen for confirming branch deletion."""

    CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #confirm-message {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, branch_name: str, track_status: str, is_merged: bool) -> None:
        super().__init__()
        self.branch_name = branch_name
        self.track_status = track_status
        self.is_merged = is_merged

    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        status_msg = ""

        # Show warning based on merge status and track status
        if not self.is_merged:
            status_msg = "\n⚠️  This branch is NOT fully merged to upstream."
            if self.track_status == ">":
                status_msg += "\nIt has unpushed commits that will be lost."
            elif self.track_status == "<>":
                status_msg += "\nIt has diverged from upstream."
            elif not self.track_status:
                status_msg += "\nIt has no upstream configured."
        else:
            # Branch is merged
            if self.track_status == ">":
                status_msg = "\nThis branch has unpushed commits (but is merged to upstream)."
            elif self.track_status == "<":
                status_msg = "\nThis branch is behind upstream."
            elif self.track_status == "<>":
                status_msg = "\nThis branch has diverged from upstream."
            elif not self.track_status:
                status_msg = "\nThis branch has no upstream configured."

        with Container(id="confirm-dialog"):
            yield Label(
                f"Delete branch '{self.branch_name}'?{status_msg}",
                id="confirm-message",
            )
            with Horizontal(id="button-container"):
                yield Button("Delete", variant="error", id="confirm")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


class BranchNameInputScreen(ModalScreen[str | None]):  # type: ignore[misc]
    """Modal screen for entering a new branch name."""

    CSS = """
    BranchNameInputScreen {
        align: center middle;
    }

    #input-dialog {
        width: 60;
        height: 13;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #input-title {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
        text-style: bold;
    }

    #input-field {
        width: 100%;
        margin-bottom: 1;
    }

    #input-button-container {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, source_branch: str, prefix: str = "") -> None:
        super().__init__()
        self.source_branch = source_branch
        self.prefix = prefix

    def compose(self) -> ComposeResult:
        """Compose the input dialog."""
        with Container(id="input-dialog"):
            yield Label(f"Create new branch from '{self.source_branch}'", id="input-title")
            yield Input(
                value=self.prefix,
                placeholder="Enter branch name...",
                id="input-field",
            )
            with Horizontal(id="input-button-container"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Focus the input field when mounted."""
        input_field = self.query_one(Input)
        input_field.focus()
        input_field.cursor_position = len(input_field.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "create":
            input_field = self.query_one(Input)
            branch_name = input_field.value.strip()
            if branch_name:
                self.dismiss(branch_name)
            else:
                # Don't dismiss if empty - show feedback
                input_field.focus()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input field."""
        branch_name = event.value.strip()
        if branch_name:
            self.dismiss(branch_name)


class BranchList(DataTable):  # type: ignore[misc]
    """Widget to display the list of branches."""

    def __init__(self, branches: list[BranchInfo]) -> None:
        super().__init__()
        self.branches = branches
        self.current_branch = ""
        with contextlib.suppress(RuntimeError):
            self.current_branch = get_current_branch()

    def _format_status(self, branch: BranchInfo) -> Text:
        """Format track status with color coding.

        Color scheme:
        - = (synced): green
        - < (behind): yellow
        - > (ahead): cyan
        - <> (diverged): red
        - -- (loading): dim white
        - (no upstream): dim white
        """
        if branch.is_loading:
            return Text("--", style="dim white")

        status = branch.track_status if branch.track_status else "  "

        # Apply colors based on track status (using terminal palette)
        if status == "=":
            return Text(status, style="bright_green")
        elif status == "<":
            return Text(status, style="bright_yellow")
        elif status == ">":
            return Text(status, style="bright_cyan")
        elif status == "<>":
            return Text(status, style="bright_red")
        else:
            # No upstream or empty status
            return Text(status, style="dim white")

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.show_header = False

        # Add columns
        self.add_column("Date", width=10)  # type: ignore[misc]
        self.add_column("Status", width=4)  # type: ignore[misc]
        self.add_column("Branch", width=40)  # type: ignore[misc]
        self.add_column("Last Commit", width=None)  # type: ignore[misc]

        # Add initial rows with loading indicators
        for branch in self.branches:
            self._add_branch_row(branch)

    def _add_branch_row(self, branch: BranchInfo) -> None:
        """Add or update a branch row in the table."""
        # Format date
        date_str = branch.creator_date.strftime("%Y-%m-%d")

        # Track status with color
        status = self._format_status(branch)

        # Branch name - highlight current branch with colored marker
        if branch.name == self.current_branch:
            branch_name = Text.assemble(
                ("* ", "bold bright_green"),
                branch.name,
            )
        else:
            branch_name = branch.name

        # Add row
        self.add_row(date_str, status, branch_name, branch.last_commit_message)  # type: ignore[misc]

    def update_branch(self, branch: BranchInfo, row_index: int) -> None:
        """Update a branch row with new metadata."""
        if row_index >= len(self.branches):
            return

        self.branches[row_index] = branch

        # Update the row
        date_str = branch.creator_date.strftime("%Y-%m-%d")
        status = self._format_status(branch)

        # Branch name - highlight current branch with colored marker
        if branch.name == self.current_branch:
            branch_name = Text.assemble(
                ("* ", "bold bright_green"),
                branch.name,
            )
        else:
            branch_name = branch.name

        # Update cells
        self.update_cell_at((row_index, 0), date_str)  # type: ignore[arg-type,misc]
        self.update_cell_at((row_index, 1), status)  # type: ignore[arg-type,misc]
        self.update_cell_at((row_index, 2), branch_name)  # type: ignore[arg-type,misc]
        self.update_cell_at((row_index, 3), branch.last_commit_message)  # type: ignore[arg-type,misc]

    def remove_branch(self, row_index: int) -> None:
        """Remove a branch from the list and table.

        Args:
            row_index: Index of the branch/row to remove
        """
        if row_index < 0 or row_index >= len(self.branches):
            return

        # Get the RowKey at the specified index from the ordered rows list
        # ordered_rows contains Row objects, extract the key from the Row
        row = list(self.ordered_rows)[row_index]  # type: ignore[misc]
        row_key = row.key  # type: ignore[misc]

        # Remove row from table using the RowKey
        self.remove_row(row_key)  # type: ignore[misc]

        # Remove from internal list
        del self.branches[row_index]

        # Adjust cursor if needed
        if self.cursor_row >= len(self.branches) and len(self.branches) > 0:
            self.cursor_row = len(self.branches) - 1  # type: ignore[misc]

    async def _on_click(self, event: events.Click) -> None:
        """Disable mouse click navigation."""
        event.prevent_default()
        event.stop()


class HopApp(App[None]):
    """Interactive git branch manager."""

    CSS = """
    BranchList {
        height: 1fr;
        overflow-x: hidden;
    }

    /* Use dimmer highlight for focused cursor */
    DataTable:focus > .datatable--cursor {
        background: $panel;
    }

    #footer-container {
        dock: bottom;
        height: 1;
        background: $boost;
    }

    #status {
        width: 1fr;
        height: 1;
        background: $boost;
        padding: 0 1;
    }

    #controls {
        width: auto;
        height: 1;
        background: $boost;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar = [
        ("c", "checkout", "Checkout"),
        ("r", "rebase", "Rebase"),
        ("d", "delete", "Delete"),
        ("n", "new_branch", "New Branch"),
        ("h", "help", "Help"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(self, branches: list[BranchInfo]) -> None:
        super().__init__()
        self.branches = branches
        self.metadata_workers: list[Worker[BranchInfo]] = []

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield BranchList(self.branches)
        with Horizontal(id="footer-container"):
            yield Static("Ready", id="status")
            yield Static(
                "[underline]c[/]heckout  [underline]r[/]ebase  "
                "[underline]n[/]ew  [underline]d[/]elete  "
                "[underline]q[/]uit",
                id="controls",
            )

    def on_mount(self) -> None:
        """Start loading metadata when app is mounted."""
        self.load_metadata()

    @work(exclusive=False, thread=True)
    def load_metadata_for_branch(self, branch: BranchInfo, index: int) -> BranchInfo:
        """Load metadata for a single branch in a background thread."""
        return fetch_branch_metadata(branch)

    def load_metadata(self) -> None:
        """Start loading metadata for all branches."""
        for i, branch in enumerate(self.branches):
            worker = self.load_metadata_for_branch(branch, i)
            worker.index = i  # type: ignore[attr-defined]
            self.metadata_workers.append(worker)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:  # type: ignore[misc]
        """Handle worker completion."""
        if (
            event.state == event.worker.state.SUCCESS  # type: ignore[misc]
            and event.worker.result is not None  # type: ignore[misc]
        ):
            index = event.worker.index  # type: ignore[attr-defined,misc]
            branch_list = self.query_one(BranchList)
            branch_list.update_branch(event.worker.result, index)  # type: ignore[arg-type,misc]

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        branch_list = self.query_one(BranchList)
        branch_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        branch_list = self.query_one(BranchList)
        branch_list.action_cursor_up()

    def action_help(self) -> None:
        """Show help screen with keyboard shortcuts."""
        self.push_screen(HelpScreen())

    def action_checkout(self) -> None:
        """Checkout the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        branch = self.branches[cursor_row]
        try:
            checkout_branch(branch.name)
            self.show_status(f"Checked out branch: {branch.name}")
            # Refresh the branch list to show the updated current branch
            # Pass the branch name to restore focus after refresh
            self.refresh_branches(focus_branch_name=branch.name)
        except RuntimeError as e:
            self.show_status(f"Error: {e}")

    def action_rebase(self) -> None:
        """Rebase to the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        branch = self.branches[cursor_row]
        try:
            rebase_to_branch(branch.name)
            self.show_status(f"Rebased to branch: {branch.name}")
            # Refresh the branch list to show the updated state
            # Pass the branch name to restore focus after refresh
            self.refresh_branches(focus_branch_name=branch.name)
        except RuntimeError as e:
            self.show_status(f"Error: {e}")

    def action_delete(self) -> None:
        """Delete the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        branch = self.branches[cursor_row]

        # If branch is synced with upstream (track_status == "="), delete without confirmation
        # Otherwise, show confirmation dialog
        if branch.track_status == "=" and not branch.is_loading:
            self._perform_delete(branch.name, cursor_row)
        else:
            # Show confirmation dialog - pass cursor_row through
            self.push_screen(
                ConfirmDeleteScreen(branch.name, branch.track_status, branch.is_merged),
                lambda confirmed: self._handle_delete_confirmation(
                    confirmed, branch.name, cursor_row
                ),
            )

    def _handle_delete_confirmation(
        self, confirmed: bool | None, branch_name: str, row_index: int
    ) -> None:
        """Handle the result of delete confirmation.

        Args:
            confirmed: Whether user confirmed the deletion
            branch_name: Name of the branch to delete
            row_index: Index of the branch in the list
        """
        if confirmed is True:
            self._perform_delete(branch_name, row_index)

    def _perform_delete(self, branch_name: str, row_index: int) -> None:
        """Perform the actual branch deletion.

        Args:
            branch_name: Name of the branch to delete
            row_index: Index of the branch in the list at the time of action
        """
        # Verify the branch at row_index still matches the name
        if row_index < 0 or row_index >= len(self.branches):
            self.show_status("Error: Branch index out of range")
            return

        if self.branches[row_index].name != branch_name:
            self.show_status("Error: Branch list changed, please try again")
            return

        try:
            delete_branch(branch_name)

            # Cancel any pending metadata workers for this branch BEFORE removing
            if row_index < len(self.metadata_workers):
                worker = self.metadata_workers[row_index]
                worker.cancel()  # type: ignore[misc]
                del self.metadata_workers[row_index]

            # Remove from branches list and update UI
            branch_list = self.query_one(BranchList)
            branch_list.remove_branch(row_index)

            self.show_status(f"Deleted branch: {branch_name}")
            # Do NOT exit - stay in UI for more operations
        except RuntimeError as e:
            self.show_status(f"Error: {e}")

    def action_new_branch(self) -> None:
        """Create a new branch from the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        source_branch = self.branches[cursor_row]

        config = load_config()
        prefix = get_prefix_for_branch(source_branch.name, config)

        self.push_screen(
            BranchNameInputScreen(source_branch.name, prefix),
            self._handle_new_branch_input,
        )

    def _handle_new_branch_input(self, branch_name: str | None) -> None:
        """Handle the result of branch name input.

        Args:
            branch_name: Name entered by user, or None if cancelled
        """
        if branch_name is None:
            return

        # Get the currently selected branch as source
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            self.show_status("Error: Invalid branch selection")
            return

        source_branch = self.branches[cursor_row]

        try:
            create_branch(source_branch.name, branch_name)
            checkout_branch(branch_name)
            self.show_status(f"Created and checked out branch: {branch_name}")
            # Refresh the branch list and move cursor to the new branch
            self.refresh_branches(focus_branch_name=branch_name)
        except RuntimeError as e:
            self.show_status(f"Error: {e}")

    def refresh_branches(self, focus_branch_name: str | None = None) -> None:
        """Refresh the branch list after creating a new branch.

        Args:
            focus_branch_name: Optional branch name to focus after refresh.
                If provided, cursor will move to this branch in the new list.
                If None, cursor position (row index) will be preserved.
        """
        from hop.git import get_branches_fast

        try:
            # Get updated branch list
            new_branches = get_branches_fast()

            # Update app's branch list
            self.branches = new_branches

            # Cancel all existing metadata workers
            for worker in self.metadata_workers:
                worker.cancel()  # type: ignore[misc]
            self.metadata_workers.clear()

            # Get the current branch list widget and save cursor position
            old_branch_list = self.query_one(BranchList)
            old_cursor_row = old_branch_list.cursor_row

            # Remove old branch list
            old_branch_list.remove()

            # Create and mount new branch list
            new_branch_list = BranchList(new_branches)
            self.mount(new_branch_list, before=1)  # Mount before Footer

            # Restore cursor position
            if focus_branch_name is not None:
                # Find the branch by name in the new list
                for idx, branch in enumerate(new_branches):
                    if branch.name == focus_branch_name:
                        new_branch_list.move_cursor(row=idx)  # type: ignore[misc]
                        break
                else:
                    # Branch not found (shouldn't happen), fall back to first row
                    if len(new_branches) > 0:
                        new_branch_list.move_cursor(row=0)  # type: ignore[misc]
            else:
                # Restore cursor position by row index (ensure it's within bounds)
                if 0 <= old_cursor_row < len(new_branches):
                    new_branch_list.move_cursor(row=old_cursor_row)  # type: ignore[misc]
                elif len(new_branches) > 0:
                    new_branch_list.move_cursor(row=0)  # type: ignore[misc]

            # Restore focus to the branch list
            new_branch_list.focus()

            # Start loading metadata for new branches
            self.load_metadata()

        except RuntimeError as e:
            self.show_status(f"Error refreshing branches: {e}")

    def show_status(self, message: str) -> None:
        """Show a status message."""
        status = self.query_one("#status", Static)
        status.update(message)


def run_interactive_ui(branches: list[BranchInfo]) -> None:
    """Run the interactive terminal UI for branch selection."""
    app = HopApp(branches)
    app.run()
