"""
Communication tests of Modbus devices (ModbusDev subclasses)
"""
from typing import Any, Tuple

from ..VisualModbus.MbClient import MbClient
from .Base import DeviceTestsBase, UNKNOWN_NAME


class _RecordingClient(MbClient):
    """
    Modbus client recording requests instead of sending them
    """

    def __init__(self):
        super().__init__()
        self.sent = []

    def open(self, settings=None, connectionless=False):
        return True

    def close(self):
        pass

    def read(self, request):
        self.sent.append(request)
        return None

    def write_hold(self, request):
        self.sent.append(request)
        return None


class ModbusDeviceTests(DeviceTestsBase):
    """
    Communication tests of a real Modbus device
    """
    #: Register address not supported by the device
    unknown_address: int = 65000
    #: Slave address with no device on the bus
    wrong_slave: int = 247

    _unknown_hint = 'unknown_address'

    def _inject_unknown(self, device) -> str:
        source = (device.regs.input or device.regs.hold)[0]
        reg = dict(source, Name=UNKNOWN_NAME, Address=[self.unknown_address], Format='INT', Min=0, Max=0)
        (device.regs.input if reg['Type'] != 'HOLD' else device.regs.hold).append(reg)
        device._regs_by_name[UNKNOWN_NAME] = reg
        return UNKNOWN_NAME

    def _remove_unknown(self, device, name: str) -> None:
        reg = device._regs_by_name.pop(name)
        for regs in (device.regs.input, device.regs.hold):
            if reg in regs:
                regs.remove(reg)

    def _swap_client(self, device, client) -> Any:
        orig = device.mb
        device.open(client=client)
        return orig

    def _stub_client(self, device):
        return _RecordingClient()

    def _value_args(self, reg: dict) -> Tuple[str, int]:
        return reg['Format'], 16 * len(reg['Address'])

    def _is_read_only(self, reg: dict) -> bool:
        return reg['Type'] != 'HOLD' or str(reg.get('Access', '')).startswith('RO')

    def test_05_wrong_slave(self, device):
        orig = device.regs.slave
        device.regs.slave = self.wrong_slave
        try:
            value = device.read(self._probe_name(device))
        finally:
            device.regs.slave = orig
        assert value is None, f"A device answered on wrong slave address {self.wrong_slave}, set wrong_slave"
        self._assert_reads(device, " after wrong slave address")
