"""HUV chases: the HUV Call Unit and police chases (batch 3 of the native game).

HUVs: the 2011 HuvTable.tdf (server_data/tables; data.Tables.huvs), which carries the server's columns
(ChaseTable::ReloadChaseTable 0x671970): 0 level, 1 id (body type + 10000), 2 name, 3 rate, 4 most
HUVs (Ea), 5 speed, 6 max speed, 7 boost accel, 8 boost time, 9 boost refresh, 10 durability,
13-15 front player / front traffic / rear player avoidance, 16 exp, 17 Mito, 18 item group, 19 drop
rate (%). The 2008 server used the TW table, whose ids differ (B-Monster S at level 70: TW 10035,
2011 10017): that is why a HUV call through the proxy did nothing (user, 2026-10-12) - the client got
a HUV it does not have.

0xbd ChaseRequest (u8 now, XiVec4 position; refused during a patrol instant mission) -> 0xba ChasePropose (u16 serial, XiVec4 start 0, XiVec4
    end 0 (the client picks a spawn), i32 type: now 1 / 2, i32 course 0, i32 HUV level, i32 HUV id,
    wchar[100] "test"). BS_GameDispatch::SendChasePropose 0x5b77a0: level = the character's (the
    highest table level not above it here), the HUV by rate among the first rows whose rates make
    100 (the regular HUVs; later rows at a level are event HUVs, High Cannon, ...).
0xb4 ChaseBegin (i32 type: 0 a HUV call, else the quest's TableIdx; XiVec4 start, i32 level, i32 id, i32 HUV count:
    0 for a call, the quest's count) -> 0xb5 ChaseBeginConfirm
    (XiVec4 start, u8 accepted 1, i32 find timeout, i32 arrest timeout, u16 n, n x 48: u16 serial (the
    player's), u16 car sort (the HUV's id here), i32 level, i32 id, f32 speed, max speed, boost accel,
    boost time, boost refresh, durability, front player, front traffic, rear player avoidance; same as
    2008). HUV count by players in the chase (user, 2026-10-13): 1: 1-4, 2: 2-6, 3: 3-8, 4: 4-12 at
    random (Cmd_ChaseBegin 0x5f6a40 had 1-4 / 3-6 / 5-8 / 7-10, then up to the row's Ea, at most 8;
    the asked count when type > 0); both timeouts = timeTable[n - 1][players - 1] minutes (ZoneServer
    0x701480; counts past 10 use row 10).
    **Party chases** (2008 PacketParser::Cmd_ChaseBegin 0x5f6a40): the caller's party members in the same
    city and channel, not in a room / chase / instant mission, chase together (fewer than 2: alone). HUV k
    belongs to member k mod n (its unit's serial) and has that member's level (GetChasePartyHuvLevel 0x5eb4c0:
    each member's HUVs at his level; user, 2026-10-15); the caller's HUVs are the one he was offered. The
    same 0xb5 goes to every member.
0xb9 ChaseProgress (u16 serial, u16 target serial, u16 target sort, i32 time, i32 state): sent with the
    sender's serial to every chase member, the sender too (Cmd_ChaseProgress 0x5f0180).
0xbb ChaseHit (44 bytes): a drop roll in mode 0 (0x2e5 + 0x192); to the other chase members with the sender's
    serial @0 (Cmd_ChaseHit 0x609910), nothing alone.
0xb7 ChaseEnd (u16 serial, u16 sort, u32 type, f32 life, u32 result, XiVec4 pos, XiVec4 vel, i32 time)
    -> 0xb8 ChaseResult (2011: u32 result, i32 time ms, u16 units, 32 bytes more (0 here; client
    0x51a230 reads the units from 0x2a), units of XiChaseResultInfo (124: name, serial, sort,
    i32 HUV Mito, i32 bonus Mito, i64 Mito, u32 HUV exp, u32 bonus exp, XiStrExpInfo, u32 level, f32
    point, u32 items, u32 x2 item TableIdx)). Serial 0: that player gives up (or his time ran out): his HUVs
    end, he leaves the chase and gets his own 0xb8 (2008 EndAllHuvs + BS_Party::RemoveChaseMember). Else the
    HUV (serial, sort) ends, and when caught (result 1) gives its exp and Mito to the player who sent it (the
    2008 server added a bonus from "HUV option" formulas; not here) and an item of its group at its drop
    rate. 0xb8 only when no HUV is left: to every member, a unit per member with what he earned.
"""
import random
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .records import pack_exp
from .. import context
from .combo import drop, take, take_if_room
from .items import add_money, mod_list, play_bonus
from .login import SVC, error, send, stat_frames
from .progress import add_exp, play_mode
from .records import wstr

