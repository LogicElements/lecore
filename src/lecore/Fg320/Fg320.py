import serial
from lecore.LeBin import SerialCom


class Fg320:
    """
    Class for simplified communication with FG320 tester
    """
    SUP_FUNCTION = ["OF", "SI", "SQ", "TR", "SA", "US"]
    SUP_MODE = ["normal", "speed", "current", "current AC"]

    @staticmethod
    def get_com_ports():
        return SerialCom().get_list_ports(vid=1155, pid=22336, sn="")

    def __init__(self, com=None):
        """
        Initialize FG-320 device class.
        :param com: COM port. Either string name, such as 'COM1' or SerialCom object. If None we try to find com port
        """
        if com is None:
            coms = self.get_com_ports()
            if len(coms) != 1:
                raise serial.SerialException(f"Could not find just one FG320 port. {coms}")
            com = coms[0]

        if isinstance(com, str):
            com_port = SerialCom()
            com_port.open_com(com, 1)
            com = com_port

        self.com = com
        self.mode = "normal"
        self.function = "OF"
        self.frequency = 100
        self.amplitude = 1
        self.dc = 10
        self.angle = 0
        self.kp_length = 25
        self.order = 1
        self.kp_high = 12
        self.kp_low = 0
        self.cmd = None

    def normal(self, function="OF", frequency=100, amplitude=1, dc=10, angle=0, kp_length=25, order=1, kp_high=12,
               kp_low=0):
        """
        Set FG320 to work in normal, signal mode
        :param function: Waveform shape of signal. Must be one of ["OF", "SI", "SQ", "TR", "SA", "US"]
        :param frequency: Frequency in Hertz (0.1 - 40000)
        :param amplitude: Amplitude (0-peak) in Volts (0 - 4)
        :param dc: DC offset voltage in Volts (-24 - 24)
        :param angle: Angle delay of KP in degrees (0 - 359)
        :param kp_length: Length of key phasor (KP) in percents of signal period (0 - 100)
        :param order: Order of KP (every n-th period contains KP)
        :param kp_high: Voltage of active state of KP in Volts (-24 - 24)
        :param kp_low: Voltage of passive state of KP in volts (-24 - 24)
        :return: None
        """
        self.mode = "normal"
        self.function = function
        self.frequency = frequency
        self.amplitude = amplitude
        self.dc = dc
        self.angle = angle
        self.kp_length = kp_length
        self.order = order
        self.kp_high = kp_high
        self.kp_low = kp_low

    def current_dc(self, dc=4):
        """
        Set FG320 to work in current DC mode
        :param dc:
        :return:
        """
        self.mode = "current"
        self.dc = dc

    def current_ac(self, function="SI", frequency=100, amplitude=4, dc=4, angle=0, kp_length=25, order=0, kp_high=12,
                   kp_low=0):
        """
        Set FG320 to work in current AC mode
        :param function: Waveform shape of current signal. Must be one of ["OF", "SI", "SQ", "TR", "SA", "US"]
        :param frequency: Frequency in Hertz (0.1 - 20000)
        :param amplitude: Amplitude (0-peak) in milliampers (0 - 24)
        :param dc: DC offset current in milliampers (0 - 24)
        :param angle: Angle delay of KP in degrees (0 - 359)
        :param kp_length: Length of key phasor (KP) in percents of signal period (0 - 100)
        :param order: Order of KP (every n-th period contains KP)
        :param kp_high: Voltage of active state of KP in Volts (-24 - 24)
        :param kp_low: Voltage of passive state of KP in volts (-24 - 24)
        :return: None
        """
        if frequency == 0:
            self.mode = "current"
        else:
            self.mode = "current AC"
        self.function = function
        self.frequency = frequency
        self.amplitude = amplitude
        self.dc = dc
        self.angle = angle
        self.kp_length = kp_length
        self.order = order
        self.kp_high = kp_high
        self.kp_low = kp_low

    def speed(self, frequency=10):
        """
        Set FG320 to work in speed mode
        :param frequency: Frequency in Hertz (0.1 - 40000)
        :return: None
        """
        self.mode = "speed"
        self.frequency = frequency

    def write(self):
        """
        Write current selected command to FG320
        :return: None
        """
        if self.mode == "normal":
            if self.function not in self.SUP_FUNCTION:
                raise ValueError(f"Function {self.function} must be one of {self.SUP_FUNCTION}")
            self.cmd = f"{self.function} {int(self.frequency * 10)} {int(self.amplitude * 10000)} " \
                       f"{int(self.dc * 100)} {int(self.angle)} {int(self.kp_length)} {int(self.order)} " \
                       f"{int(self.kp_high * 10)} {int(self.kp_low * 10)}\r\n"
        if self.mode == "current":
            self.cmd = f"IO 0 0 {int(self.dc * 100)}\r\n"
        if self.mode == "current AC":
            if self.function not in self.SUP_FUNCTION:
                raise ValueError(f"Function {self.function} must be one of {self.SUP_FUNCTION}")
            self.cmd = f"IO {int(self.frequency * 10)} {int(self.amplitude * 1000)} {int(self.dc * 100)} " \
                       f"{int(self.angle)} {int(self.kp_length)} {int(self.order)} " \
                       f"{int(self.kp_high * 10)} {int(self.kp_low * 10)} " \
                       f"{self.SUP_FUNCTION.index(self.function) + 1}\r\n"
        if self.mode == "speed":
            self.cmd = f"SD {int(self.frequency * 10)}\r\n"

        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)

    def ramp(self, time=0, shape=0):
        """
        Set ramp time (time for change from last signal settings to the new one). Use 0 to disable ramp.
        This parameter applies to all modes.
        :param time: Ramp time in seconds (resolution is ms)
        :param shape: 0 - linear, 1 - exponential
        :return: None
        """
        self.cmd = f"SR {round(time*1000)} {shape}\r\n"
        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)

    def limit_number_period(self, periods=0):
        """
        Set limit of number of AC signal periods. After this limit is generated, signal remains in DC value.
        Use 0 to disable this limit.
        This applies to Normal, Current AC, and Speed mode.
        :param periods: Number of AC signal periods
        :return:
        """
        self.cmd = f"SP {periods}\r\n"
        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)

    def identify(self):
        """
        Identify FG320 and print its welcome message
        :return: ver: Firmware version as string 1.xx
        :return sn: Serial number as string
        """
        self.cmd = "??\r\n"
        resp = self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 4)
        resp = resp.split("ver. ")[1]
        ver = resp.split(")")[0]
        resp = resp.split(".: ")[1]
        sn = resp.split(">")[0]
        print(f"FG320 FW: {ver} SN: {sn}")
        return ver, sn

    def write_calibration(self, frequency=1.0, amplitude=1.0, dc=1.0, current=1.0):
        """
        Write multiplication calibration coefficients. These values are written during factory programming.
        :param frequency: Frequency multiplication calibration
        :param amplitude: Amplitude multiplication calibration
        :param dc: DC signal multiplication calibration
        :param current: Current multiplication calibration
        :return: None
        """
        self.cmd = f"CA {frequency:.7f} 0 {amplitude:.7f} 0 {dc:.7f} 0 {current:.7f} 0\r\n"
        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)

    def read_calibration(self):
        """
        Read multiplication calibration coefficients. These values are written during factory programming.
        :return: List of Frequency, Amplitude, DC, and Current calibration
        """
        self.cmd = f"RC\r\n"
        resp = self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)
        values = resp.split(" ")
        return [values[2], values[4], values[6], values[8]]

    def write_sn(self, sn=17050001):
        """
        Write serial number.
        Note that serial number can be overwritten only 64 times
        :param sn: New serial number
        :return: None
        """
        self.cmd = f"SS {sn}\r\n"
        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)

    def update_firmware(self, file=None):
        """
        Write new firmware into FG320. FG320 will restart after receiving the whole binary file,
        so the communication port need to be reopened after device boot-up.
        :param file: Firmware file (e.g. FG320_rev_c-20201019-110.bin)
        :return: None
        """
        # Load data
        with open(file, "rb") as f:
            data = bytearray(f.read())
        length = len(data)
        # Write data into device
        self.cmd = f"FW {length}\r\n"
        # Store COM port timeout for future
        timeout = self.com.port.timeout
        self.com.port.timeout = 5
        # Send command and wait for response
        self.com.request_read_line(bytearray(self.cmd, 'utf-8'), 2)
        # Send entire firmware and wait for response
        self.com.request_read_line(data, 2)
        # Restore COM port timeout
        self.com.port.timeout = timeout





