# Development Workflow

## Required Tools

All development tools are managed via `uv`:
- **ruff** - Code formatting and linting
- **basedpyright** - Static type checking (strict mode)
- **pytest** - Testing framework

## Mandatory Pre-Commit Checks

**IMPORTANT:** Before committing any code changes, you MUST run all three checks:

### 1. Code Formatting with Ruff

Format all code automatically:
```bash
uv run ruff format
```

Check formatting without changes:
```bash
uv run ruff format --check
```

### 2. Linting with Ruff

Run linter and auto-fix issues:
```bash
uv run ruff check --fix
```

Check without fixing:
```bash
uv run ruff check
```

### 3. Type Checking with basedpyright

Run strict type checking:
```bash
uv run python -m basedpyright
```

Must pass with zero errors.

### 4. Run Tests with Coverage

Run all tests (coverage is enabled by default):
```bash
uv run python -m pytest
```

**Coverage is automatically measured** and enforced:
- Minimum coverage threshold is configured in `pyproject.toml`
- Tests will fail if coverage drops below the threshold
- Coverage report shows missing lines

Run with verbose output:
```bash
uv run python -m pytest -v
```

View detailed coverage report:
```bash
uv run python -m pytest --cov-report=html
```
Then open `htmlcov/index.html` in a browser.

## Complete Pre-Commit Workflow

Run all checks in sequence:

```bash
# 1. Format code
uv run ruff format

# 2. Fix linting issues
uv run ruff check --fix

# 3. Type check
uv run python -m basedpyright

# 4. Run tests
uv run python -m pytest

# If all pass, commit
git add .
git commit -m "Your commit message"
```

Or use this one-liner to run all checks:
```bash
uv run ruff format && uv run ruff check --fix && uv run python -m basedpyright && uv run python -m pytest
```

## Development Cycle

1. **Write code** - Implement feature or fix
2. **Format** - `uv run ruff format`
3. **Lint** - `uv run ruff check --fix`
4. **Type check** - `uv run python -m basedpyright`
5. **Test** - `uv run python -m pytest`
6. **Commit** - Only if all checks pass

## Coding Standards

### Documentation Philosophy

**Keep it minimal and meaningful:**

- ❌ **NO extensive documentation** - code should be self-explanatory
- ❌ **NO boilerplate docstrings** - don't document the obvious
- ❌ **NO redundancy with type annotations** - if the type says it all, don't repeat it
- ✅ **Document WHY, not WHAT** - explain non-obvious reasoning only
- ✅ **Complex logic only** - document algorithms, edge cases, business rules
- ✅ **Module-level docstrings** - brief description of module purpose (optional)

### Examples

**Bad (redundant with types):**
```python
def get_branch_name(branch: BranchInfo) -> str:
    """Get the name of the branch.

    Args:
        branch: The branch info object

    Returns:
        The name of the branch as a string
    """
    return branch.name
```

**Good (obvious from types):**
```python
def get_branch_name(branch: BranchInfo) -> str:
    return branch.name
```

**Good (non-obvious logic deserves explanation):**
```python
def calculate_track_status(local: str, remote: str) -> str:
    # Track status uses git's ahead/behind notation:
    # = means same commit, < is behind, > is ahead, <> is diverged
    if local == remote:
        return "="
    # ... rest of implementation
```

## Maintaining Test Coverage

**Important:** Code coverage must never decrease.

### Coverage Requirements

- Minimum coverage threshold: Set in `pyproject.toml` (`--cov-fail-under`)
- Current baseline: Check by running `uv run python -m pytest`
- Coverage includes branch coverage (both paths of if/else statements)

### When Coverage Fails

If you see:
```
ERROR: Coverage failure: total of X.XX is less than fail-under=Y.YY
```

**Action required:**
1. Check the coverage report for lines marked "Missing"
2. Write tests that exercise those code paths
3. Run tests again to verify coverage is restored
4. Only commit when all checks pass

### Improving Coverage

- Add tests for new features before implementing them (TDD)
- Test edge cases and error conditions
- Use `--cov-report=html` to see detailed line-by-line coverage
- Aim to keep coverage at or above the current baseline

## Configuration

All tool configurations are in `pyproject.toml`:
- **ruff**: Line length 100, Python 3.12 target
- **basedpyright**: Strict type checking mode
- **pytest**: Test discovery in `tests/` directory
- **coverage**: Minimum threshold, branch coverage enabled

## CI/CD

These same checks will run automatically in CI/CD pipelines to ensure code quality.
