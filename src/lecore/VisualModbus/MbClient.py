import io
import json
import logging

from time import sleep
try:
    from pymodbus.client.sync import ModbusSerialClient as ModbusClient
except ModuleNotFoundError:
    from pymodbus.client import ModbusSerialClient as ModbusClient


class MbClient:
    """
    Class for communication with modbus client
    """

    def __init__(self):
        """
        Initialize all internal variables
        """
        self.errors = 0
        self.rr = None
        self.comport = None
        self.s = None
        self.client = None
        self.log = logging.getLogger()
        self._connectionless = False

    def open(self, settings=None, connectionless=False):
        """
        Open com port with parameters given in JSON
        :param settings: Json settings file
        :param connectionless: If True, connection is open before read/write operation and closed just after
        :return: True if connected, False on error
        """
        # Read settings JSON
        if settings is not None:
            with io.open(settings, 'r', encoding='utf-8-sig') as f:
                self.s = json.load(f)
        self.comport = self.s['comport']
        # Open port
        self.client = ModbusClient(method='rtu', port=self.s['comport'], timeout=self.s['timeout'],
                                   baudrate=self.s['baud_rate'], parity=self.s['parity'],
                                   stopbits=self.s['stop_bits'])
        # Set additional timeout parameters
        self.client.inter_char_timeout *= self.s['inter_char_timeout']  # default 0.000859375
        if 'minimal_inter_char_timeout' in self.s:
            min_inter = self.s['minimal_inter_char_timeout']
        else:
            min_inter = 0.05
        self.client.inter_char_timeout = max(self.client.inter_char_timeout, min_inter)
        self.client.silent_interval *= self.s['silent_interval']
        # Connect to port
        self._connectionless = connectionless
        if self._connectionless:
            ret = False
        else:
            ret = self.client.connect()
        if ret is True:
            self.log.warning('Port {0} opened at baud rate {1}, parity {2}, stop bits {3}'.format(
                self.s['comport'], self.s['baud_rate'], self.s['parity'], self.s['stop_bits']))
        return ret

    def open_direct(self, comport, timeout=1, baud_rate=19200, parity='E', stop_bits=1, inter=30.0,
                    min_inter=0.05, client=None, connectionless=False):
        """
        Open com port directly without json settings. Passed client can be used for modbus operations
        """
        self.s = {'comport': comport, 'timeout': timeout, 'baud_rate': baud_rate, 'stop_bits': stop_bits,
                  'parity': parity, 'inter_char_timeout': inter, 'minimal_inter_char_timeout': min_inter,
                  'silent_interval': 1.0}
        if client is None:
            self.open(connectionless=connectionless)
        else:
            self.client = client

    def close(self):
        """
        Close communication port
        :return: None
        """
        self.log.warning('Port {} is closed now.'.format(self.comport))
        self.client.close()
        sleep(0.25)

    def read(self, request):
        """
        Send read request to slave device, parse response and return register values
        :param request: Request dictionary, such as {'Address': 50, 'Count': 5, 'Type': "INPUT", 'Slave': 1}
        :return: Array of read register values on success
        :return: None on read error
        """
        if not self.client.is_socket_open():
            if self._connectionless:
                if not self.client.connect():
                    sleep(0.5)
                    return None
            else:
                self.log.warning('Port {} is not opened. Try to open the port first'.format(self.comport))
                if self.comport is None:
                    return None
                if self.open() is False:
                    return None
        if request['Type'].lower() == 'Input'.lower():
            ret = self.read_input(request)
        else:
            ret = self.read_hold(request)
        if self._connectionless:
            self.client.close()
        return ret

    def read_input(self, request):
        """
        Send read Input register request to slave device, parse response and return register values
        :param request: Request dictionary, such as {'Address': 50, 'Count': 5, 'Type': "INPUT", 'Slave': 1}
        :return: Array of read register values on success
        :return: None on read error
        """
        try:
            self.rr = self.client.read_input_registers(request['Address'], request['Count'], unit=request['Slave'])
        except TypeError:
            self.rr = self.client.read_input_registers(request['Address'], request['Count'], request['Slave'])
        if self.rr.isError():
            self.log.error(str(self.rr) + str(request))
            return None
        else:
            self.log.info('Read input registers from slave {} at address {}, count {}.'
                          .format(request['Slave'], request['Address'], request['Count']))
            return self.rr.registers

    def read_hold(self, request):
        """
        Send read Holding register request to slave device, parse response and return register values
        :param request: Request dictionary, such as {'Address': 50, 'Count': 5, 'Type': "INPUT", 'Slave': 1}
        :return: Array of read register values on success
        :return: None on read error
        """
        try:
            self.rr = self.client.read_holding_registers(request['Address'], request['Count'], unit=request['Slave'])
        except TypeError:
            self.rr = self.client.read_holding_registers(request['Address'], request['Count'], request['Slave'])
        if self.rr.isError():
            self.log.error(str(self.rr) + str(request))
            return None
        else:
            self.log.info('Read holding registers from slave {} at address {}, count {}.'
                          .format(request['Slave'], request['Address'], request['Count']))
            return self.rr.registers

    def write_hold(self, request):
        """
        Send write holding register request to slave device and verify response
        :param request: Request dictionary, such as 'Address': 50, 'Values': [10, 11, 12], 'Type': "HOLD", 'Slave': 1
        :return: 0 on success
        :return: None on fail
        """
        if not self.client.is_socket_open():
            if self._connectionless:
                if not self.client.connect():
                    sleep(0.5)
                    return None
            else:
                self.log.warning('Port {} is not opened. Try to open the port first'.format(self.comport))
                if self.comport is None:
                    return None
                if self.open() is False:
                    return None
        try:
            self.rr = self.client.write_registers(request['Address'], request['Values'], unit=request['Slave'])
        except TypeError:
            self.rr = self.client.write_registers(request['Address'], request['Values'], request['Slave'])
        if self._connectionless:
            self.client.close()
        if isinstance(self.rr, bytes):
            return 0
        if self.rr.isError():
            self.log.error(str(self.rr) + str(request))
            return None
        else:
            self.log.info('Write holding registers to slave {} at address {}, count {}.'
                          .format(request['Slave'], request['Address'], request['Count']))
            return 0
