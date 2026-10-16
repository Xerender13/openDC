"""Game port (11021).

Load character 0x7c, S>C (BS_PktLoadCharAck, answer to 0x7b). Offsets from the type:
    2008: u32 m_ServerId @2, u32 m_ServerStartTime @6, XiStrCharInfo @0x0a (233 bytes),
          u32 m_nCarSize @0xf3, XiStrCarInfo[n] @0xf7 (45 bytes each)
    2011 (client handler 0x5276f0, size 0x129 + n * 0x31): character record @0x0a (283 bytes),
          u32 car count @0x125, cars @0x129 (49 bytes each)
2011 character record, read from the client (fields @0x00-0x94 as 2008):
    @0x95  8 new bytes (two u32?)            -> 0
    @0x9d  2008 @0x95.. (QuickCnt; the race reward handler 0x514b21 increments it, and adds
           to TotalDistance @0xa1), ..., CurCarId @0xc1, ..., Guild @0xe5, Mileage @0xe9
    @0xf1  42 new bytes                      -> 0
2011 car: XiStrCarUnit (32) and Color @0x20 as 2008 (SetCar 0x708820 writes id @0, color
    @0x20), 4 new bytes @0x24 -> 0, then MitronCapacity @0x28 (read at 0x70862b),
    MitronEfficiency @0x2c, AuctionOn @0x30.

Stats 0x2f8 (BS_PktStatUpdate) and party enchant 0x2f9 (BS_PktPartyEnChantUpdate), S>C:
    XiStrStatInfo 80 -> 104 bytes: the 2008 groups (Based, Equip, Char, ItemUse, Total x
    Speed/Crash/Accel/Boost) stay, 6 new longs @0x50 that the client computes itself
    (0x7204fa writes 0x54-0x5c); XiStrEnChantBonus 36 -> 40 bytes (4 new bytes, assumed at
    the end). Client handlers 0x50f160 (0x92 bytes, bonus @0x6a) and 0x50f250 (0x2a).

Item list 0x191 (BS_PktItemListAck: ListUpdate @2, ItemNum @6, items @0x0a), S>C:
    XiStrMyItem 52 -> 92 bytes (client handler 0x51af60, item parser 0x721900): CarID @0,
    Itm @4 (type word, compared with 0-6), XiStrItemUnit @8 (StackNum @8 must not be 0) as
    2008, then 36 new bytes, TableIdx @0x50 (2008 @0x2c), InvenIdx @0x54, 4 new bytes.
    Guess: the 36 bytes are new XiStrItemUnit fields after the 2008 ones (not checked yet; an
    item with options or upgrades may show wrong values).

Item changes 0x192 (BS_PktItemModList: ItemNum @2, XiStrMyItemMod[n] @6), S>C: each entry is
    XiStrMyItem + long State (56 bytes); in 2011 92 + 4 = 96 (client handler 0x51afa0, size
    0x66 + (n - 1) * 0x60). Sent e.g. when an item changes; a wrong one crashed the shop (F4).

Game setting 0x1e, S>C (BS_PktGameSetting): ServerVersion @2, Reserve @6, XiContentsFlag @0x0a.
    The content flags (feature switches, Contents.ini on the server) are bitfields in groups.
    2008 (56 bytes): Main, City, InstantMission, OMDBase, BattleZone, TeamCenter, Etc, 8 each.
    2011 (88 bytes, client handler 0x5257f0): Main @0 (16), City @0x10 (8), InstantMission
    @0x18 (12), OMDBase @0x24, BattleZone @0x2c (16), TeamCenter @0x3c, NetSync @0x40, Etc @0x44
    (20); fields moved inside the groups too. Converted by name: data/flags_2008.tsv (from the
    PDB bitfields) -> data/flags_2011.tsv (from the client's Reflect code). Flags new in 2011
    are 0 unless set in NEW_FLAGS.
"""
import os
import struct

from ..protocol import C2S, S2C
from ..wire import Frame, read_wstr
from . import on

LOAD_CHAR_ACK, GAME_SETTING, STAT_UPDATE, ENCHANT_UPDATE, ITEM_LIST, ITEM_MOD_LIST = \
    0x7c, 0x1e, 0x2f8, 0x2f9, 0x191, 0x192
