"""The 2016 DCGP layer (dcemu/native/game/dcgp.py).

Layouts: docs/neo_work/DCGP_PROTOCOL.md - S>C 0x777 (154, section 3.2), S>C 0x776 (11, section 3.1),
S>C 0x778 (type word only, section 3.3) and S>C 0x89 event 40 (18, section 3.4), plus the C>S sizes of the
same numbers. The scoring, the season dates and the reward-group names are ours (the module's docstring); the
storage is a fake database.

Nothing here was tried in game.
"""
import asyncio
import struct
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import dcgp
from dcemu.wire import Frame

SEASON = 1


class FakeDb:
    """SKID_DCGP_TB in memory: (cid, season) -> [team, points, claimed]."""

    server_id = 2016

    def __init__(self):
        self.rows_by_key = {}
        self.executed = []

    def _row(self, cid, season):
        return self.rows_by_key.setdefault((cid, season), [0, 0, 0])

    async def execute(self, sql, p=()):
        self.executed.append(sql)
        if sql.startswith('CREATE TABLE'):
            return 0
        if sql.startswith('INSERT INTO SKID_DCGP_TB'):
            _sid, cid, season = p
            self._row(cid, season)
            return 1
        if sql.startswith('UPDATE SKID_DCGP_TB SET TEAM'):
            team, _sid, cid, season = p
            self._row(cid, season)[0] = team
            return 1
        if sql.startswith('UPDATE SKID_DCGP_TB SET POINTS'):
            points, _sid, cid, season = p
            self._row(cid, season)[1] += points
            return 1
        if sql.startswith('UPDATE SKID_DCGP_TB SET CLAIMED'):
            _sid, cid, season = p
            self._row(cid, season)[2] = 1
            return 1
        raise AssertionError(f'unexpected SQL: {sql}')

    async def row(self, sql, p=()):
        if sql.startswith('SELECT TEAM, POINTS, CLAIMED'):
            _sid, cid, season = p
            r = self.rows_by_key.get((cid, season))
            return tuple(r) if r else None
        raise AssertionError(f'unexpected SQL: {sql}')

    async def rows(self, sql, p=()):
        if 'GROUP BY TEAM' in sql:
            _sid, season = p
            sums = {}
            for (cid, s), r in self.rows_by_key.items():
                if s == season and r[0] in (dcgp.WEST, dcgp.EAST):
                    sums[r[0]] = sums.get(r[0], 0) + r[1]
            return sorted(sums.items())
        raise AssertionError(f'unexpected SQL: {sql}')


class Session:
    def __init__(self, cid=101, name='Driver'):
        self.id = 0x1234
        self.state = {'player': SimpleNamespace(char=SimpleNamespace(cid=cid, name=name, level=10))}
        self.log = Mock()

    def to_client(self, frame):
        raise AssertionError('the handlers must use login.send')


def dword(frame, frame_off):
    return struct.unpack_from('<I', frame.payload, frame_off - 2)[0]


def qword(frame, frame_off):
    return struct.unpack_from('<Q', frame.payload, frame_off - 2)[0]


def text(frame, frame_off, size):
    start = frame_off - 2
    return frame.payload[start:start + size].split(b'\0', 1)[0]


def types(frames):
    return [f.type for f in frames]


