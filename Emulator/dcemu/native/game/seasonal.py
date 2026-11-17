"""Season events, the server's parts (native/events.py switches them; research: docs/neo_work/SEASON_EVENTS.md and
EMULATOR_NOTES session 48). The content flags of a running event already change the clients (Santa head and station
NPCs, Harvest station NPCs, Halloween Mita 500 skin, Valentine NPC art, ...); this module adds what needs the server.

**Event drops** (all events, ours): while an event runs, every traffic / combo pick-up first rolls the event's items
(emulator.ini [events] <event>.drops = item:percent, ... ; DROPS has the defaults). The clients do not list the event
shop rows (VShopItem SellStage 0 / 99), so the drops are how the materials reach the players with vanilla clients.

**Easter egg baskets** (UseItemClient kinds recipe_item 0x3c, chocolet_item 0x3d, chocolet_gift_item 0x3e; the 2011
client's item switch 0x72a480 has no case for them: the default 0x72ba72, so the server does the work):
  - using a recipe (permanent, "obtained as a permanent item": not used up) takes 1 paint and its eggs (the tooltips:
    Basic 10 Normal; Fancy 3 Normal + 7 Silver; Upscale 3 Normal + 3 Silver + 4 Golden; the 2015 N / S / U recipes the
    same with N / S / U eggs) and gives the basket rolled from rw_<recipe>_careful (Colorful Paint) or _twinkling
    (Sparkle Paint: better odds); Colorful is used first. The result rows' Etc_Value 1..4 (2015: 1..24) is the basket
    quality, "색칠성공 1 / 4 / 6 / 10개" (eggs painted successfully) in the rows' descriptions: kept in the basket's
    NRANDOM. Answer: 0x1a2 with count 0 (nothing used up) *(guess: not confirmed in game)*, 0x192, prize window 0x89/23.
  - eating a basket (2011 chocolet_item, both builds' chocolet_gift_item) gives the EXP of its group's level band
    (rw_exp_choco_giftbox(2): one sub-group per band, Etc_Value = the band's top level, "색칠 1개 성공 ... N~M레벨
    경험치 보상" = per painted egg) x the painted eggs. 2016 Easter baskets are plain gift boxes (rw_eastegg_2013_*).
    Gifting a basket to a friend is not implemented (no message found).

**Harvest** (Etc.EventGoodHarvest; RewardGroup descriptions "가을대풍작이벤트 ... 퀵서비스보상" = autumn harvest event,
delivery (quick service) reward):
  - a finished delivery job gives the food gift box of the job's city (event_giftbox_moon / koi / cras / oros,
    rw_event_giftbox_<city>: vegetables, fish, fruit, meat);
  - the Box Recipe (event_box_recipe 0x43, permanent) makes a Distribution Box from 1 box (Ice Box first: better odds,
    rw_box_recipe_ice; else Normal Box, rw_box_recipe_normal) + 1 of each fresh food *(guess: the amounts are not in
    the tables)*;
  - a delivery job finished while holding a Distribution Box delivers one ("Deliver it to restaurants to get receipt"):
    restaurant_evaluation (the chef's rating: 1 / 2 / 3 receipts) x the box's size (UseItemClient value 1 / 2 / 4);
  - receipts (event_autumn) are exchanged by using them: HARVEST_EXCHANGE (ours: the Harvest Distribution Center's
    rates are not in the tables) - the Fall Harvest Event car boxes Goat V1 / Fervor V2.
**Christmas tree** (2016): S>C 0xcf2 XmasTreeEventBuff (6 bytes, u32 stage @2; handler 0x52cdd0: the tree manager
  [net+0x40c]+0xc = stage (0x7191d0), the HUD buff icon [ui+0x238 + (stage-1)*4] while stage > 0 (0x656630 / 0x65765b),
  5 icons) sent at login while Christmas runs, stage = [events] christmas.tree (0 = not sent, the default: what the
  buff gave on the original server is not in the client).
**Valentine chocolate** (2016): S>C 0xfbb ValentainChocolateCheat (6 bytes, u32 on @2; handler 0x542cf0 sets
  Etc.EventValentainChocolate in the client's own flag block, 0x542d06..0x542d42) to the online 2016 players when
  gmevent switches valentine, so it takes effect without a relog.
"""
import random
import struct

