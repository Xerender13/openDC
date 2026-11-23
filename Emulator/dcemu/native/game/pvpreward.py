"""PvP race bonus reward cards: S>C 0x1e4 (Cmd_PvpBattleBonusResult) and C>S 0x1e3, 2016 client only.

Everything below was read from `DriftCity Dev Ed/DriftCity.exe` (2026-11-23); every address is a VA there.

**0x1e4** handler `0x542720`: `u32 n @frame+2`, then `n` entries of 0x18 from `frame+6`. Per entry it calls
`0x5e2720(index, serial, kind, item, amount)` with the six dwords `@0, @4, @8, @0xc, @0x10, @0x14` (`@4` is not read).
`0x5e2720` stores `serial @win+0x5c8+0x10*index`, `kind @+0x5cc`, `item @+0x5d0`, `amount @+0x5d4` and sets
`byte [win+0x6c8] = 1`. After the loop the handler calls `0x5e0ec0(n)`, which adds `n` to `[win+0x6cc]` and outlines a
control once the total passes 15. The handler returns `ax = 0x1e + (n-1)*0x18` (frame bytes, type included).

The kinds are the Neo chapter-card kinds (`0x5e0bf0` builds the caption): **0 empty/face-down**, 1 item (icon from the
item TableIdx at `+0x5d0`, its name underneath), 2 a second catalogue, 3 `%d Mito Received`, 4 mileage, 5
`%d EXP Received` (amount at `+0x5d4`).

**The click** is `0x5e1f40` (dialog `0x4127b0`, slot controls `0x4127b3..0x4127c2`, event `0x101` — the same event the
Neo card grid uses) -> `0x5e0f80(index)`. That function **only accepts a slot whose kind is 0** (`cmp [slot+0x5cc],0`
-> give up) and, once (`[win+0x12c] == -1`), sends **C>S 0x1e3** (sender `0x84d550`): `u32 index @0`, `u32
[win+0x134] @4`. `[win+0x134]` is set by the panel open `0x5e0900(arg1, arg2)`: `arg1 == 0` resets the board and sets
it to -1, otherwise `0x134 = arg2` (a reward-set id) — so the second 0x1e3 field is whatever id the server gave the
panel, and can be ignored while there is one board per race.

The client initializes the 16 face-down cards locally. The server opens a board when the first human finishes and
sends one `0x1e4` entry per reveal. `0x5e27c2` clears the addressed slot's button flag even for kind 0, so a full grid
update would also affect the untouched slots. The picker's serial supplies the name under the revealed card.

Not decoded: what opens the panel (nothing in the client calls `0x5e0900`; it is a vtable method, slot 25 of the
window whose vtable is `0x95e8c4`), and which reward group the real server used. Ours: one item per card rolled from
`rw_battle_low` / `_mid` / `_high` by the picking player's level *(guess)*, 18 s auto-pick (the same deadline as the
Neo grid, *(guess)*).
"""
import asyncio
import random
import struct

from .driftuse import roll
from .items import add_money, mod_list
from .login import SVC, content_flags, serial_of, send
from .rewards import give
from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from ..version import flag_table, is_2016

CARDS = 16
PICK_SECONDS = 18.0
# The client only draws the result's bonus board with this content flag on (a 2016 flag, flags_2016.tsv 0x38 bit 26).
# Our Contents.ini is the 2008 file, so it is off unless emulator.ini [flags] sets it; when it is off the client stores
# the board and never shows it, so the server must not send 0x1e4 and must not pay a pick either.
PVP_FLAG = 'BattleZone.PVPResultUI'
# player level -> the reward group a card is rolled from (ours: the real table is not known)
GROUPS = ((30, 'rw_battle_low'), (60, 'rw_battle_mid'), (10 ** 9, 'rw_battle_high'))


def group_for(level):
    for top, group in GROUPS:
        if level < top:
            return group
    return GROUPS[-1][1]


def enabled():
    """Is the client's PvP result UI flag on? Read from the same packed block login sends (Contents.ini + NEW_FLAGS
    + emulator.ini [flags]), so the server follows exactly what the client was told."""
    table = flag_table()
    if PVP_FLAG not in table:
        return False
    off, shift, width = table[PVP_FLAG]
    packed = content_flags()
    return ((int.from_bytes(packed[off:off + 4], 'little') >> shift) & ((1 << width) - 1)) > 0


def grid_frame(cards, *, start=0):
    """S>C 0x1e4: u32 n, then n x {u32 index, u32 0, u32 picker serial, u32 kind, u32 item, u32 amount}."""
    body = struct.pack('<I', len(cards))
    for index, (kind, item, amount, picker) in enumerate(cards, start):
        body += struct.pack('<6I', index, 0, picker, kind, item, amount)
    return Frame(0x1e4, body)


