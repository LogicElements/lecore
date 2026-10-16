"""
Jump-start helpers for new LE devices: quick guide, device class generator (in the directory with the register map)
and register name class generator.

Command line: ``python -m lecore guide``, ``python -m lecore new-device MyDevice``, ``python -m lecore regs map.json``.
The module avoids importing the Modbus/LeBin stack, so it works even without optional dependencies.
"""
from __future__ import annotations

import io
import json
import keyword
import os
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

PathLike = Union[str, "os.PathLike[str]"]

PROTOCOLS = ('modbus', 'lebin')
GUIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'QUICKSTART.md')

# Templates of configuration files, values taken from existing LE devices
_COM_SETTINGS = {
    "comport": "COM1",
    "baud_rate": 19200,
    "stop_bits": 1,
    "parity": "E",
    "timeout": 1,
    "inter_char_timeout": 30.0,
    "minimal_inter_char_timeout": 0.05,
    "silent_interval": 1.0,
}

_UPGRADE_SETTINGS = {
    "align": 4,
    "page_bytes": 64,
    "type_binary": 2050,
    "mode_operation": 1,
    "address": 1000,
    "test_mode": 1,
    "block_delay": 0.0,
    "init_delay": 0.5,
}

_VISUAL_SETTINGS = {
    "width": 650,
    "height": 614,
    "slave_address": 1,
    "reg_map": "",
    "attempts": 2,
    "retry_delay": 0.5,
    "readout_period": 1,
}


def _mb_reg(reg_type: str, name: str, address: List[int], access: str, label: str, description: str,
            fmt: str = "INT", low: int = 0, high: int = 0) -> dict:
    return {"Type": reg_type, "Name": name, "Address": address, "Format": fmt, "Value": 0, "Access": access,
            "Min": low, "Max": high, "Unit": "", "Label": label, "Description": description}


_MODBUS_REG_MAP = [
    _mb_reg("INPUT", "SYS_STATUS", [0, 1], "RO", "Status register", "Binary map of status flags", fmt="BIN"),
    _mb_reg("INPUT", "FACT_SERIAL_NUMBER", [2, 3], "RO", "Serial number", "Serial number in format XXYYZZZZ"),
    _mb_reg("INPUT", "FIRM_REVISION", [4, 5], "RO", "Firmware version",
            "Firmware revision as an incremental number, required by upgrade_firmware()"),
    _mb_reg("HOLD", "SYS_COMMAND", [0], "RW", "Command", "Value 9901 - Reset\r\nValue 8801 - Factory reset",
            high=9901),
]


def _lb_reg(category: str, name: str, reg_id: int, var_type: str, access: str, label: str, description: str,
            low: Optional[int] = None, high: Optional[int] = None) -> dict:
    reg = {"Category": category, "Name": name, "Label": label, "Id": reg_id, "VarType": var_type, "Access": access,
           "Description": description, "Value": "0", "NewValue": "0", "Reset": "0"}
    if low is not None:
        reg.update(Min=low, Max=high)
    reg.update(Units="", IsVisible=True, ConfigUser=False)
    return reg


# Lower 3 bits of Id encode the register size (2 = 4 bytes)
_LEBIN_REG_MAP = [
    _lb_reg("SYS", "UPTIME", 274, "INT", "RO", "Uptime", "Elapsed seconds from device startup"),
    _lb_reg("SYS", "STATUS", 32786, "BIN", "RO", "Status register", "Binary map of status flags"),
    _lb_reg("SYS", "COMMAND", 65874, "INT", "RW", "Command", "Value 9901 - Reset\r\nValue 8801 - Factory reset",
            0, 9901),
    _lb_reg("FACT", "SERIAL_NUMBER", 16777490, "INT", "RO", "Serial number", "Serial number in format XXYYZZZZ"),
    _lb_reg("FIRM", "REVISION", 33554706, "INT", "RO", "Firmware version",
            "Firmware revision as an incremental number, required by upgrade_firmware()"),
]


