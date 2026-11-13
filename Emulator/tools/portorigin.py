"""Player cars of the Origin client (the latest Skid Rush build) added to the 2016 client (DriftCity Dev Ed).

User, 2026-11-13: "port all of the Origin client cars to the 2016 client". The Origin client (default
~/Drift City Origin/Client; read only, its packs use agt.ORIGIN_KEY) has 197 player cars whose Unique Id the 2016
VehicleList lacks (89, 352, 443-637). Same Gamebryo 20.0.0.4 models; its tables have the 2016 columns, apart from the
differences handled below. Ids above 449 need the raised car limit (tools/carlimit2016.py, applied by `apply`).

python -m tools.portorigin dry [FOLDER]     build everything, write the tables into FOLDER, change nothing
python -m tools.portorigin apply            write the client packs, the exe patch and server_data_2016
python -m tools.portorigin reset            put the first originals back (client_backup/2016/origin)
       [--origin DIR] [--client DIR] [--sellable keep|gotcha]

What is written (2016 client):
  - Data/vehicles.agt: the cars' models / textures / neon and the tire models they name, with the .dds the models name.
  - Data/Init.agt: VehicleList (rows after the last player car), VehicleUpgrade (9 rows per car), VehicleDisplay,
    TireList, VisualItem (a car column each; the cars' own aero sets as rows), VShopItem (the aero sets' rows).
  - Data/World/data.agt: UseItemClient.tdf with the car keys.
  - Data_US/gameui/game.nui + uitex.agt: the cars' key icons and name images, found by name in the Origin dialogs.
  - Data/audio/engine: idle<uid>.wav / mid<uid>.wav.
  - DriftCity.exe: the car limit (carlimit2016).
Server: server_data_2016/Init/*.xlt and tables/UseItemClient.tdf get the same tables (restart the emulator).

Rules of ours (Origin's economy is not the 2016 one, so these are not copied):
  - VehicleUpgrade Price / Sell / CloseSell / UpgradeMito / Efficiency / Capacity / Req Level of every grade come from
    the newest 2016 car (TEMPLATE_UID, Dominator BT): Origin sells every grade for 1000-900000 with other rules.
  - A car Origin only has at some grades (e.g. V9 only: its lower rows are all 0) gets the missing grades scaled from
    its lowest filled grade by the table's "Sum" column (the stat total of a grade), so it can be driven at any grade.
  - VehicleList "Car Assist" names the 2016 Assist_Client lacks (car_field_mito_huge ...) become "-"; Req Level 1.
  - Sellable stays Origin's 1 (the dealership sells it) unless --sellable gotcha (50 / GOTCHA: only prizes).
"""
import argparse
import collections
import os
import re
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import agt  # noqa: E402
import port2016 as p  # noqa: E402
from port2016 import cells, xlt_lines, xlt_bytes, renumber, set_header, clip  # noqa: E402
from ui_texture import entries  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
ORIGIN = os.path.expanduser(os.path.join('~', 'Drift City Origin', 'Client'))
CLIENT = os.path.join(ROOT, 'DriftCity Dev Ed')
SERVER = os.path.join(HERE, '..', 'server_data_2016')
BACKUPS = os.path.join(HERE, '..', 'client_backup', '2016', 'origin')
TEMPLATE_UID = '442'
TABLES = ('VehicleList', 'VehicleUpgrade', 'VehicleDisplay', 'TireList', 'VisualItem', 'VShopItem')
CAR_DIALOGS = {'2000000': '1990000', '2850000': '2840000', '2860000': '2850000', '2870000': '2860000'}   # Origin -> 2016
BASE_PACKS = [('Data/vehicles.agt', 'data\\'), ('Data/Init.agt', 'data\\'), ('Data/World/data.agt', 'data\\world\\'),
              ('Data/GameUI/uitex.agt', 'data\\gameui\\')]


