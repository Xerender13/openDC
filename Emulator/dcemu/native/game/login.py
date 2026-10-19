"""Native game service (11021): entering the game and the lists the client asks for while loading.

Sequence (a real 2011 client, see logs/; the 2008 server's handlers in Server/tools/dev/dispatch_2008.txt):
  0x78 CheckInGame (2011: 0x78 bytes, account name @8)        -> 0x79 result (1)
  0x7b LoadChar (name, u32 serial)                             -> [0x32a ETCInfo, 0x7c LoadCharAck,
       0x1e GameSetting], 0x5dd BonusUpdate, 0x2f8 StatUpdate, 0x2f9 PartyEnChantUpdate,
       [0x708 AuctionCarOpenClose, 0x488 DayEventInfo]     ([...] = one frame, as the 2008 server sends)
  0x110 MyQuestList -> 0x111     0x190 ItemList -> 0x191 (+ 0x1a5 item data)
  0x4b0 VisualItemList -> 0x4b1  0x546 MyStickerList -> 0x547   0x244 MyAuctionList -> 0x245
  0x640 MyAuctionVSList -> 0x641  0x6a4 MyAuctionCarList -> 0x6a5 (auction.py)
  0x3f3 GetCouponForVar -> 0x3f4 (+ 0x3fd)   0x3f5 GetCouponStampList -> 0x3f6 (coupons.py)
  0x7d JoinChannel -> 0x7e + 0x280 Weather       0xe6 FriendList -> 0xe7
  0x30e FirstPosition -> 0x30f (position.py)   0x310 GetDateTime -> 0x311   0x1b2 CheckStat -> 0x2f8 + 0x2f9
  0xfa0 (2011) -> 0xfa1          0x12c JoinArea -> 0x12d      0x3e0 (instant.py)
Sizes are the 2011 client's (handlers2011: its handler for each type and the size it consumes).
"""
import asyncio
import struct
import time

from ...handlers import on, on_open
from ...handlers.game import FLAG_ALIASES, FLAGS_2011_TABLE, NEW_FLAGS, pack_flags_2011
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import admin, context, now
from . import player
from .records import enchant_bonus, wstr

SVC = 'native:game'
LIST_FULL, LIST_MORE = 0x40000, 0x40001       # ListUpdate of a list's first / following messages
ITEMS_PER_MESSAGE = 12                         # the 2008 server's chunks
KEEPALIVE_SECONDS = 3
WEATHER = 4                                    # what the 2008 server sent


def bundle(*frames):
    """Several commands in one frame: [len][type][body][type][body]..."""
    first, rest = frames[0], frames[1:]
    return Frame(first.type, first.payload + b''.join(struct.pack('<H', f.type) + f.payload for f in rest))


BUNDLE_MAX = 8192      # bytes of one bundle; a 24360-byte one (the item list of 189 items, all 0x191 parts + 0x1a5 in one
                       # frame) made the client stop reading at login ("loading data"; 14828 bytes still went through;
                       # user, 2026-10-16), so bundles are cut before that size


def send(session, *frames):
    group, size = [], 0
    for f in frames:
        n = len(f.payload) + 2
        if group and size + n > BUNDLE_MAX:
            session.to_client(bundle(*group) if len(group) > 1 else group[0])
            group, size = [], 0
        group.append(f)
        size += n
    if group:
        session.to_client(bundle(*group) if len(group) > 1 else group[0])


def error(session, key):
    """PacketSend::Send_Error: 0x0001, u16 byte length (with the terminator) + UTF-16 text, the text by
    its GlobalText_Server.xlt key (the 2008 server's GTW; its named keys are numbers: NotInitializedChar
    20017, NotFoundItem 20024, ItemBuyFail 20029, ItemSellFail 20030, ...)."""
    text = context.data.server_text.get(key, key).encode('utf-16-le') + b'\0\0'
    session.log.note(f'error {key}')
    session.to_client(Frame(0x0001, struct.pack('<H', len(text)) + text))


sessions = {}       # session id -> session, every game connection (chat, and later party / rooms)


@on_open(SVC)
async def keepalive(session):
    sessions[session.id] = session
    try:
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            session.to_client(Frame(0x02, struct.pack('<I', 0)))
    finally:
        sessions.pop(session.id, None)


