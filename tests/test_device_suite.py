"""
Device communication test suite (lecore.DeviceTests) run against in-memory fake devices, no hardware needed
"""
import os
import subprocess
import sys

import pytest

try:
    import lecore.Devices.PhaseDet as PE
    import lecore.Devices.Rftb as RFTB
    from lecore.Devices.Validation import check_reg_value
    from lecore.DeviceTests import ModbusDeviceTests, LeBinDeviceTests
    from lecore.DeviceTests.Base import random_value, pick_rejected_writes, _device, HIL_FIXTURE
except ImportError:
    import src.lecore.Devices.PhaseDet as PE
    import src.lecore.Devices.Rftb as RFTB
    from src.lecore.Devices.Validation import check_reg_value
    from src.lecore.DeviceTests import ModbusDeviceTests, LeBinDeviceTests
    from src.lecore.DeviceTests.Base import random_value, pick_rejected_writes, _device, HIL_FIXTURE

from .fake_devices import FakeMbClient, FakeLeBinCom

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')


def _fake_modbus(**kwargs):
    dev = RFTB.Rftb()
    dev.regs.delay = 0
    dev.open(client=FakeMbClient(dev.regs.input + dev.regs.hold, dev.slave, **kwargs))
    return dev


class TestFakeModbus(ModbusDeviceTests):
    """
    Whole suite against an in-memory Modbus slave with the Rftb register map
    """
    test_register = 'SYS_TEST'

    @classmethod
    def create_device(cls):
        return _fake_modbus()


def test_marker():
    assert 'hardware' in [m.name for m in TestFakeModbus.pytestmark]


def test_random_value_valid():
    for dev_cls in (RFTB.Rftb, PE.PhaseDet):
        dev = dev_cls()
        for reg in dev.regs.input + dev.regs.hold:
            fmt, bits = reg['Format'], 16 * len(reg['Address'])
            for _ in range(200):
                check_reg_value(reg, random_value(reg, fmt, bits), fmt, bits)
        dev.close()


def test_random_value_enum():
    reg = {'Name': 'E', 'Format': 'ENUM', 'EnumValue': [1, 5, 9], 'Min': 0, 'Max': 0, 'Value': 1}
    assert {random_value(reg, 'ENUM', 16) for _ in range(100)} <= {5, 9}


def test_random_value_float_limits():
    reg = {'Name': 'F', 'Min': -54, 'Max': 6, 'Value': 0}
    values = [random_value(reg, 'FLOAT', 16) for _ in range(200)]
    assert all(-54 <= v <= 6 for v in values)


def test_unknown_answered_fails():
    dev = _fake_modbus(answer_unknown=True)
    with pytest.raises(AssertionError, match='unknown_address'):
        TestFakeModbus().test_04_unknown_register(dev)
    # Injected register is removed
    assert '__LECORE_UNKNOWN__' not in dev.register_names()


def test_test_register_read_only_fails():
    class ReadOnly(TestFakeModbus):
        test_register = 'FIRM_REVISION'
    with pytest.raises(pytest.fail.Exception, match='read-only'):
        ReadOnly().test_02_write_read_back(_fake_modbus())


def test_test_register_missing_fails():
    class Missing(TestFakeModbus):
        test_register = 'NOT_IN_MAP'
    with pytest.raises(pytest.fail.Exception, match='NOT_IN_MAP'):
        Missing().test_02_write_read_back(_fake_modbus())


def test_test_register_none_skips():
    class NoRegister(TestFakeModbus):
        test_register = None
    with pytest.raises(pytest.skip.Exception, match='test_register'):
        NoRegister().test_02_write_read_back(_fake_modbus())


def test_read_back_mismatch_restores():
    dev = _fake_modbus(ignore_writes=True)
    with pytest.raises(AssertionError):
        TestFakeModbus().test_02_write_read_back(dev)
    # The last write restores the original value (zeros of the fake)
    assert dev.mb.sent[-1]['Values'] == [0, 0]


