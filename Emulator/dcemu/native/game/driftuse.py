"""Drift shop items of the Misc tab (TOP_ETC): what they do when bought or used, gift boxes, scratch cards,
lucky bags and the name change kit; rewards from the 2011 RewardGroup.xlt.

**Which items the client uses** (drift inventory 0x5ffd60): it sends 0x4b9 VisualItemUse (u32 InvenIdx, u32
car) only for the categories 0x5f6fa0 lets through: 16 inventory extension, 22 garage extension (both
checked against their limits first), 27 Mito prize, 37, 43 car transfer, 51 discount coupon (own dialog),
54. -> 0x4ba VisualItemUseAck (the same), 0x2fa ExtendUpdate (u32 HancoinInven, u32 HancoinGarage), 0x4b2
(the item, used: 2). PacketParser::Cmd_VisualItemUse 0x602df0 / XiCsCharInfo::UseVisualItem 0x5d1500
(2008) did 16 (part inventory page + 1), 22 (garage floor + 1) and 27 (Mito: the item's value), marked the
item used (state 2) and answered the others without using them. The other categories go to a second
switch (0x5fff56): 36 opens the rename dialog, 39 auto drive and 42 hongbao have their own, the rest
nothing. So the inventory item bundles cannot be used from the drift inventory: they become inventory
items when bought (AT_PURCHASE, called from vshop.py), as the VShopItem "Instant" items do (Mito prizes,
the Battle Zone Package). What an item gives is its VisualItem.xlt value (column 6):
  33 UseItem, 50 Package Set: "<inventory item> <count>" (i_b_untouchable_10 -> "i_n_00058 10"; the
     scratch cards "lotto_scratchies_Natura 1 27": the card x1, 27 = its car).
     "Normal 11" / "ST 5" (Lottery bundles): the scratch card the player picked (item text, see parse_value).
  27 Mito Prize: the amount.
  2016 packs (category 23 Mittron Enhancer Booster "i_n_double 10", 56 Manufacturing Booster "i_n_createdouble
     10", 59 Upgrade Chance Enhancing Fluid "i_n_chancetime 1", 19 Parts box "i_n_00027 25"): the inventory items
     named. The 2011 Booster i_d_double and Parts box i_d_partsbox (value 100) name no item: the Booster stays a
     drift item (used from the drift inventory by 0x1ae, upgrade.py), the Parts box gives 10.
Without an inventory item in the 2011 tables (not sold here): Seed Parts (i_n_seed_*), the "ST" / "Normal"
scratch cards. The two Premium Packages (49) stay drift items and act as the three drinks (items.PACKAGE).

**Inventory gift boxes** (UseItemClient kind "giftbox", used with 0x1a1 ItemUse) give their RewardGroup.xlt
group (UseItemClient column 3). A group's rows: Reward_Type NormalItem (inventory item x Reward_Count),
SkidItem (a drift item for Reward_Period days, 0 = for good; Instant ones act at once), Mito / Exp
(Reward_Count), RewardGroup (that group, rolled), n/a (nothing: the scratch cards' "bust"); Probability
100 = always given, the other rows are one weighted pick (the Mito table adds up to 100, the Natura card's
prizes + a 95 bust). Recycle: only the Item Recycling Kit's group (recycle). Not given: SkidItem_SetPeriod.
Money reaches the client as 0x8a MoneyMessage (kind 1, i64 delta, i64 total), exp with the stats.
"""
import random
import struct
from collections import defaultdict

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context, now
from .items import NEXT_GID_SQL, NEW, CHANGED, STACK_SQL, add_money, mod_list, new_item, active
from .login import SVC, error, send, stat_frames
from .records import VisualItem

USED = 2                       # VSItemModList / XiCsVSItem state of a used item (UseVisualItem)
INVEN_EXT, GARAGE_EXT, MITO_PRIZE, USE_ITEM, PACKAGE_SET = 16, 22, 27, 33, 50
DOUBLE_UPGRADE, CREATE_DOUBLE, FULL_CHANCE = 23, 56, 59      # 2016 packs of inventory items (see above)
GIVES_ITEMS = (USE_ITEM, PACKAGE_SET, DOUBLE_UPGRADE, CREATE_DOUBLE, FULL_CHANCE)
# Parts box (i_d_partsbox, category 19, "Sold in bulk of 10 boxes per purchase"): the 2008 server gave 10 inventory
# Parts Boxes for it (Cmd_BuyVisualItem 0x6043b4: TakeItem(PartsBoxID "i_n_00027", 10)) instead of a drift item; it
# was kept as an unusable drift item until 2026-10-14 (user). Used on a hyper part with 0x1a3 (items.item_use_ex).
PARTS_BOX, PARTS_BOX_ITEM, PARTS_BOX_COUNT = 19, 'i_n_00027', 10
AT_PURCHASE = GIVES_ITEMS + (PARTS_BOX,)

