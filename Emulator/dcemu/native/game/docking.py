"""Docking parts (2011): made by combining parts with a seed, docked into a part's slot on the car.

**Items** (ItemClient.tdf kind dock_A / dock_B / dock_C / dock_S = accel, booster, durability (crash), speed;
the client's item types 11-14): grade ON / OS / OH (for N / S / H parts), grade letters A.. (Normal A-H,
Super A-J, Hyper A-O: dock_S_N001 .. N008, S001 .. S010, H001 .. H015). The dock_D* rows ("Combined ...
Docking A") are only the icon the client draws in a docked slot (client 0x5fabe0 builds "dock_D%c_%c001"
from the docked item's type and grade); they are never given.

**Points** (the user's guide, Documents/"Parts shop", and the client): a docking item has its own points,
added flat to its stat when docked. The client's item value (0x72c9c0) = table value (0 for docking rows) +
the record's 2011 field @0x44 + the random bonus @0xc; its stat sum (0x722320) adds it for types 11-14 as for
parts. So: white (base) points -> record @0x44 (stored in SKID_ITEM_TB.BOX, records.Item.encode). Purple
bonus points: the tooltip shows them as their own line "Docked Parts Points +12p" (the user's video,
Downloads/"Drift City Remastered Dockings Guide.mp4"), the docking_b assist "Docking Bonus N" (a_00154 ..
a_00178 = 1 .. 25): stored as the assist id in ASSIST_A, sent as its index in XiStrItemUnit.AssistA @0x10. The guide: "The white base points of the Docking part are based on the parts which
are used ... the average base of the 3 parts is 34 ... the best possible outcome will be 21", in steps of 5
base points (base = the part's table value + its random bonus: level 70 base 40 beats base 39); "The grade is
a random letter ... The higher the grade, the more points"; purple: "If the parts are +0, the best possible
outcome is 5 ... +12 parts: best 17, worst 12 ... the downwards average". StrategyWiki "Drift City/Docking
Parts" (measured tables): white ranges N 0-19, S 12-27, H 18-31; letters A-K (A most common); the letter
gives a hidden bonus that depends on the base of the part it is docked on: measured values fit the base x
the letter's docking_p % (N A 10% .. H 80%, S A 7% .., H A 4% ..), rounded down. Here: white = the grade's
lowest .. best (WHITE), purple = enhancement .. enhancement + 5 (the parts' NUPGRADE, average rounded down),
letter odds guessed (roll_docking); the letter picks its band of the white range (A lowest). H dockings need a Heat Treatment Kit to come off (wiki): not done.

**Combining** (parts shop, Combine tab): 0x1ac CombiItem (2011: 22 bytes; u32 Type, u32 Src1, Src2, Src3
InvenIdx, u32 the 4th slot = a seed's InvenIdx or 0; client sender 0x7f1bd0, called from 0x648020 with
Type 0 and from 0x6480f0 with Type 1) -> 0x192 (the parts and one seed gone, the new item), 0x1ad
CombiItemAck (u32 Type, u32 InvenIdx of the new item; client 0x515600 shows it). Three parts of the same stat
type and grade, none on a car (the guide: no mixed types or grades):
- with a seed of the same class (UseItemClient kind craft_up / craft_up_plus, i_n_Seed_N / S / H): a docking
  item of that type and grade, as above;
- without a seed: the next higher regular part of that type above the parts' average level (3 x level 60
  "Big" -> level 65 "Champion"; levels 1 + 7 + 25 -> level 13; N level 25 -> S level 31), only up to level 70 (UPGRADE_MAX_LEVEL); the new part gets a random bonus 0..its range
  (ItemClient column 11). 2008: PacketParser::Cmd_CombiItem 0x605090 / XiCsCharInfo::CombiItem 0x5d6c80
  (a random part of a level group). Errors: 20034 "Failed to combine the items."

**Docking** a part: the client drags the docking item onto a part and sends 0x199 EquipItem with the part's
slot (seen), or 0x18e EnchantItem (u32 part InvenIdx, u32 docking InvenIdx; sender 0x7f1d40 from 0x5f7110,
after the check 0x5fcdb0: text 11433 "New options cannot be added to this part.") -> 0x18f EnchantItemAck
(the same 8 bytes; client 0x50f070: text 11432). The part must be on a car: the docking goes into the
part's slot (CARID, STATE = slot << 16 | 1); the docking item already there comes off. It must match the
part's stat type and grade. When the part comes off the car its docking comes off too (items.unequip_item).
"""
import math
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import CHANGED, NEW, info_of, mod_list, new_item, placed, save_state, slot_of
from .login import SVC, error, send, stat_frames

