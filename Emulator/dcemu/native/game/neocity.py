"""Neo City (2016): the player car's durability/HP, the first piece of that mode (docs/NEOCITY.md).

Neo City is the chapter-dungeon region where the player's car has HP that only that mode uses (Korean sources:
namu.wiki 스키드러쉬/게임 모드 1.9). The client syncs it about once a second:

C>S 0xf4d (6 bytes; sender wrapper 0x866270, one u32) -> S>C 0xf4e (6 bytes; handler 0x53e630):
    the client sends its **XOR base** (observed constant 0x111a); the answer is one u32, `base ^ hp`.
    The handler first tests [player+0x198] (the Neo mode flag) and does nothing when it is 0, then accepts only
    0 < hp <= 0x4e20 (20000, 0x53e663) and stores [player+0x1da4] = [player+0x1da0] ^ value (0x760910);
    anything else prints "Receive HP : %d" (format string 0x956c90).

Ours: every character starts at full HP (the client's own 20000 ceiling) and nothing damages it yet — the enemies
(spider HUS, scout HUB, armed HUV, turrets) are server-side and not implemented, so full HP is the correct answer
until they are. damage()/heal() are here so the combat work has one place to call.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, send

MAX_HP = 20000                      # the client's own bound on the answer (0x53e663)
_hp = {}                            # (server id, cid) -> current HP; absent = full


def is_on():
    from ..version import is_2016
    return is_2016()


def _key(session):
    p = session.state.get('player')
    return (context.db.server_id, p.char.cid) if p else None


def hp_of(session):
    key = _key(session)
    return _hp.get(key, MAX_HP) if key else MAX_HP


def set_hp(session, hp):
    key = _key(session)
    if key:
        _hp[key] = max(0, min(MAX_HP, int(hp)))


def damage(session, amount):
    """The car takes `amount`; -> the HP left. For the Neo City enemies when they exist."""
    left = max(0, hp_of(session) - max(0, int(amount)))
    set_hp(session, left)
    return left


def heal(session, amount):
    left = min(MAX_HP, hp_of(session) + max(0, int(amount)))
    set_hp(session, left)
    return left


@on(SVC, C2S, 0xf4d)
async def hp_sync(session, frame):
    """The client's HP poll: answer `base ^ hp` (only the 2016 client sends it)."""
    if not is_on() or len(frame.payload) < 4:
        return
    base, = struct.unpack_from('<I', frame.payload)
    send(session, Frame(0xf4e, struct.pack('<I', (base ^ (hp_of(session) & 0xffffffff)) & 0xffffffff)))
