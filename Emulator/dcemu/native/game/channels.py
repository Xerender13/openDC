"""City channels and the crews' channel battles (TeamCenter.ChannelBattle), as the 2008 server's BS_CBattleBoard /
BS_CBattleLobby / BS_CBattleRoom (ZoneServer.pdb) in the 2011 layouts.

Channels: 10 normal channels (0-1 Major, 2-9 Minor) and the Semi-channels from 10 on (the client's channel battle window,
0x6a5de0: index < 10 a normal button, >= 10 Semi-channel index - 9; MinSemi<n>ChBattleGrade). One set of channels for the
whole server; their entry rules go per client nation (emulator.ini [cbattle]): US Semi-channels 1-3 below level 40 / 60 /
70 (the 2008 BS_CBattleBoard levels, the US client's text 11411), EU (user, 2026-10-18) Semi-channel 1 up to V3 and 2 up to
V6 without level limits, normal channels V6 and up (the EU client's GlobalContent MinChBattleGrade 6, text 11288); a
Semi-channel without a line for a nation is closed to it.

The battle, every week (Contents.ini CBattleDay / CBattleHour, UTC; emulator.ini [cbattle] can move it): each channel's
lobby opens open_minutes before (registration), battles from the battle time, ends battle_minutes after it.
  States (BS_CBattleLobby::OnTick): NONE -> (open) PREPARE -> (battle time) TryBattle -> BATTLE (a round's race) -> the
  result -> ENDBATTLE (10 s) -> EndBattle -> REST (5 s) -> TryBattle ...; WAIT when there is nobody to race; at the end
  EndChannelBattle (the owner keeps / takes the channel), then NONE until the next week.
  Crews: the crew master or a first class member (rank < 3, error 20075) makes the crew's room in the channel (0x370), the
  others join it (0x371; 20081 when there is none). The owner crew's room is the defence (its client readies it at once on
  0x376); other crews' rooms are challengers and queue when their master readies them (0x384 state 1; the client's
  button wants 4 members in the room). Challengers need a Challenge Coupon (i_n_00037, 20077; used up when their first
  round starts, CBattleFee), a crew of rank B or better for the normal channels (20076), and may challenge a channel once
  per battle (a defeated crew: 20079).
  TryBattle: no defence room -> the first challenger becomes the defence and its crew the owner at once (OnNewOwnerRoom:
  "If there are no waiting members, you will lose Channel ownership"); then the next challenger. A round moves both
  crews' members into a race room (team 0 the defence on the even seats, team 1 the attack), and starts the race with
  0x1e7 type = the round number 1-3 (the client's PvP manager 0x7726d0 treats 1-99 as a channel battle race and changes
  scene), on the owner's track of that round (0x38a) or a random one. The race is the battle zone's (rooms.py; team
  points as a crew battle, type 0x28); the team with more points wins the round, a tie goes to the defence.
  The attack needs 2 straight round wins (user, 2026-10-18; 2008 EndBattle: AtkWinCnt >= 2): then it is the defence
  and the channel's owner, and the next challenger comes. A defence win sends the challenger out (it may not challenge
  this channel again this battle) and pays the defending crew's master defence_reward Mito per attacking racer
  (2008 EndBattle: 5000 x AttackMemberCnt, "CBattleWin", 0x393). The 2008 part stakes of the Major channels
  (GatherBattleItem: "If you fail, one of your equipped parts will be lost") are not done; 0x38d answers an empty list.
  EndChannelBattle: the owner's crew gets a channel win (SKID_TEAM_TB.CHANNELWINCNT) and a successive win if it owned the
  channel the week before (SKID_CBATTLE_TB); every crew room closes.
  Owners: SKID_CHANNEL_TB (OWNERTEAM / OWNTNAME / OWNDATE, LEADERCID / LEADERCNAME and BATTLE_MAP1-3 from 0x38a, ACC_TAX /
  LAST_TAX), SKID_TEAM_TB.OWNCHANNEL (the channel numbers, comma separated: XiStrTeamInfo's owned channels).
Tax (2008 CalcTax with the new tax flag; the client's texts 11400 / 11402 / 11409): every Mittron refuel payment adds to
  each owned channel's tax: Major 10 %, Minor 3 % (4 % / 5 % from the 2nd / 3rd successive week), Semi-channel 1-2 1 %,
  3 on 1.5 % (money made, not taken from the payer). Paid once a day ([cbattle] tax_hour, local time) to the owning
  crew's master (*our choice*: the 2008 payout ran in a stored procedure we do not have): Mito, SKID_TEAM_TB.TAXINCOME.
  Refuel discount for crews owning normal channels with successive wins (2008 Cmd_FuelChargeReq): 2 weeks 10 %, 3 and more
  20 % (0x2d4 sale flag bits 4 / 2; the client's "Channel Capture Discount" texts 10867 / 10868).
Test mode (user, 2026-10-18: "just 1 player is enough to attack a channel"; emulator.ini [cbattle] test = 1 or per
  character the GM chat command gmcbtest on): a test player's crew needs no Challenge Coupon or crew rank, its room
  queues as soon as it is made (no Ready). Like any challenger, with no defence room it takes the channel at once without
  a race (user, 2026-10-19: "if a crew attacks the channel and there is no crew to defend it, the channel automatically
  becomes the attacker's"); until then a test crew alone raced each round by itself. If another crew has a room with
  players in the channel (made first, not queued), that room defends instead and the test crew races against it.
  GM: gmcbattle now [minutes to the battle] [battle minutes] | start [battle minutes] (the battle at once) | end | owner <channel 1-13> <crew name | none> | status.

Messages (2011; offsets with the type; C>S payloads 2 less):
0x35c CBattleInfo (u32 act, 0x3ed from the window) -> 0x35d CBattleInfoAck: act, u32 next battle time, page 0, u32 n,
    n x XiCBattleChannel (0x134; client 0x6a5de0): i16 channel, u8 max level @2, u8 max car grade @3 (0 = none; the
    client greys the channel's Enter for a player above them, 0x6a2340; 2008: i32 channel), OwnTeam @4 and ChallengeTeam
    @0x79 (XiSmpTeamInfo, 0x75: see handlers/game.team_2011), XiCBattleSetting @0xee (0x32: i64 leader, wchar[21]
    name), ownTime @0x120, openTime @0x124, battleTime @0x128, endTime @0x12c, u16 state @0x130 (bit 0: the channel
    shown and open), u16 @0x132 (not known, 0).
0x35e GetCBattleTime (act) -> 0x35f (act, time).
0x370 CBattleRoomCreate (XiPvpUserInfo @2, u32 channel @0xe) -> the crew room: 0x26e, 0x1be (as rooms.py), 0x376
    CBattleRoomCreateAck (UserInfo, channel @0xe; client 0x5308f0: a master / first class of the channel's owner crew
    sends 0x384 state 1 itself).
0x371 CBattleRoomJoin (UserInfo @2, XiCarAttr @0xe, channel @0x1a) -> 0x26e, 0x1be of the crew's room.
0x372 EnterCBattleChannel (channel) / 0x373 ExitCBattleChannel: the channel's crew room list (0x1d0) and state.
0x384 CBattleRoomReady (u32 channel, u32 state 0 / 1), both ways: to the crew room (client 0x5307d0 keeps the state).
0x386 CBattleState (0x76; client 0x6a6120): battle time @2, end @6, area @0xa, channel @0xe (window +0x3c: "Channel %d"
    0x6a8abc; they were swapped until 2026-10-19: the crew window said "Channel 0"), defence: wchar[13] name
    @0x12, i64 crew @0x2c, i64 mark @0x34; attack @0x3c / @0x56 / @0x5e; i32 round state[4] @0x66 (1 racing, 2 defence
    won, 3 attack won). To the crew rooms and the channel's watchers when it changes.
0x390 CBattleBroadcast: u32 offset @2, u32 n @6, n x XiBattleRecord (0x6a; client 0x6a61b0): u32 time, u32 kind (0 a
    round starts, 1 a round won), channel, match, round, i32 winner (1 attack), item count, wchar[13] defence @0x1c,
    attack @0x36, next challenger @0x50. The last 20.
0x387 CBattleInstance (act) -> 0x388 (act, u32 n, n x (area, map, channel, spectators)): the races running.
0x38b CBattleJoinOBS (channel): spectate the running round (rooms.watch), else 20082.
0x38a CBattleSet (channel @2, leader wchar[13] @0x1a, 3 x (i16 map, i16 map flag, i32 traffic) @0x34): the owner crew's
    master within 24 h of taking the channel, normal channels only (20084 / 20085 / 20086, "This channel is semi channel!").
0x38e CBattleGetSetting (act, channel) -> 0x38f (0xb4; client 0x6a5230): act, channel, open, battle, end, i64 leader,
    wchar[21] leader @0x1e, i64 owner (the crew master) @0x48, wchar[21] @0x50, i64 crew @0x7a, wchar[13] crew @0x82,
    3 x race setting @0x9c.
0x38c CBattleItems (channel) -> 0x38d (channel, u32 n 0, page 0).
0x393 CBattleRewardMoney (0x40; client: Mito @0x38 added when the character @6 is the reader): channel @2, i64 cid @6,
    wchar[21] name @0xe, i64 Mito @0x38 ("The OMD government will send Crew Master %s a reward").
0x30c AreaList -> 0x315 GateListAck (u32 n, n x (GateId, Current, Max)) and 0x316 ChannelOwnershipListAck (u32 n, n x
    (ChannelId, f32 tax, u32 successive wins, crew channel wins, 0, XiSmpTeamInfo); 137 bytes each).
"""
import asyncio
import calendar
import datetime
import json
import os
import random
import struct
import time

from ...handlers import on, on_open
from ...handlers.game import team_2011
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import CLOCK_SHIFT, context, now, tick
from .login import SVC, error, send
from .records import wstr

MAIN = 10                                   # normal channels 0-9 (2008 MaxMainCh); Semi-channels from here
MAJOR = 2                                   # Major channels 0-1
GATES = [(0, 0, 3000), (1, 0, 3000)]
EMPTY_SETTING = struct.pack('<q', -1) + bytes(0x32 - 8)
NONE_, PREPARE, BATTLE, ENDBATTLE, REST, WAIT = 'none', 'prepare', 'battle', 'endbattle', 'rest', 'wait'
END_SHOW, REST_SECONDS = 0, 0               # 2008 BS_CBattleLobby: ENDBATTLE 10 s, m_restTerm 5; user, 2026-10-19:
                                            # 15 s less (the next round / the decision right after the result)
ATTACK_WINS = 2                             # straight round wins that take a channel (user, 2026-10-18)
OPEN_STATE = 3                              # bit 0: shown and open
CREW_ROOM, BATTLE_ROOM = 0x18, 0x28         # 2008 room kinds: a crew's waiting room, the race room (crew battle)
CREW_CAPACITY, BATTLE_CAPACITY = 16, 32      # crew rooms: 8 even seats (defence) or 8 odd (challengers), the window's 8 rows
CREW_CHANNEL, BATTLE_CHANNEL = 1000, 2000   # rooms.Room channel numbers (+ the channel), out of the battle zone lists
COUPON = 'i_n_00037'                        # Challenge Coupon (UseItemClient: "redeemed when the battle is started")
RECORDS = 20
ACT_INFO = 0x3ed                            # 0x35c from the Channel Battle window
ACT_SET = 0x3f1                             # 0x38e from the owner's track settings
TEST_CREW = -2                              # gmcbattle owner N test: an owner crew that never comes
FULL_DAY = 86400
TAX_SAVE_SECONDS = 300

