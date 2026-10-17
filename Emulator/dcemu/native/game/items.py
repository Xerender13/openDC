"""Items: buying and selling in the parts shop, and the item change list (batch 2 of the native game).

Item rows come from the 2011 tables (data.Tables.item_info: ItemClient.tdf, then UseItemClient.tdf;
one TableIdx for both). The rules are the 2008 server's:

0x195 BuyItem (u32 TableIdx, u32 count; 2011 + u32 -1) -> 0x196 BuyItemAck (TableIdx, count, u32 price
    paid) and 0x192 with the new or grown item. Cmd_BuyItem 0x601640 / XiCsCharInfo::BuyItem 0x5d63a0:
    the item must exist and be sold in the shop; only usable items (type 5) can be bought more than
    one at a time; price = cost x count, at most the money held (CalcMoney "BUYITEM"); a usable item
    joins a stack of the same item with room (XiCsCharInfo::FindStackableItem: stack limit
    UseItemClient column 5, 99 when empty), else a new item is made (CreateItemNew: GID from
    SKID_SEQUENCE_TB.item_sq1, inventory index = PARTINVENIDX + 1, PC_SKID_INSERTITEM, which also
    stores PARTINVENIDX).
0x197 SellItem (TableIdx, count, InvenIdx) -> 0x198 SellItemAck (TableIdx, count, u32 money received,
    InvenIdx) and 0x192 (the item gone: state 2, or a smaller stack: state 3). XiCsCharInfo::SellItem
    0x5d39c0: price = sell x count (CalcMoney "SELLITEM"), then SubItem. (Errors 20113 / locked items:
    a trade or auction in progress, not native yet.)
0x192 ItemModList (u32 n, n x XiStrMyItemMod: XiStrMyItem 2011 (92) + i32 state: 1 new, 2 removed,
    3 changed).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send, stat_frames
from .records import Item

NEW, REMOVED, CHANGED = 1, 2, 3
NEXT_GID_SQL = "SET NOCOUNT ON; UPDATE SKID_SEQUENCE_TB SET item_sq1=item_sq1+1 OUTPUT INSERTED.item_sq1"
INSERT_SQL = "EXEC PC_SKID_INSERTITEM %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s"
STACK_SQL = "UPDATE SKID_ITEM_TB SET STACKNUM=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
DELETE_SQL = "DELETE FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
GOLD_SQL = """SET NOCOUNT ON;
UPDATE SKID_CHARACTER_TB SET GOLD=GOLD+%s WHERE SERVERID=%s AND CID=%s AND GOLD+%s>=0;
SELECT @@ROWCOUNT, GOLD FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND CID=%s"""


def mod_list(*changes):
    """0x192 for (item, state) pairs."""
    return Frame(0x192, struct.pack('<I', len(changes)) + b''.join(i.encode() + struct.pack('<i', s) for i, s in changes))


async def add_money(c, delta):
    """Money + delta in the database (never below 0) -> True if done; c.mito follows the database."""
    db = context.db
    r = await db.row(GOLD_SQL, (delta, db.server_id, c.cid, delta, db.server_id, c.cid))
    if r:
        c.mito = int(r[1])
    return bool(r and r[0])


# ---- drift shop bonus items (XiCsCharInfo::HancoinBonusUpdate flags) ----------------------------------
# Held, not expired drift items of these VisualItem categories act while held: 15 EXP drink (+30% exp from
# play, 2008 CalcExperience and Cmd_TrafficItemEvent: x 0.3), 17 MITO drink (+50% Mito, ApplyBonusMito:
# a server setting, the item text says 50%), 28 Item Drink (traffic / combo pick-ups roll twice:
# PickupTrafficItem loops 1 + flag times), 24 Mittron Fuel Booster (refuelling at half price:
# Cmd_FuelChargeReq factor - 0.5). 18 Gio, 21 Turbo Man, 20 Sticker Glue, 23 Mittron Enhancer Booster
# act in the client (the 2008 server only sends their flags in 0x5dd). Not for quest rewards (item text).
EXP_DRINK, MITO_DRINK, REPAIR_GIRL, STICKER_GLUE, TURBO_MAN, ENHANCER_BOOSTER, FUEL_BOOSTER, ITEM_DRINK = 15, 17, 18, 20, 21, 23, 24, 28
# Premium Package (i_package_01) / 3 Drink Set (i_package_02), category 49: a drift item of its own that acts as the
# three drinks while held; with a drink held too the effect counts once (item text: "will not duplicate the
# effects"; user, 2026-10-14)
PACKAGE, PACKAGE_COVERS = 49, (EXP_DRINK, MITO_DRINK, ITEM_DRINK)


def active(v):
    """A drift item that has not run out (PERIOD days from CTIME; 0 = for good) and is not on auction (state 4)."""
    from .. import now
    return v.state != 4 and (not v.period or not v.ctime or v.ctime + v.period * 86400 > now())


def held_categories(p):
    """The categories of the active drift items held, the Premium Package counted as the drinks it covers."""
    t = context.data
    held = {t.visuals[v.table_idx].category for v in p.vsitems if v.table_idx in t.visuals and active(v)}
    return held | set(PACKAGE_COVERS) if PACKAGE in held else held


def holds(p, category):
    return category in held_categories(p)


BACCHUS_SECONDS = 600              # a Bacchus F / D lasts 10 minutes, each further use adds 10 (its tooltip)
BACCHUS_BONUS = 50                  # % more EXP and Mito from play while it lasts


def bacchus_left(p):
    import time
    return max(0, int(getattr(p, 'bacchus_until', 0) - time.monotonic()))


def bacchus_frame(p, kind, new=True):
    """0x483 BacchusBuffInfo (2011, 16 bytes; client 0x5188c0 -> 0x705af0): u8 1, u32 uses, u32 kind (1 Bacchus F,
    2 Bacchus D), u32 seconds left, u8 new (the sound and "Acquired [Bacchus F / D Effect]", 11936 / 11937). The client
    then keeps the boost on collisions itself (its use type 6 for content flag InstantMission.BacchusBuffSec
    seconds) and, for D, the faster charging (type 0x4d). Without it the item showed no effect (user, 2026-10-15)."""
    # seconds left (the client adds it to its clock, 0x705b1a; as the Mita 500 buff: was ms until 2026-10-15)
    return Frame(0x483, struct.pack('<BIIIB', 1, getattr(p, 'bacchus_count', 1), kind, int(bacchus_left(p)),
                                    1 if new else 0))


def play_bonus(p, exp=0, money=0, activity=None, city=None):
    """Exp and Mito from play with the drinks held, a Bacchus running and the mounted licenses' effects (their
    activity: licenses.bonus) -> (exp, money)."""
    bacchus = BACCHUS_BONUS if bacchus_left(p) else 0
    from .licenses import bonus as license_bonus
    lic_exp, lic_money = license_bonus(p, activity, city)
    from .mita500 import bonus_rate                 # a running Mita 500 buff: x its rate (2008 ApplyMita500BonusMito, Mito
    if exp:                                         # only; here exp too, as the client's MITO/EXP label says: user)
        exp += exp * ((context.drink_exp if holds(p, EXP_DRINK) else 0) + bacchus + lic_exp) // 100
        exp = exp * bonus_rate(p) // 100
    if money:
        money += money * ((context.drink_mito if holds(p, MITO_DRINK) else 0) + bacchus + lic_money) // 100
        money = money * bonus_rate(p) // 100
    return exp, money


async def new_item(p, info, count, random=0):
    """A new inventory item. random = NRANDOM: for a car key the CarID of its car (the client finds the car for
    the key's tooltip by it: user, 2026-10-14, a key bought at auction showed no tooltip; the 2008 server's keys
    have it, the emulator's had 0)."""
    db, c = context.db, p.char
    gid = int((await db.row(NEXT_GID_SQL))[0])
    c.part_inven_idx += 1
    it = Item(gid, c.part_inven_idx, info.item_id, 0, count, random, 0, 0, 0, '', '', 0, 0, info.table_idx, p.tick)
    import datetime
    it.cdate = datetime.datetime.utcnow()       # as the row's CDATE (GetDate() in the UTC container)
    await db.execute(INSERT_SQL, (db.server_id, c.cid, c.name, gid, 0, it.inven_idx, info.item_id, count, random, 0, 0, 0,
                                  '', '', 0))
    from .setparts import start_expiry
    await start_expiry(p, it)                   # items with a period: ExpireTick = tick + period (after the row exists)
    p.items.append(it)
    return it


LINK_KEY_SQL = "UPDATE SKID_ITEM_TB SET NRANDOM=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"


async def link_keys(p):
    """At login: car keys without their CarID (NRANDOM 0: made by the emulator before 2026-10-14) get the car of
    their type (the key's value) that no other key names; a car with no key gets one (2008 XiCsCharInfo::CheckCarKey
    -> CreateCarKey: the key item named after the car's model, VehicleList "File Name"; user, 2026-10-14: a new
    character's Metro had no key). -> the keys made."""
    db, t = context.db, context.data
    keys = [i for i in p.items if (info := info_of(i)) and info.kind == 'car']
    taken = {i.random for i in keys if i.random}
    for k in keys:
        if k.random:
            continue
        car = next((c for c in p.char.cars if c.car_type == info_of(k).value and c.car_id not in taken), None)
        if car:
            k.random = car.car_id
            taken.add(car.car_id)
            await db.execute(LINK_KEY_SQL, (car.car_id, db.server_id, p.char.cid, k.inven_idx))
    made = []
    for car in p.char.cars:
        if car.car_id in taken:
            continue
        key_id = t.vehicles.get(car.car_type, {}).get('File Name', '').rsplit('.', 1)[0]
        if key_id in t.item_index:
            made.append(await new_item(p, t.item_info(t.item_index[key_id]), 1, car.car_id))
    return made


def stack_for(p, info, count):
    """A stack of this usable item with room for count more (FindStackableItem), or None."""
    if info.type != 5:
        return None
    from .setparts import period
    probe = Item(0, 0, info.item_id, 0, 0, 0, 0, 0, 0, '', '', 0, 0, info.table_idx)
    hours = period(probe)
    expire = p.tick + hours if hours else 0     # timed items: only onto a stack that runs out at the same tick
    return next((i for i in p.items if i.item_id == info.item_id and i.car_id == 0 and (i.state & 0xffff) == 0
                 and i.stack + count <= info.stack_max and (not hours or i.ctime == expire)), None)  # (state 4: auction)


async def merge_stacks(p):
    """At login: stacks of the same usable item in the inventory (not on auction) are joined up to the stack limit
    (earlier auction purchases made a new stack: user, 2026-10-14). -> number of rows removed."""
    db, piles, changed, gone = context.db, {}, {}, []      # changed: id -> item (Item is not hashable)
    for it in sorted(p.items, key=lambda i: i.inven_idx):
        info = info_of(it)
        if not info or info.type != 5 or it.car_id or (it.state & 0xffff) or it.stack <= 0:
            continue
        for pile in piles.setdefault((it.item_id, it.ctime), []):     # timed items: same ExpireTick only
            take = min(info.stack_max - pile.stack, it.stack)
            if take > 0:
                pile.stack += take
                it.stack -= take
                changed[id(pile)], changed[id(it)] = pile, it
            if not it.stack:
                break
        if it.stack:
            piles[(it.item_id, it.ctime)].append(it)
        else:
            gone.append(it)
    for it in changed.values():
        if it.stack:
            await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
    for it in gone:
        await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
        p.items.remove(it)
    return len(gone)


@on(SVC, C2S, 0x195)
async def buy_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    table_idx, count = struct.unpack_from('<II', frame.payload)
    info = context.data.item_info(table_idx)
    from .alchemy import shop_items
    if not info or not (info.shop or info.item_id in shop_items()):   # + the manufacturing shop's goods
        return error(session, '20024')                  # NotFoundItem
    if count < 1 or (info.type != 5 and count != 1):
        return error(session, '20029')                  # ItemBuyFail
    price = info.cost * count
    if price > p.char.mito or not await add_money(p.char, -price):
        return error(session, '20029')                  # ItemBuyFail (XiCsCharInfo::BuyItem false)
    it = stack_for(p, info, count)
    if it:
        it.stack += count
        db = context.db
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        state = CHANGED
    else:
        it, state = await new_item(p, info, count), NEW
    session.log.note(f'buy item {info.item_id} x{count} for {price}: inventory {it.inven_idx}, stack {it.stack}')
    send(session, Frame(0x196, struct.pack('<III', table_idx, count, price)))
    send(session, mod_list((it, state)))


@on(SVC, C2S, 0x197)
async def sell_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    table_idx, count, inven_idx = struct.unpack_from('<III', frame.payload)
    it = next((i for i in p.items if i.inven_idx == inven_idx), None)
    info = context.data.item_info(table_idx)
    if not it or not info or it.table_idx != table_idx or count < 1 or count > it.stack or (it.state & 0xffff) == 4:
        return error(session, '20030')                  # (state 4: on auction)                  # ItemSellFail
    price = info.sell * count
    await add_money(p.char, price)
    db = context.db
    it.stack -= count
    if it.stack:
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, inven_idx))
        state = CHANGED
    else:
        await db.execute(DELETE_SQL, (db.server_id, p.char.cid, inven_idx))
        p.items.remove(it)
        state = REMOVED
    session.log.note(f'sell item {info.item_id} x{count} for {price}')
    send(session, Frame(0x198, struct.pack('<IIII', table_idx, count, price, inven_idx)))
    send(session, mod_list((it, state)))
    if it.car_id:
        for f in stat_frames(p):
            send(session, f)


