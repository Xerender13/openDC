"""The drift shop (F4): visual items (paint, neon, window colour, decals, aero, spoilers, ...).

Shop rows: VShopItem.xlt by column name (UniqueId = the client's TableIdx, ItemName, categories, prices
per period, bonus stats); item rows: VisualItem.xlt (data.Tables.visuals: category index, the car types
it fits). Owned items: SKID_VSITEM_TB (ITEMID, INVENIDX, CARID, STATE 1 = on the car, ITEM_DATA, PERIOD
in days with 0 = for good, CTIME, UTIME). Records: records.VisualItem (XiStrMyVSItem, 2011: 116 bytes).

**Colours (2011):** colours (category 1), neon (2), window tint (3), decals (11) and glossy colours / RGB paints (32) can
take any RGB colour (the user): the client sends it in the item's text (XiStrPlateName, 40 bytes in 2011)
as text. With Etc.ColorSetReform 3 (the colour window) it is the colour as a decimal 0xRRGGBB
("16715002" = FF 0B FA); before that flag was set the client sent 10 spaces + RRRGGGBBB
("          023110162"). A number plate sends its text ("26"). The 2008 server refused the colour codes
("Unreliable data."); here the text is stored and sent back exactly as the client sent it (the first
native version stripped / re-added 10 spaces, which turned "16715002" into "          16715002" in
0x4b2, and the car kept its colour: user, 2026-10-12).

0x4b3 BuyVisualItem (2011: u32 TableIdx, u32 car, text (40), u32 period index, u8 use mileage, i64 the
    client's G Coin, 5 more bytes) -> 0x4b2 VSItemModList, 0x4b4 BuyVisualItemAck (type, TableIdx, car,
    InvenIdx, period, Mito, G Coin, bonus Mito, mileage: what was paid), 0x5dd, 0x425, 0x2f8 + 0x2f9.
    PacketParser::Cmd_BuyVisualItem 0x6037f0 (run by the billing thread): the item must exist; period
    index 0 none, 1 7 days, 2 30, 3 90 (365 if no 90-day price), 4 for good; an item with a price for good
    (G Coin "$Price 0D" or "Mito Price") is always bought for good; mileage if asked ("Mile Price..":
    "Not Enough Mileage"), else G Coin if "UseHancoin" ("$Price..", 20134 without a price, billing
    20094), else Mito ("Mito Price" for index 0, "Mito Price7D".. "Mito Price0D"; ItemBuyFail without the
    money); XiCsCharInfo::BuyVisualItem makes the item ("BUYVSITEM"); if it fits the car
    (VisualItemCategory::IsEnableEquip) the item of the same category on that car comes off and the new
    one goes on (as recorded: bought items arrive on the car); only the EQUIPPABLE categories, the drift
    items (Misc tab) stay in the drift inventory with no car. Drinks and boosters bought while one is held
    add their days to it (EXTENDS). G Coin is taken from SKID_UNALISCOIN_TB
    here (the 2008 server called an external billing service). Category 0x13 items (parts boxes, given as
    inventory items) are not native yet.
0x4b5 EquipVisualItem (InvenIdx, slot: -1 in 2011, car) -> 0x4b6 (the same), 0x4b2, 0x425, stats.
    XiCsCharInfo::EquipVisualItem 0x5cbb40: the item fits the car and belongs to it (visual items stay
    with the car they were bought for: an unequipped paint keeps CARID, STATE 0); the item of the same
    category comes off. The 2008 server refused every 2011 equip ("Failed to equip the item."): it used
    the slot index, which the 2011 client sends as -1.
0x4b7 UnEquipVisualItem (InvenIdx, car) -> 0x4b8 (the same), 0x4b2, 0x425, stats. Not for paint, neon, tint
    (ItemUnEquipFail): they stay on their car until another one replaces and destroys them (FIXED_SLOTS).
Gifts (the shop's Gift button, 0x516 / 0x518): gifts.py, with charge / grant / finish from here.
Stats: the VShopItem "Bonus Speed / Accel / Boost / Crash" of the items on the current car are added to
the equip group (player.Player.stats).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context, now
from .cars import visual_update
from .items import NEXT_GID_SQL, active, add_money, bonus_update
from .login import SVC, error, send, stat_frames
from .records import VisualItem

NEW, CHANGED = 1, 3
ON_CAR = 1
# Categories that go on a car: 2008 VisualItemCategory::IsEnableEquip 0x5eb170 (1-13; 14 and up are drift items:
# drinks, extensions, boxes, ... used from the drift inventory) + the 2011 looks: 32 gloss paint, 47 roof,
# 48 glossy tire, 52 air duct. A drift item on the car (state 1) is not in the client's usable list.
EQUIPPABLE = frozenset(range(1, 14)) | {32, 38, 47, 48, 52}     # 38: timed car upgrades (player.TEMP_UPGRADE)
# Bought again while one is held: the held one gets the days (2008 XiCsCharInfo::GetVisualItem 0x5d36b0 ->
# LikeEnableVisualItem, AddPeriod): drinks 15 / 17 / 28, Repair Girl 18, Sticker Glue 20, Turbo Man 21, half
# Mitron charge 24, modification kit 29, and i_d_turbo02; the Premium Packages 49 too (as the drinks they stand for).
EXTENDS = (15, 17, 18, 20, 21, 24, 28, 29, 49)
# Paint (1) and glossy paint (32) are one slot and cannot come off: a new one destroys the one on the car (client
# texts 11325 "When you purchase a new paint, the existing paint item will disappear.", 10957 the same for
# Glossy Paint, 11607 a paint bought over a glossy paint; the drift shop shows them before such a purchase).
# Neon (2) and window tint (3) follow the same rule (the user), each its own slot.
FIXED_SLOTS = {1: 'paint', 32: 'paint', 2: 'neon', 3: 'tint'}
REMOVED = 2                    # 0x4b2 state: the item is gone (as driftuse.USED)
PERIODS = {1: '7D', 2: '30D', 3: '90D', 4: '0D'}
INSERT_SQL = ("INSERT INTO SKID_VSITEM_TB(SERVERID, CID, CNAME, GID, ITEMID, INVENIDX, CARID, STATE, ITEM_DATA, PERIOD,"
              " CTIME, UTIME) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
PERIOD_SQL = "UPDATE SKID_VSITEM_TB SET PERIOD=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
DELETE_SQL = "DELETE FROM SKID_VSITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
STATE_SQL = "UPDATE SKID_VSITEM_TB SET CARID=%s, STATE=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
COIN_SQL = """SET NOCOUNT ON;
UPDATE SKID_UNALISCOIN_TB SET COIN=COIN-%s, LASTACTION='BVS', LASTCNAME=%s, LASTDATE=GETDATE() WHERE MEMBERID=%s AND COIN>=%s;
SELECT @@ROWCOUNT"""
MILEAGE_SQL = """SET NOCOUNT ON;
UPDATE SKID_CHARACTER_TB SET MILEAGE=MILEAGE-%s WHERE SERVERID=%s AND CID=%s AND MILEAGE>=%s;
SELECT @@ROWCOUNT"""


def _n(row, name):
    try:
        return int(float(row.get(name) or 0))
    except ValueError:
        return 0


def price_for(row, prefix, idx):
    """A price column for the period index (2008: index 3 falls back to 365 days without a 90-day price)."""
    if idx == 3 and not _n(row, f'{prefix}90D'):
        return _n(row, f'{prefix}365D'), _n(row, 'Period 365D')
    if idx not in PERIODS:
        return 0, 0
    return _n(row, prefix + PERIODS[idx]), (_n(row, f'Period {PERIODS[idx]}') if idx != 4 else 0)


def row_changes(section):
    """emulator.ini [vshop] -> (hidden UniqueIds, {UniqueId: {VShopItem column: value}} from the sell.<UniqueId> lines).
    The server applies the changes to its rows at start (prices, period); tools/shop_rows.py writes both into the
    clients' VShopItem (the shop lists a row only with SellStage <= Etc.VShopOpenStage, 1)."""
    hidden = frozenset(int(x) for x in section.get('hidden', '').replace(',', ' ').split() if x.isdigit())
    changes = {}
    for key, value in section.items():
        if key.startswith('sell.') and key[5:].strip().isdigit():
            changes[int(key[5:])] = {k.strip(): v.strip() for k, v in (c.split('=', 1) for c in value.split(',') if '=' in c)}
    return hidden, changes


