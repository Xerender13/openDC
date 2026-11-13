"""2016 crew level / research (crewlevel.py): tables, record fields and message layouts, with a fake database."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import crewlevel, crews


class FakeDb:
    """Just enough SQL for crewlevel: dict-backed answers by statement."""
    def __init__(self):
        self.server_id = 1
        self.team = {}            # tid -> [exp, points, news]
        self.research = {}        # (tid, rid) -> end
        self.contrib = {}         # (cid, tid) -> [exp, spent]
        self.events = []

    async def execute(self, sql, p=()):
        if 'SET RPOINT=RPOINT-' in sql:
            t = self.team[p[2]]
            if t[1] >= p[3]:
                t[1] -= p[0]
                return 1
            return 0
        if sql.startswith('CREATE TABLE'):
            return
        if 'INSERT INTO SKID_TEAM2016_TB' in sql:
            self.team.setdefault(p[1], [0, 0, ''])
        elif sql.startswith('UPDATE SKID_TEAM2016_TB SET TEAMEXP'):
            self.team[p[3]][0] += p[0]
            self.team[p[3]][1] += p[1]
        elif sql.startswith('UPDATE SKID_TEAM2016_TB SET NEWS'):
            self.team[p[2]][2] = p[0]
        elif 'SKID_TEAMCONTRIB_TB' in sql:
            row = self.contrib.setdefault((p[1], p[2]), [0, 0])
            row[0] += p[3]
            row[1] += p[4]
        elif sql.startswith('INSERT INTO SKID_TEAMRESEARCH_TB'):
            self.research[(p[1], p[2])] = p[3]
        elif sql.startswith('INSERT INTO SKID_TEAMEVENT_TB'):
            self.events.append((p[1], p[2], p[3], p[4]))

    async def row(self, sql, p=()):
        if sql.startswith('SELECT TEAMEXP, RPOINT'):
            t = self.team.get(p[1])
            return tuple(t) if t else None
        if sql.startswith('SELECT TEAMEXP, SPENT'):
            c = self.contrib.get((p[1], p[2]))
            return tuple(c) if c else None
        return None

    async def rows(self, sql, p=()):
        if 'SKID_TEAMRESEARCH_TB' in sql:
            return [(rid, end) for (tid, rid), end in self.research.items() if tid == p[1]]
        if 'SKID_TEAMEVENT_TB' in sql:
            return [(text, when) for tid, board, text, when in self.events if tid == p[1] and board == p[2]]
        return []


class CrewLevelTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(root='server_data_2016')
        context.db = self.db = FakeDb()
        crewlevel._ready = False
        crewlevel._research = crewlevel._levels = None
        self.sent = []
        self.c = SimpleNamespace(cid=5, name='Master', team_id=100001, team_rank=crews.MASTER)
        self.s = SimpleNamespace(state={'player': SimpleNamespace(char=self.c)}, log=Mock())

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        crewlevel._research = crewlevel._levels = None
        version.configure({'version': '2011'})

    def call(self, fn, payload):
        with patch.object(crewlevel, 'send', side_effect=lambda to, f: self.sent.append(f)), \
                patch.object(crewlevel, 'refresh_crew', AsyncMock()), \
                patch('dcemu.native.game.crews.crew_sessions', return_value=[self.s]):
            asyncio.run(fn(self.s, SimpleNamespace(payload=payload)))

    def test_tables(self):
        self.assertEqual(len(crewlevel.research_table()), 26)
        r = crewlevel.research_table()['tr_passive_a_00007']
        self.assertEqual((r['level'], r['point'], r['tech'], r['seconds'], r['price']),
                         (2, 200000, 'tr_passive_a_00006', 172800, 100))
        self.assertEqual(crewlevel.level_of(49999), 0)
        self.assertEqual(crewlevel.level_of(50000), 1)
        self.assertEqual(crewlevel.level_of(252000), 3)

    def test_record_fields(self):
        t = dict(tid=1, mark=0, name='C', desc='', url='', created=0, closed=0, banish=0, channels='', state='A',
                 ranking=0, point=0, wins=0, count=1, exp=0, money=0, master=5, master_name='Master',
                 x2016=(260000, 1234, 'hello\nworld'))
        out = crews.info_bytes(t)
        self.assertEqual(len(out), 664)
        self.assertTrue(out[0x180:].startswith(b'hello\nworld\0'))
        self.assertEqual(struct.unpack_from('<qIq', out, 0x284), (260000, 3, 1234))

    def test_gain_is_one_percent(self):
        asyncio.run(crewlevel.gain(self.c, 1234))
        self.assertEqual(self.db.team[100001][:2], [12, 12])
        self.assertEqual(self.db.contrib[(5, 100001)], [12, 0])

    def test_research_list_layout(self):
        self.call(crewlevel.get_research, struct.pack('<I', 0))
        f = self.sent[-1]
        n, = struct.unpack_from('<H', f.payload, 4)
        self.assertEqual(n, 26)
        self.assertEqual(len(f.payload) + 2, (n - 1) * 0x48 + 0x50)      # the handler's size formula
        self.assertEqual(f.payload[6:6 + 64].decode('utf-16-le').rstrip('\0'), 'tr_passive_a_00006')

    def test_start_research_rules(self):
        rid = 'tr_passive_a_00006'.encode('utf-16-le').ljust(64, b'\0')
        self.db.team[100001] = [0, 0, '']
        with patch('dcemu.native.admin.message') as msg:
            self.call(crewlevel.start_research, struct.pack('<I', 0) + rid)       # level 0, no points
            self.assertIn('Team Level 1', msg.call_args.args[1])
            self.db.team[100001] = [60000, 50, '']
            self.call(crewlevel.start_research, struct.pack('<I', 0) + rid)
            self.assertIn('Research Points', msg.call_args.args[1])
            self.db.team[100001] = [60000, 100000, '']
            self.call(crewlevel.start_research, struct.pack('<I', 0) + rid)
        self.assertIn((100001, 'tr_passive_a_00006'), self.db.research)
        self.assertEqual(self.db.team[100001][1], 0)
        self.assertEqual(self.sent[-1].type, 0xce9)

    def test_events_board_layout(self):
        self.db.events = [(100001, 0x408, f'news {i}', 1700000000 + i) for i in range(12)]
        self.call(crewlevel.get_events, struct.pack('<4I', 1, 0x408, 1, 10))
        f = self.sent[-1]
        sel, board, page, rows, total, n = struct.unpack_from('<IIIIiH', f.payload)
        self.assertEqual((sel, board, page, rows, total, n), (1, 0x408, 1, 10, 12, 2))
        self.assertEqual(len(f.payload) + 2, (n - 1) * 0x14a + 0x162)
        e = f.payload[0x16:0x16 + 0x14a]
        self.assertEqual(e[0x35:0x35 + 14].decode('utf-16-le'), 'news 10')
        self.assertEqual(struct.unpack_from('<I', e, 0x146)[0], 1700000010)

    def test_2011_untouched(self):
        version.configure({'version': '2011'})
        asyncio.run(crewlevel.gain(self.c, 100000))
        self.assertEqual(self.db.team, {})


class CrewWindow2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def test_0xce4_creates_with_the_name(self):
        """0xce4 (0x34): i64 crew @2, i64 @0xa, wchar[17] name @0x12 -> crews.create (the 0x34a rules)."""
        p = SimpleNamespace(char=SimpleNamespace(name='M'))
        s = SimpleNamespace(state={'player': p}, log=Mock())
        body = struct.pack('<qq', -1, 5) + 'Drifters'.encode('utf-16-le').ljust(34, b'\0')
        self.assertEqual(len(body) + 2, 0x34)
        with patch.object(crews, 'create', AsyncMock()) as create:
            asyncio.run(crews.create_team_2016(s, SimpleNamespace(payload=body)))
        create.assert_awaited_once()
        self.assertEqual(create.await_args.args[2:], ('Drifters', '', '', 1))

    def test_member_list_pushed_only_to_the_list_the_client_asked_for(self):
        s = SimpleNamespace(state={})
        with patch.object(crews, 'member_frames', AsyncMock(return_value=[])) as frames, \
                patch.object(crews, 'send'):
            asyncio.run(crews.push_members(s, {'tid': 1}))
            frames.assert_not_awaited()                           # 2016, nothing asked: no unsolicited 0x358
            s.state['crew_list_act'] = 0x407
            asyncio.run(crews.push_members(s, {'tid': 1}))
            self.assertEqual(frames.await_args.args[1], 0x407)
            version.configure({'version': '2011'})
            asyncio.run(crews.push_members(SimpleNamespace(state={}), {'tid': 1}))
            self.assertEqual(frames.await_args.args[1], crews.ACT_LIST)

    def test_mito_donation(self):
        """0xceb payload: u32 always 0, then kind @4 (1 = Mito), amount @8."""
        context.data = SimpleNamespace(root='server_data_2016')
        context.db = db = FakeDb()
        crewlevel._ready = False
        c = SimpleNamespace(cid=5, name='M', team_id=7, team_rank=crews.MEMBER, mito=10000)
        s = SimpleNamespace(state={'player': SimpleNamespace(char=c)}, log=Mock())

        async def take(ch, delta):
            ch.mito += delta
            return True
        with patch('dcemu.native.game.items.add_money', take), patch.object(crewlevel, 'send'), \
                patch('dcemu.native.game.login.stat_frames', return_value=[]), \
                patch.object(crewlevel, 'refresh_crew', AsyncMock()):
            asyncio.run(crewlevel.donate(s, SimpleNamespace(payload=struct.pack('<4I', 0, 1, 2550, 0))))
        self.assertEqual(c.mito, 10000 - 2500)
        self.assertEqual(db.team[7][1], 25)

    def test_gold_mark_donation(self):
        """kind 0 = OMD Gold Mark: the account's G Coin, 1 research point each (12838). The in-game donation that
        showed the layout was kind 0 / amount 2."""
        context.data = SimpleNamespace(root='server_data_2016')
        context.db = db = FakeDb()
        crewlevel._ready = False
        db.team[7] = [0, 0, '']
        c = SimpleNamespace(cid=5, name='M', team_id=7, team_rank=crews.MEMBER, mito=0, member='acc')
        s = SimpleNamespace(state={'player': SimpleNamespace(char=c)}, log=Mock())
        spent = []

        async def take(name, amount):
            spent.append((name, amount))
            return 'acc', 0
        with patch.object(db, 'row', AsyncMock(return_value=(30,))), \
                patch('dcemu.native.admin.add_coin', take), \
                patch.object(crewlevel, 'send'), patch.object(crewlevel, 'refresh_crew', AsyncMock()):
            asyncio.run(crewlevel.donate(s, SimpleNamespace(payload=struct.pack('<4I', 0, 0, 30, 0))))
        self.assertEqual(spent, [('M', -30)])
        self.assertEqual(db.team[7][1], 30)
