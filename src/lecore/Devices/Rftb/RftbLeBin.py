from ..LeBinDev import *
from .rftbRegs import rftbRegs


class RftbLeBin(LeBinDev):
    """
    Radio-frequency Testing Block LeBin device

    Optional constructor parameters com, reg_map and config_dir override default settings,
    in most cases it is not necessary.
    """
    reg_map = "rftb_registers.json"
    reg_names = rftbRegs
    usb = UsbId(vid=1155, pid=22336, sn="RFTB")
