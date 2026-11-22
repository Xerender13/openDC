"""openDC Launcher: a character's inventory as in the game's Inventory window (Parts): the car's part slots, the items,
the car's points. Putting parts on and taking them off, selling, deleting and changing the car in use follow the
openDC server (Emulator/dcemu/native/game/items.py equip_item / unequip / sell_item / drop_item, cars.py), straight on
the database while the game is closed.

Part slots (state = slot << 16 | 1 on the car): speed 100-102, accel 103-105, crash 106-108, boost 109-111 (two lines:
Contents.ini Main.PartsInvenLine), Neo weapon 112, amplifier 113, fuse 114, armour 115. Options sit on a part's slot
(only with emulator.ini [items] option_parts = 1); docking items are docked in the game.
"""
import configparser
import os
import struct

PART_TYPES = {'speed': 0, 'crash': 1, 'accel': 2, 'boost': 3, 'op_S': 6, 'op_C': 7, 'op_A': 8, 'op_B': 9, 'op_F': 10}
SLOT_BASE = {0: 100, 2: 103, 1: 106, 3: 109}
NEO_SLOTS = {'neo_weapon': 112, 'neo_coil': 113, 'neo_fuse': 114, 'neo_armor': 115}
OPTION_TYPES, DOCK, USE = (6, 7, 8, 9, 10), 11, 5
OPTION_STAT = {6: 0, 7: 1, 8: 2, 9: 3}        # speed, crash, accel, boost
GRADE_FITS = {'N': ('FN', 'ON'), 'S': ('FN', 'FS', 'OS'), 'H': ('FN', 'FS', 'FH', 'OH'),
              'E': ('FN', 'FS', 'FH', 'FE', 'OE'), 'U': ('FN', 'FS', 'FH', 'OU')}
HEAT_GRADES = {'H': 2, 'U': 3}
# drift items that go on a car (dcemu vshop.EQUIPPABLE), the ones that share one slot, and the ones that cannot come
# off (a new one destroys the one on the car: paint / gloss paint, neon, window tint)
DRIFT_EQUIP = frozenset(range(1, 14)) | {32, 38, 47, 48, 52}
DRIFT_SAME = {1: {1, 32}, 32: {1, 32}, 8: {8, 48}, 48: {8, 48}, 4: {4, 5, 6}, 5: {4, 5, 6}, 6: {4, 5, 6}}
DRIFT_FIXED = {1, 32, 2, 3}
ON_CAR = 1


def read_tdf(path):
    with open(path, 'rb') as f:
        d = f.read()
    bmp, = struct.unpack_from('<I', d, 2)
    t = d[bmp:]
    cols, n = struct.unpack_from('<II', t, 16)
    offs = struct.unpack_from(f'<{cols * n}I', t, 24)

    def s(o):
        e = t.index(b'\0\0', o)
        while (e - o) % 2:
            e = t.index(b'\0\0', e + 1)
        return t[o:e].decode('utf-16-le')
    return [[s(offs[r * cols + c]) for c in range(cols)] for r in range(n)]


def read_xlt(path):
    with open(path, 'rb') as f:
        return [l.split('\t') for l in f.read().decode('utf-16-le').lstrip('﻿').split('\r\n')]


def num(x, cast=int):
    try:
        return cast(float(x))
    except (TypeError, ValueError):
        return 0


