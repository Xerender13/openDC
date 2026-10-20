"""Virtual HUV (Virtual Chasing, 2011; Dev Ed names ChasingBattle*): two teams in a city, each with its HUV (1 per team
in 4:4, 2 in 8:8); the other team's drivers ram it, the HUV dodges and hits traffic. Rules: the JP wiki page
(ゲームモード/バーチャルチェイシング; the mode ended there 2011-06-22); the 2008 server has no such mode, the layouts below
are the 2011 client's (EU exe addresses, ../DriftCityEU-decomp; the US exe is the same build).

Registering: the Tatiana Call Unit (i_n_00062, UseItemClient kind vc_T_callunit = client kind 0x1e; not used up) used in a
city (not Mitro City, city 5; not in a chase: client 0x601cf0, texts 11144 / 10966) sends
0x0118 ChasingBattleInfo (empty) -> 0x0119 InfoAck (u32 4:4 waiting, u32 8:8 waiting; 0x512fe0: Tatiana's VC_Enter
    dialog with the two counts, 0x57dad0) -> the player picks 4 or 8 (dialog 0x5838xx, buttons 0x7a133 / 0x7a134) ->
0x011a WaitRequest (u32 4 / 8) -> 0x011b WaitRequestAck (u32: 1 registered (10942 "Registration submitted...", the
    V-HUV chat tab), 2 the same text, else 10943 "Registration canceled due to party ..."; 0x513050).
    A party: the members in the same city and channel get 0x011c WaitSuggest (wchar[21] the registering player, u32
    mode; 0x51ac80: 10940 "Do you want to participate in the Virtual HUV? %s has planned this mission."; a member in
    a chase answers no at once, text 11145) and answer 0x011d (u32 1 yes / 0 no or the dialog's timeout,
    0x6b4xxx). All yes -> the party is registered (0x11b 1 to each), on one team; else 0x11b 0 to each.
0x012a WaitInfo (empty; the V-HUV tab) -> 0x012b WaitInfo (u32 mode, u32 waiting; 0x513280: chat 11003 "Virtual HUV
    %dvs%d Waiting Players : %d"), also sent to every waiting player when the count changes.
0x011e WaitCancel (empty) -> 0x011f (u32 0; 1 adds text 10943: sent to the other party members).
When 2 x mode are waiting in one city and channel the match starts (parties kept together):
0x0122 ChasingBattleStart (u32 mode, u32 0 (not read), u32 seconds (4:4 300, 8:8 600; the HUD clock, [net+0x154]+0x3c), u32 n,
    n x 0x56: u32 serial, u32 team 0 / 1, u32 role (1 HUV, 2 next HUV, 0 chaser: texts VC_HUVNow / VC_HUVNext /
    VC_HUV_PVP), f32 HP shown, f32 max HP, u32 0, u32 HUV id (the model the HUV gets, 0x73be70 -> 0x5e2130), u32 0,
    u32 0, wchar[25] name) (0x5262b0: the 0x84-byte records at [net+0x3d584]: +0 score, +4 serial, +8 team, +0xc
    role, +0x18 HUV id, +0x20 max HP, +0x24 HP shown, +0x28 damage, +0x48 name; size (n - 1) x 0x56 + 0x68). The
    client then counts 7.5 s down (state 2 -> 3, 0x745b00), sets the per-city machine points itself (chaser
    0x741350, HUV 0x73be70: the wiki's table) and runs the clock, the 60 s (10972) and 20 s warnings.
In the match (client state 3):
0x0123 ChasingBattleHit (u32 own serial, u32 target, u32 target team, f32 damage, i32 critical; 0x486690, only for a
    collision with a HUV (role 1) of the other team while not a HUV oneself) -> 0x0124 HitAck to all (u32 attacker,
    u32 target, u32 target team (not read), f32 damage added, i32 critical (> 0: an effect), i32 caught (1: the
    attacker's catch effect 0x6b4fc0, as 0xc15 HuvHit shows when one's own hit empties a HUV), u32 team 0 score,
    u32 team 1 score, u32 attacker's score; 0x51ed00: the target's damage + the value, its boost refilled; the
    effects only for the attacker).
0x012a (empty) from the current HUV: it hit a traffic car (once a car, 0x488xxx) -> +3 points, 5 % HP back.
0x0120 (empty) from the current HUV every 10 s while its team's next HUV is 1500 m or more away (0x7469b1) -> 5 %.
0x0129 Score (u32 serial, f32 damage added (< 0 heals; the client keeps it >= 0), u32 its score, u32 team 0, u32
    team 1; 0x51f020): the HP drain (5 % every 10 s for each HUV) and the two above.
0x0127 HuvChange (u32 team (not read), u32 old HUV (role 4, a chaser again 3 s later), u32 new HUV (role 3, the HUV 1.5 s later,
    text 10975, damage 0), u32 next HUV (role 2, text 10971), f32 HP shown, f32 max HP, u32 0, u32 HUV id; 0x51f200):
    when a HUV's HP is gone (caught: the attacker +20 points; or drained).
0x0128 ChasingBattleEnd (u32 0 (not read), i32 result 1 won / 0 lost / -1 stopped (VC_Cancel_Msg), i64 Mito, u32 exp, 4 x i32 item
    TableIdx (-1 none), 4 x u32 counts; 0x524c50: texts 10973 / 10974, the result window 0x56c020; the client adds
    the Mito to its money itself, so no 0x8a here). At the time limit: the team with more points wins (a draw: both
    lose). It must come before the client's own clock reaches 0 (that clock is also the race clock: below 0 the race
    finish runs, 0x49d3d0, and the client crashes in the city): sent 1 % of the seconds (at least 3 s) early. A player who leaves the match (disconnects) stops it for everyone (result -1, nothing given).
Rewards (the wiki: exp and Mito for both teams, items for the winners: Undercity 120% x1, Mittron Enhancers by city
(Moon Palace N x10, Koinonia N x30, Cras S x1, Oros S x3), HUV Call Unit x10 for Team ROO drivers): exp / Mito = the
HuvTable exp / Mito of a HUV at the player's level x emulator.ini [vchase] win_ / lose_ rates (the wiki gives no
amounts), doubled in 8:8.
Test mode ([vchase] test = 1, or the GM chat command gmvchasetest on): a match starts with two players waiting (any
size picked; one of them in test mode), one a team. One HUV at a time (both being HUVs, nobody could ram: the client lets only a non-HUV hit a
HUV): one player is the HUV, the other chases; when the HUV is out, the other player becomes the HUV of his team.
"""
import asyncio
import random
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, send, serial_of, sessions

