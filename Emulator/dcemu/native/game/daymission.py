"""The daily mission (Mission Girl Suyeon) and its Mission Tokens.

**Today's mission**: one row of the Instant_Client.tdf day_mission category (rows 80-90: bring an OMD Gold Coin /
a Boost Protector F, a Battle Zone race, a patrol, Lap Time, Rush Time, a delivery, ...), the same for every player
for the day (2008 XiDayMission::SetRandTodayMissionIdx); the day starts at emulator.ini [daymission] reset_hour.
**0x488 DayEventInfo** at login (2011: u32 TableIdx + 9 x u32, client 0x518980 copies the 36 bytes into its
day-event struct, 0x70b4f0; its debug line reads @4 / @8 "mission" and @0x10 / @0x14 "attendance"): 2008
Cmd_LoadChar sends XiDayMission+0x18 and the character's day-event fields from +0x341: completed today, total
completed, the run (1-6), then the day-mileage (attendance) counters (sent 0 here: not native). The client
starts today's mission itself with 0x3e0 at every login and tracks it ("*** Daily Mission Clear! *** Go find
Mission Girl Suyeon", 10912).
**Completing** (0x3e2 with today's TableIdx, sent at Suyeon; 2008 Cmd_InstantComplete, category 2): already done
today -> 20125; a mission_item row (type 0xb) takes the item it names (column 12 x column 11); the Mission Token
i_n_00049 x1; the counters (today 1, total + 1, run + 1, at 7 back to 0: the 2008 server then entered the player in
the token / attendance event: XiTokenEvent::SetTokenEventCharInfo); 0x489 DayMissionCompleteAck (u32 1, u32 event
season, u32 run, u32 total / 7; client 0x518a10: result 1 = Suyeon's "DayMission_Complete" dialog and today's count
+ 1; run 0 = text 10931 "You have been automatically entered for the %d Drift City Attendance Event! Total
Entries: %d" with season + 1 and total / 7); then (2008 order) 0x192 and the row's exp and Mito as any instant
mission (0x3e5, then 0x3e3).
Counters: SKID_PLAYMODE_TB MODEID 'DAYMISSION' (2008 BS_GameDB::GetPlayModeList -> XiCsCharInfo::SetDayEvent:
TRYCNT today (reset when LASTDATE is before the day's start: XiDayMission::CompleteCntResetCheck), WINCNT total,
POINT the run).
**Token exchange** (0x48a DayMissionGetReward, u32 row; client: Suyeon's menu, "Do you want to exchange %d %ss with
this item?" 10916, confirm 0x2c8e47 -> sender 0x7ef980): Init/TokenBook.xlt (2011 client: Exchange_ID x
Exchange_Count -> Gift1..3 items; Mission Token rows 0-4, Mitron Powder rows 5-9). 2008 Cmd_DayMissionGetReward /
XiTokenRewardTable: unknown row -> 20125; the price is taken, the gifts given (0x2e5 per gift: the pick-up icon),
0x192, then 0x48c DayMissionGetRewardAck (the 2011 client reads it as bonus mileage, text 10917 when @0 != 0: sent 0).
"""
import datetime
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .driftuse import Gains, give_item
from .items import CHANGED, DELETE_SQL, REMOVED, STACK_SQL, mod_list
from .login import SVC, error, send, stat_frames

TOKEN = 'i_n_00049'
RUN_DAYS = 7
MODE = 'DAYMISSION'
STATE_SQL = "SELECT TRYCNT, WINCNT, POINT, LASTDATE FROM SKID_PLAYMODE_TB WHERE SERVERID=%s AND CID=%s AND MODEID=%s"
SAVE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), TRYCNT=%s, WINCNT=%s, POINT=%s WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),%s,%s,%s,0,0,0,0,0,%s)"""


def day_start():
    """The start of the current mission day (local time), [daymission] reset_hour."""
    now = datetime.datetime.now()
    start = now.replace(hour=context.daymission_reset_hour, minute=0, second=0, microsecond=0)
    return start if start <= now else start - datetime.timedelta(days=1)


def rows():
    return [k for k, r in enumerate(context.data.instants) if r and r[0] == 'day_mission']


def today_mission():
    """Today's mission TableIdx: the same for everyone for the day."""
    choices = rows()
    return random.Random(day_start().date().toordinal()).choice(choices) if choices else 0


async def state(p):
    """-> [today, total, run] (today 0 again once the stored LASTDATE is before today's start)."""
    db = context.db
    r = await db.row(STATE_SQL, (db.server_id, p.char.cid, MODE))
    if not r:
        return [0, 0, 0]
    today, total, run, last = (int(r[0] or 0), int(r[1] or 0), int(r[2] or 0), r[3])
    # LASTDATE is the database's GetDate() (UTC in the container); the day starts in local time
    offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta()
    if not last or last + offset < day_start():
        today = 0
    return [today, total, run]


