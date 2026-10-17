"""Server tables in the 2011 client's formats.

The native server reads the tables the way the 2011 client has them: .xlt (UTF-16, tab
separated, header lines then rows) and .tdf (a placeholder bitmap, then a string table). The
files come from the client's effective data (Server/tools/client_tables.py: Data_US over Data,
patch packs over archives), copied to the data directory by tools/sync_data.py, so the server
does not read the client folder at run time.

Data only the server has (no 2011 version exists, the client does not carry it) comes from the
2008 server's folder, [native] server_data in emulator.ini: LevelServer.tdf (exp per level),
Contents.ini (feature switches), adminlist.txt.

Indices the client uses to name table rows (they must match the 2011 client's own tables):
  item TableIdx    ItemClient.tdf row, or 749 + UseItemClient.tdf row (749 = ItemClient rows)
  quest TableIdx   QuestClient.tdf row
  visual TableIdx  VisualItem.xlt unique id (column 4)
"""
import os
import re
import struct
from dataclasses import dataclass


def read_xlt(path):
    """-> list of lines, each a list of cells."""
    with open(path, 'rb') as f:
        text = f.read().decode('utf-16-le').lstrip('﻿')
    return [line.split('\t') for line in text.split('\r\n')]


def read_tdf(path):
    """-> rows (lists of strings)."""
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


# city id -> the name in World/Icon_<name>_Client.tdf. 1 = Moon Palace (the tutorial's city; its
# Station 1 is where the 2008 server put a character coming from the driver dome); the others by
# the order of the cities in the game *(guess)*.
CITY_ICONS = {1: 'Moonpalace', 2: 'Koinonia', 3: 'Craspeda', 4: 'Oros', 5: 'Taipei'}   # Taipei (Mitro City): map 4, its quest posts post_5th_*


def _stations(rows):
    """Icon table rows (id, name, "(x,y,z)", shown, ...) -> {n: (x, y, z)} for the "Station n" rows."""
    out = {}
    for r in rows:
        if len(r) > 2 and r[1].startswith('Station ') and r[1][8:].strip().isdigit():
            out[int(r[1][8:])] = tuple(float(v) for v in r[2].strip('()').split(','))
    return out


# XiStrItem.Type (2008 ItemTypeStrToVar 0x59ae40 for the part kind in column 0; usable items are type 5).
# 2011 adds the docking parts (dock_A/B/C/S/D: "docking onto the ... Parts"), unknown to the 2008
# server (its fallback 10); here type 11.
PART_TYPES = {'speed': 0, 'crash': 1, 'accel': 2, 'boost': 3, 'op_S': 4, 'op_C': 6, 'op_A': 7, 'op_B': 8, 'op_F': 9}
USE_TYPE, DOCK_TYPE = 5, 11
# EU part requirements (nation rule part_grade; user, 2026-10-17): the car's V grade a part needs when ItemClient
# column 8 is empty. Parts: their grade's first V grade (N 1, S 4, H 7) + 0 / 1 / 2 by tier: the normal parts
# (speed / accel / crash / boost, no set) have five levels per grade (N 1 7 13 19 25, S 31 .. 55, H 60 .. 80) ->
# + 0 0 1 1 2 (best N V3, best S V6, best H V9); set / shop / rental parts take the tier of the highest normal level
# not above their own. Options (FN / FS / FH) and docking parts (ON / OS / OH): the grade's first V grade.
GRADE_BASE = {'N': 1, 'S': 4, 'H': 7}
BASE_PARTS = ('speed', 'accel', 'crash', 'boost')


def part_tiers(rows):
    """ItemClient rows -> {grade letter: sorted levels of the normal parts (no set)}."""
    tiers = {}
    for r in rows:
        if len(r) > 7 and r[0] in BASE_PARTS and r[1] == 'n/a' and r[6] in GRADE_BASE:
            tiers.setdefault(r[6], set()).add(_num(r[7]))
    return {k: sorted(v) for k, v in tiers.items()}


