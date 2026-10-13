"""
Validation helpers for device parameters, configuration files and register values.

All checks raise built-in exceptions (TypeError, ValueError, FileNotFoundError, KeyError) with a message
naming the offending parameter or file, so mistakes are reported where they are made.
"""
from __future__ import annotations

import difflib
import io
import json
import numbers
import os
from dataclasses import dataclass, fields
from typing import Any, Iterable, Union

PathLike = Union[str, "os.PathLike[str]"]

PARITIES = ('N', 'E', 'O')
STOP_BITS = (1, 1.5, 2)
MODBUS_FORMATS = ('INT', 'BIN', 'ENUM', 'FLOAT', 'FLOAT32', 'STRING')
MODBUS_TYPES = ('HOLD', 'INPUT')
FLOAT_FORMATS = ('FLOAT', 'FLOAT32')


def _is_int(value: Any) -> bool:
    return isinstance(value, numbers.Integral) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def check_slave(slave: Any) -> int:
    """
    Check Modbus slave address
    :param slave: Slave address, integer 1..247
    :return: Validated slave address
    """
    if not _is_int(slave):
        raise TypeError(f"slave must be int, got {type(slave).__name__} ({slave!r})")
    if not 1 <= slave <= 247:
        raise ValueError(f"slave must be in range 1..247, got {slave}")
    return int(slave)


def check_comport(comport: Any) -> str:
    """
    Check COM port name
    :param comport: Non-empty port name, e.g., 'COM5' or '/dev/ttyUSB0'
    :return: Validated port name
    """
    if not isinstance(comport, str):
        raise TypeError(f"comport must be str, got {type(comport).__name__} ({comport!r})")
    if not comport.strip():
        raise ValueError("comport must not be empty")
    return comport


def check_baud_rate(baud_rate: Any) -> int:
    """
    Check baud rate
    :param baud_rate: Positive integer
    :return: Validated baud rate
    """
    if not _is_int(baud_rate):
        raise TypeError(f"baud_rate must be int, got {type(baud_rate).__name__} ({baud_rate!r})")
    if baud_rate <= 0:
        raise ValueError(f"baud_rate must be positive, got {baud_rate}")
    return int(baud_rate)


def check_parity(parity: Any) -> str:
    """
    Check parity
    :param parity: One of 'N', 'E', 'O' (case-insensitive)
    :return: Validated parity in upper case
    """
    if not isinstance(parity, str):
        raise TypeError(f"parity must be str, got {type(parity).__name__} ({parity!r})")
    if parity.upper() not in PARITIES:
        raise ValueError(f"parity must be one of {PARITIES}, got {parity!r}")
    return parity.upper()


def check_stop_bits(stop_bits: Any) -> Union[int, float]:
    """
    Check number of stop bits
    :param stop_bits: One of 1, 1.5, 2
    :return: Validated number of stop bits
    """
    if not _is_number(stop_bits):
        raise TypeError(f"stop_bits must be a number, got {type(stop_bits).__name__} ({stop_bits!r})")
    if stop_bits not in STOP_BITS:
        raise ValueError(f"stop_bits must be one of {STOP_BITS}, got {stop_bits}")
    return stop_bits


def check_timeout(timeout: Any) -> float:
    """
    Check communication timeout
    :param timeout: Positive number of seconds
    :return: Validated timeout
    """
    if not _is_number(timeout):
        raise TypeError(f"timeout must be a number, got {type(timeout).__name__} ({timeout!r})")
    if timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    return timeout


def check_file(file: Any, what: str) -> None:
    """
    Check that file exists
    :param file: File path
    :param what: Description of the file used in error messages
    :return: None
    """
    if not isinstance(file, (str, os.PathLike)):
        raise TypeError(f"{what} must be str or PathLike, got {type(file).__name__} ({file!r})")
    if not os.path.isfile(file):
        raise FileNotFoundError(f"{what} not found: {file}")


