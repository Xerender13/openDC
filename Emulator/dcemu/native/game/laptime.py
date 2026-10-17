"""Lap Time (the battle zone's time-trial arenas), as the 2008 server runs them: Cmd_RoomDirectJoin with
filter 4, BS_Room::LapTimeReady 0x5a9ec0, LapTimeGate, LapTimeRecord 0x5ae330, BS_Room::OnTick (states
4 racing .. 8 next round), LapTimeTable (laptimeinfo.txt). Message layouts are the same in 2011.

Entering: the battle zone's Lap Time button sends 0x1bb RoomDirectJoin with filter 4 (@0xf8). The player
goes into the arena of its car's grade (one room per grade "V1".."V9", made when needed: room type 0x40,
which the client opens with its lap time dialog, 32 seats), as a normal join (0x1d4 to the others,
0x26e + 0x1be to the player), then
  0x528 LapTimeLoad (i32 map, i32 area): the round's track; the client loads it and enters the area.
  0x529 LapTimeReady (C>S: i32 ready time, u32 serial) -> 0x52a LapTimeStart to the player (start time =
        its ready time, start lap 0, safe start 1) and 0x52f LapTimeNotifyStart (serial, time, lap) to
        the others (BS_Room::LapTimeReady).
  0x52b LapTimeGate (serial, time, i32 gate time, f32): kept, no answer.
  0x52c LapTimeRecord (C>S: serial, time, i32 lap time ms, f32 lap time, i32 current lap, i32 total
        laps) -> to the room with the lap's reward filled in: u32 exp @0x1a, XiStrExpInfo, u32 level,
        i64 Mito @0x2e (laptimeinfo.txt row of the arena: exp and Mito per lap; play mode 'LAPTIME').
        The first racer to finish the last lap ends the round: 0x52d LapTimeFinishing (i32 time + 20 s)
        to everyone; 20 s later 0x52e LapTimeResult (u32 n, u32 page, n x (serial, f32 best lap, 3 u32
        reward items: none)), best lap first; 8 s later the next round: 0x528 with a new track.
Tracks: PVPTrackInfo.xlt rows with CityType 4 (map ids 70-73, one per city, 5 laps); the arena's
cities come from laptimeinfo.txt (columns 5-8). laptimeinfo column 2 is a level limit per arena ("V%d
arena: level %d or lower."); not applied unless emulator.ini [battlezone] laptime_level_limit = 1.
"""
import asyncio
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import admin, context
from .login import SVC, send

LAP_ROOM_TYPE, LAP_CAPACITY, LAP_FILTER = 0x40, 32, 4
FINISH_MS, RESULT_WAIT, NEXT_ROUND_WAIT = 20000, 20.0, 8.0
LAP_TRACK_TYPE = '4'

_table = None
_tracks = None


def table():
    """laptimeinfo.txt -> {grade: (level limit, exp per lap, Mito per lap, [city 1-4 open])}."""
    global _table
    if _table is None:
        _table = {}
        try:
            for line in open(os.path.join(context.data.server_data, '..', 'laptimeinfo.txt'), encoding='latin-1'):
                f = line.split()
                if len(f) >= 8 and f[0][:1] in 'Vv' and f[0][1:].isdigit():
                    _table[int(f[0][1:])] = (int(f[1]), int(f[2]), int(f[3]), [c for c in range(1, 5) if f[3 + c] == '1'])
        except OSError:
            pass
    return _table


def tracks():
    """{city: map id} of the lap time tracks (PVPTrackInfo CityType 4)."""
    global _tracks
    if _tracks is None:
        from ..data import read_xlt
        _tracks = {}
        rows = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
        head = rows[2]
        c_id, c_type = head.index('Id'), head.index('CityType')
        c_city = len(head) - 1 - head[::-1].index('city')
        for r in rows[3:]:
            if len(r) > c_city and r[c_type].strip() == LAP_TRACK_TYPE and r[c_id].strip().isdigit():
                _tracks.setdefault(int(r[c_city]), int(r[c_id]))
    return _tracks


def pick_track(grade):
    cities = [c for c in table().get(grade, (0, 0, 0, [1]))[3] if c in tracks()] or list(tracks())
    return tracks()[random.choice(cities)] if cities else 0


class Lap:
    """A lap time arena's round state, kept on its Room as room.lap."""
    def __init__(self, grade):
        self.grade = grade
        self.best = {}              # serial -> best lap (s)
        self.finishing = False
        self.task = None


def is_lap_room(room):
    return getattr(room, 'lap', None) is not None


