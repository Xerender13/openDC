"""Player trade (trade.py): message layouts of the 2011 / 2016 clients and the exchange, with stub sessions."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.game import login, trade
from dcemu.native.game.records import Item


def player(name, cid, mito, items):
    c = SimpleNamespace(name=name, cid=cid, mito=mito, part_inven_idx=100, hancoin_inven=0)
    return SimpleNamespace(char=c, items=list(items), tick=0)


def session(p):
    return SimpleNamespace(state={'player': p, 'channel': 1}, log=SimpleNamespace(note=Mock()))


class TradeTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        trade.trades.clear()
        self.sent = []
        self.a = session(player('Alice', 11, 1000, [Item(1, 5, 'i_a', 0, 3, 0, 0, 0, 0, '', '', 0, 0, table_idx=40)]))
        self.b = session(player('Bob', 22, 50, []))
        context.extra_flags = {}
        context.db = SimpleNamespace(server_id=1, execute=AsyncMock(), row=AsyncMock(return_value=(900,)))

    def tearDown(self):
        trade.trades.clear()
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    def run_(self, fn, s, payload):
        with patch.object(trade, 'send', side_effect=lambda to, f: self.sent.append((to, f))), \
                patch.object(trade, 'by_name', side_effect=lambda n: {'Bob': self.b, 'Alice': self.a}.get(n)), \
                patch.object(trade, 'error', side_effect=lambda to, k: self.sent.append((to, k))):
            asyncio.run(fn(s, SimpleNamespace(payload=payload)))

    def frames(self, t, to=None):
        return [f for s, f in self.sent if not isinstance(f, str) and f.type == t and (to is None or s is to)]

    def open_trade(self):
        self.run_(trade.trade_open, self.a, 'Bob'.encode('utf-16-le').ljust(42, b'\0'))
        prop, = self.frames(0x1f6, self.b)
        self.assertEqual(len(prop.payload) + 2, 0x30)
        self.assertEqual(prop.payload[:42].decode('utf-16-le').rstrip('\0'), 'Alice')
        tid, = struct.unpack_from('<I', prop.payload, 0x2a)
        self.run_(trade.trade_propose_ack, self.b, struct.pack('<IH', tid, 1))
        return tid

    def test_open_layout(self):
        tid = self.open_trade()
        for who in (self.a, self.b):
            ack, = self.frames(0x1f5, who)
            self.assertEqual(len(ack.payload) + 2, 0x6c)
            host, guest = (ack.payload[i:i + 42].decode('utf-16-le').rstrip('\0') for i in (0, 42))
            self.assertEqual((host, guest), ('Alice', 'Bob'))
            self.assertEqual(struct.unpack_from('<qqIH', ack.payload, 0x54), (11, 22, tid, 1))

    def test_refusal_closes(self):
        self.run_(trade.trade_open, self.a, 'Bob'.encode('utf-16-le').ljust(42, b'\0'))
        tid, = struct.unpack_from('<I', self.frames(0x1f6)[0].payload, 0x2a)
        self.run_(trade.trade_propose_ack, self.b, struct.pack('<IH', tid, 0))
        self.assertEqual(len(self.frames(0x1ff)), 2)
        self.assertFalse(trade.trades)

    def test_item_on_sizes(self):
        for year, size in ((2011, 0x84), (2016, 0x88)):
            version.configure({'version': str(year)})
            self.sent.clear()
            trade.trades.clear()
            self.a.state.pop('trade', None), self.b.state.pop('trade', None)
            tid = self.open_trade()
            with patch('dcemu.native.game.mail.sendable', return_value=True):
                self.run_(trade.trade_item_on, self.a, struct.pack('<IIi', tid, 5, 2))
            on = self.frames(0x1f9, self.b)[0].payload
            self.assertEqual(len(on) + 2, size)
            info = on[4:size - 2 - 42]
            self.assertEqual(struct.unpack_from('<IIi', info, len(info) - 12), (40, 5, 1))   # TableIdx, InvenIdx, index
            self.assertEqual(struct.unpack_from('<i', info, 0)[0], 2)                         # stack: the offered count
            self.assertEqual(on[-42:].decode('utf-16-le').rstrip('\0'), 'Alice')

    def test_full_exchange(self):
        tid = self.open_trade()
        with patch('dcemu.native.game.mail.sendable', return_value=True):
            self.run_(trade.trade_item_on, self.a, struct.pack('<IIi', tid, 5, 2))
            self.run_(trade.trade_item_on, self.a, struct.pack('<IIi', tid, 5, 1))     # the same item again
            self.run_(trade.trade_item_on, self.a, struct.pack('<IIi', tid, 5, 0))
        self.assertEqual([k for s, k in self.sent if isinstance(k, str)], ['20055', '20050'])
        self.run_(trade.trade_money, self.b, struct.pack('<Iq', tid, 30))
        money = self.frames(0x203, self.a)[0].payload
        self.assertEqual(len(money) + 2, 0x38)
        self.run_(trade.trade_complete, self.a, struct.pack('<I', tid))
        self.assertFalse(self.frames(0x201))                        # not before both locked
        for s in (self.a, self.b):
            self.run_(trade.trade_lock, s, struct.pack('<IH', tid, 1))
        self.assertEqual([struct.unpack_from('<I', f.payload, 4)[0] for f in self.frames(0x1fd, self.a)], [1, 3])
        info = SimpleNamespace(item_id='i_a', table_idx=40, type=5)
        context.data = SimpleNamespace(item_index={'i_a': 40}, item_info=lambda i: info)
        made = []

        async def new_item(p, inf, count):
            it = Item(9, 1, inf.item_id, 0, count, 0, 0, 0, 0, '', '', 0, 0, table_idx=40)
            p.items.append(it)
            made.append((p.char.name, count))
            return it
        with patch('dcemu.native.game.mail.sendable', return_value=True), \
                patch('dcemu.native.game.items.new_item', new_item), \
                patch('dcemu.native.game.items.stack_for', return_value=None), \
                patch('dcemu.native.game.items.add_money', AsyncMock(return_value=True)) as money_, \
                patch.object(trade, 'stat_frames', return_value=[]):
            self.run_(trade.trade_complete, self.a, struct.pack('<I', tid))
            self.run_(trade.trade_complete, self.b, struct.pack('<I', tid))
        self.assertEqual(made, [('Bob', 2)])
        self.assertEqual(self.a.state['player'].items[0].stack, 1)
        self.assertEqual(sorted(c.args[1] for c in money_.await_args_list), [-30, 30])
        done = [struct.unpack_from('<I', f.payload, 4)[0] for f in self.frames(0x201, self.a)]
        self.assertEqual(done, [4, 5])
        self.assertFalse(trade.trades)

    def test_busy_player_cannot_trade(self):
        self.open_trade()
        c = session(player('Carol', 33, 0, []))
        with patch.object(trade, 'send', side_effect=lambda to, f: self.sent.append((to, f))), \
                patch.object(trade, 'by_name', return_value=self.a), \
                patch.object(trade, 'error', side_effect=lambda to, k: self.sent.append((to, k))):
            asyncio.run(trade.trade_open(c, SimpleNamespace(payload='Alice'.encode('utf-16-le').ljust(42, b'\0'))))
        self.assertIn((c, '20115'), self.sent)

    def test_2016_mito_trade_flag_and_override(self):
        version.configure({'version': '2016'})
        context.data = SimpleNamespace(contents={})
        self.assertEqual(login.content_flags()[0x4f] & 2, 2)
        tid = self.open_trade()
        context.extra_flags = {'Etc.MitoTrade': 0}
        self.assertEqual(login.content_flags()[0x4f] & 2, 0)
        self.run_(trade.trade_money, self.b, struct.pack('<Iq', tid, 30))
        self.assertFalse(self.frames(0x203))
        self.assertEqual(trade.trades[tid].guest.money, 0)

    def test_2016_mixed_trade_commits_together_or_keeps_the_offer_items(self):
        version.configure({'version': '2016'})
        info = SimpleNamespace(item_id='i_a', table_idx=40, type=5, kind='')
        context.data = SimpleNamespace(item_info=lambda _: info)
        for enough_mito in (False, True):
            with self.subTest(enough_mito=enough_mito):
                self.sent.clear()
                tid = self.open_trade()
                host_inventory = self.a.state['player'].items
                with patch('dcemu.native.game.mail.sendable', return_value=True):
                    self.run_(trade.trade_item_on, self.a, struct.pack('<IIi', tid, 5, 2))
                self.run_(trade.trade_money, self.b, struct.pack('<Iq', tid, 30))
                for s in (self.a, self.b):
                    self.run_(trade.trade_lock, s, struct.pack('<IH', tid, 1))
                cursor = Mock(rowcount=1)
                cursor.fetchone.side_effect = [(1000, 100), (50 if enough_mito else 0, 100),
                                               (1030,), (20,), (900,)]
                transaction = AsyncMock(side_effect=lambda operation: operation(cursor))
                context.db.transaction = transaction
                with patch('dcemu.native.game.mail.sendable', return_value=True), \
                        patch('dcemu.native.game.setparts.period', return_value=0), \
                        patch.object(trade, 'stat_frames', return_value=[]):
                    self.run_(trade.trade_complete, self.a, struct.pack('<I', tid))
                    self.run_(trade.trade_complete, self.b, struct.pack('<I', tid))
                transaction.assert_awaited_once()
                context.db.execute.assert_not_awaited()
                self.assertNotIn(tid, trade.trades)
                self.assertEqual(host_inventory[0].stack, 1 if enough_mito else 3)
                self.assertEqual([it.stack for it in self.b.state['player'].items], [2] if enough_mito else [])
                self.assertEqual(len(self.frames(0x8a)), 2 if enough_mito else 0)
                if not enough_mito:
                    self.assertEqual(cursor.execute.call_count, 2)


    def test_rules_of_open(self):
        other_channel = session(player('Dan', 44, 0, []))
        other_channel.state['channel'] = 2
        with patch.object(trade, 'send', side_effect=lambda to, f: self.sent.append((to, f))), \
                patch.object(trade, 'by_name', return_value=other_channel), \
                patch.object(trade, 'is_admin', side_effect=lambda s: s is other_channel), \
                patch.object(trade, 'error', side_effect=lambda to, k: self.sent.append((to, k))):
            asyncio.run(trade.trade_open(self.a, SimpleNamespace(payload='Dan'.encode('utf-16-le').ljust(42, b'\0'))))
            other_channel.state['channel'] = 1
            asyncio.run(trade.trade_open(self.a, SimpleNamespace(payload='Dan'.encode('utf-16-le').ljust(42, b'\0'))))
        self.assertEqual([k for s, k in self.sent], ['20014', '20114'])