class Origin:
    """The Origin client's files as it reads them: the base packs, then Patch/patch.000-010 (a later patch wins)."""

    def __init__(self, root):
        self.root, self.raw, self.files = root, {}, {}
        for rel, prefix in BASE_PACKS:
            self._add(os.path.join(root, *rel.split('/')), prefix)
        for i in range(100):
            path = os.path.join(root, 'Patch', 'patch.%03d' % i)
            if os.path.exists(path):
                self._add(path, '')

    def _add(self, path, prefix):
        raw, ents = agt.index(path, agt.ORIGIN_KEY)
        self.raw[path] = raw
        for e in ents:
            self.files[(prefix + e[0]).lower()] = (path, e, prefix + e[0])

    def read(self, name):
        path, e, _ = self.files[name.lower()]
        return agt.extract(self.raw[path], e, agt.ORIGIN_KEY)

    def xlt(self, name):
        return xlt_lines(self.read('data\\init\\%s.xlt' % name))


def backup_path(path):
    rel = os.path.relpath(path, CLIENT).replace(os.sep, '_')
    return os.path.join(BACKUPS, rel + '.orig')


def target(*parts):
    return os.path.join(CLIENT, *parts)


def orig_entry(pack, name):
    """An entry of a 2016 pack as it was before the first run."""
    b = backup_path(pack)
    return p.read_entry(b if os.path.exists(b) else pack, name)


def maxlen(lines, first, col):
    return max((len(cells(l)[col].encode('cp949', 'replace')) for l in lines[first:] if len(cells(l)) > col), default=0)


# ---- tables -----------------------------------------------------------------------------------------------------

def new_cars(vl16, vlo):
    """Origin player cars (Vehicle 0) whose Unique Id the 2016 table lacks: [cells]."""
    have = {cells(l)[9] for l in vl16[4:] if len(cells(l)) > 9}
    return [cells(l) for l in vlo[4:] if len(cells(l)) > 9 and cells(l)[0].strip() and cells(l)[2] == '0'
            and cells(l)[9] not in have]


def port_vehicle_list(vl16, cars, assists, sellable):
    lines = list(vl16)
    last = max(i for i, l in enumerate(lines) if len(cells(l)) > 9 and cells(l)[2] == '0')
    ncols = len(cells(lines[3]))
    limit = {c: max(maxlen(vl16, 4, c), 31) for c in (3, 4, 5, 6, 7, 8)}
    add, dropped = [], collections.Counter()
    for f in cars:
        f = (list(f) + [''] * ncols)[:ncols]
        for c, n in limit.items():
            f[c] = clip(f[c], n)
        if f[4] == 'Moonpalace Motors':
            f[4] = 'MoonPalace Motors'
        f[20] = '1'
        if f[76].strip() not in ('-', '') and not all(a in assists for a in f[76].split()):
            dropped[f[76]] += 1
            f[76] = '-'
        if sellable == 'gotcha':
            f[10], f[21] = '50', 'GOTCHA'
        add.append('\t'.join(f))
    lines[last + 1:last + 1] = add
    n = renumber(lines, 4)
    players = sum(1 for l in lines[4:] if len(cells(l)) > 9 and cells(l)[0].strip() and cells(l)[2] == '0')
    set_header(lines, 1, {1: n, 3: players})
    return lines, dropped


