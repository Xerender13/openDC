import asyncio
import os
import struct
import unittest

from dcemu.native import area, city_traffic as ct, context
from dcemu.native.tcs import UNIT
from tests.test_area import Session, enter, frame, move

DATA = 'server_data'
MOON = os.path.join(DATA, 'tables', 'MoonPalace', 'moonpalace.tcs')


class FramesTest(unittest.TestCase):
    def test_cut_between_commands(self):
        cmds = [struct.pack('<H', 0x2bd) + bytes(22)] * 200 + [struct.pack('<H', 0x2c2) + bytes(12)] * 50
        out = ct.frames(cmds)
        self.assertTrue(all(len(f.payload) + 2 <= ct.MAX_OUT for f in out))
        self.assertTrue(all((len(f.payload) + 2) % 24 == 0 for f in out[:-1]))     # only whole car moves
        self.assertEqual(sum(len(f.payload) + 2 for f in out), 200 * 24 + 50 * 14)

    def test_area_cities(self):
        # the 2011 client drives Oros in area 52 (TrafficAgent gave it Cras's lanes)
        self.assertEqual([ct.area_city(a) for a in (0, 3, 4, 13, 28, 52, 61, 76, 85)], [None, None, 1, 1, 2, 4, 4, 3, 3])


@unittest.skipUnless(os.path.exists(MOON), 'needs server_data/tables (tools.sync_data)')
class CityTrafficTest(unittest.TestCase):
    def setUp(self):
        self.t = ct.CityTraffic(DATA, log=lambda s: None)

    def test_moon_palace_lanes_and_models(self):
        city = self.t.city(1)
        self.assertEqual((len(city.lanes), len(city.lamps), len(city.tcs.controllers)), (2283, 490, 89))
        self.assertEqual(round(city.lanes[1375].end * UNIT, 1), 1248.4)
        self.assertIn(11, city.models)                     # 20012 c_t_0_012
        self.assertIn(500, [m for m, _ in self.t.models[5]])     # Taipei's 20501 c_t_5_001

    def test_cars_drive_and_obey_signals(self):
        city = self.t.city(1)
        at = ct.AreaTraffic(4, city, 300, seed=1)
        for _ in range(120):
            at.step()
            for car in at.cars:
                if not car.stopped:                 # the client's extrapolation never goes backwards
                    self.assertGreaterEqual(car.v + car.a * ct.PERIOD, -1e-6)
        moving = sum(1 for c in at.cars if c.v > 0)
        self.assertGreater(moving, 100)
        self.assertTrue(any(c.stopped for c in at.cars))

    def test_player_gets_cars_and_lamps_near_it(self):
        saved, area.worlds['area'] = area.worlds['area'], area.World()
        context.city_traffic = self.t
        try:
            async def go():
                s = Session()
                area.dispatch(s, frame(enter(1, 'A', 4)))
                at = self.t.areas[4]
                car = at.cars[0]
                x, y = car.lane.at(car.pos)
                area.dispatch(s, frame(move(1, x, y)))
                s.sent.clear()
                await asyncio.sleep(1.2)
                self.t.task.cancel()
                return s
            s = asyncio.run(go())
            cmds = []
            for f in s.sent:
                data, o = struct.pack('<H', f.type) + f.payload, 0
                while o < len(data):
                    t, = struct.unpack_from('<H', data, o)
                    cmds.append((t, data[o + 2:o + {0x2bd: 24, 0x2c2: 14}[t]]))
                    o += {0x2bd: 24, 0x2c2: 14}[t]
            moves = [struct.unpack('<IfeeHHhhh', b) for t, b in cmds if t == 0x2bd]
            self.assertIn(0, [m[4] for m in moves])          # car 0, next to the player
            self.assertTrue(all(m[6] in self.t.city(1).lanes for m in moves))
        finally:
            area.worlds['area'] = saved
            context.city_traffic = None

    def test_lamps_carry_their_change_time(self):
        # the client shows amber for 4 s after a lamp's time when it says stop, 1 s when it says go
        city = self.t.city(1)
        at = ct.AreaTraffic(4, city, 10, seed=1)
        seen = {}
        for step in range(100):
            at.step()
            now = 500000 + step * 1000
            lamp, sig, x, y = city.lamps[0]
            for c in at.commands_near(x, y, now):
                if c[:2] == b'\xc2\x02' and struct.unpack_from('<i', c, 6)[0] == lamp:
                    t, _, state = struct.unpack_from('<Iii', c, 2)
                    client = 'A' if now - t < (1000 if state else 4000) else ('G' if state else 'R')
                    self.assertEqual(client, city.light(sig, at.t))
                    seen[client] = True
        self.assertEqual(sorted(seen), ['A', 'G', 'R'])

    def test_no_traffic_in_tutorial_or_taipei(self):
        self.assertIsNone(self.t.touch(3))


if __name__ == '__main__':
    unittest.main()
