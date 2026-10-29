"""Mission Battles on the 2016 client: the end of the item ones and the Mission Battle Arena (battle zone section 13).

Measured in DriftCity Dev Ed (2016-02-16); the 2011 client has none of these messages. The 2016 client keeps the 2011
item route (Line Ball / Mecha Watch / Exodus Quake item -> 0x3df offer -> 0x3e0 -> 0x3e1, whose handler 0x534100 calls
the mission manager 0x7e1750: 0x1b8 section 5, a 0x1cc room type 0x10000; instant.py, rooms.MISSION_ROOM). New is how
a mission ends: with GlobalContent MissionBattleAdv (1 in the US column; game +0x199, read at 0x442c71; race manager
vfunc 0x68 0x7cee30 returns it) the end dispatcher 0x7e0fd0 takes 0x7df590 for every mission, which sends 0x3eb (as
2011: u32 TableIdx, u32 kind, u32 value, f32 time, u32 tries; instant.mission_battle_result) and then 0x3b8 on a
success, 0x3ba on a failure. 0x3e2 is never sent then (that is the 2011 path 0x7e1084, taken only without the flag).

Messages (sizes with the type):
  C>S 0x3b8 MissionBattleComplete (14; sender 0x851420): u16 mode @2 (1 Line Ball, 2 Mecha Watch, 3 Exodus Quake),
      u16 @4 the mission's TableIdx (mission +0x5c: the Instant_Client row on the item route, 0 in the arena), f32 time
      @6 (s), u32 value @0xa (Line Ball points, Mecha Watch crashes, Exodus Quake 0). Success, as the client judges
      it (0x7df5c7..: time within the limit +0x78 (+0x80), Line Ball points +0x60 >= goal +0x7c, Mecha Watch crashes
      +0x6c < +0x7c).
  S>C 0x3b9 MissionBattleCompleteAck (40; handler 0x52d390): @2 not read (we send mode, u16 @4 as received), i32 Mito
      gained @6 (added to char +0x68 and shown), u32 EXP gained @0xa, EXP / next / base u64 x 3 @0xe (char +0x50),
      u16 level @0x26 (char +0x4e). It resets the mission (0x7df350) and fills the result window (0x795260 ->
      0x796050(EXP, Mito), 0x796e30). The item route then also gets 0x3e3 (handler 0x527160 -> 0x7df430 / 0x766660:
      frees the instant mission, as in 2011).
  C>S 0x3ba MissionBattleFail (6; sender 0x851590): u32 mode. The client fails the mission itself (Rechallenge stays
      its own): no answer. S>C 0x3ba (6; 0x52d460) is something else: it shows 20111 "Your inventory is full. You
      cannot be awarded items." and moves the client on (0x72e970(0x36)); never sent.
Arena (section 13; client 0x67dffe names it 12704 "Mission Battle Arena"; the 0x1be handler 0x543040 copies the
client's section +0x3d528 into the room window +0x1624, and the window's Start 0x10a1eb (0x5cb8bf) sends 0x3b6 for
section 13 when +0x1614 is 1, else the normal start):
  C>S 0x3bb MissionRoomState (6; sender 0x85b020, window 0x5babb0): u16 mode 1-3, u16 difficulty 0-3 (12733-12736
      Sec / Mid / High / Premium Rank), the master's choice. S>C 0x3bb (6; 0x540dc0): u16 mode, u16 difficulty, both
      1-based (the window sets bits 1 << (v - 1) at +0x64 / +0x66, 0x5ba880); ignored by the master's own client
      (race vfunc 0x84 0x7cf290: race +0x3d0 == own serial).
  C>S 0x3b6 MissionBattleStart (6; sender 0x8512c0, window 0x5ba380): u16 mode 1-3, u16 difficulty 0-3.
  S>C 0x3b7 MissionBattleStartAck (22; 0x540e50 -> mission manager 0x7e13d0): u16 mode @2, u16 difficulty @4, u16
      track @6 (window +0x68; the master's client then calls race vfunc 0xd0 0x7cfa70: 0x1d6 for each AI, and 0x1e6
      PvpStartReq with that track), u16 @8 not read, f32 time limit @0xa (+0x78), u32 @0xe not used, u16 @0x12 /
      @0x14: Line Ball goal points +0x7c / +0x68, Mecha Watch crash limit +0x7c / +0x74, Exodus Quake f32(@0x12)
      +0x84 / +0x88. Item route values for comparison (0x7e1863..): Line Ball 150 s / 130 points, Mecha Watch 240 s /
      8, Exodus Quake 300 s (adjusted for level 50 or below).
  S>C 0x3bc MissionBattleSeed (70; 0x540e30 -> 0x8a2000): u32 @2 -> object 0xada8e0 +0x4bc, 16 x u32 @6 -> +0x47c: the
      mission random generator's state (seeded from the clock at 0x8a4b03), so that all members place the same objects.
  0x3bd MissionBattleObjectEvent (8, both ways; sender 0x85b1b0, handler 0x540ef0 -> 0x7e1cf0): u32 object, u16
      event. The sender has applied it already (0x7e0626): relayed to the other members.
Tables (the client's own, server_data_2016/Init): LineBall.xlt / MechaWatch.xlt / ExodusQuake.xlt, one row per
difficulty (low / mid / high / top; Support 1 only for low): Req_Level, Req_CarGrade, RewardExp, RewardMoreExp,
RewardMito, RewardMoreMito, ClearTime, ClearMoreTime, TrackRandID (1000-1002: not tracks), Mecha Watch Clear_Crash /
ClearMore_Crash, Exodus Quake Event_Dist / Rock_Interval. Tracks: PVPTrackInfo's MissionBattle bit 8 - mode (the item
route's pick, 0x7e19b0): Line Ball 11, Mecha Watch 1, Exodus Quake 75 (2011 logs: the client chose those).

*Our rules (guesses)*: the arena race runs as the item one does (a practice run, rooms.mission_room); the reward is the
row's RewardExp / RewardMito, plus RewardMoreExp / RewardMoreMito percent within ClearMoreTime (Mecha Watch: and at most
ClearMore_Crash crashes); Line Ball's goal is the item route's 130 points and its @0x14 is 0 (the item route leaves
+0x68 unset).
"""
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import admin, context
from ..version import is_2016
from .items import add_money
from .login import SVC, send
from .progress import add_exp, play_mode
from .records import pack_exp