CALL_UNIT = 'i_n_00062'                     # Tatiana Call Unit
MODES = (4, 8)
HUV_IDS = {1: 10005, 2: 10011, 3: 10013, 4: 10019}     # O-Raid, V-Boxer, B-Terror, R-Trouble (the wiki's appearance)
HUVS_PER_TEAM = {4: 1, 8: 2}
ENTRY, NAME_CHARS = 0x56, 25
CHASER, HUV, NEXT = 0, 1, 2
NOBODY = 0xffffffff
CITY_ITEMS = {1: ('i_n_00043', 10), 2: ('i_n_00043', 30), 3: ('i_n_00044', 1), 4: ('i_n_00044', 3)}
UNDERCITY_120, HUV_CALL_UNIT = 'i_n_00064', 'i_n_00063'
SUGGEST_SECONDS = 30                        # a party's registration waits this long for the members' answers

waiting = {}            # (city, channel, mode) -> [group], a group = [sessions] (a party registers together)
pending = {}            # id(leader session) -> dict(mode, key, members, answers)


def cfg(name):
    return context.vchase[name]


def test_mode(session):
    return cfg('test') or session.state.get('vchase_test', False)


def serial_of(s):
    return serial_of(s)


def key_of(session, mode):
    p = session.state['player']
    return p.char.city, session.state.get('channel'), mode


def count(key):
    return sum(len(g) for g in waiting.get(key, []))


def wait_info(key):
    return Frame(0x12b, struct.pack('<II', key[2], count(key)))


def tell_waiting(key):
    for g in waiting.get(key, []):
        for s in g:
            send(s, wait_info(key))


def group_of(session):
    for key, groups in waiting.items():
        for g in groups:
            if session in g:
                return key, g
    return None, None


