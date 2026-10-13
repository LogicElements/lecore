# LE core package

[![PyPI](https://img.shields.io/pypi/v/lecore)](https://pypi.org/project/lecore/)
[![Python](https://img.shields.io/pypi/pyversions/lecore)](https://pypi.org/project/lecore/)
[![License](https://img.shields.io/pypi/l/lecore)](LICENSE)

Core Python utilities for Logic Elements:
- Looger client
- Proprietary LeBin protocol
- Proprietary Modbus RTU register map handling - VisualModbus
- Test frame
- Logic Elements devices

## Install

Requires Python 3.9 or newer.

```
pip install lecore
pip install --upgrade lecore
```

Optional extras: `lecore[extra]` (graphical UI, Word documentation) and `lecore[tui]` (terminal UI).

## Usage

```python
import lecore.Devices.RtdEmul as RE

# Create RTD emulator object and open communication at COM2 (default is COM1)
rtd = RE.RtdEmul()
rtd.open(comport='COM2')

# Read serial number
sn = rtd.read(RE.Reg.FACT_SERIAL_NUMBER)

# Write emulated temperature at output 1
rtd.write(RE.Reg.EMUL_TEMPERATURE_1, 30.5)
```

New device class (in the directory with the register map): `python -m lecore new-device MyDevice`, quick guide: `python -m lecore guide`.

## Documentation

- [Devices](doc/devices.md) - RTD Emulator, VMS-1502 RTD Meter, Phase Detector, FG-320
- [Creating a new device](doc/new-device.md)
- [Looger](doc/looger.md)
- [User interfaces](doc/user-interfaces.md) - graphical and terminal register browser
- [Build and release](doc/build.md)

## License

MIT, see [LICENSE](LICENSE).