_groups = None


def groups():
    """RewardGroup.xlt -> {group: [(type, item id, period days, count, probability, Etc_Value)]}."""
    global _groups
    if _groups is None:
        import os
        from ..data import read_xlt
        _groups = defaultdict(list)
        rows = read_xlt(os.path.join(context.data.root, 'Init', 'RewardGroup.xlt'))
        # Probability by its header: column 10 in 2011, 11 in 2016 (a "Trade Restriction" column before it; read at
        # 10 every 2016 row had chance 0 and no gift box or Gotcha capsule gave anything: user, 2026-10-20)
        prob = next((i for i, c in enumerate(rows[2]) if c.strip() == 'Probability'), 10) if len(rows) > 2 else 10
        for r in rows[3:]:
            if len(r) > prob and r[1]:
                try:
                    _groups[r[1]].append((r[3], r[5], int(float(r[6] or 0)), int(float(r[7] or 0)),
                                          float(r[prob].strip() or 0), int(float(r[8] or 0))))
                except ValueError:
                    pass
    return _groups


def roll(group, depth=0):
    """-> [(type, item id, period, count, Etc_Value)] won from a group (nested groups rolled too)."""
    rows = groups().get(group, [])
    sure = [r for r in rows if r[4] >= 100]
    chance = [r for r in rows if 0 < r[4] < 100]
    won = list(sure)
    if chance:
        won.append(random.choices(chance, weights=[r[4] for r in chance])[0])
    out = []
    for kind, item, period, count, _, etc in won:
        if kind == 'RewardGroup' and depth < 5:
            for _ in range(max(count, 1)):
                out += roll(item, depth + 1)
        elif kind in ('NormalItem', 'SkidItem', 'Mito', 'Exp', 'n/a', 'Recycle'):  # n/a: nothing (a card's bust);
            # Recycle: the recycled drift item again for Reward_Period days (recycle below; give() skips it)
            out.append((kind, item, period, count, etc))
    return out


_lower = None


def item_named(name):
    """An inventory item id as the tables spell it: VisualItem values differ in case (Seed Parts "i_n_seed_S"
    -> ItemClient "i_n_Seed_S")."""
    global _lower
    if name in context.data.item_index:
        return name
    if _lower is None:
        _lower = {k.lower(): k for k in context.data.item_index}
    return _lower.get(name.lower())


def parse_value(value, text=''):
    """VisualItem value "item count [car]" -> (item id, count) or None.
    The "Lottery" / "ST Lottery" bundles (value "Normal 11" / "ST 5") name no item: the shop lets the player
    pick a car's scratch card and sends it in the item text, "<VisualItem UniqueId of the card> <count>"
    ("10829 11" = Scratch Card(Serpens)(1) -> lotto_scratchies_Serpens); the count is the bundle's."""
    t = context.data
    f = value.split()
    item = f and item_named(f[0])
    if item:
        return item, int(f[1]) if len(f) > 1 and f[1].isdigit() else 1
    if len(f) == 1 and len(f[0]) == 3 and f[0][0] in 'pf' and f[0][1] == '_' and f[0][2] in 'smf':
        # 2016 rental car packs (rent_period_rep_s .. rent_fuel_rep_f: "p_s" = time-limited small, "f_f" = meter-rated
        # large): the car the player picked comes in the item text as its VisualItem UniqueId (20954 =
        # pc_rent_gigasmini_p, value "213 0 1" = car type, size 0 small / 1 mid / 2 large, 1 time-limited / 2
        # meter-rated); it gives that car's rental capsule (UseItemClient kind rent_car_capsule, the same id)
        pick = (text or '').split()
        card = t.visuals.get(int(pick[0])) if pick and pick[0].isdigit() else None
        cf = card.value.split() if card else []
        info = t.item_info(t.item_index.get(card.item_id, -1)) if card else None
        if (info and info.kind == 'rent_car_capsule' and len(cf) == 3 and cf[1] == str('smf'.index(f[0][2]))
                and cf[2] == ('1' if f[0][0] == 'p' else '2')):
            return card.item_id, 1
        return None
    if len(f) == 2 and f[0] in ('Normal', 'ST') and f[1].isdigit():
        pick = (text or '').split()
        card = t.visuals.get(int(pick[0])) if pick and pick[0].isdigit() else None
        what = parse_value(card.value) if card and card.category in GIVES_ITEMS else None
        if what and t.item_info(t.item_index[what[0]]).kind == 'lotto':
            return what[0], int(f[1])
    return None


