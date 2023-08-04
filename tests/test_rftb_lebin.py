import unittest
import os
from time import sleep
import random

try:
    import lecore.Devices.Rftb as RFTB
except ImportError:
    import src.lecore.Devices.Rftb as RFTB

# import src.lecore.Devices.Rftb as RFTB

pth = os.path.dirname(os.path.abspath(__file__))


class TestRftbLeBin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance
        """
        rftb = RFTB.RftbLeBin()
        ports = rftb.search_com()
        rftb.open(comport=ports[0])
        cls.rftb = rftb

    def test001_rtd_read_reg(self):
        """
        Test reading register
        """
        ver = self.rftb.read(RFTB.Reg.FIRM_REVISION)
        print(f"Version: {ver}")
        self.assertIsNotNone(ver, msg=f"Version")

    def test002_rtd_write_reg(self):
        """
        Test writing register
        """
        test = random.randint(0x10000, 0xffffffff)
        self.rftb.write(RFTB.Reg.SYS_TEST, test)
        read_back = self.rftb.read(RFTB.Reg.SYS_TEST)
        self.assertEqual(test, read_back, msg=f"Read back of write operation")

    def test003_rtd_visual(self):
        """
        Test running visual application
        :return:
        """
        ret = self.rftb.visual(10)
        self.assertTrue(ret, msg="Visual return value")

    def test004_rtd_update(self):
        """
        Test update firmware
        """
        ret = self.rftb.upgrade_firmware(pth + '/binary/rftb_app-20230703-5.bin', reboot_time=10)
        self.assertTrue(ret, msg=f"Update failed")


if __name__ == '__main__':
    unittest.main()

