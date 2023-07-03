import unittest
import os
from time import sleep

try:
    import lecore.Fg320 as FG
except ImportError:
    import src.lecore.Fg320 as FG

# import src.lecore.Fg320 as FG
from lecore.LeBin import *

pth = os.path.dirname(os.path.abspath(__file__))


class TestSimple(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance of looger class
        """
        com_file = pth + "/ComSettings.json"
        com = SerialCom()
        com.open(com_file)
        fg = FG.Fg320(com)

        fg2 = FG.Fg320('COM6')

        cls.fg = fg2

    def setUp(self) -> None:
        """
        Insert just some delay between tests
        """
        sleep(0.1)

    def test001_single_iteration(self):
        """
        """
        delay = 1
        # fg.write_sn(17050001)
        # fg.write_calibration(1.0, 1.0, 1.0, 1.0)
        # fg.update_firmware("FG320_rev_c-20201019-110.bin")
        # sleep(1)

        self.fg.identify()
        print(f"Calibration: {self.fg.read_calibration()}")
        self.fg.ramp_time(delay)
        self.fg.limit_number_period(0)

        # Initial set of FG320
        self.fg.normal(function="SQ", frequency=10, amplitude=1, dc=0, angle=90,
                       kp_length=50, kp_high=11, kp_low=1, order=1)
        self.fg.write()
        sleep(delay)
        self.fg.current_dc(dc=5)
        self.fg.write()
        sleep(delay)
        self.fg.speed(frequency=10)
        self.fg.write()
        sleep(delay)


if __name__ == '__main__':
    unittest.main()

