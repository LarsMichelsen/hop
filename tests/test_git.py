"""Tests for git module."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from hop.git import (
    BranchInfo,
    checkout_branch,
    create_branch,
    delete_branch,
    fetch_branch_metadata,
    get_base_branch,
    get_branches_fast,
    get_current_branch,
    is_git_repo,
    rebase_to_branch,
)


def test_branch_info_creation() -> None:
    """Test that BranchInfo can be created with required fields."""
    branch = BranchInfo(
        name="main",
        creator_date=datetime.now(),
        last_commit_message="Initial commit",
    )
    assert branch.name == "main"
    assert branch.is_loading is True
    assert branch.upstream is None
    assert branch.track_status == ""


def test_branch_info_with_metadata() -> None:
    """Test that BranchInfo can be created with full metadata."""
    branch = BranchInfo(
        name="feature",
        creator_date=datetime.now(),
        last_commit_message="Add feature",
        upstream="origin/feature",
        track_status="=",
        is_merged=True,
        is_loading=False,
    )
    assert branch.name == "feature"
    assert branch.upstream == "origin/feature"
    assert branch.track_status == "="
    assert branch.is_merged is True
    assert branch.is_loading is False


def test_is_git_repo() -> None:
    """Test that we can detect if we're in a git repository."""
    # We're running these tests from within a git repo
    assert is_git_repo() is True


def test_is_git_repo_failure() -> None:
    """Test that we can detect when not in a git repository."""
    mock_result = Mock()
    mock_result.returncode = 128

    with patch("subprocess.run", return_value=mock_result):
        assert is_git_repo() is False


def test_get_current_branch() -> None:
    """Test that we can get the current branch name."""
    current = get_current_branch()
    # Should return a non-empty string
    assert isinstance(current, str)
    assert len(current) > 0


def test_get_current_branch_error() -> None:
    """Test that we handle errors when getting current branch."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to get current branch"):
            get_current_branch()


def test_get_branches_fast() -> None:
    """Test that we can get branches quickly."""
    branches = get_branches_fast()

    # Should have at least one branch (the current one)
    assert len(branches) > 0

    # Each branch should have the required fields
    for branch in branches:
        assert isinstance(branch.name, str)
        assert len(branch.name) > 0
        assert isinstance(branch.creator_date, datetime)
        assert isinstance(branch.last_commit_message, str)
        assert branch.is_loading is True
        assert branch.upstream is None or isinstance(branch.upstream, str)

    # Branches should be sorted by date (most recent first)
    for i in range(len(branches) - 1):
        assert branches[i].creator_date >= branches[i + 1].creator_date


def test_get_branches_fast_error() -> None:
    """Test that we handle errors when getting branches."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to get branches"):
            get_branches_fast()


def test_fetch_branch_metadata() -> None:
    """Test that we can fetch branch metadata."""
    # Get a real branch to test with
    branches = get_branches_fast()
    if not branches:
        pytest.skip("No branches available for testing")

    branch = branches[0]
    updated_branch = fetch_branch_metadata(branch)

    # Should return a BranchInfo with updated fields
    assert isinstance(updated_branch, BranchInfo)
    assert updated_branch.name == branch.name
    assert updated_branch.creator_date == branch.creator_date
    assert updated_branch.last_commit_message == branch.last_commit_message
    assert updated_branch.is_loading is False


def test_checkout_branch_error() -> None:
    """Test that we handle errors when checking out a branch."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error: pathspec 'nonexistent' did not match"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to checkout branch"):
            checkout_branch("nonexistent")


def test_get_base_branch_with_upstream() -> None:
    """Test detecting base branch when upstream is configured."""
    # Mock the for-each-ref call to return upstream
    mock_upstream = Mock()
    mock_upstream.returncode = 0
    mock_upstream.stdout = "origin/main"

    # Mock the rev-parse call to verify local branch exists
    mock_verify = Mock()
    mock_verify.returncode = 0

    with patch("subprocess.run", side_effect=[mock_upstream, mock_verify]):
        base = get_base_branch("feature")
        assert base == "main"


def test_get_base_branch_common_ancestor() -> None:
    """Test detecting base branch using common ancestor."""
    # Mock no upstream
    mock_no_upstream = Mock()
    mock_no_upstream.returncode = 0
    mock_no_upstream.stdout = ""

    # Mock rev-parse to say 'main' exists
    mock_main_exists = Mock()
    mock_main_exists.returncode = 0

    # Mock merge-base to say there's a common ancestor
    mock_merge_base = Mock()
    mock_merge_base.returncode = 0

    with patch("subprocess.run", side_effect=[mock_no_upstream, mock_main_exists, mock_merge_base]):
        base = get_base_branch("feature")
        assert base == "main"


def test_get_base_branch_none() -> None:
    """Test that we return None when base branch cannot be determined."""
    # Mock no upstream
    mock_no_upstream = Mock()
    mock_no_upstream.returncode = 0
    mock_no_upstream.stdout = ""

    # Mock that no common bases exist
    mock_no_branch = Mock()
    mock_no_branch.returncode = 1

    with patch("subprocess.run", side_effect=[mock_no_upstream] + [mock_no_branch] * 4):
        base = get_base_branch("orphan")
        assert base is None


def test_rebase_to_branch_error() -> None:
    """Test that we handle errors when rebasing to a branch."""
    # Mock successful checkout
    mock_checkout = Mock()
    mock_checkout.returncode = 0

    # Mock failed rebase
    mock_rebase = Mock()
    mock_rebase.returncode = 1
    mock_rebase.stderr = "fatal: conflict"

    with patch("hop.git.get_base_branch", return_value="main"):
        with patch("subprocess.run", side_effect=[mock_checkout, mock_rebase]):
            with pytest.raises(RuntimeError, match="Failed to rebase to main"):
                rebase_to_branch("feature")


def test_delete_branch_error() -> None:
    """Test that we handle errors when deleting a branch."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error: branch 'main' not found"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to delete branch"):
            delete_branch("main")


