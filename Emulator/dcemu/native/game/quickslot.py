"""The field quick slots (2011: 4 slots for usable items; the 2008 server had QUICKSLOT1 / QUICKSLOT2).

0x7d0 QuickSlotSave, C>S (26 bytes; client 0x7f5fa0 / 0x7f6110): u32 mode @0; mode 0: u32 TableIdx x 4 @4 (the
    four field slots, 0 = empty; sent by 0x571cc0 whenever they change), mode 1: u32 TableIdx @20 (a fifth slot,
    inventory +0x1b4, set from 0x5737d4; the client reads it back from nowhere we know, so it is not kept). No reply.
Restored at login: XiStrCharInfo @0xc5 / @0xc9 / @0xcd / @0xd1 (records.Character.encode); the 0x7c handler
    passes them to 0x71fc90, which finds each TableIdx in the inventory (usable items only, else the slot stays
    empty) and to 0x571c90 (the client's copy of what it last sent, so it does not send them back at once).
Kept in SKID_CHARACTER_TB.QUICKSLOT1 as "a,b,c,d" (varchar(32)); an older single number in QUICKSLOT1 /
QUICKSLOT2 is read as slots 1 / 2.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from .. import context
from .login import SVC

SAVE_SQL = "UPDATE SKID_CHARACTER_TB SET QUICKSLOT1=%s, QUICKSLOT2=NULL WHERE SERVERID=%s AND CID=%s"


def _num(text):
    text = (text or '').strip()
    return int(text) if text.isdigit() else 0


def quick_slots_of(qs1, qs2):
    """The 4 slots from the QUICKSLOT1 / QUICKSLOT2 columns."""
    if qs1 and ',' in qs1:
        slots = [_num(v) for v in qs1.split(',')[:4]]
    else:
        slots = [_num(qs1), _num(qs2)]
    return tuple(slots + [0] * (4 - len(slots)))


@on(SVC, C2S, 0x7d0)
async def save_quick_slots(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 20:
        return
    mode, *slots = struct.unpack_from('<5I', frame.payload)
    if mode != 0:
        return
    slots = tuple(v if v < 0x80000000 else 0 for v in slots)
    if slots == p.char.quick_slots:
        return
    p.char.quick_slots = slots
    db = context.db
    await db.execute(SAVE_SQL, (','.join(map(str, slots)), db.server_id, p.char.cid))
    session.log.note(f'quick slots {slots}')