@on(SVC, C2S, 0x78)
async def check_in(session, frame):
    member = read_wstr(frame.payload, 8, 80)
    from .. import nation
    n = nation.known(session, member)               # None: the 0x7cf may still come (it can follow the check-in)
    if n is not None and not nation.allowed(n):
        session.log.note(f'check-in {member!r}: client nation {n} ({nation.name(n)}) is not allowed here: closed')
        return session.close()
    session.state['member'] = member
    session.log.note(f'check-in {member!r}')
    send(session, Frame(0x79, struct.pack('<I', 1)))


# In the tutorial gate (gate 0) the login is kept as it was before session 11: Director Green's tutorial messages stopped
# after the license flags and frames came in (user, 2026-10-15; this morning's new character still had them). The license
# system starts when the character reaches the city (licenses.on_login from position.my_city_position); its flags with
# the next login.
TUTORIAL_FLAGS = {'Main_License': 0, 'Etc_NewLicenseSystem': 0, 'Main_LadderDisplay': 0, 'Etc_NewLicenseSystemnDay': 0}
# (The missing tutorial messages turned out to be position.first_position's state, not these flags.)


def in_tutorial(p):
    from .position import IN_CITY
    return p.char.pos_state < IN_CITY


def content_flags(**overrides):
    """XiContentsFlag (2011) from Contents.ini, by name; flags new in 2011 from NEW_FLAGS; overrides as
    Group_Flag=value (e.g. Etc_RealMatchEffect=1)."""
    named = {}
    for name, value in context.data.contents.items():
        target = FLAG_ALIASES.get(name, name)
        if target in FLAGS_2011_TABLE:
            named[target] = value
    named.update(NEW_FLAGS)
    named['Main.OptionItem'] = int(context.option_parts)      # emulator.ini [items] option_parts
    named['Main.DockingItem'] = int(context.docking_parts)    # [items] docking_parts
    # F1 opens the Communication Zone at the Walkie-Talkie (friends) tab; without it at My Crew, which only says
    # "You are not registered in a crew." (10425) for a character without one (client 0x61da87; user)
    named['Main.Letter'] = 1
    # a car's own assists (VehicleList "Car Assist": drift booster, turbo start, ..) are applied only with this
    # flag (client 0x70f5b0 from the assist rebuild 0x729b5a)
    named['Main.CarGradeAssist'] = 1
    named['Main.Modify'] = 1        # the parts shop's Convert tab (convert.py)
    named['Main.NewRepair'] = 1     # the new Restoration Kits (+6 .. +12, MK.II): client 0x64db10 (upgrade.py)
    named['Etc.ShowMainButtonGotcha'] = int(context.gotcha_enabled)     # emulator.ini [gotcha] (gotcha.py)
    named['Etc.GotchaSeason'] = context.gotcha_season if context.gotcha_enabled else 0
    named['Main.AuctionCar'] = int(context.auction_cars)               # emulator.ini [auction] (auction.py)
    named['Main.AuctionCommission'] = int(context.auction_item_fee)    # the fees the client shows (%)
    named['Main.AuctionVSCommission'] = int(context.auction_drift_fee)
    named.update(context.extra_flags)          # emulator.ini [flags]
    named.update({k.replace('_', '.', 1): v for k, v in overrides.items()})
    return pack_flags_2011(named)


def game_setting(**overrides):
    """0x1e GameSetting: server version, reserve, content flags."""
    return Frame(0x1e, struct.pack('<ii', 0, 0) + content_flags(**overrides))


def stat_frames(p):
    """0x2f8 StatUpdate + 0x2f9 PartyEnChantUpdate (the other members' party assists), after a change of the car's
    items; the other members get their 0x2f9 again, and the player a 0x425 when the car's gage / saving assists
    changed its capacity or mileage (assists.py)."""
    session = p.session
    if session is None:
        return Frame(0x2f8, p.stats().encode() + enchant_bonus()), Frame(0x2f9, enchant_bonus())
    from .assists import own_bonus, party_bonus, send_party
    from .social import party_of
    car = p.car
    before = (car.max_mitron(), car.mileage()) if car else None
    p.apply_paints()
    frames = [Frame(0x2f8, p.stats().encode() + own_bonus(p)), Frame(0x2f9, party_bonus(session))]
    if car and before != (car.max_mitron(), car.mileage()):
        from .cars import visual_update
        frames.append(visual_update(session, car))
    party = party_of(session)
    if party and len(party.members) > 1:
        send_party([s for s in party.members if s is not session])
    return frames


