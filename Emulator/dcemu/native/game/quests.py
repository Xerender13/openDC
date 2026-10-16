"""Quests (OMD missions): starting, goal places, completing, the reward (batch 3 of the native game).

Quest rows: the 2011 QuestClient.tdf by TableIdx (row; data.Tables.quests). Its columns hold what the
2008 QuestServer.tdf had: 0 quest id, 1 number (IDn), 4 previous quest number (0 none), 6 level needed,
9 giver post, 12 end post, 19 / 21 / 23 / 25 goal posts, 75 reward exp, 76 reward Mito, 77-79 reward
items (Rookie Mission 1/5: 100 exp, 300 Mito). Owned quests: SKID_QUEST_TB (QUESTID, STATE 0 started /
1 completed / 2 rewarded, FAILNUM, PLACEIDX); player.Player.quests holds (TableIdx, state, place, fails).

0x106 QuestStart (TableIdx) -> 0x107 (TableIdx, fail count). XiCsCharInfo::QuestStart 0x5cf830: the
    character's level >= the quest's (accounts with PType 'A' excepted), the previous quest rewarded,
    and not already rewarded; a quest started again keeps its fail count.
0x112 QuestGoalPlace (TableIdx): the next goal place reached (PLACEIDX + 1); no answer.
0x108 QuestComplete (TableIdx, f32 time; 2011 + 4 bytes) -> 0x109 (TableIdx): state 1.
0x10a QuestReward (TableIdx) -> 0x2f8 + 0x2f9, 0x10b QuestRewardAck (TableIdx, exp, Mito, XiStrExpInfo,
    u16 level, u16 item count, u32 x3 reward item TableIdx): state 2, exp / Mito / items ("QUEST"
    play mode). XiCsCharInfo::QuestReward 0x5d5010, Cmd_QuestReward 0x609410.
0x312 QuestPosition (u32 icon index) -> 0x313 (u32 map, XiVec4 position): the icon tables' row
    (data.Tables.icons; 51 = Moon Palace Station 1, as recorded).
0x10c QuestFail (TableIdx) -> 0x10d (TableIdx): state 3, one more fail (XiCsCharInfo::QuestFail).
0x10e QuestGiveUp (TableIdx) -> 0x10f (TableIdx): state 4 (XiCsCharInfo::QuestGiveUp 0x5d4cf0).
Leaving the game: the quest in progress is given up (XiCsCharInfo::SetEnable 0x5d545d ->
    GetProcessQuest -> QuestGiveUp: state 4, saved, "QUEST" play mode), so it is no longer running
    at the next login (user, 2026-10-12: story missions stayed active after logging out).
A failed or given-up quest can be started again (QuestStart keeps its fail count).
Errors (GlobalText_Server.xlt): 20019 NotFoundQuest, 20110 / 20241 can't start, 20111 reward item.
"""
import struct

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import new_item
from .login import SVC, error, send, stat_frames
from .progress import add_exp, play_mode

STARTED, COMPLETED, REWARDED, FAILED, GIVEN_UP = 0, 1, 2, 3, 4
QUEST_SAVE_SQL = """IF EXISTS (SELECT 1 FROM SKID_QUEST_TB WHERE SERVERID=%s AND CID=%s AND QUESTID=%s)
  UPDATE SKID_QUEST_TB SET STATE=%s, FAILNUM=%s, PLACEIDX=%s, LASTDATE=GetDate() WHERE SERVERID=%s AND CID=%s AND QUESTID=%s
ELSE
  INSERT INTO SKID_QUEST_TB(SERVERID, CID, CNAME, QUESTID, STATE, FAILNUM, PLACEIDX) VALUES (%s,%s,%s,%s,%s,%s,%s)"""
REWARD_ITEM_COLS = (77, 78, 79)


def _n(r, i):
    try:
        return int(float(r[i]))
    except (IndexError, ValueError):
        return 0


def is_repeatable(row):
    """The repeatable missions (rq_*: Moon Palace groups of three at one giver, the Koinonia and Cras chains): QuestClient
    column 5 = 1 (other rows: 0, car, chase, city_*, ROO, OMD, ...), column 7 the highest level (rq_moon_1: 11-20). They
    can be taken again once rewarded (the table has no wait or daily limit); their rewards are exp, Mito and Mittron
    Crystal Powder (i_n_00096: the Item Exchange Attendant's currency, TokenBook rows 5-9, daymission.py) with repair
    kits / Small Gift Boxes (user request, 2026-10-16)."""
    return len(row) > 5 and row[5].strip() == '1'


