"""Party Patrol (2011; Instant_Client rows of type party_move / party_move_ROO, the client's mission types 0x20 / 0x21;
the 2008 server had none). One patrol shared by a whole party: the posts any member passes count for everyone, the
party has a time limit that the posts and the emergency ("Quick Patrol") posts raise, and each member gets a result
window at the end. Rules from the Japanese wiki (ゲームモード/パトロール) and the client; *guess* marks what neither shows.

**The pillar.** With content flag InstantMission.PartyPatrol (byte [net+0x280] bit 5, client 0x62f95d; missing from the
2008 Contents.ini, so handlers/game.py NEW_FLAGS) and a party of 2 or more (party list [0x536360()+0x3d5b0], 0x4c per
member), the client shows the patrol pillars of the party rows instead of the solo ones (OMD: party_move, ROO:
party_move_ROO; every member's level at least GlobalContent MinPatrolGrade). Accepting one sends the usual 0x3e0.

0x3e0 InstantStart (a party row) -> 0x3e1 (TableIdx, u32 0, u8 0) to **every member**: the client's 0x3e1 handler
    (0x51fb40) builds the mission from its own table (0x70d0d0: any free slot of the row's category, no offer needed)
    and, for types 0x20 / 0x21, starts the party patrol: car stats from the row's <car> tag (part effects off, as the
    wiki says), the party patrol object (0x72d4d0: u32 slots[4] @0, u32 time limit ms @0x10, u32 start tick @0x14,
    u32 emergency posts asked @0x18, u32 state @0x1c: 0 none, 1 starting, 2 running), "Party Patrol Start!" (11156).
    Posts are not reported in state 1 (0x742a41); the HUD (0x652440) goes to 2 once the time left (start + limit -
    now) is 60 s or less (0x6524ac; posts are drawn only from state 2, 0x62f6ec / 0x6336b8), so 0xc27 with the first
    limit follows the 0x3e1: start_seconds + COUNTDOWN (the 0x3e1 handler's 7.5 s start effect, 0x51fce0), at
    most 60 + COUNTDOWN; a longer one (the test mode's) is sent RAISE_AFTER s later. Every member must be
    in the starter's city and channel, not in a room / chase / patrol, and in the row's level range (the wiki: all
    members at the same pillar), else the start is refused with the client's 10999 text. Members of the other
    faction get the starter's row too (the wiki: different routes per faction; not done).
0x3e9 InstantGoalPlace (TableIdx, place) from any member: a place not passed before -> 0x3ea to every member (the
    client's 0x70b750 marks the place in its mission: the post goes away for all), the passer with the row's exp per
    post, the others 0. A place passed twice (two members at once) is ignored (the official server failed the
    mission then, the wiki says). No parts every 50 posts in a party patrol (*guess*: the wiki lists them for solo
    patrols only). Every [partypatrol] bonus_posts posts of the party add bonus_seconds. Then
0xc27 S>C (18 bytes; client 0x523560): i64 cid of the member, u32 his posts, u32 time limit (s since the start). The
    client finds the member in its party list (0x521640 by cid) and shows his count in the party window (0x64f930);
    when the limit changed and the count is not 0 it shows the time added (sound 0x4ece).
0xc28 C2S (u32 post): the client picks the emergency posts itself (0x7475b0): 64 s after the start and every minute
    after, a random post of its city's quick post table near the car (0x72f280 / 0x72d0a0) -> the member's slot (his
    place in the party, 4 slots) gets that post (the client asks only with its own slot empty), and
0xc24 S>C (18 bytes; client 0x514340): i32 slots[4] (the post per member, -1 none) to every member: shown on the map
    with Officer Amy's / Member Min's call (11001 / 11002) when one is set.
0xc25 C2S (u32 slot, u32 post; client 0x742b1d): a member's car reached the post of a slot (any member may take any
    slot; the post is always -1: the client clears the slot before it reads it, 0x742b0a) -> bonus time by how fast (quick_max_seconds less one per quick_decay_seconds since it appeared, at least
    quick_min_seconds) and quick_exp x the row's exp per post to the taker (*guess*: the wiki only says faster
    pick-ups give more time), then
0xc26 S>C (32 bytes; client 0x514410): u32 slot, u32 post, u32 exp, XiStrExpInfo, u16 level, u32 time limit (s) to
    every member (exp 0 to the others): "Exp. %d" for the taker, the slot cleared, the new limit.
The end:
  - the last post (the party's places = the row's post count): to every member the row's final exp (column 15),
    the rewards, 0x3e5 InstantRewardAck (final exp; no items: they would each pop a notice), 0x3e3 (client 0x513ed0: the car's stats back, state
    0, "You've completed a Party Patrol." 11157), then
    0xc1e S>C (10 + n x 60 bytes; client 0x514560): u32 total, u32 n, n x (name 0x2a, u32 posts, u32 emergency
    posts, u16 item count, u32 item TableIdx, u32 exp): the result window (0x569ae0: the three numbers per member
    and the total as %d, the time from the patrol's start tick, the item's icon); then the patrol object is reset.
    *Guess:* which number is which (the window's labels were not read), the total = the members' exp.
    Rewards: the client's RewardGroup.xlt rw_patrol_moon / koi / cras / oros_omd / oros_roo (city of the posts;
    Oros by the row type), rows with Etc_Value 15 / 30 / 45 / 60 (Oros 3): read here as the seconds left at the
    end - the best row the party reached, else the first (*guess*); a Mittron Enhancer roll (rw_patrol_trans, rolled
    once for the count) or the Mysterious Gift Box (i_n_00085, rw_patrol_giftbox), as the wiki says (enhancers and
    boxes by city). Also the items of server_data/patrol_rewards.txt for the row.
  - time out (the limit passed, [partypatrol] grace_seconds more) -> 0x3e6 InstantFail (TableIdx) to every member
    (client 0x50ee10: stats back, "You've failed the Party Patrol." 11158).
  - a member leaves the party or the game -> 0x3e6 to the others (the wiki: a member logging out fails it).
  - 0x3e7 InstantGiveUp from a member (the client lets only the leader) -> 0x3e8 to every member ("Party Leader has
    quit the Party Patrol." 11159).
  - 0x3e6 InstantFail from a client (0x7eeea0: the client fails a mission itself, e.g. 0x70b6a0) -> 0x3e6 to all.
Licenses: GC_PartyPatrolClear / GC_Partypatrol<City> (instant.count_patrol).
"""
import asyncio
import random
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .records import pack_exp
from .. import context
from .login import SVC, send, stat_frames
from .records import name_bytes