class Gains:
    """What a use gave, sent to the client at the end."""
    def __init__(self):
        self.items, self.vsitems, self.money, self.exp, self.cars = [], [], 0, 0, []

    def send(self, session, p):
        for car in self.cars:
            # 0x62 RewardCar (XiStrCarInfo, u32 flag; client 0x51d7e0): the client adds the car; flag 0 also makes it
            # the current car, else it shows a message. (The first version sent 0x425 + 0x56 BuyCarAck for it: the
            # client crashed, user 2026-10-14.)
            send(session, Frame(0x62, car.encode() + struct.pack('<I', 1)))
        if self.items:
            send(session, mod_list(*self.items))
        if self.vsitems:
            from .items import bonus_update
            from .vshop import vs_mod_list
            send(session, vs_mod_list(*self.vsitems))
            # a drift item won (scratch card, gift box, ..): its bonus flag, as after a purchase (user: an EXP
            # drink from a scratch card did not apply)
            send(session, bonus_update(p))
        if self.money:
            send(session, Frame(0x8a, struct.pack('<iiqq', 1, 1, self.money, p.char.mito) + b'\0\0'))
        if self.exp or self.money:
            for f in stat_frames(p):
                send(session, f)


async def give_item(p, item_id, count, gains):
    """count x an inventory item: onto stacks with room, the rest as new stacks."""
    from .items import stack_for
    t, db = context.data, context.db
    info = t.item_info(t.item_index[item_id])
    while count > 0:
        n = min(count, info.stack_max or 1) if info.type == 5 else 1
        it = stack_for(p, info, 1)
        if it:
            n = min(n, info.stack_max - it.stack)
            it.stack += n
            await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
            gains.items.append((it, CHANGED))
        else:
            it = await new_item(p, info, n)
            gains.items.append((it, NEW))
        count -= n
        from .items import complete_piece
        await complete_piece(p, it)              # a full stack of pieces becomes its item (2008 AddItem)


async def give_drift_item(p, item_id, days, gains, session):
    t, c, db = context.data, p.char, context.db
    uid = t.visual_index.get(item_id)
    vis, row = t.visuals.get(uid), t.vshop.get(uid, {})
    if not vis:
        return
    if row.get('Instant') == '1' and await instant(session, p, vis, gains):
        return
    from .vshop import EXTENDS, INSERT_SQL, PERIOD_SQL
    held = next((o for o in p.vsitems if o.table_idx == uid and o.period and active(o)), None) \
        if days and vis.category in EXTENDS else None
    if held:                                    # a drink already held gets the days (as a purchase: vshop.EXTENDS)
        held.period += days
        await db.execute(PERIOD_SQL, (held.period, db.server_id, c.cid, held.inven_idx))
        gains.vsitems.append((held, CHANGED))
        return
    gid = int((await db.row(NEXT_GID_SQL))[0])
    inven = max([v.inven_idx for v in p.vsitems] + [61]) + 1
    v = VisualItem(gid, item_id, inven, 0, 0, '', days, now(), 0, uid)
    p.vsitems.append(v)
    await db.execute(INSERT_SQL, (db.server_id, c.cid, c.name, gid, item_id, inven, 0, 0, '', days, v.ctime, 0))
    gains.vsitems.append((v, NEW))
    passive_follow(p)