class Data:
    def __init__(self):
        base = next((b for b in ('server_data_2016', 'server_data') if os.path.isdir(os.path.join(b, 'tables'))), 'server_data')
        self.base = base
        self.parts = {r[2]: r for r in read_tdf(os.path.join(base, 'tables', 'ItemClient.tdf'))}
        self.use = {r[0]: r for r in read_tdf(os.path.join(base, 'tables', 'UseItemClient.tdf'))}
        self.lines = 2
        try:
            for l in open(os.path.join(base, 'tables', 'Contents.ini'), encoding='utf-8', errors='replace'):
                if l.strip().startswith('Main.PartsInvenLine='):
                    self.lines = num(l.split('=', 1)[1]) or 2
        except OSError:
            pass
        ini = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            ini.read('emulator.ini', encoding='utf-8')
        except configparser.Error:
            pass
        self.option_parts = ini.get('items', 'option_parts', fallback='0').strip() == '1'
        self.upgrade, self.cars = {}, {}
        x = read_xlt(os.path.join(base, 'Init', 'VehicleUpgrade.xlt'))
        hdr = next(i for i, r in enumerate(x) if 'GradeLvl' in r)
        col = {n: i for i, n in enumerate(x[hdr]) if n}
        for r in x[hdr + 1:]:
            if len(r) > col['GradeLvl'] and r[col['ID']].strip().isdigit() and r[col['GradeLvl']].strip().isdigit():
                self.upgrade[(int(r[col['ID']]), int(r[col['GradeLvl']]))] = {
                    k: num(r[col[k]], float if k == 'Efficiency' else int) for k in ('Speed', 'Accel', 'Crash', 'Boost', 'Capacity', 'Efficiency')
                    if k in col}
                for k in ('Sell', 'CloseSell', 'Price', 'Req Level'):
                    if k in col and len(r) > col[k]:
                        self.upgrade[(int(r[col['ID']]), int(r[col['GradeLvl']]))][k] = num(r[col[k]])
        v = read_xlt(os.path.join(base, 'Init', 'VehicleList.xlt'))
        for r in v[4:]:
            if len(r) > 23 and r[9].strip().isdigit():
                self.cars[int(r[9])] = {'name': r[6].strip() or r[5].strip(), 'model': r[7].strip().rsplit('.', 1)[0],
                                        'lvl': num(r[23]), 'sellable': num(r[10]), 'tire': r[46].strip() if len(r) > 46 else '',
                                        'tire_scale': [num(r[40]) if len(r) > 40 else 660, num(r[41]) if len(r) > 41 else 660],
                                        'tire_width': [num(r[42], float) if len(r) > 42 else 1, num(r[43], float) if len(r) > 43 else 1]}
        self.tires = {}
        try:
            for r in read_xlt(os.path.join(base, 'Init', 'TireList.xlt'))[3:]:
                if len(r) > 7 and r[1].strip():
                    self.tires[r[1].strip()] = r[7].strip().rsplit('.', 1)[0].lower()
        except OSError:
            pass

    def visuals(self):
        """VisualItem.xlt by its id: the category (index, name) and the item name."""
        if not hasattr(self, '_vis'):
            self._vis = {}
            try:
                for r in read_xlt(os.path.join(self.base, 'Init', 'VisualItem.xlt'))[4:]:
                    if len(r) > 4 and r[4].strip().isdigit() and r[1].strip().isdigit():
                        e = {'cat': int(r[1]), 'catName': r[0].replace('"', '').replace('\n', ' ').strip(), 'item': r[3].strip(),
                             'uid': r[4].strip(), 'index': num(r[2]), 'name': r[5].strip() if len(r) > 5 else ''}
                        # SKID_VSITEM_TB.ITEMID holds the item name (dcemu data.visual_index); by the id as well
                        self._vis[r[4].strip()] = e
                        self._vis.setdefault(r[3].strip(), e)
            except OSError:
                pass
        return self._vis

    def vis_cars(self):
        """VisualItem.xlt: item name (lower) -> the car types it fits (header row 2: a car type per column from 7,
        '1' = fits)."""
        if not hasattr(self, '_viscars'):
            self._viscars = {}
            try:
                x = read_xlt(os.path.join(self.base, 'Init', 'VisualItem.xlt'))
                types = {i: int(h) for i, h in enumerate(x[2]) if i >= 7 and str(h).strip().isdigit()} if len(x) > 2 else {}
                for r in x[4:]:
                    if len(r) > 6 and r[4].strip().isdigit():
                        self._viscars.setdefault(r[3].strip().lower(), {t for i, t in types.items() if i < len(r) and r[i].strip() == '1'})
            except OSError:
                pass
        return self._viscars

    def box_icons(self, item_id):
        """Other pictures for an item without its own icon: a car gift box (i_n_box_hykan_st_v1) is drawn as the
        game's gift box (giftbox_hykanst_v1) or the key of the car inside (RewardGroup rw_<item>: pc_0433s)."""
        if not hasattr(self, '_rw'):
            self._rw = {}
            try:
                for r in read_xlt(os.path.join(self.base, 'Init', 'RewardGroup.xlt'))[3:]:
                    if len(r) > 5 and r[3].strip() == 'NormalItem':
                        self._rw.setdefault(r[1].strip(), r[5].strip())
            except OSError:
                pass
        low = (item_id or '').lower()
        out = []
        if low.startswith('i_n_box_'):
            rest = low[8:]
            m = rest.rsplit('_v', 1)
            if len(m) == 2:
                out.append('item:giftbox_' + m[0].replace('_', '') + '_v' + m[1])
                out.append('item:giftbox_' + m[0].split('_')[0] + '_v' + m[1])
        inner = self._rw.get('rw_' + (item_id or ''))
        if inner:
            out += ['car:' + inner.lower(), 'item:' + inner.lower()]
        return out

    def look_lists(self):
        """SpoilerList (wings: id, name, type 1 aero / 2 booster wing, file) and TireList (listed tires: id, name, file, icon)."""
        if not hasattr(self, '_ll'):
            wings, tires = [], []
            try:
                for r in read_xlt(os.path.join(self.base, 'Init', 'SpoilerList.xlt'))[3:]:
                    if len(r) > 7 and r[1].strip().isdigit() and r[3].strip() == '1':
                        wings.append({'id': int(r[1]), 'name': r[2].strip(), 'type': num(r[6]), 'file': r[7].strip().lower()})
                for r in read_xlt(os.path.join(self.base, 'Init', 'TireList.xlt'))[3:]:
                    if len(r) > 10 and r[1].strip().isdigit() and r[3].strip() == '1':
                        tires.append({'id': int(r[1]), 'name': r[2].strip(), 'file': r[7].strip().lower().rsplit('.', 1)[0], 'icon': r[10].strip()})
            except OSError:
                pass
            self._ll = (wings, tires)
        return self._ll

    def vshop(self, item_name):
        """(shown name, tooltip) of a drift shop item by its item name."""
        self.desc('')
        v = self._vshop.get((item_name or '').lower())
        return (v[0], v[1].replace('\\n', '\n')) if v else ('', '')

    def desc(self, item_id):
        """the client's tooltip text of an item (UseItemClient description, or VShopItem's for a drift item)."""
        r = self.use.get(item_id)
        if r and len(r) > 6 and r[6] not in ('', 'n/a'):
            return r[6].replace('\\n', '\n')
        if not hasattr(self, '_vshop'):
            self._vshop = {}
            try:
                for v in read_xlt(os.path.join(self.base, 'Init', 'VShopItem.xlt'))[3:]:
                    if len(v) > 5 and v[3].strip():
                        # (name, tooltip, Sell Mito, {days: CC price} when sold for CC: UseHancoin, $Price 7D / 30D / 90D / 365D / 0D)
                        cc = {}
                        if len(v) > 52 and num(v[29]):
                            for pc, pr, d in ((31, 32, 7), (36, 37, 30), (41, 42, 90), (46, 47, 365), (51, 52, 0)):
                                if num(v[pr]):
                                    cc[num(v[pc]) or d if d else 0] = num(v[pr])
                        self._vshop.setdefault(v[3].strip().lower(), (v[4].strip(), v[5].strip(), num(v[28]) if len(v) > 28 else 0, cc,
                                                                      num(v[10]) if len(v) > 10 else 0))
            except OSError:
                pass
        v = self._vshop.get(item_id.lower())
        return v[1].replace('\\n', '\n') if v and v[1] not in ('', 'n/a') else ''

    def upgrade_grade(self, item_name):
        """the grade a timed car upgrade (category 38, i_d_u_11..18) gives: VShopItem Sub 8001 = V2 .. 8008 = V9
        (dcemu player.upgrade_grade)."""
        self.desc('')
        v = self._vshop.get((item_name or '').lower())
        sub = v[4] if v and len(v) > 4 else 0
        return sub - 8000 + 1 if 8001 <= sub <= 8099 else 0

    def vsell(self, item_name, period=0):
        """what a drift shop item sells for: its 'Sell Mito' (VShopItem); an item sold for CC without one, its CC price
        x 10 (1 CC = 10 Mito), the price of the period it was bought for (else its first CC price)."""
        self.desc('')
        v = self._vshop.get((item_name or '').lower())
        if not v:
            return 0
        if int(v[2] or 0):
            return int(v[2])
        cc = v[3] if len(v) > 3 else {}
        if not cc:
            return 0
        p = cc.get(int(period or 0))
        if p is None:
            p = next(iter(cc.values()))
        return int(p) * 10

    def info(self, item_id):
        r = self.parts.get(item_id)
        if r:
            kind = r[0]
            t = PART_TYPES.get(kind, DOCK if kind.startswith('dock_') else (12 if kind.startswith('neo_') else 13))
            return {'kind': kind, 'type': t, 'name': r[4] if r[4] != 'n/a' else item_id, 'grade': r[6], 'level': num(r[7]),
                    'req_grade': num(r[8]), 'value': num(r[9]), 'sell': num(r[13]), 'twin': r[14] if len(r) > 14 else '',
                    'icon': r[3], 'stack': 1}
        r = self.use.get(item_id)
        if r:
            return {'kind': r[1], 'type': USE, 'name': r[2], 'grade': '', 'level': 0, 'req_grade': 0, 'value': num(r[9]),
                    'sell': num(r[8]), 'twin': '', 'icon': r[3], 'stack': num(r[5]) or 999}
        return {'kind': '?', 'type': 13, 'name': item_id, 'grade': '', 'level': 0, 'req_grade': 0, 'value': 0, 'sell': 0,
                'twin': '', 'icon': '', 'stack': 1}


