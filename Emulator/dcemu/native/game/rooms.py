"""Battle zone: the lobby's room list, race rooms and the race itself (the 2008 server's BS_PvpChannel
and BS_Room), in the 2011 client's layouts. Reference: Server/BATTLEZONE.md.

Offsets below are from the message type (as the client handlers and the 2008 structs count them); the
payload starts 2 later. 2011 against 2008: serials, seats and the room type are u32 (2008 u16 / i16),
XiPvpUserInfo 12 bytes (8), XiCarAttr 12 (8), XiPlayerInfo 216 (144).

Lobby
  0x1b8 RegisterRoomObserver (u32 PvP channel, filter, page, page size) -> 0x1b9 (i32 result 1, channel,
        filter, page, u32 Real Match on, u32 Real Match time, 2011 + 12 bytes) and the room list;
        0x1ba UnregisterRoomObserver. Observers get the list again whenever a room of their channel changes
        (BS_PvpChannel::MulticastDirty).
  0x1d0 RoomListAck: u32 page @2, pages @6, count @0xa, time @0xe, count x XiPvpRoomInfo @0x12. 2011
        entry 0x72 (client 0x52be30; 2008 0x68): u32 room, u16 map flag @4, u16 @6, u32 created @8, u16 map
        @0xc, u16 state @0xe, i16 area @0x10, u32 room type @0x12, u16 players @0x16, capacity @0x18,
        viewers @0x1a, viewer capacity @0x1c, wchar[30] name @0x1e, i64 team @0x5a, i64 team mark @0x62,
        8 more bytes.
Rooms
  0x1cc RoomCreate (0xa4): UserInfo @2, u32 room type @0xe, u16 map @0x12, capacity @0x14, map flag @0x16,
        u32 @0x18, @0x1c, wchar[30] name @0x20, password @0x5c, the car's XiCarAttr @0x98
        -> one frame: 0x26e RoomMaster (u32 room, u32 master serial), 0x1be RoomState, 0x1cd RoomCreateAck
        (UserInfo, i32 result 1, room, life id, u32 room type, map, map flag).
  0x1be RoomState (2008: 0x1ce): u32 result @2, room @6, life id @0xa, u16 map @0xe, map flag @0x10, u32
        room type @0x12, u16 state @0x16, i16 area @0x18, capacity @0x1a, viewers @0x1c, room ready @0x1e,
        wchar[40] name @0x20, seats u32[32] @0x70 (a serial, 0 open, 0xffffffff locked), u32 n @0xf0,
        members @0xf4 x 63 (u32 serial, u16 age, UserInfo, bool ready, XiCarAttr, wchar[16] name).
  0x26d RoomModify, both ways (2008: 0x26c): u32 room @2, u16 map @6, u32 map flag @8, u16 capacity @0xc,
        seats @0xe. The room master only (error 20151); the capacity cannot go below the members (20150).
  Joining. Every request carries the joiner's own UserInfo, XiCarAttr and XiPlayerInfo (0xd8), which are
  passed on to the room as they are:
    0x1d4 RoomJoin (0x184; the same layout both ways): u32 serial @2, u16 age @6, UserInfo @8, CarAttr
          @0x14, room @0x20, life id @0x24, PlayerInfo @0x28 (name @0, u16 serial @0x1a, age @0x1c as
          2008), seats @0x100, u32 room type @0x180.
    0x1bc RoomSecureJoin: serial @2, UserInfo @6, CarAttr @0x12, room @0x1e, life id @0x22, PlayerInfo
          @0x26, wchar[30] password @0xfe.
    0x1bb RoomDirectJoin (any room with a free seat): channel @2, serial @6, UserInfo @0xa, PlayerInfo
          @0x16, CarAttr @0xee, filter @0xfa; 0x1bd RoomIdDirectJoin: the same + room @0xfe.
    0x1d7 ChannelRoomJoin: serial @2, UserInfo @8, CarAttr @0x14, channel @0x20, room @0x24, life id
          @0x28, PlayerInfo @0x2c.
  BS_Room::JoinPvpRoom: errors 20146 no such room, 20158 not waiting, 20162 wrong password, 20039 full;
  the members get 0x1d4 with the new seats, the joiner 0x26e and 0x1be (which opens its room dialog).
  0x1d5 RoomLeave / 0x1d6 RoomBanish (0x8a, both ways): u32 serial @2, seats @6, u32 room type @0x86. The
        others get 0x1d5; a banished member gets its own 0x1d6 too (its client closes the room). When
        the master leaves, the next member becomes master (BS_Room::ReassignBoss, 0x26e); an empty room is
        deleted. A dropped connection leaves the same way.
  0x270 (2011 only): a member moves to a free seat, see change_seat().
  The host is banished (0x1d6) when everyone has been ready for 15 s and it has not started
  (BS_Room::OnTick; Room.watch_start).
  0x1e5 PvpReadyState (u32 serial, bool ready): to the room, with the sender's serial. The master is
        always ready (its 0x1be record had ready = 1 in the 2008 recording); the client draws "Start" on
        the host from that.
Race (BS_Room::StartLoad, LoadComplete, RemoveFromWaitSet, Gate, EndRace, PvpRaceResult)
  0x1e6 PvpStartReq (i32 map, map flag, start time): without a room a practice run (see practice());
        apprentice map11 starts locally and must retain its local time=-1 lesson setup (no PvpLoad reply).
        else the master (20181), with members (20180), everyone else ready (20182), not loading yet (20186) -> to the room 0x1e7 PvpLoad (i32 type 0, map, map flag,
        area, f32 best record, start time, i32 traffic -1). The area (BArea, native/area.py) is 900 + room.
        A room with one member starts a practice run instead (type 100, nothing more from the server;
        emulator.ini [battlezone] practice_alone, on by default).
  0x1e8 PvpLoadingStatus (u32 serial, f32 percent): to the others.
  0x1e9 PvpLoadComplete (i32 time, percent): when the last member has loaded, 0x1ea PvpGo (that time,
        countdown 19500 ms, char[32] battle string) to the room.
  0x1ed PvpGate (u32 serial, i32 gate, gate time, f32 record, f32 collision points: 100 = none) -> to
        the room 0x1ee PvpGateReward (serial, i32 reward 0-7; 0 = nothing): drawn by the number of racers,
        the racer's position at that gate and "clean" from Emulator/server_data/gate_rewards.txt, which holds the
        2008 server's chances (BS_Room::Gate: s_fReward_2/3/4 up to 4 racers, s_fSingleReward[clean][7]
        [32] with the position scaled by FixedRank for more) and can be edited; team rooms with more than 4
        racers use Emulator/server_data/team_gate_rewards.txt (s_fTeamReward, with Team Boost 50%).
  0x1eb PvpEnd (u32 serial, i32 end type 1 finished / 2 retired, end time, f32 record, i32 rank, f32
        distance, XiPvpEventCounter): to the room with the rank the server counts; the first finisher
        starts the 20 s end: 0x1ef PvpFinish (end time + 20000). When everyone has ended, or 23 s after
        the first finish, the result: 0x26e, then 0x1ec PvpResult (i32 kind 1, u32 team points x 2, f32
        best record, i32 time, i32 n, n x 60: end type, serial, u32 money gained, u64 money, u32 exp
        gained, f32 record, u16 rank, u16 level, XiStrExpInfo, u32 point, u32 flag, 8 more bytes). The
        room waits again, nobody ready.
  Rewards (PvpRaceResult): rank = the finishing order, or the number of racers for someone who did not
        finish. Exp = pvpexpbase.txt[rank][racers] x pvpexprate.txt[PvP channel]; Mito = pvpmoneybase.txt
        [the car's grade, 1-9] x pvpmoneyrate.txt[rank][racers] (data.Tables.pvp_reward); a race alone
        gives nothing (as recorded from the 2008 server). PLAYMODE 'PVP' counts the race and the win.
        The exp multiplier and the car grades allowed per section: emulator.ini [battlezone] (car_allowed).
Teams: 0x26f RoomChangeTeam (change_team), team points in 0x1ec (team_point, team_room). Not here yet: Real Match (0x1c7), observers (0x1db..0x1e0),
0x1c9 GetRoomInfo, 0x1d3 RoomNotifyChange (a member changing its car in the room), item races.
"""
import asyncio
import dataclasses
import itertools
import os
import random
import struct
import time

from .records import pack_exp
from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import admin, context, now
from .items import add_money, play_bonus
from .login import SVC, error, serial_of, sessions, send
from .progress import add_exp, play_mode
from .records import wstr
from ..version import is_2016

SEATS, OPEN, LOCKED = 32, 0, 0xffffffff
WAIT, LOADING, RACING = 0, 1, 2
FINISHED, RETIRED = 1, 2
COUNTDOWN_MS, FINISH_MS = 19500, 20000
RESULT_GRACE, LOAD_TIMEOUT = 3.0, 120.0
HOST_START_SECONDS = 15             # BS_Room::OnTick (0x3a98 ms)
AREA_BASE = 900
PRACTICE, PRACTICE_AREA_BASE = 100, 20000   # 0x1e7 type of a practice run; its area = base + serial
MISSION_ROOM = 0x10000      # room type of a Mission Battle room (the client makes it itself, instant.py): a real race alone,
                            # its reward is the instant mission's (0x3e2), not the battle's
ARENA_SECTION = 13          # 2016: battle zone section "Mission Battle Arena" (missionarena.py; client 0x67dffe)


def mission_room(room):
    """A Mission Battle room: the item one (MISSION_ROOM) or, on 2016, any room of the arena section. Its start is a
    practice run, it has no gates and pays as its mission, not as a battle."""
    return bool(room.type & MISSION_ROOM) or (is_2016() and room.channel == ARENA_SECTION)
USER_INFO, CAR_ATTR, PLAYER_INFO = 12, 12, 0xd8     # 2011 sizes; 2016: user_info_size() / car_attr_size()


# 2016 (client senders 0x84a44f 0x1cc, 0x1d4 / 0x1bc / 0x1bb / 0x1bd / 0x1d7; 0x1be handler 0x543040, member stride
# 0x47): UserInfo and XiCarAttr are 16 bytes each (both + a trailing u32), so everything after them moves; PlayerInfo
# stays 0xd8. A 2011 layout read from a 2016 client gave rooms map 128 / capacity 1 and member names 8 bytes short
# ("nder" for Xerender; user 2026-10-20).
def user_info_size():
    return 16 if is_2016() else 12


def car_attr_size():
    return 16 if is_2016() else 12


def sized(raw, size):
    return bytes(raw).ljust(size, b'\0')[:size]


# Join requests, payload offsets (type excluded): UserInfo, XiCarAttr, room, PlayerInfo (and the extras).
JOIN = {2011: {0x1d4: (6, 0x12, 0x1e, 0x26), 0x1bc: (4, 0x10, 0x1c, 0x24), 0x1d7: (6, 0x12, 0x22, 0x2a)},
        2016: {0x1d4: (6, 0x16, 0x26, 0x2e), 0x1bc: (4, 0x14, 0x24, 0x2c), 0x1d7: (6, 0x16, 0x2a, 0x32)}}
SECURE_PASSWORD = {2011: 0xfc, 2016: 0x104}
# 0x1bb / 0x1bd: UserInfo, PlayerInfo, XiCarAttr, filter, room (0x1bd)
DIRECT = {2011: (8, 0x14, 0xec, 0xf8, 0xfc), 2016: (8, 0x18, 0xf0, 0x100, 0x104)}
# 0x1cc: room type (u32, map u16, capacity u16, map flag u16), u32 x2, name, password, XiCarAttr
CREATE = {2011: (0xc, 0x16, 0x1e, 0x5a, 0x96), 2016: (0x10, 0x1a, 0x22, 0x5e, 0x9a)}