def arena(grade, channel):
    from .rooms import OPEN, Room, lists_changed, rooms
    room = next((r for r in rooms.values() if is_lap_room(r) and r.lap.grade == grade and OPEN in r.seats), None)
    if room is None:
        # the channel is the lobby the button was pressed in (not a section id: with channel 4 the
        # SuperStar V8-V9 rule refused a V1 car, user 2026-10-13)
        room = Room(channel, LAP_ROOM_TYPE, pick_track(grade), 0, LAP_CAPACITY, f'V{grade} Lap Time', '')
        room.lap = Lap(grade)
        rooms[room.id] = room
        lists_changed(room.channel)
    return room


def enter(session, p):
    """0x1bb with filter 4: into the arena of the player's car grade."""
    from .rooms import direct_join
    player = session.state.get('player')
    car = player.car if player else None
    if not car:
        return
    grade = max(1, min(car.grade, 9))
    limit = table().get(grade, (9999,))[0]
    from .. import nation
    if context.laptime_level_limit and nation.rule(session, 'battle_levels') and player.char.level > limit:
        return admin.message(session, f'V{grade} arena: level {limit} or lower.')
    room = arena(grade, struct.unpack_from('<I', p)[0])
    direct_join(session, p, room)
    if room.member(session):
        session.log.note(f'lap time: V{grade} arena (room {room.id}), map {room.map_id}')
        send(session, load_frame(room))


def load_frame(room):
    return Frame(0x528, struct.pack('<ii', room.map_id, room.area))


def lap_room(session):
    from .rooms import room_of
    room = room_of(session)
    return room if room and is_lap_room(room) else None


@on(SVC, C2S, 0x529)
async def lap_ready(session, frame):
    room = lap_room(session)
    if not room or len(frame.payload) < 8:
        return
    m = room.member(session)
    ready_time, = struct.unpack_from('<i', frame.payload)
    # start lap: laps done so far (0 at the start; the 2008 server sends the player's lap count, 0 for a
    # newcomer). Sent as 1, the client began at lap 2 (user, 2026-10-13)
    send(session, Frame(0x52a, struct.pack('<iii', ready_time, 0, 1)))
    room.cast(Frame(0x52f, struct.pack('<iii', m.serial, ready_time, 0)), skip=m)


@on(SVC, C2S, 0x52b)
async def lap_gate(session, frame):
    pass


@on(SVC, C2S, 0x52c)
async def lap_record(session, frame):
    from .items import add_money
    from .progress import add_exp, play_mode
    room = lap_room(session)
    p = frame.payload
    if not room or len(p) < 0x14:
        return
    m = room.member(session)
    player = session.state['player']
    c = player.char
    _, rec_time, lap_ms, lap_s, current, total = struct.unpack_from('<IiifiI', p)
    lap = room.lap
    if lap_s > 0:
        lap.best[m.serial] = min(lap.best.get(m.serial, lap_s), lap_s)
    from .items import play_bonus
    _, exp, money, _ = table().get(lap.grade, (0, 0, 0, []))
    exp, money = play_bonus(player, exp, money)
    if exp:
        await add_exp(c, exp)
    if money:
        await add_money(c, money)
    await play_mode(c, 'LAPTIME', 1, 0, exp, money)
    session.log.note(f'lap time: lap {current}/{total} in {lap_s:.3f} s, +{exp} exp, +{money} Mito')
    room.cast(Frame(0x52c, struct.pack('<IiifiiI3IIq', m.serial, rec_time, lap_ms, lap_s, current, total, exp,
                                       c.exp, c.exp_next, c.exp_base, c.level, money)))
    if total and current >= total and not lap.finishing:
        lap.finishing = True
        room.cast(Frame(0x52d, struct.pack('<i', rec_time + FINISH_MS)))
        lap.task = asyncio.ensure_future(end_round(room))


async def end_round(room):
    from .rooms import rooms
    await asyncio.sleep(RESULT_WAIT)
    if rooms.get(room.id) is not room:
        return
    lap = room.lap
    order = sorted(lap.best.items(), key=lambda kv: kv[1])
    room.cast(Frame(0x52e, struct.pack('<II', len(order), 0)
                    + b''.join(struct.pack('<If3I', serial, best, 0, 0, 0) for serial, best in order)))
    await asyncio.sleep(NEXT_ROUND_WAIT)
    if rooms.get(room.id) is not room:
        return
    lap.best, lap.finishing = {}, False
    room.map_id = pick_track(lap.grade)
    room.cast(load_frame(room))
