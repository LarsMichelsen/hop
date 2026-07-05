import os

import pytest


@pytest.fixture(autouse=True)
def isolate_from_ambient_git(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests that shell out to git must not inherit GIT_* vars from an outer git
    # process. When the suite runs inside the pre-commit hook, git exports
    # GIT_DIR/GIT_INDEX_FILE etc., which would redirect those commands at the
    # real repository (and re-trigger the hook recursively).
    for var in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(var, raising=False)
