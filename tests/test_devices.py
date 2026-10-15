import importlib.util
import json
import os
import shutil
import tempfile
import unittest
import unittest.mock
import warnings

try:
    import lecore.Devices as D
    import lecore.Devices.PhaseDet as PE
    import lecore.Devices.Rftb as RFTB
except ImportError:
    import src.lecore.Devices as D
    import src.lecore.Devices.PhaseDet as PE
    import src.lecore.Devices.Rftb as RFTB

PHASE_DET_DIR = PE.PhaseDet.config_dir
CONFIGS = ('ComSettings.json', 'UpgradeSettings.json', 'VisualSettings.json', 'PhaseDet_Modbus.json')


class TestDevices(unittest.TestCase):
    """
    Device declaration and parameter validation, no hardware needed
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for f in CONFIGS:
            shutil.copy(os.path.join(PHASE_DET_DIR, f), self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.dir, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return path

    def test001_external_module_device(self):
        """
        Device declared in a module outside the package finds configs next to the module
        """
        path = self._write('my_device.py', "from lecore.Devices import ModbusDev\n\n"
                                           "class MyDevice(ModbusDev):\n"
                                           "    reg_map = 'PhaseDet_Modbus.json'\n")
        spec = importlib.util.spec_from_file_location('my_device', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        dev = module.MyDevice()
        self.assertEqual(os.path.dirname(dev._reg_file), self.dir)
        self.assertIn('PH_COUNTER_1', dev.register_names())
        dev.close()

    def test002_config_dir_and_no_subclass(self):
        class MyDevice(D.ModbusDev):
            config_dir = self.dir
            reg_map = 'PhaseDet_Modbus.json'
        MyDevice().close()
        # Generic device without subclass
        D.ModbusDev(reg_map='PhaseDet_Modbus.json', config_dir=self.dir).close()

    def test003_declaration_errors(self):
        with self.assertRaises(FileNotFoundError):
            class Missing(D.ModbusDev):
                config_dir = self.dir
                reg_map = 'Missing.json'
        with self.assertRaises(NotADirectoryError):
            class BadDir(D.ModbusDev):
                config_dir = os.path.join(self.dir, 'none')
                reg_map = 'PhaseDet_Modbus.json'
        with self.assertRaises(TypeError):
            class BadNames(D.ModbusDev):
                config_dir = self.dir
                reg_map = 'PhaseDet_Modbus.json'
                reg_names = "PhaseDetRegs"
        with self.assertRaises(TypeError):
            class BadUsb(D.LeBinDev):
                usb = {'vid': 1}
        with self.assertRaises(TypeError):
            D.ModbusDev()

    def test004_config_file_errors(self):
        self._write('ComSettings.json', {'comport': 'COM1', 'baud_rate': 19200, 'parity': 'X', 'stop_bits': 1,
                                         'timeout': 1})
        with self.assertRaisesRegex(ValueError, 'parity'):
            D.ModbusDev(reg_map='PhaseDet_Modbus.json', config_dir=self.dir)
        self._write('ComSettings.json', {'comport': 'COM1'})
        with self.assertRaisesRegex(ValueError, 'misses keys'):
            D.ModbusDev(reg_map='PhaseDet_Modbus.json', config_dir=self.dir)
        shutil.copy(os.path.join(PHASE_DET_DIR, 'ComSettings.json'), self.dir)
        self._write('Bad_Modbus.json', '[{"Name": "A"}')
        with self.assertRaisesRegex(ValueError, 'not valid JSON'):
            D.ModbusDev(reg_map='Bad_Modbus.json', config_dir=self.dir)
        self._write('Bad_Modbus.json', [{'Name': 'A', 'Type': 'HOLD', 'Address': [1], 'Format': 'DOUBLE',
                                         'Value': 0}])
        with self.assertRaisesRegex(ValueError, 'Format'):
            D.ModbusDev(reg_map='Bad_Modbus.json', config_dir=self.dir)

    def test005_reg_names_check(self):
        class Regs:
            PH_COUNTER_1 = "PH_COUNTER_1"
            UNKNOWN = "UNKNOWN"

        class MyDevice(D.ModbusDev):
            config_dir = self.dir
            reg_map = 'PhaseDet_Modbus.json'
            reg_names = Regs
        with self.assertWarnsRegex(UserWarning, 'UNKNOWN'):
            MyDevice().close()

    def test006_legacy_subclass(self):
        directory = self.dir

        class Legacy(D.ModbusDev):
            def __init__(self):
                super().__init__()
                self._path = directory + "/"
                self._def_regs = "PhaseDet_Modbus.json"
                self._com(None)
                self._reg_map(None)
                self._upgrade(None)
                self._visual(None)
        with self.assertWarns(DeprecationWarning):
            dev = Legacy()
        self.assertIn('PH_COUNTER_1', dev.register_names())
        dev.close()

    def test007_register_access_errors(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            dev = PE.PhaseDet()
        with self.assertRaisesRegex(D.RegisterNotFoundError, 'PH_COUNTER_1'):
            dev.read('PH_COUNTR_1')
        with self.assertRaises(KeyError):
            dev.write('NONE', 1)
        with self.assertRaises(TypeError):
            dev.read(1)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            dev.write(PE.Reg.SYS_STATUS, 1)
        with self.assertRaisesRegex(ValueError, 'range'):
            dev.write(PE.Reg.SYS_COMMAND, 9999)
        with self.assertRaisesRegex(ValueError, 'integer'):
            dev.write(PE.Reg.SYS_COMMAND, 1.5)
        with self.assertRaises(TypeError):
            dev.write(PE.Reg.SYS_COMMAND, None)
        dev.close()

    def test008_open_errors(self):
        dev = PE.PhaseDet()
        for kwargs, exc in [({'slave': 0}, ValueError), ({'slave': '1'}, TypeError), ({'parity': 'X'}, ValueError),
                            ({'baud_rate': '9600'}, TypeError), ({'stop_bits': 3}, ValueError),
                            ({'timeout': 0}, ValueError), ({'comport': ''}, ValueError),
                            ({'client': object()}, TypeError)]:
            with self.assertRaises(exc, msg=str(kwargs)):
                dev.open(**kwargs)
        dev.close()

    def test009_lebin(self):
        dev = RFTB.RftbLeBin()
        self.assertEqual(dev.usb, D.UsbId(vid=1155, pid=22336, sn="RFTB"))
        with self.assertRaises(KeyError):
            dev.read('SYS_UPTIM')
        with self.assertRaisesRegex(ValueError, 'read-only'):
            dev.write(RFTB.Reg.SYS_UPTIME, 1)
        with self.assertRaises(ValueError):
            D.UsbId(vid=0x10000)
        dev.close()

    def test010_lebin_send_file_status(self):
        dev = RFTB.RftbLeBin()
        path = self._write('file.bin', '\0' * 16)
        for run_ret in (True, False):
            dev._upg = unittest.mock.Mock(**{'run.return_value': run_ret})
            self.assertIs(dev.send_file(path), run_ret)
            dev._upg.load_file.assert_called_once_with(path)
        dev.close()


if __name__ == '__main__':
    unittest.main()