STAT_2008, STAT_NEW = 80, 24
BONUS_2008, BONUS_NEW = 36, 4
ITEM_2008, ITEM_2011 = 0x34, 0x5c
CHAR_2008, CHAR_2011 = 0xe9, 0x11b
CAR_2008, CAR_2011 = 0x2d, 0x31
FLAGS_2008, FLAGS_2011 = 0x38, 0x58
FLAG_ALIASES = {'Main.Mix': 'Main.Combi'}
# 2011-only flags. Etc.InventoryReform picks the city inventory dialog (0x4fb650 on the UI root
# [[0x948844]+0x158]: 0 -> +0x16c, 1 -> +0x170, 2 -> +0x174). Read from the running client: only
# the +0x174 one has all its controls (+0x644, +0xa84 set); 0 crashed on entering the city, 1 on
# opening the inventory (F3).
# Main.NeoCityMainUI: the 2011 city main UI (checked == 1 in 8 places, == 2 in 3 that also use
# the weapon slot dialog 4620000); 0 runs the old main UI code on the 2011 UI data (glitched).
# Etc.VShopSeason: the item shop (F4) layout. The client's tab list has type-3 tabs 6000/6100;
# the tab mapping 0x671be0 knows them only for season >= 3 (-> slots 0x3a/0x3b of [shop+0x44]);
# below that it falls back to slot 1 of [shop+0xe4], which is empty: crash at 0x698fe9.
NEW_FLAGS = {'Etc.InventoryReform': 2, 'Main.NeoCityMainUI': 1, 'Etc.VShopSeason': 3, 'Etc.ColorSetReform': 3,
             'Main.StatApply': 1000,   # StatApply: per mille of the stats the car's ram damage etc. use (0 = none)
             # every battle zone section open (the 2008 Contents.ini has 4X / 6X / 8X closed; user, 2026-10-13)
             'BattleZone.Channel4X': 1, 'BattleZone.Channel6X': 1, 'BattleZone.Channel8X': 1,
             # the dealership's purchase conditions ("Insufficient Mito", "Coupon Exclusive Vehicle", ...,
             # GlobalText 11979-11996, client 0x5d7160) are written into its _2ND message label only with
             # this flag; without it the label kept its UI-file text, Korean "coupon needed" (user, 2026-10-13)
             'Etc.NoviceAdvUI2nd': 1,
             # the community window (friends / crew, client 0x59c6f0) answers "This feature is currently
             # unavailable." (text 10745) without this flag (user, 2026-10-13: cannot open the friend list)
             'BattleZone.Friend': 1,
             # the 2011 delivery jobs (byte [net+0x287] bit 0; the flags are at [net+0x268]): delivery points drawn as the
             # quick-service pillar with the cargo (0x6e5a77 -> 0x6dd820 / 0x6dd670, quick_post_fx_01.nif; else the red
             # cylinder.nif) and "Would you like to return to the agency?" (11562, 0x5855a0) after a job (user, 2026-10-14)
             'InstantMission.ImproveQuickService': 1,
             # licenses (native/game/licenses.py): without Main.License the client hides the license panel and never asks
             # for it (0x5fd40f); Etc.NewLicenseSystem is the 2011 license window (0x61e558, opened by 0x29b too)
             'Main.License': 1, 'Etc.NewLicenseSystem': 1,
             # the nameplate's license icon (the first mounted license; own car: the 0x330 copy, others: 0x326) is drawn
             # only with this flag (0x536790, nameplate 0x627a76 / 0x62b8xx; user: no license on the nameplate)
             'Main.LadderDisplay': 1,
             # the License Ownership Reward Money reset day (dialog text 11703; licenses.RESET_DAY pays on it)
             'Etc.NewLicenseSystemnDay': 1,
             # the 2011 battle zone (checked == 1 in ~25 places, [net+0x29c] & 0x30000000): with 0 the lobby code looks up
             # old-layout controls the 2011 UI no longer has; 0x5baff0 used control 0xe30d7 unchecked and the client froze
             # in its crash handler on opening the battle zone (user, 2026-10-15: new character, Amateur section)
             'BattleZone.BattleZoneReform': 1,
             # its section buttons (client 0x5a7530): Newbie (PvP channel 11) needs ChannelNewbie, Pro (12) ChannelPro
             # (the top bit, 0x5a77a2 js); without them both stayed locked (user, 2026-10-15). Real Match is 6.
             'BattleZone.ChannelNewbie': 1, 'BattleZone.ChannelPro': 1, 'BattleZone.Channel16X': 1}


