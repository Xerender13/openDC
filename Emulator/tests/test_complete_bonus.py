"""The battle zone's complete bonus (rooms.complete_bonus): the room window's per-lap EXP / Mito (client 0x59ec60)."""
import unittest
from types import SimpleNamespace

from dcemu.native import context
from dcemu.native.game import rooms


class CompleteBonusTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        context.data = SimpleNamespace(root='server_data')
        rooms._bonus_rows = rooms._laps = None

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        rooms._bonus_rows = rooms._laps = None

    def test_as_the_client_computes_it(self):
        self.assertEqual(len(rooms.bonus_rows()), 15)
        # Newbie, 8 players: Bronze row 5 (5 points), section x3 -> 8 x 1.025 x 3 x 5, 5 x 8 x 1.8 x 3
        self.assertEqual(rooms.complete_bonus(11, 0x80, 0, 8), (123, 216))
        # Pro 4X with the speed limit, 4 players: Silver row 7 (4 points)
        self.assertEqual(rooms.complete_bonus(12, 0x20080, 0x4000, 4), (66, 115))
        # Pro 16X without the limit, 16 players: Gold row 15 (15 points)
        self.assertEqual(rooms.complete_bonus(12, 0x100080, 0, 16), (3936, 6912))
        self.assertEqual(rooms.complete_bonus(11, 0x80, 0, 1), (0, 0))         # alone: nothing (as the panel)
        self.assertEqual(rooms.complete_bonus(6, 0x80, 0, 8), (0, 0))          # Real Match and the others: none
        self.assertEqual(rooms.lap_count(0), 2)                                # moonpalace_track1


if __name__ == '__main__':
    unittest.main()