def find(p, table_idx):
    """-> index in p.quests of this quest, or None."""
    return next((k for k, q in enumerate(p.quests) if q[0] == table_idx), None)


async def save(p, table_idx):
    k = find(p, table_idx)
    _, state, place, fails = p.quests[k]
    qid = context.data.quests[table_idx][0]
    db, c = context.db, p.char
    await db.execute(QUEST_SAVE_SQL, (db.server_id, c.cid, qid, state, fails, place, db.server_id, c.cid, qid,
                                      db.server_id, c.cid, c.name, qid, state, fails, place))


@on(SVC, C2S, 0x106)
async def quest_start(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    quests = context.data.quests
    if not 0 <= table_idx < len(quests):
        return error(session, '20019')
    row, c = quests[table_idx], p.char
    repeatable = is_repeatable(row)
    if c.ptype != 'A' and (c.level < _n(row, 6) or repeatable and _n(row, 7) and c.level > _n(row, 7)):
        return error(session, '20110')
    prev = _n(row, 4)
    if prev and c.ptype != 'A':
        done = {_n(quests[q[0]], 1) for q in p.quests if q[1] == REWARDED and 0 <= q[0] < len(quests)}
        if prev not in done:
            return error(session, '20110')
    k = find(p, table_idx)
    if k is not None and p.quests[k][1] == REWARDED and not repeatable:
        return error(session, '20241')
    fails = p.quests[k][3] if k is not None else 0
    if k is None:
        p.quests.append((table_idx, STARTED, 0, fails))
    else:
        p.quests[k] = (table_idx, STARTED, 0, fails)
    await save(p, table_idx)
    session.log.note(f'quest start {row[0]} ({row[10]})')
    send(session, Frame(0x107, struct.pack('<II', table_idx, fails)))


@on(SVC, C2S, 0x112)
async def quest_goal_place(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    k = find(p, table_idx)
    if k is None:
        return error(session, '20019')
    t, state, place, fails = p.quests[k]
    p.quests[k] = (t, state, place + 1, fails)
    await save(p, table_idx)


@on(SVC, C2S, 0x108)
async def quest_complete(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    k = find(p, table_idx)
    if k is None or p.quests[k][1] != STARTED:
        return error(session, '20019')
    t, _, place, fails = p.quests[k]
    p.quests[k] = (t, COMPLETED, place, fails)
    await save(p, table_idx)
    send(session, Frame(0x109, struct.pack('<I', table_idx)))


@on(SVC, C2S, 0x10a)
async def quest_reward(session, frame):
    from .items import add_money
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    k = find(p, table_idx)
    if k is None or p.quests[k][1] != COMPLETED:
        return error(session, '20019')
    row, c, t = context.data.quests[table_idx], p.char, context.data
    t_, _, place, fails = p.quests[k]
    p.quests[k] = (t_, REWARDED, place, fails)
    await save(p, table_idx)
    exp, money = _n(row, 75), _n(row, 76)
    from .mita500 import bonus_rate                 # Mita 500 raises a quest's Mito, not its exp (user, 2026-10-15); the
    money = money * bonus_rate(p) // 100            # other play bonuses (drinks, Bacchus, licenses) neither
    await add_exp(c, exp)
    if money:
        await add_money(c, money)
    await play_mode(c, 'QUEST', exp=exp, money=money)
    items = []
    for col in REWARD_ITEM_COLS:
        iid = row[col].strip() if col < len(row) else ''
        info = t.item_info(t.item_index[iid]) if iid in t.item_index else None
        if info:
            items.append(await new_item(p, info, 1))
    session.log.note(f'quest reward {row[0]}: {exp} exp, {money} mito, items {[i.item_id for i in items]}')
    from .licenses import check, count_many
    if row[0].startswith('rq_'):
        city = {'rq_moon': 'Mo', 'rq_koi': 'Ko', 'rq_cras': 'Cr'}.get(row[2][:7].rstrip('_'))
        await count_many(session, ['RQuestClear'] + ([f'RQuestClear_{city}'] if city else []))
    else:
        await check(session, p)                 # the computed quest / faction conditions (licenses.value)
    for f in stat_frames(p):
        send(session, f)
    if items:
        from .items import mod_list
        send(session, mod_list(*((i, 1) for i in items)))
    idx = [i.table_idx for i in items] + [0] * (3 - len(items))
    send(session, Frame(0x10b, struct.pack('<III3IHH3I', table_idx, exp, money, c.exp, c.exp_next, c.exp_base, c.level,
                                           len(items), *idx[:3])))


@on(SVC, C2S, 0x312)
async def quest_position(session, frame):
    if len(frame.payload) < 4:
        return
    idx, = struct.unpack_from('<i', frame.payload)
    icons = context.data.icons
    m, x, y, z = icons[idx] if 0 <= idx < len(icons) else (0, 0.0, 0.0, 0.0)
    send(session, Frame(0x313, struct.pack('<I4f', m, x, y, z, 0.0)))


async def set_state(p, table_idx, state, fail=0):
    k = find(p, table_idx)
    t, _, place, fails = p.quests[k]
    p.quests[k] = (t, state, place, fails + fail)
    await save(p, table_idx)


@on(SVC, C2S, 0x10c)
async def quest_fail(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    k = find(p, table_idx)
    if k is None or p.quests[k][1] != STARTED:
        return error(session, '20019')
    await set_state(p, table_idx, FAILED, 1)
    send(session, Frame(0x10d, struct.pack('<I', table_idx)))


@on(SVC, C2S, 0x10e)
async def quest_give_up(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    k = find(p, table_idx)
    if k is None or p.quests[k][1] != STARTED:
        return error(session, '20019')
    await set_state(p, table_idx, GIVEN_UP)
    await play_mode(p.char, 'QUEST', wins=0)
    send(session, Frame(0x10f, struct.pack('<I', table_idx)))


async def give_up_at_login(session, p):
    """A quest still started at login was left by a connection that ended without its close (the emulator stopped or
    crashed: give_up_on_leave did not run; user, 2026-10-15: the main mission stayed active after a disconnect)."""
    for q in list(p.quests):
        if q[1] == STARTED:
            await set_state(p, q[0], GIVEN_UP)
            await play_mode(p.char, 'QUEST', wins=0)
            session.log.note(f'quest {q[0]} given up at login (left started)')


@on_open(SVC)
async def give_up_on_leave(session):
    """Runs for the whole connection; on close the quest in progress is given up (SetEnable)."""
    import asyncio
    try:
        await asyncio.Event().wait()
    finally:
        p = session.state.get('player')
        for q in list(p.quests) if p else []:
            if q[1] == STARTED:
                try:
                    await set_state(p, q[0], GIVEN_UP)
                    await play_mode(p.char, 'QUEST', wins=0)
                    session.log.note(f'quest {q[0]} given up on leaving')
                except Exception as e:      # the connection is gone; keep the close quiet
                    session.log.note(f'quest give-up on leaving failed: {e}')


# 0x76c SelectGuild (u32 guild type) -> 0x76d SelectGuildAck (the same u32; client 0x517b20 puts it in the character's
# +0xf1): the faction. The client sends it from quests: "First Task from ROO" (#108) sends 1 = ROO (user, 2026-10-16:
# the faction did not change - the message had no handler). 2008 PacketParser::Cmd_SelectGuild / XiCsCharInfo::
# SelectGuild: kept in SKID_CHARACTER_TB.GUILDTYPE (loaded with the character, in the lobby's character list too).
GUILD_SQL = "UPDATE SKID_CHARACTER_TB SET GUILDTYPE=%s WHERE SERVERID=%s AND CID=%s"
ROO_GUILD = 1


@on(SVC, C2S, 0x76c)
async def select_guild(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    guild, = struct.unpack_from('<I', frame.payload)
    c, db = p.char, context.db
    if c.guild != guild:
        session.log.note(f'faction (guild type) {c.guild} -> {guild}')
        c.guild = guild
        await db.execute(GUILD_SQL, (guild, db.server_id, c.cid))
    send(session, Frame(0x76d, struct.pack('<I', guild)))
