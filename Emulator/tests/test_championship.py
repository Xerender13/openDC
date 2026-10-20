"""GT Championship: the info window's countdown (0xd4e @0xa, client 0x591d34 -> 0x5919d0)."""
import struct
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dcemu.native import context
from dcemu.native.game import championship as ch


class InfoTimeTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        self.t = ch.Tournament()
        patcher = patch.multiple(ch, _t=self.t, clock=lambda ts: int(ts) if ts else 0,
                                 viewing=lambda s: 8, stage_map=lambda stage: (75, 4))
        patcher.start()
        self.addCleanup(patcher.stop)
        context.championship = dict(getattr(context, 'championship', None) or {}, schedule=[])

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def at(self):
        return struct.unpack_from('<I', ch.race_info_frame(SimpleNamespace()).payload, 8)[0]

    def test_counts_to_the_start_then_the_round_end(self):
        self.assertEqual(self.at(), 0)                              # nothing scheduled: the line stays empty
        self.t.active, self.t.start = True, time.time() + 60
        self.assertEqual(self.at(), int(self.t.start))              # before the preliminaries: their start
        self.t.round, self.t.round_end = ch.PRE, time.time() + 1800
        self.assertEqual(self.at(), int(self.t.round_end))          # running: the round's end
        payload = ch.race_info_frame(SimpleNamespace()).payload
        self.assertEqual(struct.unpack('<IIIII', payload)[1::2], (8, 75 | 4 << 16))

    def test_next_scheduled_championship(self):
        context.championship['schedule'] = [(None, 20, 0)]
        with patch.object(ch, 'next_start', return_value=1234567):
            self.assertEqual(self.at(), 1234567)


class RotationTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        patcher = patch.multiple(ch, _t=ch.Tournament(), _drawn=None, _pool=None, log=lambda text: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        context.data = SimpleNamespace(root='server_data')
        context.championship = dict(maps=[0, 1, 2, 3, 4], map_flag=4, rotate=True, pool=[])

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def test_pool_is_the_recommended_tracks_without_mission_battles(self):
        pool = ch.track_pool()
        self.assertIn(0, pool)                          # moonpalace_track1, Recommend 110001
        self.assertNotIn(1, pool)                       # Recommend 000000, MissionBattle 01000000
        self.assertNotIn(75, pool)                      # a Mission Battle track
        self.assertNotIn(70, pool)                      # a lap time track (no Recommend bit)

    def test_drawn_once_per_championship(self):
        first = [ch.stage_map(k)[0] for k in ch.STAGES]
        self.assertEqual(len(set(first)), 5)
        self.assertTrue(set(first) <= set(ch.track_pool()))
        self.assertEqual([ch.stage_map(k)[0] for k in ch.STAGES], first)        # kept until the championship ends
        ch.tour().maps[ch.PRE] = (33, 4)
        self.assertEqual(ch.stage_map(ch.PRE), (33, 4))                          # a GM's choice wins
        context.championship['rotate'] = False
        self.assertEqual([ch.stage_map(k)[0] for k in ch.STAGES][1:], [1, 2, 3, 4])

    def test_finish_draws_anew(self):
        import asyncio
        ch.drawn_maps()
        with patch.multiple(ch, notice_all=lambda *a: None, refresh=lambda *a: None):
            asyncio.run(ch.finish())
        self.assertIsNone(ch._drawn)


if __name__ == '__main__':
    unittest.main()
