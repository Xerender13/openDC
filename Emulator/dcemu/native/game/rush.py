"""Rush time: the hourly HUV (boss) hunt in a city channel (batch 3 of the native game).

The 2008 server's RushTime / RushEvent (ZoneServer.pdb):
Schedule: rushtimetable.txt in server_data (RushTime::LoadRushTimeTable: "weekday hour HUV type" per
    line; Data_TW has every hour of every day). The next rush is the next table hour after the current
    one (local time, RushTime::NextRushTime); 0x45c RushNotice (u32 start time) goes to everyone at 10, 5,
    2 and 1 minutes before (user, 2026-10-15; the 2008 server: 9, 8, .. 1, recorded at :51 .. :59). At the start every rush with members starts
    (StartRushEvent: state 2, AssignControl).
Rush per city channel (RushTime::GetChannelEvent; here per city and channel): made with a random
    course 0-99 (InitRushEvent; recorded 16) and the HUV type of the coming rush (11004 recorded).
0x456 EnterRushZone -> 0x457 EnterRushZoneAck (u32 start time, u32 HUV type, u32 course); joining
    leaves the previous rush. 0x458 ExitRushZone -> 0x459; the others get 0x464 RushMemberCnt (u32).
0x45d AssignHuvControl (u16 serial, u16 car sort, u32 HUV type, u32 course, u32 end time; the 2008
    server left serial / sort / end unset) to the members at the start: the members' clients may
    spawn the HUV.
0x45e NotifyRushHuv (2011: u32 HUV index, u16 serial, u16 car sort, u32 HUV type, u32 course, f32
    health, i32 start time, u32 timeout ms, u32 member count, + 4 bytes the parent HUV, see
    Server/tools/patch_server_rush.py) from a member (RushEvent::AddHuv): the first sender becomes the
    controller, others are refused; the server numbers the HUV (index = HUVs so far, serial = the
    controller's, car sort from a 1-20000 pool), puts in the member count, and sends it to every
    member; the first HUV sets the end time (now + timeout). Recorded: index 0, (20, 1), 11004, 16,
    600.0, timeout 600000.
0x45a RushHitPoint (u32 HUV index, u16 serial, u16 car sort, f32 damage, i32 time) (RushEvent::HitHuv,
    Cmd_RushHitPoint): a living HUV loses health (not below 0) -> 0x45b RushStatus (u32 n, n x (u16
    serial, u16 car sort, u16 HUV type, u16 0, f32 health)) to the members, then an item drop for the
    hitter (drop mode 3: 0x2e5 + 0x192; recorded (1, 96, 3)): parts groups only (user: the boss gives parts),
    two rolls with the Item Drink (combo.drops). When no HUV is left alive the hitter wins.
0x462 CastRushEvent, 0x463 RushObjectUpdate: sent on to the members (2011 sizes, as patched).
End (RushEvent::EndRush: all HUVs down, or the end time): 0x460 RushResult (i64 reward, i64, the
    winner's team name 42 bytes @0x10, character name 26 bytes @0x3a) to the members; the winner gets
    (2011, client text 10893) 3 Unidentified Skill Books (random_skb) and 5 Enhancement Formula (i_n_00061) (2008:
    a Mittron Enhancer, i_n_00003, "RushWIn") and Mito by city (1: 30000, 2: 50000, 3: 80000, 4:
    100000; CalcMoney "RUSHTIME", 0x8a MoneyMessage kind 1); then the rush is emptied. 0x460 was
    never recorded in 2011 (the 2008 layout is sent).
GM commands (2008 names, also with "gm" in front): rushtimenow / rushtime [HUV type] [course] (a rush in 5 s /
    305 s, the notice at once), getrushtime, rushend.
Not done: switching the controller when it leaves or members complain (0x465, 0x461 SwitchRushHuv);
    here the rush ends when its controller leaves.

2011 additions (emulator.ini [rush]; schedule = the 2008 table above, which can be switched off):
Always-on rush (always = 1; sent as the content flags City.AlwaysRushTime and City.RushTimeStartMember): the
    client's rush zone dialog (0x58ac80) then shows text 11138 "If there are %d or more users in the Rush Time
    Zone, Rush Time will be started in 1 mins." while the start time it holds is ahead, and 11139 "After the
    current Rush Time ends, you can participate in another Rush Time." with start + 600 s - now once it passed
    (without the flag only within 10 minutes of the start). A zone (one per city and gate = channel) that is idle
    and has start_members members gets a start countdown seconds ahead (PENDING), sent to its members as
    0x467 RushUpdate; fewer members before the start cancel it. The timetable hours still start every zone
    with members.
0x467 RushUpdate (S>C, 34 bytes; client 0x52e950): u32 ? @0, u32 start time @4, u32 HUV type @8, u32 course
    @12, u32 member count @16 (rush +0x54, as 0x464 RushMemberCnt), u32 @20 ([ui + 0x32c] + 0x10c), 2 x u32.
0x464 RushMemberCnt now also on entering (the zone dialog shows the count).
Announcements: only the client's own, from 0x45c RushNotice (scheduled rushes only, < 1 hour ahead; handler
    0x52eed0: text 10024 / 10025 as a chat line and as the green notice at the top, [ui + 0x278] for 9 s). No
    server chat messages (user, 2026-10-15). (0x93 rooms the client knows, for reference: "server", "bcast" /
    "Ibcast" = big yellow notice, "ccmd", "cmdchat", "coolitem".)
"""
import asyncio
import os
import random
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import CLOCK_SHIFT, context
from .items import NEW, add_money, mod_list, play_bonus
from .login import SVC, send, sessions, stat_frames
from .records import wstr

