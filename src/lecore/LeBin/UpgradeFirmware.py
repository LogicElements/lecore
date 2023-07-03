import struct


class UpgradeFirmware:
    """Class for upgrading firmware according to Le bin protocol"""
    START_BYTE = int('90', 16)
    REQUEST = 255
    RESPONSE = 127
    PAGE_SIZE = 1024

    def __init__(self, com):
        """
        Initialize internal variables, saves serial com port reference
        :param com: Communication object (e.g.: SerialCom or Ble)
        """
        self.com = com
        self.offset = 0
        self.length = 0
        self.data = None

    def load_file(self, filename):
        """
        Load binary file for firmware upgrade. No check is performed
        :param filename: Name of binary file
        :return: None
        """
        with open(filename, "rb") as f:
            self.data = bytearray(f.read())
        self.length = len(self.data)
        self.offset = 0

    def send_request(self):
        """
        Create and send Firmware upgrade request packet. Receive and return response
        :return: Received response packet
        """
        length = min(self.PAGE_SIZE, self.length - self.offset) + 8
        header = [self.START_BYTE, self.REQUEST, length % 256, length // 256]
        idx = struct.pack('L', self.offset)
        request = bytearray(header) + bytearray(idx) + self.data[self.offset:self.offset + length - 8]
        # print(f"Sending offset {self.offset}, length {length - 8}")
        return self.com.request_response(request, 12)

    def parse_response(self, response):
        """
        Parse Firmware upgrade response packet, check return code, save offset
        :param response: Received response to parse
        :return True on success
        :return False on bad return code or short response
        """
        if len(response) != 12:
            return False
        ret_code = struct.unpack_from('L', response, 8)[0]
        # print(f"Acknowledged offset {self.offset}, return code {ret_code}")
        if ret_code == 0:
            self.offset = min(struct.unpack_from('L', response, 4)[0], self.length)
            return True
        else:
            return False

    def reset(self):
        """
        Reset internal offset variable
        :return: None
        """
        self.offset = 0

    def run(self, progress_clb=None):
        """
        Run the upgrade procedure. Send the first packet, parse response, send next packet until all data are sent
        :param progress_clb: Progress callback
        :return True on successful upgrade
        :return False on some error
        """
        ret = True
        while ret:
            if progress_clb is not None:
                progress_clb(self.offset, self.length)
            response = self.send_request()
            if self.offset == self.length:
                return self.parse_response(response)
            ret = self.parse_response(response)
        return ret