def _flag_table(name):
    table = {}
    for line in open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', name), encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        n, off, shift, width = line.rstrip('\n').split('\t')
        table[n] = (int(off, 16), int(shift), int(width))
    return table


FLAGS_2008_TABLE, FLAGS_2011_TABLE = _flag_table('flags_2008.tsv'), _flag_table('flags_2011.tsv')


def pack_flags_2011(named):
    """{2011 flag name: value} -> XiContentsFlag, 2011 layout (88 bytes)."""
    new = bytearray(FLAGS_2011)
    for name, value in named.items():
        off, shift, width = FLAGS_2011_TABLE[name]
        mask = ((1 << width) - 1) << shift
        cur = struct.unpack_from('<I', new, off)[0]
        struct.pack_into('<I', new, off, (cur & ~mask) | ((value << shift) & mask))
    return bytes(new)


def flags_2011(old):
    """2008 content flags (56 bytes) -> 2011 (88 bytes), field by field by name."""
    named, lost = {}, []
    for name, (off, shift, width) in FLAGS_2008_TABLE.items():
        value = (struct.unpack_from('<I', old, off)[0] >> shift) & ((1 << width) - 1)
        target = FLAG_ALIASES.get(name, name)
        if target in FLAGS_2011_TABLE:
            named[target] = value
        elif value:
            lost.append(f'{name}={value}')
    named.update(NEW_FLAGS)
    return pack_flags_2011(named), lost


def char_2011(c):
    return c[:0x95] + bytes(8) + c[0x95:] + bytes(CHAR_2011 - CHAR_2008 - 8)


def car_2011(c):
    return c[:0x24] + bytes(4) + c[0x24:]


@on('game', S2C, LOAD_CHAR_ACK)
def load_char_ack(session, frame):
    p = frame.payload                       # offsets here are 2 less than from the type
    char = p[8:8 + CHAR_2008]
    n = struct.unpack_from('<I', p, 8 + CHAR_2008)[0]
    cars = p[8 + CHAR_2008 + 4:]
    if len(cars) != n * CAR_2008:
        session.log.note(f'load char: {n} cars in {len(cars)} bytes, unchanged')
        return frame
    out = (p[:8] + char_2011(char) + struct.pack('<I', n)
           + b''.join(car_2011(cars[i * CAR_2008:(i + 1) * CAR_2008]) for i in range(n)))
    cur = struct.unpack_from('<i', char, 0xb9)[0]
    session.log.note(f'load char {read_wstr(char, 8, 42)!r} level {struct.unpack_from("<H", char, 0x38)[0]} '
                     f'mito {struct.unpack_from("<q", char, 0x46)[0]}, {n} cars, current car {cur}')
    return Frame(frame.type, out)


@on('game', S2C, GAME_SETTING)
def game_setting(session, frame):
    p = frame.payload
    flags, lost = flags_2011(p[8:8 + FLAGS_2008])
    session.log.note(f'game setting: contents flags converted by name, set {NEW_FLAGS}'
                     + (f', not in 2011: {" ".join(lost)}' if lost else ''))
    return Frame(frame.type, p[:8] + flags + p[8 + FLAGS_2008:])


@on('game', S2C, STAT_UPDATE)
def stat_update(session, frame):
    p = frame.payload
    stat, bonus = p[:STAT_2008], p[STAT_2008:STAT_2008 + BONUS_2008]
    return Frame(frame.type, stat + bytes(STAT_NEW) + bonus + bytes(BONUS_NEW) + p[STAT_2008 + BONUS_2008:])


@on('game', S2C, ENCHANT_UPDATE)
def enchant_update(session, frame):
    p = frame.payload
    return Frame(frame.type, p[:BONUS_2008] + bytes(BONUS_NEW) + p[BONUS_2008:])


def item_2011(i):
    return i[:0x2c] + bytes(36) + i[0x2c:0x34] + bytes(4)


@on('game', S2C, ITEM_LIST)
def item_list(session, frame):
    p = frame.payload
    n = struct.unpack_from('<I', p, 4)[0]
    items = p[8:]
    if len(items) != n * ITEM_2008:
        session.log.note(f'item list: {n} items in {len(items)} bytes, unchanged')
        return frame
    return Frame(frame.type, p[:8] + b''.join(item_2011(items[k * ITEM_2008:(k + 1) * ITEM_2008]) for k in range(n)))