async def save(p, today, total, run):
    db, c = context.db, p.char
    await db.execute(SAVE_SQL, (today, total, run, db.server_id, c.cid, MODE,
                                db.server_id, c.cid, c.name, MODE, today, total, run, c.member))


async def info_frame(p):
    """0x488 DayEventInfo for the login."""
    today, total, run = await state(p)
    return Frame(0x488, struct.pack('<I9I', today_mission(), today, total, run, 0, 0, 0, 0, 0, 0))


async def take(p, item_id, count):
    """count x an inventory item taken from its stacks -> [(item, state)], or None when there are not enough."""
    db = context.db
    piles = [i for i in p.items if i.item_id == item_id and i.car_id == 0 and (i.state & 0xffff) == 0]
    if sum(i.stack for i in piles) < count:
        return None
    out = []
    for it in sorted(piles, key=lambda i: i.stack):
        n = min(count, it.stack)
        it.stack -= n
        count -= n
        if it.stack:
            await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
            out.append((it, CHANGED))
        else:
            await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
            p.items.remove(it)
            out.append((it, REMOVED))
        if not count:
            break
    return out


def _n(r, i):
    try:
        return int(float(r[i]))
    except (IndexError, ValueError):
        return 0


async def complete(session, p, idx):
    """0x3e2 with a day_mission row (from instant.instant_complete)."""
    from .instant import reward_exp
    from .items import add_money, play_bonus
    from .progress import add_exp
    row, c = context.data.instants[idx], p.char
    if idx != today_mission():
        session.log.note(f'day mission {idx}: not today\'s ({today_mission()})')
        return error(session, '20020')                  # NotFoundInstant
    today, total, run = await state(p)
    if today > 0:
        return error(session, '20125')                  # today's mission already done
    changes = []
    if row[10] == 'mission_item' and row[12] not in ('n/a', ''):
        taken = await take(p, row[12], max(_n(row, 11), 1))
        if taken is None:
            session.log.note(f'day mission {idx}: {row[12]} x{_n(row, 11)} missing')
            return error(session, '20020')
        changes += taken
    gains = Gains()
    await give_item(p, TOKEN, 1, gains)
    from .licenses import count
    await count(session, 'MissionToken')        # licenses: GC_MissionToken
    changes += gains.items
    total, run = total + 1, (run + 1) % RUN_DAYS
    await save(p, 1, total, run)
    session.state.pop('day_mission', None)
    send(session, Frame(0x489, struct.pack('<4I', 1, 0, run, total // RUN_DAYS)))
    send(session, mod_list(*changes))
    exp, money = play_bonus(p, reward_exp(row, c.level), _n(row, 13))
    if exp:
        await add_exp(c, exp)
    if money:
        await add_money(c, money)
    session.log.note(f'day mission {idx} done: token, {exp} exp, {money} mito (total {total}, run {run})')
    for f in stat_frames(p):
        send(session, f)
    # 0x3e5 before 0x3e3, as the 2008 server: 0x3e3 frees the client's mission object, which 0x3e5 needs for the
    # banner and the result window (instant.py INSTANT_ORDER)
    send(session, Frame(0x3e5, struct.pack('<III3IHH3I', idx, exp, money, c.exp, c.exp_next, c.exp_base, c.level, 0,
                                           0, 0, 0)))
    send(session, Frame(0x3e3, struct.pack('<I', idx)))


_book = None


def token_book():
    """Init/TokenBook.xlt -> {row: (price item, count, [(gift item, count)])}."""
    global _book
    if _book is None:
        from ..data import read_xlt
        _book = {}
        for r in read_xlt(os.path.join(context.data.root, 'Init', 'TokenBook.xlt'))[3:]:
            if len(r) > 13 and r[0].isdigit():
                gifts = [(r[k], _n(r, k + 1)) for k in (6, 9, 12) if r[k] not in ('n/a', '') and _n(r, k + 1) > 0]
                _book[int(r[0])] = (r[2], _n(r, 3), gifts)
    return _book


@on(SVC, C2S, 0x48a)
async def exchange(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return error(session, '20017')
    idx, = struct.unpack_from('<I', frame.payload)
    entry = token_book().get(idx)
    t = context.data
    if not entry or any(g not in t.item_index for g, _ in entry[2]):
        session.log.note(f'token exchange {idx}: no such row')
        return error(session, '20125')
    price, count, gifts = entry
    paid = await take(p, price, count)
    if paid is None:
        session.log.note(f'token exchange {idx}: {price} x{count} missing')
        return error(session, '20125')
    gains = Gains()
    for item, n in gifts:
        await give_item(p, item, n, gains)
    send(session, mod_list(*paid, *gains.items))
    for item, n in gifts:                           # the pick-up line / icon per gift (2008: 0x2e5)
        send(session, Frame(0x2e5, struct.pack('<IIi', n, t.item_index[item], 2)))
    send(session, Frame(0x48c, struct.pack('<II', 0, 0)))
    session.log.note(f'token exchange {idx}: {price} x{count} -> {gifts}')
