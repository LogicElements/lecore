# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`lecore` — Logic Elements core Python package (published on PyPI, src-layout under `src/lecore`): Looger client, LeBin protocol, VisualModbus register-map handling, test frame, and device classes. Usage examples are in `README.md`.

## Commands

- Build (runs pytest first, cleans `dist/`, then `python -m build`): `build.bat`; publish to PyPI with `build.bat upload`. It expects a `.venv` in the repo root (the committed `venv/` is not used). Dev setup: `pip install -e ".[extra,dev]"`; `build.bat skiptests` skips the (mostly hardware-bound) tests.
- Version is set in `pyproject.toml`; bump it before publishing.
- Run tests: `.venv\Scripts\python -m pytest -q` or a single file/test: `python -m pytest tests/test_looger.py::TestSimple::test_x`. Tests are `unittest` classes.
- **Most tests require real hardware** (e.g. `test_phase_det.py` opens `COM8`; others need RTD emulator, VMS-RTD, RFTB, FG-320) or network (Looger). Only some (e.g. `test_devices.py`, register-map/looger/frame tests) can run without devices — check `setUpClass` before running.
- Tests import `lecore` and fall back to `src.lecore` if the package is not installed.

## Architecture

Imports within the package use relative imports and `from X import *` heavily (e.g. `TestFrame/__init__.py`, `ModbusDev.py`), so names flow transitively through these star-imports.

- `Looger.py` — client sending debug data/logs to the Development Debug Server (exported as `lecore.Looger`).
- `VisualModbus/` — core of Modbus handling: `MbClient` (pymodbus/serial wrapper, settings from `ComSettings.json`; pymodbus API differences between versions — client constructor `method`/`framer`, request kwarg `unit`/`slave`/`device_id` — are resolved at import via `inspect`, keep new pymodbus calls going through these helpers), `RegMap` (loads a JSON register map and reads/writes registers by name, handling formats INT/FLOAT/FLOAT32/STRING), `MbUpgrade` (firmware upgrade over Modbus), `VisualMbApp` (FreeSimpleGUI GUI, optional extra; PySimpleGUI 4.x is only a fallback and breaks on Python 3.14 / Tcl 9), `TextMbApp` (Textual TUI with `.tcss`; optional — `ModbusDev` provides a stub raising `ImportError` if Textual is missing).
- `LeBin/` — the proprietary LeBin protocol over serial: `SerialCom`, `RegisterMap`, `UpgradeFirmware`, `VisualLeBin`.
- `Devices/ModbusDev.py` / `Devices/LeBinDev.py` — generic device base classes (common parent `Devices/DeviceBase.py`) that wire together com settings, register map, upgrade and visual settings. Devices are declared by class attributes (`reg_map`, `reg_names`, `config_dir`, `usb`, ...) validated in `__init_subclass__`; parameter/config/register-value checks live in `Devices/Validation.py`. Legacy subclasses (own `__init__` setting `_path`/`_def_regs`) still work with `DeprecationWarning`. See `doc/new-device.md`.
- `Devices/<Device>/` (PhaseDet, RtdEmul, VmsRtd, Rftb) — each device subclasses a base and only declares class attributes. Per-device package contains JSON config (`ComSettings`, `UpgradeSettings`, `VisualSettings`, `<Device>_Modbus.json` register map) plus `<Device>Regs.py`, a class of string constants naming the registers (exported as `Reg`). Config JSONs are package data — new ones must be registered in `[tool.setuptools.package-data]` in `pyproject.toml`.
  - When the register map JSON changes, `*Regs.py` must be kept in sync (names = register `Name`).
- `Scaffold.py` + `__main__.py` — jump-start for new devices (`python -m lecore guide | new-device | new-tests | regs`, also `lecore.guide()/new_device()/generate_tests()/generate_regs()`). Must not import the Modbus/LeBin stack. The guide text is `src/lecore/QUICKSTART.md` (package data); keep it in sync with `doc/new-device.md` and the device base classes.
- `FwBuild.py` — FW post-build (`python -m lecore binbuild`, replaces `BinBuild.exe`): stamps the FW information block (version, date, STM32 CRC, size) into a binary or Intel HEX. Stdlib only (imported by `__main__`). See `doc/fwbuild.md`.
- `DeviceTests/` — reusable pytest suite testing communication of a real device (`ModbusDeviceTests`, `LeBinDeviceTests`, protocol hooks over `Base.DeviceTestsBase`); generated `test_modbus.py`/`test_lebin.py` of device packages subclass it. Only this package imports pytest. `Plugin.py` is a pytest11 entry point registering marker `hardware` (reinstall `pip install -e .` after changing entry points). Hardware-free tests: `tests/test_device_suite.py` with fakes in `tests/fake_devices.py`.
- `TestFrame/` — helper library for device tests (`RtuClient`, `CoreTest`/`Runner` using `xmlrunner` to write reports into `test-reports/`, `TestUtils`).
- `Doc/ModbusTable.py` — generates documentation tables from register maps (needs `python-docx`).
- `Fg320/` — third-party function generator driver (not LE device).