def item_text(raw, category):
    """The item's text from the client, kept as sent (ITEM_DATA varchar(20)): a colour, or a plate text."""
    return read_wstr(raw, 0, len(raw))[:20]


def vs_mod_list(*changes):
    return Frame(0x4b2, struct.pack('<I', len(changes)) + b''.join(v.encode() + struct.pack('<i', s) for v, s in changes))


def fits(v, car):
    from .driftuse import EQUIP_PASSIVE
    vis = context.data.visuals.get(v.table_idx)
    if vis is None or (vis.category not in EQUIPPABLE and v.item_id not in EQUIP_PASSIVE) \
            or (vis.cars and car.car_type not in vis.cars):
        return False
    from .player import TEMP_UPGRADE, upgrade_grade
    # a timed V upgrade goes only on a car one grade below it: V4 car upgrade on a V3 car (user, 2026-10-14)
    return vis.category != TEMP_UPGRADE or upgrade_grade(v.table_idx) == car.grade + 1


def category_of(v):
    vis = context.data.visuals.get(v.table_idx)
    return vis.category if vis else -1


def slot_of(v):
    c = category_of(v)
    return FIXED_SLOTS.get(c, c)


async def destroy(p, *items):
    db = context.db
    for v in items:
        await db.execute(DELETE_SQL, (db.server_id, p.char.cid, v.inven_idx))
        p.vsitems.remove(v)


