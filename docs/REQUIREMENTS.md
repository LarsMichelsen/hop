# Requirements

## Project Name

**hop** - Git branch management tool for quick branch hopping

## Features

* Displaying
    * List local branches ordered by creator date (descending), showing:
        * Date (YYYY-MM-DD format)
        * Track status indicator (2 chars wide):
            * `=` branch is equal to upstream
            * `<` branch is behind upstream
            * `>` branch is ahead of upstream
            * `<>` branch has diverged from upstream
            * Empty if no upstream
        * Branch name (left-aligned, ~40 chars)
        * First line of last commit message
    * Provide the option to select a branch from the list and switch to it, rebase to it or delete it
    * For each branch find out which the upstream branch was
    * Indicate whether a branch was already merged to the upstream branch
    * Provide an interactive text-based UI for interaction
* Controls
    * Navigate the list of branches via up and down arrow keys and j and k
    * Trigger actions with "c" for checkout, "r" for rebase and "d" for delete
    * Create new branch from currently selected branch with "n" (prompts for branch name)
        * Supports configurable branch prefixes via `~/.config/hop/config.toml`
        * Prefix is pre-populated in the input field but can be edited by the user
* Performance
    * It is crucial that the command starts and shows the branch list as fast as possible for a great experience
    * In case information is expensive to compute, leave it out or make it an asynchronous computation and add it once the computation is finished
* Tech stack
    * Use Python 3.14
    * Tooling: uv for env management, pytest for testing, basedpyright for static checking