PARTY_TYPES = ('party_move', 'party_move_ROO')
SLOTS = 4
RUN_AT = 60             # the HUD (0x652440) goes from state 1 (starting) to 2 (running) at 60 s left or less
COUNTDOWN = 8           # the start countdown: the 0x3e1 handler's start effect 0x12 runs 7.5 s (0x51fce0)
RAISE_AFTER = COUNTDOWN + 1.5   # seconds before a first limit above RUN_AT + COUNTDOWN is sent (test mode)
NOT_NOW = 'You cannot accept the Party Patrol mission in current state.'      # client GlobalText 10999
CITY_GROUP = {1: 'rw_patrol_moon', 2: 'rw_patrol_koi', 3: 'rw_patrol_cras', 4: 'rw_patrol_oros_omd'}


def is_party_row(row):
    return bool(row) and len(row) > 18 and row[10] in PARTY_TYPES


def _n(r, i):
    try:
        return int(float(r[i]))
    except (IndexError, ValueError):
        return 0


class PartyPatrol:
    """One party patrol, shared by its members (session.state['instant']['party'])."""

    def __init__(self, idx, row, members):
        self.idx, self.row = idx, row
        self.members = list(members)
        self.places = set()
        self.posts = {id(s): 0 for s in members}
        self.quick = {id(s): 0 for s in members}
        self.exp = {id(s): 0 for s in members}
        self.slots = [None] * SLOTS                 # (post, monotonic time it appeared) per member slot
        self.start = time.monotonic()
        self.limit = context.partypatrol['start_seconds']
        self.over = False
        self.task = None

    @property
    def total(self):
        return max(_n(self.row, 16), 1)

    def cast(self, *frames):
        for s in self.members:
            send(s, *frames)

    def left(self):
        return self.limit - (time.monotonic() - self.start)

    def time_frame(self, s, limit=None):
        return Frame(0xc27, struct.pack('<qII', s.state['player'].char.cid, self.posts.get(id(s), 0),
                                        int(self.limit if limit is None else limit)))

    def slot_frame(self):
        return Frame(0xc24, struct.pack('<4i', *[(x[0] if x else -1) for x in self.slots]))


