"""The 2016 client's car limit raised from 450 to 2000 car Unique Ids (user, 2026-11-13).

python -m tools.carlimit2016 status | apply | remove [--client DIR]

The 2016 client (DriftCity Dev Ed/DriftCity.exe, 2016-02-16) keeps, per VisualItem item, one byte per car Unique Id
at +0x7c of a 0x248-byte record: Ids 0-449 (LoadVisualItemList 0x8b6570 has a 450-entry column map and writes
record +0x7c + Id unchecked; the next field is the float at +0x240). The vehicle tables themselves are maps without
an Id limit (GetVehicleInfo 0x4d6c.., GetVehicleUpgradeInfo, GetVehicleDisplayInfo), so this is the only limit found.

Unlike the 2011 patch (tools/port2016.py `exe`: a bigger record), the record keeps its size, because the 2016 client
copies records by value into other objects (rep movs of 0x92 dwords, e.g. 0x4c76c8). Instead:
  - a new section .p20 at 0xaf9000 (code: tools/p20_cars.s) holds the loader (2048 car columns), and one bit per
    (VisualItem row, Id 450-1999) in `ext` (200 bytes per row, 16384 rows; zero-filled memory, not in the file);
  - record +0x23e (u16; never read: Ids 450 / 451 failed every check) is the row number + 1, so every copy of a
    record still finds its bits;
  - the 8 places that read a fit byte (the only `byte [reg+reg+0x7c]` accesses in the exe) ask `ext_fit` for Ids
    450-1999, and their Id checks are raised to 2000: IsCompatible 0x7c6cc8, FindDefaultPart 0x7c6d24 / 0x7c6d69,
    IsCompatible(carId, uid) 0x7c73c9 / 0x7c73df, garage / shop 0x63b06c, two items for one car 0x6cd07d,
    0x6d1529 / 0x6d153e, 0x6e3296 / 0x6e32ab;
  - the default part cache (manager +0x770, 450 x 59) stays; its getter 0x7c68a0 calls FindDefaultPart for the
    other Ids.

`apply` changes DriftCity.exe in place (the launcher starts that file) and keeps the first original in
client_backup/2016/DriftCity.exe.orig; `remove` gives back the exact original bytes. tools/client2016.py keeps the
patch when it rebuilds DriftCity2016Test.exe.
"""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
P20_VA = 0xaf9000
P20_END = 0xe1b6e0                    # image_end of tools/p20_cars.s
P20_VSIZE = (P20_END - P20_VA + 0xfff) & ~0xfff
SYM = dict(load=0xaf9000, cache_get=0xaf92b0, d_compat=0xaf92f0, d_default=0xaf9320, d_compat2=0xaf9350,
           d_shop=0xaf9370, d_pair=0xaf93a0, d_obj1=0xaf9420, d_obj2=0xaf9450)
