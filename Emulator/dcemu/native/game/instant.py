"""Instant missions: patrols and the mission girls' tasks (batch 3 of the native game).

Rows: the 2011 Instant_Client.tdf by TableIdx (data.Tables.instants). Its columns are the 2008
Instant_Server.tdf's (XiInstantTable::LoadFile) with two after the level range and a description
added, and no reward item group: 0 category (instant / patrol / day_mission), 1 min level, 2 max
level, 5 summary, 7 repeat, 8 percent, 9 dialog, 10 type (move, party_move, battle, combo, ...),
11 value, 12 mission item, 13 reward Mito, 14 reward exp, 15 final exp, 16 posts to patrol,
17 the giver's post, 18.. the posts. The 2011 table has 147 rows to the 2008 server's 99 (new
party patrols and mission battles in between), so the 2008 server knew no 2011 index past the
first new row ("Cannot find a Courier service request" for a recorded patrol).

0x3e0 InstantStart (TableIdx; 2011 + 8 bytes) -> 0x3e1 (TableIdx; 2011 + u32 0, u8 0: without them the
    client reads on into the stream). XiCsCharInfo::InstantStart: the row exists and the level is in
    its range (accounts with PType 'A' excepted), else 20020 NotFoundInstant; the new mission
    replaces the current one. Kept for the session, as the 2008 server did (XiCsInstant).
0x3e9 InstantGoalPlace (TableIdx, place) -> 0x3ea (TableIdx, place, u32 exp, XiStrExpInfo, u16 level,
    u32 InvenIdx of an item given, else 0). XiCsCharInfo::InstantGoalPlace 0x5d6610: the current
    mission, a place below the post count not reached before; the reward exp of the row each time
    (column order from XiInstantTable::LoadFile 0x64f3bb: Mito, exp, final exp - a patrol gives 1 or 2
    exp per post; until 2026-10-13 Mito and exp were swapped here and posts gave 0, shown as "{} exp")
    (0 for patrols); patrols give an item at the 50th, 100th, 150th and 160th place, from the
    groups of InstantDrop_Server.tdf (server_data; row by level, columns 1-4), the parts' level as the client's
    InstantDrop_Client.tdf says (data.Tables._client_patrol_drops) -> 0x192. Completing it: the items of
    Emulator/server_data/patrol_rewards.txt (rewards.py).
0x3e2 InstantComplete (TableIdx) -> 0x3e5 InstantRewardAck (TableIdx, exp, Mito, XiStrExpInfo, u16 level, u16
    items 0, u32 x3), then 0x3e3 (TableIdx). INSTANT_ORDER: 0x3e5 first, as the 2008 server (Cmd_InstantComplete
    0x607e41, 0x60807e): the client's 0x3e5 handler (0x514120) needs the mission object (0x70b820) for the exp, the
    "Instant Mission Complete" banner and the result window (0x73ca10), and 0x3e3 (0x70d7c0) frees it. Sent the other
    way round until 2026-10-14: no banner (user). XiCsCharInfo::InstantComplete 0x5cb190: the
    current mission; reward exp and Mito of the row ("INSTANT" play mode). A patrol ends at its last
    post instead (0x3e9 above): 0x3ea, then 0x3e5 with the final exp, as the 2008 server did; the
    client sends no 0x3e2 for it. Day missions (category day_mission: token events, BS_PktDayMissionCompleteAck)
    are kept apart (session 'day_mission') and completed in daymission.py.
0x3e7 InstantGiveUp (TableIdx) -> 0x3e8 (TableIdx).

**Offers (2011, GlobalContent NewInstant = 1).** 0x3df InstantRequestAck (u32 TableIdx, u32 a, u32 b; client
0x513c50): the client keeps the mission as offered (with the player's "Show instant messages" option on: the call-sign
notice, dialog 760000 ID_INSTANTMISSION_*, with the TAB button 760007 and Cancel); TAB opens the mission dialog
(0x5f1c20), accepting sends 0x3e0 (TableIdx, b, a: the two values come back, sender 0x7eeaa0 from 0x579b9e). Offers:
  - 0x3de InstantRequest (u32 post, u32 flag; client 0x7ee940): the request house's "Instant Quest" button (dialog
    280000, control 280005, flag 1; post = [[0x95c904]+0x84]). 2008 PacketParser::Cmd_InstantRequest /
    XiInstantTable::InstantRequest: a roll in 0-99 against the running sum of the eligible rows' percent (column 8)
    in table order (level in range, not a day mission, a giver post only at that post), else the last eligible row.
    Here the classic rows (category instant, columns 3 / 4 = 0, no giver); NotFoundInstant 20020 without one.
  - city offers (2011 context rows, column 3 the faction, column 4 where: City / Battle_Room / Battle_Lobby /
    Chasing / QuestFail5; rewards are formulas, column 14): every [instant] city_offer_minutes while driving in a
    city field (not the Driver Dome: in_field) with no mission, a City row (skill passes, combos, HUV arrests) by its percent (city_offers). The other
    contexts are not offered yet.
"""
import asyncio
import re
import random
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .combo import take
from .items import add_money, mod_list, play_bonus
from .login import SVC, error, send, stat_frames
from .progress import add_exp, play_mode

