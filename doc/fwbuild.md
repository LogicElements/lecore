# Firmware post-build (FW information block)

`lecore.FwBuild` replaces the legacy `BinBuild.exe`: it stamps the FW information block (version, build date, CRC,
size) into a firmware binary. It runs on any platform.

```
python -m lecore binbuild 5 build/fw.bin 2            # -> build/fw-<yyyymmdd>-2.bin
python -m lecore binbuild --help                      # targets, --suffix, --out-dir
```

```python
from lecore import FwBuild
out_path, crc = FwBuild.build_file(5, "build/fw.bin", "2")
data, crc = FwBuild.build(binary, 5, "2")             # bytes in, bytes out
```

- CRC: polynom 0x04C11DB7, init 0xFFFFFFFF, 32-bit little-endian words, no reflection, no final XOR (the STM32
  hardware CRC unit). The binary is padded with zeros to a multiple of 4 B; the padded size is stored in the block.
- The block position must be free in the binary: the 32 B before it are `0x00`, the 32 B of the block are `0xFF`
  (target 4: 32 B of `0x00`, targets 6 and 7: 16 B of `0xFF`). Otherwise the build fails.
- The version argument is hexadecimal (BCD) like in `BinBuild.exe`; targets with decimal information (5, 6, 7) store
  it as a decimal number.
- Targets 1-7 give byte-identical output to `BinBuild.exe` (build of 2024-09). Target 8 (file name derived from
  the version) is not implemented.
- Target 4: the device ID (`--suffix`) is at most 4 ASCII characters, a shorter one is padded with zeros.
- Targets 6 and 7: only 16 B of the block must be free, bytes 16..31 are taken as `0xFF` in the CRC.
