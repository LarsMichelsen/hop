# hop

Git branch management tool for quick branch hopping.

## Features

- Interactive text-based UI for browsing git branches
- List branches ordered by last commit date
- Show branch info: date, sync status, name, and last commit message
- Quick actions: checkout, rebase, delete, or create branches
- Shows upstream branch and merge status
- Vim-style navigation (arrow keys or j/k)

## Installation

Requires Python 3.12 or newer.

```bash
# As a standalone CLI tool
uv tool install .

# Or with pip
pip install .
```

## Usage

```bash
hop
```

### Controls

- `↑`/`↓` or `j`/`k` - Navigate branches
- `c` - Checkout selected branch
- `r` - Rebase selected branch onto its base
- `n` - Create new branch from selected branch
- `d` - Delete selected branch
- `h` - Show help screen
- `q` - Quit

## Development

```bash
# Install dependencies
uv sync

# Run the tool
uv run hop
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development workflow and pre-commit checks.
