import unittest
import os
from time import sleep

try:
    import lecore.LeBin as LeBin
except ImportError:
    import src.lecore.LeBin as LeBin


# import src.lecore.LeBin as LeBin

pth = os.path.dirname(os.path.abspath(__file__))


class TestSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance of looger class
        """
        com = LeBin.SerialCom()
        cls.com = com
        rm = LeBin.RegisterMap(com)
        regs_file = pth + "/SBD_registers.json"
        com_file = pth + "/ComSettings.json"
        com.open(com_file)
        print(regs_file)
        rm.load(regs_file)
        cls.rm = rm

    def test001_lebin_setup(self):
        """
        Set identification of device we are sending data from
        """
        sleep(1)

    def test002_lebin_upgrade(self):
        up = LeBin.UpgradeFirmware(self.com)
        up.load_file(pth + "/SBD_registers.json")

    def test003_lebin_visual(self):
        vis = LeBin.VisualLeBin(self.rm)

        vis.draw(height=700)

        vis.handle()


if __name__ == '__main__':
    unittest.main()

