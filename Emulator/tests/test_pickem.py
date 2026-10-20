"""Pick'em (game/pickem.py): a spectator's ticket, picks, multiplier and the 0x83a draw, with stub sessions."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import driftuse, items, pickem, progress, rooms
from dcemu.wire import Frame

TICKET, PRIZE5 = 1051, 1056


def session(sid, level=10, grade=1):
    car = SimpleNamespace(shown_grade=lambda: grade)
    char = SimpleNamespace(name=f'P{sid}', level=level, mito=5000, exp=10, exp_next=100, exp_base=0)
    return SimpleNamespace(id=sid, log=SimpleNamespace(note=Mock()),
                           state={'serial': sid, 'visual_age': 1,
                                  'player': SimpleNamespace(char=char, car=car, items=[], vsitems=[])})


class PickemTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2011'})
        self.sent = {}
        names = {TICKET: 'gacha_observe', PRIZE5: 'gacha_observe_v5'}
        context.data = SimpleNamespace(item_info=lambda idx: SimpleNamespace(item_id=names.get(idx, '?')),
                                       item_index={'gacha_observe_v%d' % n: 1051 + n for n in range(1, 11)})
        context.pickem = dict(enabled=True, free=False, exp=100, mito=1000)
        self.given = []

        async def give_item(p, item, count, gains):
            it = SimpleNamespace(inven_idx=77, table_idx=context.data.item_index[item])
            self.given.append(item)
            gains.items.append((it, 1))

        async def take_one(p, it):
            it.stack -= 1
            return it, 2

        for target in (patch.multiple(pickem, send=lambda s, *f: self.sent.setdefault(s.id, []).extend(f)),
                       patch.multiple(rooms, send=Mock(), lists_changed=Mock()),
                       patch.object(driftuse, 'give_item', give_item), patch.object(driftuse, 'take_one', take_one),
                       patch.object(driftuse.Gains, 'send', Mock()),
                       patch.object(items, 'add_money', AsyncMock(return_value=True)),
                       patch.object(progress, 'add_exp', AsyncMock())):
            target.start()
            self.addCleanup(target.stop)
        # four racers: 1 and 2 weak (V1), 3 and 4 strong (V5); a spectator 9 with one ticket
        self.room = rooms.Room(1, 0, 0, 0, 8, 'r', '')
        grades = {1: 1, 2: 1, 3: 5, 4: 5}
        for sid, g in grades.items():
            m = rooms.Member(session(sid, grade=g), bytes(12), bytes(12))
            self.room.members.append(m)
            self.room.seats[sid - 1] = sid
        self.room.racers = list(grades)
        self.room.state = rooms.RACING
        rooms.rooms[1] = self.room
        self.addCleanup(rooms.rooms.pop, 1, None)
        self.spec = session(9)
        self.spec.state['watching'] = 1
        self.ticket = SimpleNamespace(table_idx=TICKET, stack=1, inven_idx=5)
        self.spec.state['player'].items.append(self.ticket)
        self.room.observers.append(self.spec)

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def run_(self, handler, payload=b''):
        asyncio.run(getattr(pickem, handler)(self.spec, Frame(0, payload)))

    def frames(self, t):
        return [f.payload for f in self.sent.get(9, []) if f.type == t]

    def test_a_whole_race(self):
        self.run_('init', bytes(0x26))
        self.assertEqual(self.ticket.stack, 0)                              # the ticket is used
        init, = self.frames(0x835)
        self.assertEqual(len(init) + 2, 0x16)
        self.assertEqual(list(init[4:8]), [1, 1, 2, 3])                     # weakest third gold .. strongest bronze
        for serial in (1, 3, 4):
            self.run_('select', struct.pack('<II', serial, 1))
        self.run_('select', struct.pack('<II', 2, 1))                       # a fourth pick: refused
        self.assertEqual([struct.unpack('<II', f) for f in self.frames(0x836)], [(1, 1), (3, 1), (4, 1)])
        self.room.gates[0] = [3, 2, 1, 4]
        self.room.gates[1] = [2, 4, 3, 1]
        for gate in (0, 0, 1, 5):                   # gate 0 twice: counted once; 5: nobody there yet
            self.run_('up', struct.pack('<IiI', 4, gate, 3) + bytes(12))
        self.assertEqual([struct.unpack('<I', f)[0] for f in self.frames(0x838)], [2, 2, 3, 3])
        # result: 1 first (gold symbol), 3 second (silver), 4 fourth -> gold, silver, bomb
        for sid, rank in {1: 1, 3: 2, 2: 3, 4: 4}.items():
            self.room.by_serial(sid).end = (rooms.FINISHED, 0, 60.0 + rank, rank)
        asyncio.run(pickem.on_result(self.room))
        result, = self.frames(0x83a)
        self.assertEqual(len(result) + 2, 3 * 8 + 0x2c)
        n, _, prize, mito, total, exp, level = struct.unpack_from('<IIIiqIH', result)
        self.assertEqual((n, prize, mito, exp), (3, 77, (3000 + 2000) * 3, (300 + 200) * 3))
        self.assertEqual([struct.unpack_from('<IHH', result, 0x2a + 8 * k) for k in range(3)],
                         [(1, 1, 1), (3, 2, 2), (4, 4, 0)])
        self.assertEqual(self.given, ['gacha_observe_v3'])                  # the multiplier's Slot Ticket
        self.assertNotIn('pickem', self.spec.state)

    def test_refused_without_ticket_or_with_ais_or_few_racers(self):
        self.spec.state['player'].items.clear()
        with patch.object(pickem.admin, 'message', Mock()) as message:
            self.run_('init')
            self.room.racers = [1, 2, 3]
            self.spec.state['player'].items.append(self.ticket)
            self.run_('init')
        self.assertEqual(message.call_count, 2)
        self.assertEqual(self.frames(0x835), [])

    def test_free_entry_and_a_new_race_forgets_the_old_picks(self):
        context.pickem['free'] = True
        self.spec.state['player'].items.clear()
        self.run_('init')
        self.assertEqual(len(self.frames(0x835)), 1)
        self.room.gates = {}                                                # the next race
        self.assertIsNone(pickem.state(self.spec, self.room))


if __name__ == '__main__':
    unittest.main()