def slot_of(it):
    return it['state'] >> 16


def on_car(it):
    return it['car'] and (it['state'] & 0xffff) == ON_CAR


# the fixed colours of the drift shop's paints (VisualItem category 1 / 32 by their index), neons (2) and tints (3):
# the client keeps them, the tables only name them
PAINT_RGB = [0xC4C8CC, 0x7EC8F0, 0xE6C66A, 0xE3D3AE, 0x3FA34D, 0xCD5C5C, 0x1E5BD8, 0xF3EBD2, 0x2B3A55, 0x169E8C, 0x3C5F9E, 0xFFE21F,
             0xFF7A12, 0x8CD13C, 0x5A2A8A, 0x4A4D52, 0xFF8FC0, 0xFF8C1A, 0x0F5A5C, 0x6E1A2E, 0x2343A8, 0x8A8F99, 0x15171C, 0x4A4D52,
             0xB0172B, 0x1846E0, 0xB3266E, 0x556B2F, 0x6A7480]
NEON_RGB = {1: 0x30FF60, 2: 0xFFE630, 3: 0xFF5AC0, 4: 0xA050FF, 5: 0xFF3030, 6: 0x3070FF}
TINT_RGB = {1: 0xB8BEC6, 2: 0x101214, 3: 0x3A2414, 4: 0x6A4426, 5: 0x10204A, 6: 0x2850A0, 7: 0x103A20, 8: 0x2E7A44}


def text_rgb(text):
    """a colour from an item text -> 0xRRGGBB. The colour window writes a Windows colour, 0x00BBGGRR, as decimal (a car
    painted red in the game holds 255 + ...: user, 2026-11-22); older texts RRRGGGBBB after spaces."""
    t = (text or '').strip()
    if not t.isdigit():
        return None
    v = int(t)
    if len(t) == 9 and v > 0xffffff:
        return (int(t[:3]) & 0xff) << 16 | (int(t[3:6]) & 0xff) << 8 | (int(t[6:]) & 0xff)
    return (v & 0xff) << 16 | (v & 0xff00) | (v >> 16 & 0xff)