def guide() -> str:
    """
    Return quick guide for creating LE devices with lecore (also printed by ``python -m lecore guide``)
    :return: Guide text in Markdown
    """
    with io.open(GUIDE_FILE, 'r', encoding='utf-8') as f:
        return f.read()


def _load_reg_map(reg_map: PathLike) -> Tuple[list, str]:
    """
    Load register map and detect its protocol
    :param reg_map: Register map JSON file
    :return: Tuple (registers, protocol)
    """
    with io.open(reg_map, 'r', encoding='utf-8-sig') as f:
        try:
            regs = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Register map {reg_map} is not valid JSON: {e}") from None
    if not isinstance(regs, list) or not regs or not isinstance(regs[0], dict):
        raise ValueError(f"Register map {reg_map} must be a non-empty JSON list of registers")
    if 'Address' in regs[0]:
        return regs, 'modbus'
    if 'VarType' in regs[0]:
        return regs, 'lebin'
    raise ValueError(f"Register map {reg_map}: cannot detect protocol, expected 'Address' (Modbus) "
                     f"or 'VarType' (LeBin) keys")


def _reg_names(regs: list, protocol: str) -> List[str]:
    """
    Register names as used by the device classes (LeBin prefixes Name by Category)
    """
    if protocol == 'lebin':
        return [r['Category'] + '_' + r['Name'] if 'Category' in r else r['Name'] for r in regs]
    return [r['Name'] for r in regs]


def _identifier(name: str) -> str:
    ident = re.sub(r'\W', '_', name)
    if not ident or ident[0].isdigit() or ident[0] == '_' or keyword.iskeyword(ident):
        ident = 'R_' + ident
    return ident


def _check_class_name(name: Any) -> str:
    if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError(f"Name must be a valid Python identifier, got {name!r}")
    return name


def generate_regs(reg_map: PathLike, class_name: str, output: Optional[PathLike] = None) -> str:
    """
    Generate class with register name constants from register map (Modbus or LeBin)
    :param reg_map: Register map JSON file
    :param class_name: Name of generated class, e.g., 'MyDeviceRegs'
    :param output: Python file to write, None to only return the source
    :return: Python source of the class
    """
    _check_class_name(class_name)
    regs, protocol = _load_reg_map(reg_map)
    lines = [f"class {class_name}:"]
    used = set()
    for name in _reg_names(regs, protocol):
        ident = _identifier(name)
        if ident in used:
            raise ValueError(f"Register map {reg_map}: duplicate register name {name!r}")
        used.add(ident)
        lines.append(f"    {ident} = {json.dumps(name, ensure_ascii=False)}")
    src = "\n".join(lines) + "\n"
    if output is not None:
        with io.open(output, 'w', encoding='utf-8', newline='\n') as f:
            f.write(src)
    return src


def _write_json(path: str, data: Any) -> None:
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _write_text(path: str, text: str) -> None:
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def _find_reg_maps(directory: str, protocol: Optional[str]) -> List[Tuple[str, str]]:
    """
    Find register map JSON files in directory
    :return: List of (file name, protocol)
    """
    found = []
    for f in sorted(os.listdir(directory)):
        if not f.lower().endswith('.json'):
            continue
        try:
            _, detected = _load_reg_map(os.path.join(directory, f))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if protocol is None or detected == protocol:
            found.append((f, detected))
    return found


def _regs_prefix(map_file: str) -> str:
    """
    Prefix of register name class derived from register map file, e.g., 'PhaseDet' from 'PhaseDet_Modbus.json'
    """
    stem = os.path.splitext(map_file)[0]
    return re.sub(r'_(Modbus|registers)$', '', stem, flags=re.IGNORECASE)