from ...wire import Frame
from .. import context, events
from .login import error, send

# event -> default drops (item id, percent per pick-up); items missing from the build's tables are skipped
DROPS = {
    'christmas': (('i_n_00088', 2.0),),                                         # Santa's Gift Box
    'newyear': (('i_n_package_power_n', 0.5), ('i_n_package_car_n', 0.2)),     # Lucky Bags
    'valentine': (('2013_valen_s_box', 0.5),),                                  # 2016: chocolate material box (S)
    'easter': (('black_chocolete', 4.0), ('white_chocolete', 2.0), ('pink_chocolete', 1.0),
               ('careful_wrapping', 1.5), ('twinkling_wrapping', 0.4),
               ('g_choco_recipe', 0.3), ('h_choco_recipe', 0.15), ('s_choco_recipe', 0.1)),
    'summer': (('giftbox_suika', 1.5),),                                        # Watermelon GiftBox
    'harvest': (('event_normalbox_n', 2.0), ('event_icebox_n', 0.5), ('event_box_recipe_n', 0.2)),
}
# recipe item -> (materials {item: count}, reward group base); paints are added for the egg recipes
PAINTS = (('careful_wrapping', '_careful'), ('twinkling_wrapping', '_twinkling'))
EGG_RECIPES = {
    'g_choco_recipe': ({'black_chocolete': 10}, 'rw_g_recipe'),
    'h_choco_recipe': ({'black_chocolete': 3, 'white_chocolete': 7}, 'rw_h_recipe'),
    's_choco_recipe': ({'black_chocolete': 3, 'white_chocolete': 3, 'pink_chocolete': 4}, 'rw_s_recipe'),
    'i_n_choco_nrecipe_2012': ({'i_n_milk_choco_2012': 10}, 'rw_n_recipe_2012'),
    'i_n_choco_srecipe_2012': ({'i_n_milk_choco_2012': 3, 'i_n_shell_choco_2012': 7}, 'rw_s_recipe_2012'),
    'i_n_choco_urecipe_2012': ({'i_n_milk_choco_2012': 3, 'i_n_shell_choco_2012': 3,
                                'i_n_ball_choco_2012': 4}, 'rw_u_recipe_2012'),
}
PAINTED = (1, 4, 6, 10)                 # basket quality 1..4 (Etc_Value, 2015 rows 1..24 cycle) -> eggs painted
FALLBACK_ODDS = {'_careful': (60, 25, 10, 5), '_twinkling': (35, 30, 20, 15)}   # the 2016 rows (2011 rows have none)
BOXES = (('event_icebox_n', 'rw_box_recipe_ice'), ('event_normalbox_n', 'rw_box_recipe_normal'))
FOODS = ('event_vegetable_n', 'event_fish_n', 'event_fruit_n', 'event_meat_n')
CITY_FOOD_BOX = {1: 'event_giftbox_moon', 2: 'event_giftbox_koi', 3: 'event_giftbox_cras', 4: 'event_giftbox_oros'}
RECEIPT = 'event_receipt_01'
HARVEST_EXCHANGE = ((30, 'event_fervor_box_v2'), (10, 'event_goat_box_v1'))     # receipts -> box (ours)


def _info(item_id):
    t = context.data
    return t.item_info(t.item_index[item_id]) if item_id in t.item_index else None


def drops_of(name):
    """[(item id, percent)] of an event: emulator.ini <event>.drops or DROPS."""
    text = context.events.get(name + '.drops')
    if text is None:
        return list(DROPS.get(name, ()))
    out = []
    for part in text.replace(';', ',').split(','):
        if ':' in part:
            item, pct = part.split(':', 1)
            try:
                out.append((item.strip(), float(pct)))
            except ValueError:
                pass
    return out


def event_drop(p, rng=random):
    """The item a pick-up gives from the running events' drops, or None."""
    for name in events.EVENTS:
        if not events.is_on(name):
            continue
        for item, pct in drops_of(name):
            info = _info(item)
            if info and pct > 0 and rng.uniform(0, 100) < pct:
                return info
    return None


