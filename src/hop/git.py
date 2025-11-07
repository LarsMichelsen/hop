"""Git operations for hop."""

import subprocess
from dataclasses import dataclass
from datetime import datetime


def get_current_branch() -> str:
    """Get the name of the currently checked out branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to get current branch: {result.stderr}")

    return result.stdout.strip()


def is_git_repo() -> bool:
    """Check if the current directory is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


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
    result = subprocess.run(
        [
            "git",
            "for-each-ref",
            "refs/heads/",
            "--sort=-creatordate",
            "--format=%(refname:short)|%(creatordate:short)|%(contents:subject)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to get branches: {result.stderr}")

    branches: list[BranchInfo] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue

        name, date_str, message = parts
        # Parse YYYY-MM-DD format
        date = datetime.strptime(date_str, "%Y-%m-%d")

        branches.append(
            BranchInfo(
                name=name,
                creator_date=date,
                last_commit_message=message,
                is_loading=True,
            )
        )

    return branches


def fetch_branch_metadata(branch: BranchInfo) -> BranchInfo:
    """Fetch upstream and merge status for a branch.

    This is an expensive operation (requires git commands per branch).
    Call this async for each branch after displaying the initial list.

    Returns a new BranchInfo with updated upstream, is_merged, and is_loading fields.
    """
    # Get upstream and track status
    result = subprocess.run(
        [
            "git",
            "for-each-ref",
            f"refs/heads/{branch.name}",
            "--format=%(upstream:short)|%(upstream:trackshort)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    upstream = None
    track_status = ""

    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split("|")
        if len(parts) >= 1:
            upstream = parts[0] if parts[0] else None
        if len(parts) >= 2:
            track_status = parts[1]

    # Check if merged to upstream
    is_merged = False
    if upstream:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", branch.name, upstream],
            capture_output=True,
            check=False,
        )
        is_merged = result.returncode == 0

    return BranchInfo(
        name=branch.name,
        creator_date=branch.creator_date,
        last_commit_message=branch.last_commit_message,
        upstream=upstream,
        track_status=track_status,
        is_merged=is_merged,
        is_loading=False,
    )


def checkout_branch(branch_name: str) -> None:
    """Checkout the specified branch."""
    result = subprocess.run(
        ["git", "checkout", branch_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to checkout branch: {result.stderr}")


def rebase_to_branch(branch_name: str) -> None:
    """Rebase current branch to the specified branch."""
    result = subprocess.run(
        ["git", "rebase", branch_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to rebase to branch: {result.stderr}")


def delete_branch(branch_name: str) -> None:
    """Delete the specified branch."""
    result = subprocess.run(
        ["git", "branch", "-d", branch_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to delete branch: {result.stderr}")
