"""Git operations for hop."""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class BranchInfo:
    name: str
    creator_date: datetime
    last_commit_message: str
    upstream: str | None = None
    track_status: str = ""  # one of: "=", "<", ">", "<>", ""
    is_merged: bool = False
    is_loading: bool = True


class GitClient(Protocol):
    """Boundary between hop and the local git installation.

    Injected into HopApp and main() so tests can supply a fake without
    patching hop.git internals.
    """

    def is_git_repo(self) -> bool: ...
    def get_current_branch(self) -> str: ...
    def get_branches_fast(self) -> list[BranchInfo]: ...
    def fetch_branch_metadata(self, branch: BranchInfo) -> BranchInfo: ...
    def checkout_branch(self, branch_name: str) -> None: ...
    def get_base_branch(self, branch_name: str) -> str | None: ...
    def rebase_to_branch(self, branch_name: str) -> None: ...
    def delete_branch(self, branch_name: str) -> None: ...
    def create_branch(self, source_branch: str, new_branch_name: str) -> None: ...


class SubprocessGitClient:
    """Default GitClient: shells out to the `git` binary."""

    def is_git_repo(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def get_current_branch(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to get current branch: {result.stderr}")

        return result.stdout.strip()

    def get_branches_fast(self) -> list[BranchInfo]:
        """Get list of local branches with basic information only.

        Returns immediately with branch name, date, and last commit message.
        Call fetch_branch_metadata for upstream and merge status.
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

    def fetch_branch_metadata(self, branch: BranchInfo) -> BranchInfo:
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

    def checkout_branch(self, branch_name: str) -> None:
        result = subprocess.run(
            ["git", "checkout", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout branch: {result.stderr}")

    def get_base_branch(self, branch_name: str) -> str | None:
        """Detect the base/upstream branch of the given branch.

        1. Use configured upstream if available
        2. Find best common ancestor with main/master/develop
        3. Return None if cannot determine
        """
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
                if "/" in upstream:
                    local_branch = upstream.split("/", 1)[1]
                    check_result = subprocess.run(
                        ["git", "rev-parse", "--verify", f"refs/heads/{local_branch}"],
                        capture_output=True,
                        check=False,
                    )
                    if check_result.returncode == 0:
                        return local_branch
                return upstream

        common_bases = ["main", "master", "develop", "development"]

        for base in common_bases:
            if base == branch_name:
                continue

            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{base}"],
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                continue

            result = subprocess.run(
                ["git", "merge-base", base, branch_name],
                capture_output=True,
                check=False,
            )

            if result.returncode == 0:
                return base

        return None

    def rebase_to_branch(self, branch_name: str) -> None:
        """Check out branch_name and rebase it onto its detected base branch."""
        base_branch = self.get_base_branch(branch_name)

        if base_branch is None:
            raise RuntimeError(
                f"Cannot determine base branch for '{branch_name}'. "
                "Please set an upstream branch or ensure the branch was created from main/master."
            )

        result = subprocess.run(
            ["git", "checkout", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout branch: {result.stderr}")

        result = subprocess.run(
            ["git", "rebase", base_branch],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to rebase to {base_branch}: {result.stderr}")

    def delete_branch(self, branch_name: str) -> None:
        try:
            current = self.get_current_branch()
        except RuntimeError:
            pass
        else:
            if current == branch_name:
                raise RuntimeError(
                    f"Cannot delete the currently checked out branch '{branch_name}'. "
                    "Please checkout another branch first."
                )

        result = subprocess.run(
            ["git", "branch", "-D", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to delete branch: {result.stderr}")

    def create_branch(self, source_branch: str, new_branch_name: str) -> None:
        if not new_branch_name or not new_branch_name.strip():
            raise RuntimeError("Branch name cannot be empty")

        new_branch_name = new_branch_name.strip()

        result = subprocess.run(
            ["git", "branch", new_branch_name, source_branch],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create branch: {result.stderr.strip()}")


# Module-level functions delegate to a default SubprocessGitClient.
# Kept for backwards compatibility with existing call sites and tests that
# patch subprocess.run; new code should accept a GitClient via DI.
_default_client = SubprocessGitClient()


def is_git_repo() -> bool:
    return _default_client.is_git_repo()


def get_current_branch() -> str:
    return _default_client.get_current_branch()


def get_branches_fast() -> list[BranchInfo]:
    return _default_client.get_branches_fast()


def fetch_branch_metadata(branch: BranchInfo) -> BranchInfo:
    return _default_client.fetch_branch_metadata(branch)


def checkout_branch(branch_name: str) -> None:
    _default_client.checkout_branch(branch_name)


def get_base_branch(branch_name: str) -> str | None:
    return _default_client.get_base_branch(branch_name)


def rebase_to_branch(branch_name: str) -> None:
    _default_client.rebase_to_branch(branch_name)


def delete_branch(branch_name: str) -> None:
    _default_client.delete_branch(branch_name)


def create_branch(source_branch: str, new_branch_name: str) -> None:
    _default_client.create_branch(source_branch, new_branch_name)
