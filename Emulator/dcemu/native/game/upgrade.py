"""Enhancing parts with Mittron Enhancers (parts shop, Modify tab), with or without the Mittron Enhancer Booster.

0x19d UpgradeItem (u32 part InvenIdx, u32 enhancer InvenIdx, i32 count: the 2011 client sends 1; sender
    0x7f1220) -> 0x192 (the part changed or gone, the enhancer stack), 0x19e UpgradeItemAck (u32 Gold = the
    fee, the client takes it off its money itself; u32 Result; u32 part, u32 enhancer, i32 count; client
    0x515290). Result (2008): 0x30000 success, 0x30001 failed (nothing changes), 0x30002 the part is destroyed.
0x1ae UpgradeItemDouble (2011: 22 bytes; + u32 the drift inventory index of the Mittron Enhancer Booster, + u32
    an inventory item's InvenIdx (client kind 0x50, none in the 2011 tables: ignored)) -> 0x192, 0x4b2 (the
    Booster used), 0x5dd, 0x1af UpgradeItemDoubleAck (Gold, Result1, Result2, part, enhancer, count, Booster;
    2011 + 4 bytes; client 0x515370). The client sends it instead of 0x19d when the 0x5dd double-upgrade flag
    is set and a Booster (drift category 23, i_d_double) is held (client 0x64d680).

2008 rules (XiCsCharInfo::UpgradeItem 0x5d75b0, UpgradeItemDouble 0x5d0920): the part is not boxed or in a trade;
the enhancer is a usable item of use kind "upgrade" whose value fits the part's grade (N 0, S 1, H 2; 99 = the
plain Mittron Enhancer, any grade), the stack holds the count; the fee is taken first ("Not enough Mito" =
ItemUpgradeFail); the step (part level + 1, part grade) is rolled: success -> level + 1, else a destroy roll ->
the part breaks (XiCsItem::ItemDestroy 0x599890: the level is negated, NUPGRADE -7 = a broken +7; the client:
"You cannot equip / enhance broken parts."), else nothing; the enhancers are used either way. With the
Booster: two success rolls (each + 1), no destroy roll, the Booster is used up.
**Fail gauge = "Modify Chance Time"** (the user, 2026-10-13; found in the running client): the ten boxes of the
Modify tab are one value per character, not per part: the parts shop window's +0x238 (boxes [+0x208 ..
+0x22c], lit while +0x238 > index, client 0x64c701), set only by 0x89 NotifyEvent type 37 (u32 type, u32 ?,
u32 value, u32 ?; client 0x51ca37); at 10 the confirm text gets "(Modify Chance Time is in use..)" (12137,
GlobalContent UseUpgradeChanceTime). It fills with failed and breaking tries: + 1 per try with a Mittron
Enhancer, + 2 with a PLUS, + 4 with a DELUXE (UseItemClient "time" column 2 / 4; the same tiers also multiply the
success % of a try: emulator.ini [items] enhancer_plus / enhancer_deluxe, tier_factor); full (GAUGE_MAX) the next
try succeeds for sure; any success empties it (the user). Stored in SKID_COUPONPARAMVALUE_TB under the
server-only CTYPE GAUGE_TYPE; sent at login and after every try.
**Expiry** (the user's guide: "Mittron Enhancers (without the N and S) have an expiration date of 72 hours valid
from the point of obtaining"): enhancers of value 99 (Mittron Enhancer, PLUS, DELUXE) get ExpireTick = tick + EXPIRE_HOURS (setparts.period;
sent @0x48, so the client shows the time left); past it they are taken away when used, and refused.
**Restoring** broken parts: 0x1b3 RepairItem (u32 part, u32 kit; 10 bytes as 2008) -> 0x192, 0x1b4 RepairItemAck
(u32 Gold = fee, u32 Result, part, kit). 2008 XiCsCharInfo::RepairItem 0x5d0fe0 / XiCsItem::ItemRepair:
0x30003 RepairZero (back at +0), 0x30004 RepairFull (the old level back). 2011 kits by their tooltips:
"repair" N / S / H Mittron Repair Kit -> +0; "full_repair" N / S / H Restoration Kit: "Fully restores broken
Parts to its previous state ... If used for +12 or higher Parts, it will be restored back to +12";
"new_repair" Restoration Kit (+6 .. +12), Ultra Restoration Kit MK.II (+20): "Restores up to Level N Parts"
(UseItemClient "time" = N; higher parts are restored to N). The kit's value is the grade (N 0, S 1, H 2); the
fee is the step fee of the broken level.
Tables: the odds from the 2008 server's ItemUpgradeServer.tdf (the 2011 client has none): per grade (with the
2008 per-grade switch on) N columns 7-10, S 11-14, H 15-18 = success %, destroy %, points, fee. Fee and stat
bonus from the 2011 client's own ItemUpgradeClient.tdf, which it shows: per step, columns 2-5 = the part's
total bonus x 100 at that level for N / S / H / U (N +1 per level; S 1, 3, 5, ..; +20: N 20, S 39, H 58, U 77),
pairs 6/7, 8/9, 10/11, 12/13 = (?, fee) for N / S / H / U. The level is NUPGRADE (XiStrItemUnit.Upgrade @0x20),
the bonus is sent as UpgradePoint @0x24 and added to the part's stat (player.Player.stats). MAX_LEVEL 15 (the
user's guide: "The maximum achievable enhancement is +15").
"""
import datetime
import os
import random
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import CHANGED, DELETE_SQL, REMOVED, STACK_SQL, add_money, info_of, mod_list
from .login import SVC, error, send, stat_frames

