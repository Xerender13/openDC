"""openDC Launcher mods: game-table changes applied to the client AND the server together.

python odc_mods.py <json request on stdin>  ->  json answer on stdout

Request: {"cmd": "rice_shop", "client": <client folder>, "server_init": <Emulator/server_data_2016/Init>,
          "refs": <folder with carros_*.ref>, "test": false}

rice_shop: the car list of Enhanced Rice (SonicTheUltraHub/Drift-city-Enhanced-Rice, Cliente/ferramentas/
adaptar_carros.py, the same algorithm) on the openDC cars that both have:
  - VehicleList (the car rows: Unique Id, Sellable, Req Cond...): V (Lvl), required level, condition (Req Cond: the
    reference has every car N/A = buyable; only the level and the coupon lock a car), points, Sellable, GradeType,
    and the shop position;
  - VehicleUpgrade (one row per car and V): points, price, sell price, upgrade Mito, required level...;
  - VehicleDisplay (the dealership list): Rice's order (V1..V9, then ST / BT / CT / MINI / Xmas); cars only openDC has
    keep their values and go at the end of their V;
  - Coupon (Coupon Book): the same car + coupon row as Rice's.
A car with no model in the client's packs never enters the shop. The client tables (Data\\Init.agt, or
Data_US\\Init_us.agt when that has them) and the server's copies get the same change, so the shop shows what the
server charges. The launcher keeps the backups (it restores them to turn the mod off).
"""
import json
import os
import re
import struct
import sys
import zlib

# NayaPack (.agt) XOR key (90 bytes, from file offset 20)
KEY = bytes.fromhex('343d30e8673636323e33343b1115161614131d181103060c040306082e5526232a232e28212126272e002d2dcfa50602'
                    '040f0718e115361860131a191115161012131738f12501050602040307080105060f0403070c31857639')


def xor(buf, start):
    return bytes(b ^ KEY[(start + i - 20) % 90] for i, b in enumerate(buf))


def parse(d):
    count = struct.unpack_from('<I', d, 16)[0]
    p = 44
    ents = []
    for _ in range(count):
        n = struct.unpack('<I', xor(d[p:p + 4], p))[0]
        name = xor(d[p + 4:p + 4 + n], p + 4).decode('latin-1')
        off, nch, usize = struct.unpack('<III', xor(d[p + 4 + n:p + 16 + n], p + 4 + n))
        if off + 2 * nch > len(d) or not name.isprintable():
            break
        ents.append(dict(name=name, off=off, nch=nch, usize=usize, dirpos=p))
        p += 16 + n
    return ents


def read_entry(d, e):
    tab = struct.unpack('<%dH' % e['nch'], xor(d[e['off']:e['off'] + 2 * e['nch']], e['off']))
    p = e['off'] + 2 * e['nch']
    out = bytearray()
    for n in tab:
        out += zlib.decompress(xor(d[p:p + n], p))
        p += n
    return bytes(out)


class Pack:
    def __init__(self, path):
        self.path = path
        self.d = bytearray(open(path, 'rb').read())
        self.ents = parse(bytes(self.d)) if self.d[:8] == b'NayaPack' else []
        self.changed = False

    def find(self, test):
        for i, e in enumerate(self.ents):
            if e['usize'] < 200 or e['usize'] > 8000000:
                continue
            try:
                t = read_entry(bytes(self.d), e).decode('utf-16')
            except Exception:
                continue
            if test(t):
                return i, t
        return None, None

    def store(self, i, text):
        e = self.ents[i]
        new = text.encode('utf-16')
        chunks = [zlib.compress(new[k:k + 16384], 9) for k in range(0, len(new), 16384)]
        tab = struct.pack('<%dH' % len(chunks), *[len(c) for c in chunks])
        size = len(tab) + sum(map(len, chunks))
        nxt = min([x['off'] for x in self.ents if x['off'] > e['off']] + [len(self.d)])
        off = e['off'] if size <= nxt - e['off'] else len(self.d)   # doesn't fit: goes to the end of the pack
        if off == len(self.d):
            self.d.extend(b'\0' * size)
        pos = off
        for part in [tab] + chunks:
            self.d[pos:pos + len(part)] = xor(part, pos)
            pos += len(part)
        p = e['dirpos'] + 4 + len(e['name'])
        self.d[p:p + 12] = xor(struct.pack('<III', off, len(chunks), len(new)), p)
        e['off'], e['nch'], e['usize'] = off, len(chunks), len(new)
        self.changed = True

    def save(self):
        tmp = self.path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(bytes(self.d))
        os.replace(tmp, self.path)


