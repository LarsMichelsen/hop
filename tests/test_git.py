"""Tests for git module."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from hop.git import (
    BranchInfo,
    SubprocessGitClient,
    checkout_branch,
    create_branch,
    delete_branch,
    fetch_branch_metadata,
    get_base_branch,
    get_branches_fast,
    get_current_branch,
    is_git_repo,
)


def test_is_git_repo_returns_false_when_git_rev_parse_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 128

    with patch("subprocess.run", return_value=mock_result):
        assert is_git_repo() is False


def test_get_current_branch_raises_when_git_rev_parse_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "not a git repository"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Failed to get current branch"),
    ):
        get_current_branch()


def test_get_branches_fast_returns_branches_sorted_by_creator_date_descending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Build an isolated repo with known branches instead of reading the ambient
    # checkout: CI's pull_request checkout is a detached HEAD with no local
    # branches, so `git for-each-ref refs/heads/` would be empty there.
    git = ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test"]
    subprocess.run([*git, "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [*git, "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run([*git, "branch", "feature"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)

    branches = get_branches_fast()

    assert len(branches) > 0
    for branch in branches:
        assert isinstance(branch.name, str)
        assert len(branch.name) > 0
        assert isinstance(branch.creator_date, datetime)
        assert isinstance(branch.last_commit_message, str)
        assert branch.is_loading is True
        assert branch.upstream is None or isinstance(branch.upstream, str)

    for i in range(len(branches) - 1):
        assert branches[i].creator_date >= branches[i + 1].creator_date


def test_get_branches_fast_raises_when_git_for_each_ref_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Failed to get branches"),
    ):
        get_branches_fast()


def test_get_branches_fast_returns_empty_list_when_git_output_is_empty() -> None:
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        branches = get_branches_fast()
        assert branches == []


def test_get_branches_fast_skips_lines_that_lack_three_pipe_separated_parts() -> None:
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "main|2025-01-01|Initial commit\ninvalid_line\n"

    with patch("subprocess.run", return_value=mock_result):
        branches = get_branches_fast()
        assert len(branches) == 1
        assert branches[0].name == "main"


def test_fetch_branch_metadata_returns_no_upstream_when_for_each_ref_emits_only_separator() -> None:
    branch = BranchInfo(
        name="local-only",
        creator_date=datetime.now(),
        last_commit_message="Local commit",
    )

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "|"

    with patch("subprocess.run", return_value=mock_result):
        updated = fetch_branch_metadata(branch)
        assert updated.upstream is None
        assert updated.track_status == ""
        assert updated.is_merged is False
        assert updated.is_loading is False


def test_fetch_branch_metadata_marks_branch_merged_when_merge_base_succeeds() -> None:
    branch = BranchInfo(
        name="feature",
        creator_date=datetime.now(),
        last_commit_message="Feature commit",
    )

    mock_for_each_ref = Mock()
    mock_for_each_ref.returncode = 0
    mock_for_each_ref.stdout = "origin/feature|="

    mock_merge_base = Mock()
    mock_merge_base.returncode = 0

    with patch("subprocess.run", side_effect=[mock_for_each_ref, mock_merge_base]):
        updated = fetch_branch_metadata(branch)
        assert updated.upstream == "origin/feature"
        assert updated.track_status == "="
        assert updated.is_merged is True
        assert updated.is_loading is False


def test_fetch_branch_metadata_marks_branch_unmerged_when_merge_base_fails() -> None:
    branch = BranchInfo(
        name="feature",
        creator_date=datetime.now(),
        last_commit_message="Feature commit",
    )

    mock_for_each_ref = Mock()
    mock_for_each_ref.returncode = 0
    mock_for_each_ref.stdout = "origin/feature|>"

    mock_merge_base = Mock()
    mock_merge_base.returncode = 1

    with patch("subprocess.run", side_effect=[mock_for_each_ref, mock_merge_base]):
        updated = fetch_branch_metadata(branch)
        assert updated.upstream == "origin/feature"
        assert updated.track_status == ">"
        assert updated.is_merged is False
        assert updated.is_loading is False


def test_checkout_branch_completes_when_git_checkout_succeeds() -> None:
    mock_result = Mock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        checkout_branch("main")


def test_checkout_branch_raises_when_git_checkout_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error: pathspec 'nonexistent' did not match"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Failed to checkout branch"),
    ):
        checkout_branch("nonexistent")


def test_get_base_branch_returns_local_branch_matching_configured_upstream() -> None:
    mock_upstream = Mock()
    mock_upstream.returncode = 0
    mock_upstream.stdout = "origin/main"

    mock_verify = Mock()
    mock_verify.returncode = 0

    with patch("subprocess.run", side_effect=[mock_upstream, mock_verify]):
        base = get_base_branch("feature")
        assert base == "main"


def test_get_base_branch_falls_back_to_main_when_upstream_is_unset() -> None:
    mock_no_upstream = Mock()
    mock_no_upstream.returncode = 0
    mock_no_upstream.stdout = ""

    mock_main_exists = Mock()
    mock_main_exists.returncode = 0

    mock_merge_base = Mock()
    mock_merge_base.returncode = 0

    with patch("subprocess.run", side_effect=[mock_no_upstream, mock_main_exists, mock_merge_base]):
        base = get_base_branch("feature")
        assert base == "main"


def test_get_base_branch_returns_none_when_no_candidate_base_exists() -> None:
    mock_no_upstream = Mock()
    mock_no_upstream.returncode = 0
    mock_no_upstream.stdout = ""

    mock_no_branch = Mock()
    mock_no_branch.returncode = 1

    with patch("subprocess.run", side_effect=[mock_no_upstream] + [mock_no_branch] * 4):
        base = get_base_branch("orphan")
        assert base is None


def test_rebase_to_branch_raises_when_git_rebase_fails() -> None:
    class StubClient(SubprocessGitClient):
        def get_base_branch(self, branch_name: str) -> str | None:
            return "main"

    mock_checkout = Mock()
    mock_checkout.returncode = 0

    mock_rebase = Mock()
    mock_rebase.returncode = 1
    mock_rebase.stderr = "fatal: conflict"

    with (
        patch("subprocess.run", side_effect=[mock_checkout, mock_rebase]),
        pytest.raises(RuntimeError, match="Failed to rebase to main"),
    ):
        StubClient().rebase_to_branch("feature")


def test_rebase_to_branch_completes_when_checkout_and_rebase_succeed() -> None:
    class StubClient(SubprocessGitClient):
        def get_base_branch(self, branch_name: str) -> str | None:
            return "main"

    mock_success = Mock()
    mock_success.returncode = 0

    with patch("subprocess.run", side_effect=[mock_success, mock_success]):
        StubClient().rebase_to_branch("feature")


def test_rebase_to_branch_raises_when_base_branch_cannot_be_determined() -> None:
    class StubClient(SubprocessGitClient):
        def get_base_branch(self, branch_name: str) -> str | None:
            return None

    with pytest.raises(RuntimeError, match="Cannot determine base branch"):
        StubClient().rebase_to_branch("orphan")


def test_delete_branch_completes_when_git_branch_delete_succeeds() -> None:
    mock_current = Mock()
    mock_current.returncode = 0
    mock_current.stdout = "main"

    mock_delete = Mock()
    mock_delete.returncode = 0

    with patch("subprocess.run", side_effect=[mock_current, mock_delete]):
        delete_branch("feature")


def test_delete_branch_raises_when_git_branch_delete_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error: branch 'main' not found"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Failed to delete branch"),
    ):
        delete_branch("main")


def test_delete_branch_refuses_to_delete_the_currently_checked_out_branch() -> None:
    class StubClient(SubprocessGitClient):
        def get_current_branch(self) -> str:
            return "main"

    with pytest.raises(RuntimeError, match="Cannot delete the currently checked out branch"):
        StubClient().delete_branch("main")


def test_create_branch_completes_when_git_branch_create_succeeds() -> None:
    mock_create = Mock()
    mock_create.returncode = 0

    with patch("subprocess.run", return_value=mock_create):
        create_branch("main", "new-feature")


@pytest.mark.parametrize(
    "new_name",
    [
        pytest.param("", id="empty string"),
        pytest.param("   ", id="whitespace only"),
    ],
)
def test_create_branch_raises_when_new_name_is_blank(new_name: str) -> None:
    with pytest.raises(RuntimeError, match="Branch name cannot be empty"):
        create_branch("main", new_name)


def test_create_branch_raises_when_git_branch_create_fails() -> None:
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: branch already exists"

    with (
        patch("subprocess.run", return_value=mock_result),
        pytest.raises(RuntimeError, match="Failed to create branch"),
    ):
        create_branch("main", "existing-branch")
