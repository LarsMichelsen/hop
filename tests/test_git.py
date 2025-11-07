"""Tests for git module."""

from hop.git import BranchInfo


def test_branch_info_creation() -> None:
    """Test that BranchInfo can be created with required fields."""
    from datetime import datetime

    branch = BranchInfo(
        name="main",
        last_commit_date=datetime.now(),
        last_commit_message="Initial commit",
        upstream=None,
        is_merged=False,
    )
    assert branch.name == "main"
