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


class WhisperDeny2016Test(unittest.TestCase):
    def test_refusal_goes_to_the_whisperer_with_the_refusing_name(self):
        """C>S 0xfb3 (client 0x847000: wchar[20] the whisperer, 4 bytes) -> S>C 0xfb3 to the whisperer (handler
        0x521830: the name at @2, 0x2e bytes with the type)."""
        from dcemu.native.game import session as game_session
        me = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='Refuser'))}, log=Mock())
        other = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='Talker'))}, log=Mock())
        sent = []
        body = 'Talker'.encode('utf-16-le').ljust(40, b'\0') + bytes(4)
        with patch('dcemu.native.game.misc.online', side_effect=lambda n: other if n == 'Talker' else None), \
                patch.object(game_session, 'send', side_effect=lambda s, f: sent.append((s, f))):
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, body)))
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, 'Nobody'.encode('utf-16-le').ljust(44, b'\0'))))
            asyncio.run(game_session.whisper_deny(me, Frame(0xfb3, b'short')))
        self.assertEqual(len(sent), 1)
        self.assertIs(sent[0][0], other)
        self.assertEqual(sent[0][1].type, 0xfb3)
        self.assertEqual(len(sent[0][1].payload) + 2, 0x2e)
        self.assertEqual(sent[0][1].payload[:40].decode('utf-16-le').rstrip('\0'), 'Refuser')


class CrewApply2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def run_apply(self, year):
        version.configure({'version': str(year)})
        c = SimpleNamespace(cid=7, name='Applicant', level=30)
        me = SimpleNamespace(state={'player': SimpleNamespace(char=c), 'serial': 5}, log=Mock())
        master = object()
        t = {'tid': 100001, 'name': 'Drifters', 'master': 1}
        sent = []
        with patch.object(crews, 'apply_checks', AsyncMock(return_value=None)), \
                patch.object(crews, 'online_member', return_value=master), \
                patch.object(crews, 'send', side_effect=lambda s, f: sent.append((s, f))):
            asyncio.run(crews.apply(me, t, b''))
        return me, master, sent

    def test_2016_applicant_gets_0x36e(self):
        """0x36e (client 0x546720, 0x5e bytes with the type): wchar[13] crew name @2, the 66-byte bind @0x1c."""
        me, master, sent = self.run_apply(2016)
        self.assertEqual([(s, f.type) for s, f in sent], [(master, 0x367), (me, 0x36e)])
        ack = sent[1][1].payload
        self.assertEqual(len(ack) + 2, 0x5e)
        self.assertEqual(ack[:26].decode('utf-16-le').rstrip('\0'), 'Drifters')
        self.assertEqual(ack[26:], sent[0][1].payload)

    def test_2011_unchanged(self):
        me, master, sent = self.run_apply(2011)
        self.assertEqual([(s, f.type) for s, f in sent], [(master, 0x367)])


class OfflineCharInfo2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_by_name_and_by_cid(self):
        """0x29e (name @2 wchar[21], i64 cid @0x2c, u32 mode @0x34) -> 0x29f: XiCharInfo 0x141 @2, the mode @0x143."""
        version.configure({'version': '2016'})
        c = character()
        p = SimpleNamespace(char=c)
        sent = []
        db = SimpleNamespace(server_id=1, row=AsyncMock(return_value=(c.name,)))
        saved = context.__dict__.get('db')
        context.db = db
        try:
            with patch.object(misc, 'online', return_value=None), \
                    patch.object(misc.player, 'load', AsyncMock(return_value=p)) as load, \
                    patch.object(misc, 'send', side_effect=lambda s, f: sent.append(f)):
                body = c.name.encode('utf-16-le').ljust(0x2a, b'\0') + struct.pack('<qI', 0, 2)
                asyncio.run(misc.game_char_info_offline(SimpleNamespace(), Frame(0x29e, body)))
                body = bytes(0x2a) + struct.pack('<qI', 1234, 3)
                asyncio.run(misc.game_char_info_offline(SimpleNamespace(), Frame(0x29e, body)))
        finally:
            context.db = saved
        self.assertEqual([f.type for f in sent], [0x29f, 0x29f])
        for f, mode in zip(sent, (2, 3)):
            self.assertEqual(len(f.payload) + 2, 0x147)
            self.assertEqual(struct.unpack_from('<I', f.payload, 0x141)[0], mode)
        self.assertEqual(load.await_args_list[1].args[0], c.name)
        self.assertEqual(db.row.await_args.args[1], (1, 1234))
