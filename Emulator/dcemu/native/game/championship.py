"""GT Championship: the 2011 client's tournament (GlobalContent "Tournament" = "토너먼트(GT Championship)"; the
battle zone's tournament lobby, game.nui dialog 900000, ID_TOUR_*). There is no tournament in the 2008 server: the
rules below are the client's (its help texts championship_help_1..4 and the code that shows them) and our choices
where the client says nothing (marked).

Classes = battle zone sections (PvP channel; 0x1b8 / 0x1b9, the lobby's tabs 900005-900008, client 0x59afd0):
  7 Rookie (level 70 or lower: the client refuses the section from 71, 0x1b9 handler 0x52a040, and the stage buttons,
  0x59ab40; GlobalText Championship_Tooltip1 says "Pre-selected Vehicle": not done, own cars), 8 Touring B and
  9 Touring A (the client caps the top speed itself, 0x4810b0: GlobalContent PvpGT_TouringB 341 / PvpGT_TouringA 361;
  the content flags TouringBSpeed / TouringASpeed only feed the tooltips), 10 GT Master (no limits).
Rounds (0x1b9 @0x1e, 0xd48 @0xa, 0xd49 @2; the client's PvP manager APP+0x168 vcalls 0x20 / 0x28): 0 none,
  2 Preliminaries, 3 Quarter-finals 1, 4 Quarter-finals 2, 5 Semi-finals, 6 Finals. Every class runs on the same clock.
Times (content flags, minutes; login.content_flags via context.extra_flags): BattleZone.PreMatchTime = the
  preliminaries; MatchWaitTime = the entry window of a later round, then MainMatchTime (quarter-finals) or
  FinalMatchTime (semi-finals, finals) for its races. The client counts down to a round's end time (0x1b9 @0x22, 0xd48
  @2, on the server clock = now()) and shows the race start at end - Main/FinalMatchTime (0x595ee0); the server starts
  the races then.
Preliminaries: time attack. The lobby's stage button sends 0x1bb RoomDirectJoin (0x596c10); the server puts the
  player into a Preliminaries room of the class (made on demand, 16 seats, the stage's track), where the room's host
  starts races as usual (the client refuses Start / Ready in the last 3 minutes, 0x596e60 / 0x598710, text 11572; so
  does the server). Each finished race's record counts; a player's best is their preliminary record. Moving to another
  class lobby during the preliminaries drops the records (the client warns, Championship_msg2).
Later rounds: the passed players are seeded into groups (A, B, ...) of up to 16, a room each ("Quarter-finals 1-A");
  the stage button or the room list's Join puts a player into their own group's room; others are refused (11574).
  At the race time the server starts the race with whoever is in the room; an absent contender is out
  (Championship_infotext3). Quarter-finals: one race, the better half of the group passes. Semi-finals and finals: two
  races, points per position (championship_help_3: 20 18 16 .. 1, the last round 30 27 24 .. 2, +3 / +5 for
  finishing); ties go to the last round's points; between the races 0xd4a RoomTimeOut 1 ("The 2nd round will begin
  shortly"). A class with fewer than min_players after the preliminaries is cancelled (Championship_msg10).
Ladder (*our choice*; the client: "The tournament ladder ... may vary depending on the number of participants"):
  up to 64 pass the preliminaries; a stage is raced only when it has more players than the next one takes
  (quarter-finals 1 -> 32, 2 -> 16, semi-finals -> 8); else everyone passes it. The finals rank everyone; prizes
  ([championship] reward.<class>.<rank>) go by message (Mito and an item).

Messages (offsets from the message type; sizes are what the client's handlers return):
  0xd48 TournamentNotice (0xe; client 0x52b4b0): u32 time @2 (the round's end / the start, server clock), u32 kind @6
        (0 the time left, 1 the round has begun / round 0: "The GT Championship Match has ended!", 2 round 0: cancelled
        (Championship_msg10 box), 3 silent: only the round and time), u32 round @0xa. To everyone in the game.
  0xd49 TournamentInfo (0x23; 0x52a510 -> the lobby UI+0x290): u32 round @2, class @6, players @0xa, the winning
        requirement rank @0xe and f32 its record @0x12 (preliminaries: "Ranking %d - m:ss:cc"), f32 my record or
        points @0x16, u32 my rank @0x1a, my state @0x1e, char my group @0x22.
        States (also 0xd4c, 0xd51): 0 none, 1 in progress, 2 contender / on standby (then "Please enter the
        Quarter-finals 1 %c Room."), 3 disqualified, 4 passed.
  0xd4a RoomTimeOut (6; 0x52aa20): u32 kind: 1 the second race comes, 5 the room's matches are over.
  0xd4b TournamentMyInfo (no body; "Details" buttons 900273 / 1010401) -> 0xd4c (0x213; 0x591270): u32 class @2,
        stage records of 0x4b from @0x6a (preliminaries: f32 best @+0x37, rank @+0x3b, players @+0x3f, races
        @+0x43, state @+0x47; quarter-finals 1 @0xb5, 2 @0x100, semi-finals @0x14b: group @+0x32, players @+0x3b,
        rank @+0x3f, (semi) points @+0x43, state @+0x47), the finals @0x196 and three round records of 0x19 from
        @0x1c8 *(their exact meaning is a guess: semi round 1 / 2, final)*.
  0xd4d TournamentRaceInfo (no body; the state button, opens the info window) -> 0xd4e (0x16; 0x52a680): @6 class,
        @0xa round, @0xe map | map flag << 16, @0x12 0.
  0xd50 TournamentList (u32 class, stage, page) -> 0xd51 (0x14 + n x 0x5e; 0x52b9e0): u16 n @2, class @4, stage @8,
        pages @0xc, page @0x10; a row per player: u32 rank, wchar[21] name @4, wchar[13] crew @0x2e, u32 map @0x48,
        state @0x4c, stage @0x50, char group @0x54, u32 points @0x56, f32 record @0x5a.
  0xd56 TournamentSearch (0x52: u32 0, class, stage, wchar[32] name, u32 page) -> 0xd57 (0x54 + n x 0x5e): the
        same rows, header u16 n @2, class @4, stage @8, the name @0xc, pages @0x4c, page @0x50.
  0xd54 TournamentRewardList (u32 class) -> 0xd55 (0x20a): u32 class @2, u32 selected @6, wchar[16] x 16 lines.
  0xd52 TournamentSetReward (GM: class, reward id) -> 0xd53 (0xb): class @2, id @6, u8 ok @0xa (GM_Rewardset_*).
  0xd4f (GM map setting: u32 @2, u16 map @6, u32 map flag @0xa): the stages' track for every class (our choice).
State lives in memory: an emulator restart ends a running championship. GM: gmtour (gm_command).
"""
import asyncio
import math
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import admin, context, now
from .login import SVC, send, sessions
from .records import wstr