async def give(session, p, rewards, gains):
    from .progress import add_exp
    for kind, item, period, count, *etc in rewards:
        info = context.data.item_info(context.data.item_index[item]) if item in context.data.item_index else None
        if kind == 'NormalItem' and info and info.kind == 'car':
            # a car key in a reward (gift boxes "includes V1 Serpens": key + Etc_Value = the grade) is the car: the
            # key item's value is the car type (UseItemClient column 9: Serpens key 96); the car comes with its key
            # (user, 2026-10-14: the Serpens gift box gave only the key)
            from .cars import create_car
            car = await create_car(session, p, info.value, (etc[0] if etc else 0) or 1)
            if car:
                gains.cars.append(car)
            gains.items.append((await new_item(p, info, 1, car.car_id if car else 0), NEW))   # the key: its CarID
        elif kind == 'NormalItem' and info:
            await give_item(p, item, max(count, 1), gains)
        elif kind == 'SkidItem':
            for _ in range(max(count, 1)):
                await give_drift_item(p, item, period, gains, session)
        elif kind == 'Mito' and count and await add_money(p.char, count):
            gains.money += count
        elif kind == 'Exp' and count:
            await add_exp(p.char, count)
            gains.exp += count
    session.log.note(f'rewards: {rewards}')


async def instant(session, p, vis, gains, text='', rental_days=0):
    """The effect of a drift item that acts by itself (bought "Instant", or used). -> False if it has none.
    text: the item text from the purchase (the card picked for a lottery bundle)."""
    from .setparts import LUBES
    if vis.category in LUBES:   # Restoration Lubes stay in the drift inventory (VShopItem Instant = 1 notwithstanding):
        return False            # used on one set part from the inventory's lube panel (setparts.replenish, 0x1b0)
    if vis.category == MITO_PRIZE:
        amount = int(vis.value) if vis.value.isdigit() else 0
        if amount and await add_money(p.char, amount):
            gains.money += amount
        return True
    if vis.category == PARTS_BOX:              # 2016 packs name their count (i_d_partsbox_25: "i_n_00027 25")
        await give_item(p, *(parse_value(vis.value) or (PARTS_BOX_ITEM, PARTS_BOX_COUNT)), gains)
        return True
    if vis.category in GIVES_ITEMS:
        what = parse_value(vis.value, text)
        if not what:
            return False
        if vis.value in ('p_s', 'p_m', 'p_f', 'f_s', 'f_m', 'f_f'):
            # Capsules are single items; NRANDOM keeps the bought term until redemption.
            it = await new_item(p, context.data.item_info(context.data.item_index[what[0]]), 1, random=rental_days or 1)
            gains.items.append((it, NEW))
        else:
            await give_item(p, *what, gains)
        return True
    return False


async def convert_bundles(session, p):
    """At login, before the character is sent: bundles bought before they were converted at purchase, and drift
    items an earlier version put on a car."""
    from .vshop import EQUIPPABLE, save_state
    t = context.data
    for v in list(p.vsitems):
        vis = t.visuals.get(v.table_idx)
        if vis and vis.category not in EQUIPPABLE and not drive_skill(vis) and vis.category != PASSIVE and v.item_id not in EQUIP_PASSIVE \
                and (v.state or v.car_id):
            v.state, v.car_id = 0, 0            # bought before drift items stopped going on the car
            await save_state(p, v)
            session.log.note(f'drift item {vis.item_id} taken off the car')
        if vis and vis.category in AT_PURCHASE and await instant(session, p, vis, Gains(), v.data):
            await use_up(p, v)
            session.log.note(f'drift item {vis.item_id} turned into inventory items')
    await one_paint_per_car(session, p)
    await restore_drive_skills(session, p)
    from .gifts import return_upgrades
    await return_upgrades(session, p)
    passive_follow(p)


async def one_paint_per_car(session, p):
    """Paint / neon / tint taken off or replaced before they became fixed slots (vshop.FIXED_SLOTS): per car and
    slot, the item on it stays (else the newest goes back on) and the others are destroyed."""
    from .vshop import FIXED_SLOTS, category_of, destroy, save_state
    by_slot = defaultdict(list)
    for v in p.vsitems:
        if v.car_id and category_of(v) in FIXED_SLOTS:
            by_slot[v.car_id, FIXED_SLOTS[category_of(v)]].append(v)
    for (car_id, slot), held in by_slot.items():
        keep = max(held, key=lambda v: (v.state == 1, v.ctime, v.inven_idx))
        if keep.state != 1:
            keep.state = 1
            await save_state(p, keep)
        gone = [v for v in held if v is not keep]
        await destroy(p, *gone)
        if gone:
            session.log.note(f'car {car_id}: {slot} {keep.item_id} kept, {len(gone)} old ones destroyed')