def patrol_of(session):
    m = session.state.get('instant')
    return m.get('party') if m else None


def busy_reason(s, me, row):
    """Why a party member cannot start the patrol with the starter, or None (2008 chase_group's checks, the row's
    levels)."""
    from .rooms import room_of
    p = s.state.get('player')
    if not p:
        return 'not in the game'
    if p.char.city != me.state['player'].char.city or s.state.get('channel') != me.state.get('channel'):
        return 'not in this city and channel'
    if room_of(s) is not None or s.state.get('chase') or (s.state.get('instant') or {}).get('patrol'):
        return 'busy (room, chase or patrol)'
    if p.char.ptype != 'A' and not _n(row, 1) <= p.char.level <= (_n(row, 2) or 1000):
        return f'level {p.char.level} out of the mission range'
    return None


async def start(session, idx, row, solo=False):
    """0x3e0 with a party row: the patrol for the whole party (see the module docstring); solo: test mode alone."""
    from .. import admin
    from .social import party_of
    party = party_of(session)
    members = party.members if party and len(party.members) >= 2 else [session] if solo else []
    if not members:
        session.log.note(f'party patrol {idx}: no party')
        return admin.message(session, NOT_NOW)
    for s in members:
        why = busy_reason(s, session, row)
        if why:
            name = s.state['player'].char.name if s.state.get('player') else '?'
            session.log.note(f'party patrol {idx} refused: {name} {why}')
            return admin.message(session, f'{NOT_NOW} ({name}: {why})')
    pp = PartyPatrol(idx, row, members[:SLOTS])
    if solo:
        pp.limit = context.partypatrol['test_start_seconds']
    pp.limit += COUNTDOWN               # the posts and the timer start after the countdown
    for s in pp.members:
        s.state['instant'] = dict(idx=idx, places=pp.places, patrol=True, party=pp)
        s.state.pop('instant_offer', None)
        s.log.note(f'party patrol {idx} starts ({row[10]}: {len(pp.members)} members, {pp.total} posts,'
                   f' {pp.limit} s)')
        send(s, Frame(0x3e1, struct.pack('<IIB', idx, 0, 0)))
    # the HUD runs (timer, posts shown and reported) only once 60 s or less are left (RUN_AT): the first limit is
    # 60 s + the start countdown, so it runs when the countdown ends (user, 2026-10-17: posts before the countdown
    # finished); a longer one (test mode) is sent as that, then raised once running (user: the test patrol had no
    # posts and no timer with 600 s at once)
    first = min(pp.limit, RUN_AT + COUNTDOWN)
    for s in pp.members:
        send(s, pp.time_frame(s, first))
    pp.task = asyncio.ensure_future(clock(pp))
    if pp.limit > first:
        asyncio.ensure_future(raise_limit(pp))


async def raise_limit(pp):
    """The real first limit, once the members' HUDs are running (they check it every frame)."""
    await asyncio.sleep(RAISE_AFTER)
    if not pp.over:
        for s in pp.members:
            send(s, pp.time_frame(s))