async def save_state(p, *items):
    db = context.db
    for v in items:
        await db.execute(STATE_SQL, (v.car_id, v.state, db.server_id, p.char.cid, v.inven_idx))


def put_on(p, v, car_id):
    """Equip v on the car; the item of its category there comes off (paint, neon, tint: is destroyed, see
    FIXED_SLOTS). -> (changed items, destroyed items)."""
    off = [o for o in p.vsitems if o is not v and o.car_id == car_id and o.state == ON_CAR and slot_of(o) == slot_of(v)]
    gone = [o for o in off if category_of(o) in FIXED_SLOTS]
    for o in off:
        o.state = 0
    v.car_id, v.state = car_id, ON_CAR
    return [o for o in off if o not in gone] + [v], gone


def after_change(session, p, car):
    p.apply_paints()
    for f in stat_frames(p):
        send(session, f)
    if car:
        # 0x63 ChangeCarGrade (u32 car, u32 grade; client 0x510df0): the grade the client shows for the car (a timed
        # V upgrade on or off: Car.shown_grade); 0x425 alone did not change it (user, 2026-10-14)
        send(session, Frame(0x63, struct.pack('<II', car.car_id, car.shown_grade())))
        send(session, visual_update(session, car))


@on(SVC, C2S, 0x4b3)
async def buy_visual_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 0x31:
        return
    table_idx, car_id = struct.unpack_from('<II', frame.payload)
    period_idx, use_mileage = struct.unpack_from('<IB', frame.payload, 0x30)
    t, c, db = context.data, p.char, context.db
    row, vis = t.vshop.get(table_idx), t.visuals.get(table_idx)
    if not row or not vis or table_idx in context.vshop_hidden:     # off sale: emulator.ini [vshop] hidden
        return error(session, 'No such Item!')
    from .driftuse import GIVES_ITEMS, parse_value
    if vis.category in GIVES_ITEMS and not parse_value(vis.value, item_text(frame.payload[8:48], vis.category)):
        return error(session, 'No such Item!')         # a bundle with nothing to give (or no card picked)
    car = next((x for x in c.cars if x.car_id == car_id), None)
    if car_id and not car:
        return error(session, '20050')                  # InvalidData
    charged = await charge(session, p, row, period_idx, use_mileage)
    if not charged:
        return
    paid, days = charged
    text = item_text(frame.payload[8:48], vis.category)
    v, held, changed, gone = await grant(p, vis, table_idx, car, text, days)
    inven = v.inven_idx
    session.log.note(f'buy visual item {vis.item_id} ({row.get("MarketName")}) text {text!r} for {days or "good"} days: '
                     f'{paid}, inventory {inven}, on car: {v.state == ON_CAR}' + (f', added to the held one ({v.period} days)' if held else ''))
    send(session, vs_mod_list(*((o, CHANGED if o is held or o is not v else NEW) for o in changed),
                              *((o, REMOVED) for o in gone)))
    send(session, Frame(0x4b4, struct.pack('<IIIIiiiii', 0, table_idx, car_id, inven, days, paid['mito'], paid['coin'],
                                           0, paid['mileage'])))
    from .gifts import record
    await record(p, v.gid, vis.item_id, paid, days, text)
    await finish(session, p, row, vis, v, car, text)


