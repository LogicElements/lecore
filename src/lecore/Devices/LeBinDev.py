import time
from ..TestFrame.TestUtils import *
from ..LeBin.SerialCom import SerialCom
from ..LeBin.RegisterMap import RegisterMap
from ..LeBin.VisualLeBin import VisualLeBin
from ..LeBin.UpgradeFirmware import UpgradeFirmware


class LeBinDev:
    """
    Generic LeBin device using proprietary LE register map and protocol
    """

    def __init__(self):
        """
        Initialize modbus slave device
        """
        self.com = SerialCom()
        self.regs = RegisterMap(self.com)
        self._path = ""
        self._upg = None
        self._vis = None
        self._def_com = "ComSettings.json"
        self._def_regs = "None"
        self._com_file = ""
        self._reg_file = ""
        self._def_usb = {'vid': 0, 'pid': 0, 'sn': ''}

    def open(self, comport=None, baud_rate=None, parity=None, stop_bits=None, timeout=None, client=None):
        """
        Open COM port with optional redefinition of default properties.

        Any from the following may redefine default COM port property defined in default json files. For all defaults,
        just open() may be used.
        :param comport: Comport name, e.g., 'COM5'
        :param baud_rate: Baud rate speed
        :param parity: Parity, either 'N', 'E', 'O'
        :param stop_bits: Number of stop bits
        :param timeout: Timeout of communication response in seconds
        :param client: Use previously created COM port, e.g., for having multiple devices on a single bus (COM port)
        :return: None
        """
        # External modbus clients object
        if client:
            self.com = client
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

    def search_com(self):
        """
        Search USB devices by VID, PID, and serial number a return a list of viable COM ports
        :return: List of COM ports
        """
        return self.com.get_list_ports(self._def_usb['vid'], self._def_usb['pid'], self._def_usb['sn'])

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
        self.com.close()

    def visual(self, timeout, height=800, width=600):
        """
        Run visual modbus graphic application
        :param timeout: Timeout of automatic application shutdown in seconds
        :param height: Height of window
        :param width: Width of window
        :return: True on exit
        """
        self.close()
        self._vis.draw(height, width)
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
        ret = self._upg.run()
        self.com.close()
        # Sleep reboot time
        time.sleep(reboot_time)
        self.com.reopen()
        # Check status and version after upgrade
        ver = self.regs.read_by_name("FIRM_REVISION")

        return ret and ver == ver_orig

    def send_file(self, file):
        """
        Send generic file to device
        :param file: File to send
        :return: Status of update, True on success, False on failure
        """
        # Run upgrade procedure
        self._upg.load_file(file)
        ret = self._upg.run()
        return ret == 0

    def _visual(self):
        """
        Initialize VisualModbus graphic application
        """
        self._vis = VisualLeBin(self.regs)

    def _upgrade(self):
        """
        Initialize upgrade module
        """
        self._upg = UpgradeFirmware(self.com)

    def _com(self, settings):
        """
        Initialize modbus communication module
        :param settings: Modbus communication settings file
        """
        self._com_file = self.__path_complete(settings, self._def_com)
        self.com.open(self._com_file)

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
