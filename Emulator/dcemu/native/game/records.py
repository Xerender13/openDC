"""The game service's records in the 2011 client's layouts.

The 2008 layouts are from ZoneServer.pdb (Server/tools/dev/pdbtypes.py); the 2011 changes were
found from the client's handlers and are described in dcemu/handlers/game.py and vshop.py (the
proxy translations). Fields the 2011 client added and we do not know yet are sent as 0.
"""
import struct
from dataclasses import dataclass, field

NAME_BYTES = 0x2a            # XiStrCharName: 20 UTF-16 characters + terminator
CHAR_2011 = 0x11b            # XiStrCharInfo: 2008 0xe9, 8 new bytes @0x95, 12 @0xcd, 30 at the end
CAR_2011 = 0x31              # XiStrCarInfo: 2008 0x2d, 4 new bytes @0x24
ITEM_2011 = 0x5c             # XiStrMyItem: 2008 0x34, 36 new bytes @0x2c, 4 at the end
VSITEM_2011 = 0x74           # XiStrMyVSItem: 2008 0x30, PlateName 20 -> 40, 48 new bytes at the end
STAT_2011 = 0x68             # XiStrStatInfo: 2008 0x50, 6 new longs at the end (combat values: Stats.combat)
BONUS_2011 = 0x28            # XiStrEnChantBonus: 2008 0x24, 4 new bytes at the end


def wstr(text, size):
    return (text or '').encode('utf-16-le')[:size - 2].ljust(size, b'\0')


def name_bytes(name):
    return wstr(name, NAME_BYTES)


@dataclass
class Car:
    car_id: int
    car_type: int
    color: int
    grade: int
    auction_cnt: int
    mitron: float
    km: float
    slot: int
    capacity: float = 0.0
    efficiency: float = 0.0
    paint: int = 0           # 0x83RRGGBB while a drift shop paint is on the car (Player.apply_paints), else 0
    tint: int = 0            # 0x82RRGGBB while a window tint is on the car, else 0 (the client's grey glass)
    on_auction: bool = False  # registered in the car auction (XiStrCarInfo AuctionOn; auction.py)
    boost_grade: int = 0     # a timed car upgrade drift item on the car (V4 car upgrade (7days)): the grade it gives

    def shown_grade(self):
        """The grade the car counts as: its own, or a higher one from a timed upgrade item on it (Player.apply_paints)."""
        return max(self.grade, self.boost_grade)

    def shown_color(self):
        """The colour the client draws: the paint on the car, else the dealership colour (SKID_CAR_TB)."""
        return self.paint or self.color

    def unit(self):
        """XiStrCarUnit (32 bytes)"""
        return struct.pack('<6I2f', self.car_id, self.car_type, self.shown_color(), self.shown_grade(), self.slot,
                           self.auction_cnt, self.mitron, self.km)

    def encode(self):
        # 2011 +0x24 (new): a colour the client applies after building the car with Color and the default
        # glass 0x82CCCCCC (client 0x708054..0x708086, with Etc.ColorSetReform): the window tint here.
        return self.unit() + struct.pack('<II2f?', self.shown_color(), self.tint, self.capacity, self.efficiency, self.on_auction)


