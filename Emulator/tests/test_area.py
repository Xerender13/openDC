import itertools
import os
import struct
import unittest

from dcemu.native import area, race
from dcemu.wire import Frame

_ids = itertools.count(1)


class Log:
    def note(self, text):
        pass


class Session:
    def __init__(self, service='area'):
        self.id, self.service = next(_ids), service
        self.log, self.state, self.log_frames, self.sent = Log(), {}, True, []

    def to_client(self, frame):
        self.sent.append(frame)

    def types(self):
        return [f.type for f in self.sent]


def frame(*cmds):
    data = b''.join(struct.pack('<H', t) + p for t, p in cmds)
    return Frame(struct.unpack_from('<H', data)[0], data[2:])


def enter(serial, name, area_id):
    return 0x232, (struct.pack('<H', serial) + name.encode('utf-16-le').ljust(42, b'\0')
                   + struct.pack('<iii', area_id, -1, 1234))


def move(serial, x, y):
    m = bytearray(area.MOVE_SIZE)
    struct.pack_into('<H', m, 0, serial)
    struct.pack_into('<ff', m, area.POS, x, y)
    return 0x21d, bytes(m)


class AreaTest(unittest.TestCase):
    def setUp(self):
        area.worlds['area'] = area.World()

    def test_enter_ack(self):
        s = Session()
        area.dispatch(s, frame(enter(17, 'Alice', 3)))
        ack = s.sent[0]
        self.assertEqual(len(ack.payload) + 2, 22)          # what the 2011 0x233 handler consumes
        self.assertEqual(struct.unpack_from('<iiI', ack.payload), (3, 1, 1234))
        self.assertEqual(s.state['car'].name, 'Alice')

    def test_moves_reach_near_cars_only(self):
        a, b, c = Session(), Session(), Session()
        area.dispatch(a, frame(enter(1, 'A', 3)))
        area.dispatch(b, frame(enter(2, 'B', 3)))
        area.dispatch(c, frame(enter(3, 'C', 3)))
        area.dispatch(b, frame(move(2, 100, 0)))
        area.dispatch(c, frame(move(3, 1000, 0)))
        area.dispatch(a, frame(move(1, 0, 0), move(1, 1, 0)))       # two moves in one frame
        self.assertEqual(b.types().count(0x221), 2)
        self.assertEqual(len(b.sent[-1].payload) + 2, 106)           # 2011 MoveVehicleExt
        self.assertNotIn(0x221, c.types())
        area.dispatch(a, frame((0x234, struct.pack('<I', 3))))
        self.assertEqual(b.sent[-1].type, 0x226)
        self.assertEqual(len(b.sent[-1].payload) + 2, 56)            # 2011 RemoveVehicle

    def test_area_status(self):
        a = Session()
        area.dispatch(a, frame(enter(1, 'A', 7)))
        area.dispatch(a, frame((0x2aa, b'')))
        counts = struct.unpack('<100I', a.sent[-1].payload)
        self.assertEqual(counts[7], 1)
        self.assertEqual(sum(counts), 1)

    def test_agent_casts_after_flush(self):
        a, g = Session(), Session()
        area.dispatch(a, frame(enter(1, 'A', 4)))
        area.dispatch(a, frame(move(1, 0, 0)))
        a.sent.clear()
        car = struct.pack('<iff', 4, 300, 0) + bytes(range(22))
        far = struct.pack('<iff', 4, 400, 0) + bytes(22)
        signal = struct.pack('<iff', 4, 0, 10) + bytes(12)
        area.dispatch(g, frame((0x2c1, struct.pack('<i', 4))))
        self.assertFalse(g.log_frames)
        area.dispatch(g, frame((0x2be, car), (0x2be, far), (0x2c3, signal)))
        self.assertEqual(a.sent, [])                                 # nothing before FlushCast
        area.dispatch(g, frame((0x2c0, b'')))
        out = struct.pack('<H', a.sent[0].type) + a.sent[0].payload
        self.assertEqual(out, struct.pack('<H', 0x2bd) + bytes(range(22)) + struct.pack('<H', 0x2c2) + bytes(12))


TABLE, SERVER = 'server_data/Init/PVPTrackInfo.xlt', 'server_data/race'


@unittest.skipUnless(os.path.exists(TABLE) and os.path.isdir(SERVER), 'needs server_data/Init (tools.sync_data) and the server folder')
class RaceTrackTest(unittest.TestCase):
    def test_2011_track_table(self):
        tracks = {t[0]: t for t in race.load_tracks(TABLE, SERVER)}
        self.assertEqual(tracks[0], (0, 'PVP_map1_01.index', 'trafficCarSettingForTrack_1.txt', -1117.9, 619.9, 1))


if __name__ == '__main__':
    unittest.main()


class ObjectTest(unittest.TestCase):
    """A client-driven object (the rush boss: same serial, another car sort) is kept apart from the
    player's car, relayed by its own position, and answered on 0x23d RequestCar."""
    def setUp(self):
        area.worlds['area'] = area.World()

    def obj_move(self, serial, sort, x, y):
        t, m = move(serial, x, y)
        m = bytearray(m)
        struct.pack_into('<H', m, 2, sort)
        return t, bytes(m)

    def test_boss_move_and_request(self):
        a, b = Session(), Session()
        area.dispatch(a, frame(enter(2, 'ctl', 4)))
        area.dispatch(b, frame(enter(6, 'other', 4)))
        area.dispatch(a, frame(self.obj_move(2, 1, 0, 0)))          # the controller's own car
        area.dispatch(b, frame(self.obj_move(6, 1, 50, 0)))
        b.sent.clear()
        area.dispatch(a, frame(self.obj_move(2, 1001, 100, 0)))     # the boss, 100 m away
        self.assertEqual(b.types().count(0x221), 1)
        self.assertEqual(area.car_of(a).pos, (0.0, 0.0))            # the player's car did not move
        b.sent.clear()
        req = struct.pack('<HHH', 1, 2, 1001) + bytes(4)            # u16 n, (serial, sort), 4 bytes as recorded
        area.dispatch(b, frame((0x23d, req), self.obj_move(6, 1, 51, 0)))
        self.assertEqual(b.types(), [0x23e])
        self.assertEqual(struct.unpack_from('<HH', b.sent[0].payload), (2, 1001))
        self.assertEqual(area.car_of(b).pos, (51.0, 0.0))           # the move after 0x23d was not dropped
