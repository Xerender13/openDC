"""Mother quests and the Mitro City (Taipei) reputations (2011; no 2008 server code: the client's handlers and
server_data/Init/MotherQuest.xlt).

MotherQuest.xlt (38 rows, the client's table index = the row, 0-based): id (mq_5th_001 .. 020 the main story, _m the
Mafia branch, _c the City Hall branch; sq_5th_001 .. 018 the repeatable sub quests), level needed, car grade needed (9 =
the car driven must be V9: user), previous mother quest, reputation kind + the least reputation needed,
repeat flag, up to 4 child quests (QuestClient nq_*; the client starts them itself with 0x106 QuestStart when the
mother quest is accepted, client 0x7ebf10 for children flagged at +0x911, and they run as ordinary quests, quests.py),
start / end post, up to 4 rewards (exp, mito, reputation "GC_Reputation_0N amount").

  0x17d MotherQuestStart (u32 row) -> 0x17e (u32 row): client 0x513310 adds it to its list and starts the children;
        "To Mitro City" (mq_5th_003) also makes it send 0xc80 for Mitro City (position.py: city travel).
  0x17f MotherQuestComplete (u32 row) -> 0x180 (u32 row): client 0x513460 shows the done message; the rewards come
        as 0x7d1 (exp), 0x7d2 (Mito), 0x7d4 (reputation).
  0x181 MotherQuestGiveUp (u32 row, u32 1 = a child quest failed (client 0x5138b0, after its 0x10d) / 0 = given up
        (0x513a70, after 0x10f)) -> 0x182 (u32 row): the client's handler 0x50ed80 only refreshes its window and never
        drops the mother quest from its held list, so the NPC would not offer it again until the next login (user:
        Mitro City missions not repeatable after failing); 0x17c is sent again after it (0x754fb0 clears and rebuilds
        the list).
  0x17c MyMotherQuestList (u32 n, n x (u32 row, u32 flag)) at login: the client's list (0x754fb0) of the mother
        quests held; flag != 0 sets a bool at +0x28 of its entry, read here as "done" *(guess)*.
  0x7d1 (XiStrExpInfo @2, u16 level @0xe, i32 exp gained @0x10; client 0x517cd0, text 11198 "%d EXP Received"),
  0x7d2 (i64 Mito @2, i64 gained @0xa; 0x517f80, 11197), 0x7d3 (i64 mileage, i64 gained; 11199, not used here),
  0x7d4 ReputationInfo (u16 kind 1 Mitro Airport Base / 2 Mitro City Hall / 3 Mafia @2, u32 total @4, i32 change
        @8; client 0x517e00 keeps the totals at +0x3d55c.., texts 11352 / 11353 for the change and 11354..11360 for a
        new level). Levels (client 0x50e3e0): <= -9000 0, <= -3000 1 hostile, <= -1000 2 somewhat hostile, < 1000 3
        neutral, < 3000 4 somewhat friendly, < 9000 5 friendly, else 6 very friendly. Sent at login with change 0.

Kept: SKID_QUEST_TB with QUESTID = the mother quest id (STATE 0 started, 2 done; a repeatable one goes back to started
when taken again, its children's rows are reset so QuestStart takes them again), reputations as the license counters
GC_Reputation_01..03 in SKID_PLAYMODE_TB (licenses.count; License_GC conditions read them).
"""
import csv
import io
import os
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import add_money
from .login import SVC, send
from .progress import add_exp, play_mode

STARTED, DONE = 0, 2
REPUTATIONS = ('GC_Reputation_01', 'GC_Reputation_02', 'GC_Reputation_03')
LOAD_SQL = "SELECT QUESTID, STATE FROM SKID_QUEST_TB WHERE SERVERID=%s AND CID=%s AND (QUESTID LIKE 'mq[_]%%' OR QUESTID LIKE 'sq[_]%%')"
SAVE_SQL = """IF EXISTS (SELECT 1 FROM SKID_QUEST_TB WHERE SERVERID=%s AND CID=%s AND QUESTID=%s)
  UPDATE SKID_QUEST_TB SET STATE=%s, LASTDATE=GetDate() WHERE SERVERID=%s AND CID=%s AND QUESTID=%s
ELSE
  INSERT INTO SKID_QUEST_TB(SERVERID, CID, CNAME, QUESTID, STATE, FAILNUM, PLACEIDX) VALUES (%s,%s,%s,%s,%s,0,0)"""
