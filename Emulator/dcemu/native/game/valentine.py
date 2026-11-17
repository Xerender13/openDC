"""2016 client: the Valentine chocolate event ("Bring it to NPCs located at stations in each city!", the 2014 Happy
Valentine Chocolate 2013_valen_choco_success). Shown with the content flag Etc.EventValentainChocolate (2016 only).

Client (2016 exe): at a station NPC's dialog the give-chocolate button (control 0x86485, 0x5a66b8) takes the NPC's
key from the station window (0x79b350: its first field, a char string) and sends
  C>S 0xfb9 (sender 0x86b020, 0x101 bytes with the type): char[] the NPC key @2 (strcpy).
The answer
  S>C 0xfba ValentainChocolateReward (handler 0x540f20, 0x72 bytes): char[] the NPC key @2; the client finds the
      key in its Init/ValentainReward.xlt rows (0x770bc0: strcmp with the row's key) and shows that NPC's thanks
      dialog (its "Thanks Message", picture) in the station window.
ValentainReward.xlt (15 rows): Active, NPC Icon Index (post_1st_00052 ...: the key), Reward Group ID
(rw_2013_valentine_moon_01 ...), Event Message, Thanks Message, NPC Name, Image File Name.

Rules (ours: no server reference): the chocolate is taken (one 2013_valen_choco_success), the row's reward group
rolled and given as a gift box gives (driftuse.roll / give), then 0xfba; an inactive row, an unknown key or no
chocolate -> nothing given (text 20036 for no chocolate). 0xfb7 / 0xfb8 / 0xfbb (Cmd_ValentainChocolateCheat, a
GM test) are not answered.
"""
import os

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, error, send

CHOCOLATE = '2013_valen_choco_success'
ANSWER = 0x70                       # 0xfba body: char[0x70]
_rows = None


def rows():
    """ValentainReward.xlt -> {NPC key: (reward group, active)}."""
    global _rows
    if _rows is None:
        from ..data import read_xlt
        _rows = {}
        path = os.path.join(context.data.root, 'Init', 'ValentainReward.xlt')
        if os.path.exists(path):
            t = read_xlt(path)
            head = t[2] if len(t) > 2 else []
            col = {n.strip(): i for i, n in enumerate(head)}
            k, g, a = col.get('NPC Icon Index', 2), col.get('Reward Group ID', 3), col.get('Active', 1)
            for r in t[3:]:
                if len(r) > max(k, g) and r[k].strip():
                    _rows[r[k].strip()] = (r[g].strip(), r[a].strip() == '1')
    return _rows


@on(SVC, C2S, 0xfb9)
async def give_chocolate(session, frame):
    from ..version import is_2016
    from .alchemy import take_count
    from .driftuse import Gains, give, roll
    from .gotcha import prize_event
    from .items import mod_list
    p = session.state.get('player')
    from .. import events
    if not is_2016() or not p or not events.is_on('valentine'):     # emulator.ini [events] valentine
        return
    key = frame.payload.split(b'\0', 1)[0].decode('latin-1').strip()
    group, active = rows().get(key, ('', False))
    if not group or not active:
        session.log.note(f'valentine: unknown or inactive NPC {key!r}')
        return
    changes = await take_count(p, CHOCOLATE, 1)
    if not changes:
        return error(session, '20036')
    send(session, mod_list(*changes))
    won = roll(group)
    gains = Gains()
    await give(session, p, won, gains)
    gains.send(session, p)
    session.log.note(f'valentine: chocolate to {key!r}: {group} -> {won}')
    send(session, Frame(0xfba, key.encode('latin-1')[:ANSWER - 1].ljust(ANSWER, b'\0')))
    prize = prize_event(won)
    if prize:
        send(session, prize)