P20_CODE = bytes.fromhex(
    '5589e5535657ff7508b8b04f8b00ffd083c40489c685f67d1168b8c597006a01b8702b4000ffd083c40831c0b9000800'
    '008d3de096af00f3abc7058094af0000000000c7058494af0000000000688494af00688094af00686484940056b89046'
    '8b00ffd083c41031ff3b3d8494af007d3b81ff000800007d33c7058c94af0000000000688c94af0068b06994008d4f07'
    '5156b850488b00ffd083c4108b158c94af008914bde096af0047ebbd6a0456b820458b00ffd083c408c7058894af0000'
    '000000a18894af003b058094af000f8d7d01000031c0b9920000008d3d9094af00f3abc705d096af00000080bf689094'
    'af0068b06994006a0156b850488b00ffd0689494af0068b06994006a0256b850488b00ffd068c094af0068d46c94006a'
    '0356b850488b00ffd068e094af0068705295006a0456b850488b00ffd083c44068e494af0068d46c94006a0556b85048'
    '8b00ffd0c6050b95af0000689894af0068d46c94006a0656b850488b00ffd083c4208b1d8894af0081fb004000007204'
    '31dbeb228d430166a3ce96af0069dbc800000081c3e0b6af005731c0b93200000089dff3ab5f31ff3b3d8494af007d68'
    '81ff000800007d60c7058c94af0000000000688c94af0068b06994008d4f075156b850488b00ffd083c4108b14bde096'
    'af0081fac2010000730da08c94af0088820c95af00eb1e81fad0070000731685db7412803d8c94af0001750981eac201'
    '00000fab1347eb908d0d9094af00b870968b00ffd08b4d0c8b11689094af00a19094af004850ff52046a0156b820458b'
    '00ffd083c408ff058894af00e972feffff56b8a0528b00ffd083c4045f5e5b5dc38db426000000002e8db42600000000'
    '52510fb7903e02000085d2742d81fa00400000772581e9c2010000721d81f90e06000073154a69d2c80000000fa38ae0'
    'b6af00730531d2595ac383caff595ac33dc20100007d0668af687c00c33dd00700007d208b54240885d27c1883fa3a7f'
    '135250b8006d7c00ffd085c074068b4004c2080031c0c208008db4260000000081f9c20100007d0668d06c7c00c381f9'
    'd00700007c0668db6c7c00c3e85fffffff0f94c0c20c00902e8db426000000008b44241401f23dc20100007d0b807c02'
    '7c0168746d7c00c35189c189d0e82effffff5968746d7c00c38db4260000000081fec20100007d07807c307c01eb0789'
    'f1e80affffff0f94c068e7737c00c39081f9d0070000731c81f9c20100007307807c017c01eb05e8e4feffff75066883'
    'b06300c3689eb46300c38db60000000081f9c20100007d066870d06c00c353570fb79e3e0200000fb7ba3e02000085db'
    '743a85ff743681fb00400000772e81ff0040000077264b69dbc80000004f69ffc800000031c98b848be0b6af0085848f'
    'e0b6af00750e4183f9327cea5f5b6885d06c00c35f5bb8010000006887d06c00c38db426000000002e8db42600000000'
    '8b40043dc2010000730b807c387c016846156d00c3515089c189f8e830feffff58596846156d00c32e8db42600000000'
    '8b480481f9c2010000730b807c397c0168b3326e00c35089f8e802feffff5868b3326e00c30000000000000000000000'
    '00000000000000000000000000000000')


def _jmp(at, to, size):
    return (b'\xe9' + struct.pack('<i', to - (at + 5)) + b'\x90' * (size - 5)).hex()


# (VA, original bytes, new bytes)
PATCHES = [
    (0x8b6570, '558bec83e4', _jmp(0x8b6570, SYM['load'], 5)),                      # LoadVisualItemList
    (0x7c68a8, '3dc20100007d23', _jmp(0x7c68a8, SYM['cache_get'], 7)),             # default part cache getter
    (0x7c6cc8, '81f9c20100007d0b', _jmp(0x7c6cc8, SYM['d_compat'], 8)),            # IsCompatible
    (0x7c6d24, '81f9c2010000', '81f9d0070000'),                                    # FindDefaultPart: Id check
    (0x7c6d69, '8b44241403d6807c027c01', _jmp(0x7c6d69, SYM['d_default'], 11)),    # ... its fit test
    (0x7c73c9, '81fec2010000', '81fed0070000'),                                    # IsCompatible(carId, uid)
    (0x7c73df, '807c307c010f94c0', _jmp(0x7c73df, SYM['d_compat2'], 8)),
    (0x63b06c, '81f9c20100000f8326040000807c017c010f851b040000', _jmp(0x63b06c, SYM['d_shop'], 23)),
    (0x6cd07d, '81f9c20100007ceb', _jmp(0x6cd07d, SYM['d_pair'], 8)),              # two items fitting one car
    (0x6d1529, '817804c2010000', '817804d0070000'),
    (0x6d153e, '8b4004807c387c01', _jmp(0x6d153e, SYM['d_obj1'], 8)),
    (0x6e3296, '817804c2010000', '817804d0070000'),
    (0x6e32ab, '8b4804807c397c01', _jmp(0x6e32ab, SYM['d_obj2'], 8)),
]


def _pe(exe):
    pe = struct.unpack_from('<I', exe, 0x3c)[0]
    nsec = struct.unpack_from('<H', exe, pe + 6)[0]
    sec = pe + 24 + struct.unpack_from('<H', exe, pe + 20)[0]
    return pe, nsec, sec


def _off(va):
    """File offset of a code address (the first section: file 0x400 -> 0x401000)."""
    return va - 0x401000 + 0x400


def applied(data):
    """True when the image has the .p20 section."""
    if data[:2] != b'MZ':
        return False
    pe, nsec, sec = _pe(data)
    return any(data[sec + 40 * i:sec + 40 * i + 8] == b'.p20\0\0\0\0' for i in range(nsec))


