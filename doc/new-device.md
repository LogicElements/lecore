# Creating a new device

New devices are created outside of `lecore` by subclassing `ModbusDev` (Modbus RTU) or `LeBinDev` (LeBin protocol).
A device is declared by class attributes only, no constructor is needed.

## Quick start

Run in the device package directory containing the register map JSON and `*Regs.py` from the LE register map
generator:

```
python -m lecore new-device MyDevice [--slave 3] [--comport COM5] [--usb VID PID SN]
python -m lecore guide       # condensed guide incl. all options
```

`new-device` detects the protocol from the register map, uses the existing `*Regs.py` and creates the device module
`MyDevice.py`, missing configuration JSONs (`ComSettings.json`, for Modbus also `UpgradeSettings.json` and
`VisualSettings.json`), missing `__init__.py` and `__main__.py` and communication tests `test_modbus.py` /
`test_lebin.py` (see [Communication tests](#communication-tests)). The package can then be run from its directory
as `python . [--comport COM5] [--slave 3] [--read NAME ...] [--list] [--gui | --tui]`, or from the parent directory
as `python -m mydevice ...` (without options all registers are read and printed).

When the directory contains both Modbus and LeBin register map with common `*Regs.py`, two classes are created:
`MyDevice` (Modbus) and `MyDeviceLeBin` with its own `ComSettings_LeBin.json` (`python . --lebin` runs it).
`reg_names` is declared only where the map contains all register names. Existing files are kept, the device module is overwritten only with
`--force`. Without a register map, `--template` creates a minimal one; `--gen-regs` or
`python -m lecore regs MAP.json --class NameRegs -o NameRegs.py` generate a missing `*Regs.py`.
The same is available as `lecore.new_device()`, `lecore.generate_tests()`, `lecore.generate_regs()` and `lecore.guide()`. The guide is shipped
with the package (`src/lecore/QUICKSTART.md`), so it can be given to an AI assistant in projects using `lecore`.

`new-device` also creates a missing `CLAUDE.md` in the package: a short description of the device classes
(Modbus and/or LeBin), their `read()`/`write()` API and the command line (`--read`, `--list`). Claude Code loads it
when working with files of the package; from a project root it can be included by `@mydevice/CLAUDE.md` in the root
`CLAUDE.md`. An existing `CLAUDE.md` is never changed (delete it to regenerate, e.g., after adding a protocol).

## Communication tests

`new-device` generates a pytest file for each generated class: `test_modbus.py` (Modbus) and/or `test_lebin.py`
(LeBin). Existing test files are kept unless `--force`. For a device package created earlier run
`python -m lecore new-tests [--dir D] [--force]` (`lecore.generate_tests()`), it creates only the missing test files
and does not touch the device modules and configuration.

The tests themselves are in `lecore.DeviceTests` (`ModbusDeviceTests`, `LeBinDeviceTests`), so they are updated with
`lecore`. The generated file only subclasses the suite and sets class attributes:

| Attribute | Default | Meaning |
|---|---|---|
| `device_class` | generated class | Device class instantiated by `create_device()` |
| `open_kwargs` | `{}` | Arguments of `open()`, empty uses `ComSettings*.json` (LeBin: port found by USB id) |
| `test_register` | `Reg.SYS_TEST` if in the map, else `None` | Register safe to write by the read-back test, `None` skips it |
| `exclude` | `[]` | Registers not read by the read-all test |
| `firmware` | `None` | Firmware binary for the upgrade test, `None` skips it |
| `reboot_time` | `5` | Wait after upgrade in seconds |
| `unknown_address` / `wrong_slave` | `65000` / `247` | Modbus: address and slave address not answered by the device |
| `unknown_id` | `0x7FFFFF02` | LeBin: register ID not supported by the device |
| `hil_signal` | `None` | DUT signal name in `hil/dut.yaml` when run on a HIL station, see below |
| `hil_supply` | `None` | HIL: power signal switched on for the whole test class |
| `hil_boot_s` | `0` | HIL: wait after switching `hil_supply` on in seconds |

For an exact device definition override classmethod `create_device()` returning an opened device; apply port
settings through `open()`, the reopen test calls `close()` and `open()` without arguments.

### On a HIL station

With `hil_signal` set and pytest run with `--hil-station` (package `hil-platform`), the device comes from the HIL
fixture `hil_lecore_device` instead of `create_device()`: HIL opens it with the port and overrides of the DUT signal
(`lebin` or `modbus_dev` in `hil/dut.yaml`), holds the station lock, writes the artifacts of the class into
`hil/out/` and skips the whole class when the terminal of the signal is not wired. The safe state comes after the
class, not after each test. Without `--hil-station` (or without `hil-platform`) the device is opened by
`create_device()` as before, `lecore` itself does not import `hil`.

Tests in order (the device is opened once per test class): read, write with read-back of `test_register` (original
value restored), read of all registers (all failures listed at once), register present in the map but unknown to
the device (`read()` returns `None` and the device answers afterwards), wrong slave address (Modbus), locally
rejected writes of a read-only and an out-of-range value (`ValueError`, nothing is sent: a stub client is used),
close and reopen, firmware upgrade (last).

The tests are plain pytest, a runner in a parent directory collects them and stores results, e.g.
`python -m pytest . --junitxml=report.xml`. All of them carry marker `hardware` (registered by the lecore pytest
plugin): `-m "not hardware"` deselects them on machines without devices; without deselecting they fail when the
device does not answer, they are never skipped silently. For a device with both protocols both files reach the same
device, enable the firmware upgrade in one of them only.

## Modbus device

Put the configuration files next to the module with the device class:

```
my_device/
    __init__.py
    MyDevice.py
    MyDeviceRegs.py          # optional class with register name constants
    MyDevice_Modbus.json     # register map
    ComSettings.json
    UpgradeSettings.json
    VisualSettings.json
```

```python
from lecore.Devices import ModbusDev
from .MyDeviceRegs import MyDeviceRegs


class MyDevice(ModbusDev):
    reg_map = "MyDevice_Modbus.json"   # required
    reg_names = MyDeviceRegs           # optional, checked against the register map
```

```python
dev = MyDevice()
dev.open(comport='COM5', slave=3)
dev.write(MyDeviceRegs.SYS_COMMAND, 9901)
```

Class attributes:

| Attribute | Default | Meaning |
|---|---|---|
| `reg_map` | - (required) | Register map JSON |
| `reg_names` | `None` | Class with register name constants; missing names are reported by `UserWarning` |
| `com_settings` | `ComSettings.json` | Communication settings |
| `upgrade_settings` | `UpgradeSettings.json` | Firmware upgrade settings (Modbus only) |
| `visual_settings` | `VisualSettings.json` | Visual application settings (Modbus only) |
| `usb` | `UsbId()` | USB VID/PID/serial number for `search_com()` (LeBin only) |
| `config_dir` | directory of the module declaring `reg_map` | Directory with configuration files |

When the configuration files are packaged with your library, register them as package data
(`[tool.setuptools.package-data]` in `pyproject.toml`).

Constructor parameters (`com`, `reg_map`, `upg`, `visual`, `config_dir`) override the defaults per instance.
Relative paths are resolved against the current working directory, then against `config_dir`.

## Device without subclass

```python
from lecore.Devices import ModbusDev

dev = ModbusDev(reg_map="MyDevice_Modbus.json", config_dir="path/to/configs")
```

## LeBin device

```python
from lecore.Devices import LeBinDev, UsbId


class MyLeBinDevice(LeBinDev):
    reg_map = "my_registers.json"
    usb = UsbId(vid=1155, pid=22336, sn="MY")
```

## Validation

Mistakes are reported immediately with a descriptive exception:

- class definition: missing configuration files (`FileNotFoundError`), invalid `config_dir` (`NotADirectoryError`),
  wrong attribute types (`TypeError`),
- device creation: invalid JSON, missing keys or values in `ComSettings.json`, `UpgradeSettings.json`,
  `VisualSettings.json` and register map (`ValueError`),
- `open()`: slave address 1..247, parity `N`/`E`/`O`, stop bits 1/1.5/2, positive baud rate and timeout,
- `read()` / `write()`: unknown register name (`RegisterNotFoundError`, a `KeyError` with suggestions of similar
  names), write to read-only register, value type, integer range of the register, `Min`/`Max` limits
  (unless both are zero) and allowed `ENUM` values (`TypeError` / `ValueError`).

Communication errors are still reported by return value `None` of `read()` / `write()`.

The devices support context manager, the port is closed at the end of `with` block:

```python
with MyDevice() as dev:
    dev.open(comport='COM5')
    print(dev.read(MyDeviceRegs.FIRM_REVISION))
```

## Migration of older subclasses

Subclasses setting `_path` and `_def_regs` and calling `_com()`, `_reg_map()`, `_upgrade()` and `_visual()`
in their own `__init__` still work but emit `DeprecationWarning`. Replace the constructor by class attribute
`reg_map` (and optionally `reg_names`).
