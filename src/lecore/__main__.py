"""
Command line jump-start for lecore, see ``python -m lecore --help``
"""
import argparse
import sys
import warnings

from .Scaffold import guide, new_device, generate_regs, generate_tests
from .FwBuild import TARGETS, build_file


def _show_warning(message, category, filename, lineno, file=None, line=None):
    print(f"warning: {message}", file=sys.stderr)


def main(argv=None) -> int:
    warnings.showwarning = _show_warning
    parser = argparse.ArgumentParser(prog="lecore", description="Logic Elements core utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("guide", help="print quick guide for creating devices with lecore")

    p = sub.add_parser("new-device", help="create device class and missing configuration files next to the "
                                          "register map")
    p.add_argument("name", help="device class name, e.g., MyDevice")
    proto = p.add_mutually_exclusive_group()
    proto.add_argument("--modbus", dest="protocol", action="store_const", const="modbus",
                       help="Modbus device (default: detected from register map)")
    proto.add_argument("--lebin", dest="protocol", action="store_const", const="lebin", help="LeBin device")
    p.add_argument("--dir", default=".", help="directory with register map (default: current)")
    p.add_argument("--reg-map", help="register map JSON in the directory (default: the single one found)")
    p.add_argument("--template", action="store_true",
                   help="create minimal register map template and *Regs.py when no register map is present")
    p.add_argument("--gen-regs", action="store_true", help="generate missing *Regs.py from the register map")
    p.add_argument("--slave", type=int, default=1, help="default Modbus slave address")
    p.add_argument("--comport", default="COM1", help="default COM port")
    p.add_argument("--baud-rate", type=int, default=19200, help="default baud rate")
    p.add_argument("--parity", default="E", choices=("N", "E", "O"), help="default parity")
    p.add_argument("--usb", nargs=3, metavar=("VID", "PID", "SN"), help="LeBin USB identification for search_com()")
    p.add_argument("--force", action="store_true", help="overwrite existing device module and configuration files")

    p = sub.add_parser("new-tests", help="create missing communication test files (test_modbus.py, test_lebin.py) "
                                         "for device classes in a directory")
    p.add_argument("--dir", default=".", help="directory with device modules (default: current)")
    p.add_argument("--force", action="store_true", help="overwrite existing test files")

    p = sub.add_parser("regs", help="generate class with register name constants from a register map")
    p.add_argument("reg_map", help="register map JSON (Modbus or LeBin)")
    p.add_argument("--class", dest="class_name", default="Regs", help="generated class name")
    p.add_argument("-o", "--output", help="output Python file (default: print)")

    p = sub.add_parser("binbuild", help="stamp the FW information block (CRC, version, size) into a binary or HEX "
                                        "(replaces BinBuild.exe)",
                       formatter_class=argparse.RawDescriptionHelpFormatter,
                       epilog="targets:\n" + "\n".join(f"  {n} - {t.description}" for n, t in TARGETS.items()))
    p.add_argument("target", type=int, choices=sorted(TARGETS), help="FW information block layout")
    p.add_argument("file", help="binary or Intel HEX (.hex) file")
    p.add_argument("version", help="FW version, hexadecimal (BCD)")
    p.add_argument("--suffix", default="", help="suffix of the output name, device ID for target 4")
    p.add_argument("--out-dir", help="output directory (default: directory of the binary)")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "guide":
            print(guide())
        elif args.cmd == "new-device":
            usb = (int(args.usb[0], 0), int(args.usb[1], 0), args.usb[2]) if args.usb else None
            result = new_device(args.name, args.protocol, args.dir, args.reg_map, args.template, args.gen_regs,
                                args.slave, args.comport, args.baud_rate, args.parity, usb, args.force)
            for path, status in result.items():
                print(f"{status:12}{path}")
        elif args.cmd == "new-tests":
            for path, status in generate_tests(args.dir, args.force).items():
                print(f"{status:12}{path}")
        elif args.cmd == "regs":
            src = generate_regs(args.reg_map, args.class_name, args.output)
            if args.output is None:
                print(src, end="")
        elif args.cmd == "binbuild":
            out, crc = build_file(args.target, args.file, args.version, args.suffix, args.out_dir)
            print(f"{out}\nNew File created with CRC value {crc:08X}")
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
