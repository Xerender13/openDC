"""Neo City (neocity.py): the HP sync (0xf4d -> 0xf4e, base ^ hp; docs/NEOCITY.md), the client's chapter /
quest tables and the stage 2 chapter flow (docs/neo_work/NEO_PROTOCOL_A.md)."""
import asyncio
import contextlib
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import neocity
from dcemu.wire import Frame


class NeoCityHpTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.db = SimpleNamespace(server_id=2016)
        neocity._hp.clear()
        self.p = SimpleNamespace(char=SimpleNamespace(cid=77))
        self.s = SimpleNamespace(state={'player': self.p}, log=Mock())

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._hp.clear()
        version.configure({'version': '2011'})

    def poll(self, base=0x111a):
        sent = []
        with patch.object(neocity, 'send', side_effect=lambda s, f: sent.append(f)):
            asyncio.run(neocity.hp_sync(self.s, Frame(0xf4d, struct.pack('<I', base))))
        return sent

    def test_no_hp_before_a_report(self):
        self.assertIsNone(neocity.hp_of(self.s))

    def test_report_is_kept_and_echoed(self):
        """0xf4d carries the car's HP (getter 0x760900); 0xf4e stores the plain value (0x53e630 -> 0x760910)."""
        sent = self.poll(0x111a)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].type, 0xf4e)
        self.assertEqual(struct.unpack_from('<I', sent[0].payload)[0], 0x111a)
        self.assertEqual(neocity.hp_of(self.s), 0x111a)

    def test_out_of_range_report(self):
        """0 is ignored; a strong car's HP above the client's 20000 bound is answered with 0 (its own HP) (45936 entered
        Neo City destroyed when it got no answer, user 2026-11-14)."""
        self.assertEqual(self.poll(0), [])
        self.assertIsNone(neocity.hp_of(self.s))
        sent = self.poll(45936)
        self.assertEqual(struct.unpack_from('<I', sent[0].payload)[0], 0)        # 0 -> -1 = the car's own HP
        self.assertEqual(neocity.hp_of(self.s), neocity.MAX_HP)

    def test_damage_and_heal_clamp(self):
        self.assertIsNone(neocity.damage(self.s, 5))
        self.poll(5000)
        self.assertEqual(neocity.damage(self.s, 1000), 4000)
        self.assertEqual(neocity.damage(self.s, 10 ** 9), 0)
        self.assertEqual(neocity.heal(self.s, 10 ** 9), neocity.MAX_HP)

    def test_2011_ignores_it(self):
        """The 2011 client has no 0xf4d sender."""
        version.configure({'version': '2011'})
        self.assertEqual(self.poll(), [])


class NeoCityFlagsTest(unittest.TestCase):
    """Stage 1: the region is gated by content flags the 2008 Contents.ini has no entry for."""
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_flags_exist_and_pack(self):
        version.configure({'version': '2016'})
        for name in ('City.NeoCity', 'City.NeoOros', 'City.Cras', 'City.NeoCras', 'City.NeoKoinonia',
                     'City.NeoMoonPalace'):
            self.assertIn(name, version.flag_table(), name)
        out = version.pack_flags({'City.NeoCity': 1, 'City.NeoOros': 1})
        value, = struct.unpack_from('<I', out, 0x14)     # flags_2016.tsv: City.NeoCity 0x14 bit 21
        self.assertTrue(value & (1 << 21))
        self.assertTrue(value & (1 << 22))

    def test_2011_flag_offsets_differ(self):
        """The 2011 client keeps the same names at another offset (0x10), so the tables must not be mixed."""
        version.configure({'version': '2011'})
        self.assertEqual(version.flag_table()['City.NeoCity'][:2], (0x10, 21))
        version.configure({'version': '2016'})
        self.assertEqual(version.flag_table()['City.NeoCity'][:2], (0x14, 21))


class FakeDb:
    """The SKID_QUEST_TB calls only (rows: no chapter cleared yet, or the rows given; update_or_insert: as the
    real one)."""
    server_id = 2016

    def __init__(self, rows=()):
        self.answer = list(rows)
        self.rows_calls = []
        self.saved = []                 # (update params, insert params)

    async def execute(self, sql, params=()):
        return True

    async def row(self, sql, params=()):
        return None

    async def rows(self, sql, params=()):
        self.rows_calls.append((sql, params))
        return self.answer

    async def update_or_insert(self, update_sql, update_params, insert_sql, insert_params):
        self.saved.append((update_params, insert_params))
        return True


class NeoCityTablesTest(unittest.TestCase):
    """NC_chapter.xlt / NC_quest.xlt as the client loads them: chapter key = data-row order, quest index =
    the quest's order among its chapter's rows, the chapter reward text."""
    def setUp(self):
        self.saved = context.__dict__.copy()
        context.data = SimpleNamespace(root='server_data_2016')
        neocity._chapters = neocity._quests = None

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._chapters = neocity._quests = None

    def test_chapter_keys(self):
        table = neocity.chapters()
        self.assertEqual(len(table), 8)
        self.assertEqual((table[0]['id'], table[0]['key']), ('c_0000', 0))
        self.assertEqual((table[1]['id'], table[1]['key']), ('c_0008', 1))     # c_0000 -> 0, c_0008 -> 1, ...
        self.assertEqual(table[2]['id'], 'c_0005')
        self.assertEqual((table[0]['city'], table[0]['level_low'], table[0]['level_high']), ('NeoOros', 40, 999))
        self.assertEqual(table[0]['member_check'], 1)
        self.assertEqual(table[1]['member_check'], 4)
        self.assertIsNone(neocity.chapter_by_key(99))

    def test_quest_indexes(self):
        chapter = neocity.chapter_by_key(2)
        self.assertEqual(chapter['id'], 'c_0005')
        self.assertEqual([q['id'] for q in neocity.quests_of(chapter)],
                         ['q_00023', 'q_00024', 'q_00025', 'q_00026', 'q_00027'])
        self.assertEqual((neocity.quests_of(chapter)[2]['exp'], neocity.quests_of(chapter)[2]['mito']),
                         (10000, 10000))
        self.assertEqual([q['id'] for q in neocity.quests_of(neocity.chapter_by_key(0))],
                         ['q_00052', 'q_00053', 'q_00054'])
        self.assertEqual(neocity.quests_of(neocity.chapter_by_key(0))[1]['items'],
                         ['neo_wp_c_21101', 'neo_wp_a_22101', 'neo_wp_w_23101'])

    def test_chapter_reward(self):
        self.assertEqual((neocity.chapter_by_key(0)['exp'], neocity.chapter_by_key(0)['mito']), (5000, 5000))
        self.assertEqual((neocity.chapter_by_key(1)['exp'], neocity.chapter_by_key(1)['mito']), (20000, 20000))


