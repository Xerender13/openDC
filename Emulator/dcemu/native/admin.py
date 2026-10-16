"""Kick, block and ban, as the 2008 server has them (its GM console commands "kick" / "block",
GM_Kick_Player 0x688620, GM_Block_Player 0x688450, and the checks in Cmd_LoadChar 0x6178xx).

  kick       the player gets "Kicked by a GM." (0x0001) and every connection of the account is closed
             (game, lobby, area, barea). With days > 0 the character is also blocked from the game:
  game block SKID_CHARACTER_TB.BLOCKGAMEDATE = now + days (BS_GameDB::BlockGame). LoadChar of a blocked
             character answers error 20089 "This character cannot be used in the game." and loads nothing.
  chat block SKID_CHARACTER_TB.BLOCKCHATDATE = now + time (BS_GameDB::BlockChat) and 0x9c4 ChatBlock
             (bool blocked, long until: time_t) to the player, also sent at LoadChar while it lasts; the
             client stops its own chat (handler 0x5184b0), and the game service drops what still comes.
  ban        the account: MEUSERMT.VALID = 'n' (getAccInfo's check). Login answers 12 "account blocked"
             (native/auth.py), the lobby and game check-ins refuse it, and whoever is online is kicked.
  duplicate login (Cmd_LoadChar): the connection that already plays the character gets "Disconnecting
             by another login!" and is closed, the new one error 20088 and has to try again.

Used by the GM commands typed in chat (game/misc.py: gmkick, gmblock, gmunblock, gmchatblock, gmban,
gmunban, gmwho) and by the control port (emulator.ini [emulator] control_port, tools/gmctl.py), which
takes the same commands without the "gm" prefix, one line per connection.
"""
import struct

from ..proxy import live
from ..wire import Frame
from . import context, now

KICK_TEXT = 'Kicked by a GM.'
DUPLICATE_TEXT = 'Disconnecting by another login!'
BLOCK_GAME_SQL = "UPDATE SKID_CHARACTER_TB SET BLOCKGAMEDATE=GetDate()+%s WHERE SERVERID=%s AND UCNAME=UPPER(%s) AND STATE <> 'D'"
BLOCK_CHAT_SQL = "UPDATE SKID_CHARACTER_TB SET BLOCKCHATDATE=GetDate()+%s WHERE SERVERID=%s AND UCNAME=UPPER(%s) AND STATE <> 'D'"
CLEAR_SQL = "UPDATE SKID_CHARACTER_TB SET {}=NULL WHERE SERVERID=%s AND UCNAME=UPPER(%s) AND STATE <> 'D'"
BLOCKS_SQL = """SELECT CASE WHEN BLOCKGAMEDATE > GetDate() THEN 1 ELSE 0 END,
    CASE WHEN BLOCKCHATDATE > GetDate() THEN DATEDIFF(second, GetDate(), BLOCKCHATDATE) ELSE 0 END
  FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND CID=%s"""
CHAR_SQL = "SELECT CNAME, MEMBERID FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND UCNAME=UPPER(%s) AND STATE IN ('P', 'R')"
VALID_SQL = "SELECT VALID FROM MEUSERMT WHERE MEMBERID=%s"
SET_VALID_SQL = "SET NOCOUNT ON; UPDATE MEUSERMT SET VALID=%s WHERE MEMBERID=%s; SELECT @@ROWCOUNT"


def message(session, text):
    """0x0001 with a text of our own (Send_Error's layout)."""
    data = text.encode('utf-16-le') + b'\0\0'
    session.to_client(Frame(0x0001, struct.pack('<H', len(data)) + data))


def player_of(session):
    return session.state.get('player') if session.service == 'game' else None


def find(name):
    """The game session playing the character with this name, or None."""
    name = name.lower()
    return next((s for s in list(live.values()) if player_of(s) and player_of(s).char.name.lower() == name), None)


def connections(member=None, names=()):
    """Every open connection of an account (game, lobby: by the account they checked in with) and of
    its characters (area, barea: by the car's name)."""
    member = (member or '').lower()
    names = {n.lower() for n in names}
    out = []
    for s in list(live.values()):
        car = s.state.get('car')
        p = player_of(s)
        if member and (s.state.get('member') or '').lower() == member \
                or p and p.char.name.lower() in names \
                or car and s.service != 'game' and car.name.lower() in names:
            out.append(s)
    return out


def drop(session, text=None, account=True):
    """Close a player's game connection and what belongs to it: its area connections, and with
    `account` every other connection of the account (not for a duplicate login: the new connection
    is the same account's)."""
    p = player_of(session)
    if text:
        message(session, text)
    member = session.state.get('member') if account else None
    for s in {session, *connections(member, [p.char.name] if p else [])}:
        s.log.note('closed by the server' + (f': {text}' if text else ''))
        s.close()


async def account_valid(member):
    """getAccInfo's VALID check; an account without a row is not valid."""
    r = await context.db.row(VALID_SQL, (member,))
    return bool(r) and (r[0] or 'y').strip().lower() == 'y'


async def blocks(cid):
    """-> (blocked from the game, chat blocked until: time_t on the server clock, or 0)."""
    db = context.db
    r = await db.row(BLOCKS_SQL, (db.server_id, cid))
    if not r:
        return False, 0
    return bool(r[0]), now() + int(r[1]) if r[1] else 0