@dataclass
class Character:
    cid: int
    name: str
    member: str
    last_date: int
    avatar: int
    level: int
    exp: int                 # current exp (NEXP)
    exp_next: int            # exp at the next level
    exp_base: int            # exp at this level
    mito: int
    team_id: int
    team_mark: int
    team_name: str
    team_rank: int
    ptype: str
    pvp: tuple               # count, wins, points
    tpvp: tuple
    quick_cnt: int
    km: float
    pos: tuple               # x, y, z, w
    last_area: int
    city: int
    pos_state: int
    cur_car: int
    quick_slots: tuple       # the 4 field quick slots (item TableIdx, 0 = empty): game/quickslot.py
    team_dates: tuple        # join, close, leave (time_t)
    hancoin_inven: int
    hancoin_garage: int
    flags: int
    guild: int
    mileage: int
    cars: list = field(default_factory=list)
    part_inven_idx: int = 0  # PARTINVENIDX: the last inventory index given to a new item

    def encode(self):
        """XiStrCharInfo, 2011 layout (0x11b bytes)."""
        a = (struct.pack('<q', self.cid) + name_bytes(self.name)
             + struct.pack('<iHH3IqqQ', self.last_date, self.avatar, self.level,
                           self.exp, self.exp_next, self.exp_base, self.mito, self.team_id, self.team_mark)
             + wstr(self.team_name, 26)
             + struct.pack('<ic6I', self.team_rank, self.ptype.encode('ascii')[:1] or b'N',
                           *self.pvp, *self.tpvp))
        b = struct.pack('<If4f4i2I', self.quick_cnt, self.km, *self.pos, self.last_area, self.city,
                        self.pos_state, self.cur_car, *self.quick_slots[:2])
        c = struct.pack('<3i2iiiq', *self.team_dates, self.hancoin_inven, self.hancoin_garage, self.flags,
                        self.guild, self.mileage)
        assert len(a) == 0x95 and len(a) + 8 + len(b) == 0xcd
        # 2011: 8 new bytes @0x95 (QuickCnt @0x9d: race reward handler 0x514b21), and 12 more before the
        # last fields: the client reads two longs @0xe5 / 0xe9 (HancoinInven / HancoinGarage), Flags @0xed
        # (0x5a39e3 tests 0x4000000 = battle tutorial done; sent 12 bytes early, the battle zone asked
        # about the tutorial at every visit: user, 2026-10-13) and @0xf1 (Guild). Where exactly between
        # QuickSlot2 and HancoinInven the 12 bytes sit is not known (the team dates there are 0 anyway); their first
        # 8 are quick slots 3 and 4 (@0xcd / @0xd1: the 0x7c handler 0x5278c3 restores the slots from @0xc5-0xd1).
        out = a + bytes(8) + b + struct.pack('<2I', *self.quick_slots[2:4]) + bytes(4) + c
        assert len(out) == 0xfd
        return out + bytes(CHAR_2011 - len(out))


@dataclass
class Item:
    gid: int
    inven_idx: int
    item_id: str
    car_id: int
    stack: int
    random: int
    state: int
    upgrade: int
    belonging: int
    assist_a: str
    assist_b: str
    box: int
    ctime: int
    table_idx: int = -1
    expire_tick: int = 0
    cdate: object = None        # SKID_ITEM_TB.CDATE (datetime, UTC): when the item was made (setparts.start_expiry)

    def encode(self):
        """XiStrMyItem, 2011 layout (0x5c bytes), from the client's tooltip 0x5c9370 (record at its struct + 0x52):
        @0 CarID, @4 state, @8 stack, @0xc random bonus, @0x10 .. @0x34 ten assist slots (Assist_Client row + 1;
        the 2008 Box / Belonging / Upgrade / UpgradePoint / ExpireTick places are assist slots now: values sent
        there showed as purple tooltip lines), @0x38 Box (non-zero: the parts box icon and untradeable; user: a gauge
        value sent in @0x38 and @0x3c showed both, and the gauge filled), @0x3c unknown (the gauge sent here did
        not fill it, nor @0x24 / @0x4c), @0x40 enhancement level
        (< 0 = broken: the tooltip prints it negated), @0x44 the stat bonus the client adds to the part's value
        (enhancement bonus; a docking item's white points), @0x48 ExpireTick (server-tick hours, items with a
        table period), @0x4c Belonging (guess), @0x58 fail gauge (being tested), @0x50 TableIdx,
        @0x54 InvenIdx."""
        from .. import context
        dock = self.item_id.startswith('dock_')
        assist = 0
        if dock and self.assist_a:                  # docking: the purple points' docking_b assist (index from 1)
            from .docking import assists
            assist = assists()[0].get(self.assist_a, 0)
        bonus_points = self.box or 0 if dock else 0
        if not dock and self.upgrade > 0:
            from .upgrade import bonus
            info = context.data.item_info(self.table_idx)
            bonus_points = bonus(info.grade, self.upgrade) if info else 0
        expire = 0
        if self.ctime:
            from .setparts import period
            expire = self.ctime if period(self) else 0
        head = struct.pack('<IIii', self.car_id, self.state, self.stack, self.random)
        second = 0
        if not dock and (self.assist_a or self.assist_b):   # converted options (convert.py)
            from .convert import assist_index
            assist, second = assist_index(self.assist_a), assist_index(self.assist_b)
        assists_ = struct.pack('<II', assist, second) + bytes(32)
        box = 0 if dock else self.box             # a docking item's BOX column holds its white points
        tail = struct.pack('<IIiiIIII4x', box, 0, self.upgrade, bonus_points, expire, self.belonging, self.table_idx,
                           self.inven_idx)
        return head + assists_ + tail

    def data(self):
        """XiStrIData: InvenIdx + 32 bytes of item data (the ASSIST_A text, as the 2008 server)."""
        text = '' if self.item_id.startswith('dock_') else (self.assist_a or '')   # docking: the assist is in the record
        return struct.pack('<I', self.inven_idx) + text.encode('latin-1', 'replace')[:31].ljust(32, b'\0')


