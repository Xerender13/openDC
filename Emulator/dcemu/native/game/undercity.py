"""The Undercity (a party rescue mission below a city, four missions in about 30 minutes): the 2008 server's rules
(ZoneServer.pdb: PacketParser::Cmd_UnderCity* / Cmd_UCPatrol* / Cmd_UCBossPatrol* / Cmd_Huv*, BS_Party::OnTick 0x5dded0,
UnderChaseEnd 0x5dd3f0, Pre/PostUnderCityResult 0x5db440 / 0x5dce10), which the 2011 client still speaks: every
message has the 2008 size except 0x100 (2011: 386 bytes) and 0xbcc (2011 field order). The JP wiki
(ゲームモード/アンダーシティ) agrees with these rules. Client addresses are of the EU exe (../DriftCityEU-decomp).
Offsets below are from the 2-byte type.

Entering (content flags City.UnderCity + City.<city>UC, on in server_data/tables/Contents.ini): Tatiana's dialog
(client 0x6b4xxx) refuses a party of fewer than 2 by itself (UC_Err_PlayTogether); the chat command /uc + the city's
letter (/ucm Moon Palace, /uck Koinonia, /ucc Cras, /uco Oros; client 0x5e43e0, allowed for every account) sends the
same request without that check (the test mode's way in, see below).
0xfc UnderCitySuggest (u32 serial @2, i32 time @6, i32 city @0xa, wchar[21] name @0xe; 56):
    alone (2008: a party of one is made) -> AgreeMode 2 and 0xff at once, no fee (here only in the test mode; else
    script message UC_Err_PlayTogether). A party: every member in the same city and channel (else UC_Err_SameCity),
    AgreeMode 1, 14.5 s to answer, the 0xfc with the suggester's name to every member (client 0x5318a0: the others
    get the "join?" box).
0xfd UnderCityAgree (u32 serial, i32 time) -> the same to all (0x5317c0); a member short of the fee (city 1 600,
    2 1200, 3 2100, 4 4200 Mito) -> UC_Err_NeedMito and 0xfe (0, 0); everyone agreed -> the fee taken from each and
    0xff UnderCityLoad (i32 time @2, i32 city @6, i32 fee @0xa, i64 Mito @0xe; 22) to each: the client (0x765950)
    keeps its city position and loads the Undercity, area 100 + city - 1 (Moon Palace 100 .. Oros 103).
0xfe UnderCityReject (serial, time) -> the same to all while AgreeMode is 1; also (0, 0) when the 14.5 s pass.
0x101 ExitUnderCity: alone -> the run is dropped (the solo party with it); in a party the player leaves the party.
Areas 100-103 (area.py): one instance per party (uc_area_key), no city traffic.
Stages (0xfa UnderCityStage: i32 start type @2, i32 stage @6, i32 time @0xa; 14; BS_Party::UpdateUCStage 0x5daab0):
    start type 1: the member's stage; once every member is at it or past it, 0xfb StageAck (i32 stage, i32 time) to
    all. Start type 2: sets it for everyone (0xfb at once). Other start types (3: the client on entering) nothing.
    Stage 0 resets the run, 1 starts it (UnderCity::Init), 7 sets the Mission 2 timer. The client (0x7677b0):
    (1, 1) when loaded -> 0xfb 1 -> UC_Ready, the start animation; the leader's [Accept] (UC_HUB_NeedAccept) sends
    (2, 4) -> 0xfb 4 -> the countdown, then Mission 1.
Mission 1, HUB destruction (UCPatrol; 100 HUBs, red ones by jump ramps):
    0xbb8 UCPatrolStart (u32 patrol = city, u32 start slot) -> 0xbb9 (u32 patrol, u32 slot, f32 x, y, z, angle; the
    city's Undercity_Start icons post_1st_00785.. ; the 2011 client reads only @2) to all.
    0xbbc UCPatrolGoalPlace (u32 patrol, u32 place 0-99, u32 jump) per HUB: the member's HUB count (UCPoint1) and,
    jumped, red HUBs (UCPoint2) -> 0xbbd (u32 patrol, place, exp 0, inven 0, serial, delta 0, i64 Mito) to all. With
    the 100th: 0xbbe UCPatrolResult (u32 patrol, result 1, u32 exp, inven 0, i32 Mito, i64 Mito) to each member: exp
    = A x his HUBs, Mito = B x HUBs + C x red HUBs (the 2008 code, city 1: 2, 2, 5; 2: 4, 8, 12; 3: 7, 15, 20; 4: 11,
    23, 29; Server2008/tools/patch_server_undercity.py). A red HUB jumped also sends 0xc4 HuvTimeBonus (10000 ms):
    the boss time grows by it, 0xc4 (i32 bonus, i32 total) to all (text "time bonus").
    0xbba UCPatrolGiveUp (u32 patrol) -> 0xbbb (patrol) to all.
Mission 2, barrier HUBs and the main HUB (UCBossPatrol; 3 tries):
    0xbc2 UCBossPatrolStart -> 0xbc3 (i32 time limit ms, i32 barrier HUBs) to all (client 0x7681c0 places them, then
    sends (1, 7): 0xfb 7 sets the server's timer to 12.6 s + the limit). Try t (1-3): limit 120 + 10 (t - 1) s (+ 20 in
    Moon Palace; the wiki's 2:20 / 2:30 / 2:40); HUBs (members - 1) x (6 - t) (2 players 5 / 4 / 3, 4 players 15 / 12
    / 9; alone the 2008 fallback 15 - 3 (t - 1), the test mode as 2 players). When the timer runs out: the next try,
    0xbc9 UCBossPatrolReset (the client asks again); after the third the run fails (result -1).
    0xbc6 UCBossPatrolGoalPlace (i32 time, u32 table, u32 place; place 0 = the main HUB) -> 0xbc7 (time, table, place,
    exp, inven, serial, delta, i64 Mito) to all; the main HUB: the time left kept (the rating), 0xbc8
    UCBossPatrolResult (result 1, u32 exp, inven, i32 Mito 0, i64 Mito) to each with exp 77 / 154 / 231 / 308 by city
    and an S Mittron Enhancer (i_n_00044; 2008 without Main.NewUpgrade: Liquid Mittron 5ml).
    0xbc4 UCBossPatrolGiveUp (u32) -> the run state is cleared (2008), 0xbc5 (the same u32) to all.
Mission 3 and 4, HUV waves and the BossHUV (the client's wave list; BS_Party::OnTick):
    0xc2 HuvParam (4 x f32: the client's position) is kept for 0xbf; 0xbe HuvReq (i32 time @2, u32 n @6, n x XiHuvInfo
    @0xa: u16 stage, HUV id, level, type, serial, car sort, hp; 14 each) holds every HUV of the run, stage 1-4 the
    waves, 5 the boss (client 0x767530). The server releases the HUVs whose stage the chase has reached: stage 1 at
    once, then 240 s, 240 s, 300 s, 360 s each (sooner when every HUV out is caught: the time left adds up for the
    rating), the boss with 900 s + the time bonus. A release: 0xc3 HuvTimeout (i32 ms left, i32 penalty; client
    0x512450: the wave texts) and 0xbf HuvRes (i32 time, 4 x f32, u32 n, n x XiHuvInfo with serial = the member whose
    client drives it, car sort = its id) to all (0x512630: every client spawns them). HUVs not caught when the next
    wave comes count against the rating (UC1..UC4LeftHuv).
    0xc0 HuvHit (u16 hitter, u16 HUV id, u16 serial, u16 car sort @8, u16, i32 hp @0xc, i32 damage, i16 critical, i16
    drift, i32 Mito, i64 Mito, i32 exp; 40) from the hitter: the HUV's hp is set; to every member the same with his
    exp / Mito: a HUV caught gives its HuvTable exp and Mito x 2 to the hitter (UCPoint3 + 1); boss damage gives each
    member exp = damage / k x (a ln(level) + b) (city 1: 6000, 100, 33; 2: 6000, 110, 60; 3: 16666, 120, 166; 4: 13333,
    200, 266), the hitter 75 % of it (his damage: UCPoint4), the others 25 / 14.3 / 10 % with 2 / 3 / 4 members. Two
    boss HUVs (Double Upset) share their hp. The last escort wave cleared: 0xbcc UnderCityReward (2011: u32 flag @2
    (1: text 11114 "Undercity 120% item has been applied."), u32 exp @6, i32 Mito @0xa, i64 Mito @0xe; client
    0x518310) with HUVs caught x (9, 3) / (12, 4) / (16, 7) / (22, 11) exp / Mito by city. The boss out (and every HUV)
    = success. While the boss is out: every 60 s with more than one HUV out each escort gives it 10 % of its hp,
    every 30 s it heals 2 %, twin bosses 5 % after 60 s without a hit: 0xc5 HuvHealth (u16 0, u16 serial, u16 sort,
    u16 kind (0 lost, 1 absorbed, 2 healed), i32 hp, i32 delta). Out of time (or no HUV left to come) = failure.
Result (UnderChaseEnd): 0xc1 HuvResult (i32 result, u32 item InvenIdx) to each, then 0x100 UnderCityResult (2011:
    i32 result (1 cleared, 0 failed, -1 Mission 2 failed) @2, i32 class 1-5 @6 (the client shows 1-4: S as A, the
    wiki's "S shows as A"), i32 Mission 2 retries @0xa, i32 ms @0xe, 4 x 0x5c units @0x12: i32 party index (-1
    none), f32 rank, i32 level, wchar[21] name, i32 exp @0x36, i32 Mito @0x3a, i32 HUBs, red HUBs, HUVs, boss % @0x3e,
    3 x i32 item TableIdx (-1 none) @0x4e, u8 @0x5a, u8 @0x5b (2011: two icons per row, 0x6b1ee0; sent 0)) to all.
    Class: the mean of six marks (HUBs evenly shared, red HUBs, Mission 2 tries and time left, HUVs left over and time
    saved, boss time left, closeness of the run to 2150 s): 92+ S, 82+ A, 72+ B, 62+ C, else D. Rank point = 0.55 boss
    % + 0.35 HUVs / 28 + 0.05 red / 10 + 0.05 HUBs / 100. Items: cleared -> a Mittron Ore of the city (gi_<c>_001, the
    beta 002 at 10-20 %) to each and an enhancer by party size, rank place and class (s_UCNewItemTable: H i_n_00045 /
    S i_n_00044); failed -> the ore alpha to all but the last place by a level chance; Mission 2 failed -> an N Mittron
    Enhancer (i_n_00043).
Exp and Mito go through items.play_bonus (drinks, Mita 500, license ME_UnderExpMito); a held Undercity 120% (i_n_00064,
    "Increases Mito and Exp. earned from Undercity by 20%") adds its 20 % and one is used up at the result *(guess:
    the 2008 server has no such item; when the 2011 one was used up is not known)*.

Test mode (emulator.ini [undercity] test = 1, or per character the GM chat command  gmuctest on | off): one player can
enter alone with /ucm (/uck, /ucc, /uco), free (the 2008 solo party), and Mission 2 has a 2-player party's barrier
HUBs (5 / 4 / 3). Not done: a member leaving in the middle (his HUVs end; 2008 handed them to another member,
DelegateHuvControl), Undercity Direct (vc_UC_Direct, Korea only).
"""
import asyncio
import math
import random
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, send, sessions

