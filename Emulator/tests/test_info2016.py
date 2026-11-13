"""2016 player profile (0x294 -> 0x295) and crew messages: the layouts measured in the 2016 client."""
import asyncio
import datetime
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import crews, misc
from dcemu.native.game.records import Stats
from dcemu.wire import Frame
from tests.test_version import car, character


class Info2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def char_info(self, year):
        version.configure({'version': str(year)})
        c = character()
        c.team_id = 0
        p = SimpleNamespace(char=c, car=car(), stats=lambda: Stats())
        target = SimpleNamespace(state={'player': p, 'serial': 0x1234})
        with patch.object(misc, 'online', return_value=target), \
                patch.object(misc, 'send', lambda s, *f: self.sent.extend(f)):
            asyncio.run(misc.game_char_info(SimpleNamespace(), Frame(0x294, 'Driver'.encode('utf-16le').ljust(0x2e, b'\0'))))
        return self.sent[-1].payload

    def test_2016_profile_layout(self):
        out = self.char_info(2016)
        self.assertEqual(len(out) + 2, 0x499)                         # handler 0x529160 returns 0x499
        self.assertEqual(struct.unpack_from('<qq', out, 0x1e3), (-1, -1))   # no crew: team @0x1e3 (packet 0x1e5)
        self.assertEqual(struct.unpack_from('<II', out, 0x47b), (0x1234, 2))  # serial @0x47d, city after it
        self.assertEqual(struct.unpack_from('<H', out, 0x141 + 4)[0], 50)    # car record @0x143: its type

    def test_2011_profile_unchanged(self):
        out = self.char_info(2011)
        self.assertEqual(len(out), misc.CHAR_INFO_ACK)
        self.assertEqual(struct.unpack_from('<I', out, 0x334)[0], 0x1234)

    def test_team_record_sizes(self):
        for year, size in ((2011, 384), (2016, 664)):
            version.configure({'version': str(year)})
            self.assertEqual(len(crews.info_bytes(None)), size)
            t = dict(tid=5, mark=6, name='Crew', desc='d', url='u', created=1, closed=0, state='A', banish=0,
                     channels='', ranking=1, point=2, wins=3, count=4, exp=5, money=6, master=7, master_name='M')
            self.assertEqual(len(crews.info_bytes(t)), size)


class VisualItem2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_drift_item_record_sizes(self):
        from dcemu.native.game.records import VisualItem
        with patch.object(VisualItem, 'assist_slots', return_value=bytes(48)):
            for year, size in ((2011, 0x74), (2016, 0x78)):      # 0x4b1 handlers: 0x74 / 0x78 per record
                version.configure({'version': str(year)})
                self.assertEqual(len(VisualItem(1, 'x', 1, 0, 0, '', 0, 0, 0, 5).encode()), size)


class WhisperDeny2016Test(unittest.TestCase):
    def test_refusal_goes_to_the_whisperer_with_the_refusing_name(self):
        """C>S 0xfb3 (client 0x847000: wchar[20] the whisperer, 4 bytes) -> S>C 0xfb3 to the whisperer (handler
        0x521830: the name at @2, 0x2e bytes with the type)."""
        from dcemu.native.game import session as game_session
        me = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='Refuser'))}, log=Mock())
        other = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='Talker'))}, log=Mock())
        sent = []
        body = 'Talker'.encode('utf-16-le').ljust(40, b'\0') + bytes(4)
        with patch('dcemu.native.game.misc.online', side_effect=lambda n: other if n == 'Talker' else None), \
                patch.object(game_session, 'send', side_effect=lambda s, f: sent.append((s, f))):
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, body)))
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, 'Nobody'.encode('utf-16-le').ljust(44, b'\0'))))
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, b'short')))
        self.assertEqual(len(sent), 1)
        self.assertIs(sent[0][0], other)
        self.assertEqual(sent[0][1].type, 0xfb3)
        self.assertEqual(len(sent[0][1].payload) + 2, 0x2e)
        self.assertEqual(sent[0][1].payload[:40].decode('utf-16-le').rstrip('\0'), 'Refuser')


