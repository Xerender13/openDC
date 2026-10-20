"""2016 drift auction handlers: wire records, ownership, money and replay races.

All sessions and database operations are isolated stubs; no live character is used.
"""
import asyncio
from contextlib import ExitStack
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.handlers import handlers_for
from dcemu.native import context, version
from dcemu.native.game import auction, items, vshop
from dcemu.native.game.records import VisualItem
from dcemu.protocol import C2S
from dcemu.wire import Frame


class Auction2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.auction_drift = True
        context.auction_days = 7
        context.auction_drift_fee = 10
        context.auction_min_level = 10
        context.data = SimpleNamespace(server_text={}, visual_index={'paint': 101}, visuals={101: object()},
                                       vshop={101: {'UseHancoin': '1', 'MarketName': 'White Paint', 'Main': '1000'}})
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock(), row=AsyncMock(return_value=(123,)))
        self.char = SimpleNamespace(cid=7, name='Seller', level=55, mito=10000)
        self.v = VisualItem(44, 'paint', 62, 0, 0, 'custom', 7, 0, 0, 101)
        self.p = SimpleNamespace(char=self.char, vsitems=[self.v], items=[])
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()), to_client=Mock())
        self.sent = []
        self.money = []
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(auction, 'LOCK', asyncio.Lock()))
        self.patches.enter_context(patch.object(auction, 'send', side_effect=lambda s, *f: self.sent.extend(f)))
        self.patches.enter_context(patch.object(auction, 'fee_for', side_effect=lambda price, percent, p: price // 10))
        self.patches.enter_context(patch.object(items, 'bonus_update', return_value=Frame(0x5dd, b'')))
        self.patches.enter_context(patch.object(vshop, 'vs_mod_list', side_effect=lambda *args: Frame(0x4b2, b'')))
        self.patches.enter_context(patch.object(vshop, 'save_state', AsyncMock()))
        self.patches.enter_context(patch.object(auction, 'ensure_tables', AsyncMock()))
        self.patches.enter_context(patch.object(auction, 'count_up', AsyncMock()))
        self.patches.enter_context(patch.object(auction, 'count_up_cid', AsyncMock()))
        self.patches.enter_context(patch.object(auction, 'next_serial', AsyncMock(return_value=9)))
        self.patches.enter_context(patch.object(items, 'add_money', AsyncMock(side_effect=self.add_money)))
        self.patches.enter_context(patch.object(auction, 'seller_session', return_value=self.s))

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    async def add_money(self, c, delta):
        if c.mito + delta < 0:
            return False
        c.mito += delta
        self.money.append((c.cid, delta))
        return True

    def listing(self, state=auction.ON_SALE, cid=7, period=7, ctime=0):
        # SQL projection followed by seller counters and listing age.
        return auction.Listing(auction.DRIFT,
            [cid, 'Seller', 9, 'paint', 62, 'custom', period, ctime, ctime + 1, 1000, state, 3, 2, 1, 0])

    def request(self):
        return Frame(0x642, struct.pack('<4I', 101, 62, 1, 1000))

    def test_register_and_lists_keep_native_2016_record_sizes(self):
        x = self.listing()
        with patch.object(auction, 'listing', AsyncMock(return_value=x)):
            asyncio.run(auction.auction_vs_on(self.s, self.request()))
        self.assertEqual(self.v.state, auction.LOCKED)
        self.assertEqual(self.money, [(7, -100)])
        ack = next(f for f in self.sent if f.type == 0x643)
        self.assertEqual(len(ack.payload), 102)  # native104 includes two-byte message type
        self.assertEqual(struct.unpack_from('<II', ack.payload), (62, 100))
        self.assertEqual(len(x.body()), 66)
        self.assertEqual(struct.unpack_from('<II', x.body()), (101, 62))
        with patch.object(auction, 'listings', AsyncMock(return_value=[x])):
            mine = asyncio.run(auction.my_list(auction.DRIFT, self.p))
        self.assertEqual((mine.type, len(mine.payload)), (0x641, 8 + 94))
        public = auction.list_frame(0x649, [x], 0, 13)
        self.assertEqual(len(public.payload), 8 + 156)
        self.assertEqual(struct.unpack_from('<II', public.payload), (1, 1))

    def test_public_filter_search_and_disabled_flag(self):
        x = self.listing()
        async def call(msg, data):
            handler = handlers_for(auction.SVC, C2S, msg)[0]
            await handler(self.s, Frame(msg, data))
        with patch.object(auction, 'listings', AsyncMock(return_value=[x])):
            asyncio.run(call(0x648, struct.pack('<6I', 0, 13, 1000, 5, 0, 0)))
            self.assertEqual(struct.unpack_from('<II', self.sent[-1].payload), (1, 1))
            def search(who, option):     # 2016 boxes: "User ID/Item Name", "Option Name"
                data = struct.pack('<5I', 0, 13, 1000, 5, 0) + who.encode('utf-16le').ljust(256, b'\0')
                asyncio.run(call(0x64f, data + option.encode('utf-16le').ljust(256, b'\0') + struct.pack('<II', 0, 0)))
                return struct.unpack_from('<I', self.sent[-1].payload)[0]
            self.assertEqual((search('White', ''), self.sent[-1].type, len(self.sent[-1].payload)), (1, 0x650, 164))
            self.assertEqual([search(x.seller, ''), search('', 'Paint'), search('', 'Nope'), search('Nobody', '')],
                             [1, 1, 0, 0])
            context.auction_drift = False
            asyncio.run(call(0x648, struct.pack('<6I', 0, 13, 0, 0, 0, 0)))
            self.assertEqual(struct.unpack_from('<II', self.sent[-1].payload), (0, 0))

    def test_2016_time_headers_sort_listing_days_and_item_lifetime(self):
        a, b = self.listing(period=7, ctime=100), self.listing(period=30, ctime=200)
        a.elapsed, b.elapsed = 2 * 86400, 86400
        self.assertEqual(auction.sort_list([a, b], 14), [b, a])
        self.assertEqual(auction.sort_list([a, b], 15), [a, b])
        with patch('dcemu.native.now', return_value=1000):
            self.assertEqual(auction.sort_list([a, b], 16), [b, a])
            self.assertEqual(auction.sort_list([a, b], 17), [a, b])
            forever = self.listing(period=0)
            self.assertEqual(auction.sort_list([a, forever], 16), [forever, a])
        version.configure({'version': '2011'})
        self.assertEqual(auction.sort_list([a, b], 14), [a, b])

    def test_register_refuses_bound_locked_expired_mito_and_bad_count(self):
        variants = [('car_id', 42), ('state', 4), ('ctime', 1)]
        for field, value in variants:
            with self.subTest(field=field):
                old = getattr(self.v, field)
                setattr(self.v, field, value)
                asyncio.run(auction.auction_vs_on(self.s, self.request()))
                setattr(self.v, field, old)
        context.data.vshop[101]['UseHancoin'] = '0'
        asyncio.run(auction.auction_vs_on(self.s, self.request()))
        context.data.vshop[101]['UseHancoin'] = '1'
        asyncio.run(auction.auction_vs_on(self.s, Frame(0x642, struct.pack('<4I', 101, 62, 2, 1000))))
        self.assertEqual(self.money, [])

    def test_two_pending_registrations_charge_once(self):
        async def race():
            # Both requests pass their initial check while setup yields.
            async def setup():
                await asyncio.sleep(0)
            with patch.object(auction, 'ensure_tables', side_effect=setup), \
                    patch.object(auction, 'listing', AsyncMock(return_value=self.listing())):
                await asyncio.gather(*(auction.auction_vs_on(self.s, self.request()) for _ in range(2)))
        asyncio.run(race())
        self.assertEqual(self.money, [(7, -100)])
        self.assertEqual(sum(f.type == 0x643 for f in self.sent), 1)

    def test_buy_preserves_term_data_and_notifies_seller(self):
        x = self.listing()
        self.char.cid, self.char.name = 8, 'Buyer'
        self.p.vsitems = []
        with patch.object(auction, 'listing', AsyncMock(return_value=x)):
            asyncio.run(auction.auction_vs_buy(self.s, Frame(0x64c, struct.pack('<I', 9))))
        v, = self.p.vsitems
        self.assertEqual((v.item_id, v.data, v.period, v.ctime, v.utime), ('paint', 'custom', 7, 0, 1))
        self.assertEqual((v.car_id, v.state, v.inven_idx), (0, 0, 62))
        self.assertEqual(self.money, [(8, -1000)])
        self.assertIn(0x64d, [f.type for f in self.sent])
        self.s.to_client.assert_called_once()
        self.assertEqual(self.s.to_client.call_args.args[0].type, 0x64e)

    def test_buy_refuses_self_expiry_no_money_or_already_claimed(self):
        for x, money, claimed in ((self.listing(), 10000, 1),
                (self.listing(cid=1, period=1, ctime=1), 10000, 1),
                (self.listing(cid=1), 0, 1), (self.listing(cid=1), 10000, 0)):
            with self.subTest(cid=x.cid, money=money, claimed=claimed):
                self.char.mito = money
                context.db.row.return_value = (claimed,)
                with patch.object(auction, 'listing', AsyncMock(return_value=x)):
                    asyncio.run(auction.auction_vs_buy(self.s, Frame(0x64c, struct.pack('<I', 9))))
        self.assertEqual(self.money, [])

    def test_cancel_unlocks_without_refunding_fee(self):
        self.v.state = 4
        for state in (auction.ON_SALE, auction.EXPIRED):
            with patch.object(auction, 'listing', AsyncMock(return_value=self.listing(state))):
                asyncio.run(auction.auction_vs_cancel(self.s, Frame(0x644, struct.pack('<I', 9))))
            self.assertEqual(self.v.state, 0)
        self.assertEqual(self.money, [])
        self.assertEqual(sum(f.type == 0x645 for f in self.sent), 2)

    def test_cancel_rechecks_sale_after_lock(self):
        self.v.state = 4
        with patch.object(auction, 'listing', AsyncMock(side_effect=[self.listing(), self.listing(auction.SOLD)])):
            asyncio.run(auction.auction_vs_cancel(self.s, Frame(0x644, struct.pack('<I', 9))))
        self.assertEqual(self.v.state, 4)
        context.db.execute.assert_not_awaited()

    def test_collect_pays_once_and_removes_locked_original(self):
        self.v.state = 4
        sold = self.listing(auction.SOLD)
        # First lookup and revalidation succeed, subsequent replay finds nothing.
        with patch.object(auction, 'listing', AsyncMock(side_effect=[sold, sold, None])):
            asyncio.run(auction.auction_vs_complete(self.s, Frame(0x646, struct.pack('<I', 9))))
            asyncio.run(auction.auction_vs_complete(self.s, Frame(0x646, struct.pack('<I', 9))))
        self.assertEqual(self.money, [(7, 1000)])
        self.assertEqual(self.p.vsitems, [])
        self.assertEqual(sum(f.type == 0x647 for f in self.sent), 1)

    def test_pending_collect_cannot_pay_a_deleted_listing(self):
        with patch.object(auction, 'listing', AsyncMock(side_effect=[self.listing(auction.SOLD), None])):
            asyncio.run(auction.auction_vs_complete(self.s, Frame(0x646, struct.pack('<I', 9))))
        self.assertEqual(self.money, [])
        context.db.execute.assert_not_awaited()