# the client's texts by key (server side: GlobalText_Server.xlt)
NO_GAME, NO_CHAR, NO_CHANNEL, NO_CREW, NOT_FIRST, LOW_CREW, NO_COUPON = '20071', '20072', '20073', '20074', '20075', '20076', '20077'
ONCE, NO_ROOM, OBS_FAIL, NOT_MASTER, NOT_OWNER, NOT_NOW = '20079', '20081', '20082', '20084', '20085', '20086'
DEFENCE_LOST, ATTACK_LOST, CHANNEL_WON, BATTLE_OVER = '20263', '20264', '20265', '20266'


def _cfg():
    return context.cbattle


def battle_time(at=None):
    """The next channel battle (Contents.ini CBattleDay 0 = Sunday, CBattleHour, UTC; emulator.ini [cbattle] day / hour
    override) as a server-clock time_t."""
    c = context.data.contents
    day = _cfg().get('day', -1)
    hour = _cfg().get('hour', -1)
    day = c.get('CBattleDay', 6) if day < 0 else day
    hour = c.get('CBattleHour', 20) if hour < 0 else hour
    at = at or datetime.datetime.now(datetime.UTC)
    t = at.replace(hour=hour, minute=0, second=0, microsecond=0)
    t += datetime.timedelta(days=(day - (t.weekday() + 1) % 7) % 7)
    if t <= at:
        t += datetime.timedelta(days=7)
    return calendar.timegm(t.timetuple()) + CLOCK_SHIFT


# ---- channel rules by nation ------------------------------------------------------------------------------------

def rule(session, ch):
    """(open, max level, min grade, max grade) of channel ch for this session's nation (0 = no limit)."""
    from .. import nation
    eu = nation.is_eu(session)
    c = _cfg()
    if ch < MAIN:
        return (True,) + tuple(c['eu_main' if eu else 'main'])
    r = c['eu_semi' if eu else 'semi'].get(ch - MAIN + 1)
    return (True,) + tuple(r) if r else (False, 0, 0, 0)


def entry_refused(session, ch):
    """The channel's limits for this player -> None, or the text that refuses it."""
    open_, max_level, min_grade, max_grade = rule(session, ch)
    p = session.state['player']
    grade = p.car.shown_grade() if p.car else 0
    if not open_:
        return 'This channel is not open to your version of the game.'
    if max_level and p.char.level > max_level:
        return f'Level Limit {max_level}'
    if min_grade and grade < min_grade:
        return f'Only V{min_grade} or higher vehicles can enter this Channel Battle.'
    if max_grade and grade > max_grade:
        return f'Only vehicles up to V{max_grade} can enter this Channel Battle.'
    return None


def channel_name(ch):
    return f'Channel {ch + 1}' if ch < MAIN else f'Semi-channel {ch - MAIN + 1}'


# ---- crews ------------------------------------------------------------------------------------------------------

def smp_team(t):
    """XiSmpTeamInfo (2011, 0x75) of a crew dict (crews.team) or None."""
    if not t:
        return team_2011(struct.pack('<qqIII26xiq42xq', -1, -1, 0xffffffff, 0, 0, 0, -1, 0))
    return team_2011(struct.pack('<qqIII', t['tid'], t['mark'], t.get('ranking', 0) & 0xffffffff, t.get('point', 0),
                                 t.get('wins', 0)) + wstr(t['name'], 26)
                     + struct.pack('<iq', t.get('count', 0), t.get('master', -1)) + wstr(t.get('master_name', ''), 42)
                     + struct.pack('<q', t.get('exp', 0)))


def test_crew():
    return dict(tid=TEST_CREW, mark=-1, name='Test Crew', master=-1, master_name='', count=0, wins=0, point=0)


async def crew(tid):
    if tid == TEST_CREW:
        return test_crew()
    from .crews import team
    return await team(tid)


def is_test(session):
    return bool(_cfg().get('test') or session.state.get('cb_test'))


# ---- the lobbies ------------------------------------------------------------------------------------------------

class Result:
    def __init__(self):
        self.round = 0
        self.def_wins = self.atk_wins = 0
        self.sub = [0, 0, 0, 0]
        self.win = 0


class Lobby:
    def __init__(self, ch):
        self.ch = ch
        self.state, self.state_time = NONE_, 0
        self.open_time = self.battle_time = self.end_time = 0
        self.owner = None               # crew dict of the owner
        self.own_time = 0
        self.leader = (-1, '')
        self.race_sets = [(-1, 0, 1)] * 3   # (map, map flag, traffic); map -1 = a random track
        self.acc_tax = 0.0              # tax since the last payout
        self.successive = 0             # the owner's successive weekly wins (SKID_CBATTLE_TB)
        self.crew_rooms = {}            # crew id -> rooms.Room (the crews' waiting rooms in this channel)
        self.queue = []                 # challenger crew ids, in order
        self.owner_room = self.challenger_room = None   # crew ids
        self.result = Result()
        self.match = 0
        self.records = []
        self.defeated = set()           # crews that lost here this battle
        self.fee_paid = set()           # characters whose Challenge Coupon is used up this battle
        self.race = None                # the round's rooms.Room
        self.attack_racers = 0
        self.won_at = 0                 # time.time() of the last "Win the channel!" (once per take)
        self.solo = False               # the attack races alone (no longer set: a challenger with no defence takes the channel)
        self.watchers = set()           # sessions that entered the channel (0x372)
        self.spectators = set()         # sessions spectating the battle (0x38b), kept from round to round
        self.stakes = {}                # Major channels: cid -> Stake (a part each racer puts at stake)
        self.dirty = False

    # rooms
    def room(self, tid):
        from . import rooms
        r = self.crew_rooms.get(tid)
        if r is not None and rooms.rooms.get(r.id) is not r:
            del self.crew_rooms[tid]
            r = None
        return r

    def humans(self, tid):
        r = self.room(tid) if tid is not None else None
        return r.humans if r else []

    def team(self, tid):
        r = self.room(tid) if tid is not None else None
        return getattr(r, 'crew', None) if r else (self.owner if tid is not None and self.owner and
                                                   self.owner['tid'] == tid else None)

    def recipients(self):
        out = set(self.watchers)
        for tid in list(self.crew_rooms):
            out.update(m.session for m in self.humans(tid))
        if self.race:
            out.update(m.session for m in self.race.humans)
        return [s for s in out if s.state.get('player')]

    # messages
    def record(self, kind, win=0):
        nxt = self.team(self.queue[0]) if self.queue else None
        d, a = self.team(self.owner_room), self.team(self.challenger_room)
        rec = (struct.pack('<IiiiiiI', now() & 0xffffffff, kind, self.ch, self.match, self.result.round, win, 0)
               + wstr(d['name'] if d else '', 26) + wstr(a['name'] if a else '', 26) + wstr(nxt['name'] if nxt else '', 26))
        self.records = (self.records + [rec])[-RECORDS:]
        out = self.broadcast_frame()
        for s in self.recipients():
            send(s, out)

    def broadcast_frame(self):
        return Frame(0x390, struct.pack('<II', 0, len(self.records)) + b''.join(self.records))

    def state_frame(self, attack=None):
        """0x386; attack: the crew shown as the attack while no round is paired (see send_state)."""
        def side(tid):
            t = self.team(tid) if tid is not None else None
            return wstr(t['name'] if t else '', 26) + struct.pack('<qq', t['tid'] if t else 0, t['mark'] if t else 0)
        area = self.race.area if self.race else -1
        atk = self.challenger_room if self.challenger_room is not None else attack
        return Frame(0x386, struct.pack('<iiii', self.battle_time, self.end_time, area, self.ch) + side(self.owner_room)
                     + side(atk) + struct.pack('<4i', *self.result.sub))

    def send_state(self, sessions_=None):
        """The client picks its crew window's layout by 0x386's attack crew (0x6a7f87: attack crew id == the player's
        crew -> the challenging crew's window; else the owner's). While no round is paired, a challenging crew's members
        get their own crew as the attack (user, 2026-10-19: a queued challenger had the "Channel Owning Crew" window)."""
        # the defence / watchers: the next challenger in the queue (user, 2026-10-19: no attack name for the defence
        # until the round)
        nxt = next((tid for tid in self.queue if self.humans(tid)), None)
        out = self.state_frame(nxt)
        own = {}
        if self.challenger_room is None:
            for tid in list(self.crew_rooms):
                if tid != self.owner_room and not (self.owner and self.owner['tid'] == tid):
                    for m in self.humans(tid):
                        own[m.session] = tid
        frames = {}
        for s in sessions_ if sessions_ is not None else self.recipients():
            tid = own.get(s)
            if tid is None:
                send(s, out)
            else:
                if tid not in frames:
                    frames[tid] = self.state_frame(tid)
                send(s, frames[tid])

    def list_frame(self):
        """0x1d0: the challenging crews' rooms. The defence (its room, or the owner crew's room) is not listed: it is
        shown as the channel's defence (user, 2026-10-19)."""
        defence = {self.owner_room, self.owner['tid'] if self.owner else None}
        found = [r for r in (self.room(t) for t in list(self.crew_rooms) if t not in defence) if r]
        return Frame(0x1d0, struct.pack('<IIIi', 0, 0, len(found), now()) + b''.join(r.list_entry() for r in found))

    def channel_record(self, session):
        open_, max_level, _, max_grade = rule(session, self.ch)
        chal = self.team(self.challenger_room) if self.challenger_room is not None else None
        setting = struct.pack('<q', self.leader[0]) + wstr(self.leader[1], 42)
        return (struct.pack('<hBB', self.ch, min(max_level, 255), min(max_grade, 255)) + smp_team(self.owner)
                + smp_team(chal) + setting.ljust(0x32, b'\0')
                + struct.pack('<iiiiHH', self.own_time, self.open_time, self.battle_time, self.end_time,
                              OPEN_STATE if open_ else 0, 0))

    def notice(self, tid, key):
        from .login import error as show
        for m in self.humans(tid):
            show(m.session, key)

    def set_state(self, state):
        self.state, self.state_time = state, time.time()
        self.dirty = True

    def is_major(self):
        return self.ch < MAJOR


class Board:
    def __init__(self):
        self.lobbies = [Lobby(ch) for ch in range(_cfg()['channels'])]
        self.next_battle = 0
        self.loaded = False
        self.last_payout = None
        self.tax_saved = time.time()

    def schedule(self, battle=None, open_seconds=None, length=None):
        c = _cfg()
        t = battle or battle_time()
        before = c['open_minutes'] * 60 if open_seconds is None else open_seconds
        length = c['battle_minutes'] * 60 if length is None else length
        self.next_battle = t
        for lb in self.lobbies:
            if lb.state == NONE_:
                lb.open_time, lb.battle_time, lb.end_time = t - before, t, t + length


_board = None


def board():
    global _board
    if _board is None:
        _board = Board()
        _board.schedule()
        asyncio.ensure_future(_ticker())
    return _board


