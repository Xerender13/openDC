"""2016 rental redemption: captured request, durable terms, options and rejection paths."""
import asyncio
from contextlib import ExitStack
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import driftuse, rentals
from dcemu.native.game.player import Player
from dcemu.native.game.records import Car, Item
from dcemu.wire import Frame
from tests.test_version import character


@unittest.skipUnless(os.path.exists('server_data_2016/tables/ItemClient.tdf'), 'needs 2016 client tables')
class RentalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = Tables('server_data_2016', 'server_data_2016/tables', 'server_data_2016/adminlist.txt')

    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = self.tables
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock(), row=AsyncMock(return_value=(77, 10000, 200)),
                                     rows=AsyncMock(return_value=[]))
        c = character()
        c.cars = [Car(42, 50, 0x01010102, 9, 0, 40., 0., 0, 40., 5.)]
        c.part_inven_idx = 200
        self.it = Item(1115, 115, 'pc_rent_gigasmini_p', 0, 1, 7, 0, 0, 0, '', '', 0, 0,
                       self.tables.item_index['pc_rent_gigasmini_p'])
        self.p = Player(c, [self.it], [], [], (0,) * 10, 0)
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()), to_client=Mock())
        self.sent = []
        self.payload = struct.pack('<11I', 213, 9, 1, 1, 0, 115, 7, 280, 185, 250, 85)

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def redeem(self, payload=None):
        with patch.object(rentals, 'send', side_effect=lambda s, *f: self.sent.extend(f)), \
                patch.object(rentals, 'stat_frames', return_value=()), \
                patch('dcemu.native.game.cars.visual_update', return_value=Frame(0x425, b'')):
            asyncio.run(rentals.redeem(self.s, Frame(0xfb4, self.payload if payload is None else payload)))

    def test_captured_request_creates_rental_and_equipped_options(self):
        with patch.object(rentals, 'now', return_value=100000):
            self.redeem()
        self.assertNotIn(self.it, self.p.items)
        car = self.p.car
        self.assertEqual((car.car_id, car.car_type, car.grade), (77, 213, 9))
        self.assertEqual(car.rental.expires, 100000 + 7 * 86400)
        self.assertEqual(self.p.stats().based, (280, 85, 185, 250))
        self.assertEqual(self.p.stats().equip, (0, 800, 0, 1))
        self.assertEqual(len(self.p.items), 8)
        self.assertTrue(all(i.car_id == 77 and i.state & 0xffff == 1 for i in self.p.items))
        self.assertEqual(len({i.state >> 16 for i in self.p.items}), 8)
        self.assertEqual(struct.unpack_from('<H', car.encode(), 0x12)[0], 1)
        record = car.rental.encode(77)
        self.assertEqual(len(record), 61)
        self.assertEqual(struct.unpack_from('<4I', record), (280, 185, 250, 85))
        self.assertEqual(record[28:60].split(b'\0')[0], b'a_00118')
        types = [f.type for f in self.sent]
        self.assertLess(types.index(0xfb6), types.index(0xfb5))
        calls = context.db.row.await_count
        self.redeem()
        self.assertEqual(context.db.row.await_count, calls)

    def test_bad_car_points_or_options_keep_capsule(self):
        for field, value in ((0, 214), (1, 1), (3, 4), (4, 4), (5, 999), (6, 30), (7, 281), (10, 0)):
            data = bytearray(self.payload)
            struct.pack_into('<I', data, field * 4, value)
            self.redeem(bytes(data))
            self.assertIn(self.it, self.p.items)
        context.db.row.assert_not_awaited()

    def test_2011_cannot_redeem(self):
        version.configure({'version': '2011'})
        self.redeem()
        context.db.row.assert_not_awaited()
        self.s.to_client.assert_not_called()

    def test_database_failure_preserves_capsule_and_garage(self):
        context.db.row.return_value = (-1,)
        self.redeem()
        self.assertEqual(self.p.items, [self.it])
        self.assertEqual(len(self.p.char.cars), 1)

    def test_rental_expiry_uses_2012_epoch_and_utc_clock(self):
        # Client compares the wire end with GetSystemTime minus 2012-01-01, not time_t.
        from dcemu.native import CLOCK_SHIFT
        utc_now = 1792486800
        r = rentals.Rental(1, utc_now + CLOCK_SHIFT + 86400, 150, 150, 250, 50, 0, 0)
        wire_end, = struct.unpack_from('<I', r.encode(7), 20)
        self.assertEqual(wire_end - (utc_now - rentals.RENTAL_EPOCH), 86400)

    def test_capsule_term_is_encoded_only_for_2016(self):
        self.assertEqual(struct.unpack_from('<I', self.it.encode(), 0x50)[0], 7)
        self.assertEqual(len(self.it.encode(version=2011)), 0x5c)

    def test_purchase_retains_term_in_new_capsule(self):
        vis = self.tables.visuals[self.tables.visual_index['rent_period_rep_s']]
        gains = driftuse.Gains()
        with patch.object(driftuse, 'new_item', AsyncMock(return_value=self.it)) as give:
            self.assertTrue(asyncio.run(driftuse.instant(self.s, self.p, vis, gains, '20954', rental_days=30)))
        self.assertEqual(give.call_args.kwargs['random'], 30)

    def test_metadata_reloads_and_2011_does_not_query_it(self):
        context.db.rows.return_value = [(42, 1, 9999999999, 280, 185, 250, 85, 1, 0)]
        asyncio.run(rentals.load(self.p))
        self.assertEqual(self.p.car.rental.stats, (280, 85, 185, 250))
        context.db.rows.reset_mock()
        version.configure({'version': '2011'})
        asyncio.run(rentals.load(self.p))
        context.db.rows.assert_not_awaited()

    def test_2016_login_reaches_rental_list_and_remaining_initialization(self):
        from dcemu.native.game import login
        from dcemu.native.game.records import wstr
        self.p.items = []
        async_targets = {
            'login.player.load': self.p, 'login.admin.account_valid': True,
            'login.admin.blocks': (False, 0), 'auction.mark_cars': None,
            'items.merge_stacks': False, 'driftuse.convert_bundles': None,
            'quests.give_up_at_login': None, 'items.link_keys': [],
            'daymission.info_frame': Frame(0x488, b''), 'alchemy.load': None,
            'licenses.on_login': None, 'mothers.on_login': None,
        }
        sent = []
        with ExitStack() as stack:
            for target, result in async_targets.items():
                stack.enter_context(patch('dcemu.native.game.' + target, AsyncMock(return_value=result)))
            stack.enter_context(patch.object(login.admin, 'find', return_value=None))
            stack.enter_context(patch.object(login, 'content_flags', return_value=bytes(96)))
            stack.enter_context(patch('dcemu.native.game.championship.speed_flags', return_value={}))
            stack.enter_context(patch.object(login, 'stat_frames', return_value=()))
            stack.enter_context(patch('dcemu.native.game.alchemy.info_frame', return_value=Frame(0xe75, b'')))
            stack.enter_context(patch.object(login, 'send', side_effect=lambda s, *frames: sent.extend(frames)))
            asyncio.run(login.load_char(self.s, Frame(0x7b, wstr(self.p.char.name, 42))))
        self.assertIn(0xfb6, [f.type for f in sent])
        self.assertTrue(self.s.state['rental_ready'])

    def test_expired_rental_returns_to_owned_car_and_removes_gear(self):
        with patch.object(rentals, 'now', return_value=100000):
            self.redeem()
        self.p.car.rental.expires = 1
        with patch.object(rentals, 'send', side_effect=lambda s, *f: self.sent.extend(f)), \
                patch.object(rentals, 'stat_frames', return_value=()), \
                patch('dcemu.native.game.cars.visual_update', return_value=Frame(0x425, b'')):
            asyncio.run(rentals.expire(self.s, self.p))
        self.assertEqual(self.p.char.cur_car, 42)
        self.assertEqual(len(self.p.char.cars), 1)
        self.assertEqual(self.p.items, [])