class NeoCityFlowTest(unittest.TestCase):
    """Stage 2: 0xe88 -> 0xe89 (solo), 0xed8 -> 0xed9, 0xedc -> 0xedd, 0xede -> 0xedf, 0xeda -> 0xedb."""
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(root='server_data_2016')
        context.db = self.db = FakeDb()
        neocity._chapters = neocity._quests = None
        neocity.runs.clear()
        neocity._hp.clear()
        self.c = SimpleNamespace(cid=7, name='Driver', level=50, city=1, exp=1000, exp_next=2000,
                                 exp_base=1000, mito=500)
        self.p = SimpleNamespace(char=self.c, items=[])
        self.s = SimpleNamespace(id=11, state={'player': self.p, 'serial': 1234, 'channel': 0}, log=Mock())
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._chapters = neocity._quests = None
        neocity.runs.clear()
        neocity._hp.clear()
        version.configure({'version': '2011'})

    def handle(self, fn, frame, patches=()):
        self.sent = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(neocity, 'send',
                                             side_effect=lambda to, *fs: self.sent.extend(fs)))
            for p in patches:
                stack.enter_context(p)
            asyncio.run(fn(self.s, frame))
        return self.sent

    def suggest(self, key=0):
        return Frame(0xe88, struct.pack('<6I', 1234, 1000, 0, key, 0, 1))

    def enter(self, key=0):
        frames = self.handle(neocity.suggest, self.suggest(key))
        self.assertEqual([f.type for f in frames], [0xe89])
        return self.s.state['neo_run']

    def reward_patches(self):
        self.add_exp, self.add_money = AsyncMock(return_value=False), AsyncMock(return_value=True)
        self.play_mode = AsyncMock()
        return [patch.object(neocity, 'add_exp', self.add_exp),
                patch.object(neocity, 'add_money', self.add_money),
                patch.object(neocity, 'play_mode', self.play_mode),
                patch.object(neocity, 'stat_frames', lambda p: []),
                patch('dcemu.native.game.rewards.give',
                      AsyncMock(return_value=(SimpleNamespace(items=[]), [])))]

    def test_solo_suggest_loads(self):
        """0x53e400: u32 0, the map selector, the chapter key, 0, 12 zero bytes; the kept HP is forgotten."""
        r = self.enter(0)
        frame = self.sent[0]
        self.assertEqual(len(frame.payload) + 2, 30)
        zero, map_id, key, run_id = struct.unpack_from('<4I', frame.payload)
        self.assertEqual((zero, map_id, key), (0, 6, 0))            # NeoOros = 6 (jump table 0x788a2c)
        self.assertEqual(frame.payload[16:], bytes(12))
        self.assertEqual(run_id, neocity.START_ENTRY)                 # activity +0x34 index (1), not the run id
        self.assertIs(neocity.runs[r.id], r)
        self.assertIsNone(neocity.hp_of(self.s))                      # the new car reports its HP
        self.assertEqual(neocity.MAPS, {'NeoOros': 6, 'NeoCras': 7, 'NeoKoinonia': 8, 'NeoMoonPalace': 9})

    def test_level_range_refused(self):
        self.c.level = 39                                            # c_0000 needs 40
        self.assertEqual(self.handle(neocity.suggest, self.suggest(0)), [])
        self.assertNotIn('neo_run', self.s.state)
        self.assertEqual(self.handle(neocity.suggest, self.suggest(99)), [])       # no such chapter key

    def test_chapter_start_ack(self):
        r = self.enter()
        frames = self.handle(neocity.chapter_start, Frame(0xed8, struct.pack('<II', 0, 0)),
                             [patch.object(neocity, 'stat_frames', lambda p: [])])
        self.assertEqual([f.type for f in frames], [0xed9])               # "Ready Quest"
        self.assertEqual(len(frames[0].payload) + 2, 18)
        self.assertEqual(struct.unpack_from('<4I', frames[0].payload), (0, 0, 0, neocity.START_ENTRY))
        self.assertIsNone(r.quest)
        frames = self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 3)))   # start zone
        # first the start row's dialogue: 0xeea result 3 (0x5340a2 -> the script runner), the quest still waits
        self.assertEqual([(f.type, struct.unpack('<4I', f.payload)) for f in frames], [(0xeea, (0, 0, 0, 3))])
        self.assertIsNone(r.quest)
        frames = self.handle(neocity.quest_start, Frame(0xedc, struct.pack('<II', 0, 0)))   # after the dialogue
        self.assertEqual((frames[0].type, struct.unpack('<II', frames[0].payload)), (0xedd, (0, 0)))
        # then the quest's enemies: one 0xc7 per Q_START row of neo_oros_ch1_q1 (NC_object 135..140)
        self.assertEqual([(f.type, struct.unpack_from('<I', f.payload, 4)[0]) for f in frames[1:]],
                         [(0xc7, n) for n in (4, 4, 4, 4, 6, 3)])
        rec = frames[1].payload[0xa:0x4a]
        self.assertEqual(struct.unpack_from('<HHHH', rec, 0)[0:2], (1, 0))          # NEO_HUB, position 0
        self.assertEqual(struct.unpack_from('<HH', rec, 8), (1234, neocity.ENEMY_FIRST))   # owner, enemy number
        keys = {struct.unpack_from('<I', f.payload, 0xa + 0x40 * i + 8)[0]
                for f in frames[1:] for i in range(struct.unpack_from('<I', f.payload, 4)[0])}
        self.assertEqual(len(keys), 25)                                           # one actor key per enemy
        self.assertIn(struct.unpack_from('<I', rec, 0xe)[0], (100466, 100560, 100561))   # NC_HuvRand group 1084
        self.assertEqual(struct.unpack_from('<IH', rec, 0x12), (1084, 135))
        self.assertEqual(struct.unpack_from('<4f', rec, 0x20)[:2], struct.unpack('<2f', struct.pack('<2f', 1719.6, 5623.5)))
        self.assertEqual(struct.unpack_from('<IIIH', rec, 0x30), (0, 0, 0, 0))     # key 0, quest 0, active
        self.assertEqual(len(r.enemies), 25)
        self.assertEqual(r.quest, 0)
        self.assertEqual(self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 3))), [])
        self.assertEqual(self.handle(neocity.quest_start, Frame(0xedc, struct.pack('<II', 0, 0))), [])  # no 2nd spawn

    def test_next_quest_removes_the_old_enemies(self):
        """Q2's start first kills Q1's 25 enemies (0xce, key +2/+4, Huv Param @0x34, no killer), then spawns."""
        r = self.enter()
        self.handle(neocity.quest_start, Frame(0xedc, struct.pack('<II', 0, 0)))
        old = [struct.unpack_from('<HH', rec, 8) for rec in r.enemies]
        huvs = [struct.unpack_from('<I', rec, 0xe)[0] for rec in r.enemies]
        r.quest = None
        frames = self.handle(neocity.quest_start, Frame(0xedc, struct.pack('<II', 0, 1)))
        kills = [f for f in frames if f.type == 0xce]
        self.assertEqual(len(kills), 25)
        self.assertEqual([struct.unpack_from('<HH', f.payload) for f in kills], old)
        self.assertEqual(len(kills[0].payload), 0x3e)
        self.assertEqual([struct.unpack_from('<I', f.payload, 0x34)[0] for f in kills], huvs)
        self.assertTrue(set(old) <= r.killed)                                 # a returning report pays nothing
        self.assertEqual(sum(1 for f in frames if f.type == 0xc7), 6)          # neo_oros_ch1_q2's enemy rows
        self.assertEqual(len(r.enemies), 28)
        self.assertFalse(set(old) & {struct.unpack_from('<HH', rec, 8) for rec in r.enemies})

    def test_start_zone_again_starts_the_quest(self):
        """Without the client's 0xedc, entering the start zone a second time starts the quest."""
        r = self.enter()
        self.handle(neocity.chapter_start, Frame(0xed8, struct.pack('<II', 0, 0)),
                    [patch.object(neocity, 'stat_frames', lambda p: [])])
        self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 3)))
        frames = self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 3)))
        self.assertEqual(frames[0].type, 0xedd)
        self.assertEqual(r.quest, 0)
        self.assertEqual(r.quest, 0)
        self.assertEqual(self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 3))), [])

    def test_quest_start_ack(self):
        r = self.enter(key=2)                                        # c_0005
        frames = self.handle(neocity.quest_start, Frame(0xedc, struct.pack('<II', 2, 2)))
        self.assertEqual(frames[0].type, 0xedd)
        self.assertEqual({f.type for f in frames[1:]}, {0xc7} if frames[1:] else set())   # the quest's enemies
        self.assertEqual(len(frames[0].payload) + 2, 10)
        self.assertEqual(struct.unpack_from('<II', frames[0].payload), (2, 2))
        self.assertEqual(r.quest, 2)

    def test_quest_reward(self):
        """q_00025 of c_0005: 10000 exp / 10000 Mito; 0xedf is 58 bytes (u64 counters, as pack_exp)."""
        r = self.enter(key=2)
        patches = self.reward_patches()
        frames = self.handle(neocity.quest_reward, Frame(0xede, struct.pack('<IIf', 2, 2, 12.5)), patches)
        self.assertEqual([f.type for f in frames], [0xedf])
        frame = frames[0]
        self.assertEqual(len(frame.payload) + 2, 58)
        key, quest, exp, money, exp_now, exp_next, exp_base, level, count, i0, i1, i2 = \
            struct.unpack_from('<4I3QHH3I', frame.payload)
        self.assertEqual((key, quest, exp, money), (2, 2, 10000, 10000))
        self.assertEqual((exp_now, exp_next, exp_base, level), (1000, 2000, 1000, 50))
        self.assertEqual((count, i0, i1, i2), (0, 0, 0, 0))
        self.add_exp.assert_awaited_once()
        self.add_money.assert_awaited_once()
        self.play_mode.assert_awaited_once_with(self.c, 'NEOCITY', exp=10000, money=10000)
        # a second 0xede for the same quest gives nothing more
        frames = self.handle(neocity.quest_reward, Frame(0xede, struct.pack('<IIf', 2, 2, 13.0)), patches)
        self.assertEqual(struct.unpack_from('<4I', frames[0].payload), (2, 2, 0, 0))
        self.add_exp.assert_awaited_once()
        self.assertIn(2, r.rewarded)

    def test_chapter_complete(self):
        """0xeda: 'neo_c_0000' STATE 2 FAILNUM 1, the chapter's 5000 exp / 5000 Mito, 0xedb 203 bytes, once."""
        r = self.enter(key=0)
        patches = self.reward_patches()
        patches.append(patch.object(neocity, 'roll_item', return_value=None))
        r.failed, r.deaths = 1, 0
        r.kills[neocity.serial_of(self.s)] = {'HUV': 15, 'HUB': 4}
        frames = self.handle(neocity.chapter_complete, Frame(0xeda, struct.pack('<II', 0, r.id)), patches)
        r.pick_task.cancel()
        self.assertEqual([f.type for f in frames], [0x7d1, 0x7d2, 0xedb, 0xee9])
        frame = frames[2]
        self.assertEqual(len(frame.payload) + 2, 203)                  # one row: n * 0x10 + 0xbb (0x52e969)
        key, n, prev, seconds, failed, deaths, grade = struct.unpack_from('<IIBIIII', frame.payload)
        self.assertEqual((key, n, prev, failed, deaths, grade), (0, 1, 0, 1, 0, 1))
        row = struct.unpack_from('<7I', frame.payload, 0x19)
        self.assertEqual(row, (neocity.serial_of(self.s), self.c.level, 15, 4, 0, 5000, 5000))
        self.assertEqual(len(frames[3].payload) + 2, 262)              # 0xee9: u32 0 + 16 x 16 (0x526d80)
        update, insert = self.db.saved[0]
        self.assertEqual(update, (2, 1, 2016, 7, 'neo_c_0000'))       # STATE 2, FAILNUM 1
        self.assertEqual(insert[3:6], ('neo_c_0000', 2, 1))
        self.add_exp.assert_awaited_once()
        self.add_money.assert_awaited_once()
        self.play_mode.assert_awaited_once_with(self.c, 'NEOCITY', exp=5000, money=5000)
        frames = self.handle(neocity.chapter_complete, Frame(0xeda, struct.pack('<II', 0, r.id)), patches)
        self.assertEqual([f.type for f in frames], [0xedb, 0xee9])      # shown again, nothing given
        self.assertEqual(len(self.db.saved), 1)                       # once per run
        self.add_exp.assert_awaited_once()
        self.assertEqual(self.p.neo_cleared[0], 1)

    def test_dying(self):
        """0xef2 (key, leftover, running count) -> 0xef3 (key, 0, 0): never a revive (a revive loop, user 2026-11-14);
        one death per burst."""
        r = self.enter(key=0)
        for n in (1, 2, 3750):
            frames = self.handle(neocity.dying, Frame(0xef2, struct.pack('<III', 0, 0x30000, n)))
            self.assertEqual(struct.unpack('<III', frames[0].payload), (0, 0, 0))
        self.assertEqual(r.deaths, 1)

    def test_revival_item_revives(self):
        """The revival item while destroyed -> 0xef3 (key, 1, 0) once; the client's next 0xef2 (its "alive again"
        notice) is not a death; not destroyed -> nothing."""
        r = self.enter(key=0)
        self.sent = []
        with patch.object(neocity, 'send', side_effect=lambda to, *fs: self.sent.extend(fs)):
            self.assertFalse(neocity.revive(self.s))                         # alive: no revive
        self.assertEqual(self.sent, [])
        self.handle(neocity.dying, Frame(0xef2, struct.pack('<III', 0, 0, 1)))
        self.sent = []
        with patch.object(neocity, 'send', side_effect=lambda to, *fs: self.sent.extend(fs)):
            self.assertTrue(neocity.revive(self.s))
            self.assertFalse(neocity.revive(self.s))                        # once per death
        self.assertEqual([(f.type, struct.unpack('<III', f.payload)) for f in self.sent], [(0xef3, (0, 1, 0))])
        frames = self.handle(neocity.dying, Frame(0xef2, struct.pack('<III', 0, 1, 2)))   # alive notice
        self.assertEqual(struct.unpack('<III', frames[0].payload), (0, 0, 0))
        self.assertEqual(r.deaths, 1)
        self.assertNotIn('neo_dead', self.s.state)

    def test_mission_params_completes(self):
        """0xeed (key, quest, mission) after a checkpoint scene -> 0xeee once."""
        r = self.enter(key=0)
        frames = self.handle(neocity.mission_params, Frame(0xeed, struct.pack('<3I', 0, 0, 1)))
        self.assertEqual([(f.type, struct.unpack('<3I', f.payload)) for f in frames], [(0xeee, (0, 0, 1))])
        self.assertEqual(self.handle(neocity.mission_params, Frame(0xeed, struct.pack('<3I', 0, 0, 1))), [])

    def test_bonus_card_pick(self):
        """0xee8 (u32 0, u32 slot): the card's item to the picker, 0xee9 with its serial; one card each."""
        r = self.enter(key=0)
        r.cards = [[1, 100 + i, 1, 0] for i in range(16)]
        r.card_items = [f'item_{i}' for i in range(16)]
        give = AsyncMock(return_value=(SimpleNamespace(items=[]), []))
        with patch('dcemu.native.game.rewards.give', give):
            frames = self.handle(neocity.chapter_reward, Frame(0xee8, struct.pack('<II', 0, 5)))
            self.assertEqual([f.type for f in frames], [0xee9])
            self.assertEqual(struct.unpack_from('<4I', frames[0].payload, 4 + 5 * 16),
                             (1, 105, 1, neocity.serial_of(self.s)))
            give.assert_awaited_once()
            self.handle(neocity.chapter_reward, Frame(0xee8, struct.pack('<II', 0, 6)))    # a second card: no
            give.assert_awaited_once()

    def test_bonus_mission_count(self):
        """0xef5 key -> 0xef6 key, 0, clears % 10."""
        self.p.neo_cleared = {2: 13}
        frames = self.handle(neocity.bonus_mission, Frame(0xef5, struct.pack('<II', 2, 0)))
        self.assertEqual(struct.unpack('<III', frames[0].payload), (2, 0, 3))

    def test_kill_class(self):
        self.assertEqual(neocity.kill_class(0, 'HUB-SL'), 'HUB')
        self.assertEqual(neocity.kill_class(1, 'HUS-QC'), 'HUS')
        self.assertEqual(neocity.kill_class(1, 'HUV-HMG'), 'HUV')
        self.assertEqual(neocity.kill_class(2, 'HUV ELITE'), 'HUV')

    def test_2011_no_answer(self):
        """The 2011 client speaks none of these messages."""
        version.configure({'version': '2011'})
        self.assertEqual(self.handle(neocity.suggest, self.suggest(0)), [])
        self.assertNotIn('neo_run', self.s.state)

    def test_area_key(self):
        """area.py: one area instance per run; a car without a run falls back to its serial."""
        r = self.enter()
        self.assertEqual(neocity.neo_area_key(self.s, 6), ('neo', 6, r.id))
        self.s.state.pop('neo_run')
        self.assertEqual(neocity.neo_area_key(self.s.state['serial'], 6), ('neo', 6, 1234))

    def test_quest_list(self):
        """0xee7 -> 0xee6: u16 n, u16 0, n x 28 bytes (chapter key @0, clear count @0x14); never during a run."""
        context.db = FakeDb([('neo_c_0000', 2), ('neo_c_0005', 1), ('sq_other', 9)])
        frames = self.handle(neocity.quest_list, Frame(0xee7, bytes(16)))
        self.assertEqual([f.type for f in frames], [0xee6])
        frame = frames[0]
        self.assertEqual(len(frame.payload) + 2, 6 + 2 * 28)
        self.assertEqual(struct.unpack_from('<HH', frame.payload), (2, 0))
        self.assertEqual(struct.unpack_from('<IH', frame.payload, 4)[0], 0)              # c_0000 -> key 0
        self.assertEqual(struct.unpack_from('<H', frame.payload, 4 + 0x14)[0], 2)
        self.assertEqual(struct.unpack_from('<IH', frame.payload, 4 + 28)[0:1], (2,))    # c_0005 -> key 2
        self.enter()                                                     # an active run: 0xee6 would drop it
        self.assertEqual(self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 0, 2))), [])  # left zone
        frames = self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 1, 1)))   # goal zone entered
        self.assertEqual([(f.type, struct.unpack('<4I', f.payload)) for f in frames], [(0xeea, (0, 0, 1, 1))])
        self.assertEqual(self.handle(neocity.quest_list, Frame(0xee7, struct.pack('<4I', 0, 0, 1, 1))), [])  # once


