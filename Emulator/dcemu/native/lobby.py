"""Native lobby service (11011): check-in, character list, name check, character creation.

Messages (offsets from the type; 2008 structs from ZoneServer.pdb, 2011 sizes from the client):
  0x29 C>S CheckInLobby  2011: 0xa8 bytes; 2008 BS_PktCheckInLobby: u32 version @2, u32 ticket @6,
                         ID @0xa (80 bytes), u32 time @0x5a, session ticket @0x5e (64).
  0x2a S>C CheckInLobbyAck: u32 result (0 OK), u32 permission.
  0x3c C>S UserInfo      2011: account ID (UTF-16) + ticket; 2008: empty.
  0x3d S>C UserInfoAck   u32 permission, u32 count, 64-byte UTF-16 string (2011 only: if it
                         equals the one the client keeps, it says "please log in again", so it
                         is a fresh token), count x XiStrCharKey (0x78): name (0x2a bytes),
                         int64 cid @0x2a, avatar @0x32, level @0x36, car id @0x3a (passed on when
                         entering the game), 2011: state @0x3e ('P', or 'R' = reserved for
                         deletion: cannot enter the game) and the deletion time (time_t on the
                         client's clock, which is the 2008 server's: native.time_t)
                         @0x42 (2008: car type, car colour), long time @0x46 (CDATE,
                         native.time_t), int64 team @0x4a, int64 team mark @0x52, team name (26
                         bytes) @0x5a, guild @0x74 (2011 reads a u16 @0x76).
  Deleting a character, 2011 (client: character select page; DeleteCharExpireDays):
  0x32 C>S/S>C SetCharState: name, int64 cid @0x2a, u32 state @0x32, u32 @0x36: from the client
                         the days to wait ('R') or 0 ('P' = cancel); from the server the deletion
                         time. The client stores state and time in the list entry.
  0x54 C>S DeleteChar (name), sent when the time has passed and the player confirms ("Are you
                         sure you want to delete this ID?"); -> 0x54 (name): the client drops it.
                         DB as the 2008 server: STATE 'D', MEMBERID '$' + member, DELDATE.
                         While reserved: STATE 'R', DELDATE = the deletion time.
  0x50 C>S CheckCharName (name)  -> 0x51 (name, bool usable)
  0x52 C>S CreateChar (name, u16 avatar, u32 car type, u32 colour) -> 0x53 (name, int64 cid, int car id)
  0x07 C>S ping (u32);  0x02 S>C keepalive (u32 server time, native.now), at once and every 3 s.
Database work as the 2008 server does it on SQL Server: the character row (CID is an identity
column: OUTPUT INSERTED.CID), then PC_SKID_CREATECAR for the first car (grade 1, Mitron =
the car's V1 capacity from the 2011 VehicleUpgrade.xlt).
"""
import asyncio
import secrets
import struct

from ..handlers import on, on_open
from ..protocol import C2S
from ..wire import Frame, read_wstr
from . import context, now, ticket_for, time_t
from .admin import account_valid

NAME_BYTES = 0x2a
CHECK_IN_ACK, USER_INFO_ACK, NAME_ACK, CREATE_ACK, KEEPALIVE = 0x2a, 0x3d, 0x51, 0x53, 0x02
KEEPALIVE_SECONDS = 3


def name_bytes(name):
    return name.encode('utf-16-le')[:NAME_BYTES - 2].ljust(NAME_BYTES, b'\0')


@on_open('native:lobby')
async def keepalive(session):
    """0x02 carries the server time; the client keeps it as its clock (the character select page
    counts down a reserved character's deletion with it), so the first one goes out at once."""
    while True:
        session.to_client(Frame(KEEPALIVE, struct.pack('<I', now())))
        await asyncio.sleep(KEEPALIVE_SECONDS)


