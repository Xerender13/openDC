"""2016 client: DCGP (Drift City Grand Prix, the battle zone's two-faction season), off unless
``emulator.ini [dcgp] enabled``.

Every layout below comes from the 2016 client's disassembly as collected in
``docs/neo_work/DCGP_PROTOCOL.md`` (section numbers and VAs are that file's; the VAs are the objdump/image VAs
of ``DriftCity Dev Ed/DriftCity.exe``). The whole module does nothing unless ``version.is_2016()`` and
``context.dcgp`` is a dict with a truthy ``enabled`` (the lead fills it from ``emulator.ini [dcgp]``; the
default is ``{}``, i.e. off). When it is off the handlers return without answering, so a 2011 client and an
untouched 2016 server behave exactly as before.

DCGP is **four things** (section 0): the content flag ``BattleZone.DCGP`` (section 2), a channel type 14
("DCGP Stadium"), three request/answer pairs that reuse the *same* type number in both directions, and one
``0x89`` NotifyEvent sub-event 40. The race itself is an ordinary battle-zone race: no DCGP identifier is read
anywhere in the race messages (section 6.2), so the scoring is entirely server-side and the client learns it
only from ``0x89`` event 40 (section 3.4) and from ``0x777`` (section 3.2).

Replies this module sends (frame = u16 type + payload; "off" = payload offset = frame offset - 2):

  S>C 0x777 Cmd_DCGPSeasonState, handler 0x530eb0 - 154 bytes fixed (section 3.2)
      +0x02 u32 season phase: 1 competition (12785 "Tournament Period"), 2 reward distribution (12786),
             anything else "Preparing" (0x5b8ae0); also gates the DCGP lobby button (0x5ceb0f)
      +0x06 u32 season number (0x530ebb; printed as "%d season %s")
      +0x0a u64 West (blue team, 서군) points (0x530f01; widget 3 390 020, "%lld points" 12793)
      +0x12 u64 East (red team, 동군) points (0x530f0b)
      +0x1a u32 competition start, Unix seconds (0x530ef5)
      +0x1e u32 competition end, Unix seconds (0x530eef)
      +0x22 u32 compensation/reward end, Unix seconds (0x530ee9)
      +0x26 char[0x38] winner reward-group name (memcpy 0x38, 0x530f2f-0x530f3b)
      +0x5e char[0x38] loser reward-group name (memcpy 0x38, 0x530f45-0x530f51)
      +0x96 4 bytes the S>C handler does not read; left 0 (the C>S *request* sets 1, section 3.2)

  S>C 0x776 Cmd_SelectDCGPTeam, handler 0x52b5c0 - 11 bytes fixed (section 3.1)
      +0x02 u8  show flag, MUST be != 0 or the handler displays nothing (0x52b5eb)
      +0x03 u32 season number -> [global+0x3eaf0] (0x52b5f7)
      +0x07 u32 team: 1 = West, anything else = East; must be > 0 to be stored in [player+0x13d]
             (0x52b5d3-0x52b5e7). That field is what un-greys the DCGP button (0x5ceb0f) and selects the
             12775 / 12776 text ("You've successfully assigned %s as the %d of DCGP.", 12790).

  S>C 0x778 Cmd_GetDCGPReward, handler 0x52b670 - 6 bytes (``mov ax,0x6`` at 0x52b6a3)
      The handler reads no payload: it shows message box 12798 "Congratulations! Obtained rewards from DCGP" and
      returns 6, so the frame carries 4 zero bytes after the type (lead, session 46: a 2-byte frame would make the
      client consume 4 bytes of whatever follows it).

  S>C 0x89 Cmd_NotifyEvent, event 40 - 18 bytes (section 3.4, entry 40 -> 0x530c00)
      Frame(0x89, struct.pack('<IIII', 40, team, points, 0)): event id @2, team @6 (validated 1..2 by the
      client), points @0xa (text 12777 "As the battle result, you've contributed %d point towards %s."),
      +0xe unused. The same shape gotcha.py (23, 24) and upgrade.py (37) already send.

Requests handled:

  C>S 0x776 11 bytes: +2 u8 mode byte (the popup's ``+0x20``, never written by the client, section 3.1 /
      section 8), +3 4 bytes not written by the sender, +7 u32 team (1 West / 2 East; the caller pushes 1 / 2
      for the ``_1WEST`` / ``_2EAST`` buttons, 0x599dec-0x599df4) -> S>C 0x776.
  C>S 0x777 154 bytes: all zero except +0x96 = 1 (sender 0x85a240; verified against the logged request,
      logs/2016/20261020-123905.msgs.txt:3980) -> S>C 0x777. Sent when the season window is opened
      (ID_PVPNEW_RMLOBBY_DCGP_INFO 950 334, 0x5b8eb0). The client caches the answer with the window closed, so
      it may be sent at any time (section 3.2).
  C>S 0x778 6 bytes, no payload (the reward window's "get reward" button, 0x85a0e0 / 0x5b9eaa) -> S>C 0x778.

What is OURS (not in the client and not in the 2008 server, which has no DCGP):

  * ``SKID_DCGP_TB`` (below) is our storage: the real server's DCGP tables were not available. One row per
    character and season: the chosen team, the points that character contributed and the "reward claimed" bit.
    The two team totals of 0x777 are the sums of POINTS over TEAM 1 / 2.
  * the season and the phase are settings (``[dcgp] season`` / ``[dcgp] phase``), because nothing in the
    client says when a season starts: the client only displays what it is told. The three timestamps are the
    current month's first and last second and the end + 7 days (UTC), the "competition" and "compensation"
    periods of texts 12799 / 12800.
  * the points of a race are ``[dcgp] win_points`` (default 10) / ``[dcgp] play_points`` (default 2). How the
    real server scored a DCGP race is unknown (section 8: "placement? gates? team totals?"); the client never
    sends its race result (it sends the ordinary 0x1eb PvpEnd and the server must score it).
  * the reward-group names default to ``rw_dcgp_common``, the only DCGP reward group string in the exe
    (0x95daf4). Section 4.2 warns that the shipped reward data may not contain it; the client then renders an
    empty list and shows no error. ``[dcgp] winner`` / ``[dcgp] loser`` override them.
  * a player may change team while POINTS == 0 (the doc does not say whether a choice can be changed at all,
    section 8; the client only stores what the ack carries), and never again once the season has points. The
    claimed bit is per season, and a claim is refused silently while the phase is 1 (racing): the client
    enables its "get reward" button only in phase 2 (0x5b9df7) and shows an empty box for 0x778 anyway.
  * a tie counts as a loss for the claiming player (the client's own bars compute 100 * west / (west + east),
    section 4.1, and treat equal totals as no winner).
"""
import struct
from datetime import datetime, timedelta, timezone

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from ..version import is_2016
from .login import SVC, send

