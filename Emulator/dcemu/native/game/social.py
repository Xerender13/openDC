"""Friends, parties and the profile search (the 2008 server's XiCsCharInfo friend functions, BS_Party,
Cmd_GameCharInfoEx), in the 2011 layouts. Area (city) chat is in native/area.py.

Friends (SKID_FRIEND_TB: SERVERID, CID, FCID, FSTATE; XiCsCharInfo::BeFriendTo / BeFriendAccept):
  XiStrFriend, 2011 0x70 (2008 0x6c + 4 new bytes @0x64, client 0x51b7e0 steps by 0x70): name 0x2a, team name
  0x1a @0x2a, i64 cid @0x44, i64 team @0x4c, i64 team mark @0x54, i32 state @0x5c (the FSTATE letter: 'F'
  friend, 'R' asked by me, 'C' asking me; the client tests 'B' blocked), the place @0x60, 8 bytes now (client 0x63a9b0: u8 kind @0x60: 0 offline,
  1 in the city with a u16 area @0x62, 2 / 3 in a room with a u8 @0x61, 4 - 6 others; sent as 1 / 0: with the
  kind 0 an online friend showed as offline, user 2026-10-14; the u32 @0x64 unknown, 0), u16 level @0x68, u16 car
  grade @0x6a (the list row, client 0x63c888), u32 serial @0x6c (0 = offline; the Communication Zone's Party
  button sends it in 0xe4, client 0x640907: with the serial @0x68 it sent 0 and got "does not exist").
  0xe6 FriendList -> 0xe7 (i32 n, u32 list update, n x XiStrFriend).
  0xe8 FriendAddByName (name) -> rows me->him 'R' and him->me 'C', 0xea FriendAddAck (his record) to me and,
       if he is online, 0xee FriendRequest (my record) to him. Errors 20127 (myself / not found), 20129
       already a friend.
  0xef FriendRequest answer (i64 cid of the asker, i16 1 accept / 0 deny, name) -> accept: both 'F' and
       0xe1 UpdateFriend to both; deny: both rows deleted; 0xef (cid, ret, his name) to the asker.
  0xeb FriendDel (name) -> both rows deleted, 0xed FriendDelAck (i64 cid, i16 type, my name, his name)
       to me and to him if online.
  Logging in and out: 0xe1 to the friends online (serial set / 0).
Parties (BS_Party; in memory only, as in the 2008 server):
  XiStrPartyMemberInfo, 2011 58 bytes (2008 54 + 4 at the end): i64 cid, name 0x2a, u16 avatar, u16 level,
  u32 the car's V grade (client 0x50f7f0 fills its own from its car record; the party window shows it as V%d:
  with the car type the user saw V81 / V79).
  0xe4 PartyPreCheck (u32 serial, name: one of the two) -> 0xe5 (u32 his serial, i64 cid, name, i32 party id, wchar[30]
       party name), or 20213 "%s does not exist." when he is not in the game.
  Two ways into a party (2008 Cmd_PartyInvite / Join and Cmd_PartyApply / Accept; 2011 sizes + 4):
  0xf0 PartyInvite (u32 serial of the player invited, u32 ticket, member info, wchar[30] party name,
       wchar[100] text; 328 bytes) -> the same to him with the inviter's serial and member info; he
       answers 0xf2 PartyJoin (u32 inviter's serial, ticket, member info) and joins the inviter's party
       (made if there is none), or 0xf1.
  0xf6 PartyApply (u32 serial of a party member, ticket, member info, wchar[50] text; 168) -> the same to
       that member; he answers 0xf7 PartyAccept (u32 applicant's serial, ...) and the applicant joins.
       (The first version had no 0xf0 and treated 0xf7 as 0xf2: user 2026-10-13, "party request not
       being accepted".)
  -> 0xf3 PartyJoinResult to every member: u32 result 1, i32 party id, wchar[30] name, u32 n @0x46, n x
       (u32 serial, member info) @0x4a; the client's handler 0x526170 takes (n - 1) x 0x3e + 0x88 = 0x4a + n x
       0x3e bytes, nothing after the units (an empty unit sent after them until 2026-10-18 was read as a message
       of type 0).
  0xf1 PartyReject (serial, ticket, member info, wchar[100]): passed on to the inviter.
  0xf4 PartyLeave / 0xf5 PartyBanish (u32 serial; banish by the leader): 0xf4 (serial) to the members;
       a party of one is dissolved. Leaving the game leaves the party.
  Party chat: session.chat sends "party" to the members.
0x296 GameCharInfoEx (name) -> 0x297 (2011 462 bytes): XiStrCharInfo @2, car @0x11d, stats @0x14e,
  u32 serial @0x1b6, u32 location @0x1ba; the profile search ("find friend").
"""
import itertools
import struct

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context
from .login import SVC, error, send, sessions
from .records import name_bytes, wstr

