import datetime
import random
import struct
import tempfile
import unittest
from pathlib import Path

try:
    from lecore import FwBuild
except ImportError:
    from src.lecore import FwBuild

DATE = datetime.date(2026, 10, 24)


def blank_binary(offset, size=2001, seed=1):
    """Random content with the free space for the information block"""
    data = bytearray(random.Random(seed).randbytes(size))
    data[offset - 32:offset] = bytes(32)
    data[offset:offset + 32] = b"\xff" * 32
    return bytes(data)


class TestCrc32(unittest.TestCase):
    def test_known_values(self):
        # Reference values of the STM32 hardware CRC unit (init 0xFFFFFFFF, polynom 0x04C11DB7)
        self.assertEqual(FwBuild.crc32(struct.pack("<I", 0x12345678)), 0xDF8A8A2B)
        self.assertEqual(FwBuild.crc32(b""), 0xFFFFFFFF)

    def test_matches_legacy_implementation(self):
        from lecore.VisualModbus import Crc32
        data = random.Random(2).randbytes(400)
        self.assertEqual(FwBuild.crc32(data), Crc32.calc_from_byte(data))

    def test_length(self):
        with self.assertRaises(ValueError):
            FwBuild.crc32(b"123")


class TestBuild(unittest.TestCase):
    def test_target5_layout(self):
        data = blank_binary(1024)
        out, crc = FwBuild.build(data, 5, "12", date=DATE)
        info = struct.unpack("<IIII", out[1024:1040])
        # Version is stored as a decimal number, the build date as decimal yyyymmdd, size is padded to 4 B
        self.assertEqual(info, (12, 20261024, crc, 2004))
        self.assertEqual(out[:1024], data[:1024])
        self.assertEqual(out[1040:2001], data[1040:])
        self.assertEqual(crc, FwBuild.crc32(data + bytes(3)))

    def test_target6_crc_ignores_block_tail(self):
        # Free space is 16 B only, the rest of the 32 B block is taken as 0xFF in the CRC
        data = bytearray(blank_binary(512))
        data[528:544] = bytes(16)
        out, crc = FwBuild.build(bytes(data), 6, "12", date=DATE)
        self.assertEqual(struct.unpack("<IIII", out[512:528]), (12, 20261024, crc, 2004))
        self.assertEqual(out[528:544], bytes(16))
        data[528:544] = bytes([0xFF]) * 16
        self.assertEqual(crc, FwBuild.crc32(bytes(data) + bytes(3)))

    def test_target4_device_id(self):
        out, crc = FwBuild.build(bytes(192) + b"\x00" * 32 + b"\x55" * 100, 4, "102", "ABCD", date=DATE)
        self.assertEqual(struct.unpack("<I4sIII", out[192:212]), (0x102, b"ABCD", 324, crc, 0x20261024))

    def test_target4_invalid_device_id(self):
        data = bytes(192) + b"\x00" * 32 + b"\x55" * 100
        for dev_id in ("ABCDE", "ÁB"):
            with self.assertRaises(ValueError):
                FwBuild.build(data, 4, "102", dev_id, date=DATE)

    def test_target1_prepends_block(self):
        data = blank_binary(512)
        out, crc = FwBuild.build(data, 1, "2", date=DATE)
        self.assertEqual(out[16:], data + bytes(3))
        self.assertEqual(struct.unpack("<IIII", out[:16]), (2, 0x20261024, crc, 2004))

    def test_occupied_info_block(self):
        data = bytearray(blank_binary(1024))
        data[1024] = 0
        with self.assertRaises(ValueError):
            FwBuild.build(bytes(data), 5, "2")

    def test_unknown_target(self):
        with self.assertRaises(ValueError):
            FwBuild.build(bytes(2048), 99, "2")

    def test_build_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "fw.bin"
            src.write_bytes(blank_binary(1024))
            out, crc = FwBuild.build_file(5, src, "2", date=DATE)
            self.assertEqual(out, Path(tmp) / "fw-20261024-2.bin")
            self.assertEqual(struct.unpack("<I", out.read_bytes()[1032:1036])[0], crc)
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            out, _ = FwBuild.build_file(5, src, "2A", "dev", out_dir, DATE)
            self.assertEqual(out, out_dir / "fw-dev-20261024-2A.bin")


if __name__ == "__main__":
    unittest.main()
