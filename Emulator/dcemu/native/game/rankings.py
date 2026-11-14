"""2016 client: the RANKING window's server side (0xfa0 - 0xfb2).

Every layout here comes from the 2016 ``DriftCity.exe`` disassembly as collected in
``docs/neo_work/RANK_PROTOCOL.md`` (section numbers below refer to that file; the VAs are the file's
objdump VAs). The 2011 client's ranking frames have different sizes (0x8b2 for 0xfa1, no 0xfa2+), so
every handler returns at once unless ``version.is_2016()``.

Requests -> replies (all sizes include the u16 type, all offsets from the frame start; payload
offset = frame offset - 2; page size is the client's literal 12):

  C>S 0xfa2 (0x12): i32 category, u32 page, u32 page size, u32 measure
      -> S>C 0xfa3 (0x16 + n*0xc4): page @2, pages @6, n @0xa, 0x00ff0000 @0xe, measure @0x12
      (echoed), n 0xc4 records @0x16.
  C>S 0xfa4 (0x39): i32 category, u32 page size, char[21] name @0xa, u8 flag @0x34, u32 measure
      @0x35 -> S>C 0xfa5 (0x1e + n*0xc4): key1 @2, key2 @6, page @0xa, pages @0xe, n @0x12,
      0x0000ff01 @0x16, measure @0x1a, n 0xc4 records @0x1e. A miss is 0xfb2 code 4, except that the
      client's automatic "locate me" request (flag 1) is answered with page 0 and key1/key2 = 0.
  C>S 0xfaa (0xa): page, page size -> S>C 0xfab (0x12 + n*0x96): page @2, pages @6, n @0xa,
      0x00ff0000 @0xe, n 0x96 team records @0x12.
  C>S 0xfac (0x20): page size, char[13] team name @6 -> S>C 0xfad (0x1a + n*0x96): key1 @2,
      key2 @6, page @0xa, pages @0xe, n @0x12, 0x0000ff01 @0x16, records @0x1a. Miss -> 0xfb2 code 4.
  C>S 0xfae (0xe): category, page, page size -> S>C 0xfaf (0x12 + n*0xc4): page, pages, n,
      0x00ff0000 @0xe, records @0x12.
  C>S 0xfb0 (0x34): category, page size, char[21] name @0xa -> S>C 0xfb1 (0x1a + n*0xc4): key1 @2,
      key2 @6, page @0xa, pages @0xe, n @0x12, 0x0000ff01 @0x16, records @0x1a. Miss -> 0xfb2 code 4.
  C>S 0xfa1 (0x9a6, character id @2) -> S>C 0xfa1 (0x9a6): the same empty frame the login sends
      (login.info_fa0, -1 at +0xd2); the window re-asks whenever its cached YYYYMM is stale
      (0x6b2ed0, 0x6b2f5f-0x6b2fa4) and waits in state 1 until it is answered, so it is answered even
      though nothing had registered C>S 0xfa1 before.
  0xfb2 (6): u16 type, u32 code @2: 2 = bad page (page >= pages, pages > 0), 4 = not on the ranking,
  3 = silent (only clears the window's busy flag) for a frame too short to parse.

Evidence for the above (RANK_PROTOCOL.md sections 1-7): the six reply handlers 0x53f2e0 (0xfa3),
0x53f360 (0xfa5), 0x53f400 (0xfab), 0x53f480 (0xfad), 0x53f520 (0xfaf), 0x53f5a0 (0xfb1);
0x53f0f0 (0xfa1); 0x53f190 (0xfb2); the 0x00ff0000 test at 0x53f2e5 / 0x53f405 / 0x53f525 and the
0x0000ff01 test at 0x53f365 / 0x53f485 / 0x53f5a5; 12 entries per page (0x6b480c, 0x6b45c0); the
0xc4 / 0x96 record sizes and their field offsets (section 5.1 / 5.2); the selection-key pairs
0x6b29e0 / 0x6b28fe; the 0xfb2 codes 0x53f2b8-0x53f2d6 (section 4.9).

What is OURS (the 2016 server's ranking data was not available):
  * every category ranks the same list, and measure 0/1 differ only in the score pair (no
    per-category counters are kept);
  * the character ranking (0xfa3 / 0xfa5) and the honor ranking (0xfaf / 0xfb1) are every alive
    character of this server (SKID_CHARACTER_TB, SERVERID = context.db.server_id, STATE 'P') ordered
    by EXP desc, level desc, CID; a row's key pair is its CID and its 1-based rank. The 0xc4 record
    keeps the client's level/name and puts EXP at +0xac/+0xb4 (measure 0/1); the honor layout puts
    the level at +0xac instead. Licence (+0x36..0x5b), car (+0x5c) and the unknown cells stay 0;
  * the team ranking (0xfab / 0xfad) is the server's open crews (SKID_TEAM_TB, TEAMSTATE 'A') ordered
    by TEAMPOINT desc, CHANNELWINCNT desc, TID (the column names and ISNULL of crews.py's TEAM_SQL /
    RANK_ORDER_SQL); MEMBERCNT is the "class" number at +0x36, CREATEDATE the 'YYYYMMDD' text at
    +0x7e (section 5.2's date field is parsed with base 10);
  * the string fields are single byte: the renderers pass record +0x0c / +0x10 / +0x42 / +0x5c as a
    ``char*`` to 0x4f0eb0 and print it with "%s" (0x6b3b1e-0x6b3b4d), so a name is written in the
    Korean client's ANSI code page (cp949, as crewlevel.py does for its char[256] crew text) and not
    as UTF-16; ASCII names are unaffected;
  * both lists are cached for TTL seconds (60; crews.py does the same);
  * a character name is matched case-insensitively, trimmed.

The handlers are registered on both 'native:game' and 'native:ranking': the 2016 client sends these
over a separate connection whose service is not settled yet. ``session.to_client`` works on either.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context, now
from ..version import is_2016

SERVICES = ('native:game', 'native:ranking')
PAGE = 12                                # 0x6b480c / 0x6b4ba6: the client's literal page size
CHAR_REC, TEAM_REC = 0xc4, 0x96          # section 5.1 / 5.2
TTL = 60                                 # seconds a computed ranking is kept
SIG_PAGE = 0x00ff0000                    # section 1: "page reply"
SIG_SEARCH = 0x0000ff01                  # section 1: "search reply"
ERR_SILENT, ERR_PAGE, ERR_NOT_FOUND = 3, 2, 4      # section 4.9
CHARS = 42                               # the 0xc4 name field (0xc4 + 0x0c .. + 0x36)
TEAM_NAME = 26                           # the 0x96 name field (+0x10 .. +0x2a)
MASTER_NAME = 42                         # +0x46 .. +0x70
CREATED = 24                             # +0x7e .. +0x96

CHAR_RANK_SQL = ("SELECT CID, CNAME, NLEVEL, NEXP FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND STATE='P'"
                 " ORDER BY ISNULL(NEXP, 0) DESC, ISNULL(NLEVEL, 0) DESC, CID")
TEAM_RANK_SQL = ("SELECT TID, TMARKID, TEAMNAME, TEAMPOINT, CHANNELWINCNT, MEMBERCNT, CNAME, CREATEDATE"
                 " FROM SKID_TEAM_TB WHERE SERVERID=%s AND TEAMSTATE='A'"
                 " ORDER BY ISNULL(TEAMPOINT, 0) DESC, ISNULL(CHANNELWINCNT, 0) DESC, TID")

_char_cache = (0, [])                    # (when, rows): rows are tuples with the 1-based rank first
_team_cache = (0, [])


def _on(msg_type):
    """Register one handler on both services (they see the same frame shape)."""
    def deco(fn):
        for service in SERVICES:
            on(service, C2S, msg_type)(fn)
        return fn
    return deco


def _i(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _s(v):
    return (v or '').strip()


def _u32(v):
    return min(max(_i(v), 0), 0xffffffff)


def sstr(text, size):
    """A single-byte string field (see the module docstring: the client prints it with "%s")."""
    return (text or '').encode('cp949', 'replace')[:size - 1].ljust(size, b'\0')


def _decode(raw):
    """A single-byte name field of a request."""
    return raw.split(b'\0', 1)[0].decode('cp949', 'replace').strip()


def _pages(n):
    return (n + PAGE - 1) // PAGE


def _error(session, code):
    session.to_client(Frame(0xfb2, struct.pack('<I', code)))


def _date(value):
    """SKID_TEAM_TB.CREATEDATE as the 'YYYYMMDD' text at record +0x7e ('' when unset)."""
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y%m%d')
    return ''.join(ch for ch in str(value) if ch.isdigit())[:8]


# ---- the data (ours, see the docstring) ----------------------------------------------------------------------------

async def characters():
    """[(rank, cid, name, level, exp)] of the server's characters, best first. Cached RANK_TTL seconds."""
    global _char_cache
    when, rows = _char_cache
    if when and now() - when < TTL:
        return rows
    db = context.db
    raw = await db.rows(CHAR_RANK_SQL, (db.server_id,))
    rows = [(i, _i(r[0]), _s(r[1]), _i(r[2]), _i(r[3])) for i, r in enumerate(raw or (), 1)]
    _char_cache = (now(), rows)
    return rows