def holds_unit(p):
    return any(i.item_id == CALL_UNIT and i.stack > 0 and (i.state & 0xffff) != 4 for i in p.items)


@on(SVC, C2S, 0x118)
async def info(session, frame):
    p = session.state.get('player')
    if not p:
        return
    send(session, Frame(0x119, struct.pack('<II', *(count(key_of(session, m)) for m in MODES))))


@on(SVC, C2S, 0x11a)
async def wait_request(session, frame):
    from .social import party_of
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    mode, = struct.unpack_from('<I', frame.payload)
    key = key_of(session, mode)
    busy = group_of(session)[0] or session.state.get('vchase') or id(session) in pending
    if mode not in MODES or busy or not holds_unit(p) or p.char.city not in HUV_IDS:
        session.log.note(f'vchase: registration refused (mode {mode}, busy {bool(busy)}, unit {holds_unit(p)})')
        return send(session, Frame(0x11b, struct.pack('<I', 0)))
    party = party_of(session)
    members = [s for s in (party.members if party else []) if s is not session and s.state.get('player')
               and s.state['player'].char.city == p.char.city and s.state.get('channel') == session.state.get('channel')
               and not group_of(s)[0] and not s.state.get('vchase')]
    if len(members) + 1 > mode:
        return send(session, Frame(0x11b, struct.pack('<I', 0)))
    if not members:
        return register(key, [session])
    pending[id(session)] = dict(mode=mode, key=key, leader=session, members=members, answers={})
    for s in members:
        s.state['vchase_invite'] = id(session)
        send(s, Frame(0x11c, p.char.name.encode('utf-16-le')[:40].ljust(42, b'\0') + struct.pack('<I', mode)))
    session.log.note(f'vchase: {p.char.name} asks {len(members)} party members ({mode}:{mode})')
    asyncio.ensure_future(invite_timeout(id(session)))


async def invite_timeout(pid):
    await asyncio.sleep(SUGGEST_SECONDS)
    inv = pending.pop(pid, None)
    if inv:
        refuse_invite(inv)


def refuse_invite(inv):
    for s in [inv['leader'], *inv['members']]:
        s.state.pop('vchase_invite', None)
        send(s, Frame(0x11b, struct.pack('<I', 0)))


@on(SVC, C2S, 0x11d)
async def invite_answer(session, frame):
    yes = len(frame.payload) >= 4 and struct.unpack_from('<I', frame.payload)[0] == 1
    pid = session.state.pop('vchase_invite', None)
    inv = pending.get(pid)
    if not inv:
        return
    inv['answers'][id(session)] = yes
    session.log.note(f'vchase: invite answered {"yes" if yes else "no"}')
    if not yes:
        pending.pop(pid, None)
        return refuse_invite(inv)
    if len(inv['answers']) == len(inv['members']):
        pending.pop(pid, None)
        register(inv['key'], [inv['leader'], *inv['members']])


def register(key, group):
    waiting.setdefault(key, []).append(group)
    for s in group:
        send(s, Frame(0x11b, struct.pack('<I', 1)))
        s.log.note(f'vchase: waiting for {key[2]}:{key[2]} in city {key[0]} channel {key[1]} ({count(key)} waiting)')
    tell_waiting(key)
    try_start(key)


def unregister(session, notify=True):
    key, g = group_of(session)
    if not g:
        return
    waiting[key].remove(g)
    if not waiting[key]:
        del waiting[key]
    for s in g:
        if notify:
            send(s, Frame(0x11f, struct.pack('<I', 0 if s is session else 1)))
    tell_waiting(key)


@on(SVC, C2S, 0x11e)
async def wait_cancel(session, frame):
    if group_of(session)[0]:
        session.log.note('vchase: registration cancelled')
        unregister(session)
    else:
        send(session, Frame(0x11f, struct.pack('<I', 0)))


# ---- the match --------------------------------------------------------------------------------------------------
class Player:
    def __init__(self, session, team):
        self.session, self.team = session, team
        self.serial = serial_of(session)
        self.score, self.damage, self.role = 0, 0.0, CHASER
        self.drain_at = 0.0


