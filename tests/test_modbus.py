import unittest
import os
from time import sleep

try:
    import lecore.VisualModbus as VM
except ImportError:
    import src.lecore.VisualModbus as VM

# import src.lecore.VisualModbus as VM

pth = os.path.dirname(os.path.abspath(__file__))


class TestSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance of looger class
        """
        mb = VM.MbClient()
        com_file = pth + "/ComSettings.json"
        mb.open(com_file, connectionless=True)
        regs = VM.RegMap(mb, slave=1)
        regs_file = pth + "/RtdEmul_Modbus.json"
        regs.load(regs_file)

        vm = VM.VisualMbApp(visual=pth + '/VisualSettings.json', upgrade=pth + '/UpgradeSettings.json', com=com_file,
                            reg_map=regs_file)

        cls.vm = vm
        cls.mb = mb
        cls.reg = regs

    def setUp(self) -> None:
        """
        Insert just some delay between tests
        """
        sleep(0.1)

    def test001_modbus_setup(self):
        """
        """
        pass

    def test003_modbus_visual(self):

        self.vm.handle(connectionless=False)


if __name__ == '__main__':
    unittest.main()