# ZoneServer timeTable[HUV count - 1][players - 1] (0x701480), minutes for finding / arresting
TIME_TABLE = ((2, 2, 2, 2), (3, 2, 2, 2), (4, 3, 3, 3), (5, 3, 3, 3), (5, 4, 3, 3),
              (5, 5, 3, 3), (5, 5, 4, 3), (5, 5, 5, 3), (5, 5, 5, 4), (5, 5, 5, 5))
# HUVs per call by the number of players in the chase (user, 2026-10-13); the 2008 server used 1-4
# alone, 3-6 / 5-8 / 7-10 with 2 / 3 / 4 players, then up to the row's Ea, at most 8.
HUV_COUNT = {1: (1, 4), 2: (2, 6), 3: (3, 8), 4: (4, 12)}
RESULT_HEAD_2011 = 32
UNIT = 124


def huv_rows(level):
    rows = context.data.huvs
    lv = max((r['level'] for r in rows if r['level'] <= level), default=None)
    if lv is None:
        lv = min((r['level'] for r in rows), default=0)
    return [r for r in rows if r['level'] == lv]


def huv(level, huv_id):
    """The HUV of that id at that level; else the same HUV at the nearest level the table has (a quest asks for its
    own level: nq_00001 wants B-Hex S 10015 at 75, which HuvTable.tdf has at 71, 73 and 78; user, 2026-10-16)."""
    same = [r for r in context.data.huvs if r['id'] == huv_id]
    exact = next((r for r in same if r['level'] == level), None)
    if exact or not same:
        return exact
    return min(same, key=lambda r: (abs(r['level'] - level), r['level'] > level))


