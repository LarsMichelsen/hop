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

### Quick Start

```bash
# Install dependencies
uv sync

# Run the tool
uv run hop
```

### Development Workflow

**Before every commit, run all checks:**

```bash
# Format code
uv run ruff format

# Lint and fix issues
uv run ruff check --fix

# Type check (strict mode)
uv run basedpyright

# Run tests
uv run pytest
```

Or run all at once:
```bash
uv run ruff format && uv run ruff check --fix && uv run basedpyright && uv run pytest
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed development workflow.
