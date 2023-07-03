from . import *
from ..VisualModbus.RegMap import RegMap as rm
from ..VisualModbus.MbClient import MbClient
import io


def assert_err(rr, exp):
    """
    Assert that request response contains given error message
    :param rr: Received response
    :param exp: Piece of expected error
    :return: True on expected error
    :return: False otherwise
    """
    if rr.isError():
        if exp in str(rr):
            return True
    return False


class RtuClient(object):

    def __init__(self, com_set, vis_set, test='SYS_TEST'):
        """
        Initialize rtu client module
        :param com_set: Communication settings json file
        :param vis_set: Visual settings json file
        :param test: Name of testing register
        """
        self.mb = MbClient()
        self.mb.open(com_set)
        self.test = test
        with io.open(vis_set, 'r', encoding='utf-8-sig') as f:
            s = json.load(f)
        self.regs = rm(self.mb, s['slave_address'])
        self.regs.load(s['reg_map'])
        if 'attempts' in s:
            self.regs.attempts = s['attempts']
        if 'retry_delay' in s:
            self.regs.delay = s['retry_delay']

    def close(self):
        """
        Close modbus connection
        :return: None
        """
        self.mb.close()
        self.mb = None

    def get_regs(self):
        """
        Get registers object
        :return: Registers object
        """
        return self.regs

    def read_write_reopen(self, baud_rate, parity, stop_bits):
        """
        Close and reopen communication port with new settings
        :param baud_rate: Baud rate
        :param parity: Parity {'N', 'E', 'O'}
        :param stop_bits: Stop bits
        :return: None
        """
        self.mb.close()
        self.mb.s['baud_rate'] = baud_rate
        self.mb.s['parity'] = parity
        self.mb.s['stop_bits'] = stop_bits
        self.mb.open()

    def read_write_test(self, delay, iterations):
        """
        Perform simple read/write test which is composed of reading all registers, writing sequence number into
        test register and reading it back
        :param delay: Delay between iterations in seconds
        :param iterations: Number of iterations
        :return: Error count
        """
        self.regs.get_error_count()
        errors = 0
        for itr in range(iterations):
            # Read all registers
            self.regs.read_in()
            self.regs.read_hold()

            # Perform write and read back
            self.regs.write_by_name(self.test, itr)
            value = self.regs.read_by_name(self.test)
            if value != itr:
                errors += 1
            sleep(delay)

        return self.regs.get_error_count() + errors

