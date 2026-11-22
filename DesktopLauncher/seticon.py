"""Put the launcher icon (a 256x256 RGBA PNG) and its name into electron.exe, in place.

No rcedit here (it is a Windows program), so this rewrites the exe's existing icon resources: Electron ships 4 icons
(16, 32, 48 as bitmaps, 256 as PNG). Each new image is written over the old one in the same space (it must not be
bigger) and the resource sizes and the icon group are updated. The .rsrc layout does not change.

The name: the version resource's strings (FileDescription is what Task Manager shows, "Electron" otherwise) are
rebuilt as openDC Launcher's and written over the old block, which is longer.

usage: python3 seticon.py ICON.png EXE [VERSION]        (needs: pip install pefile pillow)
"""
import io
import struct
import sys

import pefile
from PIL import Image


def bmp_icon(img, n):
    """an ICO-style 32-bit DIB: header (height doubled) + BGRA bottom-up + 1-bit AND mask (all 0: alpha decides)."""
    im = img.resize((n, n), Image.LANCZOS).convert('RGBA')
    hdr = struct.pack('<IiiHHIIiiII', 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    px = bytearray()
    for y in range(n - 1, -1, -1):
        for x in range(n):
            r, g, b, a = im.getpixel((x, y))
            px += bytes((b, g, r, a))
    mask_row = ((n + 31) // 32) * 4
    return hdr + bytes(px) + bytes(mask_row * n)


def png_icon(img, limit):
    """the 256 PNG, quantized more and more until it fits the old slot."""
    for colors in (None, 256, 192, 128, 96, 64):
        im = img if colors is None else img.quantize(colors, method=Image.Quantize.FASTOCTREE)
        buf = io.BytesIO()
        im.save(buf, 'PNG', optimize=True)
        if len(buf.getvalue()) <= limit:
            return buf.getvalue()
    raise SystemExit('the 256 PNG does not fit even at 64 colors')


def _pad(b):
    return b + b'\0' * ((4 - len(b) % 4) % 4)


def _node(key, value=b'', vtype=1, children=b'', vlen=None):
    """one VS_VERSIONINFO node: wLength, wValueLength, wType, key (UTF-16, padded), value (padded), children."""
    k = _pad(b'\0' * 6 + (key + '\0').encode('utf-16le'))[6:]
    body = k + (_pad(value) if value else b'') + children
    if vlen is None:
        vlen = len(value) // 2 if vtype == 1 else len(value)
    return struct.pack('<HHH', 6 + len(body), vlen, vtype) + body


def _version_block(old, strings):
    """a new RT_VERSION block: the old fixed info and translation, new strings."""
    fixed_at = old.find(b'\xbd\x04\xef\xfe')          # VS_FIXEDFILEINFO signature
    fixed = old[fixed_at:fixed_at + 52]
    translation = struct.pack('<HH', 0x409, 0x4b0)       # English (US), Unicode: the string table 040904b0
    table = b''.join(_pad(_node(k, (v + '\0').encode('utf-16le'))) for k, v in strings.items())
    sfi = _node('StringFileInfo', vtype=1, children=_node('040904b0', vtype=1, children=table), vlen=0)
    vfi = _node('VarFileInfo', vtype=1, children=_node('Translation', translation, vtype=0), vlen=0)
    return _node('VS_VERSION_INFO', fixed, vtype=0, children=_pad(sfi) + vfi)


PATCHES = []   # (file offset, bytes): applied to the file at the end


def put_rva(pe, rva, data):
    PATCHES.append((pe.get_offset_from_rva(rva), bytes(data)))


def put_size(entry, size):
    PATCHES.append((entry.get_file_offset() + 4, struct.pack('<I', size)))   # IMAGE_RESOURCE_DATA_ENTRY.Size


def set_version(pe, version):
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id != 16:
            continue
        d = t.directory.entries[0].directory.entries[0].data.struct
        old = pe.get_data(d.OffsetToData, d.Size)
        new = _version_block(old, {
            'CompanyName': 'openDC', 'FileDescription': 'openDC Launcher', 'FileVersion': version,
            'InternalName': 'openDC Launcher.exe', 'LegalCopyright': 'openDC contributors',
            'OriginalFilename': 'openDC Launcher.exe', 'ProductName': 'openDC Launcher', 'ProductVersion': version,
            'SquirrelAwareVersion': '1'})
        if len(new) > d.Size:
            raise SystemExit(f'version block: {len(new)} bytes, slot {d.Size}')
        put_rva(pe, d.OffsetToData, new + bytes(d.Size - len(new)))
        put_size(d, len(new))
        print(f'  name: openDC Launcher {version} ({len(new)} bytes)')


def main(icon, exe, version='0.1.0'):
    src = Image.open(icon).convert('RGBA')
    pe = pefile.PE(exe, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
    icons, group = {}, None
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        for e in t.directory.entries:
            for lang in e.directory.entries:
                if t.id == 3:
                    icons[e.id] = lang.data.struct
                elif t.id == 14 and group is None:
                    group = lang.data.struct
    gdata = bytearray(pe.get_data(group.OffsetToData, group.Size))
    _, _, count = struct.unpack_from('<HHH', gdata, 0)
    for i in range(count):
        off = 6 + i * 14
        w, h, cc, res, planes, bpp, size, icon_id = struct.unpack_from('<BBBBHHIH', gdata, off)
        d = icons[icon_id]
        n = w or 256
        data = png_icon(src.resize((256, 256), Image.LANCZOS), d.Size) if n == 256 else bmp_icon(src, n)
        if len(data) > d.Size:
            raise SystemExit(f'icon {n}x{n}: {len(data)} bytes, slot {d.Size}')
        put_rva(pe, d.OffsetToData, data + bytes(d.Size - len(data)))
        put_size(d, len(data))
        struct.pack_into('<BBBBHHIH', gdata, off, w, h, 0, 0, 1, 32, len(data), icon_id)
        print(f'  icon {n}x{n}: {len(data)} bytes')
    put_rva(pe, group.OffsetToData, bytes(gdata))
    set_version(pe, version)
    pe.close()
    with open(exe, 'r+b') as f:
        for off, data in PATCHES:
            f.seek(off)
            f.write(data)


if __name__ == '__main__':
    main(*sys.argv[1:4])
