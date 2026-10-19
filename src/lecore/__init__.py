"""
Logic Elements core package.

New device classes: run ``python -m lecore guide`` (or ``lecore.guide()``) for a quick guide
and ``python -m lecore new-device MyDevice [--lebin]`` to generate a device package.
"""
from .Looger import Looger
from .Scaffold import guide, new_device, generate_regs, generate_tests

_DEVICE_NAMES = ('DeviceBase', 'ModbusDev', 'LeBinDev', 'ComSettings', 'UsbId', 'RegisterNotFoundError')

__all__ = ['Looger', 'guide', 'new_device', 'generate_regs', 'generate_tests', *_DEVICE_NAMES]


def __getattr__(name):
    # Lazy import of device classes, so that importing Looger does not load Modbus stack
    if name in _DEVICE_NAMES:
        from . import Devices
        return getattr(Devices, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