@on('native:lobby', C2S, 0x29)
async def check_in(session, frame):
    p = frame.payload
    ticket = struct.unpack_from('<I', p, 4)[0]
    member = read_wstr(p, 8, 80)
    ok = bool(member) and ticket == ticket_for(member)
    if ok and not await account_valid(member):      # banned since the login (tickets outlive restarts)
        session.log.note(f'check-in {member!r}: the account is blocked')
        ok = False
    owner = member
    if ok:
        session.state['member'] = owner
    session.log.note(f'check-in {member!r}: {"ok" if ok else "bad ticket"}')
    session.to_client(Frame(CHECK_IN_ACK, struct.pack('<II', 0 if ok else 1, 0)))


@on('native:lobby', C2S, 0x3c)
async def user_info(session, frame):
    member = session.state.get('member')
    rows = []
    if member:
        rows = await context.db.rows(
            "SELECT c.CNAME, c.CID, c.AVATAR, c.NLEVEL, c.CURCAR, c.STATE, c.DELDATE, c.CDATE,"
            " c.TEAMID, t.TMARKID, t.TEAMNAME, c.GUILDTYPE"
            " FROM SKID_CHARACTER_TB c"
            " LEFT JOIN SKID_TEAM_TB t ON t.SERVERID = c.SERVERID AND t.TID = c.TEAMID"
            " WHERE c.SERVERID = %s AND c.MEMBERID = %s AND c.STATE IN ('P', 'R') ORDER BY c.CID",
            (context.db.server_id, member))
    out = []
    for name, cid, avatar, level, car, state, deldate, created, team, mark, team_name, guild in rows:
        state = (state or 'P').strip() or 'P'
        out.append(name_bytes(name)
                   + struct.pack('<qiiiIIi', int(cid), int(avatar or 0), int(level or 1), int(car or 0),
                                 ord(state), time_t(deldate) if state == 'R' else 0, time_t(created))
                   + struct.pack('<qq', int(team if team is not None else -1), int(mark or 0))
                   + (team_name or '').encode('utf-16-le')[:24].ljust(26, b'\0')
                   + struct.pack('<I', int(guild or 0)))
    token = secrets.token_hex(8).encode('utf-16-le').ljust(64, b'\0')
    session.log.note(f'user info {member!r}: {len(out)} characters')
    session.to_client(Frame(USER_INFO_ACK, struct.pack('<II', 0, len(out)) + token + b''.join(out)))


async def name_free(name):
    row = await context.db.row(
        # deleted characters (STATE 'D') free their name (user, 2026-10-15: a deleted character's name stayed taken)
        "SELECT (SELECT COUNT(*) FROM SKID_CHARACTER_TB WHERE UCNAME = UPPER(%s) AND STATE <> 'D')"
        " + (SELECT COUNT(*) FROM SKID_CNAMERESERVE_TB WHERE UCNAME = UPPER(%s))", (name, name))
    return row[0] == 0


@on('native:lobby', C2S, 0x50)
async def check_name(session, frame):
    name = read_wstr(frame.payload, 0, NAME_BYTES)
    free = bool(name.strip()) and await name_free(name)
    session.log.note(f'name {name!r}: {"free" if free else "taken"}')
    session.to_client(Frame(NAME_ACK, name_bytes(name) + bytes([1 if free else 0])))


# One transaction: the character row (CID is an identity column), its first car, CURCAR.
# NOCOUNT: otherwise the row counts of the INSERT/UPDATE come back before the SELECT.
CREATE_SQL = (
    "SET NOCOUNT ON; SET XACT_ABORT ON; BEGIN TRAN;"
    " DECLARE @c TABLE (cid numeric); DECLARE @cid numeric, @carid numeric;"
    " INSERT INTO SKID_CHARACTER_TB(SERVERID, CNAME, UCNAME, AVATAR, MEMBERID)"
    " OUTPUT INSERTED.CID INTO @c VALUES (%s, %s, UPPER(%s), %s, %s);"
    " SELECT @cid = cid FROM @c;"
    " EXEC PC_SKID_CREATECAR %s, @cid, %s, %s, %s, 1, 0, %s, 0, @carid OUTPUT;"
    " IF @carid > 0 UPDATE SKID_CHARACTER_TB SET CURCAR = @carid WHERE SERVERID = %s AND CID = @cid;"
    " ELSE ROLLBACK;"
    " IF @@TRANCOUNT > 0 COMMIT;"
    " SELECT CASE WHEN @carid > 0 THEN @cid ELSE -1 END, ISNULL(@carid, -1);")


