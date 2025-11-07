"""Main entry point for hop."""

import sys

from hop.git import get_branches_fast, is_git_repo
from hop.ui import run_interactive_ui


def main() -> None:
    """Main entry point for the hop CLI."""
    # Check if we're in a git repository
    if not is_git_repo():
        print("Error: Not a git repository", file=sys.stderr)
        sys.exit(1)

    # Get branches
    try:
        branches = get_branches_fast()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if there are any branches
    if not branches:
        print("No branches found", file=sys.stderr)
        sys.exit(1)

    # Run the UI
    try:
        run_interactive_ui(branches)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
