"""2016 items on the 2016 tables: drift packs that give inventory items, the inventory Mittron Enhancer Booster,
the Upgrade Chance Enhancing Fluid, the Manufacturing Booster and the Ultra (U / OU) part rules."""
import asyncio
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import alchemy, driftuse, items, upgrade
from dcemu.native.game.records import Item
from dcemu.wire import Frame

DATA = 'server_data_2016'


def item(t, inven, item_id, stack=1, upgrade=0, car=0):
    return Item(1000 + inven, inven, item_id, car, stack, 0, 0, upgrade, 0, '', '', 0, 0, t.item_index[item_id])


@unittest.skipUnless(os.path.exists(f'{DATA}/tables/ItemClient.tdf'), 'needs the 2016 client tables (tools.client_setup)')
class Items2016Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = Tables(DATA, f'{DATA}/tables', f'{DATA}/adminlist.txt')

    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = t = self.tables
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock(), row=AsyncMock(return_value=None),
                                     rows=AsyncMock(return_value=[]))
        upgrade._tables = None
        self.p = SimpleNamespace(char=SimpleNamespace(cid=7, name='T', mito=10 ** 9, hancoin_inven=2, level=99), items=[], vsitems=[], tick=0,
                                 lic=None, car=None, buffs={})
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()), to_client=Mock())
        self.t = t

    def tearDown(self):
        upgrade._tables = None
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def run_(self, coro):
        return asyncio.run(coro)

    def test_new_drift_packs_give_their_inventory_items(self):
        given = []

        async def give(p, item_id, count, gains):
            given.append((item_id, count))
        with patch.object(driftuse, 'give_item', give):
            for vid in ('i_d_double_10', 'i_d_createdouble_20', 'i_d_chancetime_1', 'i_d_partsbox_25'):
                vis = self.t.visuals[self.t.visual_index[vid]]
                self.assertTrue(self.run_(driftuse.instant(self.s, self.p, vis, driftuse.Gains())), vid)
            old = self.t.visuals[self.t.visual_index['i_d_double']]          # the drift Booster stays one
            self.assertFalse(self.run_(driftuse.instant(self.s, self.p, old, driftuse.Gains())))
        self.assertEqual(given, [('i_n_double', 10), ('i_n_createdouble', 20), ('i_n_chancetime', 1),
                                 ('i_n_00027', 25)])

    def test_parts_shop_sells_the_floor_marked_parts(self):
        """2016 ItemClient column 15 names the shop floor ('1F' / 'B1F') where 2011 had True."""
        t = self.t
        self.assertTrue(t.item_info(t.item_index['i_s_000001']).shop)          # '1F' (Small, TableIdx 0)
        self.assertTrue(t.item_info(t.item_index['neo_wp_c_21101']).shop)      # 'B1F'
        self.assertFalse(t.item_info(t.item_index['i_s_000002']).shop)         # 'False'
        self.assertTrue(t.item_info(t.item_index['i_n_00040']).shop)           # UseItemClient col 13 '1F' (Type A)
        sent = []
        with patch.object(items, 'send', lambda s, *f: sent.extend(f)), \
                patch.object(items, 'add_money', AsyncMock(return_value=True)), \
                patch.object(items, 'new_item', AsyncMock(return_value=item(t, 1, 'i_s_000001'))):
            self.run_(items.buy_item(self.s, Frame(0x195, struct.pack('<IIi', 0, 1, -1))))
        self.assertEqual([f.type for f in sent], [0x196, 0x192])
        self.assertEqual(struct.unpack('<III', sent[0].payload), (0, 1, 250))

    def enhance(self, payload):
        sent = []
        with patch.object(upgrade, 'send', lambda s, *f: sent.extend(f)), \
                patch.object(upgrade, 'stat_frames', return_value=()), \
                patch.object(upgrade, 'gauge_of', AsyncMock(return_value=0)), \
                patch.object(upgrade, 'set_gauge', AsyncMock()), \
                patch.object(upgrade, 'save_part', AsyncMock()), \
                patch('dcemu.native.game.licenses.count_monthly', AsyncMock()), \
                patch('dcemu.native.game.licenses.count_many', AsyncMock()), \
                patch.object(upgrade, 'add_money', AsyncMock(return_value=True)), \
                patch.object(upgrade, 'roll', return_value=True):
            result = self.run_(upgrade.enhance(self.s, Frame(0x1ae, payload), True))
        return result, sent

    def test_double_upgrade_with_an_inventory_booster(self):
        part, enh, booster = item(self.t, 1, 'i_s_000016'), item(self.t, 2, 'i_n_00003', 5), item(self.t, 3, 'i_n_double', 4)
        self.p.items = [part, enh, booster]
        result, sent = self.enhance(struct.pack('<IIiII', 1, 2, 1, 0, 3))         # drift Booster 0, inventory 3
        self.assertIsNotNone(result)
        self.assertEqual(result[1], [upgrade.SUCCESS, upgrade.SUCCESS])
        self.assertEqual((part.upgrade, enh.stack, booster.stack), (2, 4, 3))       # an Ultra part, + 2
        self.assertEqual(sent[0].type, 0x1af)

    def test_double_upgrade_without_any_booster_is_refused(self):
        self.p.items = [item(self.t, 1, 'i_s_000016'), item(self.t, 2, 'i_n_00003', 5)]
        with patch.object(upgrade, 'error') as err:
            result, _ = self.enhance(struct.pack('<IIiII', 1, 2, 1, 0, 9))
        self.assertIsNone(result)
        err.assert_called()

    def test_ultra_odds_follow_hyper(self):
        odds = upgrade.tables()[0]
        self.assertEqual(odds[1, 'U'], odds[1, 'H'])

    def test_chance_fluid_fills_the_gauge(self):
        fluid = item(self.t, 4, 'i_n_chancetime', 2)
        self.p.items = [fluid]
        sent = []
        with patch.object(items, 'send', lambda s, *f: sent.extend(f)), \
                patch('dcemu.native.game.upgrade.set_gauge', AsyncMock()) as gauge:
            self.run_(items.use_item(self.s, Frame(0x1a1, struct.pack('<II', 4, 1))))
        gauge.assert_awaited_once_with(self.p, upgrade.GAUGE_MAX)
        self.assertEqual(fluid.stack, 1)
        ack = next(f for f in sent if f.type == 0x1a2)
        self.assertEqual(struct.unpack_from('<I', ack.payload, 8)[0], 0x69)       # fullchance_upgrade, 2016 code

    def test_ultra_rules(self):
        self.assertIn('OU', items.GRADE_FITS['U'])
        ultra = self.t.item_info(self.t.item_index['i_n_00025_U'])
        hyper = self.t.item_info(self.t.item_index['i_n_00025'])
        self.assertTrue(items.kit_fits(ultra, 'U') and items.kit_fits(hyper, 'H'))
        self.assertFalse(items.kit_fits(hyper, 'U') or items.kit_fits(ultra, 'H'))
        from dcemu.native.game import docking
        self.assertEqual(len(docking.letters('dock_A', 'U')), 15)              # dock_A_U001 .. U015

    def test_manufacturing_booster_doubles_the_result(self):
        booster = item(self.t, 5, 'i_n_createdouble', 3)
        self.p.items = [booster]
        recipe = dict(items=[], kit=('', 0), result=('i_n_00003', 2), bonus=('', 0), bonus_pct=0, chance=100,
                      req=0, exp_ok=1, exp_fail=0)
        given = []

        async def give(p, item_id, count, gains):
            given.append((item_id, count))
        name = b'test_skb'
        with patch.object(alchemy, 'recipes', return_value={'test_skb': recipe}), \
                patch.object(alchemy, 'load', AsyncMock(return_value={'skills': {'test_skb'}, 'exp': 0})), \
                patch.object(alchemy, 'save', AsyncMock()), patch.object(alchemy, 'send'), \
                patch('dcemu.native.game.driftuse.give_item', give), \
                patch('dcemu.native.game.licenses.count_monthly', AsyncMock()):
            self.p.alchemy = None
            payload = name.ljust(alchemy.NAME, b'\0') + struct.pack('<II', 0, 5)
            self.run_(alchemy.manufacture(self.s, Frame(0xe78, payload)))
        self.assertEqual(given, [('i_n_00003', 4)])
        self.assertEqual(booster.stack, 2)

    def test_car_own_assists_count_on_the_server(self):
        """VehicleList "Car Assist": TOYOTA FT-86 a_mito_100 + a_00190 (Exp +100%), Porsche 918 a_00125 (speedup)."""
        from dcemu.native.game import assists
        from dcemu.native.game.records import Car
        assists._by_index = None
        types = {v['Car Name']: k for k, v in self.t.vehicles.items()}
        self.p.items, self.p.vsitems = [], []
        self.p.car = Car(1, types['TOYOTA FT-86'], 2, 1, 0, 100, 0, 0)
        got = assists.totals(self.p)
        self.assertEqual((got['exp'], got['mito']), (100, 100))
        with patch.object(items, 'holds', return_value=False), patch.object(items, 'bacchus_left', return_value=0), \
                patch('dcemu.native.game.licenses.bonus', return_value=(0, 0)), \
                patch('dcemu.native.game.mita500.bonus_rate', return_value=100):
            self.assertEqual(items.play_bonus(self.p, exp=500, money=300), (1000, 600))
        self.p.car = Car(2, next(k for k, v in self.t.vehicles.items() if 'a_00125' in v['Car Assist'].split()),
                         2, 1, 0, 100, 0, 0)                   # a Porsche 918 grade with a_00125
        self.assertGreater(assists.totals(self.p)['speedup'], 0)

    def test_gotcha_2016_prices_and_groups(self):
        from dcemu.native.game import gotcha, driftuse
        driftuse._groups = None
        context.gotcha_mito_price = context.gotcha_coin_price = 0
        self.assertEqual([gotcha.price(c, m, 20) for c, m in ((0, 0), (1, 0), (0, 1), (1, 1))], [50000, 300, 25000, 300])
        self.assertEqual(gotcha.group_for(True, 0, 0), 'rw_cash_gacha_2015')       # the car machine: season 0
        self.assertEqual(gotcha.group_for(False, 0, 0), 'rw_mito_gacha_2015')
        self.assertEqual(struct.unpack('<IIII', gotcha.prize_event([('NormalItem', 'i_n_gacha_point', 0, 10)]).payload),
                         (23, self.t.item_index['i_n_gacha_point'], 10, 0))
        self.assertEqual(gotcha.group_for(True, 1, 60), 'rw_gacha_parts_cash_60')
        version.configure({'version': '2011'})                       # 2011 unchanged
        self.assertEqual([gotcha.price(c, m, 9) for c, m in ((0, 0), (1, 0), (0, 1))], [10000, 540, 10000])
        driftuse._groups = None

    def test_2016_reward_groups_roll(self):
        """RewardGroup.xlt 2016 has Probability at column 11 (Trade Restriction at 10): read by its header."""
        driftuse._groups = None
        won = [driftuse.roll('rw_cash_gacha_2015') for _ in range(50)]
        self.assertTrue(all(len(w) == 1 for w in won))
        self.assertTrue(all(w[0][1] == 'i_n_gacha_point' or w[0][1].startswith('i_n_box_') for w in won))
        driftuse._groups = None

    def run_items(self, fn, frame):
        sent, given = [], []

        async def give(p, item_id, count, gains):
            given.append((item_id, count))
        with patch.object(items, 'send', lambda s, *f: sent.extend(f)), patch.object(items, 'error') as err, \
                patch('dcemu.native.game.driftuse.give_item', give):
            self.run_(fn(self.s, frame))
        return sent, given, err

    def test_100_capsule_points_make_an_st_ticket(self):
        pts = item(self.t, 6, 'i_n_gacha_point', 100)
        self.p.items = [pts]
        sent, given, err = self.run_items(items.use_item, Frame(0x1a1, struct.pack('<II', 6, 1)))
        err.assert_not_called()
        self.assertEqual(given, [('i_n_ticket_st_100per', 1)])
        self.assertEqual(self.p.items, [])                                  # all 100 used
        pts = item(self.t, 7, 'i_n_gacha_point', 90)
        self.p.items = [pts]
        sent, given, err = self.run_items(items.use_item, Frame(0x1a1, struct.pack('<II', 7, 1)))
        err.assert_called()
        self.assertEqual((given, pts.stack), ([], 90))                       # not enough: nothing used

    def test_stacks_merge(self):
        a, b = item(self.t, 8, 'i_n_gacha_point', 60), item(self.t, 9, 'i_n_gacha_point', 50)
        self.p.items = [a, b]
        with patch('dcemu.native.game.setparts.start_expiry', AsyncMock()):
            sent, _, err = self.run_items(items.item_union, Frame(0x19f, struct.pack('<II', 8, 9)))
        err.assert_not_called()
        self.assertEqual(b.stack, 10)                                         # stack size 100: 50 moved
        self.assertEqual((a.item_id, a.stack), ('i_n_ticket_st_100per', 1))    # the full stack became the ticket
        self.assertEqual(sent[0].type, 0x1a0)

    def test_login_merge_stacks_not_shadowed(self):
        """login.load_char calls items.merge_stacks(p): a handler of the same name once hid it (stuck at loading)."""
        import inspect
        self.assertEqual(list(inspect.signature(items.merge_stacks).parameters), ['p'])

    def test_full_piece_stack_becomes_its_item(self):
        """2008 AddItem -> IsFullPiece -> ChangeNextItem: 90 + 10 Capsule Points -> the ST Vehicle Ticket (stack 1)."""
        pts = item(self.t, 10, 'i_n_gacha_point', 90)
        self.p.items = [pts]
        with patch('dcemu.native.game.setparts.start_expiry', AsyncMock()):
            self.run_(driftuse.give_item(self.p, 'i_n_gacha_point', 10, driftuse.Gains()))
        self.assertEqual((pts.item_id, pts.stack, pts.table_idx),
                         ('i_n_ticket_st_100per', 1, self.t.item_index['i_n_ticket_st_100per']))
        more = item(self.t, 11, 'i_n_gacha_point', 40)
        self.p.items.append(more)
        with patch('dcemu.native.game.setparts.start_expiry', AsyncMock()):
            self.run_(driftuse.give_item(self.p, 'i_n_gacha_point', 10, driftuse.Gains()))
        self.assertEqual((more.item_id, more.stack), ('i_n_gacha_point', 50))   # not full: stays points

    def test_rental_pack_gives_the_picked_capsule(self):
        """rent_period_rep_s ("p_s") + item text 20954 (pc_rent_gigasmini_p, "213 0 1") -> that capsule."""
        self.assertEqual(driftuse.parse_value('p_s', '20954'), ('pc_rent_gigasmini_p', 1))
        self.assertEqual(driftuse.parse_value('f_s', '20960'), ('pc_rent_gigasmini_f', 1))
        self.assertIsNone(driftuse.parse_value('p_f', '20954'))                  # a small car in the large pack
        self.assertIsNone(driftuse.parse_value('f_s', '20954'))                  # time-limited car, meter-rated pack
        self.assertIsNone(driftuse.parse_value('p_s', ''))