DELETE_SQL = "DELETE FROM SKID_QUEST_TB WHERE SERVERID=%s AND CID=%s AND QUESTID=%s"

_rows = None


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def rows():
    """MotherQuest.xlt as dicts, by row (the client's index)."""
    global _rows
    if _rows is None:
        path = os.path.join(context.data.root, 'Init', 'MotherQuest.xlt')
        text = open(path, 'rb').read().decode('utf-16-le').lstrip('﻿')
        out = []
        for r in list(csv.reader(io.StringIO(text), delimiter='\t'))[3:]:
            if len(r) < 30 or not r[0].strip().isdigit():
                continue
            rewards = []
            for k in range(22, 30, 2):
                kind, value = r[k].strip(), r[k + 1].strip()
                if kind == 'exp' or kind == 'mito':
                    rewards.append((kind, _int(value)))
                elif kind == 'reputation' and ' ' in value:
                    name, n = value.split()
                    rewards.append((name, _int(n)))
            out.append(dict(id=r[1].strip(), level=_int(r[2]), grade=_int(r[3]),
                            prev=r[4].strip() if r[4].strip() not in ('', 'n/a', '0') else None,
                            rep=r[5].strip(), rep_min=_int(r[6], -999999), repeat=_int(r[10]) == 1, title=r[12],
                            children=[c.strip() for c in r[13:17] if c.strip() not in ('', '0', 'n/a')],
                            start=r[17].strip(), end=r[19].strip(), rewards=rewards))
        _rows = out
    return _rows


def by_id(qid):
    return next((i for i, r in enumerate(rows()) if r['id'] == qid), None)


async def load(p):
    """-> p.mothers {row: state} (cached on the player)."""
    if getattr(p, 'mothers', None) is None:
        db = context.db
        found = await db.rows(LOAD_SQL, (db.server_id, p.char.cid))
        p.mothers = {}
        for qid, state in found or []:
            i = by_id(qid)
            if i is not None:
                p.mothers[i] = int(state)
    return p.mothers


async def _save(p, i, state):
    db, c, qid = context.db, p.char, rows()[i]['id']
    p.mothers[i] = state
    await db.execute(SAVE_SQL, (db.server_id, c.cid, qid, state, db.server_id, c.cid, qid,
                                db.server_id, c.cid, c.name, qid, state))


async def reputation(p, name):
    from .licenses import load as lic_load, state as lic_state
    st = lic_state(p) or await lic_load(p)
    return st['gc'].get(name, 0)


def reputation_frame(kind, total, change=0):
    return Frame(0x7d4, struct.pack('<HIi', kind, total & 0xffffffff, change))


async def add_reputation(session, p, name, n):
    from .licenses import count
    if name not in REPUTATIONS or not n:
        return
    await count(session, name, n, p)        # stored as the license counter (negative counts are not kept by it)
    send(session, reputation_frame(REPUTATIONS.index(name) + 1, await reputation(p, name), n))


def list_frame(held):
    return Frame(0x17c, struct.pack('<I', len(held)) + b''.join(
        struct.pack('<II', i, int(s == DONE)) for i, s in sorted(held.items())))


async def on_login(session, p):
    """0x17c the mother quests held, 0x7d4 the three reputations."""
    send(session, list_frame(await load(p)))
    for k, name in enumerate(REPUTATIONS):
        send(session, reputation_frame(k + 1, await reputation(p, name)))


def _message(session, text):
    from ..admin import message
    session.log.note(f'mother quest: {text}')
    message(session, text)


def _child_rows(r):
    idx = context.data.quest_index
    return [idx[c] for c in r['children'] if c in idx]


