"""2016 battle zone room layouts: 16-byte UserInfo and XiCarAttr (RoomCreate, joins, member records)."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import rooms
from dcemu.wire import Frame

# The user's 2016 RoomCreate (logs/2016/20261020-113408, 11:36:26): spectating room 0x80, map 0, 8 seats,
# flags 0x5008, "Into the Storm".
CREATE_2016 = (bytes.fromhex('010001000000729619a7fb6700000000')          # UserInfo (16)
               + struct.pack('<IHHHII', 0x80, 0, 8, 0x5008, 0, 0)              # type, map, seats, flags @0x10
               + 'Into the Storm'.encode('utf-16le').ljust(60, b'\0')        # name @0x22
               + bytes(0x9a - 0x5e)                                          # password @0x5e
               + bytes.fromhex('0000ab0102010101cccccc8201000000'))          # XiCarAttr (16) @0x9a
assert len(CREATE_2016) == 0xaa                                              # as logged (frame 174)


class Rooms2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.saved_rooms = dict(rooms.rooms)
        rooms.rooms.clear()
        self.sent = []
        self.s = SimpleNamespace(id=5, state={'player': SimpleNamespace(char=SimpleNamespace(name='Xerender')),
                                              'pvp_channel': 11},
                                 log=SimpleNamespace(note=Mock()))

    def tearDown(self):
        rooms.rooms.clear()
        rooms.rooms.update(self.saved_rooms)
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def create(self, payload):
        with patch.object(rooms, 'send', lambda s, *f: self.sent.extend(f)), \
                patch.object(rooms, 'car_allowed', return_value=True), \
                patch.object(rooms, 'lists_changed'), patch.object(rooms, 'is_real_match', return_value=False):
            asyncio.run(rooms.room_create(self.s, Frame(0x1cc, payload)))
        return next(iter(rooms.rooms.values()))

    def test_2016_create_reads_the_shifted_fields(self):
        version.configure({'version': '2016'})
        room = self.create(CREATE_2016)
        self.assertEqual((room.type, room.map_id, room.capacity, room.map_flag), (0x80, 0, 8, 0x5008))
        self.assertEqual(room.name, 'Into the Storm')
        m = room.members[0]
        self.assertEqual((len(m.user_info), len(m.car_attr)), (16, 16))
        self.assertEqual(struct.unpack_from('<H', m.car_attr, 2)[0], 427)      # the car type
        unit = m.unit()
        self.assertEqual(len(unit), 0x47)                                       # client member stride (0x543179)
        self.assertEqual(unit[0x27:0x27 + 16].decode('utf-16le'), 'Xerender')   # name after both 16-byte records

    def test_2011_sizes_unchanged(self):
        version.configure({'version': '2011'})
        self.assertEqual((rooms.user_info_size(), rooms.car_attr_size()), (12, 12))
        self.assertEqual(rooms.CREATE[2011], (0xc, 0x16, 0x1e, 0x5a, 0x96))
        m = rooms.Member(self.s, bytes(16), bytes(16))
        self.assertEqual(len(m.unit()), 0x3f)

    def test_2016_join_offsets(self):
        version.configure({'version': '2016'})
        got = []
        p = bytearray(0x18a)
        p[6:0x16] = b'U' * 16
        p[0x16:0x26] = b'C' * 16
        struct.pack_into('<I', p, 0x26, 7)
        p[0x2e:0x2e + rooms.PLAYER_INFO] = b'P' * rooms.PLAYER_INFO
        with patch.object(rooms, 'join', lambda s, room, ui, ca, pi, pw: got.append((ui, ca, pi[:1]))):
            rooms.rooms[7] = 'room'
            asyncio.run(rooms.room_join(self.s, Frame(0x1d4, bytes(p))))
        self.assertEqual(got, [(b'U' * 16, b'C' * 16, b'P')])


class RealMatchCar2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        context.realmatch_car = (50, 9)

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def frame(self, year):
        version.configure({'version': str(year)})
        s = SimpleNamespace(state={})
        with patch.object(rooms, 'real_match_times', return_value=(True, 1234)), \
                patch('dcemu.native.game.championship.section_tail', return_value=struct.pack('<III', 0, 2, 3)):
            return rooms.section_frame(s, 6).payload

    def test_2016_section_carries_the_real_match_car(self):
        self.assertEqual(struct.unpack_from('<III', self.frame(2016), 0x18), (50, 2, 3))   # packet @0x1a
        self.assertEqual(struct.unpack_from('<III', self.frame(2011), 0x18), (0, 2, 3))    # 2011: a flag, unchanged

    def test_gm_command_sets_the_car(self):
        t = SimpleNamespace(vehicles={157: {'UI Name': 'F03-MS', 'Car Name': 'Ferrari F2003-GA', 'Vehicle': '0'}},
                            upgrade={(157, 1): {}, (157, 9): {}})
        context.data = t
        with patch.object(rooms, 'real_match_info', return_value=None), patch.object(rooms, 'sessions', {}):
            reply = rooms.gm_realmatch(['car', 'F03-MS', 'V9'])
        self.assertEqual(context.realmatch_car, (157, 9))
        self.assertIn('F03-MS', reply)
