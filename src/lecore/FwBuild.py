"""
Firmware post-build: stamps the FW information block (version, build date, CRC, size) into a binary.

Python port of the legacy ``BinBuild.exe``, usable on any platform: ``python -m lecore binbuild``.
The CRC is the one of the STM32 hardware CRC unit: polynom 0x04C11DB7, init 0xFFFFFFFF, 32-bit little-endian
words, no reflection and no final XOR. The same CRC is produced for all targets.

Targets 1-7 are verified byte by byte against BinBuild.exe (build of 2024-09). Target 8 is not implemented.
Intel HEX files are supported too (except target 1): the image from the lowest address is processed like a binary,
gaps are filled with 0x00 (like ``objcopy -O binary``) and the result is written as a contiguous HEX.
"""
import datetime
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_POLYNOM = 0x04C11DB7
_MASK = 0xFFFFFFFF


def _make_table():
    table = []
    for i in range(256):
        value = i << 24
        for _ in range(8):
            value = ((value << 1) ^ _POLYNOM if value & 0x80000000 else value << 1) & _MASK
        table.append(value)
    return table


_TABLE = _make_table()


def crc32(data: bytes, crc: int = _MASK) -> int:
    """
    CRC of the STM32 hardware CRC unit over 32-bit little-endian words
    :param data: Data, its length must be a multiple of 4
    :param crc: Initial value
    :return: CRC
    """
    if len(data) % 4:
        raise ValueError("data length must be a multiple of 4")
    table = _TABLE
    for word in struct.unpack(f"<{len(data) // 4}I", data):
        crc ^= word
        crc = ((crc << 8) & _MASK) ^ table[crc >> 24]
        crc = ((crc << 8) & _MASK) ^ table[crc >> 24]
        crc = ((crc << 8) & _MASK) ^ table[crc >> 24]
        crc = ((crc << 8) & _MASK) ^ table[crc >> 24]
    return crc


@dataclass(frozen=True)
class Target:
    """
    Layout of the FW information block
    :param offset: Offset of the block in the binary, None = prepended to the file (LeCloud)
    :param decimal: Version and build date are stored as decimal numbers (otherwise BCD hex)
    :param clear_from: Bytes of the 32 B block from this index are taken as 0xFF in the CRC (None = nothing)
    :param description: Description for the command line help
    """
    offset: Optional[int]
    decimal: bool
    clear_from: Optional[int]
    description: str


TARGETS = {
    1: Target(None, False, None, "beginning of the file for LeCloud server (JLT products)"),
    2: Target(512, False, None, "512 B offset in the FW (FG320)"),
    3: Target(512, False, None, "512 B offset in the FW (VMS)"),
    4: Target(192, False, None, "192 B offset in the FW (small alarm), device ID in the block"),
    5: Target(1024, True, None, "1024 B offset in the FW, decimal information (SBD)"),
    6: Target(512, True, 16, "512 B offset in the FW, decimal information (SIR1)"),
    7: Target(512, True, 16, "512 B offset in the FW, decimal information (Fixture)"),
}

_HEX_MAX_SIZE = 16 * 1024 * 1024  # protection against huge gaps (e.g. option bytes far away from the FW)
_HEX_RECORD = 16

_LEGACY_OFFSET = 512  # target 1 checks the same free space as the targets with a 512 B offset


def build(data: bytes, target: int, version: str, dev_id: str = "", date: Optional[datetime.date] = None) -> tuple:
    """
    Stamp the FW information block into a binary
    :param data: Binary content (padded with zeros to a multiple of 4)
    :param target: Target number, see ``TARGETS``
    :param version: FW version, hexadecimal (BCD) like in BinBuild
    :param dev_id: Device ID (max 4 characters), used by target 4 only
    :param date: Build date (default today)
    :return: Tuple (new binary content, CRC)
    """
    if target not in TARGETS:
        raise ValueError(f"unknown target {target}, valid: {', '.join(map(str, TARGETS))}")
    layout = TARGETS[target]
    version_hex = int(version, 16)
    try:
        version_dec = int(version, 10)
    except ValueError:
        version_dec = 0  # BinBuild stores 0 when the version is not a decimal number
    assembly = (date or datetime.date.today()).strftime("%Y%m%d")
    if target == 4 and (len(dev_id) > 4 or not dev_id.isascii()):
        raise ValueError(f"device ID '{dev_id}' must be at most 4 ASCII characters")

    binary = bytearray(data)
    binary += bytes(-len(binary) % 4)
    size = len(binary)

    offset = layout.offset if layout.offset is not None else _LEGACY_OFFSET
    if target == 4:
        free = [(offset, offset + 32, 0x00)]
    else:
        length = 16 if target >= 6 else 32
        free = [(offset - 32, offset, 0x00), (offset, offset + length, 0xFF)]
    for start, end, value in free:
        if end > size or any(b != value for b in binary[start:end]):
            raise ValueError("there must be free space for the FW information block "
                             f"(bytes {start}..{end - 1} must be 0x{value:02X})")

    crc_data = bytearray(binary)
    if layout.clear_from is not None:
        crc_data[offset + layout.clear_from:offset + 32] = bytes([0xFF]) * (32 - layout.clear_from)
    crc = crc32(bytes(crc_data))

    if target == 4:
        info = struct.pack("<I4sIII", version_hex, dev_id.encode("ascii"), size, crc, int(assembly, 16))
    elif layout.decimal:
        info = struct.pack("<IIII", version_dec, int(assembly), crc, size)
    else:
        info = struct.pack("<IIII", version_hex, int(assembly, 16), crc, size)

    if layout.offset is None:
        return info + bytes(binary), crc
    stamped = bytes(binary)
    return stamped[:offset] + info + stamped[offset + len(info):], crc