IDLE, PENDING, RUNNING = 0, 1, 2
CITY_NAMES = {1: 'Moon Palace', 2: 'Koinonia', 3: 'Cras', 4: 'Oros', 5: 'Taipei', 6: 'Neo Oros'}
FAR = 7 * 86400              # an idle zone's start time in always mode: ahead (the dialog shows 11138)
NOTICE_MINUTES = (10, 5, 2, 1)    # 0x45c RushNotice before a scheduled rush (user: only these; 2008 sent 9..1)
CITY_MONEY = {1: 30000, 2: 50000, 3: 80000, 4: 100000}
WIN_ITEMS = (('random_skb', 3), ('i_n_00061', 5))   # the 2011 client's text 10893: "Received 3 Unidentified Skill
# Books, %d Mito, 5 Enhancement Formula." (the 2008 TW server gave a Mittron Enhancer, i_n_00003)
HUV_TYPES = (11001, 11003, 11004, 11007, 11008)
EMERGING = (11002, 11005, 11006)   # boss parts that come out during the rush: Lil' Grimer, Doom Dizer / Dazer
SORT_BASE = 1000             # rush HUV car sorts: 1001.. (2008: a 1-20000 pool shared with every vehicle)


class Rush:
    def __init__(self, key, huv_type):
        self.key, self.members = key, []
        self.course, self.huv_type = random.randrange(100), huv_type
        self.state, self.controller, self.huvs, self.end = IDLE, None, [], 0
        self.uid = 0
        self.run = 0             # rushes started here (coupon tries)
        self.start = 0           # PENDING: when it starts; RUNNING: when it started

    def name(self):
        city, channel = self.key
        return f'{CITY_NAMES.get(city, f"city {city}")} gate {channel + 1 if isinstance(channel, int) else channel}'

    def send_all(self, frame):
        for s in self.members:
            send(s, frame)


def client_time(t):
    """A time_t on the client's clock (the 2008 server's, UTC - 1 hour: native.CLOCK_SHIFT, as 0x311 gives it).
    Real times sent as they were made the client see every rush an hour later: no countdown window (it needs
    0 < start - now < 660 s), no "under N minutes" notices (< 1 hour)."""
    return int(t) + CLOCK_SHIFT if t else 0


def zone_key(session):
    return (session.state['player'].char.city, session.state.get('channel'))