def test_get_branches_fast_empty_output() -> None:
    """Test that we handle empty git output."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result):
        branches = get_branches_fast()
        assert branches == []


def test_get_branches_fast_malformed_line() -> None:
    """Test that we skip malformed lines in git output."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "main|2025-01-01|Initial commit\ninvalid_line\n"

    with patch("subprocess.run", return_value=mock_result):
        branches = get_branches_fast()
        # Should only get the valid branch
        assert len(branches) == 1
        assert branches[0].name == "main"


def test_fetch_branch_metadata_no_upstream() -> None:
    """Test fetching metadata for a branch with no upstream."""
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


def test_fetch_branch_metadata_with_upstream() -> None:
    """Test fetching metadata for a branch with upstream."""
    branch = BranchInfo(
        name="feature",
        creator_date=datetime.now(),
        last_commit_message="Feature commit",
    )

    # Mock the for-each-ref call
    mock_for_each_ref = Mock()
    mock_for_each_ref.returncode = 0
    mock_for_each_ref.stdout = "origin/feature|="

    # Mock the merge-base call
    mock_merge_base = Mock()
    mock_merge_base.returncode = 0

    with patch("subprocess.run", side_effect=[mock_for_each_ref, mock_merge_base]):
        updated = fetch_branch_metadata(branch)
        assert updated.upstream == "origin/feature"
        assert updated.track_status == "="
        assert updated.is_merged is True
        assert updated.is_loading is False


def test_fetch_branch_metadata_not_merged() -> None:
    """Test fetching metadata for a branch not merged to upstream."""
    branch = BranchInfo(
        name="feature",
        creator_date=datetime.now(),
        last_commit_message="Feature commit",
    )

    # Mock the for-each-ref call
    mock_for_each_ref = Mock()
    mock_for_each_ref.returncode = 0
    mock_for_each_ref.stdout = "origin/feature|>"

    # Mock the merge-base call (non-zero means not merged)
    mock_merge_base = Mock()
    mock_merge_base.returncode = 1

    with patch("subprocess.run", side_effect=[mock_for_each_ref, mock_merge_base]):
        updated = fetch_branch_metadata(branch)
        assert updated.upstream == "origin/feature"
        assert updated.track_status == ">"
        assert updated.is_merged is False
        assert updated.is_loading is False


def test_checkout_branch_success() -> None:
    """Test successful branch checkout."""
    mock_result = Mock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        # Should not raise an exception
        checkout_branch("main")


def test_rebase_to_branch_success() -> None:
    """Test successful rebase to branch."""
    # Mock successful operations
    mock_success = Mock()
    mock_success.returncode = 0

    with patch("hop.git.get_base_branch", return_value="main"):
        with patch("subprocess.run", side_effect=[mock_success, mock_success]):
            # Should not raise an exception
            rebase_to_branch("feature")


def test_rebase_to_branch_no_base() -> None:
    """Test that we handle the case when base branch cannot be determined."""
    with patch("hop.git.get_base_branch", return_value=None):
        with pytest.raises(RuntimeError, match="Cannot determine base branch"):
            rebase_to_branch("orphan")


def test_delete_branch_success() -> None:
    """Test successful branch deletion."""
    mock_current = Mock()
    mock_current.returncode = 0
    mock_current.stdout = "main"

    mock_delete = Mock()
    mock_delete.returncode = 0

    with patch("subprocess.run", side_effect=[mock_current, mock_delete]):
        # Should not raise an exception
        delete_branch("feature")


def test_delete_current_branch() -> None:
    """Test that we cannot delete the current branch."""
    with patch("hop.git.get_current_branch", return_value="main"):
        with pytest.raises(RuntimeError, match="Cannot delete the currently checked out branch"):
            delete_branch("main")


def test_create_branch_success() -> None:
    """Test successful branch creation without checkout."""
    # Mock successful branch creation
    mock_create = Mock()
    mock_create.returncode = 0

    with patch("subprocess.run", return_value=mock_create):
        # Should not raise an exception
        create_branch("main", "new-feature")


def test_create_branch_empty_name() -> None:
    """Test that we handle empty branch names."""
    with pytest.raises(RuntimeError, match="Branch name cannot be empty"):
        create_branch("main", "")


def test_create_branch_whitespace_name() -> None:
    """Test that we handle whitespace-only branch names."""
    with pytest.raises(RuntimeError, match="Branch name cannot be empty"):
        create_branch("main", "   ")


def test_create_branch_creation_error() -> None:
    """Test that we handle errors when creating a branch."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: branch already exists"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="Failed to create branch"):
            create_branch("main", "existing-branch")