@on(SVC, C2S, 0x7b)
async def load_char(session, frame):
    name = read_wstr(frame.payload, 0, 0x2a)
    p = await player.load(name, session.state.get('member'))
    if not p:
        session.log.note(f'load char {name!r}: not found')
        return
    c = p.char
    # Cmd_LoadChar's checks: the character already in the game, game block, chat block
    if not await admin.account_valid(c.member):
        session.log.note(f'load char {name!r}: account {c.member!r} is blocked')
        return error(session, '20089')
    other = admin.find(c.name)
    if other and other is not session:
        session.log.note(f'load char {name!r}: already in the game (session {other.id}), that one is closed')
        admin.drop(other, admin.DUPLICATE_TEXT, account=False)
        return error(session, '20088')
    game_blocked, chat_until = await admin.blocks(c.cid)
    if game_blocked:
        session.log.note(f'load char {name!r}: blocked from the game')
        return error(session, '20089')
    session.state['player'] = p
    p.session = session
    session.state['chat_block'] = chat_until
    from .. import nation
    p.nation = nation.of(session)
    session.log.note(f'client nation {p.nation} ({nation.name(p.nation)})')
    from .auction import mark_cars, open_frame
    await mark_cars(p)
    from .items import merge_stacks
    if await merge_stacks(p):
        session.log.note('usable item stacks merged')
    from .driftuse import convert_bundles
    await convert_bundles(session, p)
    from .quests import give_up_at_login        # a quest left started by a connection that never closed properly
    await give_up_at_login(session, p)
    from .items import link_keys
    for k in await link_keys(p):
        session.log.note(f'car key {k.item_id} made for car {k.random}')
    from .items import ON_CAR, info_of, scorch
    for it in p.items:                  # hyper parts put on a car before scorching existed (2026-10-15)
        info = info_of(it)
        if it.car_id and (it.state & 0xffff) == ON_CAR and info and info.grade == 'H' and await scorch(p, it, True):
            session.log.note(f'{info.item_id} on car {it.car_id}: scorched ({it.item_id})')
    session.log.note(f'load char {c.name!r} level {c.level}, {len(c.cars)} cars, {len(p.items)} items')
    load_ack = (struct.pack('<II', context.db.server_id, context.start_time) + c.encode()
                + struct.pack('<I', len(c.cars)) + b''.join(car.encode() for car in c.cars))
    # the content flags first: the 0x7c handler builds the player's own driver model at once, with the flags the
    # client holds then (Etc.EventChristmas from leftover values put Santa parts on the driver when the 0x1e came in a
    # later frame: user, 2026-10-16; seen with a breakpoint on the model's check 0x4750ec)
    send(session, Frame(0x1e, struct.pack('<ii', 0, 0) + content_flags(**(TUTORIAL_FLAGS if in_tutorial(p) else {}))),
         Frame(0x32a, bytes(136)), Frame(0x7c, load_ack))
    from .items import bonus_update
    send(session, bonus_update(p))
    for car in c.cars:                  # a timed V upgrade on a car: the grade it shows (vshop.after_change)
        if car.shown_grade() != car.grade:
            send(session, Frame(0x63, struct.pack('<II', car.car_id, car.shown_grade())))
    for f in stat_frames(p):
        send(session, f)
    # DayEventInfo: today's mission index, the day-event counters (daymission.py)
    from .daymission import info_frame
    send(session, open_frame(), await info_frame(p))
    from . import alchemy                  # manufacturing EXP and the skill books learned (0x0e75)
    await alchemy.load(p)
    from . import licenses                 # licenses held / gained meanwhile, condition values, the mounted ones
    if not in_tutorial(p):                 # (see TUTORIAL_FLAGS)
        send(session, alchemy.info_frame(p))
        await licenses.on_login(session, p)
        from . import mothers               # Mother quests held, the Mitro City reputations
        await mothers.on_login(session, p)
    if chat_until:
        send(session, admin.chat_block_frame(chat_until))


def chunks(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)] or [[]]


def quest_list_frame(quests):
    """0x111: the client's handler (0x51adb0 -> 0x750c50) empties its quest lists and fills them again."""
    return Frame(0x111, struct.pack('<I', len(quests)) + b''.join(struct.pack('<IIIH', *q) for q in quests))


@on(SVC, C2S, 0x110)
async def quest_list(session, frame):
    p = session.state.get('player')
    send(session, quest_list_frame(p.quests if p else []))