# 0x193 DropItem (u32 TableIdx: 0 from the 2011 client's delete mode, u32 InvenIdx, i32 count) -> 0x194
#     DropItemAck (the same) and 0x192. XiCsCharInfo::DropItem 0x5d1990: the item exists, is not locked and
#     holds the count; it is removed without money (CalcMoney "DROP" 0). Items on a car are refused here.
@on(SVC, C2S, 0x193)
async def drop_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return error(session, '20017')                  # NotInitializedChar
    _, inven_idx, count = struct.unpack_from('<IIi', frame.payload)
    it = next((i for i in p.items if i.inven_idx == inven_idx), None)
    if not it or it.car_id or count <= 0 or count > max(it.stack, 1) or (it.state & 0xffff) == 4:
        return error(session, '20026')                  # ItemDropFail
    db = context.db
    it.stack -= count
    if it.stack > 0:
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        state = CHANGED
    else:
        await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
        p.items.remove(it)
        state = REMOVED
    session.log.note(f'drop item {it.item_id} x{count}')
    send(session, Frame(0x194, struct.pack('<IIi', it.table_idx, inven_idx, count)))
    send(session, mod_list((it, state)))


# --- equipping parts -------------------------------------------------------------------------------
# 0x199 EquipItem (InvenIdx, DstSlotIdx, CarID) -> 0x19a EquipItemAck (the same), 0x192, 0x2f8 + 0x2f9. A boxed
# part loses its Parts Box (BOX 0).
# 0x19b UnEquipItem (InvenIdx, CarID) -> 0x19c UnEquipItemAck (the same), 0x192, stats.
# The item's state word (SKID_ITEM_TB.STATE) is u16 state (1 = on a car) + u16 slot << 16 (100.. on the
# car; Xerender: two speed parts in 100 and 101, boost in 109).
# XiCsCharInfo::EquipItem 0x5caaf0: the item is a part (not usable, type 5), not state 4, not being heat
# treated, the character's level >= the item's (ItemClient column 7), the car exists and is not on
# auction. A part (types 0-4) needs fewer than Contents.ini Main.PartsInvenLine (2) parts of its type on
# the car. An option (types 6-10) needs a part in the target slot, replaces the option there, and its
# grade must fit the part's (ItemGrade::CheckGrade: N <- FN ON; S <- FN FS OS; H <- FN FS FH OH;
# E <- FN FS FH FE OE). The slot is kept only with Main.OptionItem.
# XiCsCharInfo::UnEquipItem 0x5ca880: a part comes off with the option on its slot.
# 2011 docking parts (type 11): docking.py (combining, 0x18e EnchantItem); an EquipItem with a docking item
# docks it into the part in that slot. Option parts only with emulator.ini [items] option_parts = 1 (the
# official 2011 server had them off; sent to the client as Main.OptionItem): refused otherwise.
OPTION_TYPES, DOCK = (6, 7, 8, 9, 10), 11
GRADE_FITS = {'N': ('FN', 'ON'), 'S': ('FN', 'FS', 'OS'), 'H': ('FN', 'FS', 'FH', 'OH'),
              'E': ('FN', 'FS', 'FH', 'FE', 'OE')}