CLASSES = (7, 8, 9, 10)
CLASS_NAMES = {7: 'Rookie', 8: 'Touring B', 9: 'Touring A', 10: 'GT Master'}
ROOKIE, ROOKIE_MAX_LEVEL = 7, 70
IDLE, PRE, QF1, QF2, SEMI, FINAL = 0, 2, 3, 4, 5, 6
LATER = (QF1, QF2, SEMI, FINAL)
STAGE_NAMES = {PRE: 'Preliminaries', QF1: 'Quarter-finals 1', QF2: 'Quarter-finals 2', SEMI: 'Semi-finals',
               FINAL: 'Finals'}
NONE, PLAYING, STANDBY, OUT, PASSED = 0, 1, 2, 3, 4
TIME_LEFT, BEGUN, CANCELLED, SILENT = 0, 1, 2, 3
GROUP_MAX = 16
PRE_PASS = 64                                       # our choice: the preliminaries' cut
NEXT_TAKES = {QF1: 32, QF2: 16, SEMI: 8, FINAL: 0}  # our choice: how many a raced stage passes on (FINAL: ranks all)
ROUND_POINTS = (20, 18, 16, 14, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0)      # championship_help_3
LAST_POINTS = (30, 27, 24, 21, 18, 16, 14, 12, 10, 9, 8, 7, 6, 5, 4, 2)
FINISH_POINTS = (3, 5)
LAST_MINUTES = 3                                    # no preliminary room start / entry in the last 3 minutes
SECOND_RACE_DELAY = 20                              # s between the two races of a semi-final / final (our choice)
NOTICE_SECONDS = (600, 300, 180, 60, 30, 10)        # "will start / end in" notices (our choice)
PAGE = 10                                           # list rows per page (our choice)
LIST_ROW = 0x5e

_t = None


def cfg():
    return context.championship


class Entrant:
    def __init__(self, cid, name, crew, cls):
        self.cid, self.name, self.crew, self.cls = cid, name, crew, cls
        self.best = 0.0             # preliminary record, s (0 = none)
        self.races = 0
        self.state = {}             # stage -> NONE .. PASSED
        self.group = {}             # stage -> group letter
        self.rank = {}              # stage -> rank (preliminaries: in the class; later: in the group)
        self.size = {}              # stage -> players in that ranking
        self.points = {}            # stage -> [race 1, race 2]
        self.record = {}            # stage -> best record of the stage's races

    def total(self, stage):
        return sum(self.points.get(stage, ()))


class Group:
    def __init__(self, stage, letter, cids):
        self.stage, self.letter, self.cids = stage, letter, list(cids)
        self.room = None
        self.race = 0               # races run (semi-finals / finals: 2)
        self.done = False


class Cls:
    def __init__(self, cid):
        self.id = cid
        self.entrants = {}
        self.groups = {}            # stage -> [Group]
        self.cancelled = False
        self.finished = False
        self.prelim_rooms = []
        self.prelim_n = 0

    def of_stage(self, stage):
        """The players of a stage (from the quarter-finals: those the previous stage passed)."""
        if stage == PRE:
            return [e for e in self.entrants.values() if e.best > 0]
        return [e for e in self.entrants.values() if e.state.get(stage) is not None]


class Tournament:
    def __init__(self):
        self.round = IDLE
        self.start = 0.0            # time.time() of the preliminaries' start
        self.round_end = 0.0        # time.time() of the current round's end
        self.race_at = 0.0          # time.time() of the current round's races (later rounds)
        self.active = False
        self.classes = {c: Cls(c) for c in CLASSES}
        self.maps = {}              # stage -> (map, flag) set by a GM (0xd4f)
        self.notified = set()
        self.closing = False
        self.races_started = False


def tour():
    global _t
    if _t is None:
        _t = Tournament()
        asyncio.ensure_future(_ticker())
    return _t


def clock(ts):
    """time.time() -> the server clock the client counts with (now())."""
    return int(ts) + (now() - int(time.time())) if ts else 0


def minutes(name):
    return max(1, int(cfg()[name]))


def stage_map(stage):
    t = tour()
    if stage in t.maps:
        return t.maps[stage]
    maps = cfg()['maps']
    return maps[min(len(maps) - 1, (PRE, QF1, QF2, SEMI, FINAL).index(stage))], cfg()['map_flag']