def year():
    return 2016 if is_2016() else 2011

rooms = {}                          # room id -> Room
_ids = itertools.count(1)


class Member:
    def __init__(self, session, user_info, car_attr, player_info=None):
        self.session = session
        self.serial = serial_of(session)
        self.user_info = sized(user_info, user_info_size())
        self.car_attr = sized(car_attr, car_attr_size())
        self.player_info = player_info
        self.ready = False
        self.loaded = False
        self.end = None             # (end type, end time, record, rank) once the race is over for it

    @property
    def player(self):
        return self.session.state.get('player')

    @property
    def name(self):
        return self.player.char.name if self.player else ''

    @property
    def age(self):
        return self.session.state.get('visual_age', 1) & 0xffff

    def unit(self):
        # the room master's record says ready (as recorded from the 2008 server): without it the 2011
        # client shows no "Start" on the host and cannot start (user, 2026-10-13)
        return (struct.pack('<IH', self.serial, self.age) + self.user_info + struct.pack('<?', self.ready)
                + self.car_attr + wstr(self.name, 32))

    def info(self):
        """XiPlayerInfo as the client sent it; name, serial and age are ours when it sent none."""
        b = (self.player_info or b'').ljust(PLAYER_INFO, b'\0')[:PLAYER_INFO]
        if not read_wstr(b, 0, 26) and self.player:
            from .misc import player_info
            b = player_info(self.session)
        return b


class AiMember:
    """An AI racer in a room (a member whose serial is above 0xffff). It has no connection: the room's messages
    are not sent to it, it is always ready, nobody waits for it. One player's client drives it: the AI joins
    as serial key << 16; right after the race's load one 0x271 with all the room's AIs names their driver and the clients make
    each serial key << 16 | driver (both clients: 2011 0x77b1c0, 2016 0x7d91f0, below). The clients look an AI up by
    key << 16 only, and each 0x271 first empties the client's list of AIs it drives (vfunc 0x1dc = 0x7d6020): one
    0x271 per AI left only the last one driven (user, 2026-10-20). At the next start each AI leaves and joins again
    unassigned (Room.reset_ais) for the next 0x271."""
    session = None
    player = None
    loaded, end = True, None

    def __init__(self, key, row, car_type, driver):
        self.key, self.row = key, row
        self.driver = driver & 0xffff
        self.assigned = False       # its 0x271 was sent (a race is on)
        self.ai_idx, self.name, self.level = row
        self.user_info = sized(struct.pack('<HHHHI', 0, self.level, 0, 0, 0), user_info_size())
        self.car_type, self.color = car_type, 0x08000002
        # the clients key a car by (car attr word 0) << 16 | serial low word (2016 0x558e40, from 0x7d93c9) and find a
        # member's car by its serial (0x7d5f80 -> 0x556c10): word 0 = the key makes the car key the AI's serial.
        # With 0 every AI was the driver's own car (user, 2026-10-20: one AI car, the driver's name, not moving);
        # with 0x4000 + key the race found no AI car for its member: the AIs never ranked ahead (Pos 1/4)
        self.car_attr = sized(struct.pack('<HHII', key, car_type, self.color, 0x82cccccc), car_attr_size())
        self.ready = True
        self.age = 1

    @property
    def serial(self):
        return self.key << 16 | self.driver if self.assigned else self.key << 16

    def unit(self):
        return (struct.pack('<IH', self.serial, self.age) + self.user_info + struct.pack('<?', True) + self.car_attr
                + wstr(self.name, 32))

    def joined_frame(self, room):
        """0x1d4 as for a player."""
        return Frame(0x1d4, struct.pack('<IH', self.serial, self.age) + self.user_info + self.car_attr
                     + struct.pack('<II', room.id, room.life_id) + self.info() + room.seat_bytes()
                     + struct.pack('<I', room.type))

    def entry(self):
        """0x271 record, 6 u32 = Cmd_RoomAiCarAssign (2016 name; 2011 handler 0x52c420 -> room vfunc 0x1d4 =
        0x77b1c0, 2016 0x542270 -> vfunc 0x1e0 = 0x7d91f0): key (the member whose serial is key << 16),
        driver (the low word of its new serial; the client whose own serial ([net+0x3d414] 2011 /
        [net+0x3d41c] 2016) it is drives the AI: 2016 0x7d9632 -> 0x7d9800 / 0x456220), AICarParam Idx
        (its name from the client's table), car type (-> member car attr +2), colour, second colour."""
        return struct.pack('<6I', self.key, self.driver, self.ai_idx, self.car_type, self.color, 0x82cccccc)

    def info(self):
        b = bytearray(PLAYER_INFO)
        b[0:26] = wstr(self.name, 26)
        struct.pack_into('<HH', b, 0x1a, 0, 1)
        struct.pack_into('<H', b, 0x26, self.level)
        return bytes(b)


_ai_table = None


def ai_table():
    """AICarParam.xlt (the client's AI drivers): [(Idx, name, AI level, [car types])]."""
    global _ai_table
    if _ai_table is None:
        from ..data import read_xlt
        _ai_table = []
        try:
            for r in read_xlt(os.path.join(context.data.root, 'Init', 'AICarParam.xlt'))[3:]:
                if len(r) > 3 and r[0].strip().isdigit():
                    cars = [int(c) for c in r[3].split() if c.isdigit()]
                    _ai_table.append((int(r[0]), r[1].strip(), int(r[2]) if r[2].strip().isdigit() else 1, cars))
        except OSError:
            pass
    return _ai_table


_ai_tracks = None


def ai_tracks():
    """Map ids (PVPTrackInfo.xlt "Id") of the tracks with AI support (column "AI" = 1)."""
    global _ai_tracks
    if _ai_tracks is None:
        from ..data import read_xlt
        _ai_tracks = set()
        try:
            rows = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
            c_id, c_ai = rows[2].index('Id'), rows[2].index('AI')
            for r in rows[3:]:
                if len(r) > c_ai and r[c_id].strip().isdigit() and r[c_ai].strip() == '1':
                    _ai_tracks.add(int(r[c_id]))
        except (OSError, ValueError):
            pass
    return _ai_tracks


def pick_ai(level, taken):
    """An AI driver near the host's level that is not in the room yet."""
    rows = [r for r in ai_table() if r[0] not in taken and r[3]] or [r for r in ai_table() if r[3]]
    if not rows:
        return None
    best = min(abs(r[2] - level) for r in rows)
    r = random.choice([r for r in rows if abs(r[2] - level) <= best + 2])
    # AICarParam lists traffic and HUV models too (ids 20001.. are traffic cars: user saw them); only
    # player cars, else a dealership car
    vl = context.data.vehicles
    # only cars the client has (VehicleList "Support" = 1): the 2016 client crashed loading car 49, BMW 760Li, Support 0
    # ("GetVehicleInfo - wrong id: 49", "carmodel fail"; user, 2026-10-20)
    def usable(v):
        return v.get('Desc') == 'PlayerCar' and v.get('Support', '1') == '1'
    cars = [c for c in r[3] if usable(vl.get(c, {}))] or \
        [k for k, v in vl.items() if usable(v) and v.get('Sellable') == '1']
    return (r[0], r[1], r[2]), random.choice(cars)


class Room:
    def __init__(self, channel, room_type, map_id, map_flag, capacity, name, password):
        self.id = next(_ids)
        self.life_id = self.id
        self.channel, self.type, self.map_id, self.map_flag = channel, room_type, map_id, map_flag
        self.capacity = max(1, min(capacity, SEATS))
        self.name, self.password = name, password
        self.created = now()
        self.state = WAIT
        self.members = []
        self.lap = None              # laptime.Lap for a lap time arena
        self.ai_keys = 0             # AI racers made so far (serial = n << 16)
        self.observers = []         # sessions watching the room (spectators)
        self.master = 0
        self.seats = [OPEN if i < self.capacity else LOCKED for i in range(SEATS)]
        self.waiting = set()        # serials still loading / racing
        self.racers = []            # serials that started the race
        self.rank = 0
        self.gates = {}             # gate index -> the serials that passed it, in order
        self.first_end = None       # end time of the first finisher
        self.timer = None
        self.kick_timer = None      # the host is banished when it runs out (everyone ready, no start)

    @property
    def area(self):
        return AREA_BASE + self.id

    def member(self, session):
        return next((m for m in self.members if m.session is session), None)

    @property
    def humans(self):
        return [m for m in self.members if m.session]

    def by_serial(self, serial):
        return next((m for m in self.members if m.serial == serial), None)

    def cast(self, *frames, skip=None):
        """To the members (not the AI racers). Spectators do not get these: a spectating client that receives 0x1e7 PvpLoad
        loads the track as a racer and drives (user, 2026-10-13); they follow the room through 0x1bf
        (refresh_observers: state and area) and get the result."""
        for m in self.members:
            if m is not skip and m.session:
                send(m.session, *frames)

    def head(self):
        return struct.pack('<IIIHHIHhHHH', 1, self.id, self.life_id, self.map_id, self.map_flag & 0xffff, self.type,
                           self.state, self.area if self.state != WAIT else -1, self.capacity, len(self.observers), 0)

    def obs_state_frame(self, result=1):
        """0x1bf, the spectator's room state (2008: 0x1df OBSState; 2011 client handler 0x52e160): the
        0x1be head, u16 @0x20, u16 @0x22 (not known, 0), wchar[41] name @0x24, i32 score[4] @0x76, i64 team
        id[2] @0x86, i64 team mark[2] @0x96, wchar[31] team name[2] @0xa6, seats @0x122, u32 n @0x1a2,
        members @0x1a6 x 63 as in 0x1be."""
        # result (client 0x52e860): 1 the state; 2 "You cannot enter the room anymore." (10030) and 3 "This room no
        # longer exists." (10031, the room cleared too) both close the spectator view
        teams = getattr(self, 'obs_teams', None)    # a channel battle round: the crews and the round states (channels.py)
        teams = teams() if teams else bytes(16) + struct.pack('<4q', -1, -1, 0, 0) + bytes(124)
        return Frame(0x1bf, struct.pack('<i', result) + self.head()[4:] + bytes(4) + wstr(self.name, 82) + teams
                     + self.seat_bytes() + struct.pack('<I', len(self.members))
                     + b''.join(m.unit() for m in self.members))

    def refresh_observers(self):
        """BS_OBSRoom::OnTick sends the state again when the room changed."""
        for s in self.observers:
            send(s, self.master_frame(), self.obs_state_frame())

    def seat_bytes(self):
        return struct.pack(f'<{SEATS}I', *self.seats)

    def master_frame(self):
        return Frame(0x26e, struct.pack('<II', self.id, self.master))

    def state_frame(self):
        return Frame(0x1be, self.head() + wstr(self.name, 80) + self.seat_bytes() + struct.pack('<I', len(self.members))
                     + b''.join(m.unit() for m in self.members))

    @property
    def ais(self):
        return [m for m in self.members if not m.session]

    def ai_by_car(self, car_key):
        """The AI racer of a car key from its driver's client (0x1ed / 0x1eb: car attr word 0 << 16 | driver serial)."""
        return next((a for a in self.ais if struct.unpack_from('<H', a.car_attr)[0] == car_key >> 16), None)

    def set_ai_serials(self, change):
        """Apply change(ai) to each AI racer and keep the seats on their serials."""
        for ai in self.ais:
            old = ai.serial
            change(ai)
            self.seats = [ai.serial if v == old else v for v in self.seats]

    def assign_ais(self):
        """One 0x271 with all the AIs, driven by the master's client: 2016 right after the load (0x1e7), 2011 when every
        member has loaded, just before the go (0x1ea; see start_request)."""
        if not self.ais:
            return
        def assign(ai):
            ai.driver, ai.assigned = self.master & 0xffff, True
        self.set_ai_serials(assign)
        self.cast(Frame(0x271, struct.pack('<I', len(self.ais)) + b''.join(a.entry() for a in self.ais)))

    def reset_ais(self):
        """At the next start (before the 0x1e7): each AI of the last race leaves and joins again under key << 16 (the
        clients keep the assigned serials and find an AI by key << 16 only)."""
        for ai in self.ais:
            if not ai.assigned:
                continue
            self.cast(Frame(0x1d5, struct.pack('<I', ai.serial) + self.seat_bytes() + struct.pack('<I', self.type)))
            old = ai.serial
            ai.assigned = False
            self.seats = [ai.serial if v == old else v for v in self.seats]
            self.cast(ai.joined_frame(self), ready_frame(ai))

    def list_entry(self):
        return (struct.pack('<IHHIHHhIHHHH', self.id, self.map_flag & 0xffff, 0, self.created & 0xffffffff, self.map_id,
                            self.state, self.area if self.state != WAIT else -1, self.type, len(self.members),
                            self.capacity, len(self.observers), 0)   # spectators @0x1a (was 0: user, 2026-10-16)
                + wstr(self.name, 60) + struct.pack('<qq', -1, 0) + bytes(8))

    def cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def modify_frame(self):
        return Frame(0x26d, struct.pack('<IHIH', self.id, self.map_id, self.map_flag, self.capacity) + self.seat_bytes())

    def all_ready(self):
        return self.state == WAIT and len(self.humans) > 1 and all(m.ready for m in self.members)

    def watch_start(self):
        """BS_Room::OnTick: a waiting room with more than one member where everyone is ready, and the
        host does not start for 15 s -> the host is banished (the next member becomes host, and the
        15 s start again). Called whenever the ready states or the members change."""
        if not self.all_ready():
            if self.kick_timer:
                self.kick_timer.cancel()
                self.kick_timer = None
        elif not self.kick_timer:
            self.kick_timer = asyncio.ensure_future(self._kick_host())

    async def _kick_host(self):
        await asyncio.sleep(HOST_START_SECONDS)
        self.kick_timer = None
        host = self.by_serial(self.master)
        if rooms.get(self.id) is self and self.all_ready() and host:
            host.session.log.note(f'room {self.id}: everyone ready for {HOST_START_SECONDS} s, the host is banished')
            leave(host.session, banished=True)


