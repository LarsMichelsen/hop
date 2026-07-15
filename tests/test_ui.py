"""Tests for UI module."""

import threading
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from rich.cells import cell_len
from rich.text import Text
from textual.widgets import Button, Label, Static

from hop.config import Config
from hop.git import BranchInfo
from hop.ui import (
    BranchList,
    BranchNameInputScreen,
    ConfirmDeleteScreen,
    HelpScreen,
    HopApp,
    delete_warning_message,
    format_branch_name,
    format_details,
    format_status_message,
    run_interactive_ui,
)
from tests.fakes import FakeGitClient


@pytest.fixture
def empty_config() -> Config:
    return Config(branch_prefixes={}, default_branch_prefix="")


def _branch(
    name: str,
    *,
    creator_date: datetime = datetime(2025, 1, 1),
    last_commit_message: str = "commit",
    upstream: str | None = None,
    track_status: str = "",
    is_merged: bool = False,
    is_loading: bool = False,
    base_branch: str | None = None,
    ahead: int | None = None,
    behind: int | None = None,
    upstream_ahead: int | None = None,
    upstream_behind: int | None = None,
) -> BranchInfo:
    return BranchInfo(
        name=name,
        creator_date=creator_date,
        last_commit_message=last_commit_message,
        upstream=upstream,
        track_status=track_status,
        is_merged=is_merged,
        is_loading=is_loading,
        base_branch=base_branch,
        ahead=ahead,
        behind=behind,
        upstream_ahead=upstream_ahead,
        upstream_behind=upstream_behind,
    )


@pytest.fixture
def sample_branches() -> list[BranchInfo]:
    return [
        _branch("main", last_commit_message="Initial commit"),
        _branch(
            "feature",
            creator_date=datetime(2025, 1, 2),
            last_commit_message="Add feature",
            upstream="origin/feature",
            track_status="=",
        ),
    ]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_format_branch_name_highlights_current_branch_in_bold_green() -> None:
    result = format_branch_name("main", is_current=True)

    assert isinstance(result, Text)
    assert result.plain == "* main"
    assert "green" in str(result.style)


def test_format_branch_name_returns_plain_string_for_non_current_branches() -> None:
    result = format_branch_name("feature", is_current=False)

    assert result == "feature"


def test_format_details_renders_loading_marker_dimmed() -> None:
    result = format_details(_branch("x", is_loading=True))

    assert result.plain == "--"
    assert str(result.style) == "dim"


def test_format_details_says_so_when_base_and_upstream_are_missing() -> None:
    result = format_details(_branch("x"))

    assert result.plain == "no base branch found | no upstream"


def test_format_details_names_the_base_when_counting_failed() -> None:
    result = format_details(_branch("x", base_branch="main"))

    assert result.plain == "base main: unknown | no upstream"


def test_format_details_names_the_refs_and_colors_nonzero_counts() -> None:
    result = format_details(
        _branch(
            "x",
            base_branch="main",
            ahead=2,
            behind=3,
            upstream="origin/x",
            upstream_ahead=1,
            upstream_behind=4,
        )
    )

    assert result.plain == "base main: +2 -3 | upstream origin/x: +1 -4"
    styles = [str(span.style) for span in result.spans if str(span.style) != "dim"]
    assert styles == ["bold", "green", "red"] * 2


def test_format_details_dims_zero_counts() -> None:
    result = format_details(
        _branch(
            "x",
            base_branch="main",
            ahead=0,
            behind=0,
            upstream="origin/x",
            upstream_ahead=0,
            upstream_behind=0,
        )
    )

    assert result.plain == "base main: +0 -0 | upstream origin/x: +0 -0"
    count_styles = [str(span.style) for span in result.spans if str(span.style) != "bold"]
    assert count_styles == ["dim"] * 5  # four zero counts plus the separator


def test_current_branch_highlight_avoids_bright_green_under_solarized() -> None:
    # Solarized remaps bright_green to a grey base tone, so the highlight must
    # use plain green to stay green across terminal themes.
    highlight = format_branch_name("x", is_current=True)

    assert isinstance(highlight, Text)
    assert "green" in str(highlight.style)
    assert "bright_green" not in str(highlight.style)


def test_format_status_message_without_a_prefix_returns_plain_text() -> None:
    assert format_status_message("Checked out branch: main") == "Checked out branch: main"