def test_read_all_reports_failures():
    dev = _fake_modbus()
    # Remove two addresses from the fake, both registers are reported at once
    del dev.mb.memory[(False, 0)], dev.mb.memory[(True, 3)]
    with pytest.raises(AssertionError, match='SYS_UPTIME.*SYS_LOG_LEVEL|SYS_LOG_LEVEL.*SYS_UPTIME'):
        TestFakeModbus().test_03_read_all(dev)


def test_wrong_slave_restored():
    dev = _fake_modbus()
    TestFakeModbus().test_05_wrong_slave(dev)
    assert dev.regs.slave == dev.slave


def test_rejected_writes_nothing_sent():
    dev = _fake_modbus()
    TestFakeModbus().test_06_read_only_rejected(dev)
    TestFakeModbus().test_06_out_of_range_rejected(dev)
    assert dev.mb.sent == []
    assert isinstance(dev.mb, FakeMbClient)


def test_pick_rejected_writes_none():
    regs = {'A': {'Name': 'A', 'Type': 'HOLD', 'Access': 'RW', 'Format': 'INT', 'Address': [0], 'Min': 0, 'Max': 0}}
    assert pick_rejected_writes(regs, lambda r: r['Access'].startswith('RO')) == (None, None)


def test_rejected_writes_skip_without_registers():
    dev = _fake_modbus()
    for reg in dev.regs.input + dev.regs.hold:
        reg['Min'] = reg['Max'] = 0
    dev.regs.input.clear()
    dev._regs_by_name = {r['Name']: r for r in dev.regs.hold if not str(r['Access']).startswith('RO')}
    with pytest.raises(pytest.skip.Exception, match='read-only'):
        TestFakeModbus().test_06_read_only_rejected(dev)
    with pytest.raises(pytest.skip.Exception, match='Min/Max'):
        TestFakeModbus().test_06_out_of_range_rejected(dev)


def test_rejected_writes_only_read_only_present():
    dev = _fake_modbus()
    for reg in dev.regs.input + dev.regs.hold:
        reg['Min'] = reg['Max'] = 0
    # Read-only part runs, the missing limited register is reported by skip
    TestFakeModbus().test_06_read_only_rejected(dev)
    with pytest.raises(pytest.skip.Exception, match='Min/Max'):
        TestFakeModbus().test_06_out_of_range_rejected(dev)


def test_restore_bypasses_validation():
    dev = _fake_modbus()
    # Original value 0 of the fake is outside the limits, it is restored anyway
    dev._regs_by_name['SYS_TEST'].update(Min=1, Max=100)
    TestFakeModbus().test_02_write_read_back(dev)
    assert dev.mb.sent[-1]['Values'] == [0, 0]


def test_restore_failure_fails():
    dev = _fake_modbus()
    write_hold, calls = dev.mb.write_hold, []

    def failing_restore(request):
        calls.append(request)
        return write_hold(request) if len(calls) == 1 else None
    dev.mb.write_hold = failing_restore
    with pytest.raises(pytest.fail.Exception, match='not restored'):
        TestFakeModbus().test_02_write_read_back(dev)


def test_plugin_does_not_load_modbus_stack():
    code = "import sys, lecore.DeviceTests.Plugin; print('pymodbus' in sys.modules, 'serial' in sys.modules)"
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60,
                         env=dict(os.environ, PYTHONPATH=SRC))
    assert out.stdout.split() == ['False', 'False'], out.stderr


def test_upgrade_skipped_without_firmware():
    with pytest.raises(pytest.skip.Exception, match='firmware'):
        TestFakeModbus().test_08_upgrade(_fake_modbus())


def test_open_failure_fails():
    class NotOpening(ModbusDeviceTests):
        device_class = RFTB.Rftb
        open_kwargs = {'comport': 'COM_NOT_EXISTING_XYZ', 'timeout': 0.1}
    with pytest.raises(pytest.fail.Exception, match='COM_NOT_EXISTING_XYZ'):
        NotOpening.create_device()



