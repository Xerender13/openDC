"""Season event server parts (game/seasonal.py) on the 2011 and 2016 tables: Easter recipes and baskets, Harvest
deliveries and receipts, event drops, the Christmas tree stage and the Valentine switch push."""
import asyncio
import itertools
import os
import random
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, events, version
from dcemu.native.data import Tables
from dcemu.native.game import driftuse, items, seasonal
from dcemu.native.game.records import Item
from dcemu.wire import Frame


class Db:
    server_id = 1

    def __init__(self):
        self.gid = itertools.count(5000)
        self.execute = AsyncMock()

    async def row(self, sql, p=()):
        return [next(self.gid)]


def run(coro):
    return asyncio.run(coro)


class SeasonalBase:
    DATA = None
    VERSION = None

    @classmethod
    def setUpClass(cls):
        tables = f'{cls.DATA}/tables'
        cls.tables = Tables(cls.DATA, tables, 'server_data/adminlist.txt')

    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': self.VERSION})
        context.data = self.tables
        context.db = Db()
        context.events = {}
        driftuse._groups = None
        self.c = SimpleNamespace(cid=7, name='T', level=35, exp=0, exp_next=10 ** 9, exp_base=0, mito=0,
                                 hancoin_inven=2, part_inven_idx=100)
        self.p = SimpleNamespace(char=self.c, items=[], tick=0)
        self.sent = []
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()),
                                 to_client=lambda f: self.sent.append(f))
        self.patches = [patch.object(seasonal, 'send', lambda s, *f: self.sent.extend(f)),
                        patch('dcemu.native.game.setparts.start_expiry', AsyncMock())]
        for x in self.patches:
            x.start()

    def tearDown(self):
        for x in self.patches:
            x.stop()
        driftuse._groups = None
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def give(self, item_id, stack=1):
        t = self.tables
        inven = len(self.p.items) + 1
        it = Item(1000 + inven, inven, item_id, 0, stack, 0, 0, 0, 0, '', '', 0, 0, t.item_index[item_id])
        self.p.items.append(it)
        return it

    def info(self, item_id):
        return self.tables.item_info(self.tables.item_index[item_id])

    def held(self, item_id):
        return seasonal.held(self.p, item_id)


@unittest.skipUnless(os.path.exists('server_data/tables/UseItemClient.tdf'), 'needs the 2011 tables')
class Easter2011Test(SeasonalBase, unittest.TestCase):
    DATA, VERSION = 'server_data', '2011'

    @classmethod
    def setUpClass(cls):
        cls.tables = Tables('server_data', 'server_data/tables', 'server_data/adminlist.txt')

    def test_basic_recipe_makes_a_basket_and_stays(self):
        recipe = self.give('g_choco_recipe')
        self.give('black_chocolete', 12)
        self.give('careful_wrapping', 2)
        random.seed(3)
        self.assertTrue(run(seasonal.craft(self.s, self.p, recipe, self.info('g_choco_recipe'))))
        self.assertEqual(self.held('black_chocolete'), 2)
        self.assertEqual(self.held('careful_wrapping'), 1)
        self.assertEqual(self.held('g_choco_recipe'), 1)                       # permanent
        basket = next(i for i in self.p.items if i.item_id == 'g_make_giftbox')
        self.assertIn(basket.random, seasonal.PAINTED)
        self.assertEqual([f.type for f in self.sent], [0x1a2, 0x192, 0x89])
        self.assertEqual(struct.unpack_from('<II', self.sent[0].payload), (recipe.inven_idx, 0))   # nothing used up

    def test_missing_eggs_refused(self):
        recipe = self.give('h_choco_recipe')
        self.give('black_chocolete', 3)
        self.give('white_chocolete', 6)
        self.give('twinkling_wrapping')
        self.assertTrue(run(seasonal.craft(self.s, self.p, recipe, self.info('h_choco_recipe'))))
        self.assertEqual([f.type for f in self.sent], [0x0001])
        self.assertEqual(self.held('white_chocolete'), 6)

    def test_basket_exp_is_the_level_band_times_the_painted_eggs(self):
        basket = self.give('g_make_giftbox')
        basket.random = 4
        gains = driftuse.Gains()
        with patch('dcemu.native.game.progress.add_exp', AsyncMock()) as add:
            run(seasonal.eat_basket(self.s, self.p, basket, self.info('g_make_giftbox'), gains))
        self.assertEqual(gains.exp, 40 * 4)                                     # level 35: exp_40 band, 40 per egg
        add.assert_awaited_once()


