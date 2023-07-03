import unittest
import os
from time import sleep

try:
    import lecore.TestFrame as TF
except ImportError:
    import src.lecore.TestFrame as TF

# import src.lecore.VisualModbus as VM

pth = os.path.dirname(os.path.abspath(__file__))


class TestSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance of looger class
        """
        com_file = pth + "/ComSettings.json"
        regs_file = pth + "/RtdEmul_Modbus.json"

        cl = TF.RtuClient(com_file, pth + '/VisualSettings.json')

        cls.cl = cl

    def setUp(self) -> None:
        """
        Insert just some delay between tests
        """
        sleep(0.1)

    def test001_frame_setup(self):
        """
        """
        pass


if __name__ == '__main__':
    unittest.main()