class RushTime:
    def __init__(self):
        self.table = {}          # weekday (0 = Sunday) -> [(hour, HUV type)]
        path = os.path.join(context.data.server_data or '', 'rushtimetable.txt')
        if os.path.exists(path):
            for line in open(path, encoding='utf-8', errors='replace'):
                f = line.split()
                if len(f) == 3 and all(x.isdigit() for x in f):
                    self.table.setdefault(int(f[0]) % 7, []).append((int(f[1]), int(f[2])))
        self.rushes = {}         # (city, channel) -> Rush
        self.next, self.huv_type = self.next_rush(time.time())
        self.course = None       # a course set by rushtime / rushtimenow for the coming rush (else random)
        self.current = 0         # start of the scheduled rush now running (its 10 minutes), 0 = none
        self.last = time.time()

    def next_rush(self, now):
        """-> (start time, HUV type) of the first table hour after the current hour, or (0, 0)."""
        if not context.rush_schedule:
            return 0, 0
        day = time.localtime(now)
        for k in range(8):
            t = time.localtime(time.mktime((day.tm_year, day.tm_mon, day.tm_mday + k, 0, 0, 0, 0, 0, -1)))
            wday = (t.tm_wday + 1) % 7
            for hour, huv in sorted(self.table.get(wday, ())):
                start = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, 0, 0, 0, 0, -1))
                if start > now:
                    return int(start), huv
        return 0, 0

    def tick(self):
        now = time.time()
        if self.next:
            for i in NOTICE_MINUTES:
                if self.last < self.next - i * 60 <= now:
                    notice = Frame(0x45c, struct.pack('<I', client_time(self.next)))
                    for s in list(sessions.values()):
                        if s.state.get('player'):
                            send(s, notice)
            if self.last < self.next - 600 <= now:      # the scheduled period begins: zones show its start
                for r in self.rushes.values():
                    if r.members and r.state == IDLE:
                        r.huv_type = self.huv_type or r.huv_type
                        update(r)
            if self.last <= self.next < now:
                self.current = self.next
                started = [r for r in self.rushes.values() if r.members and r.state != RUNNING]
                for r in started:
                    r.huv_type = self.huv_type or r.huv_type    # the table's boss, also in a player-triggered zone
                    if self.course is not None:
                        r.course = self.course
                    start(r)
                self.next, self.huv_type = self.next_rush(now)
                self.course = None
                for r in self.rushes.values():
                    if r.state == IDLE:
                        r.huv_type = self.huv_type or r.huv_type
        if context.rush_always:
            for r in list(self.rushes.values()):
                if r.state == PENDING and r.start <= now and len(r.members) >= context.rush_start_members:
                    start(r)
                else:
                    self.check(r, now)
        if self.current and self.last < self.current + 600 <= now:   # the scheduled period is over
            self.current = 0
            for r in self.rushes.values():
                if r.members and r.state == IDLE:
                    update(r)
        for r in list(self.rushes.values()):
            if r.state == RUNNING and r.end and r.end <= now:
                asyncio.ensure_future(end_rush(r, None))
        self.last = now

    def scheduled(self, now=None):
        """The scheduled rush's period (10 minutes before its start to 10 minutes after: a rush lasts at most
        600 s) -> its start time, or 0. It overrides the player-triggered rushes (user, 2026-10-15)."""
        now = now or time.time()
        if self.current and now < self.current + 600:
            return self.current
        if self.next and self.next - now <= 600:
            return self.next
        return 0

    def check(self, r, now=None):
        """Always mode: an idle zone with start_members members gets its countdown, a waiting one with fewer
        is idle again; its members are told (0x457 redraws the zone window, 0x467 alone does not). Not during
        a scheduled rush's period: a waiting zone then goes back to idle and shows the scheduled start."""
        if not context.rush_always:
            return
        now = now or time.time()
        if r.state == PENDING and self.scheduled(now):
            r.state, r.start = IDLE, 0
            r.huv_type = self.huv_type or r.huv_type
            r.course = self.course if self.course is not None else r.course
            update(r)
            return
        if r.state == IDLE and self.scheduled(now):
            return
        if r.state == IDLE and len(r.members) >= context.rush_start_members:
            r.state, r.start = PENDING, int(now) + context.rush_countdown
            r.huv_type, r.course = random.choice(HUV_TYPES), random.randrange(100)   # a boss of its own each time
        elif r.state == PENDING and len(r.members) < context.rush_start_members:
            r.state, r.start = IDLE, 0
        else:
            return
        update(r)

    def start_time(self, r):
        """The start time a zone's members are told (0x457 / 0x467)."""
        if r.state in (PENDING, RUNNING):
            return r.start
        if self.scheduled():
            return self.scheduled()
        if context.rush_always:
            return int(time.time()) + FAR
        return self.next

    def rush_of(self, session):
        return next((r for r in self.rushes.values() if session in r.members), None)


