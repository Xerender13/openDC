"""2016 messages built in session 47 (SIZED_PROTOCOL): 0xaa DormantEvent, 0x1d3 RoomNotifyChange, 0x240 -> 0x241
ReplaceCar, 0x6c -> 0x6d ReturnRentCar, 0xfc3 GMEventRush. Sizes are the client handlers' returned lengths."""
import asyncio
import struct
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

from dcemu.native import area, context, version
from dcemu.native.game import login, misc, promotion, rentals, rooms
from dcemu.wire import Frame


class Sized2016Test(unittest.TestCase):
    def setUp(self):
        version.configure({'version': '2016'})

    def tearDown(self):
        version.configure({'version': '2011'})

    def test_dormant_event(self):
        self.assertEqual(2 + len(promotion.frame(promotion.DORMANT).payload), 94)        # handler 0x52adc0
        f = promotion.frame(promotion.CUSTOM, b'11283')
        self.assertEqual(f.payload[4:9], b'11283')
        self.assertEqual(promotion.which(None, 1, 0, 30), promotion.NEW)
        self.assertIsNone(promotion.which(None, 20, 5000, 30))                           # old character, first seen
        self.assertEqual(promotion.which(31 * 86400, 20, 5000, 30), promotion.DORMANT)
        self.assertIsNone(promotion.which(86400, 20, 5000, 30))

    def test_dormant_login(self):
        sent = []
        db = N(server_id=1, row=AsyncMock(return_value=(40 * 86400,)), update_or_insert=AsyncMock())
        p = N(char=N(cid=7, name='X', member='m', level=20, exp=1))
        s = N(state={'player': p}, log=N(note=lambda t: None))
        with patch.object(context, 'promotion', {'enabled': True, 'dormant_days': 30}, create=True), \
                patch.object(context, 'db', db, create=True), \
                patch.object(login, 'send', lambda sess, *f: sent.extend(f)):
            asyncio.run(promotion.on_login(s))
        self.assertEqual([(f.type, struct.unpack_from('<I', f.payload)[0]) for f in sent], [(0xaa, promotion.DORMANT)])
        db.update_or_insert.assert_awaited()

    def test_room_notify_change(self):
        s = N(id=1, state={'player': N(char=N(name='X'))}, log=None)
        with patch.object(rooms, 'serial_of', return_value=9):
            m = rooms.Member(s, b'', b'\x00\x00\xab\x01', player_info=b'X'.ljust(0xd8, b'\0'))
        f = rooms.notify_change(m)
        self.assertEqual(2 + len(f.payload), 240)                                         # handler 0x5402e0
        self.assertEqual(struct.unpack_from('<I', f.payload)[0], 9)
        self.assertEqual(struct.unpack_from('<H', f.payload, 6 + 2)[0], 0x1ab)            # XiCarAttr car type

    def test_replace_car(self):
        sent = []
        s = N(state={'car': N(move=bytes(0x6c))}, to_client=sent.append, log=N(note=lambda t: None))
        asyncio.run(area.replace_car(s, Frame(0x240, struct.pack('<HHHHB3xf', 5, 7, 300, 11001, 0, 0.0))))
        self.assertEqual(2 + len(sent[0].payload), 72)                                    # handler 0x545860
        self.assertEqual(struct.unpack_from('<HHH', sent[0].payload), (5, 7, 300))
        sent.clear()
        asyncio.run(area.replace_car(N(state={'car': N(move=None)}, to_client=sent.append, log=N(note=lambda t: None)),
                                     Frame(0x240, bytes(16))))
        self.assertEqual(sent, [])                                                        # no move yet: no answer

    def test_return_rental_car(self):
        own, rent = N(car_id=1, rental=None), N(car_id=2, rental=N())
        p = N(char=N(cars=[own, rent]))
        s = N(state={'player': p}, log=N(note=lambda t: None))
        with patch.object(rentals, 'return_car', AsyncMock()) as back, patch.object(rentals, 'refresh'):
            asyncio.run(rentals.return_request(s, Frame(0x6c, struct.pack('<I', 2))))
            back.assert_awaited_once_with(s, p, rent, own)
            back.reset_mock()
            asyncio.run(rentals.return_request(s, Frame(0x6c, struct.pack('<I', 1))))     # not a rental car
            back.assert_not_awaited()

    def test_gm_rush_event(self):
        sent = []

        def mk(sid, name):
            return N(id=sid, state={'serial': sid, 'player': N(char=N(name=name))})
        gm, bob, far = mk(10, 'GM'), mk(11, 'Bob'), mk(12, 'Far')
        w = area.worlds['area']
        saved_areas, saved_sessions = dict(w.areas), dict(login.sessions)
        try:
            w.areas.clear()
            w.areas.update({5: {1: N(serial=10, area=5), 2: N(serial=11, area=5)}, 6: {3: N(serial=12, area=6)}})
            login.sessions.clear()
            login.sessions.update({10: gm, 11: bob, 12: far})
            with patch.object(misc, 'send', lambda s, f: sent.append((s, f))):
                misc.gm_rush_event(gm, ['Bob', '5000'])
        finally:
            w.areas.clear()
            w.areas.update(saved_areas)
            login.sessions.clear()
            login.sessions.update(saved_sessions)
        self.assertEqual({s.id for s, _ in sent}, {10, 11})
        f = sent[0][1]
        self.assertEqual((f.type, 2 + len(f.payload)), (0xfc3, 8))                         # handler 0x545330
        self.assertEqual(struct.unpack('<IH', f.payload), (5000, 11))


if __name__ == '__main__':
    unittest.main()
