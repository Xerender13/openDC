"""Drift shop gifts (the shop's Gift button): a player buys a drift item for another character, who takes it from the
gift list later. As the 2008 server (PacketParser::Cmd_SendVisualItem 0x5f9aa0, Cmd_GetVisualItem 0x603270): the
gift is a SKID_VISUALITEM_HISTORY row (sender: GETTYPE 1, STATE 1, DSTNAME the receiver; receiver: GETTYPE 2, STATE 2
= waiting, 0 = taken, DSTNAME the sender; PERIODIDX holds the days here) and a SKID_MSG_TB message of kind 300 to the
receiver (ITEM "TableIdx,days,GID,time,colour"), which the client's 0x84 handler (0x5217f0, kind 0x12c, sscanf
"%d,%d,%I64d,%d,%ld") puts in its gift list (0x73f570) instead of the inbox: the gift list is rebuilt from these
messages at every login (0x86 GetMail, mail.py). The message is deleted when the gift is taken.

0x51a IsValidCharName (wchar[21] name; the dialog's Search button) -> 0x51b (i32 found, i64 cid; client 0x50f380:
    found only with both set). The sender's own name counts as not found (2008 refused it at sending: InvalidData).
0x516 SendVisualItem (2011, 490 bytes; client 0x7f6900): u32 TableIdx @0, item text (40) @4 (a colour, a plate),
    u32 period index @0x2c (as 0x4b3), wchar[21] receiver @0x30, wchar[200] message @0x5a (the dialog sends its
    placeholder "50 characters or less" when nothing was typed). No mileage. -> 0x517 SendVisualItemAck (u32
    TableIdx, i32 days, i32 Mito, i32 G Coin, i32 bonus Mito, wchar[21] receiver; client 0x516eb0 takes the Mito /
    G Coin off its own money and shows the "sent" message), and 0x51c to the receiver when in the game. Price as a
    purchase (vshop.charge). Errors (2008): 20136 "Wrong user name.", InvalidData (self, unknown item).
    Not applied: the 2008 refusal of car upgrades (VShop category 3000, 20137 "Cannot present Modification
    function."): the 2011 client offers the V upgrades as gifts; a permanent one (category 14) is applied to a car
    when taken (CAR_UPGRADE below); nor its limit checks of the receiver's inventory / garage extensions (the client checks
    them when one is used).
0x51c ReceiveVisualItem (2011, 466 bytes; client 0x5170e0 -> 0x73f570): u32 TableIdx, i32 days, i64 GID, u32 time,
    i32 colour (the item text as a number; the client shows it as "%ld" for Aero Mk.2, else "%09ld"), wchar[200]
    message, wchar[21] sender.
0x514 BuyHistoryList (u32 offset = page x 14, u32 count 14, u32 type: 1 bought, 2 sent, 3 received; the drift shop's
    trade history window, client 0x67c930) -> 0x515 BuyHistoryListAck (u32 type, u32 count, count x 0x216-byte
    XiStrVisualItemBuyUnit: i64 GID, u32 TableIdx, u32 buy time, u32 use time, u32 GetType @0x14, u32 gold type (1 =
    Mito), i32 days, u32 G Coin, u32 Mito, u32 mileage, i32 state @0x2c, wchar[21] other player @0x30, wchar[20] item
    text @0x5a, wchar[200] message @0x82, u32 0; client 0x51bc70 -> 0x67e600 replaces the list, 0x67cdf0 shows a tab:
    bought GetType 0 / 10, sent 1 / 11, received 2 / 12 / 4). Rows: SKID_VISUALITEM_HISTORY (as the 2008 server, also
    for purchases: vshop 0x4b3 and cars 0x5b record GetType 0 with record()); a waiting gift (state 2) can be taken
    from the received tab (0x518; the ack sets the row's state to 0 in the window, 0x67cda0).
0x518 GetVisualItem (i64 GID, u32 car (0 for none), u8 (unknown; logged)) -> 0x4b2 + the purchase's follow-ups
    (vshop.grant / finish: on the car when it fits), 0x519 GetVisualItemAck (u32 type, i64 GID, u32 InvenIdx, u32
    TableIdx, i32 days, wchar[21] sender; client 0x516f70: type 0 names the shop item by TableIdx, 1 an inventory
    item by InvenIdx: 2008 sent 1 for parts boxes; here always 0).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context, now
from .items import NEXT_GID_SQL
from .login import SVC, error, send
from . import mail
from .mail import NAME, RECEIVER
from .records import wstr
from .vshop import CHANGED, NEW, ON_CAR, REMOVED, charge, finish, grant, item_text, vs_mod_list

GIFT_KIND = 300                 # SKID_MSG_TB.MSGKIND of a gift (the client's gift list)
MESSAGE = 200                   # wchar[200] in 0x516 / 0x51c
SENT, WAITING, TAKEN = 1, 2, 0  # SKID_VISUALITEM_HISTORY.STATE
HISTORY_SQL = ("INSERT INTO SKID_VISUALITEM_HISTORY(SERVERID, CID, CNAME, GID, ITEMID, BUYTIME, GETTYPE, GOLDTYPE,"
               " PERIODIDX, HANCOIN, MITO, MILEAGE, STATE, ITEM_DATA, CHAR_MSG, DSTNAME)"
               " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s)")
RECORD_SQL = ("INSERT INTO SKID_VISUALITEM_HISTORY(SERVERID, CID, CNAME, GID, ITEMID, BUYTIME, GETTYPE, GOLDTYPE,"
              " PERIODIDX, HANCOIN, MITO, MILEAGE, STATE, ITEM_DATA, CHAR_MSG, DSTNAME, USETIME)"
              " VALUES (%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s,%s,1,%s,'','',%s)")
LIST_SQL = ("SELECT GID, ITEMID, BUYTIME, USETIME, GETTYPE, GOLDTYPE, PERIODIDX, HANCOIN, MITO, MILEAGE, STATE, DSTNAME,"
            " ITEM_DATA, CHAR_MSG FROM SKID_VISUALITEM_HISTORY WHERE SERVERID=%s AND CID=%s")
TABS = {1: (0, 10), 2: (1, 11), 3: (2, 12, 4)}      # 0x514 type -> the GetTypes its tab shows (client 0x67cdf0)
PAGE = 14
UNIT = 0x216
MAIL_SQL = ("INSERT INTO SKID_MSG_TB(SERVERID, RECEIVER_ID, SENDER_ID, SNAME, MSGKIND, MSGSTATE, SUBJECT, CONTENT, GOLD,"
            " ITEM, SENDDATE) VALUES (%s, %s, %s, %s, %s, 'N', '', %s, 0, %s, GetDate())")
WAITING_SQL = ("SELECT ITEMID, PERIODIDX, ITEM_DATA, DSTNAME FROM SKID_VISUALITEM_HISTORY"
               " WHERE SERVERID=%s AND CID=%s AND GID=%s AND GETTYPE=2 AND STATE=2")
TAKE_SQL = """SET NOCOUNT ON;
UPDATE SKID_VISUALITEM_HISTORY SET STATE=0, USETIME=%s WHERE SERVERID=%s AND CID=%s AND GID=%s AND GETTYPE=2 AND STATE=2;
SELECT @@ROWCOUNT"""
MAIL_DELETE_SQL = "DELETE FROM SKID_MSG_TB WHERE SERVERID=%s AND RECEIVER_ID=%s AND MSGKIND=%s AND ITEM LIKE %s"

# VShopItem category 14 (CARREMODELING, the permanent V upgrades i_d_u_01..08): the client buys them as a car upgrade
# (0x5b for the selected car), never as a drift item, and cannot use one held in the drift inventory. A gifted one is
# applied when it is taken, to the car chosen then (cars.grade_check: a car one grade below the item); one taken
# before 2026-10-15 late (a dead drift item) goes back to the gift list at login (return_upgrades).
CAR_UPGRADE = 14

_by_name = None


def table_idx_of(item_id):
    """VShopItem.xlt ItemName -> UniqueId (unique in the 2011 table)."""
    global _by_name
    if _by_name is None:
        _by_name = {r.get('ItemName'): idx for idx, r in context.data.vshop.items()}
    return _by_name.get(item_id)


def colour(text):
    """The item text as the number the receiver's client reads: a colour or plate number, or for a lottery bundle
    ("<scratch card UniqueId> <count>", driftuse.parse_value) the card; 0 made the receiver's client freeze on the
    0x51c of an ST Lottery gift ("20408 11"; user, 2026-10-16)."""
    t = (text or '').strip().split()
    return int(t[0]) if t and t[0].isdigit() and int(t[0]) < 2 ** 31 else 0


async def receiver_of(p, name):
    db = context.db
    r = await db.row(RECEIVER, (db.server_id, name)) if name else None
    return (int(r[0]), r[1].strip()) if r and int(r[0]) != p.char.cid else None


@on(SVC, C2S, 0x51a)
async def is_valid_char_name(session, frame):
    p = session.state.get('player')
    if not p:
        return
    name = read_wstr(frame.payload, 0, NAME)
    r = await receiver_of(p, name)
    session.log.note(f'gift receiver {name!r}: {"found" if r else "not found"}')
    send(session, Frame(0x51b, struct.pack('<iq', 1 if r else 0, r[0] if r else 0)))


@on(SVC, C2S, 0x516)
async def send_visual_item(session, frame):
    p = session.state.get('player')
    pl = frame.payload
    if not p or len(pl) < 0x5a:
        return error(session, '20017')
    table_idx, = struct.unpack_from('<I', pl)
    period_idx, = struct.unpack_from('<I', pl, 0x2c)
    name = read_wstr(pl, 0x30, NAME)
    message = pl[0x5a:0x5a + 2 * MESSAGE].decode('utf-16-le', 'replace').split('\0')[0].strip()
    t, c, db = context.data, p.char, context.db
    row, vis = t.vshop.get(table_idx), t.visuals.get(table_idx)
    if not row or not vis or table_idx in context.vshop_hidden:     # off sale: emulator.ini [vshop] hidden
        return error(session, '20050')                  # InvalidData
    text = item_text(pl[4:44], vis.category)
    from .driftuse import GIVES_ITEMS, parse_value
    if vis.category in GIVES_ITEMS and not parse_value(vis.value, text):
        return error(session, '20050')
    r = await receiver_of(p, name)
    if not r:
        session.log.note(f'gift {vis.item_id} to {name!r}: no such character')
        return error(session, '20136')                  # Wrong user name.
    rcid, rname = r
    charged = await charge(session, p, row, period_idx)
    if not charged:
        return
    paid, days = charged
    gid, when = int((await db.row(NEXT_GID_SQL))[0]), now()
    gold = 0 if paid['coin'] else 1
    await db.execute(HISTORY_SQL, (db.server_id, c.cid, c.name, gid, vis.item_id, when, 1, gold, days, paid['coin'],
                                   paid['mito'], SENT, text, message[:100], rname))
    await db.execute(HISTORY_SQL, (db.server_id, rcid, rname, gid, vis.item_id, when, 2, gold, days, paid['coin'],
                                   paid['mito'], WAITING, text, message[:100], c.name))
    await db.execute(MAIL_SQL, (db.server_id, rcid, c.cid, c.name, GIFT_KIND, message[:200] or ' ',
                                f'{table_idx},{days},{gid},{when},{colour(text)}'))
    session.log.note(f'gift {vis.item_id} ({row.get("MarketName")}) text {text!r} for {days or "good"} days to '
                     f'{rname} (gid {gid}): {paid}, message {message!r}')
    send(session, Frame(0x517, struct.pack('<Iiiii', table_idx, days, paid['mito'], paid['coin'], 0) + wstr(rname, NAME)))
    from .social import online
    target = online(rcid)
    if target:
        send(target, Frame(0x51c, struct.pack('<IiqIi', table_idx, days, gid, when, colour(text))
                           + wstr(message, 2 * MESSAGE) + wstr(c.name, NAME)))


@on(SVC, C2S, 0x518)
async def get_visual_item(session, frame):
    p = session.state.get('player')
    pl = frame.payload
    if not p or len(pl) < 12:
        return error(session, '20017')
    gid, car_id = struct.unpack_from('<qI', pl)
    flag = pl[12] if len(pl) > 12 else 0
    c, db = p.char, context.db
    h = await db.row(WAITING_SQL, (db.server_id, c.cid, gid))
    table_idx = table_idx_of((h[0] or '').strip()) if h else None
    vis = context.data.visuals.get(table_idx) if table_idx else None
    row = context.data.vshop.get(table_idx) if table_idx else None
    if not vis or not row:
        session.log.note(f'gift {gid}: none waiting' + (f' ({h[0]!r} unknown)' if h else ''))
        return error(session, '20050')                  # InvalidData
    days, text, sender = int(h[1] or 0), (h[2] or '').strip(), (h[3] or '').strip()
    up = None
    if vis.category == CAR_UPGRADE:                 # applied to the car chosen now; else the gift stays in the list
        from .cars import grade_check
        from .player import upgrade_grade
        up = grade_check(session, p, next((x for x in c.cars if x.car_id == car_id), None), upgrade_grade(table_idx))
        if not up:
            return
    taken = await db.row(TAKE_SQL, (now(), db.server_id, c.cid, gid))
    if not taken or not taken[0]:
        return error(session, '20050')
    await db.execute(MAIL_DELETE_SQL, (db.server_id, c.cid, GIFT_KIND, f'%,{gid},%'))
    car = next((x for x in c.cars if x.car_id == car_id and not x.on_auction), None)
    if up:
        from .cars import raise_grade
        await raise_grade(session, p, car, up, why=f'with the gift {vis.item_id} from {sender} ({gid})')
        send(session, Frame(0x519, struct.pack('<IqIIi', 0, gid, 0, table_idx, days) + wstr(sender, NAME)))
        return
    v, held, changed, gone = await grant(p, vis, table_idx, car, text, days)
    session.log.note(f'gift {gid} taken: {vis.item_id} from {sender} for {days or "good"} days, car {car_id} (flag '
                     f'{flag}), inventory {v.inven_idx}, on car: {v.state == ON_CAR}'
                     + (f', added to the held one ({v.period} days)' if held else ''))
    send(session, vs_mod_list(*((o, CHANGED if o is held or o is not v else NEW) for o in changed),
                              *((o, REMOVED) for o in gone)))
    await finish(session, p, row, vis, v, car, text)
    send(session, Frame(0x519, struct.pack('<IqIIi', 0, gid, v.inven_idx, table_idx, days) + wstr(sender, NAME)))


async def return_upgrades(session, p):
    """At login: permanent V upgrades held as drift items (taken as gifts before they were applied on taking) go back
    to the gift list, from their sender (the taken gift's history row)."""
    from .vshop import destroy
    t, c, db = context.data, p.char, context.db
    for v in [v for v in p.vsitems if t.visuals.get(v.table_idx) and t.visuals[v.table_idx].category == CAR_UPGRADE]:
        h = await db.row("SELECT TOP 1 DSTNAME, CHAR_MSG FROM SKID_VISUALITEM_HISTORY WHERE SERVERID=%s AND CID=%s"
                         " AND ITEMID=%s AND GETTYPE=2 AND STATE=0 ORDER BY USETIME DESC", (db.server_id, c.cid, v.item_id))
        sender, message = ((h[0] or '').strip(), (h[1] or '').strip()) if h else (c.name, '')
        r = await db.row(mail.RECEIVER, (db.server_id, sender)) if sender else None
        when = now()
        await db.execute(HISTORY_SQL, (db.server_id, c.cid, c.name, v.gid, v.item_id, when, 2, 0, v.period, 0, 0,
                                       WAITING, v.data or '', message[:100], sender))
        await db.execute(MAIL_SQL, (db.server_id, c.cid, int(r[0]) if r else 0, sender, GIFT_KIND, message[:200] or ' ',
                                    f'{v.table_idx},{v.period},{v.gid},{when},{colour(v.data)}'))
        await destroy(p, v)
        session.log.note(f'{v.item_id} ({v.inven_idx}) back to the gift list (gid {v.gid}, from {sender})')


async def record(p, gid, item_id, paid, days, text=''):
    """A drift shop purchase in the trade history (Bought tab): GetType 0, state 1."""
    db, c, when = context.db, p.char, now()
    await db.execute(RECORD_SQL, (db.server_id, c.cid, c.name, gid, item_id, when, 0 if paid['coin'] else 1, days,
                                  paid['coin'], paid['mito'], paid['mileage'], (text or '')[:20], when))


def _i(x):
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def unit(r):
    gid, item_id, bought, used, get_type, gold, days, coin, mito, mileage, state, other, text, message = r
    return (struct.pack('<qIIIIIiIIIi', _i(gid), table_idx_of((item_id or '').strip()) or 0, _i(bought), _i(used),
                        _i(get_type), _i(gold), _i(days), _i(coin), _i(mito), _i(mileage), _i(state))
            + wstr((other or '').strip(), NAME) + wstr((text or '').strip(), 40) + wstr((message or '').strip(), 2 * MESSAGE)
            + bytes(4))


@on(SVC, C2S, 0x514)
async def buy_history_list(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    offset, count, kind = struct.unpack_from('<III', frame.payload)
    db = context.db
    types = TABS.get(kind)
    rows = await db.rows(LIST_SQL + (f" AND GETTYPE IN ({','.join(map(str, types))})" if types else '')
                         + " ORDER BY BUYTIME DESC, GID DESC", (db.server_id, p.char.cid))
    page = rows[offset:offset + min(count or PAGE, PAGE * 4)]
    session.log.note(f'trade history type {kind}: {len(page)} of {len(rows)} from {offset}')
    send(session, Frame(0x515, struct.pack('<II', kind, len(page)) + b''.join(unit(r) for r in page)))