def pack_names(path):
    """only the pack's directory (names), without reading the data."""
    with open(path, 'rb') as f:
        d = f.read(16 * 1024 * 1024)
    if d[:8] != b'NayaPack':
        return []
    count = struct.unpack_from('<I', d, 16)[0]
    p = 44
    out = []
    for _ in range(count):
        if p + 4 > len(d):
            break
        n = struct.unpack('<I', xor(d[p:p + 4], p))[0]
        if n <= 0 or n > 512 or p + 16 + n > len(d):
            break
        out.append(xor(d[p + 4:p + 4 + n], p + 4).decode('latin-1'))
        p += 16 + n
    return out


def models(client):
    found = set()
    for sub in ('Data', 'Data_US', 'Patch'):
        folder = os.path.join(client, sub)
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            full = os.path.join(folder, fn)
            if not os.path.isfile(full) or os.path.getsize(full) < 64:
                continue
            for n in pack_names(full):
                m = re.search(r'(?:^|\\)vehicle\\player\\(pc_[0-9]+[a-z]*)[_.]', n, re.I)
                if m:
                    found.add(m.group(1).lower())
    return found


# ---- the tables (the same names as in Enhanced Rice: vd = car rows, vl = per-V rows, cg = dealership list)
VD_COPY = ['Lvl', 'Req Level', 'Req Cond', 'MakeType', 'closestage', 'Accel', 'Speed', 'Crash', 'Boost', 'Sellable',
           'GradeType', 'Display']
VL_COPY = ['Coupon', 'Accel', 'Speed', 'Crash', 'Boost', 'Price', 'Sell', 'CloseSell', 'UpgradeMito', 'Efficiency',
           'Capacity', 'Req Level', 'Sum', 'GradeType']


def is_vd(t): return '\tUnique Id\tSellable\t' in t and 'PlayerCar' in t
def is_vl(t): return 'Game UI name' in t and '\tUpgradeMito\t' in t
def is_cg(t): return '\tUnique Id\tNew\tHot\tGM\tCategory' in t
def is_cp(t): return 'CouponStampDisaply' in t and '\ti_n_c' in t


TESTS = {'vd': is_vd, 'vl': is_vl, 'cg': is_cg, 'cp': is_cp}


def special(n):
    n = n.strip().upper()
    return any(n.endswith(x) for x in (' ST', ' BT', ' XMAS', ' MINI', ' CT'))


def cp_key(c):
    return (c[6].strip(), c[7].strip()) if len(c) > 8 and c[7].strip().startswith('i_n_c') else None


class Table:
    def __init__(self, text, kind):
        self.lines = text.split('\r\n')
        test = (lambda l: l.startswith('Index\t') and '\tUnique Id\t' in l) if kind != 'vl' else (lambda l: l.startswith('Idx\t'))
        self.hdr = [i for i, l in enumerate(self.lines[:8]) if test(l)][0]
        self.col = {}
        for i, x in enumerate(self.lines[self.hdr].split('\t')):
            self.col.setdefault(x.strip(), i)

    def rows(self):
        for i in range(self.hdr + 1, len(self.lines)):
            c = self.lines[i].split('\t')
            if len(c) > 2:
                yield i, c

    def text(self):
        return '\r\n'.join(self.lines)


# Enhanced Rice's price range at V9 for each kind of special car (V7 / V8 / V6 cars: scaled by the V's share)
SPECIAL_RANGE = {'ST': (33750000, 57500000, 1), 'BT': (10000000, 33750000, 1), 'MINI': (60000000, 81250000, 80),
                 'CT': (12500000, 17500000, 80), 'XMAS': (81250000, 105000000, 1)}
SPECIAL_SHARE = {9: 1.0, 8: 0.85, 7: 0.67, 6: 0.6, 5: 0.5}
NORMAL_V9 = (1500000, 5500000)          # Rice's normal V9 cars: 1.45M (Dominator) to 5.3M (ASTRO); openDC's are rarer


