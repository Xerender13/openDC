"""The PvP bonus card board (S>C 0x1e4 / C>S 0x1e3) as the 2016 client reads it (pvpreward.py)."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dcemu.native import context, version
from dcemu.native.game import pvpreward
from dcemu.wire import Frame


class CardBoardTest(unittest.TestCase):
    def setUp(self):
        self.saved = {k: v for k, v in context.__dict__.items() if not k.startswith('__')}
        version.configure({'version': '2016'})
        self.sent = []
        char = SimpleNamespace(name='Xerender', level=81)
        self.session = SimpleNamespace(id=1234, state={'player': SimpleNamespace(char=char)},
                                       log=SimpleNamespace(note=Mock()))
        self.other = SimpleNamespace(id=4321, state={'player': SimpleNamespace(char=char)},
                                     log=SimpleNamespace(note=Mock()))
        self.frames = []

        def cast(*frames, skip=None):
            self.frames.extend(frames)

        self.room = SimpleNamespace(id=7, members=[SimpleNamespace(session=self.session),
                                                   SimpleNamespace(session=self.other)],
                                    cast=cast)
        self.room.bonus_cards = [[0, 0, 0, 0] for _ in range(pvpreward.CARDS)]
        self.room.bonus_items = [''] * pvpreward.CARDS
        self.room.bonus_picked = {}
        self.room.bonus_task = None

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def test_frame_layout_matches_the_handler(self):
        """0x542720 reads u32 n at frame+2 and n x 0x18 from frame+6, and returns 0x1e + (n-1)*0x18."""
        frame = pvpreward.grid_frame(self.room.bonus_cards)
        self.assertEqual(frame.type, 0x1e4)
        self.assertEqual(len(frame.payload) + 2, 0x1e + (pvpreward.CARDS - 1) * 0x18)
        self.assertEqual(struct.unpack_from('<I', frame.payload)[0], pvpreward.CARDS)
        for i in range(pvpreward.CARDS):
            index, _unused, serial, kind, item, amount = struct.unpack_from('<6I', frame.payload, 4 + 0x18 * i)
            self.assertEqual((index, serial, kind, item, amount), (i, 0, 0, 0, 0))   # face-down, nobody picked

    def test_unknown_kind_zero_is_the_clickable_one(self):
        """0x5e0f80 (the pick) gives up when the slot's kind (+0x5cc) is not 0."""
        cards = [list(c) for c in self.room.bonus_cards]
        cards[3] = [1, 777, 1, 0]
        frame = pvpreward.grid_frame(cards)
        kind = struct.unpack_from('<I', frame.payload, 4 + 0x18 * 3 + 0x0c)[0]
        self.assertEqual(kind, 1)

    def test_pick_reveals_the_slot_and_grants_the_item(self):
        given = []

        async def fake_give(p, rewards):
            given.extend(rewards)
            return SimpleNamespace(items=[]), []

        with patch.object(pvpreward, 'enabled', return_value=True), \
                patch.object(pvpreward, 'roll', return_value=[('NormalItem', 'mitrondust_H', '0', '1')]), \
                patch.object(pvpreward.context, 'data',
                             SimpleNamespace(item_index={'mitrondust_H': 2134},
                                             item_info=lambda idx: SimpleNamespace(table_idx=2134))), \
                patch.object(pvpreward, 'give', fake_give), \
                patch.object(pvpreward, 'send', lambda s, *f: self.sent.extend(f)):
            self.assertTrue(asyncio.run(pvpreward.pick(self.room, self.session, 5)))
        self.assertEqual(given, [('mitrondust_H', 1)])
        self.assertEqual(self.room.bonus_cards[5], [1, 2134, 1, 1234])   # kind 1, item, picker serial
        self.assertEqual(self.room.bonus_items[5], 'mitrondust_H')
        self.assertEqual(struct.unpack_from('<I', self.frames[-1].payload, 4 + 0x18 * 5 + 0x0c)[0], 1)

    def test_one_card_each_and_none_twice(self):
        async def fake_give(p, rewards):
            return SimpleNamespace(items=[]), []

        async def fake_money(char, amount):
            return None

        with patch.object(pvpreward, 'enabled', return_value=True), \
                patch.object(pvpreward, 'roll', return_value=[]), \
                patch.object(pvpreward, 'give', fake_give), patch.object(pvpreward, 'add_money', fake_money), \
                patch.object(pvpreward, 'send', lambda s, *f: self.sent.extend(f)):
            self.assertTrue(asyncio.run(pvpreward.pick(self.room, self.session, 2)))
            self.assertFalse(asyncio.run(pvpreward.pick(self.room, self.session, 9)))
            self.assertFalse(asyncio.run(pvpreward.pick(self.room, self.other, 2)))
            self.assertTrue(asyncio.run(pvpreward.pick(self.room, self.other, 9)))

    def test_no_flag_no_feature(self):
        """BattleZone.PVPResultUI off: the board is not sent, a pick is not paid (the client cannot show either)."""
        with patch.object(pvpreward, 'enabled', return_value=False):
            asyncio.run(pvpreward.on_race_result(self.room))
            pvpreward.resend(self.room)
            self.assertFalse(asyncio.run(pvpreward.pick(self.room, self.session, 4)))
        self.assertEqual(self.frames, [])
        self.assertEqual(self.room.bonus_cards[4], [0, 0, 0, 0])

    def test_2011_gets_no_board(self):
        version.configure({'version': '2011'})
        asyncio.run(pvpreward.on_race_result(self.room))
        self.assertEqual(self.frames, [])