async def teams():
    """[(rank, tid, mark, name, point, wins, members, master, created)] of the open crews. Cached."""
    global _team_cache
    when, rows = _team_cache
    if when and now() - when < TTL:
        return rows
    db = context.db
    raw = await db.rows(TEAM_RANK_SQL, (db.server_id,))
    rows = [(i, _i(r[0]), _i(r[1]), _s(r[2]), _i(r[3]), _i(r[4]), _i(r[5]), _s(r[6]), _date(r[7]))
            for i, r in enumerate(raw or (), 1)]
    _team_cache = (now(), rows)
    return rows


# ---- records --------------------------------------------------------------------------------------------------------

def char_record(row, honor=False):
    """The 0xc4 record (section 5.1). row = (rank, cid, name, level, exp)."""
    rank, cid, name, level, exp = row
    out = bytearray(CHAR_REC)
    struct.pack_into('<III', out, 0x00, _u32(cid), _u32(rank), _u32(level))
    out[0x0c:0x0c + CHARS] = sstr(name, CHARS)
    struct.pack_into('<II', out, 0xa4, _u32(cid), _u32(level))     # 0xa4 CID, 0xa8 level
    struct.pack_into('<I', out, 0xac, _u32(level if honor else exp))
    struct.pack_into('<I', out, 0xb4, _u32(exp))                   # the measure-1 score
    return bytes(out)