FEES = {1: 600, 2: 1200, 3: 2100, 4: 4200}
AREAS = {1: 100, 2: 101, 3: 102, 4: 103}            # client 0x765950
CITY_LETTERS = {1: 'm', 2: 'k', 3: 'c', 4: 'o'}
START_ICONS = {1: ('post_1st_', 785), 2: ('post_2nd_', 793), 3: ('post_3rd_', 792), 4: ('post_4rd_', 627)}
AGREE_SECONDS = 14.5                                  # 0x38a4 ms
HUBS = 100                                            # XiUnderCityPatrolTable MaxPost
PATROL_REWARD = {1: (2, 2, 5), 2: (4, 8, 12), 3: (7, 15, 20), 4: (11, 23, 29)}     # exp / HUB, Mito / HUB, Mito / red
MAIN_HUB_EXP = {1: 77, 2: 154, 3: 231, 4: 308}
MIDDLE_REWARD = {1: (9, 3), 2: (12, 4), 3: (16, 7), 4: (22, 11)}                   # per HUV caught: exp, Mito
BOSS_EXP = {1: (6000, 100, 33), 2: (6000, 110, 60), 3: (16666, 120, 166), 4: (13333, 200, 266)}
BOSS_SHARE = {2: 0.25, 3: 0.14286, 4: 0.1}
WAVE_SECONDS = {1: 240, 2: 240, 3: 300, 4: 360}        # after releasing chase stage n, the next comes this much later
BOSS_SECONDS = 900
ESCORT_LAST, BOSS = 4, 5                               # XiHuvInfo stages
ORE_LEVEL = {1: 30, 2: 35, 3: 40, 4: 45}               # TakeUnderCityFailItem
S_ENHANCER, H_ENHANCER, N_ENHANCER = 'i_n_00044', 'i_n_00045', 'i_n_00043'
UC_120 = 'i_n_00064'
# s_UCNewItemTable[party size % 4][place][(5 - class) % 5] (2008 ZoneServer 0x6ff068; Main.NewUpgrade on)
H, S = H_ENHANCER, S_ENHANCER
RANK_ITEMS = (
    ((H, H, S, S, None), (H, H, S, S, None), (H, S, S, None, None), (H, S, S, None, None)),      # 4 players
    ((H, H, S, S, None), (H, H, S, S, None), (H, S, S, None, None), (None,) * 5),                # 1
    ((H, H, S, S, None), (H, H, S, S, None), (None,) * 5, (None,) * 5),                         # 2
    ((H, H, S, S, S), (None,) * 5, (None,) * 5, (None,) * 5))                                    # 3