class _Request:
    """
    Minimal pytest request for the device fixture, fixtures by name or missing (LookupError)
    """
    def __init__(self, cls, fixtures):
        self.cls, self.fixtures, self.requested = cls, fixtures, []

    def getfixturevalue(self, name):
        self.requested.append(name)
        if name not in self.fixtures:
            raise LookupError(name)
        return self.fixtures[name]


class _Dev:
    closed = False

    def close(self):
        self.closed = True


def _suite(hil_signal):
    class Suite(ModbusDeviceTests):
        created = []

        @classmethod
        def create_device(cls):
            dev = _Dev()
            cls.created.append(dev)
            return dev
    Suite.hil_signal = hil_signal
    return Suite


def _run_device_fixture(request):
    gen = _device(request)
    dev = next(gen)
    with pytest.raises(StopIteration):
        next(gen)
    return dev


def test_device_from_hil_is_not_closed():
    hil_dev = _Dev()
    suite = _suite('modbus')
    assert _run_device_fixture(_Request(suite, {HIL_FIXTURE: hil_dev})) is hil_dev
    assert not hil_dev.closed and not suite.created


def test_device_without_hil_station_or_plugin_by_create_device():
    for fixtures in ({HIL_FIXTURE: None}, {}):
        suite = _suite('modbus')
        dev = _run_device_fixture(_Request(suite, fixtures))
        assert suite.created == [dev] and dev.closed


def test_device_without_hil_signal_does_not_ask_hil():
    suite = _suite(None)
    request = _Request(suite, {HIL_FIXTURE: _Dev()})
    assert _run_device_fixture(request) is suite.created[0]
    assert request.requested == []


def _fake_lebin(**kwargs):
    dev = RFTB.RftbLeBin()
    dev.open(client=FakeLeBinCom(dev.regs.regs, **kwargs))
    return dev


class TestFakeLeBin(LeBinDeviceTests):
    """
    Whole suite against an in-memory LeBin device with the Rftb register map
    """
    test_register = RFTB.Reg.SYS_TEST

    @classmethod
    def create_device(cls):
        return _fake_lebin()


def test_lebin_unknown_answered_fails():
    dev = _fake_lebin(answer_unknown=True)
    with pytest.raises(AssertionError, match='unknown_id'):
        TestFakeLeBin().test_04_unknown_register(dev)
    assert '__LECORE_UNKNOWN__' not in dev.register_names()


def test_lebin_unknown_id_in_map_fails():
    class Colliding(TestFakeLeBin):
        unknown_id = 98642  # SYS_TEST
    with pytest.raises(pytest.fail.Exception, match='unknown_id'):
        Colliding().test_04_unknown_register(_fake_lebin())


def test_lebin_read_back_mismatch_restores():
    dev = _fake_lebin(ignore_writes=True)
    with pytest.raises(AssertionError):
        TestFakeLeBin().test_02_write_read_back(dev)
    # The last write restores the original value (zeros of the fake)
    assert dev.com.sent[-1][-4:] == bytes(4)


def test_lebin_foreign_reply_fails():
    dev = _fake_lebin(foreign_reply=True)
    with pytest.raises(pytest.fail.Exception, match='unknown_id'):
        TestFakeLeBin().test_04_unknown_register(dev)
    assert '__LECORE_UNKNOWN__' not in dev.register_names()


def test_lebin_rejected_writes_nothing_sent():
    dev = _fake_lebin()
    TestFakeLeBin().test_06_read_only_rejected(dev)
    TestFakeLeBin().test_06_out_of_range_rejected(dev)
    assert dev.com.sent == []
    assert isinstance(dev.com, FakeLeBinCom)


def test_lebin_random_value_valid():
    dev = RFTB.RftbLeBin()
    for reg in dev.regs.regs:
        fmt = 'FLOAT32' if reg['VarType'] == 'FLOAT' else reg['VarType']
        bits = 8 * (1 << (reg['Id'] & 7))
        for _ in range(200):
            check_reg_value(reg, random_value(reg, fmt, bits), fmt, bits, signed_ok=False)
    dev.close()