_rt = None


def rush_time():
    global _rt
    if _rt is None:
        _rt = RushTime()
        asyncio.ensure_future(_ticker())
    return _rt


async def _ticker():
    while True:
        await asyncio.sleep(1)
        try:
            _rt.tick()
        except Exception as e:          # keep the schedule going
            print('rush tick:', e)
        try:
            from .rooms import real_match_tick
            real_match_tick()           # Real Match opening notices (0x1c8)
        except Exception as e:
            print('real match tick:', e)


async def count_try(session, r):
    """Coupon book: FondoX counts rush time tries (RUSHTRY), once per player and rush."""
    from .coupons import RUSH_TRY, add_param
    key = (id(r), r.run)
    if session.state.get('rush_counted') != key:
        session.state['rush_counted'] = key
        await add_param(session, RUSH_TRY)


def update(r):
    """The zone's members get its start time again: 0x457 (the zone window redraws: countdown and boss within
    660 s of the start, client 0x58ac80) and 0x467 RushUpdate (start time, HUV type, course, member count)."""
    start_at = client_time(rush_time().start_time(r))
    r.send_all(Frame(0x457, struct.pack('<III', start_at, r.huv_type, r.course)))
    r.send_all(Frame(0x467, struct.pack('<8I', 0, start_at, r.huv_type, r.course, len(r.members), 0, 0, 0)))


def start(r):
    r.state, r.controller, r.huvs, r.end = RUNNING, None, [], 0
    r.frames = {}                               # HUV index -> its 0x45e as sent
    r.start = int(time.time())
    r.run += 1
    for s in list(r.members):
        asyncio.ensure_future(count_try(s, r))
    r.send_all(Frame(0x45d, struct.pack('<HHIII', 0, 0, r.huv_type, r.course, 0)))


def leave(session):
    rt = rush_time()
    r = rt.rush_of(session)
    if not r:
        return
    r.members.remove(session)
    if r.state == RUNNING and (not r.members or r.controller is session):
        asyncio.ensure_future(end_rush(r, None))
    else:
        r.send_all(Frame(0x464, struct.pack('<I', len(r.members))))
        rt.check(r)


@on_open(SVC)
async def rush_member(session):
    rush_time()
    try:
        await asyncio.Event().wait()
    finally:
        if _rt and _rt.rush_of(session):
            leave(session)


@on(SVC, C2S, 0x456)
async def enter_rush_zone(session, frame):
    p = session.state.get('player')
    if not p:
        return
    rt = rush_time()
    leave(session)
    key = zone_key(session)
    r = rt.rushes.get(key)
    if r is None:
        r = rt.rushes[key] = Rush(key, rt.huv_type or random.choice(HUV_TYPES))
        if rt.course is not None:
            r.course = rt.course
    r.members.append(session)
    session.log.note(f'enter rush zone {key}: {len(r.members)} members')
    before = r.state
    rt.check(r)
    if r.state == RUNNING:
        await count_try(session, r)
    if r.state == before:                       # (check sent 0x457 / 0x467 to everyone when it changed)
        send(session, Frame(0x457, struct.pack('<III', client_time(rt.start_time(r)), r.huv_type, r.course)))
    r.send_all(Frame(0x464, struct.pack('<I', len(r.members))))


def schedule_notice():
    """0x45c for the scheduled rush a player should see: the one running (its start, in the past: the client
    keeps its rush HUD without the notice texts); None when there is none."""
    rt, now = rush_time(), time.time()
    if rt.current and now < rt.current + 600:   # (a coming one would repeat the "under N minutes" texts)
        return Frame(0x45c, struct.pack('<I', client_time(rt.current)))
    return None


