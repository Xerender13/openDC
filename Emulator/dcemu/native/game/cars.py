"""Cars: choosing the current car (batch 2 of the native game; buying and upgrading to follow).

0x59 SelectCar (u32 car) -> 0x5a SelectCarAck (XiStrCarInfo, 2011: 49 bytes), 0x2f8 + 0x2f9 (stats),
    0x425 VisualUpdate (u16 serial, u16 age, u32 car, XiStrCarInfo). Cmd_SelectCar 0x5f8510: the car
    must exist (error 20025 NotFoundCar) and not be on auction ("UpgradeCar::IsAuctionOn failed."),
    then XiCsCharInfo::ChangeCurCar and SKID_CHARACTER_TB.CURCAR. The 2008 server sends 0x425 to the
    players who see the car too, and counts "age" up with every visual update of the player
    (2, 3, 4, 5 in the recordings).
"""
import random
import re
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send, stat_frames

CUR_CAR_SQL = "UPDATE SKID_CHARACTER_TB SET CURCAR=%s WHERE SERVERID=%s AND CID=%s"


def visual_update(session, car):
    """0x425 for the player; the others in its game channel get it too (the 2008 server: the players who
    see the car), and ask for its player info again (0x321) since its age changed."""
    from .login import sessions
    age = session.state['visual_age'] = session.state.get('visual_age', 1) + 1
    f = Frame(0x425, struct.pack('<HHI', session.state.get('serial', 0), age & 0xffff, car.car_id) + car.encode())
    for s in list(sessions.values()):
        if s is not session and s.state.get('player') and s.state.get('channel') == session.state.get('channel'):
            s.to_client(f)
    return f