async def clock(pp):
    """Fails the patrol when its time is up."""
    try:
        while not pp.over:
            await asyncio.sleep(0.5)
            if not pp.over and pp.left() < -context.partypatrol['grace_seconds']:
                for s in pp.members:
                    s.log.note(f'party patrol {pp.idx}: time up ({len(pp.places)}/{pp.total} posts)')
                end(pp, 0x3e6)
    except asyncio.CancelledError:
        pass


def end(pp, msg_type):
    """The patrol over without success: 0x3e6 InstantFail or 0x3e8 InstantGiveUp (TableIdx) to every member."""
    if pp.over:
        return
    pp.over = True
    for s in pp.members:
        if (s.state.get('instant') or {}).get('party') is pp:
            s.state.pop('instant', None)
        send(s, Frame(msg_type, struct.pack('<I', pp.idx)))
    if pp.task and pp.task is not asyncio.current_task():
        pp.task.cancel()


def member_gone(session):
    """A member leaves the party or the game (social.leave_party): the patrol fails for the others."""
    pp = patrol_of(session)
    if not pp or pp.over:
        return
    session.state.pop('instant', None)
    pp.members = [s for s in pp.members if s is not session]
    for s in pp.members:
        s.log.note(f'party patrol {pp.idx}: {session.state["player"].char.name if session.state.get("player") else "a member"}'
                   f' left, failed')
    end(pp, 0x3e6)


async def goal_place(session, pp, place):
    """0x3e9 from a member (instant.instant_goal_place)."""
    from .instant import reward_exp
    from .items import play_bonus
    from .progress import add_exp
    if pp.over or place >= pp.total or place in pp.places:
        session.log.note(f'party patrol {pp.idx}: place {place} ignored ({"over" if pp.over else "passed / out"})')
        return
    pp.places.add(place)
    pp.posts[id(session)] = pp.posts.get(id(session), 0) + 1
    c = session.state['player'].char
    exp = play_bonus(session.state['player'], reward_exp(pp.row, c.level), activity='patrol')[0]
    if exp:
        await add_exp(c, exp)
        pp.exp[id(session)] = pp.exp.get(id(session), 0) + exp
    every = context.partypatrol['bonus_posts']
    if every and len(pp.places) % every == 0 and len(pp.places) < pp.total:
        pp.limit += context.partypatrol['bonus_seconds']
    for s in pp.members:
        sc = s.state['player'].char
        send(s, Frame(0x3ea, pack_exp('<III3IHI', pp.idx, place, exp if s is session else 0, sc.exp, sc.exp_next,
                                         sc.exp_base, sc.level, 0)))
        send(s, Frame(0xc27, struct.pack('<qII', c.cid, pp.posts[id(session)], int(pp.limit))))
    if len(pp.places) >= pp.total:
        await complete(pp)