@unittest.skipUnless(os.path.exists('server_data_2016/tables/UseItemClient.tdf'), 'needs the 2016 tables')
class Seasonal2016Test(SeasonalBase, unittest.TestCase):
    DATA, VERSION = 'server_data_2016', '2016'

    def test_2015_recipe_quality_from_the_rows(self):
        recipe = self.give('i_n_choco_urecipe_2012')
        self.give('i_n_milk_choco_2012', 3)
        self.give('i_n_shell_choco_2012', 3)
        self.give('i_n_ball_choco_2012', 4)
        self.give('twinkling_wrapping')
        self.assertTrue(run(seasonal.craft(self.s, self.p, recipe, self.info('i_n_choco_urecipe_2012'))))
        basket = next(i for i in self.p.items if i.item_id == 'i_n_make_ugiftbox_2012')
        self.assertIn(basket.random, seasonal.PAINTED)
        self.assertEqual(self.held('i_n_ball_choco_2012'), 0)
        self.assertEqual(seasonal.painted_of(21), 1)
        self.assertEqual(seasonal.painted_of(24), 10)

    def test_box_recipe_prefers_the_ice_box(self):
        recipe = self.give('event_box_recipe_n')
        for f in seasonal.FOODS:
            self.give(f, 2)
        self.give('event_normalbox_n', 1)
        self.give('event_icebox_n', 1)
        self.assertTrue(run(seasonal.craft(self.s, self.p, recipe, self.info('event_box_recipe_n'))))
        self.assertEqual(self.held('event_icebox_n'), 0)
        self.assertEqual(self.held('event_normalbox_n'), 1)
        self.assertTrue(any(self.info(i.item_id).kind == 'deliverybox_item' for i in self.p.items))

    def test_harvest_delivery_city_box_and_receipts(self):
        context.events = {'harvest': 'on'}
        box = self.give('eventbox_result_03')                                  # Large: 4 receipts per rating point
        row = ['job', '', '', 'post_3rd_0001']
        with patch.object(seasonal, 'chef_rating', return_value=2):
            extra, changes = run(seasonal.harvest_delivery(self.s, self.p, row))
        self.assertEqual(extra, [('event_giftbox_cras', 1), ('event_receipt_01', 8)])
        self.assertEqual(len(changes), 1)
        self.assertNotIn(box, self.p.items)
        context.events = {'harvest': 'off'}
        self.assertEqual(run(seasonal.harvest_delivery(self.s, self.p, row)), ([], []))

    def test_receipt_exchange(self):
        receipts = self.give('event_receipt_01', 12)
        self.assertTrue(run(seasonal.exchange_receipts(self.s, self.p, receipts, self.info('event_receipt_01'))))
        self.assertEqual(self.held('event_receipt_01'), 2)
        self.assertEqual(self.held('event_goat_box_v1'), 1)
        self.sent.clear()
        self.assertTrue(run(seasonal.exchange_receipts(self.s, self.p, receipts, self.info('event_receipt_01'))))
        self.assertEqual([f.type for f in self.sent], [0x0001])                 # 2 left: not enough

    def test_event_drops_only_while_the_event_runs(self):
        rng = SimpleNamespace(uniform=lambda a, b: 0.0)                         # every chance hits
        context.events = {n: 'off' for n in events.EVENTS}
        self.assertIsNone(seasonal.event_drop(self.p, rng))
        context.events['summer'] = 'on'
        self.assertEqual(seasonal.event_drop(self.p, rng).item_id, 'giftbox_suika')
        context.events['summer.drops'] = 'i_n_00088:5, bogus:9'
        self.assertEqual(seasonal.event_drop(self.p, rng).item_id, 'i_n_00088')
        context.events['summer.drops'] = ''
        self.assertIsNone(seasonal.event_drop(self.p, rng))

    def test_tree_stage_at_login_and_valentine_push(self):
        context.events = {'christmas': 'on'}
        self.assertEqual(seasonal.login_frames(self.p), [])                     # stage 0: nothing
        context.events['christmas.tree'] = '3'
        f = seasonal.login_frames(self.p)
        self.assertEqual([(x.type, struct.unpack('<i', x.payload)[0]) for x in f], [(0xcf2, 3)])
        with patch('dcemu.native.game.login.sessions', {1: self.s}):
            reply = events.gm_command(['valentine', 'on'])
        self.assertIn('1 online told', reply)
        self.assertEqual((self.sent[-1].type, self.sent[-1].payload), (0xfbb, struct.pack('<I', 1)))