@on(SVC, C2S, 0x458)
async def exit_rush_zone(session, frame):
    """-> 0x459 (Cmd_ExitRushZone), then 0x45c again: the client's 0x459 handler (0x52f180) clears its rush state
    and HUD, so outside the zone the scheduled rush's information was gone (user, 2026-10-15)."""
    leave(session)
    send(session, Frame(0x459, b''))
    notice = schedule_notice()
    if notice:
        send(session, notice)


@on(SVC, C2S, 0x45e)
async def notify_rush_huv(session, frame):
    r = rush_time().rush_of(session)
    if not r or r.state != RUNNING or len(frame.payload) < 32:
        return
    if r.controller and r.controller is not session:
        # Every client runs the boss's own sequence and reports the boss part it brings out (Lil' Grimer, the
        # baby dozers); only the controller's is kept. The others get that part's 0x45e as the answer to their
        # report: the splash screen is shown on that path (user, 2026-10-15: only the controller saw it).
        huv_type, = struct.unpack_from('<I', frame.payload, 8)
        if huv_type in EMERGING:
            sent = session.state.setdefault('rush_answered', set())
            for k, h in enumerate(r.huvs):
                if h[2] == huv_type and (id(r), r.run, k) not in sent and k in r.frames:
                    sent.add((id(r), r.run, k))
                    session.log.note(f'rush HUV {huv_type}: answered with ({h[0]}, {h[1]})')
                    return send(session, Frame(0x45e, r.frames[k]))
        return
    r.controller = session
    m = bytearray(frame.payload)
    huv_type, = struct.unpack_from('<I', m, 8)
    health, = struct.unpack_from('<f', m, 16)
    timeout, = struct.unpack_from('<I', m, 24)
    r.uid = r.uid % (20000 - SORT_BASE) + 1     # a car sort no player car has (theirs are all 1);
    sort = SORT_BASE + r.uid                    # sort 1 made the boss the controller's own car (stuck, no hits)
    serial = session.state.get('serial', 0)
    struct.pack_into('<IHH', m, 0, len(r.huvs), serial, sort)
    struct.pack_into('<I', m, 28, len(r.members))
    if not r.huvs:
        r.end = time.time() + timeout / 1000
    r.huvs.append([serial, sort, huv_type, health, health])     # + the full health (test_health scaling)
    session.log.note(f'rush HUV {huv_type} ({serial}, {sort}) health {health}')
    r.frames[len(r.huvs) - 1] = bytes(m)
    r.send_all(Frame(0x45e, bytes(m)))


@on(SVC, C2S, 0x45a)
async def rush_hit_point(session, frame):
    from .combo import drops
    p = session.state.get('player')
    r = rush_time().rush_of(session)
    if not p or not r or r.state != RUNNING or len(frame.payload) < 12:
        return
    idx, serial, sort, damage = struct.unpack_from('<IHHf', frame.payload)
    if idx >= len(r.huvs) or r.huvs[idx][0] != serial or r.huvs[idx][3] <= 0:
        return
    h = r.huvs[idx]
    if context.rush_test_health:                # [rush] test_health (testing): every HUV dies in that many hits. The
        damage *= h[4] / context.rush_test_health   # health stays the client's: Lil' Grimer / the baby dozers come out
    h[3] = max(0.0, h[3] - damage)              # when the damage (max - health) passes 40% of the table's (480 / 1200)
    r.send_all(Frame(0x45b, struct.pack('<I', len(r.huvs))
                     + b''.join(struct.pack('<HHHHf', s, c, t & 0xffff, 0, hp) for s, c, t, hp, _ in r.huvs)))
    changes = await drops(session, p, 3, parts_only=True)   # parts only; two rolls with the Item Drink
    if changes:
        send(session, mod_list(*changes))
    if all(h[3] <= 0 for h in r.huvs):
        await end_rush(r, session)


@on(SVC, C2S, 0x462)
async def cast_rush_event(session, frame):
    r = rush_time().rush_of(session)
    if r:
        r.send_all(Frame(0x462, frame.payload))


