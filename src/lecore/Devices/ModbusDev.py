from __future__ import annotations

import os
import time
from typing import Any, ClassVar, Dict, Optional, Union

from ..TestFrame.TestUtils import *
from ..VisualModbus.MbClient import MbClient
from ..VisualModbus.RegMap import RegMap
from ..VisualModbus.MbUpgrade import MbUpgrade
from ..VisualModbus.VisualMbApp import VisualMbApp
from .DeviceBase import DeviceBase
from .Validation import (PathLike, ComSettings, load_json, check_modbus_reg_map, check_reg_value, check_slave,
                         check_file, check_comport, check_baud_rate, check_parity, check_stop_bits, check_timeout)
try:
    from ..VisualModbus.TextMbApp import TextMbApp
except ImportError:
    class TextMbApp:
        def __init__(self, *kargs):
            pass

        def run(self):
            raise ImportError("Textual packages not present")

_UPGRADE_KEYS = ('align', 'page_bytes', 'address', 'type_binary', 'mode_operation', 'init_delay')


class ModbusDev(DeviceBase):
    """
    Generic Modbus slave device using proprietary LE register map generator.

    A new device is declared by class attributes, the configuration files are looked up in the directory
    of the module declaring the class::

        class MyDevice(ModbusDev):
            reg_map = "MyDevice_Modbus.json"   # required
            reg_names = MyDeviceRegs           # optional, checked against the register map
            # com_settings, upgrade_settings, visual_settings and config_dir have defaults

    Without subclassing, use ``ModbusDev(reg_map="path/to/map.json", config_dir="path/to/configs")``.
    """
    #: Firmware upgrade settings JSON file name
    upgrade_settings: ClassVar[Optional[PathLike]] = "UpgradeSettings.json"
    #: Visual application settings JSON file name
    visual_settings: ClassVar[Optional[PathLike]] = "VisualSettings.json"

    _file_attrs = ('reg_map', 'com_settings', 'upgrade_settings', 'visual_settings')

    def __init__(self, com: Optional[PathLike] = None, reg_map: Optional[PathLike] = None,
                 upg: Optional[PathLike] = None, visual: Optional[PathLike] = None, *,
                 config_dir: Optional[PathLike] = None):
        """
        Initialize modbus slave device

        The respective parameters allow to redefine default settings. In most cases, it is not necessary.
        Relative paths are resolved against current working directory, then against config_dir.
        :param com: Communication settings file override
        :param reg_map: Register map definition file override
        :param upg: Upgrade settings file override
        :param visual: Visual settings file override
        :param config_dir: Directory with default configuration files override
        """
        self.mb = MbClient()
        self.regs = RegMap(self.mb, 1)
        self.slave = None
        self._path = ""
        self._upg = None
        self._vis = None
        self._text = None
        self._def_com = self.com_settings
        self._def_visual = self.visual_settings
        self._def_upg = self.upgrade_settings
        self._def_regs = None
        self._com_file = ""
        self._reg_file = ""
        self._upg_file = ""
        self._vis_file = ""
        self._regs_by_name: Dict[str, dict] = {}

        if not self._init_paths(config_dir, reg_map, type(self).__init__ is not ModbusDev.__init__):
            return

        # Initialize all internal structures
        self._com(com)
        self._reg_map(reg_map)
        self._upgrade(upg)
        self._visual(visual)

    def open(self, slave: Optional[int] = None, comport: Optional[str] = None, baud_rate: Optional[int] = None,
             parity: Optional[str] = None, stop_bits: Optional[Union[int, float]] = None,
             timeout: Optional[float] = None, client: Optional[MbClient] = None) -> Optional[bool]:
        """
        Open COM port with optional redefinition of default properties.

        Any from the following may redefine default COM port property defined in default json files. For all defaults,
        just open() may be used.
        :param slave: Slave address number 1..247
        :param comport: Comport name, e.g., 'COM5'
        :param baud_rate: Baud rate speed
        :param parity: Parity, either 'N', 'E', 'O'
        :param stop_bits: Number of stop bits, 1, 1.5 or 2
        :param timeout: Timeout of communication response in seconds
        :param client: Use previously created MbClient, e.g., for having multiple devices on a single bus (COM port)
        :return: True if port is opened, False on error, None when external client is used
        """
        # Validate all parameters before changing anything
        if slave is not None:
            check_slave(slave)
        if client is not None:
            if not isinstance(client, MbClient):
                raise TypeError(f"client must be MbClient, got {type(client).__name__}")
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

        # Slave address
        if slave is not None:
            self.slave = slave
            self.regs.slave = slave
            if self._upg is not None:
                self._upg.slave = slave

        # External modbus clients object
        if client is not None:
            self._set_client(client)
            return None

        # Com port settings
        self.close()
        if comport is not None:
            self.mb.s['comport'] = comport
        if baud_rate is not None:
            self.mb.s['baud_rate'] = baud_rate
        if parity is not None:
            self.mb.s['parity'] = parity
        if stop_bits is not None:
            self.mb.s['stop_bits'] = stop_bits
        if timeout is not None:
            self.mb.s['timeout'] = timeout
        return self.mb.open()

    def read(self, name: str) -> Any:
        """
        Read register (holding or input)
        :param name: Register name
        :return: Register value on read success
        :return: None on read error
        """
        self._get_reg(name)
        return self.regs.read_by_name(name)

    def write(self, name: str, value: Any) -> Optional[int]:
        """
        Write holding register. Value is checked against register format, Min/Max limits and enumeration.
        :param name: Register name
        :param value: Register value
        :return: 0 on write success
        :return: None on write error
        """
        reg = self._get_reg(name)
        if reg['Type'] != 'HOLD' or str(reg.get('Access', '')).startswith('RO'):
            raise ValueError(f"Register {name} is read-only")
        check_reg_value(reg, value, reg['Format'], 16 * len(reg['Address']))
        return self.regs.write_by_name(name, value)

    def close(self) -> None:
        """
        Close modbus communication
        """
        if self.mb.client is not None:
            self.mb.close()

    def visual(self, timeout: Optional[float] = None):
        """
        Run visual modbus graphic application
        :param timeout: Timeout of automatic application shutdown in seconds, None for no timeout
        :return: True on exit
        """
        if timeout is not None:
            check_timeout(timeout)
        self.close()
        return self._vis.handle(timeout)

    def textual(self) -> None:
        """
        Run textual user interface application
        """
        self._text.run()

    def upgrade_firmware(self, file: PathLike, reboot_time: float = 5) -> bool:
        """
        Upgrade firmware in the modbus slave device. This function also checks the version of firmware after upgrade.
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
        ret = self._upg.run_upgrade()
        # Sleep reboot time
        time.sleep(reboot_time)
        # Check status and version after upgrade
        ver = self.regs.read_by_name("FIRM_REVISION")

        return ret == 0 and ver == ver_orig

    def send_file(self, file: PathLike) -> bool:
        """
        Send generic file to device
        :param file: File to send
        :return: Status of update, True on success, False on failure
        """
        check_file(file, "File to send")
        # Run upgrade procedure
        self._upg.load_file(file)
        ret = self._upg.run_upgrade()
        return ret == 0

    def _set_client(self, mb: MbClient) -> None:
        """
        Use external modbus client in all internal modules
        :param mb: Modbus client
        """
        self.mb = mb
        self.regs.mb = mb
        if self._upg is not None:
            self._upg.mb = mb
        for app in (self._vis, self._text):
            if app is None or not hasattr(app, 'mb'):
                continue
            app.mb = mb
            for attr in ('regs', 'reg', '_update'):
                sub = getattr(app, attr, None)
                if sub is not None and hasattr(sub, 'mb'):
                    sub.mb = mb

    def _visual(self, settings: Optional[PathLike]) -> None:
        """
        Initialize VisualModbus graphic application
        :param settings: Visual settings json file
        """
        self._vis_file = self._path_complete(settings, self._def_visual, "Visual settings")
        s = load_json(self._vis_file, "Visual settings")
        if not isinstance(s, dict) or 'slave_address' not in s:
            raise ValueError(f"Visual settings file {self._vis_file} must contain 'slave_address'")
        try:
            check_slave(s['slave_address'])
        except (TypeError, ValueError) as e:
            raise type(e)(f"Visual settings file {self._vis_file}: {e}") from None
        self._vis = VisualMbApp(self._vis_file, self._upg_file, self._com_file, self.slave, self._reg_file, self.mb)
        self.regs.slave = self._vis.slave
        self.slave = self._vis.slave
        self._upg.slave = self._vis.slave
        self._text = TextMbApp(self._vis_file, self._upg_file, self._com_file, self.slave, self._reg_file, self.mb)

    def _upgrade(self, settings: Optional[PathLike]) -> None:
        """
        Initialize upgrade module
        :param settings: Upgrade settings json file
        """
        self._upg_file = self._path_complete(settings, self._def_upg, "Upgrade settings")
        s = load_json(self._upg_file, "Upgrade settings")
        missing = [k for k in _UPGRADE_KEYS if not isinstance(s, dict) or k not in s]
        if missing:
            raise ValueError(f"Upgrade settings file {self._upg_file} misses keys: {', '.join(missing)}")
        self._upg = MbUpgrade(self._upg_file, self.mb, self.slave)

    def _com(self, settings: Optional[PathLike]) -> None:
        """
        Initialize modbus communication module
        :param settings: Modbus communication settings file
        """
        self._com_file = self._path_complete(settings, self._def_com, "Communication settings")
        ComSettings.from_json(self._com_file)
        self.mb.open(self._com_file)

    def _reg_map(self, reg_map: Optional[PathLike]) -> None:
        """
        Initialize register map module
        :param reg_map: Register map definition json file
        """
        self._reg_file = self._path_complete(reg_map, self._def_regs, "Register map")
        check_modbus_reg_map(load_json(self._reg_file, "Register map"), self._reg_file)
        self.regs = RegMap(self.mb, self.regs.slave)
        self.regs.load(self._reg_file)
        self._regs_by_name = {r['Name']: r for r in self.regs.input + self.regs.hold}
        self._check_reg_names()

    def _reg_dict(self) -> Dict[str, dict]:
        if not self._regs_by_name:
            raise RuntimeError(f"{type(self).__name__}: register map is not loaded")
        return self._regs_by_name