async def complete(pp):
    """The last post: final exp, rewards, 0x3e5, 0x3e3 and the result window 0xc1e to every member."""
    from .driftuse import Gains, give_item
    from .instant import count_patrol
    from .items import mod_list, play_bonus
    from .progress import add_exp, play_mode
    from .rewards import give, patrol_rewards
    pp.over = True
    if pp.task:
        pp.task.cancel()
    left = max(int(pp.left()), 0)
    units, total = [], 0
    for s in pp.members:
        p = s.state['player']
        c = p.char
        if (s.state.get('instant') or {}).get('party') is pp:
            s.state.pop('instant', None)
        final = play_bonus(p, _n(pp.row, 15), activity='patrol')[0]
        if final:
            await add_exp(c, final)
        pp.exp[id(s)] = pp.exp.get(id(s), 0) + final
        total += pp.exp[id(s)]
        await play_mode(c, 'INSTANT', exp=pp.exp[id(s)])
        await count_patrol(s, pp.row)
        gains = Gains()
        prize = reward_item(pp.row, left)
        if prize:
            await give_item(p, prize[0], prize[1], gains)
        more, given = await give(p, patrol_rewards(pp.idx))
        items = gains.items + more.items
        if items:
            send(s, mod_list(*items))
        t = context.data
        s.log.note(f'party patrol {pp.idx} done: {pp.posts.get(id(s), 0)} posts, {pp.quick.get(id(s), 0)} emergency,'
                   f' final {final} exp, {left} s left, items {prize} {[(i.item_id, n) for i, n in given]}')
        for f in stat_frames(p):
            send(s, f)
        # no items in 0x3e5: its list pops a notice per item over the result window (user, 2026-10-17); the
        # result window 0xc1e shows the prize
        send(s, Frame(0x3e5, pack_exp('<III3IHH3I', pp.idx, final, 0, c.exp, c.exp_next, c.exp_base, c.level,
                                         0, 0, 0, 0)))
        send(s, Frame(0x3e3, struct.pack('<I', pp.idx)))
        item_idx = t.item_info(t.item_index[prize[0]]).table_idx if prize else 0
        units.append(name_bytes(c.name) + struct.pack('<IIHII', pp.posts.get(id(s), 0), pp.quick.get(id(s), 0),
                                                       prize[1] if prize else 0, item_idx, pp.exp[id(s)]))
    result = Frame(0xc1e, struct.pack('<II', total, len(units)) + b''.join(units))
    pp.cast(result)


def reward_item(row, left):
    """(item id, count) from the city's rw_patrol_* group: the row with the highest Etc_Value not above the seconds
    left, else the first (see the module docstring); a nested group (rw_patrol_trans) is rolled once."""
    from .driftuse import groups, roll
    from .licenses import city_of_post
    city = city_of_post(row[18] if len(row) > 18 else '')
    group = 'rw_patrol_oros_roo' if city == 4 and row[10].endswith('_ROO') else CITY_GROUP.get(city)
    rows = sorted(groups().get(group, []), key=lambda r: r[5])
    if not rows:
        return None
    reached = [r for r in rows if r[5] <= left] or rows[:1]
    kind, item, _, count, _, _ = reached[-1]
    if kind == 'RewardGroup':
        won = [w for w in roll(item) if w[0] in ('NormalItem', 'SkidItem')]
        if not won:
            return None
        item = won[0][1]
    t = context.data
    return (item, max(count, 1)) if item in t.item_index else None


@on(SVC, C2S, 0xc28)
async def quick_post_request(session, frame):
    """0xc28 (u32 post): the member's emergency post (see the module docstring)."""
    pp = patrol_of(session)
    if not pp or pp.over or len(frame.payload) < 4 or session not in pp.members:
        return
    post, = struct.unpack_from('<I', frame.payload)
    k = pp.members.index(session)
    if pp.slots[k]:         # the client asks only with its own slot empty (0x7475b0): its slot wins
        session.log.note(f'party patrol {pp.idx}: emergency post {post} replaces {pp.slots[k][0]} in slot {k}')
    pp.slots[k] = (post, time.monotonic())
    session.log.note(f'party patrol {pp.idx}: emergency post {post} in slot {k}')
    pp.cast(pp.slot_frame())


