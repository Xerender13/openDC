"""Part-time jobs (delivery, "Arbeit"): the list at a post, start, ready, go, delivery points, reward,
giving up (batch 3 of the native game).

Job rows: the 2011 ArbeitClient.tdf by TableIdx (row; data.Tables.jobs): 0 id, 2 item group (its items
were defined only on the 2008 server side; item rewards come from Emulator/server_data/delivery_rewards.txt instead, rewards.py),
3 giver post, 4 title, 8-27 delivery posts, then per medal exp / Mito / time limit (s): gold 28 29 30,
silver 31 32 33, bronze 34 35 36, below 37 38 (Pizza Delivery: 20 / 90 / 92, 17 / 64 / 99, 15 / 60 / 118,
7.5 / 30; the 2008 table had shorter limits, 69 / 74 / 89).

0x141 ArbeitList (u32 icon index of the post) -> 0x142 (post, n, n x XiStrArbeitInfo (284): Rank[3]
    XiStrRankInfo (76: name 0x2a, team 0x1a, u32 time ms, u32 rank), MyRankUnit[6] XiRankUnit (u32 time ms, i32
    rank) per date type, u32 TableIdx, u32 average time ms (120000 without records)): the jobs given at that post.
**Records** (2008 BS_GameDB::InsertArbeitRank / XiRankArbeitPlayerMgr, PktFillArbeitInfo 0x5ec1f0,
    PktFillArbeitRankList 0x5eb720): SKID_ARBEITREC_TB, one row per character and job (AID = TableIdx), the best
    TIME (ms) and its LASTDATE; ranked by TIME. Date types 0-5 (2008 clamps to 5): 0 all time, 1 this month, 2 this
    week, 3 last month, 4 last week, 5 today (the 2008 server's queries: all / since a date / between two dates; the
    mapping is ours). Rank[3] = this week's top 3, else all time's (2008 fills type 2, then type 0).
0x153 ArbeitRankList (u32 TableIdx, u32 page, u32 date type) -> 0x154 (TableIdx, page, n, n x XiStrRankInfo):
    10 per page (2008 Cmd_ArbeitRankList 0x5efb00). No handler until 2026-10-14 (user: the leaderboard showed no
    names / times).
0x143 ArbeitStart (TableIdx) -> 0x144 (serial, TableIdx, u32 number of delivery places). The client keeps the
    count in its job object (+0x2c, 0x74ac10) and marks that many of the row's posts on the maps (0x632af9) and
    for the arrow; 2008 XiCsArbeit::XiCsArbeit 0x5c2bc0 sets it to 5 (recorded: 5). Until 2026-10-14 the
    completed count was sent here (0 -> no markers, the arrow pointed back to the station: user).
0x14f ArbeitReady (serial, ready) -> 0x150 (the same).   0x151 ArbeitGo (serial) -> 0x151 (serial): the
    clock starts.
0x14b ArbeitGoalPlace (serial, place index, time) -> 0x14c (serial, place, u16 complete): complete at the
    PLACES-th delivery post; the medal follows the time from "go" (gold / silver / bronze limits, else below).
0x145 ArbeitReward (serial) -> 0x2f8 + 0x2f9, 0x146 ArbeitRewardAck (serial, exp, Mito, item count, item,
    XiStrExpInfo, u16 level, best rank unit, current rank unit, u32 result = medal; item count @0xc and item
    TableIdx @0x10: with a count the client prints the item's name (0x73d050, item by TableIdx 0x7172f0) and shows
    its HUD icon; one item: the first of delivery_rewards.txt's, the others only reach the inventory): the medal's exp and
    Mito (XiCsArbeit::GetEnableReward 0x5c8a10), PLAYMODE ARBEIT win (the character's QuickCnt). The result is
    1 gold, 2 silver, 3 bronze, 0 none (client 0x73d050: chat texts 10134 / 10135 / 10136, else "Exp. %d Mito";
    MEDAL_RESULT; until 2026-10-14 the MEDALS index was sent: a gold run showed no medal, user).
0x149 ArbeitGiveUp (serial) -> 0x14a (serial), 0x313 the giver post's position (as recorded).
0x327 SetMyDeliveryItem (u8 cargo: the a_i_%04u model number of the job's row column 2, sent once the cargo
    model is loaded into the HUD box, client 0x6eab30) -> 0x328 SetMyDeliveryItemAck (u16 serial, u16 age, u8
    cargo; client 0x516b50: own player info @0x95 and age, as the 2016 client's Cmd_SetMyDeliveryItemAck). The
    cargo goes into the player info (misc.player_info @0x95) with a new age, so the other clients ask for it
    again and draw the cargo above the car (0x6eac50); cleared when the job ends. Until 2026-10-14 ignored.
Errors: 20021 NotFoundArbeit (2008 symbol).
"""
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send, stat_frames
from .progress import add_exp, play_mode
from .records import wstr

