"""Test doubles for hop."""

from datetime import datetime

from hop.git import BranchInfo


class FakeGitClient:
    """In-memory GitClient for tests.

    Records calls and supports preset errors per method. Tests assert on
    the fake's observable state instead of patching hop.git internals.
    """

    def __init__(
        self,
        branches: list[BranchInfo] | None = None,
        current_branch: str = "main",
        *,
        is_repo: bool = True,
    ) -> None:
        self._branches: list[BranchInfo] = list(branches) if branches else []
        self._current_branch = current_branch
        self._is_repo = is_repo

        self.checkout_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.rebase_calls: list[str] = []
        self.create_calls: list[tuple[str, str]] = []

        self.get_branches_error: Exception | None = None
        self.checkout_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.rebase_error: Exception | None = None
        self.create_error: Exception | None = None
        self.base_branch: str | None = "main"

    def is_git_repo(self) -> bool:
        return self._is_repo

    def get_current_branch(self) -> str:
        return self._current_branch

    def get_branches_fast(self) -> list[BranchInfo]:
        if self.get_branches_error is not None:
            raise self.get_branches_error
        return list(self._branches)

    def fetch_branch_metadata(self, branch: BranchInfo) -> BranchInfo:
        return BranchInfo(
            name=branch.name,
            creator_date=branch.creator_date,
            last_commit_message=branch.last_commit_message,
            upstream=branch.upstream,
            track_status=branch.track_status,
            is_merged=branch.is_merged,
            is_loading=False,
        )

    def checkout_branch(self, branch_name: str) -> None:
        self.checkout_calls.append(branch_name)
        if self.checkout_error is not None:
            raise self.checkout_error
        self._current_branch = branch_name

    def get_base_branch(self, branch_name: str) -> str | None:
        return self.base_branch

    def rebase_to_branch(self, branch_name: str) -> None:
        self.rebase_calls.append(branch_name)
        if self.rebase_error is not None:
            raise self.rebase_error

    def delete_branch(self, branch_name: str) -> None:
        self.delete_calls.append(branch_name)
        if self.delete_error is not None:
            raise self.delete_error
        self._branches = [b for b in self._branches if b.name != branch_name]

    def create_branch(self, source_branch: str, new_branch_name: str) -> None:
        self.create_calls.append((source_branch, new_branch_name))
        if self.create_error is not None:
            raise self.create_error
        self._branches.append(
            BranchInfo(
                name=new_branch_name,
                creator_date=datetime.now(),
                last_commit_message="",
            )
        )
