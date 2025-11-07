"""Git operations for hop."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BranchInfo:
    """Information about a git branch.

    Supports progressive loading - basic info (name, date, message) is loaded
    immediately, while expensive info (upstream, track_status, is_merged) is loaded async.
    """

    name: str
    creator_date: datetime  # When the branch was created
    last_commit_message: str
    upstream: str | None = None  # Loaded async - upstream branch name
    track_status: str = ""  # Loaded async - one of: "=", "<", ">", "<>", ""
    is_merged: bool = False  # Loaded async - whether merged to upstream
    is_loading: bool = True  # Flag for UI to show loading state


def get_branches_fast() -> list[BranchInfo]:
    """Get list of local branches with basic information only.

    Returns immediately with branch name, date, and last commit message.
    Use fetch_branch_metadata() to load upstream and merge status async.

    Target: < 100ms even for repos with 100+ branches.
    """
    raise NotImplementedError


def fetch_branch_metadata(branch: BranchInfo) -> BranchInfo:
    """Fetch upstream and merge status for a branch.

    This is an expensive operation (requires git commands per branch).
    Call this async for each branch after displaying the initial list.

    Returns a new BranchInfo with updated upstream, is_merged, and is_loading fields.
    """
    raise NotImplementedError


def checkout_branch(branch_name: str) -> None:
    """Checkout the specified branch."""
    raise NotImplementedError


def rebase_to_branch(branch_name: str) -> None:
    """Rebase current branch to the specified branch."""
    raise NotImplementedError


def delete_branch(branch_name: str) -> None:
    """Delete the specified branch."""
    raise NotImplementedError
