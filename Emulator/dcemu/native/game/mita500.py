"""Mita 500: drink bottles lying in the city, a Mito buff (2008 XiMita500; the 2011 client has all of it).

Settings: emulator.ini [mita500] (enabled, bottles, regen_sec, buff_sec, fee, lucky_rate), sent to the client as
the content flags InstantMission.Mita500 / Mita500RegenCnt / Mita500RegenSec / Mita500BuffSec. 2008 Contents.ini:
off, 10 bottles, 300 s, 1800 s.
Positions: the client's World/<City>/mitaquest.qpos ("qpos" header, u32 500, 500 x (x, y, z)); the server only
    deals in position indexes 0-499. Per city area (city_traffic.area_city) a box of `bottles` bottles at distinct
    random indexes (2008 XiMita500InfoBox, per area id; shuffled index pool).
XiMita500Info (16 bytes): u32 position index, u32 seconds until it shows again (0 = shown), i64 the CID of who
    took it last. Client: list at 0x95c830 + 4 (16-byte entries), positions of the 5 cities at +0x10 .. +0x50.
0x12c JoinArea (login.join_area): before 0x12d, 0x481 if a buff runs and 0x47e Mita500Position (u32 drinks today,
    u16 n, n x XiMita500Info; client 0x526920; at most 16 a message) - as 2008 Cmd_JoinArea.
0x47f Mita500Get (u32 bottle number in the box) -> the bottle is taken if it shows (time passed): it moves to an
    unused position index and shows again after regen_sec (2008 XiMita500InfoBox::Mita500Get / SetNewPosition) ->
    0x480 Mita500GetAck (i64 CID, char name (42), u32 bottle number, XiMita500Info; 72 bytes) to the players of
    that area and channel. The taker's client opens the salesperson's offer (texts Mita500_1..4; Mita500_5 while
    a Bacchus runs; client 0x5184e0). More than 2 drinks today: "20125", nothing taken (2008).
0x482 Mita500GetBuff (nothing) -> fee Mito ("MITA500FEE", 2008 500; not enough: 20236), the buff (2008
    XiCsCharInfo::SetMita500Buff): rate 100 % without a running buff; below level 71 it steps 150 -> 200 -> 250, the
    step after 200 being 500 % at 1 in lucky_rate (2008 m_MitaBuff10Rate); from level 71 it stays 150; ends
    buff_sec after this drink; drinks today / in total + 1 -> 0x481 Mita500BuffInfo (2011, 28 bytes; client
    0x518780): u8 on, i32 today, i32 total, i32 rate %, u32 seconds left, i64 Mito paid (the client takes it off its
    money), u8 new. Refused while a Bacchus runs (and a Bacchus while this runs: items.use_item; their texts).
Bonus: play Mito and exp x rate / 100 while it runs (items.play_bonus; 2008 ApplyMita500BonusMito: Mito only; exp
added as the client's MITO/EXP label shows: user), quest rewards: Mito only (quests.quest_reward).
Kept: SKID_PLAYMODE_TB MODEID 'MITA500' (TRYCNT today, WINCNT total, POINT rate, NEXP end as time_t, LASTDATE day).
"""
import datetime
import random
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send, sessions
from .records import name_bytes

POSITIONS = 500                     # mitaquest.qpos entries per city
MAX_PER_MESSAGE = 16                # BS_PktMita500Position m_Info[16]
DAILY = 3                           # 2008: more than 2 drinks today -> 20125
MODE = 'MITA500'
STATE_SQL = "SELECT TRYCNT, WINCNT, POINT, NEXP, LASTDATE FROM SKID_PLAYMODE_TB WHERE SERVERID=%s AND CID=%s AND MODEID=%s"
SAVE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), TRYCNT=%s, WINCNT=%s, POINT=%s, NEXP=%s WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),%s,%s,%s,0,%s,0,0,0,%s)"""

boxes = {}                          # area -> [[position index, shows again (time.time()), cid], ...]


def enabled():
    return context.mita500.get('enabled', False)


def box(area):
    b = boxes.get(area)
    if b is None:
        picks = random.sample(range(POSITIONS), min(context.mita500['bottles'], POSITIONS))
        b = boxes[area] = [[pos, 0.0, 0] for pos in picks]
    return b


def info_bytes(bottle):
    """XiMita500Info; the client adds its own clock to the second field (0x72ea80: [+4] += now), so it is the
    seconds until the bottle shows again, 0 = shown (not a time_t: a taken bottle never came back)."""
    pos, shows, cid = bottle
    return struct.pack('<IIq', pos, max(0, int(shows - time.time())), cid)


async def state(p):
    """The player's Mita 500 record (p.mita), today's count reset on a new day."""
    m = getattr(p, 'mita', None)
    if m is None:
        db = context.db
        row = await db.row(STATE_SQL, (db.server_id, p.char.cid, MODE))
        m = dict(today=0, total=0, rate=100, end=0, day=None)
        if row:
            m.update(today=int(row[0] or 0), total=int(row[1] or 0), rate=int(row[2] or 100), end=int(row[3] or 0),
                     day=row[4].date() if row[4] else None)
        p.mita = m
    if m['day'] != datetime.date.today():
        m['today'], m['day'] = 0, datetime.date.today()
    return m


def active(p):
    m = getattr(p, 'mita', None)
    return bool(m) and m['end'] > time.time()


def bonus_rate(p):
    """The running buff's Mito rate in % (100 = none)."""
    return p.mita['rate'] if active(p) else 100


