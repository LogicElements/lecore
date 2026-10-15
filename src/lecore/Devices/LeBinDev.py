from __future__ import annotations

import time
from typing import Any, ClassVar, Dict, List, Optional, Union

import serial

from ..TestFrame.TestUtils import *
from ..LeBin.SerialCom import SerialCom
from ..LeBin.RegisterMap import RegisterMap
from ..LeBin.VisualLeBin import VisualLeBin
from ..LeBin.UpgradeFirmware import UpgradeFirmware
from .DeviceBase import DeviceBase
from .Validation import (PathLike, ComSettings, UsbId, load_json, check_lebin_reg_map, check_reg_value, check_file,
                         check_comport, check_baud_rate, check_parity, check_stop_bits, check_timeout)


class LeBinDev(DeviceBase):
    """
    Generic LeBin device using proprietary LE register map and protocol.

    A new device is declared by class attributes, the configuration files are looked up in the directory
    of the module declaring the class::

        class MyDevice(LeBinDev):
            reg_map = "my_registers.json"              # required
            usb = UsbId(vid=1155, pid=22336, sn="MY")  # optional, used by search_com()
            reg_names = MyDeviceRegs                   # optional, checked against the register map

    Without subclassing, use ``LeBinDev(reg_map="path/to/map.json", config_dir="path/to/configs")``.
    """
    #: USB identification used by search_com()
    usb: ClassVar[UsbId] = UsbId()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not isinstance(cls.usb, UsbId):
            raise TypeError(f"{cls.__name__}.usb must be UsbId, got {type(cls.usb).__name__}")

    def __init__(self, com: Optional[PathLike] = None, reg_map: Optional[PathLike] = None, *,
                 config_dir: Optional[PathLike] = None):
        """
        Initialize LeBin device

        The respective parameters allow to redefine default settings. In most cases, it is not necessary.
        Relative paths are resolved against current working directory, then against config_dir.
        :param com: Communication settings file override
        :param reg_map: Register map definition file override
        :param config_dir: Directory with default configuration files override
        """
        self.com = SerialCom()
        self.regs = RegisterMap(self.com)
        self._path = ""
        self._upg = None
        self._vis = None
        self._def_com = self.com_settings
        self._def_regs = None
        self._com_file = ""
        self._reg_file = ""
        self._def_usb = {'vid': self.usb.vid, 'pid': self.usb.pid, 'sn': self.usb.sn}
        self._regs_by_name: Dict[str, dict] = {}

        if not self._init_paths(config_dir, reg_map, type(self).__init__ is not LeBinDev.__init__):
            return

        # Initialize all internal structures
        self._com(com)
        self._reg_map(reg_map)
        self._upgrade()
        self._visual()

    def open(self, comport: Optional[str] = None, baud_rate: Optional[int] = None, parity: Optional[str] = None,
             stop_bits: Optional[Union[int, float]] = None, timeout: Optional[float] = None,
             client: Optional[SerialCom] = None) -> None:
        """
        Open COM port with optional redefinition of default properties.

        Any from the following may redefine default COM port property defined in default json files. For all defaults,
        just open() may be used.
        :param comport: Comport name, e.g., 'COM5'
        :param baud_rate: Baud rate speed
        :param parity: Parity, either 'N', 'E', 'O'
        :param stop_bits: Number of stop bits, 1, 1.5 or 2
        :param timeout: Timeout of communication response in seconds
        :param client: Use previously created communication object (SerialCom), e.g., for sharing a COM port
        :return: None
        """
        # Validate all parameters before changing anything
        if client is not None:
            if not hasattr(client, 'request_response'):
                raise TypeError(f"client must be SerialCom compatible object, got {type(client).__name__}")
            if any(p is not None for p in (comport, baud_rate, parity, stop_bits, timeout)):
                raise ValueError("COM port parameters cannot be combined with external client")
        if comport is not None:
            check_comport(comport)
        if baud_rate is not None:
            check_baud_rate(baud_rate)
        if parity is not None:
            parity = check_parity(parity)
        if stop_bits is not None:
            check_stop_bits(stop_bits)
        if timeout is not None:
            check_timeout(timeout)

        # External communication object
        if client is not None:
            self.com = client
            self.regs.com = client
            if self._upg is not None:
                self._upg.com = client
            return

        # Com port settings
        self.close()
        if comport is not None:
            self.com.comport = comport
        if baud_rate is not None:
            self.com.baud = baud_rate
        if parity is not None:
            self.com.parity = parity
        if stop_bits is not None:
            self.com.stop = stop_bits
        if timeout is not None:
            self.com.timeout = timeout
        self.com.reopen()

    def search_com(self) -> List[str]:
        """
        Search USB devices by VID, PID, and serial number a return a list of viable COM ports
        :return: List of COM ports
        """
        usb = UsbId(**self._def_usb)
        return self.com.get_list_ports(usb.vid, usb.pid, usb.sn)

    def read(self, name: str) -> Any:
        """
        Read register
        :param name: Register name
        :return: Register value on read success
        :return: None on read error
        """
        self._get_reg(name)
        try:
            return self.regs.read_by_name(name)
        except serial.SerialException:
            return None

    def write(self, name: str, value: Any) -> Optional[bool]:
        """
        Write register. Value is checked against register format, Min/Max limits and enumeration.
        A list of values writes consecutive registers starting with the given one.
        :param name: Register name
        :param value: Register value or list of values
        :return: True on write success
        :return: None on write error
        """
        reg = self._get_reg(name)
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        idx = self.regs.regs.index(reg)
        if idx + len(values) > len(self.regs.regs):
            raise ValueError(f"Writing {len(values)} values from register {name} exceeds the register map")
        for i, val in enumerate(values):
            r = self.regs.regs[idx + i]
            if str(r['Access']).startswith('RO'):
                raise ValueError(f"Register {r['Name']} is read-only")
            # LeBin FLOAT is a 32-bit float
            fmt = 'FLOAT32' if r['VarType'] == 'FLOAT' else r['VarType']
            check_reg_value(r, val, fmt, 8 * (1 << (r['Id'] & 7)), signed_ok=False)
        try:
            return self.regs.write_by_name(name, value)
        except serial.SerialException:
            return None

    def close(self) -> None:
        """
        Close communication
        """
        self.com.close()

    def visual(self, timeout: Optional[float] = None, height: int = 800, width: int = 600):
        """
        Run visual modbus graphic application
        :param timeout: Timeout of automatic application shutdown in seconds, None for no timeout
        :param height: Height of window
        :param width: Width of window
        :return: True on exit
        """
        if timeout is not None:
            check_timeout(timeout)
        for n, v in (('height', height), ('width', width)):
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"{n} must be a positive integer, got {v!r}")
        self.close()
        self._vis.draw(height, width)
        return self._vis.handle(timeout)

    def upgrade_firmware(self, file: PathLike, reboot_time: float = 5) -> bool:
        """
        Upgrade firmware in the device. This function also checks the version of firmware after upgrade.
        :param file: Firmware file to upgrade
        :param reboot_time: Time device takes to reboot
        :return: Status of update, True on success, False on failure
        """
        check_file(file, "Firmware")
        if not isinstance(reboot_time, (int, float)) or reboot_time < 0:
            raise ValueError(f"reboot_time must be a non-negative number, got {reboot_time!r}")
        self._get_reg("FIRM_REVISION")
        ver_orig = get_firmware_version(file, 512)

        # Run upgrade procedure
        self._upg.load_file(file)
        ret = self._upg.run()
        self.com.close()
        # Sleep reboot time
        time.sleep(reboot_time)
        self.com.reopen()
        # Check status and version after upgrade
        ver = self.regs.read_by_name("FIRM_REVISION")

        return ret and ver == ver_orig

    def send_file(self, file: PathLike) -> bool:
        """
        Send generic file to device
        :param file: File to send
        :return: Status of update, True on success, False on failure
        """
        check_file(file, "File to send")
        # Run upgrade procedure
        self._upg.load_file(file)
        # LeBin upgrade returns True on success (unlike Modbus return code 0)
        return bool(self._upg.run())

    def _visual(self) -> None:
        """
        Initialize VisualModbus graphic application
        """
        self._vis = VisualLeBin(self.regs)

    def _upgrade(self) -> None:
        """
        Initialize upgrade module
        """
        self._upg = UpgradeFirmware(self.com)

    def _com(self, settings: Optional[PathLike]) -> None:
        """
        Initialize communication module
        :param settings: Communication settings file
        """
        self._com_file = self._path_complete(settings, self._def_com, "Communication settings")
        ComSettings.from_json(self._com_file)
        self.com.open(self._com_file)

    def _reg_map(self, reg_map: Optional[PathLike]) -> None:
        """
        Initialize register map module
        :param reg_map: Register map definition json file
        """
        self._reg_file = self._path_complete(reg_map, self._def_regs, "Register map")
        check_lebin_reg_map(load_json(self._reg_file, "Register map"), self._reg_file)
        self.regs.load(self._reg_file)
        self._regs_by_name = {r['Name']: r for r in self.regs.regs}
        self._check_reg_names()

    def _reg_dict(self) -> Dict[str, dict]:
        if not self._regs_by_name:
            raise RuntimeError(f"{type(self).__name__}: register map is not loaded")
        return self._regs_by_name