class CrewApply2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def run_apply(self, year):
        version.configure({'version': str(year)})
        c = SimpleNamespace(cid=7, name='Applicant', level=30)
        me = SimpleNamespace(state={'player': SimpleNamespace(char=c), 'serial': 5}, log=Mock())
        master = object()
        t = {'tid': 100001, 'name': 'Drifters', 'master': 1}
        sent = []
        store = AsyncMock()
        with patch.object(crews, 'apply_checks', AsyncMock(return_value=None)), \
                patch.object(crews, 'online_member', return_value=master), \
                patch.object(crews, 'store_request', store), \
                patch.object(crews, 'send', side_effect=lambda s, f: sent.append((s, f))):
            asyncio.run(crews.apply(me, t, b''))
        return me, master, sent, store

    def test_2016_applicant_gets_0x36e(self):
        """0x36e (client 0x546720, 0x5e bytes with the type): wchar[13] crew name @2, the 66-byte bind @0x1c."""
        me, master, sent, store = self.run_apply(2016)
        self.assertEqual([(s, f.type) for s, f in sent], [(master, 0x367), (me, 0x36e)])
        ack = sent[1][1].payload
        self.assertEqual(len(ack) + 2, 0x5e)
        self.assertEqual(ack[:26].decode('utf-16-le').rstrip('\0'), 'Drifters')
        self.assertEqual(ack[26:], sent[0][1].payload)

    def test_2016_request_is_queued(self):
        """The 2016 Acceptance page lists SKID_TEAMREQ_TB, so every request is stored even when the master is on."""
        me, master, sent, store = self.run_apply(2016)
        store.assert_awaited_once_with(100001, 7)

    def test_2011_unchanged(self):
        me, master, sent, store = self.run_apply(2011)
        self.assertEqual([(s, f.type) for s, f in sent], [(master, 0x367)])
        store.assert_not_awaited()


class CrewRankingTest(unittest.TestCase):
    """XiStrTeamInfo +0xeb: 24 bits of rank in a u32 whose top byte is the grade letter."""
    def tearDown(self):
        crews._rank_cache = (0, {})

    def test_rank_tier(self):
        self.assertEqual([crews.rank_tier(r) for r in (0, 1, 3, 4, 10, 11, 20, 21)],
                         [0, 3, 3, 2, 2, 1, 1, 0])

    def test_info_packs_the_grade_above_the_rank(self):
        t = dict(tid=1, mark=1, name='Crew', desc='', url='', created=0, closed=0, banish=0, channels='',
                 state='A', ranking=2, point=0, wins=0, count=1, exp=0, money=0, master=1, master_name='M')
        out = crews.info_bytes(t)
        self.assertEqual(struct.unpack_from('<I', out, 0xeb)[0], 2 | (3 << 24))

    def test_rankings_numbers_by_team_point_and_stores(self):
        db = Mock(server_id=100, rows=AsyncMock(return_value=[(11,), (22,)]), execute=AsyncMock())
        crews._rank_cache = (0, {})
        with patch.object(crews.context, 'db', db), patch.object(crews, 'now', return_value=1000):
            table = asyncio.run(crews.rankings())
        self.assertEqual(table, {11: 1, 22: 2})
        db.execute.assert_any_await(crews.RANK_SET_SQL, (2, 100, 22))

    def test_ranking_statements_are_distinct(self):
        """RANK_SQL is the member-rank UPDATE (4 parameters). The ordering SELECT needs its own name: an earlier
        run defined both as RANK_SQL, the UPDATE won and rankings() passed it 1 parameter (a 2016 crew create
        crashed on the server's own error)."""
        self.assertTrue(crews.RANK_ORDER_SQL.lstrip().upper().startswith('SELECT'))
        self.assertEqual(crews.RANK_ORDER_SQL.count('%s'), 1)
        self.assertNotEqual(crews.RANK_ORDER_SQL, crews.RANK_SQL)


