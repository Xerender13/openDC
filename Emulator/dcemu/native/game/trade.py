"""Player trade (the trade window: two players exchange items and Mito), 2011 and 2016 clients. The emulator had no
trade until session 42; the 2008 server's PacketParser::Cmd_Trade* / BS_TradeRoom (ZoneServer.pdb) are the reference
for the messages, the 2011 client for the layouts (offsets with the 2-byte type):

C>S (same sizes in 2008, 2011 and 2016):
  0x1f4 TradeOpen (wchar[21] the other player's name; 0x2c)        sender 0x7f2000 (2011)
  0x1f7 TradeProposeAck (u32 trade, u16 1 yes / 0 no; 8)            the asked player's answer
  0x1f8 TradeItemOn (u32 trade, u32 InvenIdx, i32 count; 0xe)        0x7f22c0
  0x1fa TradeItemOff (u32 trade, i32 the item's trade index; 0xa)
  0x1fc TradeLock (u32 trade, u16 1 lock / 0 unlock; 8)             0x7f2580 (pushes 1 / 0: 0x66b000 / 0x66afe4)
  0x1fe TradeClose (u32 trade; 6)
  0x200 TradeComplete (u32 trade, i64 Gold; 0xe: the 2011 sender 0x7f2830 fills only the trade, the money is 0x202)
  0x202 TradeMoney (u32 trade, i64 Mito; 0xe; new since 2008)        0x7f2980
S>C:
  0x1f6 TradePropose (wchar[21] who asks @2, u32 trade @0x2c; 0x30): client 0x51db00 asks "trade with %s?" (it
        answers no by itself for a blocked player, 0x63d1f0, and below its level 12, 0x51da11).
  0x1f5 TradeOpenAck (wchar[21] host @2, guest @0x2c, i64 host cid @0x56, i64 guest cid @0x5e, u32 trade @0x66, u16
        result @0x6a; 0x6c, 2008 0x64 with u32 cids): client 0x51d920 opens the window for result 1 (the other
        player: the cid that is not its own).
  0x1f9 TradeItemOnAck (u32 trade @2, XiStrTradeInfo @6, wchar[21] owner @0x5a; 2011 0x84, 2016 0x88): client
        0x515650: the owner's name equal to its own -> its own side (0x724000: the item by InvenIdx @+0x4c),
        else the other side (0x724090: by TableIdx @+0x48); both clear the lock / complete marks.
        XiStrTradeInfo = XiStrItemUnit (XiStrMyItem @8.., 2011 0x48, 2016 0x4c) + TableIdx + InvenIdx + i32 the
        item's trade index (2011 0x54, 2016 0x58).
  0x1fb TradeItemOffAck (u32 trade, i32 trade index @6, wchar[21] owner @0xa; 0x34)
  0x1fd TradeLockAck (u32 trade, u32 state @6, wchar[21] whose @0xa; 0x34): client 0x70f3a0 / 0x70f400: 3 = that
        side locked (window +0x288 / +0x289), 2 = both unlocked, 1 = only the complete marks cleared.
  0x201 TradeCompleteAck (u32 trade, u32 state @6, owner @0xa; 0x34): 4 = that side pressed Trade (+0x28a /
        +0x28b), 5 = done: the client closes the window (0x51dca1).
  0x203 TradeMoneyAck (u32 trade, i64 Mito @6, owner @0xe; 0x38): that side's money (0x70f300 / 0x70f340), the
        marks cleared.
  0x1ff TradeCloseAck (u32 trade; 6): the window closes.

Rules (the 2008 server's, read in a delegated report and checked at the places quoted): open (0x5ef140): the other
player in the same channel (20014), not a GM unless the asker is one (20114), not trading (20115); an item (0x5f5dd0):
held (20024), count > 0 (20050, clamped to the stack), tradeable (20062: ours is mail.sendable: not on a car, not
bound or broken, hyper / untradeable parts only in a Parts Box; 2008: the item table's Trade flag or a Box, no
Belonging), at most 8 per side, no item twice (20055); every change clears both sides' lock / complete marks; lock
(0x594bf0): state 1, 3 once both locked, unlock 2; Trade (0x200, TradeOk 0x5949c0) only with both locked: 4, and
when both pressed the items move (TradeComplete 0x595850) and one 0x201 state 5 goes to both. Ours: Mito (0x202,
not in 2008), checked again with the items and the room in the inventories at the exchange; 0x200's Gold is ignored
(2008 too; the client leaves it unset). The 2008 holes are not copied: only the asked player answers, only the two
players act on a trade.
Items move as mail moves them (taken from one inventory, made again in the other with the same properties).
A close, a refusal or a disconnect ends the trade: 0x1ff to both.
"""
import itertools
import struct

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context
from .login import SVC, error, send, stat_frames
from .records import wstr

