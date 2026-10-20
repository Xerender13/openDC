"""2016 Part Option Extractor: moves a part's two converting options (convert.py) to another part.

Items (UseItemClient): i_n_assist_transfer (kind atransfer, client use code 0x6b; column 4 names the form it turns
into) and i_n_assist_transfer_used (atransfer_used): the used extractor holds the options in its own assist slots
(SKID_ITEM_TB ASSIST_A / ASSIST_B, sent @0x10 / @0x14 like a converted part). Both have a 720 h period (column 12).
Texts 12809 (KR "move the part's 변형옵션 [converting options] to the extractor?") and 12810 ("Current option will
be discarded. Do you want to replace it with Extractor Option?").

Client (2016 exe): using the extractor on a part in the inventory 0x6355b0 refuses an expired extractor (0x785200:
ExpireTick, text 10795), a part on a car (state & 0xf == 1, text 12811) and a part 0x62e980 does not take (parts;
option parts instead when Main.OptionItem is on: text 12812); then confirm 12809 (a fresh extractor, 0x62d7c0:
use code 0x6b) or 12810 (the used one); callback 0x62dca0 -> sender 0x86b6e0:
0xfc1 AssistTransferUse (u32 part InvenIdx @2, u32 extractor InvenIdx @6, u8 1 fresh / 0 used @0xa)
    -> 0xfc2 AssistTransferUseAck (u16 result; handler 0x52d5f0: 0 nothing shown, 1 text 12812, 2 / 3 text 12811,
    13 text 10795) and 0x192 with the changed items.
Server rules (no 2016 server to compare): extracting takes both options off the part (it becomes tradeable again,
as convert does for the untiered rows) and one fresh extractor; the used extractor is a new item with the options
and the fresh one's expiry. Applying replaces the part's options (the convert binding: tiers 1-4 untradeable)
and uses the extractor up. Parts as convert takes them: no set parts, docking parts or broken parts.
Main.AssistTransferBelongLevel (flags +0x10 bits 0-3) is not read by the client code found; not used.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from ..version import is_2016
from .convert import ASSIST_SQL, UNTRADEABLE_ROWS, tier_of
from .items import CHANGED, NEW, REMOVED, info_of, mod_list, new_item
from .login import SVC, send

OK, NOT_VALID, EQUIPPED, EXPIRED = 0, 1, 2, 13
FRESH, USED = 'atransfer', 'atransfer_used'
EXPIRE_SQL = "UPDATE SKID_ITEM_TB SET CTIME=%s WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s"


def takes(part):
    """A part the extractor works on (client 0x62e980; convert's own limits)."""
    info = info_of(part)
    if not info or part.item_id.startswith(('si_', 'dock_')) or part.upgrade < 0 or (part.state & 0xffff) == 4:
        return False
    if context.option_parts:
        return info.kind.startswith('op_')
    return info.type in (0, 1, 2, 3)


def answer(session, result, *changes):
    send(session, Frame(0xfc2, struct.pack('<H', result)))
    if changes:
        send(session, mod_list(*changes))


@on(SVC, C2S, 0xfc1)
async def transfer(session, frame):
    p = session.state.get('player')
    if not is_2016() or not p or len(frame.payload) < 9:
        return
    part_idx, tool_idx, fresh = struct.unpack_from('<IIB', frame.payload)
    part = next((i for i in p.items if i.inven_idx == part_idx), None)
    tool = next((i for i in p.items if i.inven_idx == tool_idx), None)
    tinfo = info_of(tool) if tool else None
    if not part or not tinfo or tinfo.kind not in (FRESH, USED) or tool.stack < 1 or not takes(part):
        return answer(session, NOT_VALID)
    if part.car_id or (part.state & 0xf) == 1:
        return answer(session, EQUIPPED)
    from .setparts import expired
    if expired(p, tool):
        return answer(session, EXPIRED)
    db = context.db
    from .upgrade import use_enhancers
    if tinfo.kind == FRESH:
        if not (part.assist_a or '').strip():
            return answer(session, NOT_VALID)               # nothing to extract
        t = context.data
        used_id = tinfo.extra or 'i_n_assist_transfer_used'
        if used_id not in t.item_index:
            return answer(session, NOT_VALID)
        options = part.assist_a, part.assist_b
        holder = await new_item(p, t.item_info(t.item_index[used_id]), 1)
        holder.assist_a, holder.assist_b = options
        await db.execute(ASSIST_SQL, (*options, 0, db.server_id, p.char.cid, holder.inven_idx))
        if tool.ctime and holder.ctime != tool.ctime:       # the fresh extractor's expiry goes on
            holder.ctime = tool.ctime
            await db.execute(EXPIRE_SQL, (holder.ctime, db.server_id, p.char.cid, holder.inven_idx))
        part.assist_a = part.assist_b = ''
        part.belonging = 0
        await db.execute(ASSIST_SQL, ('', '', 0, db.server_id, p.char.cid, part.inven_idx))
        spent = await use_enhancers(p, tool, 1)
        session.log.note(f'option extractor: {options[0]} + {options[1]} from {part.item_id} -> {used_id}')
        return answer(session, OK, (part, CHANGED), spent, (holder, NEW))
    if not (tool.assist_a or '').strip():
        return answer(session, NOT_VALID)                   # a used extractor without options
    part.assist_a, part.assist_b = tool.assist_a, tool.assist_b
    part.belonging = 1 if 0 <= tier_of(part) < UNTRADEABLE_ROWS else 0
    await db.execute(ASSIST_SQL, (part.assist_a, part.assist_b, part.belonging, db.server_id, p.char.cid,
                                  part.inven_idx))
    await db.execute("DELETE FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s",
                     (db.server_id, p.char.cid, tool.inven_idx))
    p.items.remove(tool)
    session.log.note(f'option extractor: {part.assist_a} + {part.assist_b} onto {part.item_id}'
                     + (' (untradeable)' if part.belonging else ''))
    answer(session, OK, (part, CHANGED), (tool, REMOVED))
