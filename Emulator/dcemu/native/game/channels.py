"""City channel lists: the gates and the team channel battles (TeamCenter.ChannelBattle).

Sent when the client goes into a city channel (with 0x314, position.py). No teams exist here, so
every channel is unowned; the values are those the 2008 server sent (recorded 2026-10-12).

0x35c CBattleInfo (u32 act, 0x3ed seen) -> 0x35d CBattleInfoAck: act, u32 battle time, page 0,
    u32 n = 13, n x XiCBattleChannel (2011: 308 bytes; client 0x5315e0 reads 0x12 + n x 0x134):
    nChannel, OwnTeam, ChallengeTeam (XiSmpTeamInfo, 2011 0x75: see handlers/game.team_2011),
    XiCBattleSetting (50: LeaderId -1, rest 0), ownTime 0, openTime = battle - 600, battleTime,
    endTime = battle + 3600, openState (3 for channels 0-9, 0 for 10-12).
    The battle time is the next Contents.ini CBattleDay (0 = Sunday) at CBattleHour, UTC, as a
    time_t on the server clock (2026-10-12: 1792263600 = Saturday 2026-10-17 20:00 UTC - 3600).
0x30c AreaList -> 0x315 GateListAck (u32 n, n x (GateId, Current, Max): (0, 0, 3000), (1, 0, 3000);
    the same in 2011) and 0x316 ChannelOwnershipListAck (u32 n = 13, n x (ChannelId, f32 AccTax, wins
    x3, XiSmpTeamInfo); 2011 137 bytes each).
"""
import calendar
import datetime
import struct

from ...handlers import on
from ...handlers.game import team_2011
from ...protocol import C2S
from ...wire import Frame
from .. import CLOCK_SHIFT, context
from .login import SVC, send

CHANNELS, OPEN_CHANNELS = 13, 10
GATES = [(0, 0, 3000), (1, 0, 3000)]
# XiSmpTeamInfo of no team (2008 layout): TeamId -1, TeamMarkId -1, TeamRanking 0xffffffff, OwnerId -1 @0x3a
EMPTY_TEAM = team_2011(struct.pack('<qqIII26xiq42xq', -1, -1, 0xffffffff, 0, 0, 0, -1, 0))
EMPTY_SETTING = struct.pack('<q', -1) + bytes(0x32 - 8)
OPEN_BEFORE, BATTLE_LENGTH = 600, 3600


def battle_time(now=None):
    """The next channel battle (Contents.ini CBattleDay, CBattleHour; UTC) as a server-clock time_t."""
    c = context.data.contents
    day, hour = c.get('CBattleDay', 6), c.get('CBattleHour', 20)
    now = now or datetime.datetime.now(datetime.UTC)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    t += datetime.timedelta(days=(day - (t.weekday() + 1) % 7) % 7)
    if t <= now:
        t += datetime.timedelta(days=7)
    return calendar.timegm(t.timetuple()) + CLOCK_SHIFT


@on(SVC, C2S, 0x35c)
async def channel_battle_info(session, frame):
    act, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    t = battle_time()
    out = struct.pack('<IIii', act, t, 0, CHANNELS)
    for k in range(CHANNELS):
        out += (struct.pack('<i', k) + EMPTY_TEAM + EMPTY_TEAM + EMPTY_SETTING
                + struct.pack('<5I', 0, t - OPEN_BEFORE, t, t + BATTLE_LENGTH, 3 if k < OPEN_CHANNELS else 0))
    send(session, Frame(0x35d, out))


@on(SVC, C2S, 0x30c)
async def area_list(session, frame):
    send(session, Frame(0x315, struct.pack('<I', len(GATES)) + b''.join(struct.pack('<iii', *g) for g in GATES)))
    send(session, Frame(0x316, struct.pack('<I', CHANNELS) + b''.join(
        struct.pack('<ifiii', k, 0.0, 0, 0, 0) + EMPTY_TEAM for k in range(CHANNELS))))
