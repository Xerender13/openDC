"""2016 client: WORLD MATCH LAP TIME (the 0xf51 - 0xf5e layer), off unless ``emulator.ini [worldmatch] enabled``.

Every layout below comes from the 2016 client's disassembly as collected in
``docs/neo_work/WMLAPTIME_PROTOCOL.md`` (section numbers and VAs are that file's; the VAs are the
objdump/image VAs of ``DriftCity Dev Ed/DriftCity.exe``). The whole module does nothing unless
``version.is_2016()`` and ``context.worldmatch`` is a dict with a truthy ``enabled`` (the lead fills it from
``emulator.ini [worldmatch]``; the default is ``{}``, i.e. off). When it is off the handlers return without
answering, so a 2011 client and an untouched 2016 server behave exactly as before.

The WM layer sits *on top of* the ordinary battle-zone Lap Time race (section 8.5 / section 10: the same
0x1bb filter 4, 0x528 LapTimeLoad ... 0x52c LapTimeRecord flow that ``laptime.py`` implements). It adds
the season, the nickname and the daily tries around it. **The race itself is unchanged.**

Replies this module sends (frame = u16 type + payload; "off" = payload offset = frame offset - 2):

  S>C 0xf59 Cmd_WMLaptimeSeasonState, handler 0x5316d0 - 202 bytes fixed (section 3.7)
      +0x02 u32 season number        (mgr+0x80, 0x5316f2 / 0x5317b0)
      +0x06 u32 season state: 0 racing (12769 "... has begun."), 1 reward period (12768
             "Distributing ... Rewards has begun.")   (0x53171d-0x53176a)
      +0x0a 4 x char[48]: tournament begin / end, reward begin / end, the four date columns of the
             season table row verbatim (0x5317b9-0x5317c7, labels 0x5edd20)
  S>C 0xf5c Cmd_WMLaptimeDailyTryCnt, handler 0x52d590 - 6 bytes (section 3.8)
      +0x02 u32 tries already used today (mgr+0x84; the client shows min(used + pending, max))
  S>C 0xf58 Cmd_WMLaptimeCharRecordAck, handler 0x52d4c0 - 99 bytes fixed (section 3.6)
      +0x02 4 bytes the client never reads; +0x06 the 93-byte manager record (copied verbatim by
      0x52d4d1-0x52d4da). Its fields, as frame offsets (= record offset + 6):
        +0x27 char[21] character name     (mgr+0x21, 0x5eac8d)
        +0x3c char[11] country            (mgr+0x36, 0x5eac97)
        +0x47 char[11] World Match nickname (mgr+0x41, 0x5eac9c-0x5eacac)
        +0x52 u32      level              (mgr+0x4c, 0x5eac7f)
        +0x56 f32      season time, seconds (mgr+0x50, 0x52d504; printed 12760 "%d min %.3f sec")
        +0x5a u32      rank A, domestic   (mgr+0x54, 0x52d4f1; 0 -> "--- Rank.")
        +0x5e u32      rank B, world      (mgr+0x58, 0x52d4f7; 0 -> "--- Rank.")
  S>C 0xf51 Cmd_WMLaptimeNationRecords, handler 0x53b960 - 6 + 0x35*n bytes (section 3.2)
      +0x02 u32 n, then n x 53-byte records (0x53a540, stride 0x35 at 0x53b9ac):
        +0x00 char[21] character name     (arg1 of "%s(%s) / Lv %d", 0x5eadb4)
        +0x15 char[11] country            (arg2, 0x5eadb3)
        +0x20 char[13] World Match nickname (0x5eadc3-0x5eadca)
        +0x2d f32      lap time, seconds  (0x5eadcf-0x5eae06)
        +0x31 u32      level              (0x5eadaa-0x5eadaf)
  S>C 0xf57 Cmd_WMLaptimeRaceInfo, handler 0x5315f0 - 0xe + len bytes (section 3.5)
      +0x02 u32 character serial of the rank-1 holder (0 when offline; the client looks it up in its
             entity list by [entity+0xe4], 0x531665 / 0x5ee1ac)
      +0x06 u32 unknown, never read -> 0 (0x531668)
      +0x0a u32 len, MUST be >= 1 (with 0 the handler returns 0xf, one byte past the frame, 0x531612)
      +0x0e char[len] the rank-1 holder's display name, NOT NUL-terminated (0x53161d-0x531688)
  S>C 0xf54 Cmd_WMNickNameUpdateAck, handler 0x52d530 - 28 bytes fixed (section 3.4)
      +0x02 u32 result: 0 rejected (prints 12789), non-zero accepted (0x52d535-0x52d55f)
      +0x06 char[11] the accepted nickname (memcpy 0xb, 0x52d540-0x52d556)
      +0x11 11 bytes the client never reads
  S>C 0xf5e Cmd_WMLaptimeTryCanceled, handler 0x52d5b0 - 130 bytes fixed (section 3.9)
      +0x02 char[128] the already-localised reason text, shown verbatim (0x52d5b6-0x52d5e1) and
             mgr+0x88 cleared

Requests (all C>S sizes are the makers' reserved ring-buffer sizes, section 4.1):

  C>S 0xf53 6 bytes (maker 0x862020, writer 0x86b160; only 0x5b0fc4 sends it, always with 3) -> the
      full 0xf59 + 0xf5c + 0xf58 + 0xf51 + 0xf57 burst (section 9.1-9.6, 9.9).
  C>S 0xf56 2 bytes (maker 0x862120, 0x86b300; sent after a good 0xf54, 0x5eceff) -> the same burst
      (section 9.7: "treat 0xf56 as 'my nickname is set, continue'").
  C>S 0xf55 0x18 bytes (maker 0x8620a0, 0x86b1f0; writer 0x86b2a2-0x86b2b5 writes 11 bytes at +2, the
      11 bytes at +0x0d are never initialised) -> 0xf54 (section 9.7).
  C>S 0xf5c 6 bytes (maker 0x8623a0, 0x86b5d0; the u32 at +2 is NEVER written) -> 0xf5c with the
      tries used today (section 9.3).
  C>S 0xf5d 2 bytes (maker 0x862320, 0x86b550; only from 0x5ecfe0) -> the try starts: no reply when
      allowed, 0xf5e with 12788's text when today's tries are used up (section 9.8).
  C>S 0xf5a 6 bytes (maker 0x8621a0, 0x86b3c0; the 15 reward buttons, argument unresolved, section
      4.3) -> 0xf51 (section 9.10: "safe: reply with 0xf51").
  C>S 0xf5b 8 bytes (maker 0x862220, 0x86b410; GM chat command 0x6145a0 / 0x618533 only) -> logged,
      no reply (section 9.11).

**S>C 0x3c0 Cmd_WMLaptimeStatusInfo** (lead, session 46): its +0x02 112-byte and +0x72 44-byte blocks are the
player's stat frame (the body of 0x2f8, handler 0x521cc0 -> 0x784470), not an area record as section 3.1 had it
(docs/neo_work/WM_AREA_BLOB.md); +0x9e the season's track (PVPTrackInfo Id), +0xa0 its city (1-4), n = 0. Sent in the
refresh burst and right after an accepted try (build_status_info). With the flag on, every lap-time race loads
through this (the loader tests only the flag), so laptime.pick_track races the season's track while enabled.

What is OURS (not in the client or the doc):
  * ``SKID_WMLAPTIME_TB`` (below) is our storage: the 2016 server's own World Match tables were not
    available, so the season ranking is this server's characters only.
  * the season's "current row" is chosen from the client's own
    ``Init/WorldMatchSeasonLaptime.xlt`` (section 5) so the season number and the tab labels agree; the
    2016 table's rows end 2014-06-29, so on a live server the fallback ("the latest row whose begin is
    past", state 1 = reward period) is what a player sees.
  * 0xf58's f32 is the player's **best lap in seconds**, the same number the 0xf51 row carries; we do
    not send a "seconds to season end" countdown (section 9.4 leaves that choice open and the reward
    window prints the value as a lap time, 12760).
  * 0xf58's rank B ("world") is the same as rank A: the 0xf51 vector is the nation *and* world list
    (section 3.3: 0xf52 does nothing, "the 'world' column of the list is the same 0xf51 vector").
  * a player without a recorded lap still gets 0xf58 (time 0.0, rank 0 -> "--- Rank.") so the own-record
    panel shows the name / country / nickname / level; only rows with BESTSEC go into 0xf51.
  * 0xf57 is only sent when somebody holds rank 1: its ``len`` must be >= 1, so an empty label cannot be
    sent (section 3.5).
  * the daily limit is ``emulator.ini [worldmatch] daily_tries`` (default 5) and the day is the server's
    local date as YYYYMMDD (``TRYDAY``); the client only knows min(used, max) from its own content flag.
  * the ranking is capped at ``MAX_ROWS`` = as many 53-byte records as one of our frames may hold
    (wire.SANE_FRAME); the client pages locally and asks for nothing (section 3.2).
  * the nickname is validated here (ASCII letters/digits, 2..10) because the client only prints 12744 for
    a bad name and does not enforce it (section 9.7); it is unique per server + season, case-insensitive.
  * strings are single-byte char[] fields printed with "%s" (rankings.py's ``sstr``): encoded cp949, the
    convention of every other char[] field the native modules write. 12788's Value_US in gt.tsv contains
    U+2019 ("You’ve"), which cp949 cannot encode, so MAX_TRIES_TEXT uses an ASCII apostrophe.
"""
import os
import struct
from collections import namedtuple
from datetime import datetime