def port_upgrades(vu16, vuo, cars):
    """9 rows per car. -> (lines, {uid: grades that were filled in by our rule})."""
    def blocks(t):
        b = collections.defaultdict(list)
        for l in t[3:]:
            f = cells(l)
            if len(f) > 1 and f[0].strip().isdigit():
                b[f[1]].append(f)
        return b
    b16, bo = blocks(vu16), blocks(vuo)
    tmpl = b16[TEMPLATE_UID]
    ncols = len(cells(vu16[2]))
    lines = list(vu16)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    limit = {c: max(maxlen(vu16, 3, c), 31) for c in (2, 3, 4)}
    add, filled = [], {}
    for car in cars:
        uid, ui = car[9], car[6]
        rows = [list(r) for r in bo.get(uid, [])]
        if len(rows) != 9:
            sys.exit(f'VehicleUpgrade: Origin car {uid} has {len(rows)} rows, not 9')
        ok = [g for g in range(9) if rows[g][6].strip() not in ('', '0')]
        if not ok:
            sys.exit(f'VehicleUpgrade: Origin car {uid} has no stats at any grade')
        src = rows[ok[0]]
        for g in range(9):
            r = rows[g]
            if g not in ok:                           # our rule: scaled by the grade's Sum
                scale = float(r[17]) / float(src[17])
                for c in (6, 7, 8, 9):
                    r[c] = str(max(1, round(int(src[c]) * scale)))
                r[5] = src[5]
                r[4] = f'{ui} {r[18].strip() or "V"}{g + 1}'
                filled.setdefault(uid, []).append(g + 1)
            for c in (10, 11, 12, 13, 14, 15, 16):
                r[c] = tmpl[g][c].strip()
            if g == 0:
                r[2], r[3] = car[5], ui
            for c in (2, 3, 4):
                r[c] = clip(r[c], limit[c])
            add.append('\t'.join((r + [''] * ncols)[:ncols]))
    lines[last + 1:last + 1] = add
    set_header(lines, 1, {2: renumber(lines, 3)})
    return lines, filled


def port_display(vd16, vdo, cars):
    uids = {f[9] for f in cars}
    lines = list(vd16)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    ncols = len(cells(lines[3]))
    add = ['\t'.join((cells(l) + [''] * ncols)[:ncols]) for l in vdo[4:]
           if len(cells(l)) > 3 and cells(l)[0].strip().isdigit() and cells(l)[3] in uids]
    lines[last + 1:last + 1] = add
    set_header(lines, 1, {1: renumber(lines, 4)})
    return lines


def port_tires(tl16, tlo, cars):
    have = {cells(l)[1] for l in tl16[3:] if len(cells(l)) > 1}
    need = {t.strip() for f in cars for t in f[46:56] if t.strip() not in ('-1', '')}
    ncols = len(cells(tl16[2]))
    lines = list(tl16)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    add = [cells(l)[:ncols] for l in tlo[3:] if len(cells(l)) > 7 and cells(l)[1] in need - have]
    lines[last + 1:last + 1] = ['\t'.join(r) for r in add]
    set_header(lines, 1, {1: renumber(lines, 3)})
    return lines, [r[7] for r in add], sorted(need - have - {r[1] for r in add})


def origin_visuals(vio):
    """The Origin VisualItem table in the 2016 layout: without its column 7 ("Trade")."""
    if cells(vio[5])[7] != 'Trade':
        sys.exit('VisualItem: the Origin table has no "Trade" column 7 (another build?)')
    return ['\t'.join(c[:7] + c[8:]) for c in map(cells, vio)]