def room_of(session):
    return rooms.get(session.state.get('room'))


# ---- Real Match -----------------------------------------------------------------------------------------
# Rooms whose type has 0x100 (and not 0x200; the 2011 client makes them in the lobby with PvP channel
# 6, types 0x180 / 0x580): every racer gets the same stats and parts, 0x1c7 RealMatchInfo, when it
# enters the room (XiRealMatch::SendRealMatchInfo; sent before the room state as the 2008 server did).
#   2008 (XiRealMatch::XiRealMatch, XiRealMatchStat::StatUpdate 0x5a0170): based = the stats of car type
#   50 at grade 9, equip = the values of eight fixed parts (table 0x700f20), nothing else; each part
#   has two fixed options (not sent yet: the option ids of the 2011 item record are not known).
#   2011 0x1c7 (client 0x52b480 / 0x727600): XiStrStatInfo (104) @2, XiStrEnChantBonus (40) @0x6a and
#   @0x92, XiVisualItem (56) @0xba, u32 n @0xf2, n x 76 @0xf6: u32 item TableIdx + the item unit (72).
# The racers keep their own car models; the client's per-seat liveries and numbers (effects\realmatch)
# go with the content flag Etc.RealMatchEffect (3 bits; emulator.ini realmatch_effect).
# Everyone drives one car chosen by the server (emulator.ini realmatch_car = car type, grade; the stats'
# base is the same car): enter_real_match / exit_real_match.
# Open hours (emulator.ini [battlezone] realmatch): always, off, or schedule = the 2008 server's
# realmatchtable.txt (weekday 0 = Sunday, hour 0-24), each entry open for realmatch_minutes. Closed:
# 0x1b9 says so (with the next opening) and such rooms cannot be created or started.
REAL_MATCH, NOT_REAL_MATCH = 0x100, 0x200
SPECTATORS_ALLOWED = 0x80           # room type bit: the room option "Spectating"
REAL_MATCH_CAR = (50, 9)            # the 2008 server's base for the stats: car type, grade
REAL_MATCH_PARTS = ('si_s02_001', 'si_s02_002', 'si_s02_003', 'si_s02_004',
                    'si_a02_001', 'si_a02_002', 'si_a02_003', 'si_a02_004')
REAL_MATCH_CLOSED = 'Real Match is closed now.'


def is_real_match(room_type):
    return bool(room_type & REAL_MATCH) and not room_type & NOT_REAL_MATCH


def real_match_slots():
    """[(weekday, hour)] of realmatchtable.txt, weekday 0 = Sunday."""
    slots = []
    try:
        for line in open(os.path.join(context.data.server_data, '..', 'realmatchtable.txt'), encoding='latin-1'):
            f = line.split()
            if len(f) >= 2 and f[0].isdigit() and f[1].isdigit():
                slots.append((int(f[0]) % 7, int(f[1])))
    except OSError:
        pass
    return slots


# GM override of emulator.ini realmatch (gm_realmatch): None = the ini, ('closed',), ('open', since), or ('at', start)
# = closed until start (real time), then open for realmatch_minutes, then back to the ini
_rm_override = None


def gm_realmatch(args):
    """realmatch open | close | in MINUTES | auto | status -> the reply text (chat gmrealmatch, control port)."""
    global _rm_override
    t = time.time()
    what = args[0].lower() if args else 'status'
    if what == 'open':
        _rm_override = ('open', t - t % 60)
    elif what in ('close', 'closed'):
        _rm_override = ('closed',)
    elif what == 'in' and len(args) > 1 and args[1].replace('.', '', 1).isdigit():
        _rm_override = ('at', int(t + float(args[1]) * 60) + 1)   # whole second, after now: the 'N minutes' notice is sent
    elif what == 'auto':
        _rm_override = None
    elif what == 'car':
        return gm_realmatch_car(args[1:])
    elif what != 'status':
        return 'realmatch open | close | in MINUTES | auto | status | car [NAME [V1-V9]]'
    is_open, at = real_match_times(t)
    shown = time.strftime('%a %H:%M:%S', time.localtime(at - (now() - int(t)))) if at else 'none'
    source = {None: f'emulator.ini ({context.realmatch})', 'closed': 'GM: closed', 'open': 'GM: open',
              'at': 'GM: countdown'}[_rm_override and _rm_override[0]]
    return f'Real Match {"open" if is_open else "closed"} ({source}); {"opened" if is_open else "next opening"}: {shown}'


def gm_realmatch_car(args):
    """realmatch car [NAME [V1-V9]]: the car everyone drives in Real Match (context.realmatch_car; until the
    emulator restarts, then emulator.ini realmatch_car). NAME as gmcar finds it (shown name, model, file name or
    Unique Id); the grade V9 when not given. Players in the battle zone get the new car at once: their section
    again (0x1b9: the 2016 client's Real Match car), and waiting Real Match rooms' members drive it."""
    from .misc import find_cars
    t = context.data
    if not args:
        car_type, grade = context.realmatch_car or REAL_MATCH_CAR
        v = t.vehicles.get(car_type, {})
        return f'Real Match car: {v.get("UI Name", "?")} ({v.get("Car Name", "?")}, type {car_type}) V{grade}'
    grade = 9
    if len(args) > 1 and args[-1].lower().lstrip('v').isdigit():
        grade, args = int(args[-1].lower().lstrip('v')), args[:-1]
    found = find_cars(' '.join(args))
    if not found or not 1 <= grade <= 9:
        return 'realmatch car NAME [V1-V9]: no such car' if not found else 'grade V1-V9'
    if len(found) > 1:
        return 'more than one car: ' + ', '.join(f'{v.get("UI Name")} ({u})' for u, v in found[:8])
    car_type, v = found[0]
    if (car_type, grade) not in t.upgrade:
        return f'{v.get("UI Name")} has no V{grade}'
    context.realmatch_car = (car_type, grade)
    info = real_match_info()
    for s in list(sessions.values()):
        obs = s.state.get('room_observer')
        if obs and s.state.get('room') is None:
            send(s, section_frame(s, s.state.get('pvp_channel', obs.get('channel', 0))))
    for room in list(rooms.values()):
        if not is_real_match(room.type) or room.state != WAIT:
            continue
        for m in room.members:
            if getattr(m, 'session', None):
                send(m.session, info)
                enter_real_match(m.session, m)
        room.cast(room.state_frame())
    return f'Real Match car: {v.get("UI Name")} ({v.get("Car Name")}, type {car_type}) V{grade}'


def real_match_times(t=None):
    """-> (open now, time_t on the server clock of the current or next opening; 0 if none)."""
    global _rm_override
    t = time.time() if t is None else t
    shift = now() - int(time.time())
    if _rm_override:
        kind = _rm_override[0]
        if kind == 'closed':
            return False, 0
        if kind == 'open':
            return True, int(_rm_override[1]) + shift
        start = _rm_override[1]
        if t < start:
            return False, int(start) + shift
        if t < start + context.realmatch_minutes * 60:
            return True, int(start) + shift
        _rm_override = None                 # the GM's opening is over: the ini again
    mode = context.realmatch
    if mode == 'always':
        return True, now() - now() % 3600
    if mode != 'schedule':
        return False, 0
    t = time.time() if t is None else t
    lt = time.localtime(t)
    midnight = t - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
    sunday = midnight - ((lt.tm_wday + 1) % 7) * 86400
    length = context.realmatch_minutes * 60
    starts = sorted(sunday + week * 604800 + day * 86400 + hour * 3600
                    for week in (-1, 0, 1) for day, hour in real_match_slots())
    shift = now() - int(time.time())
    for start in starts:
        if start <= t < start + length:
            return True, int(start) + shift
    nxt = next((s for s in starts if s > t), 0)
    return False, int(nxt) + shift if nxt else 0


REAL_MATCH_NOTICE_MINUTES = (10, 5, 2, 1)   # user, 2026-10-15
_rm = {'last': 0.0, 'open': None}


def real_match_tick():
    """Once a second (rush.py's ticker), schedule mode only: 0x1c8 RealMatchNotice (u32 time on the client clock,
    u32 type; client 0x52bac0) to everyone in the game - type 0 "Real Match will begin in %d minutes" (10840 /
    10841, counted to the time) 10 / 5 / 2 / 1 minutes before an opening, type 1 "Real Match Started! Time
    Left: %d minutes." (10842, the client fills 50) when it opens. (Types 2 "will end in" (time + 3000 s), 3
    "Real Match Finished!" not sent: the client's 50 minutes need not match realmatch_minutes.)"""
    from .login import sessions
    t = time.time()
    last, _rm['last'] = _rm['last'] or t, t
    if context.realmatch != 'schedule' and not _rm_override:
        _rm['open'] = None
        return
    is_open, at = real_match_times(t)
    frames = []
    if is_open and _rm['open'] is not True and (_rm['open'] is False or _rm_override):
        frames.append(Frame(0x1c8, struct.pack('<II', at, 1)))
    _rm['open'] = is_open
    if not is_open and at:
        real_at = at - (now() - int(t))
        frames += [Frame(0x1c8, struct.pack('<II', at, 0)) for m in REAL_MATCH_NOTICE_MINUTES
                   if last < real_at - m * 60 <= t]
    for f in frames:
        for s in list(sessions.values()):
            if s.state.get('player'):
                send(s, f)