def roll_card(level):
    """One card for this player -> ([kind, item TableIdx, amount, serial], item id or ''). Face-down while serial 0."""
    try:
        won = [w for w in roll(group_for(max(1, level)))
               if w[0] in ('NormalItem', 'SkidItem') and w[1] in context.data.item_index]
    except Exception:                      # an unknown or empty group: a Mito card rather than no reward
        won = []
    if won:
        item, count = won[0][1], max(int(won[0][3]), 1)
        info = context.data.item_info(context.data.item_index[item])
        return [1, info.table_idx, count, 0], item
    return [3, 0, 1000, 0], ''            # kind 3 = "%d Mito Received"


def _room(session):
    from .rooms import room_of
    return room_of(session)


def reset(room):
    """Discard the previous board and timeout when a new race starts."""
    if getattr(room, 'bonus_task', None):
        room.bonus_task.cancel()
    room.bonus_task = room.bonus_cards = None


def open_board(room):
    """Prepare the board before the first finisher can act on the result window."""
    from .rooms import mission_room
    if not is_2016() or not enabled() or mission_room(room) or getattr(room, 'bonus_cards', None) is not None:
        return
    players = [m for m in room.members if m.session is not None]
    if not players:
        return
    room.bonus_cards = [[0, 0, 0, 0] for _ in range(CARDS)]
    room.bonus_items = [''] * CARDS
    room.bonus_picked = {}
    room.bonus_task = None
    # 0x5e0900 creates the face-down cards. The update at 0x5e27c2 clears bit 4 of the addressed slot even
    # when its kind is zero. Leave those controls alone until a slot is revealed.
    players[0].session.log.note(f'room {room.id}: pvp bonus board opened ({CARDS} face-down cards)')


async def on_race_result(room):
    """Start the fallback once every racer has a result and can pick."""
    open_board(room)
    if (getattr(room, 'bonus_cards', None) is not None and not room.bonus_task
            and any(serial_of(m.session) not in room.bonus_picked for m in room.humans if m.serial in room.racers)):
        room.bonus_task = asyncio.create_task(_auto(room))


async def _auto(room):
    """Nobody picked a card: give everyone who is still there a random free one (server side, as in Neo)."""
    await asyncio.sleep(PICK_SECONDS)
    room.bonus_task = None
    if getattr(room, 'bonus_cards', None) is None:
        return
    cards = room.bonus_cards
    for m in list(room.members):
        if room.bonus_cards is not cards:
            return
        if not m.session or m.serial not in room.racers or serial_of(m.session) in room.bonus_picked:
            continue
        free = [i for i, c in enumerate(cards) if not c[3]]
        if free:
            await pick(room, m.session, random.choice(free))


@on(SVC, C2S, 0x1e3)
async def bonus_pick(session, frame):
    """C>S 0x1e3 (sender 0x84d550, the card click): u32 slot index @0, u32 reward-set id @4."""
    if not is_2016() or not enabled() or len(frame.payload) < 8:
        return
    room = _room(session)
    index, _set = struct.unpack_from('<II', frame.payload)
    if room is None or getattr(room, 'bonus_cards', None) is None:
        session.log.note(f'pvp: bonus card {index} picked outside a race result: ignored')
        return
    from .rooms import RACING
    member = room.member(session)
    if not member or member.serial not in room.racers or (room.state == RACING and not member.end):
        return
    await pick(room, session, index)


async def pick(room, session, index):
    """Grant the card behind `index` to this player and reveal it to the room. One card each."""
    if not enabled():
        return False
    cards = room.bonus_cards
    me = serial_of(session)
    p = session.state.get('player')
    if not 0 <= index < len(cards) or me in room.bonus_picked or cards[index][3]:
        if 0 <= index < len(cards) and cards[index][3]:
            send(session, grid_frame([cards[index]], start=index))
        session.log.note(f'pvp: bonus card {index}: not available')
        return False
    card, item = roll_card(p.char.level if p else 1)
    card[3] = me
    cards[index] = card
    room.bonus_items[index] = item
    room.bonus_picked[me] = index
    kind, _idx, amount, _ = card
    if p and kind == 1 and item:
        gains, _given = await give(p, [(item, max(amount, 1))])
        if gains and gains.items:
            send(session, mod_list(*gains.items))
    elif p and kind == 3:
        await add_money(p.char, amount)
    if room.bonus_cards is cards:
        room.cast(grid_frame([card], start=index))
    label = item or f'{amount} Mito'
    session.log.note(f'pvp: bonus card {index} picked: {label} x{amount}')
    if (room.bonus_cards is cards and room.bonus_task
            and all(serial_of(m.session) in room.bonus_picked for m in room.humans if m.serial in room.racers)):
        room.bonus_task.cancel()
        room.bonus_task = None
    return True
