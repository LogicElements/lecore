# lecore quick guide: new LE device

Shipped with the `lecore` package, print it by `python -m lecore guide` (or `lecore.guide()`).
Use it as instructions when creating a device class based on `lecore.Devices.ModbusDev` or `lecore.Devices.LeBinDev`.

## 1. Generate the device class

The register map JSON (`*_Modbus.json` / `*_registers.json`) and its register name class (`*Regs.py`) are
produced by the LE register map generator and kept in sync by it. Copy them into the device package directory
(e.g. `src/mypkg/mydevice/`) and run there:

```
python -m lecore new-device MyDevice [--slave 3] [--comport COM5] [--baud-rate 19200] [--parity E]
python -m lecore new-device MyDevice [--usb 1155 22336 MYDEV]        # LeBin map, USB id for search_com()
```

Options: `--dir D` (default: current directory), `--reg-map F` (when more maps are present), `--modbus`/`--lebin`
(default: detected from the map), `--force` (overwrite device module and configs), `--gen-regs` (create a missing
`*Regs.py`), `--template` (no map yet: create a minimal map and its `*Regs.py`).
Python API: `lecore.new_device("MyDevice", directory=".", ...)` returns `{path: created|overwritten|kept|used}`.

| File | Action |
|---|---|
| `MyDevice.py` | created (error if it exists, unless `--force`) - device class, only class attributes |
| `*_Modbus.json` / `*_registers.json` | used - register map, protocol is detected from it |
| `*Regs.py` | used - register name class (`<map prefix>Regs.py`), `reg_names` is omitted when missing |
| `ComSettings.json` | created if missing - serial port (`comport`, `baud_rate`, `parity`, `stop_bits`, `timeout`) |
| `UpgradeSettings.json` | created if missing (Modbus only) - firmware upgrade, must match the device bootloader |
| `VisualSettings.json` | created if missing (Modbus only) - GUI settings incl. default `slave_address` |
| `__init__.py` | created if missing - exports device class, register class and alias `Reg`; existing one is not changed |
| `__main__.py` | created if missing - command line: `python -m <package> [--comport COM5] [--slave 3] [--read NAME ...] [--list] [--gui \| --tui]` |

Run it from the package directory as `python . [options]`, or from its parent as `python -m mydevice [options]`;
without options all registers are read and printed. `python MyDevice.py` does not work (relative imports).

**Modbus and LeBin map together** (one `*Regs.py`, `*_Modbus.json` and `*_registers.json`, different COM ports):
`new-device MyDevice` creates two classes in the package, `MyDevice` (Modbus, `ComSettings.json`) and `MyDeviceLeBin`
(LeBin, `com_settings = "ComSettings_LeBin.json"`, `--usb` applies to it). `reg_names` is declared only in the
class whose map contains all register names (otherwise a note is put in its docstring). `python . --lebin` selects
the LeBin device. `--modbus`/`--lebin`/`--reg-map` generate a single class from the selected map only.

## 2. Device class

```python
from lecore.Devices import ModbusDev
from .MyDeviceRegs import MyDeviceRegs


class MyDevice(ModbusDev):
    reg_map = "MyDevice_Modbus.json"   # required, relative to the module directory
    reg_names = MyDeviceRegs           # optional, checked against the register map
```

```python
from lecore.Devices import LeBinDev, UsbId


class MyDevice(LeBinDev):
    reg_map = "MyDevice_registers.json"
    reg_names = MyDeviceRegs
    usb = UsbId(vid=1155, pid=22336, sn="MYDEV")   # used by search_com()
```

Do not write a constructor. Optional attributes: `com_settings`, `upgrade_settings`, `visual_settings` (file names)
and `config_dir` (default: directory of the module). Device specific helpers are plain methods using
`self.read()` / `self.write()`.

## 3. Register names

- Modbus: constant = register `Name`. LeBin: constant = `Category_Name` (e.g. `SYS_STATUS`).
- `*Regs.py` is regenerated together with the map by the LE register map generator. Only without it:
  `python -m lecore regs MyDevice_Modbus.json --class MyDeviceRegs -o MyDeviceRegs.py`.
- Always use the constants (`Reg.SYS_COMMAND`), never string literals.

## 4. Usage

```python
from mypkg.MyDevice import MyDevice, Reg

with MyDevice() as dev:
    dev.open(comport='COM5', slave=3)     # LeBin: dev.open(comport=dev.search_com()[0]), no slave
    print(dev.read(Reg.FIRM_REVISION))    # None on communication error
    dev.write(Reg.SYS_COMMAND, 9901)      # None on communication error
    print(dev.register_names())
# dev.visual() - GUI, dev.textual() - TUI (Modbus), dev.upgrade_firmware("fw.bin") needs FIRM_REVISION register
```

## 5. Rules and checks

- Register map formats: Modbus keys `Name, Type (HOLD/INPUT), Address [list], Format (INT/BIN/ENUM/FLOAT/FLOAT32/STRING), Value`,
  optional `Access, Min, Max, EnumValue, Label, Unit, Description`. LeBin keys `Name, Id, VarType, Access`, optional `Category`.
- Errors are raised early: missing config files at class definition, invalid JSON / missing keys at instance creation,
  invalid `open()` parameters, unknown register names (`RegisterNotFoundError` with suggestions), writes to read-only
  registers and values outside type range, `Min`/`Max` (unless both 0) or `EnumValue`.
- When the device package is distributed, register the JSON files as package data
  (`[tool.setuptools.package-data]` `"mypkg.MyDevice" = ["*.json"]` in `pyproject.toml`).
- Reference implementations inside lecore: `lecore.Devices.PhaseDet` (Modbus), `lecore.Devices.Rftb.RftbLeBin` (LeBin).