def real_match_info():
    """0x1c7 for everyone alike."""
    from .records import Stats, enchant_bonus
    t = context.data
    stats = Stats(based=t.car_stats(*(context.realmatch_car or REAL_MATCH_CAR)))
    equip, parts = [0, 0, 0, 0], []
    for item_id in REAL_MATCH_PARTS:
        idx, stat = t.item_index.get(item_id), t.part_stat(item_id)
        if idx is None or not stat:
            continue
        equip[stat[0]] += stat[1]
        parts.append(struct.pack('<I', idx) + struct.pack('<ii2I2Iii I', 1, 0, 0, 0, 0, 0, 0, 0, 0) + bytes(36)
                     + bytes(4 if is_2016() else 0))   # 2016 entries 0x50 (client 0x541290; 2011 0x4c)
    stats.equip = tuple(equip)
    return Frame(0x1c7, stats.encode() + enchant_bonus() + enchant_bonus() + bytes(56)
                 + struct.pack('<I', len(parts)) + b''.join(parts))


def real_match_car(p):
    """The player's current car turned into the Real Match car: the server's car type and grade
    (emulator.ini realmatch_car), the player's own car id and colours, a full tank of its own (it had the
    player's fuel, and the client's fuel reports for it were saved onto the player's car: user, 2026-10-15;
    session.drive_info ignores them while real_match_car is set)."""
    car = p.car
    if not car or not context.realmatch_car:
        return None
    car_type, grade = context.realmatch_car
    u = context.data.upgrade.get((car_type, grade)) or {}
    capacity = float(u.get('capacity', car.capacity) or car.capacity)
    return dataclasses.replace(car, car_type=car_type, grade=grade, capacity=capacity, mitron=capacity,
                               efficiency=float(u.get('efficiency', car.efficiency) or car.efficiency))


def car_attr_of(car):
    """XiCarAttr, 2011 (12 bytes; as the client sends it in 0x1cc / 0x1d4 and in its moves): u16 0, u16
    car type, u32 colour, u32 second colour (the glass: the tint, or the default 0x82cccccc)."""
    return sized(struct.pack('<HHII', 0, car.car_type, car.shown_color(), car.tint or 0x82cccccc), car_attr_size())


def drive(session, car):
    """Make the client drive this car: 0x425 (visual update) with the player's own serial switches its current car
    model (client 0x516980 -> 0x708820: car id, type, colour; then the car is rebuilt) and tells the others.
    0x5a SelectCarAck is not used: outside the garage its handler (0x510ea0) always starts the car-change
    light column (0x6d1960 -> levelup.nif) and sound 0x4ea1, shown on entering and on leaving a Real Match room
    (user, 2026-10-16: the switch should be seamless)."""
    from .cars import visual_update
    send(session, visual_update(session, car))


# Tried and removed (2026-10-13, neither made a missing seat thumbnail appear): sending every member's
# 0x425 car record at a join, and repeating the Real Match refresh (0x5a + 0x425) with the player's own
# car in ordinary rooms. 0x5a also makes the client play its level-up-like effect the next time the
# character is loaded (user: on both clients after leaving a room), so it is used for Real Match only.

def enter_real_match(session, m):
    """Everyone in a Real Match room drives the one car the server chose (user, 2026-10-13): the client
    gets it as its current car, and the room shows it for this member."""
    p = session.state.get('player')
    car = real_match_car(p) if p else None
    if context.realmatch_effect:
        # the client's Real Match look is a content flag (0x1e). Sent to everyone at login it emptied the
        # car models in ordinary rooms (user, 2026-10-13), so it is switched on only while the player is
        # in a Real Match room, with a second 0x1e, and off again when it leaves.
        from .login import game_setting
        session.state['real_match_effect'] = True
        from .championship import speed_flags
        send(session, game_setting(Etc_RealMatchEffect=context.realmatch_effect, **speed_flags(session)))
    if car:
        session.state['real_match_car'] = True
        m.car_attr = car_attr_of(car)
        drive(session, car)


def exit_real_match(session):
    """Back to the player's own car when it leaves the Real Match room."""
    p = session.state.get('player')
    try:                                        # the connection may be gone already
        if session.state.pop('real_match_effect', None):
            from .login import game_setting
            from .championship import speed_flags
            send(session, game_setting(**speed_flags(session)))
        if session.state.pop('real_match_car', None) and p and p.car:
            drive(session, p.car)
    except Exception:
        pass


# ---- lobby ---------------------------------------------------------------------------------------------

def list_frame(obs):
    found = [r for r in rooms.values() if r.channel == obs['channel']]
    size = max(1, obs['size'])
    # "pages" in 0x1d0 is the number of the last page (0 while everything fits on one): the client lights
    # its next-page arrow while page < pages. Sent as a page count (1 for one room), the arrow was lit
    # with a single room (user, 2026-10-13); the 2008 recordings only had 0 with an empty list.
    pages = max(len(found) - 1, 0) // size
    page = min(obs['page'], pages)
    part = found[page * size:(page + 1) * size]
    return Frame(0x1d0, struct.pack('<IIIi', page, pages, len(part), now()) + b''.join(r.list_entry() for r in part))


def lists_changed(channel):
    for r in rooms.values():
        if r.channel == channel and r.observers:
            r.refresh_observers()
    for s in list(sessions.values()):
        obs = s.state.get('room_observer')
        if obs and obs['channel'] == channel:
            send(s, list_frame(obs))


@on(SVC, C2S, 0x1b8)
async def register_observer(session, frame):
    if not session.state.get('player') or len(frame.payload) < 16:
        return
    channel, room_filter, page, size = struct.unpack_from('<IIII', frame.payload)
    obs = session.state['room_observer'] = dict(channel=channel, filter=room_filter, page=page, size=size)
    send(session, section_frame(session, channel, room_filter, page))
    send(session, list_frame(obs))
    from .championship import on_section       # a GT Championship class lobby (sections 7-10): its state (0xd49)
    on_section(session, channel)


def section_frame(session, channel, room_filter=3, page=0):
    """0x1b9 RegisterObserverAck: the client takes its battle zone section from it (handler 0x52a040 stores the
    channel at +0x3d520 and redraws that section's lobby; the room rules shown come from it)."""
    session.state['pvp_channel'] = channel
    rm_open, rm_time = real_match_times()
    from .championship import section_tail     # @0x1a 0, @0x1e the GT Championship round, @0x22 its end time
    tail = section_tail()
    if is_2016() and rm_open and context.realmatch_car:
        # 2016 (handler 0x53fb00, branch 0x53fefe while @0x12 != 0): @0x1a is the Real Match car type
        # ([root +0x168] vcall 0x18 -> +0xa0), read by the Real Match car window for its car-name model
        # (0x57d960: VehicleList old file name); 0 left that box empty (user 2026-10-20). 2011 reads it as a flag.
        tail = struct.pack('<I', context.realmatch_car[0]) + tail[4:]
    return Frame(0x1b9, struct.pack('<iIIIII', 1, channel, room_filter, page, int(rm_open), rm_time) + tail)


@on(SVC, C2S, 0x1ba)
async def unregister_observer(session, frame):
    session.state.pop('room_observer', None)


# ---- rooms ---------------------------------------------------------------------------------------------

PRO_CHANNEL = 12
# the 2011 battle zone's Pro section (BattleZoneReform): the room's EXP tier is a room type bit (0x1cc / 0x1d4 type
# 0x20080 = 4X, 0x100080 = 16X as recorded 2026-10-16; not a map flag bit as first guessed); its limits are the
# client's GlobalContent.xlt *11New rows (client 0x5a6950; the client caps the car's top speed at the tier's
# MaxBattle*SpeedLimit by itself, 0x489165, when the room has map flag 0x4000) -> name, low, high, exp x, level min, max
PRO_TIERS = {0x20000: ('Pro 4X', 1, 5, 4, 11, 1000), 0x40000: ('Pro 6X', 1, 7, 6, 31, 1000),
             0x80000: ('Pro 8X', 1, 9, 8, 51, 1000), 0x100000: ('Pro 16X', 1, 9, 16, 71, 1000)}
# EU players (user, 2026-10-17): the tiers by V grade only (no levels: nation rule battle_levels), as set in the EU
# client's GlobalContent.xlt Value_EU_eng (*Grade11New); the sections from emulator.ini eu.section.<channel>
PRO_TIERS_EU = {0x20000: ('Pro 4X', 4, 5, 4, 0, 9999), 0x40000: ('Pro 6X', 6, 6, 6, 0, 9999),
                0x80000: ('Pro 8X', 7, 8, 8, 0, 9999), 0x100000: ('Pro 16X', 9, 9, 16, 0, 9999)}


def section_rule(channel, room_type=0, x=None):
    """emulator.ini's section line, or for a Pro room the rules of its EXP tier (a room type bit); x (a session or
    player) an EU player: the EU lines (eu.section.<channel>, PRO_TIERS_EU) where there are some."""
    from .. import nation
    eu = x is not None and nation.is_eu(x)
    if channel == PRO_CHANNEL:
        tier = next((r for bit, r in (PRO_TIERS_EU if eu else PRO_TIERS).items() if room_type & bit), None)
        if tier:
            return tier
    return (eu and context.sections_eu.get(channel)) or context.sections.get(channel)


# ---- complete bonus (the room window's "< Complete Bonus Reward >": "You can acquire Mito and EXP by completing each
# Lap.", GlobalText 11963 / 12084 / 12085) -----------------------------------------------------------------------
# The client draws it itself (0x59ec60, content flags ChannelNewbie / ChannelPro: [net+0x29c] & 0x30000000) from
# Init/Reward_ExpMito.xlt (US only; loaded by 0x7894a0, object 0x955118): rows of star kind Bronze (Newbie, section
# 11), Silver (Pro with the speed limit, map flag 0x4000) and Gold (Pro without), star points and the player-count
# range (Newbie / Pro columns); the stars = the row's place in its kind (0x788fc0) for the human racers (members below
# serial 0x10000, 0x5b0330), nothing alone. Per lap (0x788e70 / 0x789340): EXP = players x 1.025 x section x points,
# Mito = points x players x 1.8 x section; section = 3 (Newbie) or the Pro tier 4 / 6 / 8 / 16 (else 1).
# *Our choice* (the client shows the amounts, the server pays them): a finisher gets them x the track's LapCount on
# top of the race result's EXP / Mito (US players; the EU client's table has no such rows).
BONUS_KINDS = {'Bronze': 0, 'Sliver': 1, 'Silver': 1, 'Gold': 2}
_bonus_rows = None
_laps = None


def bonus_rows():
    """[(kind 0 bronze / 1 silver / 2 gold, points, newbie min, max, pro min, max)] of Reward_ExpMito.xlt."""
    global _bonus_rows
    if _bonus_rows is None:
        from ..data import read_xlt
        _bonus_rows = []
        try:
            for r in read_xlt(os.path.join(context.data.root, 'Init', 'Reward_ExpMito.xlt'))[3:]:
                if len(r) > 7 and r[1].strip() in BONUS_KINDS and r[3].strip().isdigit():
                    _bonus_rows.append((BONUS_KINDS[r[1].strip()], *(int(x) for x in r[3:8])))
        except (OSError, ValueError):
            pass
    return _bonus_rows


def lap_count(map_id):
    """PVPTrackInfo.xlt LapCount of a track (the first row of its Id)."""
    global _laps
    if _laps is None:
        from ..data import read_xlt
        _laps = {}
        try:
            rows = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
            c_id, c_laps = rows[2].index('Id'), rows[2].index('LapCount')
            for r in rows[3:]:
                if len(r) > c_laps and r[c_id].strip().isdigit() and r[c_laps].strip().isdigit():
                    _laps.setdefault(int(r[c_id]), int(r[c_laps]))
        except (OSError, ValueError):
            pass
    return _laps.get(map_id, 1)


