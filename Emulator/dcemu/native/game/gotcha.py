"""The Gotcha machine (capsule boxes; main menu button "Gotcha", client dialog [ui + 0x320], code 0x66b000..0x670900).

The client shows it with Etc.ShowMainButtonGotcha = 1 and offers the seasons up to Etc.GotchaSeason (its own
GlobalContent.xlt GotchaViewSeason = 13 says "set Contents.ini to the same"). Four machines: car capsules for G Coin /
Mito, parts capsules for G Coin / Mito (the US client's GlobalContent PartsGotchaClose = 1 closes the parts machines).
Prices are the client's GlobalContent GotchaSeasonCash%02d / GotchaSeasonMito%02d (car), Gacha_Price_PartsCash /
PartsMito (parts); the client checks the money / G Coin itself before it asks.

0xdac Gotcha (2011, 24 bytes; sender 0x805fe0 from 0x66dcd2): u32 currency (0 Mito, 1 G Coin), u32 price (as the
    client computed it), u32 machine (0 car, 1 parts), u32 the client's G Coin, u32 0, u32 season (1..16).
    The client has no answer message of its own (no 0xdad): the server sends what the capsule gave, as for a gift
    box (0x192 / 0x4b2, 0x62 a car, 0x8a Mito), the money / G Coin (0x8a, 0x579), and the prize for the window:
    0x89 NotifyEvent type 23 / 24 (prize_event). The window plays the capsule animation by itself.
Rewards: RewardGroup.xlt rw_gacha_{car|parts}_{mito|cash}_{season:02} (e.g. rw_gacha_car_mito_09: Winner car parts
    A-D or key parts; seasons 3 and 4 have no groups: rw_gacha_item_mito / _cash then), rolled as gift boxes
    (driftuse.roll / give). The car parts (i_n_gacha_A.., i_n_*_k_v5) are for combining into the car (not native).
emulator.ini [gotcha]: enabled, season (the newest season offered), prices.
2016 client (its GlobalContent): GotchaViewSeason 60 (season groups up to rw_gacha_*_62; Etc.GotchaSeason is 6 bits
    wide there), Gacha_Price_PartsMito 25000, and GachaUpdate2015 = 1: the window's car price (0x6bf872 / 0x6bf940)
    is then GachaUpdate2015Cash 300 / GachaUpdate2015Mito 50000 for every season instead of GotchaSeason*%02d.
    That car machine has no season: the client sends season 0 (seen 2026-10-20; refused before, "Failed to use
    item"). RewardGroup rw_cash_gacha_2015 / rw_mito_gacha_2015 are its capsules (G Coin / Mito): seven slot cars
    (Dominator, Hykan, Prometheus, GRAVITY, PLUCK, Honour, Pandora: an ST or BT V1 car gift box) or 10 Capsule Points
    (i_n_gacha_point). The parts machine keeps its seasons.
    The 2016 prize window: NotifyEvent type 23 passes u32 @0xa with the item (0x5304ec -> 0x6c2590): the count; 0
    there showed no reward icon (user, 2026-10-20). Not done: the Battle Zone "OB Gacha" (BattleZone.ObserveGacha, Etc.EventFreeOBGacha;
    0x834 / 0x836 / 0x837 -> 0x835 ObsGachaInit .. 0x83a ObsGachaResult).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send

# GlobalContent.xlt GotchaSeasonCash01..16 (US client); Mito 10000 for every season and the parts machines
SEASON_COIN = (300, 300, 300, 300, 290, 490, 390, 190, 540, 300, 300, 300, 300, 300, 300, 300)
PARTS_COIN, MITO_PRICE = 300, 10000
UPDATE_2015_COIN, UPDATE_2015_MITO, PARTS_MITO_2016 = 300, 50000, 25000     # 2016 GlobalContent (see above)
GACHA_2015 = {True: 'rw_cash_gacha_2015', False: 'rw_mito_gacha_2015'}     # G Coin / Mito
COIN_TAKE_SQL = """SET NOCOUNT ON;
UPDATE SKID_UNALISCOIN_TB SET COIN=COIN-%s, LASTACTION='GCH', LASTCNAME=%s, LASTDATE=GETDATE() WHERE MEMBERID=%s AND COIN>=%s;
SELECT @@ROWCOUNT, (SELECT COIN FROM SKID_UNALISCOIN_TB WHERE MEMBERID=%s)"""


def price(coin, machine, season):
    from ..version import is_2016
    if not coin:
        if context.gotcha_mito_price:
            return context.gotcha_mito_price
        if is_2016():
            return PARTS_MITO_2016 if machine == 1 else UPDATE_2015_MITO
        return MITO_PRICE
    if context.gotcha_coin_price:
        return context.gotcha_coin_price
    if is_2016() and machine != 1:
        return UPDATE_2015_COIN
    if machine == 1:
        return PARTS_COIN
    return SEASON_COIN[season - 1] if 1 <= season <= len(SEASON_COIN) else SEASON_COIN[0]


def group_for(coin, machine, season):
    from .driftuse import groups
    from ..version import is_2016
    if is_2016() and machine != 1 and GACHA_2015[bool(coin)] in groups():
        return GACHA_2015[bool(coin)]
    money = 'cash' if coin else 'mito'
    g = f"rw_gacha_{'parts' if machine == 1 else 'car'}_{money}_{season:02}"
    return g if g in groups() else f'rw_gacha_item_{money}'


@on(SVC, C2S, 0xdac)
async def gotcha(session, frame):
    from .driftuse import Gains, give, roll
    from .items import add_money
    p = session.state.get('player')
    if not p or len(frame.payload) < 24:
        return
    currency, asked, machine, client_coin, _, season = struct.unpack_from('<6I', frame.payload)
    coin = currency == 1
    session.log.note(f'gotcha: {"G Coin" if coin else "Mito"}, machine {"parts" if machine else "car"}, season {season}, '
                     f'client price {asked}')
    from ..version import is_2016
    lowest = 0 if is_2016() and machine != 1 else 1     # the 2016 car machine sends season 0 (GachaUpdate2015)
    if not context.gotcha_enabled or not lowest <= season <= max(context.gotcha_season, 1):
        return error(session, '20036')
    cost, group = price(coin, machine, season), group_for(coin, machine, season)
    db, c = context.db, p.char
    if coin:
        r = await db.row(COIN_TAKE_SQL, (cost, c.name, c.member, cost, c.member))
        if not r or not r[0]:
            return error(session, '20094')              # not enough G Coin
        balance = int(r[1] or 0)
    elif cost > c.mito or not await add_money(c, -cost):
        return error(session, '20092')                  # Insufficient funds
    won = roll(group)
    gains = Gains()
    await give(session, p, won, gains)
    session.log.note(f'gotcha {group} for {cost} {"G Coin" if coin else "Mito"}: {won}')
    if not coin:
        send(session, Frame(0x8a, struct.pack('<iiqq', 1, 1, -cost, c.mito) + b'\0\0'))
    gains.send(session, p)
    if coin:
        send(session, Frame(0x579, struct.pack('<Iq', balance, c.mileage)))
    prize = prize_event(won)
    if prize:
        send(session, prize)


def parts_for(info):
    """The vehicle parts a Gotcha key needs: its UseItemClient column 4 group (rw_winner_compound_09: i_n_gacha_A..D,
    one each); keys of the first seasons name groups that are not in the table (rw_shadow_compound): that car's own
    parts A-D then (i_n_shadow_A..D, i_n_hunter_A..D; item texts: "After collecting Vehicle Parts from A to D, you
    can use the Key Parts to receive a gift box with a V5 level vehicle.")."""
    from .driftuse import groups
    t = context.data
    rows = groups().get(info.extra, [])
    if rows:
        return [(r[1], max(r[3], 1)) for r in rows if r[0] == 'NormalItem']
    name = info.extra.removeprefix('rw_').split('_compound')[0]
    parts = [(f'i_n_{name}_{x}', 1) for x in 'ABCD']
    return parts if all(p in t.item_index for p, _ in parts) else [(f'i_n_gacha_{x}', 1) for x in 'ABCD']


async def combine(session, p, key, info):
    """0x1a1 ItemUse on a Gotcha key parts item (UseItemClient kind gacha_key): with one of each vehicle part it needs
    held, the parts and the key are used up and the key's gift box (column 3, e.g. i_n_winner_box_v1) is given; that box
    opens into the car (gift boxes: driftuse). -> 0x1a2 ItemUseAck, 0x192, the box's prize window (0x89 type 23)."""
    from .driftuse import Gains, give_item, take_one
    from .items import USE_KINDS, info_of
    t = context.data
    need = parts_for(info)
    held = {}
    for item_id, n in need:
        pile = next((i for i in p.items if i.item_id == item_id and not i.car_id and (i.state & 0xffff) == 0
                     and i.stack >= n), None)
        if not pile:
            session.log.note(f'gotcha combine {info.item_id}: {item_id} missing (needs {need})')
            return error(session, '20036')              # ItemUseFail
        held[item_id] = pile
    box = info.reward
    if box not in t.item_index:
        session.log.note(f'gotcha combine {info.item_id}: no gift box {box!r}')
        return error(session, '20036')
    gains = Gains()
    for item_id, n in need:
        for _ in range(n):
            gains.items.append(await take_one(p, held[item_id]))
    gains.items.append(await take_one(p, key))
    await give_item(p, box, 1, gains)
    session.log.note(f'gotcha combine {info.item_id}: {[i for i, _ in need]} + key -> {box}')
    send(session, Frame(0x1a2, struct.pack('<II4I', key.inven_idx, 1, USE_KINDS.get(info.kind, 0), 0, 0, 0)))
    gains.send(session, p)
    send(session, Frame(0x89, struct.pack('<IIII', 23, t.item_index[box], 0, 0)))


def prize_event(won):
    """The prize window ("Congratulations!", [ui + 0x324], filled by 0x670b70): 0x89 NotifyEvent type 23 (u32 item
    TableIdx @6) or type 24 (u32 drift item id @6, u32 @0xe: the days) (client 0x51c40f / 0x51c447). Without it the
    window opened empty (user screenshot, 2026-10-14)."""
    from ..version import is_2016
    t = context.data
    for kind, item, period, count, *_ in won:
        if kind == 'NormalItem' and item in t.item_index:
            return Frame(0x89, struct.pack('<IIII', 23, t.item_index[item], max(count, 1) if is_2016() else 0, 0))
        if kind == 'SkidItem' and item in t.visual_index:
            return Frame(0x89, struct.pack('<IIII', 24, t.visual_index[item], 0, period))
    return None