def log(text):
    print(f'championship: {text}', flush=True)


def players():
    return [s for s in list(sessions.values()) if s.state.get('player')]


def entrant_of(session):
    p = session.state.get('player')
    if not p:
        return None
    for c in tour().classes.values():
        e = c.entrants.get(p.char.cid)
        if e:
            return e
    return None


def viewing(session):
    """The tournament class whose lobby the session shows (its battle zone section), or None."""
    ch = session.state.get('pvp_channel')
    return ch if ch in CLASSES else None


# ---- frames ------------------------------------------------------------------------------------------------------

def notice_frame(kind, rnd=None, at=None):
    t = tour()
    rnd = t.round if rnd is None else rnd
    return Frame(0xd48, struct.pack('<III', clock(at if at is not None else t.round_end), kind, rnd))


def section_tail():
    """0x1b9's last 12 bytes (client 0x52a040: pvp vcalls 0x18, 0x20, 0x24): u32 0, the round, its end time."""
    t = tour()
    return struct.pack('<III', 0, t.round, clock(t.round_end) if t.round else clock(t.start))


def requirement(c, e):
    """0xd49 @0xe / @0x12: the winning requirement of the current round (rank, its record)."""
    t = tour()
    if t.round == PRE:
        ranked = sorted((x for x in c.entrants.values() if x.best > 0), key=lambda x: x.best)
        cut = min(PRE_PASS, max(len(ranked), 1))
        return cut, ranked[cut - 1].best if len(ranked) >= cut else 0.0
    g = group_of(c, t.round, e) if e else None
    if g:
        takes = pass_count(c, t.round, g)
        return takes, 0.0
    return 0, 0.0


def info_frame(session):
    """0xd49 for a session in a tournament lobby."""
    t = tour()
    cls = viewing(session) or ROOKIE
    c = t.classes[cls]
    e = entrant_of(session)
    if e and e.cls != cls:
        e = None
    stage = t.round if t.round in (PRE,) + LATER else PRE
    rank_need, rec_need = requirement(c, e)
    mine, my_rank, my_state, letter = 0.0, 0, 0, 0
    if e:
        if stage == PRE:
            mine = e.best
            my_rank = prelim_rank(c, e)
        elif stage in (SEMI, FINAL):
            mine = float(e.total(stage))
            my_rank = e.rank.get(stage, 0)
        else:
            mine = e.record.get(stage, 0.0)
            my_rank = e.rank.get(stage, 0)
        my_state = e.state.get(stage, NONE)
        letter = ord(e.group.get(stage, '\0')[:1] or '\0')
    count = len(c.of_stage(stage)) if t.round else len(c.entrants)
    return Frame(0xd49, struct.pack('<IIIIffIIB', t.round, cls, count, rank_need, rec_need, mine, my_rank, my_state,
                                    letter))


def prelim_rank(c, e):
    ranked = sorted((x for x in c.entrants.values() if x.best > 0), key=lambda x: x.best)
    return next((i + 1 for i, x in enumerate(ranked) if x is e), 0)


def my_info_frame(session):
    """0xd4c TournamentMyInfo (0x213 bytes)."""
    t = tour()
    e = entrant_of(session)
    cls = e.cls if e else (viewing(session) or ROOKIE)
    b = bytearray(0x213)
    struct.pack_into('<H', b, 0, 0xd4c)
    struct.pack_into('<I', b, 2, cls)
    if e:
        c = t.classes[cls]
        if e.best > 0 or e.state.get(PRE) is not None:
            n = len(c.of_stage(PRE))
            struct.pack_into('<fIIII', b, 0x6a + 0x37, e.best, prelim_rank(c, e), n, e.races, e.state.get(PRE, PLAYING))
        for stage, base in ((QF1, 0xb5), (QF2, 0x100), (SEMI, 0x14b)):
            if e.state.get(stage) is None:
                continue
            b[base + 0x32] = ord(e.group.get(stage, '-')[:1])
            struct.pack_into('<IIII', b, base + 0x3b, e.size.get(stage, 0), e.rank.get(stage, 0), e.total(stage),
                             e.state[stage])
        if e.state.get(FINAL) is not None:              # *guess*: which of these blocks is which race
            pts = e.points.get(FINAL, [0, 0])
            struct.pack_into('<III', b, 0x19f, e.size.get(FINAL, 0), e.rank.get(FINAL, 0), pts[0])
            struct.pack_into('<IIII', b, 0x1b8, e.size.get(FINAL, 0), e.rank.get(FINAL, 0), e.total(FINAL),
                             e.state[FINAL])
        for k, (stage, race) in enumerate(((SEMI, 0), (SEMI, 1), (FINAL, 1))):
            if e.state.get(stage) is None:
                continue
            base = 0x1c8 + 0x19 * k
            b[base] = ord(e.group.get(stage, 'Z')[:1])
            pts = e.points.get(stage, [0, 0])
            struct.pack_into('<IIII', b, base + 9, e.size.get(stage, 0), e.rank.get(stage, 0), pts[race],
                             e.state[stage])
    return Frame(0xd4c, bytes(b[2:]))


def row(e, stage, map_id):
    """A 0xd51 / 0xd57 row (0x5e)."""
    if stage == PRE:
        rank, points, record = prelim_rank(tour().classes[e.cls], e), 0, e.best
    else:
        rank, points, record = e.rank.get(stage, 0), e.total(stage), e.record.get(stage, 0.0)
    return (struct.pack('<I', rank) + wstr(e.name, 0x2a) + wstr(e.crew, 0x1a)
            + struct.pack('<IIIBBIf', map_id, e.state.get(stage, NONE), stage,
                          ord(e.group.get(stage, '\0')[:1] or '\0'), 0, points, record))


