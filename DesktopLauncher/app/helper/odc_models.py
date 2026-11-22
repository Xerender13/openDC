"""openDC Launcher: the game's own 3D files for the Garage window.

Cars: Data/vehicles.agt has vehicle\\player\\<model>_01.nif (the body), <model>_dm.nif (dummy nodes: where the wheels,
plates and spoilers go), <model>_s.nif (a plain copy of the body the game casts the shadow with), vehicle\\player\\wheel\\<tire>.nif and vehicle\\texture\\*.dds (each NIF names its textures as
.bmp / .tga / .dds, the pack keeps them as .dds). Newer cars also have <model>_map.dds + <model>_mask.dds: the body's
second UV set reads the map, the mask's red / blue say where the paint and the glass colour go.
The garage: Data/World/garage.agt garage\\garage.nif (its textures are inside the NIF).
Music: Data/audio/bgm/DriftCity_garage.mp3, select sound Data/audio/sfx/SID_GARAGE_SELECT.wav, the
sell sound (Mito in) Data/audio/sfx/SID_ITEM_SELL.wav.

Files are copied out once into runtime/models (by name); the window reads them.

request: {"client": dir, "out": dir, "cars": [{"model": "pc_0071s", "tire": "tire_ply0000"}]}
-> {"files": {name: path}, "cars": {model: {"body", "dm", "tire", "map", "mask"}}, "garage": path, "music", "select"}
"""
import json
import mmap
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odc_icons import pack_entries, read_entry

TEX_RE = re.compile(rb'([\w\-\. ]+)\.(?:dds|bmp|tga)', re.I)


class Pack:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.d = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        self.by = {}
        for e in pack_entries(self.d):
            self.by.setdefault(os.path.basename(e[0].replace('\\', '/')).lower(), e)

    def get(self, base):
        e = self.by.get(base.lower())
        return read_entry(self.d, e[1], e[2]) if e else None


ALIAS = {'pc_0076s': 'pc_0055s', 'pc_0080s': 'pc_0063s'}


def safe(n):
    return re.sub(r'[^\w\-\.]', '_', n.lower())


