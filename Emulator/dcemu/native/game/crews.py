"""Crews (teams): the Communication Zone's My Crew tab (F1) and the crew windows, as the 2008 server's PacketParser::
Cmd_*Team* / XiTeamInfoBox (ZoneServer.pdb), in the 2011 layouts. Kept as the 2008 server did: SKID_TEAM_TB (TID from
100000, TMARKID, TEAMNAME / UTEAMNAME, TEAMDESC, TEAMURL, MEMBERCNT, TEAMSTATE 'A' / 'C' closing, CID / CNAME the master,
CREATEDATE, CLOSEDATE = when a closing crew is deleted) and SKID_CHARACTER_TB TEAMID / TEAMRANK / TEAMJOINDATE /
TEAMCLOSEDATE (here: when the character was kicked) / TEAMLEAVEDATE. No crew: TEAMID -1, TEAMRANK -1.

Ranks (2008): 1 Crew Master, 2 first class (sub-master), 3 member (a new member). Rules (2008 errors, GlobalText_Server):
  create: level 20 (20163), 10000 Mito (20164, "TEAMCREATE"), not in a crew (20165), a free name (20166); join: the
  applicant in no crew (20225), the crew exists (20196) and is not closing (20197), at most 100 members (20171), the master
  online to approve (20199), 24 hours after being kicked (20242), one crew per account (20262); the master cannot leave
  (20174); master only: close / cancel / kick / ranks / hand over (20084, 20201, 20202); a new master: level 20 (10849),
  online (10869). Closing: TEAMSTATE 'C', deleted 7 days later (cancel before: 0x355); deleted when a member logs in or
  asks for the crew after that time.

XiStrTeamInfo, 2011 (384 bytes; 2008 371; client copy at [char + 0x1964], fields read by the My Crew tab 0x6a4700 and
0x537e70 / 0x63a416): i64 TeamId @0, i64 TeamMarkId @8, wchar[13] name @0x10, wchar[61] description @0x2a, char[33] URL
@0xa4, u32 create @0xc5, close @0xc9, banish @0xcd (time_t), char[24] owned channels @0xd1 (1 each), char[2] state @0xe9
('A', 'C' = closing: 0x6a472e), u32 ranking @0xeb (24 bits), u8 ranking tier @0xef (new in 2011: 1-3 S, 4-10 A, 11-20 B),
u32 point @0xf0, u32 channel wins @0xf4, u32 member count @0xf8, i64 total exp @0xfc, i64 total Mito @0x104, u32 version
@0x10c, i64 owner @0x110, i64 leader @0x118, wchar[21] owner name @0x120, leader name @0x14a, u32 @0x174 (12 bytes new in
2011; [char + 0x1ad8], the client sets it to -1 on a notice; 0 here), 8 bytes.

Messages (2011 sizes; offsets with the type):
0x348 MyTeamInfo (u32 act) -> 0x349 (act, i64 cid, i32 rank, XiStrTeamInfo @0x12, u16 age @0x192; 404 bytes; client
    0x530070: the character's crew id / mark / name / rank from it; act 0x3eb / 0x3ec open windows).
0x34a CreateTeam (XiStrTeamInfo: name @0x10, description, URL, mark @8) -> 0x34b (i32 result, info, u16 age @0x186, i64
    the character's Mito @0x188; client 0x530960: rank 1, its money set to the value).
0x353 CheckTeamName (wchar[17]) -> 0x354 (i32 1 free / 0, the name).   0x364 CheckTeamUrl (char[17]) -> 0x365 (i32, url).
0x342 SetTeamUrl (i64 crew, char[33]) -> 0x343 (i32, crew, url).
0x357 TeamMembers (i32 act, i64 crew, i32 channel) -> 0x358 (act, crew, channel, i64 master @0x12, u16 n @0x1a, u16 page
    @0x1c (0 = the list starts again), n x 76 @0x1e: i64 cid, wchar[17] name, i32 rank @0x2a, i32 level, XiCarAttr (12)
    @0x32, u16 serial @0x3e (0 = offline), 8-byte place @0x40 (social.place_of), u32 join time @0x48; client 0x530e30:
    act 0x3f1 / 0x3f2 / 0x3f4).
0x35a CharTeamInfo (act, i64 cid, i64 crew, i32 rank) -> 0x35b (act, cid, info @0xe, i32 rank @0x18e; 402 bytes).
0x367 JoinTeamApply / 0x366 JoinTeamApplyByName (wchar[13] crew name @2, then the bind): XiTeamBind (66 bytes: i64 crew,
    i64 cid, u32 serial, wchar[21] name, i32 level) -> the same 0x367 to the crew master (client 0x530440: "Do you approve
    %s to join your crew?"; its answer is 0x368).
0x368 JoinTeamConfirm (bind, i32 0: the 2011 client sends it for OK only; Cancel = 0x36c) -> the applicant: 0x34f JoinTeamAck (i32 1, info, u16 age; client
    0x530b50: rank 3, text 10016) and notice 4 to the crew; no -> 0x36c RejectTeamApply (u16 serial, wchar[21] master name,
    i64 cid, wchar[13] crew name @0x36, i64 crew; client 0x530560: text with the crew name). 0x36c from the master's client
    is passed on the same way.
0x350 LeaveTeam (i64 crew) -> 0x351 (i32 1, u16 age; client 0x530cd0), notice 5.
0x36b BanishTeamMember (bind of the member, u16 age, u16 type) -> the member: 0x36b (bind, age @0x44, type @0x46; client
    0x5314a0 clears its crew), the master: 0x358 again; notice 6.
0x374 AssignTeamRank (i64 cid, i32 rank 2 / 3, wchar[21] name) -> 0x375 (cid, rank), notice 8 (promotion text by rank).
0x352 DelegateTeamMaster (i64 crew, i64 cid, wchar[21] name) -> 0x359 (i32 1, crew, cid) to both, notice 7.
0x34c CloseTeam / 0x355 CancelCloseTeam (i64 crew) -> 0x34d / 0x356 (i32 1, info; client 0x530250 copies the info),
    notices 1 / 2; a closed crew deleted: notice 3.
0x340 GetTeamMark (i64 crew) -> 0x341 (i32 0, crew, i64 0, i32 size 0): only the built-in marks (gameui/teammark/01-10 =
    TMARKID 1-10) are used.
0x36d TeamNotify (u32 type, wchar[13] crew, wchar[21] name, u32 time @0x4a, i32 rank @0x4e; client 0x530f80): 1 closing
    asked (10814), 2 cancelled (10815), 3 deleted (10816), 4 joined (10817), 5 left (10818), 6 kicked (10819), 7 new master
    (10820), 8 promoted (10838 / 10839 by rank), 9 deletion countdown (10821 / 10822), 10 renamed (11305), 11 logged on
    (11413), 12 logged off (12214).
Crew chat: 0x92 room "team" -> 0x93 to the crew's members in the game (session.chat).
"""
import asyncio
import datetime
import struct

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context, now, time_t
from .login import SVC, error, send, sessions
from .records import wstr