def lobby(ch):
    b = board()
    return b.lobbies[ch] if isinstance(ch, int) and 0 <= ch < len(b.lobbies) else None


async def _ticker():
    await load()
    while True:
        await asyncio.sleep(1)
        for lb in _board.lobbies:
            try:
                await lobby_tick(lb)
            except Exception as e:          # one lobby's trouble must not stop the others
                print(f'channel battle tick ({lb.ch}):', repr(e), flush=True)
        try:
            await tax_payout()
            if time.time() > _board.tax_saved + TAX_SAVE_SECONDS:     # the taxes collected, kept over a restart
                _board.tax_saved = time.time()
                for lb in _board.lobbies:
                    if lb.owner and lb.acc_tax >= 1:
                        await save(lb)
        except Exception as e:
            print('channel tax:', repr(e), flush=True)


# ---- the database -------------------------------------------------------------------------------------------------

CHANNEL_SQL = ("SELECT CHANNELID, OWNERTEAM, OWNDATE, LEADERCID, LEADERCNAME, BATTLE_MAP1, BATTLE_MAP2, BATTLE_MAP3,"
               " ACC_TAX FROM SKID_CHANNEL_TB WHERE SERVERID=%s")
SAVE_SQL = """IF EXISTS (SELECT 1 FROM SKID_CHANNEL_TB WHERE SERVERID=%s AND CHANNELID=%s)
UPDATE SKID_CHANNEL_TB SET OWNERID=%s, OWNERTEAM=%s, OWNCNAME=%s, OWNTNAME=%s, OWNDATE=%s, LEADERCID=%s, LEADERCNAME=%s,
  BATTLE_MAP1=%s, BATTLE_MAP2=%s, BATTLE_MAP3=%s, ACC_TAX=%s WHERE SERVERID=%s AND CHANNELID=%s
ELSE INSERT INTO SKID_CHANNEL_TB(SERVERID, CHANNELID, OWNERID, OWNERTEAM, OWNCNAME, OWNTNAME, OWNDATE, LEADERCID,
  LEADERCNAME, BATTLE_MAP1, BATTLE_MAP2, BATTLE_MAP3, ACC_TAX) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
LAST_SQL = ("SELECT TOP 1 MASTERTEAM_ID, SUCCESSIVE_WIN FROM SKID_CBATTLE_TB WHERE SERVERID=%s AND CHANNELID=%s"
            " ORDER BY BATTLEID DESC")
WIN_SQL = """DELETE FROM SKID_CBATTLE_TB WHERE SERVERID=%s AND CHANNELID=%s AND BATTLEID=%s;
INSERT INTO SKID_CBATTLE_TB(SERVERID, CHANNELID, BATTLEID, MASTERTEAM_ID, SUCCESSIVE_WIN, BATTLE_ODATE)
VALUES (%s, %s, %s, %s, %s, GetDate())"""
LOG_SQL = ("INSERT INTO SKID_CBATTLELOG_TB(SERVERID, CHANNELID, BATTLE_ODATE, BATTLEID, CDATE, DEF_TEAMID, ATK_TEAMID,"
           " DEF_TEAMNAME, ATK_TEAMNAME, DEF_MEMBERS, ATK_MEMBERS, DEF_POINT, ATK_POINT, NROUND, NMATCH)"
           " VALUES (%s, %s, SYSDATETIME(), %s, GetDate(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
RECORD_SQL = ("SELECT COUNT(*), SUM(CASE WHEN (DEF_TEAMID=%s AND DEF_POINT>0) OR (ATK_TEAMID=%s AND ATK_POINT>=2)"
              " THEN 1 ELSE 0 END) FROM SKID_CBATTLELOG_TB WHERE SERVERID=%s AND (DEF_TEAMID=%s OR ATK_TEAMID=%s)")
TEAM_WIN_SQL = "UPDATE SKID_TEAM_TB SET CHANNELWINCNT=ISNULL(CHANNELWINCNT, 0) + 1 WHERE SERVERID=%s AND TID=%s"
OWN_SQL = "UPDATE SKID_TEAM_TB SET OWNCHANNEL=%s WHERE SERVERID=%s AND TID=%s"
TAX_PAY_SQL = """UPDATE SKID_CHARACTER_TB SET GOLD=GOLD+%s WHERE SERVERID=%s AND CID=%s;
UPDATE SKID_TEAM_TB SET TAXINCOME=ISNULL(TAXINCOME, 0)+%s WHERE SERVERID=%s AND TID=%s;
UPDATE SKID_CHANNEL_TB SET LAST_TAX=%s, LAST_COLDATE=GetDate(), ACC_TAX=0 WHERE SERVERID=%s AND CHANNELID=%s"""


def _map_text(s):
    v = [int(x) for x in str(s or '').split(',') if x.strip().lstrip('-').isdigit()]
    return tuple(v) if len(v) == 3 else (-1, 0, 1)


async def load():
    b = _board
    if b.loaded:
        return
    b.loaded = True
    db = context.db
    try:
        rows = await db.rows(CHANNEL_SQL, (db.server_id,))
    except Exception as e:
        print('channels: SKID_CHANNEL_TB not read:', repr(e), flush=True)
        return
    from .. import time_t
    for r in rows:
        lb = lobby(int(r[0]))
        if not lb:
            continue
        tid = int(r[1]) if r[1] is not None else -1
        if tid > 0 or tid == TEST_CREW:
            lb.owner = await crew(tid)
        lb.own_time = time_t(r[2]) if lb.owner else 0
        lb.leader = (int(r[3]) if r[3] is not None else -1, (r[4] or '').strip())
        lb.race_sets = [_map_text(r[5]), _map_text(r[6]), _map_text(r[7])]
        lb.acc_tax = float(r[8] or 0)
        last = await db.row(LAST_SQL, (db.server_id, lb.ch))
        lb.successive = int(last[1] or 0) if last and lb.owner and int(last[0] or -1) == lb.owner['tid'] else 0


async def save(lb):
    db = context.db
    o = lb.owner or {}
    maps = [','.join(str(x) for x in s) for s in lb.race_sets]
    own = datetime.datetime.fromtimestamp(lb.own_time - CLOCK_SHIFT, datetime.UTC).replace(tzinfo=None) if lb.owner else None
    vals = (o.get('master', -1), o.get('tid', -1), o.get('master_name', '')[:32], o.get('name', '')[:16], own,
            lb.leader[0], lb.leader[1][:32], *maps, int(lb.acc_tax))
    await db.execute(SAVE_SQL, (db.server_id, lb.ch, *vals, db.server_id, lb.ch, db.server_id, lb.ch, *vals))


async def save_owned(tid):
    """SKID_TEAM_TB.OWNCHANNEL of a crew: its channels now."""
    if tid is None or tid < 0:
        return
    owned = [str(lb.ch) for lb in _board.lobbies if lb.owner and lb.owner['tid'] == tid]
    db = context.db
    await db.execute(OWN_SQL, (','.join(owned)[:40], db.server_id, tid))


# ---- ownership --------------------------------------------------------------------------------------------------

async def set_owner(lb, t, when=None):
    """BS_CBattleLobby::SetChannelOwner (or DeleteChannelOwner with None)."""
    old = lb.owner['tid'] if lb.owner else None
    lb.owner = t
    lb.own_time = (when or now()) if t else now()
    lb.leader = (-1, '')
    lb.race_sets = [(-1, 0, 1)] * 3
    if not t or t['tid'] != old:
        lb.successive = 0
    lb.dirty = True
    await save(lb)
    await save_owned(old)
    if t:
        await save_owned(t['tid'])
    log(f'{channel_name(lb.ch)}: owner {t["name"] if t else "none"}')


def log(text):
    print('channel battle:', text, flush=True)


# ---- the state machine (BS_CBattleLobby::OnTick) ---------------------------------------------------------------------

async def lobby_tick(lb):
    t = now()
    if lb.state == NONE_:
        if lb.open_time < t < lb.end_time:
            prepare(lb)
    elif lb.state == PREPARE:
        if lb.battle_time < t < lb.end_time:
            await try_battle(lb)
        elif t >= lb.end_time:
            await end_channel_battle(lb)
    elif lb.state == BATTLE:
        from . import rooms
        if lb.race is None or rooms.rooms.get(lb.race.id) is not lb.race:
            # everyone left the race (BS_CBattleLobby::StopBattle): the defence keeps the round
            lb.race = None
            await round_over(lb, 0)
    elif lb.state == ENDBATTLE:
        if time.time() > lb.state_time + END_SHOW:
            await end_battle(lb)
    elif lb.state == REST:
        decided = lb.result.def_wins or lb.result.atk_wins >= ATTACK_WINS or lb.challenger_room is None
        if t > lb.end_time and decided:
            await end_channel_battle(lb)
        elif time.time() > lb.state_time + REST_SECONDS:
            await try_battle(lb)
    elif lb.state == WAIT:
        if lb.battle_time < t < lb.end_time:
            await try_battle(lb)
        elif t >= lb.end_time:
            await end_channel_battle(lb)
    if lb.dirty:
        lb.dirty = False
        reseat(lb)
        lb.send_state()
        send_list(lb)
        for s in lb.recipients():       # the channel list again: its defence / challenging crew changed (user,
            send(s, info_frame(s, ACT_INFO))    # 2026-10-19: the attacker's name did not show; the window asks only once)


def prepare(lb):
    lb.result = Result()
    lb.match = 0
    lb.records = []
    lb.defeated.clear()
    lb.fee_paid.clear()
    lb.solo = False
    lb.set_state(PREPARE)
    log(f'{channel_name(lb.ch)}: open for registration, battle at {lb.battle_time}')


def pop_challenger(lb):
    while lb.queue:
        tid = lb.queue.pop(0)
        if tid != lb.owner_room and tid not in lb.defeated and lb.humans(tid):
            return tid
    return None


def owner_absent(lb):
    """Test mode: the channel's owner crew has no room here (or nobody owns it)."""
    return lb.owner is None or lb.owner['tid'] not in lb.crew_rooms


def waiting_defence(lb):
    """Test mode: the crew room (with players, not queued, not beaten) that was made first in the channel, or None. It
    defends against the test crew (user, 2026-10-19: Xerander raced alone though Newbie's crew had a room in the
    channel; a room that is not a test crew's queues only by Ready with 4 members)."""
    rooms_ = [(lb.room(tid).id, tid) for tid in list(lb.crew_rooms)
              if lb.room(tid) is not None and lb.humans(tid) and tid not in lb.queue and tid not in lb.defeated
              and tid != lb.challenger_room]
    return min(rooms_)[1] if rooms_ else None