PATROL_TYPES = {'move', 'party_move', 'move_ROO', 'party_move_ROO', 'move_event'}
DROP_AT = {50: 1, 100: 2, 150: 3, 160: 4}       # places reached -> InstantDrop_Server column
# Items for completing a patrol: the client's tables have none; Emulator/server_data/patrol_rewards.txt (rewards.py; user,
# 2026-10-14; was emulator.ini [patrol] prize / prize_count). Listed in 0x3e5 by **TableIdx** (at most 3) (u16 count, u32 TableIdx each; client 0x514120
# looks each up with 0x7172f0 as 0x2e5 does, then 0x739f70(item, 1): chat line + pick-up icon, and a notice; the count
# shown is always 1, so each item is listed once and the inventory gets its count). The first version sent the
# InvenIdx: the client showed TableIdx 1065 (Ch 03. Battle Ghost Ticket).


def _n(r, i):
    try:
        return int(float(r[i]))
    except (IndexError, ValueError):
        return 0


def current(session, table_idx):
    m = session.state.get('instant')
    return m if m and m['idx'] == table_idx else None


CLASSIC, CITY = '0', 'City'


def eligible(row, level, where):
    """A row offered at a request house (where = CLASSIC) or in a context (City, ...) for this level."""
    if not row or len(row) < 18 or row[0] != 'instant' or row[17] not in ('n/a', ''):
        return False
    if (row[4] if where != CLASSIC else row[3] + row[4]) != (where if where != CLASSIC else '00'):
        return False
    return _n(row, 1) <= level <= (_n(row, 2) or 1000)


def pick(level, where):
    """2008 XiInstantTable::InstantRequest: a roll in 0-99 against the running sum of the percents, else the last.
    The 2011 table's classic rows all end at level 1000 (2008: 4-7, 8-12, ... 56-1000), so only the band with the
    highest start not above the level counts, as the 2008 bands did."""
    rows = context.data.instants
    starts = [_n(r, 1) for r in rows if eligible(r, level, where)]
    band = max(starts) if starts and where == CLASSIC else None
    roll, total, last = random.randrange(100), 0.0, None
    for idx, row in enumerate(rows):
        if not eligible(row, level, where) or (band is not None and _n(row, 1) != band):
            continue
        last = idx
        try:
            total += float(row[8])
        except ValueError:
            pass
        if roll < total:
            return idx
    return last


def offer(session, idx, a=0, b=0):
    """0x3df: the mission offered (the client echoes a / b in its 0x3e0)."""
    session.state['instant_offer'] = idx
    session.log.note(f'instant offer {idx}: {context.data.instants[idx][5]}')
    send(session, Frame(0x3df, struct.pack('<III', idx, a, b)))