@on(SVC, C2S, 0x463)
async def rush_object_update(session, frame):
    r = rush_time().rush_of(session)
    if r:
        r.send_all(Frame(0x463, frame.payload))


async def end_rush(r, winner):
    if r.state != RUNNING:
        return
    r.state, r.huvs, r.end, r.start = IDLE, [], 0, 0
    money, name = 0, ''
    p = winner.state.get('player') if winner else None
    if p and r.members:
        c, t = p.char, context.data
        name = c.name
        money = play_bonus(p, money=CITY_MONEY.get(c.city, 0))[1]
        from .combo import take
        changes = []
        for item_id, count in WIN_ITEMS:
            info = t.item_info(t.item_index.get(item_id, -1))
            for _ in range(count if info else 0):
                changes.append(await take(p, info))
        merged = {}                             # one entry per item: NEW when it was made here, else CHANGED
        for it, state in changes:
            merged[id(it)] = (it, merged[id(it)][1] if id(it) in merged and merged[id(it)][1] == NEW else state)
        if merged:
            send(winner, mod_list(*merged.values()))
        if money and await add_money(c, money):
            send(winner, Frame(0x8a, struct.pack('<iiqq', 1, 1, money, c.mito) + b'\0\0'))
            for f in stat_frames(p):
                send(winner, f)
        winner.log.note(f'rush won: {money} mito, {WIN_ITEMS}')
    r.send_all(Frame(0x460, struct.pack('<qq', money, 0) + bytes(42) + wstr(name, 26)))
    if p:                                       # licenses: GC_RushtimeClear for every member, GC_LuckyDriver the winner
        from .licenses import count
        for s in list(r.members):
            await count(s, 'RushtimeClear')
        await count(winner, 'LuckyDriver')
    r.members.clear()


# --- GM commands (the 2008 server's, ProcessGameStream 0x613dc7..: typed in the chat by an admin) -----------------
def set_start(seconds, huv_type=-1, course=-1):
    """2008 RushTime::SetStartRushTime + RushNotice: the next rush starts in seconds (rushtimenow: 5, rushtime: 305),
    with this HUV type / course (-1: the table's type, a random course); the notice goes to everyone at once."""
    rt = rush_time()
    rt.next = int(time.time()) + seconds
    if huv_type > 0:
        rt.huv_type = huv_type
    rt.huv_type = rt.huv_type or random.choice(HUV_TYPES)
    rt.course = course if 0 <= course < 100 else None
    for r in rt.rushes.values():
        if r.state == IDLE:
            r.huv_type = rt.huv_type
            if rt.course is not None:
                r.course = rt.course
    notice = Frame(0x45c, struct.pack('<I', client_time(rt.next)))
    for s in list(sessions.values()):
        if s.state.get('player'):
            send(s, notice)
    return f'rush at {time.strftime("%H:%M:%S", time.localtime(rt.next))}, HUV {rt.huv_type}, course ' \
           f'{rt.course if rt.course is not None else "random"}'


async def gm_command(cmd, args):
    """rushtimenow [HUV type] [course], rushtime [HUV type] [course], getrushtime, rushend -> the reply text."""
    nums = [int(a) for a in args[:2] if a.lstrip('-').isdigit()] + [-1, -1]
    if cmd == 'rushtimenow':
        return set_start(5, nums[0], nums[1])
    if cmd == 'rushtime':
        return set_start(305, nums[0], nums[1])
    rt = rush_time()
    if cmd == 'getrushtime':
        running = sum(1 for r in rt.rushes.values() if r.state == RUNNING)
        return (f'next rush {time.strftime("%a %H:%M:%S", time.localtime(rt.next)) if rt.next else "none"}, '
                f'HUV {rt.huv_type}; {running} running')
    if cmd == 'rushend':
        running = [r for r in rt.rushes.values() if r.state == RUNNING]
        for r in running:
            await end_rush(r, None)
        return f'{len(running)} rushes ended'
    return None


RUSH_COMMANDS = ('rushtimenow', 'rushtime', 'getrushtime', 'rushend')
