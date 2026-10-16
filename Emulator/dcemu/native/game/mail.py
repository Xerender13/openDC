"""Messages (the Communication Zone's Messages tab): SKID_MSG_TB, as the 2008 server (BS_GameDB::SelectMessage /
InsertMessage / ModifyMessage / DeleteMessage), with the 2011 client's new requests.

0x86 GetMail (no body; the client asks after entering the game) -> one 0x84 MailContent per message.
0x84 MailContent, 2011 (client 0x521d40; at least 252 bytes; offsets with the 2-byte type): i64 mid @2, i64
    sender cid @0xa, i64 receiver cid @0x12, wchar[21] sender name @0x1a, u32 send time (time_t; the client
    shows it with localtime) @0x44, u32 @0x48 (unknown, 0), u32 kind @0x4c, char state @0x50, wchar[21] subject
    @0x54, i64 Mito @0x7e, char[101] item @0x86, i32 text length @0xeb, the text (wide) @0xef; the message
    takes 0xef + 2 x length bytes and is ignored when the text is empty (a space is sent then).
    Kind (low word) 0 = a player's message: it goes to the kept list for state 'K', else to the inbox ('N' new,
    'R' read). The other kinds are the old pop-up notices (100, 400, 500 Mito, 800: the queue at 0x9506b4,
    answered by the client with 0x85 MailSet), not used here; 300 = a drift shop gift waiting (gifts.py: the
    client's gift list, not the inbox).
0x85 MailSet (i64 mid, i32 cmd; 2008 Cmd_MailSet): cmd 1 = read.
0x5c8 ReadMail / 0x5ca DeleteMail / 0x5cc KeepMail (i64 mid) -> 0x5c9 / 0x5cb / 0x5cd (u32 result 1, i64 mid;
    client 0x523630 / 0x523720 / 0x523800): the state becomes 'R' / the row is deleted / 'K'.
0x5ce SendMail (668 bytes: wchar[21] receiver @2, wchar[300] text @0x2c, u32 item count @0x284, u32 item
    InvenIdx @0x288, four more u32 (every sender in this client pushes 0); client 0x7f35a0: the gift dialog 0x69eee9, the gift box 0x6be554 and the chat
    command "/쪽지보내기 name text inven" 0x5e6cbe) -> 0x5cf SendMailAck (wchar[21] receiver @2, i32 result @0x2c:
    1 = sent (text 11033), 0 = 11038 "%s does not exist.", -2 = 11034 "This item cannot be sent as an
    attachment.", others 11035 "%s cannot receive any messages at this time."; i32 Mito @0x30 the client takes off
    its money: the fee, emulator.ini [mail] fee; client 0x5191d0), 0x192 for an item sent, and 0x84 to the receiver when in the game.
0x5d0 GetMailItem (i64 mid, u32 0) -> 0x192 / 0x8a (the item / the Mito), 0x5d1 GetMailItemAck (i32 result >= 0,
    i64 mid, char[101] the message's item text from now on: empty; client 0x523900).
The item text is the 2008 server's item string (XiItemTable::ItemStinrg2Param: "%s %d %d %d %d %s %s %s %d";
only the id's place is certain): here id, count, random bonus, enhancement level, box, the two convert options
(NONE when empty), NONE, belonging; an item received is made again from it (a boxed part stays boxed). Items on a
car, bound or broken are not sent, nor hyper parts / untradeable items without a Parts Box (sendable; the Auction
House's rule, user 2026-10-14; no reference for the official mail rules).
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context
from .items import DELETE_SQL, NEW, REMOVED, CHANGED, STACK_SQL, add_money, info_of, mod_list, new_item, stack_for
from .login import SVC, error, send, stat_frames
from .records import wstr

NAME = 42                           # wchar[21]
TEXT_MAX = 200                      # SKID_MSG_TB.CONTENT
SELECT = ("SELECT MID, SENDER_ID, SNAME, MSGKIND, MSGSTATE, SUBJECT, CONTENT, GOLD, ITEM, SENDDATE FROM SKID_MSG_TB"
          " WHERE SERVERID=%s AND RECEIVER_ID=%s")
INSERT = ("SET NOCOUNT ON; INSERT INTO SKID_MSG_TB(SERVERID, RECEIVER_ID, SENDER_ID, SNAME, MSGKIND, MSGSTATE, SUBJECT,"
          " CONTENT, GOLD, ITEM, SENDDATE) OUTPUT INSERTED.MID VALUES (%s, %s, %s, %s, %s, 'N', %s, %s, %s, %s, GetDate())")
STATE = "UPDATE SKID_MSG_TB SET MSGSTATE=%s WHERE SERVERID=%s AND RECEIVER_ID=%s AND MID=%s"
DELETE = "DELETE FROM SKID_MSG_TB WHERE SERVERID=%s AND RECEIVER_ID=%s AND MID=%s"
TAKEN = "UPDATE SKID_MSG_TB SET GOLD=0, ITEM='' WHERE SERVERID=%s AND RECEIVER_ID=%s AND MID=%s"
RECEIVER = "SELECT CID, CNAME FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND UCNAME=UPPER(%s) AND STATE='P'"
PROPS = ("UPDATE SKID_ITEM_TB SET NRANDOM=%s, NUPGRADE=%s, BOX=%s, ASSIST_A=%s, ASSIST_B=%s, BELONGING=%s"
         " WHERE SERVERID=%s AND CID=%s AND INVENIDX=%s")


def content(mid, sender, receiver, sname, kind, state, subject, text, gold, item, sent):
    text = (text or '')[:TEXT_MAX] or ' '
    when = int(sent.timestamp()) if sent else 0
    return Frame(0x84, struct.pack('<qqq', mid, sender, receiver) + wstr(sname, NAME)
                 + struct.pack('<III', when, 0, kind) + ((state or 'N')[:1].encode('latin-1', 'replace') or b'N')
                 + bytes(3) + wstr(subject, NAME) + struct.pack('<q', gold)
                 + (item or '').encode('latin-1', 'replace')[:100].ljust(101, b'\0')
                 + struct.pack('<i', len(text) + 1) + (text + '\0').encode('utf-16-le'))


def row_frame(cid, r):
    return content(int(r[0]), int(r[1] or 0), cid, (r[2] or '').strip(), int(r[3] or 0), (r[4] or 'N').strip(),
                   (r[5] or '').strip(), r[6] or '', int(r[7] or 0), (r[8] or '').strip(), r[9])


async def mail_row(p, mid):
    db = context.db
    return await db.row(SELECT + " AND MID=%s", (db.server_id, p.char.cid, mid))


@on(SVC, C2S, 0x86)
async def get_mail(session, frame):
    p = session.state.get('player')
    if not p:
        return
    db = context.db
    session.state['in_game'] = True                 # (asked once the game screen is up)
    from .licenses import tell_payment
    tell_payment(session)                           # this month's license reward, paid at login
    rows = await db.rows(SELECT + " ORDER BY MID", (db.server_id, p.char.cid))
    for r in rows:
        send(session, row_frame(p.char.cid, r))
    if rows:
        session.log.note(f'{len(rows)} messages')


async def set_state(session, frame, state, ack):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return
    mid, = struct.unpack_from('<q', frame.payload)
    db = context.db
    r = await mail_row(p, mid)
    if r and state is None:
        await db.execute(DELETE, (db.server_id, p.char.cid, mid))
    elif r and not (state == 'R' and (r[4] or '').strip() == 'K'):     # a kept message stays kept when read
        await db.execute(STATE, (state, db.server_id, p.char.cid, mid))
    session.log.note(f'message {mid}: {"deleted" if state is None else state}{"" if r else " (not found)"}')
    if ack:
        send(session, Frame(ack, struct.pack('<Iq', 1 if r else 0, mid)))


@on(SVC, C2S, 0x5c8)
async def read_mail(session, frame):
    await set_state(session, frame, 'R', 0x5c9)


@on(SVC, C2S, 0x5ca)
async def delete_mail(session, frame):
    await set_state(session, frame, None, 0x5cb)


@on(SVC, C2S, 0x5cc)
async def keep_mail(session, frame):
    await set_state(session, frame, 'K', 0x5cd)


@on(SVC, C2S, 0x85)
async def mail_set(session, frame):
    if len(frame.payload) >= 12 and struct.unpack_from('<i', frame.payload, 8)[0] == 1:
        await set_state(session, frame, 'R', 0)


def item_text(it, count):
    return (f'{it.item_id} {count} {it.random} {it.upgrade} {it.box} {(it.assist_a or "").strip() or "NONE"} '
            f'{(it.assist_b or "").strip() or "NONE"} NONE {it.belonging}')


def parse_item(text):
    """-> (item id, count, random, upgrade, box, assist a, assist b, belonging) or None."""
    f = (text or '').split()
    if not f or f[0] not in context.data.item_index:
        return None
    def num(i, default=0):
        try:
            return int(f[i])
        except (IndexError, ValueError):
            return default
    def name(i):
        return f[i] if len(f) > i and f[i] != 'NONE' else ''
    return f[0], max(num(1, 1), 1), num(2), num(3), num(4), name(5), name(6), num(8)


def sendable(it, count):
    """Not on a car, not bound or broken, and tradeable: hyper parts and untradeable items only in a Parts Box (as
    the Auction House; user, 2026-10-14). Until then any item without a box could be sent, a boxed one not."""
    from .items import boxed, info_of, needs_box
    info = info_of(it) if it else None
    if not it or not info or it.car_id or it.belonging or it.upgrade < 0 or count > max(it.stack, 1):
        return False
    return boxed(it) or not needs_box(it, info)


@on(SVC, C2S, 0x5ce)
async def send_mail(session, frame):
    """emulator.ini [mail]: min_level (a lower character cannot send), fee (Mito per message, taken here and told
    to the client in the ack). One attachment: the compose window holds a single item (its slots 2 and 3 are
    crossed out; client 0x69e790 refuses a second item, 0x69eeb3 sends 0 for the other four u32)."""
    p = session.state.get('player')
    pl = frame.payload
    if not p or len(pl) < 0x282 + 24:
        return error(session, '20017')
    name = read_wstr(pl, 0, NAME)
    text = pl[0x2a:0x282].decode('utf-16-le', 'replace').split('\0')[0]
    pair = struct.unpack_from('<II', pl, 0x282)
    db, c = context.db, p.char

    def ack(result, fee=0):
        send(session, Frame(0x5cf, wstr(name, NAME) + struct.pack('<ii', result, fee)))
    if c.level < context.mail_min_level:
        session.log.note(f'message to {name!r}: level {c.level} < {context.mail_min_level}')
        from .. import admin
        return admin.message(session, f'Only drivers at Level {context.mail_min_level} or higher can send messages.')
    r = await db.row(RECEIVER, (db.server_id, name))
    if not r or int(r[0]) == c.cid:
        session.log.note(f'message to {name!r}: no such character')
        return ack(0)
    rcid, attached = int(r[0]), []
    for count, inven in (pair,):
        if not (count and inven):
            continue
        it = next((i for i in p.items if i.inven_idx == inven), None)
        if not sendable(it, count):
            session.log.note(f'message to {name!r}: item {inven} x{count} cannot be sent')
            return ack(-2)                              # text 11034 "This item cannot be sent as an attachment."
        attached.append((it, count))
    fee = max(context.mail_fee, 0)
    if fee and not await add_money(c, -fee):
        from .. import admin
        return admin.message(session, 'Not enough Mito to send the message.')
    changes, items = [], []
    for it, count in attached:
        items.append(item_text(it, count))
        it.stack -= count
        if it.stack > 0:
            await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
            changes.append((it, CHANGED))
        else:
            await db.execute(DELETE_SQL, (db.server_id, c.cid, it.inven_idx))
            p.items.remove(it)
            changes.append((it, REMOVED))
    ack(1, fee)
    if changes:
        send(session, mod_list(*changes))
    from .social import online
    target = online(rcid)
    for item in items or ['']:
        row = await db.row(INSERT, (db.server_id, rcid, c.cid, c.name, 0, '', text[:TEXT_MAX], 0, item))
        mid = int(row[0]) if row else 0
        session.log.note(f'message {mid} to {r[1]!r}: {text[:40]!r}' + (f' with {item}' if item else ''))
        got = await db.row(SELECT + " AND MID=%s", (db.server_id, rcid, mid)) if target and mid else None
        if got:
            send(target, row_frame(rcid, got))


@on(SVC, C2S, 0x5d0)
async def get_mail_item(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 8:
        return error(session, '20017')
    mid, = struct.unpack_from('<q', frame.payload)
    db, c = context.db, p.char
    r = await mail_row(p, mid)

    def ack(result):
        send(session, Frame(0x5d1, struct.pack('<iq', result, mid) + bytes(101)))
    if not r:
        return ack(-1)
    gold, parsed, changes = int(r[7] or 0), parse_item((r[8] or '').strip()), []
    await db.execute(TAKEN, (db.server_id, c.cid, mid))
    if parsed:
        item_id, count, rnd, upgrade, box, a, b, belonging = parsed
        info = context.data.item_info(context.data.item_index[item_id])
        it = stack_for(p, info, count)
        if it:
            it.stack += count
            await db.execute(STACK_SQL, (it.stack, db.server_id, c.cid, it.inven_idx))
            changes.append((it, CHANGED))
        else:
            it = await new_item(p, info, count if info.type == 5 else 1)
            it.random, it.upgrade, it.box, it.assist_a, it.assist_b, it.belonging = rnd, upgrade, box, a, b, belonging
            await db.execute(PROPS, (rnd, upgrade, box, a, b, belonging, db.server_id, c.cid, it.inven_idx))
            changes.append((it, NEW))
    if changes:
        send(session, mod_list(*changes))
    if gold > 0 and await add_money(c, gold):
        send(session, Frame(0x8a, struct.pack('<iiqq', 1, 1, gold, c.mito) + b'\0\0'))
        for f in stat_frames(p):
            send(session, f)
    session.log.note(f'message {mid}: took {r[8] or "no item"}, {gold} Mito')
    ack(0)
