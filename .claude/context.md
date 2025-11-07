# Claude Development Instructions for hop

## MANDATORY: Pre-Commit Checklist

**CRITICAL:** Before ANY commit to this repository, you MUST run ALL of these checks and they MUST pass:

### 1. Format Code
```bash
uv run ruff format
```
- Automatically formats all Python code
- Must run before any commit

### 2. Lint and Fix
```bash
uv run ruff check --fix
```
- Checks code style and common issues
- Auto-fixes where possible
- All issues must be resolved

### 3. Type Check (Strict Mode)
```bash
uv run python -m basedpyright
```
- Runs strict type checking
- MUST pass with ZERO errors
- No exceptions - fix all type issues

### 4. Run All Tests with Coverage
```bash
uv run python -m pytest
```
- Runs all unit tests with coverage measurement
- ALL tests MUST pass
- Coverage MUST NOT decrease below the configured threshold
- No failing tests allowed in commits
- Coverage report shows uncovered lines

## One-Liner for All Checks

Run this before every commit:
```bash
uv run ruff format && uv run ruff check --fix && uv run python -m basedpyright && uv run python -m pytest
```

## Workflow

1. Write/modify code
2. **RUN ALL CHECKS** (see above)
3. Fix any issues found
4. **VERIFY ALL CHECKS PASS**
5. Only then commit

## No Exceptions

- DO NOT commit if any check fails
- DO NOT skip any of the four checks
- DO NOT commit without running all checks
- Fix all issues before committing

## Coverage Verification

**CRITICAL:** Test coverage must NEVER decrease:

1. **Before making changes:** Note the current coverage percentage
2. **After making changes:** Run pytest to check new coverage
3. **If coverage decreased:**
   - STOP immediately - do not commit
   - Review the coverage report (shows missing lines)
   - Add tests for uncovered code paths
   - Re-run all checks
   - Only commit when coverage is >= baseline
4. **Automatic iteration:** If coverage fails, automatically write tests to restore/improve coverage

**Coverage failure example:**
```
ERROR: Coverage failure: total of 60.00 is less than fail-under=65.00
```

**What to do:**
1. Check the coverage report for "Missing" lines
2. Write tests that exercise those code paths
3. Re-run: `uv run python -m pytest`
4. Verify coverage is back to baseline or higher
5. Then commit

## Automatic Git Commits

**MANDATORY:** After each significant change where all checks pass, you MUST create a git commit automatically:

1. **Run all pre-commit checks** (format, lint, type check, tests with coverage)
2. **STOP IMMEDIATELY if ANY check fails** - do not proceed to commit
3. **If coverage decreased:** Automatically add tests to restore coverage
4. **Fix the failure** and re-run all checks from the beginning
5. **Only when ALL checks pass** (including coverage), immediately create a commit
6. **No user confirmation needed** - commit automatically when checks pass
7. **Commit message format:**
   - Clear, concise description of changes

**What counts as "significant change":**
- New feature implementation
- Bug fix
- Refactoring
- Documentation updates
- Test additions

**Do NOT wait for user to ask** - commit proactively when checks pass.

**Example workflow:**
```bash
# After making changes
uv run ruff format && uv run ruff check --fix && uv run python -m basedpyright && uv run python -m pytest

# If all pass, immediately commit
git add .
git commit -m "$(cat <<'EOF'
Add feature X
EOF
)"
```

## Coding Standards

### Documentation Philosophy

**IMPORTANT:** Keep documentation minimal:
- ❌ NO extensive documentation
- ❌ NO boilerplate docstrings
- ❌ NO redundancy with type annotations
- ✅ Only document non-obvious WHY, not obvious WHAT
- ✅ Complex algorithms and business logic only

**Example - Don't do this:**
```python
def get_name(branch: BranchInfo) -> str:
    """Get the branch name."""  # Redundant with types
    return branch.name
```

**Example - Do this:**
```python
def get_name(branch: BranchInfo) -> str:
    return branch.name  # Self-explanatory
```

Only add docstrings when explaining:
- Non-obvious algorithms
- Complex business logic
- Edge cases that aren't clear from code

## Documentation

Full workflow documentation: `docs/DEVELOPMENT.md`
