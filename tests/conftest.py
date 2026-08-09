import os

import pytest


@pytest.fixture(autouse=True)
def isolate_from_user_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point HOME at a fresh directory so tests never read the developer's
    real ~/.config/hop/config.toml.

    main() and HopApp fall back to load_config() when no config is injected;
    without this, tests would pick up the developer's settings — and a broken
    real config would fail the whole suite now that load_config hard-fails.
    """
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))


@pytest.fixture(autouse=True)
def isolate_from_ambient_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every git spawned by a test behave like on a bare CI machine."""
    # Tests that shell out to git must not inherit GIT_* vars from an outer git
    # process. When the suite runs inside the pre-commit hook, git exports
    # GIT_DIR/GIT_INDEX_FILE etc., which would redirect those commands at the
    # real repository (and re-trigger the hook recursively).
    for var in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(var, raising=False)

    # Blank the developer's global and system git config so tests (and hop's
    # own git subprocesses) don't pick up identity, aliases, hooksPath,
    # commit.gpgsign etc. that CI machines don't have.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    # Even with no config at all, git guesses a committer identity from the
    # OS (gecos field, /etc/mailname) on typical dev machines, while CI
    # runners fail for lack of one. Disable the guessing and the $EMAIL
    # fallback so identity-requiring operations (commit, rebase) fail
    # everywhere unless a test configures an identity explicitly.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    monkeypatch.delenv("EMAIL", raising=False)