def renumber_items(t16, vio, vso, cars):
    """The new cars' own items (pc_XXXXs_0N ...) whose Origin Unique Id belongs to another item in 2016 (Origin
    reused the Ids of 2016 decals) get Ids after every Id of both tables. -> (VisualItem, VShopItem, {item: new id})."""
    bases = {f[7].lower()[:-4] for f in cars}
    taken = {}
    for l in t16['VisualItem'][6:]:
        c = cells(l)
        if len(c) > 4 and c[4].strip().isdigit():
            taken[c[4].strip()] = c[3]
    for l in t16['VShopItem'][3:]:
        c = cells(l)
        if len(c) > 3 and c[2].strip().isdigit():
            taken.setdefault(c[2].strip(), c[3])
    ids = [int(k) for k in taken]
    for t, first, col in ((vio, 6, 4), (vso, 3, 2)):
        ids += [int(cells(l)[col]) for l in t[first:] if len(cells(l)) > col and cells(l)[col].strip().isdigit()]
    nxt = (max(ids) // 1000 + 1) * 1000
    moved = {}
    for t, first, col in ((vio, 6, 4), (vso, 3, 2)):
        for i in range(first, len(t)):
            c = cells(t[i])
            if len(c) > max(col, 3) and c[3].lower().rsplit('_', 1)[0] in bases and taken.get(c[col].strip(), c[3]) != c[3]:
                if c[3] not in moved:
                    moved[c[3]] = nxt
                    nxt += 1
                c[col] = str(moved[c[3]])
                t[i] = '\t'.join(c)
    return vio, vso, moved


def origin_defaults(lines, vio, cars):
    """Keep each new car's body (the default part of the aero category) as Origin has it. The client takes the first row of a
    category that fits the car as its default part (FindDefaultPart 0x7c6d00); for the aero category that is the car's
    body (a BT / ST car uses its base car's sets, SUDI8 the sets of pc_0424s ...). Origin also marks unrelated older
    sets as fitting (pc_0079s_01 fits Survivor BT) behind the right one; in the 2016 table those rows come first. So
    in the rows before Origin's first fitting item, the car's fit is cleared. -> (lines, {category: cells cleared})."""
    src = [cells(l) for l in vio]
    col_o = {src[2][i].strip(): i for i in range(7, len(src[2])) if src[2][i].strip()}
    out = [cells(l) for l in lines]
    col = {out[2][i].strip(): i for i in range(7, len(out[2])) if out[2][i].strip()}
    rows = collections.defaultdict(list)                  # category -> [row index]
    for n, r in enumerate(out):
        if n >= 6 and len(r) > 4 and r[3]:
            rows[r[1]].append(n)
    cleared = collections.Counter()
    for f in cars:
        io, i = col_o.get(f[9]), col[f[9]]
        if io is None:
            continue
        first = {}
        for r in src[6:]:
            if len(r) > io and r[3] and r[io].strip() == '1':
                first.setdefault(r[1], r[3])
        for cat, item in first.items():
            at = next((n for n in rows[cat] if out[n][3] == item), None)
            if at is None or not re.match(r'pc_\d{4}', item):        # only the car's body
                continue
            for n in rows[cat]:
                if n >= at:
                    break
                if out[n][i].strip() == '1':
                    out[n][i] = '0'
                    cleared[cat] += 1
    return ['\t'.join(r) for r in out], dict(cleared)


def port_vshop(vs16, vso, items):
    """The aero sets' shop rows, by column name; category names from a 2016 row with the same category numbers."""
    h16, ho = cells(vs16[2]), cells(vso[2])
    norm = lambda s: re.sub(r'(?<=\D)0+(?=\d)', '', s.replace(' ', '')).lower()
    col_o = {}
    for i, n in enumerate(ho):
        col_o.setdefault(norm(n), i)
    names = {}
    for l in vs16[3:]:
        f = cells(l)
        if len(f) > 12 and f[0].strip().isdigit():
            names.setdefault((f[6], f[8], f[10]), (f[7], f[9], f[11], f[12]))
    have = {cells(l)[2]: cells(l)[3] for l in vs16[3:] if len(cells(l)) > 3}
    width = max(maxlen(vs16, 3, 4), 34)
    add, nocat = [], set()
    for l in vso[3:]:
        f = cells(l)
        if len(f) > 4 and f[3] in items:
            if have.get(f[2], f[3]) != f[3]:
                sys.exit(f'VShopItem: Unique Id {f[2]} is {have[f[2]]} in 2016 and {f[3]} in Origin')
            if f[2] in have:
                continue
            row = [f[col_o[norm(n)]] if n and norm(n) in col_o and col_o[norm(n)] < len(f) else '' for n in h16]
            key = (row[6], row[8], row[10])
            if key in names:
                row[7], row[9], row[11], row[12] = names[key]
            else:
                nocat.add(key)
            row[4] = clip(row[4], width)
            add.append('\t'.join(row))
    lines = list(vs16)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    lines[last + 1:last + 1] = add
    n = renumber(lines, 3)
    uids = [int(cells(l)[2]) for l in lines[3:] if len(cells(l)) > 2 and cells(l)[2].strip().isdigit()]
    set_header(lines, 1, {1: n, 3: max(uids) + 1})
    return lines, len(add), nocat


# ---- interface --------------------------------------------------------------------------------------------------

class Interface(p.Interface):
    """The 2016 client's game.nui / uitex.agt, with the Origin client's as the source."""

    def __init__(self, origin):
        self.nui_path = target('Data_US', 'gameui', 'game.nui')
        self.tex_path = target('Data_US', 'gameui', 'uitex.agt')
        self.nui = open(self.nui_path, 'rb').read().decode('cp949')
        self.dev_nui = open(os.path.join(origin.root, 'Data', 'GameUI', 'game.nui'), 'rb').read().decode('cp949', 'replace')
        self.tex_header, self.tex_files = agt.read(self.tex_path)
        self.pieces = {}
        for i, (n, d) in enumerate(self.tex_files):
            if n.lower().endswith('.ntx'):
                for e, off, size in entries(d):
                    self.pieces[e.lower()] = (i, d[off + 72:off + 72 + size])
        self.src = {}
        for name in sorted(origin.files):
            if name.startswith('data\\gameui\\tex\\') and name.endswith('.ntx'):
                d = origin.read(name)
                for e, off, size in entries(d):
                    self.src.setdefault(e.lower(), d[off + 72:off + 72 + size])
        self.add_pieces, self.changed = {}, False

    def piece_for(self, name):
        data = self.src.get(name.lower())
        if data is None:
            return None
        have = self.pieces.get(name.lower())
        if have is None:
            return name, data
        if have[1] == data:
            return name, None
        coords, atlas = name.split('_', 1)
        new = f'{coords}_po{atlas}'
        if new.lower() in self.pieces and self.pieces[new.lower()][1] == data:
            return new, None
        return new, data


# ---- the port ---------------------------------------------------------------------------------------------------

def build(origin, sellable):
    from dcemu.native.data import read_tdf
    init = target('Data', 'Init.agt')
    t16 = {n: xlt_lines(orig_entry(init, 'Init\\%s.xlt' % n)) for n in TABLES}
    to = {n: origin.xlt(n) for n in TABLES}
    cars = new_cars(t16['VehicleList'], to['VehicleList'])
    uids = sorted(int(f[9]) for f in cars)
    print(f'{len(cars)} Origin player cars the 2016 client lacks (Unique Ids {uids[0]}-{uids[-1]}, '
          f'{sum(u >= 450 for u in uids)} of them above the 2016 limit of 449)')
    assists = {c for r in read_tdf(os.path.join(SERVER, 'tables', 'Assist_Client.tdf')) for c in r}
    tables, report = {}, []
    tables['VehicleList'], dropped = port_vehicle_list(t16['VehicleList'], cars, assists, sellable)
    if dropped:
        report.append('Car Assist not in the 2016 Assist_Client, set to "-": ' + ', '.join(sorted(dropped)))
    tables['VehicleUpgrade'], filled = port_upgrades(t16['VehicleUpgrade'], to['VehicleUpgrade'], cars)
    if filled:
        report.append(f'{len(filled)} cars had empty grades in Origin, filled by the Sum rule: ' +
                      ', '.join(f'{u} (V{min(g)}-V{max(g)})' for u, g in sorted(filled.items(), key=lambda x: int(x[0]))))
    tables['VehicleDisplay'] = port_display(t16['VehicleDisplay'], to['VehicleDisplay'], cars)
    tables['TireList'], tire_files, no_tire = port_tires(t16['TireList'], to['TireList'], cars)
    if no_tire:
        report.append('tire ids no table has: ' + ', '.join(no_tire))
    p.ITEM_NAME_BYTES = max(maxlen(t16['VisualItem'], 6, 5), 34)
    vio, vso, moved = renumber_items(t16, origin_visuals(to['VisualItem']), to['VShopItem'], cars)
    if moved:
        report.append(f'{len(moved)} aero items whose Origin Unique Id another 2016 item has got new Ids '
                      f'{min(moved.values())}-{max(moved.values())}')
    to['VShopItem'] = vso
    tables['VisualItem'], aero, missing = p.port_visuals(t16['VisualItem'], vio, [(f, int(f[9])) for f in cars])
    if missing:
        report.append('no Origin VisualItem column for ' + ', '.join(missing))
    tables['VisualItem'], cleared = origin_defaults(tables['VisualItem'], vio, cars)
    if cleared:
        report.append(f'fits of the new cars cleared in rows before their Origin default part, by category: {cleared}')
    tables['VShopItem'], shop_rows, nocat = port_vshop(t16['VShopItem'], to['VShopItem'], set(aero))
    if nocat:
        report.append(f'VShopItem categories without a 2016 row (names left as Origin has them): {sorted(nocat)}')
    print(f'  tables: {len(cars)} VehicleList rows, {9 * len(cars)} VehicleUpgrade rows, {len(tire_files)} tires, '
          f'{len(aero)} aero items ({shop_rows} shop rows)')
    # car keys
    data_pack = target('Data', 'World', 'data.agt')
    key_data = orig_entry(data_pack, 'Data\\UseItemClient.tdf')
    have_keys = {r[0] for r in p._tdf_rows(key_data)}
    okeys = {r[0]: r for r in p._tdf_rows(origin.read('data\\world\\data\\useitemclient.tdf'))}
    tmpl = next(r for r in p._tdf_rows(key_data) if r[0] == 'pc_0442s')
    keys = []
    for f in cars:
        k = f[7][:-4]
        if k in have_keys:
            continue
        r = list(okeys[k]) if k in okeys else [k, tmpl[1], f[6] + ' Key'] + list(tmpl[3:])
        r[6], r[9] = r[2], f[9]
        keys.append(r)
    key_data = p.tdf_append(key_data, keys) if keys else key_data
    print(f'  {len(keys)} car keys ({sum(1 for f in cars if f[7][:-4] not in okeys)} made from the Dominator BT key)')
    # files
    vfiles = {n: v for n, v in origin.files.items() if n.startswith('data\\vehicle\\')}
    by_base = collections.defaultdict(list)
    for n in vfiles:
        by_base[n.rsplit('\\', 1)[-1]].append(n)
    pack = target('Data', 'vehicles.agt')
    b = backup_path(pack)
    have = set(p.pack_entries(b if os.path.exists(b) else pack))
    want = set()
    for f in cars:
        base = f[7].lower()[:-4]
        want |= {n for n in vfiles if base in n.rsplit('\\', 1)[-1]}
    for t in tire_files:
        want |= set(by_base.get(t.lower(), [])) | set(by_base.get(t.lower()[:-4] + '.dds', []))
    add = {}
    for n in sorted(want):
        add[n] = origin.read(n)
    for n in list(add):                               # textures the models name
        if n.endswith('.nif'):
            for r in set(re.findall(rb'[\w\-.]+\.dds', add[n], re.I)):
                for m in by_base.get(r.decode('latin-1').lower(), []):
                    if m not in add:
                        add[m] = origin.read(m)
    files = {origin.files[n][2][5:]: d for n, d in add.items() if n[5:] not in have}
    print(f'  {len(files)} vehicle files ({sum(map(len, files.values())) // 1000000} MB; {len(add) - len(files)} '
          f'already in the 2016 pack, kept)')
    no_model = [f[7] for f in cars if not any(n.rsplit('\\', 1)[-1].startswith(f[7].lower()[:-4]) for n in add)]
    if no_model:
        report.append('cars without any model file: ' + ', '.join(no_model))
    # interface
    ui = Interface(origin)
    names = sorted({f[7][:-4] for f in cars})
    for src, dst in CAR_DIALOGS.items():
        done = ui.copy_controls(src, dst, names)
        print(f'  game.nui dialog {dst}: {len(done)} of {len(names)} car pictures')
    if getattr(ui, 'skipped', None):
        report.append(f'{len(ui.skipped)} pictures whose piece the Origin uitex lacks, left out')
    sounds = []
    for f in cars:
        for kind in ('idle', 'mid'):
            src = os.path.join(origin.root, 'Data', 'audio', 'engine', f'{kind}{f[9]}.wav')
            if os.path.exists(src):
                sounds.append((src, target('Data', 'audio', 'engine', f'{kind}{f[9]}.wav')))
    print(f'  {len(sounds)} engine sounds')
    return dict(cars=cars, tables=tables, key_data=key_data, files=files, ui=ui, sounds=sounds, report=report)


def write(b):
    import carlimit2016
    os.makedirs(BACKUPS, exist_ok=True)
    p.backup_path, p.BACKUPS, p.ROOT = backup_path, BACKUPS, ROOT
    exe = target('DriftCity.exe')
    data = open(exe, 'rb').read()
    new = carlimit2016.apply(data)
    if new != data:
        keep = os.path.join(HERE, '..', 'client_backup', '2016', 'DriftCity.exe.orig')
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        if not os.path.exists(keep):
            shutil.copy2(exe, keep)
        open(exe + '.tmp', 'wb').write(new)
        shutil.copymode(exe, exe + '.tmp')
        os.replace(exe + '.tmp', exe)
        print('  DriftCity.exe: car limit raised to 2000 Unique Ids')
    if b['files']:
        p.pack_update(target('Data', 'vehicles.agt'), b['files'])
    p.pack_update(target('Data', 'Init.agt'), {'Init\\%s.xlt' % n: xlt_bytes(l) for n, l in b['tables'].items()})
    p.pack_update(target('Data', 'World', 'data.agt'), {'Data\\UseItemClient.tdf': b['key_data']})
    b['ui'].save()
    n = 0
    for src, dst in b['sounds']:
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
            n += 1
    print(f'  {n} engine sounds copied')
    for name, lines in b['tables'].items():
        open(os.path.join(SERVER, 'Init', name + '.xlt'), 'wb').write(xlt_bytes(lines))
    open(os.path.join(SERVER, 'tables', 'UseItemClient.tdf'), 'wb').write(b['key_data'])
    print('  server_data_2016: the tables written (restart the emulator)')


def reset():
    if not os.path.isdir(BACKUPS):
        return print('nothing to reset')
    for rel in ('Data/vehicles.agt', 'Data/Init.agt', 'Data/World/data.agt', 'Data_US/gameui/game.nui',
                'Data_US/gameui/uitex.agt'):
        path = target(*rel.split('/'))
        b = backup_path(path)
        if os.path.exists(b):
            shutil.copy2(b, path)
            print('  restored', rel)
    init = target('Data', 'Init.agt')
    for n in TABLES:
        open(os.path.join(SERVER, 'Init', n + '.xlt'), 'wb').write(p.read_entry(init, 'Init\\%s.xlt' % n))
    open(os.path.join(SERVER, 'tables', 'UseItemClient.tdf'), 'wb').write(
        p.read_entry(target('Data', 'World', 'data.agt'), 'Data\\UseItemClient.tdf'))
    print('  server_data_2016 tables restored; the exe patch and engine sounds stay (carlimit2016 remove)')


def main():
    global ORIGIN, CLIENT
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('action', choices=('dry', 'apply', 'reset'))
    ap.add_argument('folder', nargs='?')
    ap.add_argument('--origin', default=ORIGIN)
    ap.add_argument('--client', default=CLIENT)
    ap.add_argument('--sellable', choices=('keep', 'gotcha'), default='keep')
    a = ap.parse_args()
    ORIGIN, CLIENT = a.origin, a.client
    if a.action == 'reset':
        return reset()
    b = build(Origin(ORIGIN), a.sellable)
    for line in b['report']:
        print('  note:', line)
    if a.action == 'dry':
        if a.folder:
            os.makedirs(a.folder, exist_ok=True)
            for n, lines in b['tables'].items():
                open(os.path.join(a.folder, n + '.xlt'), 'wb').write(xlt_bytes(lines))
            open(os.path.join(a.folder, 'UseItemClient.tdf'), 'wb').write(b['key_data'])
            open(os.path.join(a.folder, 'files.txt'), 'w').write('\n'.join(sorted(b['files'])))
            open(os.path.join(a.folder, 'game.nui'), 'wb').write(b['ui'].nui.encode('cp949'))
            print('  dry run: tables in', a.folder, '; picture pieces', len(b['ui'].add_pieces))
        return
    write(b)


if __name__ == '__main__':
    main()
