# Implementation Plan for hop

**NOTE:** This plan is updated with each implementation step to track progress.

**Last Updated:** 2025-11-07 (after implementing delete confirmation)

## Project Overview

**hop** is a git branch management tool that provides an interactive text-based UI for quick branch navigation and operations.

## Architecture

The project is organized into three main modules:

1. **`hop.git`** - Git operations and data models
2. **`hop.ui`** - Interactive terminal UI
3. **`hop.main`** - Entry point and orchestration

## Current Status Summary

### ✅ Completed
- Phase 1: Git operations (fast branch retrieval, metadata loading, all operations)
- Phase 2: Interactive UI (Textual-based TUI, progressive loading, navigation, key bindings)
- Phase 3: Integration (main entry point, async coordination, comprehensive testing)
- **Rebase feature**: Correctly rebases selected branch to its upstream/base
- **Delete feature**: Conditional confirmation + current branch protection
- Test coverage: 77.68% (52 tests)

### 🚧 In Progress
- None currently

### ⏳ Pending
- Color coding for track status indicators
- Phase 4: CI/CD setup

## Performance Requirements

**Critical:** The tool must start and display the branch list as fast as possible (< 100ms for typical repos).

**Strategy:**
- **Phase 1 (Fast):** Show branch list immediately with essential info only:
  - Branch name
  - Last commit date
  - Last commit message
- **Phase 2 (Async):** Load expensive data in background and update UI progressively:
  - Upstream branch detection (requires per-branch git calls)
  - Merge status checking (requires per-branch git calls)

**Implementation approach:**
- Use a single fast `git for-each-ref` command to get basic branch data
- Return immediately to UI with partial data
- Spawn async tasks to fetch upstream/merge status per branch
- Update UI as each piece of data becomes available

## Implementation Phases

### Phase 1: Git Operations Module (`hop.git`)

**Goal:** Implement fast git operations with async support for expensive operations.

#### Data Model Updates:

Update `BranchInfo` to support progressive loading:

```python
@dataclass
class BranchInfo:
    name: str
    creator_date: datetime       # When branch was created (for sorting)
    last_commit_message: str
    upstream: str | None = None  # Loaded async - upstream branch name
    track_status: str = ""       # Loaded async - "=", "<", ">", "<>", or ""
    is_merged: bool = False      # Loaded async - merged to upstream
    is_loading: bool = True      # Flag for UI to show loading state
```

**Track Status Meanings:**
- `=` - branch is equal to upstream (same commit)
- `<` - branch is behind upstream (needs pull)
- `>` - branch is ahead of upstream (needs push)
- `<>` - branch has diverged from upstream (needs merge/rebase)
- `""` - no upstream configured

#### Tasks:

1. **Fast Branch Information Retrieval (Synchronous)** ✅ COMPLETED
   - Implement `get_branches_fast()` to return immediately with basic data
   - Use single optimized git command:
     ```
     git for-each-ref refs/heads/ \
       --sort=-creatordate \
       --format='%(refname:short)|%(creatordate:short)|%(contents:subject)'
     ```
   - Parse output: branch name, creator date (YYYY-MM-DD), commit message
   - Returns list sorted by creator date (most recent first)
   - **Target:** < 100ms even for repos with 100+ branches
   - Note: This matches the user's existing `git brv` format but without track status (loaded async)

2. **Async Upstream and Track Status Loading** ✅ COMPLETED
   - Implement `fetch_branch_metadata(branch: BranchInfo) -> BranchInfo`
   - For each branch, use git command to get upstream and track status:
     ```
     git for-each-ref refs/heads/<branch> \
       --format='%(upstream:short)|%(upstream:trackshort)'
     ```
   - Parse output to get upstream name and track status indicator
   - Track status from git: `=` (equal), `<` (behind), `>` (ahead), `<>` (diverged)
   - If upstream exists, check merge status using `git merge-base --is-ancestor <branch> <upstream>`
   - Handle branches without upstream gracefully (empty string for track_status)
   - Return updated BranchInfo with is_loading=False
   - Can be called per-branch from async context

3. **Batch Metadata Loading (Optional Optimization)** ⏭️ SKIPPED (using Textual workers instead)
   - ~~Implement `fetch_all_metadata(branches: list[BranchInfo]) -> AsyncIterator[BranchInfo]`~~
   - Using Textual's @work decorator for concurrent metadata fetching

4. **Branch Operations** ✅ COMPLETED
   - ✅ Implement `checkout_branch(name)` using `git checkout`
   - ✅ **FIXED**: `rebase_to_branch(name)` - now correctly rebases selected branch to its upstream
   - ✅ **IMPROVED**: `delete_branch(name)` - prevents deleting current branch, uses safe delete
   - ✅ Add proper error handling for each operation

