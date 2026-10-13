from ..ModbusDev import *
from .PhaseDetRegs import PhaseDetRegs


class PhaseDet(ModbusDev):
    """
    Phase detector modbus slave device

    Optional constructor parameters com, reg_map, upg, visual and config_dir override default settings,
    in most cases it is not necessary.
    """
    reg_map = "PhaseDet_Modbus.json"
    reg_names = PhaseDetRegs