POSTS = range(8, 28)
PLACES = 5                      # delivery places per job (2008 XiCsArbeit: 5; the row lists 20 posts)
MEDALS = ((28, 29, 30), (31, 32, 33), (34, 35, 36), (37, 38, None))     # exp, Mito, time limit (s)
MEDAL_RESULT = (1, 2, 3, 0)     # MEDALS index -> 0x146 result (client: 1 gold, 2 silver, 3 bronze, 0 none)
AVERAGE_MS = 120000


def _f(r, i):
    try:
        return float(r[i])
    except (IndexError, ValueError, TypeError):
        return 0.0


def posts(row):
    return [row[i] for i in POSTS if i < len(row) and row[i] not in ('0', '', 'n/a')]


PAGE = 10
# date type -> condition on LASTDATE (the database's GetDate(), so its own clock); day 0 of SQL Server is a Monday
_TODAY = "CAST(CAST(GETDATE() AS date) AS datetime)"
_MONTH = "DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
_WEEK = f"DATEADD(day, -(DATEDIFF(day, 0, GETDATE()) %% 7), {_TODAY})"
RANGES = {0: "", 1: f" AND LASTDATE >= {_MONTH}", 2: f" AND LASTDATE >= {_WEEK}",
          3: f" AND LASTDATE >= DATEADD(month, -1, {_MONTH}) AND LASTDATE < {_MONTH}",
          4: f" AND LASTDATE >= DATEADD(day, -7, {_WEEK}) AND LASTDATE < {_WEEK}", 5: f" AND LASTDATE >= {_TODAY}"}
RECORD_SQL = ("SET NOCOUNT ON; UPDATE SKID_ARBEITREC_TB SET TIME=%s, TID=%s, TEAMNAME=%s, LASTDATE=GetDate()"
              " WHERE SERVERID=%s AND CID=%s AND AID=%s AND TIME > %s;"
              " IF NOT EXISTS (SELECT 1 FROM SKID_ARBEITREC_TB WHERE SERVERID=%s AND CID=%s AND AID=%s)"
              " INSERT INTO SKID_ARBEITREC_TB (SERVERID, AID, TIME, CID, CNAME, TID, TEAMNAME, LASTDATE)"
              " VALUES (%s, %s, %s, %s, %s, %s, %s, GetDate())")


async def top(table_idx, dtype, offset, count):
    """-> [(rank, time ms, cid, name, team id, team name)] of a job's records for a date type."""
    db = context.db
    rows = await db.rows("SELECT TIME, CID, CNAME, TID, TEAMNAME FROM SKID_ARBEITREC_TB WHERE SERVERID=%s AND AID=%s"
                         + RANGES.get(dtype, "") + " ORDER BY TIME ASC, LASTDATE ASC"
                         " OFFSET %s ROWS FETCH NEXT %s ROWS ONLY", (db.server_id, table_idx, offset, count))
    return [(offset + k + 1, int(r[0]), int(r[1]), r[2] or '', int(r[3] or 0), r[4] or '') for k, r in enumerate(rows)]


async def my_unit(cid, table_idx, dtype, time_ms=None):
    """-> (time ms, rank) of a character's record for a date type (time_ms: the rank a time would have); (0, 0)
    without one."""
    db = context.db
    if time_ms is None:
        r = await db.row("SELECT TIME FROM SKID_ARBEITREC_TB WHERE SERVERID=%s AND AID=%s AND CID=%s"
                         + RANGES.get(dtype, ""), (db.server_id, table_idx, cid))
        if not r:
            return 0, 0
        time_ms = int(r[0])
    r = await db.row("SELECT COUNT(*) FROM SKID_ARBEITREC_TB WHERE SERVERID=%s AND AID=%s AND TIME < %s AND CID <> %s"
                     + RANGES.get(dtype, ""), (db.server_id, table_idx, time_ms, cid))
    return time_ms, int(r[0]) + 1


def rank_info(rank, time_ms, name, team_name):
    """XiStrRankInfo (76): CharName (0x2a), TeamName (0x1a), u32 time ms, u32 rank."""
    return wstr(name, 0x2a) + wstr(team_name, 0x1a) + struct.pack('<II', time_ms, rank)


