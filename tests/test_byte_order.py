import struct
import unittest

try:
    from lecore.LeBin.RegisterMap import RegisterMap
    from lecore.LeBin.UpgradeFirmware import UpgradeFirmware
    from lecore.VisualModbus.RegMap import _get_values_for_mb, _set_value_from_mb
except ImportError:
    from src.lecore.LeBin.RegisterMap import RegisterMap
    from src.lecore.LeBin.UpgradeFirmware import UpgradeFirmware
    from src.lecore.VisualModbus.RegMap import _get_values_for_mb, _set_value_from_mb

# Register IDs, the lowest 3 bits encode log2 of the value length
ID_INT = 0x01020301  # 2 bytes
ID_FLOAT = 0x0A0B0C02  # 4 bytes


class FakeCom:
    """
    Communication stub recording sent requests and returning a prepared response
    """

    def __init__(self, response=b''):
        self.ble = False
        self.response = response
        self.requests = []

    def request_response(self, request, resp_len):
        self.requests.append(bytes(request))
        return self.response


class TestByteOrder(unittest.TestCase):
    """
    Packet byte layout must be platform independent (4-byte little-endian IDs), no hardware needed
    """

    def setUp(self):
        self.com = FakeCom()
        self.map = RegisterMap(self.com)
        self.map.regs = [
            {'Name': 'Int', 'Id': ID_INT, 'VarType': 'INT', 'Access': 'RW', 'Value': '0'},
            {'Name': 'Float', 'Id': ID_FLOAT, 'VarType': 'FLOAT', 'Access': 'RW', 'Value': '0'},
        ]

    def test_lebin_write_packet(self):
        self.map.write_register(0, [0x1234, 1.5])
        expected = (bytes([0x90, 129, 18, 0])
                    + bytes([0x01, 0x03, 0x02, 0x01, 0x34, 0x12])
                    + bytes([0x02, 0x0C, 0x0B, 0x0A]) + bytes.fromhex('0000c03f'))
        self.assertEqual(self.com.requests[0], expected)

    def test_lebin_read_packet(self):
        self.map.read_all()
        expected = bytes([0x90, 130, 12, 0, 0x01, 0x03, 0x02, 0x01, 0x02, 0x0C, 0x0B, 0x0A])
        self.assertEqual(self.com.requests[0], expected)

    def test_lebin_parse_response(self):
        self.com.response = (bytes([0x90, 130, 18, 0])
                             + bytes([0x01, 0x03, 0x02, 0x01, 0x34, 0x12])
                             + bytes([0x02, 0x0C, 0x0B, 0x0A]) + bytes.fromhex('0000c03f'))
        self.assertTrue(self.map.read_all())
        self.assertEqual(self.map.regs[0]['Value'], str(0x1234))
        self.assertEqual(float(self.map.regs[1]['Value']), 1.5)

    def test_upgrade_packets(self):
        upg = UpgradeFirmware(self.com)
        upg.data = bytearray(0x200)
        upg.length = len(upg.data)
        upg.offset = 0x0102
        upg.send_request()
        # Length 0xFE data bytes + 8 header bytes, 4-byte offset
        self.assertEqual(self.com.requests[0][:8], bytes([0x90, 255, 0x06, 0x01, 0x02, 0x01, 0, 0]))
        self.assertEqual(len(self.com.requests[0]), 0x106)
        response = bytes([0x90, 127, 12, 0]) + struct.pack('<LL', 0x180, 0)
        self.assertTrue(upg.parse_response(response))
        self.assertEqual(upg.offset, 0x180)
        self.assertFalse(upg.parse_response(bytes([0x90, 127, 12, 0]) + struct.pack('<LL', 8, 1)))

    def test_modbus_float32(self):
        reg = {'Format': 'FLOAT32', 'Value': '1.5'}
        self.assertEqual(_get_values_for_mb(reg), [0x0000, 0x3FC0])
        _set_value_from_mb(reg, [0x0000, 0x4020])
        self.assertEqual(float(reg['Value']), 2.5)


if __name__ == '__main__':
    unittest.main()