NAME = 42
MAX_ITEMS = 8               # 2008 BS_TradeRoom::TradeItemOn 0x595324 (MaxTradeNum): a 9th item is refused
LOCKED, UNLOCKED, BOTH_LOCKED = 1, 2, 3
PRESSED, DONE = 4, 5
_ids = itertools.count(1)
trades = {}                  # trade id -> Trade


class Side:
    def __init__(self, session):
        self.session = session
        self.items = {}          # trade index -> (InvenIdx, count)
        self.money = 0
        self.locked = False
        self.pressed = False

    @property
    def player(self):
        return self.session.state.get('player')

    @property
    def name(self):
        p = self.player
        return p.char.name if p else ''


class Trade:
    def __init__(self, host, guest):
        self.id = next(_ids)
        self.host, self.guest = Side(host), Side(guest)
        self.open = False
        self.next_index = itertools.count(1)

    def sides(self):
        return (self.host, self.guest)

    def side(self, session):
        return next((s for s in self.sides() if s.session is session), None)

    def other(self, side):
        return self.guest if side is self.host else self.host

    def cast(self, frame):
        for s in self.sides():
            send(s.session, frame)

    def reset_marks(self):
        for s in self.sides():
            s.locked = s.pressed = False


def is_admin(session):
    """A GM (PType 'A' or the admin list): the 2008 server let only a GM trade with a GM (0x5ef28a)."""
    from .misc import is_admin as admin
    try:
        return admin(session)
    except (AttributeError, TypeError):
        return False


def trade_of(session):
    t = trades.get(session.state.get('trade'))
    return t if t and t.side(session) else None


def by_name(name):
    from .misc import online
    return online(name)


def info_bytes(it, index):
    """XiStrTradeInfo: the item unit, TableIdx, InvenIdx (XiStrMyItem @8 ..) and the item's trade index."""
    from ..version import is_2016
    return it.encode()[8:0x5c if is_2016() else 0x58] + struct.pack('<i', index)


def close(t, why=''):
    trades.pop(t.id, None)
    for s in t.sides():
        if s.session.state.get('trade') == t.id:
            s.session.state.pop('trade', None)
        send(s.session, Frame(0x1ff, struct.pack('<I', t.id)))
        s.session.log.note(f'trade {t.id} closed{": " + why if why else ""}')


@on(SVC, C2S, 0x1f4)
async def trade_open(session, frame):
    """0x1f4 (the other player's name) -> 0x1f6 TradePropose to that player."""
    p = session.state.get('player')
    if not p or len(frame.payload) < 2:
        return
    name = read_wstr(frame.payload, 0, NAME)
    target = by_name(name)
    if target is session:
        return                                          # 2008 0x5ef255: no answer
    if not target or target.state.get('channel') != session.state.get('channel'):
        return error(session, '20014')                  # "Cannot find the user in the channel."
    if is_admin(target) and not is_admin(session):
        return error(session, '20114')                  # "You may not trade with this user."
    if trade_of(target):
        return error(session, '20115')                  # "The user is now trading."
    if trade_of(session):
        return error(session, '20113')                  # ours: "This is not allowed during a trade."
    t = Trade(session, target)
    trades[t.id] = t
    session.state['trade'] = target.state['trade'] = t.id
    session.log.note(f'trade {t.id}: {p.char.name!r} asks {name!r}')
    send(target, Frame(0x1f6, wstr(p.char.name, NAME) + struct.pack('<I', t.id)))


