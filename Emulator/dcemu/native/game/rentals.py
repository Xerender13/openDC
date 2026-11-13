"""2016 rental capsule redemption (2011 does not use this protocol).

0xfb4: 11 u32: car type, grade, kind, special, parts, capsule inventory id,
term, speed/accel/boost/crash. Observed request: 213,9,1,1,0,115,0,280,185,250,85.
0xfb5: 50-byte car (0x524270). 0xfb6: count + 61-byte records (0x53c170):
four points, car id, expiry (UTC seconds since 2012-01-01), two u16 options,
char[32] associated item id, byte.
Car record u16 +0x12 is rental kind (0x78400e); points replace base stats
(0x7840ca). Sender 0x5946b2 reorders the window's boost/crash fields.
"""
import asyncio
import struct
from dataclasses import dataclass

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import CLOCK_SHIFT, context, now
from ..version import is_2016
from ..data import read_xlt
from .login import SVC, error, send, stat_frames
from .records import Car, Item

RENTAL_EPOCH = 1325376000  # 2012-01-01 UTC; client 0x6536b1 -> 0x69fc80

SPECIAL_ASSISTS = ('a_00002', 'a_00118', 'a_00081', 'a_00221')
LOCK = asyncio.Lock()
SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS SKID_RENTCAR_TB(
 SERVERID numeric(18,0) NOT NULL, CID numeric(18,0) NOT NULL, CARID numeric(18,0) NOT NULL,
 KIND int NOT NULL, EXPIRES bigint NOT NULL, SPEED int NOT NULL, ACCEL int NOT NULL,
 BOOST int NOT NULL, CRASH int NOT NULL, SPECIAL int NOT NULL, PARTS int NOT NULL,
 PRIMARY KEY(SERVERID,CID,CARID))"""


def redeem_in_db(cur, sid, cid, inven, item, name, car_type, color, capacity, rental, specs):
    """db.transaction: the capsule (still held, unused) -> a rental car (pc_skid_createcar, grade 9), its terms row,
    its rental parts (8 item ids from the sequence), the capsule deleted, the car current. -> (car, first gid, first
    inventory index) or None (nothing changed)."""
    cur.execute("SELECT 1 FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s AND ITEMID=%s AND STATE=0"
                " AND STACKNUM=1 FOR UPDATE", (sid, cid, inven, item))
    if not cur.fetchall():
        return None
    cur.execute("SELECT pc_skid_createcar(%s, %s, %s, %s, %s, 9, 0, %s, 0)", (sid, cid, name, car_type, color, capacity))
    car = int(cur.fetchone()[0] or -1)
    if car <= 0:
        raise RuntimeError('no rental car')
    cur.execute("INSERT INTO SKID_RENTCAR_TB VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (sid, cid, car, rental.kind, rental.expires, rental.speed, rental.accel, rental.boost, rental.crash,
                 rental.special, rental.parts))
    cur.execute("UPDATE SKID_SEQUENCE_TB SET item_sq1=item_sq1+8 RETURNING item_sq1-8")
    gid = int(cur.fetchone()[0])
    cur.execute("SELECT PARTINVENIDX FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND CID=%s", (sid, cid))
    idx = int(cur.fetchone()[0])
    for n, (info, slot, aid) in enumerate(specs, 1):
        cur.execute("INSERT INTO SKID_ITEM_TB(SERVERID,CID,CNAME,GID,CARID,INVENIDX,ITEMID,STACKNUM,NRANDOM,STATE,"
                    "NUPGRADE,BELONGING,ASSIST_A,ASSIST_B,CTIME) VALUES(%s,%s,%s,%s,%s,%s,%s,1,0,%s,0,1,'','',0)",
                    (sid, cid, name, gid + n, car, idx + n, info.item_id, (slot << 16) | 1))
    cur.execute("DELETE FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s", (sid, cid, inven))
    cur.execute("UPDATE SKID_CHARACTER_TB SET CURCAR=%s, PARTINVENIDX=%s WHERE SERVERID=%s AND CID=%s",
                (car, idx + 8, sid, cid))
    return car, gid, idx


def remove_in_db(cur, sid, cid, car):
    """db.transaction: an expired rental: its rental parts deleted, other gear back to the inventory, the car and its
    terms row deleted."""
    cur.execute("DELETE FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s AND CARID=%s AND ITEMID LIKE 'r\\_type\\_%%'",
                (sid, cid, car))
    cur.execute("UPDATE SKID_ITEM_TB SET CARID=0,STATE=0 WHERE SERVERID=%s AND CID=%s AND CARID=%s", (sid, cid, car))
    cur.execute("UPDATE SKID_VSITEM_TB SET CARID=0,STATE=0 WHERE SERVERID=%s AND CID=%s AND CARID=%s", (sid, cid, car))
    cur.execute("DELETE FROM SKID_CAR_TB WHERE SERVERID=%s AND CID=%s AND CARID=%s", (sid, cid, car))
    if cur.rowcount > 0:
        cur.execute("UPDATE SKID_CHARACTER_TB SET NUMCAR=NUMCAR-1 WHERE SERVERID=%s AND CID=%s", (sid, cid))
    cur.execute("DELETE FROM SKID_RENTCAR_TB WHERE SERVERID=%s AND CID=%s AND CARID=%s", (sid, cid, car))


@dataclass
class Rental:
    kind: int
    expires: int
    speed: int
    accel: int
    boost: int
    crash: int
    special: int
    parts: int

    @property
    def stats(self):
        return self.speed, self.crash, self.accel, self.boost

    def expired(self):
        return self.kind == 1 and self.expires <= now()

    def encode(self, car_id):
        expires = max(0, self.expires - CLOCK_SHIFT - RENTAL_EPOCH)
        return struct.pack('<6I2H32sB', self.speed, self.accel, self.boost, self.crash,
                           car_id, expires, self.parts * 2 + 1, self.parts * 2 + 2,
                           SPECIAL_ASSISTS[self.special].encode('ascii'), 0)


def part_specs(option):
    """The two rental sets chosen together: A+B / C+D / E+F / G+H.
    Parts occupy both ordinary lines (base slot + 0/1). Their table values are zero;
    each part's Assist column supplies the actual bonus on the client and server.
    """
    from .items import SLOT_BASE
    out = []
    for line, group in enumerate((option * 2 + 1, option * 2 + 2)):
        for suffix in ('sp', 'ac', 'cr', 'bo'):
            item_id = f'r_type_{group}_{suffix}'
            info = context.data.item_info(context.data.item_index[item_id])
            aid = context.data.items[item_id][20]
            out.append((info, SLOT_BASE[info.type] + line, '' if aid == 'n/a' else aid))
    return out


def gear_assists(p, car):
    """The client applies column 20 for each complete rental set, just as for si_*.
    Leave conversion assist slots empty to avoid applying the same bonus twice.
    """
    ids = {i.item_id for i in p.items if i.car_id == car.car_id and i.state & 0xffff == 1}
    out = []
    for group in (car.rental.parts * 2 + 1, car.rental.parts * 2 + 2):
        members = {f'r_type_{group}_{suffix}' for suffix in ('sp', 'ac', 'cr', 'bo')}
        if members <= ids:
            out.extend(context.data.items[item_id][20] for item_id in sorted(members)
                       if context.data.items[item_id][20] != 'n/a')
    return out


async def load(p):
    if not is_2016():
        return
    db = context.db
    await db.execute(SCHEMA_SQL)
    rows = await db.rows('SELECT CARID,KIND,EXPIRES,SPEED,ACCEL,BOOST,CRASH,SPECIAL,PARTS '
                         'FROM SKID_RENTCAR_TB WHERE SERVERID=%s AND CID=%s', (db.server_id, p.char.cid))
    by_id = {int(r[0]): Rental(*(int(v) for v in r[1:])) for r in rows}
    for car in p.char.cars:
        car.rental = by_id.get(car.car_id)


def list_frame(p):
    rows = [c.rental.encode(c.car_id) for c in p.char.cars if c.rental]
    return Frame(0xfb6, struct.pack('<I', len(rows)) + b''.join(rows))


async def expire(session, p):
    if not is_2016():
        return
    expired = [c for c in p.char.cars if c.rental and c.rental.expired()]
    fallback = next((c for c in p.char.cars if not c.rental), None)
    if not expired or not fallback:
        return
    db = context.db
    for car in expired:
        if p.char.cur_car == car.car_id:
            p.char.cur_car = fallback.car_id
            await db.execute('UPDATE SKID_CHARACTER_TB SET CURCAR=%s WHERE SERVERID=%s AND CID=%s',
                             (fallback.car_id, db.server_id, p.char.cid))
        from .items import mod_list, REMOVED, CHANGED
        gear = [it for it in p.items if it.car_id == car.car_id and it.item_id.startswith('r_type_')]
        # Return cosmetics and any non-rental gear to inventory, then remove the rental.
        await db.transaction(lambda cur, car_id=car.car_id: remove_in_db(cur, db.server_id, p.char.cid, car_id))
        for it in gear:
            p.items.remove(it)
        moved = [it for it in p.items if it.car_id == car.car_id]
        visuals = [it for it in p.vsitems if it.car_id == car.car_id]
        for it in moved + visuals:
            it.car_id, it.state = 0, 0
        if session.state.get('rental_ready'):
            if moved:
                send(session, mod_list(*((it, CHANGED) for it in moved)))
            if visuals:
                from .vshop import vs_mod_list
                send(session, vs_mod_list(*((it, CHANGED) for it in visuals)))
        if gear and session.state.get('rental_ready'):
            send(session, mod_list(*((it, REMOVED) for it in gear)))
        p.char.cars.remove(car)
        if session.state.get('rental_ready'):
            send(session, Frame(0x6d, struct.pack('<I', car.car_id) + p.car.encode()))
    if session.state.get('rental_ready'):
        p.apply_paints()
        from .cars import visual_update
        send(session, *stat_frames(p), list_frame(p), visual_update(session, p.car))


@on(SVC, C2S, 0xfb4)
async def redeem(session, frame):
    if not is_2016():
        return
    p = session.state.get('player')
    if not p or len(frame.payload) != 44:
        return
    async with LOCK:
        car_type, grade, kind, special, parts, inven, term, speed, accel, boost, crash = struct.unpack('<11I', frame.payload)
        capsule = next((i for i in p.items if i.inven_idx == inven and i.state == 0 and i.stack == 1), None)
        t = context.data
        info = t.item_info(capsule.table_idx) if capsule else None
        vis = t.visuals.get(t.visual_index.get(capsule.item_id)) if capsule else None
        fields = (vis.value or '').split() if vis else []
        if (not info or info.kind != 'rent_car_capsule' or len(fields) != 3 or not all(v.isdigit() for v in fields)
                or int(fields[0]) != car_type or int(fields[2]) != kind or grade != 9
                or kind not in (1, 2) or special > 3 or parts > 3):
            return error(session, '20036')
        rows = read_xlt(t._p('Init', 'RentCarOptionPoint.xlt'))
        preset = next((r for r in rows[3:] if r and r[0] == fields[1]), None)
        if not preset or len(preset) < 10:
            return error(session, '20036')
        minimum = tuple(int(preset[k]) for k in (2, 3, 5, 4))
        points = (speed, accel, boost, crash)
        if (not int(preset[6]) <= sum(points) <= int(preset[8])
                or any(n < lo or n > int(preset[9]) for n, lo in zip(points, minimum))):
            return error(session, '20036')
        # Earlier capsules lost the bought term (default purchase was the one-day pack).
        days = capsule.random or 1
        if term not in (0, days) or days not in (1, 7, 30):
            return error(session, '20036')
        if kind == 2:
            return error(session, 'Meter-rated rentals are not implemented yet.')
        from .cars import DEFAULT_COLOR, garage_space, visual_update
        if garage_space(p) <= 0:
            return error(session, 'Not Enough Garage Space')
        up = t.upgrade.get((car_type, 9))
        if not up:
            return error(session, '20036')
        db = context.db
        await db.execute(SCHEMA_SQL)
        rental = Rental(kind, now() + days * 86400, speed, accel, boost, crash, special, parts)
        specs = part_specs(parts)
        row = await db.transaction(lambda cur: redeem_in_db(cur, db.server_id, p.char.cid, inven, capsule.item_id,
                                                            p.char.name, car_type, DEFAULT_COLOR, float(up['capacity']),
                                                            rental, specs))
        if not row or int(row[0]) <= 0:
            return error(session, '20036')
        car = Car(int(row[0]), car_type, DEFAULT_COLOR, 9, 0, float(up['capacity']), 0., 0,
                  float(up['capacity']), float(up['efficiency']), rental=rental)
        p.char.cars.append(car)
        p.char.cur_car = car.car_id
        p.items.remove(capsule)
        given = []
        gid, idx = int(row[1]), int(row[2])
        for n, (info, slot, aid) in enumerate(specs, 1):
            it = Item(gid + n, idx + n, info.item_id, car.car_id, 1, 0, (slot << 16) | 1,
                      0, 1, '', '', 0, 0, info.table_idx)
            p.items.append(it)
            given.append(it)
        p.char.part_inven_idx = idx + len(given)
        p.apply_paints()
        from .items import mod_list, REMOVED, NEW
        send(session, mod_list((capsule, REMOVED), *((i, NEW) for i in given)), list_frame(p), Frame(0xfb5, car.encode()),
             *stat_frames(p), visual_update(session, car))
        session.state['rental_ready'] = True
        session.log.note(f'rental capsule {inven} -> car {car.car_id} type {car_type}, {days} days; '
                         f'points {rental.stats}, options {special}/{parts}')
