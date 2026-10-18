"""Manufacturing (2011; the client calls it alchemy): skill books, manufacturing, the manufacturing shop.

Recipes: the client's Init/Alchemy_SkillBook.xlt, one row per skill book (SkillBookID): ReqLv (manufacturing level),
    up to 3 materials (ItemID_n, Count), a kit (KitID, Count), the result (Result_ItemID, Count), a bonus item
    (reward_ItemID, Count) at reward_random %, SuccessChance(%), SuccessExp / FailExp. Levels: Init/
    Alchemy_LevelModify.xlt (EXP_MAX of levels 1-4: 8610 / 66420 / 221430 / 521640).
Kept: SKID_PLAYMODE_TB, MODEID 'ALCHEMY' (POINT = manufacturing EXP) and one row 'SKB_<skill book id>' per skill
    book learned.

0x0e75 AlchemyInfo (S>C, at login; client 0x51d300): u32 0, u32 n, u64 EXP (character +0x191d), n x wchar[60]
    skill book ids learned (0x704860 marks each; the client's recipe names are UTF-16, 0x186e-byte records at
    [0x95a134 + 4 .. + 8], name @8, learned @0xe8). Size 18 + 120 n.
Learning: the client's inventory right-click on a skill book (UseItemClient kind user_create, 0x6015a0) checks
    the book exists ("Skill Book does not exist.", 11895), its ReqLv against the manufacturing level and whether it
    is learned ("You have the skill book already.", 11896), then sends 0x1a1 ItemUse -> learn(): saved, 0x0e7c
    AlchemyLearn (char[56] skill book id; client 0x519790 marks it learned and new) and the book is used up
    (items.use_item). (0x0e7b, the same layout, unmarks one: not sent.)
0x0e78 Manufacture (C>S, char[56] skill book id; the manufacturing window 0x5c3cc7 -> 0x8060a0, once per item when
    a quantity is chosen) -> materials and kit taken, the success chance rolled: on success the result and (by
    its chance) the bonus item; SuccessExp / FailExp added. The chance: SuccessChance + a mounted license's
    ME_DoubleUserCreate + a Manufacturing Enhancer's value (i_n_createup, UseItemClient kind user_create_source,
    value 20; item text "When you have this in your inventory, the ratio of manufacturing will increase"; sold in the
    drift shop as bundles of 50 / 10): one is used up per try. The client sends only the skill book id; right-
    clicking an enhancer only opens the manufacturing window (EU exe 0x61d190, kind 0x48), so the server applies it -> 0x0e79 AlchemyResult (char[56] id, u8 1 success / 0
    failure (client 0x5c39b0: the completed count and the sound), u64 EXP, u32 0) + 0x192.
    Refused (not learned, level, missing materials, inventory full): a Send_Error text, no 0x0e79.
Parts Grinder: 0x0e1a -> 0x0e1b, see grind_part below.
The manufacturing shop (NPC "Sid", texts manufashop_B0_*: in the Driver Dome, city 0): its goods are RewardGroup
    rs_manufashop_01..03 (kits, Parts Grinder, Space Warp Engine, skill books) at their item price; bought with the
    ordinary 0x195 BuyItem (items.buy_item: shop_items).
"""
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send

EXP_MODE, SKILL_PREFIX = 'ALCHEMY', 'SKB_'
ENHANCER_KIND = 'user_create_source'        # Manufacturing Enhancer (client use kind 0x48)
NAME = 56                                   # char[56] skill book id in 0x0e78 / 0x0e79 / 0x0e7b / 0x0e7c
ENTRY = 0x78                                # one skill book id in 0x0e75
STATE_SQL = ("SELECT MODEID, POINT FROM SKID_PLAYMODE_TB WHERE SERVERID=%s AND CID=%s AND"
             " (MODEID=%s OR MODEID LIKE 'SKB[_]%%')")
