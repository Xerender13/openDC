"""Neo City HP sync (neocity.py): 0xf4d -> 0xf4e, base ^ hp (docs/NEOCITY.md)."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import neocity
from dcemu.wire import Frame


class NeoCityHpTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.db = SimpleNamespace(server_id=2016)
        neocity._hp.clear()
        self.p = SimpleNamespace(char=SimpleNamespace(cid=77))
        self.s = SimpleNamespace(state={'player': self.p}, log=Mock())

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        neocity._hp.clear()
        version.configure({'version': '2011'})

    def poll(self, base=0x111a):
        sent = []
        with patch.object(neocity, 'send', side_effect=lambda s, f: sent.append(f)):
            asyncio.run(neocity.hp_sync(self.s, Frame(0xf4d, struct.pack('<I', base))))
        return sent

    def test_full_hp_default(self):
        self.assertEqual(neocity.hp_of(self.s), neocity.MAX_HP)

    def test_answer_is_base_xor_hp(self):
        """Handler 0x53e630 stores [player+0x1da4] = [player+0x1da0] ^ value, 0-20000 only."""
        sent = self.poll(0x111a)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].type, 0xf4e)
        value, = struct.unpack_from('<I', sent[0].payload)
        self.assertEqual(value, 0x111a ^ neocity.MAX_HP)
        self.assertEqual(value ^ 0x111a, neocity.MAX_HP)      # what the client decodes

    def test_damage_and_heal_clamp(self):
        neocity.damage(self.s, 5000)
        self.assertEqual(neocity.hp_of(self.s), neocity.MAX_HP - 5000)
        value, = struct.unpack_from('<I', self.poll(0)[0].payload)
        self.assertEqual(value, neocity.MAX_HP - 5000)
        neocity.damage(self.s, 10 ** 9)
        self.assertEqual(neocity.hp_of(self.s), 0)
        neocity.heal(self.s, 10 ** 9)
        self.assertEqual(neocity.hp_of(self.s), neocity.MAX_HP)

    def test_2011_ignores_it(self):
        """The 2011 client has no 0xf4d sender."""
        version.configure({'version': '2011'})
        self.assertEqual(self.poll(), [])


class NeoCityFlagsTest(unittest.TestCase):
    """Stage 1: the region is gated by content flags the 2008 Contents.ini has no entry for."""
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_flags_exist_and_pack(self):
        version.configure({'version': '2016'})
        for name in ('City.NeoCity', 'City.NeoOros', 'City.Cras', 'City.NeoCras', 'City.NeoKoinonia',
                     'City.NeoMoonPalace'):
            self.assertIn(name, version.flag_table(), name)
        out = version.pack_flags({'City.NeoCity': 1, 'City.NeoOros': 1})
        value, = struct.unpack_from('<I', out, 0x14)     # flags_2016.tsv: City.NeoCity 0x14 bit 21
        self.assertTrue(value & (1 << 21))
        self.assertTrue(value & (1 << 22))

    def test_2011_flag_offsets_differ(self):
        """The 2011 client keeps the same names at another offset (0x10), so the tables must not be mixed."""
        version.configure({'version': '2011'})
        self.assertEqual(version.flag_table()['City.NeoCity'][:2], (0x10, 21))
        version.configure({'version': '2016'})
        self.assertEqual(version.flag_table()['City.NeoCity'][:2], (0x14, 21))