5. **NEW: Detect Base/Upstream Branch** ✅ COMPLETED
   - ✅ Implement `get_base_branch(branch_name: str) -> str | None`
   - Strategies implemented:
     1. Use configured upstream if available (extracts local branch from origin/main)
     2. Find merge-base with common branches (main, master, develop, development)
     3. Returns None if cannot determine
   - Used by rebase operation

6. **FIX: Rebase Operation** ✅ COMPLETED
   - ✅ Updated `rebase_to_branch(name)` to:
     1. Detect the base/upstream branch of the selected branch
     2. Checkout the selected branch
     3. Rebase the selected branch to its base branch
   - Example: Branch `xyz` branched from `master` with 3 commits
     - Now executes: `git checkout xyz && git rebase master` ✅
     - No longer: `git rebase xyz` ❌
   - Added proper error message if base branch cannot be determined

#### Dependencies:
- Use `subprocess` module to execute git commands
- Use `subprocess.run()` with `capture_output=True` and `text=True`
- Consider `asyncio` + `ThreadPoolExecutor` for concurrent metadata fetching

#### Testing:
- Test fast branch retrieval (< 100ms target)
- Test branch parsing and sorting
- Test async metadata loading
- Test error handling for invalid branches
- Test upstream and merge status detection

---

### Phase 2: Interactive UI Module (`hop.ui`)

**Goal:** Build a fast, responsive text-based UI with progressive data loading.

#### UI Library: `textual`

**Decision:** Use `textual` for the TUI framework.

**Why `textual`:**
- Full-featured TUI framework with modern design
- Built-in async support - perfect for progressive data loading
- Reactive properties for automatic UI updates
- Rich styling and color support
- Professional-looking UI with minimal code
- Excellent documentation and active development

#### Tasks:

1. **Initial Fast Display** ✅ COMPLETED
   - Show branch list immediately with basic data (name, date, message)
   - Display format matching `git brv` output:
     ```
     YYYY-MM-DD [TS] branch-name             commit-message
     ```
     Where `[TS]` is 2-char track status (initially empty/loading)
   - Column layout:
     - Date: 10 chars (YYYY-MM-DD)
     - Track status: 2 chars right-aligned (or loading indicator)
     - Branch name: ~40 chars left-aligned
     - Commit message: remaining space
   - Highlight currently selected branch (different background/bold)
   - **Critical:** UI must render within milliseconds of receiving initial data
   - Show loading indicator in track status column until async data arrives

2. **Progressive Data Loading** ✅ COMPLETED
   - Show loading indicators for track status initially (e.g., `··` or `--`)
   - Update individual rows as metadata becomes available
   - Use reactive properties to automatically refresh display
   - Smooth transitions - no jarring redraws

3. **Branch Status Display with Color** ⏳ PENDING
   - Track status indicators with semantic colors:
     - `=` in green (synced with upstream)
     - `<` in yellow (behind, needs pull)
     - `>` in cyan (ahead, needs push)
     - `<>` in red (diverged, needs attention)
   - Highlight merged branches with dimmer/gray text
   - Current branch in bold or different color
   - Use subtle visual cues for loading state

4. **Additional "Awesome" Features** ⏳ FUTURE
   - Show total branch count and loading progress at top
   - Filter/search branches by typing (optional future enhancement)
   - Show tooltips with full upstream branch name on hover/selection
   - Visual feedback for actions (smooth transitions)
   - Maybe show ahead/behind commit counts when available

5. **Navigation** ✅ COMPLETED
   - Implement arrow key navigation (↑/↓)
   - Implement vim-style navigation (j/k)
   - Handle scrolling for long branch lists
   - Navigation should work immediately, even while data loads

6. **Actions** ✅ COMPLETED
   - ✅ Bind `c` key to checkout action
   - ✅ Bind `r` key to rebase action (FIXED - now uses upstream)
   - ✅ Bind `d` key to delete action with conditional confirmation
   - ✅ Bind `q` key to quit
   - ✅ Conditional confirmation for delete (only when branch differs from upstream)

7. **Status Display** ✅ COMPLETED
   - Show current branch indicator
   - Show action feedback (success/error messages)
   - Display count of branches still loading metadata

#### Testing:
- Test fast initial render (< 100ms)
- Test progressive updates as data loads
- Test keyboard event handling during data loading
- Test rendering of branch list with partial data
- Test action binding and execution
- Manual testing for UX and perceived performance

---

### Phase 3: Integration & Polish

**Goal:** Connect all modules with async data flow and refine the user experience.

#### Tasks:

1. **Main Entry Point with Async Flow** ✅ COMPLETED
   - Initial load: `get_branches_fast()` → display immediately in UI
   - Background task: spawn async metadata loading
   - Update UI progressively as metadata arrives
   - Handle errors gracefully (not in git repo, no branches, etc.)
   - Add command-line argument parsing if needed (e.g., `--help`)

