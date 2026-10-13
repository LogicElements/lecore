from ..ModbusDev import *
from .VMS_RTDRegs import VMS_RTDRegs


class VmsRtd(ModbusDev):
    """
    VMS-1502 RTD meter modbus slave device

    Optional constructor parameters com, reg_map, upg, visual and config_dir override default settings,
    in most cases it is not necessary.
    """
    reg_map = "VMS_RTD_Modbus.json"
    reg_names = VMS_RTDRegs
