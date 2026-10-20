"""Perfect Base: dropped / rewarded parts get a random base bonus (2008 ItemRandValue), shop parts none."""
import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import items

DATA = {2011: ('server_data', 'server_data/tables'), 2016: ('server_data_2016', 'server_data_2016/tables')}


class PerfectBaseTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        context.random_base = True

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def tables(self, year):
        root, tables = DATA[year]
        if not os.path.exists(f'{tables}/ItemClient.tdf'):
            self.skipTest(f'needs the {year} client tables')
        version.configure({'version': str(year)})
        return Tables(root, tables)

    def test_roll_stays_in_the_table_range_both_versions(self):
        for year in (2011, 2016):
            with self.subTest(year=year):
                t = self.tables(year)
                small = t.item_info(t.item_index['i_s_000001'])        # Small: value 1, columns 10 / 11 = 0 / 2
                self.assertEqual(small.base_range, (0, 2))
                rolls = {items.roll_base(small) for _ in range(300)}
                self.assertEqual(rolls, {0, 1, 2})                       # both ends included (lo + rand % (hi-lo+1))
                self.assertEqual(items.roll_base(small, perfect=True), 2)
                use = t.item_info(t.item_index['i_n_00040'])
                self.assertEqual(items.roll_base(use), 0)                # usable items: none
                context.random_base = False
                self.assertEqual(items.roll_base(small), 0)
                context.random_base = True

    def test_new_item_rolls_unless_given(self):
        t = self.tables(2011)
        context.data = t
        context.db = SimpleNamespace(server_id=1, execute=AsyncMock(), row=AsyncMock(return_value=(77,)))
        p = SimpleNamespace(char=SimpleNamespace(cid=1, name='T', part_inven_idx=0), items=[], tick=0)
        big = t.item_info(t.item_index['i_s_000003'])                  # Big: 0 .. 3
        got = {asyncio.run(items.new_item(p, big, 1)).random for _ in range(200)}
        self.assertTrue(got <= {0, 1, 2, 3} and len(got) > 1)
        self.assertEqual(asyncio.run(items.new_item(p, big, 1, 0)).random, 0)   # the shop's explicit 0
