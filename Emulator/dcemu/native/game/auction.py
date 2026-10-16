"""The Auction House: parts and usable items, cars (emulator.ini [auction] cars) and drift items ([auction]
drift_items). The rules are the 2008 server's (PacketParser::Cmd_Auction*, XiAuctionMgr, XiAuctionCarMgr,
XiCsCharInfo::Auction*); the 2011 layouts are from the client's handlers.

Listings: SKID_AUCTION_TB (items), SKID_AUCTIONCAR_TB (cars), both the 2008 server's, and SKID_AUCTIONVS_TB
(drift items; the 2008 server had no drift item auction, the table is made here on first use with the
columns of SKID_VSITEM_TB). SKID_AUCTIONMILEAGE_TB counts each character's registrations / purchases / sales
(shown with the seller in the lists). REGID is the listing's serial.

States (XiAuctionItem Info.State): 1 on sale, 2 sold (the seller collects the money with Complete), 3 expired
(the seller takes the item back with Cancel), 4 done (the row is deleted here). A listing runs for
[auction] days (7: XiAuctionItem::CalcPeriod = 7 - whole days since REGDATE; client text 10572 "If not sold
after 7 days, it will expire."); an expired listing leaves the public lists and stays in the seller's list
(XiAuctionMgr::UpdateAuctionPeriod, run here before every auction request).

Registering (2008 XiCsCharInfo::AuctionOn): the fee is taken at once and not given back: price x commission %,
at least 1 (items Main.AuctionCommission, drift items Main.AuctionVSCommission: [auction] item_fee / drift_fee,
also sent as those flags, the client shows them; cars price x CarTaxReg 10 %: [auction] car_fee). The item
stays with the seller in state 4 (XiStrMyItem / XiStrMyVSItem state; the client looks the listing's item up in
its own inventory by InvenIdx and skips listings whose item it does not hold); a usable item registered from a
bigger stack is split off. A part needs the table's trade column (ItemClient column 17, UseItemClient
column 15) and not be a hyper part (grade H: all need one, user 2026-10-14), or have a Parts Box on it (BOX column;
0x1a6 / 0x1a3, items.py), no Belonging, not on a car. A car (XiCsCharInfo::AuctionCarOn): the car auction open (else 20238),
not the current car, never bought at auction (AUCTIONCNT 0: text 10586), no part on it, its key (the usable
item named after the car) goes to state 4. The drift items on it (state 1) are deleted at registration: the 2011
client checks the car first (0x71ab80, from 0x5f6176): a part on it, or a drift item for which 0x72c770 is true
(its VShop row's +0xfc > 0: the "CC items" of the refusal text 10578), refuses; any other drift item on it asks
text 11147 "Equipped items on selected car will be removed permanently. Do you want to proceed?" and sends 0x6a6
on Yes (user, 2026-10-14: the server refused it). The 2008 server had no such step. Unequipped paint / neon /
tint still bound to the car are deleted with it when it is sold. A drift item: in the drift inventory (state 0), not run out, bought with G Coin (text 12146:
"You cannot register the Skid Items purchased with Mitto").

Buying (XiAuctionMgr::AuctionBuy, XiCsCharInfo::AuctionBuy): on sale, not expired, not the buyer's own (text
10499), the price in money; the buyer gets a new item with the listing's values (Box cleared: the part comes out
of its box), a car (AUCTIONCNT + 1: it cannot be auctioned again) with its key, a drift item (its period keeps
running from its CTIME). The seller is told (0x252 / 0x64e / 0x6b0) and collects the money later with Complete
(their item / car / drift item is deleted then).

Messages (C>S as 2008 except the item / drift item searches; S>C 2011):
  0x244 / 0x640 / 0x6a4 my listings -> 0x245 / 0x641 / 0x6a5 (u32 ListUpdate 0x40000, u32 n, n x entry)
  0x24c / 0x648 / 0x6ac list (Offset, ListNum 13, Type, SortType, StLevel, EnLevel) -> 0x24d / 0x649 / 0x6ad
  0x253 / 0x64f (2011 0x21e: + SearchType, item text 128 wchar, seller text 128 wchar, StLevel, EnLevel),
      0x6b1 (0x11e: one text) search -> 0x254 / 0x650 / 0x6b2 (u32 total, u32 n, n x seller + entry)
  0x246 / 0x642 (TableIdx, InvenIdx, ItemNum, Price), 0x6a6 (TableIdx, key InvenIdx, CarID, Price) register
      -> 0x192 / 0x4b2 then 0x247 / 0x643 / 0x6a7 (InvenIdx, fee: the client takes it off its money, entry)
  0x248 / 0x644 / 0x6a8 cancel (Serial) -> 0x249 / 0x645 / 0x6a9 (Serial), then the item back (state 0)
  0x24a / 0x646 / 0x6aa complete (Serial) -> 0x24b / 0x647 / 0x6ab (Serial, Price: the client adds it)
  0x250 / 0x64c buy (Serial), 0x6ae (Serial, CarType, Grade, Price) -> the new item, then 0x251 / 0x64d
      (Serial, Price: the client takes it off) / 0x6af (Serial, Price, XiStrCarInfo); 0x252 / 0x64e / 0x6b0
      (Serial) to the seller
Entries: XiStrAuctionUnit (2011: 28 bytes: Serial, TableIdx, InvenIdx, Price, State, RegDate, + a u32 the
client prints as a number in the list rows: the days left here, a guess) + XiStrItemUnit (2011: 72 bytes =
XiStrMyItem @8..@0x50) / XiStrCarUnit (32) / drift item (66 bytes: TableIdx, InvenIdx, text 42 bytes, Period
@0x32, start time @0x36 (the client counts the period from it), CTIME, 0; partly a guess); the public lists put
XiStrAuctionClientUnit (62: Cid, name, RegNum, BuyNum, SellNum) before each.
Type (the list filter): 0 = all; items 1-4 parts, 6-10 option parts, 11-14 docking parts, 5 general items; cars the grade; drift items
VShopItem "Main" (type_fits). SortType 0-13 (2008 XiAuctionMgr m_SortFuncs): serial, level, name,
price, count, seller name, seller's sales; even = descending.
0x708 (u32 1 / 0, at login): the car auction open (client [mgr + 0x824]).
The drift item auction is in the client's code (GlobalContent.xlt AuctionVSItem = 1), but the US UI layout
(game.nui) has no drift item tab and no images for the header set that mode switches to (controls 1220030..38:
the column titles go blank). Tried 2026-10-14 and reverted: the US client keeps AuctionVSItem = 0, so the drift
item handlers here are unused unless the UI layout is extended.
"""
import asyncio
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context, time_t
from .login import LIST_FULL, SVC, error, send, stat_frames
from .records import Car, Item, name_bytes, wstr