def test_format_status_message_adds_a_colored_prefix_label() -> None:
    result = format_status_message("something broke", "Error", "bold red")

    assert isinstance(result, Text)
    assert result.plain == "[Error] something broke"
    red = next(s for s in result.spans if "red" in str(s.style))
    assert result.plain[red.start : red.end] == "Error"


def test_format_status_message_strips_trailing_whitespace() -> None:
    # Git errors often end in a newline; it must not leave blank lines behind.
    result = format_status_message("not a valid branch name\n\n", "Error", "bold red")

    assert isinstance(result, Text)
    assert result.plain == "[Error] not a valid branch name"


# ---------------------------------------------------------------------------
# BranchList widget
# ---------------------------------------------------------------------------


def test_branch_list_falls_back_to_empty_current_branch_when_get_current_branch_raises(
    sample_branches: list[BranchInfo],
) -> None:
    with patch("hop.ui.get_current_branch", side_effect=RuntimeError("Not in a repo")):
        branch_list = BranchList(sample_branches)

    assert branch_list.branches == sample_branches
    assert branch_list.current_branch == ""


async def test_update_branch_replaces_branch_entry_in_internal_list(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        branch_list = app.query_one(BranchList)

        updated = _branch(
            "main",
            last_commit_message="Updated message",
            upstream="origin/main",
            track_status="<",
        )
        branch_list.update_branch(updated)

        assert branch_list.branches[0] == updated


async def test_update_branch_is_noop_when_branch_is_no_longer_listed(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        branch_list = app.query_one(BranchList)
        before = list(branch_list.branches)

        branch_list.update_branch(_branch("ghost"))

        assert branch_list.branches == before


async def test_details_line_shows_base_distance_for_the_selected_branch() -> None:
    branches = [
        _branch("feature", base_branch="main", ahead=1, behind=2),
        _branch("main"),
    ]
    app = HopApp(branches, client=FakeGitClient(branches=branches))

    async with app.run_test() as pilot:
        await pilot.pause()

        details = app.query_one("#details", Static)
        assert "base main: +1 -2" in str(details.content)


async def test_details_line_follows_the_cursor() -> None:
    branches = [
        _branch("feature", base_branch="main", ahead=1, behind=2),
        _branch("main"),
    ]
    app = HopApp(branches, client=FakeGitClient(branches=branches))

    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("j")

        details = app.query_one("#details", Static)
        assert "no base branch found" in str(details.content)


async def test_deleting_the_bottom_branch_moves_cursor_and_details_to_the_row_above() -> None:
    branches = [
        _branch("keep", base_branch="main", ahead=1, behind=0),
        _branch("gone", track_status="=", is_merged=True),
    ]
    app = HopApp(branches, client=FakeGitClient(branches=branches))

    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("j")
        await pilot.press("d")  # synced branch deletes without confirmation

        branch_list = app.query_one(BranchList)
        assert branch_list.cursor_row == 0
        details = app.query_one("#details", Static)
        assert "base main: +1 -0" in str(details.content)


async def test_mouse_clicks_do_not_move_the_cursor(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        branch_list = app.query_one(BranchList)
        assert branch_list.cursor_row == 0

        await pilot.click(BranchList, offset=(10, 1))  # second row

        assert branch_list.cursor_row == 0


async def test_remove_branch_is_noop_for_out_of_range_indices(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        branch_list = app.query_one(BranchList)
        before = list(branch_list.branches)

        branch_list.remove_branch(-1)
        branch_list.remove_branch(99)

        assert branch_list.branches == before


# ---------------------------------------------------------------------------
# Cursor / keyboard navigation
# ---------------------------------------------------------------------------


async def test_pressing_j_moves_cursor_down(sample_branches: list[BranchInfo]) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(BranchList).cursor_row == 0

        await pilot.press("j")

        assert app.query_one(BranchList).cursor_row == 1


async def test_pressing_k_moves_cursor_up(sample_branches: list[BranchInfo]) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        assert app.query_one(BranchList).cursor_row == 1

        await pilot.press("k")

        assert app.query_one(BranchList).cursor_row == 0


# ---------------------------------------------------------------------------
# Checkout (c)
# ---------------------------------------------------------------------------


async def test_pressing_c_checks_out_selected_branch_and_updates_status(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # select "feature"
        await pilot.press("c")
        await pilot.pause()

        assert client.checkout_calls == ["feature"]
        status = app.query_one("#status", Static)
        assert "[OK] Checked out branch: feature" in str(status.content)


async def test_pressing_c_shows_error_status_when_checkout_fails(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.checkout_error = RuntimeError("Checkout failed")
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert "[Error] Checkout failed" in str(status.content)


async def test_pressing_c_on_empty_branch_list_is_a_noop() -> None:
    client = FakeGitClient(branches=[])
    app = HopApp([], client=client)

    async with app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()

        assert client.checkout_calls == []


# ---------------------------------------------------------------------------
# Rebase (r)
# ---------------------------------------------------------------------------


async def test_pressing_r_rebases_selected_branch_and_updates_status(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("r")
        await pilot.pause()

        assert client.rebase_calls == ["feature"]
        status = app.query_one("#status", Static)
        assert "Rebased to branch: feature" in str(status.content)


async def test_pressing_r_shows_error_status_when_rebase_fails(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.rebase_error = RuntimeError("Rebase failed")
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert "[Error] Rebase failed" in str(status.content)


async def test_pressing_r_on_empty_branch_list_is_a_noop() -> None:
    client = FakeGitClient(branches=[])
    app = HopApp([], client=client)

    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()

        assert client.rebase_calls == []


# ---------------------------------------------------------------------------
# Delete (d)
# ---------------------------------------------------------------------------


async def test_pressing_d_deletes_synced_branch_without_confirmation_screen(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # select "feature" (track_status="=")
        await pilot.press("d")
        await pilot.pause()

        assert client.delete_calls == ["feature"]
        assert not isinstance(app.screen, ConfirmDeleteScreen)
        assert [b.name for b in app.query_one(BranchList).branches] == ["main"]


async def test_pressing_d_on_diverged_branch_opens_confirmation_screen(
    sample_branches: list[BranchInfo],
) -> None:
    diverged = _branch(
        "feature",
        creator_date=datetime(2025, 1, 2),
        upstream="origin/feature",
        track_status="<>",
    )
    branches = [sample_branches[0], diverged]
    client = FakeGitClient(branches=branches)
    app = HopApp(branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDeleteScreen)
        assert app.screen.branch_name == "feature"
        assert client.delete_calls == []


async def test_clicking_confirm_in_delete_dialog_deletes_branch(
    sample_branches: list[BranchInfo],
) -> None:
    ahead = _branch(
        "feature",
        creator_date=datetime(2025, 1, 2),
        upstream="origin/feature",
        track_status=">",
    )
    branches = [sample_branches[0], ahead]
    client = FakeGitClient(branches=branches)
    app = HopApp(branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("d")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()

        assert client.delete_calls == ["feature"]
        assert [b.name for b in app.query_one(BranchList).branches] == ["main"]


async def test_clicking_cancel_in_delete_dialog_keeps_branch(
    sample_branches: list[BranchInfo],
) -> None:
    ahead = _branch(
        "feature",
        creator_date=datetime(2025, 1, 2),
        upstream="origin/feature",
        track_status=">",
    )
    branches = [sample_branches[0], ahead]
    client = FakeGitClient(branches=branches)
    app = HopApp(branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")
        await pilot.press("d")
        await pilot.pause()
        await pilot.click("#cancel")
        await pilot.pause()

        assert client.delete_calls == []
        assert [b.name for b in app.query_one(BranchList).branches] == ["main", "feature"]


async def test_pressing_d_shows_error_status_when_delete_fails(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.delete_error = RuntimeError("Delete failed")
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # select synced "feature" -> straight delete attempt
        await pilot.press("d")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert "[Error] Delete failed" in str(status.content)
        assert [b.name for b in app.query_one(BranchList).branches] == ["main", "feature"]


async def test_pressing_d_on_empty_branch_list_is_a_noop() -> None:
    client = FakeGitClient(branches=[])
    app = HopApp([], client=client)

    async with app.run_test() as pilot:
        await pilot.press("d")
        await pilot.pause()

        assert client.delete_calls == []
        assert not isinstance(app.screen, ConfirmDeleteScreen)


@pytest.mark.parametrize(
    "track_status,is_merged,expected_phrase",
    [
        pytest.param("<>", False, "diverged", id="not merged + diverged"),
        pytest.param(">", False, "unpushed commits that will be lost", id="not merged + ahead"),
        pytest.param("", False, "no upstream configured", id="not merged + no upstream"),
        pytest.param("<", False, "NOT fully merged", id="not merged + behind"),
        pytest.param(">", True, "unpushed commits (but is merged", id="merged + ahead"),
        pytest.param("<", True, "behind upstream", id="merged + behind"),
        pytest.param("<>", True, "diverged", id="merged + diverged"),
        pytest.param("", True, "no upstream configured", id="merged + no upstream"),
    ],
)
async def test_confirm_delete_screen_warns_about_branch_state(
    track_status: str, is_merged: bool, expected_phrase: str
) -> None:
    app = HopApp([], client=FakeGitClient(branches=[]))

    async with app.run_test() as pilot:
        app.push_screen(ConfirmDeleteScreen("feature", track_status, is_merged))
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDeleteScreen)
        label = app.screen.query_one("#confirm-message", Label)
        assert expected_phrase in str(label.content)


@pytest.mark.parametrize("is_merged", [True, False])
@pytest.mark.parametrize("track_status", ["", "<", ">", "<>", "="])
def test_delete_warning_uses_only_unambiguous_width_characters(
    track_status: str, is_merged: bool
) -> None:
    # Emoji like ⚠️ render as two cells but Rich measures them as one, which
    # shifts the dialog's right border. Guard that every line's Rich cell width
    # equals its length so the border stays aligned.
    for line in delete_warning_message(track_status, is_merged).splitlines():
        assert cell_len(line) == len(line)


def test_delete_warning_is_empty_for_a_synced_merged_branch() -> None:
    assert delete_warning_message("=", is_merged=True) == ""


async def test_confirm_delete_screen_highlights_the_warning() -> None:
    app = HopApp([], client=FakeGitClient(branches=[]))

    async with app.run_test() as pilot:
        app.push_screen(ConfirmDeleteScreen("feature", "", is_merged=False))
        await pilot.pause()

        content = app.screen.query_one("#confirm-message", Label).content
        assert isinstance(content, Text)
        assert any("bold" in str(span.style) for span in content.spans)


# ---------------------------------------------------------------------------
# Metadata routing while the branch list is mutated
# ---------------------------------------------------------------------------


class _GatedMetadataClient(FakeGitClient):
    """FakeGitClient whose metadata load blocks until the test releases it.

    Lets a test act on the branch list (e.g. delete a branch) while the
    background metadata workers are still in flight.
    """

    def __init__(self, branches: list[BranchInfo]) -> None:
        super().__init__(branches=branches)
        self._gate = threading.Event()

    def release_metadata(self) -> None:
        self._gate.set()

    def fetch_branch_metadata(self, branch: BranchInfo) -> BranchInfo:
        # Bounded wait so a forgotten release() can never hang the suite.
        self._gate.wait(timeout=5)
        return super().fetch_branch_metadata(branch)


async def _drain_workers(app: HopApp, pilot: object) -> None:
    """Pump the app until every metadata worker has finished and been routed."""
    for _ in range(100):
        await pilot.pause()  # type: ignore[attr-defined]
        if all(worker.is_finished for worker in list(app.workers)):
            break
    await pilot.pause()  # type: ignore[attr-defined]


async def test_in_flight_metadata_lands_on_its_own_branch_after_a_delete() -> None:
    # Deleting a branch shifts every lower row up by one. Metadata workers that
    # are still loading must write their result onto their OWN branch, not onto
    # whatever branch now occupies their old row index.
    branches = [
        _branch("main", track_status="<", is_loading=False),
        _branch("synced", track_status="=", is_loading=False),
        _branch("diverged", track_status="<>", is_loading=True),
        _branch("ahead", track_status=">", is_loading=True),
    ]
    client = _GatedMetadataClient(branches)
    app = HopApp(list(branches), client=client)

    async with app.run_test() as pilot:
        await pilot.pause()  # workers start and block in fetch_branch_metadata

        await pilot.press("j")  # cursor -> "synced" (row 1)
        await pilot.press("d")  # synced + not loading -> instant delete
        await pilot.pause()
        assert client.delete_calls == ["synced"]

        client.release_metadata()  # the in-flight workers now complete
        await _drain_workers(app, pilot)

        result = app.query_one(BranchList).branches
        assert [b.name for b in result] == ["main", "diverged", "ahead"]
        assert all(not b.is_loading for b in result)
        assert {b.name: b.track_status for b in result} == {
            "main": "<",
            "diverged": "<>",
            "ahead": ">",
        }


# ---------------------------------------------------------------------------
# New branch (n)
# ---------------------------------------------------------------------------


async def test_pressing_n_opens_branch_name_input_with_source_branch(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert app.screen.source_branch == "main"
        assert app.screen.prefix == ""


async def test_pressing_n_uses_configured_prefix_for_source_branch(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    config = Config(branch_prefixes={"main": "feature/"}, default_branch_prefix="")
    app = HopApp(sample_branches, client=client, config=config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert app.screen.prefix == "feature/"


async def test_pressing_n_uses_default_prefix_when_branch_has_no_configured_prefix(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    config = Config(branch_prefixes={"main": "feature/"}, default_branch_prefix="hotfix/")
    app = HopApp(sample_branches, client=client, config=config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j")  # select "feature"
        await pilot.press("n")
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert app.screen.source_branch == "feature"
        assert app.screen.prefix == "hotfix/"


async def test_pressing_enter_in_new_branch_dialog_creates_and_checks_out_branch(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "new-feature":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert client.create_calls == [("main", "new-feature")]
        assert client.checkout_calls == ["new-feature"]


async def test_clicking_create_in_new_branch_dialog_creates_branch(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "hotpatch":
            await pilot.press(ch)
        await pilot.click("#create")
        await pilot.pause()

        assert client.create_calls == [("main", "hotpatch")]


async def test_clicking_cancel_in_new_branch_dialog_creates_no_branch(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.click("#cancel")
        await pilot.pause()

        assert client.create_calls == []
        assert not isinstance(app.screen, BranchNameInputScreen)


async def test_create_failure_shows_error_status_and_skips_checkout(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.create_error = RuntimeError("Branch already exists")
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "dupe":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert client.checkout_calls == []
        status = app.query_one("#status", Static)
        assert "[Error] Branch already exists" in str(status.content)


async def test_checkout_failure_after_create_surfaces_error_in_status(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    client.checkout_error = RuntimeError("Checkout failed")
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "newone":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert client.create_calls == [("main", "newone")]
        status = app.query_one("#status", Static)
        assert "[Error] Checkout failed" in str(status.content)


async def test_new_branch_dialog_flags_an_invalid_name_and_disables_create(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    app = HopApp(
        sample_branches, client=FakeGitClient(branches=sample_branches), config=empty_config
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "bad name":
            await pilot.press(ch)
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert "space" in str(app.screen.query_one("#input-hint", Label).content)
        assert app.screen.query_one("#create", Button).disabled is True


async def test_new_branch_dialog_clears_hint_and_enables_create_for_a_valid_name(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    app = HopApp(
        sample_branches, client=FakeGitClient(branches=sample_branches), config=empty_config
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "valid-name":
            await pilot.press(ch)
        await pilot.pause()

        assert str(app.screen.query_one("#input-hint", Label).content) == ""
        assert app.screen.query_one("#create", Button).disabled is False


async def test_pressing_enter_with_an_invalid_name_keeps_the_dialog_open(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "bad name":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert client.create_calls == []


async def test_pressing_n_on_empty_branch_list_is_a_noop() -> None:
    client = FakeGitClient(branches=[])
    app = HopApp([], client=client)

    async with app.run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()

        assert not isinstance(app.screen, BranchNameInputScreen)
        assert client.create_calls == []


async def test_blank_input_in_new_branch_dialog_keeps_dialog_open(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("enter")  # submit empty
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert client.create_calls == []


async def test_clicking_create_with_blank_input_keeps_dialog_open(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.click("#create")
        await pilot.pause()

        assert isinstance(app.screen, BranchNameInputScreen)
        assert client.create_calls == []


# ---------------------------------------------------------------------------
# Help (h)
# ---------------------------------------------------------------------------


async def test_pressing_h_opens_help_screen(sample_branches: list[BranchInfo]) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.press("h")
        await pilot.pause()

        assert isinstance(app.screen, HelpScreen)


async def test_help_screen_close_button_dismisses_screen(
    sample_branches: list[BranchInfo],
) -> None:
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches))

    async with app.run_test() as pilot:
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.click("#close")
        await pilot.pause()

        assert not isinstance(app.screen, HelpScreen)


# ---------------------------------------------------------------------------
# Refresh after action
# ---------------------------------------------------------------------------


async def test_checkout_refreshes_branch_list_with_remote_state(
    sample_branches: list[BranchInfo],
) -> None:
    # The client holds an extra branch the initial view doesn't know about;
    # after the checkout-triggered refresh it should appear.
    hotfix = _branch("hotfix", creator_date=datetime(2025, 1, 3))
    client = FakeGitClient(branches=[*sample_branches, hotfix])
    app = HopApp(list(sample_branches), client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert {b.name for b in app.query_one(BranchList).branches} == {"main", "feature"}

        await pilot.press("c")
        await pilot.pause()

        assert {b.name for b in app.query_one(BranchList).branches} == {
            "main",
            "feature",
            "hotfix",
        }


async def test_refresh_failure_shows_error_status(
    sample_branches: list[BranchInfo],
) -> None:
    client = FakeGitClient(branches=sample_branches)
    app = HopApp(sample_branches, client=client)

    async with app.run_test() as pilot:
        await pilot.pause()
        client.get_branches_error = RuntimeError("git unavailable")

        await pilot.press("c")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert "[Error] Could not refresh branches" in str(status.content)


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


async def test_on_mount_applies_theme_from_config(
    sample_branches: list[BranchInfo],
) -> None:
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="light")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme == "textual-light"


async def test_on_mount_resolves_auto_theme_from_hop_theme_env(
    sample_branches: list[BranchInfo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOP_THEME", "nord")
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="auto")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme == "nord"


async def test_on_mount_applies_terminal_adapting_theme_by_default(
    sample_branches: list[BranchInfo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With theme='auto', the app should mount on a terminal-adapting theme."""
    monkeypatch.delenv("HOP_THEME", raising=False)
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="auto")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme in {"ansi-dark", "textual-ansi"}
        assert app.theme in app.available_themes


async def test_on_mount_falls_back_when_resolved_theme_is_not_registered(
    sample_branches: list[BranchInfo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Textual's theme catalog changes across versions (e.g. textual-ansi was
    renamed to ansi-dark in 8.2.5). The app must pick a registered terminal-
    adapting theme rather than crashing.
    """

    def fake_resolve(_setting: str, _env: object) -> str:
        return "not-a-real-theme"

    monkeypatch.setattr("hop.ui.resolve_theme", fake_resolve)
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="auto")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.theme in app.available_themes
        assert app.theme in {"ansi-dark", "textual-ansi", "textual-dark"}


async def test_pressing_t_toggles_between_dark_and_light(
    sample_branches: list[BranchInfo],
) -> None:
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="dark")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"

        await pilot.press("t")
        await pilot.pause()
        assert app.theme == "textual-light"

        await pilot.press("t")
        await pilot.pause()
        assert app.theme == "textual-dark"


async def test_toggle_theme_action_reports_new_theme_in_status(
    sample_branches: list[BranchInfo],
) -> None:
    config = Config(branch_prefixes={}, default_branch_prefix="", theme="dark")
    app = HopApp(sample_branches, client=FakeGitClient(branches=sample_branches), config=config)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert "textual-light" in str(status.content)


# ---------------------------------------------------------------------------
# Status footer layout
# ---------------------------------------------------------------------------


async def test_long_status_message_uses_full_width_and_wraps_in_small_terminal(
    sample_branches: list[BranchInfo],
    empty_config: Config,
) -> None:
    # Git errors are often wider than the terminal; the status line must span
    # the full width and wrap so the whole message stays visible instead of
    # being clipped by sharing a single row with the controls hint.
    client = FakeGitClient(branches=sample_branches)
    client.create_error = RuntimeError(
        "failed to create branch: fatal: 'aaaaaaaaaaaaaaaaaaaaaaaa' is not a valid branch name"
    )
    app = HopApp(sample_branches, client=client, config=empty_config)

    async with app.run_test(size=(60, 24)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for ch in "dupe":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()

        status = app.query_one("#status", Static)
        assert status.region.width == app.size.width
        assert status.region.height > 1


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


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
