"""Large Address Aware flag for a 32-bit client exe: +2 GB of address space on 64-bit Windows.

DriftCity.exe is a 32-bit (0x014c) image whose PE Characteristics lacks bit 0x20 (IMAGE_FILE_LARGE_ADDRESS_AWARE),
so Windows gives it a 2 GB user address space. With the 2016 port's ~600 player cars the client runs out while it
streams a city and dies with "Microsoft Visual C++ Runtime Library - abnormal program termination" (user,
2026-11-19: after viewing many cars in the dealership / garage, on entering Moon Palace; the GameLog stops after
NeoCity at "ThreadLoad0 Start:MoonPalace:Main"). Setting that one flag lets a 64-bit Windows give it 4 GB; it is a
header-only change, no code is patched, and the client is unaffected if Windows cannot honour it.

usage (from Emulator/):
    python -m tools.laa status [EXE]        show the flag (default ../DriftCity Dev Ed/DriftCity.exe)
    python -m tools.laa apply  [EXE]        set it (the original is kept in client_backup/)
    python -m tools.laa remove [EXE]        clear it again

The client must be restarted: a running process keeps the header it was started with.
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
DEFAULT = os.path.join(ROOT, 'DriftCity Dev Ed', 'DriftCity.exe')
BACKUP_DIR = os.path.join(HERE, '..', 'client_backup')
LAA = 0x0020
MACHINE_I386 = 0x014C


def characteristics(data):
    """(the offset of Characteristics, its value) of a PE image."""
    if data[:2] != b'MZ':
        raise ValueError('not an MZ file')
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('no PE header')
    return pe + 4 + 18, struct.unpack_from('<H', data, pe + 4 + 18)[0]


def status(path):
    data = open(path, 'rb').read()
    off, chars = characteristics(data)
    machine = struct.unpack_from('<H', data, struct.unpack_from('<I', data, 0x3C)[0] + 4)[0]
    return dict(path=path, offset=off, characteristics=chars, laa=bool(chars & LAA),
                machine=machine, i386=machine == MACHINE_I386)


def normalised(data):
    """The image with the LAA bit cleared, so a change of that one header flag does not look like a different exe
    (tools/client2016.py checks the original's SHA-256 before patching ports). Non-PE input comes back unchanged, so
    the caller still reports it as an unsupported build."""
    try:
        off, chars = characteristics(bytes(data))
    except (ValueError, struct.error):
        return bytes(data)
    out = bytearray(data)
    struct.pack_into('<H', out, off, chars & ~LAA)
    return bytes(out)


def set_flag(path, on=True, backup=True):
    """-> the new Characteristics value; the original goes to client_backup/<name>.before_laa once."""
    data = bytearray(open(path, 'rb').read())
    off, chars = characteristics(bytes(data))
    new = (chars | LAA) if on else (chars & ~LAA)
    if new == chars:
        return chars
    if backup:
        keep = os.path.join(BACKUP_DIR, os.path.basename(path) + '.before_laa')
        if not os.path.exists(keep):
            os.makedirs(BACKUP_DIR, exist_ok=True)
            shutil.copy2(path, keep)
            print('  original kept as', os.path.normpath(keep))
    struct.pack_into('<H', data, off, new)
    tmp = path + '.tmp'
    open(tmp, 'wb').write(bytes(data))
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    return new


def main(argv):
    action = argv[0] if argv else 'status'
    path = argv[1] if len(argv) > 1 else DEFAULT
    if action not in ('status', 'apply', 'remove'):
        sys.exit(__doc__)
    if not os.path.exists(path):
        sys.exit(f'no such file: {path}')
    if action == 'status':
        st = status(path)
        print(f'{st["path"]}: Characteristics 0x{st["characteristics"]:04x}, '
              f'LAA {"on" if st["laa"] else "off"}, machine 0x{st["machine"]:04x}'
              f'{" (32-bit)" if st["i386"] else ""}')
        return
    if action == 'apply':
        st = status(path)
        if not st['i386']:
            sys.exit('not a 32-bit image: LAA would do nothing')
    new = set_flag(path, on=action == 'apply')
    print(f'  Characteristics 0x{new:04x}: LAA {"on" if new & LAA else "off"}')
    print('  restart the client for it to take effect')


if __name__ == '__main__':
    main(sys.argv[1:])