def held(p, item_id):
    return sum(i.stack for i in p.items if i.item_id == item_id and not i.car_id and (i.state & 0xffff) != 4)


def _weighted_row(group, odds=None, rng=random):
    """One NormalItem row of a result group (nested groups followed) -> (item id, Etc_Value) or None. Rows without a
    probability (the 2011 table) take `odds` by position."""
    from .driftuse import groups
    rows = groups().get(group, [])
    for kind, item, *_ in rows:
        if kind == 'RewardGroup':
            return _weighted_row(item, odds, rng)
    rows = [r for r in rows if r[0] == 'NormalItem']
    if not rows:
        return None
    weights = [r[4] for r in rows]
    if not any(w > 0 for w in weights):
        weights = [odds[i] if odds and i < len(odds) else 1 for i in range(len(rows))]
    r = rng.choices(rows, weights=weights)[0]
    return r[1], r[5]


def painted_of(etc):
    return PAINTED[(etc - 1) % 4] if etc > 0 else 1


async def _take(p, materials):
    from .alchemy import take_count
    changes = []
    for item, n in materials.items():
        changes += await take_count(p, item, n)
    return changes


def _need_text(materials):
    return ', '.join(f'{n} {(_info(i).name if _info(i) else i)}' for i, n in materials.items())


async def craft(session, p, it, info):
    """0x1a1 on a recipe_item / event_box_recipe item -> True when this module answered it."""
    from .combo import free_slots
    from .items import NEW, USE_KINDS, mod_list, new_item
    if info.item_id in EGG_RECIPES:
        eggs, base = EGG_RECIPES[info.item_id]
        paint = next(((i, sfx) for i, sfx in PAINTS if held(p, i) >= 1), None)
        materials = dict(eggs)
        if paint:
            materials[paint[0]] = 1
        group, odds = (base + paint[1], FALLBACK_ODDS[paint[1]]) if paint else (None, None)
    elif info.kind == 'event_box_recipe':
        box = next(((i, g) for i, g in BOXES if held(p, i) >= 1), None)
        materials = {f: 1 for f in FOODS}
        if box:
            materials[box[0]] = 1
        group, odds, paint = (box[1] if box else None), None, box
    else:
        return False
    missing = {i: n for i, n in materials.items() if held(p, i) < n}
    if not paint or missing:
        need = dict(materials)
        if not paint:
            need = ({'careful_wrapping': 1} if info.item_id in EGG_RECIPES else {'event_normalbox_n': 1}) | need
        session.log.note(f'craft {info.item_id}: missing {missing or "paint / box"}')
        error(session, f'You need {_need_text(need)}.')
        return True
    got = _weighted_row(group, odds)
    result = _info(got[0]) if got else None
    if not result or free_slots(p) < 1:
        error(session, '20036' if not result else 'Your inventory is full.')
        return True
    changes = await _take(p, materials)
    quality = painted_of(got[1]) if info.item_id in EGG_RECIPES else 0
    made = await new_item(p, result, 1, random=quality)
    send(session, Frame(0x1a2, struct.pack('<II4I', it.inven_idx, 0, USE_KINDS.get(info.kind, 0), 0, 0, 0)))
    send(session, mod_list(*changes, (made, NEW)))
    send(session, Frame(0x89, struct.pack('<IIII', 23, result.table_idx, 1, 0)))
    session.log.note(f'craft {info.item_id}: {materials} -> {result.item_id}'
                     + (f' ({quality} eggs painted)' if quality else ''))
    return True


async def eat_basket(session, p, it, info, gains):
    """A used Easter basket (chocolet_item / chocolet_gift_item, already taken out): EXP of the player's level band x
    the eggs painted (NRANDOM; 1 when unknown)."""
    from .driftuse import give, groups
    bands = sorted((r for r in groups().get(info.reward, []) if r[0] == 'RewardGroup'), key=lambda r: r[5])
    band = next((r for r in bands if p.char.level <= r[5]), bands[-1] if bands else None)
    if not band:
        return
    per_egg = sum(r[3] for r in groups().get(band[1], []) if r[0] == 'Exp')
    painted = it.random if 0 < it.random <= 10 else 1
    if per_egg:
        await give(session, p, [('Exp', '', 0, per_egg * painted, 100, 0)], gains)
    session.log.note(f'basket {info.item_id}: {per_egg} x {painted} eggs EXP (band {band[1]})')


