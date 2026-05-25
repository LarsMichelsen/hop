# Claude Development Instructions for hop

## MANDATORY: Pre-Commit Checks via prek

**CRITICAL:** Every commit must pass all four checks below. They are wired up
as a [prek](https://prek.j178.dev) hook (config in `prek.toml`) so a plain
`git commit` runs them automatically. prek is a dev dependency — `uv sync`
installs it, and `uv run prek install` registers the git hook.

### The four checks
1. `uv run ruff format` — auto-format
2. `uv run ruff check --fix` — lint and auto-fix
3. `uv run python -m basedpyright` — strict type check, zero errors
4. `uv run python -m pytest` — full suite with `--cov-fail-under` enforced

### Preferred flow

```bash
uv run prek run --all-files   # run everything before committing
git add <files>
git commit -m "..."            # prek runs the same hooks again
```

If a hook modifies files (ruff format / ruff check --fix), prek aborts the
commit. Re-stage the modified files and commit again.

### Fallback one-liner

```bash
uv run ruff format && uv run ruff check --fix && uv run python -m basedpyright && uv run python -m pytest
```

## No Exceptions

- DO NOT commit if any hook fails
- DO NOT skip hooks with `--no-verify` unless the user explicitly asks
- DO NOT bypass the coverage threshold — write tests instead
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
ERROR: Coverage failure: total of 70.00 is less than fail-under=75.00
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
# After making changes, let prek run all four hooks during commit
git add <files>
git commit -m "$(cat <<'EOF'
Add feature X
EOF
)"
```

If prek aborts because a hook (ruff format / ruff check --fix) modified files,
re-stage them and re-run the commit. If a check fails non-recoverably, fix the
underlying issue and retry — never use `--no-verify`.

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
