"""
In-memory fake transports simulating devices for hardware-free tests of the device test suite
"""
try:
    from lecore.VisualModbus.MbClient import MbClient
except ImportError:
    from src.lecore.VisualModbus.MbClient import MbClient


class FakeMbClient(MbClient):
    """
    Modbus slave simulated in memory, registers of the given register map exist, other addresses are unknown
    """

    def __init__(self, regs, slave=1, answer_unknown=False, ignore_writes=False):
        """
        :param regs: Registers of the register map (input and holding)
        :param slave: Slave address the fake answers to
        :param answer_unknown: Answer also addresses not present in the register map (zeros)
        :param ignore_writes: Acknowledge writes without storing values
        """
        super().__init__()
        self.s = {'comport': 'FAKE'}
        self.comport = 'FAKE'
        self.slave = slave
        self.answer_unknown = answer_unknown
        self.ignore_writes = ignore_writes
        self.memory = {}
        self.sent = []
        for reg in regs:
            for addr in reg['Address']:
                self.memory[(reg['Type'] == 'HOLD', addr)] = 0

    def open(self, settings=None, connectionless=False):
        return True

    def close(self):
        pass

    def read(self, request):
        if request['Slave'] != self.slave:
            return None
        hold = request['Type'].upper() != 'INPUT'
        keys = [(hold, request['Address'] + i) for i in range(request['Count'])]
        if not self.answer_unknown and any(k not in self.memory for k in keys):
            return None
        return [self.memory.get(k, 0) for k in keys]

    def write_hold(self, request):
        self.sent.append(request)
        if request['Slave'] != self.slave:
            return None
        if not self.ignore_writes:
            for i, value in enumerate(request['Values']):
                self.memory[(True, request['Address'] + i)] = value
        return 0


class FakeLeBinCom:
    """
    LeBin device simulated in memory (packet format of LeBin/RegisterMap.py), registers of the map exist
    """
    START_BYTE = 0x90

    def __init__(self, regs, answer_unknown=False, ignore_writes=False, foreign_reply=False):
        """
        :param regs: Registers of the register map
        :param answer_unknown: Answer also IDs not present in the register map (zeros)
        :param foreign_reply: Answer unknown IDs by a packet with another ID not present in the register map
        :param ignore_writes: Acknowledge writes without storing values
        """
        self.ble = False
        self.comport, self.baud, self.parity, self.stop, self.timeout = 'FAKE', 115200, 'N', 1, 1
        self.answer_unknown = answer_unknown
        self.ignore_writes = ignore_writes
        self.foreign_reply = foreign_reply
        self.memory = {reg['Id']: bytes(1 << (reg['Id'] & 7)) for reg in regs}
        self.sent = []

    def close(self):
        pass

    def reopen(self):
        pass

    def request_response(self, msg, resp_len):
        msg = bytes(msg)
        self.sent.append(msg)
        header, idx = msg[:4], 4
        if msg[1] == 130:
            resp = bytearray(header)
            while idx + 4 <= len(msg):
                reg_id = int.from_bytes(msg[idx:idx + 4], 'little')
                idx += 4
                if reg_id not in self.memory and self.foreign_reply:
                    return bytes([self.START_BYTE, msg[1], 12, 0]) + (0x7EEEEE02).to_bytes(4, 'little') + bytes(4)
                if reg_id not in self.memory and not self.answer_unknown:
                    return bytes([self.START_BYTE, msg[1], 4, 0])
                resp += reg_id.to_bytes(4, 'little') + self.memory.get(reg_id, bytes(1 << (reg_id & 7)))
            resp[2:4] = len(resp).to_bytes(2, 'little')
            return bytes(resp)
        while idx + 4 <= len(msg):
            reg_id = int.from_bytes(msg[idx:idx + 4], 'little')
            length = 1 << (reg_id & 7)
            if not self.ignore_writes:
                self.memory[reg_id] = msg[idx + 4:idx + 4 + length]
            idx += 4 + length
        return msg
