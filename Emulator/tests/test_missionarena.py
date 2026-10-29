"""2016 Mission Battles (game/missionarena.py): the arena's 0x3bb / 0x3b6 / 0x3b8 and the item route's 0x3b8, with stub
sessions and the 2016 client's own tables (server_data_2016/Init)."""
import asyncio
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import instant, missionarena, rooms
from dcemu.wire import Frame

DATA = 'server_data_2016'


def session(sid, level=10, grade=1):
    car = SimpleNamespace(shown_grade=lambda: grade)
    char = SimpleNamespace(name=f'P{sid}', level=level, mito=5000, exp=10, exp_next=100, exp_base=0, ptype='N')
    return SimpleNamespace(id=sid, log=SimpleNamespace(note=Mock()),
                           state={'serial': sid, 'visual_age': 1, 'room': 1,
                                  'player': SimpleNamespace(char=char, car=car, items=[], vsitems=[])})


@unittest.skipUnless(os.path.exists(f'{DATA}/Init/LineBall.xlt'), 'needs server_data_2016/Init')
class MissionArenaTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        missionarena._rows.clear()
        missionarena._tracks = None
        mission_row = ['instant', '0', '1000', 'ROO', 'Battle_Lobby', 'Line Ball', '', 'True', '30', '',
                       'Mission_Battle1', 'n/a', 'n/a', '0', '', 'n/a', '0', 'n/a']
        context.data = SimpleNamespace(root=DATA, instants=[None] * 184 + [mission_row])
        self.sent = {}
        record = lambda s, *f: self.sent.setdefault(s.id, []).extend(f)
        for target in (patch.multiple(missionarena, send=record, add_money=AsyncMock(), add_exp=AsyncMock(),
                                      play_mode=AsyncMock()),
                       patch.multiple(instant, add_money=AsyncMock(), add_exp=AsyncMock(), play_mode=AsyncMock(),
                                      play_bonus=lambda p, exp, money, kind: (exp, money),
                                      send=record, stat_frames=lambda p: []),
                       patch.multiple(rooms, send=record),
                       patch('dcemu.native.game.login.stat_frames', lambda p: []),
                       patch('dcemu.native.admin.message', Mock())):
            target.start()
            self.addCleanup(target.stop)
        self.room = rooms.Room(rooms.ARENA_SECTION, 0, 0, 0, 4, 'arena', '')
        self.master, self.other = session(1), session(2)
        for s in (self.master, self.other):
            m = rooms.Member(s, bytes(16), bytes(16))
            m.ready = True
            self.room.members.append(m)
        self.room.master = 1
        rooms.rooms[1] = self.room
        self.addCleanup(rooms.rooms.pop, 1, None)

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def run_(self, handler, s, payload):
        asyncio.run(getattr(missionarena, handler)(s, Frame(0, payload)))

    def frames(self, s, t):
        return [f.payload for f in self.sent.get(s.id, []) if f.type == t]

    def test_tracks_from_pvptrackinfo(self):
        self.assertEqual([missionarena.track(m) for m in (1, 2, 3)], [11, 1, 75])

    def test_choice_goes_to_the_others_one_based(self):
        self.run_('room_state', self.master, struct.pack('<HH', 2, 0))
        self.assertEqual(self.frames(self.other, 0x3bb), [struct.pack('<HH', 2, 1)])
        self.assertEqual(self.frames(self.master, 0x3bb), [])
        self.run_('room_state', self.other, struct.pack('<HH', 3, 0))      # not the master: ignored
        self.assertEqual(self.room.arena_choice, (2, 0))

    def test_start_sends_seed_and_mission(self):
        self.run_('mission_start', self.master, struct.pack('<HH', 3, 0))
        for s in (self.master, self.other):
            seed, = self.frames(s, 0x3bc)
            ack, = self.frames(s, 0x3b7)
            self.assertEqual(len(seed) + 2, 70)
            self.assertEqual(len(ack) + 2, 22)
            mode, diff, track, _, limit, _, dist, interval = struct.unpack('<HHHHfIHH', ack)
            self.assertEqual((mode, diff, track, limit, dist, interval), (3, 0, 75, 200.0, 300, 4))
        self.assertEqual(rooms.mission_room(self.room), True)
        self.assertEqual(missionarena.start_flag(self.master, self.room), 0x2048)

    def test_start_refused_for_a_closed_difficulty(self):
        self.run_('mission_start', self.master, struct.pack('<HH', 1, 1))      # Support 0
        self.assertEqual(self.frames(self.master, 0x3b7), [])
        self.assertIsNone(missionarena.start_flag(self.master, self.room))

    def test_arena_complete_pays_the_row(self):
        self.run_('mission_start', self.master, struct.pack('<HH', 1, 0))
        self.run_('mission_complete', self.master, struct.pack('<HHfI', 1, 0, 100.0, 140))     # within ClearMoreTime
        ack, = self.frames(self.master, 0x3b9)
        self.assertEqual(len(ack) + 2, 40)
        mito, exp = struct.unpack_from('<iI', ack, 4)
        self.assertEqual((exp, mito), (900 + 90, 500 + 50))
        self.assertEqual(self.frames(self.master, 0x3e3), [])

    def test_item_route_complete_pays_the_instant_row(self):
        self.master.state['instant'] = dict(idx=184, places=set(), patrol=False)
        self.master.state['mission_result'] = dict(idx=184, kind=1, value=150, seconds=120.0, tries=0)
        self.run_('mission_complete', self.master, struct.pack('<HHfI', 1, 184, 120.0, 150))
        ack, = self.frames(self.master, 0x3b9)
        self.assertEqual(struct.unpack_from('<I', ack, 8)[0], instant.mission_battle_exp(
            context.data.instants[184], 10, dict(value=150, seconds=120.0)))
        self.assertEqual(self.frames(self.master, 0x3e3), [struct.pack('<I', 184)])
        self.assertNotIn('instant', self.master.state)

    def test_object_event_relayed_to_the_others(self):
        self.run_('object_event', self.master, struct.pack('<IH', 7, 2))
        self.assertEqual(self.frames(self.other, 0x3bd), [struct.pack('<IH', 7, 2)])
        self.assertEqual(self.frames(self.master, 0x3bd), [])


if __name__ == '__main__':
    unittest.main()