ON_SALE, SOLD, EXPIRED = 1, 2, 3
LOCKED = 4                       # item / drift item state while registered
CARS_PER_FLOOR = 8
LOCK = asyncio.Lock()            # one auction change at a time (serials, two buyers of one listing)

VS_TABLE_SQL = """IF OBJECT_ID(N'dbo.SKID_AUCTIONVS_TB', N'U') IS NULL
CREATE TABLE dbo.SKID_AUCTIONVS_TB(SERVERID numeric(18,0) NOT NULL, CID numeric(18,0) NOT NULL,
  CNAME varchar(32) NOT NULL, REGID numeric(18,0) NOT NULL, ITEMID varchar(32) NOT NULL,
  INVENIDX numeric(18,0) NOT NULL, ITEM_DATA varchar(20) NULL, PERIOD numeric(18,0) NOT NULL,
  CTIME numeric(18,0) NOT NULL, UTIME numeric(18,0) NOT NULL, PRICE numeric(18,0) NOT NULL,
  STATE numeric(18,0) NOT NULL, REGDATE datetime NULL DEFAULT (getdate()),
  PRIMARY KEY CLUSTERED (CID, SERVERID, REGID))"""
MILEAGE_SQL = """IF NOT EXISTS (SELECT 1 FROM SKID_AUCTIONMILEAGE_TB WHERE SERVERID=%s AND CID=%s)
  INSERT INTO SKID_AUCTIONMILEAGE_TB(SERVERID, CID, CNAME, REGNUM, BUYNUM, SELLNUM) VALUES (%s, %s, %s, 0, 0, 0);
UPDATE SKID_AUCTIONMILEAGE_TB SET {col}={col}+1 WHERE SERVERID=%s AND CID=%s"""
SELLER = ("m.REGNUM, m.BUYNUM, m.SELLNUM, DATEDIFF(second, a.REGDATE, GETDATE()) FROM {table} a"
          " LEFT OUTER JOIN SKID_AUCTIONMILEAGE_TB m ON m.SERVERID=a.SERVERID AND m.CID=a.CID WHERE a.SERVERID=%s")
CLAIM_SQL = """SET NOCOUNT ON; UPDATE {table} SET STATE=2 WHERE SERVERID=%s AND REGID=%s AND STATE=1
  AND DATEDIFF(second, REGDATE, GETDATE()) < %s; SELECT @@ROWCOUNT"""
UNCLAIM_SQL = "UPDATE {table} SET STATE=1 WHERE SERVERID=%s AND REGID=%s"
DELETE_SQL = "DELETE FROM {table} WHERE SERVERID=%s AND REGID=%s"
EXPIRE_SQL = ("UPDATE {table} SET STATE=3 WHERE SERVERID=%s AND STATE=1"
              " AND DATEDIFF(second, REGDATE, GETDATE()) >= %s")
SERIAL_SQL = "SELECT ISNULL(MAX(REGID), 0) + 1 FROM {table} WHERE SERVERID=%s"


class Kind:
    """What differs between the three auctions."""
    def __init__(self, name, table, cols, types):
        self.name, self.table, self.cols = name, table, cols
        (self.my_ack, self.list_ack, self.search_ack, self.on_ack, self.cancel_ack, self.complete_ack,
         self.buy_ack, self.buyed) = types


ITEMS = Kind('item', 'SKID_AUCTION_TB',
             'a.CID, a.CNAME, a.REGID, a.ITEMID, a.ITEMNUM, a.NRANDOM, a.NUPGRADE, a.INVENIDX, a.PRICE, a.STATE,'
             ' a.ASSIST_A, a.ASSIST_B, a.BOX, a.CTIME',
             (0x245, 0x24d, 0x254, 0x247, 0x249, 0x24b, 0x251, 0x252))
CARS = Kind('car', 'SKID_AUCTIONCAR_TB',
            'a.CID, a.CNAME, a.REGID, a.ITEMID, a.INVENIDX, a.CARID, a.CARTYPE, a.BASECOLOR, a.NGRADE, a.NSLOT,'
            ' a.FMITRON, a.FKMH, a.PRICE, a.STATE',
            (0x6a5, 0x6ad, 0x6b2, 0x6a7, 0x6a9, 0x6ab, 0x6af, 0x6b0))
DRIFT = Kind('drift item', 'SKID_AUCTIONVS_TB',
             'a.CID, a.CNAME, a.REGID, a.ITEMID, a.INVENIDX, a.ITEM_DATA, a.PERIOD, a.CTIME, a.UTIME, a.PRICE, a.STATE',
             (0x641, 0x649, 0x650, 0x643, 0x645, 0x647, 0x64d, 0x64e))
_vs_table_ready = False


def _i(v):
    return int(v) if v is not None else 0


def period_seconds():
    return context.auction_days * 86400