@on(SVC, C2S, 0xbd)
async def chase_request(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 1:
        return
    now = frame.payload[0]
    m = session.state.get('instant')
    if m and m.get('patrol'):                   # no HUV calls during a patrol (user, 2026-10-13)
        session.log.note('chase request refused: patrol in progress')
        return error(session, 'You cannot call a HUV during a patrol.')
    if is_roo(p) and not call_units(p):
        session.log.note('chase request refused: ROO member without a HUV Call Unit')
        return error(session, 'ROO drivers need a HUV Call Unit (parts shop) to receive HUV calls.')
    r = pick_huv(p.char.level)
    if not r:
        return
    serial = session.state.get('serial', 0)
    session.log.note(f'chase request: HUV {r["id"]} {r["name"]} level {r["level"]}')
    send(session, Frame(0xba, struct.pack('<H4f4fiiii', serial, *(0.0,) * 8, 1 if now else 2, 0, r['level'], r['id'])
                        + wstr('test', 200)))


# Factions (2011; the 2008 server had none): the Oros quest "Choice" (#126) leads to "Team ROO Headquarters" (#127, ROO)
# or "Patrol Oros City" (#145, OMD); the side is the one taken (licenses.faction, QuestClient column 5). A ROO driver
# receives HUV calls only with a HUV Call Unit (i_n_00063, use kind vc_C_callunit, 1000 Mito in the parts shop: "Allows
# ROO players to receive HUV Call Signs. 1 Consumed when call accepted."); one is used up when the call's chase begins.
CALL_UNIT = 'i_n_00063'


def is_roo(p):
    from .licenses import faction
    return faction(p) == 'ROO'


def call_units(p):
    from .items import info_of
    return [it for it in p.items if (info := info_of(it)) and info.item_id == CALL_UNIT and it.stack > 0]


async def use_call_unit(session, p):
    """One HUV Call Unit used up (as items.use_item does) -> False if none is held."""
    from .items import CHANGED, DELETE_SQL, REMOVED, STACK_SQL
    held = call_units(p)
    if not held:
        return False
    it, db, c = held[0], context.db, p.char
    it.stack -= 1
    if it.stack:
        await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
        state = CHANGED
    else:
        await db.execute(DELETE_SQL, (db.server_id, c.cid, it.inven_idx))
        p.items.remove(it)
        state = REMOVED
    send(session, mod_list((it, state)))
    session.log.note(f'HUV Call Unit used ({it.stack} left)')
    return True


def pick_huv(level):
    """A HUV for a player of this level: the first set of rows whose rates make 100 (the regular HUVs; later
    sets at a level are event HUVs, High Cannon, ...), one of them by rate."""
    rows, total = [], 0.0
    for r in huv_rows(level):
        if r['rate'] > 0 and total < 100:
            rows.append(r)
            total += r['rate']
    return random.choices(rows, weights=[max(x['rate'], 0.001) for x in rows])[0] if rows else None


class Chase:
    """One chase, shared by its members (session.state['chase'])."""

    def __init__(self, members):
        self.members = list(members)
        self.huvs = {}                          # (owner serial, sort) -> (HUV row, owner session)
        self.got = {id(s): dict(exp=0, money=0, items=[], caught=0) for s in members}
        self.start = time.monotonic()

    def cast(self, frame, but=None):
        for s in self.members:
            if s is not but:
                send(s, frame)


def chase_group(session):
    """The caller and the party members chasing with him (2008 Cmd_ChaseBegin's AddChaseMember checks)."""
    from .rooms import room_of
    from .social import party_of
    party = party_of(session)
    if not party:
        return [session]
    me = session.state['player'].char
    group = [session]
    for s in party.members:
        p = s.state.get('player')
        if (s is session or not p or s.state.get('chase') or room_of(s) is not None
                or (s.state.get('instant') or {}).get('patrol')
                or p.char.city != me.city or s.state.get('channel') != session.state.get('channel')):
            continue
        group.append(s)
    return group


@on(SVC, C2S, 0xb4)
async def chase_begin(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 32:
        return
    kind, x, y, z, w, level, huv_id, asked = struct.unpack_from('<i4fiii', frame.payload)
    r = huv(level, huv_id)
    if not r:
        session.log.note(f'chase begin: no HUV {huv_id} at level {level}')
        return send(session, Frame(0xb5, struct.pack('<4fBiiH', x, y, z, w, 0, 0, 0, 0)))
    if kind == 0 and is_roo(p) and not await use_call_unit(session, p):    # a HUV call accepted by a ROO driver
        session.log.note('chase begin refused: ROO member without a HUV Call Unit')
        error(session, 'ROO drivers need a HUV Call Unit (parts shop) to receive HUV calls.')
        return send(session, Frame(0xb5, struct.pack('<4fBiiH', x, y, z, w, 0, 0, 0, 0)))
    members = chase_group(session)
    players = len(members)
    quest = kind > 0                    # a quest's chase: the quest's row and its HUV count (ordinary calls: 0, 0)
    n = max(1, min(asked, 12)) if quest else random.randint(*HUV_COUNT[min(players, 4)])
    timeout = TIME_TABLE[min(n, len(TIME_TABLE)) - 1][min(players, 4) - 1] * 60
    chase = Chase(members)
    picks = {id(session): r}
    units = b''
    for k in range(n):
        owner = members[k % players]
        row = picks.get(id(owner))
        if row is None:
            row = picks[id(owner)] = r if quest else pick_huv(owner.state['player'].char.level) or r
        serial, sort = owner.state.get('serial', 0), k + 1
        chase.huvs[(serial, sort)] = (row, owner)
        units += struct.pack('<HHii9f', serial, sort, row['level'], row['id'], row['speed'], row['max_speed'],
                             row['nos_accel'], row['nos_time'], row['nos_refresh'], row['durability'],
                             row['avoid_front_player'], row['avoid_front_traffic'], row['avoid_rear_player'])
    for s in members:
        s.state['chase'] = chase
    names = ', '.join(f'{s.state["player"].char.name} ({picks[id(s)]["name"]} L{picks[id(s)]["level"]})'
                      for s in members if id(s) in picks)
    session.log.note(f'chase begin: {n} HUVs for {players} player(s): {names}, {timeout} s'
                     + (f' (quest {context.data.quests[kind][0] if kind < len(context.data.quests) else kind})' if quest else ''))
    chase.cast(Frame(0xb5, struct.pack('<4fBiiH', x, y, z, w, 1, timeout, timeout, n) + units))


@on(SVC, C2S, 0xb9)
async def chase_progress(session, frame):
    chase = session.state.get('chase')
    if chase and len(frame.payload) >= 2:
        chase.cast(Frame(0xb9, struct.pack('<H', session.state.get('serial', 0)) + frame.payload[2:]))


@on(SVC, C2S, 0xbb)
async def chase_hit(session, frame):
    p = session.state.get('player')
    chase = session.state.get('chase')
    if not p or not chase:
        return
    if len(chase.members) > 1 and len(frame.payload) >= 2:
        chase.cast(Frame(0xbb, struct.pack('<H', session.state.get('serial', 0)) + frame.payload[2:]), but=session)
    f, changes = await drop(p, 0)
    send(session, f)
    if changes:
        send(session, mod_list(*changes))


def result_unit(session, p, money=0, exp=0, items=()):
    c = p.char
    idx = list(items)[:2]
    return (wstr(c.name, 64) + pack_exp('<HHiiqII3IIfI', session.state.get('serial', 0), 0, money, 0, c.mito, exp, 0,
                                           c.exp, c.exp_next, c.exp_base, c.level, 0.0, len(idx))
            + struct.pack('<2I', *(idx + [0] * (2 - len(idx)))))


@on(SVC, C2S, 0xb7)
async def chase_end(session, frame):
    """One HUV ends (caught: result 1, or got away), or the sender's whole chase (serial 0: given up / time
    out). As Cmd_ChaseEnd 0x609b70: 0xb8 ChaseResult only when no HUV is left (a party's HUV count +0x104 = 0),
    with what each member earned. (Sending 0xb8 for every HUV made the client end the chase at the first one:
    user, 2026-10-13 "killing one HUV kills all".)"""
    p = session.state.get('player')
    chase = session.state.get('chase')
    if not p or not chase or len(frame.payload) < 16:
        return
    serial, sort, kind, life, result = struct.unpack_from('<HHIfI', frame.payload)
    if serial == 0:
        session.log.note(f'chase end: {p.char.name} stops (result {result})')
        await leave_chase(session, result)
        return
    key = (serial, sort)
    if key in chase.huvs:
        r, _ = chase.huvs.pop(key)
        if result == 1:
            await catch(session, chase, r)
        session.log.note(f'chase end: HUV {key} result {result}, {len(chase.huvs)} left')
    if not chase.huvs:
        await finish(chase, chase.members, result, cleared=True)


async def catch(session, chase, r):
    """A caught HUV's exp, Mito and drop for the player who caught it."""
    p, t = session.state['player'], context.data
    c = p.char
    got = chase.got[id(session)]
    exp, money = play_bonus(p, r['exp'], r['money'], 'chase')
    if exp:
        await add_exp(c, exp)
    if money:
        await add_money(c, money)
    group = t.drop_groups.get(r['item_group'])
    from .licenses import drop_bonus
    if group and random.uniform(0, 100) < r['drop_rate'] * (100 + drop_bonus(p)) / 100:
        info = t.item_info(random.choice(group))
        change = await take_if_room(p, info) if info else None     # nothing when the inventory is full
        if change:
            got['items'].append(info.table_idx)
            send(session, mod_list(change))
    got['exp'] += exp
    got['money'] += money
    got['caught'] += 1
    for f in stat_frames(p):
        send(session, f)


async def finish(chase, who, result, cleared=False):
    """0xb8 to these members (units for all of them), and they leave the chase. cleared: no HUV left (not given up):
    a member who caught one has cleared a HUV round (licenses: GC_ChasingClear, per city, party)."""
    who = list(who)
    ms = int((time.monotonic() - chase.start) * 1000)
    units = b''
    for s in who:
        p, got = s.state['player'], chase.got[id(s)]
        await play_mode(p.char, 'CHASE', wins=1 if got['caught'] else 0, exp=got['exp'], money=got['money'])
        s.log.note(f'chase over: {got["caught"]} caught, {got["exp"]} exp, {got["money"]} mito, items {got["items"]}')
        if cleared and got['caught']:
            from .licenses import CITY_SUFFIX, count_many
            sfx = CITY_SUFFIX.get(p.char.city, ('', '', ''))[1]
            names = ['ChasingClear'] + ([f'ChasingClear_{sfx}'] if sfx else [])
            if len(chase.members) > 1:
                names += ['PartyChasingClear'] + ([f'PartyChasingClear_{sfx}'] if sfx else [])
            await count_many(s, names)
        units += result_unit(s, p, got['money'], got['exp'], got['items'])
    frame = Frame(0xb8, struct.pack('<IiH', result, ms, len(who)) + bytes(RESULT_HEAD_2011) + units)
    for s in who:
        if s.state.get('chase') is chase:
            s.state.pop('chase', None)
        if s in chase.members:
            chase.members.remove(s)
        send(s, frame)


async def leave_chase(session, result=0, closing=False):
    """The player stops chasing (gave up, time out; closing: left the game): his HUVs end, he gets his own
    result; the others go on, or finish when no HUV is left."""
    chase = session.state.get('chase')
    if not chase:
        return
    for key in [k for k, (_, owner) in chase.huvs.items() if owner is session]:
        chase.huvs.pop(key)
    if not closing:
        await finish(chase, [session], result)
    else:
        session.state.pop('chase', None)
        if session in chase.members:
            chase.members.remove(session)
    if chase.members and not chase.huvs:
        await finish(chase, list(chase.members), result)