@on('native:lobby', C2S, 0x52)
async def create_char(session, frame):
    p = frame.payload
    name = read_wstr(p, 0, NAME_BYTES)
    avatar, car_type, color = struct.unpack_from('<HII', p, NAME_BYTES)
    member = session.state.get('member')
    cid, car_id = -1, -1
    capacity = context.data.mitron_capacity(car_type)
    if member and capacity is not None and await name_free(name):
        try:
            cid, car_id = map(int, await context.db.row(CREATE_SQL, (
                context.db.server_id, name, name, avatar, member,
                context.db.server_id, name, car_type, color, capacity, context.db.server_id)))
        except Exception as e:                  # the transaction is rolled back; tell the client
            session.log.note(f'create {name!r} failed: {e}')
            cid, car_id = -1, -1
    session.log.note(f'create {name!r} avatar {avatar} car type {car_type}: cid {cid}, car {car_id}')
    session.to_client(Frame(CREATE_ACK, name_bytes(name) + struct.pack('<qi', cid, car_id)))


@on('native:lobby', C2S, 0x32)
async def set_char_state(session, frame):
    """Reserve a character for deletion ('R', wait n days) or cancel it ('P')."""
    p = frame.payload
    name = read_wstr(p, 0, NAME_BYTES)
    cid, state, days = struct.unpack_from('<qII', p, NAME_BYTES)
    member = session.state.get('member')
    if context.delete_wait_days is not None:
        days = context.delete_wait_days
    state = chr(state) if state in (ord('R'), ord('P')) else None
    row = None
    if member and state:
        row = await context.db.row(
            "SET NOCOUNT ON; UPDATE SKID_CHARACTER_TB SET STATE = %s,"
            " DELDATE = CASE WHEN %s = 'R' THEN DATEADD(day, %s, GETUTCDATE()) ELSE NULL END"
            " WHERE SERVERID = %s AND CID = %s AND MEMBERID = %s AND STATE IN ('P', 'R');"
            " SELECT STATE, DELDATE FROM SKID_CHARACTER_TB WHERE SERVERID = %s AND CID = %s AND MEMBERID = %s",
            (state, state, int(days), context.db.server_id, cid, member, context.db.server_id, cid, member))
    cur, when = (row[0].strip(), time_t(row[1])) if row else ('P', 0)
    session.log.note(f'char state {name!r}: asked {state!r} ({days} days) -> {cur!r} until {when}')
    session.to_client(Frame(0x32, name_bytes(name) + struct.pack('<qII', cid, ord(cur), when if cur == 'R' else 0)))


@on('native:lobby', C2S, 0x54)
async def delete_char(session, frame):
    """Delete a reserved character whose time has passed (as the 2008 server: STATE 'D'). With delete_wait_days = 0 an
    unreserved one too: the client sends 0x54 without a 0x32 first for a new character (user, 2026-10-15: a level 1
    character in the tutorial could not be deleted)."""
    name = read_wstr(frame.payload, 0, NAME_BYTES)
    member = session.state.get('member')
    row = None
    at_once = 1 if context.delete_wait_days == 0 else 0
    if member:
        row = await context.db.row(
            "SET NOCOUNT ON; UPDATE SKID_CHARACTER_TB SET MEMBERID = '$' + MEMBERID, STATE = 'D', DELDATE = GETUTCDATE()"
            " WHERE SERVERID = %s AND UCNAME = UPPER(%s) AND MEMBERID = %s AND ((STATE = 'R' AND DELDATE <= GETUTCDATE())"
            " OR (STATE = 'P' AND %s = 1));"
            " SELECT @@ROWCOUNT", (context.db.server_id, name, member, at_once))
    ok = bool(row and row[0])
    session.log.note(f'delete {name!r}: {"done" if ok else "refused (not reserved, or its time has not come)"}')
    if ok:
        session.to_client(Frame(0x54, name_bytes(name)))


@on('native:lobby', C2S, 0x07)
async def ping(session, frame):
    pass
