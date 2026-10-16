"""Combos and traffic items: exp for drift combos, item drops (batch 3 of the native game).

0x2e4 TrafficItemEvent (u32 type, u32 time, f32 arg, i32 arg1, i32 arg2, u32 flags; as in 2008).
    PacketParser::Cmd_TrafficItemEvent 0x608130, at most one every 2 s (accounts with PType 'A'
    excepted):
    type 0, arg > 100: a traffic item picked up (drop mode 1).
    type 1: a combo (recorded: 1, time, 20.0, 1, 1, flags 3). The 2008 server counts the combo
        numbers (arg1 / arg2, flag 1 / 2 resets them) to find bots ("autoSuspect" log, a test question
        to the player, the "_Bad" drop table); not done here. Then an item drop (mode 2) and the
        combo exp: comboexp.txt by level (the party's average level when lower), +30% premium (not
        here); the fraction is kept and the whole part added (CalcExperience) -> 0x410 ComboExp (u32
        exp, u32 money 0, XiStrExpInfo, u16 level, f32 the exp of this combo; recorded: 1, 0,
        (1, 100, 0), 1, 0.6) when it is at least 1, and the "COMBO" play mode.
Drops (PickupTrafficItem 0x6900f0, PickUpItem, XiCsLevelDropGroup::DropItemOfMode 0x5a2f00): the
    ItemDropServer.tdf rows for the character's level (the highest table level not above it), a roll
    in 0-100% (0-10% in mode 1) against the groups' rates of the mode added up; the first group past
    the roll gives one of its items at random (TakeItem: onto a stack or a new item -> 0x192). One
    roll (two with the double-drop item, not here) -> 0x2e5 TrafficItemEventAck (u32 count, u32 item
    TableIdx, u32 drop mode); nothing dropped: (1, -1, mode) (PickUpItem 0x68f980); (0, -1, mode) is
    "inventory full" to the client. Recorded: (1, 212, 2) then 0x410, 0x192.
"""
import random
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import CHANGED, NEW, STACK_SQL, mod_list, new_item, stack_for
from .items import EXP_DRINK, holds
from .login import SVC, send, stat_frames
from .progress import add_exp, play_mode

TRAFFIC, COMBO = 0, 1
MIN_GAP = 2.0


def free_slots(p):
    """Free inventory slots: 20 per page, 2 pages + the drift shop expansions (HancoinInven), less the items not
    on a car (as gmsets counts)."""
    return (p.char.hancoin_inven + 2) * 20 - sum(1 for i in p.items if not i.car_id)


async def take_if_room(p, info):
    """take, or None when it needs a new slot and the inventory is full (the drops checked nothing: with the
    Item Drink's second roll items went past the limit; user, 2026-10-15)."""
    if not stack_for(p, info, 1) and free_slots(p) <= 0:
        return None
    return await take(p, info)


async def take(p, info):
    """One item into the inventory (XiCsCharInfo::TakeItem: onto a stack, else a new item) -> (item, state)."""
    it = stack_for(p, info, 1)
    if it:
        it.stack += 1
        db = context.db
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        return it, CHANGED
    return await new_item(p, info, 1), NEW


PART_KINDS = ('speed', 'accel', 'crash', 'boost')


def parts_group(group):
    """A drop group of parts only (ig_p_*: speed / accel / crash / boost parts)."""
    t = context.data
    infos = [t.item_info(i) for i in t.drop_groups.get(group, ())]
    return bool(infos) and all(i and i.kind in PART_KINDS for i in infos)


async def drop(p, mode, parts_only=False):
    """One roll of a drop mode (1 traffic, 2 combo, 3 rush hit) -> (0x2e5 frame, [(item, state)]). parts_only
    (rush bosses, user 2026-10-15: a part on every hit): one of the level's part groups, weighted by their
    rates of this mode (equal weights when they are all 0)."""
    t = context.data
    if parts_only:
        groups = [(g, rates[mode] if mode < len(rates) else 0.0) for g, rates in t.drop_rates(p.char.level)
                  if parts_group(g)]
        if groups:
            weights = [w for _, w in groups] if any(w > 0 for _, w in groups) else None
            group = random.choices([g for g, _ in groups], weights=weights)[0]
            info = t.item_info(random.choice(t.drop_groups[group]))
            got = await take_if_room(p, info)
            if got is None:
                return Frame(0x2e5, struct.pack('<Iii', 0, -1, mode)), []
            return Frame(0x2e5, struct.pack('<IIi', 1, info.table_idx, mode)), [got]
        return Frame(0x2e5, struct.pack('<Iii', 1, -1, mode)), []
    roll = random.uniform(0, 100 if mode != 1 else 10)
    total = 0.0
    from .licenses import drop_bonus
    more = drop_bonus(p)                        # mounted licenses: parts drop chance + % (ME_PartDropRate, ...)
    for group, rates in t.drop_rates(p.char.level):
        rate = rates[mode] if mode < len(rates) else 0.0
        total += rate * (100 + more) / 100 if more and parts_group(group) else rate
        if total > roll:
            items = t.drop_groups.get(group)
            info = t.item_info(random.choice(items)) if items else None
            if not info:
                break
            got = await take_if_room(p, info)
            if got is None:                     # inventory full: (0, -1), the client says so
                return Frame(0x2e5, struct.pack('<Iii', 0, -1, mode)), []
            return Frame(0x2e5, struct.pack('<IIi', 1, info.table_idx, mode)), [got]
    # nothing dropped: PickUpItem succeeds with no item (1, -1); (0, -1) means the item could not be
    # taken (inventory full) and the client says so (user, 2026-10-13: "inventory full" on HUV hits)
    return Frame(0x2e5, struct.pack('<Iii', 1, -1, mode)), []


async def drops(session, p, mode, parts_only=False):
    """The pick-up rolls: two with the Item Drink held (PickupTrafficItem loops 1 + flag times), one 0x2e5
    each (the second only when it dropped something or the inventory is full). -> [(item, state)]"""
    from .items import ITEM_DRINK, holds
    changes = []
    for k in range(2 if holds(p, ITEM_DRINK) else 1):
        f, got = await drop(p, mode, parts_only)
        if k == 0 or got or struct.unpack_from('<I', f.payload)[0] == 0:
            send(session, f)
        changes += got
    return changes


@on(SVC, C2S, 0x2e4)
async def traffic_item_event(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    kind, _, arg = struct.unpack_from('<IIf', frame.payload)
    c, now = p.char, time.monotonic()
    if now - session.state.get('combo_last', 0.0) < MIN_GAP and c.ptype != 'A':
        return
    session.state['combo_last'] = now
    changes = []
    if kind == TRAFFIC and arg > 100:
        changes = await drops(session, p, 1)
    elif kind == COMBO:
        changes = await drops(session, p, 2)
        t = context.data
        got = t.combo_exp[min(c.level, len(t.combo_exp)) - 1] if t.combo_exp and c.level > 0 else 0.0
        if holds(p, EXP_DRINK):                     # on the fraction, as Cmd_TrafficItemEvent (x 0.3)
            got *= 1 + context.drink_exp / 100
        frac = session.state.get('combo_exp', 0.0) + got
        exp = int(frac)
        session.state['combo_exp'] = frac - exp
        if exp > 0:
            up = await add_exp(c, exp)
            send(session, Frame(0x410, struct.pack('<II3IHf', exp, 0, c.exp, c.exp_next, c.exp_base, c.level, got)))
            if up:
                for f in stat_frames(p):
                    send(session, f)
        await play_mode(c, 'COMBO', exp=exp)
    if changes:
        send(session, mod_list(*changes))