SORT_BASE = 30000                                      # HUV car sorts 30001.. (rush.py uses 1001-20000)
UNIT = 0x5c
TICK = 0.5

runs = {}                   # party id -> Run
_sorts = iter(range(1, 1 << 30))


def ms():
    return int(time.monotonic() * 1000)


def test_mode(session):
    return context.undercity['test'] or session.state.get('uc_test', False)


def serial(s):
    return s.state.get('serial', 0)


def script(session, key):
    """0x09 ScriptMessage (i32 type 0, wchar[64] script id): a Tatiana dialog of the client's GlobalText."""
    send(session, Frame(0x09, struct.pack('<i', 0) + key.encode('utf-16-le')[:126].ljust(128, b'\0')))


class Member:
    def __init__(self, session):
        self.session = session
        self.stage = 0
        self.agree = False
        self.hubs = self.jumps = self.huvs = 0
        self.boss = 0.0                                # boss damage, then its share in %
        self.exp = self.mito = 0
        self.items = [-1, -1, -1]
        self.huv_sorts = []
        self.uc120 = False


class Actor:
    """A HUV out in the chase (BS_Actor): driven by its owner's client."""
    def __init__(self, owner, info, sort, attr):
        self.owner = owner
        self.info = info                               # the XiHuvInfo as the client sent it (stage, id, level, type, ..)
        self.stage = info[0]
        self.sort = sort
        self.hp = self.max_hp = info[6]
        self.exp, self.money = (attr['exp'], attr['money']) if attr else (0, 0)
        self.hit_at = 0


