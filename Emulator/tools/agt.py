"""NayaPack .agt reader/writer (port of amPerl/RiceTools RicePack AGT.cs)."""
import struct, sys, os, zlib
KEY = bytes([0x01,0x05,0x06,0x02,0x04,0x03,0x07,0x08,0x01,0x05,0x06,0x0F,0x04,0x03,0x07,0x0C,
 0x31,0x85,0x76,0x39,0x34,0x3D,0x30,0xE8,0x67,0x36,0x36,0x32,0x3E,0x33,0x34,0x3B,
 0x11,0x15,0x16,0x16,0x14,0x13,0x1D,0x18,0x11,0x03,0x06,0x0C,0x04,0x03,0x06,0x08,
 0x2E,0x55,0x26,0x23,0x2A,0x23,0x2E,0x28,0x21,0x21,0x26,0x27,0x2E,0x00,0x2D,0x2D,
 0xCF,0xA5,0x06,0x02,0x04,0x0F,0x07,0x18,0xE1,0x15,0x36,0x18,0x60,0x13,0x1A,0x19,
 0x11,0x15,0x16,0x10,0x12,0x13,0x17,0x38,0xF1,0x25])

def xor_range(raw, start, end):
    """Decode raw[start:end] (everything after the 32-byte header is XORed with KEY by
    absolute position)."""
    lo = max(start, 32)
    if lo >= end:
        return bytes(raw[start:end])
    k = len(KEY); n = end - lo
    ks = (KEY[lo % k:] + KEY * (n // k + 2))[:n]
    body = (int.from_bytes(raw[lo:end], 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little')
    return bytes(raw[start:lo]) + body

def xor(buf):
    return bytearray(xor_range(buf, 0, len(buf)))

def index(path):
    """Entries of a pack without unpacking them: (raw bytes, [(name, offset, chunks, size)])."""
    raw = open(path, 'rb').read()
    assert raw[:8] == b'NayaPack', 'not a NayaPack file'
    n, = struct.unpack_from('<i', raw, 16)
    end = 32
    entries, pos = [], 32
    for _ in range(n):
        hp, cc, dlen, plen = struct.unpack_from('<4i', xor_range(raw, pos, pos + 16)); pos += 16
        name = xor_range(raw, pos, pos + plen).decode('latin-1'); pos += plen
        entries.append((name, hp, cc, dlen))
    return raw, entries

def extract(raw, entry):
    """Unpack one entry returned by index()."""
    name, hp, cc, dlen = entry
    lens = struct.unpack_from(f'<{cc}H', xor_range(raw, hp, hp + 2 * cc))
    p = hp + 2 * cc
    blob = xor_range(raw, p, p + sum(lens))
    data, q = bytearray(), 0
    for L in lens:
        # chunk = 78 9c + deflate + adler; newer packs (GoonCity) end some files with
        # a 6-byte empty chunk that is not a complete stream, so decompress leniently
        data += zlib.decompressobj().decompress(blob[q:q + L])
        q += L
    return bytes(data[:dlen])

def read(path):
    raw, entries = index(path)
    return raw[:32], [(e[0], extract(raw, e)) for e in entries]

def write(path, header, files, chunk=16384):
    ent = 32 + sum(16 + len(n.encode('latin-1')) for n, _ in files)
    tab, blobs, off = bytearray(), bytearray(), ent
    for n, d in files:
        chunks = [zlib.compress(d[i:i+chunk], 6) for i in range(0, len(d), chunk)] or [zlib.compress(b'')]
        tab += struct.pack('<4i', off, len(chunks), len(d), len(n)) + n.encode('latin-1')
        blk = struct.pack(f'<{len(chunks)}H', *map(len, chunks)) + b''.join(chunks)
        blobs += blk; off += len(blk)
    # same header RicePack writes: magic, 0, 1, 1, count, 12 zero bytes
    hdr = bytearray(b'NayaPack' + struct.pack('<iHHi', 0, 1, 1, len(files)) + bytes(12))
    # a new file swapped in: a running game keeps reading the old one instead of a half-written pack
    tmp = path + '.tmp'
    open(tmp, 'wb').write(bytes(xor(hdr + tab + blobs)))
    os.replace(tmp, path)

if __name__ == '__main__':
    cmd, src = sys.argv[1], sys.argv[2]
    hdr, files = read(src)
    if cmd == 'list':
        for n, d in files: print(len(d), n)
    elif cmd == 'extract':
        dst = sys.argv[3]
        for n, d in files:
            p = os.path.join(dst, *n.split('\\')); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(d)
        print(len(files), 'files ->', dst)
