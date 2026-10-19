"""Training car persistence, starter validation, and both client completion layouts."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu import commands
from dcemu.native import context, version
from dcemu.native.game import apprentice, items, login, rooms
from dcemu.native.game.records import Car
from dcemu.wire import Frame
from tests.test_version import character


class ApprenticeTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({})
        context.extra_flags = {}
        context.data = SimpleNamespace(vehicles={29: {'Sellable': '10001'}, 999: {'Sellable': '1'}},
                                       upgrade={(29, 1): {'capacity': 100, 'efficiency': 2}})
        context.db = SimpleNamespace(server_id=2016, row=AsyncMock(return_value=(43, 12345)))
        c = character()
        c.pos_state, c.city = 3, 0
        c.cars = [Car(42, 95, 0x01000002, 1, 0, 106, 0, apprentice.TRAINING_SLOT)]
        self.p = SimpleNamespace(char=c, car=c.cars[0], apply_paints=Mock())
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()),
                                 to_client=Mock())

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def test_marker_and_legacy_switch(self):
        self.assertTrue(apprentice.enabled())
        context.extra_flags['Main.Apprentice'] = 0
        self.assertFalse(apprentice.enabled())
        self.assertTrue(login.in_tutorial(self.p))
        self.p.car.slot = 0
        self.assertFalse(apprentice.training_car(self.p.car))
        self.assertFalse(login.in_tutorial(self.p))

    def test_wire_both_versions(self):
        car = Car(43, 29, 2, 1, 0, 100, 0, 0)
        for year, length, tail in ((2011, 0x4f, 0x43), (2016, 0x50, 0x44)):
            version.configure({'version': str(year)})
            f = apprentice.completion_ack(42, car, 2**40, 123)
            raw = struct.pack('<H', f.type) + f.payload
            self.assertEqual(len(raw), length)
            self.assertEqual(struct.unpack_from('<I', raw, 10)[0], 42)
            self.assertEqual(struct.unpack_from('<I', raw, 18)[0], 43)
            self.assertEqual(struct.unpack_from('<iq', raw, tail), (0, 2**40))
        self.assertEqual(commands.size_2008(struct.pack('<H4I', 0x5d2, 0, 123, 29, 2)), 18)

    def test_complete_replaces_car_and_preserves_field_intro(self):
        with patch.object(items, 'link_keys', AsyncMock(return_value=[])), \
                patch.object(login, 'stat_frames', return_value=()):
            asyncio.run(apprentice.complete(self.s, Frame(0x5d2, struct.pack('<4I', 0, 123, 29, 2))))
        c = self.p.char
        self.assertEqual([v.car_id for v in c.cars], [43])
        self.assertEqual((c.cur_car, c.pos_state, c.city, c.last_area), (43, 0, 1, -1))
        self.assertEqual(c.mito, 12345)
        self.assertEqual(self.s.to_client.call_args.args[0].type, 0x5d3)
        self.p.car = c.cars[0]
        asyncio.run(apprentice.complete(self.s, Frame(0x5d2, struct.pack('<4I', 0, 123, 29, 2))))
        context.db.row.assert_awaited_once()

    def test_invalid_and_replayed_completion_do_not_change_character(self):
        for payload in (bytes(15), struct.pack('<4I', 0, 123, 999, 2), struct.pack('<4I', 1, 123, 29, 2)):
            asyncio.run(apprentice.complete(self.s, Frame(0x5d2, payload)))
        context.db.row.assert_not_awaited()
        context.db.row.return_value = (-1, 12345)
        asyncio.run(apprentice.complete(self.s, Frame(0x5d2, struct.pack('<4I', 0, 123, 29, 2))))
        self.assertEqual(self.p.char.cur_car, 42)
        self.s.to_client.assert_not_called()

    def test_training_car_gets_no_permanent_key(self):
        self.p.items = []
        context.data.item_index = {'training': 1}
        context.data.vehicles[95] = {'File Name': 'training.nif'}
        with patch.object(items, 'new_item', AsyncMock()) as make:
            self.assertEqual(asyncio.run(items.link_keys(self.p)), [])
            make.assert_not_awaited()

    def test_local_training_start_does_not_replace_lessons_with_practice(self):
        for year in (2011, 2016):
            version.configure({'version': str(year)})
            with patch.object(rooms, 'send') as send:
                rooms.practice(self.s, struct.pack('<iii', 11, 0, 123))
                send.assert_not_called()

    def test_permanent_car_still_gets_normal_practice(self):
        self.p.car.slot = 0
        self.s.id = 12
        with patch.object(rooms, 'send') as send:
            rooms.practice(self.s, struct.pack('<iii', 11, 0, 123))
        frame = send.call_args.args[1]
        self.assertEqual(frame.type, 0x1e7)
        self.assertEqual(struct.unpack('<iiiifii', frame.payload), (100, 11, 0, 20012, 0.0, 123, -1))