@on(SVC, C2S, 0xc25)
async def quick_post_taken(session, frame):
    """0xc25 (u32 slot, u32 post): a member reached an emergency post -> 0xc26 to every member."""
    from .instant import reward_exp
    from .items import play_bonus
    from .progress import add_exp
    pp = patrol_of(session)
    if not pp or pp.over or len(frame.payload) < 8:
        return
    k, post = struct.unpack_from('<II', frame.payload)
    # the client clears its slot (-1) before it reads the post to send (0x742b0a / 0x742b11): the post is always
    # -1, so the slot alone says which (user, 2026-10-17: one emergency post only)
    if k >= SLOTS or not pp.slots[k]:
        return session.log.note(f'party patrol {pp.idx}: emergency post slot {k} not set')
    post = pp.slots[k][0]
    cfg = context.partypatrol
    waited = time.monotonic() - pp.slots[k][1]
    pp.slots[k] = None
    bonus = max(cfg['quick_max_seconds'] - int(waited // max(cfg['quick_decay_seconds'], 1)), cfg['quick_min_seconds'])
    pp.limit += bonus
    p = session.state['player']
    c = p.char
    exp = play_bonus(p, reward_exp(pp.row, c.level) * cfg['quick_exp'], activity='patrol')[0]
    if exp:
        await add_exp(c, exp)
        pp.exp[id(session)] = pp.exp.get(id(session), 0) + exp
    pp.quick[id(session)] = pp.quick.get(id(session), 0) + 1
    session.log.note(f'party patrol {pp.idx}: emergency post {post} (slot {k}) after {waited:.1f} s: +{bonus} s,'
                     f' {exp} exp, limit {pp.limit} s')
    for s in pp.members:
        sc = s.state['player'].char
        send(s, Frame(0xc26, pack_exp('<III3IHI', k, post, exp if s is session else 0, sc.exp, sc.exp_next,
                                         sc.exp_base, sc.level, int(pp.limit))))


# ---- test mode ------------------------------------------------------------------------------------------------
# (user, 2026-10-17: "a testing mode for party patrol, where I can check the party patrol by myself and to be able to
# complete it within the time limits"). The client shows the party pillars only to a party of 2 or more (0x62f95d), so
# a player alone accepts a solo patrol row there; in test mode that 0x3e0 starts the party row of the same city
# (the city of the posts), faction (party_move_ROO for a move_ROO row) and level band instead (the highest band
# start not above the level), with the player as the only member and [partypatrol] test_start_seconds as the first
# limit. The client builds the mission from the TableIdx in the 0x3e1 (0x70d0d0), not from what it asked for, so it
# runs the party patrol: the HUD timer, emergency posts (slot 0), the result window. Its party window has no row
# for the player (0xc27 finds no member: only the time is updated). On for everyone with [partypatrol] test = 1, or
# for one character with the GM chat command gmpartytest on | off (until he logs out).

def test_mode(session):
    return context.partypatrol['test'] or session.state.get('partypatrol_test', False)


def test_row(session, row):
    """The party row (TableIdx) a solo patrol row stands for in test mode, or None."""
    from .licenses import city_of_post
    from .social import party_of
    party = party_of(session)
    if not test_mode(session) or (party and len(party.members) >= 2) or not row or len(row) < 19:
        return None
    if row[10] not in ('move', 'move_ROO'):
        return None
    want = 'party_move_ROO' if row[10] == 'move_ROO' else 'party_move'
    city, level = city_of_post(row[18]), session.state['player'].char.level
    rows = context.data.instants
    found = [(i, r) for i, r in enumerate(rows) if is_party_row(r) and r[10] == want and city_of_post(r[18]) == city
             and _n(r, 1) <= level]
    if not found and want == 'party_move_ROO':          # no ROO party row for this city / level: the OMD one
        found = [(i, r) for i, r in enumerate(rows) if is_party_row(r) and city_of_post(r[18]) == city and _n(r, 1) <= level]
    if not found:
        return None
    band = max(_n(r, 1) for _, r in found)
    same_post = [i for i, r in found if _n(r, 1) == band and r[17] == row[17]]
    return same_post[0] if same_post else next(i for i, r in found if _n(r, 1) == band)


def gm_test(session, args):
    """gmpartytest on | off | (nothing: status)."""
    word = (args[0].lower() if args else '')
    if word in ('on', '1'):
        session.state['partypatrol_test'] = True
    elif word in ('off', '0'):
        session.state['partypatrol_test'] = False
    on_ = test_mode(session)
    return (f'party patrol test mode {"on" if on_ else "off"}'
            + (' (emulator.ini [partypatrol] test = 1)' if context.partypatrol['test'] else '')
            + (f': accept a patrol at a pillar alone, {context.partypatrol["test_start_seconds"]} s to start' if on_ else ''))