LINE_BALL, MECHA_WATCH, EXODUS_QUAKE = 1, 2, 3
TABLES = {LINE_BALL: 'LineBall.xlt', MECHA_WATCH: 'MechaWatch.xlt', EXODUS_QUAKE: 'ExodusQuake.xlt'}
TRACKS = {LINE_BALL: 11, MECHA_WATCH: 1, EXODUS_QUAKE: 75}      # when PVPTrackInfo has no MissionBattle bit
LINE_BALL_GOAL = 130
DIFFICULTY = ('Sec rank', 'Mid Rank', 'High Rank', 'Premium Rank')

_rows = {}
_tracks = None


def rows(mode):
    """The mode's table as dicts by column name, one per difficulty (index 0-3)."""
    if mode not in _rows:
        from ..data import read_xlt
        out = []
        try:
            lines = read_xlt(os.path.join(context.data.root, 'Init', TABLES[mode]))
            head = lines[2]
            for line in lines[3:]:
                if len(line) >= len(head) and line[0].strip().isdigit():
                    out.append({k: line[i].strip() for i, k in enumerate(head) if k})
        except (OSError, IndexError, KeyError):
            pass
        _rows[mode] = out
    return _rows[mode]


def _n(row, key, kind=int):
    try:
        return kind(float(row.get(key, 0)))
    except ValueError:
        return kind(0)


def track(mode):
    """PVPTrackInfo's track with the mode's MissionBattle bit (8 - mode of the bit string, read as a bitset)."""
    global _tracks
    if _tracks is None:
        from ..data import read_xlt
        _tracks = {}
        try:
            lines = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
            col = {k: lines[2].index(k) for k in ('Support', 'Id', 'MissionBattle')}
            for r in lines[3:]:
                if len(r) <= max(col.values()) or not r[col['Id']].strip().isdigit() or r[col['Support']].strip() != '1':
                    continue
                bits = r[col['MissionBattle']].strip().strip('"')
                for m in TABLES:
                    if len(bits) == 8 and bits[len(bits) - 1 - (8 - m)] == '1':
                        _tracks.setdefault(m, int(r[col['Id']]))
        except (OSError, ValueError):
            pass
    return _tracks.get(mode, TRACKS[mode])


def arena_room(session):
    from .rooms import ARENA_SECTION, room_of
    room = room_of(session)
    return room if room and is_2016() and room.channel == ARENA_SECTION else None


def on_join(session, room):
    """A member joins an arena room: the master's choice for its window."""
    choice = getattr(room, 'arena_choice', None)
    if choice:
        send(session, Frame(0x3bb, struct.pack('<HH', choice[0], choice[1] + 1)))


@on(SVC, C2S, 0x3bb)
async def room_state(session, frame):
    room = arena_room(session)
    me = room.member(session) if room else None
    if not me or len(frame.payload) < 4 or me.serial != room.master:
        return
    mode, diff = struct.unpack_from('<HH', frame.payload)
    if mode not in TABLES or not 0 <= diff < 4:
        return
    room.arena_choice = (mode, diff)
    room.cast(Frame(0x3bb, struct.pack('<HH', mode, diff + 1)), skip=me)