def read_hex(text: str) -> tuple:
    """
    Parse an Intel HEX file into a contiguous image, gaps are filled with 0x00
    :param text: HEX file content
    :return: Tuple (base address, image, start address record line or None)
    """
    chunks = {}
    upper = 0
    start = None
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            if line[0] != ":":
                raise ValueError
            record = bytes.fromhex(line[1:])
        except ValueError:
            raise ValueError(f"line {number}: not an Intel HEX record") from None
        if len(record) < 5 or len(record) != record[0] + 5:
            raise ValueError(f"line {number}: wrong record length")
        if sum(record) & 0xFF:
            raise ValueError(f"line {number}: wrong checksum")
        rtype, payload = record[3], record[4:-1]
        if rtype == 0x00:
            address = upper + int.from_bytes(record[1:3], "big")
            chunks[address] = chunks.get(address, b"") + payload
        elif rtype == 0x01:
            break
        elif rtype == 0x02:
            upper = int.from_bytes(payload, "big") << 4
        elif rtype == 0x04:
            upper = int.from_bytes(payload, "big") << 16
        elif rtype in (0x03, 0x05):
            start = line
        else:
            raise ValueError(f"line {number}: unknown record type {rtype:02X}")
    if not chunks:
        raise ValueError("no data in the HEX file")
    base = min(chunks)
    size = max(address + len(payload) for address, payload in chunks.items()) - base
    if size > _HEX_MAX_SIZE:
        raise ValueError(f"HEX image is too large ({size} B from 0x{base:08X}), check for data at distant addresses")
    image = bytearray(size)
    for address, payload in chunks.items():
        image[address - base:address - base + len(payload)] = payload
    return base, bytes(image), start


def _hex_record(rtype: int, address: int, payload: bytes) -> str:
    record = bytes([len(payload)]) + address.to_bytes(2, "big") + bytes([rtype]) + payload
    return ":" + (record + bytes([-sum(record) & 0xFF])).hex().upper()


def write_hex(base: int, image: bytes, start: Optional[str] = None) -> str:
    """
    Write a contiguous image as an Intel HEX file
    :param base: Address of the image
    :param image: Image content
    :param start: Start address record line (from ``read_hex``)
    :return: HEX file content
    """
    lines = []
    upper = None
    address = base
    end = base + len(image)
    while address < end:
        if address >> 16 != upper:
            upper = address >> 16
            lines.append(_hex_record(0x04, 0, upper.to_bytes(2, "big")))
        length = min(_HEX_RECORD, end - address, 0x10000 - (address & 0xFFFF))
        lines.append(_hex_record(0x00, address & 0xFFFF, image[address - base:address - base + length]))
        address += length
    if start:
        lines.append(start)
    lines.append(_hex_record(0x01, 0, b""))
    return "\n".join(lines) + "\n"


def build_file(target: int, path, version: str, suffix: str = "", out_dir=None,
               date: Optional[datetime.date] = None) -> tuple:
    """
    Stamp the FW information block into a binary or Intel HEX (``.hex``) file, the result is written next to it
    (or to ``out_dir``) as ``<name>[-<suffix>]-<yyyymmdd>-<version>.bin`` (``.hex``)
    :param target: Target number, see ``TARGETS``
    :param path: Binary or Intel HEX file
    :param version: FW version, hexadecimal (BCD)
    :param suffix: Suffix of the output name, also used as the device ID of target 4
    :param out_dir: Output directory (default directory of the input file)
    :param date: Build date (default today)
    :return: Tuple (output path, CRC)
    """
    path = Path(path)
    date = date or datetime.date.today()
    is_hex = path.suffix.lower() == ".hex"
    if is_hex:
        if TARGETS.get(target) is not None and TARGETS[target].offset is None:
            raise ValueError(f"target {target} prepends the block to the file, it is not supported for HEX files")
        base, image, start = read_hex(path.read_text(encoding="ascii"))
        result, crc = build(image, target, version, suffix, date)
        content = write_hex(base, result, start).encode("ascii")
    else:
        content, crc = build(path.read_bytes(), target, version, suffix, date)
    name = f"{path.stem}{'-' + suffix if suffix else ''}-{date:%Y%m%d}-{int(version, 16):X}"
    name += ".hex" if is_hex else ".bin"
    out = Path(out_dir) / name if out_dir else path.with_name(name)
    out.write_bytes(content)
    return out, crc