ON_CAR = 1
HEAT_TEXT = 'Use a Heat Treatment Kit on this part to take it off the car.'
ITEM_STATE_SQL = "UPDATE SKID_ITEM_TB SET CARID=%s, STATE=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"


def slot_of(it):
    return it.state >> 16


# the client's part slots on a car: 3 per type, speed 100-102, accel 103-105, crash 106-108, boost 109-111
# (client 0x5fe7eb.., PART_TYPES numbering)
SLOT_BASE = {0: 100, 2: 103, 1: 106, 3: 109}


async def fix_shared_slots(p):
    """Two parts in one slot (left by the old EquipItem, which did not take the slot's part off): the client draws
    the second in a free slot of its type and docking there was refused (user, 2026-10-16). The lower InvenIdx
    moves to the first free slot of its type, as the client shows it; its docking / option stay with the other."""
    moved = []
    for car_id in {i.car_id for i in p.items if i.car_id}:
        parts = sorted((i for i in p.items if i.car_id == car_id and (i.state & 0xffff) == ON_CAR and info_of(i)
                        and info_of(i).type in SLOT_BASE), key=lambda i: -i.inven_idx)
        taken = set()
        for it in parts:
            if slot_of(it) not in taken:
                taken.add(slot_of(it))
                continue
            base = SLOT_BASE[info_of(it).type]
            free = next((s for s in range(base, base + 3) if s not in taken and not any(
                slot_of(i) == s and i.car_id == car_id and (i.state & 0xffff) == ON_CAR for i in p.items)), None)
            if free is None:
                placed(it, 0, 0)
            else:
                placed(it, car_id, free)
                taken.add(free)
            moved.append(it)
    if moved:
        await save_state(p, *moved)
    return moved