STATE_LEN = 154                            # S>C 0x777 (0x530eb0, mov ax,0x9a)
NAME_LEN = 0x38                            # the two reward-group names (0x530f2f, 0x530f45)
WINNER_OFF, LOSER_OFF = 0x24, 0x5c        # payload offsets of the two names (frame - 2)
WEST, EAST = 1, 2                          # 0x52b600: 1 = West (서군), anything else = East (동군)
PHASE_RACING, PHASE_REWARD = 1, 2          # 0x5b8ae0: 1 -> 12785, 2 -> 12786, else 10758
EVENT_POINTS = 40                          # Cmd_NotifyEvent sub-event (0x530c00)

DEFAULT_SEASON = 1                         # ours: [dcgp] season
DEFAULT_WIN_POINTS, DEFAULT_PLAY_POINTS = 10, 2         # ours: [dcgp] win_points / play_points
DEFAULT_GROUP = 'rw_dcgp_common'           # the only DCGP reward group string in the exe (0x95daf4)

SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS SKID_DCGP_TB(
 SERVERID numeric(18,0) NOT NULL, CID numeric(18,0) NOT NULL, SEASON integer NOT NULL,
 TEAM integer NOT NULL DEFAULT 0, POINTS bigint NOT NULL DEFAULT 0, CLAIMED integer NOT NULL DEFAULT 0,
 PRIMARY KEY (SERVERID, CID, SEASON))"""
ROW_SQL = "SELECT TEAM, POINTS, CLAIMED FROM SKID_DCGP_TB WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
ENSURE_SQL = ("INSERT INTO SKID_DCGP_TB(SERVERID, CID, SEASON, TEAM, POINTS, CLAIMED)"
              " VALUES (%s, %s, %s, 0, 0, 0) ON CONFLICT DO NOTHING")
TEAM_SQL = "UPDATE SKID_DCGP_TB SET TEAM=%s WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
POINTS_SQL = "UPDATE SKID_DCGP_TB SET POINTS=POINTS+%s WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
CLAIM_SQL = "UPDATE SKID_DCGP_TB SET CLAIMED=1 WHERE SERVERID=%s AND CID=%s AND SEASON=%s"
# the 0x777 totals: the whole server's contributions, so they must not be a character's POINTS
TOTAL_SQL = ("SELECT TEAM, SUM(POINTS) FROM SKID_DCGP_TB WHERE SERVERID=%s AND SEASON=%s AND TEAM IN (1, 2)"
             " GROUP BY TEAM")

_ready = False          # the table has been created on this connection set


# ---- strings (rankings.py / worldmatch.py's convention) --------------------------------------------------

def sstr(text, size):
    """A single-byte char[] field: the client looks these names up with "%s" (section 4.2)."""
    return (text or '').encode('cp949', 'replace')[:size - 1].ljust(size, b'\0')


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


# ---- configuration --------------------------------------------------------------------------------------

def config():
    """emulator.ini [dcgp] as a dict (the lead fills context.dcgp; default {} = off)."""
    value = getattr(context, 'dcgp', None)
    return value if isinstance(value, dict) else {}


def enabled():
    return is_2016() and bool(config().get('enabled'))


def season_key():
    """The season number we are in (ours: [dcgp] season, default 1)."""
    return _int(config().get('season', DEFAULT_SEASON), DEFAULT_SEASON)


def phase():
    """The season phase (ours: [dcgp] phase, default 1 = competition / racing)."""
    return _int(config().get('phase', PHASE_RACING), PHASE_RACING)


def race_points_for(won):
    """The points one race contributes (ours: [dcgp] win_points / play_points)."""
    if won:
        return max(_int(config().get('win_points', DEFAULT_WIN_POINTS), DEFAULT_WIN_POINTS), 0)
    return max(_int(config().get('play_points', DEFAULT_PLAY_POINTS), DEFAULT_PLAY_POINTS), 0)


def group_names():
    """-> (winner group, loser group): the two 0x38-byte names (ours: [dcgp] winner / loser)."""
    return (config().get('winner') or DEFAULT_GROUP, config().get('loser') or DEFAULT_GROUP)


def season_times(when=None):
    """-> (start, end, reward end) Unix seconds, UTC (ours, section 3.2's three timestamps).

    The first and the last second of the current month, and the end + 7 days: the "competition" and the
    "compensation" periods the client prints with 12799 / 12800.
    """
    when = when or datetime.now(timezone.utc)
    first = datetime(when.year, when.month, 1, tzinfo=timezone.utc)
    following = (first.replace(year=first.year + 1, month=1) if first.month == 12
                 else first.replace(month=first.month + 1))
    end = following - timedelta(seconds=1)
    return int(first.timestamp()), int(end.timestamp()), int((end + timedelta(days=7)).timestamp())


# ---- the database ---------------------------------------------------------------------------------------

async def ensure():
    global _ready
    if not _ready:
        await context.db.execute(SCHEMA_SQL)
        _ready = True


async def my_row(cid, season):
    """-> (team (0 = none), points, claimed) of one character's season row."""
    await ensure()
    db = context.db
    r = await db.row(ROW_SQL, (db.server_id, cid, season))
    return (_int(r[0]), _int(r[1]), _int(r[2])) if r else (0, 0, 0)


async def totals(season):
    """-> (West points, East points): the sums of POINTS per TEAM for the season (section 7.7)."""
    await ensure()
    db = context.db
    out = {WEST: 0, EAST: 0}
    for team, points in await db.rows(TOTAL_SQL, (db.server_id, season)):
        out[_int(team)] = _int(points)
    return out[WEST], out[EAST]


async def set_team(cid, season, team):
    db = context.db
    await ensure()
    await db.execute(ENSURE_SQL, (db.server_id, cid, season))
    await db.execute(TEAM_SQL, (team, db.server_id, cid, season))


async def add_points(cid, season, points):
    db = context.db
    await ensure()
    await db.execute(ENSURE_SQL, (db.server_id, cid, season))
    await db.execute(POINTS_SQL, (points, db.server_id, cid, season))


async def mark_claimed(cid, season):
    db = context.db
    await ensure()
    await db.execute(CLAIM_SQL, (db.server_id, cid, season))


# ---- the frames -----------------------------------------------------------------------------------------

def state_frame(phase, season, west, east, start, end, reward_end, winner=DEFAULT_GROUP, loser=DEFAULT_GROUP):
    """0x777 (154): phase @2, season @6, the two u64 totals @0xa / @0x12, three Unix times @0x1a, the two
    char[0x38] reward-group names @0x26 / @0x5e (section 3.2)."""
    out = bytearray(STATE_LEN - 2)
    struct.pack_into('<IIQQIII', out, 0x00, phase, season, max(west, 0), max(east, 0), start, end, reward_end)
    out[WINNER_OFF:WINNER_OFF + NAME_LEN] = sstr(winner, NAME_LEN)
    out[LOSER_OFF:LOSER_OFF + NAME_LEN] = sstr(loser, NAME_LEN)
    return Frame(0x777, bytes(out))


def team_frame(season, team):
    """0x776 (11): show flag @2 must be != 0, the season @3, the team @7 (section 3.1)."""
    return Frame(0x776, struct.pack('<BII', 1, season, team))


def claim_frame():
    """0x778 (6): the handler shows text 12798, reads nothing and returns 6 (0x52b6a3): 4 zero bytes."""
    return Frame(0x778, bytes(4))


def points_frame(team, points):
    """0x89 event 40 (18): Frame(0x89, '<IIII' 40, team, points, 0) (section 3.4)."""
    return Frame(0x89, struct.pack('<IIII', EVENT_POINTS, team, points, 0))


# ---- the replies ----------------------------------------------------------------------------------------

def _player(session):
    return session.state.get('player')


async def send_state(session):
    """S>C 0x777: phase, season, the two team totals, the three times, the two group names (section 3.2).

    The answer to C>S 0x777. Its handler caches the state even with the season window closed and the doc
    allows the server to send it at any time (section 3.2), so this is also what a login push may call: the
    DCGP lobby button reads the phase global that only this frame writes (0x5ceb0f, section 2).
    """
    if not enabled():
        return
    p = _player(session)
    if not p:
        return
    season = season_key()
    west, east = await totals(season)
    start, end, reward_end = season_times()
    send(session, state_frame(phase(), season, west, east, start, end, reward_end, *group_names()))


@on(SVC, C2S, 0x777)
async def season_state(session, frame):
    """C>S 0x777 (154; the payload is zeros except +0x96 = 1) -> S>C 0x777."""
    await send_state(session)


@on(SVC, C2S, 0x776)
async def select_team(session, frame):
    """C>S 0x776 (11; mode byte @2, team @7) -> S>C 0x776 with the season and the team now held.

    The first choice is stored; a later one changes it only while the character has no points this season
    (ours: the doc does not say whether a choice can be changed, section 8), otherwise the ack repeats the
    team the player already has.
    """
    if not enabled():
        return
    p = _player(session)
    if not p or len(frame.payload) < 9:
        return
    mode = frame.payload[0]
    team, = struct.unpack_from('<I', frame.payload, 5)
    if team not in (WEST, EAST):
        session.log.note(f'dcgp: team {team} refused (only 1 West / 2 East, section 3.1)')
        return
    season = season_key()
    held, points, _claimed = await my_row(p.char.cid, season)
    if held not in (WEST, EAST) or (held != team and points == 0):
        await set_team(p.char.cid, season, team)
        held = team
        session.log.note(f'dcgp: {p.char.name!r} joins team {team} (mode {mode}) in season {season}')
    else:
        session.log.note(f'dcgp: {p.char.name!r} keeps team {held} in season {season} '
                         f'(asked for {team}, {points} points)')
    send(session, team_frame(season, held))


@on(SVC, C2S, 0x778)
async def claim(session, frame):
    """C>S 0x778 (6, no payload) -> S>C 0x778 and the reward group's items, once per season after the racing
    phase; refused silently while racing or when already claimed (section 3.3)."""
    if not enabled():
        return
    p = _player(session)
    if not p:
        return
    season = season_key()
    if phase() == PHASE_RACING:
        session.log.note(f'dcgp: {p.char.name!r} claimed while racing: refused (phase 1, 0x5b9df7)')
        return
    team, _points, claimed = await my_row(p.char.cid, season)
    if team not in (WEST, EAST) or claimed:
        session.log.note(f'dcgp: {p.char.name!r} claimed with team {team} / claimed {claimed}: refused')
        return
    west, east = await totals(season)
    mine, other = (west, east) if team == WEST else (east, west)
    won = mine > other                       # a tie counts as a loss for the claiming player (ours)
    group = group_names()[0 if won else 1]
    await mark_claimed(p.char.cid, season)
    send(session, claim_frame())
    gains, given = await give_group(session, p, group)
    session.log.note(f'dcgp: {p.char.name!r} claimed the {"winner" if won else "loser"} group {group!r} of '
                     f'season {season} ({mine} vs {other}): {[i[0].name for i in given]}')
    if gains and gains.items:
        from .items import mod_list
        send(session, mod_list(*gains.items))


async def give_group(session, p, group):
    """The group's NormalItem / SkidItem rows, through rewards.give -> (Gains, [(ItemInfo, count)]).

    The same pattern as neocity.enemy_kill: roll the group, keep the rows whose item this server's tables
    know (context.data.item_index), give them and let the caller send items.mod_list. -> (None, []) when the
    group is not in RewardGroup.xlt (the client would show an empty list, section 4.2).
    """
    from .driftuse import roll
    from .rewards import give
    won = [w for w in roll(group) if w[0] in ('NormalItem', 'SkidItem') and w[1] in context.data.item_index]
    if not won:
        return None, []
    return await give(p, [(w[1], max(_int(w[3]), 1)) for w in won])


# ---- the race (called by the lead when a battle-zone race ends) ----------------------------------------

async def race_points(session, won, place):
    """A battle-zone race's result -> the team's points, then 0x89 event 40 (section 3.4).

    Called from the battle zone's result loop (rooms.result, per racer, rank known). Only a player with a team
    this season contributes: the points are ours ([dcgp] win_points / play_points) and are added to POINTS,
    then the client is told with ``Frame(0x89, '<IIII' 40, team, points, 0)`` so it floats text 12777. `place`
    is only logged: how the real server scored a race (placement? gates?) is unknown (section 8).
    """
    if not enabled():
        return
    p = _player(session)
    if not p:
        return
    season = season_key()
    team, _points, _claimed = await my_row(p.char.cid, season)
    if team not in (WEST, EAST):
        return
    points = race_points_for(won)
    if points:
        await add_points(p.char.cid, season, points)
    send(session, points_frame(team, points))
    session.log.note(f'dcgp: {p.char.name!r} place {place}, {"won" if won else "lost"}: {points} points to '
                     f'team {team} in season {season}')
