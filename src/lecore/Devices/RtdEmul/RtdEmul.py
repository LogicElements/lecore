from ..ModbusDev import *
from .RtdEmulRegs import RtdEmulRegs


class RtdEmul(ModbusDev):
    """
    RTD Emulator modbus slave device

    Optional constructor parameters com, reg_map, upg, visual and config_dir override default settings,
    in most cases it is not necessary.
    """
    reg_map = "RtdEmul_Modbus.json"
    reg_names = RtdEmulRegs