SAVE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), POINT=%s WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),0,0,%s,0,0,0,0,0,%s)"""

_recipes = _levels = _shop = None


def _n(v, kind=int):
    try:
        return kind(float(v))
    except (TypeError, ValueError):
        return 0


def recipes():
    """Alchemy_SkillBook.xlt -> {skill book id: recipe}."""
    global _recipes
    if _recipes is None:
        import os
        from ..data import read_xlt
        rows = read_xlt(os.path.join(context.data.root, 'Init', 'Alchemy_SkillBook.xlt'))
        col = {name: i for i, name in reversed(list(enumerate(rows[2])))}
        _recipes = {}
        for r in rows[3:]:
            if len(r) <= 27 or not r[1].strip():
                continue
            items = [(r[i].strip(), _n(r[i + 1])) for i in (6, 8, 10) if r[i].strip()]
            _recipes[r[1].strip()] = dict(
                req=_n(r[col['ReqLv']]), items=items, kit=(r[12].strip(), _n(r[13])), result=(r[14].strip(), _n(r[15]) or 1),
                bonus_pct=_n(r[16], float), bonus=(r[17].strip(), _n(r[18])), chance=_n(r[25], float),
                exp_ok=_n(r[26]), exp_fail=_n(r[27]), name=r[4].strip())
    return _recipes


def levels():
    """Alchemy_LevelModify.xlt -> [EXP_MAX of level 1, 2, ...]."""
    global _levels
    if _levels is None:
        import os
        from ..data import read_xlt
        rows = read_xlt(os.path.join(context.data.root, 'Init', 'Alchemy_LevelModify.xlt'))
        _levels = [_n(r[1]) for r in rows[3:] if len(r) > 2 and r[1].strip().isdigit()]
    return _levels


def level_of(exp):
    caps = levels()
    return min(1 + sum(1 for cap in caps if exp >= cap), max(len(caps), 1))


def shop_items():
    """The manufacturing shop's goods: the item ids of RewardGroup rs_manufashop_*."""
    global _shop
    if _shop is None:
        from .driftuse import groups
        _shop = {row[1] for g, rows in groups().items() if g.startswith('rs_manufashop') for row in rows}
    return _shop


def name_bytes(name, size):
    return name.encode('latin-1', 'replace')[:size - 1].ljust(size, b'\0')


async def load(p):
    """The player's manufacturing EXP and skill books (p.alchemy)."""
    db = context.db
    exp, skills = 0, set()
    for mode, point in await db.rows(STATE_SQL, (db.server_id, p.char.cid, EXP_MODE)):
        mode = str(mode).strip()
        if mode == EXP_MODE:
            exp = _n(point)
        else:
            skills.add(mode[len(SKILL_PREFIX):])
    p.alchemy = dict(exp=exp, skills=skills)
    return p.alchemy


def info_frame(p):
    a = p.alchemy
    names = sorted(a['skills'])
    # the entries are UTF-16 (wchar[60]): the handler looks them up as they are, while 0x0e7c's char[56] is
    # converted first (user, 2026-10-15: a skill learned was gone after logging in again - sent as char[0x78])
    return Frame(0xe75, struct.pack('<IIQ', 0, len(names), a['exp'])
                 + b''.join(n.encode('utf-16-le')[:ENTRY - 2].ljust(ENTRY, b'\0') for n in names))


async def save(p, mode, point):
    db, c = context.db, p.char
    await db.execute(SAVE_SQL, (point, db.server_id, c.cid, mode, db.server_id, c.cid, c.name, mode, point, c.member))


async def learn(session, p, info):
    """A skill book used (items.use_item, before the book is used up) -> True when learned."""
    a = getattr(p, 'alchemy', None) or await load(p)
    r = recipes().get(info.item_id)
    if not r:
        error(session, 'Skill Book does not exist.')
        return False
    if info.item_id in a['skills']:
        error(session, 'You have the skill book already.')
        return False
    if level_of(a['exp']) < r['req']:
        error(session, f'Your manufacturing skill level must be {r["req"]} to learn this skill book.')
        return False
    a['skills'].add(info.item_id)
    await save(p, SKILL_PREFIX + info.item_id, 1)
    send(session, Frame(0xe7c, name_bytes(info.item_id, NAME)))
    session.log.note(f'skill book learned: {info.item_id}')
    return True


def held_count(p, item_id):
    return sum(i.stack for i in p.items if i.item_id == item_id and not i.car_id and (i.state & 0xffff) != 4)


async def take_count(p, item_id, count):
    """count of an item out of the inventory (smallest stacks first) -> [(item, state)]."""
    from .driftuse import take_one
    changes = []
    for it in sorted((i for i in p.items if i.item_id == item_id and not i.car_id and (i.state & 0xffff) != 4),
                     key=lambda i: i.stack):
        while count > 0 and it in p.items and it.stack > 0:
            changes.append(await take_one(p, it))
            count -= 1
        if count <= 0:
            break
    merged = {}
    for it, state in changes:                   # one entry per item, its last state
        merged[id(it)] = (it, state)
    return list(merged.values())


def enhancer(p):
    """The Manufacturing Enhancer held (UseItemClient kind user_create_source with a value: i_n_createup, 20) ->
    (item, value %) or None. Space Warp Engine is the same kind with no value (a material)."""
    t = context.data
    best = None
    for it in p.items:
        info = t.item_info(it.table_idx) if not it.car_id and (it.state & 0xffff) != 4 else None
        if info and info.kind == ENHANCER_KIND and info.value > 0 and (not best or info.value > best[1]):
            best = (it, info.value)
    return best


