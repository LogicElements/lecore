# Generated Device Communication Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lecore ships a reusable pytest suite testing the communication API of a real `ModbusDev` / `LeBinDev`
device, and `new-device` / `new-tests` generate `test_modbus.py` / `test_lebin.py` plugging a device into it.

**Architecture:** New package `lecore.DeviceTests` with a protocol-independent base class (configuration, class-scoped
`device` fixture, common tests) and Modbus/LeBin subclasses implementing protocol hooks. A pytest plugin (entry
point `pytest11`) registers marker `hardware`. `Scaffold.py` renders the test files from text templates (no import
of the Modbus/LeBin stack). Suite logic is tested without hardware against in-memory fake transports.

**Tech Stack:** Python 3.9+, pytest, existing lecore `Devices` / `VisualModbus` / `LeBin`.

**Spec:** `doc/specs/2026-10-19-device-tests-design.md`

## Global Constraints

- Python >= 3.9; pymodbus 2.x and 3.x through existing `MbClient` helpers.
- No runtime dependency on pytest: only `lecore.DeviceTests` imports pytest; `lecore/__init__.py`, `Scaffold.py`,
  `__main__.py` must not import it. No new extra, pytest is already in extra `dev`.
- `Scaffold.py` must not import the Modbus/LeBin stack.
- Source code and comments in English; existing docs are English.
- The suite never writes to a register other than `test_register` on the real device; locally rejected writes run
  with a stub client and assert nothing was sent.
- No device answering → tests fail, never skip. Skip only for missing configuration (`test_register`, `firmware`)
  or a map without a suitable register, always with a reason.
- All suite tests carry marker `hardware`.
- Generated test files are kept unless `force`.
- Tests of lecore itself are `unittest` classes or plain pytest functions; new hardware-free test files must be
  added to `.github/workflows/ci.yml` and the list in `doc/build.md`.
- After adding the `pytest11` entry point, reinstall the dev package (`.venv\Scripts\pip install -e ".[extra,dev]"`)
  or the marker plugin is not loaded locally.

## Review Focus

1. Device answers the injected unknown register with data → `test_04_unknown_register` fails with a message
   naming `unknown_address` / `unknown_id` (Task 1, Task 2).
2. `test_register` not in the map or read-only → write test fails with a clear message, not a bare `KeyError`
   (Task 1).
3. Read-back differs → test fails **and** the original value is still restored (Task 1).
4. Map without a read-only or without a limited writable register → the respective part of test 6 is skipped with a
   reason, the other part still runs (Task 1).
5. Re-running `new-tests` without `force` keeps an edited test file; with `force` overwrites it (Task 3).

---

### Task 1: Suite base, Modbus suite and marker plugin

**Files:**
- Create: `src/lecore/DeviceTests/__init__.py` (plain import/export of `ModbusDeviceTests`; LeBin added in Task 2)
- Create: `src/lecore/DeviceTests/Base.py`
- Create: `src/lecore/DeviceTests/ModbusTests.py`
- Create: `src/lecore/DeviceTests/Plugin.py`
- Modify: `pyproject.toml` (entry point)
- Create: `tests/fake_devices.py`
- Create: `tests/test_device_suite.py`

**Interfaces:**
- Produces (`Base.py`):
  - `random_value(reg: dict, fmt: str, bits: int, signed: bool = False) -> Any` — random value passing
    `check_reg_value(reg, value, fmt, bits, signed_ok=signed)`, different from `reg['Value']` when possible.
    INT/BIN: non-negative int within Min/Max (if not both 0) and bit width; `EnumValue` present → choice from it;
    FLOAT (Modbus 0.1 resolution) / FLOAT32: `round(uniform(lo, hi), 1)` within Min/Max or a ±1000 default range;
    STRING: 1..bytes ASCII letters.
  - `pick_rejected_writes(device) -> Tuple[Optional[str], Optional[str]]` — (read-only register name, writable
    numeric register name with Min/Max not both 0); `None` when the map has none.
  - `class DeviceTestsBase` with class attributes `device_class = None`, `open_kwargs: dict = {}`,
    `test_register: Optional[str] = None`, `exclude: list = []`, `firmware = None`, `reboot_time: float = 5`,
    `pytestmark = [pytest.mark.hardware]`; classmethod `create_device(cls)` (instantiate `device_class`,
    `open(**open_kwargs)`; Modbus `open()` returning `False` → `pytest.fail` with the port name); class-scoped
    fixture `device` (create, yield, close); tests `test_01_read`, `test_02_write_read_back`, `test_03_read_all`,
    `test_04_unknown_register`, `test_06_rejected_writes`, `test_07_reopen`, `test_08_upgrade`.
  - Protocol hooks (abstract in base): `_inject_unknown(self, device) -> str` (adds register, returns its name),
    `_remove_unknown(self, device, name) -> None`, `_unknown_hint: str` (`"unknown_address"` / `"unknown_id"`),
    `_swap_client(self, device, client) -> Any` (installs client, returns the original), `_stub_client(self, device)`
    (recording stub with list attribute `sent`), `_value_args(self, reg) -> Tuple[str, int, bool]` (fmt, bits,
    signed for `random_value`).
