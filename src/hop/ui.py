"""Text-based UI for hop."""

import contextlib
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static
from textual.worker import Worker

from hop.git import (
    BranchInfo,
    checkout_branch,
    delete_branch,
    fetch_branch_metadata,
    get_current_branch,
    rebase_to_branch,
)


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

    def __init__(self, branch_name: str, track_status: str) -> None:
        super().__init__()
        self.branch_name = branch_name
        self.track_status = track_status

    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        status_msg = ""
        if self.track_status == ">":
            status_msg = "\nThis branch is ahead of upstream (has unpushed commits)."
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


class BranchList(DataTable):  # type: ignore[misc]
    """Widget to display the list of branches."""

    def __init__(self, branches: list[BranchInfo]) -> None:
        super().__init__()
        self.branches = branches
        self.current_branch = ""
        with contextlib.suppress(RuntimeError):
            self.current_branch = get_current_branch()

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        self.cursor_type = "row"
        self.zebra_stripes = True

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
        status = "--" if branch.is_loading else branch.track_status if branch.track_status else "  "

        # Branch name - highlight current branch
        branch_name = branch.name
        if branch.name == self.current_branch:
            branch_name = f"* {branch_name}"

        # Add row
        self.add_row(date_str, status, branch_name, branch.last_commit_message)  # type: ignore[misc]

    def update_branch(self, branch: BranchInfo, row_index: int) -> None:
        """Update a branch row with new metadata."""
        if row_index >= len(self.branches):
            return

        self.branches[row_index] = branch

        # Update the row
        date_str = branch.creator_date.strftime("%Y-%m-%d")
        status = branch.track_status if branch.track_status else "  "
        branch_name = branch.name
        if branch.name == self.current_branch:
            branch_name = f"* {branch_name}"

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

        # Get row key BEFORE modifying anything
        row_key = self.get_row_at(row_index)[0]  # type: ignore[misc]

        # Remove row from table
        self.remove_row(row_key)  # type: ignore[misc]

        # Remove from internal list
        del self.branches[row_index]

        # Adjust cursor if needed
        if self.cursor_row >= len(self.branches) and len(self.branches) > 0:
            self.cursor_row = len(self.branches) - 1  # type: ignore[misc]


class HopApp(App[None]):
    """Interactive git branch manager."""

    CSS = """
    BranchList {
        height: 1fr;
    }

    #status {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar = [
        ("c", "checkout", "Checkout"),
        ("r", "rebase", "Rebase"),
        ("d", "delete", "Delete"),
        ("q", "quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(self, branches: list[BranchInfo]) -> None:
        super().__init__()
        self.branches = branches
        self.metadata_workers: list[Worker[BranchInfo]] = []

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()
        yield BranchList(self.branches)
        yield Static("", id="status")
        yield Footer()

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
            # Exit after successful checkout
            self.exit()
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
            # Exit after successful rebase
            self.exit()
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
            self._perform_delete(branch.name)
        else:
            # Show confirmation dialog
            self.push_screen(
                ConfirmDeleteScreen(branch.name, branch.track_status),
                self._handle_delete_confirmation,
            )

    def _handle_delete_confirmation(self, confirmed: bool | None) -> None:
        """Handle the result of delete confirmation."""
        if confirmed is True:
            branch_list = self.query_one(BranchList)
            cursor_row = branch_list.cursor_row
            if cursor_row < 0 or cursor_row >= len(self.branches):
                return
            branch = self.branches[cursor_row]
            self._perform_delete(branch.name)

    def _perform_delete(self, branch_name: str) -> None:
        """Perform the actual branch deletion."""
        # Get the current cursor position before deletion
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row

        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        try:
            delete_branch(branch_name)

            # Cancel any pending metadata workers for this branch BEFORE removing
            if cursor_row < len(self.metadata_workers):
                worker = self.metadata_workers[cursor_row]
                worker.cancel()  # type: ignore[misc]
                del self.metadata_workers[cursor_row]

            # Remove from branches list and update UI
            # Note: This updates both branch_list.branches AND self.branches
            # because they reference the same list object
            branch_list.remove_branch(cursor_row)

            self.show_status(f"Deleted branch: {branch_name}")
            # Do NOT exit - stay in UI for more operations
        except RuntimeError as e:
            self.show_status(f"Error: {e}")

    def show_status(self, message: str) -> None:
        """Show a status message."""
        status = self.query_one("#status", Static)
        status.update(message)


def run_interactive_ui(branches: list[BranchInfo]) -> None:
    """Run the interactive terminal UI for branch selection."""
    app = HopApp(branches)
    app.run()