TEAM_INFO = 384
MASTER, FIRST, MEMBER = 1, 2, 3
CREATE_LEVEL, CREATE_FEE, MAX_MEMBERS = 20, 10000, 100
CLOSE_DAYS, KICK_WAIT_HOURS = 7, 24
NAME_CHARS = 12                          # wchar[13] / SKID_TEAM_TB.TEAMNAME varchar(16)
PAGE = 20
ACT_LIST = 0x3f2

TEAM_SQL = ("SELECT TID, TMARKID, TEAMNAME, TEAMDESC, TEAMPOINT, TEAMRANKING, CHANNELWINCNT, TEAMSTATE, OWNCHANNEL, CID,"
            " CNAME, CREATEDATE, CLOSEDATE, BANISHDATE, TEAMURL FROM SKID_TEAM_TB WHERE SERVERID=%s")
STATS_SQL = ("SELECT COUNT(CID), SUM(NEXP), SUM(GOLD) FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND TEAMID=%s"
             " AND STATE='P'")
MEMBERS_SQL = ("SELECT a.CID, a.CNAME, a.TEAMRANK, a.NLEVEL, a.TEAMJOINDATE, b.CARTYPE, b.COLOR FROM SKID_CHARACTER_TB a"
               " LEFT OUTER JOIN SKID_CAR_TB b ON a.SERVERID=b.SERVERID AND a.CID=b.CID AND a.CURCAR=b.CARID"
               " WHERE a.SERVERID=%s AND a.TEAMID=%s AND a.STATE='P' ORDER BY a.TEAMRANK, a.CNAME")
CREATE_SQL = ("SET NOCOUNT ON; INSERT INTO SKID_TEAM_TB(SERVERID, TMARKID, TEAMNAME, UTEAMNAME, TEAMDESC, TEAMLEVEL,"
              " TEAMPOINT, MEMBERCNT, CID, CNAME, TEAMSTATE, TEAMURL, UTEAMURL, CREATEDATE, LASTDATE) OUTPUT INSERTED.TID"
              " VALUES (%s,%s,%s,UPPER(%s),%s,0,0,1,%s,%s,'A',%s,UPPER(%s),GetDate(),GetDate())")
NAME_USED_SQL = "SELECT COUNT(*) FROM SKID_TEAM_TB WHERE SERVERID=%s AND UTEAMNAME=UPPER(%s)"
URL_USED_SQL = "SELECT COUNT(*) FROM SKID_TEAM_TB WHERE SERVERID=%s AND UTEAMURL=UPPER(%s)"
CHAR_TEAM_SQL = ("UPDATE SKID_CHARACTER_TB SET TEAMID=%s, TEAMRANK=%s, TEAMJOINDATE=CASE WHEN %s=1 THEN GetDate() ELSE"
                 " TEAMJOINDATE END, TEAMCLOSEDATE=CASE WHEN %s=1 THEN GetDate() ELSE TEAMCLOSEDATE END, TEAMLEAVEDATE="
                 "CASE WHEN %s=1 THEN GetDate() ELSE TEAMLEAVEDATE END WHERE SERVERID=%s AND CID=%s")