def ranking(cls, stage, name=None):
    c = tour().classes.get(cls)
    if not c:
        return []
    found = c.of_stage(stage)
    if name:
        found = [e for e in found if name.lower() in e.name.lower()]
    if stage == PRE:
        return sorted(found, key=lambda e: e.best)
    return sorted(found, key=lambda e: (e.group.get(stage, ''), e.rank.get(stage, 99), e.name))


def list_frame(cls, stage, page, name=None):
    rows = ranking(cls, stage, name)
    pages = max(1, math.ceil(len(rows) / PAGE))
    page = max(0, min(page, pages - 1))
    part = rows[page * PAGE:(page + 1) * PAGE]
    map_id = stage_map(stage)[0] if stage in STAGE_NAMES else 0
    body = b''.join(row(e, stage, map_id) for e in part)
    if name is None:
        return Frame(0xd51, struct.pack('<HIIII', len(part), cls, stage, pages, page) + body)
    return Frame(0xd57, struct.pack('<HII', len(part), cls, stage) + wstr(name, 64) + struct.pack('<II', pages, page)
                 + body)


def race_info_frame(session):
    t = tour()
    stage = t.round if t.round in STAGE_NAMES else PRE
    map_id, flag = stage_map(stage)
    return Frame(0xd4e, struct.pack('<IIIII', 1, viewing(session) or ROOKIE, t.round, (map_id & 0xffff) | (flag << 16),
                                    0))


def reward_lines(cls):
    out = []
    for rank in range(1, 17):
        r = cfg()['rewards'].get((cls, rank))
        if not r:
            continue
        mito, item, count = r
        text = f'{rank}. ' + (f'{mito // 1000}k' if mito >= 1000 else str(mito) if mito else '')
        if item:
            text += f' +{item if count == 1 else f"{count} {item}"}'
        out.append(text[:15])
    return out


def reward_frame(cls):
    lines = reward_lines(cls)[:16]
    return Frame(0xd55, struct.pack('<II', cls, 0) + b''.join(wstr(x, 32) for x in lines + [''] * (16 - len(lines))))


MILE = 1.609344


def speed_flags(session):
    """Content flag overrides for the Touring classes' speed texts (login.py, the 0x1e at the character load). The
    flags only feed texts: the lobby tooltip (Championship_Tooltip2, 0x597f0c) and the rules window (11527, 0x591b69);
    the cap itself is GlobalContent PvpGT_TouringA / B, km/h. The US client's Value_US says "%d mph or under" (11527)
    and, since 2026-10-19, "Speed Limit: %d mph" (Championship_Tooltip2, tools/global_text.py; was "%dkm/h"): US
    clients get the caps in mph (341 km/h -> 212); EU clients (their texts say km/h) the km/h."""
    from .. import nation
    a, b = cfg()['touring_a'], cfg()['touring_b']
    if not nation.is_eu(session):
        a, b = round(a / MILE), round(b / MILE)
    return {'BattleZone_TouringASpeed': a, 'BattleZone_TouringBSpeed': b}


# ---- sending -----------------------------------------------------------------------------------------------------

def broadcast(*frames):
    for s in players():
        send(s, *frames)


def refresh(cls=None):
    """0xd49 again to everyone in a tournament lobby (of the class)."""
    for s in players():
        v = viewing(s)
        if v and (cls is None or v == cls):
            send(s, info_frame(s))


def notice_all(kind, rnd=None, at=None):
    broadcast(notice_frame(kind, rnd, at))


# ---- the schedule ------------------------------------------------------------------------------------------------

def next_start(after=None):
    """The next scheduled start ([championship] schedule: "weekday HH:MM" entries, local time; weekday 0 = Sunday
    .. 6, or * for every day) after the given time, or 0."""
    after = time.time() if after is None else after
    best = 0
    lt = time.localtime(after)
    midnight = after - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
    for day, hh, mm in cfg()['schedule']:
        for k in range(8):
            d = midnight + k * 86400
            wd = (time.localtime(d).tm_wday + 1) % 7
            if day is not None and wd != day:
                continue
            at = d + hh * 3600 + mm * 60
            if at > after and (not best or at < best):
                best = at
    return best


def schedule(start):
    t = tour()
    if t.active:
        return False
    t.__init__()
    t.start = start
    t.active = True
    log(f'scheduled for {time.strftime("%a %H:%M", time.localtime(start))}')
    refresh()
    return True


async def _ticker():
    while True:
        await asyncio.sleep(1)
        try:
            await tick()
        except Exception as e:          # the championship must not stop the server
            log(f'tick: {e!r}')


async def tick():
    t = _t
    now_ = time.time()
    if not t.active:
        if cfg()['enabled'] and cfg()['schedule']:
            start = next_start(now_ - 1)
            if start and start - now_ <= max(NOTICE_SECONDS):
                schedule(start)
        return
    if t.round == IDLE:
        left = int(t.start - now_)
        for sec in NOTICE_SECONDS:
            if left <= sec and ('start', sec) not in t.notified and left > 0:
                t.notified.add(('start', sec))
                notice_all(TIME_LEFT, IDLE, t.start)
        if now_ >= t.start:
            begin_prelims()
        return
    left = int(t.round_end - now_)
    for sec in (300, 60, 30):
        if 0 < left <= sec and ('end', t.round, sec) not in t.notified:
            t.notified.add(('end', t.round, sec))
            notice_all(TIME_LEFT)
    if t.round == PRE:
        if now_ >= t.round_end:
            await end_prelims()
        return
    if not t.races_started and now_ >= t.race_at:
        t.races_started = True
        start_round_races()
    if now_ >= t.round_end and all_done():
        await next_round()


