"""The 2016 WORLD MATCH LAP TIME layer (dcemu/native/game/worldmatch.py).

Layouts: docs/neo_work/WMLAPTIME_PROTOCOL.md - 0xf59 (202), 0xf5c (6), 0xf58 (99), 0xf51 (6 + 0x35*n),
0xf57 (0xe + len), 0xf54 (28), 0xf5e (130) and the C>S sizes of 0xf53 / 0xf55 / 0xf56 / 0xf5a / 0xf5b /
0xf5c / 0xf5d (sections 3 and 4). The season rows come from the real
server_data_2016/Init/WorldMatchSeasonLaptime.xlt (5 seasons, 2013-04-24 .. 2014-06-29, section 5); the
ranking itself is ours and comes from a fake database.

Nothing here was tried in game.
"""
import asyncio
import os
import struct
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import login, worldmatch
from dcemu.wire import Frame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server_data_2016')
REC = 0x35


class FakeDb:
    """SKID_WMLAPTIME_TB in memory; the ranking's NLEVEL comes from `chars` (SKID_CHARACTER_TB)."""

    server_id = 2016

    def __init__(self):
        self.rows_by_key = {}     # (cid, season) -> [nickname, best seconds or None, tries, tryday]
        self.chars = {}           # cid -> (name, level)
        self.executed = []

    async def execute(self, sql, p=()):
        self.executed.append(sql)
        if sql.startswith('CREATE TABLE'):
            return 0
        if sql.startswith('INSERT INTO SKID_WMLAPTIME_TB'):
            if 'BESTSEC=CASE' in sql:                       # BEST_SQL: keep the lowest lap
                _sid, cid, _cname, season, secs = p
                row = self.rows_by_key.setdefault((cid, season), ['', None, 0, 0])
                if row[1] is None or secs < row[1]:
                    row[1] = secs
                return 1
            _sid, cid, _cname, season = p                   # ENSURE_SQL
            self.rows_by_key.setdefault((cid, season), ['', None, 0, 0])
            return 1
        if sql.startswith('UPDATE SKID_WMLAPTIME_TB SET NICKNAME'):
            name, _sid, cid, season = p
            self.rows_by_key.setdefault((cid, season), ['', None, 0, 0])[0] = name
            return 1
        if sql.startswith('UPDATE SKID_WMLAPTIME_TB SET TRIES'):
            tries, day, _sid, cid, season = p
            row = self.rows_by_key.setdefault((cid, season), ['', None, 0, 0])
            row[2], row[3] = tries, day
            return 1
        raise AssertionError(f'unexpected SQL: {sql}')

    async def row(self, sql, p=()):
        if sql.startswith('SELECT NICKNAME, BESTSEC'):
            _sid, cid, season = p
            r = self.rows_by_key.get((cid, season))
            return tuple(r) if r else None
        if sql.startswith('SELECT CID FROM SKID_WMLAPTIME_TB'):
            _sid, season, cid, name = p
            for (other, s), r in self.rows_by_key.items():
                if s == season and other != cid and r[0] and r[0].lower() == name.lower():
                    return (other,)
            return None
        raise AssertionError(f'unexpected SQL: {sql}')

    async def rows(self, sql, p=()):
        if 'LEFT JOIN SKID_CHARACTER_TB' in sql:             # LIST_SQL
            _sid, season = p
            out = []
            for (cid, s), r in self.rows_by_key.items():
                if s == season and r[1] is not None:
                    name, level = self.chars.get(cid, ('', 0))
                    out.append((name, r[0], r[1], level, cid))
            out.sort(key=lambda r: (r[2], r[4]))
            return out
        raise AssertionError(f'unexpected SQL: {sql}')


class Session:
    def __init__(self, cid=101, name='Driver', level=10, serial=0x1234):
        char = SimpleNamespace(cid=cid, name=name, level=level)
        self.id = serial
        self.state = {'player': SimpleNamespace(char=char), 'serial': serial}
        self.log = Mock()

    def to_client(self, frame):
        raise AssertionError('the handlers must use login.send')


def dword(frame, frame_off):
    return struct.unpack_from('<I', frame.payload, frame_off - 2)[0]