@on(SVC, C2S, 0xe78)
async def manufacture(session, frame):
    from .combo import free_slots
    from .driftuse import Gains, give_item
    from .items import mod_list, stack_for
    p = session.state.get('player')
    if not p or len(frame.payload) < 1:
        return
    name = frame.payload[:NAME].split(b'\0', 1)[0].decode('latin-1')
    a = getattr(p, 'alchemy', None) or await load(p)
    r = recipes().get(name)
    if not r or name not in a['skills']:
        return error(session, 'You have not learned this skill book.')
    if level_of(a['exp']) < r['req']:
        return error(session, f'Your manufacturing skill level must be {r["req"]}.')
    t = context.data
    need = r['items'] + ([r['kit']] if r['kit'][0] else [])
    missing = [item for item, count in need if held_count(p, item) < count]
    if missing:
        return error(session, 'Not enough materials for manufacturing.')
    result = t.item_info(t.item_index.get(r['result'][0], -1))
    if not result:
        return error(session, 'Manufacturing failed.')
    if not stack_for(p, result, r['result'][1]) and free_slots(p) <= 0:
        return error(session, 'Your inventory is full.')
    changes = []
    for item, count in need:
        changes += await take_count(p, item, count)
    from . import licenses
    from .driftuse import take_one
    # a mounted license (ME_DoubleUserCreate): the basic production chance + its value %; a Manufacturing Enhancer
    # held: + its value % more, one used up per try
    chance = r['chance'] + licenses.effects(p).get('ME_DoubleUserCreate', 0)
    boost = enhancer(p)
    if boost:
        chance += boost[1]
        changes.append(await take_one(p, boost[0]))
    ok = random.uniform(0, 100) < chance
    gains = Gains()
    if ok:
        await give_item(p, r['result'][0], r['result'][1], gains)
        bonus, n = r['bonus']
        if bonus in t.item_index and n and random.uniform(0, 100) < r['bonus_pct']:
            await give_item(p, bonus, n, gains)
    a['exp'] += r['exp_ok'] if ok else r['exp_fail']
    await save(p, EXP_MODE, a['exp'])
    session.log.note(f'manufacture {name}: {"success" if ok else "failure"} at {chance:g} %'
                     + (f' ({boost[0].item_id} +{boost[1]})' if boost else '') + f', EXP {a["exp"]} (level {level_of(a["exp"])})')
    send(session, Frame(0xe79, name_bytes(name, NAME) + struct.pack('<BQI', 1 if ok else 0, a['exp'], 0)))
    if changes:
        send(session, mod_list(*changes))
    gains.send(session, p)
    await licenses.count_monthly(session, 'Create')     # licenses: this month's production tries (GC_CreateThis/LastMonth)


# ---- Parts Grinder (UseItemClient kind partsgrinder: PartsGrinder, from the manufacturing shop) -------------------
# 0x0e1a GrindPart (C>S: u32 part InvenIdx, u32 grinder InvenIdx; after the client's "Grind %s parts. Do you wish
#      to continue?" (11889)) -> 0x0e1b (the same 8 bytes; client 0x50f060 reads nothing) + 0x192: the part and one
#      grinder used up, RewardGroup rw_partsgrinder_<n|s|h> (1 Parts Dust of the part's grade + 1 Modified Parts
#      Piece; docking items: _dock, 3 pieces) given. Other items (Ultra / event parts, non-parts, a part on a car or
#      on auction): "This item can't be grinded." (11888), nothing used.
PART_KINDS = ('speed', 'accel', 'crash', 'boost')


def grind_group(info):
    from .driftuse import groups
    dock = info.kind.startswith('dock_')
    if not (dock or info.kind in PART_KINDS) or not info.grade:
        return None
    group = f'rw_partsgrinder_{info.grade[-1].lower()}' + ('_dock' if dock else '')
    return group if group in groups() else None


@on(SVC, C2S, 0xe1a)
async def grind_part(session, frame):
    from .driftuse import Gains, give, roll, take_one
    from .items import info_of, mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    part_idx, grinder_idx = struct.unpack_from('<II', frame.payload)
    part = next((i for i in p.items if i.inven_idx == part_idx), None)
    grinder = next((i for i in p.items if i.inven_idx == grinder_idx), None)
    pinfo, ginfo = (info_of(part) if part else None), (info_of(grinder) if grinder else None)
    group = grind_group(pinfo) if pinfo else None
    if (not ginfo or ginfo.kind != 'partsgrinder' or not group or part.car_id or (part.state & 0xffff) == 4
            or (grinder.state & 0xffff) == 4):
        return error(session, "This item can't be grinded.")
    db = context.db
    from .items import DELETE_SQL, REMOVED
    await db.execute(DELETE_SQL, (db.server_id, p.char.cid, part.inven_idx))
    p.items.remove(part)
    changes = [(part, REMOVED), await take_one(p, grinder)]
    gains = Gains()
    await give(session, p, roll(group), gains)
    session.log.note(f'grind {part.item_id} ({group})')
    send(session, Frame(0xe1b, frame.payload[:8]))
    send(session, mod_list(*changes))
    gains.send(session, p)