def part_grade_rule(kind, grade, req_level, tiers):
    """The EU rule above for one item (column 0 kind, column 6 grade, column 7 level) -> V grade, 0 = none. Also
    written into the EU client's own ItemClient.tdf (tools/eu_client.py grades: its tooltip shows the grade)."""
    if len(grade) == 2 and grade[0] in 'FO' and grade[1] in GRADE_BASE:      # options, docking parts
        return GRADE_BASE[grade[1]]
    if kind not in BASE_PARTS or grade not in GRADE_BASE:
        return 0
    levels = tiers.get(grade) or [req_level]
    pos = max((k for k, lv in enumerate(levels) if lv <= req_level), default=0)
    return GRADE_BASE[grade] + pos * 3 // len(levels)
USE_STACK = 99           # usable items stack to UseItem column 5, 99 when empty (the 2008 loader)


@dataclass
class Visual:
    """A VisualItem.xlt row: unique id (the client's TableIdx), item id, category index (1 Paint, 2 Neon,
    3 Window Color, 11 Decal, 32 GrossPaint, 7 Spoiler, ...), name, the car types it fits ("Exist")."""
    uid: int
    item_id: str
    category: int
    name: str
    cars: frozenset
    index: int = 0           # its number inside the category (column "index", from 1)
    value: str = ''          # column 6: what it gives ("i_n_00058 10" = 10 x that item, Mito, a passive id, ...)


@dataclass
class ItemInfo:
    """An item row: ItemClient.tdf (id 2, kind 0, cost 12, sell 13, shop 15) or UseItemClient.tdf
    (id 0, use kind 1, cost 7, sell 8, shop 13, stack 5)."""
    table_idx: int
    item_id: str
    kind: str
    type: int
    cost: int
    sell: int
    shop: bool
    stack_max: int
    grade: str = ''          # ItemClient column 6: N S H E (parts), FN.. FE / ON.. OE (options, docking)
    req_level: int = 0       # ItemClient column 7
    req_grade: int = 0       # ItemClient column 8 (the car's V grade a part needs: nation.part_allowed)
    value: int = 0           # UseItemClient column 9 (e.g. 30 points), usable items
    time: int = 0            # UseItemClient column 10 (seconds)
    reward: str = ''         # UseItemClient column 3: its RewardGroup.xlt group (gift boxes, lucky bags, lotteries)
    name: str = ''           # ItemClient column 4 / UseItemClient column 2 (the shown name)
    extra: str = ''          # UseItemClient column 4 (Gotcha key parts: the RewardGroup of the parts it needs)
    tradeable: bool = True   # ItemClient column 17 / UseItemClient column 15 (False: rental and hyper parts, coupons,
                             # ...; car keys are True: they go with the car in a car auction)


def _num(x, cast=int):
    try:
        return cast(float(x))
    except ValueError:
        return 0