def look_entry(v, text, wings, tires, vis):
    """one equipped drift item -> {cat, file, name, rgb} for the 3D views."""
    cat, item, idx = v['cat'], v['item'], v.get('index', 0)
    e = {'cat': cat, 'file': item.lower(), 'name': v.get('name') or item}
    low = item.lower()
    if cat in (1, 32, 2, 3):
        rgb = text_rgb(text)
        if rgb is None:
            if cat in (1, 32) and 1 <= idx <= 29:
                e['pal'] = idx                       # the paint's colour is VehicleColor.nxt's of the same number
                rgb = PAINT_RGB[idx - 1] if idx <= len(PAINT_RGB) else None
            elif cat == 2:
                rgb = NEON_RGB.get(idx, 0x40C0FF)     # the colour-window neons (N, S5 ...) without a colour yet
            elif cat == 3:
                rgb = TINT_RGB.get(idx)
        e['rgb'] = rgb
    elif cat == 6 and not low.startswith('pc_0') and text.strip():
        uid = text.strip()[-5:]                     # a generic aero set: the car's own body from its text (... style, id)
        a = vis.get(uid.lstrip('0') or '0') or vis.get(uid)
        if a:
            e['file'] = a['item'].lower()
    elif cat == 7 and text.strip().isdigit():          # a wing picked at the purchase: its SpoilerList id
        w = next((w for w in wings if w['id'] == int(text)), None)
        if w:
            e['file'] = w['file']
    elif cat == 11:                                    # a decal: decal.nxt's decal of that number, in its colour
        e['index'] = idx
        e['rgb'] = text_rgb(text)
    elif cat == 9:                                     # a number plate: its picture (i_num0N) and the text written on it
        e['plate'] = idx if 1 <= idx <= 7 else 1
        e['text'] = ''.join(ch for ch in (text or '').strip() if ' ' <= ch <= '~')[:8]
    elif cat in (8, 48) and text.strip().isdigit():    # a tire / wheel picked at the purchase: its TireList id
        w = next((w for w in tires if w['id'] == int(text)), None)
        if w:
            e['file'] = w['file']
    return e


def repair_vs(cur, rows, sid, cid, vis):
    """Rows written by launchers before 0.1.2 kept the VisualItem id in ITEMID; the game reads the item name there
    (dcemu player.load: data.visual_index[ITEMID]), so it did not see them: put the name."""
    for inv, iid in rows("SELECT invenidx, itemid FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND itemid ~ '^[0-9]+$'", (sid, cid)):
        e = vis.get(str(iid).strip())
        if e and e.get('item'):
            cur.execute('UPDATE skid_vsitem_tb SET itemid = %s WHERE serverid = %s AND cid = %s AND invenidx = %s', (e['item'], sid, cid, int(inv)))