async def save(p):
    m, db, c = p.mita, context.db, p.char
    await db.execute(SAVE_SQL, (m['today'], m['total'], m['rate'], m['end'], db.server_id, c.cid, MODE,
                                db.server_id, c.cid, c.name, MODE, m['today'], m['total'], m['rate'], m['end'], c.member))


def buff_frame(p, paid=0, new=False):
    m = p.mita
    left = max(0, int(m['end'] - time.time()))
    # the time left in SECONDS: the client adds it to its clock (0x72d414) and shows minutes (x / 60, 0x518796); sent in ms
    # until 2026-10-15 the timer read 998 minutes (user)
    return Frame(0x481, struct.pack('<BiiiIqB', 1 if left else 0, m['today'], m['total'], m['rate'], left, paid,
                                    1 if new else 0))


def position_frames(p, area):
    b = box(area)
    today = p.mita['today'] if getattr(p, 'mita', None) else 0
    for k in range(0, len(b), MAX_PER_MESSAGE):
        part = b[k:k + MAX_PER_MESSAGE]
        yield Frame(0x47e, struct.pack('<iH', today if k == 0 else -1, len(part)) + b''.join(info_bytes(x) for x in part))


async def on_join_area(session, area):
    """login.join_area, before its 0x12d: the buff and the area's bottles (city areas only)."""
    from ..city_traffic import area_city
    session.state['mita_area'] = area
    p = session.state.get('player')
    if not enabled() or not p or area_city(area) is None:
        return
    await state(p)
    if active(p):
        send(session, buff_frame(p))
    for f in position_frames(p, area):
        send(session, f)


@on(SVC, C2S, 0x47f)
async def mita_get(session, frame):
    p = session.state.get('player')
    area = session.state.get('mita_area')
    if not enabled() or not p or area is None or len(frame.payload) < 4 or area not in boxes:
        return
    m = await state(p)
    if m['today'] >= DAILY:
        return error(session, '20125')
    idx, = struct.unpack_from('<I', frame.payload)
    b = boxes[area]
    now = time.time()
    if idx >= len(b) or b[idx][1] > now:
        return                                  # someone was faster, or not shown yet
    used = {x[0] for x in b}
    b[idx] = [random.choice([q for q in range(POSITIONS) if q not in used]), now + context.mita500['regen_sec'], p.char.cid]
    session.log.note(f'Mita 500 bottle {idx} taken in area {area}, now at position {b[idx][0]}')
    out = Frame(0x480, struct.pack('<q', p.char.cid) + name_bytes(p.char.name) + struct.pack('<I', idx) + info_bytes(b[idx]))
    channel = session.state.get('channel')
    for s in list(sessions.values()):
        if s.state.get('player') and s.state.get('mita_area') == area and s.state.get('channel') == channel:
            send(s, out)


@on(SVC, C2S, 0x482)
async def mita_buff(session, frame):
    from .items import add_money, bacchus_left
    from .login import stat_frames
    p = session.state.get('player')
    if not enabled() or not p:
        return
    m = await state(p)
    if m['today'] >= DAILY:
        return error(session, '20125')
    if bacchus_left(p):
        return error(session, 'You cannot drink Mita 500 while the Bacchus effect lasts.')
    fee = context.mita500['fee']
    if fee and (p.char.mito < fee or not await add_money(p.char, -fee)):
        return error(session, '20236')
    if not active(p):
        m['rate'] = 100
    if p.char.level < 71:
        if m['rate'] <= 100:
            m['rate'] = 150
        elif m['rate'] == 150:
            m['rate'] = 200
        elif m['rate'] == 200:
            lucky = context.mita500['lucky_rate']
            m['rate'] = 500 if lucky and random.randrange(lucky) == 0 else 250
        else:
            m['rate'] = 150
    elif m['rate'] <= 100:
        m['rate'] = 150
    from .licenses import count
    await count(session, 'MitaCount')           # licenses: drinks, the 500 % roll, the third step (250 %)
    if m['rate'] == 500:
        await count(session, 'MitaCritical')
    elif m['rate'] == 250:
        await count(session, 'MitaEnhance')
    m['end'] = int(time.time()) + context.mita500['buff_sec']
    m['today'] += 1
    m['total'] += 1
    await save(p)
    session.log.note(f'Mita 500 drunk: {m["rate"]} % for {context.mita500["buff_sec"]} s, today {m["today"]}')
    send(session, buff_frame(p, paid=fee, new=True))
    for f in stat_frames(p):
        send(session, f)
