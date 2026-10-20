"""2016 Part Option Extractor (0xfc1 -> 0xfc2): extract, apply and the refusals, on the 2016 tables."""
import asyncio
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import convert, extractor
from dcemu.native.game.records import Item
from dcemu.wire import Frame

DATA = 'server_data_2016'


@unittest.skipUnless(os.path.exists(f'{DATA}/tables/ItemClient.tdf'), 'needs the 2016 client tables (tools.client_setup)')
class Extractor2016Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = Tables(DATA, f'{DATA}/tables', f'{DATA}/adminlist.txt')

    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = t = self.tables
        context.option_parts = False
        self.gid = iter(range(5000, 6000))
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock(),
                                     row=AsyncMock(side_effect=lambda *a: (next(self.gid),)))
        self.p = SimpleNamespace(char=SimpleNamespace(cid=7, name='T', part_inven_idx=100), items=[], tick=1000)
        self.sent = []
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()),
                                 to_client=lambda f: self.sent.append(f))
        extractor.send = lambda s, *f: self.sent.extend(f)
        self.row = convert.rows()[10]                       # a tradeable tier (row 11)

    def tearDown(self):
        from dcemu.native.game import login
        extractor.send = login.send
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def item(self, inven, item_id, a='', b='', car=0, state=0, ctime=0):
        t = self.tables
        it = Item(1000 + inven, inven, item_id, car, 1, 0, state, 0, 0, a, b, 0, ctime, t.item_index[item_id])
        self.p.items.append(it)
        return it

    def use(self, part, tool, fresh):
        self.sent.clear()
        asyncio.run(extractor.transfer(self.s, Frame(0xfc1, struct.pack('<IIB', part.inven_idx, tool.inven_idx, fresh))))
        return struct.unpack('<H', self.sent[0].payload)[0]

    def test_extract_then_apply_moves_both_options(self):
        a, b = self.row[0], self.row[1]
        source = self.item(1, 'i_s_000001', a, b)
        target = self.item(2, 'i_c_000001', 'x', 'y')
        tool = self.item(3, 'i_n_assist_transfer', ctime=1500)
        self.assertEqual(self.use(source, tool, 1), 0)
        self.assertEqual([f.type for f in self.sent], [0xfc2, 0x192])
        held = next(i for i in self.p.items if i.item_id == 'i_n_assist_transfer_used')
        self.assertEqual((held.assist_a, held.assist_b, held.ctime), (a, b, 1500))
        self.assertEqual((source.assist_a, source.assist_b, source.belonging), ('', '', 0))
        self.assertNotIn(tool, self.p.items)
        self.assertEqual(self.use(target, held, 0), 0)
        self.assertEqual((target.assist_a, target.assist_b), (a, b))
        self.assertNotIn(held, self.p.items)

    def test_refusals_use_the_client_codes(self):
        bare = self.item(1, 'i_s_000001')
        on_car = self.item(2, 'i_s_000001', 'x', 'y', car=9, state=1)
        tool = self.item(3, 'i_n_assist_transfer', ctime=1500)
        old = self.item(4, 'i_n_assist_transfer', ctime=900)
        converted = self.item(5, 'i_s_000001', self.row[0], self.row[1])
        self.assertEqual(self.use(bare, tool, 1), extractor.NOT_VALID)          # no options to extract
        self.assertEqual(self.use(on_car, tool, 1), extractor.EQUIPPED)
        self.assertEqual(self.use(converted, old, 1), extractor.EXPIRED)
        self.assertEqual(self.use(converted, converted, 1), extractor.NOT_VALID)   # not an extractor
        self.assertEqual(len(self.sent), 1)                                      # nothing changed
        version.configure({'version': '2011'})
        self.sent.clear()
        asyncio.run(extractor.transfer(self.s, Frame(0xfc1, struct.pack('<IIB', 5, 3, 1))))
        self.assertEqual(self.sent, [])                                          # 2016 only