async def harvest_delivery(session, p, row):
    """A finished delivery job while Harvest runs -> [(item id, count)] more rewards: the city's food box and the
    receipts for one Distribution Box delivered (taken from the inventory)."""
    if not events.is_on('harvest'):
        return [], []
    from .licenses import city_of_post
    out, changes = [], []
    box = CITY_FOOD_BOX.get(city_of_post(row[3]))
    if box and _info(box):
        out.append((box, 1))
    carried = sorted((i for i in p.items if _info(i.item_id) and _info(i.item_id).kind == 'deliverybox_item'
                      and not i.car_id), key=lambda i: -(_info(i.item_id).value or 1))
    if carried:
        from .driftuse import take_one
        size = _info(carried[0].item_id).value or 1
        changes.append(await take_one(p, carried[0]))
        rating = chef_rating()
        out.append((RECEIPT, rating * size))
        session.log.note(f'harvest: {carried[0].item_id} delivered -> {rating * size} receipt(s)')
    return out, changes


def chef_rating(rng=random):
    """restaurant_evaluation: the chef's rating, rows that differ only by their receipt count (1 / 2 / 3 at
    55 / 30 / 15 % in 2016) -> the count."""
    from .driftuse import groups
    rows = [r for r in groups().get('restaurant_evaluation', []) if r[0] == 'NormalItem' and r[3] > 0]
    if not rows:
        return 1
    weights = [r[4] for r in rows] if any(r[4] > 0 for r in rows) else [55, 30, 15][:len(rows)] + [1] * (len(rows) - 3)
    return rng.choices([r[3] for r in rows], weights=weights[:len(rows)])[0]


async def exchange_receipts(session, p, it, info):
    """Using Receipts (event_autumn): the largest HARVEST_EXCHANGE step the stack reaches. -> True when answered."""
    from .alchemy import take_count
    from .driftuse import Gains, give_item
    from .items import USE_KINDS
    have = held(p, RECEIPT)
    step = next(((n, box) for n, box in HARVEST_EXCHANGE if have >= n and _info(box)), None)
    if not step:
        low = min(n for n, _ in HARVEST_EXCHANGE)
        error(session, f'Collect {low} Receipts to exchange them for a Harvest gift box.')
        return True
    gains = Gains()
    gains.items += await take_count(p, RECEIPT, step[0])
    await give_item(p, step[1], 1, gains)
    send(session, Frame(0x1a2, struct.pack('<II4I', it.inven_idx, 0, USE_KINDS.get(info.kind, 0), 0, 0, 0)))
    gains.send(session, p)
    send(session, Frame(0x89, struct.pack('<IIII', 23, _info(step[1]).table_idx, 1, 0)))
    session.log.note(f'harvest: {step[0]} receipts -> {step[1]}')
    return True


def login_frames(p):
    """Frames for a 2016 login while Christmas runs: 0xcf2 with the configured tree stage (none when 0)."""
    from ..version import is_2016
    if not is_2016() or not events.is_on('christmas'):
        return []
    try:
        stage = int(context.events.get('christmas.tree', '0'))
    except ValueError:
        stage = 0
    return [Frame(0xcf2, struct.pack('<i', min(max(stage, 0), 5)))] if stage > 0 else []


def push_event_switch(name):
    """gmevent: tell the online 2016 clients what they can be told without a relog (0xfbb for Valentine)."""
    from ..version import is_2016
    from .login import sessions
    if name != 'valentine' or not is_2016():
        return 0
    on = 1 if events.is_on('valentine') else 0
    n = 0
    for s in list(sessions.values()):
        if s.state.get('player'):
            send(s, Frame(0xfbb, struct.pack('<I', on)))
            n += 1
    return n
