"""2016 requests whose layout differs from 2011, found by comparing every sender of both clients (session 42)."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import version
from dcemu.native.game import chase, rooms
from dcemu.wire import Frame


class ChaseEnd2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def run_end(self, year, payload):
        version.configure({'version': str(year)})
        s = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='X')), 'chase': object()},
                            log=Mock())
        with patch.object(chase, 'leave_chase', AsyncMock()) as leave:
            asyncio.run(chase.chase_end(s, Frame(0xb7, payload)))
        return leave

    def test_2016_result_at_0x10(self):
        """The logged 2016 frame (2026-10-20 15:24:19): serial 0, result 0 at @0x10, not 706 (the 2011 @0xe)."""
        logged = bytes.fromhex('000000000000000000000000c202000000002300000000000000c202253331002500000000000000c20225'
                               '3331002600000000000000')
        leave = self.run_end(2016, logged)
        leave.assert_awaited_once()
        self.assertEqual(leave.await_args.args[1], 0)

    def test_2011_unchanged(self):
        leave = self.run_end(2011, struct.pack('<HHIfI', 0, 0, 0, 0.0, 3) + bytes(36))
        self.assertEqual(leave.await_args.args[1], 3)


class SecureJoins2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_channel_secure_join_reads_password_after_player_info(self):
        for year in (2011, 2016):
            version.configure({'version': str(year)})
            ui, ca, room_at, pi = rooms.JOIN[year][0x1d7]
            p = bytearray({2011: 0x1c0, 2016: 0x1c8}[year] - 2)          # the sender's full size (0x80 unused at the end)
            struct.pack_into('<I', p, room_at, 77)
            at = pi + rooms.PLAYER_INFO                                   # 2016: packet @0x10c (wcsncpy at 0x84af2a)
            p[at:at + 60] = 'pw'.encode('utf-16-le').ljust(60, b'\0')
            with patch.object(rooms, 'join') as join, patch.dict(rooms.rooms, {77: 'room'}):
                asyncio.run(rooms.channel_room_secure_join(SimpleNamespace(), Frame(0x1d8, bytes(p))))
            self.assertEqual(join.call_args.args[1], 'room')
            self.assertEqual(join.call_args.args[5], 'pw')

    def test_secure_switch_checks_password(self):
        version.configure({'version': '2016'})
        room = SimpleNamespace(password='pw')
        body = bytes(16) + 'pw'.encode('utf-16-le').ljust(60, b'\0')
        self.assertEqual(len(body) + 2, 0x4e)
        with patch.object(rooms, 'watching', return_value=room), patch.object(rooms, 'unwatch'), \
                patch.object(rooms, 'join') as join, patch.object(rooms, 'error') as err:
            asyncio.run(rooms.secure_switch_to_player(SimpleNamespace(), Frame(0x1dd, body)))
            join.assert_called_once()
            asyncio.run(rooms.secure_switch_to_player(SimpleNamespace(), Frame(0x1dd, bytes(16) + b'x\0' * 29)))
            err.assert_called_once_with(unittest.mock.ANY, '20162')


class Valentine2016Test(unittest.TestCase):
    def tearDown(self):
        version.configure({'version': '2011'})

    def test_chocolate_to_station_npc(self):
        """0xfb9 (char[] NPC key @2, 0x101) -> chocolate taken, the row's group given, 0xfba (the key, 0x72)."""
        from dcemu.native.game import valentine
        version.configure({'version': '2016'})
        sent = []
        s = SimpleNamespace(state={'player': SimpleNamespace(char=SimpleNamespace(name='X'))}, log=Mock())
        body = b'post_1st_00052'.ljust(0xff, b'\0')
        with patch.object(valentine, 'rows', return_value={'post_1st_00052': ('rw_2013_valentine_moon_01', True)}), \
                patch('dcemu.native.events.is_on', return_value=True), \
                patch('dcemu.native.game.alchemy.take_count', AsyncMock(return_value=[('it', 3)])), \
                patch('dcemu.native.game.items.mod_list', return_value=Frame(0x192, b'')), \
                patch('dcemu.native.game.driftuse.roll', return_value=[]) as roll, \
                patch('dcemu.native.game.driftuse.give', AsyncMock()), \
                patch('dcemu.native.game.driftuse.Gains', return_value=SimpleNamespace(send=Mock())), \
                patch.object(valentine, 'send', side_effect=lambda to, f: sent.append(f)):
            asyncio.run(valentine.give_chocolate(s, Frame(0xfb9, body)))
        roll.assert_called_once_with('rw_2013_valentine_moon_01')
        ans = [f for f in sent if f.type == 0xfba][0]
        self.assertEqual(len(ans.payload) + 2, 0x72)
        self.assertTrue(ans.payload.startswith(b'post_1st_00052\0'))

    def test_table_keys(self):
        from dcemu.native import context
        from dcemu.native.game import valentine
        saved = context.__dict__.get('data')
        context.data = SimpleNamespace(root='server_data_2016')
        valentine._rows = None
        try:
            r = valentine.rows()
        finally:
            valentine._rows = None
            context.data = saved
        self.assertEqual(r['post_1st_00052'], ('rw_2013_valentine_moon_01', True))
        self.assertEqual(len(r), 15)