def begin_prelims():
    t = tour()
    t.round = PRE
    t.round_end = t.start + minutes('pre') * 60
    t.notified = {k for k in t.notified if k[0] == 'start'}
    log(f'preliminaries until {time.strftime("%H:%M:%S", time.localtime(t.round_end))}')
    notice_all(BEGUN)
    refresh()


def prelim_racing(c):
    from . import rooms
    return any(r.state != rooms.WAIT for r in (rooms.rooms.get(i) for i in c.prelim_rooms) if r)


async def end_prelims():
    """The preliminaries are over: the running races are waited for, then everyone leaves the rooms and the classes
    are seeded."""
    t = tour()
    if any(prelim_racing(c) for c in t.classes.values()) and time.time() < t.round_end + 180:
        if not t.closing:
            t.closing = True
            log('preliminaries over: waiting for the running races')
        return
    t.closing = False
    from . import rooms
    for c in t.classes.values():
        for rid in c.prelim_rooms:
            r = rooms.rooms.get(rid)
            if r:
                close_room(r)
        c.prelim_rooms = []
        ranked = c.of_stage(PRE)
        if not ranked and not c.entrants:
            c.cancelled = True
            continue
        if len(ranked) < cfg()['min_players']:
            c.cancelled = True
            for e in c.entrants.values():
                e.state[PRE] = OUT
            tell_class(c, notice_frame(CANCELLED, IDLE, time.time()))
            log(f'{CLASS_NAMES[c.id]}: {len(ranked)} with a record, fewer than {cfg()["min_players"]}: cancelled')
            continue
        ranked.sort(key=lambda e: e.best)
        for i, e in enumerate(ranked):
            e.rank[PRE], e.size[PRE] = i + 1, len(ranked)
            e.state[PRE] = PASSED if i < PRE_PASS else OUT
            if i < PRE_PASS:
                e.state[QF1] = STANDBY
        for e in c.entrants.values():
            if e.best <= 0:                     # entered, but no finished race: no record
                e.state[PRE] = OUT
        log(f'{CLASS_NAMES[c.id]}: {min(len(ranked), PRE_PASS)} of {len(ranked)} pass the preliminaries')
    await next_round()


def tell_class(c, *frames):
    cids = set(c.entrants)
    for s in players():
        if s.state['player'].char.cid in cids or viewing(s) == c.id:
            send(s, *frames)


async def next_round():
    """The next round with racing in it (a round no class races is skipped), or the end."""
    t = tour()
    order = (QF1, QF2, SEMI, FINAL)
    start = order.index(t.round) + 1 if t.round in order else 0
    for stage in order[start:]:
        raced = False
        for c in t.classes.values():
            if c.cancelled or c.finished:
                continue
            raced |= seed(c, stage)
        if raced:
            t.round = stage
            t.races_started = False
            wait = minutes('wait') * 60
            length = minutes('main' if stage in (QF1, QF2) else 'final') * 60
            t.race_at = time.time() + wait
            t.round_end = t.race_at + length
            t.notified = {k for k in t.notified if k[0] == 'start'}
            log(f'{STAGE_NAMES[stage]}: races at {time.strftime("%H:%M:%S", time.localtime(t.race_at))}')
            notice_all(BEGUN)
            refresh()
            return
    await finish()


def seed(c, stage):
    """The stage's groups for a class (snake seeding by the previous ranking). -> True when the stage is raced; a
    stage with no more players than the next takes passes everyone without a race."""
    players_ = [e for e in c.entrants.values() if e.state.get(stage) == STANDBY]
    prev = {QF1: PRE, QF2: QF1, SEMI: QF2, FINAL: SEMI}[stage]
    players_.sort(key=lambda e: (e.rank.get(prev, 999), e.best or 9e9))
    if not players_:
        c.finished = True
        return False
    takes = NEXT_TAKES[stage]
    if stage != FINAL and len(players_) <= takes:
        nxt = {QF1: QF2, QF2: SEMI, SEMI: FINAL}[stage]
        for i, e in enumerate(players_):
            e.state[stage], e.state[nxt] = PASSED, STANDBY
            e.rank[stage], e.size[stage] = i + 1, len(players_)
        return False
    n_groups = max(1, math.ceil(len(players_) / GROUP_MAX))
    groups = [[] for _ in range(n_groups)]
    for i, e in enumerate(players_):
        k = i % (2 * n_groups)
        groups[k if k < n_groups else 2 * n_groups - 1 - k].append(e)
    c.groups[stage] = []
    for k, members in enumerate(groups):
        letter = chr(ord('A') + k) if stage != FINAL else 'Z'
        g = Group(stage, letter, [e.cid for e in members])
        for e in members:
            e.group[stage], e.size[stage] = letter, len(members)
        c.groups[stage].append(g)
        make_room(c, g)
    log(f'{CLASS_NAMES[c.id]} {STAGE_NAMES[stage]}: {len(players_)} players in {n_groups} group(s)')
    return True


def pass_count(c, stage, g):
    if stage == FINAL:
        return len(g.cids)
    takes = NEXT_TAKES[stage]
    total = sum(len(x.cids) for x in c.groups.get(stage, [])) or 1
    return max(1, min(len(g.cids), round(takes * len(g.cids) / total)))


def group_of(c, stage, e):
    return next((g for g in c.groups.get(stage, []) if e.cid in g.cids), None)