async def arbeit_info(cid, table_idx):
    """XiStrArbeitInfo (284) for the job list."""
    best = await top(table_idx, 2, 0, 3) or await top(table_idx, 0, 0, 3)
    out = b''.join(rank_info(rank, ms, name, team) for rank, ms, _, name, _, team in best)
    out = out.ljust(3 * 76, b'\0')
    for dtype in range(6):
        out += struct.pack('<Ii', *await my_unit(cid, table_idx, dtype))
    db = context.db
    avg = await db.row("SELECT AVG(TIME) FROM SKID_ARBEITREC_TB WHERE SERVERID=%s AND AID=%s", (db.server_id, table_idx))
    return out + struct.pack('<II', table_idx, int(avg[0]) if avg and avg[0] else AVERAGE_MS)


@on(SVC, C2S, 0x141)
async def job_list(session, frame):
    if len(frame.payload) < 4:
        return
    post, = struct.unpack_from('<I', frame.payload)
    t = context.data
    p = session.state.get('player')
    cid = p.char.cid if p else 0
    jobs = [k for k, r in enumerate(t.jobs) if t.icon_index.get(r[3]) == post]
    out = b''.join([await arbeit_info(cid, k) for k in jobs])
    send(session, Frame(0x142, struct.pack('<II', post, len(jobs)) + out))


@on(SVC, C2S, 0x153)
async def job_rank_list(session, frame):
    if len(frame.payload) < 12:
        return
    table_idx, page, dtype = struct.unpack_from('<III', frame.payload)
    dtype = min(dtype, 5)
    rows = await top(table_idx, dtype, page * PAGE, PAGE)
    session.log.note(f'job rank list {table_idx} page {page} type {dtype}: {len(rows)}')
    send(session, Frame(0x154, struct.pack('<III', table_idx, page, len(rows))
                        + b''.join(rank_info(rank, ms, name, team) for rank, ms, _, name, _, team in rows)))