async def try_battle(lb):
    """BS_CBattleLobby::TryBattle: the defence and the next challenger, and their next round."""
    if lb.owner_room is not None and not lb.humans(lb.owner_room):
        # the defence left the channel: "If there are no waiting members, you will lose Channel ownership"
        # (OnNewOwnerRoom's notice; user, 2026-10-19: the crew kept the channel after leaving it)
        gone, lb.owner_room = lb.owner_room, None
        if lb.owner and lb.owner['tid'] == gone:
            log(f'{channel_name(lb.ch)}: {lb.owner["name"]} left the channel: ownership lost')
            await set_owner(lb, None)
        lb.dirty = True
    if lb.challenger_room is not None and not lb.humans(lb.challenger_room):
        lb.defeated.add(lb.challenger_room)
        lb.challenger_room = None
        lb.dirty = True
    new_pair = False
    if lb.owner_room is None:
        # no defence: the first challenger takes the channel at once, without a race (user, 2026-10-19; 2008 TryBattle)
        # and defends it from now on. Test mode: a crew room already here that is not queued (it would need Ready and 4
        # members) defends against the test crew instead
        defence = waiting_defence(lb) if any(getattr(lb.room(tid), 'test', False) for tid in lb.queue) else None
        if defence is not None:
            lb.owner_room = defence
            log(f'{channel_name(lb.ch)}: test mode, {lb.team(defence)["name"]} (room here, not queued) defends')
        elif lb.challenger_room is not None:
            lb.owner_room, lb.challenger_room = lb.challenger_room, None
        else:
            lb.owner_room = pop_challenger(lb)
        if lb.owner_room is not None:
            await new_owner_room(lb)
    if lb.owner_room is None and not lb.solo:
        if lb.state != WAIT:
            lb.set_state(WAIT)
        return
    if lb.challenger_room is None:
        lb.challenger_room = pop_challenger(lb)
        new_pair = lb.challenger_room is not None
    if lb.challenger_room is None or not (lb.solo or lb.humans(lb.owner_room)):
        if lb.state != WAIT:
            lb.set_state(WAIT)
        return
    if new_pair:
        lb.result = Result()
    await start_round(lb)


async def new_owner_room(lb):
    """BS_CBattleLobby::OnNewOwnerRoom: the defence's crew owns the channel from now on."""
    t = lb.team(lb.owner_room)
    if t and (not lb.owner or lb.owner['tid'] != t['tid']):
        await set_owner(lb, t, lb.battle_time)
        lb.notice(lb.owner_room, CHANNEL_WON)       # our choice: the 2008 text for the channel taken (20265)
        lb.won_at = time.time()
    lb.dirty = True


def pick_track(lb, n):
    from . import rooms
    m, flag, traffic = lb.race_sets[n % 3]
    if m is None or m < 0 or flag & 1:
        m = random.choice(sorted(tracks()) or [0])
    return m, flag & ~1, traffic


_tracks = None


def tracks():
    """PVPTrackInfo.xlt "Id" of the tracks the client supports (column "Support" = 1); Taipei only with City.Taipei."""
    global _tracks
    if _tracks is None:
        import os
        from ..data import read_xlt
        _tracks = set()
        try:
            rows = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
            hdr = rows[2]
            c_id, c_sup, c_city = hdr.index('Id'), hdr.index('Support'), hdr.index('city')
            for r in rows[3:]:
                if len(r) > c_sup and r[c_id].strip().isdigit() and r[c_sup].strip() == '1':
                    if r[c_city].strip().lower() == 'taipei' and not context.extra_flags.get('City.Taipei'):
                        continue
                    _tracks.add(int(r[c_id]))
        except (OSError, ValueError):
            pass
    return _tracks


async def take_fees(lb):
    """CBattleFee: the attack's Challenge Coupons, once per character and battle (not in the test mode)."""
    from .alchemy import take_count
    from .items import mod_list
    for m in lb.humans(lb.challenger_room):
        p = m.player
        if not p or p.char.cid in lb.fee_paid or is_test(m.session) or not _cfg()['coupon']:
            continue
        changes = await take_count(p, COUPON, 1)
        if changes:
            lb.fee_paid.add(p.char.cid)
            send(m.session, mod_list(*changes))
            m.session.log.note(f'channel battle: Challenge Coupon used ({channel_name(lb.ch)})')


async def start_round(lb):
    """A round: both crews' members into a race room, team 0 the defence, 1 the attack, and the race starts."""
    from . import rooms
    if lb.result.round == 0:
        await take_fees(lb)
    n = lb.result.round
    map_id, flag, traffic = pick_track(lb, n)
    race = rooms.Room(BATTLE_CHANNEL + lb.ch, BATTLE_ROOM, map_id, flag, BATTLE_CAPACITY,
                      f'{channel_name(lb.ch)} round {n + 1}', '')
    race.cbattle = lb
    race.no_start = True
    race.on_result = lambda room, points, frame: asyncio.ensure_future(race_result(lb, room, points, frame))
    race.obs_teams = lambda: obs_teams(lb)
    rooms.rooms[race.id] = race
    lb.race = race
    for team, tid in ((0, lb.owner_room), (1, lb.challenger_room)):
        if tid is None or (team == 0 and lb.solo):
            continue
        r = lb.room(tid)
        for m in list(r.humans):
            r.members.remove(m)
            r.seats = [rooms.OPEN if v == m.serial else v for v in r.seats]
            seat = next((i for i in range(team, rooms.SEATS, 2) if race.seats[i] == rooms.OPEN), None)
            if seat is None:
                r.members.append(m)            # more than 16: waits in the crew room
                continue
            race.seats[seat] = m.serial
            m.ready, m.loaded, m.end = True, False, None
            race.members.append(m)
            m.session.state['room'] = race.id
    lb.attack_racers = sum(1 for m in race.members if race.seats.index(m.serial) & 1)
    if not race.members:
        del rooms.rooms[race.id]
        lb.race = None
        return
    race.master = race.members[0].serial
    lb.result.sub[min(n, 3)] = 1
    if n == 0:
        stake_parts(lb, race)
    start_recording(lb, race, n)
    lb.set_state(BATTLE)
    lb.send_state()     # the pair first: the round's VS splash (0x6a1f21) shows 0x386's names (user, 2026-10-19: the
    lb.record(0)        # defence's splash had no attack crew when the round came at the tick the challenger queued)
    log(f'{channel_name(lb.ch)}: round {n + 1}, {lb.team(lb.owner_room)["name"] if lb.owner_room is not None else "nobody"}'
        f' against {lb.team(lb.challenger_room)["name"]}, track {map_id}, {len(race.members)} racers')
    race.state = rooms.LOADING
    race.waiting = {o.serial for o in race.humans}
    race.racers = [o.serial for o in race.humans]
    race.rank, race.first_end, race.gates = 0, None, {}
    race.cast(race.master_frame(), race.state_frame())
    race.cast(Frame(0x1e7, struct.pack('<iiiifii', n + 1, map_id, flag, race.area, 0.0, tick() & 0x7fffffff, -1)))
    race.timer = asyncio.ensure_future(rooms.after(race, rooms.LOAD_TIMEOUT, rooms.LOADING))
    lb.send_state()
    for s in list(lb.spectators):
        spectate(s, lb)




async def race_result(lb, race, points, frame=None):
    """rooms.result's end for a channel battle race: the round's winner (more team points; a tie: the defence; a
    test crew alone wins by finishing)."""
    if lb.race is not race:
        return
    stop_recording(lb, race, frame)
    win = 1 if points[1] > points[0] else 0
    await round_over(lb, win)


async def round_over(lb, win):
    """BS_CBattleLobby::OnResult + ResultBattle: the round counted, everyone back into its crew room."""
    from . import rooms
    r = lb.result
    n = min(r.round, 3)
    r.win = win
    if win:
        r.atk_wins += 1
        r.sub[n] = 3
    else:
        r.def_wins += 1
        r.sub[n] = 2
    race, lb.race = lb.race, None
    if race is not None:
        race.cancel_timer()
        stop_recording(lb, race, None)
        for s in list(race.observers):          # spectators wait for the next round (spectate() at its start)
            s.state.pop('watching', None)
        race.observers = []
        for m in list(race.members):
            if not m.session:
                continue
            seat = race.seats.index(m.serial) if m.serial in race.seats else 0
            tid = lb.challenger_room if seat & 1 else lb.owner_room
            back = lb.room(tid) if tid is not None else None
            race.members.remove(m)
            if back is None:
                m.session.state.pop('room', None)
                continue
            free = free_seat(lb, back)
            if free is not None:
                back.seats[free] = m.serial
            m.ready = m.serial == back.master
            back.members.append(m)
            m.session.state['room'] = back.id
            send(m.session, back.master_frame(), back.state_frame())
        rooms.rooms.pop(race.id, None)
    lb.record(1, win)
    for s in list(lb.spectators):
        send(s, lb.state_frame())
    log(f'{channel_name(lb.ch)}: round {r.round + 1} won by the {"attack" if win else "defence"}'
        f' (attack {r.atk_wins}, defence {r.def_wins})')
    r.round += 1
    lb.set_state(ENDBATTLE)


async def log_match(lb, atk_won):
    """2008 SKID_CBATTLELOG_TB: one row per finished match (the Team Comparison's Total / Win / Lose, 0xe24)."""
    d, a = lb.team(lb.owner_room), lb.team(lb.challenger_room)
    if not d or not a or lb.solo:
        return
    r, db = lb.result, context.db
    battle_id = int(time.strftime('%Y%m%d', time.gmtime(lb.battle_time - CLOCK_SHIFT)))
    names = lambda tid: ','.join(m.name for m in lb.humans(tid))[:200]
    try:
        await db.execute(LOG_SQL, (db.server_id, lb.ch, battle_id, d['tid'], a['tid'], d['name'], a['name'],
                                   names(lb.owner_room), names(lb.challenger_room), r.def_wins, r.atk_wins, r.round,
                                   lb.match))
    except Exception as e:                  # the record must not stop the battle
        log(f'{channel_name(lb.ch)}: match log: {e!r}')


async def end_battle(lb):
    """BS_CBattleLobby::EndBattle: after the result's 10 s, the match goes on, or a crew is out."""
    r = lb.result
    lb.set_state(REST)
    if r.win and r.atk_wins < ATTACK_WINS:
        return
    await log_match(lb, bool(r.win))
    if r.win:
        # the attack takes the channel and defends it from now on
        if lb.owner_room is not None:
            lb.notice(lb.owner_room, DEFENCE_LOST)
            close_room(lb, lb.owner_room)
        await settle_stakes(lb, 1)
        lb.owner_room, lb.challenger_room, lb.solo = lb.challenger_room, None, False
        await new_owner_room(lb)                    # tells the new owner "Win the channel!"
        lb.match += 1
        lb.result = Result()
        return
    # the defence holds: the challenger is out of this channel for this battle
    await settle_stakes(lb, 0)
    if lb.challenger_room is not None:
        lb.defeated.add(lb.challenger_room)
        lb.notice(lb.challenger_room, ATTACK_LOST)
        close_room(lb, lb.challenger_room)
    lb.challenger_room = None
    if not lb.solo and lb.owner_room is not None and lb.attack_racers:
        await defence_reward(lb)
    lb.solo = False
    lb.match += 1
    lb.result = Result()


async def defence_reward(lb):
    """2008 EndBattle: 5000 Mito x the attacking racers to the defending crew's master ("CBattleWin"), 0x393 to the
    defence's room."""
    from .items import add_money
    from .social import online
    t = lb.team(lb.owner_room)
    amount = _cfg()['defence_reward'] * lb.attack_racers
    if not t or amount <= 0 or t['master'] < 0:
        return
    s = online(t['master'])
    if s:
        await add_money(s.state['player'].char, amount)
    else:
        db = context.db
        await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD=GOLD+%s WHERE SERVERID=%s AND CID=%s",
                         (amount, db.server_id, t['master']))
    out = Frame(0x393, struct.pack('<iq', lb.ch, t['master']) + wstr(t['master_name'], 42) + struct.pack('<q', amount))
    for m in lb.humans(lb.owner_room):
        send(m.session, out)
    log(f'{channel_name(lb.ch)}: defence reward {amount} Mito to {t["master_name"]}')


