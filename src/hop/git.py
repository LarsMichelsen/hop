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


def get_base_branch(branch_name: str) -> str | None:
    """Detect the base/upstream branch of the given branch.

    Tries multiple strategies to find the base branch:
    1. Use configured upstream if available
    2. Find best common ancestor with main/master/develop
    3. Return None if cannot determine

    Args:
        branch_name: Name of the branch to find the base for

    Returns:
        Name of the base branch, or None if cannot determine
    """
    # Strategy 1: Check for configured upstream
    result = subprocess.run(
        [
            "git",
            "for-each-ref",
            f"refs/heads/{branch_name}",
            "--format=%(upstream:short)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0 and result.stdout.strip():
        upstream = result.stdout.strip()
        if upstream:
            # Extract branch name from upstream (e.g., "origin/main" -> "main")
            # Try to find local branch corresponding to upstream
            if "/" in upstream:
                local_branch = upstream.split("/", 1)[1]
                # Check if local branch exists
                check_result = subprocess.run(
                    ["git", "rev-parse", "--verify", f"refs/heads/{local_branch}"],
                    capture_output=True,
                    check=False,
                )
                if check_result.returncode == 0:
                    return local_branch
            return upstream

    # Strategy 2: Try common base branches
    common_bases = ["main", "master", "develop", "development"]

    for base in common_bases:
        # Skip if checking against itself
        if base == branch_name:
            continue

        # Check if base branch exists
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{base}"],
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            continue

        # Check if there's a merge-base (common ancestor)
        result = subprocess.run(
            ["git", "merge-base", base, branch_name],
            capture_output=True,
            check=False,
        )

        if result.returncode == 0:
            # Found a common ancestor, this is likely the base branch
            return base

    # Could not determine base branch
    return None


def rebase_to_branch(branch_name: str) -> None:
    """Rebase the selected branch to its upstream/base branch.

    This function:
    1. Detects the base/upstream branch of the selected branch
    2. Checks out the selected branch
    3. Rebases it to its base branch

    Example: If branch 'feature' was branched from 'main' with 3 commits,
    this will execute: git checkout feature && git rebase main

    Args:
        branch_name: Name of the branch to rebase

    Raises:
        RuntimeError: If rebase fails or base branch cannot be determined
    """
    # First, detect the base branch
    base_branch = get_base_branch(branch_name)

    if base_branch is None:
        raise RuntimeError(
            f"Cannot determine base branch for '{branch_name}'. "
            "Please set an upstream branch or ensure the branch was created from main/master."
        )

    # Checkout the branch
    result = subprocess.run(
        ["git", "checkout", branch_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to checkout branch: {result.stderr}")

    # Rebase to the base branch
    result = subprocess.run(
        ["git", "rebase", base_branch],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to rebase to {base_branch}: {result.stderr}")


def delete_branch(branch_name: str) -> None:
    """Delete the specified branch (force delete).

    Uses git branch -D to force delete the branch, regardless of merge status.
    This suppresses the "not fully merged" error.

    Args:
        branch_name: Name of the branch to delete

    Raises:
        RuntimeError: If deletion fails (e.g., trying to delete current branch)
    """
    # Check if trying to delete the current branch
    try:
        current = get_current_branch()
    except RuntimeError:
        # If we can't get current branch, let git handle the error
        pass
    else:
        if current == branch_name:
            raise RuntimeError(
                f"Cannot delete the currently checked out branch '{branch_name}'. "
                "Please checkout another branch first."
            )

    # Use -D (force delete) instead of -d (safe delete)
    # This allows deleting branches that aren't fully merged
    result = subprocess.run(
        ["git", "branch", "-D", branch_name],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to delete branch: {result.stderr}")


def create_branch(source_branch: str, new_branch_name: str) -> None:
    """Create a new branch from the source branch without checking it out.

    Args:
        source_branch: Name of the branch to use as the starting point
        new_branch_name: Name for the new branch

    Raises:
        RuntimeError: If branch creation fails
    """
    # Validate branch name (basic validation - let git handle detailed validation)
    if not new_branch_name or not new_branch_name.strip():
        raise RuntimeError("Branch name cannot be empty")

    new_branch_name = new_branch_name.strip()

    # Create the new branch from the source branch
    result = subprocess.run(
        ["git", "branch", new_branch_name, source_branch],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create branch: {result.stderr.strip()}")