class NeoCityMissionTest(unittest.TestCase):
    """NEO_PROTOCOL_E: the mission list of NC_mission.xlt and the answers of 0xeeb (0xeec / 0xeee) and
    0xf4f (0xf50 to the victim only), in a two-member run of c_0005 (key 2)."""
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(root='server_data_2016')
        context.db = FakeDb()
        neocity._chapters = neocity._quests = neocity._missions = None
        neocity.runs.clear()
        neocity._hp.clear()
        self.c = SimpleNamespace(cid=7, name='Driver', level=50, city=1, exp=1000, exp_next=2000,
                                 exp_base=1000, mito=500)
        self.p = SimpleNamespace(char=self.c, items=[])
        self.s = SimpleNamespace(id=11, state={'player': self.p, 'serial': 1234, 'channel': 0}, log=Mock())
        self.c2 = SimpleNamespace(cid=8, name='Two', level=50, city=1, exp=500, exp_next=900,
                                  exp_base=500, mito=50)
        self.p2 = SimpleNamespace(char=self.c2, items=[])
        self.s2 = SimpleNamespace(id=12, state={'player': self.p2, 'serial': 5678, 'channel': 0}, log=Mock())
        self.r = neocity.Run([self.s, self.s2], neocity.chapter_by_key(2), solo=False)   # c_0005, key 2
        neocity.runs[self.r.id] = self.r
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._chapters = neocity._quests = neocity._missions = neocity._huvs = None
        neocity.runs.clear()
        neocity._hp.clear()
        version.configure({'version': '2011'})

    def handle(self, fn, frame):
        """-> [(recipient session, frame)] for one message sent as self.s."""
        self.sent = []
        with patch.object(neocity, 'send',
                          side_effect=lambda to, *fs: self.sent.extend((to, f) for f in fs)):
            asyncio.run(fn(self.s, frame))
        return self.sent

    def frames(self, fn, frame):
        return [f for _, f in self.handle(fn, frame)]

    def progress(self, key=2, quest=0, mission=0, value=0, report=0, huv=0):
        """C>S 0xeeb (26): +2 key, +6 quest, +0xa mission, +0xe value, +0x12 report, +0x16 HUV key."""
        return Frame(0xeeb, struct.pack('<6I', key, quest, mission, value, report, huv))

    def test_mission_list_of_q00023(self):
        """q_00023 (c_0005 quest 0): its rows without start / *_pass, in file order -> move, patrol,
        destroy, move, move (mission IDs m_000097, m_000098, m_000098, m_000099, m_000100)."""
        chapter = neocity.chapter_by_key(2)
        got = [neocity.mission_of(chapter, 0, i) for i in range(5)]
        self.assertEqual([(m['type'], m['number']) for m in got],
                         [('move', 2), ('patrol', 8), ('destroy', 11), ('move', 2), ('move', 2)])
        self.assertEqual([m['id'] for m in got],
                         ['m_000097', 'm_000098', 'm_000098', 'm_000099', 'm_000100'])
        self.assertEqual(got[2]['param_1'], ['100482', 'n/a', 'n/a', 'n/a', 'n/a'])
        self.assertEqual(got[2]['param_2'], 3)
        self.assertIsNone(neocity.mission_of(chapter, 0, 5))               # out of the list
        self.assertIsNone(neocity.mission_of(chapter, 9, 0))               # no such quest
        self.assertIsNone(neocity.mission_of(neocity.chapter_by_key(99), 0, 0))
        self.assertEqual(neocity.mission_of(chapter, 1, 0)['type'], 'collect')   # q_00024
        self.assertEqual(neocity.mission_of(chapter, 1, 0)['param_2'], 5)

    def test_patrol_answers_eec_only(self):
        """0xeeb patrol -> 0xeec (26): key, quest, mission, param1 = the value, param2 = 0, 4 zeros;
        0xeea must not be sent (it would stop the client's mission tick)."""
        frames = self.frames(neocity.mission_progress, self.progress(quest=0, mission=1, value=3))
        self.assertEqual([f.type for f in frames], [0xeec])
        self.assertEqual(len(frames[0].payload) + 2, 26)
        self.assertEqual(struct.unpack_from('<5I', frames[0].payload), (2, 0, 1, 3, 0))
        self.assertEqual(frames[0].payload[20:], bytes(4))
        # the point is not one of the completed rules: no 0xeee, and the repeat is not logged twice
        self.assertEqual(self.r.missions_done, set())
        self.assertEqual(self.frames(neocity.mission_progress,
                                     self.progress(quest=0, mission=1, value=3)), frames)
        self.assertEqual(self.s.log.note.call_count, 1)

    def test_destroy_hit_report_is_dropped(self):
        """0xeeb with +0x12 or +0x16 non-zero is a destroy hit report (0x5132ae): no answer, no log."""
        self.assertEqual(self.handle(neocity.mission_progress,
                                     self.progress(quest=0, mission=2, value=100482, report=7)), [])
        self.assertEqual(self.handle(neocity.mission_progress,
                                     self.progress(quest=0, mission=2, value=100482, huv=100482)), [])
        self.s.log.note.assert_not_called()

    def test_collect_completes_once(self):
        """q_00024 (quest 1) mission 0 needs param_2 = 5: every 0xeeb gets 0xeec, the count gets one 0xeee."""
        frame = self.progress(quest=1, mission=0, value=4)
        self.assertEqual([f.type for f in self.frames(neocity.mission_progress, frame)], [0xeec])
        self.assertEqual(self.r.missions_done, set())
        frame = self.progress(quest=1, mission=0, value=5)
        frames = self.frames(neocity.mission_progress, frame)
        self.assertEqual([f.type for f in frames], [0xeec, 0xeee])
        self.assertEqual(struct.unpack_from('<5I', frames[0].payload), (2, 1, 0, 5, 0))
        self.assertEqual(struct.unpack_from('<3I', frames[1].payload), (2, 1, 0))
        self.assertIn((1, 0), self.r.missions_done)
        frames = self.frames(neocity.mission_progress, frame)             # second time: no second 0xeee
        self.assertEqual([f.type for f in frames], [0xeec])

    def test_mission_complete_marks_done(self):
        """0xeef -> 0xeee and the pair is marked, so a later collect 0xeeb sends no second 0xeee."""
        frames = self.frames(neocity.mission_complete, Frame(0xeef, struct.pack('<3I', 2, 1, 0)))
        self.assertEqual([f.type for f in frames], [0xeee])
        self.assertEqual(struct.unpack_from('<3I', frames[0].payload), (2, 1, 0))
        self.assertIn((1, 0), self.r.missions_done)
        frames = self.frames(neocity.mission_progress, self.progress(quest=1, mission=0, value=5))
        self.assertEqual([f.type for f in frames], [0xeec])

    def test_explosion_forwarded_to_the_victim_only(self):
        """0xf4f -> 0xf50 (18) to the member whose serial low 16 bits is +2: its serial, VICTIM_SORT,
        then the request's +6..+0x11 (effect id, radius, distance) unchanged."""
        hit = struct.pack('<HH I f f', 5678, 0x1111, 7, 10.0, 2.5)        # +2, +4, +6, +0xa, +0xe
        sent = self.handle(neocity.explosion_hit, Frame(0xf4f, hit))
        self.assertEqual([s for s, _ in sent], [self.s2])
        frame = sent[0][1]
        self.assertEqual(frame.type, 0xf50)
        self.assertEqual(len(frame.payload) + 2, 18)
        self.assertEqual(struct.unpack_from('<HH', frame.payload), (5678, neocity.VICTIM_SORT))
        self.assertEqual(frame.payload[4:], hit[4:])
        self.assertEqual(self.r.hits, 1)
        self.assertFalse(self.r.effects_dropped)
        self.s.log.note.assert_not_called()

    def test_explosion_without_a_victim_is_dropped(self):
        """No member with that serial, or the sender's own serial: nothing sent, one note per run."""
        hit = struct.pack('<HH I f f', 9999, 0, 7, 10.0, 2.5)
        self.assertEqual(self.handle(neocity.explosion_hit, Frame(0xf4f, hit)), [])
        self.assertEqual(self.handle(neocity.explosion_hit,
                                     Frame(0xf4f, struct.pack('<HH I f f', 1234, 0, 7, 10.0, 2.5))), [])
        self.assertEqual(self.handle(neocity.explosion_hit, Frame(0xf4f, hit)), [])
        self.assertEqual(self.s.log.note.call_count, 1)
        self.assertTrue(self.r.effects_dropped)
        self.assertEqual(self.r.hits, 0)

    def test_2011_nothing(self):
        """The 2011 client sends none of these messages."""
        version.configure({'version': '2011'})
        self.assertEqual(self.handle(neocity.mission_progress, self.progress(value=1)), [])
        self.assertEqual(self.handle(neocity.explosion_hit, Frame(0xf4f, bytes(16))), [])


