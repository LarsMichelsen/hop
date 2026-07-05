"""Main entry point for hop."""

import argparse
import sys

from hop import __version__
from hop.config import install_example_config
from hop.git import GitClient, SubprocessGitClient
from hop.ui import run_interactive_ui


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hop",
        description="Helper for quick git branch hopping.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="write an example config to the default location and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="with --init-config, overwrite an existing config file",
    )
    return parser.parse_args(argv)


def _init_config(force: bool) -> None:
    try:
        path = install_example_config(force=force)
    except FileExistsError as e:
        print(f"Config already exists at {e}. Re-run with --force to overwrite.", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote example config to {path}")


def main(argv: list[str] | None = None, client: GitClient | None = None) -> None:
    # --help / --version / --init-config are handled here, before we touch git,
    # so they work outside a repository too.
    args = _parse_args(argv)

    if args.init_config:
        _init_config(args.force)
        return

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