NAME = 0x2a
FRIEND_2011, MEMBER_2011 = 0x70, 58
FRIENDS_SQL = ("SELECT f.FCID, f.FSTATE, c.CNAME, c.NLEVEL, c.LASTCITYID, c.TEAMID FROM SKID_FRIEND_TB f"
               " JOIN SKID_CHARACTER_TB c ON c.SERVERID = f.SERVERID AND c.CID = f.FCID"
               " WHERE f.SERVERID = %s AND f.CID = %s AND c.STATE = 'P'")
CHAR_SQL = "SELECT CID, CNAME, NLEVEL, LASTCITYID FROM SKID_CHARACTER_TB WHERE SERVERID = %s AND UCNAME = UPPER(%s) AND STATE = 'P'"
STATE_SQL = "SELECT FSTATE FROM SKID_FRIEND_TB WHERE SERVERID = %s AND CID = %s AND FCID = %s"
INSERT_SQL = "INSERT INTO SKID_FRIEND_TB(SERVERID, CID, FCID, FSTATE) VALUES (%s, %s, %s, %s)"
UPDATE_SQL = "UPDATE SKID_FRIEND_TB SET FSTATE = %s WHERE SERVERID = %s AND CID = %s AND FCID = %s"
DELETE_SQL = "DELETE FROM SKID_FRIEND_TB WHERE SERVERID = %s AND ((CID = %s AND FCID = %s) OR (CID = %s AND FCID = %s))"


def online(cid):
    return next((s for s in list(sessions.values())
                 if s.state.get('player') and s.state['player'].char.cid == cid), None)


def place_of(s):
    """The 8-byte place of an online player (XiStrFriend @0x60, 0x297 GameCharInfoEx @0x1ba; client 0x63a9b0 texts,
    0x5bfc20 "play together"): u8 kind, u8, u16, u32. Kinds: 1 in the city; 2 / 3 in a battle zone room (u8 the
    section / PvP channel, u16 the room id, u32 the room flags: bet rooms 0x7000 cost Mito to join), 2 waiting (the
    client joins with 0x1d7 ChannelRoomJoin), 3 racing (it opens the lobby on that room); 4 spectating; 5 channel
    battle; 6 Lap Time (u8 class - 1, u16 the arena's room; joined with 0x1bd). Only 2, 3 and 6 can be joined
    ("You cannot do this with a friend.", 10202, otherwise; user, 2026-10-14). Offline: zeros."""
    if s is None:
        return bytes(8)
    from .rooms import RACING, WAIT, room_of
    room = room_of(s)
    if room is not None:
        lap = getattr(room, 'lap', None)
        if lap is not None:
            return struct.pack('<BBHI', 6, max(lap.grade - 1, 0), room.id, room.map_flag & 0xffffffff)
        kind = 2 if room.state == WAIT else 3
        return struct.pack('<BBHI', kind, room.channel & 0xff, room.id, room.map_flag & 0xffffffff)
    return struct.pack('<BBHI', 1, 0, 0, 0)


def friend_record(cid, name, level, city, state, s=None):
    """XiStrFriend (2011). With the session of an online character its live values are used."""
    p = s.state['player'] if s else None
    if p:
        level, city = p.char.level, p.char.city
    grade = p.car.grade if p and p.car else 0
    return (name_bytes(name) + bytes(0x1a) + struct.pack('<qqqi', cid, -1, -1, ord(state)) + place_of(s)
            + struct.pack('<HHI', level or 1, grade, s.state.get('serial', 0) if s else 0))


