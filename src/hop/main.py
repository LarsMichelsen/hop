"""Main entry point for hop."""

import sys

from hop.git import GitClient, SubprocessGitClient
from hop.ui import run_interactive_ui


def main(client: GitClient | None = None) -> None:
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
