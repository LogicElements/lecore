import io
import json
import serial
import serial.tools.list_ports


class SerialCom:
    """Serial communication class"""

    def __init__(self):
        self.port = None
        self.settings = None
        self.ports = None
        self.ble = False
        self.baud = 115200
        self.stop = 1
        self.parity = 'N'
        self.timeout = 1.0
        self.comport = None

    def open(self, filename):
        """
        Open com port with given communication settings
        :param filename: Json settings of COM port
        :return: None
        """
        with io.open(filename, 'r', encoding='utf-8-sig') as f:
            s = json.load(f)
            self.settings = s

        self.comport = s['comport']
        self.baud = s['baud_rate']
        self.stop = s['stop_bits']
        self.parity = s['parity']
        self.timeout = s['timeout']
        return self._open_comport()

    def open_com(self, com, timeout):
        """
        Open comport given just com port and timeout.
        This is usually used with USB communication
        :param com: Com port name
        :param timeout: Timeout of communication in seconds
        :return: True on success, False on exception
        """
        self.comport = com
        self.timeout = timeout
        return self._open_comport()

    def reopen(self):
        """
        Re-open COM port
        :return: None
        """
        self._open_comport()

    def close(self):
        """
        Close com port
        :return: None
        """
        if self.port is not None and self.port.is_open:
            self.port.close()
        self.port = None

    def request_response(self, msg, resp_len):
        """
        Send message and receive response
        :param msg: Message byte array to send
        :param resp_len: Expected length of data to receive
        :return: Received data
        """
        itr = 0
        self._write_reopen(msg)
        while self.port.out_waiting != 0:
            itr += 1
        resp = self.port.read(resp_len)

        return resp

    def request_read_line(self, msg, lines):
        """
        Send message and receive response
        :param msg: Message byte array to send
        :param lines: Number of lines we expect to receive
        :return: Received data
        """
        itr = 0
        self._write_reopen(msg)
        resp = ""
        while self.port.out_waiting != 0:
            itr += 1
        for i in range(lines):
            resp += self.port.readlines(lines)[0].decode('utf-8')

        return resp

    def get_rssi(self):
        """
        Get signal strength compatibility function
        :return: -1 always
        """
        return -1

    def get_list_ports(self, vid=1155, pid=22337, sn=None):
        """
        Get list of all COM ports with given VID and PID
        :param sn: Fragment of serial number to find
        :param vid: Vendor ID of USB device
        :param pid: Product ID of USB device
        :return: List of COm ports
        """
        self.ports = []
        ports = serial.tools.list_ports.comports()
        for comport in ports:
            if vid == 0 or (comport.pid == pid and comport.vid == vid and (sn is None or sn in comport.serial_number)):
                self.ports.append(comport.device)
        return self.ports

    def _open_comport(self):
        """
        Open com port with stored properties
        :return: True on success
        :return: False on serial exception
        """
        try:
            self.port = serial.Serial(port=self.comport, baudrate=self.baud, stopbits=self.stop, parity=self.parity,
                                      timeout=self.timeout)
            return True
        except serial.SerialException:
            return False

    def _write_reopen(self, msg):
        """
        Write data into serial port. On serial exception reopen com port and write it again
        :param msg: Message to write
        :return: None
        """
        try:
            self.port.write(msg)
        except (serial.SerialException, AttributeError):
            if self.comport is not None:
                self.close()
                self._open_comport()
                self.port.write(msg)
            else:
                print("No com port opened yet")
                raise serial.SerialException


if __name__ == '__main__':
    port = SerialCom()

    coms = port.get_list_ports()

    print(coms)
