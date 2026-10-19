"""Shared 2011/2016 apprentice tutorial: Driver Dome and the local Battle Zone training race.

Main.Apprentice makes the name wizard create Birdie RTI (type 95), colour 0x01000002.
The client recognizes a training car by the short at XiStrCarUnit+0x12 == 3 (2011
0x7087c0): the upper half of SLOT. Persist it and LASTPOSSTATE=3 for interrupted logins.
0x5d2 CompleteApprentice: four u32 (result, elapsed, starter type, colour).
0x5d3: four u32 (result, elapsed, returned car ID, reserve), permanent Car record,
       i32 Mito award, i64 total Mito. Size including type: 0x4f / 0x50.
Client handlers 2011 0x519510 / 2016 0x52ccb0 add/select the new car then remove the
returned one. They drive the field handoff locally; the next FirstPosition starts
Director Green's existing intro (state 0). No speculative training cash award.
"""
import struct

from ...handlers import on
from ...handlers.game import NEW_FLAGS
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .records import Car

TRAINING_TYPE = 95
TRAINING_SLOT = 3 << 16


def enabled():
    return bool(context.extra_flags.get('Main.Apprentice', NEW_FLAGS['Main.Apprentice']))


def training_car(car):
    return car is not None and car.car_type == TRAINING_TYPE and (car.slot >> 16) & 0xffff == 3


# Lock the character before checking/removing its training car. The DB condition also
# protects against duplicate requests from another connection with a stale player object.
COMPLETE_SQL = (
    "SET NOCOUNT ON; SET XACT_ABORT ON; BEGIN TRY BEGIN TRAN;"
    " DECLARE @sid numeric=%s, @cid numeric=%s, @old numeric=%s, @slot numeric=%s;"
    " DECLARE @new numeric=-1, @money bigint, @current numeric;"
    " SELECT @money=GOLD, @current=CURCAR FROM SKID_CHARACTER_TB WITH (UPDLOCK, HOLDLOCK)"
    " WHERE SERVERID=@sid AND CID=@cid;"
    " IF @current=@old AND EXISTS (SELECT 1 FROM SKID_CAR_TB WITH (UPDLOCK, HOLDLOCK)"
    " WHERE SERVERID=@sid AND CID=@cid AND CARID=@old AND CARTYPE=95 AND SLOT=@slot) BEGIN"
    " EXEC PC_SKID_CREATECAR @sid, @cid, %s, %s, %s, 1, 0, %s, 0, @new OUTPUT;"
    " IF ISNULL(@new,-1)<=0 THROW 50001, 'Cannot create apprentice starter', 1;"
    " DELETE FROM SKID_CAR_TB WHERE SERVERID=@sid AND CID=@cid AND CARID=@old;"
    " UPDATE SKID_CHARACTER_TB SET CURCAR=@new, NUMCAR=NUMCAR-1, LASTPOSSTATE=0,"
    " LASTCITYID=1, LASTAREA=-1, LASTPOSX=0, LASTPOSY=0, LASTPOSZ=0, LASTPOSW=0"
    " WHERE SERVERID=@sid AND CID=@cid; END;"
    " COMMIT; SELECT @new, @money;"
    " END TRY BEGIN CATCH IF @@TRANCOUNT>0 ROLLBACK; THROW; END CATCH;")


def completion_ack(old_id, car, mito, elapsed):
    return Frame(0x5d3, struct.pack('<4I', 0, elapsed, old_id, 0)
                 + car.encode() + struct.pack('<iq', 0, mito))


@on('native:game', C2S, 0x5d2)
async def complete(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) != 16 or not training_car(p.car):
        return
    result, elapsed, car_type, color = struct.unpack('<4I', frame.payload)
    t, db, c, old = context.data, context.db, p.char, p.car
    vehicle, up = t.vehicles.get(car_type, {}), t.upgrade.get((car_type, 1))
    # The creation picker selects the four models tagged 10001..40001, not any dealership car.
    if result != 0 or int(vehicle.get('Sellable') or 0) not in (10001, 20001, 30001, 40001) or not up:
        session.log.note(f'apprentice: refused starter {car_type}, result {result}')
        return
    capacity = float(up['capacity'])
    row = await db.row(COMPLETE_SQL, (db.server_id, c.cid, old.car_id, old.slot,
                                     c.name, car_type, color, capacity))
    if not row or int(row[0] or -1) <= 0:
        session.log.note('apprentice: training car already returned or character changed')
        return
    car = Car(int(row[0]), car_type, color, 1, 0, capacity, 0.0, 0,
              capacity, float(up['efficiency']))
    c.cars = [v for v in c.cars if v.car_id != old.car_id] + [car]
    c.cur_car, c.mito = car.car_id, int(row[1])
    c.pos_state, c.city, c.last_area, c.pos = 0, 1, -1, (0.0,) * 4
    p.apply_paints()
    session.to_client(completion_ack(old.car_id, car, c.mito, elapsed))
    from .items import NEW, link_keys, mod_list
    from .login import send, stat_frames
    keys = await link_keys(p)
    send(session, *([mod_list(*[(key, NEW) for key in keys])] if keys else []), *stat_frames(p))
    session.log.note(f'apprentice complete: {c.name!r}, elapsed {elapsed}, training {old.car_id}'
                     f' -> starter {car.car_id} (type {car_type}); field introduction next')