def placed(it, car_id, slot):
    it.car_id, it.state = car_id, (slot << 16 | ON_CAR) if car_id else 0


async def save_state(p, *items):
    db = context.db
    for it in items:
        await db.execute(ITEM_STATE_SQL, (it.car_id, it.state, db.server_id, p.char.cid, it.inven_idx))


def on_top(t):
    return t in OPTION_TYPES


def info_of(it):
    return context.data.item_info(it.table_idx)


@on(SVC, C2S, 0x199)
async def equip_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return
    inven_idx, slot, car_id = struct.unpack_from('<III', frame.payload)
    it = next((i for i in p.items if i.inven_idx == inven_idx), None)
    info = info_of(it) if it else None
    car = next((c for c in p.char.cars if c.car_id == car_id), None)
    from .. import nation
    why = nation.part_allowed(session, p, info, car) if info else None
    if (not it or not info or info.type == 5 or (it.state & 0xffff) == 4 or it.upgrade < 0   # < 0: broken
            or why or not car or car.on_auction
            or (on_top(info.type) and not context.option_parts)):
        if why:
            session.log.note(f'equip {info.item_id}: refused ({why}; nation {nation.of(session)})')
        return error(session, '20027')                  # ItemEquipFail
    if info.type == DOCK:
        from .docking import dock
        part = next((i for i in p.items if i.car_id == car_id and slot_of(i) == slot and (i.state & 0xffff) == ON_CAR
                     and info_of(i).type in (0, 1, 2, 3)), None)
        err = await dock(session, p, part, it) if part and context.docking_parts else '20027'
        if err:
            return error(session, err)
        return send(session, Frame(0x19a, frame.payload[:12]))
    contents = context.data.contents
    on_car = [i for i in p.items if i.car_id == car_id and i is not it and (i.state & 0xffff) == ON_CAR]
    changed, redraw = [], None
    if on_top(info.type):
        base = next((i for i in on_car if not on_top(info_of(i).type) and slot_of(i) == slot), None)
        if not base or info.grade not in GRADE_FITS.get(info_of(base).grade, ()):
            return error(session, '20027')
        for old in [i for i in on_car if slot_of(i) == slot and on_top(info_of(i).type)]:
            placed(old, 0, 0)
            changed.append(old)
    else:
        # a part dropped on an occupied slot: the client sends only this EquipItem and expects the part there to come
        # off (with its option and docking; a hyper one not: it needs a Heat Treatment Kit used on it). Before, both parts
        # stayed in one slot and the kit was skipped (user, 2026-10-16: Double Beta over High GR Beta)
        old = next((i for i in on_car if slot_of(i) == slot and info_of(i).type in (0, 1, 2, 3)), None)
        lines = contents.get('Main.PartsInvenLine', 2)
        if old and info_of(old).type == info.type and info.type in SLOT_BASE:
            # the client sends the slot it was dropped on even when the type's other line is free (user,
            # 2026-10-16: equipping the second set took the first one off): use a free line first, replace only
            # when the type's lines are full
            taken = {slot_of(i) for i in on_car}
            base = SLOT_BASE[info.type]
            free = next((s for s in range(base, base + lines) if s not in taken), None)
            if free is not None:
                # the client has already drawn the new part over the dropped-on one (user: the first set's parts
                # became invisible): resend that one after the new part so it is drawn back in its own slot
                redraw = old
                slot, old = free, None
                frame = Frame(frame.type, struct.pack('<III', inven_idx, slot, car_id) + frame.payload[12:])
        if old:
            if info_of(old).type != info.type:
                return error(session, '20027')
            if needs_heat(p, old):
                session.log.note(f'equip {info.item_id} over {old.item_id}: H part / docking, needs a Heat Treatment Kit')
                return error(session, HEAT_TEXT)
            await take_off(session, p, old)
            on_car = [i for i in on_car if i.car_id == car_id and (i.state & 0xffff) == ON_CAR]
        if sum(1 for i in on_car if info_of(i).type == info.type) >= contents.get('Main.PartsInvenLine', 2):
            return error(session, '20027')
    placed(it, car_id, slot if contents.get('Main.OptionItem', 1) else 0)
    changed.append(it)
    if boxed(it):       # a part put on a car comes out of its Parts Box (as when bought at auction; user, 2026-10-14)
        it.box = 0
        db = context.db
        await db.execute("UPDATE SKID_ITEM_TB SET BOX=0 WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                         (db.server_id, p.char.cid, it.inven_idx))
    if info.grade == 'H' and await scorch(p, it, True):
        session.log.note(f'{info.item_id} is scorched: {it.item_id}')
    await save_state(p, *changed)
    session.log.note(f'equip {info.item_id} on car {car_id} slot {slot}')
    send(session, Frame(0x19a, frame.payload[:12]))
    send(session, mod_list(*((i, CHANGED) for i in changed + ([redraw] if redraw else []))))
    for f in stat_frames(p):
        send(session, f)


SWAP_SQL = "UPDATE SKID_ITEM_TB SET ITEMID=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"


async def scorch(p, it, scorched):
    """A hyper part becomes its scorched twin when put on a car, and the twin the part again when a Heat Treatment
    Kit takes it off: ItemClient column 14 links them (i_a_000009 Gargoyle <-> i_a_000009_b Scorched Gargoyle; 20
    hyper parts have one; same stats). The client draws the twin's icon (user, 2026-10-15: no scorched icon).
    -> True when the item changed."""
    t = context.data
    rows = t._part_rows
    if not 0 <= it.table_idx < len(rows) or len(rows[it.table_idx]) <= 14:
        return False
    twin = rows[it.table_idx][14]
    if twin not in t.item_index or scorched != twin.endswith('_b') or it.item_id.endswith('_b') == scorched:
        return False
    db = context.db
    it.item_id, it.table_idx = twin, t.item_index[twin]
    await db.execute(SWAP_SQL, (twin, db.server_id, p.char.cid, it.inven_idx))
    return True


def heat_kit(p):
    """A Heat Treatment Kit held (UseItemClient kind heattreatment, i_n_00025; value 2 = hyper), or None."""
    return next((i for i in p.items if not i.car_id and info_of(i) and info_of(i).kind == 'heattreatment'), None)


def hyper_docked(p, it):
    """The part + docking pair it belongs to when that slot holds an H docking (grade OH) -> list, else []."""
    pair = [i for i in p.items if i.car_id == it.car_id and slot_of(i) == slot_of(it) and (i.state & 0xffff) == ON_CAR
            and (info_of(i).type == DOCK or not on_top(info_of(i).type))]
    return pair if any(info_of(i).type == DOCK and info_of(i).grade == 'OH' for i in pair) else []


def needs_heat(p, it):
    """Taking it off needs a Heat Treatment Kit: a normal hyper part itself (grade H; user, 2026-10-14) or a slot
    holding an H docking on one. Set parts (si_*, also grade H) never: the kit is only for normal H parts (user,
    2026-10-16, checked with other players), with or without an H docking on them."""
    from .setparts import is_set
    info = info_of(it)
    part = it if info.type != DOCK else next((i for i in hyper_docked(p, it) if info_of(i).type != DOCK), None)
    if part and is_set(part):
        return False
    return bool(hyper_docked(p, it)) or (info.grade == 'H' and not on_top(info.type) and info.type != DOCK)


async def take_off(session, p, it, kit=None):
    """it (and, for a part, the option and docking on its slot; for a hyper docking, its part) comes off the car;
    kit (a Heat Treatment Kit) is used up. -> False if a needed kit is missing."""
    changed = [it]
    if not on_top(info_of(it).type) and info_of(it).type != DOCK:     # its option and docking come off too
        changed += [i for i in p.items if i is not it and i.car_id == it.car_id and slot_of(i) == slot_of(it)
                    and (on_top(info_of(i).type) or info_of(i).type == DOCK)]
    hyper = needs_heat(p, it)
    if hyper:
        # an H part, or a slot with an H docking, comes off only with a Heat Treatment Kit; an H docking takes its
        # part with it (the user, wiki)
        kit = kit or heat_kit(p)
        if not kit:
            return False
        changed += [i for i in hyper_docked(p, it) if i not in changed]
    for i in changed:
        placed(i, 0, 0)
        if hyper:
            await scorch(p, i, False)           # a scorched part is the part again (heat treatment)
    await save_state(p, *changed)
    mods = [(i, CHANGED) for i in changed]
    if hyper:
        from .driftuse import take_one
        mods.append(await take_one(p, kit))
        session.log.note(f'heat treatment: {[i.item_id for i in changed]} off the car, kit used')
    send(session, mod_list(*mods))
    for f in stat_frames(p):
        send(session, f)
    return True


@on(SVC, C2S, 0x19b)
async def unequip_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    inven_idx, car_id = struct.unpack_from('<II', frame.payload)
    it = next((i for i in p.items if i.inven_idx == inven_idx and i.car_id), None)
    if not it:
        return error(session, '20028')                  # ItemUnEquipFail
    if needs_heat(p, it):
        # as the client does for normal (scorched) hyper parts: only a Heat Treatment Kit used on the part (0x1a3)
        # takes it off; set parts the client lets drag off (user, 2026-10-16: a kit in the bag was used silently)
        session.log.note(f'unequip {it.item_id}: H part / docking, needs a Heat Treatment Kit used on it')
        return error(session, HEAT_TEXT)
    send(session, Frame(0x19c, frame.payload[:8]))
    await take_off(session, p, it)


# 0x1a3 ItemUseEx (u32 DestInvenIdx, u32 SrcInvenIdx, u32 CarID) -> 0x1a4 ItemUseExAck (the same) and 0x192.
# 2008 XiCsCharInfo::UseItemEx 0x5ce420: a Parts Box (use kind partsbox) on a hyper part (table grade H; the
# tradeable ones too, as the 2011 client offers: user 2026-10-14): here the part goes into the box (SKID_ITEM_TB.BOX = 1; the client shows the parts box icon) and one
# Open Part Box (i_n_00026) is used up; a boxed part can be registered in the Auction House, and comes out of the
# box when bought (auction.py; the user, 2026-10-14: hyper parts need a parts box to be sold). Here also a Heat
# Treatment Kit on a part or docking on the car: an H docking slot comes off with its part (take_off).
async def pack_item(session, p, part, box):
    """A Parts Box on a hyper part (table grade H, not on a car, not yet boxed): BOX = 1, one box used up.
    -> the 0x192 changes, or None (refused)."""
    pinfo = info_of(part) if part else None
    if (not part or not pinfo or part.car_id or (part.state & 0xffff) or part.box or pinfo.grade != 'H'
            or pinfo.type not in (0, 1, 2, 3)):
        session.log.note(f'parts box on {part.item_id if part else None}: refused')
        return None
    part.box = 1
    db = context.db
    await db.execute("UPDATE SKID_ITEM_TB SET BOX=1 WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                     (db.server_id, p.char.cid, part.inven_idx))
    from .driftuse import take_one
    used = await take_one(p, box)
    session.log.note(f'parts box: {part.item_id} boxed')
    return [(part, CHANGED), used]


def needs_box(it, info):
    """Whether the item may change hands (auction, mail) only in a Parts Box: every hyper part (grade H; user,
    2026-10-14: all H parts) and untradeable items (ItemClient column 17 / UseItemClient column 15)."""
    return info.grade == 'H' or not info.tradeable


def boxed(it):
    return bool(it.box) and not it.item_id.startswith('dock_')    # a docking item's BOX holds its white points


def parts_box(p, inven):
    return next((i for i in p.items if i.inven_idx == inven and info_of(i) and info_of(i).kind == 'partsbox'
                 and (i.state & 0xffff) == 0), None)


# 0x1a6 PackItem (u32 part InvenIdx, u32 Parts Box InvenIdx; 2011, the client's inventory "pack" with an
# i_n_00027 Parts Box from the drift shop) -> 0x1a7 PackItemAck (the same 8 bytes; the client's handler 0x50f060
# reads nothing) and 0x192. No handler until 2026-10-14 (user: the parts boxes did not work).
@on(SVC, C2S, 0x1a6)
async def pack(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    dest, src = struct.unpack_from('<II', frame.payload)
    box = parts_box(p, src)
    part = next((i for i in p.items if i.inven_idx == dest), None)
    changes = await pack_item(session, p, part, box) if box else None
    if not changes:
        return error(session, '20036')                  # ItemUseFail
    send(session, Frame(0x1a7, frame.payload[:8]))
    send(session, mod_list(*changes))


@on(SVC, C2S, 0x1a3)
async def item_use_ex(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return error(session, '20017')
    dest, src, car_id = struct.unpack_from('<III', frame.payload)
    box = parts_box(p, src)
    if box:
        changes = await pack_item(session, p, next((i for i in p.items if i.inven_idx == dest), None), box)
        if not changes:
            return error(session, '20036')
        send(session, Frame(0x1a4, frame.payload[:12]))
        send(session, mod_list(*changes))
        return
    it = next((i for i in p.items if i.inven_idx == dest and i.car_id), None)
    kit = next((i for i in p.items if i.inven_idx == src and info_of(i) and info_of(i).kind == 'heattreatment'), None)
    session.log.note(f'item use ex: dest {dest} src {src} car {car_id}')
    if not it or not kit:
        return error(session, '20036')                  # ItemUseFail (Parts Box not native)
    send(session, Frame(0x1a4, frame.payload[:12]))
    await take_off(session, p, it, kit)


# --- using items -------------------------------------------------------------------------------------
# 0x1a1 ItemUse (InvenIdx, count) -> 0x1a2 ItemUseAck (InvenIdx, count, XiStrItemUseInfo: use type, value,
# time, and in 2011 a fourth u32: a time that replaces the third when not 0, 0x72b264; without it the client logged
# "Wrong Packet Size. CMD(418) CmdLen: 26, AnalysisSize: 24" at every use, user 2026-10-15) and 0x192. The use type is the 2011 client's (its UseItemClient kind -> code
# function 0x7014e8: the 2008 codes + 1, then new kinds); the ack's handler 0x51fdc0 -> 0x72a480 switches on
# it: fuel 3, fuelsave 5, turbosave 6, damage 7, the point-ups 8-10, 0x1b / 0x1c, cartrans 0x28, auto_drive
# 0x29 (opens the Auto-Drive destination window, [ui + 0x1ac] 0x625ff0; warp 0x4b too), 0x4c-0x64 (Neo
# items); any other code does nothing there. Until 2026-10-15 the 2008 codes went out (one off: the
# Auto-Driver got 0x1a = day_mission and opened nothing). The server: fuel adds its value to the current car's
# Mitron (up to the capacity); the point-up items give their value to one stat for their time (char buff
# slots); the others are used up and act on the client. Unknown kinds go out as 0 (nothing on the client).
USE_KINDS = {'piece': 1, 'upgrade': 2, 'fuel': 3, 'money': 4, 'fuelsave': 5, 'turbosave': 6, 'damage': 7,
             'accelpointup': 8, 'crashpointup': 9, 'speedpointup': 0xa, 'incomaccel': 0xb, 'incomspeed': 0xc,
             'incomcrash': 0xd, 'incomboost': 0xe, 'heattreatment': 0xf, 'partsbox': 0x10, 'garbage': 0x11,
             'coupon': 0x12, 'car': 0x13, 'teampoint': 0x14, 'ch_attack': 0x15, 'event_item': 0x16, 'jewel': 0x17,
             'trans': 0x18, 'repair': 0x19, 'day_mission': 0x1a, 'battle_quick': 0x1b, 'under_quick': 0x1c,
             'trans_up': 0x1d, 'vc_T_callunit': 0x1e, 'vc_C_callunit': 0x1f, 'vc_UC_120': 0x20, 'vc_UC_Direct': 0x21,
             'icon_only': 0x22, 'giftbox': 0x23, 'reward_piece': 0x24, 'lotto': 0x25, 'full_repair': 0x26,
             'buff_item': 0x27, 'cartrans': 0x28, 'auto_drive': 0x29, 'craft_up': 0x2a, 'gacha': 0x2b, 'trade': 0x2c,
             'luckybag': 0x2d, 'giftbox_lv': 0x2e, 'ch_ghost': 0x2f, 'giftbox_car': 0x30, 'GWEvent': 0x31,
             'EventBox': 0x32, 'item_recycle': 0x33, 'craft_up_X': 0x34, 'enchant_kit': 0x35, 'mobile_shop': 0x36,
             'dcbadge': 0x37, 'battle_exp': 0x38, 'Ultra_repair': 0x39, 'instant_r': 0x3a, 'instant': 0x3b,
             'recipe_item': 0x3c, 'chocolet_item': 0x3d, 'chocolet_gift_item': 0x3e, 'gacha_key': 0x3f,
             'gacha_parts': 0x40, 'MitoCarUpgrade': 0x41, 'partsgrinder': 0x42, 'event_box_recipe': 0x43,
             'user_create': 0x47, 'user_create_source': 0x48, 'user_create_kit': 0x49, 'reward_piece_use': 0x4a,
             'warp': 0x4b, 'bacchus_f': 0x4c, 'bacchus_d': 0x4d, 'craft_up_plus': 0x4e, 'new_repair': 0x4f,
             'double_upgrade': 0x50, 'quickslotextend': 0x51, 'shield': 0x52, 'YS': 0x53, 'drop_giftbox': 0x54,
             'giftbox_auto': 0x55, 'leveldown': 0x56, 'healthup': 0x57, 'healthupnow': 0x58,
             'party_healthupnow': 0x59, 'revival': 0x5a, 'shieldup': 0x5b, 'weapondamage': 0x5c,
             'neowslotextend': 0x5d, 'minimaprader': 0x5e, 'booster_chage': 0x5f, 'loweraggro': 0x60,
             'repair_waepon': 0x61, 'repair_coil': 0x62, 'repair_fusion': 0x63, 'repair_armor': 0x64}
POINT_UP = {'speedpointup': 0, 'crashpointup': 1, 'accelpointup': 2}       # stat index (speed, crash, accel, boost)


@on(SVC, C2S, 0x1a1)
async def use_item(session, frame):
    import time
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    inven_idx, count = struct.unpack_from('<II', frame.payload)
    it = next((i for i in p.items if i.inven_idx == inven_idx), None)
    info = info_of(it) if it else None
    if not it or not info or info.type != 5 or count < 1 or count > it.stack or (it.state & 0xffff) == 4:
        return error(session, '20036')                  # ItemUseFail
    db, c = context.db, p.char
    if info.kind == 'gacha_key':                    # Gotcha key parts + vehicle parts A-D -> the car gift box
        from .gotcha import combine
        return await combine(session, p, it, info)
    if info.kind in ('bacchus_f', 'bacchus_d'):
        from .mita500 import active as mita_active
        if mita_active(p):                          # its tooltip: "Cannot be used with the Mita 500 effect"
            return error(session, 'Bacchus cannot be used while the Mita 500 effect lasts.')
    if info.kind == 'user_create':                  # a skill book: learned (alchemy.py), then used up
        from .alchemy import learn
        if not await learn(session, p, info):
            return
    upgrade = None
    if info.kind == 'MitoCarUpgrade':               # a chance to upgrade the current car (cars.roll_upgrade_item)
        from .cars import grade_check, item_grade
        upgrade = grade_check(session, p, p.car, item_grade(info.item_id))
        if not upgrade:
            return
        count = 1
    stats = False
    if info.kind == 'fuel':
        car = p.car
        if car:
            car.mitron = min(car.capacity, car.mitron + info.value * count)
            await db.execute("UPDATE SKID_CAR_TB SET MITRON=%s WHERE SERVERID=%s AND CID=%s AND CARID=%s",
                             (car.mitron, db.server_id, c.cid, car.car_id))
    elif info.kind in ('bacchus_f', 'bacchus_d'):
        # Bacchus F / D (manufactured): +50 % EXP and Mito (play_bonus) for 10 minutes, more uses add up; the client's
        # side (boost kept on collisions, D: faster boost charging, its buff display) comes with 0x483 (bacchus_frame).
        p.bacchus_until = time.monotonic() + bacchus_left(p) + BACCHUS_SECONDS * count
        p.bacchus_count = getattr(p, 'bacchus_count', 0) + count
    elif info.kind == 'cartrans':                   # camouflage kits: 5 min, Adv. 15 min (their texts)
        from . import licenses
        seconds = (900 if 'Adv' in info.name else 300) * count
        st = licenses.state(p)
        if st is not None:                          # ME_CarTransExp: more Mito while it runs
            st['camo_until'] = max(st.get('camo_until', 0), time.time()) + seconds
        await licenses.count(session, 'CamoKitUseTime', seconds)
    elif info.kind in POINT_UP:
        p.buffs[POINT_UP[info.kind]] = (info.value, time.monotonic() + info.time)
        stats = True
        loop_stats_after(session, p, info.time)
    it.stack -= count
    if it.stack:
        await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, inven_idx))
        state = CHANGED
    else:
        await db.execute(DELETE_SQL, (db.server_id, c.cid, inven_idx))
        p.items.remove(it)
        state = REMOVED
    session.log.note(f'use item {info.item_id} ({info.kind}) x{count}')
    send(session, Frame(0x1a2, struct.pack('<II4I', inven_idx, count, USE_KINDS.get(info.kind, 0), info.value,
                                           info.time, 0)))
    if info.kind in ('bacchus_f', 'bacchus_d'):
        send(session, bacchus_frame(p, 1 if info.kind == 'bacchus_f' else 2))
    send(session, mod_list((it, state)))
    if info.kind in ('giftbox', 'giftbox_car', 'giftbox_lv') and info.reward:   # gift boxes, Gotcha car boxes: their RewardGroup
        from .driftuse import open_gift_box
        for _ in range(count):
            (await open_gift_box(session, p, info)).send(session, p)
    if stats:
        for f in stat_frames(p):
            send(session, f)
    if upgrade:
        from .cars import roll_upgrade_item
        await roll_upgrade_item(session, p, p.car, upgrade, info)


def loop_stats_after(session, p, seconds):
    """Send the stats again when a timed bonus ends (the 2008 server's tick did the same)."""
    import asyncio

    async def later():
        await asyncio.sleep(seconds + 0.5)
        for f in stat_frames(p):
            send(session, f)
    asyncio.ensure_future(later())


# 0x5dc ItemExpireCmd -> 0x5dd BonusUpdate (u32 x9: exp bonus, Mito bonus, Repair Girl, Turbo Man, sticker,
# double upgrade, half Mitron charge, 2x item drop, inventory upgrade). Cmd_ItemExpireCmd 0x5ed6a0
# recomputes them from the drift shop items (XiCsCharInfo::HancoinBonusUpdate). Here: 1 for each kind of
# which an item is held (VisualItem categories 15 Drinkexp, 17 Drinkmito, 18 RepairGirl, 21 Turboman, 20
# StickerLicense, 23 DoubleUpgrade, 24 HalfMitronCharge, 28 EXTEND_ITEMDROP2X, 29 EXTEND_INVENUPGRADE),
# active (not expired) items only.
BONUS_CATEGORIES = (15, 17, 18, 21, 20, 23, 24, 28, 29)


def bonus_update(p):
    held = held_categories(p)
    return Frame(0x5dd, struct.pack('<9I', *(1 if k in held else 0 for k in BONUS_CATEGORIES)))


@on(SVC, C2S, 0x5dc)
async def item_expire(session, frame):
    p = session.state.get('player')
    if p:
        send(session, bonus_update(p))
