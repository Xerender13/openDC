"""Welcome / welcome-back promotion (2016: 0xaa DormantEvent; SIZED_PROTOCOL section 2; emulator.ini [promotion]).

0xaa (2016 handler 0x52adc0, 94 bytes; 2011 6): u32 selector @2, then (selector 4 only) two narrow C strings, 32 bytes
@6 and 56 bytes @0x26. Each selector sets one flag that a UI tick (0x523af1) turns into a panel:
    0  returning ("dormant") player: GlobalText 11283 "Wow! It's been a while to see you, $name! ... various equipment
       for returning drivers" (panel 0x10)
    1  new player: 11282 "Welcome to Mitron Island, $name!! ... various equipment for new drivers" (panel 0x17)
    2  event: 11386 (panel 0x1b);  3 nothing;  4 the text key in string A (panel 0x29)
The texts promise equipment, which the client does not give: the server does, here a RewardGroup.xlt group
([promotion] new_reward / dormant_reward, given as dcgp.give_group gives). The 2008 server pushed the bare message;
who counts as dormant is a server rule (ours): no login for [promotion] dormant_days. Logins are kept in
SKID_PLAYMODE_TB MODEID 'LOGIN' (LASTDATE, UTC) because nothing keeps the character's own LASTDATE. A character
without that row is "new" only while it is level 1 without EXP; older characters just get the row (turning the
feature on does not greet everyone). Not yet tried in game.
"""
import struct

from ...wire import Frame
from .. import context

MODE = 'LOGIN'
DORMANT, NEW, EVENT, CUSTOM = 0, 1, 2, 4
SIZE = 94
SINCE_SQL = ("SELECT extract(epoch FROM GETUTCDATE() - LASTDATE)::bigint FROM SKID_PLAYMODE_TB"
             " WHERE SERVERID=%s AND CID=%s AND MODEID=%s")
SAVE_SQL = ("UPDATE SKID_PLAYMODE_TB SET LASTDATE=GETUTCDATE(), TRYCNT=TRYCNT+1 WHERE SERVERID=%s AND CID=%s"
            " AND MODEID=%s",
            "INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT,"
            " PLAYTIME, NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GETUTCDATE(),GETUTCDATE(),"
            "1,0,0,0,0,0,0,0,%s)")


def frame(selector, key=b'', extra=b''):
    """0xaa: the selector, then string A (32) and B (56) for selector 4 -> 94 bytes."""
    return Frame(0xaa, struct.pack('<I', selector) + key[:31].ljust(32, b'\0') + extra[:55].ljust(56, b'\0'))


def which(seconds_since, level, exp, dormant_days):
    """The selector for a login (None: no popup). seconds_since: since the last login, None when never seen."""
    if seconds_since is None:
        return NEW if level <= 1 and not exp else None
    if dormant_days > 0 and seconds_since >= dormant_days * 86400:
        return DORMANT
    return None


async def on_login(session):
    """At the character load (login.load_char, 2016): greet and give, then note the login."""
    from ..version import is_2016
    cfg = context.promotion
    p = session.state.get('player')
    if not is_2016() or not cfg.get('enabled') or not p:
        return
    db, c = context.db, p.char
    r = await db.row(SINCE_SQL, (db.server_id, c.cid, MODE))
    since = int(r[0]) if r and r[0] is not None else None
    selector = which(since, c.level, c.exp, cfg.get('dormant_days', 30))
    await db.update_or_insert(SAVE_SQL[0], (db.server_id, c.cid, MODE),
                              SAVE_SQL[1], (db.server_id, c.cid, c.name, MODE, c.member))
    if selector is None:
        return
    from .login import send
    group = cfg.get('new_reward' if selector == NEW else 'dormant_reward', '')
    given = []
    if group:
        from .dcgp import give_group
        gains, given = await give_group(session, p, group)
        if gains and gains.items:
            from .items import mod_list
            send(session, mod_list(*gains.items))
    send(session, frame(selector))
    session.log.note(f'promotion: {"new" if selector == NEW else "returning"} player'
                     + (f' ({since // 86400} days away)' if since is not None else '')
                     + f', group {group!r}: {[i[0].name for i in given]}')