def chat_block_frame(until):
    return Frame(0x9c4, struct.pack('<?i', until > now(), until))


async def kick(name, days=0.0):
    """-> True if the character was online (or got a game block)."""
    db = context.db
    s = find(name)
    if days > 0:
        await db.execute(BLOCK_GAME_SQL, (float(days), db.server_id, name))
    if s:
        drop(s, KICK_TEXT)
    return bool(s) or days > 0 and bool(await db.row(CHAR_SQL, (db.server_id, name)))


async def block_game(name, days):
    db = context.db
    if not await db.row(CHAR_SQL, (db.server_id, name)):
        return False
    if days > 0:
        return await kick(name, days)
    await db.execute(CLEAR_SQL.format('BLOCKGAMEDATE'), (db.server_id, name))
    return True


async def block_chat(name, minutes):
    db = context.db
    if not await db.row(CHAR_SQL, (db.server_id, name)):
        return False
    if minutes > 0:
        await db.execute(BLOCK_CHAT_SQL, (minutes / 1440.0, db.server_id, name))
    else:
        await db.execute(CLEAR_SQL.format('BLOCKCHATDATE'), (db.server_id, name))
    s = find(name)
    if s:
        until = now() + int(minutes * 60) if minutes > 0 else 0
        s.state['chat_block'] = until
        s.to_client(chat_block_frame(until))
    return True


async def ban(account, valid=False):
    """account: an account ID, or the name of one of its characters. -> the account, or None."""
    db = context.db
    r = await db.row(SET_VALID_SQL, ('y' if valid else 'n', account))
    if not (r and r[0]):
        c = await db.row(CHAR_SQL, (db.server_id, account))
        if not c or c[1].startswith('$'):
            return None
        account = c[1]
        await db.execute(SET_VALID_SQL, ('y' if valid else 'n', account))
    if not valid:
        for s in connections(account):
            if player_of(s):
                drop(s, KICK_TEXT)
            else:
                s.close()
    return account


def who():
    return [f'{p.char.name} (account {s.state.get("member")}, level {p.char.level}, '
            f'{s.client_w.get_extra_info("peername")[0]})'
            for s in list(live.values()) if (p := player_of(s))]


def _num(args, k, default):
    try:
        return float(args[k])
    except (IndexError, ValueError):
        return default


async def command(cmd, args):
    """One GM command -> (done, text). kick NAME [days] | block NAME days | unblock NAME |
    chatblock NAME minutes (0 lifts it) | ban ACCOUNT-or-NAME | unban ACCOUNT-or-NAME | who |
    item NAME ITEM-ID [count] (as the chat command gmitem) | drift NAME DRIFT-ITEM-ID [days] (as gmdrift; 0 days
    = for good); both for a character online | realmatch open | close | in MINUTES | auto | status"""
    if cmd == 'who':
        names = who()
        return True, f'{len(names)} online' + ''.join('\n  ' + n for n in names)
    if cmd == 'realmatch':
        from .game.rooms import gm_realmatch
        return True, gm_realmatch(args)
    if not args:
        return False, 'a name is needed'
    name = args[0]
    if cmd == 'kick':
        ok = await kick(name, _num(args, 1, 0.0))
    elif cmd == 'block':
        ok = await block_game(name, _num(args, 1, 1.0))
    elif cmd == 'unblock':
        ok = await block_game(name, 0)
    elif cmd == 'chatblock':
        ok = await block_chat(name, _num(args, 1, 10.0))
    elif cmd == 'item':
        from .game.misc import gm
        ok = len(args) >= 2 and await gm(None, 'gmitem', args)
    elif cmd == 'drift':
        session = find(name)
        if not session or len(args) < 2 or args[1] not in context.data.visual_index:
            return False, f'drift {name}: not online, or no drift item {args[1:2]}'
        from .game.driftuse import Gains, give_drift_item
        from .game.items import bonus_update
        from .game.login import send
        p, gains = player_of(session), Gains()
        await give_drift_item(p, args[1], int(_num(args, 2, 0)), gains, session)
        gains.send(session, p)
        send(session, bonus_update(p))
        ok = True
    elif cmd in ('ban', 'unban'):
        account = await ban(name, valid=cmd == 'unban')
        return bool(account), f'{cmd} account {account}' if account else f'no account or character {name!r}'
    else:
        return False, f'unknown command {cmd!r} (kick, block, unblock, chatblock, ban, unban, who, item, drift, realmatch)'
    return ok, f'{cmd} {name}: {"done" if ok else "no such character, or not online"}'


async def control(reader, writer):
    """The control port: one command line, one reply."""
    try:
        words = (await reader.readline()).decode('utf-8', 'replace').split()
        ok, text = await command(words[0].lower(), words[1:]) if words else (False, 'empty command')
        print(f'control: {" ".join(words)!r} -> {text}', flush=True)
        writer.write((('OK ' if ok else 'FAILED ') + text + '\n').encode('utf-8'))
        await writer.drain()
    except Exception as e:                      # a bad command must not hurt the server
        writer.write(f'FAILED {e}\n'.encode('utf-8'))
    finally:
        writer.close()