def team_record(row):
    """The 0x96 record (section 5.2). row = (rank, tid, mark, name, point, wins, members, master, created)."""
    rank, tid, mark, name, point, wins, members, master, created = row
    out = bytearray(TEAM_REC)
    struct.pack_into('<II', out, 0x08, _u32(point), _u32(wins))
    out[0x10:0x10 + TEAM_NAME] = sstr(name, TEAM_NAME)
    struct.pack_into('<II', out, 0x2a, _u32(mark), _u32(tid))      # the selection-key pair
    struct.pack_into('<Q', out, 0x36, min(max(members, 0), 0xffffffffffffffff))   # the "class" number
    out[0x46:0x46 + MASTER_NAME] = sstr(master, MASTER_NAME)
    struct.pack_into('<I', out, 0x72, _u32(rank))
    out[0x7e:0x7e + CREATED] = sstr(created, CREATED)
    return bytes(out)


def _recs(rows, build):
    return b''.join(build(r) for r in rows)


# ---- replies --------------------------------------------------------------------------------------------------------

def rank_page(page, pages, rows, measure):
    """0xfa3: page, pages, n, 0x00ff0000, the echoed measure, the 0xc4 records."""
    return Frame(0xfa3, struct.pack('<IIIII', page, pages, len(rows), SIG_PAGE, measure & 0xffffffff)
                 + _recs(rows, char_record))


def char_search(key1, key2, page, pages, rows, measure):
    """0xfa5: the selection keys, the page that holds the row, the echoed measure, the page's records."""
    return Frame(0xfa5, struct.pack('<IIIIIII', key1, key2, page, pages, len(rows), SIG_SEARCH,
                                    measure & 0xffffffff) + _recs(rows, char_record))


def honor_page(page, pages, rows):
    """0xfaf: no measure and no sub field (sub is hard-coded 0 by 0x53f568)."""
    return Frame(0xfaf, struct.pack('<IIII', page, pages, len(rows), SIG_PAGE)
                 + _recs(rows, lambda r: char_record(r, honor=True)))


def honor_search(key1, key2, page, pages, rows):
    """0xfb1."""
    return Frame(0xfb1, struct.pack('<IIIII', key1, key2, page, pages, len(rows)) + struct.pack('<I', SIG_SEARCH)
                 + _recs(rows, lambda r: char_record(r, honor=True)))


def team_page(page, pages, rows):
    """0xfab."""
    return Frame(0xfab, struct.pack('<IIII', page, pages, len(rows), SIG_PAGE) + _recs(rows, team_record))


def team_search(key1, key2, page, pages, rows):
    """0xfad."""
    return Frame(0xfad, struct.pack('<IIIII', key1, key2, page, pages, len(rows)) + struct.pack('<I', SIG_SEARCH)
                 + _recs(rows, team_record))


# ---- requests -------------------------------------------------------------------------------------------------------