PASSIVE = 41                     # PassiveAssist drift items: "applied automatically just by keeping it"
# PassiveAssist items that go on a car instead (user, 2026-10-14: the DriftBooster equippable, its effect only while
# it is on the car being driven, and it can come off again): vshop.fits lets them on; records.VisualItem
# .assist_slots sends their assist only while VisualItem.on_current_car (Player.apply_paints)
EQUIP_PASSIVE = frozenset({'passive_a_00118', 'passive_a_00247'})      # PassiveAssist(DriftBooster) x 2
DRIVE_SKILL = 58                 # 2016 Turbo / Drift Booster: native Visual Item slot 20 (0x767ca0)


def drive_skill(vis):
    """The 2016 car-bound driving skill; the older PassiveAssist inventory items keep their own rules."""
    from ..version import is_2016
    return bool(vis and vis.category == DRIVE_SKILL and is_2016())


async def restore_drive_skills(session, p):
    """Repair category-58 purchases from before their car binding was implemented, during character load."""
    from .vshop import destroy, put_on, save_state
    car = p.car
    if not car:
        return
    skills = [v for v in p.vsitems if drive_skill(context.data.visuals.get(v.table_idx))
              and v.state in (0, 1) and active(v)]
    unbound = [v for v in skills if not v.car_id]
    if not unbound:
        return
    candidates = unbound + [v for v in skills if v.car_id == car.car_id]
    keep = max(candidates, key=lambda v: (v.ctime, v.inven_idx))
    # The newest purchase replaces older skills; do not disturb skills belonging to another car.
    gone = [v for v in candidates if v is not keep]
    await destroy(p, *gone)
    if not keep.car_id:
        put_on(p, keep, car.car_id)
        await save_state(p, keep)
    session.log.note(f'driving skill {keep.item_id}: restored car {car.car_id}, {len(gone)} older skills removed')


def passive_follow(p):
    """PassiveAssist items stay in the drift item inventory (state 0, no car): the client applies the assist
    slots of a category 40 / 41 item in any state while it has time left (0x72961f; records.assist_slots).
    Putting them on the car (tried first) hid them from the inventory. -> the items that changed."""
    t, out = context.data, []
    for v in p.vsitems:
        vis = t.visuals.get(v.table_idx)
        if vis and vis.category == PASSIVE and v.item_id not in EQUIP_PASSIVE and (v.car_id or v.state):
            v.car_id, v.state = 0, 0
            out.append(v)
    return out