@on(SVC, C2S, 0x17d)
async def mother_start(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    i, = struct.unpack_from('<I', frame.payload)
    table = rows()
    if not 0 <= i < len(table):
        return
    r, c = table[i], p.char
    held = await load(p)
    admin = c.ptype == 'A'
    if held.get(i) == STARTED:
        return send(session, Frame(0x17e, struct.pack('<I', i)))     # the client asks again: it is held
    if held.get(i) == DONE and not r['repeat']:
        return _message(session, f'{r["id"]}: already done.')
    if not admin:
        if c.level < r['level']:
            return _message(session, f'Level {r["level"]} is needed for this mission.')
        grade = p.car.shown_grade() if p.car else 0
        if grade < r['grade']:
            return _message(session, f'A V{r["grade"]} vehicle is needed for this mission (yours is V{grade}).')
        if r['prev'] and held.get(by_id(r['prev'])) != DONE:
            return _message(session, 'Finish the previous mission first.')
        if r['rep'] in REPUTATIONS and await reputation(p, r['rep']) < r['rep_min']:
            return _message(session, f'Your reputation is too low for this mission (at least {r["rep_min"]}).')
    if r['repeat']:                         # its children may be rewarded from last time: QuestStart takes them again
        from . import quests
        for t in _child_rows(r):
            k = quests.find(p, t)
            if k is not None:
                p.quests.pop(k)
                db = context.db
                await db.execute(DELETE_SQL, (db.server_id, c.cid, context.data.quests[t][0]))
    await _save(p, i, STARTED)
    session.log.note(f'mother quest start {r["id"]} (row {i}), children {r["children"]}')
    send(session, Frame(0x17e, struct.pack('<I', i)))


@on(SVC, C2S, 0x17f)
async def mother_complete(session, frame):
    from . import quests
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    i, = struct.unpack_from('<I', frame.payload)
    table = rows()
    held = await load(p)
    if not 0 <= i < len(table) or held.get(i) != STARTED:
        return _message(session, 'This mission is not in progress.')
    r, c = table[i], p.char
    for t in _child_rows(r):
        k = quests.find(p, t)
        if k is None or p.quests[k][1] not in (quests.COMPLETED, quests.REWARDED):
            return _message(session, f'Finish "{context.data.quests[t][10]}" first.')
    await _save(p, i, DONE)
    exp = sum(n for kind, n in r['rewards'] if kind == 'exp')
    money = sum(n for kind, n in r['rewards'] if kind == 'mito')
    if exp:
        await add_exp(c, exp)
        send(session, Frame(0x7d1, struct.pack('<3IHi', c.exp, c.exp_next, c.exp_base, c.level, exp)))
    if money:
        await add_money(c, money)
        send(session, Frame(0x7d2, struct.pack('<qq', c.mito, money)))
    await play_mode(c, 'QUEST', exp=exp, money=money)
    for kind, n in r['rewards']:
        if kind.startswith('GC_Reputation_'):
            await add_reputation(session, p, kind, n)
    session.log.note(f'mother quest done {r["id"]}: {exp} exp, {money} Mito, '
                     f'{[x for x in r["rewards"] if x[0].startswith("GC_")]}')
    from .login import stat_frames
    for f in stat_frames(p):
        send(session, f)
    send(session, Frame(0x180, struct.pack('<I', i)))
    from .licenses import check
    await check(session, p)


@on(SVC, C2S, 0x181)
async def mother_give_up(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    i, = struct.unpack_from('<I', frame.payload)
    held = await load(p)
    if held.get(i) == STARTED:
        db, c = context.db, p.char
        held.pop(i)
        await db.execute(DELETE_SQL, (db.server_id, c.cid, rows()[i]['id']))
        session.log.note(f'mother quest given up: {rows()[i]["id"]} ({frame.payload[4:8].hex()})')
    send(session, Frame(0x182, struct.pack('<I', i)))
    send(session, list_frame(held))         # the client keeps a given-up / failed one held otherwise