from ...handlers import on
from ...protocol import C2S
from ...wire import SANE_FRAME, Frame
from .. import context
from ..version import is_2016
from .login import SVC, send, serial_of, sessions

COUNTRY = 'USA'                            # ours: the 2016 US client's country label (11-byte field)

REC = 0x35                                 # 0xf51 record stride (0x53b9ac)
MY_REC = 0x5d                              # the 93 bytes copied into mgr+0 (0x52d4d1)
SEASON_LEN = 202                           # 0xf59 (0x5316d0)
MY_LEN = 99                                # 0xf58 (0x52d4c0)
NICK_LEN = 28                              # 0xf54 (0x52d530)
TRY_LEN = 130                              # 0xf5e (0x52d5b0)
PERIODS = 4 * 48                           # 0xf59 +0xa: tournament / reward begin + end
STATE_RACING, STATE_REWARD = 0, 1          # 0xf59 +6 (0x53171d-0x531758)
MAX_ROWS = (SANE_FRAME - 6) // REC         # our framing limit, not the client's (it pages locally)
NICK_MIN, NICK_MAX, NICK_FIELD = 2, 10, 11  # 12744; the 11-byte field of C>S 0xf55 / S>C 0xf54
TRIES_DEFAULT = 5                          # ours: emulator.ini [worldmatch] daily_tries

