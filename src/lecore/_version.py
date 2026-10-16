"""Package version, taken from the installed distribution metadata (single source: pyproject.toml)."""
from importlib import metadata

try:
    __version__ = metadata.version("lecore")
except metadata.PackageNotFoundError:  # running from a source tree without installation
    __version__ = "unknown"