ENHANCE_LEVELS = (('X', 10), ('XI', 11), ('XII', 12), ('XIII', 13), ('XV', 15), ('XIX', 19))   # GC_PartsEnhance<name>
SUCCESS, FAILED, DESTROYED, REPAIR_ZERO, REPAIR_FULL = 0x30000, 0x30001, 0x30002, 0x30003, 0x30004
MAX_LEVEL = 15
GAUGE_MAX = 10                      # the Modify tab's ten boxes
GAUGE_TYPE = 1000                   # SKID_COUPONPARAMVALUE_TB CTYPE of the gauge (coupons.SERVER_ONLY)
NOTIFY_GAUGE = 37                   # 0x89 NotifyEvent type
EXPIRE_HOURS = 72
FULL_REPAIR_CAP = 12
GAUGE_SQL = "UPDATE SKID_ITEM_TB SET NUPGRADE=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"
GRADES = 'NSHU'
ANY_GRADE = 99
UPGRADE_SQL = "UPDATE SKID_ITEM_TB SET NUPGRADE=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"

_tables = None


def tables():
    """-> (odds {(level, grade): (success %, destroy %)}, client {(level, grade): (bonus x 100, fee)},
    gauge {level: size})."""
    global _tables
    if _tables is None:
        from ..data import read_tdf
        odds, client, gauge = {}, {}, {}
        server = os.path.join(context.data.server_data or '', 'ItemUpgradeServer.tdf')
        for level, r in enumerate(read_tdf(server) if os.path.exists(server) else [], 1):
            for k, g in enumerate('NSH'):
                c = 7 + 4 * k
                odds[level, g] = (float(r[c] or 0), float(r[c + 1] or 0))
        for level, r in enumerate(read_tdf(os.path.join(context.data.server_data, 'ItemUpgradeClient.tdf')), 1):
            if len(r) < 14:
                continue
            for k, g in enumerate(GRADES):
                client[level, g] = (int(float(r[2 + k] or 0)), int(float(r[7 + 2 * k] or 0)))
        _tables = odds, client, gauge
    return _tables


def bonus(grade, level):
    """The stat points a part of this grade has at this enhancement level."""
    return tables()[1].get((level, grade), (0, 0))[0] // 100 if level > 0 else 0


def tier_factor(einfo):
    """x success % by the enhancer's tier: PLUS (UseItemClient "time" 2) emulator.ini enhancer_plus, DELUXE (4)
    enhancer_deluxe ("Better chances" / "Much better chances than Mittron Enhancer"; the 2008 odds table has no
    PLUS / DELUXE: user, 2026-10-15)."""
    return {2: context.enhancer_plus, 4: context.enhancer_deluxe}.get(einfo.time, 1.0)


def roll(percent):
    return random.random() * 100 < percent


def fits(enhancer, part):
    return enhancer.kind == 'upgrade' and (enhancer.value == ANY_GRADE or GRADES[:3].find(part.grade) == enhancer.value)


