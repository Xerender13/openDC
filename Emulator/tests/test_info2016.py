"""2016 player profile (0x294 -> 0x295) and crew messages: the layouts measured in the 2016 client."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import crews, misc
from dcemu.native.game.records import Stats
from dcemu.wire import Frame
from tests.test_version import car, character


class Info2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.sent = []

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def char_info(self, year):
        version.configure({'version': str(year)})
        c = character()
        c.team_id = 0
        p = SimpleNamespace(char=c, car=car(), stats=lambda: Stats())
        target = SimpleNamespace(state={'player': p, 'serial': 0x1234})
        with patch.object(misc, 'online', return_value=target), \
                patch.object(misc, 'send', lambda s, *f: self.sent.extend(f)):
            asyncio.run(misc.game_char_info(SimpleNamespace(), Frame(0x294, 'Driver'.encode('utf-16le').ljust(0x2e, b'\0'))))
        return self.sent[-1].payload

    def test_2016_profile_layout(self):
        out = self.char_info(2016)
        self.assertEqual(len(out) + 2, 0x499)                         # handler 0x529160 returns 0x499
        self.assertEqual(struct.unpack_from('<qq', out, 0x1e3), (-1, -1))   # no crew: team @0x1e3 (packet 0x1e5)
        self.assertEqual(struct.unpack_from('<II', out, 0x47b), (0x1234, 2))  # serial @0x47d, city after it
        self.assertEqual(struct.unpack_from('<H', out, 0x141 + 4)[0], 50)    # car record @0x143: its type

    def test_2011_profile_unchanged(self):
        out = self.char_info(2011)
        self.assertEqual(len(out), misc.CHAR_INFO_ACK)
        self.assertEqual(struct.unpack_from('<I', out, 0x334)[0], 0x1234)

    def test_team_record_sizes(self):
        for year, size in ((2011, 384), (2016, 664)):
            version.configure({'version': str(year)})
            self.assertEqual(len(crews.info_bytes(None)), size)
            t = dict(tid=5, mark=6, name='Crew', desc='d', url='u', created=1, closed=0, state='A', banish=0,
                     channels='', ranking=1, point=2, wins=3, count=4, exp=5, money=6, master=7, master_name='M')
            self.assertEqual(len(crews.info_bytes(t)), size)


class VisualItem2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_drift_item_record_sizes(self):
        from dcemu.native.game.records import VisualItem
        with patch.object(VisualItem, 'assist_slots', return_value=bytes(48)):
            for year, size in ((2011, 0x74), (2016, 0x78)):      # 0x4b1 handlers: 0x74 / 0x78 per record
                version.configure({'version': str(year)})
                self.assertEqual(len(VisualItem(1, 'x', 1, 0, 0, '', 0, 0, 0, 5).encode()), size)
