"""Main entry point for hop."""

import argparse
import sys

from hop import __version__
from hop.git import GitClient, SubprocessGitClient
from hop.ui import run_interactive_ui


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hop",
        description="Helper for quick git branch hopping.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, client: GitClient | None = None) -> None:
    # --help / --version are handled here by argparse, which exits before we
    # touch git — so they work outside a repository too.
    _parse_args(argv)

    if client is None:
        client = SubprocessGitClient()

    if not client.is_git_repo():
        print("Error: Not a git repository", file=sys.stderr)
        sys.exit(1)

    try:
        branches = client.get_branches_fast()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not branches:
        print("No branches found", file=sys.stderr)
        sys.exit(1)

    try:
        run_interactive_ui(branches, client)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
