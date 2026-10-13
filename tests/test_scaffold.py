import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout

try:
    import lecore
    import lecore.Devices.PhaseDet as PE
    import lecore.Devices.Rftb as RFTB
    from lecore.__main__ import main
except ImportError:
    import src.lecore as lecore
    import src.lecore.Devices.PhaseDet as PE
    import src.lecore.Devices.Rftb as RFTB
    from src.lecore.__main__ import main

PKG = 'scaffold_dev'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestScaffold(unittest.TestCase):
    """
    Device class generator and quick guide, no hardware needed
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, PKG)
        os.mkdir(self.dir)
        sys.path.insert(0, self.root)

    def tearDown(self):
        sys.path.remove(self.root)
        for m in [m for m in sys.modules if m.split('.')[0] == PKG]:
            del sys.modules[m]
        shutil.rmtree(self.root, ignore_errors=True)

    def _copy(self, src_dir, *files):
        for f in files:
            shutil.copy(os.path.join(src_dir, f), self.dir)

    def _import(self, name):
        importlib.invalidate_caches()
        with warnings.catch_warnings():
            warnings.simplefilter('error', UserWarning)
            return importlib.import_module(f"{PKG}.{name}")

    def test_guide(self):
        self.assertIn('new-device', lecore.guide())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(['guide']), 0)
        self.assertIn('ModbusDev', out.getvalue())

    def test_modbus_existing_map(self):
        self._copy(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json', 'PhaseDetRegs.py')
        result = lecore.new_device('MbDevice', directory=self.dir, slave=7, comport='COM9')
        self.assertEqual(result[os.path.join(self.dir, 'PhaseDetRegs.py')], 'used')
        self.assertEqual(result[os.path.join(self.dir, 'MbDevice.py')], 'created')
        self.assertFalse([f for f in os.listdir(self.dir) if f.endswith('Regs.py') and f != 'PhaseDetRegs.py'])
        pkg = self._import('MbDevice')
        self.assertIs(pkg.MbDevice.reg_names, importlib.import_module(f"{PKG}.PhaseDetRegs").PhaseDetRegs)
        dev = pkg.MbDevice()
        self.assertEqual(dev.slave, 7)
        self.assertEqual(dev.mb.s['comport'], 'COM9')
        dev.close()
        self.assertEqual(importlib.import_module(PKG).Reg.SYS_COMMAND, 'SYS_COMMAND')

    def test_lebin_existing_map(self):
        self._copy(RFTB.RftbLeBin.config_dir, 'rftb_registers.json', 'rftbRegs.py')
        self.assertEqual(main(['new-device', 'LbDevice', '--dir', self.dir, '--usb', '0x483', '22336', 'LB']), 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'VisualSettings.json')))
        pkg = self._import('LbDevice')
        self.assertEqual(pkg.LbDevice.usb, lecore.UsbId(0x483, 22336, 'LB'))
        self.assertEqual(pkg.LbDevice.reg_names.__name__, 'rftbRegs')
        dev = pkg.LbDevice()
        # Communication error is reported by None
        dev.open(comport='COM_NOT_EXISTING')
        self.assertIsNone(dev.read(pkg.LbDevice.reg_names.SYS_STATUS))
        dev.close()

    def test_dual(self):
        self._copy(RFTB.RftbLeBin.config_dir, 'rftb_Modbus.json', 'rftb_registers.json', 'rftbRegs.py')
        with self.assertWarns(UserWarning):
            result = lecore.new_device('Dual', directory=self.dir, usb=(1155, 22336, 'RFTB'))
        for f in ('Dual.py', 'DualLeBin.py', 'ComSettings.json', 'ComSettings_LeBin.json', 'VisualSettings.json'):
            self.assertEqual(result[os.path.join(self.dir, f)], 'created')
        self.assertEqual(result[os.path.join(self.dir, 'rftbRegs.py')], 'used')
        pkg = importlib.import_module(PKG)
        # Register names follow LeBin map, the Modbus map misses some of them
        self.assertIsNone(pkg.Dual.reg_names)
        self.assertIs(pkg.DualLeBin.reg_names, pkg.Reg)
        self.assertEqual(pkg.DualLeBin.com_settings, 'ComSettings_LeBin.json')
        with warnings.catch_warnings():
            warnings.simplefilter('error', UserWarning)
            pkg.Dual().close()
            pkg.DualLeBin().close()
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'src'))
        for extra in ([], ['--lebin']):
            out = subprocess.run([sys.executable, '.', '--list', *extra], cwd=self.dir, env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('COM_RESERVED', out.stdout.split())
        out = subprocess.run([sys.executable, '.', '--lebin', '--tui'], cwd=self.dir, env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 2)
        # Explicit protocol selects one map only
        result = lecore.new_device('Single', 'lebin', directory=self.dir)
        self.assertNotIn(os.path.join(self.dir, 'rftb_Modbus.json'), result)

    def test_main(self):
        self._copy(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json', 'PhaseDetRegs.py')
        lecore.new_device('MbDevice', directory=self.dir)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(ROOT, 'src'), self.root]))
        run = lambda *a: subprocess.run([sys.executable, '-m', PKG, *a], cwd=self.root, env=env,
                                        capture_output=True, text=True, timeout=60)
        out = run('--list')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('FIRM_REVISION', out.stdout.split())
        out = run('--read', 'NO_SUCH_REG')
        self.assertEqual(out.returncode, 2)
        self.assertIn('NO_SUCH_REG', out.stderr)
        out = run('--read', 'FIRM_REVISION', '--comport', 'COM_NOT_EXISTING')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('communication error', out.stdout)
        # Run from the package directory
        for target in ('.', '__main__.py'):
            out = subprocess.run([sys.executable, target, '--list'], cwd=self.dir, env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn('FIRM_REVISION', out.stdout.split())
        # Existing entry point is kept
        result = lecore.new_device('Other', directory=self.dir)
        self.assertEqual(result[os.path.join(self.dir, '__main__.py')], 'kept')

    def test_keep_configs(self):
        self._copy(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json', 'PhaseDetRegs.py', 'ComSettings.json')
        with open(os.path.join(self.dir, '__init__.py'), 'w') as f:
            f.write("# own init\n")
        result = lecore.new_device('MbDevice', directory=self.dir, comport='COM9')
        self.assertEqual(result[os.path.join(self.dir, 'ComSettings.json')], 'kept')
        self.assertEqual(result[os.path.join(self.dir, '__init__.py')], 'kept')
        with open(os.path.join(self.dir, 'ComSettings.json'), encoding='utf-8-sig') as f:
            self.assertEqual(json.load(f)['comport'], 'COM1')
        with self.assertRaises(FileExistsError):
            lecore.new_device('MbDevice', directory=self.dir)
        result = lecore.new_device('MbDevice', directory=self.dir, comport='COM9', force=True)
        self.assertEqual(result[os.path.join(self.dir, 'ComSettings.json')], 'overwritten')

    def test_without_regs(self):
        self._copy(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json')
        with self.assertWarns(UserWarning):
            lecore.new_device('MbDevice', directory=self.dir)
        self.assertIsNone(self._import('MbDevice').MbDevice.reg_names)
        lecore.new_device('MbDevice', directory=self.dir, gen_regs=True, force=True)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, 'PhaseDetRegs.py')))
        self.assertEqual(self._import('PhaseDetRegs').PhaseDetRegs.SYS_TIMESTAMP, 'SYS_TIMESTAMP')

    def test_template(self):
        with self.assertRaises(FileNotFoundError):
            lecore.new_device('LbDevice', 'lebin', directory=self.dir)
        lecore.new_device('LbDevice', 'lebin', directory=self.dir, template=True)
        pkg = self._import('LbDevice')
        dev = pkg.LbDevice()
        self.assertIn(pkg.LbDeviceRegs.SYS_COMMAND, dev.register_names())
        dev.close()

    def test_generate_regs(self):
        reg_map = os.path.join(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json')
        ns = {}
        exec(lecore.generate_regs(reg_map, 'PhaseDetRegs'), ns)
        expected = {k: v for k, v in vars(PE.PhaseDetRegs).items() if not k.startswith('_')}
        self.assertEqual({k: v for k, v in vars(ns['PhaseDetRegs']).items() if not k.startswith('_')}, expected)

    def test_errors(self):
        self._copy(PE.PhaseDet.config_dir, 'PhaseDet_Modbus.json', 'PhaseDetRegs.py')
        with self.assertRaises(ValueError):
            lecore.new_device('My-Device', directory=self.dir)
        with self.assertRaises(ValueError):
            lecore.new_device('X', protocol='can', directory=self.dir)
        with self.assertRaises(FileNotFoundError):
            lecore.new_device('X', protocol='lebin', directory=self.dir)
        with self.assertRaises(ValueError):
            lecore.new_device('X', directory=self.dir, reg_map=os.path.join(RFTB.RftbLeBin.config_dir,
                                                                             'rftb_registers.json'))
        with self.assertRaises(ValueError):
            lecore.new_device('X', directory=self.dir, usb=(1, 2, 'X'))
        self._copy(RFTB.RftbLeBin.config_dir, 'rftb_Modbus.json')
        with self.assertRaises(ValueError):
            lecore.new_device('X', directory=self.dir)
        lecore.new_device('X', directory=self.dir, reg_map='rftb_Modbus.json', gen_regs=True)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, 'rftbRegs.py')))
        bad = os.path.join(self.root, 'bad.json')
        with open(bad, 'w') as f:
            json.dump([{'Foo': 1}], f)
        with self.assertRaises(ValueError):
            lecore.generate_regs(bad, 'Regs')
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            main(['new-device'])


if __name__ == '__main__':
    unittest.main()
