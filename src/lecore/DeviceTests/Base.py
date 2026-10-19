"""
Protocol independent part of the device communication test suite
"""
import math
import random
import string
from typing import Any, Callable, Dict, Optional, Tuple

import pytest

#: Name of the register injected into the loaded register map by the unknown register test
UNKNOWN_NAME = '__LECORE_UNKNOWN__'

_STRING_FORMATS = ('STRING',)
_FLOAT_FORMATS = ('FLOAT', 'FLOAT32')


def _limits(reg: dict) -> Optional[Tuple[float, float]]:
    """
    Min/Max limits of register, None when not defined (both zero or not numbers)
    """
    low, high = reg.get('Min', 0), reg.get('Max', 0)
    numbers = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (low, high))
    if not numbers or (low == 0 and high == 0):
        return None
    return low, high


def random_value(reg: dict, fmt: str, bits: int) -> Any:
    """
    Random value valid for writing into the register, different from its current value when possible
    :param reg: Register definition from register map
    :param fmt: Register format, e.g., 'INT', 'ENUM', 'FLOAT', 'FLOAT32', 'STRING'
    :param bits: Raw bit width of the register
    :return: Value passing check_reg_value()
    """
    current = str(reg.get('Value'))
    if fmt in _STRING_FORMATS:
        def gen():
            return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(1, min(bits // 8, 8))))
    elif fmt == 'ENUM' and reg.get('EnumValue'):
        choices = [c for c in reg['EnumValue'] if str(c) != current] or list(reg['EnumValue'])

        def gen():
            return random.choice(choices)
    elif fmt in _FLOAT_FORMATS:
        low, high = _limits(reg) or (-1000, 1000)
        # Halves are exact in binary, so the value survives the 0.1 resolution and float32 conversions
        low2, high2 = math.ceil(low * 2), math.floor(high * 2)
        if fmt == 'FLOAT':
            low2, high2 = max(low2, -6553), min(high2, 6553)

        def gen():
            return random.randint(low2, high2) / 2
    else:
        low, high = _limits(reg) or (0, (1 << bits) - 1)
        low, high = max(math.ceil(low), 0), min(math.floor(high), (1 << bits) - 1)

        def gen():
            return random.randint(low, high)
    value = gen()
    for _ in range(10):
        if str(value) != current:
            break
        value = gen()
    return value


def pick_rejected_writes(regs: Dict[str, dict], is_read_only: Callable[[dict], bool]) \
        -> Tuple[Optional[str], Optional[str]]:
    """
    Find registers whose write is rejected locally by validation
    :param regs: Registers of the map by name
    :param is_read_only: Function deciding whether register is read-only
    :return: (read-only register name, writable numeric register name with Min/Max limits), None when not found
    """
    read_only = next((n for n, r in regs.items() if n != UNKNOWN_NAME and is_read_only(r)), None)
    limited = next((n for n, r in regs.items() if n != UNKNOWN_NAME and not is_read_only(r)
                    and r.get('Format', r.get('VarType')) not in _STRING_FORMATS and _limits(r)), None)
    return read_only, limited


#: Fixture of a test environment (HIL platform) providing an opened device for classes with hil_signal
HIL_FIXTURE = 'hil_lecore_device'


def _device(request):
    """
    Device opened once per test class, by the test environment (hil_signal) or by create_device()
    """
    if getattr(request.cls, 'hil_signal', None):
        try:
            dev = request.getfixturevalue(HIL_FIXTURE)
        except LookupError:  # pytest.FixtureLookupError, the HIL platform is not installed
            dev = None
        if dev is not None:  # None: no HIL station selected, the device is opened here
            yield dev  # the environment owns the device and closes it
            return
    dev = request.cls.create_device()
    yield dev
    dev.close()


class DeviceTestsBase:
    """
    Communication tests of a real device, subclass it (class name starting with Test) and set class attributes
    """
    pytestmark = [pytest.mark.hardware]

    #: Device class (ModbusDev or LeBinDev subclass) instantiated by create_device()
    device_class = None
    #: Arguments of device open(), e.g., {'comport': 'COM5'}; empty uses ComSettings*.json
    open_kwargs: dict = {}
    #: Register safe to write by the read-back test, None skips the test
    test_register: Optional[str] = None
    #: Registers not read by the read-all test
    exclude: list = []
    #: Firmware binary for the upgrade test, None skips the test
    firmware = None
    #: Time the device takes to reboot after upgrade in seconds
    reboot_time: float = 5
    #: DUT signal name (hil/dut.yaml) of the device when run on a HIL station, None opens it by create_device()
    hil_signal: Optional[str] = None
    #: DUT power signal switched on by HIL for the whole test class, None leaves the power as it is
    hil_supply: Optional[str] = None
    #: Time in seconds HIL waits after switching hil_supply on before opening the device
    hil_boot_s: float = 0

    #: Name of the attribute configuring the unknown register, used in failure hints
    _unknown_hint = ''

    @classmethod
    def create_device(cls):
        """
        Create and open the device, override it for an exact device definition
        :return: Opened device
        """
        if cls.device_class is None:
            pytest.fail(f"{cls.__name__}: set device_class or override create_device()")
        dev = cls.device_class()
        if dev.open(**cls.open_kwargs) is False:
            dev.close()
            pytest.fail(f"{cls.__name__}: cannot open {cls.device_class.__name__} with {cls.open_kwargs or 'defaults'}"
                        f" ({_port_name(dev)})")
        return dev

    # Static fixture taking the test class from request: an instance method class fixture is deprecated
    # in pytest 9 and a classmethod fixture fails on Python 3.9 (classmethod has no __name__)
    device = staticmethod(pytest.fixture(scope="class", name="device")(_device))

    # Protocol hooks

    def _inject_unknown(self, device) -> str:
        raise NotImplementedError

    def _remove_unknown(self, device, name: str) -> None:
        raise NotImplementedError

    def _swap_client(self, device, client) -> Any:
        raise NotImplementedError

    def _stub_client(self, device):
        raise NotImplementedError

    def _value_args(self, reg: dict) -> Tuple[str, int]:
        raise NotImplementedError

    def _is_read_only(self, reg: dict) -> bool:
        raise NotImplementedError

    # Helpers

    def _probe_name(self, device) -> str:
        """
        Register read to check the device answers
        """
        names = device.register_names()
        return self.test_register if self.test_register in names else names[0]

    def _assert_reads(self, device, what: str = "") -> None:
        name = self._probe_name(device)
        assert device.read(name) is not None, f"Device does not answer reading {name}{what}"

    # Tests

    def test_01_read(self, device):
        self._assert_reads(device)

    def test_02_write_read_back(self, device):
        name = self.test_register
        if name is None:
            pytest.skip("test_register is not set")
        regs = device._reg_dict()
        if name not in regs:
            pytest.fail(f"test_register {name} not found in the register map")
        reg = regs[name]
        if self._is_read_only(reg):
            pytest.fail(f"test_register {name} is read-only")
        original = device.read(name)
        assert original is not None, f"Device does not answer reading {name}"
        fmt, bits = self._value_args(reg)
        value = random_value(reg, fmt, bits)
        restored = None
        try:
            assert device.write(name, value) is not None, f"Write of {value!r} into {name} failed"
            back = device.read(name)
            if isinstance(value, float):
                assert back is not None and math.isclose(back, value, abs_tol=1e-3), \
                    f"Read back {back!r} of {name} differs from written {value!r}"
            else:
                assert back == value, f"Read back {back!r} of {name} differs from written {value!r}"
        finally:
            # Restore without validation, the original value may be outside the limits of the map
            try:
                restored = device.regs.write_by_name(name, original)
            except Exception:
                restored = None
        if restored is None:
            pytest.fail(f"Original value {original!r} of {name} not restored")

    def test_03_read_all(self, device):
        names = [n for n in device.register_names() if n not in self.exclude]
        failed = [n for n in names if device.read(n) is None]
        assert not failed, f"Reading {len(failed)} of {len(names)} registers failed: {', '.join(failed)}"

    def test_04_unknown_register(self, device):
        name = self._inject_unknown(device)
        try:
            value = device.read(name)
        except Exception as e:
            pytest.fail(f"Reading register unknown to the device raised {e!r}, set {self._unknown_hint} "
                        f"to an address not supported by the device")
        finally:
            self._remove_unknown(device, name)
        assert value is None, (f"Device answered register unknown to it with {value!r}, set {self._unknown_hint} "
                               f"to an address not supported by the device")
        self._assert_reads(device, " after unknown register")

    def _assert_rejected(self, device, name: str, value: Any) -> None:
        """
        Write must be rejected by local validation (ValueError) with nothing sent to the device
        """
        stub = self._stub_client(device)
        orig = self._swap_client(device, stub)
        try:
            with pytest.raises(ValueError):
                device.write(name, value)
        finally:
            self._swap_client(device, orig)
        assert stub.sent == [], f"Rejected write of {name} was sent to the device"

    def test_06_read_only_rejected(self, device):
        read_only, _ = pick_rejected_writes(device._reg_dict(), self._is_read_only)
        if read_only is None:
            pytest.skip("Register map has no read-only register")
        self._assert_rejected(device, read_only, 0)

    def test_06_out_of_range_rejected(self, device):
        _, limited = pick_rejected_writes(device._reg_dict(), self._is_read_only)
        if limited is None:
            pytest.skip("Register map has no writable numeric register with Min/Max limits")
        self._assert_rejected(device, limited, device._reg_dict()[limited]['Max'] + 1)

    def test_07_reopen(self, device):
        device.close()
        assert device.open() is not False, "Device cannot be reopened"
        self._assert_reads(device, " after reopen")

    def test_08_upgrade(self, device):
        if self.firmware is None:
            pytest.skip("firmware is not set")
        assert device.upgrade_firmware(self.firmware, self.reboot_time), f"Firmware upgrade by {self.firmware} failed"
        self._assert_reads(device, " after firmware upgrade")


def _port_name(dev) -> str:
    """
    COM port of device for error messages
    """
    mb = getattr(dev, 'mb', None)
    if mb is not None and getattr(mb, 's', None):
        return f"port {mb.s.get('comport')}"
    com = getattr(dev, 'com', None)
    return f"port {getattr(com, 'comport', '?')}"
