"""XiVisualItem of other players' cars: neon @0 (colour u32 @0xa), plate @2 (text @0x26), decal @4 (colour u32 @6) as the car model reads them
(2011 0x468100, 2016 0x471170); the aero slots from @0xe."""
import os
import struct
import unittest
from types import SimpleNamespace as N

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import misc
from dcemu.native.game.records import VisualItem

DATA = {2011: 'server_data', 2016: 'server_data_2016'}


class VisualItemTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def test_decal_and_its_colour(self):
        for year, root in DATA.items():
            with self.subTest(year=year):
                if not os.path.exists(f'{root}/tables/ItemClient.tdf'):
                    self.skipTest(f'needs the {year} client tables')
                version.configure({'version': str(year)})
                t = context.data = Tables(root, f'{root}/tables')
                decal = next(k for k, v in t.visual_index.items() if k.startswith('i_g_d_'))
                bumper = next(k for k, v in t.visual_index.items()
                              if t.visuals[v].category == 4 and t.visuals[v].index)
                neon = next(k for k, v in t.visual_index.items() if t.visuals[v].category == 2 and t.visuals[v].index > 6)
                plate = next(k for k, v in t.visual_index.items() if t.visuals[v].category == 9 and t.visuals[v].index)
                vs = []
                for item_id, data in ((decal, '-16185079'), (bumper, ''), (neon, '16382457'), (plate, 'Xerender')):
                    v = VisualItem(1, item_id, 1, 5, 1, data, 0, 0, 0)
                    v.table_idx = t.visual_index[item_id]
                    vs.append(v)
                out = misc.visual_item(N(car=N(car_id=5, car_type=50), vsitems=vs))
                self.assertEqual(struct.unpack_from('<h', out, 4)[0], t.visuals[t.visual_index[decal]].index)
                self.assertEqual(struct.unpack_from('<I', out, 6)[0], 0xff090909)
                self.assertEqual(struct.unpack_from('<h', out, 0xe)[0], t.visuals[t.visual_index[bumper]].index)
                self.assertEqual(struct.unpack_from('<hh', out, 0), (t.visuals[t.visual_index[neon]].index,
                                                                      t.visuals[t.visual_index[plate]].index))
                self.assertEqual(struct.unpack_from('<I', out, 0xa)[0], 0xf9f9f9)              # neon colour
                self.assertEqual(out[0x26:0x36].decode('utf-16le'), 'Xerender')              # plate text