class Slot:
    """One HUV of a team: its current driver and the next one."""
    def __init__(self, team):
        self.team, self.huv, self.next = team, None, None


class Match:
    def __init__(self, key, teams, test):
        self.key, self.mode, self.city = key, key[2], key[0]
        self.players = [Player(s, t) for t, members in enumerate(teams) for s in members]
        self.seconds = int(cfg('seconds_8') if self.mode == 8 else cfg('seconds_4'))
        self.test = test
        self.started = time.monotonic()
        # the client's clock (0x745b00, frame times) ran ~0.5 % fast (user, 2026-10-18: both clients crashed at its 0, 1.6 s
        # before this 0x128): below 0 the race code shares it (0x49d3d0: [net+0x154]+0x3c < 0 -> the race finish
        # 0x500270 / 0x44b800, no race in a city) until 0x128 resets it. So the match ends END_MARGIN early.
        self.ends = self.started + COUNTDOWN + self.seconds - max(END_MIN, self.seconds * END_MARGIN)
        self.slots = []
        self.over = False
        if test:                                # two players: one HUV at a time, on a random team
            slot = Slot(random.choice((0, 1)))
            slot.huv = next(m for m in self.players if m.team == slot.team)
            slot.huv.role, slot.huv.drain_at = HUV, self.started + COUNTDOWN + DRAIN_SECONDS
            self.slots.append(slot)
            return
        for team in (0, 1):
            members = [m for m in self.players if m.team == team]
            random.shuffle(members)
            for _ in range(min(HUVS_PER_TEAM[self.mode], len(members))):
                slot = Slot(team)
                slot.huv = members.pop(0)
                slot.huv.role = HUV
                slot.huv.drain_at = self.started + COUNTDOWN + DRAIN_SECONDS
                self.slots.append(slot)
            for slot in [x for x in self.slots if x.team == team]:
                if members:
                    slot.next = members.pop(0)
                    slot.next.role = NEXT

    def by_serial(self, serial):
        return next((m for m in self.players if m.serial == serial), None)

    def by_session(self, session):
        return next((m for m in self.players if m.session is session), None)

    def team_score(self, team):
        return sum(m.score for m in self.players if m.team == team)

    def scores(self):
        return self.team_score(0), self.team_score(1)

    def broadcast(self, frame):
        for m in self.players:
            send(m.session, frame)

    def start_frame(self):
        huv_id = HUV_IDS.get(self.city, HUV_IDS[1])
        body = b''.join(struct.pack('<IIIffIIII', m.serial, m.team, m.role, MAX_HP, MAX_HP, 0, huv_id, 0, 0)
                        + m.session.state['player'].char.name.encode('utf-16-le')[:2 * NAME_CHARS - 2]
                        .ljust(2 * NAME_CHARS, b'\0') for m in self.players)
        return Frame(0x122, struct.pack('<IIII', self.mode, 0, self.seconds, len(self.players)) + body)

    def score_frame(self, m, delta):
        return Frame(0x129, struct.pack('<IfIII', m.serial, delta, m.score, *self.scores()))

    def slot_of(self, m):
        return next((x for x in self.slots if x.huv is m), None)

    def pick_next(self, slot):
        """The team's next HUV after slot.huv: in team order after the last ones, not a HUV or another slot's next."""
        busy = {id(x.huv) for x in self.slots} | {id(x.next) for x in self.slots if x is not slot and x.next}
        team = [m for m in self.players if m.team == slot.team]
        start = team.index(slot.huv) if slot.huv in team else -1
        for i in range(1, len(team) + 1):
            m = team[(start + i) % len(team)]
            if id(m) not in busy:
                return m
        return None

    def change(self, slot, now):
        """slot's HUV is out: the next one takes over (alone: the same driver again)."""
        old = slot.huv
        new = slot.next if slot.next and slot.next in self.players else old
        if self.test:                           # the test's single HUV goes to the other player's team
            new = next((m for m in self.players if m is not old), old)
            slot.team = new.team
        old.role = CHASER
        slot.huv, new.role, new.damage = new, HUV, 0.0
        new.drain_at = now + 1.5 + DRAIN_SECONDS
        slot.next = None if self.test else self.pick_next(slot)
        if slot.next:
            slot.next.role = NEXT
        huv_id = HUV_IDS.get(self.city, HUV_IDS[1])
        self.broadcast(Frame(0x127, struct.pack('<IIIIffII', slot.team, old.serial, new.serial,
                                                slot.next.serial if slot.next else NOBODY, MAX_HP, MAX_HP, 0, huv_id)))
        old.session.log.note(f'vchase: team {slot.team} HUV {old.serial} -> {new.serial}, next '
                             f'{slot.next.serial if slot.next else "-"}')

    def hurt(self, m, delta, now):
        """Damage (or healing) for HUV m -> 0x129; its HP gone: the HUV changes. -> True when it changed."""
        m.damage = max(0.0, m.damage + delta)
        self.broadcast(self.score_frame(m, delta))
        slot = self.slot_of(m)
        if slot and m.damage >= MAX_HP:
            self.change(slot, now)
            return True
        return False


