"""Major channel stake entries (0x38d / 0x391 / 0x392): XiCBattleItemInfo is 0x88 bytes in 2011, 0x8c in 2016 (the
item unit grows by the 2016 item record's new dword; timeline.slide.town size diffs, 2015-06-17 US 0.69a)."""
import unittest
from unittest.mock import patch

from dcemu.native import context, version
from dcemu.native.game import channels
from dcemu.native.game.records import Item


class StakeEntryTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def entry(self, year):
        version.configure({'version': str(year)})
        it = Item(1001, 1, 'p_test', 0, 1, 0, 0, 0, 0, '', '', 0, 0, 5)
        with patch('dcemu.native.game.mail.item_text', return_value=''):
            return channels.Stake(1, 7, 'T', it).entry()

    def test_sizes(self):
        self.assertEqual(len(self.entry(2011)), 0x88)
        self.assertEqual(len(self.entry(2016)), 0x8c)


if __name__ == '__main__':
    unittest.main()