def my_record(session, state):
    c = session.state['player'].char
    return friend_record(c.cid, c.name, c.level, c.city, state, session)


async def friends_of(cid):
    db = context.db
    return await db.rows(FRIENDS_SQL, (db.server_id, cid))


@on(SVC, C2S, 0xe6)
async def friend_list(session, frame):
    from .login import LIST_FULL
    p = session.state.get('player')
    rows = await friends_of(p.char.cid) if p else []
    recs = [friend_record(int(fcid), name, int(lvl or 1), int(city or 0), (st or 'F').strip() or 'F', online(int(fcid)))
            for fcid, st, name, lvl, city, _ in rows]
    send(session, Frame(0xe7, struct.pack('<iI', len(recs), LIST_FULL) + b''.join(recs)))


async def tell_friends(session, logged_in=True):
    """0xe1 UpdateFriend to the friends online when a character comes or goes."""
    p = session.state.get('player')
    if not p:
        return
    for fcid, st, *_ in await friends_of(p.char.cid):
        s = online(int(fcid))
        if s and s is not session:
            c = p.char
            rec = friend_record(c.cid, c.name, c.level, c.city, 'F' if (st or '').strip() == 'F' else 'C',
                                session if logged_in else None)
            send(s, Frame(0xe1, rec))


@on(SVC, C2S, 0xe8)
async def friend_add(session, frame):
    p = session.state.get('player')
    if not p:
        return
    db, c = context.db, p.char
    name = read_wstr(frame.payload, 0, NAME)
    r = await db.row(CHAR_SQL, (db.server_id, name))
    if not r or int(r[0]) == c.cid:
        return error(session, '20127')
    fcid = int(r[0])
    if await db.row(STATE_SQL, (db.server_id, c.cid, fcid)):
        return error(session, '20129')
    await db.execute(INSERT_SQL, (db.server_id, c.cid, fcid, 'R'))
    if not await db.row(STATE_SQL, (db.server_id, fcid, c.cid)):
        await db.execute(INSERT_SQL, (db.server_id, fcid, c.cid, 'C'))
    s = online(fcid)
    session.log.note(f'friend request {c.name!r} -> {r[1]!r} ({"online" if s else "offline"})')
    send(session, Frame(0xea, friend_record(fcid, r[1], int(r[2] or 1), int(r[3] or 0), 'R', s)))
    if s:
        send(s, Frame(0xee, my_record(session, 'C')))


