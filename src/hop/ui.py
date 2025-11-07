"""Text-based UI for hop."""

import contextlib
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Static
from textual.worker import Worker

from hop.git import (
    BranchInfo,
    checkout_branch,
    delete_branch,
    fetch_branch_metadata,
    get_current_branch,
    rebase_to_branch,
)


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
        try:
            delete_branch(branch.name)
            self.show_status(f"Deleted branch: {branch.name}")
            # Exit after successful delete
            self.exit()
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