def complete_bonus(channel, room_type, map_flag, players):
    """(EXP, Mito) per lap, as the room window shows them (0x59ec60), or (0, 0)."""
    if channel == 11:
        kind, section = 0, 3
    elif channel == PRO_CHANNEL:
        kind = 1 if map_flag & 0x4000 else 2
        section = next((m for bit, m in ((0x20000, 4), (0x40000, 6), (0x80000, 8), (0x100000, 16))
                        if room_type & bit), 1)
    else:
        return 0, 0
    if players <= 1:
        return 0, 0
    for k, points, nmin, nmax, pmin, pmax in bonus_rows():
        low, high = (nmin, nmax) if kind == 0 else (pmin, pmax)
        if k == kind and high and low <= players <= high:
            return int(players * 1.025 * section * points + 0.5), int(points * players * 1.8 * section + 0.5)
    return 0, 0


def car_allowed(session, channel, room_type=0):
    """The section's rules (emulator.ini [battlezone]: the grade of the car driven, V1-V9, and optional
    level limits, none by default; Pro rooms: their tier's). The 2008 server had no such check on its side. -> True, or False after telling the player."""
    rule = section_rule(channel, room_type, session)
    p = session.state.get('player')
    car = p.car if p else None
    if not rule or not car:
        return True
    name, low, high, _, min_level, max_level = rule
    level = p.char.level
    from .. import nation
    if nation.rule(session, 'battle_levels') and not min_level <= level <= max_level:   # EU: V grades only
        session.log.note(f'section {name} (PvP channel {channel}): level {level} is outside {min_level}-{max_level}')
        admin.message(session, f'{name} section: only for levels {min_level} to {max_level}. Your level is {level}.')
        return False
    if low <= car.shown_grade() <= high:
        return True
    session.log.note(f'section {name} (PvP channel {channel}): car grade V{car.shown_grade()} is outside V{low}-V{high}')
    admin.message(session, f'{name} section: only V{low} to V{high} vehicles can race here. Your vehicle is V{car.shown_grade()}.')
    return False


@on(SVC, C2S, 0x1cc)
async def room_create(session, frame):
    p = frame.payload
    if not session.state.get('player') or len(p) < CREATE[year()][4]:
        return
    at, extra_at, name_at, password_at, car_at = CREATE[year()]
    room_type, map_id, capacity, map_flag = struct.unpack_from('<IHHH', p, at)
    extra = struct.unpack_from('<II', p, extra_at)
    if not car_allowed(session, session.state.get('pvp_channel', 0), room_type):
        return
    leave(session)
    name, password = read_wstr(p, name_at, 60), read_wstr(p, password_at, 60)
    if is_real_match(room_type) and not real_match_times()[0]:
        return admin.message(session, REAL_MATCH_CLOSED)
    room = Room(session.state.get('pvp_channel', 0), room_type, map_id, map_flag, capacity, name, password)
    m = Member(session, p[0:user_info_size()], p[car_at:car_at + car_attr_size()])
    rooms[room.id] = room
    room.members.append(m)
    room.seats[0] = room.master = m.serial
    m.ready = True
    session.state['room'] = room.id
    session.log.note(f'room {room.id} created: {name!r}, type {room_type:#x}, map {map_id}, flags {map_flag:#x} '
                     f'(after: {extra[0]:#x} {extra[1]:#x}), '
                     f'capacity {room.capacity}, PvP channel {room.channel}')
    info = [real_match_info()] if is_real_match(room_type) else []
    if info:
        enter_real_match(session, m)
    send(session, room.master_frame(), *info, room.state_frame(),
         Frame(0x1cd, m.user_info + struct.pack('<iIIIHH', 1, room.id, room.life_id, room_type, map_id, map_flag)))
    lists_changed(room.channel)


@on(SVC, C2S, 0x26d)
async def room_modify(session, frame):
    p = frame.payload
    room = room_of(session)
    if not room or len(p) < 0xc + 4 * SEATS:
        return
    m = room.member(session)
    if m.serial != room.master:
        return error(session, '20151')
    _, map_id, map_flag, capacity = struct.unpack_from('<IHIH', p)
    capacity = max(1, min(capacity, SEATS))
    if capacity < len(room.members):
        return error(session, '20150')
    asked = struct.unpack_from(f'<{SEATS}I', p, 0xc)
    for i, v in enumerate(asked):
        cur = room.seats[i] if i < len(room.seats) else LOCKED
        if v == AI_SEAT and cur == OPEN and i < capacity and room.state == WAIT \
                and context.battle_ai:          # emulator.ini [battlezone] ai = 0: no AI seats at all
            add_ai(room, i, m)
        elif v == AI_SEAT and 0xffff < cur != LOCKED and room.state == WAIT:
            remove_ai(room, cur)                # the AI button on an AI's seat takes it out
    # other seats: the client sends its own view, where the AIs' seats may differ (it moved an AI when
    # another seat was clicked: user, 2026-10-13); AIs stay where the server put them (below)
    seats = []
    for i, cur in enumerate(room.seats):            # BS_Room::ApplySlot: taken seats stay, the rest as asked
        if cur not in (OPEN, LOCKED):
            seats.append(cur)
        else:
            seats.append(LOCKED if i >= capacity or asked[i] == LOCKED else OPEN)
    room.map_id, room.map_flag, room.capacity, room.seats = map_id, map_flag, capacity, seats
    session.log.note(f'room {room.id} modified: map {map_id}, flags {map_flag:#x}, capacity {capacity}')
    room.cast(room.modify_frame())
    lists_changed(room.channel)


LAP_FILTER = 4                      # 0x1bb filter of the Lap Time button (laptime.py)
AI_SEAT = 0xffff                    # 0x26d from the master with the AI button on: an AI racer for this seat


def add_ai(room, seat, master):
    """emulator.ini [battlezone] ai = 1: the master clicked a seat with "AI Vehicles Activated" -> an AI member joins:
    0x1d4 as for a player under serial key << 16; its driver is named at the go (Room.assign_ais)."""
    p = master.player
    picked = pick_ai(p.char.level if p else 1, {m.ai_idx for m in room.members if not m.session})
    if not picked:
        return
    room.ai_keys += 1
    ai = AiMember(room.ai_keys, *picked, master.serial)
    room.seats[seat] = ai.serial
    room.members.append(ai)
    master.session.log.note(f'room {room.id}: AI {ai.name!r} (AICarParam {ai.ai_idx}, level {ai.level}, '
                            f'car {ai.car_type}, serial {ai.serial:#x}) in seat {seat}')
    room.cast(ai.joined_frame(room))
    lists_changed(room.channel)


def remove_ai(room, serial):
    ai = room.by_serial(serial)
    if not ai or ai.session:
        return
    room.members.remove(ai)
    room.seats = [OPEN if v == serial else v for v in room.seats]
    room.cast(Frame(0x1d5, struct.pack('<I', serial) + room.seat_bytes() + struct.pack('<I', room.type)))
    lists_changed(room.channel)


@on(SVC, C2S, 0x21f)
async def ai_move(session, frame):
    """0x21f (2011, 0x6c bytes both ways; sent by 0x53a13d for the AI cars the client simulates; handler
    0x50c930 takes it when @0x68 is its area and the serial @2 is not its own): passed on to the others in
    the room. 2016: 0x21f is the peer-to-peer move over UDP (0x847760, to peers with a port), so it is not the AI
    cars' moves; their driver is named in 0x271 (AiMember.entry)."""
    room = room_of(session)
    if room:
        room.cast(Frame(0x21f, frame.payload), skip=room.member(session))


@on(SVC, C2S, 0x270)
async def change_seat(session, frame):
    """0x270 (2011 only; u32 room, u32 serial, u32 seat): a member clicked a free seat of its room. The
    member moves there and the room gets the seats with 0x26d (the message the client already takes
    seat changes from) *(our answer: the real server's is not known; the 2008 server had only 0x26f
    RoomChangeTeam)*. Locked and taken seats are refused silently."""
    room = room_of(session)
    if not room or len(frame.payload) < 12 or room.state != WAIT:
        return
    m = room.member(session)
    seat, = struct.unpack_from('<I', frame.payload, 8)
    if seat >= room.capacity or room.seats[seat] != OPEN:
        return
    room.seats = [OPEN if v == m.serial else v for v in room.seats]
    room.seats[seat] = m.serial
    session.log.note(f'room {room.id}: {m.name!r} moves to seat {seat}')
    room.cast(room.modify_frame())


@on(SVC, C2S, 0x26f)
async def change_team(session, frame):
    """0x26f RoomChangeTeam (u32 room, u32 serial, u32 team 0 / 1): the team button. A team is the seat's parity
    (2008 BS_Room::ChangeTeam / TeamCount: seats of one team are every second one); the member moves to the
    given seat if it is free and on the other team, else to the first free seat of that team, and the room gets the
    seats (0x26d, as change_seat). No handler until 2026-10-14 (user: the team select button did nothing)."""
    room = room_of(session)
    if not room or len(frame.payload) < 12 or room.state != WAIT:
        return
    m = room.member(session)
    want, = struct.unpack_from('<I', frame.payload, 8)
    cur = room.seats.index(m.serial) if m and m.serial in room.seats else None
    if cur is None or (cur & 1) == (want & 1):
        return
    free = [i for i, v in enumerate(room.seats[:room.capacity]) if v == OPEN and (i & 1) == (want & 1)]
    seat = want if want in free else (free[0] if free else None)
    if seat is None:
        session.log.note(f'room {room.id}: {m.name!r} team {want & 1}: no free seat')
        return
    room.seats[cur], room.seats[seat] = OPEN, m.serial
    session.log.note(f'room {room.id}: {m.name!r} to team {seat & 1} (seat {seat})')
    room.cast(room.modify_frame())


def team_room(room_type):
    """Team points in the result (2008 BS_Room::PvpRaceResult): crew battles (type 0x28) and team rooms (bit 0)."""
    return room_type == 0x28 or bool(room_type & 1)


# 2008 GetTeamPoint 0x5a7330: T[rank] - T[racers + 1] (0 past 32 racers or a rank past the racers), T from .data 0x700c0c
TEAM_POINTS = (0, 40, 37, 34, 32, 30, 28, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7,
               6, 5, 4, 3, 2, 1, 0)


def team_point(rank, racers):
    if racers > 32 or not 1 <= rank <= racers:
        return 0
    return TEAM_POINTS[rank] - TEAM_POINTS[racers + 1]


def join(session, room, user_info, car_attr, player_info, password=None):
    if not session.state.get('player'):
        return
    if room is None:
        return error(session, '20146')
    if room.member(session):
        return send(session, room.master_frame(), room.state_frame())
    if not room.lap and not car_allowed(session, room.channel, room.type):   # lap arenas: by grade already
        return
    check = getattr(room, 'join_check', None)  # GT Championship rooms: their group's contenders only
    if check and not check(session):
        return
    if room.state != WAIT:
        return error(session, '20158')
    if room.password and password is not None and password != room.password:
        return error(session, '20162')
    if room.password and password is None:
        return error(session, '20158')
    seat = next((i for i, v in enumerate(room.seats) if v == OPEN), None)
    if seat is None:
        return error(session, '20039')
    leave(session)
    m = Member(session, user_info, car_attr, player_info)
    if is_real_match(room.type):
        enter_real_match(session, m)
    room.seats[seat] = m.serial
    joined = Frame(0x1d4, struct.pack('<IH', m.serial, m.age) + m.user_info + m.car_attr
                   + struct.pack('<II', room.id, room.life_id) + m.info() + room.seat_bytes()
                   + struct.pack('<I', room.type))
    room.cast(joined)
    room.members.append(m)
    session.state['room'] = room.id
    session.log.note(f'{m.name!r} (serial {m.serial}) joins room {room.id}, seat {seat}')
    info = [real_match_info()] if is_real_match(room.type) else []
    if session.state.get('pvp_channel') != room.channel:
        # joined from another section's lobby (an invitation): the client kept its own section's rules (speed
        # limit, EXP tier) for the room (user, 2026-10-16), so it is moved to the room's section first
        session.log.note(f'room {room.id}: moved from PvP channel {session.state.get("pvp_channel")} to {room.channel}')
        obs = session.state.get('room_observer')
        if obs:
            obs['channel'] = room.channel
        info.insert(0, section_frame(session, room.channel))
    send(session, room.master_frame(), *info, room.state_frame())
    if mission_room(room):
        from .missionarena import on_join          # the arena room's mode / difficulty for the joiner's window
        on_join(session, room)
    room.watch_start()
    lists_changed(room.channel)