2. **Async Coordination** ✅ COMPLETED
   - Set up async event loop (textual handles this)
   - Spawn metadata fetching tasks in background
   - Update UI state as each branch's metadata completes
   - Handle cancellation if user quits during loading

3. **Error Handling** ✅ COMPLETED
   - Check if current directory is a git repository
   - Handle git command failures gracefully
   - Show user-friendly error messages
   - Handle errors in async metadata loading (don't crash, just mark as unavailable)

4. **Edge Cases** ✅ COMPLETED
   - Handle repository with no branches
   - Handle repository with only one branch
   - Handle detached HEAD state
   - Handle branches being deleted externally during session
   - Handle slow git commands (show progress)

5. **Performance Validation** ✅ COMPLETED
   - Measure time to first paint (target: < 100ms)
   - Test with large repos (100+ branches)
   - Profile async metadata loading
   - Ensure UI stays responsive during background loading
   - Consider limiting concurrent git operations

6. **Documentation** ✅ COMPLETED
   - Update README with installation instructions
   - Add usage examples
   - Document keyboard shortcuts
   - Document performance characteristics

#### Testing:
- End-to-end testing with real git repositories
- Test with various repository states and sizes
- Test async loading behavior
- Test error scenarios
- Performance testing (startup time, large repos)

---

### Phase 4: CI/CD & Distribution

**Goal:** Set up automated testing and prepare for distribution.

#### Tasks:

1. **GitHub Actions**
   - Set up pytest workflow
   - Set up basedpyright type checking
   - Run on multiple Python versions (if compatible)

2. **Package Distribution**
   - Test installation via `uv`
   - Consider publishing to PyPI
   - Create release workflow

---

## Technical Decisions

### Git Command Execution

Use `subprocess.run()` with the following pattern:

```python
result = subprocess.run(
    ["git", "command", "args"],
    capture_output=True,
    text=True,
    check=False,  # Handle errors manually
)
if result.returncode != 0:
    # Handle error
```

### Data Flow

**Fast Path (Synchronous):**
```
main() → get_branches_fast() → [BranchInfo] (partial) → run_interactive_ui() → immediate display
                                                             ↓
                                                      user can navigate
```

**Async Path (Background):**
```
run_interactive_ui() → spawn_metadata_tasks() → fetch_branch_metadata() → update BranchInfo
                                                          ↓
                                                  UI auto-updates as data arrives
```

**User Actions:**
```
UI key press → checkout_branch() / rebase_to_branch() / delete_branch() → git operations
```

### UI Library

Using `textual` for the TUI framework - provides async support, reactive updates, and modern styling.

---

## Success Criteria

- [x] **Performance:** Displays branch list in < 100ms for typical repos
- [x] **Performance:** UI is immediately interactive, even while data loads
- [x] Lists all local branches sorted by commit date
- [x] Shows branch name, date, and last commit message immediately
- [x] Progressively loads and displays upstream branch for each branch
- [x] Progressively loads and indicates merged branches
- [x] Supports navigation with arrow keys and j/k
- [x] Can checkout branch with `c`
- [x] Can rebase with `r` - **COMPLETED: Now rebases selected branch to its upstream**
- [x] Can delete branch with `d` with conditional confirmation
- [x] Handles errors gracefully
- [x] All tests pass (52 tests, 77.68% coverage)
- [x] Type checking passes (strict mode)
- [x] Works in real-world git repositories
- [x] Smooth UX with loading indicators for async data
- [x] Conditional confirmation for delete (only when differs from upstream)
- [ ] Color-coded track status indicators - PENDING

---

## Timeline Estimate

- Phase 1: Git Operations - 3-4 hours
- Phase 2: Interactive UI - 4-5 hours
- Phase 3: Integration - 2-3 hours
- Phase 4: CI/CD - 1-2 hours

**Total: ~10-14 hours of development**

---

## Next Steps

**Current Priority:**
1. ⏳ Add color coding for track status indicators
2. ⏳ Phase 4: CI/CD setup (GitHub Actions, PyPI distribution)

**Recent Changes:**
- ✅ Implemented `get_base_branch()` to detect upstream/base branch (commit b4162ee)
- ✅ Fixed `rebase_to_branch()` to rebase selected branch to its upstream (commit b4162ee)
- ✅ Added current branch deletion protection (commit 18d28d2)
- ✅ Added conditional confirmation for delete - only when branch differs from upstream (commit 18d28d2)
  - No confirmation when track_status == "=" (synced with upstream)
  - Shows confirmation dialog with context for unsynced branches
- Tests: 52 passing, coverage 77.68%

**Process Note:** This implementation plan is updated with each step to maintain accurate project status.