# gt.tsv (scratchpad/loc) row 12788, Value_US: "You’ve reached max daily challenging counts." - U+2019
# cannot be encoded in a cp949 char[], so the ASCII apostrophe goes on the wire (see the docstring).
MAX_TRIES_TEXT = "You've reached max daily challenging counts."      # 12788 (section 3.9)

SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS SKID_WMLAPTIME_TB(
 SERVERID numeric(18,0) NOT NULL, CID numeric(18,0) NOT NULL, CNAME varchar(32), NICKNAME varchar(16),
 SEASON integer NOT NULL, BESTSEC real, TRIES integer NOT NULL DEFAULT 0, TRYDAY integer NOT NULL DEFAULT 0,
 PRIMARY KEY (SERVERID, CID, SEASON))"""
ROW_SQL = "SELECT NICKNAME, BESTSEC, TRIES, TRYDAY FROM SKID_WMLAPTIME_TB WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
# the row the nickname / tries are stored on, when the player has not set a lap yet (BESTSEC stays NULL, so
# the row never reaches 0xf51)
ENSURE_SQL = ("INSERT INTO SKID_WMLAPTIME_TB(SERVERID, CID, CNAME, NICKNAME, SEASON, BESTSEC, TRIES, TRYDAY)"
              " VALUES (%s, %s, %s, '', %s, NULL, 0, 0) ON CONFLICT DO NOTHING")
NICK_SQL = "UPDATE SKID_WMLAPTIME_TB SET NICKNAME=%s WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
USED_SQL = ("SELECT CID FROM SKID_WMLAPTIME_TB WHERE SERVERID=%s AND SEASON=%s AND CID<>%s"
            " AND LOWER(NICKNAME)=LOWER(%s)")
TRY_SQL = "UPDATE SKID_WMLAPTIME_TB SET TRIES=%s, TRYDAY=%s WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
# one statement keeps the best lap of the season and leaves NICKNAME / TRIES / TRYDAY alone
BEST_SQL = ("INSERT INTO SKID_WMLAPTIME_TB(SERVERID, CID, CNAME, NICKNAME, SEASON, BESTSEC, TRIES, TRYDAY)"
            " VALUES (%s, %s, %s, '', %s, %s, 0, 0) ON CONFLICT (SERVERID, CID, SEASON) DO UPDATE SET"
            " CNAME=EXCLUDED.CNAME,"
            " BESTSEC=CASE WHEN SKID_WMLAPTIME_TB.BESTSEC IS NULL"
            " OR EXCLUDED.BESTSEC < SKID_WMLAPTIME_TB.BESTSEC"
            " THEN EXCLUDED.BESTSEC ELSE SKID_WMLAPTIME_TB.BESTSEC END")
LIST_SQL = ("SELECT w.CNAME, w.NICKNAME, w.BESTSEC, ISNULL(c.NLEVEL, 0), w.CID"
            " FROM SKID_WMLAPTIME_TB w LEFT JOIN SKID_CHARACTER_TB c"
            " ON c.SERVERID=w.SERVERID AND c.CID=w.CID"
            " WHERE w.SERVERID=%s AND w.SEASON=%s AND w.BESTSEC IS NOT NULL"
            " ORDER BY w.BESTSEC, w.CID")

Season = namedtuple('Season', 'number city track stat begin end reward_begin reward_end '
                             'begin_text end_text reward_begin_text reward_end_text')
DATE_FORMATS = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d')

_ready = False          # the table has been created on this connection set


# ---- strings (rankings.py's convention) -----------------------------------------------------------------

def sstr(text, size):
    """A single-byte char[] field: the client prints these with "%s" (section 3.2 / 3.6)."""
    return (text or '').encode('cp949', 'replace')[:size - 1].ljust(size, b'\0')


def _decode(raw):
    return raw.split(b'\0', 1)[0].decode('cp949', 'replace')


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _cell(row, col, name):
    i = col.get(name)
    return row[i].strip().strip('"') if i is not None and i < len(row) else ''


# ---- the season table (section 5) -----------------------------------------------------------------------

def season_table():
    """Init/WorldMatchSeasonLaptime.xlt -> [Season], in file order.

    UTF-16-LE, tab separated; the header row is the first whose first cell is 'Idx' or 'Index'
    (case-insensitive). The columns are the 2016 client's own (section 5): the season number, the city /
    track / stat table ids and four dates. A missing or broken file gives [], which the callers treat as
    "season 0" (the burst is still answered: section 9's "never leave C>S 0xf53 unanswered").
    """
    path = os.path.join(context.data.root, 'Init', 'WorldMatchSeasonLaptime.xlt')
    try:
        with open(path, 'rb') as f:
            text = f.read().decode('utf-16-le').lstrip('\ufeff')
    except OSError:
        return []
    lines = [line.split('\t') for line in text.split('\r\n')]
    header = next((r for r in lines if r and r[0].strip().lower() in ('idx', 'index')), None)
    if header is None:
        return []
    col = {name.strip().lower(): i for i, name in enumerate(header)}
    out, started = [], False
    for row in lines:
        if row is header:
            started = True
            continue
        if not started or len(row) < 2:
            continue
        number = _cell(row, col, 'season number')
        if not number.lstrip('-').isdigit():
            continue
        out.append(Season(_int(number), _int(_cell(row, col, 'city id')), _int(_cell(row, col, 'track id')),
                          _int(_cell(row, col, 'stat table index')),
                          _date(_cell(row, col, 'begin date')), _date(_cell(row, col, 'end date')),
                          _date(_cell(row, col, 'reward send start date')),
                          _date(_cell(row, col, 'reward send end date')),
                          _cell(row, col, 'begin date'), _cell(row, col, 'end date'),
                          _cell(row, col, 'reward send start date'),
                          _cell(row, col, 'reward send end date')))
    return out


def pick_season(seasons=None, when=None):
    """-> (Season or None, state): the row whose tournament period contains `when`, else the latest row
    whose begin is past; state 0 while racing, 1 once that row's reward period has begun (section 3.7)."""
    seasons = season_table() if seasons is None else seasons
    when = when or datetime.now()
    for s in seasons:
        if s.begin and s.end and s.begin <= when <= s.end:
            return s, STATE_RACING
    for s in seasons:
        if s.reward_begin and s.reward_end and s.reward_begin <= when <= s.reward_end:
            return s, STATE_REWARD
    past = [s for s in seasons if s.begin and s.begin <= when]
    if not past:
        return None, STATE_RACING
    s = max(past, key=lambda x: x.begin)
    if s.reward_end and when > s.reward_end:
        return s, STATE_RACING          # ours: the table's seasons ended in 2014, so the last one keeps running
    return s, STATE_REWARD if s.reward_begin and when >= s.reward_begin else STATE_RACING


def season_now(when=None):
    return pick_season(season_table(), when)


# ---- configuration --------------------------------------------------------------------------------------

def config():
    """emulator.ini [worldmatch] as a dict (the lead fills context.worldmatch; default {} = off)."""
    value = getattr(context, 'worldmatch', None)
    return value if isinstance(value, dict) else {}


def enabled():
    return is_2016() and bool(config().get('enabled'))


def daily_tries():
    return max(_int(config().get('daily_tries', TRIES_DEFAULT), TRIES_DEFAULT), 0)


def _today():
    """TRYDAY: the local date as YYYYMMDD (ours; the client sends no day)."""
    return int(datetime.now().strftime('%Y%m%d'))


# ---- the database ---------------------------------------------------------------------------------------

async def ensure():
    global _ready
    if not _ready:
        await context.db.execute(SCHEMA_SQL)
        _ready = True


async def my_row(cid, season):
    """(nickname, best seconds or None, tries, tryday) of one character's season row."""
    await ensure()
    db = context.db
    r = await db.row(ROW_SQL, (db.server_id, cid, season))
    return (r[0] or '', None if r[1] is None else float(r[1]), _int(r[2]), _int(r[3])) if r else ('', None, 0, 0)


async def tries_used(cid, season):
    """Today's tries (a row whose TRYDAY is an older day has used none: section 9.3)."""
    row = await my_row(cid, season)
    return row[2] if row[3] == _today() else 0


def used_today(tries, day):
    return tries if day == _today() else 0


async def set_nickname(cid, name, season):
    db = context.db
    await ensure()
    await db.execute(NICK_SQL, (name, db.server_id, cid, season))


async def nickname_taken(cid, name, season):
    db = context.db
    await ensure()
    return await db.row(USED_SQL, (db.server_id, season, cid, name)) is not None


async def list_rows(season):
    """[(name, nickname, seconds, level, cid)] of the season, best first (only rows with BESTSEC)."""
    await ensure()
    db = context.db
    rows = await db.rows(LIST_SQL, (db.server_id, season))
    return [(r[0] or '', r[1] or '', float(r[2]), _int(r[3]), _int(r[4])) for r in rows][:MAX_ROWS]


def my_rank(rows, cid):
    """-> (1-based rank or 0, the row) of a character in the 0xf51 list."""
    for i, row in enumerate(rows, 1):
        if row[4] == cid:
            return i, row
    return 0, None


# ---- records --------------------------------------------------------------------------------------------

def nation_record(name, nickname, seconds, level):
    """One 0xf51 record (section 3.2): name @0, country @0x15, nickname @0x20, seconds @0x2d, level @0x31."""
    out = bytearray(REC)
    out[0x00:0x15] = sstr(name, 21)
    out[0x15:0x20] = sstr(COUNTRY, 11)
    out[0x20:0x2d] = sstr(nickname, 13)
    struct.pack_into('<fI', out, 0x2d, seconds, level)
    return bytes(out)


def my_record(name, nickname, level, seconds, rank):
    """The 93-byte own record (section 3.6): name @0x21, country @0x36, nickname @0x41, level @0x4c,
    seconds @0x50, rank A @0x54, rank B @0x58; frame offsets are these + 6."""
    out = bytearray(MY_REC)
    out[0x21:0x36] = sstr(name, 21)
    out[0x36:0x41] = sstr(COUNTRY, 11)
    out[0x41:0x4c] = sstr(nickname, 11)
    struct.pack_into('<IfII', out, 0x4c, level, seconds, rank, rank)
    return bytes(out)


def season_frame(season, state):
    """0xf59 (202): season number @2, state @6, the four date columns @0xa as 4 x char[48]."""
    out = bytearray(SEASON_LEN - 2)
    struct.pack_into('<II', out, 0, _int(getattr(season, 'number', 0)), state)
    texts = ((season.begin_text, season.end_text, season.reward_begin_text, season.reward_end_text)
             if season else ('', '', '', ''))
    for i, text in enumerate(texts):
        out[8 + i * 48:8 + (i + 1) * 48] = sstr(text, 48)
    return Frame(0xf59, bytes(out))


def tries_frame(used):
    """0xf5c (6): the tries already used today."""
    return Frame(0xf5c, struct.pack('<I', max(used, 0)))


def record_frame(name, nickname, level, seconds, rank):
    """0xf58 (99): 4 unread bytes, then the 93-byte own record."""
    return Frame(0xf58, bytes(4) + my_record(name, nickname, level, seconds, rank))


def list_frame(rows):
    """0xf51 (6 + 0x35*n): n, then the season records best first. The handler takes n = 0 as 1 for its size
    (0x53b9bb: (max(n, 1) - 1) * 0x35 + 0x3b), so an empty list still carries one zero record (lead, session 46)."""
    body = b''.join(nation_record(*r[:4]) for r in rows) or bytes(REC)
    return Frame(0xf51, struct.pack('<I', len(rows)) + body)


def race_info_frame(serial, name):
    """0xf57 (0xe + len): the rank-1 holder's serial (0 offline), 0, len >= 1, the name without NUL."""
    text = (name or '').encode('cp949', 'replace') or b'-'      # len must be >= 1 (0x531612)
    return Frame(0xf57, struct.pack('<III', serial, 0, len(text)) + text)


def nickname_frame(ok, name=''):
    """0xf54 (28): result @2 (0 rejected -> 12789), the accepted nickname @6, 11 unread bytes @0x11."""
    return Frame(0xf54, struct.pack('<I', 1 if ok else 0) + sstr(name if ok else '', 11) + bytes(11))


def canceled_frame(text):
    """0xf5e (130): an already-localised reason in a char[128]."""
    return Frame(0xf5e, sstr(text, 128))


def build_status_info(p, season):
    """S>C 0x3c0 Cmd_WMLaptimeStatusInfo (0xa4 + 0x50*n; handler 0x542c20) for the season's track.

    Lead, session 46 (docs/neo_work/WM_AREA_BLOB.md, checked at 0x521cc0): the 112-byte block @0x02 and the 44-byte
    block @0x72 are the player's car **stat frame**, the same two blocks as the body of 0x2f8 StatUpdate (its handler
    0x521cc0 hands msg+2 / msg+0x72 to the same 0x784470 and returns 0x9e). With BattleZone.WorldMatch set the
    lap-time race loader (0x7caad5 / 0x7cab49 / 0x7cc74a / 0x7cc9e6, flag test only) applies them and takes the track
    from @0x9e (PVPTrackInfo Id, 70-73) and the city from @0xa0 (PVPTrackInfo city 1-4 = the season's 0-based
    City ID + 1). @0xa2 n = 0 (the 0x50 records are never read). Zeroed blocks would give the car zero stats.
    """
    from .records import enchant_bonus
    track = season.track if season else 0
    city = (season.city + 1) if season else 0
    return Frame(0x3c0, p.stats().encode() + enchant_bonus() + struct.pack('<HHH', track, city, 0))


# ---- the replies ----------------------------------------------------------------------------------------

def _player(session):
    return session.state.get('player')


async def send_records(session, season):
    """S>C 0xf58 + 0xf51: my record and the season list (the post-race refresh, section 8.6)."""
    p = _player(session)
    cid = p.char.cid if p else 0
    nickname, best, _tries, _day = await my_row(cid, season) if cid else ('', None, 0, 0)
    rows = await list_rows(season)
    rank = my_rank(rows, cid)[0]
    name, level = (p.char.name, p.char.level) if p else ('', 0)
    send(session, record_frame(name, nickname, level, best or 0.0, rank), list_frame(rows))


async def send_all(session):
    """The 0xf53 / 0xf56 burst: 0xf59, 0xf5c, 0xf58, 0xf51, and 0xf57 when rank 1 is taken."""
    p = _player(session)
    cid = p.char.cid if p else 0
    season, state = season_now()
    number = season.number if season else 0
    nickname, best, tries, day = await my_row(cid, number) if cid else ('', None, 0, 0)
    used = used_today(tries, day)
    rows = await list_rows(number)
    rank = my_rank(rows, cid)[0]
    name, level = (p.char.name, p.char.level) if p else ('', 0)
    frames = [season_frame(season, state), tries_frame(used),
              record_frame(name, nickname, level, best or 0.0, rank), list_frame(rows)]
    if rows:                                     # len must be >= 1: no holder, no 0xf57 (section 3.5)
        frames.append(race_info_frame(_serial_of_cid(rows[0][4]), rows[0][0]))
    if p:
        frames.insert(0, build_status_info(p, season))
    send(session, *frames)


def _serial_of_cid(cid):
    """The online session's serial of a character, 0 when it is offline (section 3.5)."""
    for s in list(sessions.values()):
        p = s.state.get('player')
        if p and p.char.cid == cid:
            return serial_of(s)
    return 0


# ---- requests -------------------------------------------------------------------------------------------

@on(SVC, C2S, 0xf53)
async def refresh(session, frame):
    """C>S 0xf53 (6; the argument is always 3 and unused, section 4.2) -> the full burst."""
    if not enabled():
        return
    await send_all(session)


@on(SVC, C2S, 0xf56)
async def nickname_done(session, frame):
    """C>S 0xf56 (2; sent after a good 0xf54) -> the full burst (section 9.7)."""
    if not enabled():
        return
    await send_all(session)


@on(SVC, C2S, 0xf55)
async def set_nickname_request(session, frame):
    """C>S 0xf55 (0x18; 11 bytes at +2) -> 0xf54 ok / 0xf54 rejected (section 9.7, text 12744)."""
    if not enabled():
        return
    p = _player(session)
    if not p:
        return send(session, nickname_frame(False))
    name = _decode(frame.payload[:NICK_FIELD])
    season, _state = season_now()
    number = season.number if season else 0
    # 12744 "Your World Match Nickname must be alphanumeric and between 2~10 characters." is the client's
    # own rule text; it does not enforce it, so the server does. A rejection is 0xf54 result 0, which makes
    # the client print 12789 "This name is unable to use." (0x5ecf11-0x5ecf32).
    if not (NICK_MIN <= len(name) <= NICK_MAX and name.isascii() and name.isalnum()):
        session.log.note(f'world match: nickname {name!r} refused (12744: 2..10 alphanumeric)')
        return send(session, nickname_frame(False))
    if await nickname_taken(p.char.cid, name, number):
        session.log.note(f'world match: nickname {name!r} already taken in season {number}')
        return send(session, nickname_frame(False))
    db = context.db
    await db.execute(ENSURE_SQL, (db.server_id, p.char.cid, p.char.name, number))
    await set_nickname(p.char.cid, name, number)
    session.log.note(f'world match: nickname of {p.char.name!r} set to {name!r} for season {number}')
    send(session, nickname_frame(True, name))


@on(SVC, C2S, 0xf5c)
async def daily_count(session, frame):
    """C>S 0xf5c (6; the u32 at +2 is never written by the client) -> 0xf5c with today's tries."""
    if not enabled():
        return
    p = _player(session)
    if not p:
        return
    season, _state = season_now()
    send(session, tries_frame(await tries_used(p.char.cid, season.number if season else 0)))


@on(SVC, C2S, 0xf5d)
async def start_try(session, frame):
    """C>S 0xf5d (2; sent together with 0xf5c by 0x5ecfe0) -> allow silently, or 0xf5e when out of tries."""
    if not enabled():
        return
    p = _player(session)
    if not p:
        return
    season, _state = season_now()
    number = season.number if season else 0
    used = await tries_used(p.char.cid, number)
    if used >= daily_tries():
        session.log.note(f'world match: {p.char.name!r} out of tries ({used}/{daily_tries()}) in season {number}')
        return send(session, canceled_frame(MAX_TRIES_TEXT))
    db = context.db
    await db.execute(ENSURE_SQL, (db.server_id, p.char.cid, p.char.name, number))
    await db.execute(TRY_SQL, (used + 1, _today(), db.server_id, p.char.cid, number))
    session.state['wm_try'] = number
    send(session, build_status_info(p, season))      # after the try starts: 0x2f8 is ignored while mgr+0x88 == 1 (0x521cc5)
    session.log.note(f'world match: {p.char.name!r} starts try {used + 1}/{daily_tries()} in season {number}')


@on(SVC, C2S, 0xf5a)
async def reward_request(session, frame):
    """C>S 0xf5a (6; the reward window's [win+0x144], meaning unresolved, section 4.3) -> 0xf51."""
    if not enabled():
        return
    season, _state = season_now()
    send(session, list_frame(await list_rows(season.number if season else 0)))


@on(SVC, C2S, 0xf5b)
async def gm_command(session, frame):
    """C>S 0xf5b (8; three u16, GM chat command 0x6145a0 only): logged, no reply (section 9.11)."""
    if not enabled():
        return
    p = frame.payload
    if len(p) < 6:
        return
    a, b, c = struct.unpack_from('<HHH', p)
    session.log.note(f'world match: GM command 0xf5b {a} {b} {c} (no reply)')


# ---- the lap (called from laptime.py) -------------------------------------------------------------------

async def record_lap(session, lap_ms):
    """A 0x52c LapTimeRecord's lap time -> the season's best, then 0xf58 + 0xf51 (section 8.6).

    Called by ``laptime.lap_record`` only while a World Match try is running (``session.state['wm_try']``
    = the season it was started in, set by C>S 0xf5d). Returns quietly otherwise, so an ordinary battle
    zone Lap Time race costs nothing. The best (lowest) seconds of the try is kept; a slower lap leaves the
    stored value alone but still refreshes the client (the record it shows is the season's best).
    """
    season = session.state.get('wm_try')
    if not season or not is_2016():
        return
    p = _player(session)
    if not p or lap_ms is None or lap_ms <= 0:
        return
    seconds = lap_ms / 1000.0
    db = context.db
    await ensure()
    await db.execute(BEST_SQL, (db.server_id, p.char.cid, p.char.name, season, seconds))
    await send_records(session, season)
    session.log.note(f'world match: {p.char.name!r} lap {seconds:.3f} s in season {season}')