def days_left(elapsed):
    """XiAuctionItem::CalcPeriod: listing days - whole days since registration, at least 0."""
    return max(0, context.auction_days - elapsed // 86400)


AUCTION_MIN = 20000                     # licenses: GC_AuctionOn / GC_AuctionSuccess count 20k Mito or more


def fee_for(price, percent, p=None):
    """The registration fee; the mounted licenses' fee discounts (ME_AuctionFeeDis, ME_FeeDis) taken off."""
    fee = max(1, int(price * percent / 100))
    if p:
        from .licenses import fee_discount
        fee = max(1, fee * (100 - fee_discount(p, 'auction')) // 100)
    return fee


class Listing:
    """One row of a listing table, with the seller's counters."""
    def __init__(self, kind, r):
        self.kind = kind
        n = len(kind.cols.split(','))
        self.f = r[:n]
        self.cid, self.seller, self.serial, self.item_id = int(r[0]), r[1], _i(r[2]), r[3]
        self.reg, self.bought, self.sold, self.elapsed = (_i(x) for x in r[n:n + 4])
        self.regdate = None
        price_col = {'item': 8, 'car': 12, 'drift item': 9}[kind.name]
        self.price, self.state = _i(r[price_col]), _i(r[price_col + 1])
        if self.state == ON_SALE and self.elapsed >= period_seconds():
            self.state = EXPIRED

    # --- what the listing holds ---
    def item(self):
        """ITEMS: the item as an Item record (no car, state 0)."""
        f = self.f
        t = context.data
        return Item(0, _i(f[7]), f[3], 0, _i(f[4]), _i(f[5]), 0, _i(f[6]), 0, f[10] or '', f[11] or '', _i(f[12]),
                    _i(f[13]), t.item_index.get(f[3], -1))

    def car(self):
        f = self.f
        return Car(_i(f[5]), _i(f[6]), _i(f[7]), _i(f[8]), 0, float(f[10] or 0), float(f[11] or 0), _i(f[9]))

    def drift(self):
        """DRIFT: (table idx, inven, text, period, ctime, utime)."""
        f = self.f
        return context.data.visual_index.get(f[3], 0), _i(f[4]), f[5] or '', _i(f[6]), _i(f[7]), _i(f[8])

    @property
    def inven_idx(self):
        return _i(self.f[4] if self.kind is not ITEMS else self.f[7])

    @property
    def table_idx(self):
        if self.kind is ITEMS:
            return context.data.item_index.get(self.item_id, -1)
        if self.kind is CARS:
            return context.data.item_index.get(self.item_id, -1)     # the key's
        return context.data.visual_index.get(self.item_id, 0)

    # --- sorting / filtering ---
    def name(self):
        t = context.data
        if self.kind is ITEMS:
            info = t.item_info(self.table_idx)
            return (info.name if info else '') or self.item_id
        if self.kind is CARS:
            v = t.vehicles.get(self.car().car_type) or {}
            return v.get('UI Name') or self.item_id
        row = t.vshop.get(self.table_idx) or {}
        return row.get('MarketName') or self.item_id

    def level(self):
        if self.kind is ITEMS:
            info = context.data.item_info(self.table_idx)
            return info.req_level if info else 0
        if self.kind is CARS:
            return self.car().grade
        return 0

    def count(self):
        return _i(self.f[4]) if self.kind is ITEMS else 1

    # --- records ---
    def unit(self, inven_idx=None):
        return struct.pack('<6Ii', self.serial, self.table_idx, self.inven_idx if inven_idx is None else inven_idx,
                           self.price, self.state, time_t(self.regdate) if self.regdate else 0,
                           days_left(self.elapsed))

    def body(self, own=None):
        """The entry after the auction unit; own: the seller's own item / drift item record, if held."""
        if self.kind is ITEMS:
            return (own or self.item()).encode()[8:0x50]
        if self.kind is CARS:
            return self.car().unit()
        table_idx, inven, text, period, ctime, utime = self.drift()
        return struct.pack('<II', table_idx, inven) + wstr(text, 42) + struct.pack('<iiii', period, ctime, ctime, 0)

    def client_unit(self):
        return struct.pack('<q', self.cid) + name_bytes(self.seller) + struct.pack('<III', self.reg, self.bought,
                                                                                  self.sold)


async def ensure_tables():
    global _vs_table_ready
    if not _vs_table_ready:
        await context.db.execute(VS_TABLE_SQL)
        _vs_table_ready = True


async def expire_old():
    """XiAuctionMgr::UpdateAuctionPeriod: listings past their period become state 3 (expired)."""
    db = context.db
    await ensure_tables()
    for kind in (ITEMS, CARS, DRIFT):
        await db.execute(EXPIRE_SQL.format(table=kind.table), (db.server_id, period_seconds()))


async def listings(kind, where='', params=()):
    db = context.db
    await expire_old()
    rows = await db.rows(f'SELECT {kind.cols}, a.REGDATE, ' + SELLER.format(table=kind.table) + where,
                         (db.server_id, *params))
    out = []
    for r in rows:
        r = list(r)
        regdate = r.pop(len(kind.cols.split(',')))
        x = Listing(kind, r)
        x.regdate = regdate
        out.append(x)
    return out


async def listing(kind, serial):
    found = await listings(kind, ' AND a.REGID=%s', (serial,))
    return found[0] if found else None


async def count_up(c, col):
    db = context.db
    await db.execute(MILEAGE_SQL.format(col=col), (db.server_id, c.cid, db.server_id, c.cid, c.name, db.server_id,
                                                   c.cid))


async def count_up_cid(cid, name, col):
    class C:
        pass
    c = C()
    c.cid, c.name = cid, name
    await count_up(c, col)


_last_serial = {}


async def next_serial(kind):
    """A new listing's REGID: above every one in the table and every one given since the start (a collected or
    cancelled listing's row is deleted; its serial is not given again while the emulator runs)."""
    db = context.db
    n = max(int((await db.row(SERIAL_SQL.format(table=kind.table), (db.server_id,)))[0]),
            _last_serial.get(kind.name, 0) + 1)
    _last_serial[kind.name] = n
    return n


def seller_session(cid):
    from .login import sessions
    return next((s for s in list(sessions.values()) if s.state.get('player') and s.state['player'].char.cid == cid),
                None)


def can_use(session, p):
    if p.char.level < context.auction_min_level:
        error(session, f'Player with less than level {context.auction_min_level} cannot use Auction House')
        return False
    return True


# --- lists -----------------------------------------------------------------------------------------------
SORT_KEYS = (lambda x: x.serial, lambda x: x.level(), lambda x: x.name().lower(), lambda x: x.price,
             lambda x: x.count(), lambda x: (x.seller or '').lower(), lambda x: x.sold)


def sort_list(found, sort_type):
    if 0 <= sort_type < 14:
        found.sort(key=SORT_KEYS[sort_type // 2], reverse=sort_type % 2 == 0)
    return found


# The client's list filters (tables {label[32], value} at 0x93aa78 / 0x93ad28 / 0x93ae90; the item labels are filled at
# start from texts 10493-10497, 10918-10922, 11005-11008, 10498 in that order): 0 = All Items; items 1-4 speed /
# durability / acceleration / booster parts, 6-10 their option parts and the all-use ones, 11-14 speed / crash / accel /
# booster docking parts, 5 General Items (the rest); cars the grade (V1 = 1); drift items VShopItem "Main".
ITEM_TABS = {'speed': 1, 'crash': 2, 'accel': 3, 'boost': 4, 'op_S': 6, 'op_C': 7, 'op_A': 8, 'op_B': 9, 'op_F': 10,
             'dock_S': 11, 'dock_C': 12, 'dock_A': 13, 'dock_B': 14}
GENERAL_TAB = 5


def type_fits(kind, x, type_):
    if not type_:
        return True
    if kind is ITEMS:
        info = context.data.item_info(x.table_idx)
        return ITEM_TABS.get(info.kind if info and info.type != 5 else '', GENERAL_TAB) == type_
    if kind is CARS:
        return x.car().grade == type_
    row = context.data.vshop.get(x.table_idx) or {}
    return row.get('Main', '') == str(type_)


def level_fits(x, lo, hi):
    lv = x.level()
    return (not lo or lv >= lo) and (not hi or lv <= hi)


async def public_list(kind, type_, lo, hi, item_text='', seller_text=''):
    found = [x for x in await listings(kind, ' AND a.STATE=1') if x.state == ON_SALE and type_fits(kind, x, type_)
             and level_fits(x, lo, hi)]
    if item_text:
        found = [x for x in found if item_text.lower() in x.name().lower()]
    if seller_text:
        found = [x for x in found if seller_text.lower() in (x.seller or '').lower()]
    return found


def list_frame(type_, found, offset, count):
    page = found[offset:offset + max(0, min(count, 50))]
    return Frame(type_, struct.pack('<II', len(found), len(page))
                 + b''.join(x.client_unit() + x.unit() + x.body() for x in page))


async def my_list(kind, p):
    found = sort_list(await listings(kind, ' AND a.CID=%s', (p.char.cid,)), 1)
    out = []
    for x in found:
        own = next((i for i in p.items if i.inven_idx == x.inven_idx), None) if kind is ITEMS else None
        out.append(x.unit() + x.body(own))
    return Frame(kind.my_ack, struct.pack('<II', LIST_FULL, len(out)) + b''.join(out))


def _kind_on(kind):
    return kind is ITEMS or (kind is CARS and context.auction_cars) or (kind is DRIFT and context.auction_drift)


def register_lists(kind, my_type, list_type, search_type, search_size):
    @on(SVC, C2S, my_type)
    async def my(session, frame):
        p = session.state.get('player')
        if p:                                      # also with the switch off: the seller can still take back / collect
            send(session, await my_list(kind, p))

    @on(SVC, C2S, list_type)
    async def public(session, frame):
        p = session.state.get('player')
        if not p or len(frame.payload) < 24:
            return
        offset, count, type_, sort, lo, hi = struct.unpack_from('<6I', frame.payload)
        found = sort_list(await public_list(kind, type_, lo, hi), sort) if _kind_on(kind) else []
        session.log.note(f'{kind.name} auction list type {type_} sort {sort} levels {lo}-{hi}: {len(found)}')
        send(session, list_frame(kind.list_ack, found, offset, count))

    @on(SVC, C2S, search_type)
    async def search(session, frame):
        p = session.state.get('player')
        if not p or len(frame.payload) < search_size - 2:
            return
        offset, count, type_, sort, search_t = struct.unpack_from('<5I', frame.payload)
        if search_size == 0x21e:                   # 2011: item text, seller text
            item_text, seller_text = read_wstr(frame.payload, 0x14, 0x100), read_wstr(frame.payload, 0x114, 0x100)
            lo, hi = struct.unpack_from('<II', frame.payload, 0x214)
        else:                                      # cars: one text (car or seller name by SearchType)
            text = read_wstr(frame.payload, 0x14, 0x100)
            item_text, seller_text = (text, '') if search_t in (0, 1, 3) else ('', text)
            lo, hi = struct.unpack_from('<II', frame.payload, 0x114)
        found = sort_list(await public_list(kind, type_, lo, hi, item_text.strip(), seller_text.strip()), sort) \
            if _kind_on(kind) else []
        session.log.note(f'{kind.name} auction search {item_text!r} / {seller_text!r} type {type_}: {len(found)}')
        send(session, list_frame(kind.search_ack, found, offset, count))


register_lists(ITEMS, 0x244, 0x24c, 0x253, 0x21e)
register_lists(DRIFT, 0x640, 0x648, 0x64f, 0x21e)
register_lists(CARS, 0x6a4, 0x6ac, 0x6b1, 0x11e)


# --- registering -----------------------------------------------------------------------------------------
def item_refusal(p, it, count):
    """Why this item cannot be registered (a GlobalText_Server key), or None (2008 XiCsCharInfo::AuctionOn)."""
    from .items import info_of
    info = info_of(it) if it else None
    if not it or not info:
        return '20050'
    if it.car_id or (it.state & 0xffff) != 0 or count < 1 or count > max(it.stack, 1) or info.kind == 'car':
        return '20063'
    if it.belonging or it.upgrade < 0:             # bound, or a broken part
        return '20063'
    from .items import boxed, needs_box
    if needs_box(it, info) and not boxed(it):      # hyper parts / untradeable: only in a Parts Box (user, 2026-10-14)
        return '20062'
    from .upgrade import expired
    if info.type == 5 and expired(p, it):          # run-out timed items, e.g. Mittron Enhancers (text 11579)
        return 'Expired Strengtheners cannot be registered at the Auction Hall.'
    return None


@on(SVC, C2S, 0x246)
async def auction_on(session, frame):
    from .items import CHANGED, NEW, STACK_SQL, add_money, mod_list, new_item, save_state, info_of
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return
    table_idx, inven, count, price = struct.unpack_from('<4I', frame.payload)
    if not can_use(session, p):
        return
    it = next((i for i in p.items if i.inven_idx == inven), None)
    why = '20050' if not it or it.table_idx != table_idx or not price else item_refusal(p, it, count)
    if why:
        session.log.note(f'auction on {inven} x{count} for {price}: refused ({why})')
        return error(session, why)
    fee = fee_for(price, context.auction_item_fee, p)
    db, c = context.db, p.char
    async with LOCK:
        if fee > c.mito or not await add_money(c, -fee):
            return error(session, '20092')
        changed = []
        if info_of(it).type == 5 and count < it.stack:       # split the registered count off the stack
            it.stack -= count
            await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
            changed.append((it, CHANGED))
            it = await new_item(p, info_of(it), count)
            it.state = LOCKED
            await save_state(p, it)
            changed.append((it, NEW))
        else:
            it.state = LOCKED
            await save_state(p, it)
            changed.append((it, CHANGED))
        serial = await next_serial(ITEMS)
        await db.execute("INSERT INTO SKID_AUCTION_TB(SERVERID, CID, CNAME, REGID, ITEMID, ITEMNUM, NRANDOM, NUPGRADE,"
                         " INVENIDX, PRICE, STATE, ASSIST_A, ASSIST_B, BOX, CTIME) VALUES"
                         " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)",
                         (db.server_id, c.cid, c.name, serial, it.item_id, max(it.stack, 1), it.random, it.upgrade,
                          it.inven_idx, price, it.assist_a, it.assist_b, it.box, it.ctime))
        await count_up(c, 'REGNUM')
        if price >= AUCTION_MIN:
            from .licenses import count
            await count(session, 'AuctionOn')      # licenses: GC_AuctionOn
    x = await listing(ITEMS, serial)
    session.log.note(f'auction on {it.item_id} x{max(it.stack, 1)} for {price}: serial {serial}, fee {fee}')
    send(session, mod_list(*changed))
    send(session, Frame(ITEMS.on_ack, struct.pack('<II', it.inven_idx, fee) + x.unit() + x.body(it)))


@on(SVC, C2S, 0x642)
async def auction_vs_on(session, frame):
    from .items import active, add_money
    from .vshop import CHANGED, save_state, vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return
    table_idx, inven, count, price = struct.unpack_from('<4I', frame.payload)
    if not context.auction_drift:
        return error(session, '20051')
    if not can_use(session, p):
        return
    v = next((x for x in p.vsitems if x.inven_idx == inven), None)
    row = context.data.vshop.get(v.table_idx) if v else None
    why = None
    if not v or v.table_idx != table_idx or not price:
        why = '20050'
    elif v.state != 0 or not active(v):
        why = '20063'
    elif not row or row.get('UseHancoin') != '1':     # drift items bought with Mito (text 12146)
        why = 'You cannot register the Skid Items purchased with Mitto'
    if why:
        session.log.note(f'auction drift item on {inven} for {price}: refused ({why})')
        return error(session, why)
    fee = fee_for(price, context.auction_drift_fee, p)
    db, c = context.db, p.char
    await ensure_tables()
    async with LOCK:
        if fee > c.mito or not await add_money(c, -fee):
            return error(session, '20092')
        v.state = LOCKED
        await save_state(p, v)
        serial = await next_serial(DRIFT)
        await db.execute("INSERT INTO SKID_AUCTIONVS_TB(SERVERID, CID, CNAME, REGID, ITEMID, INVENIDX, ITEM_DATA, PERIOD,"
                         " CTIME, UTIME, PRICE, STATE) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
                         (db.server_id, c.cid, c.name, serial, v.item_id, v.inven_idx, v.data, v.period, v.ctime,
                          v.utime, price))
        await count_up(c, 'REGNUM')
        if price >= AUCTION_MIN:
            from .licenses import count
            await count(session, 'AuctionOn')      # licenses: GC_AuctionOn
    x = await listing(DRIFT, serial)
    session.log.note(f'auction drift item on {v.item_id} for {price}: serial {serial}, fee {fee}')
    send(session, vs_mod_list((v, CHANGED)))
    send(session, Frame(DRIFT.on_ack, struct.pack('<II', v.inven_idx, fee) + x.unit() + x.body()))
    from .items import bonus_update
    send(session, bonus_update(p))


def car_refusal(p, car, key):
    """Why this car cannot be registered, or None (2008 Cmd_AuctionCarOn / XiCsCharInfo::AuctionCarOn)."""
    from .items import info_of
    if not context.auction_cars:
        return '20238'
    if not car or not key or (key.state & 0xffff) != 0 or info_of(key).kind != 'car':
        return '20050'
    if car.car_id == p.char.cur_car or car.on_auction:
        return '20051'
    if car.auction_cnt:
        return 'Cars bought from the Auction House cannot be resold in the Auction House.'
    if any(i.car_id == car.car_id for i in p.items):    # parts: the client refuses them too (0x71ab80)
        return ('If there are any equipped parts, CC items, and/or Drift items, you cannot register it for auction.'
                ' Remove all items before registering.')
    return None


@on(SVC, C2S, 0x6a6)
async def auction_car_on(session, frame):
    from .items import CHANGED, add_money, mod_list, save_state
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return
    table_idx, inven, car_id, price = struct.unpack_from('<4I', frame.payload)
    if not can_use(session, p):
        return
    car = next((x for x in p.char.cars if x.car_id == car_id), None)
    key = next((i for i in p.items if i.inven_idx == inven), None)
    why = '20050' if not price or (key and key.table_idx != table_idx) else car_refusal(p, car, key)
    if why:
        session.log.note(f'auction car on {car_id} (key {inven}) for {price}: refused ({why})')
        return error(session, why)
    fee = fee_for(price, context.auction_car_fee, p)
    db, c = context.db, p.char
    async with LOCK:
        if fee > c.mito or not await add_money(c, -fee):
            return error(session, '20092')
        key.state = LOCKED
        await save_state(p, key)
        car.on_auction = True
        serial = await next_serial(CARS)
        await db.execute("INSERT INTO SKID_AUCTIONCAR_TB(SERVERID, CID, CNAME, REGID, ITEMID, INVENIDX, CARID, CARTYPE,"
                         " BASECOLOR, NGRADE, NSLOT, FMITRON, FKMH, PRICE, STATE) VALUES"
                         " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
                         (db.server_id, c.cid, c.name, serial, key.item_id, key.inven_idx, car.car_id, car.car_type,
                          car.color, car.grade, car.slot, int(car.mitron), int(car.km), price))
        await count_up(c, 'REGNUM')
        if price >= AUCTION_MIN:
            from .licenses import count
            await count(session, 'AuctionOn')      # licenses: GC_AuctionOn
        # the drift items on the car are removed permanently (client text 11147, asked before 0x6a6)
        gone = [v for v in p.vsitems if v.car_id == car.car_id and v.state == 1]
        if gone:
            from .vshop import REMOVED as VS_REMOVED, destroy, vs_mod_list
            await destroy(p, *gone)
            p.apply_paints()
    x = await listing(CARS, serial)
    session.log.note(f'auction car on {car_id} (type {car.car_type}, V{car.grade}) for {price}: serial {serial}, fee {fee},'
                     f' drift items removed {[v.item_id for v in gone]}')
    if gone:
        from .cars import visual_update
        send(session, vs_mod_list(*((v, VS_REMOVED) for v in gone)))
        send(session, visual_update(session, car))
    send(session, mod_list((key, CHANGED)))
    send(session, Frame(CARS.on_ack, struct.pack('<II', key.inven_idx, fee) + x.unit() + x.body()))


# --- cancel / complete -----------------------------------------------------------------------------------
async def own_listing(session, kind, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return None, None
    serial, = struct.unpack_from('<I', frame.payload)
    x = await listing(kind, serial)
    return p, (x if x and x.cid == p.char.cid else None)


@on(SVC, C2S, 0x248)
async def auction_cancel(session, frame):
    from .items import CHANGED, REMOVED, DELETE_SQL as ITEM_DELETE, STACK_SQL, mod_list, save_state, stack_for, info_of
    p, x = await own_listing(session, ITEMS, frame)
    if not x or x.state not in (ON_SALE, EXPIRED):
        return error(session, '20052') if p else None
    db, c = context.db, p.char
    async with LOCK:
        await db.execute(DELETE_SQL.format(table=ITEMS.table), (db.server_id, x.serial))
        it = next((i for i in p.items if i.inven_idx == x.inven_idx), None)
        changed = []
        if it:
            it.state = 0
            info = info_of(it)
            pile = stack_for(p, info, it.stack) if info and info.type == 5 else None
            if pile and pile is not it and pile.state == 0:      # back onto a stack of the same item
                pile.stack += it.stack
                await db.execute(STACK_SQL, (pile.stack, db.server_id, c.cid, pile.inven_idx))
                await db.execute(ITEM_DELETE, (db.server_id, c.cid, it.inven_idx))
                p.items.remove(it)
                changed += [(pile, CHANGED), (it, REMOVED)]
            else:
                await save_state(p, it)
                changed.append((it, CHANGED))
    session.log.note(f'auction cancel {x.serial} ({x.item_id}, state {x.state})')
    send(session, Frame(ITEMS.cancel_ack, struct.pack('<I', x.serial)))
    if changed:
        send(session, mod_list(*changed))


@on(SVC, C2S, 0x644)
async def auction_vs_cancel(session, frame):
    from .vshop import CHANGED, save_state, vs_mod_list
    p, x = await own_listing(session, DRIFT, frame)
    if not x or x.state not in (ON_SALE, EXPIRED):
        return error(session, '20052') if p else None
    db = context.db
    async with LOCK:
        await db.execute(DELETE_SQL.format(table=DRIFT.table), (db.server_id, x.serial))
        v = next((o for o in p.vsitems if o.inven_idx == x.inven_idx), None)
        if v:
            v.state = 0
            await save_state(p, v)
    session.log.note(f'auction drift item cancel {x.serial} ({x.item_id}, state {x.state})')
    send(session, Frame(DRIFT.cancel_ack, struct.pack('<I', x.serial)))
    if v:
        send(session, vs_mod_list((v, CHANGED)))
        from .items import bonus_update
        send(session, bonus_update(p))


@on(SVC, C2S, 0x6a8)
async def auction_car_cancel(session, frame):
    from .items import CHANGED, mod_list, save_state
    p, x = await own_listing(session, CARS, frame)
    if not x or x.state not in (ON_SALE, EXPIRED):
        return error(session, '20052') if p else None
    db = context.db
    async with LOCK:
        await db.execute(DELETE_SQL.format(table=CARS.table), (db.server_id, x.serial))
        key = next((i for i in p.items if i.inven_idx == x.inven_idx), None)
        if key:
            key.state = 0
            await save_state(p, key)
        car = next((o for o in p.char.cars if o.car_id == x.car().car_id), None)
        if car:
            car.on_auction = False
    session.log.note(f'auction car cancel {x.serial} (car {x.car().car_id}, state {x.state})')
    send(session, Frame(CARS.cancel_ack, struct.pack('<I', x.serial)))
    if key:
        send(session, mod_list((key, CHANGED)))
    if car:
        from .cars import visual_update
        send(session, visual_update(session, car))


async def complete(session, kind, frame):
    """The seller collects a sold listing: the money, the listing and the sold thing are gone. -> (p, x) or None."""
    from .items import add_money
    p, x = await own_listing(session, kind, frame)
    if not x or x.state != SOLD:
        if p:
            error(session, '20054')
        return None
    db = context.db
    async with LOCK:
        await db.execute(DELETE_SQL.format(table=kind.table), (db.server_id, x.serial))
        await add_money(p.char, x.price)
    session.log.note(f'auction {kind.name} complete {x.serial} ({x.item_id}): +{x.price}')
    send(session, Frame(kind.complete_ack, struct.pack('<II', x.serial, x.price)))
    return p, x


@on(SVC, C2S, 0x24a)
async def auction_complete(session, frame):
    from .items import REMOVED, DELETE_SQL as ITEM_DELETE, mod_list
    done = await complete(session, ITEMS, frame)
    if not done:
        return
    p, x = done
    it = next((i for i in p.items if i.inven_idx == x.inven_idx and (i.state & 0xffff) == LOCKED), None)
    if it:
        db = context.db
        await db.execute(ITEM_DELETE, (db.server_id, p.char.cid, it.inven_idx))
        p.items.remove(it)
        send(session, mod_list((it, REMOVED)))


@on(SVC, C2S, 0x646)
async def auction_vs_complete(session, frame):
    from .vshop import REMOVED, destroy, vs_mod_list
    done = await complete(session, DRIFT, frame)
    if not done:
        return
    p, x = done
    v = next((o for o in p.vsitems if o.inven_idx == x.inven_idx and o.state == LOCKED), None)
    if v:
        await destroy(p, v)
        send(session, vs_mod_list((v, REMOVED)))


@on(SVC, C2S, 0x6aa)
async def auction_car_complete(session, frame):
    from .items import REMOVED, DELETE_SQL as ITEM_DELETE, mod_list
    from .vshop import REMOVED as VS_REMOVED, destroy, vs_mod_list
    done = await complete(session, CARS, frame)
    if not done:
        return
    p, x = done
    db, c = context.db, p.char
    car_id = x.car().car_id
    key = next((i for i in p.items if i.inven_idx == x.inven_idx), None)
    if key:
        await db.execute(ITEM_DELETE, (db.server_id, c.cid, key.inven_idx))
        p.items.remove(key)
        send(session, mod_list((key, REMOVED)))
    gone = [v for v in p.vsitems if v.car_id == car_id]           # its paint / neon / tint go with the car
    if gone:
        await destroy(p, *gone)
        send(session, vs_mod_list(*((v, VS_REMOVED) for v in gone)))
    await db.execute("DELETE FROM SKID_CAR_TB WHERE SERVERID=%s AND CID=%s AND CARID=%s;"
                     " UPDATE SKID_CHARACTER_TB SET NUMCAR=NUMCAR-1 WHERE SERVERID=%s AND CID=%s AND NUMCAR>0",
                     (db.server_id, c.cid, car_id, db.server_id, c.cid))
    c.cars = [o for o in c.cars if o.car_id != car_id]


# --- buying ----------------------------------------------------------------------------------------------
async def claim(session, p, kind, x, price_check=None):
    """Take a listing for the buyer: on sale, not their own, the money -> True (the listing is state 2)."""
    from .items import add_money
    db, c = context.db, p.char
    if not x or x.state != ON_SALE:
        error(session, '20053')
        return False
    if x.cid == c.cid:
        error(session, 'You cannot buy an Auction item that you registered.')
        return False
    if x.price > c.mito:
        error(session, '20092')
        return False
    r = await db.row(CLAIM_SQL.format(table=kind.table), (db.server_id, x.serial, period_seconds()))
    if not r or not r[0]:
        error(session, '20053')
        return False
    if not await add_money(c, -x.price):
        await db.execute(UNCLAIM_SQL.format(table=kind.table), (db.server_id, x.serial))
        error(session, '20092')
        return False
    await count_up(c, 'BUYNUM')
    await count_up_cid(x.cid, x.seller, 'SELLNUM')
    if x.price >= AUCTION_MIN:                  # licenses: GC_AuctionSuccess for the seller (online or not)
        from .licenses import count_cid
        await count_cid(x.cid, 'AuctionSuccess')
    return True


def tell_seller(kind, x):
    s = seller_session(x.cid)
    if s:
        s.to_client(Frame(kind.buyed, struct.pack('<I', x.serial)))


async def buy_target(session, kind, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4 or not can_use(session, p):
        return None, None
    serial, = struct.unpack_from('<I', frame.payload)
    return p, await listing(kind, serial)


@on(SVC, C2S, 0x250)
async def auction_buy(session, frame):
    from .items import CHANGED, NEW, STACK_SQL, mod_list, new_item, stack_for
    p, x = await buy_target(session, ITEMS, frame)
    if not p:
        return
    info = context.data.item_info(x.table_idx) if x else None
    if x and not info:
        return error(session, '20053')
    async with LOCK:
        if not await claim(session, p, ITEMS, x):
            return
        src = x.item()
        db = context.db
        pile = stack_for(p, info, max(src.stack, 1)) if info.type == 5 else None
        if pile:                                   # a usable item joins a stack with room (as BuyItem)
            pile.stack += max(src.stack, 1)
            await db.execute(STACK_SQL, (pile.stack, db.server_id, p.char.cid, pile.inven_idx))
    if pile:
        session.log.note(f'auction buy {x.serial} {x.item_id} x{src.stack} from {x.seller} for {x.price}: '
                         f'onto the stack in {pile.inven_idx} (now {pile.stack})')
        send(session, mod_list((pile, CHANGED)))
        send(session, Frame(ITEMS.buy_ack, struct.pack('<II', x.serial, x.price)))
        return tell_seller(ITEMS, x)
    async with LOCK:
        it = await new_item(p, info, max(src.stack, 1))
        it.random, it.upgrade, it.assist_a, it.assist_b, it.ctime = src.random, src.upgrade, src.assist_a, src.assist_b, src.ctime
        it.box = src.box if it.item_id.startswith('dock_') else 0      # out of its Parts Box (2008 AuctionBuy)
        if it.ctime:
            it.expire_tick = it.ctime
        await db.execute("UPDATE SKID_ITEM_TB SET NRANDOM=%s, NUPGRADE=%s, ASSIST_A=%s, ASSIST_B=%s, BOX=%s, CTIME=%s"
                         " WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                         (it.random, it.upgrade, it.assist_a, it.assist_b, it.box, it.ctime, db.server_id,
                          p.char.cid, it.inven_idx))
    session.log.note(f'auction buy {x.serial} {x.item_id} x{it.stack} from {x.seller} for {x.price}: inventory {it.inven_idx}')
    send(session, mod_list((it, NEW)))
    send(session, Frame(ITEMS.buy_ack, struct.pack('<II', x.serial, x.price)))
    tell_seller(ITEMS, x)


@on(SVC, C2S, 0x64c)
async def auction_vs_buy(session, frame):
    from .items import NEXT_GID_SQL, active
    from .records import VisualItem
    from .vshop import INSERT_SQL, NEW, vs_mod_list
    p, x = await buy_target(session, DRIFT, frame)
    if not p:
        return
    if not context.auction_drift:
        return error(session, '20053')
    table_idx, _, text, period, ctime, utime = x.drift() if x else (0, 0, '', 0, 0, 0)
    vis = context.data.visuals.get(table_idx)
    if x and (not vis or not active(VisualItem(0, x.item_id, 0, 0, 0, text, period, ctime, utime))):
        return error(session, '20053')                  # run out while on sale
    db, c = context.db, p.char
    async with LOCK:
        if not await claim(session, p, DRIFT, x):
            return
        gid = int((await db.row(NEXT_GID_SQL))[0])
        inven = max([o.inven_idx for o in p.vsitems] + [61]) + 1
        v = VisualItem(gid, x.item_id, inven, 0, 0, text, period, ctime, utime, table_idx)
        p.vsitems.append(v)
        await db.execute(INSERT_SQL, (db.server_id, c.cid, c.name, gid, x.item_id, inven, 0, 0, text, period, ctime,
                                      utime))
    session.log.note(f'auction buy drift item {x.serial} {x.item_id} from {x.seller} for {x.price}: inventory {inven}')
    send(session, vs_mod_list((v, NEW)))
    send(session, Frame(DRIFT.buy_ack, struct.pack('<II', x.serial, x.price)))
    from .items import bonus_update
    send(session, bonus_update(p))
    tell_seller(DRIFT, x)


@on(SVC, C2S, 0x6ae)
async def auction_car_buy(session, frame):
    from .items import NEW, mod_list, new_item
    p, x = await buy_target(session, CARS, frame)
    if not p:
        return
    if not context.auction_cars:
        return error(session, '20053')
    t, c, db = context.data, p.char, context.db
    if x and len(frame.payload) >= 16:
        _, car_type, grade, price = struct.unpack_from('<4I', frame.payload)
        car0 = x.car()
        if (car_type, grade, price) != (car0.car_type, car0.grade, x.price):
            session.log.note(f'auction car buy {x.serial}: the client asked for {car_type} V{grade} {price}')
            return error(session, '20053')
    floors = c.hancoin_garage + sum(1 for v in p.vsitems if v.item_id == 'i_d_garage') + 1
    if floors * CARS_PER_FLOOR - len(c.cars) <= 0:
        return error(session, 'Not Enough Garage Space')
    async with LOCK:
        if not await claim(session, p, CARS, x):
            return
        src = x.car()
        r = await db.row("SET NOCOUNT ON; DECLARE @carid numeric; EXEC PC_SKID_CREATECAR %s, %s, %s, %s, %s, %s, %s, %s,"
                         " %s, @carid OUTPUT; IF @carid > 0 UPDATE SKID_CAR_TB SET SLOT=%s WHERE SERVERID=%s AND CID=%s"
                         " AND CARID=@carid; SELECT ISNULL(@carid, -1)",
                         (db.server_id, c.cid, c.name, src.car_type, src.color, src.grade, 1, int(src.mitron),
                          int(src.km), src.slot, db.server_id, c.cid))
        car_id = int(r[0]) if r else -1
        if car_id <= 0:
            return error(session, '20053')
        up = t.upgrade.get((src.car_type, src.grade)) or {}
        car = Car(car_id, src.car_type, src.color, src.grade, 1, src.mitron, src.km, src.slot,
                  float(up.get('capacity', 0)), float(up.get('efficiency', 0)))
        c.cars.append(car)
        key_info = t.item_info(t.item_index.get(x.item_id, -1))
        key = await new_item(p, key_info, 1, car_id) if key_info else None
    session.log.note(f'auction buy car {x.serial} (type {src.car_type}, V{src.grade}) from {x.seller} for {x.price}: car {car_id}')
    if key:
        send(session, mod_list((key, NEW)))
    send(session, Frame(CARS.buy_ack, struct.pack('<II', x.serial, x.price) + car.encode()))
    tell_seller(CARS, x)


# --- other modules ---------------------------------------------------------------------------------------
async def mark_cars(p):
    """At login: the cars registered in the car auction (AuctionOn in XiStrCarInfo)."""
    db = context.db
    ids = {_i(r[0]) for r in await db.rows("SELECT CARID FROM SKID_AUCTIONCAR_TB WHERE SERVERID=%s AND CID=%s",
                                           (db.server_id, p.char.cid))}
    for car in p.char.cars:
        car.on_auction = car.car_id in ids


def open_frame():
    """0x708 AuctionCarOpenClose: u32 1 = cars can be registered (client [mgr + 0x824])."""
    return Frame(0x708, struct.pack('<i', 1 if context.auction_cars else 0))
