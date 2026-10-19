"""Account administration for the loopback GM console / desktop editor.

Passwords use the existing client's MD5 format and are never returned or logged.
Account creation and resets are explicit commands, not login workarounds.
"""
import hashlib
import json
from . import context
from . import admin

COMMANDS = {'accounts','account','account-create','account-password','account-role'}
SECRET_COMMANDS = {'account-create','account-password'}


def encoded(value):
    return True, json.dumps(value,ensure_ascii=False,default=str)


async def command(cmd,args):
    db=context.db
    if cmd=='accounts':
        query=' '.join(args)
        rows=await db.rows("""SELECT TOP 300 MEMBERID, VALID, JOINDATE FROM MEUSERMT
            WHERE MEMBERID LIKE %s ORDER BY MEMBERID""",('%'+query+'%',))
        return encoded([dict(zip(('account','valid','joined'),r)) for r in rows])
    if not args:
        return False,'account ID required'
    member=args[0]
    r=await db.row('SELECT MEMBERID, VALID, JOINDATE FROM MEUSERMT WHERE MEMBERID=%s',(member,))
    if cmd=='account-create':
        from .auth import REGISTER_ID
        if not REGISTER_ID.fullmatch(member) or len(args)!=2 or not args[1] or len(args[1].encode('utf-8'))>63:
            return False,'usage: account-create ID PASSWORD (ID: 1-32 letters/digits/_.-; password: 1-63 UTF-8 bytes, no spaces)'
        if r:
            return False,'account already exists'
        await db.execute("INSERT INTO MEUSERMT (MEMBERID,PASSWORD,VALID,JOINDATE) VALUES (%s,%s,'y',GETDATE())",
                         (member,hashlib.md5(args[1].encode('utf-8')).hexdigest()))
        return True,'account created'
    if not r:
        return False,'no such account'
    if cmd=='account':
        chars=await db.rows("""SELECT CID,CNAME,NLEVEL,GOLD,PTYPE,STATE FROM SKID_CHARACTER_TB
            WHERE SERVERID=%s AND MEMBERID=%s ORDER BY CID""",(db.server_id,member))
        coin=await db.row('SELECT COIN FROM SKID_UNALISCOIN_TB WHERE MEMBERID=%s',(member,))
        result=dict(zip(('account','valid','joined'),r))
        result['coins']=int(coin[0] or 0) if coin else 0
        result['characters']=[dict(zip(('cid','name','level','mito','role','state'),c)) for c in chars]
        for c in result['characters']:
            c['online']=bool(admin.find(c['name']))
        return encoded(result)
    # Check the account's lobby as well as its game session before changing credentials/roles.
    if admin.connections(member):
        return False,'account must be fully offline (exit the game and lobby first)'
    if cmd=='account-password':
        if len(args)!=2 or not args[1] or len(args[1].encode('utf-8'))>63:
            return False,'password must be 1-63 UTF-8 bytes with no spaces'
        await db.execute('UPDATE MEUSERMT SET PASSWORD=%s WHERE MEMBERID=%s',
                         (hashlib.md5(args[1].encode('utf-8')).hexdigest(),member))
        return True,'password reset'
    if cmd=='account-role':
        if len(args)!=2 or args[1] not in ('A','N'):
            return False,'role must be A (GM) or N (normal)'
        # The emulator also accepts adminlist.txt; do not imply revocation when it overrides PTYPE.
        if args[1]=='N' and member.lower() in {a.lower() for a in context.data.admins}:
            return False,'account is also in server_data/adminlist.txt; remove that entry to revoke GM access'
        await db.execute("UPDATE SKID_CHARACTER_TB SET PTYPE=%s WHERE SERVERID=%s AND MEMBERID=%s AND STATE<>'D'",
                         (args[1],db.server_id,member))
        return True,'role updated for existing characters (new characters use their default role)'
    return False,'unknown account command'