@_on(0xfa2)
async def ranking_page(session, frame):
    """C>S 0xfa2 -> 0xfa3 (character ranking page)."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 0x10:
        return _error(session, ERR_SILENT)
    _category, page, _size, measure = struct.unpack_from('<iIII', p)
    rows = await characters()
    pages = _pages(len(rows))
    if pages and page >= pages:
        return _error(session, ERR_PAGE)
    session.to_client(rank_page(page, pages, rows[page * PAGE:(page + 1) * PAGE], measure))


@_on(0xfa4)
async def ranking_search(session, frame):
    """C>S 0xfa4 -> 0xfa5, or 0xfb2 code 4 (page 0 with keys 0 for the client's automatic locate)."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 0x37:
        return _error(session, ERR_SILENT)
    _category, _size = struct.unpack_from('<iI', p)
    name = _decode(p[8:8 + 21])
    flag = p[0x32]
    measure, = struct.unpack_from('<I', p, 0x33)
    rows = await characters()
    pages = _pages(len(rows))
    want = name.casefold()
    for i, row in enumerate(rows):
        if row[2].casefold() == want:
            address = i // PAGE
            key1, key2 = row[1], row[0]
            session.to_client(char_search(key1, key2, address, pages, rows[address * PAGE:(address + 1) * PAGE],
                                          measure))
            return
    if flag == 1:                            # the tab's own "where am I" ask: show page 0, nothing selected
        session.to_client(char_search(0, 0, 0, pages, rows[:PAGE], measure))
        return
    _error(session, ERR_NOT_FOUND)


@_on(0xfaa)
async def team_page_request(session, frame):
    """C>S 0xfaa -> 0xfab (team ranking page)."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 8:
        return _error(session, ERR_SILENT)
    page, _size = struct.unpack_from('<II', p)
    rows = await teams()
    pages = _pages(len(rows))
    if pages and page >= pages:
        return _error(session, ERR_PAGE)
    session.to_client(team_page(page, pages, rows[page * PAGE:(page + 1) * PAGE]))


@_on(0xfac)
async def team_search_request(session, frame):
    """C>S 0xfac -> 0xfad, or 0xfb2 code 4."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 17:
        return _error(session, ERR_SILENT)
    name = _decode(p[4:4 + 13])
    rows = await teams()
    pages = _pages(len(rows))
    want = name.casefold()
    for i, row in enumerate(rows):
        if row[3].casefold() == want:
            address = i // PAGE
            session.to_client(team_search(row[2], row[1], address, pages, rows[address * PAGE:(address + 1) * PAGE]))
            return
    _error(session, ERR_NOT_FOUND)


@_on(0xfae)
async def honor_page_request(session, frame):
    """C>S 0xfae -> 0xfaf (honor ranking page)."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 0xc:
        return _error(session, ERR_SILENT)
    _category, page, _size = struct.unpack_from('<iII', p)
    rows = await characters()
    pages = _pages(len(rows))
    if pages and page >= pages:
        return _error(session, ERR_PAGE)
    session.to_client(honor_page(page, pages, rows[page * PAGE:(page + 1) * PAGE]))


@_on(0xfb0)
async def honor_search_request(session, frame):
    """C>S 0xfb0 -> 0xfb1, or 0xfb2 code 4."""
    if not is_2016():
        return
    p = frame.payload
    if len(p) < 0x1d:                        # name @0xa .. +0x1f in the frame (payload @8 .. +0x1d)
        return _error(session, ERR_SILENT)
    _category, _size = struct.unpack_from('<iI', p)
    name = _decode(p[8:8 + 21])
    rows = await characters()
    pages = _pages(len(rows))
    want = name.casefold()
    for i, row in enumerate(rows):
        if row[2].casefold() == want:
            address = i // PAGE
            session.to_client(honor_search(row[1], row[0], address, pages,
                                           rows[address * PAGE:(address + 1) * PAGE]))
            return
    _error(session, ERR_NOT_FOUND)


@_on(0xfa1)
async def my_rank_refresh(session, frame):
    """C>S 0xfa1 (0x9a6, character id @2) -> the login's 0xfa1 frame (login.info_fa0, -1 at +0xd2).

    The window sends this whenever its cached YYYYMM is stale (0x6b2ed0, 0x6b2f5f-0x6b2fa4, sender
    0x86ab50) and waits in state 1; before this handler nothing answered C>S 0xfa1, so the tab froze.
    """
    if not is_2016():
        return
    from .login import info_fa0
    await info_fa0(session, frame)