async def use_enhancers(p, it, count):
    db = context.db
    it.stack -= count
    if it.stack > 0:
        await db.execute(STACK_SQL, (it.stack, db.server_id, p.char.cid, it.inven_idx))
        return it, CHANGED
    await db.execute(DELETE_SQL, (db.server_id, p.char.cid, it.inven_idx))
    p.items.remove(it)
    return it, REMOVED


async def gauge_of(p):
    from .coupons import params
    return int((await params(p)).get(GAUGE_TYPE, 0))


async def set_gauge(p, value):
    from .coupons import params
    db = context.db
    (await params(p))[GAUGE_TYPE] = float(value)
    await db.execute("UPDATE SKID_COUPONPARAMVALUE_TB SET VALUE=%s, LASTDATE=GetDate() WHERE SERVERID=%s AND CID=%s"
                     " AND CTYPE=%s; IF @@ROWCOUNT = 0 INSERT INTO SKID_COUPONPARAMVALUE_TB(SERVERID, CID, CTYPE, VALUE,"
                     " LASTDATE) VALUES (%s,%s,%s,%s,GetDate())",
                     (value, db.server_id, p.char.cid, GAUGE_TYPE, db.server_id, p.char.cid, GAUGE_TYPE, value))


def gauge_frame(value):
    return Frame(0x89, struct.pack('<IIII', NOTIFY_GAUGE, 0, value, 0))


def expired(p, it):
    """An enhancer past its ExpireTick (setparts.period: EXPIRE_HOURS for the value-99 ones, from when it was got)."""
    from .setparts import expired as past
    return bool(past(p, it))


async def save_part(p, part):
    db = context.db
    await db.execute(GAUGE_SQL, (part.upgrade, db.server_id, p.char.cid, part.inven_idx))


async def enhance(session, frame, double):
    p = session.state.get('player')
    if not p or len(frame.payload) < 12:
        return None
    src, add, count = struct.unpack_from('<IIi', frame.payload)
    part = next((i for i in p.items if i.inven_idx == src), None)
    enh = next((i for i in p.items if i.inven_idx == add), None)
    pinfo, einfo = (info_of(part) if part else None), (info_of(enh) if enh else None)
    if enh and einfo and einfo.kind == 'upgrade' and expired(p, enh):
        session.log.note(f'enhance with {einfo.item_id}: expired (tick {enh.ctime}, now {p.tick}), taken away')
        send(session, mod_list(await use_enhancers(p, enh, enh.stack)))
        error(session, '20033')
        return None
    booster = None
    if double:
        vs_idx = struct.unpack_from('<I', frame.payload, 12)[0] if len(frame.payload) >= 16 else 0
        booster = next((v for v in p.vsitems if v.inven_idx == vs_idx), None)
        vis = context.data.visuals.get(booster.table_idx) if booster else None
        if not vis or vis.category != 23:                # Mittron Enhancer Booster (i_d_double)
            booster = None
    level = part.upgrade if part else 0
    odds = tables()[0].get((level + 1, pinfo.grade if pinfo else ''))
    fee = tables()[1].get((level + 1, pinfo.grade if pinfo else ''), (0, 0))[1]
    from . import licenses
    if fee:                                              # mounted licenses: ME_EnhanceFeeDis / ME_FeeDis (the ack has it)
        fee = fee * (100 - licenses.fee_discount(p, 'enhance')) // 100
    if (not pinfo or pinfo.type not in (0, 1, 2, 3) or level < 0 or not einfo or not fits(einfo, pinfo) or count < 1
            or enh.stack < count or level >= MAX_LEVEL or not odds or (double and not booster)
            or fee > p.char.mito or not await add_money(p.char, -fee)):
        session.log.note(f'enhance {part and part.item_id} +{level} with {enh and enh.item_id}: refused')
        error(session, '20033')                          # ItemUpgradeFail
        return None
    success, destroy = odds
    success = min(100.0, success * tier_factor(einfo))   # PLUS / DELUXE: better chances (their tooltips)
    fill, size = max(einfo.time, 1), GAUGE_MAX
    fill *= max(1, licenses.effects(p).get('ME_DoubleChanceTime', 1))   # mounted license: the gauge fills faster
    gauge, results = await gauge_of(p), []
    for _ in range(2 if double else 1):
        sure = size and gauge >= size
        if sure or roll(success):
            results.append(SUCCESS)
            gauge = 0
        elif not double and roll(destroy):
            results.append(DESTROYED)
            gauge = min(gauge + fill, size)
        else:
            results.append(FAILED)
            gauge = min(gauge + fill, size)
    db, changes = context.db, []
    gained = results.count(SUCCESS)
    if DESTROYED in results:
        part.upgrade = -level if level > 0 else 0       # broken (XiCsItem::ItemDestroy)
        if part.car_id:                                 # a broken part cannot stay on the car
            from .items import placed, save_state
            placed(part, 0, 0)
            await save_state(p, part)
    elif gained:
        part.upgrade = min(level + gained, MAX_LEVEL)
    await save_part(p, part)
    await set_gauge(p, gauge)
    changes.append((part, CHANGED))
    changes.append(await use_enhancers(p, enh, count))
    session.log.note(f'enhance {pinfo.item_id} +{level} ({pinfo.grade}, {success}% / destroy {destroy}%) with '
                     f'{einfo.item_id}{" + Booster" if double else ""}: {[hex(r) for r in results]} -> '
                     f'{"broken" if DESTROYED in results else "+%d" % part.upgrade}, gauge {gauge}/{size}, fee {fee}')
    # the ack first, then the item list (2008 Cmd_UpgradeItem / Cmd_UpgradeItemDouble): the client's ack handler
    # leaves the window waiting for the list; the other way round the parts shop could not be left (user)
    if double:
        send(session, Frame(0x1af, struct.pack('<III', fee, *results) + frame.payload[:16]
                            + frame.payload[16:20].ljust(4, b'\0')))
    else:
        send(session, Frame(0x19e, struct.pack('<II', fee, results[0]) + frame.payload[:12]))
    send(session, mod_list(*changes))
    send(session, gauge_frame(gauge))
    # licenses: this month's modify tries (GC_UpgradeThisMonth / LastMonth), parts enhanced to +10 .. +19 or higher
    await licenses.count_monthly(session, 'Upgrade', len(results))
    if gained and DESTROYED not in results:
        await licenses.count_many(session, [f'PartsEnhance{name}' for name, lv in ENHANCE_LEVELS if part.upgrade >= lv])
    if double:
        from .driftuse import USED, use_up
        from .items import bonus_update
        from .vshop import vs_mod_list
        await use_up(p, booster)
        send(session, vs_mod_list((booster, USED)))
        send(session, bonus_update(p))
    for f in stat_frames(p):
        send(session, f)
    return fee, results