@on('game', S2C, ITEM_MOD_LIST)
def item_mod_list(session, frame):
    p = frame.payload
    n = struct.unpack_from('<I', p, 0)[0]
    entries, size = p[4:], ITEM_2008 + 4
    if len(entries) != n * size:
        session.log.note(f'item mod list: {n} entries in {len(entries)} bytes, unchanged')
        return frame
    return Frame(frame.type, p[:4] + b''.join(
        item_2011(entries[k * size:k * size + ITEM_2008]) + entries[k * size + ITEM_2008:(k + 1) * size]
        for k in range(n)))


# --- client messages the 2008 server does not know or reads shorter -----------------------

CHECK_IN_GAME, CHECK_IN_2008 = 0x78, 0x23


@on('game', C2S, CHECK_IN_GAME)
def check_in_game(session, frame):
    """0x78: 2008 BS_PktCheckInGame is 0x23 bytes (version, ticket, pc room, crm code); the 2011
    client sends 120 with the account name, and the server read the rest as commands
    ("Wrong Command: 97" = 'a'). Cut to the 2008 size; the server answered the same before."""
    return Frame(frame.type, frame.payload[:CHECK_IN_2008 - 2])


@on('game', C2S, 0x484)
def unknown_484(session, frame):
    """0x484, sent by the 2011 client while loading (sender 0x7ef92d); unknown to the 2008 server
    and no reply is registered for it. Dropped."""
    session.log.note('0x484 dropped (2011 only, no reply known)')
    return None


@on('game', C2S, 0x640)
def item_list_2(session, frame):
    """0x640 -> 0x641: a second item list, new in 2011 (client handler 0x51b420: ListUpdate @2,
    u16 count @6, 0x5e-byte entries @0x0a). Answered here with an empty full list."""
    session.to_client(Frame(0x641, struct.pack('<II', 0x40000, 0)))
    return None


@on('game', C2S, 0xfa0)
def info_fa0(session, frame):
    """0xfa0 (character name, u32) -> 0xfa1, new in 2011; the loading screen waits for it.
    0xfa1 (client handler 0x529720, 0x8b2 bytes): 8 bytes, two 168-byte blocks copied into the
    character object (+0x1074, +0x111c), the u32 @0xaa (end of the first block) is -1 for
    "none", then 1880 bytes (-> +0x11c4). Probably the mentor/apprentice data (guess).
    Answered with an empty record."""
    p = bytearray(0x8b2 - 2)
    struct.pack_into('<i', p, 0xaa - 2, -1)
    session.to_client(Frame(0xfa1, bytes(p)))
    return None


POSITION_ACK, MY_CITY_POSITION = 0x30f, 0x314


@on('game', C2S, MY_CITY_POSITION)
def my_city_position(session, frame):
    session.state['city_position_asked'] = True
    return frame


@on('game', S2C, POSITION_ACK)
def position_ack(session, frame):
    """0x30f MyPositionAck (i32 city, i32 channel, XiVec4 position, i32 state). A character in the
    tutorial gate (the first 0x30f: channel -1) that asks for its city position (0x314, at the end
    of the tutorial) is put at Station 1 of Moon Palace, state 2: the 2008 server answered the
    stored tutorial position (it handles 0x314 before the client's own 0xa2 with the Station 1
    position), so the client put the car back where the tutorial ended (see native/game/position.py)."""
    p = frame.payload
    if len(p) < 28:
        return frame
    city, channel = struct.unpack_from('<ii', p)
    if not session.state.pop('city_position_asked', False):
        session.state['in_tutorial'] = channel == -1
        return frame
    if not session.state.pop('in_tutorial', False):
        return frame
    from ..native import context
    stations = context.data.stations.get(1, {}) if context.data else {}
    x, y, z = stations.get(1, (-3379.0, 1213.2, 85.5))      # Icon_Moonpalace_Client.tdf "Station 1"
    session.log.note(f'tutorial gate left: Station 1 ({x}, {y}, {z}) instead of the tutorial position')
    return Frame(frame.type, struct.pack('<ii4fi', city or 1, channel, x, y, z, 0.0, 2) + p[28:])


TEAM_2008, TEAM_NEW_AT = 0x74, 0x1c