MAX_HP, DRAIN_SECONDS, COUNTDOWN = 100.0, 10.0, 7.5
END_MARGIN, END_MIN = 0.01, 3.0               # the end comes this share of the match seconds (at least END_MIN) early
matches = []


def team_split(groups, size):
    """Groups (parties) onto two teams of size each, biggest first -> [team 0, team 1] or None."""
    teams = [[], []]
    for g in sorted(groups, key=len, reverse=True):
        t = min((0, 1), key=lambda i: len(teams[i]))
        if len(teams[t]) + len(g) > size:
            t = 1 - t
            if len(teams[t]) + len(g) > size:
                return None
        teams[t] += g
    return teams


def try_start(key):
    groups = waiting.get(key, [])
    if not groups:
        return
    test = any(test_mode(s) for g in groups for s in g)
    need = 2 if test else 2 * key[2]
    chosen, n = [], 0
    for g in groups:                            # first come, first served; a party that does not fit waits
        if n + len(g) <= need:
            chosen.append(g)
            n += len(g)
    if n < need:
        return
    size = 1 if test else key[2]
    teams = team_split(chosen, size)
    if not teams:
        return
    for g in chosen:
        groups.remove(g)
    if not groups:
        waiting.pop(key, None)
    tell_waiting(key)
    m = Match(key, teams, test)
    matches.append(m)
    for pl in m.players:
        pl.session.state['vchase'] = m
    m.broadcast(m.start_frame())
    m.players[0].session.log.note(f'vchase: match {key[2]}:{key[2]} started in city {key[0]} with '
                                  f'{len(m.players)} players' + (' (test)' if test else ''))
    m.task = asyncio.ensure_future(clock(m))


async def clock(m):
    try:
        while not m.over:
            await asyncio.sleep(0.5)
            now = time.monotonic()
            if now >= m.ends:
                return await finish(m)
            for slot in list(m.slots):
                h = slot.huv
                if h.drain_at and now >= h.drain_at:
                    h.drain_at = now + DRAIN_SECONDS
                    m.hurt(h, cfg('drain'), now)
    except asyncio.CancelledError:
        pass


def match_of(session):
    m = session.state.get('vchase')
    return m if m and not m.over else None


@on(SVC, C2S, 0x123)
async def hit(session, frame):
    m = match_of(session)
    if not m or len(frame.payload) < 20:
        return
    attacker, target, team, damage, critical = struct.unpack_from('<IIIfi', frame.payload)
    me, h = m.by_session(session), m.by_serial(target)
    now = time.monotonic()
    if (not me or not h or attacker != me.serial or h.team == me.team or not m.slot_of(h) or me.role == HUV
            or now < m.started + COUNTDOWN):
        return
    delta = MAX_HP / cfg('hits')
    caught = h.damage + delta >= MAX_HP
    me.score += 3 if critical > 0 else random.randint(1, 2)
    if caught:
        me.score += int(cfg('catch_points'))
    h.damage = min(MAX_HP, h.damage + delta)
    m.broadcast(Frame(0x124, struct.pack('<IIIfiiIII', me.serial, h.serial, h.team, delta, 1 if critical > 0 else 0,
                                         1 if caught else 0, *m.scores(), me.score)))
    session.log.note(f'vchase: {me.serial} hit HUV {h.serial} ({h.damage:g} %)' + (' - caught' if caught else ''))
    if caught:
        m.change(m.slot_of(h), now)


