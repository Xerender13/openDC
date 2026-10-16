"""The coupon book: earning the coupons of the coupon cars (2008 PacketParser::Cmd_GetCouponStampList,
Cmd_MarkCoupon, Cmd_OpenCoupon, Cmd_GetCoupon, XiCsCharInfo::MarkCouponStamp / OpenCouponStamp /
GetCouponStamp; layouts from ZoneServer.pdb, the 2011 client's sizes match).

Coupon.xlt (2011, Init): one row per coupon, grouped by type (the group's row order = type): 0 battles, 1
quick service, 2 chases, 3 combos, 4 driving time (minutes), 5 drifts, 6 art drive, 7 jumps, 8 reverse
driving (minutes), 9 game modes, 10 quest (the tutorial's SS); columns: index in the group, count, minutes
(-1 = counted), car, car Unique ID, coupon item, grade, DB type, DB index, DB field.
Counters:
  types 0-8 and type 9 index 0 (undercity): the client's XiStrCouponForVar (0x3f2 / 0x3f4, session.py;
  combos and drifts u32, the times in seconds).
  DB types 11 (Duel: Real Match wins, DUEL_RM) and 14 (FondoX: rush time tries, RUSHTRY): kept by the
  server (SKID_COUPONPARAMVALUE_TB CTYPE / VALUE; BS_Room::UpdateDuelRealMatch raised 11), sent as 0x3fd
  UpdateCouponParam (u32 CType, f32 value) after 0x3f4 and when they change.
Stamps (SKID_COUPONSTAMP_TB CTYPE / STAMPIDX = the row's DB type / index, STATE 1 marked, 2 opened, 3 coupon
taken):
  0x3f5 GetCouponStampList -> 0x3f6 (u32 n, n x XiStrCoupon: i32 type, u32 index, u32 state; the client
       reads one entry even for n = 0). The client then marks every coupon whose counter has reached its
       target (handler 0x51bbf0 -> 0x7f5b80):
  0x3f7 MarkCoupon (u32 type, i32 index) -> 0x3f8 (the same): a new stamp, state 1 (20064 if it exists, or for
       the server's own counters DUEL_RM / RUSH_TRY if short; the client's counters are its decision: it sends
       0x3f7 before the 0x3f2 with the counter that reached the target).
  0x3f9 OpenCoupon (type, index) -> 0x3fa: state 1 -> 2 (20065).
  0x3fb GetCoupon (type, index) -> 0x3fc, 0x192: state 1 or 2 -> 3, the coupon item (20066).
A coupon car is then bought with its coupon item (cars.py: Coupon.xlt car -> coupon item, used up).
"""
import struct
from collections import namedtuple

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send

Coupon = namedtuple('Coupon', 'type index count minutes car item db_type db_idx field')
MARKED, OPENED, TAKEN = 1, 2, 3
DUEL_RM, RUSH_TRY = 11, 14          # server-side counters (DB types)
GAME_MODES, UNDERCITY = 9, 9

_coupons = None


def coupons():
    """Coupon.xlt rows -> {(type, index): Coupon}."""
    global _coupons
    if _coupons is None:
        import os
        from ..data import read_xlt
        _coupons, kind = {}, -1
        for r in read_xlt(os.path.join(context.data.root, 'Init', 'Coupon.xlt'))[4:]:
            if len(r) < 11 or not r[1].strip().lstrip('-').isdigit():
                continue
            if r[0].strip():
                kind += 1
            n = lambda x: int(float(x)) if x.strip().lstrip('-').replace('.', '', 1).isdigit() else 0
            c = Coupon(kind, n(r[1]), n(r[3]), n(r[4]), n(r[6]), r[7].strip(), n(r[9]), n(r[10]), r[11].strip() if len(r) > 11 else '')
            _coupons[(c.type, c.index)] = c
    return _coupons


def by_db(db_type, db_idx):
    return next((c for c in coupons().values() if (c.db_type, c.db_idx) == (db_type, db_idx)), None)


async def stamps(p):
    """{(db type, db index): state}, loaded once per session."""
    if getattr(p, 'coupon_stamps', None) is None:
        db = context.db
        rows = await db.rows("SELECT CTYPE, STAMPIDX, STATE FROM SKID_COUPONSTAMP_TB WHERE SERVERID=%s AND CID=%s",
                             (db.server_id, p.char.cid))
        p.coupon_stamps = {(int(t), int(i)): int(s) for t, i, s in rows}
    return p.coupon_stamps


async def params(p):
    """{CType: value} of the server-side counters."""
    if getattr(p, 'coupon_params', None) is None:
        db = context.db
        rows = await db.rows("SELECT CTYPE, VALUE FROM SKID_COUPONPARAMVALUE_TB WHERE SERVERID=%s AND CID=%s",
                             (db.server_id, p.char.cid))
        p.coupon_params = {int(t): float(v) for t, v in rows}
    return p.coupon_params


