"""Set parts (si_*), their expiry and set bonus, the Alpha / Beta Restoration Lubes, and the server tick.

**Set parts** (ItemClient.tdf rows si_*): column 1 = the set (kayla, yuki, AH, ...), 5 its name, 14 the expired
form ("si_s01_001_to": the client's icon and value once the part has run out), 19 the set bonus text, 20 the
part's piece of the set bonus (an Assist_Client row), 21 the period in server-tick hours (360 = 15 days; 0 =
for good), 22 Jew_A / Jew_B (Alpha / Beta; the 2011 game no longer crafts them from gemstones: the user).
The set bonus is the assists of all parts of the set, only while every part of the set is on the car and
none has expired ("Collect all 4 of Kayla's Set Parts to increase ..."); the server counts the stat ones
(bonusspeed / bonuscrash / bonusaccel / bonusboost points; the others act in the client or are not native).
**Expiry** (client 0x72c9c0, the item value): for an item whose table period is not 0 the client compares
XiStrMyItem @0x48 (ExpireTick, 2011; 2008 had it @0x28) with the current server tick (0x311 GetDateTimeAck's
tick, advanced by the client at seconds / 3600: hours, 0x537d20): while it is ahead the value is table value +
@0x44 (the enhancement bonus) + the random bonus; once it has run out the client takes the expired form's
table value + the random bonus (no enhancement), and shows its icon. Here: ExpireTick is stored in
SKID_ITEM_TB.CTIME (as the 2008 server: "ExpireTick = CTIME"), set to tick + period when a set part is made
(or first loaded without one); an expired part loses its enhancement bonus and the set bonus (player.stats).
**Restoration Lubes** (drift shop, Misc): Alpha Set Restoration Lube (i_d_set_ch01, category 25) "Temporarily
restores the bonus effect of Alpha sets", Beta Parts Restoration Lube (i_d_set_ch02, 26) the same for Beta: kept in
the drift inventory, used on one part at a time from the inventory's lube panel (replenish, 0x1b0).
**Server tick**: SKID_SERVER_TB.SERVERPTICK counts hours (2008 UpdateServerTick); advanced at each login by the
whole hours since LASTDATE (current_tick); Player.tick is the live value (tick_now).
**Usable items with a period** (UseItemClient column 12, see period) expire the same way: ExpireTick in CTIME, sent
@0x48; they stack only with items of the same ExpireTick (items.stack_for).
"""
import datetime
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import info_of
from .login import SVC

LUBES = {25: 'A', 26: 'B'}          # VisualItem category -> set family
STAT_KINDS = {'bonusspeed': 0, 'bonuscrash': 1, 'bonusaccel': 2, 'bonusboost': 3}
EXPIRE_SQL = "UPDATE SKID_ITEM_TB SET CTIME=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
TICK_GET = "SELECT SERVERPTICK, LASTDATE FROM SKID_SERVER_TB WHERE SERVERID=%s"
TICK_SET = "UPDATE SKID_SERVER_TB SET SERVERPTICK=%s, LASTDATE=%s WHERE SERVERID=%s"

_assists = None


def row(it):
    rows = context.data._part_rows
    return rows[it.table_idx] if 0 <= it.table_idx < len(rows) else None


def is_set(it):
    r = row(it)
    return bool(r) and r[2].startswith('si_')


def period(it):
    """The item's period in server-tick hours (0 = for good): set parts ItemClient column 21; usable items
    UseItemClient column 12 (24 Mittron Enhancer, 167 Battle Ghost Tickets, 240 crude parts, ...; their column 4 is
    the expired form the client then shows), except the value-99 Mittron Enhancers (Mittron Enhancer / PLUS /
    DELUXE): the user's guide says 72 h (upgrade.EXPIRE_HOURS; the table says 24)."""
    t = context.data
    n = len(t._part_rows)
    if it.table_idx >= n:
        r = t._use_rows[it.table_idx - n] if it.table_idx - n < len(t._use_rows) else None
        col = 12
        info = info_of(it)
        if info and info.kind == 'upgrade' and info.value == 99:
            from .upgrade import EXPIRE_HOURS
            return EXPIRE_HOURS
    else:
        r, col = row(it), 21
    try:
        return int(float(r[col])) if r and len(r) > col else 0
    except ValueError:
        return 0


def family(it):
    """'A' (Alpha) or 'B' (Beta) for a set part."""
    r = row(it)
    gem = r[22] if r and len(r) > 22 else ''
    if gem in ('Jew_A', 'Jew_B'):
        return gem[-1]
    return r[2][3] if r and len(r[2]) > 3 and r[2][3] in 'AB' else ''


def expired(p, it):
    return period(it) > 0 and it.ctime and it.ctime <= p.tick


def expired_value(it):
    """The expired form's table value (column 14), or the part's own when it has none."""
    r = row(it)
    t = context.data
    other = t.part_stat(r[14]) if r and len(r) > 14 and r[14] in t.item_index else None
    return other[1] if other else (t.part_stat(it.item_id) or (0, 0))[1]