@on(SVC, C2S, 0xef)
async def friend_answer(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 10 + NAME:
        return
    db, c = context.db, p.char
    asker, ret = struct.unpack_from('<qh', frame.payload)
    if not await db.row(STATE_SQL, (db.server_id, asker, c.cid)):
        return error(session, '20132')
    s = online(asker)
    r = await db.row("SELECT CNAME, NLEVEL, LASTCITYID FROM SKID_CHARACTER_TB WHERE SERVERID = %s AND CID = %s",
                     (db.server_id, asker))
    if ret == 1:
        await db.execute(UPDATE_SQL, ('F', db.server_id, c.cid, asker))
        await db.execute(UPDATE_SQL, ('F', db.server_id, asker, c.cid))
        if r:
            send(session, Frame(0xe1, friend_record(asker, r[0], int(r[1] or 1), int(r[2] or 0), 'F', s)))
        if s:
            send(s, Frame(0xe1, my_record(session, 'F')))
    else:
        await db.execute(DELETE_SQL, (db.server_id, c.cid, asker, asker, c.cid))
    session.log.note(f'friend answer from {c.name!r} to cid {asker}: {"yes" if ret == 1 else "no"}')
    if s:
        send(s, Frame(0xef, struct.pack('<qh', c.cid, ret) + name_bytes(c.name)))


@on(SVC, C2S, 0xeb)
async def friend_del(session, frame):
    p = session.state.get('player')
    if not p:
        return
    db, c = context.db, p.char
    name = read_wstr(frame.payload, 0, NAME)
    r = await db.row(CHAR_SQL, (db.server_id, name))
    if not r:
        return error(session, '20213')
    fcid = int(r[0])
    await db.execute(DELETE_SQL, (db.server_id, c.cid, fcid, fcid, c.cid))
    send(session, Frame(0xed, struct.pack('<qh', fcid, 0) + name_bytes(c.name) + name_bytes(r[1])))
    s = online(fcid)
    if s:
        send(s, Frame(0xed, struct.pack('<qh', c.cid, 1) + name_bytes(r[1]) + name_bytes(c.name)))


# ---- parties ----------------------------------------------------------------------------------------------

_party_ids = itertools.count(1)
parties = {}                        # party id -> Party


class Party:
    def __init__(self, leader):
        self.id = next(_party_ids)
        self.members = [leader]     # sessions, the leader first

    def cast(self, *frames):
        for s in self.members:
            send(s, *frames)


def party_of(session):
    return parties.get(session.state.get('party'))


def member_info(session):
    p = session.state['player']
    c = p.char
    return (struct.pack('<q', c.cid) + name_bytes(c.name)
            + struct.pack("<HHI", c.avatar, c.level, p.car.grade if p.car else 0))


def party_state(party):
    units = b''.join(struct.pack('<I', s.state.get('serial', 0)) + member_info(s) for s in party.members)
    leader = party.members[0].state['player'].char.name
    return Frame(0xf3, struct.pack('<Ii', 1, party.id) + wstr(f"{leader}'s party", 60)
                 + struct.pack('<I', len(party.members)) + units)


def by_serial(serial):
    return next((s for s in list(sessions.values())
                 if s.state.get('player') and s.state.get('serial') == serial), None)


@on(SVC, C2S, 0xe4)
async def party_precheck(session, frame):
    if not session.state.get('player') or len(frame.payload) < 4 + NAME:
        return
    name = read_wstr(frame.payload, 4, NAME)
    from .misc import online as online_by_name
    # from another car's menu the client sends only the serial, the name empty (recorded 2026-10-13: the
    # look-up by name answered "does not exist" and no invitation went out); from a list, the name
    s = online_by_name(name) if name.strip() else by_serial(struct.unpack_from('<I', frame.payload)[0])
    if not s or s is session:
        msg = context.data.server_text.get('20213', '%s does not exist.').replace('%s', name)
        from .. import admin
        return admin.message(session, msg)
    # the target's party: -1 = none (the client 0x51a890 invites only then; 0 was read as a party)
    party = party_of(s)
    send(session, Frame(0xe5, struct.pack('<Iq', s.state.get('serial', 0), s.state['player'].char.cid)
                        + name_bytes(s.state['player'].char.name)
                        + struct.pack("<i", party.id if party else -1) + bytes(60)))


def relay_request(msg_type):
    """0xf0 PartyInvite (to the player invited) / 0xf6 PartyApply (to a party's member): u32 serial of the
    other side, u32 ticket, XiStrPartyMemberInfo, texts -> the same to that player with the sender's
    serial and member info."""
    async def relay(session, frame):
        p = frame.payload
        if not session.state.get('player') or len(p) < 8:
            return
        target = by_serial(struct.unpack_from('<I', p)[0])
        if not target or target is session:
            return error(session, '20213')
        session.log.note(f'party {"invitation" if msg_type == 0xf0 else "application"} to '
                         f'{target.state["player"].char.name!r}')
        send(target, Frame(msg_type, struct.pack('<I', session.state.get('serial', 0)) + p[4:8] + member_info(session)
                           + p[8 + MEMBER_2011:]))
    return relay


on(SVC, C2S, 0xf0)(relay_request(0xf0))
on(SVC, C2S, 0xf6)(relay_request(0xf6))


def join(leader, joiner):
    """joiner goes into leader's party (made if leader has none); 0xf3 to every member."""
    leave_party(joiner)
    party = party_of(leader)
    if not party:
        party = Party(leader)
        parties[party.id] = party
        leader.state['party'] = party.id
    party.members.append(joiner)
    joiner.state['party'] = party.id
    joiner.log.note(f'joins party {party.id} ({len(party.members)} members)')
    party.cast(party_state(party))
    from .assists import send_party         # the party assists (partyspeedup / partycrashup) of the others
    send_party(party.members)


def other_side(session, frame):
    p = frame.payload
    if not session.state.get('player') or len(p) < 4:
        return None
    other = by_serial(struct.unpack_from('<I', p)[0])
    if not other or other is session:
        error(session, '20213')
        return None
    return other


@on(SVC, C2S, 0xf2)
async def party_join(session, frame):
    """0xf2 PartyJoin (u32 inviter's serial, ticket, member info): the invited player said yes."""
    inviter = other_side(session, frame)
    if inviter:
        join(inviter, session)


@on(SVC, C2S, 0xf7)
async def party_accept(session, frame):
    """0xf7 PartyAccept (u32 applicant's serial, ticket, member info): a member let the applicant in."""
    applicant = other_side(session, frame)
    if applicant:
        join(session, applicant)


@on(SVC, C2S, 0xf1)
async def party_reject(session, frame):
    p = frame.payload
    if not session.state.get('player') or len(p) < 4:
        return
    inviter = by_serial(struct.unpack_from('<I', p)[0])
    if inviter:
        send(inviter, Frame(0xf1, struct.pack('<I', session.state.get('serial', 0)) + p[4:8] + member_info(session)
                            + p[8 + MEMBER_2011:].ljust(200, b'\0')[:200]))


def leave_party(session, banished=False):
    party = parties.get(session.state.pop('party', None))
    if not party or session not in party.members:
        return
    from .partypatrol import member_gone       # a party patrol fails when a member leaves (the wiki)
    member_gone(session)
    # 0xf5 PartyBanish (serial) when the leader removed him: the client then says he was kicked, not that
    # he left (user, 2026-10-13; the 2008 Cmd_PartyBanish sends 0xf5 too)
    gone = Frame(0xf5 if banished else 0xf4, struct.pack('<I', session.state.get('serial', 0)))
    party.cast(gone)
    party.members.remove(session)
    if len(party.members) < 2:
        for s in party.members:
            s.state.pop('party', None)
            send(s, Frame(0xf4, struct.pack('<I', s.state.get('serial', 0))))
        parties.pop(party.id, None)
    else:
        party.cast(party_state(party))
    from .assists import send_party         # his party assists count no more (also the one left alone)
    send_party(party.members + [session])


@on(SVC, C2S, 0xf4)
async def party_leave(session, frame):
    leave_party(session)


@on(SVC, C2S, 0xf5)
async def party_banish(session, frame):
    party = party_of(session)
    if not party or party.members[0] is not session or len(frame.payload) < 4:
        return
    target = by_serial(struct.unpack_from('<I', frame.payload)[0])
    if target in party.members and target is not session:
        leave_party(target, banished=True)


@on_open(SVC)
async def social_on_close(session):
    import asyncio
    told = False
    try:
        while True:
            await asyncio.sleep(1)
            if not told and session.state.get('player') and session.state.get('channel'):
                told = True
                await tell_friends(session, True)
    finally:
        from .chase import leave_chase
        try:
            await leave_chase(session, closing=True)
        except Exception as e:
            session.log.note(f'leaving the chase on close failed: {e}')
        leave_party(session)
        if told:
            await tell_friends(session, False)


# ---- profile search ----------------------------------------------------------------------------------------

@on(SVC, C2S, 0x296)
async def game_char_info_ex(session, frame):
    from . import player
    from .misc import online as online_by_name
    name = read_wstr(frame.payload, 0, NAME)
    s = online_by_name(name)
    p = s.state['player'] if s else await player.load(name)
    if not p:
        return error(session, '20019')
    c = p.char
    from .records import Car
    from ..version import is_2016
    empty_car = bytes(len(Car(0, 0, 0, 0, 0, 0, 0, 0).encode()))
    out = c.encode() + (p.car.encode() if p.car else empty_car) + p.stats().encode()
    out += struct.pack('<I', s.state.get('serial', 0) if s else 0) + place_of(s)
    # 2011 462 bytes with the type (handler 0x515d80); 2016 0x1fd (0x529340: the 2016 char / car / stats records,
    # then the same 24-byte tail @0x1e5)
    send(session, Frame(0x297, out.ljust((0x1fd if is_2016() else 462) - 2, b'\0')))