def team_2011(t):
    """XiSmpTeamInfo (2008 0x74: TeamId, TeamMarkId, TeamRanking, TeamPoint, ChannelWinCnt @0x18,
    wchar[13] TeamName @0x1c, MemberCnt, OwnerId, OwnerName, TeamTotalExp): the 2011 client reads one
    more byte before the name (0x316 handler 0x51b4b0: name @+0x1d, member count @+0x37) -> 0."""
    return t[:TEAM_NEW_AT] + b'\0' + t[TEAM_NEW_AT:]


def _units(p, head, count_at, unit, convert):
    n, = struct.unpack_from('<i', p, count_at)
    if n < 0 or len(p) != head + n * unit:
        return None
    return p[:head] + b''.join(convert(p[head + k * unit:head + (k + 1) * unit]) for k in range(n))


@on('game', S2C, 0x316)
def channel_ownership_list(session, frame):
    """0x316 ChannelOwnershipListAck: u32 n, n x 136 (ChannelId, AccTax, wins x3, XiSmpTeamInfo @0x14);
    2011 137 per channel ("CmdLen 1787, AnalysisSize 1776" for 13 channels)."""
    out = _units(frame.payload, 4, 0, 0x88, lambda u: u[:0x14] + team_2011(u[0x14:0x88]))
    return Frame(frame.type, out) if out is not None else frame


@on('game', S2C, 0x35d)
def channel_battle_info(session, frame):
    """0x35d CBattleInfoAck: nAct, BattleTime, Page, u32 n @0xc, n x XiCBattleChannel (306: nChannel,
    OwnTeam @4, ChallengeTeam @0x78, setting and times); 2011 308 (client 0x5315e0: 0x12 + n x 0x134)."""
    out = _units(frame.payload, 0x10, 0xc, 0x132,
                 lambda u: u[:4] + team_2011(u[4:0x78]) + team_2011(u[0x78:0xec]) + u[0xec:])
    return Frame(frame.type, out) if out is not None else frame


FUEL_CHARGE_REQ, FUEL_REQ_2008 = 0x2d3, 0x12


@on('game', C2S, FUEL_CHARGE_REQ)
def fuel_charge_req(session, frame):
    """0x2d3 FuelChargeReq: XiStrFuelChargeReq (u32 car, i64 pay, f32 fuel); 2011 adds 4 bytes (0 so
    far), which the 2008 server would read as a command: cut."""
    return Frame(frame.type, frame.payload[:FUEL_REQ_2008 - 2])


SELECT_CAR_ACK, BUY_CAR_ACK = 0x5a, 0x56


@on('game', S2C, SELECT_CAR_ACK)
def select_car_ack(session, frame):
    """0x5a BS_PktSelectCarAck: XiStrCarInfo (2011: 4 more bytes, as in 0x7c; client 51 from the type)."""
    if len(frame.payload) != CAR_2008:
        return frame
    return Frame(frame.type, car_2011(frame.payload))


@on('game', S2C, BUY_CAR_ACK)
def buy_car_ack(session, frame):
    """0x56 BS_PktBuyCarAck: XiStrCarInfo + u32 Gold (2011: the car 4 bytes longer)."""
    if len(frame.payload) != CAR_2008 + 4:
        return frame
    return Frame(frame.type, car_2011(frame.payload[:CAR_2008]) + frame.payload[CAR_2008:])


# --- replies the 2011 client reads longer (sizes from its handlers: handlers2011) -----------
# type -> (2008 size from the type, 2011 size); the new bytes are added at the end as 0.
PAD_TO_2011 = {
    0x2d4: (50, 54),     # BS_PktFuelChargeRes: u32 @0x32 (1 = do not update the fuel dialog; client 0x520290)
    0x488: (34, 42),     # BS_PktDayEventInfo: XiDayEvent + 8 bytes
    0x30f: (30, 31),     # BS_PktMyPositionAck
    0x3f6: (6, 18),      # BS_PktGetCouponStampListAck: the client always reads one XiStrCoupon
}


def _pad(session, frame):
    old, new = PAD_TO_2011[frame.type]
    if len(frame.payload) + 2 != old:
        return frame
    return Frame(frame.type, frame.payload + bytes(new - old))


for _t in PAD_TO_2011:
    on('game', S2C, _t)(_pad)
