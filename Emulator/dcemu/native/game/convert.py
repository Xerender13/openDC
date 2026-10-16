"""Converting parts (parts shop, Convert tab): a Converting Solution gives a part two options.

0x1aa ModifyItem (u32 part InvenIdx, u32 solution InvenIdx, i32 count; 14 bytes as 2008) -> 0x192 (the part, the
    solution stack), 0x1ab ModifyItemAck (2011: 50 bytes: u32 part InvenIdx, the part's ten assist slots as
    Assist_Client row + 1 (the client's text 11414 names the first two), u32 mode 0; client 0x515420).
    The tab is shown with the content flag Main.Modify (2011; sent as 1, login.content_flags).
2008 (XiCsCharInfo::ModifyItem 0x5cd8c0, XiItemModifyTable 0x5a2130 / PartModify_Server.tdf): the part is not
boxed or in a trade; the solution is a usable item of kind "trans" whose type is 1 / 2 / 3 (A / B / C); a row
(tier) is drawn by its probability; the part's two assists become the row's columns 0 + 1 (type A: speed), 2 + 3
(B: acceleration), 4 + 5 (C: booster time + durability) (XiCsItem::ChangeAssist); rows 1-4 make the part
untradeable (Belonging 1), the others tradeable again; one solution is used.
2011: the client's PartModify_Client.tdf has 34 rows of the same six columns and no odds; the 2008 server
table's 17 odds are spread over them in order (ODDS: row n takes half of 2008 row (n + 1) // 2), so the first
rows stay the common ones. Solutions: Converting Solution Type A / B / C (i_n_00040 / 41 / 42, also _ex
Training and _plus), "Change Solution Option Type N / S / H" (i_n_00116 / 117 / 118; value 0 / 1 / 2 = grade)
for option parts (op_*), whose column pair follows the option's kind (op_S speed -> A, op_A accel -> B, the
others -> C). A PLUS solution ("Increases chances ...") gives one more draw, the best row counts (guess).
**Enhancement Formula** (kind trans_up; the client's "Converting Warranty System", GlobalContent
OptionCraft_Guarantee): while one is held, a convert that would give a lower tier than the part already has is
not applied: the part keeps its options and one Formula is used up (the user: it "retains the best outcome of
converting ... and when it works it consumes the item"). The ack's mode tells the client: 0 = kept by the
warranty (text 11415 "Retain the current settings through the Converting Warranty System."; sending 0 for
every convert showed that text each time), anything else = a normal convert (MODE_NORMAL).
The user (2026-10-13): parts and option parts only, not docking parts or set parts.
The assists are stored as ids in SKID_ITEM_TB.ASSIST_A / ASSIST_B (2008) and sent in the record's assist slots
@0x10 / @0x14; the stat ones (bonusspeed / bonuscrash / bonusaccel / bonusboost points) count for a part on the
car (assist_bonus, player.stats).
"""
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import CHANGED, info_of, mod_list
from .login import SVC, error, send, stat_frames

# PartModify_Server.tdf column 6 (2008): the chance of each of its 17 rows
ODDS_2008 = (0.3372956, 0.3372956, 0.116, 0.116, 0.03, 0.03, 0.015, 0.0075, 0.00375, 0.00375, 0.001875,
             0.0009375, 0.0004688, 0.0001, 2.5e-05, 2.5e-06, 1e-07)
UNTRADEABLE_ROWS = 4                # 2008: rows 1-4 bind the part
MODE_KEPT, MODE_NORMAL = 0, 2       # 0x1ab mode (client 0x51546f)
SOLUTION_TYPE = {'i_n_00040': 0, 'i_n_00041': 1, 'i_n_00042': 2}      # A, B, C -> column pair
OPTION_SOLUTION = {'i_n_00116': 'N', 'i_n_00117': 'S', 'i_n_00118': 'H'}
OPTION_PAIR = {'op_S': 0, 'op_A': 1}                                   # the other options: pair 2
STAT_KINDS = {'bonusspeed': 0, 'bonuscrash': 1, 'bonusaccel': 2, 'bonusboost': 3}
ASSIST_SQL = ("UPDATE SKID_ITEM_TB SET ASSIST_A=%s, ASSIST_B=%s, BELONGING=%s WHERE SERVERID=%s AND CID=%s"
              " AND INVENIDX=%s")

_rows = _assists = None


def rows():
    global _rows
    if _rows is None:
        from ..data import read_tdf
        _rows = [r[:6] for r in read_tdf(os.path.join(context.data.server_data, 'PartModify_Client.tdf')) if len(r) >= 6]
    return _rows


