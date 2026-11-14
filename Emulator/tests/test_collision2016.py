"""2016 PvP collision damage (rooms.collision): 0xfbd from the attacker -> 0xfbe to the racer it hit, server HP,
retire at 0."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context
from dcemu.native.game import login, rooms
from dcemu.wire import Frame


def session(sid, name, room_id):
    return SimpleNamespace(id=sid, state={'player': SimpleNamespace(char=SimpleNamespace(name=name)), 'room': room_id},
                           log=SimpleNamespace(note=Mock()))


class CollisionTest(unittest.TestCase):
    def setUp(self):
        self.saved_attack = dict(context.attack)
        context.attack.clear()
        context.attack.update(enabled=True, damage=40.0, retire=True)
        self.saved_rooms = dict(rooms.rooms)
        rooms.rooms.clear()
        self.room = rooms.Room(11, 0, 0, 0, 8, 'r', '')
        rooms.rooms[self.room.id] = self.room
        self.a, self.b = session(1, 'A', self.room.id), session(2, 'B', self.room.id)
        with patch.object(rooms, 'serial_of', side_effect=lambda s: {1: 101, 2: 102}[s.id]):
            self.ma = rooms.Member(self.a, b'', b'')
            self.mb = rooms.Member(self.b, b'', b'')
        self.room.members = [self.ma, self.mb]
        self.room.state, self.room.racers = rooms.RACING, [101, 102]
        self.room.waiting = {101, 102}
        self.sent = []
        self.cast = []

    def tearDown(self):
        rooms.rooms.clear()
        rooms.rooms.update(self.saved_rooms)
        context.attack.clear()
        context.attack.update(self.saved_attack)

    def hit(self, sender, target_id):
        with patch.object(rooms, 'send', lambda s, f: self.sent.append((s, f))), \
                patch.object(rooms.Room, 'cast', lambda r, *f, skip=None: self.cast.extend(f)), \
                patch.object(rooms, 'progress', new=lambda room: asyncio.sleep(0)):
            asyncio.run(rooms.collision(sender, Frame(0xfbd, struct.pack('<I', target_id))))

    def test_damage_goes_to_the_racer_hit(self):
        self.hit(self.a, (7 << 16) | 102)          # the high half is the client's own counter
        self.assertEqual(len(self.sent), 1)
        who, f = self.sent[0]
        self.assertIs(who, self.b)
        self.assertEqual((f.type, len(f.payload)), (0xfbe, 4))
        self.assertAlmostEqual(struct.unpack('<f', f.payload)[0], 40.0)
        self.assertEqual(self.mb.hp, 60.0)

    def test_one_hit_a_second(self):
        self.hit(self.a, 102)
        self.hit(self.a, 102)
        self.assertEqual(len(self.sent), 1)

    def test_retired_at_zero(self):
        for _ in range(3):
            self.mb.hp = max(self.mb.hp, 1)
            self.ma.last_hit = 0.0
            self.hit(self.a, 102)
        self.assertEqual(self.mb.hp, 0.0)
        self.assertEqual(self.mb.end[0], rooms.RETIRED)
        end = [f for f in self.cast if f.type == 0x1eb]
        self.assertEqual(len(end), 1)
        self.assertEqual(len(end[0].payload), 0x4a)
        self.assertEqual(struct.unpack_from('<Ii', end[0].payload), (102, rooms.RETIRED))
        self.assertNotIn(102, self.room.waiting)

    def test_ignored(self):
        self.hit(self.a, 101)                        # itself
        self.hit(self.a, 999)                        # nobody in the room (traffic, a local object)
        context.attack['enabled'] = False
        self.ma.last_hit = 0.0
        self.hit(self.a, 102)
        self.assertEqual(self.sent, [])

    def test_content_flag(self):
        from dcemu.native import version
        version.configure({'version': '2016'})
        try:
            with patch.object(context, 'data', SimpleNamespace(contents={}), create=True):
                on = login.content_flags()
                context.attack['enabled'] = False
                off = login.content_flags()
        finally:
            version.configure({'version': '2011'})
        bit = lambda flags: struct.unpack_from('<I', flags, 0x3c)[0] >> 5 & 1     # flags_2016.tsv: 0x3c bit 5
        self.assertEqual((bit(on), bit(off)), (1, 0))


if __name__ == '__main__':
    unittest.main()