@dataclass
class VisualItem:
    gid: int
    item_id: str
    inven_idx: int
    car_id: int
    state: int
    data: str
    period: int
    ctime: int
    utime: int
    table_idx: int = 0
    on_current_car: bool = False    # on the car being driven (Player.apply_paints): equippable PassiveAssist items

    def plate(self):
        t = (self.data or '').rstrip('\0')   # as the client sent it (vshop.item_text)
        return wstr(t if t.strip() else '', 40)

    def encode(self):
        return (struct.pack('<iiII', self.car_id, self.state, self.table_idx, self.inven_idx) + self.plate()
                + struct.pack('<iii', self.period, self.utime, self.ctime) + self.assist_slots())

    def assist_slots(self):
        """The 48 bytes new in 2011 (@0x44): @0x4c ten assist slots (Assist_Client row + 1), which the client
        applies for a drift item on the current car (client 0x7295a2) and for a category 40 / 41 item in any
        state (0x72961f; twice if such an item were also on the car). An item whose VisualItem value is an assist
        id (PassiveAssist items "passive_a_00118", the old tints) carries that assist in the first slot."""
        from .. import context
        out = bytearray(VSITEM_2011 - 0x44)
        vis = context.data.visuals.get(self.table_idx) if context.data else None
        from .convert import assist_index
        slots = []
        from ..game.driftuse import EQUIP_PASSIVE
        if self.item_id in EQUIP_PASSIVE and not self.on_current_car:
            pass                        # equippable PassiveAssist: no effect unless on the car being driven
        elif vis and vis.value and assist_index(vis.value):
            slots.append(assist_index(vis.value))
        bonus = context.data.vshop.get(self.table_idx, {}).get('Bonus Assist', '') if context.data else ''
        if assist_index(bonus):         # VShopItem "Bonus Assist" (booster max speed, parts drop chance, ...): the
            slots.append(assist_index(bonus))   # client applies the slots of the items on the current car
        from .aero import mk2_assists
        slots += [assist_index(a) for a in mk2_assists(self) if assist_index(a)]    # Aero kit Mk.2 ticked options
        for k, a in enumerate(slots[:10]):
            struct.pack_into('<I', out, 0x4c - 0x44 + 4 * k, a)
        # @0x44 4 x i16 speed, acceleration, durability, boost points the tooltip adds to the table bonus (client
        # 0x658bb2: struct + 0x4c..0x52, texts 10407 / 10406 / 10408 / 10409): an Aero kit Mk.2's distributed points
        from .aero import mk2_points
        pts = mk2_points(self) if context.data else ()
        if pts:                                 # mk2_points: (speed, crash, accel, boost)
            struct.pack_into('<4h', out, 0, pts[0], pts[2], pts[1], pts[3])
        return bytes(out)


@dataclass
class Stats:
    """XiStrStatInfo groups, each speed / crash / accel / boost."""
    based: tuple = (0, 0, 0, 0)
    equip: tuple = (0, 0, 0, 0)
    char: tuple = (0, 0, 0, 0)
    item_use: tuple = (0, 0, 0, 0)

    def total(self):
        return tuple(sum(g[i] for g in (self.based, self.equip, self.char, self.item_use)) for i in range(4))

    def combat(self):
        """The 6 longs the 2011 client added after Total*: only the server fills them (the client does
        not compute them). From the client: [20] = the car's max HP in battles (0x72fb90), [22] = damage
        and [23] = random extra of the player's own attack in the weapon path (0x7c8a10); Dev Ed texts
        name HP / Defense (SP) / Crash Damage. No reference for the real values: sent as 0 (as the 2008
        server). Ram damage on HUVs does not use them: it comes from the stats x Main.StatApply (see
        handlers/game.NEW_FLAGS)."""
        return (0, 0, 0, 0, 0, 0)

    def encode(self):
        return struct.pack('<26i', *self.based, *self.equip, *self.char, *self.item_use, *self.total(),
                           *self.combat()) + bytes(STAT_2011 - 104)


def enchant_bonus():
    """XiStrEnChantBonus (party enchant), none: 2011 layout."""
    return bytes(BONUS_2011)
