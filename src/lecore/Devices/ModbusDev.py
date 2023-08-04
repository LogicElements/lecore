import time
from ..TestFrame.TestUtils import *
from ..VisualModbus.MbClient import MbClient
from ..VisualModbus.RegMap import RegMap
from ..VisualModbus.MbUpgrade import MbUpgrade
from ..VisualModbus.VisualMbApp import VisualMbApp


class ModbusDev:
    """
    Generic Modbus slave device using proprietary LE register map generator
    """

    def __init__(self):
        """
        Initialize modbus slave device
        """
        self.mb = MbClient()
        self.regs = RegMap(self.mb, 1)
        self.slave = None
        self._path = ""
        self._upg = None
        self._vis = None
        self._def_com = "ComSettings.json"
        self._def_visual = "VisualSettings.json"
        self._def_upg = "UpgradeSettings.json"
        self._def_regs = "None"
        self._com_file = ""
        self._reg_file = ""
        self._upg_file = ""
        self._vis_file = ""

    def open(self, slave=None, comport=None, baud_rate=None, parity=None, stop_bits=None, timeout=None, client=None):
        """
        Open COM port with optional redefinition of default properties.

        Any from the following may redefine default COM port property defined in default json files. For all defaults,
        just open() may be used.
        :param slave: Slave address number
        :param comport: Comport name, e.g., 'COM5'
        :param baud_rate: Baud rate speed
        :param parity: Parity, either 'N', 'E', 'O'
        :param stop_bits: Number of stop bits
        :param timeout: Timeout of communication response in seconds
        :param client: Use previously created COM port, e.g., for having multiple devices on a single bus (COM port)
        :return: None
        """
        # Slave address
        if slave is not None:
            self.slave = slave
            self.regs.slave = slave
            self._upg.slave = slave

        # External modbus clients object
        if client:
            self.mb = client
            return

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
        self.mb.open()

    def read(self, name):
        """
        Read register (holding or input)
        :param name: Register name
        :return: Register value on read success
        :return: None on read error
        """
        return self.regs.read_by_name(name)

    def write(self, name, value):
        """
        Write register (holding or input)
        :param name: Register name
        :param value: Register value
        :return: 0 on write success
        :return: None on write error
        """
        return self.regs.write_by_name(name, value)

    def close(self):
        """
        Close modbus communication
        """
        self.mb.close()

    def visual(self, timeout):
        """
        Run visual modbus graphic application
        :param timeout: Timeout of automatic application shutdown in seconds
        :return: True on exit
        """
        self.close()
        return self._vis.handle(timeout)

    def upgrade_firmware(self, file, reboot_time=5):
        """
        Upgrade firmware in the modbus slave device. This function also checks the version of firmware after upgrade.
        :param file: Firmware file to upgrade
        :param reboot_time: Time device takes to reboot
        :return: Status of update, True on success, False on failure
        """
        ver_orig = get_firmware_version(file, 512)

        # Run upgrade procedure
        self._upg.load_file(file)
        ret = self._upg.run_upgrade()
        # Sleep reboot time
        time.sleep(reboot_time)
        # Check status and version after upgrade
        ver = self.regs.read_by_name("FIRM_REVISION")

        return ret == 0 and ver == ver_orig

    def send_file(self, file):
        """
        Send generic file to device
        :param file: File to send
        :return: Status of update, True on success, False on failure
        """
        # Run upgrade procedure
        self._upg.load_file(file)
        ret = self._upg.run_upgrade()
        return ret == 0

    def _visual(self, settings):
        """
        Initialize VisualModbus graphic application
        :param settings: Visual settings json file
        """
        self._vis_file = self.__path_complete(settings, self._def_visual)
        self._vis = VisualMbApp(self._vis_file, self._upg_file, self._com_file, self.slave, self._reg_file, self.mb)
        self.regs.slave = self._vis.slave
        self.slave = self._vis.slave
        self._upg.slave = self._vis.slave

    def _upgrade(self, settings):
        """
        Initialize upgrade module
        :param settings: Upgrade settings json file
        """
        self._upg_file = self.__path_complete(settings, self._def_upg)
        self._upg = MbUpgrade(self._upg_file, self.mb, self.slave)

    def _com(self, settings):
        """
        Initialize modbus communication module
        :param settings: Modbus communication settings file
        """
        self._com_file = self.__path_complete(settings, self._def_com)
        self.mb.open(self._com_file)

    def _reg_map(self, reg_map):
        """
        Initialize register map module
        :param reg_map: Register map definition json file
        """
        self._reg_file = self.__path_complete(reg_map, self._def_regs)
        self.regs.load(self._reg_file)

    def __path_complete(self, arg, default):
        """
        Complete relative path to absolute path
        :param arg: Passed relative path
        :param default: Default path
        :return: Absolute path
        """
        if arg is None:
            ret = self._path + default
        else:
            # elif "/" in arg or '\\' in arg:
            ret = arg
        # else:
        #     ret = self._path + arg
        return ret