class Run:
    def __init__(self, party, city, solo):
        self.party, self.city, self.solo = party, city, solo
        self.members = {id(s): Member(s) for s in party.members}
        for s in party.members:
            s.state['uc_run'] = self
        self.agree_mode = 0
        self.agree_timeout = 0
        self.uc_stage = 0
        self.init()
        self.task = asyncio.ensure_future(self.tick())

    def init(self):
        """BS_Party::UnderCity::Init."""
        self.chase_stage = -1
        self.chase_base = 0
        self.boss_bonus = 0
        self.penalty = 0
        self.penalty_check = self.revive_check = 0
        self.chase_pos = (0.0,) * 4
        self.chase_start = 0
        self.boss_try = -1
        self.retry = 0
        self.bosses = []
        self.uc2_record = 0
        self.left_huv = [0, 0, 0, 0]
        self.start = ms()
        self.acc_left = 0
        self.patrol = None                             # {place: ms} of Mission 1
        self.stack = []                                # HUVs still to come (XiHuvInfo tuples)
        self.actors = {}                               # car sort -> Actor
        self.over = False

    @property
    def sessions(self):
        return [m.session for m in self.members.values() if m.session.id in sessions]

    def member(self, session):
        return self.members.get(id(session))

    def cast(self, *frames):
        for s in self.sessions:
            send(s, *frames)

    def note(self, text):
        for s in self.sessions[:1]:
            s.log.note(f'undercity: {text}')

    async def tick(self):
        try:
            while not self.over:
                await asyncio.sleep(TICK)
                await self.on_tick()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.note(f'tick failed: {e!r}')

    async def on_tick(self):
        """BS_Party::OnTick."""
        now = ms()
        if self.agree_mode == 1 and now >= self.agree_timeout:
            self.agree_mode = 0
            self.cast(Frame(0xfe, struct.pack('<Ii', 0, 0)))
            return drop_run(self)
        if self.boss_try >= 0:
            if now >= self.chase_base + self.penalty:
                self.boss_try += 1
                self.retry += 1
                self.chase_base = now + (self.boss_try * 10 + 110) * 1000
                if self.boss_try > 3:
                    return await self.end(-1)
                self.note(f'Mission 2 out of time: try {self.boss_try}')
                self.cast(Frame(0xbc9, b''))
            return
        if self.chase_stage < 0:
            return
        if not self.actors:
            left = self.chase_base + self.penalty - now
            if left > 0:
                self.acc_left += left
            self.chase_base = now
        released = []
        if now >= self.chase_base + self.penalty:
            if not self.stack:
                return await self.end(0)
            if self.actors and 2 <= self.chase_stage <= 5:
                self.left_huv[self.chase_stage - 2] = len(self.actors)
            released = [h for h in self.stack if h[0] <= self.chase_stage]
            self.stack = [h for h in self.stack if h[0] > self.chase_stage]
            if not released:
                self.chase_stage = -1
                self.stack = []
                return
            st = self.chase_stage
            if st in WAVE_SECONDS:
                self.chase_base = now + WAVE_SECONDS[st] * 1000
            elif st == BOSS:
                await self.middle_reward()
                self.chase_base = now + BOSS_SECONDS * 1000 + self.boss_bonus
                self.penalty_check, self.revive_check = now + 60000, now + 30000
            elif self.actors:
                return await self.end(0)
            self.chase_stage = st + 1
        if released:
            self.release(released, now)
        if self.chase_stage == BOSS + 1:
            self.boss_heal(now)

    def release(self, huvs, now):
        """0xc3 + 0xbf: these HUVs come out, one member's client driving each (in turn)."""
        owners = self.sessions
        if not owners:
            return
        self.cast(Frame(0xc3, struct.pack('<ii', self.chase_base + self.penalty - now, self.penalty)))
        out = b''
        for i, h in enumerate(huvs):
            owner = owners[i % len(owners)]
            sort = SORT_BASE + next(_sorts) % 30000
            a = Actor(owner, h, sort, huv_attr(h))
            self.actors[sort] = a
            self.member(owner).huv_sorts.append(sort)
            if a.stage == BOSS:
                a.hit_at = now
                self.bosses.append(a)
            out += struct.pack('<7H', h[0], h[1], h[2], h[3], serial(owner), sort, h[6])
        self.cast(Frame(0xbf, struct.pack('<i4fI', self.chase_start, *self.chase_pos, len(huvs)) + out))
        self.note(f'chase stage {self.chase_stage - 1}: {len(huvs)} HUVs out ({len(self.actors)} in all), '
                  f'next in {(self.chase_base - now) // 1000} s')

    def boss_heal(self, now):
        def health(a, delta, kind):
            self.cast(Frame(0xc5, struct.pack('<4Hii', 0, serial(a.owner), a.sort, kind, a.hp, delta)))
        bosses = [b for b in self.bosses if b.sort in self.actors]
        if len(bosses) > 1 and any(b.hit_at + 60000 <= now for b in bosses[:2]):
            for b in bosses[:2]:
                b.hit_at = now
            for b in bosses:
                d = b.max_hp // 20
                if b.hp + d <= b.max_hp:
                    b.hp += d
                    health(b, d, 2)
        if now >= self.penalty_check:
            if len(self.actors) > 1:
                alive = [a for a in self.actors.values() if a.hp]
                boss = [a for a in alive if a.stage == BOSS]
                escorts = [a for a in alive if a.stage != BOSS]
                if boss and boss[0].hp < boss[0].max_hp:
                    for e in escorts:
                        d = min(e.max_hp // 10, e.hp)
                        e.hp -= d
                        health(e, -d, 0)
                    gain = min(len(escorts) * boss[0].max_hp // 100, boss[0].max_hp - boss[0].hp)
                    for b in boss:
                        b.hp += gain
                        health(b, gain, 1)
                    for a in [a for a in self.actors.values() if a.hp == 0]:
                        self.end_huv(a)
            self.penalty_check = now + 60000
        if now >= self.revive_check:
            for b in bosses:
                d = b.max_hp // 50
                if b.hp + d <= b.max_hp:
                    b.hp += d
                    health(b, d, 2)
            self.revive_check = now + 30000

    def end_huv(self, a):
        self.actors.pop(a.sort, None)
        m = self.member(a.owner)
        if m and a.sort in m.huv_sorts:
            m.huv_sorts.remove(a.sort)

    async def gain(self, m, exp, mito, activity=True):
        """Exp / Mito for a member (play bonuses, Undercity 120 %) -> (exp, mito) given."""
        from .items import add_money, play_bonus
        from .progress import add_exp
        s = m.session
        p = s.state.get('player')
        if not p:
            return 0, 0
        exp, mito = play_bonus(p, exp, mito, 'undercity') if activity else (exp, mito)
        rate = uc120_rate(p)
        if rate and (exp or mito):
            exp, mito = exp * (100 + rate) // 100, mito * (100 + rate) // 100
            m.uc120 = True
        if exp > 0:
            await add_exp(p.char, exp)
            m.exp += exp
            send(s, exp_info(p.char))
        if mito > 0:
            await add_money(p.char, mito)
            m.mito += mito
        return max(exp, 0), max(mito, 0)

    async def middle_reward(self):
        """BS_Party::UnderChaseMiddleReward: the escort waves are over."""
        per_exp, per_mito = MIDDLE_REWARD.get(self.city, MIDDLE_REWARD[1])
        for m in self.members.values():
            if m.huvs > 0 and m.session.id in sessions:
                exp, mito = await self.gain(m, m.huvs * per_exp, m.huvs * per_mito)
                p = m.session.state['player']
                send(m.session, Frame(0xbcc, struct.pack('<IIiq', 1 if m.uc120 else 0, exp, mito, p.char.mito)))
        self.note('escort waves over: middle reward')

    async def end(self, result):
        """BS_Party::UnderChaseEnd: 0xc1 to each, then 0x100 to all; the run is over."""
        if self.over:
            return
        self.over = True
        from .combo import take
        from .items import mod_list
        t = context.data
        now = ms()
        if result < 0:
            for m in self.members.values():
                p = m.session.state.get('player')
                info = t.item_info(t.item_index[N_ENHANCER]) if p else None
                if info:
                    it, state = await take(p, info)
                    send(m.session, mod_list((it, state)))
                    m.items[0] = info.table_idx
        cls, chance = self.rating(result, now)
        order = sorted(self.members.values(), key=rank_point, reverse=True)
        for m in self.members.values():
            m.huv_sorts = []
            got = 0
            p = m.session.state.get('player')
            if result > 0 and p:
                ore = f'gi_{CITY_LETTERS.get(self.city, "m")}_00{2 if random.uniform(0, 100) < chance else 1}'
                info = t.item_info(t.item_index[ore]) if ore in t.item_index else None
                if info:
                    it, state = await take(p, info)
                    send(m.session, mod_list((it, state)))
                    got, m.items[1] = it.inven_idx, info.table_idx
            if m.session.id in sessions:
                send(m.session, Frame(0xc1, struct.pack('<iI', result, got)))
        self.actors, self.stack, self.chase_stage = {}, [], -1
        n = len(order)
        for place, m in enumerate(order):
            p = m.session.state.get('player')
            if not p:
                continue
            item = None
            if result == 0 and place + 1 != n:
                d = abs(ORE_LEVEL.get(self.city, 30) - p.char.level)
                if random.uniform(0, 100) <= (100 if d < 21 else 80 if d < 31 else 60 if d < 41 else 40):
                    item = f'gi_{CITY_LETTERS.get(self.city, "m")}_001'
            elif result > 0:
                item = RANK_ITEMS[n % 4][place % 4][(5 - cls) % 5]
            info = t.item_info(t.item_index[item]) if item and item in t.item_index else None
            if info:
                it, state = await take(p, info)
                send(m.session, mod_list((it, state)))
                m.items[1 if result == 0 else 2] = info.table_idx
            if m.uc120:
                await use_uc120(m.session, p)
        units = b''
        for idx, m in sorted(enumerate(self.members.values()), key=lambda e: rank_point(e[1]), reverse=True)[:4]:
            p = m.session.state.get('player')
            c = p.char if p else None
            units += struct.pack('<ifi', idx, rank_point(m), c.level if c else 0)
            units += (c.name if c else '').encode('utf-16-le')[:40].ljust(42, b'\0')
            units += struct.pack('<ii4i3iBB', m.exp, m.mito, m.hubs, m.jumps, m.huvs, int(m.boss), *m.items, 0, 0)
        units += struct.pack('<if', -1, 0.0).ljust(UNIT, b'\0') * (4 - min(len(self.members), 4))
        self.cast(Frame(0x100, struct.pack('<iiii', result, cls, self.retry, now - self.start) + units))
        self.note(f'run over: result {result}, class {cls}, {(now - self.start) // 1000} s; ' +
                  ', '.join(f'{m.session.state["player"].char.name}: {m.hubs} HUBs, {m.jumps} red, {m.huvs} HUVs, '
                            f'boss {int(m.boss)} %, {m.exp} exp, {m.mito} Mito'
                            for m in self.members.values() if m.session.state.get('player')))
        self.uc_stage, self.agree_mode = 0, 0
        drop_run(self)

    def rating(self, result, now):
        """BS_Party::PreUnderCityResult -> (class 1-5, % chance of the beta ore). Members' boss damage becomes %."""
        ms_ = list(self.members.values())
        n = len(ms_) or 1
        secs = (now - self.start) / 1000
        boss_sum = sum(m.boss for m in ms_)
        levels = [m.session.state['player'].char.level for m in ms_ if m.session.state.get('player')] or [1]
        a = min(min(m.hubs for m in ms_) * n, 100) if ms_ else 0
        b = min(max(sum(m.jumps for m in ms_) * 10, 0), 100)
        uc2 = self.uc2_record // 1000 if self.retry == 0 else 0
        c = min(max((6 - self.retry) * 15 + uc2, 0), 100)
        left = sum(self.left_huv)
        d = min(90 - left + max(self.acc_left // 1000 - left * 10, 0), 100)
        boss_left = max((self.chase_base + self.penalty - now) // 1000, 0)
        e = min(boss_left // 4 + 40, 100)
        f = min(max(100 - int(round(abs(2150 - result * secs))) // 10, 0), 100)
        mean = int((a + b + c + d + e + f) / 6)
        cls = 5 if mean >= 92 else 4 if mean >= 82 else 3 if mean >= 72 else 2 if mean >= 62 else 1
        spread = max(levels) - sum(levels) / len(levels)
        chance = min(max(spread * 7, 0), 10) + 10
        total, top = 0, None
        for m in ms_:
            m.boss = int((m.boss * 100 + 0.5) / boss_sum) if boss_sum else 0
            total += m.boss
            if top is None or m.boss > top.boss:
                top = m
        if top and boss_sum:
            top.boss += 100 - total
        self.note(f'rating: HUBs {a} red {b} Mission 2 {c} HUVs {d} boss time {e} run time {f} -> {mean}, class {cls}')
        return cls, chance


def rank_point(m):
    """BS_GameDispatch::UnderCity::GetRankPoint."""
    return m.boss / 100 * 0.55 + m.huvs / 28 * 0.35 + m.jumps / 10 * 0.05 + m.hubs / 100 * 0.05


def huv_attr(h):
    """ChaseTable::GetHuvAttr(level, HUV id): the HuvTable row (exp, Mito), by id then by type."""
    huvs = context.data.huvs
    return (next((r for r in huvs if r['level'] == h[2] and r['id'] == h[1]), None)
            or next((r for r in huvs if r['id'] in (h[1], h[3])), None))


def exp_info(c):
    """0x7d1 ExpInfo (XiStrExpInfo, u16 level, i32 0: no "EXP received" text; client 0x517cd0)."""
    return Frame(0x7d1, struct.pack('<3IHi', c.exp, c.exp_next, c.exp_base, c.level, 0))


def uc120_rate(p):
    if not any(i.item_id == UC_120 and i.stack > 0 for i in p.items):
        return 0
    info = context.data.item_info(context.data.item_index[UC_120])
    return (info.value if info else 0) or 20


async def use_uc120(session, p):
    from .combo import take  # noqa: F401  (items.CHANGED / REMOVED via the module below)
    from .items import CHANGED, DELETE_SQL, REMOVED, STACK_SQL, mod_list
    db = context.db
    it = next((i for i in p.items if i.item_id == UC_120 and i.stack > 0), None)
    if not it:
        return
    it.stack -= 1
    if it.stack <= 0:
        await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
        p.items.remove(it)
        send(session, mod_list((it, REMOVED)))
    else:
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        send(session, mod_list((it, CHANGED)))


def run_of(session):
    r = session.state.get('uc_run')
    return r if r and not r.over and runs.get(r.party.id) is r else None


def drop_run(r):
    r.over = True
    r.task.cancel()
    if runs.get(r.party.id) is r:
        del runs[r.party.id]
    for m in r.members.values():
        m.session.state.pop('undercity', None)
        if m.session.state.get('uc_run') is r:
            m.session.state.pop('uc_run', None)
    if r.solo:
        from .social import leave_party
        for s in list(r.party.members):
            leave_party(s)


def uc_area_key(serial_, area):
    """area.py: the area key of a car in an Undercity area (one instance per party)."""
    from .social import by_serial
    s = by_serial(serial_)
    r = run_of(s) if s else None
    return ('uc', area, r.party.id if r else serial_)


def in_undercity(session):
    return bool(session.state.get('undercity'))


async def load(r, session, time_, fee):
    """0xff UnderCityLoad to one member (the fee taken)."""
    from .items import add_money
    p = session.state['player']
    if fee:
        await add_money(p.char, -fee)
    session.state['undercity'] = r.city
    send(session, Frame(0xff, struct.pack('<iiiq', time_, r.city, fee, p.char.mito)))
    session.log.note(f'undercity: loads city {r.city} (area {AREAS.get(r.city)}), fee {fee}')


@on(SVC, C2S, 0xfc)
async def suggest(session, frame):
    from .social import Party, parties, party_of, party_state
    p = session.state.get('player')
    if not p or len(frame.payload) < 0x36:
        return
    time_, city = struct.unpack_from('<ii', frame.payload, 4)
    if city not in FEES:
        city = p.char.city if p.char.city in FEES else 1
    party = party_of(session)
    if not party or len(party.members) < 2:
        if not test_mode(session):
            session.log.note('undercity: alone (test mode off) -> UC_Err_PlayTogether')
            return script(session, 'UC_Err_PlayTogether')
        if not party:                                  # 2008: a party of one is made
            party = Party(session)
            parties[party.id] = party
            session.state['party'] = party.id
            send(session, party_state(party))
        old = runs.pop(party.id, None)
        if old:
            drop_run(old)
        r = runs[party.id] = Run(party, city, solo=True)
        r.agree_mode = 2
        return await load(r, session, time_, 0)
    r = runs.get(party.id)
    if r and r.agree_mode != 0:
        return
    city_ok = all(s.state.get('player') and s.state['player'].char.city == p.char.city
                  and s.state.get('channel') == session.state.get('channel') for s in party.members)
    if not city_ok:
        return script(session, 'UC_Err_SameCity')
    if r:
        drop_run(r)
    r = runs[party.id] = Run(party, city, solo=False)
    r.agree_mode = 1
    r.agree_timeout = ms() + int(AGREE_SECONDS * 1000)
    r.member(session).agree = True
    out = frame.payload[:0xc] + p.char.name.encode('utf-16-le')[:40].ljust(42, b'\0')
    r.cast(Frame(0xfc, out))
    session.log.note(f'undercity: suggested city {city} to {len(party.members)} members')


@on(SVC, C2S, 0xfd)
async def agree(session, frame):
    r = run_of(session)
    if not r or len(frame.payload) < 8:
        return
    r.cast(Frame(0xfd, frame.payload[:8]))
    m = r.member(session)
    if m:
        m.agree = True
    fee = FEES.get(r.city, FEES[4])
    if any(s.state['player'].char.mito < fee for s in r.sessions if s.state.get('player')):
        for s in r.sessions:
            script(s, 'UC_Err_NeedMito')
        if r.agree_mode == 1:
            r.agree_mode = 0
            r.cast(Frame(0xfe, struct.pack('<Ii', 0, 0)))
        return
    if all(m.agree for m in r.members.values()):
        r.agree_mode = 2
        time_, = struct.unpack_from('<i', frame.payload, 4)
        for s in r.sessions:
            await load(r, s, time_, fee)


@on(SVC, C2S, 0xfe)
async def reject(session, frame):
    r = run_of(session)
    if r and r.agree_mode == 1:
        r.agree_mode = 0
        r.cast(Frame(0xfe, frame.payload[:8].ljust(8, b'\0')))
        drop_run(r)


@on(SVC, C2S, 0x101)
async def exit_uc(session, frame):
    from .social import leave_party
    r = run_of(session)
    session.state.pop('undercity', None)
    session.log.note('undercity: exit')
    if not r:
        return
    if len(r.party.members) < 2:
        return drop_run(r)
    r.members.pop(id(session), None)
    session.state.pop('uc_run', None)
    leave_party(session)


@on(SVC, C2S, 0xfa)
async def stage(session, frame):
    """BS_Party::UpdateUCStage."""
    r = run_of(session)
    if not r or len(frame.payload) < 12:
        return
    start_type, st, time_ = struct.unpack_from('<iii', frame.payload)
    m = r.member(session)
    if m:
        m.stage = st
    if start_type == 1:
        if st == 1:
            r.boss_bonus = 0
        done = sum(1 for x in r.members.values() if st <= x.stage)
    elif start_type == 2:
        for x in r.members.values():
            x.stage = st
        done = len(r.members)
    else:
        return
    if done != len(r.members):
        return
    if st == 0:
        r.init()
    elif st == 1:
        r.init()
    elif st == 7:
        limit = 120 + (r.boss_try - 1) * 10 + (20 if r.city == 1 else 0)
        r.chase_base = ms() + 12600 + limit * 1000
    r.uc_stage = st
    r.cast(Frame(0xfb, struct.pack('<ii', st, time_)))
    session.log.note(f'undercity: stage {st}')


@on(SVC, C2S, 0xbb8)
async def patrol_start(session, frame):
    r = run_of(session)
    if not r or len(frame.payload) < 8:
        return
    patrol, slot = struct.unpack_from('<II', frame.payload)
    r.init()
    for m in r.members.values():
        m.hubs = m.jumps = m.huvs = 0
        m.boss = 0.0
        m.exp = m.mito = 0
        m.items = [-1, -1, -1]
    r.patrol = {}
    t = context.data
    pre, first = START_ICONS.get(r.city, START_ICONS[1])
    x = y = z = angle = 0.0
    if slot < 4:
        i, j = t.icon_index.get(f'{pre}{first + slot:05d}'), t.icon_index.get(f'{pre}{first + 4 + slot:05d}')
        if i is not None:
            _, x, y, z = t.icons[i]
            if j is not None:
                angle = math.atan2(t.icons[j][2] - y, t.icons[j][1] - x)
    r.cast(Frame(0xbb9, struct.pack('<II4f', patrol, slot, x, y, z, angle)))
    session.log.note(f'undercity: Mission 1 (patrol {patrol}) starts')


@on(SVC, C2S, 0xbba)
async def patrol_give_up(session, frame):
    r = run_of(session)
    if r:
        r.patrol = None
        r.cast(Frame(0xbbb, frame.payload[:4].ljust(4, b'\0')))


@on(SVC, C2S, 0xbbc)
async def patrol_goal(session, frame):
    r = run_of(session)
    m = r.member(session) if r else None
    if not m or r.patrol is None or len(frame.payload) < 12:
        return
    patrol, place, jump = struct.unpack_from('<III', frame.payload)
    if jump:
        m.jumps += 1
    m.hubs += 1
    if place >= HUBS or place in r.patrol:
        return
    r.patrol[place] = ms()
    p = session.state['player']
    r.cast(Frame(0xbbd, struct.pack('<IIIIIiq', patrol, place, 0, 0, serial(session), 0, p.char.mito)))
    if len(r.patrol) < HUBS:
        return
    r.patrol = None
    a, b, c = PATROL_REWARD.get(r.city, PATROL_REWARD[1])
    for x in list(r.members.values()):
        if x.session.id not in sessions:
            continue
        exp, mito = await r.gain(x, a * x.hubs, b * x.hubs + c * x.jumps)
        send(x.session, Frame(0xbbe, struct.pack('<IIIIiq', patrol, 1, exp, 0, mito,
                                                 x.session.state['player'].char.mito)))
    r.note(f'Mission 1 done in {(ms() - r.start) // 1000} s')


@on(SVC, C2S, 0xbc2)
async def boss_patrol_start(session, frame):
    r = run_of(session)
    if not r:
        return
    if r.boss_try < 0:
        r.boss_try = 1
    n = len(r.members)
    if test_mode(session) and n < 2:
        n = 2
    hubs = (n - 1) * (6 - r.boss_try)
    if hubs < 1:
        hubs = (r.boss_try - 1) * -3 + 15
    limit = 120 + (r.boss_try - 1) * 10 + (20 if r.city == 1 else 0)
    r.chase_base = ms() + 300000
    r.cast(Frame(0xbc3, struct.pack('<ii', limit * 1000, hubs)))
    session.log.note(f'undercity: Mission 2 try {r.boss_try}: {hubs} barrier HUBs, {limit} s')


@on(SVC, C2S, 0xbc4)
async def boss_patrol_give_up(session, frame):
    r = run_of(session)
    if r:
        r.init()
        r.cast(Frame(0xbc5, frame.payload[:4].ljust(4, b'\0')))


@on(SVC, C2S, 0xbc6)
async def boss_patrol_goal(session, frame):
    from .combo import take
    from .items import mod_list
    r = run_of(session)
    if not r or len(frame.payload) < 12:
        return
    time_, table, place = struct.unpack_from('<iII', frame.payload)
    now = ms()
    r.uc2_record = r.chase_base + r.penalty - now
    p = session.state['player']
    r.cast(Frame(0xbc7, struct.pack('<iIIIIIiq', time_, table, place, 0, 0, serial(session), 0, p.char.mito)))
    if place != 0:
        return
    r.boss_try = -1                                    # UCBossPatrolReward
    t = context.data
    item = S_ENHANCER if context.data.contents.get('Main.NewUpgrade', 1) else 'i_n_00002'
    for m in list(r.members.values()):
        q = m.session.state.get('player')
        if not q or m.session.id not in sessions:
            continue
        inven = 0
        info = t.item_info(t.item_index[item])
        if info:
            it, state = await take(q, info)
            send(m.session, mod_list((it, state)))
            inven, m.items[0] = it.inven_idx, info.table_idx
        exp, _ = await r.gain(m, MAIN_HUB_EXP.get(r.city, MAIN_HUB_EXP[1]), 0)
        send(m.session, Frame(0xbc8, struct.pack('<IIIiq', 1, exp, inven, 0, q.char.mito)))
    r.note(f'Mission 2 done ({r.retry} retries, {r.uc2_record // 1000} s left)')


@on(SVC, C2S, 0xc2)
async def huv_param(session, frame):
    r = run_of(session)
    if r and len(frame.payload) >= 16:
        r.chase_pos = struct.unpack_from('<4f', frame.payload)


@on(SVC, C2S, 0xbe)
async def huv_req(session, frame):
    """Cmd_HuvReq: the run's HUVs; the chase starts (stage 1 at once)."""
    r = run_of(session)
    if not r or len(frame.payload) < 8:
        return
    start, n = struct.unpack_from('<iI', frame.payload)
    n = min(n, (len(frame.payload) - 8) // 14)
    for a in list(r.actors.values()):
        r.end_huv(a)
    r.chase_base = ms()
    r.chase_stage = 1
    r.penalty = 0
    r.boss_try = -1
    r.chase_start = start
    r.stack = [struct.unpack_from('<7H', frame.payload, 8 + 14 * i) for i in range(n)]
    r.bosses = []
    stages = {}
    for h in r.stack:
        stages[h[0]] = stages.get(h[0], 0) + 1
    session.log.note(f'undercity: HUV list {n} ({", ".join(f"stage {k}: {v}" for k, v in sorted(stages.items()))})')


@on(SVC, C2S, 0xc4)
async def huv_time_bonus(session, frame):
    r = run_of(session)
    if not r or len(frame.payload) < 4:
        return
    bonus, = struct.unpack_from('<i', frame.payload)
    r.boss_bonus += bonus
    r.cast(Frame(0xc4, struct.pack('<ii', bonus, r.boss_bonus)))


@on(SVC, C2S, 0xc0)
async def huv_hit(session, frame):
    """Cmd_HuvHit 0x678b10."""
    r = run_of(session)
    if not r or len(frame.payload) < 38:
        return
    hitter, = struct.unpack_from('<H', frame.payload)
    sort, = struct.unpack_from('<H', frame.payload, 6)
    hp, = struct.unpack_from('<i', frame.payload, 0xa)
    a = r.actors.get(sort)
    if not a or hp < 0:
        return
    delta = a.hp - hp
    if delta < 1 or delta > 1000000:
        return
    a.hp = hp
    now = ms()
    boss = a.stage == BOSS
    if boss:
        a.hit_at = now
    n = len(r.members)
    twin = None
    if boss:
        others = [b for b in r.bosses if b is not a and b.sort in r.actors]
        if others and len([b for b in r.bosses if b.sort in r.actors]) > 1:
            twin = others[0]
            twin.hp = hp
    for m in list(r.members.values()):
        q = m.session.state.get('player')
        if not q or m.session.id not in sessions:
            continue
        exp = mito = 0
        if a.hp == 0 and serial(m.session) == hitter and not boss:
            exp, mito = a.exp * 2, a.money * 2
            m.huvs += 1
        if boss:
            k, x, y = BOSS_EXP.get(r.city, BOSS_EXP[1])
            exp = int(round(delta / k * (math.log(max(q.char.level, 1)) * x + y)))
            if serial(m.session) == hitter:
                m.boss += delta
                exp = int(exp * 0.75)
            else:
                exp = int(exp * BOSS_SHARE.get(n, 1))
        exp, mito = await r.gain(m, exp, mito)
        if twin:
            send(m.session, Frame(0xc0, frame.payload[:4] + struct.pack('<HH', serial(twin.owner), twin.sort)
                                  + frame.payload[8:0x16] + struct.pack('<iqi', 0, q.char.mito, 0)))
        send(m.session, Frame(0xc0, frame.payload[:0x16] + struct.pack('<iqi', mito, q.char.mito, exp)))
    if a.hp:
        return
    r.end_huv(a)
    if a.stage == ESCORT_LAST:
        if not r.actors and not r.stack:
            await r.middle_reward()
    elif boss:
        if twin:
            r.end_huv(twin)
        r.note(f'boss HUV out ({len(r.actors)} HUVs left)')
        if not r.actors:
            await r.end(1)


@on_open(SVC)
async def undercity_on_close(session):
    try:
        await asyncio.Event().wait()
    finally:
        r = session.state.get('uc_run')
        if r and not r.over:
            m = r.members.pop(id(session), None)
            for sort in (m.huv_sorts if m else []):
                r.actors.pop(sort, None)
            if not r.members or r.solo:
                drop_run(r)


def gm_test(session, args):
    on_ = not args or args[0].lower() not in ('off', '0', 'no')
    session.state['uc_test'] = on_
    return ('Undercity test mode on: alone, chat /ucm /uck /ucc /uco (Moon Palace, Koinonia, Cras, Oros) to enter'
            if on_ else 'Undercity test mode off')