def _find_regs_class(directory: str, map_file: str) -> Optional[Tuple[str, str]]:
    """
    Find class with register name constants generated together with the register map
    :return: Tuple (module name, class name) or None
    """
    candidates = []
    for f in sorted(os.listdir(directory)):
        if not f.endswith('Regs.py'):
            continue
        with io.open(os.path.join(directory, f), 'r', encoding='utf-8-sig') as fh:
            m = re.search(r'^class\s+(\w+)', fh.read(), re.MULTILINE)
        if m:
            candidates.append((f[:-3], m.group(1)))
    prefix = _regs_prefix(map_file).lower() + 'regs'
    for module, cls in candidates:
        if module.lower() == prefix:
            return module, cls
    # Other naming is accepted only when it cannot belong to another register map
    if len(candidates) == 1 and len({_regs_prefix(f) for f, _ in _find_reg_maps(directory, None)}) == 1:
        return candidates[0]
    return None


def _regs_constants(directory: str, module: str) -> List[str]:
    """
    Register names (string values of constants) defined in *Regs.py
    """
    with io.open(os.path.join(directory, module + '.py'), 'r', encoding='utf-8-sig') as f:
        return re.findall(r'^\s+[A-Za-z]\w*\s*=\s*["\'](.*?)["\']', f.read(), re.MULTILINE)


