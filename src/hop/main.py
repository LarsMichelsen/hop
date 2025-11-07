"""Main entry point for hop."""

from hop.git import get_branches_fast
from hop.ui import run_interactive_ui


def main() -> None:
    """Main entry point for the hop CLI."""
    branches = get_branches_fast()
    run_interactive_ui(branches)


if __name__ == "__main__":
    main()
