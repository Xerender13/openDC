"""AI racers in battle zone rooms: an AI joins as key << 16, one 0x271 names the master as the driver of all (2016 after the 0x1e7, 2011 just before the go)
(both clients: 2011 0x77b1c0, 2016 0x7d91f0), after the race they join again unassigned."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import rooms


def session(sid, name):
    return SimpleNamespace(id=sid, state={'player': SimpleNamespace(char=SimpleNamespace(name=name, level=10)),
                                         'serial': sid, 'visual_age': 1}, log=SimpleNamespace(note=Mock()))


class AiRacersTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.sent = {}
        patcher = patch.multiple(rooms, send=lambda s, *f: self.sent.setdefault(s.id, []).extend(f),
                                 lists_changed=Mock(), pick_ai=lambda level, taken: ((7, 'Bot', 10), 50))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.room = rooms.Room(1, 0, 0, 0, 8, 'r', '')
        self.host = rooms.Member(session(3, 'Host'), bytes(12), bytes(12))
        self.room.members.append(self.host)
        self.room.seats[0] = self.room.master = 3

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def frames(self, sid, t):
        return [f.payload for f in self.sent.get(sid, []) if f.type == t]

    def test_add_joins_unassigned(self):
        for year in (2011, 2016):
            with self.subTest(year=year):
                version.configure({'version': str(year)})
                self.sent.clear()
                self.room.members[1:] = []
                rooms.add_ai(self.room, 1, self.host)
                ai = self.room.members[-1]
                joined, = self.frames(3, 0x1d4)
                self.assertEqual(struct.unpack_from('<I', joined)[0], ai.key << 16)     # looked up by key << 16
                self.assertEqual(self.frames(3, 0x271), [])                              # named at the go
                self.assertEqual(self.room.seats[1], ai.key << 16)
                # the clients key cars by car attr word 0 << 16 | serial low word: not the driver's car (word 0 = 0)
                self.assertNotEqual(struct.unpack_from('<H', ai.car_attr)[0], 0)
                ca = 6 + len(ai.user_info)
                self.assertEqual(joined[ca:ca + len(ai.car_attr)], ai.car_attr)

    def test_one_0x271_with_all_ais_at_the_go_then_reset(self):
        rooms.add_ai(self.room, 1, self.host)
        rooms.add_ai(self.room, 2, self.host)
        a, b = self.room.ais
        self.sent.clear()
        self.room.assign_ais()
        assign, = self.frames(3, 0x271)                     # each 0x271 empties the client's driven list: one for all
        self.assertEqual(struct.unpack('<I', assign[:4])[0], 2)
        self.assertEqual(struct.unpack_from('<2I', assign, 4), (a.key, 3))
        self.assertEqual(struct.unpack_from('<2I', assign, 28), (b.key, 3))
        self.assertEqual(self.room.seats[1:3], [a.key << 16 | 3, b.key << 16 | 3])
        self.sent.clear()
        self.room.reset_ais()
        self.assertEqual([struct.unpack_from('<I', p)[0] for p in self.frames(3, 0x1d5)], [a.key << 16 | 3, b.key << 16 | 3])
        self.assertEqual([struct.unpack_from('<I', p)[0] for p in self.frames(3, 0x1d4)], [a.key << 16, b.key << 16])
        self.assertEqual(self.room.seats[1:3], [a.key << 16, b.key << 16])


class AiLoadTest(AiRacersTest):
    def test_2011_names_the_driver_when_all_have_loaded(self):
        """2011: the 0x271 places the cars on the loaded track (0x77b1c0 -> 0x7749d0), so it goes just before the go;
        2016 sends it right after the 0x1e7 (start_request), not again here."""
        import asyncio
        from dcemu.wire import Frame
        rooms.add_ai(self.room, 1, self.host)
        rooms.rooms[self.room.id] = self.room
        self.addCleanup(rooms.rooms.pop, self.room.id, None)
        self.host.session.state['room'] = self.room.id
        for year, want in ((2011, [0x271, 0x1ea]), (2016, [0x1ea])):
            with self.subTest(year=year):
                version.configure({'version': str(year)})
                self.room.reset_ais()
                self.room.state, self.room.racers, self.room.waiting = rooms.LOADING, [3], {3}
                self.sent.clear()
                asyncio.run(rooms.load_complete(self.host.session, Frame(0x1e9, struct.pack('<ii', 0, 100))))
                self.assertEqual([f.type for f in self.sent[3] if f.type in (0x271, 0x1ea)], want)
                self.room.cancel_timer()


class AiRaceTest(AiRacersTest):
    """The driver's client reports its AIs' gates (0x1ed) and ends (0x1eb) under their car key."""
    def race(self):
        import asyncio
        from dcemu.wire import Frame
        rooms.add_ai(self.room, 1, self.host)
        ai = self.room.ais[0]
        self.room.assign_ais()
        self.room.state, self.room.racers, self.room.waiting = rooms.RACING, [3], {3}
        rooms.rooms[self.room.id] = self.room
        self.host.session.state['room'] = self.room.id
        self.addCleanup(rooms.rooms.pop, self.room.id, None)
        key = struct.unpack_from('<H', ai.car_attr)[0] << 16 | 3
        self.sent.clear()
        run = lambda t, p: asyncio.run(getattr(rooms, t)(self.host.session, Frame(0, p)))
        return ai, key, run

    def test_ai_gate_is_not_the_drivers(self):
        ai, key, run = self.race()
        run('gate', struct.pack('<Iiiff', key, 0, 0, 0, 100))
        self.assertEqual(self.frames(3, 0x1ee), [struct.pack('<Ii', key, 0)])
        run('gate', struct.pack('<Iiiff', 3, 0, 0, 0, 100))
        self.assertEqual(struct.unpack('<I', self.frames(3, 0x1ee)[1][:4])[0], 3)   # the player: second at the gate
        self.assertEqual(self.room.gates[0], [ai.serial, 3])

    def test_ai_end_takes_a_place(self):
        ai, key, run = self.race()
        run('race_end', struct.pack('<IiifI', key, rooms.FINISHED, 1000, 60.0, 0).ljust(0x4a, b'\0'))
        self.assertEqual(ai.end[3], 1)
        self.assertIsNone(self.host.end)
        self.assertEqual(struct.unpack_from('<I', self.frames(3, 0x1eb)[0])[0], key)
        self.assertEqual(self.room.waiting, {3})                         # the race still waits for the player
        if self.room.timer:
            self.room.timer.cancel()


class PickAiTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def test_only_cars_the_client_supports(self):
        context.data = SimpleNamespace(vehicles={
            49: {'Desc': 'PlayerCar', 'Support': '0', 'Sellable': '1'},       # the 2016 client crashed loading it
            50: {'Desc': 'PlayerCar', 'Support': '1', 'Sellable': '1'},
            20001: {'Desc': 'TrafficCar', 'Support': '1'}})
        with patch.object(rooms, 'ai_table', return_value=[(1, 'Bot', 10, [49, 20001, 50])]):
            self.assertEqual({rooms.pick_ai(10, set())[1] for _ in range(50)}, {50})
        with patch.object(rooms, 'ai_table', return_value=[(1, 'Bot', 10, [49])]):
            self.assertEqual(rooms.pick_ai(10, set())[1], 50)                  # none of its own: a dealership car


if __name__ == '__main__':
    unittest.main()