- Produces (`ModbusTests.py`): `class ModbusDeviceTests(DeviceTestsBase)` with `unknown_address: int = 65000`,
  `wrong_slave: int = 247`, extra test `test_05_wrong_slave`.
- Produces (`Plugin.py`): `pytest_configure(config)` adding marker line
  `"hardware: test needs a real device (deselect by -m 'not hardware')"`.
- Produces (`tests/fake_devices.py`): `FakeMbClient(MbClient)` — in-memory slave: `slave` attribute, register memory
  by address, `answer_unknown: bool = False`, list `sent` of write requests; overrides `open()` → True, `close()`,
  `read(request)` (None for wrong slave or address not in the map unless `answer_unknown`), `write_hold(request)`
  → 0; constructor `FakeMbClient(reg_map_regs: list, slave: int)` with attribute `s = {'comport': 'FAKE'}`.

Test behaviour (spec "Tests"), decided details:
- `test_01_read`: reads `test_register` or the first of `device.register_names()`, asserts not `None`.
- `test_02_write_read_back`: skip with reason if `test_register is None`; `pytest.fail` with message if it is not in
  `register_names()` or is read-only; read original, write `random_value`, read back, compare (`math.isclose`
  `abs_tol=0.05` for floats), restore original in `finally`.
- `test_03_read_all`: all names except `exclude`, collect those returning `None`, one assertion listing them.
- `test_04_unknown_register`: inject, `read()` must return `None` (message on data contains `self._unknown_hint`),
  remove in `finally`, then a normal read (as in test 1) must succeed ("recovery").
- `test_05_wrong_slave`: swap `device.regs.slave` to `wrong_slave`, read returns `None`, restore in `finally`,
  then normal read succeeds.
- `test_06_rejected_writes`: `pick_rejected_writes`; for each found name swap a stub client, `pytest.raises(ValueError)`
  on `write` (read-only: any valid value; range: `Max + 1`), restore client in `finally`, assert `stub.sent == []`;
  skip only when both are `None`, a missing one is reported in the skip/pass message.
- `test_07_reopen`: `device.close()`, `device.open()`, read succeeds.
- `test_08_upgrade`: skip if `firmware is None`; `upgrade_firmware(firmware, reboot_time)` is True, then read succeeds.
- Modbus `_inject_unknown`: copy of the first INPUT register (else HOLD) with `Address=[unknown_address]`,
  `Name='__LECORE_UNKNOWN__'`, appended to `device.regs.input`/`hold` and `device._regs_by_name`.
- Modbus stub: subclass of `MbClient` recording `write_hold`/`read` requests in `sent`, returning `None`.

- [ ] **Step 1: Write failing hardware-free tests** in `tests/test_device_suite.py`

```python
class TestFakeModbus(ModbusDeviceTests):
    """Whole suite against an in-memory Modbus slave (Rftb map)"""
    test_register = 'SYS_TEST'

    @classmethod
    def create_device(cls):
        dev = RFTB.Rftb()
        dev.open(client=FakeMbClient(dev.regs.input + dev.regs.hold, dev.slave))
        return dev
# collected by pytest: tests 01-07 pass, test_08 skipped ("firmware")

def test_random_value_valid():  # 200 samples per register of Rftb and PhaseDet maps pass check_reg_value
def test_random_value_enum():   # reg with EnumValue [1, 5, 9] → value in it
def test_unknown_answered_fails():
    # FakeMbClient(answer_unknown=True); calling TestFakeModbus().test_04_unknown_register(dev)
    # raises AssertionError whose message contains 'unknown_address'
def test_test_register_read_only_fails():  # test_register = 'FIRM_REVISION' → pytest.fail.Exception with 'read-only'
def test_read_back_mismatch_restores():
    # fake returning a different value on read-back → AssertionError, fake memory holds the original value
def test_pick_rejected_writes_none():  # map without RO / limited regs → (None, None); test_06 raises pytest.skip.Exception
def test_marker():  # 'hardware' in [m.name for m in TestFakeModbus.pytestmark]
```

- [ ] **Step 2: Run, verify failure**