def close_room(lb, tid):
    """A crew room leaves the channel (BS_CBattleLobby::RoomClose): its members are sent out (0x1d6 to each: the
    client closes the room) and the room goes."""
    from . import rooms
    r = lb.crew_rooms.pop(tid, None)
    if tid in lb.queue:
        lb.queue.remove(tid)
    if r is None or rooms.rooms.get(r.id) is not r:
        return
    for m in list(r.humans):
        m.session.state.pop('room', None)
        send(m.session, Frame(0x1d6, struct.pack('<I', m.serial) + r.seat_bytes() + struct.pack('<I', r.type)))
    r.members = []
    rooms.rooms.pop(r.id, None)
    send_list(lb)


async def end_channel_battle(lb):
    """BS_CBattleLobby::EndChannelBattle: the owner keeps / takes the channel; every crew room closes."""
    if lb.race is not None:
        return
    t = lb.owner
    if t and t['tid'] > 0:
        db = context.db
        last = await db.row(LAST_SQL, (db.server_id, lb.ch))
        prev_owner = int(last[0]) if last and last[0] is not None else -1
        lb.successive = (int(last[1] or 0) if prev_owner == t['tid'] else 0) + 1
        battle_id = int(time.strftime('%Y%m%d', time.gmtime(lb.battle_time - CLOCK_SHIFT)))
        await db.execute(WIN_SQL, (db.server_id, lb.ch, battle_id, db.server_id, lb.ch, battle_id, t['tid'], lb.successive))
        await db.execute(TEAM_WIN_SQL, (db.server_id, t['tid']))
        if lb.owner_room is not None and time.time() > lb.won_at + 30:     # not again right after taking it
            lb.notice(lb.owner_room, CHANNEL_WON)
        log(f'{channel_name(lb.ch)}: {t["name"]} holds the channel ({lb.successive} week(s) in a row)')
    for tid in list(lb.crew_rooms):
        if tid != lb.owner_room:
            lb.notice(tid, BATTLE_OVER)
        close_room(lb, tid)
    lb.owner_room = lb.challenger_room = None
    lb.queue.clear()
    lb.solo = False
    release_stakes(lb)
    for s in list(lb.spectators):
        send(s, lb.state_frame())
    lb.spectators.clear()
    lb.set_state(NONE_)
    lb.open_time = lb.battle_time = lb.end_time = 0
    if all(x.state == NONE_ for x in _board.lobbies):
        _board.schedule()


# ---- tax ----------------------------------------------------------------------------------------------------------

def tax_rate(lb):
    c = _cfg()
    if lb.ch < MAJOR:
        return c['tax_major']
    if lb.ch < MAIN:
        return c['tax_minor'][min(max(lb.successive, 1), 3) - 1]
    return c['tax_semi'][min(lb.ch - MAIN, len(c['tax_semi']) - 1)]


def collect_tax(paid):
    """A refuel payment (session.fuel_charge): each owned channel's share."""
    if paid <= 0 or _board is None:
        return
    for lb in _board.lobbies:
        if lb.owner and lb.owner['tid'] > 0:
            lb.acc_tax += paid * tax_rate(lb) / 100.0


def fuel_discount(p):
    """2008 Cmd_FuelChargeReq: a crew owning a normal channel for 2 weeks in a row -> 10 % off (flag 4), 3 and more -> 20 %
    (flag 2) -> (factor off, sale flag bits)."""
    if _board is None or p.char.team_id <= 0:
        return 0.0, 0
    best = max((lb.successive for lb in _board.lobbies[:MAIN] if lb.owner and lb.owner['tid'] == p.char.team_id),
               default=0)
    return (0.2, 2) if best >= 3 else (0.1, 4) if best == 2 else (0.0, 0)


async def tax_payout():
    """Once a day at [cbattle] tax_hour (local time): each owned channel's tax to its crew's master."""
    b = _board
    t = time.localtime()
    day = time.strftime('%Y%m%d', t)
    if t.tm_hour < _cfg()['tax_hour'] or b.last_payout == day:
        return
    b.last_payout = day
    from .social import online
    db = context.db
    for lb in b.lobbies:
        amount = int(lb.acc_tax)
        if not lb.owner or lb.owner['tid'] <= 0 or amount <= 0 or lb.owner['master'] < 0:
            continue
        master = lb.owner['master']
        await db.execute(TAX_PAY_SQL, (amount, db.server_id, master, amount, db.server_id, lb.owner['tid'],
                                       amount, db.server_id, lb.ch))
        lb.acc_tax -= amount
        s = online(master)
        if s:
            c = s.state['player'].char
            c.mito += amount
            send(s, Frame(0x8a, struct.pack('<iiqq', 1, 1, amount, c.mito) + b'\0\0'))
            from .. import admin
            admin.message(s, f'{channel_name(lb.ch)} tax: {amount} Mito for your crew {lb.owner["name"]}.')
        log(f'{channel_name(lb.ch)}: tax {amount} Mito to {lb.owner["master_name"]}')


# ---- handlers -----------------------------------------------------------------------------------------------------

@on_open(SVC)
async def start_board(session):
    board()


def info_frame(session, act):
    b = board()
    out = struct.pack('<IIii', act, b.next_battle, 0, len(b.lobbies))
    return Frame(0x35d, out + b''.join(lb.channel_record(session) for lb in b.lobbies))


@on(SVC, C2S, 0x35c)
async def channel_battle_info(session, frame):
    act, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    send(session, info_frame(session, act))


@on(SVC, C2S, 0x35e)
async def get_battle_time(session, frame):
    act, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    send(session, Frame(0x35f, struct.pack('<Ii', act, board().next_battle)))


def ownership_frame():
    b = board()
    return Frame(0x316, struct.pack('<I', len(b.lobbies)) + b''.join(
        struct.pack('<ifiii', lb.ch, lb.acc_tax, lb.successive, lb.owner.get('wins', 0) if lb.owner else 0, 0)
        + smp_team(lb.owner) for lb in b.lobbies))


@on(SVC, C2S, 0x30c)
async def area_list(session, frame):
    send(session, Frame(0x315, struct.pack('<I', len(GATES)) + b''.join(struct.pack('<iii', *g) for g in GATES)))
    send(session, ownership_frame())


def send_list(lb):
    out = lb.list_frame()
    for s in list(lb.watchers):
        send(s, out)


def watch(session, lb):
    old = session.state.get('cb_watch')
    if old is not None and old is not lb:
        old.watchers.discard(session)
    session.state['cb_watch'] = lb
    lb.watchers.add(session)
    send(session, lb.list_frame())
    lb.send_state([session])
    send(session, lb.broadcast_frame())


@on(SVC, C2S, 0x372)
async def enter_channel(session, frame):
    if not session.state.get('player'):
        return error(session, NO_CHAR)
    lb = lobby(struct.unpack_from('<i', frame.payload)[0] if len(frame.payload) >= 4 else -1)
    if lb is None:
        return error(session, NO_CHANNEL)
    watch(session, lb)


@on(SVC, C2S, 0x373)
async def exit_channel(session, frame):
    lb = session.state.pop('cb_watch', None)
    if lb:
        lb.watchers.discard(session)


async def checks(session, ch, create):
    """The 2008 Cmd_CBattleRoomCreate / Join checks -> (lobby, crew dict) or None after telling the player."""
    from .crews import refresh
    p = session.state.get('player')
    if not p:
        error(session, NO_CHAR)
        return None
    lb = lobby(ch)
    if lb is None:
        error(session, NO_CHANNEL)
        return None
    t = await refresh(session, p) if p.char.team_id > 0 else None
    if not t:
        error(session, NO_CREW)
        return None
    if create and p.char.team_rank >= 3:
        error(session, NOT_FIRST)
        return None
    refused = entry_refused(session, ch)
    if refused:
        from .. import admin
        session.log.note(f'channel battle {channel_name(ch)}: {refused}')
        admin.message(session, refused)
        return None
    t_now = now()
    if not lb.open_time <= t_now <= lb.end_time:
        error(session, '20080')
        return None
    owner = lb.owner and lb.owner['tid'] == t['tid']
    test = is_test(session)
    if not owner:
        from .crews import crew_level
        if create and ch < MAIN and crew_level(t) == 0 and not test:
            error(session, LOW_CREW)
            return None
        if t['tid'] in lb.defeated:
            error(session, ONCE)
            return None
        if _cfg()['coupon'] and not test and p.char.cid not in lb.fee_paid and \
                not any(i.item_id == COUPON and not i.car_id for i in p.items):
            error(session, NO_COUPON)
            return None
    for other in board().lobbies:
        if other is not lb and other.room(t['tid']):
            from .. import admin
            admin.message(session, f'Your crew is already registered in {channel_name(other.ch)}.')
            return None
    return lb, t


def crew_room(lb, t, test):
    from . import rooms

    class CrewRoom(rooms.Room):
        def list_entry(self):
            e = bytearray(super().list_entry())
            struct.pack_into('<qq', e, 0x5a, t['tid'], t['mark'])
            return bytes(e)
    r = CrewRoom(CREW_CHANNEL + lb.ch, CREW_ROOM, 0, 0, CREW_CAPACITY, t['name'], '')
    r.crew, r.cbattle, r.no_start, r.test = t, lb, True, test
    rooms.rooms[r.id] = r
    lb.crew_rooms[t['tid']] = r
    return r


def is_defence(lb, tid):
    return tid == lb.owner_room or (lb.owner is not None and lb.owner['tid'] == tid and lb.owner_room is None)


def free_seat(lb, r):
    """A crew room seat by the crew's role: the client shows the owner's window ("Channel Owning Crew", blue) for an
    even seat and the challenger's (red) for an odd one (0x6a7e0a: the player's serial among the room's seats, bit 0),
    as the race seats the defence on even seats (user, 2026-10-19: a challenger had the owner's window)."""
    from . import rooms
    first = 0 if is_defence(lb, r.crew['tid']) else 1
    return next((i for i in range(first, rooms.SEATS, 2) if r.seats[i] == rooms.OPEN), None)


def reseat(lb):
    """Each crew room's members on the seats of its role (after the defence changed); the room told if moved."""
    from . import rooms
    for tid in list(lb.crew_rooms):
        r = lb.room(tid)
        if r is None:
            continue
        parity = 0 if is_defence(lb, tid) else 1
        wrong = [i for i, v in enumerate(r.seats) if v not in (rooms.OPEN, rooms.LOCKED) and i % 2 != parity]
        if not wrong:
            continue
        for i in wrong:
            serial, r.seats[i] = r.seats[i], rooms.OPEN
            seat = free_seat(lb, r)
            r.seats[seat if seat is not None else i] = serial
        r.cast(r.state_frame())