def run(cmd, req, sid, cid, cur, rows, one):
    """-> the reply dict (the caller commits when it has no 'error')."""
    D = Data()
    ch = one('SELECT nlevel, gold, curcar FROM skid_character_tb WHERE serverid = %s AND cid = %s', (sid, cid))
    level, gold, cur_car = int(ch[0]), int(ch[1]), int(ch[2] or 0)

    def load_items():
        out = []
        for inv, iid, car, n, rnd, state, upg, box in rows("""SELECT invenidx, itemid, carid, stacknum, nrandom, state,
                nupgrade, box FROM skid_item_tb WHERE serverid = %s AND cid = %s ORDER BY invenidx""", (sid, cid)):
            out.append({'inv': int(inv), 'id': str(iid), 'car': int(car or 0), 'count': int(n or 1), 'random': int(rnd or 0),
                        'state': int(state or 0), 'upgrade': int(upg or 0), 'box': int(box or 0), 'info': D.info(str(iid))})
        return out

    cars = [{'id': int(c), 'type': int(t), 'grade': int(g), 'color': int(col or 0)} for c, t, g, col in
            rows('SELECT carid, cartype, nupgrade, color FROM skid_car_tb WHERE serverid = %s AND cid = %s ORDER BY carid', (sid, cid))]
    auction = set()
    if one("SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'skid_auctioncar_tb'"):
        auction = {int(r[0]) for r in rows('SELECT carid FROM skid_auctioncar_tb WHERE serverid = %s AND cid = %s', (sid, cid))}
    items = load_items()

    def save(it):
        cur.execute('UPDATE skid_item_tb SET carid = %s, state = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                    (it['car'], it['state'], sid, cid, it['inv']))

    def place(it, car, slot):
        it['car'], it['state'] = (car, slot << 16 | ON_CAR) if car else (0, 0)
        save(it)

    def swap_id(it, new):
        it['id'] = new
        it['info'] = D.info(new)
        cur.execute('UPDATE skid_item_tb SET itemid = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                    (new, sid, cid, it['inv']))

    def needs_heat(it):
        i = it['info']
        if i['type'] in OPTION_TYPES or i['type'] in (12, 13, USE) or it['id'].startswith('si_'):
            return None
        if i['type'] == DOCK:
            return 'H' if i['grade'] in ('OH', 'OU') else None
        pair = [x for x in items if on_car(x) and x['car'] == it['car'] and slot_of(x) == slot_of(it) and x['info']['type'] == DOCK
                and x['info']['grade'] in ('OH', 'OU')]
        if pair:
            return i['grade'] if i['grade'] in HEAT_GRADES else 'H'
        return i['grade'] if i['grade'] in HEAT_GRADES else None

    def kit_for(grade):
        return next((x for x in items if not x['car'] and x['info']['kind'] == 'heattreatment'
                     and x['info']['value'] == HEAT_GRADES.get(grade, 2)), None)

    def take_off(it, use_kit):
        """the part with what sits on its slot (option, docking); a hyper / ultra part needs a Heat Treatment Kit."""
        slot, car = slot_of(it), it['car']
        group = [x for x in items if on_car(x) and x['car'] == car and slot_of(x) == slot] if it['info']['type'] in SLOT_BASE \
            or it['info']['type'] == DOCK else [it]
        heat = next((g for g in (needs_heat(x) for x in group) if g), None)
        if heat:
            kit = kit_for(heat)
            if not kit:
                return 'needs_kit_' + heat
            if not use_kit:
                return 'ask_kit_' + heat
            kit['count'] -= 1
            if kit['count'] > 0:
                cur.execute('UPDATE skid_item_tb SET stacknum = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (kit['count'], sid, cid, kit['inv']))
            else:
                cur.execute('DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, kit['inv']))
                items.remove(kit)
        for x in group:
            if x['id'].endswith('_b') and x['info']['twin'] and not x['info']['twin'].endswith('_b'):
                swap_id(x, x['info']['twin'])          # the scorched twin becomes the part again
            place(x, 0, 0)
        return None

    def sell_price(car):
        up = D.upgrade.get((car['type'], car.get('base_grade', car['grade'])))
        if not up or 'Sell' not in up:
            return None
        sold = (D.cars.get(car['type']) or {}).get('sellable', 0)
        return int(up['Sell'] if sold else up.get('CloseSell', up['Sell']))

    # drift items (SKID_VSITEM_TB): ITEMID = VisualItem's id; its row gives the category and the item name (icon),
    # VShopItem (by item name) the shown name and the tooltip; PERIOD in days from CTIME (0 = for good)
    has_vs = bool(one("SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'skid_vsitem_tb'"))

    def load_drift():
        if not has_vs:
            return []
        vis = D.visuals()
        repair_vs(cur, rows, sid, cid, vis)
        out = []
        for inv, iid, car, state, data, period, ctime in rows("""SELECT invenidx, itemid, carid, state, item_data, period, ctime
                FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s ORDER BY invenidx""", (sid, cid)):
            v = vis.get(str(iid).strip(), {})
            name, desc = D.vshop(v.get('item', ''))
            left = None
            if int(period or 0) > 0 and ctime:
                try:
                    import datetime
                    t0 = ctime if isinstance(ctime, datetime.datetime) else datetime.datetime.fromtimestamp(int(ctime))
                    left = max(0, int(period) - (datetime.datetime.now() - t0).days)
                except (TypeError, ValueError, OverflowError, OSError):
                    left = None
            out.append({'inv': int(inv), 'vid': str(iid).strip(), 'id': v.get('item', ''), 'name': name or v.get('item') or str(iid),
                        'desc': desc, 'cat': v.get('cat', 0), 'catName': v.get('catName', ''), 'car': int(car or 0),
                        'on': int(state or 0) == 1, 'period': int(period or 0), 'left': left, 'data': str(data or '').strip()})
        return out

    def sale_of(car_id):
        """what selling a car brings: the car (its grade's Sell), the performance parts on it (their Sell x count) and
        its drift shop items (VShopItem 'Sell Mito'); each line {name, mito, kind}."""
        lines = [{'kind': 'part', 'name': x['info']['name'], 'mito': int(x['info']['sell'] or 0) * max(1, x['count']), 'inv': x['inv']}
                 for x in items if on_car(x) and x['car'] == car_id]
        if has_vs:
            vis = D.visuals()
            for inv, iid, period in rows('SELECT invenidx, itemid, period FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s AND state = 1',
                                         (sid, cid, car_id)):
                v = vis.get(str(iid).strip(), {})
                name = D.vshop(v.get('item', ''))[0] or v.get('item') or str(iid)
                lines.append({'kind': 'drift', 'name': name, 'mito': D.vsell(v.get('item', ''), period), 'inv': int(inv)})
        return lines

    if cmd == 'inv_do' and str(req.get('act', '')).startswith('drift_'):
        act = req['act']
        drift = load_drift()
        d = next((x for x in drift if x['inv'] == int(req.get('inv', -1))), None)
        if not d:
            return {'error': 'no_item'}
        car = int(req.get('car', 0) or 0)
        if act == 'drift_on':
            if d['cat'] not in DRIFT_EQUIP:
                return {'error': 'drift_not_car'}
            if not any(c['id'] == car for c in cars):
                return {'error': 'no_car'}
            # an item bought for (or worn by) another car can go on this one, when it fits (below); paint, neon and glass
            # worn by another car stay there (they do not come off a car)
            if d['on'] and d['car'] and d['car'] != car and d['cat'] in DRIFT_FIXED:
                return {'error': 'drift_fixed'}
            # as the game: an item made for some cars only (VisualItem's car columns), a wing picked at the purchase
            # (SpoilerList id: a car's own wing fits only that car) or an Aero set bought for one car type (its text)
            ctype = next(c['type'] for c in cars if c['id'] == car)
            vc = D.vis_cars()
            fits = vc.get(d['id'].lower())
            if fits and ctype not in fits:
                return {'error': 'drift_not_this_car'}
            txt = (d['data'] or '').strip()
            if d['cat'] == 7 and txt.isdigit():
                w = next((w for w in D.look_lists()[0] if w['id'] == int(txt)), None)
                wf = vc.get(w['file']) if w else None
                if wf and ctype not in wf:
                    return {'error': 'drift_not_this_car'}
            # (the Aero set's text ends with car type (3 digits), style, VisualItem id (5 digits))
            if d['cat'] == 6 and not d['id'].lower().startswith('pc_0') and len(txt) >= 9 and txt[-9:-6].isdigit() and int(txt[-9:-6]) != ctype % 1000:
                return {'error': 'drift_not_this_car'}
            group = DRIFT_SAME.get(d['cat'], {d['cat']})
            for x in drift:
                if x is not d and x['on'] and x['car'] == car and x['cat'] in group:
                    if x['cat'] in DRIFT_FIXED:
                        cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, x['inv']))
                    else:
                        cur.execute('UPDATE skid_vsitem_tb SET state = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, x['inv']))
            cur.execute('UPDATE skid_vsitem_tb SET carid = %s, state = 1 WHERE serverid = %s AND cid = %s AND invenidx = %s', (car, sid, cid, d['inv']))
            return {'ok': True}
        if act == 'drift_off':
            if d['cat'] in DRIFT_FIXED:
                return {'error': 'drift_fixed'}
            cur.execute('UPDATE skid_vsitem_tb SET state = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, d['inv']))
            return {'ok': True}
        if act == 'drift_del':
            cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, d['inv']))
            return {'ok': True}
        return {'error': 'bad_act'}

    if cmd == 'inv_do':
        act = req.get('act')
        it = next((x for x in items if x['inv'] == int(req.get('inv', -1))), None)
        if act == 'sell_car':
            # as selling it in the game's garage (dcemu native/game/cars.py sell_car): not the car in use, not on auction,
            # not the last car, no parts on it; the grade's Sell (CloseSell for a car no longer sold) in Mito; the car
            # key and its drift shop items and stickers go with it
            car_id = int(req.get('car', 0))
            car = next((c for c in cars if c['id'] == car_id), None)
            if not car:
                return {'error': 'no_car'}
            if car_id == cur_car:
                return {'error': 'car_current'}
            if car_id in auction:
                return {'error': 'car_auction'}
            if len(cars) < 2:
                return {'error': 'car_last'}
            price = sell_price(car)
            if price is None:
                return {'error': 'no_sell'}
            # with = 'parts': the parts and drift items on the car are sold with it (their prices added);
            # with = 'car': they come off into the inventory first (a hyper / ultra part asks for its Heat Treatment Kit)
            mode = req.get('with')
            lines = sale_of(car_id)
            if lines and mode not in ('parts', 'car'):
                return {'error': 'car_parts'}
            extra = 0
            if mode == 'car':
                for x in [x for x in items if on_car(x) and x['car'] == car_id]:
                    if on_car(x):
                        why = take_off(x, bool(req.get('kit')))
                        if why:
                            return {'error': why}
                if has_vs:
                    cur.execute('UPDATE skid_vsitem_tb SET state = 0, carid = 0 WHERE serverid = %s AND cid = %s AND carid = %s',
                                (sid, cid, car_id))
            elif mode == 'parts':
                extra = sum(l['mito'] for l in lines)
                for l in lines:
                    if l['kind'] == 'part':
                        cur.execute('DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, l['inv']))
            price += extra
            cur.execute('DELETE FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car_id))
            cur.execute('UPDATE skid_character_tb SET numcar = numcar - 1 WHERE serverid = %s AND cid = %s AND numcar > 0', (sid, cid))
            cur.execute("DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND nrandom = %s AND itemid LIKE 'pc\\_%%'",
                        (sid, cid, car_id))
            for t in ('skid_vsitem_tb', 'skid_stitem_tb'):
                if one('SELECT 1 FROM information_schema.tables WHERE lower(table_name) = %s', (t,)):
                    cur.execute(f'DELETE FROM {t} WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car_id))
            cur.execute('UPDATE skid_character_tb SET gold = gold + %s WHERE serverid = %s AND cid = %s', (price, sid, cid))
            return {'mito': price}
        if act == 'use_car':
            car = int(req.get('car', 0))
            if car not in [c['id'] for c in cars]:
                return {'error': 'no_car'}
            if car in auction:
                return {'error': 'car_auction'}
            cur.execute('UPDATE skid_character_tb SET curcar = %s WHERE serverid = %s AND cid = %s', (car, sid, cid))
            return {}
        if not it:
            return {'error': 'no_item'}
        if (it['state'] & 0xffff) == 4:
            return {'error': 'item_auction'}
        i = it['info']
        if act == 'merge':
            # drag a pile onto another pile of the same item: as many as fit (the item's stack limit) go over
            to = next((x for x in items if x['inv'] == int(req.get('to', -1))), None)
            if not to or to is it:
                return {'error': 'no_item'}
            if to['id'] != it['id'] or on_car(it) or on_car(to) or (to['state'] & 0xffff) == 4:
                return {'error': 'no_merge'}
            room = max(0, int(i['stack'] or 1) - to['count'])
            if room <= 0 or int(i['stack'] or 1) <= 1:
                return {'error': 'stack_full'}
            n = min(room, it['count'])
            cur.execute('UPDATE skid_item_tb SET stacknum = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                        (to['count'] + n, sid, cid, to['inv']))
            if n < it['count']:
                cur.execute('UPDATE skid_item_tb SET stacknum = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (it['count'] - n, sid, cid, it['inv']))
            else:
                cur.execute('DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, it['inv']))
            return {'moved': n}
        if act == 'off':
            if not on_car(it):
                return {}
            why = take_off(it, bool(req.get('kit')))
            return {'error': why} if why else {}
        if act in ('sell', 'delete'):
            if on_car(it):
                return {'error': 'item_on_car'}
            if act == 'sell' and (it['id'].startswith('r_type_') or it['id'] in {v['model'] for v in D.cars.values()}):
                return {'error': 'no_sell'}
            n = max(1, min(it['count'], int(req.get('count') or it['count'])))
            if act == 'sell':
                cur.execute('UPDATE skid_character_tb SET gold = gold + %s WHERE serverid = %s AND cid = %s', (i['sell'] * n, sid, cid))
            if n < it['count']:
                cur.execute('UPDATE skid_item_tb SET stacknum = %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (it['count'] - n, sid, cid, it['inv']))
            else:
                cur.execute('DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, it['inv']))
            return {'mito': i['sell'] * n if act == 'sell' else 0}
        if act == 'on':
            car_id, slot = int(req.get('car', 0)), req.get('slot')
            car = next((c for c in cars if c['id'] == car_id), None)
            if not car:
                return {'error': 'no_car'}
            if car_id in auction:
                return {'error': 'car_auction'}
            if on_car(it):
                return {'error': 'item_on_car'}
            if it['upgrade'] < 0:
                return {'error': 'part_broken'}
            if i['level'] > level:
                return {'error': 'part_level'}
            if i['req_grade'] and car['grade'] < i['req_grade']:
                return {'error': 'part_grade'}
            mine = [x for x in items if on_car(x) and x['car'] == car_id]
            if i['kind'] in NEO_SLOTS:
                s = NEO_SLOTS[i['kind']]
                for old in [x for x in mine if slot_of(x) == s]:
                    place(old, 0, 0)
                place(it, car_id, s)
            elif i['type'] in SLOT_BASE:
                base = SLOT_BASE[i['type']]
                line = range(base, base + D.lines)
                taken = {slot_of(x) for x in mine if x['info']['type'] in SLOT_BASE}
                s = int(slot) if slot is not None and int(slot) in line else None
                if s is None or s in taken:
                    free = next((x for x in line if x not in taken), None)
                    if s is None:
                        s = free if free is not None else base
                    elif free is not None and s in taken:
                        pass                    # dropped on a full slot: replace it (as the game)
                old = next((x for x in mine if slot_of(x) == s and x['info']['type'] == i['type']), None)
                if old:
                    why = take_off(old, bool(req.get('kit')))
                    if why:
                        return {'error': why}
                place(it, car_id, s)
                if it['box'] and not it['id'].startswith('dock_'):
                    cur.execute('UPDATE skid_item_tb SET box = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, it['inv']))
                if i['grade'] in HEAT_GRADES and i['twin'].endswith('_b') and i['twin'] in D.parts:
                    swap_id(it, i['twin'])      # a hyper / ultra part becomes its scorched twin on the car
            elif i['type'] in OPTION_TYPES:
                if not D.option_parts:
                    return {'error': 'options_off'}
                s = int(slot) if slot is not None else None
                base = next((x for x in mine if x['info']['type'] in SLOT_BASE and (s is None or slot_of(x) == s)
                             and (i['type'] == 10 or OPTION_STAT[i['type']] == {0: 0, 1: 1, 2: 2, 3: 3}[x['info']['type']])
                             and i['grade'] in GRADE_FITS.get(x['info']['grade'], ())), None)
                if not base:
                    return {'error': 'option_no_part'}
                for old in [x for x in mine if slot_of(x) == slot_of(base) and x['info']['type'] in OPTION_TYPES]:
                    place(old, 0, 0)
                place(it, car_id, slot_of(base))
            else:
                return {'error': 'not_part'}
            return {}
        return {'error': 'unknown_command'}

    # cmd == 'inv': everything the window shows
    def points(car):
        up = D.upgrade.get((car['type'], car['grade'])) or {}
        base = [up.get('Speed', 0), up.get('Accel', 0), up.get('Crash', 0), up.get('Boost', 0)]
        extra = [0, 0, 0, 0]
        order = {0: 0, 2: 1, 1: 2, 3: 3}                   # part type -> speed, accel, crash, boost
        for x in items:
            if not on_car(x) or x['car'] != car['id']:
                continue
            t = x['info']['type']
            if t in SLOT_BASE:
                extra[order[t]] += x['info']['value'] + x['random']
            elif t in OPTION_STAT:
                extra[order[OPTION_STAT[t]]] += x['info']['value'] + x['random']
        return {'base': base, 'parts': extra, 'tank': up.get('Capacity', 0), 'efficiency': up.get('Efficiency', 0)}

    # the look of each car from its drift items (as the game draws it): paint / tint / neon colours, the body of an aero
    # set, wings, tires, roof items, air ducts, classic bumpers; the files are resolved here (SpoilerList / TireList for
    # the 2011 stat items, the aero set's own body from its text) so the 3D views only load and place them
    paints, tints, looks, pals = {}, {}, {}, {}
    if one("SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'skid_vsitem_tb'"):
        vis = D.visuals()
        wings, tires = D.look_lists()
        for item, car_id, state, data in rows('SELECT itemid, carid, state, item_data FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s',
                                              (sid, cid)):
            v = vis.get(str(item).strip())
            if int(state or 0) != 1 or not v:
                continue
            e = look_entry(v, str(data or ''), wings, tires, vis)
            looks.setdefault(int(car_id or 0), []).append(e)
            if v['cat'] in (1, 32) and e.get('pal'):
                pals[int(car_id or 0)] = e['pal']
            elif e.get('rgb') is not None and v['cat'] in (1, 32):
                paints[int(car_id or 0)] = e['rgb']
            if e.get('rgb') is not None and v['cat'] == 3:
                tints[int(car_id or 0)] = e['rgb']

    # a timed car upgrade on a car (category 38, "V4 car upgrade (7days)"): the car is that V while it lasts, as the game
    # counts it (dcemu records.Car.grade = max(grade, boost_grade)); shown at once after the purchase
    boost = {}
    for d in (load_drift() if has_vs else []):
        if d['cat'] == 38 and d['on'] and d['car'] and (d['period'] == 0 or (d['left'] or 0) > 0):
            boost[d['car']] = max(boost.get(d['car'], 0), D.upgrade_grade(d['id']))
    out_cars = []
    for c in cars:
        c = dict(c, base_grade=c['grade'], grade=max(c['grade'], boost.get(c['id'], 0)))
        info = D.cars.get(c['type'], {})
        out_cars.append(dict(c, name=info.get('name', f"#{c['type']}"), model=info.get('model', '').lower(), current=c['id'] == cur_car, auction=c['id'] in auction,
                             points=points(c), tire=D.tires.get(info.get('tire', ''), ''), tire_scale=info.get('tire_scale', [660, 660]),
                             tire_width=info.get('tire_width', [1, 1]), v=info.get('lvl', 0), sell=sell_price(c),
                             parts_on=any(on_car(x) and x['car'] == c['id'] for x in items),
                             paint=paints.get(c['id']), paintPal=pals.get(c['id']), tint=tints.get(c['id']), look=looks.get(c['id'], []),
                             sale=[{k: l[k] for k in ('kind', 'name', 'mito')} for l in sale_of(c['id'])]))
    return {'inv': {'level': level, 'mito': gold, 'lines': D.lines, 'option_parts': D.option_parts, 'cars': out_cars,
                    'items': [{'inv': x['inv'], 'id': x['id'], 'name': x['info']['name'], 'kind': x['info']['kind'],
                               'type': x['info']['type'], 'grade': x['info']['grade'], 'level': x['info']['level'],
                               'value': x['info']['value'] + x['random'], 'sell': x['info']['sell'], 'count': x['count'],
                               'car': x['car'] if on_car(x) else 0, 'slot': slot_of(x) if on_car(x) else 0,
                               'auction': (x['state'] & 0xffff) == 4, 'broken': x['upgrade'] < 0,
                               'heat': bool(on_car(x) and needs_heat(x)), 'desc': D.desc(x['id']), 'alt': D.box_icons(x['id']),
                               'stack': x['info']['stack']} for x in items],
                    'drift': load_drift()}}


def catalog():
    """every car, part, usable item and drift item the server knows, for the launcher's GM panel."""
    D = Data()
    cars = sorted(({'type': k, 'name': v['name'], 'model': v['model'].lower(), 'lvl': v['lvl'], 'tire': D.tires.get(v.get('tire', ''), ''),
                    'tire_scale': v.get('tire_scale'), 'tire_width': v.get('tire_width')} for k, v in D.cars.items()
                   if v['model']), key=lambda c: c['name'].lower())
    parts, use = [], []
    for iid, r in D.parts.items():
        if r[4] in ('', 'n/a'):
            continue
        parts.append({'id': iid, 'name': r[4], 'kind': r[0], 'grade': r[6], 'level': num(r[7]), 'value': num(r[9])})
    for iid, r in D.use.items():
        if r[2] in ('', 'n/a'):
            continue
        use.append({'id': iid, 'name': r[2], 'kind': r[1]})
    drift, seen = [], set()
    try:
        for v in read_xlt(os.path.join(D.base, 'Init', 'VShopItem.xlt'))[3:]:
            if len(v) > 9 and v[3].strip() and v[1].strip() == '1' and v[3].strip().lower() not in seen:
                seen.add(v[3].strip().lower())
                drift.append({'id': v[3].strip(), 'name': v[4].strip() or v[3].strip(), 'kind': v[9].strip()})
    except OSError:
        pass
    key = lambda x: x['name'].lower()
    return {'catalog': {'cars': cars, 'parts': sorted(parts, key=key), 'use': sorted(use, key=key), 'drift': drift}}
