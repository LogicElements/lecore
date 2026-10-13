# Build and release

## Environment

Create the virtual environment in the repository root (the build script expects `.venv`):

```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -e ".[extra,dev]"
```

## Tests

```
.venv\Scripts\python -m pytest -q
```

Most tests communicate with real hardware (COM ports) or the Looger server, so they cannot pass without the devices.

## Build

```
build.bat              # run tests, build sdist and wheel into dist\
build.bat skiptests    # build without running tests
build.bat upload       # build and upload to PyPI with twine
build.bat skiptests upload
```

Bump `version` in `pyproject.toml` before publishing.