def all_done():
    t = tour()
    return all(g.done for c in t.classes.values() for g in c.groups.get(t.round, []))


# ---- rooms -------------------------------------------------------------------------------------------------------

def make_room(c, g):
    from . import rooms
    map_id, flag = stage_map(g.stage)
    name = (f'{STAGE_NAMES[g.stage]}-{g.letter}' if g.stage in (QF1, QF2, SEMI) else STAGE_NAMES[g.stage])
    r = rooms.Room(c.id, 0, map_id, flag, GROUP_MAX, name, '')
    r.no_start = True
    r.real_alone = True
    r.fixed_map = map_id
    r.tour_group = (c.id, g)
    r.join_check = lambda session, room=r: may_join(session, room)
    r.on_result = lambda room, points, frame, grp=g, cls=c: asyncio.ensure_future(stage_result(cls, grp, room))
    rooms.rooms[r.id] = r
    g.room = r
    rooms.lists_changed(c.id)
    return r


def prelim_room(c):
    from . import rooms
    for rid in list(c.prelim_rooms):
        r = rooms.rooms.get(rid)
        if not r:
            c.prelim_rooms.remove(rid)
        elif r.state == rooms.WAIT and rooms.OPEN in r.seats:
            return r
    map_id, flag = stage_map(PRE)
    c.prelim_n += 1
    r = rooms.Room(c.id, 0, map_id, flag, GROUP_MAX, f'{STAGE_NAMES[PRE]} {c.prelim_n}', '')
    r.real_alone = True
    r.fixed_map = map_id
    r.start_check = lambda session: prelim_start_ok(session)
    r.on_result = lambda room, points, frame, cls=c: prelim_result(cls, room)
    rooms.rooms[r.id] = r
    c.prelim_rooms.append(r.id)
    return r


def close_room(r):
    from . import rooms
    for m in list(r.humans):
        send(m.session, Frame(0xd4a, struct.pack('<I', 5)))
        rooms.leave(m.session)
    if rooms.rooms.get(r.id) is r:
        del rooms.rooms[r.id]
        rooms.lists_changed(r.channel)


def prelim_start_ok(session):
    left = tour().round_end - time.time()
    if tour().round != PRE or left <= LAST_MINUTES * 60:
        admin.message(session, 'You cannot enter or start a Preliminaries room if there are 3 minutes or fewer '
                               'before preliminaries end.')
        return False
    return True


def may_join(session, room):
    """A later round's room: its own group's contenders only (11574)."""
    p = session.state.get('player')
    g = room.tour_group[1]
    if p and p.char.cid in g.cids and not g.done:
        return True
    admin.message(session, 'You cannot participate in this match because you are a non-contender or have been '
                           'disqualified. You may enter the stadium as an observer.')
    return False


def enter(session, payload, cls):
    """0x1bb from a tournament lobby (its stage button): into the player's room for the current round."""
    from . import rooms
    t = tour()
    p = session.state['player']
    c = t.classes[cls]
    if cls == ROOKIE and p.char.level > ROOKIE_MAX_LEVEL:
        return admin.message(session, 'Only players at level 70 or lower are eligible for this match.')
    if t.round == PRE:
        if not prelim_start_ok(session):
            return
        e = entrant_of(session)
        if e and e.cls != cls:
            drop(e)
            e = None
        if not e:
            e = c.entrants[p.char.cid] = Entrant(p.char.cid, p.char.name, p.char.team_name or '', cls)
            e.state[PRE] = PLAYING
        room = prelim_room(c)
    elif t.round in LATER:
        e = c.entrants.get(p.char.cid)
        g = group_of(c, t.round, e) if e else None
        if not g or g.done or e.state.get(t.round) != STANDBY:
            return admin.message(session, 'You cannot enter the stadium because you are a non-contender or have '
                                          'been disqualified.')
        room = g.room
        if room is None or rooms.rooms.get(room.id) is not room:
            room = make_room(c, g)
    else:
        return admin.message(session, 'The GT Championship is not running now.')
    put_in(session, payload, room)


def put_in(session, payload, room):
    from . import rooms
    empty = not room.humans
    rooms.direct_join(session, payload, room)
    m = room.member(session)
    if m and empty:                             # a server-made room: its first player is the host
        room.master = m.serial
        m.ready = True
        room.cast(room.master_frame(), room.state_frame())
    if m:
        send(session, info_frame(session))


def drop(e):
    """Moving to another class during the preliminaries drops the records (Championship_msg2)."""
    c = tour().classes[e.cls]
    c.entrants.pop(e.cid, None)
    log(f'{e.name}: records in {CLASS_NAMES[e.cls]} dropped (another class)')


# ---- races -------------------------------------------------------------------------------------------------------

def prelim_result(c, room):
    t = tour()
    for m in room.members:
        p = m.player
        if not p or not m.end:
            continue
        e = c.entrants.get(p.char.cid)
        if not e:
            e = c.entrants[p.char.cid] = Entrant(p.char.cid, p.char.name, p.char.team_name or '', c.id)
        e.races += 1
        end_type, _, record, _ = m.end
        from .rooms import FINISHED
        if end_type == FINISHED and record > 0 and (not e.best or record < e.best):
            e.best = record
            m.session.log.note(f'GT Championship {CLASS_NAMES[c.id]}: new best {record:.2f}')
    if t.round == PRE:
        refresh(c.id)


def start_round_races():
    t = tour()
    for c in t.classes.values():
        for g in c.groups.get(t.round, []):
            start_race(c, g)