Run: `.venv\Scripts\python -m pytest -q tests/test_device_suite.py`
Expected: FAIL / collection error `No module named 'lecore.DeviceTests'`

- [ ] **Step 3: Implement** `Base.py`, `ModbusTests.py`, `Plugin.py`, `__init__.py`, `tests/fake_devices.py`;
  in `pyproject.toml` add `[project.entry-points.pytest11] lecore = "lecore.DeviceTests.Plugin"`; reinstall `.venv\Scripts\pip install -e ".[extra,dev]"`.

- [ ] **Step 4: Run, verify pass**

Run: `.venv\Scripts\python -m pytest -q -W error::pytest.PytestUnknownMarkWarning tests/test_device_suite.py tests/test_devices.py tests/test_scaffold.py`
Expected: all pass, 1 skipped (`test_08_upgrade`), no unknown-marker warning

- [ ] **Step 5: Commit**

```bash
git add src/lecore/DeviceTests pyproject.toml tests/fake_devices.py tests/test_device_suite.py
git commit -m "Add reusable device communication test suite (Modbus)"
```

### Task 2: LeBin suite

**Files:**
- Create: `src/lecore/DeviceTests/LeBinTests.py`
- Modify: `src/lecore/DeviceTests/__init__.py`
- Modify: `tests/fake_devices.py`, `tests/test_device_suite.py`

**Interfaces:**
- Consumes: `DeviceTestsBase`, hooks and `random_value` from Task 1.
- Produces: `class LeBinDeviceTests(DeviceTestsBase)` with `unknown_id: int = 0x7FFFFF02` (assert not in map at
  injection, else `pytest.fail` asking to set `unknown_id`); no wrong-slave test.
- Produces (`tests/fake_devices.py`): `FakeLeBinCom` — `ble = False`, attributes `comport`, `baud`, `parity`,
  `stop`, `timeout`; `close()`, `reopen()`, `request_response(msg, resp_len) -> bytes` implementing the LeBin
  packet format of `LeBin/RegisterMap.py` (read: answer header + id + value per known id; header only when any id
  is unknown, unless `answer_unknown`; write: store values, echo request); list `sent`.

Decided details: `_inject_unknown` copies the first register with `VarType` INT, sets `Id=unknown_id`,
`Name='__LECORE_UNKNOWN__'`, appends to `device.regs.regs` and `device._regs_by_name`; `_swap_client` uses
`device.open(client=...)` and restores the original `device.com`; `_value_args` → (`'FLOAT32'` for FLOAT else
VarType, `8 * (1 << (Id & 7))`, `False`) — same as `LeBinDev.write`.

- [ ] **Step 1: Write failing tests**: `class TestFakeLeBin(LeBinDeviceTests)` with `test_register = 'SYS_TEST'`
  (name as in Rftb LeBin map after `Category_` prefix — check `rftbRegs.py`) and `create_device` returning
  `RFTB.RftbLeBin()` opened with `FakeLeBinCom`; `test_lebin_unknown_answered_fails` (message contains `unknown_id`).
- [ ] **Step 2: Run, verify failure**: `.venv\Scripts\python -m pytest -q tests/test_device_suite.py` → ImportError
  `LeBinDeviceTests`.
- [ ] **Step 3: Implement** `LeBinTests.py`, `FakeLeBinCom`, export in `__init__.py`.
- [ ] **Step 4: Run, verify pass**: same command → all pass, 2 skipped (`test_08_upgrade` of both classes).
- [ ] **Step 5: Commit** `git commit -m "Add LeBin device communication test suite"`

### Task 3: Generating test files (`new-device`, `new-tests`)

**Files:**
- Modify: `src/lecore/Scaffold.py` (template, `generate_tests`, call from `new_device`)
- Modify: `src/lecore/__main__.py` (subcommand `new-tests`)
- Modify: `src/lecore/__init__.py` (export `generate_tests`)
- Modify: `tests/test_scaffold.py`

**Interfaces:**
- Consumes: class names `ModbusDeviceTests`, `LeBinDeviceTests` and attributes from Tasks 1–2 (only as text).
- Produces:
  - `_test_source(cls_name: str, protocol: str, regs: Optional[Tuple[str, str]], test_register: Optional[str]) -> str`
  - `_write_tests(directory: str, devices: List[Tuple[str, str]], regs, force: bool, result: Dict[str, str]) -> None`
    — devices as (class name, protocol); file `test_modbus.py` / `test_lebin.py`; existing → `kept` unless `force`.
  - `generate_tests(directory: PathLike = '.', force: bool = False) -> Dict[str, str]` — finds device classes by
    regex `^class (\w+)\((ModbusDev|LeBinDev)\):` in `*.py` of the directory (no import), their `reg_map = "..."`,
    regs class via `_find_regs_class`; `NotADirectoryError` for a missing directory, `ValueError` when no device
    class is found or more than one class per protocol (message lists them).
  - CLI: `python -m lecore new-tests [--dir DIR] [--force]`, prints `status  path` like `new-device`.

