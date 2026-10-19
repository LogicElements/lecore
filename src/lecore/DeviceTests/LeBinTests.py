"""
Communication tests of LeBin devices (LeBinDev subclasses)
"""
from typing import Any, Tuple

import pytest

from .Base import DeviceTestsBase, UNKNOWN_NAME


class _RecordingCom:
    """
    LeBin communication object recording requests instead of sending them
    """

    def __init__(self):
        self.ble = False
        self.sent = []

    def close(self):
        pass

    def reopen(self):
        pass

    def request_response(self, msg, resp_len):
        self.sent.append(bytes(msg))
        return b''


class LeBinDeviceTests(DeviceTestsBase):
    """
    Communication tests of a real LeBin device
    """
    #: Register ID not supported by the device (lowest 3 bits encode value length)
    unknown_id: int = 0x7FFFFF02

    _unknown_hint = 'unknown_id'

    def _inject_unknown(self, device) -> str:
        if any(r['Id'] == self.unknown_id for r in device.regs.regs):
            pytest.fail(f"unknown_id {self.unknown_id:#x} exists in the register map, set unknown_id")
        source = next((r for r in device.regs.regs if r['VarType'] == 'INT'), device.regs.regs[0])
        reg = dict(source, Name=UNKNOWN_NAME, Id=self.unknown_id, VarType='INT', Min=0, Max=0)
        device.regs.regs.append(reg)
        device._regs_by_name[UNKNOWN_NAME] = reg
        return UNKNOWN_NAME

    def _remove_unknown(self, device, name: str) -> None:
        reg = device._regs_by_name.pop(name)
        if reg in device.regs.regs:
            device.regs.regs.remove(reg)

    def _swap_client(self, device, client) -> Any:
        orig = device.com
        device.open(client=client)
        return orig

    def _stub_client(self, device):
        return _RecordingCom()

    def _value_args(self, reg: dict) -> Tuple[str, int]:
        # LeBin FLOAT is a 32-bit float, same as LeBinDev.write()
        return 'FLOAT32' if reg['VarType'] == 'FLOAT' else reg['VarType'], 8 * (1 << (reg['Id'] & 7))

    def _is_read_only(self, reg: dict) -> bool:
        return str(reg.get('Access', '')).startswith('RO')