def start_race(c, g):
    """The group's race on the stage's track, with whoever is in the room (rooms.py's start, server side)."""
    from . import rooms
    from .. import tick as server_tick
    r = g.room
    present = {m.player.char.cid for m in (r.humans if r and rooms.rooms.get(r.id) is r else []) if m.player}
    for cid in g.cids:
        e = c.entrants[cid]
        if cid not in present and e.state.get(g.stage) in (STANDBY, PLAYING):
            e.state[g.stage] = OUT                      # not in the room at the start (Championship_infotext3)
    if not present:
        g.done = True
        log(f'{CLASS_NAMES[c.id]} {STAGE_NAMES[g.stage]} {g.letter}: nobody came')
        if r and rooms.rooms.get(r.id) is r:
            close_room(r)
        refresh(c.id)
        return
    for cid in present:
        if cid in g.cids:
            c.entrants[cid].state[g.stage] = PLAYING
    g.race += 1
    r.state = rooms.LOADING
    r.waiting = {o.serial for o in r.humans}
    r.racers = [o.serial for o in r.humans]
    r.rank, r.first_end, r.gates = 0, None, {}
    for o in r.members:
        o.loaded, o.end = False, None
    map_id, flag = stage_map(g.stage)
    r.map_id = map_id
    log(f'{CLASS_NAMES[c.id]} {STAGE_NAMES[g.stage]} {g.letter}: race {g.race}, {len(present)} racers, map {map_id}')
    r.cast(r.master_frame(), r.state_frame(),
           Frame(0x1e7, struct.pack('<iiiifii', 0, map_id, flag, r.area, 0.0, server_tick() & 0x7fffffff, -1)))
    r.cancel_timer()
    r.timer = asyncio.ensure_future(rooms.after(r, rooms.LOAD_TIMEOUT, rooms.LOADING))
    rooms.lists_changed(r.channel)
    refresh(c.id)


async def stage_result(c, g, room):
    """A later round's race is over: quarter-finals rank and pass at once; semi-finals and finals count points and
    race twice."""
    from .rooms import FINISHED
    order, out = [], []
    for m in room.members:
        p = m.player
        if not p or p.char.cid not in g.cids:
            continue
        end_type, _, record, rank = m.end or (0, 0, 0.0, 0)
        e = c.entrants[p.char.cid]
        if end_type == FINISHED and rank:
            order.append((rank, e, record))
            if record > 0 and (not e.record.get(g.stage) or record < e.record[g.stage]):
                e.record[g.stage] = record
        else:
            out.append(e)
    order.sort(key=lambda x: x[0])
    ranked = [e for _, e, _ in order] + out
    if g.stage in (SEMI, FINAL):
        last = g.race >= 2
        table = LAST_POINTS if last else ROUND_POINTS
        for i, e in enumerate(ranked):
            pts = e.points.setdefault(g.stage, [0, 0])
            finished = i < len(order)
            pts[g.race - 1] = (table[i] if i < len(table) else 0) + (FINISH_POINTS[last] if finished else 0)
        if not last:
            room.cast(Frame(0xd4a, struct.pack('<I', 1)))
            for e in ranked:
                e.rank[g.stage] = 0
            await asyncio.sleep(SECOND_RACE_DELAY)
            start_race(c, g)
            return
        everyone = [c.entrants[cid] for cid in g.cids if c.entrants[cid].state.get(g.stage) != OUT or
                    c.entrants[cid].points.get(g.stage)]
        everyone.sort(key=lambda e: (-e.total(g.stage), -e.points.get(g.stage, [0, 0])[1]))
        ranked = everyone
    takes = pass_count(c, g.stage, g)
    for i, e in enumerate(ranked):
        e.rank[g.stage] = i + 1
        if g.stage == FINAL:
            e.state[FINAL] = PASSED
        elif i < takes and e.state.get(g.stage) == PLAYING:
            e.state[g.stage] = PASSED
            e.state[{QF1: QF2, QF2: SEMI, SEMI: FINAL}[g.stage]] = STANDBY
        else:
            e.state[g.stage] = OUT
    g.done = True
    log(f'{CLASS_NAMES[c.id]} {STAGE_NAMES[g.stage]} {g.letter}: ' + ', '.join(
        f'{e.rank[g.stage]}. {e.name}' for e in ranked))
    if g.stage == FINAL:
        await prizes(c, ranked)
        c.finished = True
    close_room(room)
    refresh(c.id)


async def prizes(c, ranked):
    """The finals' ranks: [championship] reward.<class>.<rank> = Mito[, item id[, count]] by message."""
    from . import mail
    from .social import online
    db = context.db
    for i, e in enumerate(ranked):
        r = cfg()['rewards'].get((c.id, i + 1))
        text = f'GT Championship {CLASS_NAMES[c.id]}: rank {i + 1}'
        s = online(e.cid)
        if s:
            admin.message(s, f'{text} of {len(ranked)}.' + (' Your prize is in your messages.' if r else ''))
        if not r:
            continue
        mito, item, count = r
        item_text = f'{item} {count} 0 0 0 NONE NONE NONE 0' if item else ''
        row_ = await db.row(mail.INSERT, (db.server_id, e.cid, 0, 'GT Championship', 0, '', text, mito, item_text))
        log(f'prize: {e.name} rank {i + 1}: {mito} Mito' + (f', {count} x {item}' if item else ''))
        if row_ and s:
            got = await db.row(mail.SELECT + " AND MID=%s", (db.server_id, e.cid, int(row_[0])))
            if got:
                send(s, mail.row_frame(e.cid, got))