def join_request(session, p, msg, password_at=None):
    ui, ca, room_at, pi = JOIN[year()][msg]
    if len(p) < max(pi + PLAYER_INFO, (password_at or 0) + 60):
        return
    room_id, = struct.unpack_from('<I', p, room_at)
    join(session, rooms.get(room_id), p[ui:ui + user_info_size()], p[ca:ca + car_attr_size()], p[pi:pi + PLAYER_INFO],
         read_wstr(p, password_at, 60) if password_at else None)


@on(SVC, C2S, 0x1d4)
async def room_join(session, frame):
    join_request(session, frame.payload, 0x1d4)


@on(SVC, C2S, 0x1bc)
async def room_secure_join(session, frame):
    join_request(session, frame.payload, 0x1bc, SECURE_PASSWORD[year()])


def direct_join(session, p, room):
    ui, pi, ca = DIRECT[year()][:3]
    join(session, room, p[ui:ui + user_info_size()], p[ca:ca + car_attr_size()], p[pi:pi + PLAYER_INFO], None)


@on(SVC, C2S, 0x1bb)
async def room_direct_join(session, frame):
    p = frame.payload
    filter_at = DIRECT[year()][3]
    if len(p) < filter_at + 4:
        return
    channel, = struct.unpack_from('<I', p)
    if struct.unpack_from('<I', p, filter_at)[0] == LAP_FILTER:     # the Lap Time button
        from .laptime import enter
        return enter(session, p)
    from .championship import CLASSES
    if session.state.get('pvp_channel') in CLASSES:            # a GT Championship lobby's stage button
        from .championship import enter
        return enter(session, p, session.state['pvp_channel'])
    room = next((r for r in rooms.values() if r.channel == channel and r.state == WAIT and not r.password
                 and OPEN in r.seats and not getattr(r, 'lap', None)), None)
    if room is None:
        return error(session, '20159')
    direct_join(session, p, room)


@on(SVC, C2S, 0x1bd)
async def room_id_direct_join(session, frame):
    p = frame.payload
    room_at = DIRECT[year()][4]
    if len(p) < room_at + 4:
        return
    room = rooms.get(struct.unpack_from('<I', p, room_at)[0])
    if room is not None and getattr(room, 'lap', None) is not None:
        # a friend's Lap Time arena (social.place_of kind 6): the player's own grade's arena, as the Lap Time button
        from .laptime import enter
        return enter(session, p)
    direct_join(session, p, room)


@on(SVC, C2S, 0x1d7)
async def channel_room_join(session, frame):
    join_request(session, frame.payload, 0x1d7)


def leave(session, banished=False):
    """Take the session's member out of its room (RoomLeave, RoomBanish, a dropped connection)."""
    room = rooms.get(session.state.pop('room', None))
    m = room.member(session) if room else None
    if not m:
        return
    room.members.remove(m)
    exit_real_match(session)
    room.seats = [OPEN if v == m.serial else v for v in room.seats]
    session.log.note(f'{m.name!r} (serial {m.serial}) {"is banished from" if banished else "leaves"} room {room.id}')
    gone = Frame(0x1d6 if banished else 0x1d5, struct.pack('<I', m.serial) + room.seat_bytes()
                 + struct.pack('<I', room.type))
    if room.state == WAIT and not banished:
        # the host's Start stayed greyed out when a member left without having been ready (user, 2026-10-16:
        # ready first, then leaving, was fine; so was a kick): the client's 0x1d5 does not drop the member's
        # not-ready state, so the room hears it ready just before it leaves. The host too: after a race the
        # clients hold everyone not ready, and a guest that became host after the host left had Start greyed
        # (user, 2026-10-16); the client enables Start from 0x5a2a60 (+0x14a6: every member ready)
        m.ready = True
        room.cast(ready_frame(m))
    room.cast(gone)
    if banished:
        send(session, gone)
    if not room.humans:
        if room.lap and room.lap.task:
            room.lap.task.cancel()
        room.cancel_timer()
        room.watch_start()
        room.members = []
        send_off_spectators(room, 3)        # they were not told before (2026-10-16)
        del rooms[room.id]
    else:
        if room.master == m.serial and room.humans:
            new = room.humans[0]
            room.master = new.serial
            new.ready = True
            room.cast(room.master_frame(), ready_frame(new))
        if room.state == WAIT:
            # the full room state again: after a player left by itself the host's Start stayed greyed out (the
            # client still counted it as not ready; user, 2026-10-16: with or without spectators; after a kick,
            # which the host's own client does, it was fine)
            room.cast(room.state_frame())
        if room.state != WAIT:                      # it no longer holds up the loading or the result
            room.waiting.discard(m.serial)
            if m.serial in room.racers:
                room.racers.remove(m.serial)
            asyncio.ensure_future(progress(room))
        room.watch_start()
    if getattr(room, 'cbattle', None) is not None:     # a channel battle room (channels.py): its channel's list
        from .channels import room_changed
        room_changed(room.cbattle)
    lists_changed(room.channel)


@on(SVC, C2S, 0x1d5)
async def room_leave(session, frame):
    leave(session)


@on(SVC, C2S, 0x1d6)
async def room_banish(session, frame):
    room = room_of(session)
    if not room or len(frame.payload) < 4:
        return
    me = room.member(session)
    target = room.by_serial(struct.unpack_from('<I', frame.payload)[0])
    if me.serial != room.master:
        return error(session, '20151')
    if target and target is not me and room.state == WAIT:
        leave(target.session, banished=True)


@on_open(SVC)
async def leave_on_close(session):
    try:
        await asyncio.Event().wait()
    finally:
        leave(session)
        unwatch(session)


def ready_frame(m):
    return Frame(0x1e5, struct.pack('<I?', m.serial, m.ready))


@on(SVC, C2S, 0x1e5)
async def ready_state(session, frame):
    room = room_of(session)
    if not room or len(frame.payload) < 5 or room.state != WAIT:
        return
    m = room.member(session)
    m.ready = bool(frame.payload[4]) or m.serial == room.master
    room.cast(ready_frame(m))
    room.refresh_observers()
    room.watch_start()


# ---- race ----------------------------------------------------------------------------------------------

@on(SVC, C2S, 0x1e6)
async def start_request(session, frame):
    room = room_of(session)
    if len(frame.payload) < 12:
        return
    if not room:
        return practice(session, frame.payload)
    m = room.member(session)
    if not room.members:
        return error(session, '20180')
    if m.serial != room.master:
        return error(session, '20181')
    if getattr(room, 'no_start', False):        # channel battle rooms: the server starts their races (channels.py)
        return
    if room.state != WAIT:
        return error(session, '20186')
    check = getattr(room, 'start_check', None)  # GT Championship preliminaries: not in their last 3 minutes
    if check and not check(session):
        return
    if any(not o.ready for o in room.members if o is not m):
        return error(session, '20182')
    if is_real_match(room.type) and not real_match_times()[0]:
        return admin.message(session, REAL_MATCH_CLOSED)
    map_id, map_flag, start_time = struct.unpack_from('<iii', frame.payload)
    if map_id >= 0 and not room.lap and getattr(room, 'fixed_map', None) is None:   # championship: the stage's track
        # the track is the start request's (2008 Cmd_PvpStartReq passes it to BS_Room::StartLoad): the 2011
        # client keeps the room's map at 0 and sends the track it chose (a pick, Recommended or Random) here;
        # the room's map was raced instead, always track 0 (user, 2026-10-16)
        room.map_id = map_id
    if any(not o.session for o in room.members) and room.map_id not in ai_tracks():
        # the client says "The map does not support AI Battle" but sends the start anyway; started, it
        # raced with 7 strange cars (user, 2026-10-13)
        return admin.message(session, 'This track does not support AI racers: choose a track with the AI icon.')
    if mission_room(room):
        # a Mission Battle runs as a practice run (0x1e7 type 100): the client's race object then marks it practice
        # (0x7727c7: +0x126 = 1), which its Rechallenge (0x7824f0 -> race vfunc 0xcc 0x77bd20: a local restart only for
        # practice) needs, and it has no gates (user: gates showed and Rechallenge did nothing in a normal race). The
        # mission ends and pays through the client's 0x3eb / 0x3e2 (instant.py), not the race result. The client sends
        # the start twice at once: the second is ignored. 2016 arena rooms: the master's client sends this start only
        # after the server's 0x3b7 (missionarena.py), with the mission's track; 2016 ends both kinds with 0x3eb / 0x3b8.
        flag = room.map_flag
        if not room.type & MISSION_ROOM:
            from .missionarena import start_flag
            flag = start_flag(session, room)
            if flag is None:
                return
        now_ = asyncio.get_running_loop().time()
        if now_ - getattr(room, 'mission_start', -10.0) < 2.0:
            return
        room.mission_start = now_
        session.log.note(f'room {room.id}: Mission Battle on map {room.map_id} in area {room.area} (practice run)')
        return room.cast(Frame(0x1e7, struct.pack('<iiiifii', PRACTICE, room.map_id, flag, room.area, 0.0,
                                                start_time, -1)))
    if len(room.members) == 1 and context.practice_alone and not getattr(room, 'real_alone', False):
        # BS_Room::StartLoad's practice path (Contents.ini BattleZone.PracticeMode): one member -> 0x1e7 type
        # 100, the room keeps waiting: no go signal, no gate rewards, no end, no result (user, 2026-10-13)
        session.log.note(f'room {room.id}: one member, practice run on map {room.map_id} in area {room.area}')
        if room.observers:      # 2 players + a spectator, one left: nothing to watch (user, 2026-10-16)
            session.log.note(f'room {room.id}: {len(room.observers)} spectator(s) sent off (practice run)')
            # result 3: with 2 the message showed but the client stayed in the room (user, 2026-10-16)
            send_off_spectators(room, 3, 'The host started a practice run alone: there is no race to spectate.')
            lists_changed(room.channel)
        return room.cast(Frame(0x1e7, struct.pack('<iiiifii', PRACTICE, room.map_id, map_flag, room.area, 0.0,
                                                start_time, -1)))
    room.state = LOADING
    room.watch_start()
    room.waiting = {o.serial for o in room.humans}
    room.racers = [o.serial for o in room.humans]
    room.rank, room.first_end = 0, None
    room.gates = {}
    for o in room.members:
        o.loaded, o.end = False, None
    session.log.note(f'room {room.id}: loading map {room.map_id} in area {room.area}, {len(room.members)} racers')
    room.reset_ais()                    # AIs of an earlier race: unassigned again for the 0x271 below
    room.cast(Frame(0x1e7, struct.pack('<iiiifii', 0, room.map_id, map_flag, room.area, 0.0, start_time, -1)))
    # the AIs' drivers right after the load starts. Before the 0x1e7 (the cars made in the room, no track yet) they
    # never appeared; at the go or after the 0x1e7 with FrontAi 1 they appeared when the countdown ended (their grid
    # slot was seat - 24); with FrontAi 0 the slot is the seat (user, 2026-10-20). The 2011 client: at the go (progress),
    # its 0x271 handler 0x77b1c0 puts the cars on the grid itself (0x7749d0 at 0x77b42b / 0x77b45d) and loads the track
    # only over the next 0x1e8s: right after the 0x1e7 the AIs appeared only when the countdown ended (user, 2026-10-20)
    if year() == 2016:
        room.assign_ais()
    room.cancel_timer()
    room.timer = asyncio.ensure_future(after(room, LOAD_TIMEOUT, LOADING))
    lists_changed(room.channel)