PART_OF_DOCK = {'dock_S': 'speed', 'dock_C': 'crash', 'dock_A': 'accel', 'dock_B': 'boost'}
DOCK_OF_PART = {v: k for k, v in PART_OF_DOCK.items()}
WHITE_STEP = 5                      # guide: white points go up per 5 base points of the parts
# part grade -> (lowest, highest white points (wiki "Docking Part Base Range"), best white per base point:
# H 0.7 from the guide (average base 34 -> best 21; base 45 -> 31 = the wiki's top); N and S guessed so that
# the best parts reach the wiki's top)
WHITE = {'N': (0, 19, 1.0), 'S': (12, 27, 0.9), 'H': (18, 31, 0.7)}
# letters a grade can get: Normal A-H, Super A-J (the client's tables), Hyper A-L (the user's video "Drift City
# Remastered Dockings Guide"; the wiki saw up to K); odds: the video's curve, A about 25 %, each next one
# about 3/4 of the one before (LETTER_DECAY; a Seed PLUS: a slower decay, guessed)
MAX_LETTERS = {'N': 8, 'S': 10, 'H': 12}
LETTER_DECAY = {False: 0.75, True: 0.8}
PURPLE_SPREAD = 5                   # guide: +0 parts 0..5, +12 parts 12..17
UPGRADE_MAX_LEVEL = 70              # guide: "This mechanism is possible till level 70."
WHITE_HYPER = (21, 21, 27, 1.0, 4 / 3)      # sum of base // 5, lowest, highest, their steps per count more
ON_CAR = 1
# The values above are the defaults; Emulator/server_data/docking_chances.txt (read once, comments there) overrides them.
CHANCES_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'server_data', 'docking_chances.txt')
_chances = None


def chances():
    """docking_chances.txt -> dict(letters {(grade, plus): [chance per letter]}, white {grade: (lo, hi, rate)},
    hyper (sum, lo, hi, lo step, hi step), purple, max_level); the defaults where the file says nothing."""
    global _chances
    if _chances is None:
        c = dict(letters={}, white=dict(WHITE), hyper=WHITE_HYPER, purple=PURPLE_SPREAD, max_level=UPGRADE_MAX_LEVEL)
        for g, n in MAX_LETTERS.items():
            for plus in (False, True):
                c['letters'][g, plus] = [LETTER_DECAY[plus] ** k for k in range(n)]
        try:
            for line in open(CHANCES_FILE, encoding='utf-8'):
                f = line.split('#')[0].split()
                if not f:
                    continue
                if f[0] == 'letters' and len(f) > 3 and f[2] in ('seed', 'plus'):
                    c['letters'][f[1].upper(), f[2] == 'plus'] = [max(float(v), 0.0) for v in f[3:]]
                elif f[0] == 'white' and len(f) >= 5:
                    c['white'][f[1].upper()] = (int(f[2]), int(f[3]), float(f[4]))
                elif f[0] == 'white_hyper' and len(f) >= 6:
                    c['hyper'] = (int(f[1]), int(f[2]), int(f[3]), float(f[4]), float(f[5]))
                elif f[0] == 'purple' and len(f) >= 2:
                    c['purple'] = int(f[1])
                elif f[0] == 'upgrade_max_level' and len(f) >= 2:
                    c['max_level'] = int(f[1])
        except (OSError, ValueError) as e:
            print(f'docking chances: {CHANCES_FILE}: {e} (defaults used for the rest)', flush=True)
        _chances = c
    return _chances


def is_dock(info):
    return info is not None and info.kind in PART_OF_DOCK


def letters(kind, grade):
    """-> the docking item ids of a kind and part grade that can be made, letter A first (MAX_LETTERS)."""
    prefix = f'{kind}_{grade}'
    most = max(len(chances()['letters'].get((grade, plus), ())) for plus in (False, True))
    return sorted(i for i in context.data.item_index if i.startswith(prefix) and i[len(prefix):].isdigit())[:most]


def seed_class(info):
    """A seed item -> its grade letter (i_n_Seed_S, i_n_Seedplus_H, i_n_Seed_N_ex), or None."""
    if not info or info.kind not in ('craft_up', 'craft_up_plus'):
        return None
    f = info.item_id.split('_')
    return f[3] if len(f) > 3 else None


def base_points(it):
    """A part's white base points: its table value + its random bonus."""
    stat = context.data.part_stat(it.item_id)
    return (stat[1] if stat else 0) + it.random