def apply(data):
    """The 2016 image with the car limit raised. Refuses anything but the expected bytes."""
    if applied(data):
        return bytes(data)
    exe = bytearray(data)
    pe, nsec, sec = _pe(exe)
    if struct.unpack_from('<I', exe, pe + 24 + 96 + 5 * 8 + 4)[0]:
        raise ValueError('the image has relocations: not the 2016 Dev Ed build')
    for va, old, new in PATCHES:
        cur = exe[_off(va):_off(va) + len(old) // 2].hex()
        if cur != old:
            raise ValueError(f'unexpected bytes at {va:#x}: {cur} (nothing written)')
    last = sec + 40 * (nsec - 1)
    vsize, rva, rawsize, raw = struct.unpack_from('<IIII', exe, last + 8)
    if sec + 40 * (nsec + 1) > struct.unpack_from('<I', exe, sec + 20)[0]:
        raise ValueError('no room for a section header')
    if raw + rawsize != len(exe) or 0x400000 + ((rva + vsize + 0xfff) & ~0xfff) != P20_VA:
        raise ValueError('unexpected section layout')
    for va, old, new in PATCHES:
        n = bytes.fromhex(new)
        exe[_off(va):_off(va) + len(n)] = n
    body = P20_CODE + bytes((-len(P20_CODE)) % 0x200)
    struct.pack_into('<8sIIIIIIHHI', exe, sec + 40 * nsec, b'.p20', P20_VSIZE, P20_VA - 0x400000, len(body), len(exe),
                     0, 0, 0, 0, 0xE0000060)
    struct.pack_into('<H', exe, pe + 6, nsec + 1)
    struct.pack_into('<I', exe, pe + 24 + 56, P20_VA - 0x400000 + P20_VSIZE)          # SizeOfImage
    return bytes(exe + body)


def strip(data):
    """The image without the patch (the exact bytes apply() started from)."""
    if not applied(data):
        return bytes(data)
    exe = bytearray(data)
    pe, nsec, sec = _pe(exe)
    last = sec + 40 * (nsec - 1)
    if exe[last:last + 8] != b'.p20\0\0\0\0':
        raise ValueError('.p20 is not the last section')
    rawsize, raw = struct.unpack_from('<II', exe, last + 16)
    if raw + rawsize != len(exe):
        raise ValueError('unexpected data after .p20')
    for va, old, new in PATCHES:
        if exe[_off(va):_off(va) + len(new) // 2].hex() != new:
            raise ValueError(f'unexpected bytes at {va:#x}')
        exe[_off(va):_off(va) + len(old) // 2] = bytes.fromhex(old)
    del exe[raw:]
    exe[last:last + 40] = bytes(40)
    struct.pack_into('<H', exe, pe + 6, nsec - 1)
    struct.pack_into('<I', exe, pe + 24 + 56, P20_VA - 0x400000)
    return bytes(exe)


def build_code():
    """P20 bytes assembled from tools/p20_cars.s, or None without binutils."""
    src = Path(__file__).with_name('p20_cars.s')
    if not (shutil.which('as') and shutil.which('ld')):
        return None
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['as', '--32', '-o', f'{d}/p.o', str(src)], check=True)
        subprocess.run(['ld', '-m', 'elf_i386', f'-Ttext={P20_VA:#x}', '--oformat', 'binary', '-o', f'{d}/p.bin',
                        f'{d}/p.o'], check=True)
        return open(f'{d}/p.bin', 'rb').read()[:len(P20_CODE)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('action', choices=('status', 'apply', 'remove'))
    parser.add_argument('--client', type=Path, default=ROOT / 'DriftCity Dev Ed')
    args = parser.parse_args()
    for name in ('DriftCity.exe', 'DriftCity2016Test.exe'):
        path = args.client / name
        if not path.exists():
            continue
        data = path.read_bytes()
        if args.action == 'status':
            print(f'{name}: car Unique Ids up to', 1999 if applied(data) else 449)
            continue
        new = apply(data) if args.action == 'apply' else strip(data)
        if new == data:
            print(f'{name}: nothing to do')
            continue
        if name == 'DriftCity.exe':
            backup = ROOT / 'Emulator/client_backup/2016/DriftCity.exe.orig'
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(path, backup)
                print('  original kept as', backup)
        tmp = path.with_suffix('.exe.tmp')
        tmp.write_bytes(new)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: car limit', 'raised to 2000 Unique Ids (.p20 section added)' if args.action == 'apply'
              else 'patch removed')


if __name__ == '__main__':
    main()
