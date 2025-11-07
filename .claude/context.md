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
uv run basedpyright
```
- Runs strict type checking
- MUST pass with ZERO errors
- No exceptions - fix all type issues

### 4. Run All Tests
```bash
uv run pytest
```
- Runs all unit tests
- ALL tests MUST pass
- No failing tests allowed in commits

## One-Liner for All Checks

Run this before every commit:
```bash
uv run ruff format && uv run ruff check --fix && uv run basedpyright && uv run pytest
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