async def finish():
    t = tour()
    from . import rooms
    for c in t.classes.values():
        for groups in c.groups.values():
            for g in groups:
                if g.room and rooms.rooms.get(g.room.id) is g.room:
                    close_room(g.room)
    t.round = IDLE
    t.active = False
    t.round_end = time.time()
    log('the GT Championship is over')
    notice_all(BEGUN, IDLE, time.time())
    refresh()


async def end_round_now():
    """gmtour next: the current round ends now (its races are not waited for)."""
    t = tour()
    if t.round == IDLE:
        t.start = time.time()
        return
    if t.round == PRE:
        t.round_end = time.time() - 181
        await end_prelims()
        return
    for c in t.classes.values():
        for g in c.groups.get(t.round, []):
            if not g.done:
                for cid in g.cids:
                    if c.entrants[cid].state.get(t.round) in (STANDBY, PLAYING):
                        c.entrants[cid].state[t.round] = OUT
                g.done = True
                if g.room:
                    close_room(g.room)
    await next_round()


# ---- handlers ----------------------------------------------------------------------------------------------------

@on_open(SVC)
async def start_tour(session):
    tour()


def on_section(session, channel):
    """0x1b8 into a tournament lobby (rooms.register_observer): the class's state."""
    if channel in CLASSES:
        send(session, info_frame(session))


@on(SVC, C2S, 0xd4b)
async def my_info(session, frame):
    if session.state.get('player'):
        send(session, my_info_frame(session))


@on(SVC, C2S, 0xd4d)
async def race_info(session, frame):
    if session.state.get('player'):
        send(session, race_info_frame(session), info_frame(session))


@on(SVC, C2S, 0xd50)
async def tournament_list(session, frame):
    p = frame.payload
    if not session.state.get('player') or len(p) < 12:
        return
    cls, stage, page = struct.unpack_from('<III', p)
    send(session, list_frame(cls, stage, page))


@on(SVC, C2S, 0xd56)
async def tournament_search(session, frame):
    p = frame.payload
    if not session.state.get('player') or len(p) < 0x50:
        return
    _, cls, stage = struct.unpack_from('<III', p)
    name = read_wstr(p, 0xc, 64)
    page, = struct.unpack_from('<I', p, 0x4c)
    send(session, list_frame(cls, stage, page, name))


@on(SVC, C2S, 0xd54)
async def reward_list(session, frame):
    if session.state.get('player') and len(frame.payload) >= 4:
        send(session, reward_frame(struct.unpack_from('<I', frame.payload)[0]))


@on(SVC, C2S, 0xd52)
async def set_reward(session, frame):
    """GM reward setting: the client's own reward sets are not known to the server; answered as failed unless the
    sender is an admin (then only acknowledged: the prizes stay [championship] reward.*)."""
    p = frame.payload
    if len(p) < 8:
        return
    cls, rid = struct.unpack_from('<II', p)
    from .misc import is_admin
    ok = is_admin(session)
    send(session, Frame(0xd53, struct.pack('<IIB', cls, rid, int(bool(ok)))))


@on(SVC, C2S, 0xd4f)
async def set_map(session, frame):
    """GM map setting (GM_CMapset_*): the track for every stage of the coming rounds (our choice)."""
    p = frame.payload
    from .misc import is_admin
    if len(p) < 12 or not is_admin(session):
        return
    map_id, = struct.unpack_from('<H', p, 4)
    flag, = struct.unpack_from('<I', p, 8)
    t = tour()
    for stage in STAGE_NAMES:
        t.maps[stage] = (map_id, flag)
    admin.message(session, f'The GT Championship map has been set: track {map_id}, flags {flag:#x}.')


# ---- GM ----------------------------------------------------------------------------------------------------------

async def gm_command(session, args):
    """gmtour start [minutes to the preliminaries] | next | end | status | test on|off."""
    t = tour()
    w = [a.lower() for a in args]
    if not w or w[0] == 'status':
        if not t.active:
            nxt = next_start() if cfg()['schedule'] else 0
            return 'GT Championship: not running' + (
                f'; next {time.strftime("%a %H:%M", time.localtime(nxt))}' if nxt else '')
        out = [f'round {t.round} ({STAGE_NAMES.get(t.round, "before the start")})',
               f'ends {time.strftime("%H:%M:%S", time.localtime(t.round_end if t.round else t.start))}']
        for c in t.classes.values():
            state = 'cancelled' if c.cancelled else 'finished' if c.finished else f'{len(c.entrants)} entrants'
            out.append(f'{CLASS_NAMES[c.id]}: {state}')
        return '; '.join(out)
    if w[0] == 'start':
        wait = float(w[1]) if len(w) > 1 else 1.0
        if t.active:
            return 'the GT Championship is running: gmtour end first'
        schedule(time.time() + wait * 60)
        notice_all(TIME_LEFT, IDLE, t.start)
        return (f'GT Championship: preliminaries in {wait:g} min ({minutes("pre")} min, then rounds of '
                f'{minutes("wait")} + {minutes("main")} / {minutes("final")} min); min players {cfg()["min_players"]}')
    if w[0] == 'next':
        if not t.active:
            return 'the GT Championship is not running'
        await end_round_now()
        return f'now round {t.round} ({STAGE_NAMES.get(t.round, "over")})'
    if w[0] == 'end':
        if not t.active:
            return 'the GT Championship is not running'
        await finish()
        return 'GT Championship ended'
    if w[0] == 'test':
        on_ = len(w) < 2 or w[1] in ('on', '1')
        cfg()['min_players'] = 1 if on_ else cfg()['min_players_ini']
        return f'GT Championship test mode {"on (1 player is enough)" if on_ else "off"}'
    return 'usage: gmtour start [minutes] | next | end | status | test on|off'