@on(SVC, C2S, 0x59)
async def select_car(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    car_id, = struct.unpack_from('<I', frame.payload)
    car = next((c for c in p.char.cars if c.car_id == car_id), None)
    if not car:
        return error(session, '20025')                  # NotFoundCar
    if car.on_auction:                                  # text 10573 (auction.py)
        return error(session, 'You cannot drive cars that are registered for auction.')
    p.char.cur_car = car_id
    db = context.db
    await db.execute(CUR_CAR_SQL, (car_id, db.server_id, p.char.cid))
    session.log.note(f'select car {car_id} (type {car.car_type})')
    send(session, Frame(0x5a, car.encode()))
    for f in stat_frames(p):
        send(session, f)
    send(session, visual_update(session, car))
    from .driftuse import EQUIP_PASSIVE, passive_follow
    before = {id(v): v.on_current_car for v in p.vsitems if v.item_id in EQUIP_PASSIVE}
    p.apply_paints()
    moved = passive_follow(p)                   # PassiveAssist items stay in the inventory
    # an equipped DriftBooster acts only on its car: its assist goes on / off with the car change
    moved += [v for v in p.vsitems if id(v) in before and before[id(v)] != v.on_current_car and v not in moved]
    if moved:
        from .vshop import vs_mod_list
        send(session, vs_mod_list(*((v, 3) for v in moved)))


# --- buying a car ------------------------------------------------------------------------------------
# 0x55 BuyCar (character name, u32 car type, u32 colour; the 2008 layout in 2011) -> 0x2f8 + 0x2f9,
# 0x192 (the key, and the coupon used), 0x425, 0x56 BuyCarAck (car record + u32 price paid; recorded:
# 1000, 1000000). Cmd_BuyCar 0x605d30 / XiCsCharInfo::CreateCar 0x5d3f00:
#   the car type must be in VehicleList.xlt and sold (else 20042 BuyCarFail). The 2008 server compared
#   Contents.ini Etc.CarOpenStage with Sellable / closestage; in 2011 Sellable is a category: 0 not sold
#   (191 cars), 1 dealership (83), 50 premium / event series (ST, BT, MINI: 34), 101 (4), 10001 / 20001 /
#   30001 / 40001 the four starter cars (Laputa, Drifter, Metro, Birdie). The user: the Drifter must be
#   buyable, so here any Sellable other than 0 can be bought. Price = the default grade's Price (VehicleUpgrade.xlt, grade
#   1), at most the money held (20092); garage space = floors x 8 - cars (GetGarageSpace; floors =
#   HANCOINGARAGE + the "i_d_garage" drift shop items + 1, the 2008 server's SQL); a coupon car (Coupon.xlt) uses up one coupon item
#   from the inventory (20093 without); then CalcMoney "BUYCAR", PC_SKID_CREATECAR (Mitron = capacity), the new car
#   becomes the current one, and its key: the usable item named after the car's file (VehicleList File Name without
#   ".nif", e.g. pc_0073s "Drifter key").
#   Grade: the first grade with a real VehicleUpgrade row (start_grade). The 2008 server made grade 1, but 77 sold 2011
#   cars have empty rows (stats and capacity 0) below their class (VehicleList column 23, the dealership's V tab: record
#   +0x138, tabs at window +0x140 + class * 4, 0x5db6xx): Utopia's only real row is V9 (price 100000; V1 1000). The
#   2016 cars (port2016) have all nine rows and start at V1 (as in the 2016 client), though listed under their class tab.
#   Price = that grade's Price.
CREATE_CAR_SQL = ("SET NOCOUNT ON; DECLARE @carid numeric; EXEC PC_SKID_CREATECAR %s, %s, %s, %s, %s, %s, 0, %s, 0,"
                  " @carid OUTPUT; IF @carid > 0 UPDATE SKID_CHARACTER_TB SET CURCAR=@carid WHERE SERVERID=%s AND CID=%s;"
                  " SELECT ISNULL(@carid, -1)")
CARS_PER_FLOOR = 8
GIVE_CAR_SQL = ("SET NOCOUNT ON; DECLARE @carid numeric; EXEC PC_SKID_CREATECAR %s, %s, %s, %s, %s, %s, 0, %s, 0,"
                " @carid OUTPUT; SELECT ISNULL(@carid, -1)")


def garage_space(p):
    c = p.char
    floors = c.hancoin_garage + sum(1 for v in p.vsitems if v.item_id == 'i_d_garage') + 1
    return floors * CARS_PER_FLOOR - len(c.cars)


def start_grade(car_type):
    """The first grade of the car with a real VehicleUpgrade row (capacity > 0), else 1."""
    t = context.data
    return next((g for g in range(1, MAX_GRADE + 1) if (t.upgrade.get((car_type, g)) or {}).get('capacity')), 1)


DEFAULT_COLOR = 0x01010102     # the dealership's first colour (what the client sends with BuyCar)


async def create_car(session, p, car_type, grade, color=DEFAULT_COLOR):
    """A car given (a gift box): car type at grade, full Mitron (sent with 0x62 RewardCar; not the current car). -> Car or None (no such car,
    no garage space)."""
    from .records import Car
    t, c, db = context.data, p.char, context.db
    grade = max(grade, start_grade(car_type))
    up = t.upgrade.get((car_type, grade)) or t.upgrade.get((car_type, 1))
    if car_type not in t.vehicles or not up:
        session.log.note(f'give car {car_type} V{grade}: no such car')
        return None
    if garage_space(p) <= 0:
        session.log.note(f'give car {car_type} V{grade}: no garage space')
        error(session, 'Not Enough Garage Space')
        return None
    capacity = float(up['capacity'])
    r = await db.row(GIVE_CAR_SQL, (db.server_id, c.cid, c.name, car_type, color, grade, capacity))
    car_id = int(r[0]) if r else -1
    if car_id <= 0:
        return None
    car = Car(car_id, car_type, color, grade, 0, capacity, 0.0, 0, capacity, float(up['efficiency']))
    c.cars.append(car)
    session.log.note(f'give car {car_type} ({t.vehicles[car_type].get("UI Name")}) V{grade}: car {car_id}')
    return car


@on(SVC, C2S, 0x55)
async def buy_car(session, frame):
    from .items import CHANGED, REMOVED, STACK_SQL, DELETE_SQL, add_money, mod_list, new_item
    from .records import Car
    p = session.state.get('player')
    if not p or len(frame.payload) < 0x32:
        return
    car_type, color = struct.unpack_from('<II', frame.payload, 0x2a)
    t, c, db = context.data, p.char, context.db
    v = t.vehicles.get(car_type)
    grade = start_grade(car_type)
    up = t.upgrade.get((car_type, grade))
    if not v or not up:
        return error(session, '20042')                  # BuyCarFail
    if not int(v.get('Sellable') or 0):
        session.log.note(f'buy car {car_type}: not sold (Sellable 0)')
        return error(session, '20042')
    price = up['price']
    if price > c.mito:
        return error(session, '20092')
    floors = c.hancoin_garage + sum(1 for v in p.vsitems if v.item_id == 'i_d_garage') + 1
    if floors * CARS_PER_FLOOR - len(c.cars) <= 0:
        return error(session, 'Not Enough Garage Space')
    changed = []
    coupon_id = t.car_coupons.get(car_type)
    if coupon_id:
        coupon = next((i for i in p.items if i.item_id == coupon_id and i.stack > 0), None)
        if not coupon:
            return error(session, '20093')
        coupon.stack -= 1
        if coupon.stack:
            await db.execute(STACK_SQL, (coupon.stack, db.server_id, c.cid, coupon.inven_idx))
            changed.append((coupon, CHANGED))
        else:
            await db.execute(DELETE_SQL, (db.server_id, c.cid, coupon.inven_idx))
            p.items.remove(coupon)
            changed.append((coupon, REMOVED))
    if not await add_money(c, -price):
        return error(session, '20042')
    capacity = float(up['capacity'])
    car_id = int((await db.row(CREATE_CAR_SQL, (db.server_id, c.cid, c.name, car_type, color, grade, capacity,
                                                db.server_id, c.cid)))[0])
    if car_id <= 0:
        return error(session, '20042')
    car = Car(car_id, car_type, color, grade, 0, capacity, 0.0, 0, capacity, float(up['efficiency']))
    c.cars.append(car)
    c.cur_car = car_id
    key = t.item_info(t.item_index.get(v.get('File Name', '').rsplit('.', 1)[0], -1))
    if key:
        changed.append((await new_item(p, key, 1, car_id), 1))
    session.log.note(f'buy car {car_type} ({v.get("UI Name")}) V{grade} for {price}: car {car_id}')
    for f in stat_frames(p):
        send(session, f)
    if changed:
        send(session, mod_list(*changed))
    send(session, visual_update(session, car))
    send(session, Frame(0x56, car.encode() + struct.pack('<I', price)))


# --- upgrading a car ----------------------------------------------------------------------------------
# 0x5b UpgradeCar (u32 car, i64 the client's G Coin, u8 use mileage, u32 (0 so far)) -> 0x5c UpgradeCarAck (u32 car,
# u32 new grade, u32 G Coin spent @0xa, u32 mileage spent @0xe: the client takes both off its own counts; 2011 + i32
# @0x12 that it ADDS to its Mito; handler 0x510f20), 0x2f8 + 0x2f9, 0x425.
# The client sends it from the upgrade window (0x79b9f9) and when a permanent V upgrade is bought in the drift shop
# (0x680ea0, VShop category 14: no drift item is made). As the 2008 server (Cmd_UpgradeCar 0x601950, XiCsCharInfo::
# UpgradeCar 0x5cb770): each grade is sold as the drift shop's CARREMODELING item (i_d_u_01 V2 .. i_d_u_08 V9, VShopItem
# "$Price 0D" in G Coin (CC), or its mileage price) and paid like a purchase (vshop.charge, SKID_UNALISCOIN_TB). Until
# 2026-10-15 it was paid in Mito by VehicleUpgrade.xlt "UpgradeMito" (user: a bug, V upgrades cost CC). The 2011
# VehicleUpgrade.xlt row of the grade gives the level ("Req Level"), capacity and efficiency; its condition
# ("UpgradeCon") and part options ("OptionID") are not applied. SKID_CAR_TB NUPGRADE and UPn_DATE (the 2008 SQL).
UPGRADE_SQL = "UPDATE SKID_CAR_TB SET NUPGRADE=%s, UP{n}_DATE=GetDate() WHERE SERVERID=%s AND CID=%s AND CARID=%s"
MAX_GRADE = 9
CAR_UPGRADE = 14            # VisualItem category of the permanent V upgrades (VShopItem CARREMODELING)


def upgrade_row(grade):
    """The drift shop row that sells this grade (VShopItem Sub 8001 = V2 .. 8008 = V9, category 14)."""
    from .player import upgrade_grade
    t = context.data
    return next((r for idx, r in t.vshop.items() if t.visuals.get(idx) and t.visuals[idx].category == CAR_UPGRADE
                 and upgrade_grade(idx) == grade), None)


@on(SVC, C2S, 0x5b)
async def upgrade_car(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    car_id, = struct.unpack_from('<I', frame.payload)
    use_mileage = len(frame.payload) > 12 and frame.payload[12] == 1
    c, t = p.char, context.data
    car = next((x for x in c.cars if x.car_id == car_id), None)
    if not car or car.on_auction:
        return error(session, '20025')                  # NotFoundCar (on auction: text 10596)
    up = t.upgrade.get((car.car_type, car.grade + 1))
    row = upgrade_row(car.grade + 1)
    if car.grade >= MAX_GRADE or not up or not row or c.level < up['req_level']:
        return error(session, '20044')                  # UpgradeCarFail
    from .vshop import charge
    charged = await charge(session, p, row, 4, use_mileage)
    if not charged:
        return
    paid, _ = charged
    from .gifts import record
    from .items import NEXT_GID_SQL
    await record(p, int((await context.db.row(NEXT_GID_SQL))[0]), row.get('ItemName'), paid, 0)
    await raise_grade(session, p, car, up, paid['mito'], paid['coin'], paid['mileage'],
                      why=f'for {paid["coin"]} CC / {paid["mileage"]} mileage / {paid["mito"]} Mito ({row.get("ItemName")})')


async def raise_grade(session, p, car, up, cost=0, coin=0, mileage=0, why=''):
    """The car goes up one grade (up: its VehicleUpgrade row): 0x5c (the client sets the grade and shows text 10501
    "The vehicle has been upgraded to the next level."; it takes coin / mileage / cost (Mito) off its own counts),
    stats, look."""
    c, db = p.char, context.db
    car.grade += 1
    car.capacity, car.efficiency = float(up['capacity']), float(up['efficiency'])
    await db.execute(UPGRADE_SQL.format(n=car.grade), (car.grade, db.server_id, c.cid, car.car_id))
    session.log.note(f'upgrade car {car.car_id} to grade {car.grade} {why}')
    send(session, Frame(0x5c, struct.pack('<IIIIi', car.car_id, car.grade, coin, mileage, -cost)))
    await drop_spent_upgrades(session, p, car)
    for f in stat_frames(p):
        send(session, f)
    send(session, visual_update(session, car))


# --- upgrade items -------------------------------------------------------------------------------------
# Mito car upgrade items (UseItemClient kind MitoCarUpgrade, i_d_mu_v2_2per .. i_d_mu_v9_10per: "V3 Car Upgrade(4%)",
# value column = the chance in %). The client (0x5f9990, before it sends 0x1a1 ItemUse) checks the current car: its
# own grade (a timed V upgrade on it does not count) + 1 = the item's grade (its table of names 0x8e0d48: i_d_mu_01_n
# .. 08_n, then v2..v9 per chance; text 10521 otherwise), the level of that grade (VehicleUpgrade "Req Level", text
# 10297), not on auction (10596). Its 0x1a2 handler does nothing for the kind (0x41), so the server tells the result:
# success = the upgrade (0x5c, as the upgrade window), failure = a message. The item is used up either way. No Mito.
# Permanent V upgrades from the drift shop (VShopItem category 14 CARREMODELING, i_d_u_01..08): buying one makes the
# client send 0x5b for the selected car (0x680ea0), so such an item only exists as a gift: applied when the gift is
# taken (gifts.py, the car chosen there), the same checks.
def item_grade(item_id):
    """The grade a Mito upgrade item gives (i_d_mu_v3_4per -> 3, i_d_mu_02_n -> 3), else 0."""
    m = re.match(r'i_d_mu_(?:v(\d)_\d+per|0(\d)_n)$', item_id or '')
    return (int(m[1]) if m[1] else int(m[2]) + 1) if m else 0


def grade_check(session, p, car, grade):
    """The client's checks for an upgrade item of this grade on the car -> its VehicleUpgrade row, or None (told)."""
    if not car or car.grade + 1 != grade or grade > MAX_GRADE:
        session.log.note(f'upgrade item V{grade}: car {car.car_id if car else None} is V{car.grade if car else "-"}')
        error(session, f'This item upgrades a V{grade - 1} car to V{grade}: modification is not allowed for this '
                       'vehicle.')
        return None
    if car.on_auction:
        error(session, 'You cannot modify cars registered for auction.')
        return None
    up = context.data.upgrade.get((car.car_type, grade))
    if not up or p.char.level < up['req_level']:
        error(session, 'Your current level is not high enough.' if up else '20044')
        return None
    return up


async def roll_upgrade_item(session, p, car, up, info):
    """After the item was used up: success with its chance (value column, %)."""
    chance = max(0, min(info.value, 100))
    if random.random() * 100 < chance:
        await raise_grade(session, p, car, up, why=f'with {info.item_id} ({chance}%)')
    else:
        session.log.note(f'upgrade item {info.item_id} ({chance}%) on car {car.car_id}: failed')
        from .. import admin
        admin.message(session, f'The upgrade to V{car.grade + 1} failed ({chance}% chance). The item was used up.')


async def drop_spent_upgrades(session, p, car):
    """A real upgrade reached the grade of a timed V upgrade item on the car: that item is destroyed (user, 2026-10-14)."""
    from .player import TEMP_UPGRADE, upgrade_grade
    from .vshop import REMOVED, destroy, vs_mod_list
    t = context.data
    spent = [v for v in p.vsitems if v.car_id == car.car_id and t.visuals.get(v.table_idx)
             and t.visuals[v.table_idx].category == TEMP_UPGRADE and upgrade_grade(v.table_idx) <= car.grade]
    if spent:
        await destroy(p, *spent)
        p.apply_paints()
        session.log.note(f'car {car.car_id} upgraded to V{car.grade}: {[v.item_id for v in spent]} destroyed')
        send(session, vs_mod_list(*((v, REMOVED) for v in spent)))
        send(session, Frame(0x63, struct.pack('<II', car.car_id, car.shown_grade())))
