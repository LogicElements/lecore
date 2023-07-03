from . import *


class ModbusUnitTest(object):

    def assert_val(self, name, val2, msg):
        val = self.regs.read_by_name(name)
        self.assertEqual(val, val2, msg)