@on(SVC, C2S, 0x1b3)
async def repair_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    src, add = struct.unpack_from('<II', frame.payload)
    part = next((i for i in p.items if i.inven_idx == src), None)
    kit = next((i for i in p.items if i.inven_idx == add), None)
    pinfo, kinfo = (info_of(part) if part else None), (info_of(kit) if kit else None)
    level = -part.upgrade if part and part.upgrade < 0 else 0
    fee = tables()[1].get((level, pinfo.grade if pinfo else ''), (0, 0))[1]
    if (not level or not kinfo or kinfo.kind not in ('repair', 'full_repair', 'new_repair')
            or GRADES[:3].find(pinfo.grade) != kinfo.value or fee > p.char.mito or not await add_money(p.char, -fee)):
        session.log.note(f'restore {part and part.item_id} ({part and part.upgrade}) with {kit and kit.item_id}: refused')
        return error(session, '20033')
    if kinfo.kind == 'repair':
        result, part.upgrade = REPAIR_ZERO, 0
    else:
        cap = FULL_REPAIR_CAP if kinfo.kind == 'full_repair' else (kinfo.time or level)
        result, part.upgrade = REPAIR_FULL, min(level, cap)
    await save_part(p, part)
    changes = [(part, CHANGED), await use_enhancers(p, kit, 1)]
    session.log.note(f'restore {pinfo.item_id} broken +{level} with {kinfo.item_id}: +{part.upgrade}, fee {fee}')
    send(session, Frame(0x1b4, struct.pack('<II', fee, result) + frame.payload[:8]))     # ack first (2008)
    send(session, mod_list(*changes))


@on(SVC, C2S, 0x19d)
async def upgrade_item(session, frame):
    await enhance(session, frame, False)


@on(SVC, C2S, 0x1ae)
async def upgrade_item_double(session, frame):
    await enhance(session, frame, True)
