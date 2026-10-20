"""Pick'em (the client's "Display Gotcha", ObsGacha 0x834-0x83a): a battle zone spectator bets on three racers.

The 2008 server has no such thing; everything here is read from the 2011 client (window game.nui 1930000
ID_VIEWING_GACHA_*, draw window 3720000 ID_GACHA_*), and the scoring is *our choice* where the client says nothing.

The ticket: drift shop Pick'em Ticket (VShopItem gacha_observe_01 / 10 / 30) -> inventory item `gacha_observe`
x1 / 10 / 30 (driftuse.AT_PURCHASE). The client offers it (0x7af4f0) to a spectator of a race with more than 3 room
members (0x529ec0) before the race is half done (0x7acb30), when the player holds a `gacha_observe`; never in AI
battles (text 11398). Without a ticket it starts by itself when [+0xa24] or content flag net+0x2b4 & 0x1000 with room
flag 0x200 (not used here).

Messages (sizes are what the client's handlers return):
  0x834 ObsGachaInit (0x805c90; the prompt's YES 0x1d7323): u32 @2, char[32] @6 (empty). One ticket is used ->
        0x835 (0x16; 0x52b0c0 -> 0x7ab420): u32 0 @2, i8[16] @6 a symbol per seat (window +0x62c: 1 gold,
        2 silver, 3 bronze next to the racer, 0 none); the multiplier starts at 1 and the client picks the
        first three members by itself (0x836).
  0x836 (C>S, 0x7a6840: u32 serial, u32 1 pick / 0 unpick; at most 3 picks, window +0x620) -> the same back
        (10; 0x52b0e0 -> 0x7a68a0 applies it).
  0x837 ObsGachaUp (0x805d90; 0x7acbb0 when the race's gate counter changes): u32 @2, u32 gate @6 (counter - 1),
        u32 n @0xa (3), n x (u16 serial, u16 seat + 1) @0xe -> 0x838 (6; 0x7a6940): u32 multiplier (window +0x6ac,
        pictures x1..x10).
  0x839 SelectState (u16 n @2, 3 x u32 picks @4; n * 2 + 6; 0x7a6910): not needed (the 0x836 answers keep them).
  0x83a ObsGachaResult (n * 8 + 0x2c; 0x52cc70): u32 n @2, u32 0 @6, u32 @0xa the prize's inventory id
        (GameData_FindItem 0x7178e0: the draw window shows rank picture gacha_observe_v1..v10 if the item has that
        name), i32 Mito gained @0xe, i64 Mito @0x12 (char +0x46), u32 EXP gained @0x1a, u16 level @0x1e (+0x38),
        u32 EXP / next / base @0x20 / 0x24 / 0x28 (+0x3a / 0x3e / 0x42), n x (u32 serial, u16 rank, u16 medal)
        @0x2c. The draw window (0x6bd930) spins three reels and stops on the first three medals: 0 bomb, 1 gold,
        2 silver, 3 bronze.

*Our rules* ([pickem] in emulator.ini):
  - a seat's symbol by the racers' strength (car grade, then level): the strongest third bronze, the middle silver,
    the weakest third gold (the long odds pay more);
  - multiplier: +1 (up to 10) for each gate where a pick passes among the first three;
  - medal of a pick = its symbol if it finishes in the top 3, else a bomb; EXP / Mito = per medal [pickem] exp / mito
    x (4 - medal) (gold 3x, silver 2x, bronze 1x), times the multiplier;
  - with a medal: one Slot Ticket of the multiplier's grade (inventory item gacha_observe_v<N>, "Slot Ticket Grade N";
    used, it gives its RewardGroup rw_gacha_ob_v<N>: passive assists, items.item_use).
2011 client only (the 2016 messages are not read).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import admin, context
from .login import SVC, send

GOLD, SILVER, BRONZE, BOMB = 1, 2, 3, 0
SEATS = 16
PICKS = 3
MAX_MULTIPLIER = 10
TICKET = 'gacha_observe'
PRIZE = 'gacha_observe_v%d'


def cfg():
    return context.pickem


def state(session, room):
    """The spectator's Pick'em of this race, or None (a new race starts with room.gates = {})."""
    s = session.state.get('pickem')
    return s if s and s['room'] is room and s['race'] is room.gates else None


def strength(m):
    p = m.player
    car = p.car if p else None
    return (car.shown_grade() if car else 0, p.char.level if p else 0)


def symbols(room):
    """{serial: 1 gold / 2 silver / 3 bronze} of the race's racers (see the rules)."""
    racers = sorted((m for m in room.members if m.serial in room.racers and m.session), key=strength)
    n = len(racers)
    return {m.serial: GOLD if i < n / 3 else SILVER if i < 2 * n / 3 else BRONZE for i, m in enumerate(racers)}