def main(req):
    client, out = req['client'], req['out']
    os.makedirs(out, exist_ok=True)
    data = os.path.join(client, 'Data')
    files = {}
    pack = None

    def want(base):
        """copy a pack entry out (once) -> path, or None."""
        nonlocal pack
        base = base.lower()
        if base in files:
            return files[base]
        p = os.path.join(out, safe(base))
        if not os.path.exists(p):
            if pack is None:
                pack = Pack(os.path.join(data, 'vehicles.agt'))
            b = pack.get(base)
            if b is None:
                files[base] = None
                return None
            with open(p + '.tmp', 'wb') as f:
                f.write(b)
            os.replace(p + '.tmp', p)
        files[base] = p
        return p

    def nif(base):
        p = want(base)
        if p and base.endswith('.nif'):
            for m in set(TEX_RE.findall(open(p, 'rb').read())):
                n = m.decode('latin-1').strip().lower()
                want(n + '.dds')
        return p

    # the decals (Data/decal.agt): decal.nxt says, for each car type and decal number, where each piece goes (area: 0 roof,
    # 1 left side, 2 right side, 3 front, 4 rear; size in % and centre on a 1000 x 1000 view of that area, turn,
    # mirror, colour); the pieces' pictures are <name>_side / _roof.dds, a car's own decal (<car>_only0N) its
    # <model>_decal0N.dds
    dpack, dtable = None, None

    def decal_table():
        nonlocal dpack, dtable
        if dtable is not None:
            return dtable
        dtable = {}
        try:
            dpack = Pack(os.path.join(data, 'decal.agt'))
            raw = (dpack.get('decal.nxt') or b'').decode('latin-1')
        except OSError:
            return dtable
        key = None
        for line in raw.replace('\r', '').split('\n'):
            f = line.split('\t')
            if len(f) < 12:
                continue
            if f[0].strip():
                if not (f[0].strip().isdigit() and f[1].strip().isdigit()):
                    key = None
                    continue
                key = (int(f[0]), int(f[1]))
                dtable[key] = {'name': f[2].strip(), 'pieces': []}
            if key is None:
                continue
            try:
                fx, fy = (int(x) for x in f[7].split(':'))
                w, h = (float(x) for x in f[8].split(':'))
                x, y = (float(x) for x in f[10].split(':'))
                rgb = [int(v) for v in f[11].split(':')] if f[11].count(':') == 2 else [255, 255, 255]
                dtable[key]['pieces'].append({'part': f[4].strip().lower(), 'area': int(f[5]), 'flip': [fx, fy], 'w': w, 'h': h,
                                              'rot': float(f[9] or 0), 'x': x, 'y': y, 'rgb': rgb})
            except (ValueError, IndexError):
                continue
        return dtable

    def want_decal(base):
        base = base.lower()
        if base in files:
            return files[base]
        p = os.path.join(out, safe(base))
        if not os.path.exists(p):
            b = dpack.get(base) if dpack else None
            if b is None:
                return None
            with open(p + '.tmp', 'wb') as fh:
                fh.write(b)
            os.replace(p + '.tmp', p)
        files[base] = p
        return p

    def decal(ctype, num, model):
        d = decal_table().get((ctype, num))
        if not d:
            return None
        name = d['name'].lower()
        pieces = []
        for pc in d['pieces']:
            m = re.search(r'_only0?(\d+)$', name)
            if m:
                cand = [f'{model}_decal{int(m.group(1)):02d}']
            else:
                cand = [name + ('_side' if pc['area'] in (1, 2) else '_roof'), name + '_side', name + '_roof', name]
            tex = next((c for c in cand if want_decal(c + '.dds')), None)
            if tex:
                pieces.append(dict(pc, tex=tex))
        return {'name': d['name'], 'pieces': pieces} if pieces else None

    cars = {}
    for c in req.get('cars', []):
        m = (c.get('model') or '').lower()
        if not m or m in cars:
            continue
        m = m.strip()
        # the older cars (pc_0001c ...) keep their body as <model>.nif; some maps drop the model's last s (pc_0144_map)
        key = m
        body = nif(m + '_01.nif') or nif(m + '.nif')
        # the patrol cars have no files of their own in the client: they are drawn as the car they were made from
        if not body and m in ALIAS:
            m = ALIAS[m]
            body = nif(m + '_01.nif') or nif(m + '.nif')
        short = m[:-1] if m.endswith('s') else m
        # the map / mask the body names (an ST / BT car uses its base car's: pc_0192s -> pc_0191s_map.dds)
        named = {x.decode('latin-1').strip().lower() for x in TEX_RE.findall(open(body, 'rb').read())} if body else set()
        nmap = next((x for x in named if x.endswith('_map')), None)
        nmask = next((x for x in named if x.endswith('_mask')), None)
        cars[key] = {'body': body, 'dm': nif(m + '_dm.nif'), 'shadow': want(m + '_s.nif'),
                   'light': nif(m + '_light.nif'), 'spoiler': nif(m + '_sp01.nif'),
                   'tire': nif((c.get('tire') or 'tire_ply0000').lower() + '.nif') or nif('tire_ply0000.nif'),
                   'map': (want(nmap + '.dds') if nmap else None) or want(m + '_map.dds') or want(short + '_map.dds'),
                   'mask': (want(nmask + '.dds') if nmask else None) or want(m + '_mask.dds') or want(short + '_mask.dds'),
                   'decal': want(m + '_decal01.dds'),
                   'neon': nif('neon_' + m + '.nif')}
        # the drift shop's looks: other bodies (aero sets), wings, roof items, air ducts, tires, classic bumpers ... by file name
        cars[key]['parts'] = {}
        cars[key]['decals'] = {}
        for part in c.get('parts') or []:
            part = str(part).lower()
            if part.startswith('decal:'):
                try:
                    num = int(part[6:])
                    d = decal(int(c.get('type') or 0), num, m)
                except (ValueError, OSError):
                    d = None
                if d:
                    cars[key]['decals'][str(num)] = d
                continue
            if re.fullmatch(r'[\w\-. +]+', part):
                cars[key]['parts'][part] = nif(part if part.endswith('.nif') else part + '.nif')

    garage = None
    if req.get('garage'):
        g = os.path.join(out, 'garage.nif')
        if not os.path.exists(g):
            gp = os.path.join(data, 'World', 'garage.agt')
            if os.path.exists(gp):
                b = Pack(gp).get('garage.nif')
                if b:
                    open(g + '.tmp', 'wb').write(b)
                    os.replace(g + '.tmp', g)
        garage = g if os.path.exists(g) else None

    def audio(*p):
        f = os.path.join(data, 'audio', *p)
        return f if os.path.exists(f) else None

    # the car colours: Data/effects.agt effects\VehicleColor.nxt, "ColorID<TAB>Name<TAB>R:G:B" per line
    palette = {}
    try:
        b = Pack(os.path.join(data, 'effects.agt')).get('vehiclecolor.nxt')
        for line in (b or b'').decode('latin-1').splitlines()[1:]:
            f = line.split('\t')
            if len(f) >= 3 and f[0].strip().isdigit() and f[2].count(':') == 2:
                palette[int(f[0])] = [max(0, min(255, int(x))) for x in f[2].strip().split(':')]
    except (OSError, ValueError):
        pass

    # the number plates' pictures (i_num01..07): the 3D views write the plate's text on them
    if cars:
        for n in range(1, 8):
            want('i_num%02d.dds' % n)
    tex = {k[:-4]: v for k, v in files.items() if v and k.endswith('.dds')}
    bgm = re.sub(r'[^A-Za-z0-9_]', '', str(req.get('bgm') or 'garage'))
    return {'ok': True, 'cars': cars, 'textures': tex, 'garage': garage, 'palette': palette,
            'music': audio('bgm', 'DriftCity_' + bgm + '.mp3'), 'select': audio('sfx', 'SID_GARAGE_SELECT.wav'),
            'sell': audio('sfx', 'SID_ITEM_SELL.wav')}


if __name__ == '__main__':
    try:
        r = main(json.loads(sys.stdin.buffer.read().decode("utf-8", "replace")))
    except Exception as e:      # noqa: BLE001 - the launcher shows the message
        r = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    sys.stdout.write(json.dumps(r))