@on(SVC, C2S, 0x370)
async def room_create(session, frame):
    """0x370 CBattleRoomCreate (the crew master / first class): the crew's room in the channel, or into it."""
    from . import rooms
    p = frame.payload
    if len(p) < 0x10:
        return
    ch, = struct.unpack_from('<i', p, 0xc)
    got = await checks(session, ch, True)
    if not got:
        return
    lb, t = got
    pl = session.state['player']
    r = lb.room(t['tid'])
    if r is not None:
        return join_room(session, lb, r, p[0:rooms.USER_INFO], rooms.car_attr_of(pl.car) if pl.car else bytes(12))
    rooms.leave(session)
    test = is_test(session)
    r = crew_room(lb, t, test)
    m = rooms.Member(session, p[0:rooms.USER_INFO], rooms.car_attr_of(pl.car) if pl.car else bytes(12))
    m.ready = True
    r.members.append(m)
    r.master = m.serial
    r.seats[free_seat(lb, r)] = m.serial
    session.state['room'] = r.id
    owner = lb.owner and lb.owner['tid'] == t['tid']
    session.log.note(f'channel battle {channel_name(ch)}: room {r.id} of crew {t["name"]!r}'
                     f' ({"owner" if owner else "challenger"}{", test" if test else ""})')
    send(session, r.master_frame(), r.state_frame(), Frame(0x376, p[0:rooms.USER_INFO] + struct.pack('<i', ch)))
    if owner and lb.state in (PREPARE, WAIT, REST, NONE_) and lb.owner_room is None:
        lb.owner_room = t['tid']
        lb.dirty = True
    elif not owner and test:
        queue(lb, t['tid'], session)
    watch(session, lb)
    send_list(lb)
    lb.dirty = True


def join_room(session, lb, r, user_info, car_attr):
    from . import rooms
    if r.member(session):
        return send(session, r.master_frame(), r.state_frame())
    seat = free_seat(lb, r)
    if seat is None:
        return error(session, '20039')
    rooms.leave(session)
    m = rooms.Member(session, user_info, car_attr)
    r.cast(Frame(0x1d4, struct.pack('<IH', m.serial, m.age) + m.user_info + m.car_attr
                 + struct.pack('<II', r.id, r.life_id) + m.info() + r.seat_bytes() + struct.pack('<I', r.type)))
    r.seats[seat] = m.serial
    r.members.append(m)
    session.state['room'] = r.id
    session.log.note(f'channel battle {channel_name(lb.ch)}: joins the room of crew {r.crew["name"]!r}')
    send(session, r.master_frame(), r.state_frame())
    watch(session, lb)
    send_list(lb)
    lb.send_state([session])


@on(SVC, C2S, 0x371)
async def room_join(session, frame):
    """0x371 CBattleRoomJoin (a member): into the crew's room in the channel."""
    p = frame.payload
    if len(p) < 0x1c:
        return
    ch, = struct.unpack_from('<i', p, 0x18)
    got = await checks(session, ch, False)
    if not got:
        return
    lb, t = got
    r = lb.room(t['tid'])
    if r is None:
        return error(session, NO_ROOM)
    join_room(session, lb, r, p[0:12], p[12:24])


def queue(lb, tid, session=None):
    if tid not in lb.queue and tid != lb.owner_room and tid != lb.challenger_room:
        lb.queue.append(tid)
        if session:
            session.log.note(f'channel battle {channel_name(lb.ch)}: crew {tid} queued ({len(lb.queue)} waiting)')
        lb.dirty = True


@on(SVC, C2S, 0x384)
async def room_ready(session, frame):
    """0x384 CBattleRoomReady (channel, state): a challenger room queues (1) or leaves the queue (0); the owner's room
    readies itself (its client, on 0x376)."""
    from . import rooms
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    ch, state = struct.unpack_from('<ii', frame.payload)
    lb = lobby(ch)
    r = rooms.room_of(session)
    if lb is None or r is None or getattr(r, 'cbattle', None) is not lb:
        return
    if p.char.team_rank >= 3:
        return error(session, NOT_FIRST)
    tid = r.crew['tid']
    if lb.owner and lb.owner['tid'] == tid:
        if lb.owner_room is None and state:
            lb.owner_room = tid
            lb.dirty = True
    elif state:
        queue(lb, tid, session)
    elif tid in lb.queue:
        lb.queue.remove(tid)
        lb.dirty = True
    r.cast(Frame(0x384, struct.pack('<ii', ch, state)))
    send_list(lb)


@on(SVC, C2S, 0x387)
async def battle_instance(session, frame):
    act, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    from . import rooms
    running = [lb for lb in board().lobbies if lb.race is not None]
    send(session, Frame(0x388, struct.pack('<II', act, len(running)) + b''.join(
        struct.pack('<iiii', lb.race.area, lb.race.map_id, lb.ch, rooms.spectator_count(lb.race)) for lb in running)))


@on(SVC, C2S, 0x38e)
async def get_setting(session, frame):
    if len(frame.payload) < 8:
        return
    act, ch = struct.unpack_from('<Ii', frame.payload)
    lb = lobby(ch)
    if lb is None:
        return error(session, '20087')
    o = lb.owner
    out = struct.pack('<Iiiii', act, ch, lb.open_time, lb.battle_time, lb.end_time)
    out += struct.pack('<q', lb.leader[0]) + wstr(lb.leader[1], 42)
    out += struct.pack('<q', o['master'] if o else 0) + wstr(o['master_name'] if o else '', 42)
    out += struct.pack('<q', o['tid'] if o else 0) + wstr(o['name'] if o else '', 26)
    out += b''.join(struct.pack('<hhi', max(-1, m), f & 0xffff, tr) for m, f, tr in lb.race_sets)
    send(session, Frame(0x38f, out))


@on(SVC, C2S, 0x38a)
async def battle_set(session, frame):
    """0x38a CBattleSet: the owner crew's master sets the battle leader and the three rounds' tracks (within 24 h of
    taking a normal channel; GMs any time)."""
    from .misc import is_admin
    p = session.state.get('player')
    f = frame.payload
    if not p or len(f) < 0x4a:
        return
    ch, = struct.unpack_from('<i', f)
    lb = lobby(ch)
    if lb is None:
        return error(session, NO_CHANNEL)
    gm = is_admin(session)
    if not gm:
        if p.char.team_id <= 0:
            return error(session, NO_CREW)
        if p.char.team_rank != 1:
            return error(session, NOT_MASTER)
        if not lb.owner or lb.owner['tid'] != p.char.team_id:
            return error(session, NOT_OWNER)
        if not lb.own_time <= now() <= lb.own_time + FULL_DAY:
            return error(session, NOT_NOW)
        if ch >= MAIN:
            from .. import admin
            return admin.message(session, 'This channel is semi channel!')
    leader = read_wstr(f, 0x18, 26)
    sets = [struct.unpack_from('<hhi', f, 0x32 + 8 * k) for k in range(3)]
    lb.leader = (p.char.cid if leader == p.char.name else lb.leader[0] if leader == lb.leader[1] else -1, leader)
    lb.race_sets = [(m, fl & 0xffff, tr) for m, fl, tr in sets]
    session.log.note(f'channel battle {channel_name(ch)}: leader {leader!r}, tracks {lb.race_sets}')
    await save(lb)


def room_changed(lb):
    """rooms.leave from a channel battle room: a crew room that emptied leaves the channel; the list again."""
    from . import rooms
    for tid in list(lb.crew_rooms):
        r = lb.crew_rooms[tid]
        if rooms.rooms.get(r.id) is not r:
            del lb.crew_rooms[tid]
            if tid in lb.queue:
                lb.queue.remove(tid)
            lb.dirty = True
    send_list(lb)


@on_open(SVC)
async def forget_watcher(session):
    try:
        await asyncio.Event().wait()
    finally:
        lb = session.state.get('cb_watch')
        if lb:
            lb.watchers.discard(session)


# ---- spectators ---------------------------------------------------------------------------------------------------

def obs_teams(lb):
    """The 0x1bf spectator state's crew block for the round (rooms.Room.obs_state_frame): i32 round state[4], i64 crew
    [2], i64 mark[2], wchar[31] name[2] (the defence first)."""
    d, a = (lb.team(lb.owner_room) if lb.owner_room is not None else None), lb.team(lb.challenger_room)
    return (struct.pack('<4i', *lb.result.sub)
            + struct.pack('<qq', d['tid'] if d else -1, a['tid'] if a else -1)
            + struct.pack('<qq', d['mark'] if d else -1, a['mark'] if a else -1)
            + wstr(d['name'] if d else '', 62) + wstr(a['name'] if a else '', 62))


def spectate(session, lb):
    """A spectator onto the round's race (the battle zone's spectator view: 0x26e + 0x1bf, then the race's moves on
    the race connection with 0x336). Not rooms.watch: a channel battle race always allows spectators, also one test
    racer alone."""
    from . import rooms
    race = lb.race
    if race is None or not session.state.get('player'):
        return
    rooms.unwatch(session)
    if session not in race.observers:
        race.observers.append(session)
    session.state['watching'] = race.id
    send(session, race.master_frame(), race.obs_state_frame())
    rooms.spectator_count(race)
    session.log.note(f'channel battle {channel_name(lb.ch)}: spectates round {lb.result.round + 1}')


def stop_spectating(session):
    for lb in (_board.lobbies if _board else []):
        lb.spectators.discard(session)


@on(SVC, C2S, 0x38b)
async def join_obs(session, frame):
    """0x38b CBattleJoinOBS (channel): spectate the battle; between rounds the view waits for the next one."""
    from .. import admin
    lb = lobby(struct.unpack_from('<i', frame.payload)[0] if len(frame.payload) >= 4 else -1)
    if lb is None or lb.state in (NONE_,) or not session.state.get('player'):
        return error(session, OBS_FAIL)
    stop_spectating(session)
    lb.spectators.add(session)
    send(session, lb.state_frame(), lb.broadcast_frame())
    if lb.race is not None:
        spectate(session, lb)
    else:
        admin.message(session, f'{channel_name(lb.ch)}: no round is running; the view follows the next one.')


# ---- Major channel part stakes (2008 BS_CBattleRoom::RegisterBattleItem / BS_CBattleLobby::GatherBattleItem) -------

STAKED_TEXT = 'This part is at stake in a Major channel battle until the match ends.'


class Stake:
    def __init__(self, team, cid, name, it):
        self.team, self.cid, self.name = team, cid, name
        self.gid, self.inven_idx, self.item_id = it.gid, it.inven_idx, it.item_id
        from .mail import item_text
        self.text = item_text(it, 1)
        self.unit = it.encode()[:0x48]

    def entry(self):
        """XiCBattleItemInfo as 0x38d / 0x391 / 0x392 carry it (0x88): wchar[32] item id, the item unit (0x48)."""
        return wstr(self.item_id, 64) + self.unit


def staked(p, it):
    return any((x := lb.stakes.get(p.char.cid)) and x.gid == it.gid and x.inven_idx == it.inven_idx
               for lb in (_board.lobbies if _board else []))