def watched(session):
    from . import rooms
    room = rooms.rooms.get(session.state.get('watching'))
    from .. import version
    return room if room and not version.is_2016() else None


@on(SVC, C2S, 0x834)
async def init(session, frame):
    from . import rooms
    from .driftuse import Gains, take_one
    p = session.state.get('player')
    room = watched(session)
    if not p or not room or not cfg()['enabled']:
        return
    if room.state not in (rooms.LOADING, rooms.RACING) or room.ais or len(room.racers) <= 3:   # countdown too
        session.log.note(f"pick'em refused: room {room.id} state {room.state}, {len(room.racers)} racers, "
                         f'{len(room.ais)} AIs')
        return admin.message(session, "Pick'em: only while a race of 4 or more players is running.")
    if state(session, room):
        return
    gains = Gains()
    if not cfg()['free']:
        it = next((i for i in p.items if context.data.item_info(i.table_idx).item_id == TICKET and i.stack > 0), None)
        if not it:
            return admin.message(session, "Pick'em: you have no Pick'em Ticket.")
        gains.items.append(await take_one(p, it))
    marks = symbols(room)
    seats = bytes(marks.get(s, 0) for s in (room.seats + [0] * SEATS)[:SEATS])
    session.state['pickem'] = dict(room=room, race=room.gates, picks=[], marks=marks, multiplier=1, gates=set())
    session.log.note(f"pick'em in room {room.id}: symbols {marks}")
    gains.send(session, p)
    send(session, Frame(0x835, struct.pack('<I', 0) + seats))


@on(SVC, C2S, 0x836)
async def select(session, frame):
    room = watched(session)
    s = state(session, room) if room else None
    if not s or len(frame.payload) < 8:
        return
    serial, on_ = struct.unpack_from('<II', frame.payload)
    picks = s['picks']
    if on_ and serial not in picks and serial in s['marks'] and len(picks) < PICKS:
        picks.append(serial)
    elif not on_ and serial in picks:
        picks.remove(serial)
    else:
        return
    send(session, Frame(0x836, struct.pack('<II', serial, 1 if on_ else 0)))


@on(SVC, C2S, 0x837)
async def up(session, frame):
    room = watched(session)
    s = state(session, room) if room else None
    if not s or len(frame.payload) < 12:
        return
    _, gate, _ = struct.unpack_from('<IiI', frame.payload)
    if gate not in s['gates']:
        s['gates'].add(gate)
        if any(serial in room.gates.get(gate, [])[:3] for serial in s['picks']):
            s['multiplier'] = min(MAX_MULTIPLIER, s['multiplier'] + 1)
    send(session, Frame(0x838, struct.pack('<I', s['multiplier'])))


def medals(s, room):
    """[(serial, rank, medal)] of the picks: its symbol when it finished in the top 3, else a bomb."""
    from .rooms import FINISHED
    out = []
    for serial in s['picks']:
        m = room.by_serial(serial)
        end = m.end if m else None
        rank = end[3] if end and end[0] == FINISHED else 0
        out.append((serial, rank, s['marks'].get(serial, BOMB) if 1 <= rank <= 3 else BOMB))
    return out


async def on_result(room):
    """The race result (rooms.result): each spectator who played gets the draw (0x83a) and the prizes."""
    for session in list(room.observers):
        s = state(session, room)
        p = session.state.get('player')
        if not s or not p:
            continue
        session.state.pop('pickem', None)
        await pay(session, p, s, medals(s, room))


async def pay(session, p, s, won):
    from .driftuse import Gains, give_item
    from .items import add_money
    from .progress import add_exp
    gains = Gains()                            # the prize item only: 0x83a carries the Mito, EXP and level itself
    c = p.char
    hits = [m for _, _, m in won if m != BOMB]
    mult = s['multiplier']
    exp = sum(cfg()['exp'] * (4 - m) for m in hits) * mult
    mito = sum(cfg()['mito'] * (4 - m) for m in hits) * mult
    prize = PRIZE % mult if hits else None
    if exp:
        await add_exp(c, exp)
    if mito and not await add_money(c, mito):
        mito = 0
    if prize and prize in context.data.item_index:
        await give_item(p, prize, 1, gains)
    prize_inven = next((it.inven_idx for it, _ in gains.items), 0)
    session.log.note(f"pick'em result: {won}, x{mult}, +{exp} exp, +{mito} Mito, prize {prize}")
    gains.send(session, p)                     # first: the draw window finds the prize in the inventory
    rows = (won + [(0, 0, BOMB)] * PICKS)[:max(PICKS, len(won))]
    body = struct.pack('<IIIiqIHIII', len(rows), 0, prize_inven, mito, c.mito, exp, c.level,
                       c.exp, c.exp_next, c.exp_base)
    body += b''.join(struct.pack('<IHH', serial, rank, medal) for serial, rank, medal in rows)
    send(session, Frame(0x83a, body))