async def charge(session, p, row, period_idx, use_mileage=False):
    """Take the price of a drift shop row for the period index (a purchase or a gift: gifts.py) -> (paid
    {mito, coin, mileage}, days; 0 = for good), or None after an error was sent."""
    c, db = p.char, context.db
    if (_n(row, 'UseHancoin') and _n(row, '$Price 0D')) or (_n(row, 'Use Mito') and _n(row, 'Mito Price')):
        period_idx = 4
    paid = dict(mito=0, coin=0, mileage=0)
    if use_mileage:
        price, days = price_for(row, 'Mile Price', period_idx)
        r = await db.row(MILEAGE_SQL, (price, db.server_id, c.cid, price)) if price else None
        if not price or not r or not r[0]:
            return error(session, 'Not Enough Mileage')
        c.mileage -= price
        paid['mileage'] = price
    elif _n(row, 'UseHancoin'):
        price, days = price_for(row, '$Price ', period_idx)
        if not price:
            return error(session, '20134')
        r = await db.row(COIN_SQL, (price, c.name, c.member, price))
        if not r or not r[0]:
            return error(session, '20094')
        paid['coin'] = price
    else:
        price, days = (_n(row, 'Mito Price'), 0) if period_idx == 0 else price_for(row, 'Mito Price', period_idx)
        if period_idx == 4:
            price = price or _n(row, 'Mito Price')
        if not price or price > c.mito or not await add_money(c, -price):
            return error(session, '20029')              # ItemBuyFail
        paid['mito'] = price
    return paid, days


async def grant(p, vis, table_idx, car, text, days):
    """Give p the drift item (bought, or a gift claimed): added to a held drink / booster (EXTENDS), else a new item,
    on the car when it fits. -> (item, the held item it was added to or None, changed items, destroyed items)."""
    c, db = p.char, context.db
    car_id = car.car_id if car else 0
    held = next((o for o in p.vsitems if o.table_idx == table_idx and o.period and active(o)), None) \
        if days and (vis.category in EXTENDS or vis.item_id == 'i_d_turbo02') else None
    gone = []
    if held:
        v, changed = held, [held]
        v.period += days
        await db.execute(PERIOD_SQL, (v.period, db.server_id, c.cid, v.inven_idx))
    else:
        gid = int((await db.row(NEXT_GID_SQL))[0])
        inven = max([v.inven_idx for v in p.vsitems] + [61]) + 1
        v = VisualItem(gid, vis.item_id, inven, car_id if vis.category in EQUIPPABLE else 0, 0, text, days, now(), 0,
                       table_idx)
        p.vsitems.append(v)
        from .aero import is_mk2
        # an Aero kit Mk.2 stays in the drift inventory (bound to the car): its points are set from there first (the
        # client offers the window only from the inventory; user, 2026-10-14)
        changed, gone = put_on(p, v, car_id) if car and fits(v, car) and not is_mk2(v) else ([v], [])
        await destroy(p, *gone)
        await db.execute(INSERT_SQL, (db.server_id, c.cid, c.name, gid, vis.item_id, inven, v.car_id, v.state, text,
                                      days, v.ctime, 0))
        await save_state(p, *[o for o in changed if o is not v])
    return v, held, changed, gone


