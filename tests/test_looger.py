import unittest
from time import sleep

from src.lecore.Looger import Looger


class TestLooger(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Create instance of looger class
        """
        cls.log = Looger()

    def setUp(self) -> None:
        """
        Insert just some delay between tests
        """
        sleep(1)

    def test001_set_device(self):
        """
        Set identification of device we are sending data from
        """
        self.log.set_device("12345678910", 0, None)

    def test002_send_data(self):
        """
        Send data dictionary only
        """
        data = {'data_1': 1.23, 'data_2': 2.54646178617}
        ret = self.log.send(data, None, 0)
        self.assertTrue(ret, msg=f"Send data")

    def test003_send_log(self):
        """
        Send message log only
        """
        log = "Message to device alone"
        ret = self.log.send(None, log, 0)
        self.assertTrue(ret, msg=f"Send log message only")

    def test004_send_data_and_log(self):
        """
        Send data dictionary and message log at the same time
        """
        data = {'data_1': 2.35, 'data_2': 1.54646178617}
        log = "Message to device along with data"
        ret = self.log.send(data, log, 0)
        self.assertTrue(ret, msg=f"Send data and message log")


if __name__ == '__main__':
    unittest.main()

