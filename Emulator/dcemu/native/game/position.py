"""Where the character is: first position, city position, saving the car's position.

The 2008 server (Cmd_FirstPosition 0x5f33a0.., Cmd_MyCityPosition 0x5ee690, Cmd_SaveCarPos 0x5ecdd0)
keeps a position state (SKID_CHARACTER_TB.LASTPOSSTATE): 0 new, 1 in the tutorial gate, 2 in a
city, otherwise (3) in the driver dome (city 0).

0x30e FirstPosition -> 0x30f MyPositionAck (i32 city, i32 channel, XiVec4 position, i32 state;
    2011: one more byte, 0):
    state 0/1: city 1, channel -1 (the tutorial gate, area 3), one of TUTORIAL_STARTS at random,
               the state as stored (0 = new: the client's start message by Director Green)
    state 2:   the stored city (0 -> 1), a random channel 0-9, the stored position
    else:      city 0, the stored area as the channel, position 0
0x314 MyCityPosition (2011: i32 channel, u8 gate dialog: 1 going to the city, 0 gate chosen; echoed in
    0x30f's 2011 byte; 2008 reads the channel only) -> 0x30f: the stored
    city (0 -> 1), the asked channel, the stored position and state. Sent when the client goes into
    a city channel, e.g. at the end of the tutorial, right before its own 0xa2 with the Station 1
    position: the 2008 server answered the tutorial position (it handles 0x314 before that 0xa2),
    so the client put the car back where the tutorial ended. **Here a character in the tutorial
    gate (state <= 1) is put at Station 1 of Moon Palace** (Icon_Moonpalace_Client.tdf "Station 1",
    where the 2008 server put characters coming from the driver dome), state 2, and that is saved.
0xc80 CityLeaveCheck (2011; u32 city, char[255] arrival post, char[255] post to face, e.g. 3 "post_4rd_00506"
    "post_4rd_00505": driving into another city) -> 0xc81 CityLeaveCheckAck (u32 result 1, then the same 514
    bytes; client 0x519310: looks both posts up in that city, puts the car at the first facing the second and goes
    on). No handler until 2026-10-14 (user: entering another city did not work).
0xa2 SaveCarPos (i32 channel, XiVec4 position, i32 city, i32 state): kept, and written at once
    (the 2008 server wrote it with the character at logout: LASTAREA, LASTPOS*, LASTCITYID,
    LASTPOSSTATE).
"""
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, send

# BS (Cmd_FirstPosition): the 10 starts in the tutorial gate (x, y, z, heading), from ZoneServer.exe
TUTORIAL_STARTS = [(-2157.2, -205.05, 85.72, 90.97), (-1796.56, 144.41, 85.72, -167.71),
                   (-1395.23, 229.33, 94.33, -163.55), (-1095.65, 684.3, 95.99, -173.95),
                   (-738.07, 1229.89, 85.68, -169.93), (-1375.85, 1098.5, 103.3, -159.4),
                   (-881.33, 1558.56, 107.55, -175.38), (-1108.28, 1929.36, 132.91, -178.04),
                   (-1821.7, 2459.66, 168.1, -90.9), (-1083.99, 342.49, 93.68, -158.54)]
NEW, TUTORIAL, IN_CITY, DRIVER_DOME = 0, 1, 2, 3
TUTORIAL_CITY, TUTORIAL_CHANNEL = 1, -1
CHANNELS = 10
SAVE_SQL = ("UPDATE SKID_CHARACTER_TB SET LASTAREA=%s, LASTPOSX=%s, LASTPOSY=%s, LASTPOSZ=%s, LASTPOSW=%s,"
            " LASTCITYID=%s, LASTPOSSTATE=%s WHERE SERVERID=%s AND CID=%s")


def position_ack(city, channel, pos, state, select_gate=0):
    """0x30f; the 2011 byte @0x1c (frame 0x1e) = "show the gate selection" (client 0x516050: with the
    client switch Select_Gate_MainEX, a 1 keeps the gate dialog up instead of loading the city)."""
    return Frame(0x30f, struct.pack('<ii4fiB', city, channel, *pos, state, select_gate))


async def save(c):
    db = context.db
    await db.execute(SAVE_SQL, (c.last_area, *c.pos, c.city, c.pos_state, db.server_id, c.cid))


def station(city, n=1):
    x, y, z = context.data.stations[city][n]
    return (x, y, z, 0.0)


@on(SVC, C2S, 0x30e)
async def first_position(session, frame):
    p = session.state.get('player')
    if not p:
        return
    c = p.char
    if c.pos_state in (NEW, TUTORIAL):
        # the state as stored (2008 Cmd_FirstPosition 0x5f344e: MyPositionAck.state = LASTPOSSTATE): 0 for a new
        # character, which makes the client play Director Green's start message (StartMent_Client.tdf) in the tutorial
        # gate; the emulator sent 1 from the start and the message never came (user, 2026-10-15)
        c.city, c.pos = TUTORIAL_CITY, random.choice(TUTORIAL_STARTS)
        ack = position_ack(TUTORIAL_CITY, TUTORIAL_CHANNEL, c.pos, c.pos_state)
    elif c.pos_state == IN_CITY:
        ack = position_ack(c.city or 1, random.randrange(CHANNELS), c.pos, c.pos_state)
    else:
        ack = position_ack(0, c.last_area, (0.0,) * 4, c.pos_state)
    send(session, ack)


@on(SVC, C2S, 0x314)
async def my_city_position(session, frame):
    p = session.state.get('player')
    if not p:
        return
    c = p.char
    channel, = struct.unpack_from('<i', frame.payload)
    if c.pos_state <= TUTORIAL:
        c.city, c.pos, c.pos_state, c.last_area = TUTORIAL_CITY, station(TUTORIAL_CITY), IN_CITY, channel
        session.log.note(f'{c.name!r} leaves the tutorial gate: Station 1 {c.pos[:3]}')
        await save(c)
        from . import licenses                      # the license system starts now (login.TUTORIAL_FLAGS): Rookie
        await licenses.on_login(session, p)
    # the 2011 byte after the channel: 1 = the client is about to show the gate dialog (going to the
    # city), 0 = the gate was chosen there; echoed in 0x30f so the dialog stays until a gate is picked
    # (we sent 0 always and the client went straight to Gate 1: user, 2026-10-13)
    select_gate = frame.payload[4] if len(frame.payload) > 4 else 0
    session.log.note(f'city position: channel {channel}, gate dialog {select_gate}')
    send(session, position_ack(c.city or 1, channel, c.pos, c.pos_state, select_gate))


@on(SVC, C2S, 0xa2)
async def save_car_pos(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 28:
        return
    c = p.char
    channel, x, y, z, w, city, state = struct.unpack_from('<i4fii', frame.payload)
    c.last_area, c.pos, c.pos_state = channel, (x, y, z, w), state
    if city:
        c.city = city
    await save(c)
    if state == DRIVER_DOME:                    # the license reward is paid in the Driver Dome (licenses.pay_monthly)
        from .licenses import pay_monthly
        await pay_monthly(session, p)


@on(SVC, C2S, 0xc80)
async def city_leave_check(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4 + 2 * 0xff:
        return
    city, = struct.unpack_from('<I', frame.payload)
    post = frame.payload[4:4 + 0xff].split(b'\0')[0].decode('latin-1')
    session.log.note(f'city change to {city} at {post}')
    send(session, Frame(0xc81, struct.pack('<I', 1) + frame.payload[:4 + 2 * 0xff]))