SERVER_ONLY = 1000      # CTYPE from here on: the server's own per-character values (upgrade.GAUGE_TYPE), not sent


def param_frames(values):
    return [Frame(0x3fd, struct.pack('<If', t, v)) for t, v in sorted(values.items()) if t < SERVER_ONLY]


async def add_param(session, ctype, delta=1):
    """A server-side counter goes up (Real Match wins, rush tries); saved and sent."""
    p = session.state.get('player')
    if not p:
        return
    values, db = await params(p), context.db
    values[ctype] = values.get(ctype, 0.0) + delta
    await db.execute("UPDATE SKID_COUPONPARAMVALUE_TB SET VALUE=%s, LASTDATE=GetDate() WHERE SERVERID=%s AND CID=%s"
                     " AND CTYPE=%s; IF @@ROWCOUNT = 0 INSERT INTO SKID_COUPONPARAMVALUE_TB(SERVERID, CID, CTYPE, VALUE,"
                     " LASTDATE) VALUES (%s,%s,%s,%s,GetDate())",
                     (values[ctype], db.server_id, p.char.cid, ctype, db.server_id, p.char.cid, ctype, values[ctype]))
    send(session, *param_frames({ctype: values[ctype]}))


async def reached(p, c):
    """Has the coupon's counter reached its target?"""
    if c.db_type in (DUEL_RM, RUSH_TRY):
        return (await params(p)).get(c.db_type, 0.0) >= c.count
    # The other counters are the client's (XiStrCouponForVar): it marks a coupon (0x3f7) as its counter reaches
    # the target and sends the new counters (0x3f2) right after, so the stored ones are one step behind (user,
    # 2026-10-15: ERIC marked at 14000 combos, refused with 13999 stored -> "failed to mark"). The client decides.
    return True


def stamp_key(c):
    return c.db_type, c.db_idx


def requested(frame):
    if len(frame.payload) < 8:
        return None
    kind, idx = struct.unpack_from('<Ii', frame.payload)
    return coupons().get((kind, idx))


@on(SVC, C2S, 0x3f5)
async def stamp_list(session, frame):
    p = session.state.get('player')
    entries = []
    if p:
        for (db_type, db_idx), state in sorted((await stamps(p)).items()):
            c = by_db(db_type, db_idx)
            if c:
                entries.append(struct.pack('<iII', c.type, c.index, state))
    send(session, Frame(0x3f6, struct.pack('<I', len(entries)) + (b''.join(entries) or bytes(12))))


@on(SVC, C2S, 0x3f7)
async def mark_coupon(session, frame):
    p, c = session.state.get('player'), requested(frame)
    if not p or not c:
        return error(session, '20064')
    have = await stamps(p)
    if stamp_key(c) in have or not await reached(p, c):
        session.log.note(f'coupon {c.type}/{c.index} ({c.car}): not marked (stamp {have.get(stamp_key(c))})')
        return error(session, '20064')
    db = context.db
    await db.execute("INSERT INTO SKID_COUPONSTAMP_TB(SERVERID, CID, CNAME, CTYPE, STAMPIDX, STATE) VALUES (%s,%s,%s,%s,%s,%s)",
                     (db.server_id, p.char.cid, p.char.name, c.db_type, c.db_idx, MARKED))
    have[stamp_key(c)] = MARKED
    session.log.note(f'coupon {c.type}/{c.index} ({c.car}) marked')
    send(session, Frame(0x3f8, frame.payload[:8]))


async def set_state(p, c, state):
    db = context.db
    await db.execute("UPDATE SKID_COUPONSTAMP_TB SET STATE=%s WHERE SERVERID=%s AND CID=%s AND CTYPE=%s AND STAMPIDX=%s",
                     (state, db.server_id, p.char.cid, c.db_type, c.db_idx))
    (await stamps(p))[stamp_key(c)] = state


@on(SVC, C2S, 0x3f9)
async def open_coupon(session, frame):
    p, c = session.state.get('player'), requested(frame)
    if not p or not c or (await stamps(p)).get(stamp_key(c)) != MARKED:
        return error(session, '20065')
    await set_state(p, c, OPENED)
    send(session, Frame(0x3fa, frame.payload[:8]))


@on(SVC, C2S, 0x3fb)
async def get_coupon(session, frame):
    from .driftuse import Gains, give_item
    p, c = session.state.get('player'), requested(frame)
    if not p or not c or (await stamps(p)).get(stamp_key(c)) not in (MARKED, OPENED) \
            or c.item not in context.data.item_index:
        return error(session, '20066')
    gains = Gains()
    await give_item(p, c.item, 1, gains)
    await set_state(p, c, TAKEN)
    session.log.note(f'coupon {c.type}/{c.index}: {c.item} ({c.car}) taken')
    send(session, Frame(0x3fc, frame.payload[:8]))
    gains.send(session, p)