def _resolve_maps(directory: str, name: str, protocol: Optional[str], reg_map: Optional[PathLike],
                  template: bool, result: Dict[str, str]) -> List[Tuple[str, str]]:
    """
    Find register maps of the device
    :return: List of (map file, protocol), two items (Modbus first) for a device with both Modbus and LeBin map
    """
    if reg_map is not None:
        path = os.fspath(reg_map)
        if not os.path.isfile(path):
            path = os.path.join(directory, path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Register map not found: {reg_map}")
        if os.path.normcase(os.path.dirname(os.path.abspath(path))) != os.path.normcase(os.path.abspath(directory)):
            raise ValueError(f"Register map {reg_map} must be located in directory {directory}")
        _, detected = _load_reg_map(path)
        if protocol is not None and detected != protocol:
            raise ValueError(f"Register map {reg_map} is a {detected} map, but protocol is {protocol}")
        result[os.path.join(directory, os.path.basename(path))] = 'used'
        return [(os.path.basename(path), detected)]

    found = _find_reg_maps(directory, protocol)
    if len(found) > 1 and sorted(p for _, p in found) != sorted(PROTOCOLS):
        raise ValueError(f"More register maps in {directory}: {', '.join(f for f, _ in found)}, "
                         f"select one by reg_map")
    if found:
        found.sort(key=lambda m: PROTOCOLS.index(m[1]))
        for f, _ in found:
            result[os.path.join(directory, f)] = 'used'
        return found
    if not template:
        raise FileNotFoundError(f"No {protocol or 'Modbus/LeBin'} register map JSON in {directory}, "
                                f"generate it first or use template")
    protocol = protocol or 'modbus'
    map_file = f"{name}_Modbus.json" if protocol == 'modbus' else f"{name}_registers.json"
    _write_json(os.path.join(directory, map_file), _MODBUS_REG_MAP if protocol == 'modbus' else _LEBIN_REG_MAP)
    result[os.path.join(directory, map_file)] = 'created'
    return [(map_file, protocol)]


def new_device(name: str, protocol: Optional[str] = None, directory: PathLike = '.',
               reg_map: Optional[PathLike] = None, template: bool = False, gen_regs: bool = False,
               slave: int = 1, comport: str = 'COM1', baud_rate: int = 19200, parity: str = 'E',
               usb: Optional[Tuple[int, int, str]] = None, force: bool = False) -> Dict[str, str]:
    """
    Create a device class and missing configuration files in a directory, which typically already contains
    the register map JSON and its register name class (``*Regs.py``) from the LE register map generator::

        <name>.py, __init__.py, __main__.py and CLAUDE.md (if missing),
        ComSettings.json (+ UpgradeSettings.json, VisualSettings.json for Modbus)

    When the directory contains both Modbus and LeBin register map (and no protocol or reg_map is given), two classes
    sharing the register names are created: ``<name>`` (Modbus) and ``<name>LeBin`` with ``ComSettings_LeBin.json``.

    :param name: Device class name (also module name), e.g., 'MyDevice'
    :param protocol: 'modbus' (ModbusDev), 'lebin' (LeBinDev) or None to detect it from the register map(s)
    :param directory: Target directory (package with device files)
    :param reg_map: Register map JSON in the directory, None to find the ones present
    :param template: Create minimal register map template (and its *Regs.py) when no register map is present
    :param gen_regs: Generate missing ``*Regs.py`` from the register map
    :param slave: Default Modbus slave address (VisualSettings.json)
    :param comport: Default COM port (ComSettings*.json)
    :param baud_rate: Default baud rate (ComSettings*.json)
    :param parity: Default parity 'N', 'E' or 'O' (ComSettings*.json)
    :param usb: LeBin USB identification (vid, pid, sn) for search_com()
    :param force: Overwrite existing device modules, configuration files and __main__.py
    :return: Dictionary {file path: 'created' | 'overwritten' | 'kept' | 'used'}
    """
    _check_class_name(name)
    if protocol is not None and protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {PROTOCOLS}, got {protocol!r}")
    if not isinstance(slave, int) or not 1 <= slave <= 247:
        raise ValueError(f"slave must be in range 1..247, got {slave!r}")
    if parity not in ('N', 'E', 'O'):
        raise ValueError(f"parity must be one of ('N', 'E', 'O'), got {parity!r}")
    directory = os.fspath(directory)
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Directory not found: {directory}")
    result: Dict[str, str] = {}

    # Register maps, configuration files are resolved relative to the device module directory
    maps = _resolve_maps(directory, name, protocol, reg_map, template, result)
    dual = len(maps) == 2
    if usb is not None and 'lebin' not in [p for _, p in maps]:
        raise ValueError("usb is supported only for LeBin devices")
    # (class name, map file, protocol, communication settings file)
    devices = [(name + 'LeBin' if dual and p == 'lebin' else name, f, p,
                'ComSettings_LeBin.json' if dual and p == 'lebin' else 'ComSettings.json') for f, p in maps]
    existing = [os.path.join(directory, d[0] + '.py') for d in devices
                if os.path.exists(os.path.join(directory, d[0] + '.py'))]
    if existing and not force:
        raise FileExistsError(f"Device module already exists: {', '.join(existing)} (use force to overwrite)")

    regs_found = None
    for cls_name, map_file, proto, com_file in devices:
        # Class with register name constants, normally generated together with the register map
        regs = _find_regs_class(directory, map_file)
        if regs is not None:
            result.setdefault(os.path.join(directory, regs[0] + '.py'), 'used')
        elif gen_regs or result[os.path.join(directory, map_file)] == 'created':
            cls = _check_class_name(_regs_prefix(map_file) + 'Regs')
            generate_regs(os.path.join(directory, map_file), cls, os.path.join(directory, cls + '.py'))
            regs = (cls, cls)
            result[os.path.join(directory, cls + '.py')] = 'created'
        else:
            warnings.warn(f"No *Regs.py with register names found for {map_file}, reg_names of {cls_name} "
                          f"is not declared", UserWarning, stacklevel=2)
        regs_found = regs_found or regs

        # Register names missing in this map would be reported by UserWarning on every device creation
        missing = []
        if regs is not None:
            map_names = set(_reg_names(_load_reg_map(os.path.join(directory, map_file))[0], proto))
            missing = [c for c in _regs_constants(directory, regs[0]) if c not in map_names]
            if missing:
                warnings.warn(f"Register names of {regs[1]} missing in {map_file}: {', '.join(missing)}, "
                              f"reg_names of {cls_name} is not declared", UserWarning, stacklevel=2)

        # Configuration files, existing ones are kept
        # Com port, baud rate and parity apply to the Modbus device, LeBin of a dual device keeps the defaults
        com = {} if dual and proto == 'lebin' else dict(comport=comport, baud_rate=baud_rate, parity=parity)
        configs = {com_file: dict(_COM_SETTINGS, **com)}
        if proto == 'modbus':
            configs['UpgradeSettings.json'] = _UPGRADE_SETTINGS
            configs['VisualSettings.json'] = dict(_VISUAL_SETTINGS, slave_address=slave, reg_map=map_file)
        for file, data in configs.items():
            path = os.path.join(directory, file)
            if os.path.exists(path) and not force:
                result[path] = 'kept'
                continue
            result[path] = 'overwritten' if os.path.exists(path) else 'created'
            _write_json(path, data)

        path = os.path.join(directory, cls_name + '.py')
        result[path] = 'overwritten' if os.path.exists(path) else 'created'
        _write_text(path, _device_source(cls_name, proto, map_file, com_file, regs, missing, usb))

    # Package init, an existing one is never changed
    init = os.path.join(directory, '__init__.py')
    if os.path.exists(init):
        result[init] = 'kept'
        with open(init, encoding='utf-8') as f:
            init_text = f.read()
        absent = [d[0] for d in devices if not re.search(rf"import\s+(?:.*[\s,])?{re.escape(d[0])}(?![\w])", init_text)]
        if absent:
            warnings.warn(f"{init} is kept and does not export {', '.join(absent)}: 'from package import {absent[0]}' "
                          f"returns the submodule, add 'from .{absent[0]} import {absent[0]}'", stacklevel=2)
    else:
        text = "".join(f"from .{d[0]} import {d[0]}\n" for d in devices)
        if regs_found:
            text += (f"from .{regs_found[0]} import {regs_found[1]}\n\n"
                     f"# Shorter alias of register names\n"
                     f"from .{regs_found[0]} import {regs_found[1]} as Reg\n")
        _write_text(init, text)
        result[init] = 'created'

    # Command line entry point of the package (python -m <package>)
    main = os.path.join(directory, '__main__.py')
    if os.path.exists(main) and not force:
        result[main] = 'kept'
    else:
        result[main] = 'overwritten' if os.path.exists(main) else 'created'
        _write_text(main, _main_source([(d[0], d[2]) for d in devices],
                                       os.path.basename(os.path.abspath(directory))))

    # Usage notes for AI assistants (Claude Code), may be edited by user, so an existing one is never changed
    claude = os.path.join(directory, 'CLAUDE.md')
    if os.path.exists(claude):
        result[claude] = 'kept'
    else:
        _write_text(claude, _claude_source(devices, os.path.basename(os.path.abspath(directory)), regs_found))
        result[claude] = 'created'
    return result


def _device_source(name: str, protocol: str, map_file: str, com_file: str, regs: Optional[Tuple[str, str]],
                   missing: List[str], usb: Optional[Tuple[int, int, str]]) -> str:
    """
    Source of generated device module
    """
    if protocol == 'modbus':
        base, imports, extra = 'ModbusDev', 'ModbusDev', ''
        doc = "Optional constructor parameters com, reg_map, upg, visual and config_dir override default settings."
    else:
        base, imports = 'LeBinDev', 'LeBinDev, UsbId'
        vid, pid, sn = usb if usb is not None else (0, 0, '')
        extra = f"\n    usb = UsbId(vid={vid}, pid={pid}, sn={json.dumps(sn)})"
        doc = "Optional constructor parameters com, reg_map and config_dir override default settings."
    if com_file != 'ComSettings.json':
        extra = f"\n    com_settings = {json.dumps(com_file)}" + extra
    regs_import, regs_attr = "", ""
    if regs and not missing:
        regs_import = f"from .{regs[0]} import {regs[1]}\n"
        regs_attr = f"\n    reg_names = {regs[1]}"
    elif regs:
        doc += f"\n\n    Register names ({regs[1]}) are not checked, missing in {map_file}: {', '.join(missing)}."
    return (f"from lecore.Devices import {imports}\n"
            f"{regs_import}\n\n"
            f"class {name}({base}):\n"
            f"    \"\"\"\n"
            f"    {name} device\n\n"
            f"    {doc}\n"
            f"    \"\"\"\n"
            f"    reg_map = {json.dumps(map_file)}{regs_attr}{extra}\n")


def _claude_source(devices: List[Tuple[str, str, str, str]], package: str,
                   regs: Optional[Tuple[str, str]]) -> str:
    """
    Source of generated CLAUDE.md describing the device package API for AI assistants
    :param devices: List of (class name, map file, protocol, communication settings file), Modbus first
    :param package: Package name
    :param regs: Register name class (module, class) or None
    """
    dual = len(devices) == 2
    reg = 'Reg.NAME' if regs else '"NAME"'
    names = (f"Name constants are in `{regs[0]}.py` (alias `Reg`)" if regs else
             f"Names are listed by `python -m {package} --list`") + \
        ", descriptions, limits and enumerations in the register map."
    rows, api = [], []
    for cls, map_file, proto, com_file in devices:
        if proto == 'modbus':
            rows.append(f"| `{cls}` | Modbus RTU | `{map_file}` | `{com_file}`, slave address in `VisualSettings.json` |")
            api.append(f"with {cls}() as dev:  # Modbus RTU\n"
                       f"    dev.open(comport='COM5', slave=1)  # omitted arguments from {com_file}\n"
                       f"    value = dev.read({reg})  # None on communication error\n"
                       f"    dev.write({reg}, value)  # 0 on success, None on error\n")
        else:
            rows.append(f"| `{cls}` | LeBin | `{map_file}` | `{com_file}`, USB VID/PID/SN in class attribute `usb` |")
            api.append(f"with {cls}() as dev:  # LeBin\n"
                       f"    ports = dev.search_com()  # COM ports by USB VID/PID/SN\n"
                       f"    dev.open(comport=ports[0] if ports else None)\n"
                       f"    value = dev.read({reg})  # None on communication error\n"
                       f"    dev.write({reg}, value)  # True on success, None on error, "
                       f"list writes consecutive registers\n")
    imports = ", ".join([d[0] for d in devices] + (['Reg'] if regs else []))
    opts = f"[--comport COM5]{' [--slave 3]' if devices[0][2] == 'modbus' else ''}"
    cli = (f"python -m {package} --list                    # register names\n"
           f"python -m {package} --read NAME [NAME ...]    # read and print values {opts}\n")
    if dual:
        cli += f"python -m {package} --lebin --read NAME       # the same over LeBin ({devices[1][0]})\n"
    return (f"# {package} device package\n\n"
            f"Python package `{package}` controls the device by [lecore](https://pypi.org/project/lecore/). "
            f"Registers are accessed by name. {names}\n\n"
            f"| Class | Protocol | Register map | Connection settings |\n"
            f"|---|---|---|---|\n"
            + "\n".join(rows) +
            f"\n\n## Read register values from command line\n\n"
            f"Run from the parent directory (or `python .` in this directory):\n\n"
            f"```\n{cli}```\n\n"
            f"## Python API\n\n"
            f"```python\n"
            f"from {package} import {imports}\n\n"
            + "\n".join(api) +
            f"```\n\n"
            f"- `write()` validates values against the register map: read-only registers and out-of-range values "
            f"raise `ValueError`, unknown names `RegisterNotFoundError` (`KeyError`).\n"
            f"- `dev.upgrade_firmware(file)` returns True when upgraded and firmware version verified.\n"
            f"- Full lecore guide: `python -m lecore guide`.\n")


def _indent(code: str, spaces: int) -> str:
    return "".join(" " * spaces + line if line.strip() else line for line in code.splitlines(True))


def _main_source(devices: List[Tuple[str, str]], package: str) -> str:
    """
    Source of generated __main__.py running the device from command line
    :param devices: List of (class name, protocol), Modbus first
    :param package: Package name
    """
    protocols = [p for _, p in devices]
    modbus, dual = 'modbus' in protocols, len(devices) == 2
    title = " / ".join(n for n, _ in devices)
    usage = f"python -m {package} {'[--lebin] ' if dual else ''}[--comport COM5]" \
            f"{' [--slave 3]' if modbus else ''} [--read NAME ...] [--list] [--gui{' | --tui' if modbus else ''}]"

    imports = "".join(f"    from .{n} import {n}\n" for n, _ in devices)
    script_imports = "".join(f'    {n} = importlib.import_module(os.path.basename(_pkg_dir) + ".{n}").{n}\n'
                             for n, _ in devices)
    args = '    parser.add_argument("--comport", help="COM port, e.g., COM5 (default: ComSettings*.json)")\n'
    if dual:
        args += f'    parser.add_argument("--lebin", action="store_true", help="use LeBin device {devices[1][0]}")\n'
    if modbus:
        args += (f'    parser.add_argument("--slave", type=int, help="{"Modbus " if dual else ""}slave address '
                 f'(default: VisualSettings.json)")\n')
    args += ('    parser.add_argument("--read", nargs="+", metavar="NAME", help="read and print given registers")\n'
             '    parser.add_argument("--list", action="store_true", help="print register names only")\n'
             '    ui = parser.add_mutually_exclusive_group()\n'
             '    ui.add_argument("--gui", action="store_true", help="run graphic application")\n')
    if modbus:
        args += (f'    ui.add_argument("--tui", action="store_true", '
                 f'help="run textual user interface{" (Modbus)" if dual else ""}")\n')

    if dual:
        select = ('    if args.lebin and (args.tui or args.slave is not None):\n'
                  '        parser.error("--tui and --slave are available for Modbus device only")\n'
                  f'    device = {devices[1][0]} if args.lebin else {devices[0][0]}\n')
    else:
        select = f'    device = {devices[0][0]}\n'
    tui = '        if args.tui:\n            return dev.textual()\n' if modbus else ''
    open_modbus = 'dev.open(slave=args.slave, comport=args.comport)\n'
    open_lebin = ('comport = args.comport\n'
                  'if comport is None and dev.usb.vid:\n'
                  '    # Find the device by USB VID/PID/serial number\n'
                  '    ports = dev.search_com()\n'
                  '    comport = ports[0] if ports else None\n'
                  'dev.open(comport=comport)\n')
    if dual:
        port = '        if args.lebin:\n' + _indent(open_lebin, 12) + '        else:\n' + _indent(open_modbus, 12)
    else:
        port = _indent(open_modbus if modbus else open_lebin, 8)

    return (f'"""\n'
            f'Run {title} device from command line: {usage}\n\n'
            f'Without options all registers are read and printed.\n'
            f'Run from the package directory itself as: python . [options]\n'
            f'"""\n'
            f'import argparse\n'
            f'import importlib\n'
            f'import os\n'
            f'import sys\n\n'
            f'if __package__:\n'
            f'{imports}'
            f'else:\n'
            f'    # Started as a script (python . or python __main__.py), import the device as a package\n'
            f'    _pkg_dir = os.path.dirname(os.path.abspath(__file__))\n'
            f'    sys.path.insert(0, os.path.dirname(_pkg_dir))\n'
            f'{script_imports}\n\n'
            f'def main():\n'
            f'    parser = argparse.ArgumentParser(prog="python -m {package}", description="{title} device")\n'
            f'{args}'
            f'    args = parser.parse_args()\n'
            f'{select}\n'
            f'    with device() as dev:\n'
            f'        if args.list:\n'
            f'            print("\\n".join(dev.register_names()))\n'
            f'            return\n'
            f'        # Applications use their own COM port settings\n'
            f'        if args.gui:\n'
            f'            return dev.visual()\n'
            f'{tui}'
            f'        names = args.read or dev.register_names()\n'
            f'        unknown = [n for n in names if n not in dev.register_names()]\n'
            f'        if unknown:\n'
            f'            parser.error(f"unknown registers: {{\', \'.join(unknown)}} (see --list)")\n'
            f'{port}'
            f'        width = max(len(n) for n in names)\n'
            f'        for n in names:\n'
            f'            value = dev.read(n)\n'
            f'            print(f"{{n:{{width}}}}  {{\'communication error\' if value is None else value}}")\n\n\n'
            f'if __name__ == "__main__":\n'
            f'    main()\n')