def load_json(path: PathLike, what: str) -> Any:
    """
    Load JSON file with a descriptive error
    :param path: JSON file path
    :param what: Description of the file used in error messages, e.g., 'register map'
    :return: Parsed JSON content
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{what} file not found: {path}")
    try:
        with io.open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"{what} file {path} is not valid JSON: {e}") from None


@dataclass(frozen=True)
class ComSettings:
    """
    Validated serial communication settings (content of ComSettings.json)
    """
    comport: str
    baud_rate: int
    parity: str
    stop_bits: Union[int, float]
    timeout: float

    def __post_init__(self):
        check_comport(self.comport)
        check_baud_rate(self.baud_rate)
        # Normalize parity case
        object.__setattr__(self, 'parity', check_parity(self.parity))
        check_stop_bits(self.stop_bits)
        check_timeout(self.timeout)

    @classmethod
    def from_json(cls, path: PathLike) -> "ComSettings":
        """
        Load and validate communication settings from JSON file. Unknown keys are ignored.
        :param path: ComSettings JSON file
        :return: ComSettings object
        """
        data = load_json(path, "Communication settings")
        if not isinstance(data, dict):
            raise ValueError(f"Communication settings file {path} must contain a JSON object")
        names = [f.name for f in fields(cls)]
        missing = [n for n in names if n not in data]
        if missing:
            raise ValueError(f"Communication settings file {path} misses keys: {', '.join(missing)}")
        try:
            return cls(**{n: data[n] for n in names})
        except (TypeError, ValueError) as e:
            raise type(e)(f"Communication settings file {path}: {e}") from None


@dataclass(frozen=True)
class UsbId:
    """
    USB identification of a device used for COM port search
    """
    vid: int = 0
    pid: int = 0
    sn: str = ''

    def __post_init__(self):
        for name in ('vid', 'pid'):
            value = getattr(self, name)
            if not _is_int(value):
                raise TypeError(f"UsbId.{name} must be int, got {type(value).__name__} ({value!r})")
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"UsbId.{name} must be in range 0..0xFFFF, got {value}")
        if not isinstance(self.sn, str):
            raise TypeError(f"UsbId.sn must be str, got {type(self.sn).__name__} ({self.sn!r})")


def check_modbus_reg_map(regs: Any, path: PathLike) -> None:
    """
    Check structure of Modbus register map
    :param regs: Parsed register map JSON
    :param path: Register map file used in error messages
    :return: None
    """
    if not isinstance(regs, list) or not regs:
        raise ValueError(f"Register map {path} must be a non-empty JSON list of registers")
    names = set()
    for i, reg in enumerate(regs):
        where = f"Register map {path}, register #{i}"
        if not isinstance(reg, dict):
            raise ValueError(f"{where} must be a JSON object")
        missing = [k for k in ('Name', 'Type', 'Address', 'Format', 'Value') if k not in reg]
        if missing:
            raise ValueError(f"{where} ({reg.get('Name', '?')}) misses keys: {', '.join(missing)}")
        where = f"Register map {path}, register {reg['Name']!r}"
        if not isinstance(reg['Name'], str) or not reg['Name']:
            raise ValueError(f"{where}: Name must be a non-empty string")
        if reg['Name'] in names:
            raise ValueError(f"{where}: duplicate Name")
        names.add(reg['Name'])
        if reg['Type'] not in MODBUS_TYPES:
            raise ValueError(f"{where}: Type must be one of {MODBUS_TYPES}, got {reg['Type']!r}")
        if reg['Format'] not in MODBUS_FORMATS:
            raise ValueError(f"{where}: Format must be one of {MODBUS_FORMATS}, got {reg['Format']!r}")
        addr = reg['Address']
        if not isinstance(addr, list) or not addr or not all(_is_int(a) and 0 <= a <= 0xFFFF for a in addr):
            raise ValueError(f"{where}: Address must be a non-empty list of integers 0..65535, got {addr!r}")
        if reg['Format'] == 'FLOAT32' and len(addr) != 2:
            raise ValueError(f"{where}: FLOAT32 register must have 2 addresses, got {len(addr)}")


def check_lebin_reg_map(regs: Any, path: PathLike) -> None:
    """
    Check structure of LeBin register map
    :param regs: Parsed register map JSON
    :param path: Register map file used in error messages
    :return: None
    """
    if not isinstance(regs, list) or not regs:
        raise ValueError(f"Register map {path} must be a non-empty JSON list of registers")
    for i, reg in enumerate(regs):
        where = f"Register map {path}, register #{i}"
        if not isinstance(reg, dict):
            raise ValueError(f"{where} must be a JSON object")
        missing = [k for k in ('Name', 'Id', 'VarType', 'Access') if k not in reg]
        if missing:
            raise ValueError(f"{where} ({reg.get('Name', '?')}) misses keys: {', '.join(missing)}")
        if not _is_int(reg['Id']):
            raise ValueError(f"{where} ({reg['Name']}): Id must be an integer, got {reg['Id']!r}")


class RegisterNotFoundError(KeyError):
    """
    Register name not found in register map
    """
    def __str__(self):
        return str(self.args[0]) if self.args else ""


def check_reg_name(name: Any, names: Iterable[str], path: PathLike) -> str:
    """
    Check that register name exists in register map
    :param name: Register name
    :param names: All register names in the map
    :param path: Register map file used in error messages
    :return: Validated name
    """
    if not isinstance(name, str):
        raise TypeError(f"Register name must be str, got {type(name).__name__} ({name!r})")
    names = list(names)
    if name not in names:
        close = difflib.get_close_matches(name, names, n=3)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise RegisterNotFoundError(f"Register {name!r} not found in register map {path}.{hint}")
    return name


def check_reg_value(reg: dict, value: Any, fmt: str, bits: int, signed_ok: bool = True) -> None:
    """
    Check that value can be written into the register
    :param reg: Register definition from register map
    :param value: Value to write
    :param fmt: Register format, e.g., 'INT', 'FLOAT', 'STRING'
    :param bits: Raw bit width of the register
    :param signed_ok: Whether negative integers can be represented (two's complement)
    :return: None
    """
    name = reg['Name']
    if fmt == 'STRING':
        if not isinstance(value, str):
            raise TypeError(f"Register {name} expects str, got {type(value).__name__} ({value!r})")
        size = len(value.encode('utf-8'))
        if size > bits // 8:
            raise ValueError(f"Register {name} holds at most {bits // 8} bytes, got {size}")
        return

    # Numeric value, numeric strings are accepted for compatibility with GUI
    num = value
    if isinstance(value, str):
        try:
            num = float(value) if fmt in FLOAT_FORMATS else int(value, 0)
        except ValueError:
            raise ValueError(f"Register {name} expects a number, got {value!r}") from None
    elif not _is_number(value):
        raise TypeError(f"Register {name} expects a number, got {type(value).__name__} ({value!r})")

    if fmt in FLOAT_FORMATS:
        if fmt == 'FLOAT' and not -3276.8 <= num <= 3276.7:
            raise ValueError(f"Register {name} (FLOAT, 0.1 resolution) must be in range -3276.8..3276.7, got {num}")
    else:
        if num != int(num):
            raise ValueError(f"Register {name} expects an integer, got {num}")
        num = int(num)
        low = -(1 << (bits - 1)) if signed_ok else 0
        if not low <= num <= (1 << bits) - 1:
            raise ValueError(f"Register {name} value {num} does not fit into {bits} bits")
        if fmt == 'ENUM' and reg.get('EnumValue') and num not in reg['EnumValue']:
            raise ValueError(f"Register {name} must be one of {reg['EnumValue']}, got {num}")

    # Limits apply unless both are zero (no limit defined)
    low, high = reg.get('Min', 0), reg.get('Max', 0)
    if (low != 0 or high != 0) and _is_number(low) and _is_number(high) and not low <= num <= high:
        raise ValueError(f"Register {name} must be in range {low}..{high}, got {num}")
