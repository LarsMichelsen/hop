"""Text-based UI for hop."""

import contextlib
import os
from typing import ClassVar

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static
from textual.worker import Worker

from hop.config import Config, get_prefix_for_branch, load_config
from hop.git import (
    BranchInfo,
    GitClient,
    SubprocessGitClient,
    get_current_branch,
    validate_branch_name,
)
from hop.theme import pick_terminal_fallback, resolve_theme, toggle_dark_light


class HelpScreen(ModalScreen[None]):  # type: ignore[misc]
    """Modal screen showing keyboard shortcuts help."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-dialog {
        width: 60;
        height: 20;
        border: round $primary;
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
  t          Toggle light/dark theme
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


def delete_warning_message(track_status: str, is_merged: bool) -> str:
    """Caution text for the delete dialog, or "" when deletion is safe.

    ASCII-only on purpose: terminals render emoji such as ⚠️ as two cells while
    Rich measures them as one, which shifts the dialog's right border. Emphasis
    is applied with a text style in the UI instead (see ConfirmDeleteScreen).
    """
    if not is_merged:
        message = "This branch is NOT fully merged to upstream."
        if track_status == ">":
            message += "\nIt has unpushed commits that will be lost."
        elif track_status == "<>":
            message += "\nIt has diverged from upstream."
        elif not track_status:
            message += "\nIt has no upstream configured."
        return message

    if track_status == ">":
        return "This branch has unpushed commits (but is merged to upstream)."
    if track_status == "<":
        return "This branch is behind upstream."
    if track_status == "<>":
        return "This branch has diverged from upstream."
    if not track_status:
        return "This branch has no upstream configured."
    return ""


class ConfirmDeleteScreen(ModalScreen[bool]):  # type: ignore[misc]
    """Modal screen for confirming branch deletion."""

    CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: 11;
        border: round $primary;
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
        # Build the message as a Rich Text so the warning can be highlighted
        # (bold + color) without markup parsing of the branch name and without
        # changing cell widths — styling keeps the dialog border aligned.
        message = Text(f"Delete branch '{self.branch_name}'?")
        warning = delete_warning_message(self.track_status, self.is_merged)
        if warning:
            # Red for the dangerous not-merged case, amber for merged-but-unsynced.
            message.append("\n")
            message.append(warning, style="bold red" if not self.is_merged else "bold yellow")

        with Container(id="confirm-dialog"):
            yield Label(message, id="confirm-message")
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

    /* Height grows with the content so a long source-branch title (which
       wraps) or the validation hint never pushes the buttons past the border. */
    #input-dialog {
        width: 60;
        height: auto;
        border: round $primary;
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

    /* Distinct focus color for the active input, instead of the theme default. */
    #input-field:focus {
        border: tall $success;
    }

    /* Reserves its own line (blank when the name is valid) so the dialog does
       not resize as the hint appears; the equal top (input) and bottom margins
       center it between the input and the buttons. */
    #input-hint {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: $error;
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
            yield Label("", id="input-hint")
            with Horizontal(id="input-button-container"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Focus the input field and set the initial validation state."""
        input_field = self.query_one(Input)
        input_field.focus()
        input_field.cursor_position = len(input_field.value)
        self._refresh_validity(input_field.value)

    def _refresh_validity(self, value: str) -> bool:
        """Update the hint and Create button for ``value``; return whether valid.

        The pre-filled prefix (e.g. ``feature/``) is not yet a usable name, so
        keep quiet about it until the user has typed something.
        """
        error = validate_branch_name(value)
        untouched = value in ("", self.prefix)
        self.query_one("#input-hint", Label).update("" if untouched else error or "")
        self.query_one("#create", Button).disabled = error is not None
        return error is None

    def on_input_changed(self, event: Input.Changed) -> None:
        """Validate on every keystroke for immediate feedback."""
        self._refresh_validity(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "create":
            input_field = self.query_one(Input)
            if self._refresh_validity(input_field.value):
                self.dismiss(input_field.value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input field."""
        if self._refresh_validity(event.value):
            self.dismiss(event.value)


def format_status(branch: BranchInfo) -> Text:
    """Color-code a branch's upstream tracking status for display.

    = synced (green), < behind (yellow), > ahead (cyan),
    <> diverged (red), -- loading or no upstream (dim).
    """
    if branch.is_loading:
        return Text("--", style="dim")

    status = branch.track_status if branch.track_status else "  "

    if status == "=":
        return Text(status, style="bright_green")
    elif status == "<":
        return Text(status, style="bright_yellow")
    elif status == ">":
        return Text(status, style="bright_cyan")
    elif status == "<>":
        return Text(status, style="bright_red")
    else:
        return Text(status, style="dim")


def format_branch_name(branch_name: str, is_current: bool) -> Text | str:
    """Highlight the current branch: a green ``*`` marker and a bold green name.

    Uses plain ``green`` (not ``bright_green``, which Solarized remaps to a grey
    base tone) so the highlight stays green across terminal themes.
    """
    if is_current:
        return Text(f"* {branch_name}", style="bold green")
    return branch_name


def format_status_message(message: str, prefix: str = "", prefix_style: str = "") -> Text | str:
    """Build a status line, optionally with a coloured ``[prefix]`` label.

    Trailing whitespace (git errors often end in a newline) is trimmed so it
    does not leave blank lines in the wrapping footer.
    """
    message = message.rstrip()
    if not prefix:
        return message
    return Text.assemble("[", (prefix, prefix_style), "] ", message)


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
        self.show_header = False

        # Add columns
        self.add_column("Date", width=10)  # type: ignore[misc]
        self.add_column("Status", width=4)  # type: ignore[misc]
        self.add_column("Branch", width=40)  # type: ignore[misc]
        self.add_column("Last Commit", width=None)  # type: ignore[misc]

        for branch in self.branches:
            self._add_branch_row(branch)

    def _add_branch_row(self, branch: BranchInfo) -> None:
        date_str = branch.creator_date.strftime("%Y-%m-%d")
        status = format_status(branch)
        branch_name = format_branch_name(branch.name, branch.name == self.current_branch)
        self.add_row(date_str, status, branch_name, branch.last_commit_message)  # type: ignore[misc]

    def update_branch(self, branch: BranchInfo) -> None:
        """Refresh the row for ``branch``, matched by name.

        Metadata loads asynchronously, so by the time a result arrives the
        branch may have moved to a different row (a branch above it was
        deleted) or be gone entirely. Match by name — not by a positional
        index captured when the load started — so the result never lands on a
        different branch's row. Do nothing if the branch is no longer listed.
        """
        row_index = next(
            (i for i, existing in enumerate(self.branches) if existing.name == branch.name),
            None,
        )
        if row_index is None:
            return

        self.branches[row_index] = branch

        date_str = branch.creator_date.strftime("%Y-%m-%d")
        status = format_status(branch)
        branch_name = format_branch_name(branch.name, branch.name == self.current_branch)

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

    /* Use the theme's purpose-built cursor colors instead of $panel/$foreground.
       In the terminal-adapting "textual-ansi" theme every semantic color
       (panel, foreground, surface, boost) collapses to ansi_default, so a
       $panel/$foreground cursor is indistinguishable from a normal row. The
       $block-cursor-* variables are the one pair each theme guarantees to
       contrast — ansi_blue on ansi_default here, an auto-contrasting fg on the
       accent elsewhere. */
    DataTable:focus > .datatable--cursor {
        background: $block-cursor-background;
        color: $block-cursor-foreground;
        text-style: $block-cursor-text-style;
    }

    /* Status and controls each get their own full-width row so a long status
       message (e.g. a multi-line git error) wraps and stays fully visible
       instead of being clipped by sharing one line with the controls. */
    #footer-container {
        dock: bottom;
        height: auto;
        background: $boost;
    }

    #status {
        width: 100%;
        height: auto;
        background: $boost;
        padding: 0 1;
    }

    #controls {
        width: 100%;
        height: 1;
        background: $boost;
        padding: 0 1;
        text-align: right;
    }
    """

    BINDINGS: ClassVar = [
        ("c", "checkout", "Checkout"),
        ("r", "rebase", "Rebase"),
        ("d", "delete", "Delete"),
        ("n", "new_branch", "New Branch"),
        ("t", "toggle_theme", "Toggle Theme"),
        ("h", "help", "Help"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(
        self,
        branches: list[BranchInfo],
        client: GitClient | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__()
        self.branches = branches
        self.client: GitClient = client if client is not None else SubprocessGitClient()
        self.config: Config = config if config is not None else load_config()
        self.metadata_workers: list[Worker[BranchInfo]] = []

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield BranchList(self.branches)
        with Vertical(id="footer-container"):
            yield Static("Ready", id="status")
            yield Static(
                "[underline]c[/]heckout  [underline]r[/]ebase  "
                "[underline]n[/]ew  [underline]d[/]elete  "
                "[underline]q[/]uit",
                id="controls",
            )

    def on_mount(self) -> None:
        """Apply configured theme and start loading metadata when app is mounted."""
        resolved = resolve_theme(self.config.theme, os.environ)
        # Textual's theme catalog varies across versions (e.g. "textual-ansi"
        # was renamed to "ansi-dark"/"ansi-light" in 8.2.5). If the resolved
        # name isn't registered here, fall back to the closest terminal-
        # adapting theme that is — preserving the "auto" intent.
        if resolved not in self.available_themes:
            resolved = pick_terminal_fallback(frozenset(self.available_themes))
        self.theme = resolved
        self.load_metadata()

    def action_toggle_theme(self) -> None:
        """Toggle between Textual's dark and light themes."""
        self.theme = toggle_dark_light(self.theme)
        self.show_status(f"Theme: {self.theme}")

    @work(exclusive=False, thread=True)
    def load_metadata_for_branch(self, branch: BranchInfo) -> BranchInfo:
        """Load metadata for a single branch in a background thread."""
        return self.client.fetch_branch_metadata(branch)

    def load_metadata(self) -> None:
        """Start loading metadata for all branches."""
        for branch in self.branches:
            self.metadata_workers.append(self.load_metadata_for_branch(branch))

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:  # type: ignore[misc]
        """Handle worker completion.

        The result carries the branch name, so routing goes by name inside
        update_branch — the branch may have shifted rows or been deleted while
        this metadata was loading.
        """
        if (
            event.state == event.worker.state.SUCCESS  # type: ignore[misc]
            and event.worker.result is not None  # type: ignore[misc]
        ):
            branch_list = self.query_one(BranchList)
            branch_list.update_branch(event.worker.result)  # type: ignore[arg-type,misc]

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
            self.client.checkout_branch(branch.name)
            self.show_success(f"Checked out branch: {branch.name}")
            # Refresh the branch list to show the updated current branch
            # Pass the branch name to restore focus after refresh
            self.refresh_branches(focus_branch_name=branch.name)
        except RuntimeError as e:
            self.show_error(str(e))

    def action_rebase(self) -> None:
        """Rebase to the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        branch = self.branches[cursor_row]
        try:
            self.client.rebase_to_branch(branch.name)
            self.show_success(f"Rebased to branch: {branch.name}")
            # Refresh the branch list to show the updated state
            # Pass the branch name to restore focus after refresh
            self.refresh_branches(focus_branch_name=branch.name)
        except RuntimeError as e:
            self.show_error(str(e))

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
            self.show_error("Branch index out of range")
            return

        if self.branches[row_index].name != branch_name:
            self.show_error("Branch list changed, please try again")
            return

        try:
            self.client.delete_branch(branch_name)

            # Cancel any pending metadata workers for this branch BEFORE removing
            if row_index < len(self.metadata_workers):
                worker = self.metadata_workers[row_index]
                worker.cancel()  # type: ignore[misc]
                del self.metadata_workers[row_index]

            # Remove from branches list and update UI
            branch_list = self.query_one(BranchList)
            branch_list.remove_branch(row_index)

            self.show_success(f"Deleted branch: {branch_name}")
            # Do NOT exit - stay in UI for more operations
        except RuntimeError as e:
            self.show_error(str(e))

    def action_new_branch(self) -> None:
        """Create a new branch from the selected branch."""
        branch_list = self.query_one(BranchList)
        cursor_row = branch_list.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.branches):
            return

        source_branch = self.branches[cursor_row]

        prefix = get_prefix_for_branch(source_branch.name, self.config)

        self.push_screen(
            BranchNameInputScreen(source_branch.name, prefix),
            self.handle_new_branch_input,
        )

    def handle_new_branch_input(self, branch_name: str | None) -> None:
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
            self.show_error("Invalid branch selection")
            return

        source_branch = self.branches[cursor_row]

        try:
            self.client.create_branch(source_branch.name, branch_name)
            self.client.checkout_branch(branch_name)
            self.show_success(f"Created and checked out branch: {branch_name}")
            # Refresh the branch list and move cursor to the new branch
            self.refresh_branches(focus_branch_name=branch_name)
        except RuntimeError as e:
            self.show_error(str(e))

    def refresh_branches(self, focus_branch_name: str | None = None) -> None:
        """Refresh the branch list after creating a new branch.

        Args:
            focus_branch_name: Optional branch name to focus after refresh.
                If provided, cursor will move to this branch in the new list.
                If None, cursor position (row index) will be preserved.
        """
        try:
            # Get updated branch list
            new_branches = self.client.get_branches_fast()

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
            self.show_error(f"Could not refresh branches: {e}")

    def show_status(self, message: str) -> None:
        """Show a neutral status message."""
        self._render_status(format_status_message(message))

    def show_success(self, message: str) -> None:
        """Show a success message with a green ``[OK]`` prefix."""
        self._render_status(format_status_message(message, "OK", "bold green"))

    def show_error(self, message: str) -> None:
        """Show an error message with a red ``[Error]`` prefix."""
        self._render_status(format_status_message(message, "Error", "bold red"))

    def _render_status(self, content: str | Text) -> None:
        self.query_one("#status", Static).update(content)


def run_interactive_ui(branches: list[BranchInfo], client: GitClient | None = None) -> None:
    """Run the interactive terminal UI for branch selection."""
    app = HopApp(branches, client)
    app.run()