def f32(frame, frame_off):
    return struct.unpack_from('<f', frame.payload, frame_off - 2)[0]


def text(frame, frame_off, size):
    return frame.payload[frame_off - 2:frame_off - 2 + size].split(b'\0', 1)[0]


def types(frames):
    return [f.type for f in frames]


class WorldMatch2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.saved_sessions = dict(login.sessions)
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(root=ROOT)
        context.worldmatch = {'enabled': True}
        context.db = self.db = FakeDb()
        worldmatch._ready = False
        self.db.chars = {101: ('Driver', 10), 102: ('Rival', 20)}
        self.s = Session()
        self.sent = []
        self.season = worldmatch.season_now()[0].number

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        login.sessions.clear()
        login.sessions.update(self.saved_sessions)
        version.configure({'version': '2011'})

    def call(self, handler, payload=b''):
        """Run one handler with the module's send() recorded (login.send bundles several frames)."""
        self.sent = []
        with patch.object(worldmatch, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)), \
                patch.object(worldmatch, 'build_status_info', lambda p, season: Frame(0x3c0, b'')):
            asyncio.run(handler(self.s, Frame(0xf53, payload)))
        return self.sent

    def burst(self):
        return self.call(worldmatch.refresh, struct.pack('<I', 3))

    def record(self, lap_ms):
        """record_lap with the module's send() recorded."""
        self.sent = []
        with patch.object(worldmatch, 'send', side_effect=lambda to, *frames: self.sent.extend(frames)):
            asyncio.run(worldmatch.record_lap(self.s, lap_ms))
        return list(self.sent)

    def by_type(self, frames, msg_type):
        return next(f for f in frames if f.type == msg_type)

    # ---- the season table (section 5) and the season pick ---------------------------------------------

    def test_season_table(self):
        """5 data rows: seasons 1..5, city / track / stat ids and the four dates of section 5."""
        rows = worldmatch.season_table()
        self.assertEqual([r.number for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual((rows[0].city, rows[0].track, rows[0].stat), (0, 70, 1))
        self.assertEqual(rows[4].begin_text, '2014-04-01 00:00:00')
        self.assertEqual(rows[4].end_text, '2014-06-29 23:59:59')
        self.assertEqual(rows[4].reward_begin_text, '2014-06-30 00:00:00')
        self.assertEqual(rows[4].reward_end_text, '2014-06-30 23:59:59')

    def test_season_pick_by_date(self):
        """tournament period -> the row, state 0; its reward period -> state 1 (section 3.7)."""
        rows = worldmatch.season_table()
        season, state = worldmatch.pick_season(rows, datetime(2013, 5, 1, 12))
        self.assertEqual((season.number, state), (1, worldmatch.STATE_RACING))
        season, state = worldmatch.pick_season(rows, datetime(2013, 6, 30, 12))
        self.assertEqual((season.number, state), (1, worldmatch.STATE_REWARD))
        season, state = worldmatch.pick_season(rows, datetime(2014, 2, 1))
        self.assertEqual((season.number, state), (4, worldmatch.STATE_RACING))
        season, state = worldmatch.pick_season(rows, datetime(2014, 6, 30, 12))
        self.assertEqual((season.number, state), (5, worldmatch.STATE_REWARD))

    def test_season_pick_fallbacks(self):
        """Before every row: no season. After the last begin: that row, state 1 once rewards began."""
        rows = worldmatch.season_table()
        season, state = worldmatch.pick_season(rows, datetime(2012, 1, 1))
        self.assertIsNone(season)
        self.assertEqual(state, worldmatch.STATE_RACING)
        season, state = worldmatch.pick_season(rows, datetime(2026, 1, 1))
        self.assertEqual((season.number, state), (5, worldmatch.STATE_RACING))   # ours: the last season keeps running
        # a row with neither period (a broken table row) still answers
        season, state = worldmatch.pick_season([], datetime(2026, 1, 1))
        self.assertIsNone(season)
        self.assertEqual(state, worldmatch.STATE_RACING)

    # ---- the sizes and the burst order ---------------------------------------------------------------

    def test_sizes_empty_season(self):
        """0xf59 = 202, 0xf5c = 6, 0xf58 = 99, 0xf51 = 0x3b with n = 0 (0x53b9bb; sections 3.7 / 3.8 / 3.6 / 3.2)."""
        frames = self.burst()
        self.assertEqual(types(frames), [0x3c0, 0xf59, 0xf5c, 0xf58, 0xf51])     # no rank 1: no 0xf57
        _, f59, f5c, f58, f51 = frames
        self.assertEqual(len(f59.payload) + 2, 202)
        self.assertEqual(len(f5c.payload) + 2, 6)
        self.assertEqual(len(f58.payload) + 2, 99)
        self.assertEqual(dword(f51, 0x02), 0)
        self.assertEqual(len(f51.payload) + 2, 0x3b)          # n = 0 is sized as 1 (0x53b9bb)

    def test_burst_order_and_season_frame(self):
        """0xf59 (season, state, 4 x char[48] copied from the table), 0xf5c, 0xf58, 0xf51, 0xf57."""
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 1, int(datetime.now().strftime('%Y%m%d'))]
        frames = self.burst()
        self.assertEqual(types(frames), [0x3c0, 0xf59, 0xf5c, 0xf58, 0xf51, 0xf57])
        season, state = worldmatch.season_now()
        f59 = frames[1]
        self.assertEqual(dword(f59, 0x02), season.number)
        self.assertEqual(dword(f59, 0x06), state)
        self.assertEqual(text(f59, 0x0a, 48).decode(), season.begin_text)
        self.assertEqual(text(f59, 0x0a + 48, 48).decode(), season.end_text)
        self.assertEqual(text(f59, 0x0a + 96, 48).decode(), season.reward_begin_text)
        self.assertEqual(text(f59, 0x0a + 144, 48).decode(), season.reward_end_text)
        self.assertEqual(dword(frames[2], 0x02), 1)                       # one try used

    def test_51_record(self):
        """0xf51: n @2, then {char[21] name, char[11] country, char[13] nickname, f32 seconds, u32 level}."""
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 0, 0]
        self.db.rows_by_key[(102, self.season)] = ['RIVAL', 88.25, 0, 0]
        f51 = self.by_type(self.burst(), 0xf51)
        self.assertEqual(dword(f51, 0x02), 2)
        self.assertEqual(len(f51.payload) + 2, 6 + 2 * REC)
        base = 6
        self.assertEqual(text(f51, base + 0x00, 21).decode(), 'Rival')    # best first
        self.assertEqual(text(f51, base + 0x15, 11).decode(), 'USA')
        self.assertEqual(text(f51, base + 0x20, 13).decode(), 'RIVAL')
        self.assertAlmostEqual(f32(f51, base + 0x2d), 88.25, places=4)
        self.assertEqual(dword(f51, base + 0x31), 20)
        second = base + REC
        self.assertEqual(text(f51, second + 0x00, 21).decode(), 'Driver')
        self.assertEqual(dword(f51, second + 0x31), 10)

    def test_58_record(self):
        """0xf58: +6 is the manager record, so name @0x27, country @0x3c, nickname @0x47, level @0x52,
        seconds @0x56, rank A @0x5a, rank B @0x5e (sections 3.6 / 9.4)."""
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 0, 0]
        self.db.rows_by_key[(102, self.season)] = ['RIVAL', 88.25, 0, 0]
        f58 = self.by_type(self.burst(), 0xf58)
        self.assertEqual(f58.payload[:4], bytes(4))
        self.assertEqual(text(f58, 0x27, 21).decode(), 'Driver')
        self.assertEqual(text(f58, 0x3c, 11).decode(), 'USA')
        self.assertEqual(text(f58, 0x47, 11).decode(), 'SPEED')
        self.assertEqual(dword(f58, 0x52), 10)
        self.assertAlmostEqual(f32(f58, 0x56), 91.5, places=4)
        self.assertEqual(dword(f58, 0x5a), 2)                             # our rank, best first
        self.assertEqual(dword(f58, 0x5e), 2)                             # the "world" rank (section 3.3)
        self.assertEqual(len(f58.payload), 0x63 - 2)

    def test_58_without_a_record(self):
        """No lap yet: 0.0 and rank 0 -> the client prints "--- Rank." (section 3.6)."""
        f58 = self.by_type(self.burst(), 0xf58)
        self.assertAlmostEqual(f32(f58, 0x56), 0.0)
        self.assertEqual((dword(f58, 0x5a), dword(f58, 0x5e)), (0, 0))
        self.assertEqual(text(f58, 0x27, 21).decode(), 'Driver')

    def test_57_rank1(self):
        """0xf57: serial @2 (0 offline), 0 @6, len @0xa >= 1, the name without NUL @0xe (section 3.5)."""
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 0, 0]
        f57 = self.by_type(self.burst(), 0xf57)
        self.assertEqual(dword(f57, 0x02), 0)                             # rank 1 is offline
        self.assertEqual(dword(f57, 0x06), 0)
        self.assertEqual(dword(f57, 0x0a), len('Driver'))
        self.assertEqual(len(f57.payload) + 2, 0xe + len('Driver'))
        self.assertEqual(f57.payload[0xc:], b'Driver')                    # +0xe is payload +0xc

    def test_57_rank1_serial_when_online(self):
        online = Session(cid=101, name='Driver', serial=0x321)
        login.sessions[7] = online
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 0, 0]
        f57 = self.by_type(self.burst(), 0xf57)
        self.assertEqual(dword(f57, 0x02), 0x321)

    # ---- the nickname (C>S 0xf55 -> S>C 0xf54) -------------------------------------------------------

    def test_54_size_and_accept(self):
        """0xf54 = 28 fixed: result @2, the 11-byte name @6, 11 unread bytes @0x11 (section 3.4)."""
        self.db.rows_by_key[(102, self.season)] = ['OTHER', None, 0, 0]
        frames = self.call(worldmatch.set_nickname_request, b'SPEED'.ljust(11, b'\0') + bytes(11))
        self.assertEqual(types(frames), [0xf54])
        f = frames[0]
        self.assertEqual(len(f.payload) + 2, 28)
        self.assertEqual(dword(f, 0x02), 1)
        self.assertEqual(text(f, 0x06, 11).decode(), 'SPEED')
        self.assertEqual(f.payload[0x11 - 2:], bytes(11))
        self.assertEqual(self.db.rows_by_key[(101, self.season)][0], 'SPEED')

    def test_54_validation(self):
        """12744's rule: alphanumeric, 2..10 characters; a rejection is result 0 (the client prints 12789)."""
        for name in (b'A', b'ABCDEFGHIJK', b'AB-C', b'AB C', b'A_B', b''):
            frames = self.call(worldmatch.set_nickname_request, name.ljust(11, b'\0') + bytes(11))
            f = frames[0]
            self.assertEqual(types(frames), [0xf54], name)
            self.assertEqual(dword(f, 0x02), 0, name)
            self.assertEqual(len(f.payload) + 2, 28)
            self.assertEqual(text(f, 0x06, 11), b'', name)
        for name in (b'AB', b'ABCDEFGHIJ', b'driver12'):
            frames = self.call(worldmatch.set_nickname_request, name.ljust(11, b'\0') + bytes(11))
            self.assertEqual(dword(frames[0], 0x02), 1, name)
        self.assertEqual(self.db.rows_by_key[(101, self.season)][0], 'driver12')

    def test_54_uniqueness_case_insensitive(self):
        """Unique per server + season, case-insensitive; the player's own row may keep its name."""
        self.db.rows_by_key[(102, self.season)] = ['SPEED', None, 0, 0]
        f = self.call(worldmatch.set_nickname_request, b'speed'.ljust(11, b'\0') + bytes(11))[0]
        self.assertEqual(dword(f, 0x02), 0)
        # another season's nickname does not clash
        self.db.rows_by_key[(102, self.season - 1)] = ['RIVAL', None, 0, 0]
        f = self.call(worldmatch.set_nickname_request, b'RIVAL'.ljust(11, b'\0') + bytes(11))[0]
        self.assertEqual(dword(f, 0x02), 1)
        # the same player setting the same name again is not a clash with itself
        f = self.call(worldmatch.set_nickname_request, b'RIVAL'.ljust(11, b'\0') + bytes(11))[0]
        self.assertEqual(dword(f, 0x02), 1)
        f = self.call(worldmatch.set_nickname_request, b'SPEED'.ljust(11, b'\0') + bytes(11))[0]
        self.assertEqual(dword(f, 0x02), 0)

    def test_56_answers_the_burst(self):
        """C>S 0xf56 (2) -> the same 0xf59 / 0xf5c / 0xf58 / 0xf51 burst (section 9.7)."""
        frames = self.call(worldmatch.nickname_done)
        self.assertEqual(types(frames), [0x3c0, 0xf59, 0xf5c, 0xf58, 0xf51])

    # ---- the daily tries (C>S 0xf5c / 0xf5d, S>C 0xf5c / 0xf5e) ---------------------------------------

    def test_5c_reports_today(self):
        """0xf5c = 6: the tries already used today (section 3.8 / 9.3)."""
        today = int(datetime.now().strftime('%Y%m%d'))
        self.db.rows_by_key[(101, self.season)] = ['', None, 3, today]
        f = self.call(worldmatch.daily_count)[0]
        self.assertEqual(types([f]), [0xf5c])
        self.assertEqual(len(f.payload) + 2, 6)
        self.assertEqual(dword(f, 0x02), 3)

    def test_5d_limit_then_5e(self):
        """Allowed tries are silent; over [worldmatch] daily_tries -> 0xf5e with 128 bytes (section 3.9)."""
        context.worldmatch['daily_tries'] = 2
        self.assertEqual(types(self.call(worldmatch.start_try)), [0x3c0])   # accepted: 0x3c0 only
        self.assertEqual(types(self.call(worldmatch.start_try)), [0x3c0])   # accepted: 0x3c0 only
        self.s.state.pop('wm_try')
        frames = self.call(worldmatch.start_try)
        self.assertEqual(types(frames), [0xf5e])
        f = frames[0]
        self.assertEqual(len(f.payload) + 2, 130)
        self.assertEqual(f.payload[:len(worldmatch.MAX_TRIES_TEXT)], worldmatch.MAX_TRIES_TEXT.encode('cp949'))
        self.assertEqual(f.payload[len(worldmatch.MAX_TRIES_TEXT):], bytes(128 - len(worldmatch.MAX_TRIES_TEXT)))
        self.assertEqual(self.db.rows_by_key[(101, self.season)][2], 2)             # the refused try did not count
        self.assertNotIn('wm_try', self.s.state)

    def test_5d_marks_the_try(self):
        frames = self.call(worldmatch.start_try)
        self.assertEqual(types(frames), [0x3c0])
        row = self.db.rows_by_key[(101, self.season)]
        self.assertEqual(row[2], 1)
        self.assertEqual(row[3], int(datetime.now().strftime('%Y%m%d')))
        self.assertEqual(self.s.state['wm_try'], worldmatch.season_now()[0].number)

    def test_new_day_resets_tries(self):
        """TRYDAY older than today -> 0 used, and the next try counts from 1 (section 9.3)."""
        yesterday = int((datetime.now() - timedelta(days=1)).strftime('%Y%m%d'))
        self.db.rows_by_key[(101, self.season)] = ['', None, 5, yesterday]
        f = self.call(worldmatch.daily_count)[0]
        self.assertEqual(dword(f, 0x02), 0)
        self.assertEqual(types(self.call(worldmatch.start_try)), [0x3c0])
        self.assertEqual(self.db.rows_by_key[(101, self.season)][2:], [1, int(datetime.now().strftime('%Y%m%d'))])

    # ---- the lap (record_lap, called from laptime.py) ------------------------------------------------

    def test_record_lap_keeps_the_best(self):
        """Only during a try; 0xf58 + 0xf51 after each record, the best (lowest) seconds kept."""
        season = self.season
        asyncio.run(worldmatch.record_lap(self.s, 90000))                 # no try running: nothing
        self.assertEqual(self.db.rows_by_key, {})

        self.s.state['wm_try'] = season
        self.assertEqual(self.record(0), [])                             # a zero lap is ignored
        self.assertEqual(self.db.rows_by_key, {})
        sent = self.record(90500)
        self.assertEqual(types(sent), [0xf58, 0xf51])
        self.assertAlmostEqual(self.db.rows_by_key[(101, season)][1], 90.5, places=4)
        self.assertAlmostEqual(f32(sent[0], 0x56), 90.5, places=4)
        self.assertAlmostEqual(f32(sent[1], 0x06 + 0x2d), 90.5, places=4)

        self.record(80000)                                               # better: replaces
        sent = self.record(95000)                                        # worse: kept
        self.assertAlmostEqual(self.db.rows_by_key[(101, season)][1], 80.0, places=4)
        self.assertAlmostEqual(f32(sent[0], 0x56), 80.0, places=4)

    def test_record_lap_needs_a_try(self):
        self.assertEqual(self.record(50000), [])
        self.assertEqual(self.db.rows_by_key, {})

    # ---- 0xf5a / 0xf5b -------------------------------------------------------------------------------

    def test_5a_answers_51(self):
        """C>S 0xf5a -> 0xf51 (section 9.10)."""
        self.db.rows_by_key[(101, self.season)] = ['SPEED', 91.5, 0, 0]
        frames = self.call(worldmatch.reward_request, struct.pack('<I', 2))
        self.assertEqual(types(frames), [0xf51])
        self.assertEqual(dword(frames[0], 0x02), 1)

    def test_5b_logs_only(self):
        """C>S 0xf5b (8): three u16 from the GM chat command, no reply (section 9.11)."""
        self.s.log = Mock()
        self.assertEqual(self.call(worldmatch.gm_command, struct.pack('<HHH', 1, 2, 3)), [])
        self.s.log.note.assert_called_once()

    # ---- off -----------------------------------------------------------------------------------------

    def test_disabled_sends_nothing(self):
        """context.worldmatch without enabled (the default {}) -> no answer, no query."""
        context.worldmatch = {}
        self.assertFalse(worldmatch.enabled())
        payloads = [(worldmatch.refresh, struct.pack('<I', 3)), (worldmatch.nickname_done, b''),
                    (worldmatch.set_nickname_request, b'SPEED'.ljust(11, b'\0') + bytes(11)),
                    (worldmatch.daily_count, bytes(4)), (worldmatch.start_try, b''),
                    (worldmatch.reward_request, struct.pack('<I', 2)),
                    (worldmatch.gm_command, struct.pack('<HHH', 1, 2, 3))]
        for handler, payload in payloads:
            self.assertEqual(self.call(handler, payload), [], handler.__name__)
        self.assertEqual(self.db.executed, [])

    def test_2011_gets_nothing(self):
        """The 2011 client has no 0xf51 - 0xf5e (its Lap Time is documented in laptime.py)."""
        version.configure({'version': '2011'})
        self.assertFalse(worldmatch.enabled())
        for handler in (worldmatch.refresh, worldmatch.nickname_done, worldmatch.set_nickname_request,
                        worldmatch.daily_count, worldmatch.start_try, worldmatch.reward_request,
                        worldmatch.gm_command):
            self.assertEqual(self.call(handler, b'SPEED'.ljust(11, b'\0') + bytes(11)), [])
        self.assertEqual(self.db.executed, [])

    def test_status_info(self):
        """0x3c0 = 0x2f8's body (112 + 44, handler 0x521cc0) + track, city, n = 0 -> 0xa4 bytes with the type."""
        season = worldmatch.Season(5, 3, 73, 5, None, None, None, None, '', '', '', '')
        p = SimpleNamespace(stats=lambda: SimpleNamespace(encode=lambda: bytes(range(112))))
        with patch('dcemu.native.game.records.enchant_bonus', return_value=b'\x07' * 44):
            f = worldmatch.build_status_info(p, season)
        self.assertEqual((f.type, len(f.payload) + 2), (0x3c0, 0xa4))
        self.assertEqual(f.payload[:112], bytes(range(112)))
        self.assertEqual(f.payload[112:156], b'\x07' * 44)
        self.assertEqual(struct.unpack_from('<HHH', f.payload, 156), (73, 4, 0))

if __name__ == '__main__':
    unittest.main()