async def finish(session, p, row, vis, v, car, text):
    """After a drift item was given (grant): bonus flags, passive assists, the car's look and stats, and the items
    that act at once (Mito prizes, inventory item bundles, parts boxes)."""
    send(session, bonus_update(p))
    from .driftuse import passive_follow
    moved = passive_follow(p)
    if moved:
        send(session, vs_mod_list(*((o, CHANGED) for o in moved)))
    after_change(session, p, car if v.state == ON_CAR else None)
    from .driftuse import AT_PURCHASE, USED, Gains, instant, use_up
    if row.get('Instant') == '1' or vis.category in AT_PURCHASE:    # Mito prizes, inventory item bundles
        gains = Gains()
        if await instant(session, p, vis, gains, text):
            await use_up(p, v)
            send(session, vs_mod_list((v, USED)))
            gains.send(session, p)


@on(SVC, C2S, 0x4b5)
async def equip_visual_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    inven, _, car_id = struct.unpack_from('<IiI', frame.payload)
    v = next((x for x in p.vsitems if x.inven_idx == inven), None)
    car = next((x for x in p.char.cars if x.car_id == car_id), None)
    if not v or not car or car.on_auction or v.state == 4 or (v.car_id and v.car_id != car_id) or not fits(v, car):
        return error(session, '20027')                  # ItemEquipFail
    changed, gone = put_on(p, v, car_id)
    await destroy(p, *gone)
    await save_state(p, *changed)
    send(session, Frame(0x4b6, frame.payload[:12]))
    p.apply_paints()                            # (on_current_car: equippable PassiveAssist items)
    send(session, vs_mod_list(*((o, CHANGED) for o in changed), *((o, REMOVED) for o in gone)))
    after_change(session, p, car)


@on(SVC, C2S, 0x4bb)
async def drop_visual_item(session, frame):
    """0x4bb DropVisualItem (u32 TableIdx, u32 InvenIdx): a drift item thrown away -> 0x4bc DropVisualItemAck (the
    same; client 0x516bb0 takes it out of the drift inventory), 0x4b2, 0x5dd, and the car's look and stats when it
    was on one. 2008 PacketParser::Cmd_DropVisualItem 0x602bc0: an item on a car comes off first
    (XiCsCharInfo::UnEquipVisualItem), then XiCsCharInfo::DropVSItem. Here an item on a car goes whatever its slot
    (paint, neon, tint and the other items that cannot be taken off; user, 2026-10-14: they could not be deleted:
    0x4bb had no handler). Items on auction (state 4) are refused (ItemDropFail 20026)."""
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    table_idx, inven = struct.unpack_from('<II', frame.payload)
    v = next((x for x in p.vsitems if x.inven_idx == inven), None)
    if not v or v.state == 4:
        session.log.note(f'drop visual item {inven}: refused')
        return error(session, '20026')                  # ItemDropFail
    car = next((x for x in p.char.cars if x.car_id == v.car_id), None) if v.state == ON_CAR else None
    await destroy(p, v)
    session.log.note(f'drop visual item {v.item_id} ({inven})' + (f', was on car {car.car_id}' if car else ''))
    send(session, Frame(0x4bc, struct.pack('<II', table_idx, inven)))
    send(session, vs_mod_list((v, REMOVED)))
    send(session, bonus_update(p))
    after_change(session, p, car)


@on(SVC, C2S, 0x4b7)
async def unequip_visual_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    inven, car_id = struct.unpack_from('<II', frame.payload)
    v = next((x for x in p.vsitems if x.inven_idx == inven and x.state == ON_CAR), None)
    if not v or category_of(v) in FIXED_SLOTS:         # paint / neon / tint stay until another one replaces them
        return error(session, '20028')                  # ItemUnEquipFail
    v.state = 0
    await save_state(p, v)
    send(session, Frame(0x4b8, frame.payload[:8]))
    p.apply_paints()
    send(session, vs_mod_list((v, CHANGED)))
    after_change(session, p, next((x for x in p.char.cars if x.car_id == v.car_id), None))