@on(SVC, C2S, 0x143)
async def job_start(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    table_idx, = struct.unpack_from('<I', frame.payload)
    if not 0 <= table_idx < len(context.data.jobs):
        return error(session, '20021')
    serial = session.state['job_serial'] = session.state.get('job_serial', 0) + 1
    session.state['job'] = dict(serial=serial, table_idx=table_idx, place=0, start=None, medal=None)
    session.log.note(f'job start {context.data.jobs[table_idx][0]} ({context.data.jobs[table_idx][4].strip()})')
    send(session, Frame(0x144, struct.pack('<III', serial, table_idx, min(PLACES, len(posts(context.data.jobs[table_idx]))))))


def current(session, serial):
    j = session.state.get('job')
    return j if j and j['serial'] == serial else None


@on(SVC, C2S, 0x14f)
async def job_ready(session, frame):
    serial, ready = struct.unpack_from('<II', frame.payload)
    if not current(session, serial):
        return error(session, '20021')
    send(session, Frame(0x150, struct.pack('<II', serial, ready)))


@on(SVC, C2S, 0x151)
async def job_go(session, frame):
    serial, = struct.unpack_from('<I', frame.payload)
    j = current(session, serial)
    if not j:
        return error(session, '20021')
    j['start'] = time.monotonic()
    send(session, Frame(0x151, struct.pack('<I', serial)))


@on(SVC, C2S, 0x14b)
async def job_goal_place(session, frame):
    serial, place, _ = struct.unpack_from('<III', frame.payload)
    j = current(session, serial)
    if not j:
        return error(session, '20021')
    row = context.data.jobs[j['table_idx']]
    if place >= min(PLACES, len(posts(row))):
        return error(session, '20021')
    j.setdefault('done', set()).add(place)      # any order: the client keeps a done flag per place (job +0x10)
    j['place'] = len(j['done'])
    complete = j['place'] >= min(PLACES, len(posts(row)))
    if complete:
        took = time.monotonic() - (j['start'] or time.monotonic())
        j['ms'] = int(took * 1000)
        j['medal'] = next((m for m, (_, _, limit) in enumerate(MEDALS) if limit and took <= _f(row, limit)), 3)
        session.log.note(f'job done in {took:.1f} s: medal {j["medal"]}')
    send(session, Frame(0x14c, struct.pack('<IIH', serial, place, 1 if complete else 0)))


@on(SVC, C2S, 0x145)
async def job_reward(session, frame):
    from .items import add_money
    p = session.state.get('player')
    serial, = struct.unpack_from('<I', frame.payload)
    j = current(session, serial)
    if not p or not j or j['medal'] is None:
        return error(session, '20021')
    row, c = context.data.jobs[j['table_idx']], p.char
    exp_col, money_col, _ = MEDALS[j['medal']]
    from .items import play_bonus
    from .licenses import city_of_post
    exp, money = play_bonus(p, int(_f(row, exp_col)), int(_f(row, money_col)), 'delivery', city_of_post(row[3]))
    await add_exp(c, exp)
    await add_money(c, money)
    await play_mode(c, 'ARBEIT', exp=exp, money=money)
    c.quick_cnt += 1
    session.state.pop('job', None)
    if session.state.get('cargo'):
        set_cargo(session, 0)
    # the record: kept when better (2008 InsertArbeitRank / UpdateRank); BestRankUnit = the best after it,
    # CurRankUnit = this run's time and the rank it has among all records
    db, ms, aid = context.db, j.get('ms', 0), j['table_idx']
    if ms > 0:
        team = c.team_id if c.team_id > 0 else 0
        await db.execute(RECORD_SQL, (ms, team, c.team_name[:16], db.server_id, c.cid, aid, ms, db.server_id, c.cid, aid,
                                      db.server_id, aid, ms, c.cid, c.name, team, c.team_name[:16]))
    from .rewards import delivery_rewards, give
    from .items import mod_list
    gains, given = await give(p, delivery_rewards(row[0], j['medal']))
    if gains.items:
        send(session, mod_list(*gains.items))
    shown = (given[0][1], given[0][0].table_idx) if given else (0, 0)
    best, cur = await my_unit(c.cid, aid, 0), await my_unit(c.cid, aid, 0, ms)
    session.log.note(f'job record {row[0]}: {ms} ms, best {best}, this run {cur};'
                     f' items {[(i.item_id, n) for i, n in given]}')
    for f in stat_frames(p):
        send(session, f)
    await count_delivery(session, row, MEDAL_RESULT[j['medal']])
    send(session, Frame(0x146, struct.pack('<IIIII3IH', serial, exp, money, *shown, c.exp, c.exp_next, c.exp_base, c.level)
                        + struct.pack('<IiIi', *best, *cur) + struct.pack('<I', MEDAL_RESULT[j['medal']])))


async def count_delivery(session, row, medal):
    """Licenses: GC_QuickService, the medal (1 gold, 2 silver, 3 bronze; GC_QuickGold / Siver / Bronze), and the job's own
    conditions: GC_Quick<City>_NNN (any medal) / GC_QuickG<City>_NNN (gold) for job a_00NNN."""
    from .licenses import count_many, tables
    names = ['QuickService'] + ({1: ['QuickGold'], 2: ['QuickSiver'], 3: ['QuickBronze']}.get(medal, []))
    num = row[0][2:] if row[0].startswith('a_') and row[0][2:].isdigit() else None
    if num and medal in (1, 2, 3):
        for gc in tables().gc_id:
            if gc.startswith('GC_Quick') and gc.endswith('_' + num[-3:]) and (medal == 1 or not gc.startswith('GC_QuickG')):
                names.append(gc)
    await count_many(session, names)


def set_cargo(session, cargo):
    """The delivery cargo in the player info (0 = none) -> 0x328 with a new age (the others ask again)."""
    if session.state.get('cargo', 0) == cargo and cargo:
        return
    session.state['cargo'] = cargo
    age = session.state['visual_age'] = session.state.get('visual_age', 1) + 1
    send(session, Frame(0x328, struct.pack('<HHB', session.state.get('serial', 0) & 0xffff, age & 0xffff, cargo)))


@on(SVC, C2S, 0x327)
async def set_delivery_item(session, frame):
    if session.state.get('player') and frame.payload:
        set_cargo(session, frame.payload[0])


@on(SVC, C2S, 0x149)
async def job_give_up(session, frame):
    serial, = struct.unpack_from('<I', frame.payload)
    j = current(session, serial)
    if not j:
        return error(session, '20021')
    session.state.pop('job', None)
    if session.state.get('cargo'):
        set_cargo(session, 0)
    send(session, Frame(0x14a, struct.pack('<I', serial)))
    t = context.data
    idx = t.icon_index.get(t.jobs[j['table_idx']][3], -1)
    m, x, y, z = t.icons[idx] if idx >= 0 else (0, 0.0, 0.0, 0.0)
    send(session, Frame(0x313, struct.pack('<I4f', m, x, y, z, 0.0)))