def practice(session, p):
    """A start request without a room: the 2011 client sends it from the battle zone lobby (recorded
    2026-10-13: map 74) and starts loading the track whatever the answer; the 2008 server knew no such
    request (error 20180). Answered as a practice run: 0x1e7 type 100 (what BS_Room::StartLoad sends
    for practice: no go signal, no gates, no result) in an area of the player's own.
    Apprentice training is different: native 0x5a0690 initializes its own race with time=-1.
    A practice reply overwrites that sentinel, bypassing 0x77dcb0's lesson initialization.
    Keep the local guided lesson and subsequent race under client control.
    *(guess: what the real 2011 server answered for ordinary practice is not known)*"""
    if not session.state.get('player'):
        return
    map_id, map_flag, start_time = struct.unpack_from('<iii', p)
    from .apprentice import enabled, training_car
    if enabled() and training_car(session.state['player'].car) and map_id == 11 and map_flag == 0:
        session.log.note('apprentice local race: preserving client lesson setup (no practice reply)')
        return
    area = PRACTICE_AREA_BASE + serial_of(session)
    session.log.note(f'practice run without a room: map {map_id}, area {area}')
    send(session, Frame(0x1e7, struct.pack('<iiiifii', PRACTICE, map_id, map_flag, area, 0.0, start_time, -1)))


# ---- invitations (the 2008 PacketParser::Cmd_InviteeList / Cmd_RoomInvite) -------------------------------
# 0x1c2 InviteeList (i32 PvP channel; the room's invite window asks about once a second) -> 0x1c3 InviteeListAck:
# u32 n @2, u32 page @6 (0 = a new list: client 0x52c9d0 clears it first), n x XiStrSimpleCharInfo @0xa (44 bytes:
# u32 serial, wchar[16] name, u32 level, u32 car level; the client lists name and +0x28) - the players in any
# section's lobby who are not in a room and pass the room's rules (invitees(); 2008: the PvP channel's user list).
# 0x1d1 RoomInvite (2011 128 bytes: u32 serial @2, room @6, 4 bytes @0xa, room life id @0xe, i64 cid @0x12,
# wchar[21] name @0x1a, wchar[30] room name @0x44; 0x1d2 RoomPrivateInvite + wchar[30] password @0x80): from the
# host with the invitee's serial; to the invitee with the inviter's serial, cid and name (client 0x52c130: text 10026
# with the name, Accept joins room @6 / life id @0xe). Not there any more: 20155. (user, 2026-10-15: the invite
# window stayed empty)
INVITEE_MAX = 30


def invitees(channel, me):
    """Players in a battle zone lobby (any section, the inviter's own first) and not in a room, who may join the
    inviter's room by its section's level / car grade rules. The 2008 server listed the request's PvP channel only;
    the 2011 sections are separate lobbies, so a player in another section never showed (user, 2026-10-16: Newbie
    in the Newbie section, the room in Real Match)."""
    room = rooms.get(me.state.get('room'))
    out = []
    for s in list(sessions.values()):
        obs, p = s.state.get('room_observer'), s.state.get('player')
        if s is me or not p or not obs or s.state.get('room') is not None:
            continue
        rule = section_rule(room.channel, room.type, s) if room else None      # the invitee's nation's rules
        grade = p.car.shown_grade() if p.car else 0
        from .. import nation
        level_ok = not nation.rule(s, 'battle_levels') or rule and rule[4] <= p.char.level <= rule[5]
        if rule and not (level_ok and rule[1] <= grade <= rule[2]):
            continue
        out.append((obs['channel'] != channel, serial_of(s), p.char.name,
                    p.char.level, grade))
    return [r[1:] for r in sorted(out, key=lambda r: r[0])][:INVITEE_MAX]


@on(SVC, C2S, 0x1c2)
async def invitee_list(session, frame):
    if not session.state.get('player') or len(frame.payload) < 4:
        return
    channel, = struct.unpack_from('<i', frame.payload)
    rows = invitees(channel, session)
    body = b''.join(struct.pack('<I', serial) + name.encode('utf-16-le')[:30].ljust(32, b'\0')
                    + struct.pack('<II', level, level) for serial, name, level, _ in rows)
    send(session, Frame(0x1c3, struct.pack('<II', len(rows), 0) + body))


async def room_invite(session, frame):
    p = session.state.get('player')
    room = rooms.get(session.state.get('room'))
    data = bytes(frame.payload)
    if not p or not room or len(data) < 0x7e:
        return
    target_serial, = struct.unpack_from('<I', data)
    target = next((s for s in sessions.values() if s.state.get('serial') == target_serial and s.state.get('player')), None)
    if target is None:
        return error(session, '20155')
    me = serial_of(session)
    name = p.char.name.encode('utf-16-le')[:40].ljust(42, b'\0')
    out = (struct.pack('<II', me, room.id) + data[8:12] + struct.pack('<Iq', room.life_id, p.char.cid) + name
           + data[0x42:])
    session.log.note(f'room {room.id}: invites {target.state["player"].char.name!r}')
    send(target, Frame(frame.type, out))


on(SVC, C2S, 0x1d1)(room_invite)
on(SVC, C2S, 0x1d2)(room_invite)


# ---- spectators (the 2008 BS_OBSRoom) -----------------------------------------------------------------
# 0x1de JoinOBS (u32 room), 0x1d9 SecureJoinOBS (u32 room, wchar[30] password) -> 0x26e + 0x1bf to the
# spectator, 0x1cb UpdateRoomInfo (u16 spectators) to the room; errors 20146 no such room, 20162 password.
# 0x1e0 LeaveOBS. 0x1db SwitchToOBS (a member becomes a spectator; 20187 if it is alone), 0x1dc
# SwitchToPlayer (UserInfo; a spectator takes a free seat). Spectators get 0x1bf again whenever the room
# changes (members, ready, loading / racing with the race's area) and the result 0x1ec; not the racers'
# messages (first version sent them all: the spectator's client then raced). *(How the 2011 client
# gets into the race's area as a viewer from 0x1bf is not read yet; to be tested in game.)*

def watching(session):
    return rooms.get(session.state.get('watching'))


def spectator_count(room):
    """0x1cb to the players and the spectators (their own view showed 0 without it: user, 2026-10-16)."""
    f = Frame(0x1cb, struct.pack('<H', len(room.observers)))
    for s in [m.session for m in room.members if m.session] + list(room.observers):
        try:
            send(s, f)
        except Exception:
            pass


def watch(session, room, password=None):
    if not session.state.get('player'):
        return
    if room is None:
        return error(session, '20146')
    if not room.type & SPECTATORS_ALLOWED:
        # the room option "Spectating" is bit 0x80 of the room type (rooms made with it off: type 0x100 /
        # 0x0); Cmd_JoinOBS refuses those with 20158. The 2011 client always draws its Spectate button as
        # usable (its click handlers 0x5a2130 / 0x598d0d send 0x1de whatever the type): answered with a
        # message (the user tried a silent drop and went back to messages, 2026-10-13).
        session.log.note(f'spectating room {room.id} refused: spectating is off (type {room.type:#x})')
        return admin.message(session, 'Spectating is turned off for this room.')
    if room.password and password != room.password:
        return error(session, '20162')
    if len(room.members) < 2 and context.practice_alone and not room.member(session):
        # one player = a practice room: nothing to watch (user, 2026-10-13)
        session.log.note(f'spectating room {room.id} refused: a practice room (one player)')
        return admin.message(session, 'This is a practice room (one player): there is no race to spectate.')
    leave(session)
    unwatch(session)
    room.observers.append(session)
    session.state['watching'] = room.id
    session.log.note(f'spectates room {room.id} ({len(room.observers)} spectators)')
    send(session, room.master_frame(), room.obs_state_frame())
    spectator_count(room)
    lists_changed(room.channel)


def send_off_spectators(room, result, note=None):
    """Close every spectator's view of this room (0x1bf with result 2 / 3)."""
    frame = room.obs_state_frame(result)
    for s in list(room.observers):
        s.state.pop('watching', None)
        try:
            send(s, frame)
            if note:
                admin.message(s, note)
        except Exception:
            pass
    room.observers = []
    spectator_count(room)


def unwatch(session):
    room = rooms.get(session.state.pop('watching', None))
    if room and session in room.observers:
        room.observers.remove(session)
        spectator_count(room)
        lists_changed(room.channel)


@on(SVC, C2S, 0x1de)
async def join_obs(session, frame):
    if len(frame.payload) >= 4:
        watch(session, rooms.get(struct.unpack_from('<I', frame.payload)[0]))


@on(SVC, C2S, 0x1d9)
async def secure_join_obs(session, frame):
    if len(frame.payload) >= 4:
        watch(session, rooms.get(struct.unpack_from('<I', frame.payload)[0]), read_wstr(frame.payload, 4, 60))


@on(SVC, C2S, 0x1e0)
async def leave_obs(session, frame):
    unwatch(session)
    from .channels import stop_spectating      # a channel battle spectator, also between rounds
    stop_spectating(session)
    session.state.pop('ghost', None)           # a replay (and its Ghost Battle) is left with 0x1e0 too


@on(SVC, C2S, 0x1db)
async def switch_to_obs(session, frame):
    room = room_of(session)
    if not room:
        return error(session, '20189')
    if len(room.members) < 2:
        return error(session, '20187')
    if room.state != WAIT:
        return error(session, '20188')
    leave(session)
    watch(session, room, room.password)


@on(SVC, C2S, 0x1dc)
async def switch_to_player(session, frame):
    room = watching(session)
    if not room:
        return error(session, '20189')
    unwatch(session)
    join(session, room, frame.payload[:user_info_size()], b'', None, room.password)


@on(SVC, C2S, 0x1e8)
async def loading_status(session, frame):
    room = room_of(session)
    if room and len(frame.payload) >= 8:
        m = room.member(session)
        room.cast(Frame(0x1e8, struct.pack('<I', m.serial) + frame.payload[4:8]), skip=m)


@on(SVC, C2S, 0x1e9)
async def load_complete(session, frame):
    room = room_of(session)
    if not room or room.state != LOADING or len(frame.payload) < 4:
        return
    m = room.member(session)
    m.loaded = True
    room.start_time, = struct.unpack_from('<i', frame.payload)
    room.waiting.discard(m.serial)
    await progress(room)


async def after(room, seconds, state):
    """The room's timer: a loading or a race end that takes too long goes on without the stragglers."""
    await asyncio.sleep(seconds)
    room.timer = None
    if rooms.get(room.id) is room and room.state == state:
        room.waiting.clear()
        await progress(room)


async def progress(room):
    """BS_Room::RemoveFromWaitSet: nobody left to wait for -> go (after loading) or the result (racing)."""
    if rooms.get(room.id) is not room or room.waiting:
        return
    if room.state == LOADING:
        room.cancel_timer()
        room.state = RACING
        room.waiting = set(room.racers) | {a.serial for a in room.ais}    # the AIs' ends come from their driver
        room.refresh_observers()
        if year() != 2016:
            room.assign_ais()           # 2011: the track is loaded now (start_request)
        room.cast(Frame(0x1ea, struct.pack('<ii', getattr(room, 'start_time', 0), COUNTDOWN_MS) + bytes(32)))
    elif room.state == RACING:
        room.cancel_timer()
        await result(room)


