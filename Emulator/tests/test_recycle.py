"""Item Recycling Kit (driftuse.recycle, 0x4bf -> 0x4c0) with stub sessions."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context
from dcemu.native.game import driftuse
from dcemu.wire import Frame

KIT, MITRON = 1092, 3
DRINK = 10700


class RecycleTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        kinds = {KIT: SimpleNamespace(kind='item_recycle', reward='rw_item_recycle', name='Item Recycling Kit'),
                 MITRON: SimpleNamespace(kind='upgrade', reward='', name='Mitron Enhancer')}
        context.data = SimpleNamespace(item_info=lambda i: kinds[i], item_index={'i_n_00003': MITRON},
                                       visuals={DRINK: SimpleNamespace(name='EXP Drink', item_id='i_d_exp')},
                                       visual_index={'i_d_exp': DRINK})
        self.sent = []
        self.drift = []
        self.given = []

        async def give_drift_item(p, item_id, days, gains, session):
            self.drift.append((item_id, days))

        async def give(session, p, rewards, gains):
            self.given += rewards

        async def take_one(p, it):
            it.stack -= 1
            return it, 3

        self.use_up = AsyncMock()
        for target in (patch.multiple(driftuse, send=lambda s, *f: self.sent.extend(f), give=give,
                                      give_drift_item=give_drift_item, take_one=take_one, use_up=self.use_up),
                       patch.object(driftuse.Gains, 'send', Mock()),
                       patch('dcemu.native.admin.message', Mock()),
                       patch('dcemu.native.game.vshop.vs_mod_list', lambda *changes: Frame(0x4b2, b''))):
            target.start()
            self.addCleanup(target.stop)
        self.kit = SimpleNamespace(table_idx=KIT, stack=2)
        self.item = SimpleNamespace(inven_idx=70, table_idx=DRINK, item_id='i_d_exp', state=0, period=1, ctime=1)
        self.p = SimpleNamespace(items=[self.kit], vsitems=[self.item])
        self.session = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()))

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def recycle(self, won):
        with patch.object(driftuse, 'roll', return_value=won):
            asyncio.run(driftuse.recycle(self.session, Frame(0x4bf, struct.pack('<I', 70))))
        return [struct.unpack('<II', f.payload) for f in self.sent if f.type == 0x4c0]

    def test_same_item_for_days(self):
        self.assertEqual(self.recycle([('Recycle', '', 3, 1, 0)]), [(DRINK, 1)])
        self.assertEqual(self.kit.stack, 1)
        self.use_up.assert_awaited_once()
        self.assertEqual(self.drift, [('i_d_exp', 3)])

    def test_other_prize(self):
        self.assertEqual(self.recycle([('NormalItem', 'i_n_00003', 0, 5, 0)]), [(DRINK, 1)])
        self.assertEqual(self.given, [('NormalItem', 'i_n_00003', 0, 5, 0)])
        self.assertEqual(self.drift, [])

    def test_refused_when_not_expired_or_without_kit(self):
        self.item.ctime = 2 ** 40                       # still running
        self.assertEqual(self.recycle([]), [(DRINK, 0)])
        self.item.ctime, self.kit.stack = 1, 0
        self.sent.clear()
        self.assertEqual(self.recycle([]), [(DRINK, 0)])
        self.use_up.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
