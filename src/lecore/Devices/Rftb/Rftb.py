from ..ModbusDev import *


class Rftb(ModbusDev):
    """
    Radio-frequency Testing Block modbus slave device

    Optional constructor parameters com, reg_map, upg, visual and config_dir override default settings,
    in most cases it is not necessary.

    Register names (rftbRegs) follow the LeBin register map, so they are not checked against Modbus map.
    """
    reg_map = "rftb_Modbus.json"