def stake_parts(lb, race):
    """A Major channel match's first round: one random part on each racer's car is at stake ([cbattle] major_stakes;
    the client's own warning, text 10553: "If you fail, one of your equipped parts will be lost.")."""
    from .items import ON_CAR, SLOT_BASE, info_of
    lb.stakes = {}
    if not (_cfg()['major_stakes'] and lb.is_major()) or lb.solo:
        return
    for m in race.humans:
        p = m.player
        if not p or not p.car:
            continue
        parts = [i for i in p.items if i.car_id == p.car.car_id and (i.state & 0xffff) == ON_CAR and info_of(i)
                 and info_of(i).type in SLOT_BASE]
        if not parts:
            continue
        it = random.choice(parts)
        team = race.seats.index(m.serial) & 1
        lb.stakes[p.char.cid] = Stake(team, p.char.cid, p.char.name, it)
        from .. import admin
        admin.message(m.session, f'{channel_name(lb.ch)} (Major channel): your {info_of(it).name or it.item_id} is at '
                                 f'stake until the match ends. If your crew loses, it goes to the winning crew.')
        m.session.log.note(f'channel battle {channel_name(lb.ch)}: at stake {it.item_id} (inven {it.inven_idx})')


def release_stakes(lb):
    lb.stakes = {}


async def settle_stakes(lb, winner):
    """A decided Major channel match: the losing crew's staked parts leave their owners (0x392) and go to the winning
    crew's master as a message with the part attached (2008: into the master's inventory, by message when offline);
    the winners get 0x391 with them."""
    from .items import DELETE_SQL, REMOVED, info_of, mod_list
    from .login import stat_frames
    from .social import online
    from . import mail
    stakes, lb.stakes = lb.stakes, {}
    lost = [x for x in stakes.values() if x.team != winner]
    win_tid = lb.challenger_room if winner else lb.owner_room
    t = lb.team(win_tid) if win_tid is not None else None
    if not lost or not t or t['master'] < 0:
        return
    db = context.db
    for x in lost:
        s = online(x.cid)
        if s:
            p = s.state['player']
            it = next((i for i in p.items if i.gid == x.gid and i.inven_idx == x.inven_idx), None)
            if not it:
                continue
            await db.execute(DELETE_SQL, (db.server_id, x.cid, it.inven_idx))
            p.items.remove(it)
            send(s, mod_list((it, REMOVED)), Frame(0x392, struct.pack('<iII', lb.ch, 1, 0) + x.entry()), *stat_frames(p))
        else:
            await db.execute(DELETE_SQL + " AND GID=%s", (db.server_id, x.cid, x.inven_idx, x.gid))
        row = await db.row(mail.INSERT, (db.server_id, t['master'], 0, 'Channel Battle', 0, '',
                                         f'{channel_name(lb.ch)}: won from {x.name}', 0, x.text))
        target = online(t['master'])
        if row and target:
            got = await db.row(mail.SELECT + " AND MID=%s", (db.server_id, t['master'], int(row[0])))
            if got:
                send(target, mail.row_frame(t['master'], got))
        log(f'{channel_name(lb.ch)}: {x.name} loses {x.item_id} to {t["name"]} ({t["master_name"]})')
    prize = Frame(0x391, struct.pack('<iII', lb.ch, len(lost), 0) + b''.join(x.entry() for x in lost))
    for m in lb.humans(win_tid):
        send(m.session, prize)