class Tables:
    def __init__(self, root, server_data=None, admin_list=None):
        self.root = root
        self.server_data = server_data
        self.upgrade = {}        # (car type id, grade level) -> dict(accel, speed, crash, boost, efficiency, capacity)
        self._vehicle_upgrade()
        self.item_index = {}     # item id -> TableIdx
        self.items = {}          # item id -> row (ItemClient) for parts
        self._items()
        self.visual_index = {}   # visual item id -> unique id
        self.visuals = {}        # unique id -> Visual (VisualItem.xlt: category index, item id, cars it fits)
        vi = read_xlt(self._p('Init', 'VisualItem.xlt'))
        car_cols = [(i, int(c)) for i, c in enumerate(vi[2]) if i >= 7 and c.strip().isdigit()]
        for r in vi[4:]:
            if len(r) > 4 and r[3] and r[4].strip().isdigit():
                uid = int(r[4])
                self.visual_index[r[3]] = uid
                self.visuals[uid] = Visual(uid, r[3], _num(r[1]), r[5],
                                           frozenset(t for i, t in car_cols if i < len(r) and r[i].strip() == '1'),
                                           _num(r[2]), r[6].strip() if len(r) > 6 else '')
        self.vshop = {}          # VShopItem.xlt UniqueId -> {column name: value}
        vs = read_xlt(self._p('Init', 'VShopItem.xlt'))
        for r in vs[3:]:
            if len(r) > 3 and r[2].strip().isdigit():
                self.vshop[int(r[2])] = {n: r[i].strip() for i, n in enumerate(vs[2]) if n and i < len(r)}
        self.vehicles = {}       # car type (Unique Id) -> VehicleList.xlt row as {column name: value}
        vl = read_xlt(self._p('Init', 'VehicleList.xlt'))
        names = vl[3]
        for r in vl[4:]:
            if len(r) > 12 and r[9].strip().isdigit():
                self.vehicles[int(r[9])] = {n: r[i].strip() for i, n in enumerate(names) if n and i < len(r)}
        self.car_coupons = {}    # car type -> coupon item id (Coupon.xlt: car Unique ID col 6, coupon id col 7)
        for r in read_xlt(self._p('Init', 'Coupon.xlt'))[4:]:
            if len(r) > 7 and r[6].strip().isdigit() and r[7].strip():
                self.car_coupons[int(r[6])] = r[7].strip()
        self.quest_index = {}    # quest id -> TableIdx (QuestClient.tdf row)
        self.stations = {}       # city id -> {station number: (x, y, z)} (the city map icons)
        self.icons = []          # (map, x, y, z) by icon index: the icon tables' rows, Moon Palace first (XiIconTable)
        self.icon_index = {}     # icon (post) id -> icon index
        for m, (city, name) in enumerate(sorted(CITY_ICONS.items())):
            path = os.path.join(self.server_data, f'Icon_{name}_Client.tdf')
            if os.path.exists(path):
                rows = read_tdf(path)
                self.stations[city] = _stations(rows)
                for r in rows:
                    self.icon_index.setdefault(r[0], len(self.icons))
                    try:
                        self.icons.append((m, *(float(v) for v in r[2].strip('()').split(','))))
                    except (IndexError, ValueError):
                        self.icons.append((m, 0.0, 0.0, 0.0))
        self.jobs = read_tdf(os.path.join(self.server_data, 'ArbeitClient.tdf'))     # part-time jobs, by TableIdx (row)
        self.quests = read_tdf(os.path.join(self.server_data, 'QuestClient.tdf'))   # by TableIdx (row)
        self.quest_index = {r[0]: i for i, r in enumerate(self.quests)}
        self.huvs = []           # HuvTable.tdf rows (HUV chases; columns as ChaseTable::ReloadChaseTable reads them)
        for r in read_tdf(os.path.join(self.server_data, 'HuvTable.tdf')):
            if len(r) > 19 and r[0].strip().isdigit():
                self.huvs.append(dict(
                    level=_num(r[0]), id=_num(r[1]), name=r[2], rate=_num(r[3], float), ea=_num(r[4]),
                    speed=_num(r[5], float), max_speed=_num(r[6], float), nos_accel=_num(r[7], float),
                    nos_time=_num(r[8], float), nos_refresh=_num(r[9], float), durability=_num(r[10], float),
                    avoid_front_player=_num(r[13], float), avoid_front_traffic=_num(r[14], float),
                    avoid_rear_player=_num(r[15], float), exp=_num(r[16]), money=_num(r[17]), item_group=r[18].strip(),
                    drop_rate=_num(r[19], float)))
        self.instants = read_tdf(os.path.join(self.server_data, 'Instant_Client.tdf'))  # instant missions, by TableIdx (row)
        self.level_exp = []      # exp needed for level n+1 at [n-1]
        self.contents = {}       # Contents.ini name -> int
        self.admins = set()
        if server_data:
            self.level_exp = [int(r[1]) for r in sorted(read_tdf(os.path.join(server_data, 'LevelServer.tdf')),
                                                        key=lambda r: int(r[0]))]
            for line in open(os.path.join(server_data, 'Contents.ini'), encoding='utf-8', errors='replace'):
                k, eq, v = line.partition('=')
                if eq and v.strip().lstrip('-').isdigit():
                    self.contents[k.strip()] = int(v)
        self.combo_exp = []      # exp per combo for level n at [n-1] (comboexp.txt)
        self.drops = []          # (level, group, (rates of drop modes 0-5, %)) from ItemDropServer.tdf
        self.instant_drops = []  # (level, [drop group x 4]) from InstantDrop_Server.tdf
        self.drop_groups = {}    # drop group -> [item TableIdx] (ItemServer.tdf col 3, UseItemServer.tdf col 3)
        if server_data:
            self._drops(server_data)
        # race rewards (PvpTrackTable::LoadPvpExp; the 2008 server's own files, next to its exe)
        self.pvp_exp_base, self.pvp_money_rate = [], []   # [rank - 1][16 - racers]
        self.pvp_exp_rate, self.pvp_money_base = [], []   # [PvP channel - 1], [car grade - 1]
        if server_data:
            self._pvp(os.path.join(server_data, '..'))
        self.server_text = {}    # GlobalText_Server.xlt key -> the US text (error messages, Send_Error)
        if server_data:
            path = os.path.join(server_data, '..', 'Localize', 'GlobalText_Server.xlt')
            if os.path.exists(path):
                for r in read_xlt(path)[3:]:
                    if len(r) > 5 and r[3]:
                        self.server_text[r[3]] = r[5]
        if admin_list and os.path.exists(admin_list):
            self.admins = {l.strip().lower() for l in open(admin_list, encoding='utf-8', errors='replace') if l.strip()}

    def _pvp(self, folder):
        def numbers(name):
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                return []
            return [[float(v) for v in line.split()] for line in open(path, encoding='utf-8', errors='replace')
                    if line.strip()]
        self.pvp_exp_base, self.pvp_money_rate = numbers('pvpexpbase.txt'), numbers('pvpmoneyrate.txt')
        self.pvp_exp_rate = [r[0] for r in numbers('pvpexprate.txt')]
        self.pvp_money_base = [r[0] for r in numbers('pvpmoneybase.txt')]

    def pvp_reward(self, rank, racers, channel, grade):   # channel: the section's exp multiplier
        """(exp, Mito) of a race (BS_Room::PvpRaceResult, PvpTrackTable::GetPvpMoney). The tables have a
        row per rank and a column per number of racers, 16 down to 2: one racer alone gets nothing."""
        def cell(table):
            col = 16 - racers
            if 1 <= rank <= len(table) and 0 <= col < len(table[rank - 1]):
                return table[rank - 1][col]
            return 0.0
        rate = channel          # the section's exp multiplier (emulator.ini [battlezone]; 2008: pvpexprate.txt)
        base = self.pvp_money_base[max(1, min(grade, 9)) - 1] if len(self.pvp_money_base) >= 9 else 0.0
        return int(cell(self.pvp_exp_base) * rate), int(base * cell(self.pvp_money_rate))

    def _drops(self, server_data):
        path = os.path.join(server_data, '..', 'comboexp.txt')
        if os.path.exists(path):
            self.combo_exp = [_num(l.strip(), float) for l in open(path, encoding='utf-8', errors='replace') if l.strip()]
        path = os.path.join(server_data, 'ItemDropServer.tdf')
        if os.path.exists(path):
            # level, group, then 3 x (rates of drop modes 0-5) for the play-time blocks (0, 4 h, 12 h:
            # GetDropRateOfMode); the first block is used. Modes: 1 traffic item, 2 combo, 3 rush HUV hit.
            self.drops = [(_num(r[0]), r[1], tuple(_num(x, float) for x in r[2:8])) for r in read_tdf(path) if len(r) > 7]
        path = os.path.join(server_data, 'InstantDrop_Server.tdf')
        if os.path.exists(path):          # level, then the drop groups for 50 / 100 / 150 / 160 patrolled places
            self.instant_drops = sorted((_num(r[0]), r[1:5]) for r in read_tdf(path) if len(r) > 4)
        for name, id_col in (('ItemServer.tdf', 2), ('UseItemServer.tdf', 0)):
            path = os.path.join(server_data, name)
            if os.path.exists(path):
                for r in read_tdf(path):
                    if len(r) > 3 and r[3].startswith('ig_') and r[id_col] in self.item_index:
                        self.drop_groups.setdefault(r[3], []).append(self.item_index[r[id_col]])
        self._client_patrol_drops()

    def _client_patrol_drops(self):
        """The 2011 client's patrol reward texts (World/InstantDrop_Client.tdf: level, "There are no item rewards." /
        "Acquire a Lvl N part for every 50 locations patrolled.") decide the parts of the 50 / 100 / 150 places: none
        at levels 4-7 (the 2008 table gave Lvl 7 parts), Lvl 65 parts from level 67 (the 2008 table stops at Lvl 60).
        Lvl N = the 2008 group ig_p_N, else the crash / accel / boost parts of level N (as the 2008 groups are made).
        The 160th place keeps the 2008 group (ig_n_F car upgrade coupons). No prize for completing: none in the
        client's tables (the completion message 0x3e5 could carry items, client 0x514120)."""
        path = os.path.join(self.server_data, 'InstantDrop_Client.tdf')
        if not os.path.exists(path):
            return
        old = self.instant_drops
        self.instant_drops = []
        for r in read_tdf(path):
            if len(r) < 2 or not r[0].isdigit():
                continue
            level, m = int(r[0]), re.search(r'Lvl\.? *(\d+) part', r[1])
            if not m:
                self.instant_drops.append((level, [None] * 4))
                continue
            group = f'ig_p_{m[1]}'
            if group not in self.drop_groups:
                self.drop_groups[group] = [
                    idx for iid, idx in self.item_index.items() if re.fullmatch(r'i_[cab]_\d+', iid)
                    and (i := self.item_info(idx)) and i.req_level == int(m[1])]
            last = next((g for lv, g in reversed(old) if lv <= level), old[-1][1] if old else [None] * 4)
            self.instant_drops.append((level, [group] * 3 + [last[3] if len(last) > 3 else None]))
        self.instant_drops.sort()

    def instant_drop(self, level):
        """-> the patrol drop groups for a level (the row of the highest level not above it)."""
        return next((g for lv, g in reversed(self.instant_drops) if lv <= level), self.instant_drops[0][1] if self.instant_drops else [])

    def drop_rates(self, level):
        """-> [(group, rates)] for a level: the rows of the highest table level not above it."""
        lv = max((l for l, _, _ in self.drops if l <= level), default=None)
        return [(g, r) for l, g, r in self.drops if l == lv]

    def drop_rates_of_grade(self, grade):
        """-> [(group, rates)] for a car's V grade (nation rule drop_by_grade): the table's levels in order, V1 the
        first (1, 5, 11, 21, 31, 41, 51, 61, 71 for V1-V9); a grade past the last level takes the last."""
        levels = sorted({l for l, _, _ in self.drops})
        if not levels:
            return []
        lv = levels[max(1, min(grade, len(levels))) - 1]
        return [(g, r) for l, g, r in self.drops if l == lv]

    def _p(self, *parts):
        return os.path.join(self.root, *parts)

    def _vehicle_upgrade(self):
        lines = read_xlt(self._p('Init', 'VehicleUpgrade.xlt'))
        names = lines[2]
        col = {n: i for i, n in reversed(list(enumerate(names)))}
        for r in lines[3:]:
            if len(r) <= col['GradeLvl'] or not r[col['ID']].strip().isdigit():
                continue
            key = (int(r[col['ID']]), _num(r[col['GradeLvl']]))
            self.upgrade[key] = {k.lower(): _num(r[col[k]], float if k == 'Efficiency' else int)
                                 for k in ('Accel', 'Speed', 'Crash', 'Boost', 'Efficiency', 'Capacity')}
            self.upgrade[key].update(price=_num(r[col['Price']]), sell=_num(r[col['Sell']]),
                                     req_level=_num(r[col['Req Level']]), upgrade_mito=_num(r[col['UpgradeMito']]),
                                     options=r[col['OptionID']].strip(), condition=r[col['UpgradeCon']].strip())

    def _items(self):
        parts = self._part_rows = read_tdf(os.path.join(self.server_data, 'ItemClient.tdf'))
        for i, r in enumerate(parts):
            self.item_index[r[2]] = i
            self.items[r[2]] = r
        self._use_rows = read_tdf(os.path.join(self.server_data, 'UseItemClient.tdf'))
        for i, r in enumerate(self._use_rows):
            self.item_index.setdefault(r[0], len(parts) + i)

    def part_req_grade(self, info):
        """-> the car V grade a part, option or docking part needs (0: none): ItemClient column 8, else the EU rule
        above (GRADE_BASE)."""
        if info.req_grade:
            return info.req_grade
        tiers = getattr(self, '_part_tiers', None)
        if tiers is None:
            tiers = self._part_tiers = part_tiers(self._part_rows)
        return part_grade_rule(info.kind, info.grade or '', info.req_level, tiers)

    def item_info(self, table_idx):
        """-> ItemInfo of an item by its TableIdx (ItemClient.tdf rows, then UseItemClient.tdf), or None."""
        parts, use = self._part_rows, self._use_rows
        if 0 <= table_idx < len(parts):
            r = parts[table_idx]
            return ItemInfo(table_idx, r[2], r[0], PART_TYPES.get(r[0], DOCK_TYPE if r[0].startswith('dock_') else 10),
                            _num(r[12]), _num(r[13]), r[15] == 'True', 1, r[6], _num(r[7]), req_grade=_num(r[8]), name=r[4],
                            tradeable=len(r) > 17 and r[17] == 'True')
        k = table_idx - len(parts)
        if 0 <= k < len(use):
            r = use[k]
            return ItemInfo(table_idx, r[0], r[1], USE_TYPE, _num(r[7]), _num(r[8]), r[13] == 'True',
                            _num(r[5]) or USE_STACK, value=_num(r[9]), time=_num(r[10]),
                            reward=r[3] if r[3] != 'n/a' else '', name=r[2], tradeable=len(r) > 15 and r[15] == 'True',
                            extra=r[4] if r[4] != 'n/a' else '')
        return None

    def mitron_capacity(self, car_type, grade=1):
        u = self.upgrade.get((car_type, grade))
        return u['capacity'] if u else None

    def car_stats(self, car_type, grade):
        """-> (speed, crash, accel, boost) of a car grade (VehicleUpgrade.xlt)."""
        u = self.upgrade.get((car_type, grade))
        return (u['speed'], u['crash'], u['accel'], u['boost']) if u else (0, 0, 0, 0)

    PART_STAT = {'speed': 0, 'crash': 1, 'accel': 2, 'boost': 3}

    def part_stat(self, item_id):
        """-> (stat index 0-3, value) of a car part (ItemClient.tdf: kind @0, value @9), or None."""
        r = self.items.get(item_id)
        if not r or r[0] not in self.PART_STAT:
            return None
        return self.PART_STAT[r[0]], _num(r[9])

    def exp_bounds(self, level):
        """-> (exp at this level, exp at the next): LevelServer.tdf holds the exp for each level."""
        base = sum(self.level_exp[:level - 1])
        return base, base + (self.level_exp[level - 1] if 0 < level <= len(self.level_exp) else 0)
