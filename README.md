# hop

Git branch management tool for quick branch hopping.

## Features

- Interactive text-based UI for browsing git branches
- List branches ordered by last commit date
- Show branch info: date, name, and last commit message
- Quick actions: checkout, rebase, or delete branches
- Shows upstream branch and merge status
- Vim-style navigation (arrow keys or j/k)

## Installation

```bash
uv sync
```

## Usage

```bash
hop
```

### Controls

- `�`/`�` or `j`/`k` - Navigate branches
- `c` - Checkout selected branch
- `r` - Rebase to selected branch
- `d` - Delete selected branch
- `q` - Quit

## Development

```bash
# Install dependencies
uv sync

# Run the tool
uv run hop
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development workflow and pre-commit checks.