class NeoCityCombatTest(unittest.TestCase):
    """Stage 3: Neo enemies (0xc6 -> 0xc7, 0xcd, 0xce), turrets (0xf41 -> 0xf42) and part repair
    (0x4c4 -> 0x4c5), all in a two-member run (docs/neo_work/NEO_PROTOCOL_B.md)."""
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(root='server_data_2016', item_index={'i_neo_test': 999})
        context.db = FakeDb()
        neocity._chapters = neocity._quests = neocity._huvs = None
        neocity.runs.clear()
        neocity._hp.clear()
        self.c = SimpleNamespace(cid=7, name='Driver', level=50, city=1, exp=1000, exp_next=2000,
                                 exp_base=1000, mito=500)
        self.p = SimpleNamespace(char=self.c, items=[])
        self.s = SimpleNamespace(id=11, state={'player': self.p, 'serial': 1234, 'channel': 0}, log=Mock())
        self.c2 = SimpleNamespace(cid=8, name='Two', level=50, city=1, exp=500, exp_next=900,
                                  exp_base=500, mito=50)
        self.p2 = SimpleNamespace(char=self.c2, items=[])
        self.s2 = SimpleNamespace(id=12, state={'player': self.p2, 'serial': 5678, 'channel': 0}, log=Mock())
        self.r = neocity.Run([self.s, self.s2], neocity.chapter_by_key(2), solo=False)   # c_0005, key 2
        neocity.runs[self.r.id] = self.r
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._chapters = neocity._quests = neocity._huvs = None
        neocity.runs.clear()
        neocity._hp.clear()
        version.configure({'version': '2011'})

    def handle(self, fn, frame, patches=()):
        self.sent = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(neocity, 'send',
                                             side_effect=lambda to, *fs: self.sent.extend(fs)))
            for p in patches:
                stack.enter_context(p)
            asyncio.run(fn(self.s, frame))
        return self.sent

    def test_collect_drop(self):
        """q_00024 (c_0005 quest 1) collects 5 neo_q_00001 from HUV 100482 at 100 % (NC_mission param_1): a kill of
        that HUV gives one while fewer than 5 are held; another HUV or a full stack gives nothing."""
        neocity._missions = None
        context.data.item_index['neo_q_00001'] = 1000
        self.r.quest = 1
        give = AsyncMock(return_value=(SimpleNamespace(items=['changed']), []))
        with patch('dcemu.native.game.rewards.give', give), \
                patch('dcemu.native.game.items.mod_list', lambda *a: Frame(0x192, b'')), \
                patch.object(neocity, 'send', side_effect=lambda to, *fs: self.sent.extend(fs)):
            asyncio.run(neocity.collect_drop(self.s, self.p, self.r, 100482))
            self.assertEqual(give.await_args.args[1], [('neo_q_00001', 1)])
            self.assertEqual([f.type for f in self.sent], [0x192])
            give.reset_mock()
            asyncio.run(neocity.collect_drop(self.s, self.p, self.r, 100481))       # not the mission's enemy
            give.assert_not_awaited()
            self.p.items = [SimpleNamespace(item_id='neo_q_00001', stack=5)]
            asyncio.run(neocity.collect_drop(self.s, self.p, self.r, 100482))       # already 5
            give.assert_not_awaited()

    def reward_patches(self, level=10):
        """The exp / Mito / item / table calls mocked; a fake NeoHuvParam loader and one reward group."""
        self.add_exp, self.add_money = AsyncMock(return_value=False), AsyncMock(return_value=True)
        self.play_mode = AsyncMock()
        self.give = AsyncMock(return_value=(SimpleNamespace(items=[]),
                                            [(SimpleNamespace(item_id='i_neo_test'), 1)]))
        return [patch.object(neocity, 'add_exp', self.add_exp),
                patch.object(neocity, 'add_money', self.add_money),
                patch.object(neocity, 'play_mode', self.play_mode),
                patch.object(neocity, 'stat_frames', lambda p: []),
                patch.object(neocity, 'huv_params',
                             lambda: {100002: dict(level=level, name='NEO HUV', reward='rw_neo_test')}),
                patch('dcemu.native.game.driftuse.roll',
                      lambda group, depth=0: [('NormalItem', 'i_neo_test', 0, 1, 0)]),
                patch('dcemu.native.game.rewards.give', self.give)]

    def test_enemy_request_answers_every_member(self):
        """0xc6 -> 0xc7 (0xc + 0x40 n) to both members: serial @8, 1 @0xa, chapter key @0x30, quest @0x34."""
        self.r.quest = 3
        rec = bytearray(0x40)
        struct.pack_into('<H', rec, 0, 1)                   # kind 1
        struct.pack_into('<I', rec, 0xe, 100001)            # Huv Param ID
        struct.pack_into('<IIHH', rec, 0x12, 0xdeadbeef, 0x12345678, 0x1111, 0x2222)   # the unclear block
        struct.pack_into('<3f', rec, 0x20, 1.0, 2.0, 3.0)   # position
        # n = 3 but only one record: n is clamped to the payload (0xa + 0x40 with the type)
        frames = self.handle(neocity.enemy_request,
                             Frame(0xc6, struct.pack('<II', 4242, 3) + bytes(rec)))
        self.assertEqual([f.type for f in frames], [0xc7, 0xc7])
        frame = frames[0]
        self.assertEqual(len(frame.payload) + 2, 0xc + 0x40)
        self.assertEqual(struct.unpack_from('<IIH', frame.payload), (4242, 1, 0))
        out = frame.payload[0xa:]
        self.assertEqual(len(out), 0x40)
        self.assertEqual(struct.unpack_from('<H', out, 8)[0], 1234)       # the sender's serial
        self.assertEqual(struct.unpack_from('<H', out, 0xa)[0], neocity.ENEMY_FIRST)   # unique, not 0
        self.assertEqual(struct.unpack_from('<I', out, 0x30)[0], 2)       # chapter key (c_0005)
        self.assertEqual(struct.unpack_from('<I', out, 0x34)[0], 3)       # the run's quest
        self.assertEqual(struct.unpack_from('<I', out, 0xe)[0], 100001)   # unchanged
        self.assertEqual(struct.unpack_from('<H', out, 0)[0], 1)          # unchanged
        self.assertEqual(out[0x12:0x1c], bytes(rec[0x12:0x1c]))          # +0x12..+0x1a left as sent
        self.assertEqual(out[0x20:0x2c], bytes(rec[0x20:0x2c]))          # position
        self.assertEqual(self.r.enemies, [out])

    def test_hub_summons_not_relayed(self):
        """Kind-3 records (a HUB's summons) crashed the client at 0x4a99a1 once relayed: dropped."""
        summon, hub = bytearray(0x40), bytearray(0x40)
        struct.pack_into('<H', summon, 0, 3)
        struct.pack_into('<H', hub, 0, 1)
        self.assertEqual(self.handle(neocity.enemy_request, Frame(0xc6, struct.pack('<II', 1, 1) + bytes(summon))),
                         [])
        frames = self.handle(neocity.enemy_request,
                             Frame(0xc6, struct.pack('<II', 1, 2) + bytes(summon) + bytes(hub)))
        self.assertEqual([(f.type, struct.unpack_from('<I', f.payload, 4)[0]) for f in frames], [(0xc7, 1)] * 2)
        self.assertEqual(struct.unpack_from('<H', frames[0].payload, 0xa)[0], 1)

    def test_enemy_hit_relay(self):
        """0xcd: 42 bytes back to every run member, +2..+0x19 copied, Mito / i64 / exp zero at +0x1a."""
        rec = bytearray(0x28)
        struct.pack_into('<H', rec, 0, 1234)                # hitter serial (frame +2)
        struct.pack_into('<HH', rec, 4, 0x11, 0x22)        # victim key lo / hi (+6 / +8)
        struct.pack_into('<i', rec, 0xa, 40)                # HP left (+0xc)
        struct.pack_into('<i', rec, 0xe, 60)                # damage (+0x10)
        frames = self.handle(neocity.enemy_hit, Frame(0xcd, bytes(rec)))
        self.assertEqual([f.type for f in frames], [0xcd, 0xcd])          # the sender too
        out = frames[0].payload
        self.assertEqual(len(out) + 2, 42)
        self.assertEqual(out[:0x18], bytes(rec[:0x18]))
        self.assertEqual(struct.unpack_from('<iqi', out, 0x18), (0, 0, 0))
        self.assertEqual(len(out), 0x28)

    def test_enemy_kill_relays_and_pays_once(self):
        """0xce: the same 62 bytes to both members; the killer gets level x 10 exp / Mito and 0x7d1 / 0x7d2."""
        rec = bytearray(0x3e)
        struct.pack_into('<HH', rec, 0, 7, 9)               # key lo / hi (frame +2 / +4)
        struct.pack_into('<I', rec, 0x34, 100002)           # Huv Param ID (frame +0x36)
        struct.pack_into('<I', rec, 0x38, 0xac)             # the HUV record's +0xac (frame +0x3a)
        struct.pack_into('<H', rec, 0x3c, 1234)             # killer serial (frame +0x3e)
        patches = self.reward_patches(level=10)
        frames = self.handle(neocity.enemy_kill, Frame(0xce, bytes(rec)), patches)
        self.assertEqual([f.type for f in frames], [0xce, 0xce, 0x7d1, 0x7d2])
        self.assertEqual(frames[0].payload, bytes(rec))
        self.assertEqual(frames[1].payload, bytes(rec))
        self.assertEqual(len(frames[0].payload) + 2, 64)
        self.add_exp.assert_awaited_once_with(self.c, 100)
        self.add_money.assert_awaited_once_with(self.c, 100)
        self.play_mode.assert_awaited_once_with(self.c, 'NEOCITY', exp=100, money=100)
        self.give.assert_awaited_once_with(self.p, [('i_neo_test', 1)])
        self.assertIn((7, 9), self.r.killed)
        # a second report of the same enemy is relayed but not paid again
        frames = self.handle(neocity.enemy_kill, Frame(0xce, bytes(rec)), patches)
        self.assertEqual([f.type for f in frames], [0xce, 0xce])
        self.add_exp.assert_awaited_once()
        self.add_money.assert_awaited_once()
        self.give.assert_awaited_once()

    def test_enemy_kill_unknown_id_relays_only(self):
        rec = bytearray(0x3e)
        struct.pack_into('<I', rec, 0x34, 999999)           # not in the (empty) Huv Param table
        frames = self.handle(neocity.enemy_kill, Frame(0xce, bytes(rec)),
                             [patch.object(neocity, 'huv_params', lambda: {})])
        self.assertEqual([f.type for f in frames], [0xce, 0xce])
        self.assertIn((0, 0), self.r.killed)

    def test_turret_request(self):
        """0xf41 -> 0xf42: n = 1 from the client's 22-byte request; serial, per-run id, the 12 bytes."""
        positions = struct.pack('<3f', 1.0, 2.0, 3.0)
        frames = self.handle(neocity.turret_request,
                             Frame(0xf41, struct.pack('<IHH', 1, 7, 9) + positions))
        self.assertEqual([f.type for f in frames], [0xf42, 0xf42])
        frame = frames[0]
        self.assertEqual(len(frame.payload) + 2, 0xa + 0x10)
        self.assertEqual(struct.unpack_from('<IHH', frame.payload), (1, 7, 9))
        self.assertEqual(struct.unpack_from('<HH', frame.payload, 8), (1234, 1))
        self.assertEqual(frame.payload[0xc:], positions)
        # the client reserves 22 bytes for every n: n = 5 in a 22-byte request is clamped to its 1 record
        frames = self.handle(neocity.turret_request,
                             Frame(0xf41, struct.pack('<IHH', 5, 7, 9) + positions))
        self.assertEqual(struct.unpack_from('<I', frames[0].payload)[0], 1)
        self.assertEqual(struct.unpack_from('<H', frames[0].payload, 0xa)[0], 2)    # the next run id

    def test_repair_answer(self):
        """0x4c4 -> 0x4c5: the item id and code 1, also outside a run."""
        self.s.state.pop('neo_run')
        frames = self.handle(neocity.repair_parts, Frame(0x4c4, struct.pack('<I', 777)))
        self.assertEqual([f.type for f in frames], [0x4c5])
        self.assertEqual(len(frames[0].payload) + 2, 10)
        self.assertEqual(struct.unpack_from('<II', frames[0].payload), (777, 1))

    def test_2011_nothing(self):
        """The 2011 client sends none of these messages."""
        version.configure({'version': '2011'})
        self.assertEqual(self.handle(neocity.enemy_request, Frame(0xc6, bytes(8))), [])
        self.assertEqual(self.handle(neocity.enemy_hit, Frame(0xcd, bytes(0x28))), [])
        self.assertEqual(self.handle(neocity.enemy_kill, Frame(0xce, bytes(0x3e))), [])
        self.assertEqual(self.handle(neocity.turret_request, Frame(0xf41, bytes(20))), [])
        self.assertEqual(self.handle(neocity.repair_parts, Frame(0x4c4, bytes(4))), [])