@on(SVC, C2S, 0x12a)
async def traffic_or_wait_info(session, frame):
    m = match_of(session)
    if not m:
        key = group_of(session)[0]
        if key:
            send(session, wait_info(key))
        return
    me = m.by_session(session)
    if me and m.slot_of(me):                    # the HUV hit a traffic car: +3 points, 5 % HP back
        me.score += int(cfg('traffic_points'))
        m.hurt(me, -cfg('traffic_heal'), time.monotonic())


@on(SVC, C2S, 0x120)
async def far_from_next(session, frame):
    m = match_of(session)
    me = m.by_session(session) if m else None
    if me and m.slot_of(me):                    # 1500 m or more from the team's next HUV: 5 % more
        m.hurt(me, cfg('drain'), time.monotonic())


def huv_row(level):
    rows = [r for r in context.data.huvs if r['level'] <= level] or context.data.huvs
    top = max(r['level'] for r in rows)
    return next(r for r in rows if r['level'] == top)


async def finish(m, stopped=False):
    """The time is up (or a player left: stopped) -> 0x128 to each player, with the rewards."""
    if m.over:
        return
    m.over = True
    if m in matches:
        matches.remove(m)
    a, b = m.scores()
    winner = None if stopped or a == b else (0 if a > b else 1)
    for pl in m.players:
        s = pl.session
        s.state.pop('vchase', None)
        p = s.state.get('player')
        if not p or s.id not in sessions:
            continue
        try:
            await end_for(m, pl, s, p, pl.team == winner, stopped, (a, b))
        except Exception as e:                  # one player's failure does not keep the others' results back
            s.log.note(f'vchase: end failed: {e!r}')


async def end_for(m, pl, s, p, won, stopped, score):
    """One player's end of a match: exp, Mito and the winners' items, then 0x128."""
    from .driftuse import Gains, give_item
    from .items import add_money
    from .licenses import faction
    from .progress import add_exp
    mito = exp = 0
    items = []
    gains = Gains()
    if not stopped:
        r = huv_row(p.char.level)
        rate = (cfg('win_rate') if won else cfg('lose_rate')) * (2 if m.mode == 8 else 1)
        exp, mito = int(r['exp'] * rate), int(r['money'] * rate)
        if exp:
            await add_exp(p.char, exp)
            gains.exp = exp
        if mito:
            await add_money(p.char, mito)
        if won:
            items = [(UNDERCITY_120, 1), CITY_ITEMS.get(m.city, CITY_ITEMS[1])]
            if faction(p) == 'ROO':
                items.append((HUV_CALL_UNIT, 10))
            for item, n in items:
                await give_item(p, item, n, gains)
    t = context.data
    ids = [t.item_index[i] for i, _ in items][:4] + [-1] * (4 - len(items[:4]))
    counts = [n for _, n in items][:4] + [0] * (4 - len(items[:4]))
    gains.send(s, p)                        # items (0x192) and stats; the Mito comes with the 0x128
    result = -1 if stopped else 1 if won else 0
    send(s, Frame(0x128, struct.pack('<IiqI4i4I', 0, result, mito, exp, *ids, *counts)))
    s.log.note(f'vchase: match over ({score[0]}:{score[1]}), {"stopped" if stopped else "won" if won else "lost"}: '
               f'{exp} exp, {mito} Mito, items {items}')


@on_open(SVC)
async def vchase_on_close(session):
    try:
        await asyncio.Event().wait()
    finally:
        unregister(session)
        pid = session.state.pop('vchase_invite', None)
        inv = pending.pop(pid, None) or pending.pop(id(session), None)
        if inv:
            refuse_invite(inv)
        m = match_of(session)
        if m:
            m.players = [x for x in m.players if x.session is not session]
            m.task.cancel()
            await finish(m, stopped=True)


def gm_test(session, args):
    on_ = not args or args[0].lower() not in ('off', '0', 'no')
    session.state['vchase_test'] = on_
    return ('Virtual HUV test mode on: a match starts with two players waiting (one of them with it on, or [vchase] test)' if on_
            else 'Virtual HUV test mode off')