class AcceptancePage2016Test(unittest.TestCase):
    """The crew Acceptance page: 0x357 act 0x3f4 asks, 0x358 act 0x3f4 answers, 0x36f accepts / refuses."""
    CREW = {'tid': 100001, 'name': 'Drifters', 'master': 1}

    def tearDown(self):
        version.configure({'version': '2011'})

    def test_act_0x3f4_answers_the_queue(self):
        """Client: 0x5c2f2d asks act 0x3f4; its answer 0x547060 -> 0x68ae50 is the member list's handler, sub-view 2."""
        version.configure({'version': '2016'})
        db = Mock(server_id=100, execute=AsyncMock(),
                  rows=AsyncMock(return_value=[(7, 'Applicant', 0, 30, datetime.datetime(2024, 1, 2, 3, 4, 5), 5, 0)]))
        sent = []
        with patch.object(crews.context, 'db', db), \
                patch.object(crews, 'team', AsyncMock(return_value=self.CREW)), \
                patch.object(crews, 'online_member', return_value=None), \
                patch.object(crews, 'send', side_effect=lambda s, *fs: sent.extend(fs)):
            asyncio.run(crews.team_members(SimpleNamespace(state={}, log=Mock()),
                                           Frame(0x357, struct.pack('<iqi', crews.ACCEPT_ACT, 100001, 0))))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].type, 0x358)
        act, tid, channel, master, n, page = struct.unpack_from('<iqiqHH', sent[0].payload)
        self.assertEqual((act, tid, channel, master, n, page), (0x3f4, 100001, 0, 1, 1, 0))
        self.assertEqual(struct.unpack_from('<q', sent[0].payload, 0x1c)[0], 7)     # the applicant's cid (entry @0x1e, type 2)
        db.rows.assert_awaited()

    def answer(self, result):
        version.configure({'version': '2016'})
        me = SimpleNamespace(char=SimpleNamespace(cid=1, name='Master', team_id=100001, team_rank=crews.MASTER))
        session = SimpleNamespace(state={'player': me}, log=Mock())
        db = Mock(server_id=100, row=AsyncMock(return_value=('Applicant',)))
        self.drop, self.ok = AsyncMock(), AsyncMock()
        with patch.object(crews, 'master_check', AsyncMock(return_value=(me, self.CREW))), \
                patch.object(crews, 'has_request', AsyncMock(return_value=True)), \
                patch.object(crews, 'drop_request', self.drop), \
                patch.object(crews, 'approve', self.ok), \
                patch.object(crews.context, 'db', db):
            asyncio.run(crews.team_apply_answer(session, Frame(0x36f, struct.pack('<qb', 7, result))))
        return session, me

    def test_accept_answer_joins(self):
        """0x36f: i64 applicant @2 + u8 result @0xa (sender 0x868a00, buttons 0x1d4c40 / 0x1d4c41 at 0x5902b8)."""
        session, me = self.answer(1)
        self.drop.assert_awaited_once_with(100001, 7)
        self.ok.assert_awaited_once_with(session, me, self.CREW, 7, 'Applicant')

    def test_refuse_answer_only_drops(self):
        session, me = self.answer(0)
        self.drop.assert_awaited_once_with(100001, 7)
        self.ok.assert_not_awaited()

    def test_2011_ignores_0x36f(self):
        """The 2011 client has no 0x36f sender."""
        version.configure({'version': '2011'})
        drop = AsyncMock()
        with patch.object(crews, 'drop_request', drop):
            asyncio.run(crews.team_apply_answer(SimpleNamespace(state={}, log=Mock()),
                                                Frame(0x36f, struct.pack('<qb', 7, 1))))
        drop.assert_not_awaited()


class OfflineCharInfo2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_by_name_and_by_cid(self):
        """0x29e (name @2 wchar[21], i64 cid @0x2c, u32 mode @0x34) -> 0x29f: XiCharInfo 0x141 @2, the mode @0x143."""
        version.configure({'version': '2016'})
        c = character()
        p = SimpleNamespace(char=c)
        sent = []
        db = SimpleNamespace(server_id=1, row=AsyncMock(return_value=(c.name,)))
        saved = context.__dict__.get('db')
        context.db = db
        try:
            with patch.object(misc, 'online', return_value=None), \
                    patch.object(misc.player, 'load', AsyncMock(return_value=p)) as load, \
                    patch.object(misc, 'send', side_effect=lambda s, f: sent.append(f)):
                body = c.name.encode('utf-16-le').ljust(0x2a, b'\0') + struct.pack('<qI', 0, 2)
                asyncio.run(misc.game_char_info_offline(SimpleNamespace(), Frame(0x29e, body)))
                body = bytes(0x2a) + struct.pack('<qI', 1234, 3)
                asyncio.run(misc.game_char_info_offline(SimpleNamespace(), Frame(0x29e, body)))
        finally:
            context.db = saved
        self.assertEqual([f.type for f in sent], [0x29f, 0x29f])
        for f, mode in zip(sent, (2, 3)):
            self.assertEqual(len(f.payload) + 2, 0x147)
            self.assertEqual(struct.unpack_from('<I', f.payload, 0x141)[0], mode)
        self.assertEqual(load.await_args_list[1].args[0], c.name)
        self.assertEqual(db.row.await_args.args[1], (1, 1234))
