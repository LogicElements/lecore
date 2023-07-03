import io
import json
import struct


def _reg_length(reg):
    """
    Get length of register
    :param reg Register
    :return: Byte length of register
    """
    return 1 << (reg['Id'] & 7)


def _get_value(reg):
    """
    Return value of register in respective format
    :param reg Register
    :return Register value
    """
    if reg['VarType'] == 'FLOAT' or reg['VarType'] == 'FLOAT32':
        return float(reg['Value'])
    elif reg['VarType'] == 'STRING':
        return reg['Value']
    else:
        return int(reg['Value'])


def _has_hex(reg):
    """
    Return true if register is integer type
    :param reg: Register
    :return: True if hex is supported
    :return: False if hex is not supported
    """
    if reg['VarType'] in ('FLOAT', 'FLOAT32', 'STRING'):
        return False
    else:
        return True


class RegisterMap:
    """ Map of register, based on LeBinPro representation
        This class can be used with UART or BLE
    """
    START_BYTE = int('90', 16)
    COM_WRITE_REQUEST = 129
    CMD_READ_REQUEST = 130

    def __init__(self, com):
        """
        Initialize register map and pass communication block
        :param com Instance of either SerialCom or LeBle
        """
        self.max_len = 20
        self.com = com
        self.errors = 0
        self.bounds = 0
        self.last_write = None
        self.regs = None
        if com.ble:
            self.START_BYTE = 0x80

    def load(self, filename):
        """
        Load register map from json and sort into input and holding
        :param filename: File name of JSON register map
        :return: None
        """
        with io.open(filename, 'r', encoding='utf-8-sig') as f:
            self.regs = json.load(f)
        for r in self.regs:
            if "Category" in r:
                r["Name"] = r["Category"] + "_" + r["Name"]
            if "Min" not in r:
                r["Min"] = 0
            if "Max" not in r:
                r["Max"] = 0

    def read_by_nb(self, number):
        """ Read register indexed by ordinal number in the map
            This is useful for visual application
        :param number: Ordinal number of register in map
        :return: New value of the register
        """
        reg = self.regs[number]
        self.read_register(number)
        return _get_value(reg)

    def read_by_name(self, name, count=1):
        """ Read register given by name
            This is useful for script testing
        :param name: Name of the register
        :param count: Number of consecutive registers to read
        :return: New value of register(s)
        """
        reg = next(x for x in self.regs if x['Name'] == name)
        idx = self.regs.index(reg)
        if self.read_register(idx, count) is None:
            return None
        if count == 1:
            return _get_value(reg)
        else:
            return [_get_value(self.regs[idx + i]) for i in range(count)]

    def read_register(self, idx, count=1):
        """
        Read register already selected
        :param idx: Ordinal number of register in the list
        :param count: Number of registers to read
        :return: New value of register(s)
        """
        msg = bytearray([self.START_BYTE, self.CMD_READ_REQUEST, 0, 0])
        resp_len = 4
        for i in range(count):
            reg = self.regs[idx + i]
            resp_len += self.read_append_reg(msg, reg)
        struct.pack_into('H', msg, 2, len(msg))
        return self.request_resp(msg, resp_len)

    def read_all(self):
        """
        Read all registers in single command
        :return: New value of registers
        """
        msg = bytearray([self.START_BYTE, self.CMD_READ_REQUEST, 0, 0])
        resp_len = 4
        for reg in self.regs:
            resp_len += self.read_append_reg(msg, reg)
        struct.pack_into('H', msg, 2, len(msg))
        return self.request_resp(msg, resp_len)

    def read_append_reg(self, msg, reg):
        """
        Append register into stream to get one packet
        :param msg: Message containing stream
        :param reg: Register to append
        :return: Length increment of msg
        """
        val = struct.pack('L', reg['Id'])
        msg += bytearray(val)
        return 4 + _reg_length(reg)

    def write_by_nb(self, number, value):
        """
        Write register indexed by ordinal number
        This is useful for visual application
        :param number: Ordinal number of register
        :param value: New value of register
        :return: True on success, None on failure
        """
        # reg = self.regs[number]
        return self.write_register(number, value)

    def write_by_name(self, name, value):
        """
        Write register given by its name
        :param name: Name of register
        :param value: New value of register
        :return: True on success, None on failure
        """
        reg = next(x for x in self.regs if x['Name'] == name)
        idx = self.regs.index(reg)
        return self.write_register(idx, value)

    def write_register(self, idx, value):
        """ Write register already selected
        :param idx: Index of register
        :param value: New value of register
        :return: True on success, None on failure
        """
        msg = bytearray(4)
        msg[0] = self.START_BYTE
        msg[1] = self.COM_WRITE_REQUEST
        try:
            iter(value)
            if isinstance(value, str):
                value = [value]
        except TypeError:
            value = [value]
        for val in value:
            reg = self.regs[idx]
            self.write_append_reg(msg, reg, val)
            idx += 1
        struct.pack_into('H', msg, 2, len(msg))
        return self.request_resp(msg, len(msg))

    def write_all(self):
        """
        Write all writeable registers in a single packet
        :return: True on success, None on failure
        """
        msg = bytearray(4)
        msg[0] = self.START_BYTE
        msg[1] = self.COM_WRITE_REQUEST
        for reg in self.regs:
            if reg['Access'] in ('RW', 'RWF'):
                idx = self.regs.index(reg)
                self.write_append_reg(msg, reg, reg['Value'])
        struct.pack_into('H', msg, 2, len(msg))
        return self.request_resp(msg, len(msg))

    def write_append_reg(self, msg, reg, value):
        """
        Append register into stream to get one packet
        :param msg: Message containing stream
        :param reg: Register to append
        :param value: Value to write
        :return: None
        """
        val = struct.pack('L', reg['Id'])
        length = _reg_length(reg)
        if reg['VarType'] in 'FLOAT':
            val2 = struct.pack('f', float(value))
        elif reg['VarType'] in 'STRING':
            val2 = bytearray(value, 'utf-8')
            val2 += bytearray(length - len(val2))
        else:
            val2 = int(value).to_bytes(length, 'little')
        msg += bytearray(val) + bytearray(val2)

    def request_resp(self, req, resp_len):
        """
        Send request and check response
        :param req: Request message to send
        :param resp_len: Expected length of response
        :return: True on success, None on failure
        """
        resp = self.com.request_response(req, resp_len)
        if len(resp) < 4:
            return None
        length = self.check_response(resp)
        if length is not None:
            self.parse_stream(resp)
        return True if length is not None else None

    def parse_stream(self, data):
        """
        Parse received stream of ID + Data
        :param data: Received data to parse
        :return: None
        """
        idx = 4   # Skip header
        while idx <= len(data) - 5:
            id_cur = struct.unpack_from('L', data, idx)[0]
            idx += 4
            reg = next(x for x in self.regs if x['Id'] == id_cur)
            length = _reg_length(reg)
            if reg['VarType'] in ('INT', 'BIN', 'ENUM'):
                value = int.from_bytes(data[idx:idx+length:1], 'little')
                reg['Value'] = str(value)
            if reg['VarType'] in 'FLOAT':
                value = struct.unpack_from('f', data, idx)[0]
                reg['Value'] = str(round(value, 4))
            if reg['VarType'] in 'STRING':
                value = str(data[idx:idx+length:1], 'utf-8').strip('\x00')
                reg['Value'] = str(value)
            idx += length

    def check_response(self, data):
        """
        Check received buffer if it contains valid packet
        :param data: Received data to check on completeness
        :return: Length of parsed data
        :return: None on failure
        """
        if data[0] == self.START_BYTE:
            length = data[2] + data[3] * 256
            if length <= len(data):
                return length
        self.errors += 1
        return None

    def check_limits(self, reg):
        """
        Check minimum and maximum limits of register
        :param reg: Register
        :return: None
        """
        if reg['Min'] != 0 and reg['Max'] != 0:
            if reg['Format'] == 'FLOAT' or reg['Format'] == 'FLOAT32':
                if float(reg['Value']) > reg['Max']:
                    self.bounds += 1
                if float(reg['Value']) < reg['Min']:
                    self.bounds += 1
            elif reg['Format'] == 'STRING':
                if len(reg['Value']) > reg['Max']:
                    self.bounds += 1
                if len(reg['Value']) < reg['Min']:
                    self.bounds += 1
            else:
                if int(reg['Value']) > reg['Max']:
                    self.bounds += 1
                if int(reg['Value']) < reg['Min']:
                    self.bounds += 1

    def get_error_count(self, clear=1):
        """
        Return number of errors
        :param clear Set to 1 in order to clear error counter
        :return: Error count
        """
        ret = self.errors
        if clear:
            self.errors = 0
        return ret

    def get_out_of_bound(self, clear=1):
        """
        Return number of out-of-bound errors
        :param clear Set to 1 in order to clear out-of-bound counter
        :return: Out-of-bound error count
        """
        ret = self.bounds
        if clear:
            self.bounds = 0
        return ret

    def from_visual(self, values, suffix):
        """
        Pass all values from visual application to check for changes in values
        :param values: List of all values
        :param suffix: Suffix of hex values
        :return: Result of write operation
        """
        ret = None
        for reg in self.regs:
            write = 0
            new_val = values[reg['Name']]
            if reg['Value'] != new_val:
                write = 1
            elif _has_hex(reg):
                new_val = values[reg['Name'] + suffix]
                if new_val != self.val_to_hex(reg):
                    new_val = str(int(new_val.replace("0x", ""), 16))
                    write = 1
            if write != 0:
                idx = self.regs.index(reg)
                ret = self.write_register(idx, new_val)
                self.last_write = (idx, new_val)

        if ret is None and self.last_write is not None:
            ret = self.write_register(self.last_write[0], self.last_write[1])
        return ret

    def val_to_hex(self, reg):
        """
        Convert value to hexadecimal
        :param reg: Register
        :return: Hexadecimal value
        """
        if not _has_hex(reg):
            return ""
        else:
            try:
                ret = hex(int(reg['Value']))
            except ValueError:
                ret = ""
            return ret