class Dcgp2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(item_index={'i_n_00001': 1, 'part_a': 2})
        context.dcgp = {'enabled': True}
        context.db = self.db = FakeDb()
        dcgp._ready = False
        self.s = Session()
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def call(self, handler, payload=b''):
        """Run one handler with the module's send() recorded (login.send bundles several frames)."""
        self.sent = []
        with patch.object(dcgp, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)):
            asyncio.run(handler(self.s, Frame(0x777, payload)))
        return list(self.sent)

    def points(self, won, place=1):
        self.sent = []
        with patch.object(dcgp, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)):
            asyncio.run(dcgp.race_points(self.s, won, place))
        return list(self.sent)

    def claim(self, roll=(), gains_items=()):
        """C>S 0x778 with driftuse.roll / rewards.give stubbed (the real ones need RewardGroup.xlt)."""
        self.groups, self.given = [], []

        async def give(p, pairs):
            self.given = pairs
            return SimpleNamespace(items=list(gains_items)), []

        def do_roll(group):
            self.groups.append(group)
            return list(roll)

        self.sent = []
        with patch.object(dcgp, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)), \
                patch('dcemu.native.game.driftuse.roll', do_roll), \
                patch('dcemu.native.game.rewards.give', give):
            asyncio.run(dcgp.claim(self.s, Frame(0x778, b'')))
        return self.sent

    def by_type(self, frames, msg_type):
        return next(f for f in frames if f.type == msg_type)

    # ---- the sizes (sections 3.1 - 3.4) ---------------------------------------------------------------

    def test_sizes(self):
        """0x777 = 154, 0x776 = 11, 0x778 = 6 (0x52b6a3) and 0x89 = 18."""
        f777 = self.by_type(self.call(dcgp.season_state, bytes(152)), 0x777)
        self.assertEqual(len(f777.payload) + 2, 154)
        f776 = self.by_type(self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', 1)), 0x776)
        self.assertEqual(len(f776.payload) + 2, 11)
        self.assertEqual(len(dcgp.claim_frame().payload) + 2, 6)
        self.assertEqual(len(dcgp.points_frame(1, 10).payload) + 2, 18)

    def test_state_frame_defaults(self):
        """0x777 without cfg: phase 1, season 1, zero totals, the three dates, rw_dcgp_common x 2."""
        f = self.by_type(self.call(dcgp.season_state, bytes(152)), 0x777)
        self.assertEqual(dword(f, 0x02), dcgp.PHASE_RACING)
        self.assertEqual(dword(f, 0x06), SEASON)
        self.assertEqual((qword(f, 0x0a), qword(f, 0x12)), (0, 0))
        start, end, reward_end = dcgp.season_times()
        self.assertEqual((dword(f, 0x1a), dword(f, 0x1e), dword(f, 0x22)),
                         (start, end, reward_end))
        self.assertEqual(text(f, 0x26, 0x38).decode(), 'rw_dcgp_common')
        self.assertEqual(text(f, 0x5e, 0x38).decode(), 'rw_dcgp_common')
        self.assertEqual(f.payload[0x96 - 2:], bytes(4))          # +0x96 is not read by the client

    def test_state_frame_totals_per_team(self):
        """The two u64 totals are the sums of POINTS per TEAM this season (section 7.7)."""
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 30, 0]
        self.db.rows_by_key[(102, SEASON)] = [dcgp.WEST, 12, 0]
        self.db.rows_by_key[(103, SEASON)] = [dcgp.EAST, 7, 0]
        self.db.rows_by_key[(104, SEASON)] = [0, 99, 0]            # no team: never counted
        self.db.rows_by_key[(101, SEASON - 1)] = [dcgp.EAST, 500, 0]     # another season
        f = self.by_type(self.call(dcgp.season_state, bytes(152)), 0x777)
        self.assertEqual((qword(f, 0x0a), qword(f, 0x12)), (42, 7))

    def test_state_frame_settings(self):
        """[dcgp] season / phase / winner / loser are ours and land in the frame (section 3.2)."""
        context.dcgp.update(season=4, phase=dcgp.PHASE_REWARD, winner='rw_a', loser='rw_b')
        f = self.by_type(self.call(dcgp.season_state, bytes(152)), 0x777)
        self.assertEqual((dword(f, 0x02), dword(f, 0x06)), (dcgp.PHASE_REWARD, 4))
        self.assertEqual(text(f, 0x26, 0x38).decode(), 'rw_a')
        self.assertEqual(text(f, 0x5e, 0x38).decode(), 'rw_b')

    def test_login_push(self):
        """The same 0x777 without a request (the login push the lead may add); silent when disabled."""
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 3, 0]
        self.sent = []
        with patch.object(dcgp, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)):
            asyncio.run(dcgp.send_state(self.s))
        self.assertEqual(types(self.sent), [0x777])
        self.assertEqual(len(self.sent[0].payload) + 2, 154)
        self.assertEqual(qword(self.sent[0], 0x0a), 3)
        context.dcgp = {}
        self.sent = []
        with patch.object(dcgp, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)):
            asyncio.run(dcgp.send_state(self.s))
        self.assertEqual(self.sent, [])

    def test_season_times(self):
        """The three timestamps: first / last second of the month, then end + 7 days (UTC, ours)."""
        start, end, reward_end = dcgp.season_times(datetime(2026, 2, 15, 12, tzinfo=timezone.utc))
        self.assertEqual(start, int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(end, int(datetime(2026, 2, 28, 23, 59, 59, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(reward_end, int(datetime(2026, 3, 7, 23, 59, 59, tzinfo=timezone.utc).timestamp()))
        start, end, _ = dcgp.season_times(datetime(2026, 12, 31, tzinfo=timezone.utc))    # December
        self.assertEqual(start, int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(end, int(datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(dcgp.season_times()[0] <= dcgp.season_times()[1], True)

    # ---- 0x776 (team) --------------------------------------------------------------------------------

    def test_776_stores_the_team(self):
        """S>C 0x776: show flag @2 = 1, the season @3, the team @7; the choice is stored (section 3.1)."""
        f = self.by_type(self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', dcgp.WEST)), 0x776)
        self.assertEqual(f.payload[0], 1)
        self.assertEqual(dword(f, 0x03), SEASON)
        self.assertEqual(dword(f, 0x07), dcgp.WEST)
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][0], dcgp.WEST)

    def test_776_change_while_no_points(self):
        """Ours: the team may change while POINTS == 0, never after (the doc says nothing, section 8)."""
        self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', dcgp.WEST))
        f = self.by_type(self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', dcgp.EAST)), 0x776)
        self.assertEqual((dword(f, 0x07), self.db.rows_by_key[(101, SEASON)][0]), (dcgp.EAST, dcgp.EAST))
        self.db.rows_by_key[(101, SEASON)][1] = 12                 # the season has points now
        f = self.by_type(self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', dcgp.WEST)), 0x776)
        self.assertEqual((dword(f, 0x07), self.db.rows_by_key[(101, SEASON)][0]), (dcgp.EAST, dcgp.EAST))

    def test_776_bad_team_is_ignored(self):
        """Only 1 West / 2 East (0x530c10's validation is the 0x89 one; the client pushes only 1 or 2)."""
        for team in (0, 3, 0xffffffff):
            self.assertEqual(self.call(dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', team)), [])
        self.assertNotIn((101, SEASON), self.db.rows_by_key)

    def test_776_needs_the_payload(self):
        self.assertEqual(self.call(dcgp.select_team, b'\0' + bytes(4)), [])

    # ---- 0x778 (claim) -------------------------------------------------------------------------------

    def test_778_refused_while_racing(self):
        """Phase 1 (racing, the default): silent, nothing stored, no item given (0x5b9df7)."""
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 10, 0]
        self.assertEqual(self.claim(), [])
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][2], 0)
        self.assertEqual((self.groups, self.given), ([], []))

    def test_778_granted_once_after_racing(self):
        """Phase 2: 0x778 (6 bytes), the group rolled, CLAIMED = 1, and a second claim does nothing."""
        context.dcgp['phase'] = dcgp.PHASE_REWARD
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 10, 0]
        frames = self.claim(roll=[('NormalItem', 'i_n_00001', 0, 2, 0)])
        self.assertEqual(types(frames), [0x778])
        self.assertEqual(len(frames[0].payload) + 2, 6)
        self.assertEqual(self.given, [('i_n_00001', 2)])
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][2], 1)
        self.assertEqual(self.claim(), [])
        self.assertEqual(self.given, [])

    def test_778_winner_and_loser_group(self):
        """The group is the winner's when the player's team leads, else the loser's (ours; a tie loses)."""
        context.dcgp['phase'] = dcgp.PHASE_REWARD
        context.dcgp.update(winner='rw_win', loser='rw_lose')
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 10, 0]     # West 10
        self.db.rows_by_key[(102, SEASON)] = [dcgp.EAST, 4, 0]      # East 4
        self.claim()
        self.assertEqual(self.groups, ['rw_win'])
        self.db.rows_by_key[(101, SEASON)][2] = 0
        self.db.rows_by_key[(102, SEASON)][1] = 30                  # West 10 : East 34: the losing side
        self.claim()
        self.assertEqual(self.groups, ['rw_lose'])
        self.db.rows_by_key[(101, SEASON)][2] = 0
        self.db.rows_by_key[(102, SEASON)][1] = 10                  # 10 : 10, a tie
        self.claim()
        self.assertEqual(self.groups, ['rw_lose'])

    def test_778_unknown_group_gives_nothing(self):
        """A group with no usable row still acks: the client shows 12798 and lists nothing (section 4.2)."""
        context.dcgp['phase'] = dcgp.PHASE_REWARD
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 0, 0]
        frames = self.claim(roll=[('n/a', '', 0, 0, 0), ('NormalItem', 'not_an_item', 0, 1, 0)])
        self.assertEqual(types(frames), [0x778])
        self.assertEqual((self.given, self.db.rows_by_key[(101, SEASON)][2]), ([], 1))

    def test_778_sends_the_items(self):
        """The changed inventory items go out as items.mod_list (0x192) after the ack, as neocity does."""
        context.dcgp['phase'] = dcgp.PHASE_REWARD
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 0, 0]
        item = SimpleNamespace(encode=lambda: bytes(0x100))
        frames = self.claim(roll=[('NormalItem', 'i_n_00001', 0, 1, 0)], gains_items=((item, 1),))
        self.assertEqual(types(frames), [0x778, 0x192])
        self.assertEqual(dword(frames[1], 0x02), 1)
        self.assertEqual(len(frames[1].payload), 0x100 + 4 + 4)

    def test_778_without_a_team(self):
        context.dcgp['phase'] = dcgp.PHASE_REWARD
        self.db.rows_by_key[(101, SEASON)] = [0, 40, 0]
        self.assertEqual(self.claim(), [])

    # ---- 0x89 event 40 (race_points) -----------------------------------------------------------------

    def test_89_points_with_a_team(self):
        """Win: [dcgp] win_points (10), 0x89 = 18 bytes, event 40, team, points (section 3.4)."""
        self.db.rows_by_key[(101, SEASON)] = [dcgp.EAST, 5, 0]
        frames = self.points(True, place=1)
        self.assertEqual(types(frames), [0x89])
        f = frames[0]
        self.assertEqual(len(f.payload) + 2, 18)
        self.assertEqual((dword(f, 0x02), dword(f, 0x06), dword(f, 0x0a), dword(f, 0x0e)),
                         (dcgp.EVENT_POINTS, dcgp.EAST, 10, 0))
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][1], 15)

    def test_89_play_points(self):
        """A loss pays [dcgp] play_points (2); the settings are ours."""
        self.db.rows_by_key[(101, SEASON)] = [dcgp.WEST, 0, 0]
        f = self.points(False, place=4)[0]
        self.assertEqual((dword(f, 0x06), dword(f, 0x0a)), (dcgp.WEST, 2))
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][1], 2)
        context.dcgp.update(win_points=25, play_points=3)
        self.db.rows_by_key[(101, SEASON)][1] = 0
        self.assertEqual(dword(self.points(True)[0], 0x0a), 25)
        self.assertEqual(dword(self.points(False)[0], 0x0a), 3)
        self.assertEqual(self.db.rows_by_key[(101, SEASON)][1], 28)

    def test_89_needs_a_team(self):
        """A player who has not chosen a team contributes nothing (and no row is created)."""
        self.assertEqual(self.points(True), [])
        self.assertEqual(self.db.rows_by_key, {})
        self.assertEqual(self.db.executed.count(dcgp.SCHEMA_SQL), 1)     # only CREATE TABLE

    # ---- off ----------------------------------------------------------------------------------------

    def test_disabled_sends_nothing(self):
        """context.dcgp without enabled (the default {}) -> no answer, no query."""
        context.dcgp = {}
        self.assertFalse(dcgp.enabled())
        payloads = [(dcgp.season_state, bytes(152)),
                    (dcgp.select_team, b'\0' + bytes(4) + struct.pack('<I', dcgp.WEST)),
                    (dcgp.claim, b''), (dcgp.claim, bytes(4))]
        for handler, payload in payloads:
            self.assertEqual(self.call(handler, payload), [], handler.__name__)
        self.assertEqual(self.points(True), [])
        self.assertEqual(self.db.executed, [])

    def test_2011_gets_nothing(self):
        """The 2011 flag table has no BattleZone.DCGP at all (section 7)."""
        version.configure({'version': '2011'})
        self.assertFalse(dcgp.enabled())
        for handler in (dcgp.season_state, dcgp.select_team, dcgp.claim):
            self.assertEqual(self.call(handler, bytes(152)), [])
        self.assertEqual(self.points(True), [])
        self.assertEqual(self.db.executed, [])

    def test_enabled_needs_a_dict(self):
        """A context.dcgp that is not a dict is treated as off (the default {})."""
        for value in (None, True, 'yes', []):
            context.dcgp = value
            self.assertFalse(dcgp.enabled())
        self.assertEqual(dcgp.config(), {})
        self.assertEqual(dcgp.season_key(), SEASON)
        self.assertEqual(dcgp.phase(), dcgp.PHASE_RACING)
        self.assertEqual(dcgp.group_names(), ('rw_dcgp_common', 'rw_dcgp_common'))


if __name__ == '__main__':
    unittest.main()