async def start_expiry(p, it):
    """An item with a period and no expiry yet gets tick + its period, counted from when it was made (CDATE) for
    items made before expiry was sent (usable items until 2026-10-14: the client showed them expired at once)."""
    if period(it) > 0 and not it.ctime:
        db = context.db
        # CDATE is the database's GetDate(): UTC in the container (the emulator's clock is local time)
        age = int((datetime.datetime.utcnow() - it.cdate).total_seconds() // 3600) if it.cdate else 0
        it.ctime = p.tick - max(age, 0) + period(it)
        await db.execute(EXPIRE_SQL, (it.ctime, db.server_id, p.char.cid, it.inven_idx))


LUBE_HOURS = 720                    # 2008 XiCsCharInfo::ReplenishItem: ChangeCTime(0x2d0)


@on(SVC, C2S, 0x1b0)
async def replenish(session, frame):
    """0x1b0 ReplenishItem (u32 part InvenIdx, u32 lube drift InvenIdx): a Restoration Lube on one set part.
    Client: the drift inventory's lube panel (dialog 3260000 "Restore or Extend expiration time for Set Parts.",
    window + 0x870; Use button 3260010 -> confirm 0x2c8e47 -> 0x5f91e0: the held drift item of category 25 for an
    Alpha part, 26 for a Beta one, 0x803f20 sends). 2008 PacketParser::Cmd_ReplenishItem 0x604ea0 /
    XiCsCharInfo::ReplenishItem 0x5cd7a0: the part's family must match the lube's category; XiCsItem::ChangeCTime(720):
    a run-out part gets tick + 720, a running one + 720 (30 days); the lube is used (state 2). -> 0x1b1
    ReplenishItemAck (part, lube, i32 ExpireTick - tick, u32 720; client 0x50f140 refreshes the part), stats, 0x192,
    0x4b2, 0x5dd. (Until 2026-10-14 the lubes acted when bought, on every part of the family: user, wrong.)"""
    from .driftuse import USED, use_up
    from .items import CHANGED, active, bonus_update, mod_list
    from .login import error, send, stat_frames
    from .vshop import vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return error(session, '20017')                  # NotInitializedChar
    part_idx, lube_idx = struct.unpack_from('<II', frame.payload)
    it = next((i for i in p.items if i.inven_idx == part_idx), None)
    v = next((x for x in p.vsitems if x.inven_idx == lube_idx and active(x)), None)
    vis = context.data.visuals.get(v.table_idx) if v else None
    if not it or not vis or vis.category not in LUBES or not is_set(it) or family(it) != LUBES[vis.category]:
        session.log.note(f'replenish {part_idx} with {lube_idx}: refused')
        return error(session, '20024')                  # NotFoundItem
    tick = p.tick
    it.ctime = (it.ctime if it.ctime and it.ctime > tick else tick) + LUBE_HOURS
    db = context.db
    await db.execute(EXPIRE_SQL, (it.ctime, db.server_id, p.char.cid, it.inven_idx))
    await use_up(p, v)
    session.log.note(f'replenish {it.item_id} ({part_idx}) with {vis.item_id}: until tick {it.ctime} (now {tick})')
    send(session, Frame(0x1b1, struct.pack('<IIiI', part_idx, lube_idx, it.ctime - tick, LUBE_HOURS)))
    for f in stat_frames(p):
        send(session, f)
    send(session, mod_list((it, CHANGED)))
    send(session, vs_mod_list((v, USED)))
    send(session, bonus_update(p))


def assists():
    global _assists
    if _assists is None:
        import os
        from ..data import read_tdf
        _assists = {r[1]: r for r in read_tdf(os.path.join(context.data.server_data, 'Assist_Client.tdf')) if len(r) > 5}
    return _assists


def set_bonus(p, car_id):
    """-> [speed, crash, accel, boost] of the complete, unexpired sets on the car."""
    t = context.data
    out = [0, 0, 0, 0]
    on = [i for i in p.items if i.car_id == car_id and (i.state & 0xffff) == 1 and is_set(i)]
    for key in {row(i)[1] for i in on}:
        members = {r[2] for r in t._part_rows if r[2].startswith('si_') and r[1] == key and not r[2].endswith('_to')}
        mine = [i for i in on if row(i)[1] == key]
        if {i.item_id for i in mine} != members or any(expired(p, i) for i in mine):
            continue
        for i in mine:
            a = assists().get(row(i)[20])
            if a and a[2] in STAT_KINDS:
                try:
                    out[STAT_KINDS[a[2]]] += int(float(a[5]))
                except ValueError:
                    pass
    return out


_base = None                     # (SERVERPTICK, LASTDATE) as last read: tick_now counts on from it


def tick_now():
    """The server tick now: the last read SERVERPTICK + the whole hours since its LASTDATE (the tick goes on during a
    session, as the client's own does; until 2026-10-14 a player kept the tick of their login)."""
    if not _base:
        return 0
    tick, last = _base
    return tick + max(int((datetime.datetime.now() - last).total_seconds() // 3600), 0)


async def current_tick():
    """SERVERPTICK advanced by the whole hours since LASTDATE (stored back)."""
    db = context.db
    r = await db.row(TICK_GET, (db.server_id,))
    if not r:
        return 0
    tick, last = int(r[0] or 0), r[1]
    now = datetime.datetime.now()
    hours = int((now - last).total_seconds() // 3600) if last else 0
    if hours > 0 or not last:
        tick += max(hours, 0)
        last = (last + datetime.timedelta(hours=hours)) if last else now
        await db.execute(TICK_SET, (tick, last, db.server_id))
    global _base
    _base = (tick, last)
    return tick