@on(SVC, C2S, 0x1f7)
async def trade_propose_ack(session, frame):
    if len(frame.payload) < 6:
        return
    tid, yes = struct.unpack_from('<IH', frame.payload)
    t = trades.get(tid)
    if not t or t.guest.session is not session or t.open:
        return
    if yes != 1:
        return close(t, f'{t.guest.name!r} said no')
    t.open = True
    h, g = t.host.player.char, t.guest.player.char
    t.cast(Frame(0x1f5, wstr(h.name, NAME) + wstr(g.name, NAME) + struct.pack('<qqIH', h.cid, g.cid, t.id, 1)))
    session.log.note(f'trade {t.id}: {h.name!r} and {g.name!r} open the window')


def running(session, frame, size):
    """The trade a request is about (its id first), if the window is open and the sender is in it."""
    if len(frame.payload) < size:
        return None, None
    tid, = struct.unpack_from('<I', frame.payload)
    t = trades.get(tid)
    side = t.side(session) if t else None
    return (t, side) if t and t.open and side else (None, None)


@on(SVC, C2S, 0x1f8)
async def trade_item_on(session, frame):
    from .mail import sendable
    t, side = running(session, frame, 12)
    if not t:
        return
    _, inven, count = struct.unpack_from('<IIi', frame.payload)
    p = side.player
    it = next((i for i in p.items if i.inven_idx == inven), None)
    if not it:
        return error(session, '20024')
    if count <= 0:
        return error(session, '20050')                  # "Unreliable data."
    count = min(count, max(it.stack, 1))                # 2008 0x595250: clamped to the stack
    if not sendable(it, count):
        session.log.note(f'trade {t.id}: {it.item_id} cannot be traded')
        return error(session, '20062')                  # "This item cannot be traded."
    if len(side.items) >= MAX_ITEMS or any(v[0] == inven for v in side.items.values()):
        return error(session, '20055')                  # "Failed to trade items."
    index = next(t.next_index)
    side.items[index] = (inven, count)
    t.reset_marks()
    shown = it
    if count != it.stack:                               # the record with the offered count
        import copy
        shown = copy.copy(it)
        shown.stack = count
    t.cast(Frame(0x1f9, struct.pack('<I', t.id) + info_bytes(shown, index) + wstr(side.name, NAME)))
    session.log.note(f'trade {t.id}: {side.name!r} offers {it.item_id} x{count}')


@on(SVC, C2S, 0x1fa)
async def trade_item_off(session, frame):
    t, side = running(session, frame, 8)
    if not t:
        return
    _, index = struct.unpack_from('<Ii', frame.payload)
    if side.items.pop(index, None) is None:
        return error(session, '20056')                  # "Failed to cancel the trade." (2008 TradeItemOff)
    t.reset_marks()
    t.cast(Frame(0x1fb, struct.pack('<Ii', t.id, index) + wstr(side.name, NAME)))


@on(SVC, C2S, 0x202)
async def trade_money(session, frame):
    t, side = running(session, frame, 12)
    if not t:
        return
    _, money = struct.unpack_from('<Iq', frame.payload)
    if money < 0 or money > side.player.char.mito:
        return error(session, '20092')                  # Insufficient funds
    side.money = money
    t.reset_marks()
    t.cast(Frame(0x203, struct.pack('<Iq', t.id, money) + wstr(side.name, NAME)))


@on(SVC, C2S, 0x1fc)
async def trade_lock(session, frame):
    t, side = running(session, frame, 6)
    if not t:
        return
    _, lock = struct.unpack_from('<IH', frame.payload)
    if lock == 1:                                       # 2008 TradeLock 0x594bf0: 1, both locked 3; unlock 2
        side.locked = True
        for s in t.sides():
            s.pressed = False
        state = BOTH_LOCKED if all(s.locked for s in t.sides()) else LOCKED
        t.cast(Frame(0x1fd, struct.pack('<II', t.id, state) + wstr(side.name, NAME)))
    else:
        t.reset_marks()
        t.cast(Frame(0x1fd, struct.pack('<II', t.id, UNLOCKED) + wstr(side.name, NAME)))


@on(SVC, C2S, 0x1fe)
async def trade_close(session, frame):
    if len(frame.payload) < 4:
        return
    t = trades.get(struct.unpack_from('<I', frame.payload)[0])
    if t and t.side(session):
        close(t, f'{t.side(session).name!r} closed it')