@on(SVC, C2S, 0x190)
async def item_list(session, frame):
    p = session.state.get('player')
    items = p.items if p else []
    out = []
    for k, part in enumerate(chunks(items, ITEMS_PER_MESSAGE)):
        out.append(Frame(0x191, struct.pack('<II', LIST_MORE if k else LIST_FULL, len(part))
                         + b''.join(i.encode() for i in part)))
    out.append(Frame(0x1a5, struct.pack('<I', len(items)) + b''.join(i.data() for i in items)))
    send(session, *out)


@on(SVC, C2S, 0x4b0)
async def visual_item_list(session, frame):
    p = session.state.get('player')
    items = p.vsitems if p else []
    send(session, Frame(0x4b1, struct.pack('<II', LIST_FULL, len(items)) + b''.join(v.encode() for v in items)))


# 0x546 MyStickerList: stickers.py


# 0x244 / 0x640 / 0x6a4 my auction listings (items, drift items, cars): auction.py


@on(SVC, C2S, 0x3f3)
async def coupon_vars(session, frame):
    """0x3f4 the counters, then 0x3fd per server-side counter (Cmd_GetCouponForVar; coupons.py)."""
    from .coupons import param_frames, params
    p = session.state.get('player')
    from .session import pack_coupon_vars
    send(session, Frame(0x3f4, pack_coupon_vars(p.coupon_vars if p else (0.0,) * 10)))
    if p:
        for f in param_frames(await params(p)):
            send(session, f)


@on(SVC, C2S, 0x7d)
async def join_channel(session, frame):
    channel = read_wstr(frame.payload, 0, 20)
    p = session.state.get('player')
    serial = session.state.setdefault('serial', session.id & 0xffff)
    send(session, Frame(0x7e, frame.payload[:20].ljust(20, b'\0')
                        + wstr(p.char.name if p else '', 32)
                        + struct.pack('<HH', serial, 1)))
    send(session, Frame(0x280, struct.pack('<i', WEATHER)))
    session.state['channel'] = channel
    session.log.note(f'join channel {channel!r}')


# 0xe6 FriendList: social.py


@on(SVC, C2S, 0x310)
async def date_time(session, frame):
    """GetDateTimeAck: Action, GlobalTime and LocalTime echoed, time_t, server tick start, tick,
    date (year, month 0-11, day, weekday) and time (hour, min, sec, 0); the date fields as the
    2008 server fills them (year - 1742: what it sent in 2026)."""
    action, global_time, local_time = struct.unpack_from('<iif', frame.payload)
    t = time.gmtime()
    p = session.state.get('player')
    send(session, Frame(0x311, struct.pack('<iifiIi4h4b', action, global_time, local_time, now(), context.start_time,
                                           p.tick if p else 0, t.tm_year - 1742, t.tm_mon - 1, t.tm_mday, (t.tm_wday + 1) % 7,
                                           t.tm_hour, t.tm_min, t.tm_sec, 0)))
    if p and not session.state.get('gauge_sent'):
        # the Modify tab's chance gauge (0x89 type 37): the client writes it into the parts shop window without
        # a null check, so it is sent here (the game UI exists), not in the login burst
        from .upgrade import gauge_frame, gauge_of
        session.state['gauge_sent'] = True
        send(session, gauge_frame(await gauge_of(p)))


@on(SVC, C2S, 0x1b2)
async def check_stat(session, frame):
    p = session.state.get('player')
    if p:
        for f in stat_frames(p):
            send(session, f)


@on(SVC, C2S, 0xfa0)
async def info_fa0(session, frame):
    """2011 only (character name, u32) -> 0xfa1: an empty record (see handlers/game.py info_fa0)."""
    out = bytearray(0x8b2 - 2)
    struct.pack_into('<i', out, 0xaa - 2, -1)
    send(session, Frame(0xfa1, bytes(out)))


@on(SVC, C2S, 0x12c)
async def join_area(session, frame):
    area, = struct.unpack_from('<i', frame.payload)
    from .mita500 import on_join_area           # Mita 500 buff and bottles first, as 2008 Cmd_JoinArea
    await on_join_area(session, area)
    send(session, Frame(0x12d, struct.pack('<ii', area, 1)))
    if session.state.get('player') and not in_tutorial(session.state['player']):
        from .licenses import nameplate_frame       # the player's own nameplate: its mounted licenses
        send(session, nameplate_frame(session))


@on(SVC, C2S, 0x484)
async def unknown_484(session, frame):
    pass


@on(SVC, C2S, 0x07)
async def ping(session, frame):
    pass