def refused(session, room, mode, diff):
    """-> the reason the arena mission cannot start, or None."""
    table = rows(mode)
    if diff >= len(table) or _n(table[diff], 'Support') != 1:
        return f'{DIFFICULTY[diff]} is not open for this mission.'
    row = table[diff]
    for m in room.members:
        p = m.session and m.session.state.get('player')
        if not p:
            continue
        if p.char.level < _n(row, 'Req_Level'):
            return f'{p.char.name}: level {_n(row, "Req_Level")} or higher is needed.'
        if not p.car or p.car.shown_grade() < _n(row, 'Req_CarGrade'):
            return f'{p.char.name}: a V{_n(row, "Req_CarGrade")} or higher vehicle is needed.'
    if any(not o.ready for o in room.members if o.serial != room.master and o.session):
        return 'Everyone must be ready.'
    return None


@on(SVC, C2S, 0x3b6)
async def mission_start(session, frame):
    room = arena_room(session)
    if not room or len(frame.payload) < 4:
        return
    from .rooms import WAIT
    me = room.member(session)
    if not me or me.serial != room.master or room.state != WAIT:
        return
    mode, diff = struct.unpack_from('<HH', frame.payload)
    if mode not in TABLES or not 0 <= diff < 4:
        return session.log.note(f'arena start: mode {mode} difficulty {diff} unknown')
    why = refused(session, room, mode, diff)
    if why:
        session.log.note(f'arena start refused: {why}')
        return admin.message(session, why)
    row, map_id = rows(mode)[diff], track(mode)
    if mode == LINE_BALL:
        a, b = LINE_BALL_GOAL, 0
    elif mode == MECHA_WATCH:
        a, b = _n(row, 'Clear_Crash'), _n(row, 'ClearMore_Crash')
    else:
        a, b = _n(row, 'Event_Dist'), _n(row, 'Rock_Interval')
    room.arena = dict(mode=mode, diff=diff, map=map_id, row=row)
    session.log.note(f'room {room.id}: arena {TABLES[mode][:-4]} {DIFFICULTY[diff]} on track {map_id},'
                     f' {_n(row, "ClearTime")} s, {a} / {b}')
    seed = struct.pack('<I16I', 0, *(random.getrandbits(32) for _ in range(16)))
    room.cast(Frame(0x3bc, seed),
              Frame(0x3b7, struct.pack('<HHHHfIHH', mode, diff, map_id, 0, _n(row, 'ClearTime', float), 0, a, b)))


def start_flag(session, room):
    """rooms.start_request for an arena room: the map flag of its practice run, or None (no arena mission chosen)."""
    a = getattr(room, 'arena', None)
    if not a:
        session.log.note(f'room {room.id}: arena start without a mission (0x3b6) refused')
        admin.message(session, 'Choose a mission and press Start.')
        return None
    return 0x204a if a['map'] == TRACKS[LINE_BALL] else 0x2048      # what the item route's room has (0x7e196b)


@on(SVC, C2S, 0x3b8)
async def mission_complete(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    mode, idx, seconds, value = struct.unpack_from('<HHfI', frame.payload)
    c = p.char
    from . import instant
    m = instant.current(session, idx) if idx else None
    if m:                                       # the item route: its Instant_Client row's reward (instant.py)
        exp, money = await instant.pay(session, p, idx, m)
        reply = [Frame(0x3e3, struct.pack('<I', idx))]
    else:
        room = arena_room(session)
        a = getattr(room, 'arena', None) if room else None
        if not a or a['mode'] != mode:
            return session.log.note(f'mission complete {mode}/{idx}: no mission running')
        row = a['row']
        exp, money = _n(row, 'RewardExp'), _n(row, 'RewardMito')
        more = 0 < seconds <= _n(row, 'ClearMoreTime', float)
        if mode == MECHA_WATCH:
            more = more and value <= _n(row, 'ClearMore_Crash')
        if more:
            exp += exp * _n(row, 'RewardMoreExp') // 100
            money += money * _n(row, 'RewardMoreMito') // 100
        if exp:
            await add_exp(c, exp)
        if money:
            await add_money(c, money)
        await play_mode(c, 'INSTANT', exp=exp, money=money)
        from .login import stat_frames
        for f in stat_frames(p):
            send(session, f)
        reply = []
        session.log.note(f'arena mission {TABLES[mode][:-4]} {DIFFICULTY[a["diff"]]}: {seconds:.2f} s, value {value},'
                         f' {exp} exp, {money} Mito{" (bonus)" if more else ""}')
    send(session, Frame(0x3b9, pack_exp('<HHiI3IH', mode, idx, money, exp, c.exp, c.exp_next, c.exp_base, c.level)),
         *reply)


@on(SVC, C2S, 0x3ba)
async def mission_fail(session, frame):
    mode, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    session.state.pop('mission_result', None)
    session.log.note(f'mission battle {mode} failed (the client retries or leaves by itself)')


@on(SVC, C2S, 0x3bd)
async def object_event(session, frame):
    room = arena_room(session)
    if room and len(frame.payload) >= 6:
        room.cast(Frame(0x3bd, frame.payload[:6]), skip=room.member(session))