RANK_SQL = "UPDATE SKID_CHARACTER_TB SET TEAMRANK=%s WHERE SERVERID=%s AND CID=%s AND TEAMID=%s"
COUNT_SQL = ("UPDATE SKID_TEAM_TB SET MEMBERCNT=(SELECT COUNT(*) FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND TEAMID=%s"
             " AND STATE='P'), LASTDATE=GetDate() WHERE SERVERID=%s AND TID=%s")
CHAR_SQL = ("SELECT CID, CNAME, NLEVEL, TEAMID, TEAMRANK, MEMBERID, TEAMCLOSEDATE FROM SKID_CHARACTER_TB"
            " WHERE SERVERID=%s AND CID=%s AND STATE='P'")
ACCOUNT_TEAM_SQL = ("SELECT COUNT(*) FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND MEMBERID=%s AND TEAMID>0 AND CID<>%s"
                    " AND STATE='P'")


def _i(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _s(v):
    return (v or '').strip()


async def team(tid):
    """The crew row as a dict (deleting it first when its closing time has passed), or None."""
    if not tid or tid < 0:
        return None
    db = context.db
    r = await db.row(TEAM_SQL + " AND TID=%s", (db.server_id, tid))
    if not r:
        return None
    t = dict(tid=int(r[0]), mark=_i(r[1]), name=_s(r[2]), desc=_s(r[3]), point=_i(r[4]), ranking=_i(r[5]),
             wins=_i(r[6]), state=_s(r[7]) or 'A', channels=_s(r[8]), master=_i(r[9]), master_name=_s(r[10]),
             created=time_t(r[11]), closed=time_t(r[12]), banish=time_t(r[13]), url=_s(r[14]))
    if t['state'] == 'C' and t['closed'] and t['closed'] <= now():
        await delete(t)
        return None
    n, exp, money = await db.row(STATS_SQL, (db.server_id, tid))
    t.update(count=_i(n), exp=_i(exp), money=_i(money))
    return t


async def team_by_name(name):
    db = context.db
    r = await db.row("SELECT TID FROM SKID_TEAM_TB WHERE SERVERID=%s AND UTEAMNAME=UPPER(%s)", (db.server_id, name))
    return await team(int(r[0])) if r else None


def crew_level(t):
    """The crew's grade as the client works it out for its own crew (0x537e70): total exp / 10 + points >= 500000 or
    any channel win -> 3 (S), >= 100000 -> 2 (A), >= 20000 -> 1 (B), else 0 (C). Others get it in XiPlayerInfo @0x58
    and the crew nameplate is coloured by it (0x62ac31: S orange, A pink, B blue, C green; user, 2026-10-16: own
    nameplate pink, green for the others: 0 had been sent)."""
    if not t:
        return 0
    v = t.get('exp', 0) // 10 + t.get('point', 0)
    return 3 if v >= 500000 or t.get('wins', 0) else 2 if v >= 100000 else 1 if v >= 20000 else 0


def info_bytes(t):
    """XiStrTeamInfo, 2011 (384 bytes)."""
    if not t:
        return struct.pack('<qq', -1, -1) + bytes(TEAM_INFO - 16)
    out = bytearray(TEAM_INFO)
    struct.pack_into('<qq', out, 0, t['tid'], t['mark'])
    out[0x10:0x2a] = wstr(t['name'], 26)
    out[0x2a:0xa4] = wstr(t['desc'], 122)
    out[0xa4:0xc5] = t['url'].encode('latin-1', 'replace')[:32].ljust(33, b'\0')
    struct.pack_into('<III', out, 0xc5, t['created'], t['closed'] if t['state'] == 'C' else 0, t['banish'])
    for ch in (_i(x, -1) for x in t['channels'].split(',') if x.strip()):
        if 0 <= ch < 24:
            out[0xd1 + ch] = 1
    out[0xe9] = ord(t['state'][:1] or 'A')
    struct.pack_into('<I', out, 0xeb, t['ranking'] & 0xffffff)
    struct.pack_into('<IIIqqI', out, 0xf0, t['point'], t['wins'], t['count'], t['exp'], t['money'], 0)
    struct.pack_into('<qq', out, 0x110, t['master'], t['master'])
    out[0x120:0x14a] = wstr(t['master_name'], 42)
    out[0x14a:0x174] = wstr(t['master_name'], 42)
    return bytes(out)


def age(session):
    """A new player-info age (the others ask for the player info again: crew name / mark above the car)."""
    session.state['visual_age'] = session.state.get('visual_age', 1) + 1
    return session.state['visual_age'] & 0xffff


def online_member(cid):
    from .social import online
    return online(cid)


def set_char(p, t, rank):
    c = p.char
    if t:
        c.team_id, c.team_mark, c.team_name, c.team_rank = t['tid'], t['mark'], t['name'], rank
    else:
        c.team_id, c.team_mark, c.team_name, c.team_rank = -1, -1, '', -1


async def save_char(cid, tid, rank, joined=0, kicked=0, left=0):
    db = context.db
    await db.execute(CHAR_TEAM_SQL, (tid, rank, joined, kicked, left, db.server_id, cid))


async def recount(tid):
    db = context.db
    await db.execute(COUNT_SQL, (db.server_id, tid, db.server_id, tid))


def crew_sessions(tid):
    return [s for s in list(sessions.values()) if s.state.get('player') and s.state['player'].char.team_id == tid]


def notify(tid, crew_name, kind, name='', rank=0, when=0, skip=None):
    out = Frame(0x36d, struct.pack('<I', kind) + wstr(crew_name, 26) + wstr(name, 42) + struct.pack('<Ii', when, rank))
    for s in crew_sessions(tid):
        if s is not skip:
            send(s, out)


def my_info_frame(session, p, act=0):
    c = p.char
    return Frame(0x349, struct.pack('<Iqi', act, c.cid, c.team_rank if c.team_id > 0 else -1)
                 + info_bytes(session.state.get('crew')) + struct.pack('<H', session.state.get('visual_age', 1) & 0xffff))


async def refresh(session, p):
    """The character's crew (session.state['crew']), as kept in the database."""
    t = await team(p.char.team_id) if p.char.team_id > 0 else None
    if p.char.team_id > 0 and not t:            # the crew was deleted meanwhile
        set_char(p, None, -1)
    elif t:
        set_char(p, t, p.char.team_rank)
    session.state['crew'] = t
    return t


async def delete(t):
    """A closed crew whose time ran out: every member leaves, the row goes."""
    db = context.db
    tid = t['tid']
    for s in crew_sessions(tid):
        set_char(s.state['player'], None, -1)
        s.state['crew'] = None
        send(s, Frame(0x36d, struct.pack('<I', 3) + wstr(t['name'], 26) + wstr('', 42) + struct.pack('<Ii', 0, 0)))
        send(s, my_info_frame(s, s.state['player']))
    await db.execute("UPDATE SKID_CHARACTER_TB SET TEAMID=-1, TEAMRANK=-1 WHERE SERVERID=%s AND TEAMID=%s",
                     (db.server_id, tid))
    await db.execute("DELETE FROM SKID_TEAM_TB WHERE SERVERID=%s AND TID=%s", (db.server_id, tid))


# ---- my crew ------------------------------------------------------------------------------------------------------

@on(SVC, C2S, 0x348)
async def my_team_info(session, frame):
    p = session.state.get('player')
    if not p:
        return
    act, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    await refresh(session, p)
    send(session, my_info_frame(session, p, act))


@on(SVC, C2S, 0x35a)
async def char_team_info(session, frame):
    if len(frame.payload) < 12:
        return
    act, cid = struct.unpack_from('<Iq', frame.payload)
    db = context.db
    r = await db.row(CHAR_SQL, (db.server_id, cid))
    t = await team(_i(r[3], -1)) if r else None
    send(session, Frame(0x35b, struct.pack('<Iq', act, cid) + info_bytes(t) + struct.pack('<i', _i(r[4], -1) if t else -1)))


def member_entry(r):
    cid, name, rank, level, joined, car_type, color = r
    s = online_member(int(cid))
    from .social import place_of
    car = struct.pack('<HHII', 0, _i(car_type), _i(color) or 0x01010102, 0x82cccccc)
    serial = s.state.get('serial', 0) if s else 0
    if s and s.state['player'].car:
        from .rooms import car_attr_of
        car = car_attr_of(s.state['player'].car)
    return (struct.pack('<q', int(cid)) + wstr(_s(name), 34) + struct.pack('<ii', _i(rank, MEMBER), _i(level))
            + car + struct.pack('<H', serial & 0xffff) + place_of(s) + struct.pack('<I', time_t(joined)))


async def member_frames(t, act, channel=0):
    db = context.db
    rows = await db.rows(MEMBERS_SQL, (db.server_id, t['tid']))
    pages = [rows[i:i + PAGE] for i in range(0, len(rows), PAGE)] or [[]]
    return [Frame(0x358, struct.pack('<iqiqHH', act, t['tid'], channel, t['master'], len(part), k)
                  + b''.join(member_entry(r) for r in part)) for k, part in enumerate(pages)]


@on(SVC, C2S, 0x357)
async def team_members(session, frame):
    if len(frame.payload) < 16:
        return
    act, tid, channel = struct.unpack_from('<iqi', frame.payload)
    t = await team(tid)
    if not t:
        return error(session, '20192')
    send(session, *await member_frames(t, act, channel))


# ---- creating, names, URL, mark ---------------------------------------------------------------------------------

@on(SVC, C2S, 0x353)
async def check_team_name(session, frame):
    name = read_wstr(frame.payload, 0, 34).strip()
    ok = await name_free(name)
    send(session, Frame(0x354, struct.pack('<i', 1 if ok else 0) + frame.payload[:34].ljust(34, b'\0')))


async def name_free(name):
    if not name or len(name) > NAME_CHARS:
        return False
    db = context.db
    r = await db.row(NAME_USED_SQL, (db.server_id, name))
    return bool(r) and not r[0]


@on(SVC, C2S, 0x364)
async def check_team_url(session, frame):
    url = frame.payload[:17].split(b'\0')[0].decode('latin-1', 'replace').strip()
    db = context.db
    r = await db.row(URL_USED_SQL, (db.server_id, url)) if url else None
    send(session, Frame(0x365, struct.pack('<i', 1 if r and not r[0] else 0) + frame.payload[:17].ljust(17, b'\0')))


@on(SVC, C2S, 0x342)
async def set_team_url(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    tid, = struct.unpack_from('<q', frame.payload)
    url = frame.payload[8:41].split(b'\0')[0].decode('latin-1', 'replace').strip()[:32]
    c, db = p.char, context.db
    if c.team_id != tid or c.team_rank != MASTER:
        return error(session, '20084')
    await db.execute("UPDATE SKID_TEAM_TB SET TEAMURL=%s, UTEAMURL=UPPER(%s) WHERE SERVERID=%s AND TID=%s",
                     (url, url, db.server_id, tid))
    send(session, Frame(0x343, struct.pack('<iq', 1, tid) + url.encode('latin-1', 'replace').ljust(33, b'\0')))


MARK_DIR = 'teammark'                    # server_data/teammark/01-10: the built-in marks (sync_data copies them)
MARK_MAX = 0x4000


def builtin_mark(mark):
    """The bytes of a built-in mark (TMARKID 1-10), or b''."""
    import os
    try:
        with open(os.path.join(context.data.root, MARK_DIR, f'{mark:02d}'), 'rb') as f:
            return f.read()
    except OSError:
        return b''


async def mark_data(mark):
    db = context.db
    r = await db.row("SELECT IMGDATA FROM SKID_IMAGE_TB WHERE IMGID=%s", (mark,))
    return bytes(r[0] or b'') if r else builtin_mark(mark)


@on(SVC, C2S, 0x340)
async def get_team_mark(session, frame):
    """0x340 GetTeamMark (i64 crew) -> 0x341 (i32 result, i64 crew, i64 mark id, i32 size, the BMP; client 0x530f10)."""
    tid, = struct.unpack_from('<q', frame.payload) if len(frame.payload) >= 8 else (0,)
    t = await team(tid)
    data = await mark_data(t['mark']) if t else b''
    send(session, Frame(0x341, struct.pack('<iqqi', 1 if data else 0, tid, t['mark'] if t else 0, len(data)) + data))


@on(SVC, C2S, 0x33e)
async def set_team_mark(session, frame):
    """0x33e SetTeamMark (i64 crew, i32 size, the image as the client read it from the chosen file: a JPEG in the
    recording, 1014 bytes; the My Crew tab's Crew Mark, master only) -> SKID_IMAGE_TB (a new IMGID from the sticker
    sequence, as the 2008 server kept marks in the image table), TMARKID = that id -> 0x33f (i32 1, crew, i64 mark id,
    i32 size, u16 age; client 0x530380) to the crew's members. The clients fetch the picture from the lobby: 0x40
    GetImage (act 0x3f5, i64 crew, i64 mark) -> 0x41 (stickers.get_image; the built-in marks 1-10 from
    server_data/teammark). A file on disk was not seen by the client (user: an empty square)."""
    import pytds
    from ..stickers import next_id
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    tid, size = struct.unpack_from('<qi', frame.payload)
    data = frame.payload[12:12 + max(0, min(size, MARK_MAX))]
    got = await master_check(session, tid)
    if not got:
        return
    if not data:
        session.log.note('crew mark upload: empty')
        return
    db = context.db
    mark = await next_id()
    await db.execute("INSERT INTO SKID_IMAGE_TB(IMGID, SERVERID, IMGTYPE, IMGSIZE, IMGCOLORKEY, IMGDATA, CDATE)"
                     " VALUES (%s, %s, 0, %s, 0, %s, GetDate())", (mark, db.server_id, len(data), pytds.Binary(data)))
    await db.execute("UPDATE SKID_TEAM_TB SET TMARKID=%s WHERE SERVERID=%s AND TID=%s", (mark, db.server_id, tid))
    t = await team(tid)
    session.log.note(f'crew {t["name"]!r}: new mark {mark} ({len(data)} bytes)')
    for s in crew_sessions(tid):
        set_char(s.state['player'], t, s.state['player'].char.team_rank)
        s.state['crew'] = t
        send(s, Frame(0x33f, struct.pack('<iqqiH', 1, tid, mark, len(data), age(s))))


@on(SVC, C2S, 0x34a)
async def create_team(session, frame):
    from .items import add_money
    p = session.state.get('player')
    if not p or len(frame.payload) < TEAM_INFO:
        return
    info = frame.payload[:TEAM_INFO]
    mark, = struct.unpack_from('<q', info, 8)
    name = read_wstr(info, 0x10, 26).strip()
    desc = read_wstr(info, 0x2a, 122).strip()
    url = info[0xa4:0xc5].split(b'\0')[0].decode('latin-1', 'replace').strip()[:32]
    c, db = p.char, context.db
    if c.level < CREATE_LEVEL:
        return error(session, '20163')
    if c.team_id > 0 and await team(c.team_id):
        return error(session, '20165')
    if not await name_free(name):
        return error(session, '20166')
    if c.mito < CREATE_FEE or not await add_money(c, -CREATE_FEE):
        return error(session, '20164')
    r = await db.row(CREATE_SQL, (db.server_id, max(mark, 1), name, name, desc[:80], c.cid, c.name, url, url))
    tid = int(r[0])
    await save_char(c.cid, tid, MASTER, joined=1)
    t = await team(tid)
    set_char(p, t, MASTER)
    session.state['crew'] = t
    session.log.note(f'crew {name!r} ({tid}) created, mark {mark}, {CREATE_FEE} Mito')
    send(session, Frame(0x34b, struct.pack('<i', 1) + info_bytes(t) + struct.pack('<Hq', age(session), c.mito)))


async def master_check(session, tid):
    """-> (player, crew) when the sender is that crew's master, else None (an error sent)."""
    p = session.state.get('player')
    if not p:
        return None
    t = await team(tid)
    if not t:
        error(session, '20167')
        return None
    if p.char.team_id != tid or p.char.team_rank != MASTER:
        error(session, '20084')
        return None
    return p, t


@on(SVC, C2S, 0x34c)
async def close_team(session, frame):
    if len(frame.payload) < 8:
        return
    got = await master_check(session, struct.unpack_from('<q', frame.payload)[0])
    if not got:
        return
    p, t = got
    if t['state'] == 'C':
        return error(session, '20168')
    db = context.db
    await db.execute(f"UPDATE SKID_TEAM_TB SET TEAMSTATE='C', CLOSEDATE=DATEADD(day, {CLOSE_DAYS}, GetDate())"
                     " WHERE SERVERID=%s AND TID=%s", (db.server_id, t['tid']))
    t = await team(t['tid'])
    session.log.note(f'crew {t["name"]!r} closing until {t["closed"]}')
    for s in crew_sessions(t['tid']):
        s.state['crew'] = t
    send(session, Frame(0x34d, struct.pack('<i', 1) + info_bytes(t)))
    notify(t['tid'], t['name'], 1, p.char.name, when=t['closed'])


@on(SVC, C2S, 0x355)
async def cancel_close_team(session, frame):
    if len(frame.payload) < 8:
        return
    got = await master_check(session, struct.unpack_from('<q', frame.payload)[0])
    if not got:
        return
    p, t = got
    if t['state'] != 'C':
        return error(session, '20169')
    db = context.db
    await db.execute("UPDATE SKID_TEAM_TB SET TEAMSTATE='A', CLOSEDATE=NULL WHERE SERVERID=%s AND TID=%s",
                     (db.server_id, t['tid']))
    t = await team(t['tid'])
    for s in crew_sessions(t['tid']):
        s.state['crew'] = t
    send(session, Frame(0x356, struct.pack('<i', 1) + info_bytes(t)))
    notify(t['tid'], t['name'], 2, p.char.name)


# ---- joining ----------------------------------------------------------------------------------------------------------

BIND = 66


def bind_of(raw):
    tid, cid, serial = struct.unpack_from('<qqI', raw)
    return dict(tid=tid, cid=cid, serial=serial, name=read_wstr(raw, 0x14, 42), level=struct.unpack_from('<i', raw, 0x3e)[0])


async def apply_checks(session, p, t):
    """The applicant's side of a join -> an error key or None."""
    c, db = p.char, context.db
    if c.team_id > 0 and await team(c.team_id):
        return '20225'
    if not t:
        return '20196'
    if t['state'] == 'C':
        return '20197'
    if t['count'] >= MAX_MEMBERS:
        return '20171'
    r = await db.row(CHAR_SQL, (db.server_id, c.cid))
    kicked = time_t(r[6]) if r else 0
    if kicked and now() - kicked < KICK_WAIT_HOURS * 3600:
        left = (KICK_WAIT_HOURS * 3600 - (now() - kicked) + 3599) // 3600
        return context.data.server_text.get('20242', '20242').replace('%d', str(left))
    r = await db.row(ACCOUNT_TEAM_SQL, (db.server_id, c.member, c.cid))
    if r and r[0]:
        return '20262'
    if not online_member(t['master']):
        return '20199'
    return None


async def apply(session, t, raw_bind):
    p = session.state.get('player')
    if not p:
        return
    why = await apply_checks(session, p, t)
    if why:
        session.log.note(f'crew apply to {t["name"] if t else "?"}: refused ({why})')
        return error(session, why)
    c = p.char
    bind = (struct.pack('<qqI', t['tid'], c.cid, session.state.get('serial', 0)) + wstr(c.name, 42)
            + struct.pack('<i', c.level))
    session.log.note(f'crew apply to {t["name"]!r}: sent to the master')
    send(online_member(t['master']), Frame(0x367, bind))


@on(SVC, C2S, 0x367)
async def join_team_apply(session, frame):
    if len(frame.payload) < BIND:
        return
    await apply(session, await team(bind_of(frame.payload)['tid']), frame.payload[:BIND])


@on(SVC, C2S, 0x366)
async def join_team_apply_by_name(session, frame):
    if len(frame.payload) < 26 + BIND:
        return
    name = read_wstr(frame.payload, 0, 26).strip()
    t = await team_by_name(name)
    if not t:
        return error(session, '20195')
    await apply(session, t, frame.payload[26:26 + BIND])


def reject_frame(master_name, cid, t):
    return Frame(0x36c, struct.pack('<H', 0) + wstr(master_name, 42) + struct.pack('<q', cid) + wstr(t['name'], 26)
                 + struct.pack('<q', t['tid']))


@on(SVC, C2S, 0x368)
async def join_team_confirm(session, frame):
    if len(frame.payload) < BIND + 4:
        return
    b = bind_of(frame.payload)
    # the 2011 client sends 0x368 only for OK (its popup 0x52ff90 -> 0x804830), with the i32 left 0; Cancel sends 0x36c
    # (0x8048d0, reject_team_apply). Read as a result, every approval was a refusal (user, 2026-10-15).
    yes = True
    got = await master_check(session, b['tid'])
    if not got:
        return
    p, t = got
    s = online_member(b['cid'])
    if not yes:
        session.log.note(f'crew {t["name"]!r}: {b["name"]} refused')
        if s:
            send(s, reject_frame(p.char.name, b['cid'], t))
        return
    if not s:
        return error(session, '20206')
    why = await apply_checks(s, s.state['player'], t)
    if why and why != '20199':
        return error(session, '20203' if why == '20225' else why)
    await save_char(b['cid'], t['tid'], MEMBER, joined=1)
    await recount(t['tid'])
    t = await team(t['tid'])
    set_char(s.state['player'], t, MEMBER)
    for x in crew_sessions(t['tid']):
        x.state['crew'] = t
    session.log.note(f'crew {t["name"]!r}: {b["name"]} joined')
    send(s, Frame(0x34f, struct.pack('<i', 1) + info_bytes(t) + struct.pack('<H', age(s))))
    notify(t['tid'], t['name'], 4, b['name'], MEMBER, skip=s)
    send(session, *await member_frames(t, ACT_LIST))


@on(SVC, C2S, 0x36c)
async def reject_team_apply(session, frame):
    """The master refusing an applicant (0x36c from its client): passed on to the applicant."""
    p = session.state.get('player')
    if not p or len(frame.payload) < 0x56:
        return
    cid, = struct.unpack_from('<q', frame.payload, 0x2c)
    t = session.state.get('crew') or await team(p.char.team_id)
    s = online_member(cid)
    if s and t:
        send(s, reject_frame(p.char.name, cid, t))


# ---- leaving, kicking, ranks, master ------------------------------------------------------------------------------

@on(SVC, C2S, 0x350)
async def leave_team(session, frame):
    p = session.state.get('player')
    if not p:
        return
    c = p.char
    t = await team(c.team_id)
    if not t:
        return error(session, '20173')
    if c.team_rank == MASTER:
        return error(session, '20174')
    await save_char(c.cid, -1, -1, left=1)
    await recount(t['tid'])
    set_char(p, None, -1)
    session.state['crew'] = None
    session.log.note(f'left crew {t["name"]!r}')
    send(session, Frame(0x351, struct.pack('<iH', 1, age(session))))
    notify(t['tid'], t['name'], 5, c.name)


@on(SVC, C2S, 0x36a)
async def leave_team_confirm(session, frame):
    """The master approving a leave request (2008 LeaveTeamRequest / Confirm; the 2011 client leaves with 0x350)."""
    if len(frame.payload) < BIND + 4:
        return
    b = bind_of(frame.payload)
    yes, = struct.unpack_from('<i', frame.payload, BIND)
    got = await master_check(session, b['tid'])
    if not got or not yes:
        return
    p, t = got
    await remove_member(session, t, b, kicked=False)


async def remove_member(session, t, b, kicked):
    db = context.db
    r = await db.row(CHAR_SQL, (db.server_id, b['cid']))
    if not r or _i(r[3]) != t['tid']:
        return error(session, '20273')
    if _i(r[4]) == MASTER:
        return error(session, '20174')
    await save_char(b['cid'], -1, -1, kicked=1 if kicked else 0, left=0 if kicked else 1)
    await recount(t['tid'])
    s = online_member(b['cid'])
    if s:
        set_char(s.state['player'], None, -1)
        s.state['crew'] = None
        if kicked:
            send(s, Frame(0x36b, struct.pack('<qqI', t['tid'], b['cid'], s.state.get('serial', 0)) + wstr(_s(r[1]), 42)
                          + struct.pack('<iHH', _i(r[2]), age(s), 1)))
        else:
            send(s, Frame(0x351, struct.pack('<iH', 1, age(s))))
    session.log.note(f'crew {t["name"]!r}: {_s(r[1])} {"kicked" if kicked else "left"}')
    notify(t['tid'], t['name'], 6 if kicked else 5, _s(r[1]))
    t = await team(t['tid'])
    for x in crew_sessions(t['tid']):
        x.state['crew'] = t
    send(session, *await member_frames(t, ACT_LIST))


@on(SVC, C2S, 0x36b)
async def banish_team_member(session, frame):
    if len(frame.payload) < BIND:
        return
    b = bind_of(frame.payload)
    p = session.state.get('player')
    if not p:
        return
    t = await team(p.char.team_id)
    if not t or (b['tid'] and b['tid'] != t['tid']):
        return error(session, '20200')
    if p.char.team_rank != MASTER:
        return error(session, '20202')
    if b['cid'] == p.char.cid:
        return error(session, '20174')
    await remove_member(session, t, b, kicked=True)


@on(SVC, C2S, 0x374)
async def assign_team_rank(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    cid, rank = struct.unpack_from('<qi', frame.payload)
    t = await team(p.char.team_id)
    if not t:
        return error(session, '20200')
    if p.char.team_rank != MASTER:
        return error(session, '20084')
    db = context.db
    r = await db.row(CHAR_SQL, (db.server_id, cid))
    if rank not in (FIRST, MEMBER) or not r or _i(r[3]) != t['tid'] or _i(r[4]) == MASTER:
        return error(session, '20208')
    await db.execute(RANK_SQL, (rank, db.server_id, cid, t['tid']))
    s = online_member(cid)
    if s:
        s.state['player'].char.team_rank = rank
    session.log.note(f'crew {t["name"]!r}: {_s(r[1])} rank {rank}')
    send(session, Frame(0x375, struct.pack('<qi', cid, rank)))
    notify(t['tid'], t['name'], 8, _s(r[1]), rank)
    send(session, *await member_frames(t, ACT_LIST))


@on(SVC, C2S, 0x352)
async def delegate_team_master(session, frame):
    if len(frame.payload) < 16:
        return
    tid, cid = struct.unpack_from('<qq', frame.payload)
    got = await master_check(session, tid)
    if not got:
        return
    p, t = got
    db = context.db
    r = await db.row(CHAR_SQL, (db.server_id, cid))
    if not r or _i(r[3]) != tid or cid == p.char.cid:
        return error(session, '20273')
    s = online_member(cid)
    if not s:
        return error(session, 'The user must be online in order to become the Crew Leader.')
    if _i(r[2]) < CREATE_LEVEL:
        return error(session, 'The user has to be level 20 or above in order to become a Crew Leader.')
    await db.execute(RANK_SQL, (FIRST, db.server_id, p.char.cid, tid))
    await db.execute(RANK_SQL, (MASTER, db.server_id, cid, tid))
    await db.execute("UPDATE SKID_TEAM_TB SET CID=%s, CNAME=%s WHERE SERVERID=%s AND TID=%s",
                     (cid, _s(r[1]), db.server_id, tid))
    p.char.team_rank = FIRST
    s.state['player'].char.team_rank = MASTER
    t = await team(tid)
    for x in crew_sessions(tid):
        x.state['crew'] = t
    session.log.note(f'crew {t["name"]!r}: master now {_s(r[1])}')
    ack = Frame(0x359, struct.pack('<iqq', 1, tid, cid))
    send(session, ack)
    send(s, ack)
    notify(tid, t['name'], 7, _s(r[1]), MASTER)
    send(session, *await member_frames(t, ACT_LIST))


# ---- logging on / off, chat ------------------------------------------------------------------------------------------

@on_open(SVC)
async def crew_presence(session):
    """Logged on / off notices to the crew (TeamNotify 11 / 12), as the client's texts 11413 / 12214."""
    told = None
    try:
        while True:
            await asyncio.sleep(2)
            p = session.state.get('player')
            if told is None and p and session.state.get('channel'):
                t = await refresh(session, p)
                told = t['tid'] if t else 0
                if t:
                    notify(t['tid'], t['name'], 11, p.char.name, skip=session)
                if t and t['state'] == 'C':         # the crew is being deleted: the countdown notice (10821 / 10822)
                    send(session, Frame(0x36d, struct.pack('<I', 9) + wstr(t['name'], 26) + wstr('', 42)
                                        + struct.pack('<Ii', max(0, t['closed'] - now()), 0)))
    finally:
        p = session.state.get('player')
        if told and p and p.char.team_id == told:
            t = session.state.get('crew')
            if t:
                notify(told, t['name'], 12, p.char.name, skip=session)


def chat(session, p, frame_out):
    """Crew chat (room "team"): to the crew's members in the game -> False without a crew."""
    tid = p.char.team_id
    if tid <= 0:
        return False
    for s in crew_sessions(tid):
        s.to_client(frame_out)
    return True