def assists():
    """-> {assist id: (index from 1, kind, value)}."""
    global _assists
    if _assists is None:
        from ..data import read_tdf
        _assists = {}
        for n, r in enumerate(read_tdf(os.path.join(context.data.server_data, 'Assist_Client.tdf'))):
            if len(r) > 5:
                try:
                    value = float(r[5])
                except ValueError:
                    value = 0.0
                _assists[r[1]] = (n + 1, r[2], value)
    return _assists


def assist_index(assist_id):
    a = assists().get((assist_id or '').strip())
    return a[0] if a else 0


def assist_bonus(it):
    """-> [(stat index, points)] of a part's converted assists."""
    out = []
    for aid in (it.assist_a, it.assist_b):
        a = assists().get((aid or '').strip())
        if a and a[1] in STAT_KINDS:
            out.append((STAT_KINDS[a[1]], int(a[2])))
    return out


def draw(tries=1):
    """-> a row index of PartModify_Client.tdf (0 = the commonest), the best of the tries."""
    n = len(rows())
    weights = [ODDS_2008[min(k // 2, len(ODDS_2008) - 1)] / 2 for k in range(n)]
    return max(random.choices(range(n), weights=weights)[0] for _ in range(max(tries, 1)))


def tier_of(it):
    """The row a part's two options come from, or -1."""
    have = ((it.assist_a or '').strip(), (it.assist_b or '').strip())
    if not have[0]:
        return -1
    for n, r in enumerate(rows()):
        if have in ((r[0], r[1]), (r[2], r[3]), (r[4], r[5])):
            best = n                                    # the same pair can stand in several rows: the highest
    return locals().get('best', -1)


def base_id(item_id):
    return item_id.replace('_ex', '').replace('_plus', '')


@on(SVC, C2S, 0x1aa)
async def modify_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return error(session, '20017')
    src, add, count = struct.unpack_from('<IIi', frame.payload)
    part = next((i for i in p.items if i.inven_idx == src), None)
    sol = next((i for i in p.items if i.inven_idx == add), None)
    pinfo, sinfo = (info_of(part) if part else None), (info_of(sol) if sol else None)
    pair = None
    if pinfo and sinfo and sinfo.kind == 'trans' and sol.stack >= 1 and not part.item_id.startswith(('si_', 'dock_')) \
            and part.upgrade >= 0:
        sid = base_id(sinfo.item_id)
        if pinfo.type in (0, 1, 2, 3) and sid in SOLUTION_TYPE:
            pair = SOLUTION_TYPE[sid]
        elif pinfo.kind.startswith('op_') and OPTION_SOLUTION.get(sid) == pinfo.grade[-1:]:
            pair = OPTION_PAIR.get(pinfo.kind, 2)
    if pair is None:
        session.log.note(f'convert {part and part.item_id} with {sol and sol.item_id}: refused')
        return error(session, '20033')                  # ItemUpgradeFail (2008 answered nothing)
    row = draw(1 + sinfo.item_id.endswith('_plus'))
    formula = next((i for i in p.items if info_of(i) and info_of(i).kind == 'trans_up'), None)
    db = context.db
    from .upgrade import use_enhancers
    changes = [await use_enhancers(p, sol, 1)]
    kept = bool(formula) and row < tier_of(part)
    if kept:                                            # the Enhancement Formula keeps the better options
        changes.append(await use_enhancers(p, formula, 1))
    else:
        part.assist_a, part.assist_b = rows()[row][pair * 2], rows()[row][pair * 2 + 1]
        part.belonging = 1 if row < UNTRADEABLE_ROWS else 0
        await db.execute(ASSIST_SQL, (part.assist_a, part.assist_b, part.belonging, db.server_id, p.char.cid,
                                      part.inven_idx))
    session.log.note(f'convert {pinfo.item_id} with {sinfo.item_id}: tier {row + 1} of {len(rows())} -> '
                     + (f'kept tier {tier_of(part) + 1} (Enhancement Formula used)' if kept else
                        f'{part.assist_a} + {part.assist_b}{" (untradeable)" if part.belonging else ""}'))
    slots = [assist_index(part.assist_a), assist_index(part.assist_b)] + [0] * 8
    # the ack first, then the list (2008)
    send(session, Frame(0x1ab, struct.pack('<I10II', src, *slots, MODE_KEPT if kept else MODE_NORMAL)))
    send(session, mod_list((part, CHANGED), *changes))
    from .licenses import count_monthly
    await count_monthly(session, 'Enchant')             # licenses: this month's convert tries (GC_EnchantThis/LastMonth)
    if part.car_id:
        for f in stat_frames(p):
            send(session, f)