@on(SVC, C2S, 0x38c)
async def battle_items(session, frame):
    """0x38c CBattleItems (channel) -> 0x38d: the parts at stake in the channel's match (10 per frame)."""
    ch, = struct.unpack_from('<i', frame.payload) if len(frame.payload) >= 4 else (0,)
    lb = lobby(ch)
    entries = [x.entry() for x in lb.stakes.values()] if lb else []
    for page in range(max(1, (len(entries) + 9) // 10)):
        part = entries[page * 10:page * 10 + 10]
        send(session, Frame(0x38d, struct.pack('<iII', ch, len(part), page) + b''.join(part)))


# ---- replays -------------------------------------------------------------------------------------------------------
# The client's replay = the race as it arrived (its own recorder, App+0x174 0x78d9e0 "play_record.r0"): 0x26d RoomModify
# (0x8e), 0x1be RoomState, 0x329 + XiPlayerInfo per racer (0xde), then every race command in its raw form (type +
# payload): moves 0x221, jumps 0x225, objects 0x2d0, traffic 0x21e / 0x220 / 0x223, AI 0x21f, and the result 0x1ec.
# Here the server records each channel battle round so (area.recorders) into Emulator/replays/<key>.r0, listed in
# replays/index.json.
#   0x395 ReplayList (u32 version) -> 0x396 ReplayListAck (client 0x52dbf0): u32 version (the client sends it back),
#       offset, total, n @0xe,
#       n x 0xec @0x12: char[32] key, char[16] channel number @0x20 (the price: Major 1000, Minor 500, Semi free,
#       client 0x78cfb0), u32 match @0x30, round @0x34, wchar[66] "%d %d %I64d %I64d %31s %31s" @0x38 (round, match,
#       defence crew, attack crew, their names; client 0x58ee60 shows "Match %d"), u32 @0xbc time, @0xc0 size, @0xc4
#       map, @0xc8 0, u32 views @0xe8 ("Viewed: %d").
#   0x397 Replay (the entry's key, channel text, match, round, u32 step @0x3a, i64 price @0x3e) -> 0x398 ReplayRes
#       (the same + i64 Mito @0x46; client 0x52b130): step 0 opens it (result 0 starts the download, 1 = text 10293
#       "not enough Mito"); step 1 comes with the first data and pays (the answer's price and Mito set the client's
#       money; result 2 so nothing restarts). Free with the Ch. Battle Replay Pass (drift item category 44).
#   0x227 ReplayData (race connection; key, u32 x3, u32 have @0x2e) -> 0x228 (u32 size @2, offset @6, n @0xa, bytes).

REPLAY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                          'replays')
REPLAY_CHUNK = 16000
REPLAY_PASS, GHOST_PASS = 44, 45            # VisualItem categories: Ch. Battle Replay Pass, Ch. Replay Ghost Pass
RECORDED = {0x221, 0x225, 0x2d0, 0x21e, 0x220, 0x223, 0x21f}
_replays = None


def replays():
    global _replays
    if _replays is None:
        try:
            _replays = json.load(open(os.path.join(REPLAY_DIR, 'index.json')))
        except (OSError, ValueError):
            _replays = []
    return _replays


def save_replays():
    os.makedirs(REPLAY_DIR, exist_ok=True)
    tmp = os.path.join(REPLAY_DIR, 'index.json.new')
    json.dump(replays(), open(tmp, 'w'), indent=1)
    os.replace(tmp, os.path.join(REPLAY_DIR, 'index.json'))


class Recorder:
    def __init__(self, key, head):
        self.key, self.data, self.pov = key, bytearray(head), None

    def __call__(self, t, p):
        if t in RECORDED:
            self.data += struct.pack('<H', t) + bytes(p)


def start_recording(lb, race, n):
    from ..area import recorders
    head = bytearray(struct.pack('<H', 0x26d) + race.modify_frame().payload)
    head += struct.pack('<H', 0x1be) + race.state_frame().payload
    # the replay's header (crew names, round states) is the spectator state's (0x1bf, 0x52e160); without it the client
    # showed its placeholder names (user, 2026-10-19)
    head += struct.pack('<H', 0x1bf) + race.obs_state_frame().payload
    for m in race.humans:
        head += struct.pack('<HI', 0x329, 1) + m.info()
    battle = time.strftime('%y%m%d%H%M', time.gmtime(lb.battle_time - CLOCK_SHIFT))
    rec = Recorder(f'cb{battle}_{lb.ch:02d}_{lb.match}_{n}', head)
    rec.pov = race.humans[0].serial if race.humans else None
    d, a = (lb.team(lb.owner_room) if lb.owner_room is not None else None), lb.team(lb.challenger_room)
    rec.meta = dict(key=rec.key, ch=lb.ch, match=lb.match, round=n, time=now(), map=race.map_id, views=0,
                    def_tid=d['tid'] if d else -1, def_name=d['name'] if d else '-',
                    atk_tid=a['tid'] if a else -1, atk_name=a['name'] if a else '-')
    recorders[race.area] = rec
    race.recorder = rec


def stop_recording(lb, race, result_frame):
    from ..area import recorders
    rec = getattr(race, 'recorder', None)
    if rec is None or recorders.get(race.area) is not rec:
        return
    del recorders[race.area]
    race.recorder = None
    if result_frame is not None:
        rec.data += struct.pack('<H', result_frame.type) + result_frame.payload
    os.makedirs(REPLAY_DIR, exist_ok=True)
    open(os.path.join(REPLAY_DIR, rec.key + '.r0'), 'wb').write(bytes(rec.data))
    rec.meta['size'] = len(rec.data)
    keep = _cfg()['replays']
    lst = [r for r in replays() if r['key'] != rec.key] + [rec.meta]
    for old in lst[:-keep] if keep and len(lst) > keep else []:
        try:
            os.remove(os.path.join(REPLAY_DIR, old['key'] + '.r0'))
        except OSError:
            pass
    replays()[:] = lst[-keep:] if keep else lst
    save_replays()
    log(f'{channel_name(lb.ch)}: replay {rec.key} saved ({len(rec.data)} bytes)')


def replay_price(p, ch):
    """Major 1000 / Minor 500 Mito, Semi-channels free (the client's prices, 0x78cfb0); free with the Replay Pass."""
    from .items import holds
    if holds(p, REPLAY_PASS):
        return 0
    return 1000 if ch < MAJOR else 500 if ch < MAIN else 0


def replay_entry(r):
    text = (f'{r["round"]} {r["match"]} {r["def_tid"]} {r["atk_tid"]} {r["def_name"].replace(" ", "_") or "-"} '
            f'{r["atk_name"].replace(" ", "_") or "-"}')
    out = (r['key'].encode('ascii')[:31].ljust(32, b'\0') + str(r['ch']).encode().ljust(16, b'\0')
           + struct.pack('<II', r['match'], r['round']) + wstr(text, 0x84)
           + struct.pack('<IIII', r['time'] & 0xffffffff, r.get('size', 0), r['map'], 0))
    return out.ljust(0xe8, b'\0') + struct.pack('<I', r.get('views', 0))


@on(SVC, C2S, 0x395)
async def replay_list(session, frame):
    """The u32 is not a channel: the client keeps 0x396's first u32 (App+0x174 +0x1c, 0x52dbf0) and sends it back with
    its next 0x395 (0x58ddac): a list version. It was read as a channel filter, so every list came back empty (the
    client always had 0 = Channel 1; user, 2026-10-19: "server records no Channel Battle replays"). All replays are
    sent, newest first; the version is the newest replay's time."""
    found = list(reversed(replays()))
    version = max((r.get('time', 0) for r in found), default=0) & 0x7fffffff
    for off in range(0, max(len(found), 1), 20):
        part = found[off:off + 20]
        send(session, Frame(0x396, struct.pack('<iIII', version, off, len(found), len(part))
                            + b''.join(replay_entry(r) for r in part)))


@on(SVC, C2S, 0x397)
async def replay_open(session, frame):
    from .items import add_money
    p = session.state.get('player')
    f = frame.payload
    if not p or len(f) < 0x44:
        return
    key = f[:32].split(b'\0')[0].decode('ascii', 'replace')
    step, = struct.unpack_from('<I', f, 0x38)
    r = next((x for x in replays() if x['key'] == key), None)
    price = replay_price(p, r['ch']) if r else 0
    head = f[:0x38]
    if r is None or not os.path.exists(os.path.join(REPLAY_DIR, key + '.r0')):
        from .. import admin
        admin.message(session, 'This replay is no longer kept.')
        return send(session, Frame(0x398, head + struct.pack('<iqq', 3, 0, p.char.mito)))
    if step == 0:
        if price > p.char.mito:
            return send(session, Frame(0x398, head + struct.pack('<iqq', 1, 0, p.char.mito)))
        session.state['replay'] = key
        session.log.note(f'replay {key}: open (price {price})')
        return send(session, Frame(0x398, head + struct.pack('<iqq', 0, 0, p.char.mito)))
    # step 1: the data came, it is paid now
    if price and not await add_money(p.char, -price):
        return send(session, Frame(0x398, head + struct.pack('<iqq', 1, 0, p.char.mito)))
    r['views'] = r.get('views', 0) + 1
    save_replays()
    session.log.note(f'replay {key}: watched for {price} Mito')
    send(session, Frame(0x398, head + struct.pack('<iqq', 2, price, p.char.mito)))


def replay_chunk(session, p):
    """0x227 on the race connection: the next REPLAY_CHUNK bytes of the replay from what the client has."""
    if len(p) < 0x34:
        return
    key = p[:32].split(b'\0')[0].decode('ascii', 'replace')
    have, = struct.unpack_from('<I', p, 0x2c)
    try:
        data = open(os.path.join(REPLAY_DIR, os.path.basename(key) + '.r0'), 'rb').read()
    except OSError:
        data = b''
    part = data[have:have + REPLAY_CHUNK]
    session.to_client(Frame(0x228, struct.pack('<III', len(data), have, len(part)) + part))


# ---- Ghost Battle in a replay (Ch. Replay Ghost Pass, Ch. Battle Ghost Tickets) -------------------------------------
# 0x212 GhostStart (0x1b6; client 0x7a9ee0: five u32, the racer's XiStrStatInfo (104) @0x14, XiStrEnChantBonus (40)
# @0x7c, 268 bytes @0xa4) -> 0x213 GhostStartAck (0x1b2; client 0x52cda0 takes the same three blocks @0x16 / @0x7e /
# @0xa6 and starts): answered with the client's own blocks when the player holds the Ghost Pass (category 45) or uses
# up a Ghost Ticket of the replay's channel (ch_ghost_NN, NN = channel + 1, or the old ch_ghost). 0x216 GhostResult
# (u32, u32) -> 0x217 (0x2a, ignored by the client). *The ticket rule is ours: the client shows the tickets' text only.*

def game_session_of(session):
    from .login import sessions
    if session.service == 'game':
        return session
    car = session.state.get('car')
    name = car.name if car else ''
    return next((s for s in sessions.values() if s.state.get('player') and s.state['player'].char.name == name), None)


def ghost_message(session, t, p):
    asyncio.ensure_future(_ghost(session, t, p))


async def _ghost(session, t, p):
    from .alchemy import take_count
    from .items import holds, mod_list
    from .. import admin
    if t == 0x216:
        return session.to_client(Frame(0x217, bytes(0x28)))
    gs = game_session_of(session)
    pl = gs.state.get('player') if gs else None
    if not pl or len(p) < 0x1b0:
        return
    key = gs.state.get('replay', '')
    r = next((x for x in replays() if x['key'] == key), None)
    ch = r['ch'] if r else -1
    if not holds(pl, GHOST_PASS):
        tickets = [f'ch_ghost_{ch + 1:02d}', 'ch_ghost']
        used = None
        for item_id in tickets:
            changes = await take_count(pl, item_id, 1)
            if changes:
                used = item_id
                send(gs, mod_list(*changes))
                break
        if not used:
            gs.log.note(f'ghost battle in replay {key or "?"}: no Ghost Pass or ticket')
            return admin.message(gs, 'Ghost Battle needs the Ch. Replay Ghost Pass or a Battle Ghost Ticket of this channel.')
        gs.log.note(f'ghost battle in replay {key}: {used} used')
    session.to_client(Frame(0x213, p[:0x1b0]))           # the blocks at the same places as the client sent them


@on(SVC, C2S, 0x212)
async def ghost_start_game(session, frame):
    await _ghost(session, 0x212, frame.payload)


@on(SVC, C2S, 0x216)
async def ghost_result_game(session, frame):
    await _ghost(session, 0x216, frame.payload)


# ---- GM -----------------------------------------------------------------------------------------------------------

def gm_test(session, args):
    """gmcbtest on | off: this character's channel battle test mode."""
    on_ = not args or args[0].lower() not in ('off', '0', 'no')
    session.state['cb_test'] = on_
    if not on_:
        return 'channel battle test mode off'
    return ('channel battle test mode on: no Challenge Coupon or crew rank needed, your crew room queues at once; with no '
            'crew to defend the channel your crew takes it when the battle starts. Open a battle now with: gmcbattle now')


async def gm_command(session, args):
    """gmcbattle now [minutes to the battle] [battle minutes] | start [battle minutes] | end | owner <channel> <crew |
    test | none> | status."""
    b = board()
    w = [a.lower() for a in args]
    if not w or w[0] == 'status':
        out = [f'next battle {time.strftime("%a %H:%M UTC", time.gmtime(b.next_battle - CLOCK_SHIFT))}']
        for lb in b.lobbies:
            out.append(f'{lb.ch + 1}:{lb.state}' + (f' {lb.owner["name"]}' if lb.owner else '')
                       + (f' q{len(lb.queue)}' if lb.queue else ''))
        return '; '.join(out)
    if w[0] == 'now':
        wait = float(w[1]) if len(w) > 1 else 1.0
        length = float(w[2]) if len(w) > 2 else 20.0
        t = now() + int(wait * 60)
        for lb in b.lobbies:
            if lb.state != NONE_:
                return f'a battle is running in {channel_name(lb.ch)}: gmcbattle end first'
        b.schedule(t, int(wait * 60) + 1, int(length * 60))
        return (f'channel battle: registration open now, the battle starts in {wait:g} min and lasts {length:g} min '
                f'(open the Crew window > Channel Battle)')
    if w[0] == 'start':                         # the battle at once (user, 2026-10-19: "start channel battle right away")
        length = float(w[1]) if len(w) > 1 else 20.0
        t = now()
        busy = [lb for lb in b.lobbies if lb.state not in (NONE_, PREPARE)]
        if busy:
            return f'the battle is already on in {channel_name(busy[0].ch)} ({busy[0].state}): gmcbattle end first'
        open_ = [lb for lb in b.lobbies if lb.state == PREPARE]
        if open_:                               # registration running: skip the rest of it
            for lb in open_:
                lb.battle_time = t - 1
                lb.end_time = max(lb.end_time, t + int(length * 60))
                lb.dirty = True
            b.next_battle = t - 1
            return (f'channel battle starts now in {len(open_)} channels (until '
                    f'{time.strftime("%H:%M UTC", time.gmtime(max(lb.end_time for lb in open_) - CLOCK_SHIFT))}); '
                    f'crews whose rooms are ready race first')
        b.schedule(t, 1, int(length * 60))     # registration and battle open together
        return (f'channel battle on now for {length:g} min: make or join the crew room (Crew window > Channel Battle) '
                f'and press Ready; the first room in a channel without a defence takes it')
    if w[0] == 'end':
        for lb in b.lobbies:
            lb.end_time = min(lb.end_time, now() - 1) if lb.state != NONE_ else lb.end_time
            if lb.race is not None:
                await round_over(lb, 0)
        return 'channel battles end now'
    if w[0] == 'stakes':
        if len(w) > 1:
            _cfg()['major_stakes'] = w[1] in ('on', '1', 'yes')
        return (f'Major channel part stakes {"on" if _cfg()["major_stakes"] else "off"} (a part of each racer; the losing '
                f'crew\'s parts go to the winning crew master)')
    if w[0] == 'replays':
        return f'{len(replays())} channel battle replays kept: ' + ', '.join(r['key'] for r in replays()[-8:])
    if w[0] == 'owner' and len(args) >= 3 and args[1].isdigit():
        lb = lobby(int(args[1]) - 1)
        if lb is None:
            return f'no channel {args[1]} (1-{len(b.lobbies)})'
        name = ' '.join(args[2:])
        if name.lower() == 'none':
            await set_owner(lb, None)
            return f'{channel_name(lb.ch)}: no owner'
        if name.lower() == 'test':
            await set_owner(lb, test_crew())
            return f'{channel_name(lb.ch)}: owned by a test crew that never defends'
        from .crews import team_by_name
        t = await team_by_name(name)
        if not t:
            return f'no crew {name!r}'
        await set_owner(lb, t)
        return f'{channel_name(lb.ch)}: owned by {t["name"]}'
    return ('usage: gmcbattle now [minutes to the battle] [battle minutes] | start [battle minutes] | end | owner <channel> <crew|test|none> | '
            'stakes [on|off] | replays | status')


# ---- Team Comparison ----------------------------------------------------------------------------------------------
# 0xe24 TeamCompare (i64 crew, i64 crew; the battle's T button, new in 2011: no 2008 handler) -> 0xe25 (0xb8; client
# 0x5199f0): i64 crew @0 / @8, i64 mark @0x10 / @0x18 (the client asks 0x40 GetImage 0x3f5 with crew @0 and mark @0x10:
# user, 2026-10-19: the second crew's icon was missing while it was crew, mark, crew, mark), wchar[13] names @0x20 / @0x3a, masters @0x54 / @0x6e, then i32 pairs (first, second): ranking @0x88 ("Rank
# %d"), members @0x90, channels owned @0x98, matches @0xa0, won @0xa8, lost @0xb0 (" %dTotal %dWin %dLose", 12033).
# The record counts SKID_CBATTLELOG_TB (written by log_match since 2026-10-19): a defence wins a match with any round,
# an attack with ATTACK_WINS rounds.
@on(SVC, C2S, 0xe24)
async def team_compare(session, frame):
    from .crews import team
    if len(frame.payload) < 16:
        return
    db = context.db
    sides = []
    for tid in struct.unpack_from('<qq', frame.payload):
        t = await team(tid) if tid > 0 else None
        total = won = 0
        if t:
            r = await db.row(RECORD_SQL, (tid, tid, db.server_id, tid, tid))
            total, won = (int(r[0] or 0), int(r[1] or 0)) if r else (0, 0)
        sides.append((tid, t, total, won))
    out = struct.pack('<qq', *(tid for tid, _, _, _ in sides))
    out += struct.pack('<qq', *(t['mark'] if t else 0 for _, t, _, _ in sides))
    out += b''.join(wstr(t['name'] if t else '', 26) for _, t, _, _ in sides)
    out += b''.join(wstr(t['master_name'] if t else '', 26) for _, t, _, _ in sides)
    owned = lambda t: len([x for x in t['channels'].split(',') if x.strip()]) if t else 0
    for f in (lambda x: x[1]['ranking'] if x[1] else 0, lambda x: x[1]['count'] if x[1] else 0,
              lambda x: owned(x[1]), lambda x: x[2], lambda x: x[3], lambda x: x[2] - x[3]):
        out += struct.pack('<ii', *(f(x) for x in sides))
    session.log.note(f'team compare {[(x[1]["name"] if x[1] else x[0], x[2], x[3]) for x in sides]}')
    send(session, Frame(0xe25, out))