def special_kind(n):
    n = n.strip().upper()
    for k in ('ST', 'BT', 'MINI', 'CT', 'XMAS'):
        if n.endswith(' ' + k):
            return k, n[:-len(k) - 1].strip()
    return None, None


def specials_prices(vd, vl, refdir, ref, model_ok, cv):
    """The special cars that are not in Rice's dealership: price at their V (and Sell = half) from the score of the
    base car in especiais.tsv, between the low and high end of Rice's range for that kind; MINI and CT need level 80
    as in Rice. -> {unique id: order key (score, base name, kind)} for the dealership order."""
    f = os.path.join(refdir, 'carros_opendc.tsv')
    if not os.path.isfile(f):
        return {}
    score = {}
    for l in open(f, encoding='utf-8').read().splitlines():
        c = l.split('\t')
        if l.startswith('#') or len(c) < 2 or not c[1].strip().isdigit():
            continue
        score[c[0].strip().upper()] = int(c[1])
    u = ref['cg'].col['Unique Id']
    rice_shop = {c[u].strip() for i, c in ref['cg'].rows() if len(c) > u}
    rows = {}
    for i, c in vl.rows():
        if len(c) > vl.col['GradeLvl'] and c[vl.col['GradeLvl']].strip().isdigit():
            rows[(c[vl.col['ID']].strip(), int(c[vl.col['GradeLvl']]))] = i
    out = {}
    for cid, i in cv.items():
        if cid in rice_shop or not model_ok(cid):
            continue
        c = vd.lines[i].split('\t')
        kind, base = special_kind(c[vd.col['UI Name']])
        lv = c[vd.col['Lvl']].strip()
        lv = int(lv) if lv.isdigit() else 9
        if not kind:                      # a normal car: only openDC's V9 ones (placeholder 1,000,000) get a price
            base = c[vd.col['UI Name']].strip().upper()
            r = rows.get((cid, lv))
            if base not in score or lv != 9 or r is None:
                continue
            lo, hi = NORMAL_V9
            price = int(round((lo + (score[base] - 1) / 9.0 * (hi - lo)) / 50000.0)) * 50000
            g = vl.lines[r].split('\t')
            g[vl.col['Price']], g[vl.col['Sell']] = str(price), str(price // 2)
            vl.lines[r] = '\t'.join(g)
            c[vd.col['Req Level']] = '80'
            vd.lines[i] = '\t'.join(c)
            continue
        if base not in score:
            continue
        r = rows.get((cid, lv))
        if r is None:
            continue
        lo, hi, req = SPECIAL_RANGE[kind]
        share = SPECIAL_SHARE.get(lv, 0.5)
        price = int(round((lo + (score[base] - 1) / 9.0 * (hi - lo)) * share / 250000.0)) * 250000
        g = vl.lines[r].split('\t')
        g[vl.col['Price']] = str(price)
        g[vl.col['Sell']] = str(price // 2)
        vl.lines[r] = '\t'.join(g)
        if req > 1:
            c[vd.col['Req Level']] = str(req if lv >= 9 else max(10, int(req * share / 10) * 10))
            vd.lines[i] = '\t'.join(c)
        out[cid] = kind
    return out


def transform(texts, refdir, have):
    """texts: {'vd','vl','cg','cp'} -> the same, changed by Enhanced Rice's reference. -> (texts, summary)."""
    ref = {k: Table(open(os.path.join(refdir, 'carros_%s.ref' % n), encoding='utf-8', newline='').read(), k)
           for k, n in (('vd', 'VehicleDisplay'), ('vl', 'VehicleList'), ('cg', 'Loja'))}
    vd, vl, cg = Table(texts['vd'], 'vd'), Table(texts['vl'], 'vl'), Table(texts['cg'], 'cg')
    # coupons (Coupon Book): openDC's stays (rev 7, the user: the dealership follows openDC's coupon book); the coupon
    # cars get the V the book gives them (below)
    ncp = 0
    cp_lines = texts['cp'].split('\r\n') if texts.get('cp') else None
    coupon_v = {}
    for l in cp_lines or []:
        c = l.split('\t')
        if cp_key(c) and c[6].strip().isdigit() and c[8].strip().isdigit():
            coupon_v.setdefault(c[6].strip(), int(c[8]))

    rv = {}
    for i, c in ref['vd'].rows():
        if len(c) > ref['vd'].col['Display'] and c[ref['vd'].col['Desc']] == 'PlayerCar':
            rv.setdefault(c[ref['vd'].col['Unique Id']], c)
    cv = {}
    for i, c in vd.rows():
        if len(c) > vd.col['Display'] and c[vd.col['Desc']] == 'PlayerCar':
            cv.setdefault(c[vd.col['Unique Id']], i)

    def crow(u): return vd.lines[cv[u]].split('\t')

    def model_ok(u):
        f = crow(u)[vd.col['File Name']].strip().lower()
        base = f[:-4] if f.endswith('.nif') else f
        return not have or not base.startswith('pc_') or base in have

    def sup(u): return crow(u)[vd.col['Support']].strip() == '1'
    def rsup(u): return u in rv and rv[u][ref['vd'].col['Support']].strip() == '1'
    def available(u): return u in cv and model_ok(u) and (sup(u) or (u in rv and not rsup(u)))

    # Req Cond: the client draws a car scaled from its base car for SMALL / GOTCHA_SMALL (the MINI and small ST cars);
    # GOTCHA / LOTTO / EVENT... are the gotcha restriction, taken off (rev 7)
    small = {u: 'SMALL' in vd.lines[i].split('\t')[vd.col['Req Cond']].upper() for u, i in cv.items()}
    nvd = 0
    for u, i in cv.items():
        if u not in rv or not model_ok(u):   # a car without a model stays as it is (e.g. the hidden Zorro)
            continue
        c = vd.lines[i].split('\t')
        r = rv[u]
        old = list(c)
        for name in VD_COPY:
            if name in vd.col and name in ref['vd'].col:
                c[vd.col[name]] = r[ref['vd'].col[name]]
        # Support stays openDC's: a car openDC has at 0 (PT Cruiser, Solo, Seven, CR2, Deluxe...) has a model the 2016
        # client can't draw (only the wheels show) (rev 5)
        if c != old:
            vd.lines[i] = '\t'.join(c)
            nvd += 1

    for u, i in cv.items():
        c = vd.lines[i].split('\t')
        rc = 'SMALL' if small[u] else 'N/A'
        if c[vd.col['Req Cond']] != rc:
            c[vd.col['Req Cond']] = rc
            vd.lines[i] = '\t'.join(c)

    def vkey(t, c):
        g = c[t.col['GradeLvl']].strip() if len(c) > t.col['GradeLvl'] else ''
        return (c[t.col['ID']].strip(), g)
    rl = {}
    for i, c in ref['vl'].rows():
        if len(c) > ref['vl'].col['GradeLvl']:
            rl.setdefault(vkey(ref['vl'], c), c)
    nvl = 0
    for i, c in vl.rows():
        if len(c) <= vl.col['GradeLvl']:
            continue
        r = rl.get(vkey(vl, c))
        if r is None:
            continue
        old = list(c)
        for name in VL_COPY:
            if name in vl.col and name in ref['vl'].col and ref['vl'].col[name] < len(r):
                c[vl.col[name]] = r[ref['vl'].col[name]]
        if c != old:
            vl.lines[i] = '\t'.join(c)
            nvl += 1

    # ---- coupon cars at the coupon book's V, with that V's level (rev 7)
    req_at = {}
    for i, c in vl.rows():
        if len(c) > max(vl.col['GradeLvl'], vl.col['Req Level']) and c[vl.col['GradeLvl']].strip().isdigit():
            req_at[(c[vl.col['ID']].strip(), int(c[vl.col['GradeLvl']]))] = c[vl.col['Req Level']].strip()
    # Rice's level by V, and the middle price of Rice's normal cars at each V (for a coupon car Rice puts at another V)
    REQ_BY_V = {1: 1, 2: 10, 3: 20, 4: 30, 5: 40, 6: 50, 7: 60, 8: 75, 9: 80}
    rrow = {}
    for i, c in ref['vl'].rows():
        if len(c) > ref['vl'].col['GradeLvl'] and c[ref['vl'].col['GradeLvl']].strip().isdigit():
            rrow[(c[ref['vl'].col['ID']].strip(), int(c[ref['vl'].col['GradeLvl']]))] = c
    by_v = {}
    for u, r in rv.items():
        lv = r[ref['vd'].col['Lvl']].strip()
        if lv.isdigit() and not special(r[ref['vd'].col['UI Name']]) and (u, int(lv)) in rrow:
            x = rrow[(u, int(lv))][ref['vl'].col['Price']].strip()
            if x.isdigit():
                by_v.setdefault(int(lv), []).append(int(x))
    mid = {v: sorted(p)[len(p) // 2] for v, p in by_v.items() if p}
    vrows = {}
    for i, c in vl.rows():
        if len(c) > vl.col['GradeLvl'] and c[vl.col['GradeLvl']].strip().isdigit():
            vrows[(c[vl.col['ID']].strip(), int(c[vl.col['GradeLvl']]))] = i
    for u, g in coupon_v.items():
        if u not in cv:
            continue
        c = vd.lines[cv[u]].split('\t')
        old = list(c)
        rice_v = rv[u][ref['vd'].col['Lvl']].strip() if u in rv else ''
        c[vd.col['Lvl']] = str(g)
        c[vd.col['Req Level']] = str(REQ_BY_V.get(g, 1))
        if c != old:
            vd.lines[cv[u]] = '\t'.join(c)
        if rice_v != str(g) and (u, g) in vrows and g in mid:     # Rice has it at another V: a price of that V
            r = vl.lines[vrows[(u, g)]].split('\t')
            r[vl.col['Price']], r[vl.col['Sell']] = str(mid[g]), str(mid[g] // 2)
            r[vl.col['Req Level']] = str(REQ_BY_V.get(g, 1))
            vl.lines[vrows[(u, g)]] = '\t'.join(r)

    # ---- special cars only openDC has (ST / BT / MINI / CT / XMAS): placed and priced like Rice's (especiais.tsv)
    spe = specials_prices(vd, vl, refdir, ref, model_ok, cv)

    # ---- the dealership list
    def shop_ids(t):
        u = t.col['Unique Id']
        return [c[u].strip() for i, c in t.rows() if len(c) > u and c[u].strip().isdigit()]

    def rdisp(u): return int(rv[u][ref['vd'].col['Display']])
    ref_order = sorted([u for u in shop_ids(ref['cg']) if u in rv], key=rdisp)
    pos = {u: k for k, u in enumerate(ref_order)}

    def lvl(u): return int(crow(u)[vd.col['Lvl']]) if crow(u)[vd.col['Lvl']].strip().isdigit() else 9

    def group(u):
        if u in rv:
            return 10 if special(rv[u][ref['vd'].col['UI Name']]) else int(rv[u][ref['vd'].col['Lvl']])
        return 10 if special(crow(u)[vd.col['UI Name']]) else lvl(u)
    mine = [u for u in shop_ids(cg) if u not in pos and u in cv and sup(u) and model_ok(u)]

    def cdisp(u):
        x = crow(u)[vd.col['Display']].strip()
        return int(x) if x.lstrip('-').isdigit() else 0
    # the order (rev 6): normal cars by V, then price; then the special cars, Rice's and openDC's together, by kind
    # as in Rice (CT, BT, ST, MINI, XMAS), then V, then price
    vrow = {}
    for i, c in vl.rows():
        if len(c) > max(vl.col['GradeLvl'], vl.col['Price']) and c[vl.col['GradeLvl']].strip().isdigit():
            vrow[(c[vl.col['ID']].strip(), int(c[vl.col['GradeLvl']]))] = c

    def price(u):
        g = vrow.get((u, lvl(u)))
        x = g[vl.col['Price']].strip() if g else ''
        return int(x) if x.isdigit() else 0

    def okey(u):
        name = crow(u)[vd.col['UI Name']].strip().upper()
        kind, base = special_kind(name)
        if kind:
            return (1, ['CT', 'BT', 'ST', 'MINI', 'XMAS'].index(kind), lvl(u), price(u), base)
        return (0, lvl(u), price(u), name)
    final = sorted([u for u in ref_order if available(u)] + mine, key=okey)
    seen = set()
    final = [u for u in final if not (u in seen or seen.add(u))]
    # every other openDC car with a model (not in the dealership before) goes in too, in its V tab, so every car can
    # be looked at and placed (rev 3)
    extra = sorted([u for u in cv if u not in seen and model_ok(u) and sup(u)], key=okey)
    if extra:
        final = sorted(final + extra, key=okey)
        mine = mine + extra
    # the cars openDC hides (Support 0) are not listed; all the others are sold (Sellable 0 -> 1; the starters'
    # categories stay)
    final = [u for u in final if sup(u) and not (u in rv and rdisp(u) < 0)]   # Rice's Display -1: not shown (Birdie RTI V9)
    nopen = 0
    for u in final:
        c = crow(u)
        old = list(c)
        if c[vd.col['Sellable']].strip() in ('', '0'):
            c[vd.col['Sellable']] = '1'
        if c != old:
            vd.lines[cv[u]] = '\t'.join(c)
            nopen += 1
    rrow, crow_cg = {}, {}
    for i, c in ref['cg'].rows():
        if len(c) > ref['cg'].col['Unique Id']:
            rrow.setdefault(c[ref['cg'].col['Unique Id']].strip(), c)
    for i, c in cg.rows():
        if len(c) > cg.col['Unique Id']:
            crow_cg.setdefault(c[cg.col['Unique Id']].strip(), c)
    same = ref['cg'].lines[ref['cg'].hdr] == cg.lines[cg.hdr]
    ndisp = 0
    if not mine:
        keep = set(final)
        order = [u for u in (c[ref['cg'].col['Unique Id']].strip() for i, c in ref['cg'].rows()
                             if len(c) > ref['cg'].col['Unique Id']) if u in keep]
        order = [u for k, u in enumerate(order) if u not in order[:k]]
        renum = len(order) != len(rrow)
    else:
        order = final
        renum = True
        for k, u in enumerate(final):
            c = crow(u)
            if c[vd.col['Display']] != str(k + 1):
                c[vd.col['Display']] = str(k + 1)
                vd.lines[cv[u]] = '\t'.join(c)
                ndisp += 1
    body = []
    for k, u in enumerate(order):
        c = list(rrow[u]) if (same and u in rrow) else list(crow_cg.get(u) or [])
        if not c:
            c = [''] * len(cg.lines[cg.hdr].split('\t'))
            r = crow(u)
            c[cg.col['Car Name']] = r[vd.col['Car Name']]
            c[cg.col['UI Name']] = r[vd.col['UI Name']]
            c[cg.col['Unique Id']] = u
            for n in ('New', 'Hot', 'GM'):
                c[cg.col[n]] = '0'
            c[cg.col['Category']] = '7'
        if renum or not same:
            c[0] = str(k)
        body.append('\t'.join(c))
    head = cg.lines[:cg.hdr + 1]
    for j, l in enumerate(head):
        if l.startswith('Value\t'):
            c = l.split('\t')
            c[1] = str(len(order))
            head[j] = '\t'.join(c)
    tail = [l for l in cg.lines[cg.hdr + 1:] if not l.split('\t')[0].strip().isdigit()]
    cg.lines = head + body + (tail if tail else [''])

    out = {'vd': vd.text(), 'vl': vl.text(), 'cg': cg.text()}
    if cp_lines is not None:
        out['cp'] = '\r\n'.join(cp_lines)
    summary = dict(shop=len(order), from_rice=len(order) - len(mine), only_opendc=len(mine),
                   cars=nvd, grades=nvl, positions=ndisp, coupons=ncp, added=len(extra), opened=nopen, specials=len(spe))
    return out, summary


def class_start(texts):
    """Server only: a dealership car is bought at its V tab (VehicleList Lvl), as the dealership shows it (V, stats and
    price of that V). The openDC server (native/game/cars.py start_grade) starts a car at its first VehicleUpgrade row
    with Capacity and stats, so the rows below the V tab get Capacity 0: e.g. Dragoon, V9 in the dealership, was bought
    as V1 for the V1 price. A car never goes down a V, so those rows are not used. -> (texts, cars changed)."""
    vd, vl, cg = Table(texts['vd'], 'vd'), Table(texts['vl'], 'vl'), Table(texts['cg'], 'cg')
    u = cg.col['Unique Id']
    shop = {c[u].strip() for i, c in cg.rows() if len(c) > u and c[u].strip().isdigit()}
    cls = {}
    for i, c in vd.rows():
        if len(c) <= vd.col['Lvl'] or c[vd.col['Desc']] != 'PlayerCar':
            continue
        cid, lv, sell = c[vd.col['Unique Id']].strip(), c[vd.col['Lvl']].strip(), c[vd.col['Sellable']].strip()
        if cid in shop and lv.isdigit() and int(lv) > 1 and sell not in ('', '0'):
            cls.setdefault(cid, int(lv))
    cap, gl, idc = vl.col['Capacity'], vl.col['GradeLvl'], vl.col['ID']
    rows = {}
    for i, c in vl.rows():
        if len(c) > max(cap, gl) and c[idc].strip() in cls and c[gl].strip().isdigit():
            rows.setdefault(c[idc].strip(), {})[int(c[gl].strip())] = i
    cars = 0
    for cid, lv in cls.items():
        r = rows.get(cid, {})
        top = r.get(lv)
        if top is None or vl.lines[top].split('\t')[cap].strip() in ('', '0'):
            continue                     # no real row at its V: left as it is
        hit = False
        for g, i in r.items():
            if g < lv:
                c = vl.lines[i].split('\t')
                if c[cap].strip() not in ('', '0'):
                    c[cap] = '0'
                    vl.lines[i] = '\t'.join(c)
                    hit = True
        cars += hit
    out = dict(texts)
    out['vl'] = vl.text()
    return out, cars


def read_server_tables(init_dir):
    """the server's copies: Init/*.xlt (UTF-16), found by their content like the client's."""
    found = {}
    for fn in sorted(os.listdir(init_dir)):
        if not fn.lower().endswith('.xlt'):
            continue
        p = os.path.join(init_dir, fn)
        raw = open(p, 'rb').read()
        if raw[:2] not in (b'\xff\xfe', b'\xfe\xff'):
            continue
        t = raw.decode('utf-16')
        for k, test in TESTS.items():
            if k not in found and test(t):
                found[k] = (p, t)
    return found


def rice_shop(req):
    client, init_dir, refdir = req['client'], req['server_init'], req['refs']
    have = models(client)
    if not have:
        return {'ok': False, 'error': 'no_models'}
    packs = [Pack(p) for p in (os.path.join(client, 'Data_US', 'Init_us.agt'), os.path.join(client, 'Data', 'Init.agt'))
             if os.path.isfile(p)]
    where = {}
    for k, test in TESTS.items():
        for pk in packs:
            i, t = pk.find(test)
            if i is not None:
                where[k] = (pk, i, t)
                break
    if any(k not in where for k in ('vd', 'vl', 'cg')):
        return {'ok': False, 'error': 'no_tables'}
    new, summary = transform({k: v[2] for k, v in where.items()}, refdir, have)
    server = read_server_tables(init_dir) if init_dir and os.path.isdir(init_dir) else {}
    if any(k not in server for k in ('vd', 'vl', 'cg')):
        return {'ok': False, 'error': 'no_server_tables'}
    snew, ssum = transform({k: v[1] for k, v in server.items()}, refdir, have)
    snew, ssum['class_start'] = class_start(snew)
    files = []
    if not req.get('test'):
        for k, (pk, i, t) in where.items():
            if k in new and new[k] != t:
                pk.store(i, new[k])
        for pk in packs:
            if pk.changed:
                pk.save()
                files.append(pk.path)
        for k, (p, t) in server.items():
            if k in snew and snew[k] != t:
                tmp = p + '.tmp'
                with open(tmp, 'wb') as f:
                    f.write(snew[k].encode('utf-16'))
                os.replace(tmp, p)
                files.append(p)
    return {'ok': True, 'client': summary, 'server': ssum, 'models': len(have), 'written': files}


def backup_targets(req):
    """the files rice_shop may change (the launcher copies them before, and back to turn the mod off)."""
    out = [p for p in (os.path.join(req['client'], 'Data_US', 'Init_us.agt'), os.path.join(req['client'], 'Data', 'Init.agt'))
           if os.path.isfile(p)]
    if req.get('server_init') and os.path.isdir(req['server_init']):
        out += [p for p, _ in read_server_tables(req['server_init']).values()]
    return {'ok': True, 'files': out}


def main():
    req = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace') or '{}')
    try:
        fn = {'rice_shop': rice_shop, 'targets': backup_targets}[req.get('cmd')]
        out = fn(req)
    except Exception as e:  # noqa: BLE001 - reported to the launcher
        out = {'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}
    sys.stdout.write(json.dumps(out))


if __name__ == '__main__':
    main()
