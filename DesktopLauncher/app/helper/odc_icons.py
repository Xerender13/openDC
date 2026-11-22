"""openDC Launcher: the game's own pictures of items and cars, for the Inventory window.

The client's Data_US/gameui/game.nui names each picture: dialog 290000 the item icons (NM = item id, 64 x 64),
1990000 the car icons (NM = car model, pc_XXXXs, 63 x 63), 2840000 the car name logos (182 x 62). A picture is
I1_1="x,y~x2,y2_<texture>.dds" with UV1_1 (where in it): a small DDS of its own in the containers tex\\0.ntx ..
tex\\F.ntx of Data_US/gameui/uitex.agt (Emulator/tools/ui_texture.py). The pieces asked for are copied out once
into runtime/icons (by name) with index.json; the window decodes the DDS itself.

request: {"client": dir, "out": dir, "names": [...]} -> {"icons": {name: {"file": .., "uv": [u0, v0, u1, v1]}}}
"""
import json
import os
import re
import struct
import zlib

KEY = bytes.fromhex('343d30e8673636323e33343b1115161614131d181103060c040306082e5526232a232e28212126272e002d2dcfa50602'
                    '040f0718e115361860131a191115161012131738f12501050602040307080105060f0403070c31857639')
DIALOGS = {'290000': 'item', '2880000': 'item', '1990000': 'car', '2840000': 'logo', '1980000': 'item', '1950000': 'item'}  # 1980000 / 1950000: the car coupons


def xor(buf, start):
    k = KEY
    n = len(buf)
    ks = bytes(k[(start + i - 20) % 90] for i in range(min(n, 90)))
    ks = (ks * (n // 90 + 1))[:n]
    return (int.from_bytes(buf, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little')


def pack_entries(d):
    """(name, offset, chunks, size) of each entry: from byte 32, i32 offset, chunks, size, name length, then the name
    (Emulator/tools/agt.py index)."""
    count = struct.unpack_from('<I', d, 16)[0]
    p, out = 32, []
    for _ in range(count):
        off, nch, usize, n = struct.unpack('<4i', xor(d[p:p + 16], p))
        if not 0 < n < 1024:
            break
        name = xor(d[p + 16:p + 16 + n], p + 16).decode('latin-1')
        p += 16 + n
        if 32 <= off and off + 2 * nch <= len(d):
            out.append((name, off, nch, usize))
    return out


def read_entry(d, off, nch):
    tab = struct.unpack('<%dH' % nch, xor(d[off:off + 2 * nch], off))
    p, out = off + 2 * nch, bytearray()
    for n in tab:
        out += zlib.decompress(xor(d[p:p + n], p))
        p += n
    return bytes(out)


def index(client, out):
    """name -> (piece, uv) from game.nui, cached by its size and time."""
    nui = os.path.join(client, 'Data_US', 'gameui', 'game.nui')
    st = os.stat(nui)
    stamp = f'{st.st_size}:{int(st.st_mtime)}:v3'
    f = os.path.join(out, 'index.json')
    try:
        j = json.load(open(f, encoding='utf-8'))
        if j.get('stamp') == stamp:
            return j
    except (OSError, ValueError):
        pass
    t = open(nui, 'rb').read().decode('cp949', 'replace')
    names = {}
    for m in re.finditer(r'<DIALOG C="(\d+)"[^>]*>(.*?)</DIALOG>', t, re.S):
        kind = DIALOGS.get(m.group(1))
        for info in re.finditer(r'<INFO [^>]*>', m.group(2)):
            a = dict(re.findall(r'(\w+)="([^"]*)"', info.group(0)))
            if not a.get('NM') or not a.get('I1_1'):
                continue
            # the User Info portraits: "유저정보_omd캐릭터01".."08" and "..._roo캐릭터01".."08" (OMD / ROO side, avatar 1-8)
            face = re.match('^\uc720\uc800\uc815\ubcf4_(omd|roo)\uce90\ub9ad\ud130(\\d+)$', a['NM'])
            if face:
                key = f'face:{face.group(1)}{int(face.group(2))}'
            elif not kind:
                continue
            else:
                key = kind + ':' + a['NM'].lower()
            if key in names:
                continue
            uv = [float(x) for x in a.get('UV1_1', '0 0 1 0 0 1 1 1').split()] or [0, 0, 1, 0, 0, 1, 1, 1]
            names[key] = {'piece': a['I1_1'], 'uv': [uv[0], uv[1], uv[-2], uv[-1]] if len(uv) >= 8 else [0, 0, 1, 1]}
    j = {'stamp': stamp, 'names': names, 'have': []}
    os.makedirs(out, exist_ok=True)
    json.dump(j, open(f, 'w', encoding='utf-8'))
    return j


def safe(piece):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', piece)


def icons(req):
    client, out = req['client'], req['out']
    os.makedirs(out, exist_ok=True)
    j = index(client, out)
    want = {}
    for n in req.get('names', []):
        e = j['names'].get(n.lower())
        if e:
            want[n] = e
    # the first time (or after the client's pictures changed): every piece game.nui names for items and cars is copied
    # out in one pass over the containers (about 3,600 small DDS), so later windows only read files
    missing = set()
    if not j.get('extracted'):
        missing = {e['piece'].lower() for e in j['names'].values()}
    if missing:
        d = open(os.path.join(client, 'Data_US', 'gameui', 'uitex.agt'), 'rb').read()
        for name, off, nch, usize in pack_entries(d):
            if not name.lower().endswith('.ntx') or not missing:
                continue
            try:
                ntx = read_entry(d, off, nch)
            except (struct.error, zlib.error):
                continue
            p = 0
            while p + 72 <= len(ntx):
                pn = ntx[p:p + 64].split(b'\0')[0].decode('latin-1')
                size = struct.unpack_from('<I', ntx, p + 64)[0]
                if pn.lower() in missing:
                    open(os.path.join(out, safe(pn) + '.dds'), 'wb').write(ntx[p + 72:p + 72 + size])
                    missing.discard(pn.lower())
                p += 72 + size
    if not j.get('extracted'):
        j['extracted'] = True
        json.dump(j, open(os.path.join(out, 'index.json'), 'w', encoding='utf-8'))
    res = {}
    for n, e in want.items():
        f = os.path.join(out, safe(e['piece']) + '.dds')
        if os.path.exists(f):
            res[n] = {'file': f, 'uv': e['uv']}
    return {'icons': res}


if __name__ == '__main__':
    import sys
    try:
        r = icons(json.loads(sys.stdin.buffer.read().decode("utf-8", "replace")))
        r['ok'] = True
    except Exception as e:
        r = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    sys.stdout.write(json.dumps(r))