@on(SVC, C2S, 0x200)
async def trade_complete(session, frame):
    t, side = running(session, frame, 4)
    if not t or not all(s.locked for s in t.sides()):
        return                                          # 2008 TradeOk 0x5949c0: nothing before both locked
    side.pressed = True
    if all(s.pressed for s in t.sides()):
        return await exchange(t, side)
    t.cast(Frame(0x201, struct.pack('<II', t.id, PRESSED) + wstr(side.name, NAME)))


def check(t):
    """-> None, or why the exchange cannot be done (the items still held and tradeable, the Mito, room)."""
    from .combo import free_slots
    from .mail import sendable
    for s in t.sides():
        p = s.player
        if not p:
            return f'{s.name!r} left'
        for inven, count in s.items.values():
            it = next((i for i in p.items if i.inven_idx == inven), None)
            if not sendable(it, count):
                return f'{s.name!r} no longer holds item {inven}'
        if s.money > p.char.mito:
            return f'{s.name!r} has not the Mito'
    for s in t.sides():
        o = t.other(s)
        if free_slots(s.player) - len(s.items) < len(o.items):
            return f'{s.name!r} has no room'
    return None


async def exchange(t, last):
    from .items import CHANGED, DELETE_SQL, NEW, REMOVED, STACK_SQL, add_money, mod_list, new_item, stack_for
    from .mail import PROPS as PROPS_SQL, item_text, parse_item
    why = check(t)
    if why:
        for s in t.sides():
            from .. import admin
            error(s.session, '20059')                    # "Failed to complete the item trade."
        return close(t, why)
    db = context.db
    moves = []                                          # (from side, to side, item text)
    for s in t.sides():
        p, c = s.player, s.player.char
        changes = []
        for inven, count in s.items.values():
            it = next(i for i in p.items if i.inven_idx == inven)
            moves.append((s, t.other(s), item_text(it, count)))
            it.stack -= count
            if it.stack > 0:
                await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
                changes.append((it, CHANGED))
            else:
                await db.execute(DELETE_SQL, (db.server_id, c.cid, it.inven_idx))
                p.items.remove(it)
                changes.append((it, REMOVED))
        if changes:
            send(s.session, mod_list(*changes))
    got = {id(s): [] for s in t.sides()}
    for src, dst, text in moves:
        item_id, count, rnd, upgrade, box, a, b, belonging = parse_item(text)
        p, c = dst.player, dst.player.char
        info = context.data.item_info(context.data.item_index[item_id])
        it = stack_for(p, info, count) if not (rnd or upgrade or box or a or b) else None
        if it:
            it.stack += count
            await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
            got[id(dst)].append((it, CHANGED))
        else:
            it = await new_item(p, info, count if info.type == 5 else 1)
            it.random, it.upgrade, it.box, it.assist_a, it.assist_b, it.belonging = rnd, upgrade, box, a, b, belonging
            await db.execute(PROPS_SQL, (rnd, upgrade, box, a, b, belonging, db.server_id, c.cid, it.inven_idx))
            got[id(dst)].append((it, NEW))
        dst.session.log.note(f'trade {t.id}: {src.name!r} -> {dst.name!r}: {text}')
    for s in t.sides():
        o = t.other(s)
        net = o.money - s.money
        if net:
            await add_money(s.player.char, net)
            send(s.session, Frame(0x8a, struct.pack('<iiqq', 1, 1, net, s.player.char.mito) + b'\0\0'))
        if got[id(s)]:
            send(s.session, mod_list(*got[id(s)]))
        for f in stat_frames(s.player):
            send(s.session, f)
    t.cast(Frame(0x201, struct.pack('<II', t.id, DONE) + wstr(last.name, NAME)))   # the client closes the window
    trades.pop(t.id, None)
    for s in t.sides():
        s.session.state.pop('trade', None)
        s.session.log.note(f'trade {t.id} done: {s.name!r} gave {len(s.items)} item(s), {s.money} Mito')


@on_open(SVC)
async def trade_on_close(session):
    import asyncio
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        t = trade_of(session)
        if t:
            close(t, 'a player left')