@on(SVC, C2S, 0x3de)
async def instant_request(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    post, flag = struct.unpack_from('<II', frame.payload.ljust(8, b'\0'))
    idx = pick(p.char.level, CLASSIC)
    session.log.note(f'instant request at post {post} (flag {flag}): {idx}')
    if idx is None:
        return error(session, '20020')                  # NotFoundInstant
    offer(session, idx, flag, post)


def in_field(session):
    """Whether the player's car is in a city field area (area.py; areas 0-3 are the Driver Dome / tutorial, where the
    client starts after logging in: city_traffic.area_city gives None there). The area is on the player's area
    connection, found by the game serial."""
    from ..area import worlds
    from ..city_traffic import area_city
    serial = session.state.get('serial')
    for cars in worlds['area'].areas.values():
        for car in cars.values():
            if car.serial == serial and car.area is not None:
                return area_city(car.area) is not None
    return False


@on_open(SVC)
async def city_offers(session):
    """Every [instant] city_offer_minutes: a City mission offered to a player driving in the city with none running."""
    from .position import IN_CITY
    while True:
        minutes = context.instant_city_minutes
        await asyncio.sleep(max(minutes, 1) * 60)
        p = session.state.get('player')
        if not minutes or not p:
            continue
        # position state 2 or more = past the tutorial (the client saves 3 in the city: 0xa2; checking == 2 here
        # offered nothing, user 2026-10-14)
        busy = [k for k in ('instant', 'room', 'chase') if session.state.get(k)]
        if not busy and not in_field(session):       # not in the Driver Dome (user, 2026-10-15)
            busy = ['not in the field']
        if busy or p.char.pos_state < IN_CITY:
            session.log.note(f'city instant offer skipped: {busy or "position state " + str(p.char.pos_state)}')
            continue
        level, where = city_offer_kind(p.char.level)
        if where == CITY:
            from .licenses import faction       # the City rows are OMD's (column 3): a ROO driver gets the request
            if faction(p) == 'ROO':             # house band instead
                where = CLASSIC
        idx = pick(level, where)
        if idx is not None:
            offer(session, idx)


CITY_MIN_LEVEL = 56     # the request house's top band (classic rows 73-76 start at 56)


def city_offer_kind(level):
    """(level, where) for a city offer: the 2011 City rows (100 skill passes, 500 combos, 30 HUVs) are one size for
    every level, so below the top band the player's request-house band is offered instead (user, 2026-10-15: a level 2
    character got "Accumulate 500 Combos"); below level 4 (the first band) nothing."""
    return (level, CITY) if level >= CITY_MIN_LEVEL else (level, CLASSIC)


def reward_exp(row, level):
    """Column 14: a number, or a 2011 formula of {Level} (INT((({Level}^1.7)/5+10)); formulas with other values
    (battle / chase rewards) give 0 here."""
    text = row[14] if len(row) > 14 else ''
    try:
        return int(float(text))
    except ValueError:
        pass
    expr = text.replace('{Level}', str(level)).replace('^', '**').replace('INT', 'int').replace('[', '(').replace(']', ')')
    if not re.fullmatch(r'[0-9+\-*/(). int]*', expr):
        return 0
    try:
        return max(int(eval(expr, {'__builtins__': {}}, {'int': int})), 0)
    except Exception:
        return 0


@on(SVC, C2S, 0x3e0)
async def instant_start(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    idx, = struct.unpack_from('<I', frame.payload)
    rows, c = context.data.instants, p.char
    row = rows[idx] if 0 <= idx < len(rows) else None
    if not row or (c.ptype != 'A' and not _n(row, 1) <= c.level <= (_n(row, 2) or 1000)):
        session.log.note(f'instant start {idx}: refused')
        return error(session, '20020')
    if row[0] == 'day_mission':     # today's day mission (the client starts it at login): kept apart from the
        session.state['day_mission'] = idx      # instant mission, which may run at the same time (daymission.py)
    else:
        session.state['instant'] = dict(idx=idx, places=set(), patrol=row[10] in PATROL_TYPES)
    session.state.pop('instant_offer', None)
    session.log.note(f'instant start {idx} ({row[10]}: {row[5]})')
    send(session, Frame(0x3e1, struct.pack('<IIB', idx, 0, 0)))


@on(SVC, C2S, 0x3e9)
async def instant_goal_place(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    idx, place = struct.unpack_from('<II', frame.payload)
    m = current(session, idx)
    row = context.data.instants[idx] if m else None
    if not m or place >= max(_n(row, 16), 1) or place in m['places']:
        return error(session, '20020')
    m['places'].add(place)
    c, t = p.char, context.data
    exp = play_bonus(p, reward_exp(row, c.level), activity='patrol' if m['patrol'] else None)[0]
    if exp:
        await add_exp(c, exp)
    inven = 0
    col = DROP_AT.get(len(m['places'])) if m['patrol'] else None
    if col:
        groups = t.instant_drop(c.level)
        items = t.drop_groups.get(groups[col - 1]) if len(groups) >= col else None
        info = t.item_info(random.choice(items)) if items else None
        if info:
            change = await take(p, info)
            inven = change[0].inven_idx
            send(session, mod_list(change))
    send(session, Frame(0x3ea, struct.pack('<III3IHI', idx, place, exp, c.exp, c.exp_next, c.exp_base, c.level, inven)))
    if m['patrol'] and len(m['places']) >= _n(row, 16):
        # the last post ends the patrol here: the client sends no 0x3e2 for it (user, 2026-10-13: the
        # mission did not end). 2008 Cmd_InstantGoalPlace 0x606528: 0x3e5 InstantRewardAck with the
        # final exp (Mito 0) after the 0x3ea, and the mission is gone.
        final = play_bonus(p, _n(row, 15), activity='patrol')[0]
        if final:
            await add_exp(c, final)
        session.state.pop('instant', None)
        await play_mode(c, 'INSTANT', exp=exp + final)
        await count_patrol(session, row)
        from .rewards import give, patrol_rewards
        gains, given = await give(p, patrol_rewards(idx))
        if gains.items:
            send(session, mod_list(*gains.items))
        prizes = [i.table_idx for i, _ in given][:3]
        session.log.note(f'patrol {idx} done: {len(m["places"])} posts, final {final} exp,'
                         f' items {[(i.item_id, n) for i, n in given]}')
        for f in stat_frames(p):
            send(session, f)
        send(session, Frame(0x3e5, struct.pack('<III3IHH3I', idx, final, 0, c.exp, c.exp_next, c.exp_base, c.level,
                                               len(prizes), *(prizes + [0, 0, 0])[:3])))


async def count_patrol(session, row):
    """Licenses: a patrol cleared - GC_PatrolClear / GC_Patrol<City> alone, GC_PartyPatrolClear / GC_Partypatrol<City> for a
    party patrol (type party_move*); the city of its posts (column 18 on)."""
    from .licenses import CITY_SUFFIX, city_of_post, count_many
    city = CITY_SUFFIX.get(city_of_post(row[18] if len(row) > 18 else ''), ('',))[0]
    if row[10].startswith('party_'):
        names = ['PartyPatrolClear'] + ([f'Partypatrol{city}'] if city else [])
    else:
        names = ['PatrolClear'] + ([f'Patrol{city}'] if city else [])
    await count_many(session, names)


@on(SVC, C2S, 0x3e2)
async def instant_complete(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    idx, = struct.unpack_from('<I', frame.payload)
    rows = context.data.instants
    if 0 <= idx < len(rows) and rows[idx] and rows[idx][0] == 'day_mission':
        from .daymission import complete
        return await complete(session, p, idx)
    m = current(session, idx)
    if not m:
        return error(session, '20020')
    row, c = context.data.instants[idx], p.char
    session.state.pop('instant', None)
    exp, money = reward_exp(row, c.level), _n(row, 13)
    if m['patrol'] and len(m['places']) >= _n(row, 16):
        exp += _n(row, 15)
    exp, money = play_bonus(p, exp, money, 'patrol' if m['patrol'] else None)
    if exp:
        await add_exp(c, exp)
    if money:
        await add_money(c, money)
    await play_mode(c, 'INSTANT', exp=exp, money=money)
    if m['patrol'] and len(m['places']) >= _n(row, 16):
        await count_patrol(session, row)
    session.log.note(f'instant complete {idx}: {exp} exp, {money} mito ({len(m["places"])} places)')
    for f in stat_frames(p):
        send(session, f)
    send(session, Frame(0x3e5, struct.pack('<III3IHH3I', idx, exp, money, c.exp, c.exp_next, c.exp_base, c.level, 0,
                                           0, 0, 0)))
    send(session, Frame(0x3e3, struct.pack('<I', idx)))     # after 0x3e5: see INSTANT_ORDER


@on(SVC, C2S, 0x3e7)
async def instant_give_up(session, frame):
    if len(frame.payload) < 4:
        return
    idx, = struct.unpack_from('<I', frame.payload)
    if not current(session, idx):
        return error(session, '20020')
    session.state.pop('instant', None)
    send(session, Frame(0x3e8, struct.pack('<I', idx)))
