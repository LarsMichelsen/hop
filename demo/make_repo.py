"""Build a deterministic synthetic git repository for the hop demo.

Created from scratch every time with fixed identities, dates and a local bare
"origin", so `hop` shows a stable set of branches that exercise every upstream
state:

    =   synced      <   behind      >   ahead      <>  diverged      (none)

`main` is given the most recent date so it sorts to the top of hop's list (hop
orders by last-commit date), which keeps the demo's "branch off main" and
"switch back to main" steps a single keystroke away. Local user.name/email are
configured so the demo's own `git commit` works without extra setup.

Run standalone to inspect it:

    uv run python demo/make_repo.py /tmp/hop-demo && cd /tmp/hop-demo && hop
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_NAME, _EMAIL = "Ada Hopper", "ada@example.com"

# Isolate from the machine's global/system git config for reproducibility.
_BASE_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": _NAME,
    "GIT_AUTHOR_EMAIL": _EMAIL,
    "GIT_COMMITTER_NAME": _NAME,
    "GIT_COMMITTER_EMAIL": _EMAIL,
    "GIT_TERMINAL_PROMPT": "0",
}


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = dict(_BASE_ENV)
    if date is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
        env=env,
        check=True,
        capture_output=True,
    )


def _commit(repo: Path, message: str, date: str, *, filename: str = "work.txt") -> None:
    (repo / filename).open("a", encoding="utf-8").write(message + "\n")
    _git(repo, "add", filename)
    _git(repo, "commit", "-m", message, date=date)


def build(target: Path) -> Path:
    """Create the synthetic repo at ``target`` (removed first if it exists)."""
    target = target.resolve()
    subprocess.run(["rm", "-rf", str(target)], check=True)
    target.mkdir(parents=True)

    origin = target.with_name(target.name + ".origin.git")
    subprocess.run(["rm", "-rf", str(origin)], check=True)
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True
    )

    _git(target, "init", "-b", "main")
    # Local identity so the demo's own `git commit` works with no global config.
    _git(target, "config", "user.name", _NAME)
    _git(target, "config", "user.email", _EMAIL)

    _commit(target, "Initial project skeleton", "2026-05-02T09:00:00")
    _git(target, "remote", "add", "origin", str(origin))
    _git(target, "push", "-u", "origin", "main")

    # feature/init-config: ahead (>) — pushed, then one extra local commit.
    _git(target, "checkout", "-b", "feature/init-config", "main")
    _commit(target, "Add `hop --init-config` command", "2026-05-06T14:10:00")
    _git(target, "push", "-u", "origin", "feature/init-config")
    _commit(target, "Ship the example config inside the package", "2026-05-07T11:30:00")

    # fix/dialog-border: behind (<) — push two, then rewind local by one.
    _git(target, "checkout", "-b", "fix/dialog-border", "main")
    _commit(target, "Reproduce the delete-dialog border glitch", "2026-05-10T08:05:00")
    _git(target, "push", "-u", "origin", "fix/dialog-border")
    _commit(target, "Drop the width-ambiguous warning emoji", "2026-05-11T16:45:00")
    _git(target, "push", "origin", "fix/dialog-border")
    _git(target, "reset", "--hard", "HEAD~1")

    # feature/theme-support: diverged (<>) — local and origin each have a commit
    # the other lacks.
    _git(target, "checkout", "-b", "feature/theme-support", "main")
    _commit(target, "Adapt the UI theme to the terminal palette", "2026-05-14T10:20:00")
    _git(target, "push", "-u", "origin", "feature/theme-support")
    _commit(target, "Pair the cursor row color with its background", "2026-05-15T13:15:00")
    _git(target, "push", "origin", "feature/theme-support")
    _git(target, "reset", "--hard", "HEAD~1")
    _commit(target, "Rework the block-cursor colors instead", "2026-05-16T09:40:00")

    # experiment/rebase-flow: no upstream ("").
    _git(target, "checkout", "-b", "experiment/rebase-flow", "main")
    _commit(target, "Prototype an interactive rebase view", "2026-05-20T15:55:00")

    # Advance main last so it is the most recently dated branch (top of the
    # list) and still synced with origin.
    _git(target, "checkout", "main")
    _commit(target, "Update project metadata", "2026-05-24T12:00:00")
    _git(target, "push", "origin", "main")

    return target


def main(argv: list[str]) -> None:
    target = Path(argv[1]) if len(argv) > 1 else Path("/tmp/hop-demo")
    build(target)
    print(f"Synthetic demo repo ready at {target}")


if __name__ == "__main__":
    main(sys.argv)
