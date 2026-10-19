"""
Reusable pytest suite testing communication of real devices, see doc/new-device.md
"""
__all__ = ['ModbusDeviceTests', 'LeBinDeviceTests']


def __getattr__(name):
    # Lazy import, the pytest plugin of this package must not load the Modbus/LeBin stack into every pytest session
    if name == 'ModbusDeviceTests':
        from .ModbusTests import ModbusDeviceTests
        return ModbusDeviceTests
    if name == 'LeBinDeviceTests':
        from .LeBinTests import LeBinDeviceTests
        return LeBinDeviceTests
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