async def use_up(p, v):
    db = context.db
    await db.execute("DELETE FROM SKID_VSITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                     (db.server_id, p.char.cid, v.inven_idx))
    p.vsitems.remove(v)
    v.state = USED


@on(SVC, C2S, 0x4b9)
async def visual_item_use(session, frame):
    from .vshop import vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return error(session, '20017')                  # NotInitializedChar
    inven, car_id = struct.unpack_from('<II', frame.payload)
    v = next((x for x in p.vsitems if x.inven_idx == inven and x.state != 4), None)   # 4: on auction
    vis = context.data.visuals.get(v.table_idx) if v else None
    if not vis:
        return error(session, '20036')                  # ItemUseFail
    db, c, gains = context.db, p.char, Gains()
    if vis.category == INVEN_EXT:
        c.hancoin_inven += 1
        await db.execute("UPDATE SKID_CHARACTER_TB SET HANCOININVEN=%s WHERE SERVERID=%s AND CID=%s",
                         (c.hancoin_inven, db.server_id, c.cid))
    elif vis.category == GARAGE_EXT:
        # garage floors = HANCOINGARAGE + held i_d_garage items + 1: the item becomes a floor for good
        c.hancoin_garage += 1
        await db.execute("UPDATE SKID_CHARACTER_TB SET HANCOINGARAGE=%s WHERE SERVERID=%s AND CID=%s",
                         (c.hancoin_garage, db.server_id, c.cid))
    elif not await instant(session, p, vis, gains):
        # items that work while held (drinks, Turbo Man, Gio, ...): the 2008 server answered and kept them
        session.log.note(f'use visual item {vis.item_id} (category {vis.category}): works while held, kept')
        return send(session, Frame(0x4ba, struct.pack('<II', inven, car_id)))
    await use_up(p, v)
    session.log.note(f'use visual item {vis.item_id} (category {vis.category}, {vis.value!r})')
    send(session, Frame(0x4ba, struct.pack('<II', inven, car_id)))
    send(session, Frame(0x2fa, struct.pack('<II', c.hancoin_inven, c.hancoin_garage)))
    send(session, vs_mod_list((v, USED)))
    gains.send(session, p)


# ---- Item Recycling Kit (inventory item i_n_00114, kind item_recycle, group rw_item_recycle) -------------------
# The drift inventory offers it on an expired drift item (confirmation box 0x2c8e47, 0x5f70a0) and sends
# 0x4bf RecycleVSItem (u32 the drift item's InvenIdx, item +0x14) -> 0x4c0 RecycleVSItemAck (u32 its VisualItem id,
# u32 1 = done; 0x517160: text 11295 "1 Recycling Kit has been used. Expired Drift Item %s has been thrown away."
# with the item's name, 0x769c20; the client keeps the item: the server removes it, 0x4b2 state 2).
# The kit is used, the item thrown away, and one roll of rw_item_recycle given: the same drift item for 1 / 3 / 5 days
# (Reward_Type Recycle, 35 / 12 / 6), the 100k Mito drift item, 5 Mitron Enhancers or a part (*the rest of the flow is
# ours*: the prize goes out like a gift box's, then text 11294 "By recycling %s, you've received %s.").
@on(SVC, C2S, 0x4bf)
async def recycle(session, frame):
    from .items import REMOVED
    from .vshop import vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    inven, = struct.unpack_from('<I', frame.payload)
    t = context.data
    v = next((x for x in p.vsitems if x.inven_idx == inven and x.state != 4), None)
    kit = next((i for i in p.items if t.item_info(i.table_idx).kind == 'item_recycle' and i.stack > 0), None)
    vis = t.visuals.get(v.table_idx) if v else None
    if not vis or active(v) or not kit:
        why = 'no such item' if not vis else 'not expired' if active(v) else 'no Item Recycling Kit'
        session.log.note(f'recycle refused: {why}')
        return send(session, Frame(0x4c0, struct.pack('<II', v.table_idx if v else 0, 0)))
    gains = Gains()
    info = t.item_info(kit.table_idx)
    gains.items.append(await take_one(p, kit))
    await use_up(p, v)
    send(session, vs_mod_list((v, REMOVED)))
    won = roll(info.reward)
    names = []
    for kind, item, period, count, _ in won:
        if kind == 'Recycle':
            await give_drift_item(p, v.item_id, period, gains, session)
            names.append(f'{vis.name} ({period} days)' if period else vis.name)
    await give(session, p, [w for w in won if w[0] != 'Recycle'], gains)
    for kind, item, _, count, _ in won:
        if kind == 'NormalItem' and item in t.item_index:
            names.append(t.item_info(t.item_index[item]).name + (f' x{count}' if count > 1 else ''))
        elif kind == 'SkidItem' and item in t.visual_index:
            names.append(t.visuals[t.visual_index[item]].name)
    session.log.note(f'recycled {vis.item_id}: {won}')
    gains.send(session, p)
    send(session, Frame(0x4c0, struct.pack('<II', v.table_idx, 1)))
    if names:
        from .. import admin
        admin.message(session, f"By recycling {vis.name}, you've received {', '.join(names)}.")


async def open_gift_box(session, p, info):
    """An inventory gift box / package used (0x1a1): its RewardGroup. A level box (kind giftbox_lv: the repeatable
    missions' Small Gift Box, rw_rq_koi) holds one sub-group per level band, each at 100 % with the band's top level as
    Etc_Value (20, 30, .. 1000): only the player's band is rolled (all of them at once otherwise)."""
    gains = Gains()
    group = info.reward
    if info.kind == 'giftbox_lv':
        bands = sorted((r for r in groups().get(group, []) if r[0] == 'RewardGroup'), key=lambda r: r[5])
        band = next((r for r in bands if p.char.level <= r[5]), bands[-1] if bands else None)
        group = band[1] if band else group
    await give(session, p, roll(group), gains)
    return gains


# ---- scratch cards and lucky bags (inventory items of UseItemClient kind "lotto" / "luckybag") ----------
# 0x5aa OpenLotto (u32 InvenIdx of the card) -> 0x5ab OpenLottoAck (u32 id: sent back by 0x5ac, i32 prize
#      item A, i32 prize item B: TableIdx or -1, shown only with a content flag, f32 the dialog's scale).
# 0x5ac ScratchLotto (u32 id) -> 0x5ad ScratchLottoAck: 3 cells as u32 kind[3], u32 id[3], u16 count[3];
#      kind 1 = inventory item (id = TableIdx), 2 = drift item (id = VisualItem id), 0 = empty (client
#      0x618f70). The card is used when scratched; its group (UseItemClient column 3, lotto_Natura: items,
#      Mito, the Natura prizes or a bust) gives one cell each.
# 0x5b4 UseLuckyBag (u32 InvenIdx) -> 0x5b5 UseLuckyBagAck (u32 n, n x (u32 kind, u32 id, u16 count), at
#      most 6, client 0x61a270; its handler takes (n - 1) x 60 + 16 bytes, so the message is padded to that).
#      The window shows an inventory prize (kind 1) only if it finds an item of that TableIdx in the player's own
#      inventory (0x717d40), so the 0x192 with the prizes goes first (user, 2026-10-18: the Big 4 Shopping Bag
#      showed only the Enhancement Formula's icon, the one prize already held). Drift items: by table (0x846cd0).
#      The shop's lucky bags name groups that are not in RewardGroup.xlt (rw_package_car_n / power_n); the
#      Cupid's Gift Boxes have the same contents (rw_valentine_package_car_n / power_n) and are used.
def cell(reward):
    kind, item, _, count = reward[:4]
    t = context.data
    if kind in ('NormalItem', 'n/a') and item in t.item_index:
        return 1, t.item_index[item], max(count, 1)
    if kind == 'SkidItem' and item in t.visual_index:
        return 2, t.visual_index[item], max(count, 1)
    return 0, 0, 0


def group_of(info):
    g = info.reward
    if g not in groups() and g.startswith('rw_package_'):
        g = g.replace('rw_package_', 'rw_valentine_package_', 1)
    return g


async def take_one(p, it):
    from .items import DELETE_SQL, REMOVED
    db = context.db
    it.stack -= 1
    if it.stack:
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        return it, CHANGED
    await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
    p.items.remove(it)
    return it, REMOVED


def held(p, inven, kind):
    it = next((i for i in p.items if i.inven_idx == inven), None)
    info = context.data.item_info(it.table_idx) if it else None
    return (it, info) if info and info.kind == kind else (None, None)


@on(SVC, C2S, 0x5aa)
async def open_lotto(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    inven, = struct.unpack_from('<I', frame.payload)
    it, info = held(p, inven, 'lotto')
    if not it:
        return error(session, '20036')
    session.state['lotto'] = inven
    send(session, Frame(0x5ab, struct.pack('<Iiif', inven, -1, -1, 1.0)))


@on(SVC, C2S, 0x5ac)
async def scratch_lotto(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    inven, = struct.unpack_from('<I', frame.payload)
    it, info = held(p, inven, 'lotto')
    if not it or session.state.pop('lotto', None) != inven:
        return error(session, '20036')
    gains = Gains()
    gains.items.append(await take_one(p, it))
    won = roll(group_of(info))[:3]
    await give(session, p, won, gains)
    cells = [cell(r) for r in won] + [(0, 0, 0)] * (3 - len(won))
    session.log.note(f'scratch card {info.item_id}: {won}')
    send(session, Frame(0x5ad, struct.pack('<3I3I3H', *(c[0] for c in cells), *(c[1] for c in cells), *(c[2] for c in cells))))
    gains.send(session, p)


@on(SVC, C2S, 0x5b4)
async def use_lucky_bag(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    inven, = struct.unpack_from('<I', frame.payload)
    it, info = held(p, inven, 'luckybag')
    if not it:
        return error(session, '20036')
    gains = Gains()
    gains.items.append(await take_one(p, it))
    won = roll(group_of(info))[:6]
    await give(session, p, won, gains)
    cells = [c for c in map(cell, won) if c[0]] or [(0, 0, 0)]
    body = struct.pack('<I', len(cells)) + b''.join(struct.pack('<IIH', *c) for c in cells)
    session.log.note(f'lucky bag {info.item_id}: {won}')
    gains.send(session, p)          # first: the window finds each prize in the inventory (see above)
    send(session, Frame(0x5b5, body.ljust((len(cells) - 1) * 60 + 14, b'\0')))


# ---- name change kit (drift item i_changenick, category 36) ---------------------------------------------
# The kit opens the client's rename dialog (drift inventory 0x6001ba, dialog [ui + 0x3a4]), which sends
# 0x6a RenameChar (u32 mode: 1 = is the name free, 0 = rename; wchar[21] name) -> 0x6b RenameCharAck (u32
# mode, wchar[21] name, u32 result 1 = ok; client 0x51ce70: texts 10605 free / 10604 taken, 10954 renamed
# / 10960 failed). Names as at character creation (lobby.name_free: not used, not reserved). Renaming
# uses the kit and changes CNAME / UCNAME in every table that has CID and CNAME; the other players see the
# new name when they load the player again.
# The kit's texts (10954 / 10955) say a new name cannot be changed for 60 days ([items] rename_days). The
# time of the last rename is kept in SKID_PLAYMODE_TB MODEID 'RENAME' (LASTDATE, UTC). The client's 0x6b
# only knows ok / failed (10604 taken / 10960 failed), so a rename too early gets a Send_Error text instead.
CHANGE_NICK = 36
NAME_TABLES = None
RENAME_MODE = 'RENAME'
RENAME_WAIT_SQL = ("SELECT DATEDIFF(second, LASTDATE, GETUTCDATE()) FROM SKID_PLAYMODE_TB"
                   " WHERE SERVERID=%s AND CID=%s AND MODEID=%s")
RENAME_SAVE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GETUTCDATE(), TRYCNT=TRYCNT+1 WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GETUTCDATE(),GETUTCDATE(),1,0,0,0,0,0,0,0,%s)"""


async def name_tables():
    global NAME_TABLES
    if NAME_TABLES is None:
        rows = await context.db.rows(
            "SELECT t.name, CASE WHEN EXISTS (SELECT 1 FROM sys.columns u WHERE u.object_id = t.object_id AND u.name = 'UCNAME')"
            " THEN 1 ELSE 0 END FROM sys.tables t WHERE EXISTS (SELECT 1 FROM sys.columns c WHERE c.object_id = t.object_id"
            " AND c.name = 'CNAME') AND EXISTS (SELECT 1 FROM sys.columns c WHERE c.object_id = t.object_id AND c.name = 'CID')")
        NAME_TABLES = [(str(n), bool(u)) for n, u in rows]
    return NAME_TABLES


async def rename_wait(c):
    """Seconds left before the character may be renamed again (0 = now)."""
    if context.rename_days <= 0:
        return 0
    row = await context.db.row(RENAME_WAIT_SQL, (context.db.server_id, c.cid, RENAME_MODE))
    return max(0, context.rename_days * 86400 - int(row[0])) if row and row[0] is not None else 0


def wait_text(seconds):
    n, unit = (-(-seconds // 86400), 'day') if seconds > 86400 else (-(-seconds // 3600), 'hour')
    left = f'{n} {unit}' + 's' * (n != 1)
    return (f'A character name cannot be changed again for {context.rename_days} days after a name change. '
            f'You can change it again in {left}.')


def rename_ack(mode, name, ok):
    return Frame(0x6b, struct.pack('<I', mode) + name.encode('utf-16-le')[:40].ljust(42, b'\0') + struct.pack('<I', 1 if ok else 0))


@on(SVC, C2S, 0x6a)
async def rename_char(session, frame):
    from ...wire import read_wstr
    from ..lobby import name_free
    from .vshop import vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 6:
        return
    mode, = struct.unpack_from('<I', frame.payload)
    name = read_wstr(frame.payload, 4, 42).strip()
    t = context.data
    kit = next((v for v in p.vsitems if t.visuals.get(v.table_idx) and t.visuals[v.table_idx].category == CHANGE_NICK), None)
    wait = await rename_wait(p.char) if kit else 0
    if wait:
        session.log.note(f'rename to {name!r}: refused, {wait} s before the next rename')
        if not mode:
            send(session, rename_ack(mode, name, False))
        return error(session, wait_text(wait))
    ok = bool(kit) and 0 < len(name) <= 20 and await name_free(name)
    if mode or not ok:
        session.log.note(f'rename to {name!r}: {"free" if ok else "refused"} (kit: {bool(kit)})')
        return send(session, rename_ack(mode, name, ok))
    db, c = context.db, p.char
    old = c.name
    for table, has_upper in await name_tables():
        await db.execute(f"UPDATE {table} SET CNAME = %s" + (", UCNAME = UPPER(%s)" if has_upper else "")
                         + " WHERE CID = %s", (name, name, c.cid) if has_upper else (name, c.cid))
    c.name = name
    await db.execute(RENAME_SAVE_SQL, (db.server_id, c.cid, RENAME_MODE, db.server_id, c.cid, name, RENAME_MODE, c.member))
    await use_up(p, kit)
    session.log.note(f'renamed {old!r} -> {name!r}')
    send(session, rename_ack(0, name, True))
    send(session, vs_mod_list((kit, USED)))
