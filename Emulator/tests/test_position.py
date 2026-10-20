import asyncio
import os
import struct
import unittest
from unittest.mock import AsyncMock, patch

from dcemu.native import context
from dcemu.native.data import Tables
from dcemu.native.game import position
from dcemu.native.game.records import Character
from dcemu.wire import Frame


class Log:
    def note(self, text):
        pass


class Session:
    def __init__(self, player):
        self.log, self.state, self.sent = Log(), {'player': player}, []

    def to_client(self, frame):
        self.sent.append(frame)


class DB:
    server_id = 100

    def __init__(self):
        self.calls = []

    async def execute(self, sql, params=()):
        self.calls.append((sql, params))


class Player:
    def __init__(self, char):
        self.char = char


def char(state, pos=(1.0, 2.0, 3.0, 4.0), city=1, area=0):
    return Character(cid=7, name='T', member='t', last_date=0, avatar=0, level=1, exp=0, exp_next=0, exp_base=0,
                     mito=0, team_id=-1, team_mark=0, team_name='', team_rank=-1, ptype='N', pvp=(0, 0, 0),
                     tpvp=(0, 0, 0), quick_cnt=0, km=0.0, pos=pos, last_area=area, city=city, pos_state=state,
                     cur_car=0, quick_slots=(0, 0, 0, 0), team_dates=(0, 0, 0), hancoin_inven=0,
                     hancoin_garage=0, flags=0, guild=0, mileage=0)


def ack(frame):
    return struct.unpack_from('<ii4fi', frame.payload)


@unittest.skipUnless(os.path.exists('server_data/tables/Icon_Moonpalace_Client.tdf'), 'needs server_data/tables (tools.sync_data)')
class PositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context.data = Tables('server_data', 'server_data/tables')

    def setUp(self):
        context.db = DB()

    def run_handler(self, fn, s, payload=b''):
        asyncio.run(fn(s, Frame(0, payload)))
        return s.sent[-1]

    def test_new_character_starts_in_the_tutorial_gate(self):
        s = Session(Player(char(0)))
        f = self.run_handler(position.first_position, s)
        city, channel, x, y, z, w, state = ack(f)
        # A new character must keep state 0 so the client's introduction starts.
        self.assertEqual((city, channel, state), (1, -1, position.NEW))
        self.assertIn((x, y), [(pytest_round(a), pytest_round(b)) for a, b, *_ in position.TUTORIAL_STARTS])
        self.assertEqual(len(f.payload) + 2, 31)                 # 2011 MyPositionAck

    def test_leaving_the_tutorial_goes_to_station_1(self):
        p = Player(char(1))
        s = Session(p)
        # The license start has its own DB reads; this test covers position and saving.
        with patch('dcemu.native.game.licenses.start', new_callable=AsyncMock) as license_start:
            f = self.run_handler(position.my_city_position, s, struct.pack('<iB', 0, 1))
        license_start.assert_awaited_once_with(s, p)
        city, channel, x, y, z, w, state = ack(f)
        self.assertEqual((city, channel, state), (1, 0, 2))
        self.assertAlmostEqual(x, -3379.0, 2)
        self.assertAlmostEqual(y, 1213.2, 2)
        self.assertEqual(p.char.pos_state, 2)
        self.assertEqual(len(context.db.calls), 1)               # saved

    def test_city_position_keeps_the_stored_place(self):
        s = Session(Player(char(2, pos=(10.0, 20.0, 30.0, 0.0))))
        f = self.run_handler(position.my_city_position, s, struct.pack('<iB', 3, 1))
        self.assertEqual(ack(f)[:4], (1, 3, 10.0, 20.0))
        self.assertEqual(context.db.calls, [])

    def test_save_car_pos(self):
        p = Player(char(2))
        s = Session(p)
        asyncio.run(position.save_car_pos(s, Frame(0xa2, struct.pack('<i4fii', 5, 1.0, 2.0, 3.0, 4.0, 1, 2))))
        self.assertEqual((p.char.last_area, p.char.pos, p.char.pos_state), (5, (1.0, 2.0, 3.0, 4.0), 2))
        self.assertEqual(len(context.db.calls), 1)


def pytest_round(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless(os.path.exists('server_data/tables/Icon_Moonpalace_Client.tdf'), 'needs server_data/tables (tools.sync_data)')
class TutorialLicenseTest(unittest.TestCase):
    """Licenses wait for the end of the tutorial, then start in the same session (user, 2026-10-20)."""
    @classmethod
    def setUpClass(cls):
        context.data = Tables('server_data', 'server_data/tables')

    def setUp(self):
        context.db = DB()
        from dcemu.native.game import apprentice
        from dcemu.native.game.records import Car
        self.p = Player(char(position.DRIVER_DOME, city=0))
        self.p.car = Car(42, apprentice.TRAINING_TYPE, 2, 1, 0, 100, 0, apprentice.TRAINING_SLOT)
        self.p.items, self.p.quests = [], []
        self.p.lic = dict(gc={}, held={}, slots=[0, 0, 0], version=1, conds_version=1, camo_until=0)

    def test_no_license_and_no_reward_with_the_training_car(self):
        from dcemu.native.game import licenses
        s = Session(self.p)
        self.assertEqual(asyncio.run(licenses.check(s, self.p)), [])
        asyncio.run(licenses.pay_monthly(s, self.p))
        self.assertEqual((self.p.lic['held'], s.sent, context.db.calls), ({}, [], []))

    def test_start_switches_the_license_flags_on_then_gains_rookie(self):
        from dcemu.native import version
        from dcemu.native.game import licenses, login
        self.p.car = None
        self.p.char.pos_state = position.IN_CITY
        try:
            for year, size in (('2011', 0x62), ('2016', 0x6a)):     # the apprentice tutorial runs on both clients
                with self.subTest(year):
                    version.configure({'version': year})
                    self.p.lic['held'] = {}
                    s = Session(self.p)
                    with patch.object(licenses, 'load', new_callable=AsyncMock), \
                            patch.object(licenses, '_add', new_callable=AsyncMock):
                        asyncio.run(licenses.start(s, self.p))
                    types = [f.type for f in s.sent]
                    self.assertEqual(len(s.sent[0].payload) + 2, size)
                    self.assertNotEqual(s.sent[0].payload, login.game_setting(**login.TUTORIAL_FLAGS).payload)
                    self.assertIn(licenses.ROOKIE, self.p.lic['held'])
                    self.assertEqual(types[:3], [0x1e, 0x331, 0x32c])  # the flags, the notice, the lists and slots
        finally:
            version.configure({})
