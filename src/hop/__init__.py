from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hop")
except PackageNotFoundError:  # pragma: no cover - running from a source tree, not installed
    __version__ = "0.0.0"
