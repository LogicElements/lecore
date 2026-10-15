# Device API

Modbus devices subclass `ModbusDev` and LeBin devices subclass `LeBinDev`. The basic API is the same for both:
registers are addressed by name (`Reg` constants), values are checked against the register map before writing.

| Method | Modbus (`ModbusDev`) | LeBin (`LeBinDev`) |
|---|---|---|
| `open(...)` | `slave`, `comport`, `baud_rate`, `parity`, `stop_bits`, `timeout`, `client` | `comport`, `baud_rate`, `parity`, `stop_bits`, `timeout`, `client` |
| `read(name)` | value, `None` on error | value, `None` on error |
| `write(name, value)` | `0` on success, `None` on error | `True` on success, `None` on error; a list writes consecutive registers |
| `upgrade_firmware(file, reboot_time=5)` | `True` when upgraded and `FIRM_REVISION` matches the file | same |
| `search_com()` | - | COM ports matching the USB VID/PID/serial number |
| `close()` | closes the COM port | closes the COM port |

Parameters not given to `open()` are taken from `ComSettings*.json` of the device.

## Modbus device

```python
import lecore.Devices.RtdEmul as RE

dev = RE.RtdEmul()
dev.open(comport='COM5', slave=1)

sn = dev.read(RE.Reg.FACT_SERIAL_NUMBER)
dev.write(RE.Reg.EMUL_TEMPERATURE_1, 30.5)

if not dev.upgrade_firmware('RtdEmul_v1.2.bin'):
    print("Firmware upgrade failed")
dev.close()
```

More devices on one bus share the Modbus client: `dev2.open(slave=2, client=dev.mb)`.

## LeBin device

```python
import lecore.Devices.Rftb as RF

dev = RF.RftbLeBin()
# Find the COM port by USB VID/PID/serial number declared in the device class
ports = dev.search_com()
dev.open(comport=ports[0] if ports else None)

sn = dev.read(RF.Reg.FACT_SERIAL_NUMBER)
dev.write(RF.Reg.SYS_COMMAND, 4401)  # refresh calibration data from FLASH

if not dev.upgrade_firmware('Rftb_v1.0.bin'):
    print("Firmware upgrade failed")
dev.close()
```

Unknown register names raise `RegisterNotFoundError` (a `KeyError`), writes to read-only registers and out-of-range
values raise `ValueError`.