Generated file content (decided): module docstring with run commands
(`python -m pytest <dir> --junitxml=report.xml`, `-m "not hardware"` without devices); imports
`from lecore.DeviceTests import ModbusDeviceTests` (or LeBin), `from .<Device> import <Device>`,
`from .<Regs module> import <Regs class> as Reg` when regs exist; class `Test<Device>(<Base>)` with
`device_class = <Device>`, `open_kwargs = {}` (comment with example), `test_register = Reg.SYS_TEST` when the map has
`SYS_TEST` (designer's call) else `None` with comment, `exclude = []`, `firmware = None`, `reboot_time = 5`,
commented `unknown_address`/`wrong_slave` (Modbus) or `unknown_id` (LeBin), commented `create_device` override
("return an opened device, apply port settings through open()"); dual device: LeBin file comment recommends enabling
upgrade in one file only.

- [ ] **Step 1: Write failing tests** in `tests/test_scaffold.py`:
  - `test_modbus_existing_map` / `test_lebin_existing_map` / `test_dual`: result contains `test_modbus.py` and/or
    `test_lebin.py` as `created`, single-protocol directories do not contain the other file.
  - `test_new_tests`: after `new_device`, delete `test_modbus.py`, write marker text into nothing else;
    `main(['new-tests', '--dir', self.dir]) == 0` recreates it; edit it, run again → `kept` and edit preserved;
    `force=True` → `overwritten`; empty directory → `ValueError`.
  - `test_generated_tests_collect`: subprocess
    `python -m pytest <root> -q -m "not hardware" -W error::pytest.PytestUnknownMarkWarning` in the temp root with
    `PYTHONPATH=src` → return code 5 (all deselected) and `deselected` in stdout; and
    `python -m pytest <root> --collect-only -q` lists `test_modbus.py::TestMbDevice::test_01_read`.
- [ ] **Step 2: Run, verify failure**: `.venv\Scripts\python -m pytest -q tests/test_scaffold.py` → new assertions fail.
- [ ] **Step 3: Implement** `_test_source`, `_write_tests`, `generate_tests`, call `_write_tests` at the end of
  `new_device`, CLI subcommand, export.
- [ ] **Step 4: Run, verify pass**: `.venv\Scripts\python -m pytest -q tests/test_scaffold.py tests/test_device_suite.py tests/test_devices.py` → all pass.
- [ ] **Step 5: Commit** `git commit -m "Generate device test files by new-device and new-tests"`

### Task 4: Documentation and CI

**Files:**
- Modify: `src/lecore/Scaffold.py` (`_claude_source`: section `## Tests`)
- Modify: `src/lecore/QUICKSTART.md`, `doc/new-device.md` (in sync), `CLAUDE.md` (architecture line for
  `DeviceTests/`, command `new-tests`), `doc/build.md` (CI test list), `.github/workflows/ci.yml` (add
  `tests/test_device_suite.py`), `README.md` only if it lacks a link to `doc/new-device.md`
- Modify: `tests/test_scaffold.py`

Generated CLAUDE.md section (decided content): files `test_modbus.py` / `test_lebin.py`, what to fill
(`test_register`, `open_kwargs`, `firmware`, `exclude`), how to run (`python -m pytest . --junitxml=...`), marker
`hardware`, regenerate by `python -m lecore new-tests`.

- [ ] **Step 1: Write failing test**: in `test_modbus_existing_map` assert `'## Tests'`, `'test_register'` and
  `'-m "not hardware"'` in the generated CLAUDE.md; in `test_guide` assert `'new-tests'` in `lecore.guide()`.
- [ ] **Step 2: Run, verify failure**: `.venv\Scripts\python -m pytest -q tests/test_scaffold.py`.
- [ ] **Step 3: Update** `_claude_source` and the docs listed above.
- [ ] **Step 4: Run, verify pass**: `.venv\Scripts\python -m pytest -q tests/test_scaffold.py tests/test_devices.py tests/test_byte_order.py tests/test_device_suite.py` → all pass;
  `build.bat skiptests` builds and the wheel contains `lecore/DeviceTests/*.py` and the `pytest11` entry point
  (`entry_points.txt`).
- [ ] **Step 5: Commit** `git commit -m "Document generated device tests, run suite tests in CI"`

Real hardware verification is done by the owner at the integration site (not part of this plan).