def white_range(grade, bases):
    """-> (lowest, highest) white points from the three parts' bases.
    Hyper (the user's video, measured): each part counts base // 5; their sum - 21 = t (3 x base 37-39: t 0 ->
    21-27; +1 per step: 22-29, 23-30, 24-31 (3 x base 40-43), 25-33, 26-34, 27-35 (3 x base 45-48)): lowest 21 + t,
    highest 27 + ceil(4t / 3). Normal / Super (not measured): the grade's lowest .. the average base rounded
    down to 5 x WHITE's rate, within the wiki's ranges."""
    c = chances()
    if grade == 'H':
        base, lo, hi, lo_step, hi_step = c['hyper']
        t = sum(b // WHITE_STEP for b in bases) - base
        return max(int(lo + math.floor(t * lo_step + 1e-9)), 0), max(int(hi + math.ceil(t * hi_step - 1e-9)), 0)
    lo, hi, rate = c['white'].get(grade, (0, 0, 0))
    best = min(hi, int(int(sum(bases) / len(bases)) // WHITE_STEP * WHITE_STEP * rate))
    return min(lo, best), best


def roll_docking(n, grade, bases, upgrades, plus=False):
    """-> (letter index, white points, purple points). The white range is cut into one band per letter, A the
    lowest (user, 2026-10-16: a later letter must have more stats; before, white was rolled apart from the letter
    and an A could beat a J); bands overlap when the range is narrower than the letter count."""
    c = chances()
    weights = (list(c['letters'].get((grade, plus), ())) + [0.0] * n)[:n]
    if not any(weights):
        weights = [1.0] + [0.0] * (n - 1)
    letter = random.choices(range(n), weights=weights)[0]
    lo, hi = white_range(grade, bases)
    width = (hi - lo + 1) / n
    white = random.randint(lo + int(letter * width), max(lo + int(letter * width), lo + math.ceil((letter + 1) * width) - 1))
    low = sum(upgrades) // len(upgrades)
    return letter, white, random.randint(low, low + c['purple'])


def next_part(kind, level):
    """The regular part (i_*, no _b / _g variant) of a kind one level step above level (the parts' average
    level; the next grade's first part above the top of a grade: 3 x N level 25 -> S level 31)."""
    t = context.data
    rows = [r for r in t._part_rows if r[0] == kind and r[2].startswith('i_') and r[2].count('_') == 2]
    above = sorted((int(r[7]), r[2]) for r in rows if level < int(r[7]) <= chances()['max_level'])
    return above[0][1] if above else None


def dock_percent(item_id):
    """Docking item id -> the % of its letter (Assist_Client.tdf docking_p row named in ItemClient column 20)."""
    global _pct
    if _pct is None:
        import os
        from ..data import read_tdf
        assist = {r[1]: r for r in read_tdf(os.path.join(context.data.server_data, 'Assist_Client.tdf')) if len(r) > 5}
        _pct = {}
        for r in context.data._part_rows:
            a = assist.get(r[20]) if r[0] in PART_OF_DOCK and len(r) > 20 else None
            if a and a[2] == 'docking_p' and a[5].isdigit():
                _pct[r[2]] = int(a[5])
    return _pct.get(item_id, 0)


_pct = None
_assists = None


def assists():
    """Assist_Client.tdf -> ({assist id: index}, {docking_b value: assist id}). The index the item record carries
    (XiStrItemUnit.AssistA @0x10) is the row number from 1 (2008 XiAssistTable::LoadFile 0x64dd90: key = row + 1)."""
    global _assists
    if _assists is None:
        import os
        from ..data import read_tdf
        rows = read_tdf(os.path.join(context.data.server_data, 'Assist_Client.tdf'))
        index = {r[1]: n + 1 for n, r in enumerate(rows) if len(r) > 1}
        bonus = {int(r[5]): r[1] for r in rows if len(r) > 5 and r[2] == 'docking_b' and r[5].isdigit()}
        _assists = index, bonus
    return _assists


def purple_assist(points):
    """Purple points -> the docking_b assist id ("Docking Bonus N": Docked Parts Points +Np, 1-25), or ''."""
    bonus = assists()[1]
    return bonus.get(min(points, max(bonus))) if points > 0 and bonus else ''


def purple_points(d):
    """A docking item's purple points: its docking_b assist (older items: the random bonus)."""
    if d.assist_a:
        for value, aid in assists()[1].items():
            if aid == d.assist_a:
                return value
    return d.random


def dock_bonus(p, car_id):
    """-> [speed, crash, accel, boost] the docked items on a car add: white + purple + the hidden bonus (the
    docked part's base x the letter's %, rounded down; enhancement does not count: wiki)."""
    out = [0, 0, 0, 0]
    on = [i for i in p.items if i.car_id == car_id and (i.state & 0xffff) == ON_CAR]
    for d in on:
        info = info_of(d)
        if not is_dock(info):
            continue
        part = next((i for i in on if slot_of(i) == slot_of(d) and info_of(i).kind == PART_OF_DOCK[info.kind]), None)
        if part:
            hidden = base_points(part) * dock_percent(info.item_id) // 100
            out[context.data.PART_STAT[info_of(part).kind]] += d.box + purple_points(d) + hidden
    return out


async def take(p, it):
    from .driftuse import take_one
    return await take_one(p, it)


POINTS_SQL = "UPDATE SKID_ITEM_TB SET NRANDOM=%s, BOX=%s, ASSIST_A=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"


@on(SVC, C2S, 0x1ac)
async def combine(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return error(session, '20017')                  # NotInitializedChar
    kind, *srcs = struct.unpack_from('<IIII', frame.payload)
    seed_idx = struct.unpack_from('<I', frame.payload, 16)[0] if len(frame.payload) >= 20 else 0
    parts = [next((i for i in p.items if i.inven_idx == s), None) for s in srcs]
    infos = [info_of(i) if i else None for i in parts]
    ok = (all(parts) and len({i.inven_idx for i in parts}) == 3 and all(not i.car_id for i in parts)
          and all(f and f.kind in DOCK_OF_PART for f in infos)
          and len({f.kind for f in infos}) == 1 and len({f.grade for f in infos}) == 1)
    seed_it = next((i for i in p.items if i.inven_idx == seed_idx), None) if seed_idx else None
    t, db = context.data, context.db
    result = None
    if ok and seed_it:
        names = letters(DOCK_OF_PART[infos[0].kind], infos[0].grade)
        if seed_class(info_of(seed_it)) == infos[0].grade and names:
            letter, white, purple = roll_docking(len(names), infos[0].grade, [base_points(i) for i in parts],
                                                 [i.upgrade for i in parts], info_of(seed_it).kind == 'craft_up_plus')
            result = await new_item(p, t.item_info(t.item_index[names[letter]]), 1)
            result.box, result.assist_a = white, purple_assist(purple)
            what = f'{names[letter]} (letter {"ABCDEFGHIJKLMNO"[letter]}) white {white} purple {purple}'
    elif ok:
        name = next_part(infos[0].kind, sum(f.req_level for f in infos) / 3)
        if name:
            result = await new_item(p, t.item_info(t.item_index[name]), 1)
            row = t.items.get(name)
            result.random = random.randint(0, int(row[11])) if row and row[11].isdigit() else 0
            what = f'{name} random {result.random}'
    if not result:
        session.log.note(f'combine {srcs} + {seed_idx}: refused')
        return error(session, '20034')                  # "Failed to combine the items."
    await db.execute(POINTS_SQL, (result.random, result.box, result.assist_a, db.server_id, p.char.cid, result.inven_idx))
    changes = [await take(p, it) for it in parts]
    if seed_it:
        changes.append(await take(p, seed_it))
    session.log.note(f'combine {[f.item_id for f in infos]} + seed {seed_it and info_of(seed_it).item_id}: {what}')
    send(session, mod_list(*changes, (result, NEW)))
    send(session, Frame(0x1ad, struct.pack('<II', kind, result.inven_idx)))


async def dock(session, p, part, item):
    """Dock item into part's slot -> error text or None."""
    info, pinfo = info_of(item), info_of(part)
    if not is_dock(info) or not pinfo or PART_OF_DOCK[info.kind] != pinfo.kind \
            or info.grade != 'O' + pinfo.grade or (part.state & 0xffff) != ON_CAR or not part.car_id:
        return '20027'                                  # ItemEquipFail
    if item.car_id:
        return '20027'
    slot = slot_of(part)
    old = [i for i in p.items if i.car_id == part.car_id and slot_of(i) == slot and is_dock(info_of(i))
           and (i.state & 0xffff) == ON_CAR]
    for o in old:
        placed(o, 0, 0)
    placed(item, part.car_id, slot)
    await save_state(p, *old, item)
    session.log.note(f'dock {info.item_id} (white {item.box}, purple {purple_points(item)}, hidden '
                     f'{base_points(part) * dock_percent(info.item_id) // 100}) into {pinfo.item_id} slot {slot}')
    send(session, mod_list(*((i, CHANGED) for i in old + [item])))
    for f in stat_frames(p):
        send(session, f)
    return None


@on(SVC, C2S, 0x18e)
async def enchant_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    a, b = struct.unpack_from('<II', frame.payload)
    first = next((i for i in p.items if i.inven_idx == a), None)
    second = next((i for i in p.items if i.inven_idx == b), None)
    if first and second and is_dock(info_of(first)):    # either order
        first, second = second, first
    if not first or not second or not is_dock(info_of(second)):
        session.log.note(f'enchant {a} {b}: not a docking item (options are not native)')
        return error(session, '20027')
    err = await dock(session, p, first, second)
    if err:
        return error(session, err)
    send(session, Frame(0x18f, frame.payload[:8]))
