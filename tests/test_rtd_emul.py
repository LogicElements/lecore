import unittest
import os
from time import sleep
import random

try:
    import lecore.Devices.RtdEmul as RE
except ImportError:
    import src.lecore.Devices.RtdEmul as RE
import random

# import src.lecore.Devices.RtdEmul as RE

pth = os.path.dirname(os.path.abspath(__file__))


class TestSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance
        """
        rtd = RE.RtdEmul()
        rtd.open(comport='COM8', slave=33)
        cls.rtd = rtd

    def setUp(self) -> None:
        """
        Insert just some delay between tests
        """
        sleep(0.1)

    def test001_rtd_read_reg(self):
        """
        Test reading register
        """
        ver = self.rtd.read(RE.Reg.FIRM_REVISION)
        print(f"Version: {ver}")
        self.assertIsNotNone(ver, msg=f"Version")

    def test002_rtd_write_reg(self):
        """
        Test writing register
        """
        test = random.randint(0x10000, 0xffffffff)
        self.rtd.write(RE.Reg.SYS_TEST, test)
        read_back = self.rtd.read(RE.Reg.SYS_TEST)
        self.assertEqual(test, read_back, msg=f"Read back of write operation")

    def test003_rtd_visual(self):
        """
        Test running visual application
        :return:
        """
        self.rtd.visual(5)

    def test004_rtd_update(self):
        """
        Test update firmware
        """
        ret = self.rtd.upgrade_firmware(pth + '/binary/RtdEmulator-app-20201113-5.bin')
        self.assertTrue(ret, msg=f"Update failed")


if __name__ == '__main__':
    unittest.main()

