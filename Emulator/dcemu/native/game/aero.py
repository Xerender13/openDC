"""Aero kit Mk.2 (VisualItem category 6, value "mk2...", e.g. pc_AeroMK2+ "AeroMK2+": "Equip to distribute the 2 option
types and 60 points.").

The item's text (ITEM_DATA, the 2011 plate text) is 10 reserved characters + what the shop wrote (car type, style, ...;
bought: "          142120012"). The client offers its Mk.2 window ([ui + 0x3b4], 0x55bfd0) from the drift inventory only
while the text is empty or starts with a space (client 0x5fff8d): the distribution is kept in those 10 characters.

0x4bd SetAeroStats (u32 InvenIdx, u16 points x4, u16 option x2; sender 0x7f7020 from the window 0x55c230: the four values
    add up to GlobalContent MK2_StatSum_* (60 for the AeroSet), each option 1-4 from a group of four buttons)
    -> 0x4be SetAeroStatsAck (u32 InvenIdx, u32 result: 1 = the client's "Custom Aeroset Setting completed", 11064),
    the item again (0x4b2) with the text "PPPPPPPPOO" + the rest, the stats.
Points: speed, acceleration, durability, booster in the window's order (a guess: the window's rows are not labelled in
the US layout we read); added to the equip stats while the item is on the current car (player.stats). The options are
stored; what they select is not known yet (the shop's style pictures Pc_Aero_Atype.. suggest the look).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send

MAX_POINTS = 60
# The window's tick boxes (layout 3470000, picture 3,452~737,931_ui_contents53.dds): option 1 = "For Battle Zone Only"
# box 1-4 (ID_AEROSET_ETC_OPTION1..4), option 2 = "Field or Undercity Only" box 1-4 (ID_AEROSET_FIELD_OPTION1..4); 0 =
# none (the window enables only one group for bumpers / intercoolers). They are these assists (Assist_Client.tdf):
BATTLE_OPTIONS = ('a_00179', 'a_00180', 'a_00181', 'a_00182')  # booster +10% on traffic crash, recharge +25%,
                                                               # 5% full booster on crash, 10% full repair on crash
FIELD_OPTIONS = ('a_00183', 'a_00184', 'a_00185', 'a_00186')   # HUV damage +20, 10% full booster on crash,
                                                               # recharge +100%, 5% full booster after use
POINT_STATS = (0, 2, 1, 3)       # window order -> stat index (speed, crash, accel, boost): speed, accel, crash, boost


def is_mk2(v):
    vis = context.data.visuals.get(v.table_idx)
    return bool(vis and vis.category == 6 and (vis.value or '').lower().startswith('mk2'))


def mk2_points(v):
    """-> (speed, crash, accel, boost) points distributed on an Aero kit Mk.2, or () when not set."""
    text = v.data or ''
    if not is_mk2(v) or len(text) < 10 or not text[:10].isdigit():
        return ()
    raw = [int(text[2 * k:2 * k + 2]) for k in range(4)]
    out = [0, 0, 0, 0]
    for k, n in enumerate(raw):
        out[POINT_STATS[k]] = n
    return tuple(out)


def mk2_assists(v):
    """-> the assist ids of an Aero kit Mk.2's ticked options (sent in the item record's assist slots, which the client
    lists in the tooltip and applies for an item on the current car)."""
    text = v.data or ''
    if not is_mk2(v) or len(text) < 10 or not text[:10].isdigit():
        return []
    out = []
    for digit, table in ((text[8], BATTLE_OPTIONS), (text[9], FIELD_OPTIONS)):
        n = int(digit)
        if 1 <= n <= len(table):
            out.append(table[n - 1])
    return out


@on(SVC, C2S, 0x4bd)
async def set_aero_stats(session, frame):
    from .vshop import CHANGED, after_change, vs_mod_list
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return
    inven, = struct.unpack_from('<I', frame.payload)
    points = struct.unpack_from('<4H', frame.payload, 4)
    options = struct.unpack_from('<2H', frame.payload, 12)
    v = next((x for x in p.vsitems if x.inven_idx == inven and x.state != 4), None)
    text = (v.data or '') if v else ''
    session.log.note(f'set aero stats {inven}: points {points}, options {options}, text {text!r}')
    if (not v or not is_mk2(v) or sum(points) > MAX_POINTS or any(n > 99 for n in points)
            or not all(0 <= o <= 4 for o in options) or (text and not text.startswith(' '))):
        send(session, Frame(0x4be, struct.pack('<Ii', inven, 0)))
        return error(session, '20036')
    v.data = (''.join(f'{n:02}' for n in points) + ''.join(str(o) for o in options) + text[10:])[:20]
    db = context.db
    await db.execute("UPDATE SKID_VSITEM_TB SET ITEM_DATA=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                     (v.data, db.server_id, p.char.cid, inven))
    send(session, Frame(0x4be, struct.pack('<Ii', inven, 1)))
    send(session, vs_mod_list((v, CHANGED)))
    car = next((c for c in p.char.cars if c.car_id == v.car_id), None)
    after_change(session, p, car)
