"""Put the launcher icon (a 256x256 RGBA PNG) into electron.exe, in place.

No rcedit here (it is a Windows program), so this rewrites the exe's existing icon resources: Electron ships 4 icons
(16, 32, 48 as bitmaps, 256 as PNG). Each new image is written over the old one in the same space (it must not be
bigger) and the resource sizes and the icon group are updated. The .rsrc layout does not change.

usage: python3 seticon.py ICON.png EXE        (needs: pip install pefile pillow)
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


def main(icon, exe):
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
        pe.set_bytes_at_rva(d.OffsetToData, data + bytes(d.Size - len(data)))
        d.Size = len(data)
        struct.pack_into('<BBBBHHIH', gdata, off, w, h, 0, 0, 1, 32, len(data), icon_id)
        print(f'  icon {n}x{n}: {len(data)} bytes')
    pe.set_bytes_at_rva(group.OffsetToData, bytes(gdata))
    out = pe.write()
    pe.close()
    with open(exe, 'wb') as f:
        f.write(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
