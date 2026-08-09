# hop

[![CI](https://github.com/LarsMichelsen/hop/actions/workflows/ci.yml/badge.svg)](https://github.com/LarsMichelsen/hop/actions/workflows/ci.yml)

Helper for quick git branch hopping.

When you live in short-lived feature branches, switching between them with `git checkout` means
remembering names and typing them out. `hop` shows the branches you've touched most recently at the
top, so the one you want is almost always a keystroke away.

<!-- Absolute URLs: PyPI renders this README but does not resolve relative links. -->
![hop demo](https://raw.githubusercontent.com/LarsMichelsen/hop/main/demo/demo.gif)

<sub>Recorded from a reproducible synthetic repo — see [`demo/PLAYBOOK.md`](https://github.com/LarsMichelsen/hop/blob/main/demo/PLAYBOOK.md).</sub>

## Features

- Interactive text-based UI for browsing git branches
- List branches ordered by last commit date
- Type-to-filter: `/` narrows the list as you type
- Show branch info: date, name, and last commit message
- Details line for the selected branch: commits ahead/behind its base branch
  and its upstream (e.g. `base main: +2 -5 | upstream origin/x: +1 -0`)
- Quick actions: checkout, rebase, delete, or create branches
- Shows upstream branch and merge status
- Worktree aware: branches checked out in another worktree are marked `+`
  (like `git branch`), checkout/delete of them is refused with a clear
  message, and rebase runs inside the worktree that holds them
- Vim-style navigation (arrow keys or j/k)

## Installation

Requires Python 3.12 or newer. Installation via `uv` recommended (isolated, added to PATH):

```bash
uv tool install git-hop
```

Or install the latest development state straight from the repository:

```bash
uv tool install git+https://github.com/LarsMichelsen/hop.git
```

## Updating

```bash
uv tool upgrade git-hop
```

## Usage

The package installs the command as both `hop` and a `git hop` subcommand:

```bash
hop            # launch the interactive branch browser
git hop        # the same, as a git subcommand
hop --help     # show usage and exit
hop --version  # print the version and exit
```

Note: the worktree-jumping shell wrapper below wraps `hop`; `git hop` runs
without it (everything works, jumping to another worktree just tells you the
path instead of changing into it). And as with any external git subcommand,
`git hop --help` asks git for a man page — use `hop --help` instead.

### Controls

- `↑`/`↓` or `j`/`k` - Navigate branches
- `c` or `Enter` - Checkout selected branch (or jump to its worktree, see below)
- `/` - Filter branches: type to narrow, `↑`/`↓` to pick, `Enter` to checkout, `Esc` to cancel
- `r` - Rebase selected branch onto its base
- `n` - Create new branch from selected branch
- `d` - Delete selected branch
- `t` - Cycle theme (dark/light, then back to the startup theme)
- `h` - Show help screen
- `q` - Quit

### Shell integration: jump between worktrees

Branches checked out in another worktree are marked `+`. Pressing `c` on one
jumps to that worktree — but `hop` runs as a child process and cannot change
your shell's working directory by itself. Add this wrapper to your
`~/.bashrc` / `~/.zshrc`:

```bash
hop() {
    local tmp target
    tmp="$(mktemp)"
    command hop --cd-file "$tmp" "$@"
    target="$(cat "$tmp")"
    rm -f "$tmp"
    if [ -n "$target" ] && [ "$target" != "$PWD" ]; then
        cd "$target" || return
    fi
}
```

Or for fish (`~/.config/fish/config.fish`):

```fish
function hop
    set -l tmp (mktemp)
    command hop --cd-file $tmp $argv
    set -l target (cat $tmp)
    rm -f $tmp
    if test -n "$target" -a "$target" != "$PWD"
        cd $target
    end
end
```

Without the wrapper everything else still works; pressing `c` on a `+` branch
then shows where the branch lives instead of jumping.

## Configuration

`hop` reads an optional TOML file at `~/.config/hop/config.toml`. Everything in
it is optional. An absent file, section, or key falls back to the defaults
shown below. A file that exists but cannot be parsed (or contains invalid
values) is an error: `hop` refuses to start until it is fixed — or rewritten
with `hop init-config --force`. Create a documented starting point with:

```bash
hop init-config          # write ~/.config/hop/config.toml
hop init-config --force  # overwrite an existing file
```

```toml
[ui]
# Color theme. "auto" (default) honours $HOP_THEME, otherwise adapts to the
# terminal's ANSI palette. Also accepts "light", "dark", or any built-in
# Textual theme, e.g. "nord", "gruvbox", "dracula", "monokai", "tokyo-night",
# "catppuccin-mocha", "catppuccin-latte", "solarized-light", "flexoki".
theme = "auto"

[defaults]
# Prefix pre-filled in the "new branch" dialog when the source branch has no
# entry in [branch_prefixes].
branch_prefix = ""

[branch_prefixes]
# Per-source-branch prefixes: creating a branch from one of these pre-fills the
# input with the mapped prefix. Quote names containing dots or slashes —
# unquoted, TOML splits keys like 2.5.0 at the dots.
main = "feature/"
develop = "feat/"
# "release/v1.0" = "bugfix/"
# "2.5.0" = "bugfix/"
```

| Setting | Purpose |
| --- | --- |
| `[ui] theme` | Color theme; `"auto"` adapts to the terminal. Cycle themes at runtime with `t` (always returns to the configured theme). |
| `[defaults] branch_prefix` | Default prefix for new branch names. |
| `[branch_prefixes]` | Prefix overrides keyed by the source branch you create from. |

## Development

```bash
# Install dependencies
uv sync

# Run the tool
uv run hop
```

See [docs/DEVELOPMENT.md](https://github.com/LarsMichelsen/hop/blob/main/docs/DEVELOPMENT.md) for development workflow and pre-commit checks.

## License

[Apache License 2.0](https://github.com/LarsMichelsen/hop/blob/main/LICENSE.md) © Lars Michelsen