GATE_REWARDS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'server_data', 'gate_rewards.txt')
# team rooms with more than 4 racers (2008 BS_Room::Gate: room type & 1 or & 8 -> s_fTeamReward; up to 4 racers the
# small tables, as any race): Emulator/server_data/team_gate_rewards.txt (user, 2026-10-14)
TEAM_GATE_REWARDS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'server_data', 'team_gate_rewards.txt')
SMALL_RACE = 4
CLEAN_GATE = 100.0                  # the gate request's last float when the racer had no collision
REWARDS, LAST_RESORT = 8, 6
# reward numbers (user, 2026-10-13, with gmgate): 0 nothing, 1 Boost 50%, 2 Boost 100%, 3 Skid Rush,
# 4 Repairs Complete, 5 Untouchable, 6 Hyper Boost, 7 Team Boost 50%
_gate_tables = {}
forced_reward = None               # gmgate: every gate gives this reward until gmgate off


def gate_rewards(path=GATE_REWARDS_FILE):
    """A gate reward file -> {(racers, position, clean): [chance of reward 0..7]} (read once)."""
    table = _gate_tables.get(path)
    if table is None:
        table = _gate_tables[path] = {}
        try:
            for line in open(path, encoding='utf-8'):
                f = line.split('#')[0].split()
                if len(f) >= 3 + REWARDS:
                    table[(int(f[0]), int(f[1]), int(f[2]))] = [float(v) for v in f[3:3 + REWARDS]]
        except (OSError, ValueError) as e:
            print(f'gate rewards: {path}: {e}', flush=True)
    return table


def team_gates(room_type, racers):
    """The team table applies: a team room (type & 1 or & 8, BS_Room::Gate) with more than 4 racers."""
    return bool(room_type & 9) and racers > SMALL_RACE


def gate_reward(racers, position, clean, team=False):
    """BS_Room::Gate 0x5a8ca0: a random 0-100 against the row's chances added up; the first reward
    whose sum reaches it. A missing row: the nearest lower position, then racer count."""
    table = gate_rewards(TEAM_GATE_REWARDS_FILE if team else GATE_REWARDS_FILE)
    row = None
    for n in range(min(max(racers, 1), 16), 0, -1):
        for pos in range(min(position, n), 0, -1):
            row = table.get((n, pos, int(clean))) or table.get((n, pos, 0))
            if row:
                break
        if row:
            break
    if not row or not any(row):
        return 0
    roll, total = random.random() * 100.0, 0.0
    for k, chance in enumerate(row):
        total += chance
        if chance and total >= roll:
            return k
    return LAST_RESORT


@on(SVC, C2S, 0x1ed)
async def gate(session, frame):
    room = room_of(session)
    if not room or room.state != RACING or len(frame.payload) < 20:
        return
    m = room.member(session)
    who, index, _, _, col_point = struct.unpack_from('<Iiiff', frame.payload)
    passed = room.gates.setdefault(index, [])
    ai = room.ai_by_car(who) if m and who != m.serial else None
    if ai:          # an AI its client drives (car key): it takes a place at the gate, no reward
        if ai.serial not in passed:
            passed.append(ai.serial)
            room.cast(Frame(0x1ee, struct.pack('<Ii', who, 0)))
        return
    if m.serial in passed or m.serial not in room.racers:
        return
    passed.append(m.serial)
    field = len(room.racers) + len(room.ais)         # the AIs count for the places (user, 2026-10-20: "8 of 1")
    reward = gate_reward(field, len(passed), col_point == CLEAN_GATE, team_gates(room.type, field))
    if forced_reward is not None:               # GM command gmgate N (to find out what each number is)
        reward = forced_reward
    if mission_room(room):                      # no gates in a Mission Battle (user, 2026-10-17)
        reward = 0
    session.log.note(f'gate {index}: position {len(passed)} of {field}, reward {reward}')
    room.cast(Frame(0x1ee, struct.pack('<Ii', m.serial, reward)))


@on(SVC, C2S, 0x1eb)
async def race_end(session, frame):
    p = frame.payload
    room = room_of(session)
    if not room or room.state != RACING or len(p) < 0x4a:
        return
    m = room.member(session)
    who = struct.unpack_from('<I', p)[0]
    ai = room.ai_by_car(who) if m and who != m.serial else None
    if ai:          # an AI its client drives: its end (and finishing place) goes to the room, not to the driver
        m = ai
    if m.end or (not ai and m.serial not in room.racers):
        return
    _, end_type, end_time, record, _ = struct.unpack_from('<IiifI', p)
    rank = 0
    if end_type == FINISHED:
        room.rank += 1
        rank = room.rank
    m.end = (end_type, end_time, record, rank)
    session.log.note(f'room {room.id}: {m.name!r} ends (type {end_type}, record {record:.2f}, rank {rank})')
    frames = [Frame(0x1eb, struct.pack('<IiifI', who if ai else m.serial, end_type, end_time, record, rank)
                    + p[0x14:0x4a])]
    if end_type == FINISHED and room.first_end is None:
        room.first_end = end_time
        finish_ms = getattr(room, 'finish_ms', FINISH_MS)     # channel battle races: 10 s (channels.py)
        frames.append(Frame(0x1ef, struct.pack('<i', end_time + finish_ms)))
        room.cancel_timer()
        room.timer = asyncio.ensure_future(after(room, finish_ms / 1000 + RESULT_GRACE, RACING))
    room.cast(*frames)
    room.waiting.discard(m.serial)
    await progress(room)


async def battle_exp_item(session, p, exp):
    """Battle EXP 25% / 50% up (i_n_battleEXP_25 / _50, use kind battle_exp: "To apply the effect automatically, carry it
    in the inventory"; no client code reads them): the best one held adds its % to a battle's EXP, one is used up per
    battle that pays EXP (a guess: they come in stacks) -> the EXP added."""
    from .alchemy import take_count
    from .items import info_of, mod_list
    held = [(int(i.item_id.rsplit('_', 1)[1]), i.item_id) for i in p.items
            if i.item_id.startswith('i_n_battleEXP_') and i.item_id.rsplit('_', 1)[1].isdigit() and not i.car_id
            and (i.state & 0xffff) != 4 and info_of(i) and info_of(i).kind == 'battle_exp']
    if not exp or not held:
        return 0
    rate, item_id = max(held)
    changes = await take_count(p, item_id, 1)
    if changes:
        send(session, mod_list(*changes))
    session.log.note(f'{item_id}: +{rate}% battle EXP')
    return exp * rate // 100


async def result(room):
    racers = [m for m in room.members if m.serial in room.racers and m.player]
    # the AI racers are in the result too (user, 2026-10-20: they were missing) and count for the places and the
    # field size of the rewards; they get nothing
    racers += [m for m in room.ais if room.racers]
    n = len(racers)
    entries = []
    team_points = [0, 0]
    for m in sorted(racers, key=lambda m: m.end[3] if m.end and m.end[3] else n + 1):
        if not m.session:
            end_type, _, record, rank = m.end or (RETIRED, 0, 0.0, 0)
            if end_type != FINISHED or not rank:
                end_type, rank = RETIRED, n
            point = team_point(min(rank, 32), n) if team_room(room.type) and end_type == FINISHED else 0
            if point and m.serial in room.seats:
                team_points[room.seats.index(m.serial) & 1] += point
            entries.append(pack_exp('<iIIQIfHH3III', end_type, m.serial, 0, 0, 0, record, rank, m.level, 0, 0, 0,
                                    point, 0) + bytes(8))
            continue
        p = m.player
        c = p.char
        end_type, _, record, rank = m.end or (RETIRED, 0, 0.0, 0)
        if end_type != FINISHED or not rank:
            end_type, rank = RETIRED, n
        car = p.car
        exp, money = context.data.pvp_reward(rank, n, (section_rule(room.channel, room.type) or ('', 1, 9, 1.0, 0, 9999))[3],
                                             car.shown_grade() if car else 1)
        from .licenses import CITY_SUFFIX, city_of_track, count_many
        city = city_of_track(room.map_id)
        exp, money = play_bonus(p, exp, money, 'battle_team' if team_room(room.type) else 'battle_personal', city)
        from .. import nation
        if end_type == FINISHED and not nation.is_eu(m.session):      # the complete bonus, per lap (see above)
            bonus = complete_bonus(room.channel, room.type, room.map_flag, len(room.racers))
            laps = lap_count(room.map_id)
            if bonus != (0, 0):
                exp, money = exp + bonus[0] * laps, money + bonus[1] * laps
                m.session.log.note(f'complete bonus: {laps} laps x {bonus} (EXP, Mito), {len(room.racers)} players')
        if mission_room(room):                  # a Mission Battle pays as its instant mission (instant.py)
            exp = money = 0
        exp += await battle_exp_item(m.session, p, exp)
        if exp:
            await add_exp(c, exp)
        if money:
            await add_money(c, money)
        # licenses: a battle played (team or individual room) and a race on a track of that city
        if not mission_room(room):
            await count_many(m.session, ['BattleTeam' if team_room(room.type) else 'BattlePersonal']
                             + ([f'BattleTrack{CITY_SUFFIX[city][0]}'] if city in CITY_SUFFIX else []))
        if n > 1:
            await play_mode(c, 'PVP', 1, 1 if rank == 1 else 0, exp, money)
            if rank == 1 and is_real_match(room.type):     # coupon book: Duel (Real Match wins, DUEL_RM)
                from .coupons import DUEL_RM, add_param
                await add_param(m.session, DUEL_RM)
            tries, wins, points = c.pvp
            c.pvp = (tries + 1, wins + (rank == 1), points)
        # team rooms: a finisher's points go to its team (the seat's parity), as the 2008 PvpRaceResult
        point = team_point(min(rank, 32), n) if team_room(room.type) and end_type == FINISHED else 0
        if point and m.serial in room.seats:
            team_points[room.seats.index(m.serial) & 1] += point
        m.session.log.note(f'race result: rank {rank} of {n}, +{exp} exp, +{money} Mito'
                           + (f', team point {point}' if team_room(room.type) else ''))
        entries.append(pack_exp('<iIIQIfHH3III', end_type, m.serial, money, c.mito, exp, record, rank, c.level,
                                   c.exp, c.exp_next, c.exp_base, point, 0) + bytes(8))
    room.state = WAIT
    room.waiting.clear()
    for m in room.members:
        m.ready = m.serial == room.master or not m.session     # AIs are always ready (a second race was refused 20182)
    if team_room(room.type) and room.members:
        room.members[0].session.log.note(f'room {room.id}: team points {team_points}')
    result_frame = Frame(0x1ec, struct.pack('<iIIfii', 1, *team_points, 0.0, room.first_end or 0, len(entries))
                         + b''.join(entries))
    host = room.by_serial(room.master)
    # the AIs stay as they are until the next start (Room.reset_ais there): leaving right after the result took them
    # out of the result screen (user, 2026-10-20)
    room.cast(room.master_frame(), result_frame, *([ready_frame(host)] if host else []), *map(ready_frame, room.ais))
    for s in room.observers:                    # BS_OBSRoom::SetResult
        send(s, result_frame)
    from .pickem import on_result               # spectators' Pick'em draws (after the result they see)
    await on_result(room)
    lists_changed(room.channel)
    hook = getattr(room, 'on_result', None)     # a channel battle round (channels.race_result)
    if hook:
        hook(room, team_points, result_frame)
