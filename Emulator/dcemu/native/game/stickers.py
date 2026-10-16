"""Stickers, game side: the stickers on a player's cars (SKID_STITEM_TB), attaching and detaching, and
showing other players' stickers (the 2008 Cmd_MyStickerList, Cmd_AttachSticker, Cmd_DetachSticker,
BS_PktStickerInfoRes from Cmd_PlayerInfoReq). Layouts as in 2008 (the 2011 client's sizes match). The
catalog and the images are the lobby's (native/stickers.py).

XiSticker (24): i64 sticker id, u32 colour, u16 x, y, scale x, scale y, rotate, u8 part, u8 flip.
XiStrMySTItem (64): u32 car id, u32 inventory index, char[32] sticker name, XiSticker.
0x546 MyStickerList -> 0x547 (u32 n, u32 list update, n x XiStrMySTItem).
0x548 AttachSticker (u32 car, XiSticker, i64 sticker id, wchar[32] name, i64 creator, wchar[32] creator
     name, i64 sales) -> 0x549 (i32 result 1, u16 age, XiStrMySTItem, i64 Mito paid, i64 creator, i64
     sticker id). Price Contents.ini Etc.StickerPrice (2000), as many per car as the Sticker Glue held
     allows (glue_limit, 20239), 20092 without the money; the creator gets half (CalcMoney "SellSticker") and, if online,
     0x54c NotifySelledSticker (i64 sticker, wchar[32] name, i64 creator, wchar[32] creator name, i64
     Mito). The catalog's use count goes up.
0x54a DetachSticker (u32 inventory index) -> 0x54b (index, u16 age, i32 result 1).
0x324 StickerInfoRes (u16 serial, u16 age, u32 car, u16 n, n x XiSticker): a player's stickers on the car
     it drives, to whoever asks for its player info (0x321) and to its channel after a change.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import context
from .login import SVC, error, send, sessions

ITEMS_SQL = ("SELECT INVENIDX, CARID, STICKERID, STICKERNAME, COLOR, POSX, POSY, SCALEX, SCALEY, ROTATE, FLIP, PART"
             " FROM SKID_STITEM_TB WHERE SERVERID = %s AND CID = %s ORDER BY INVENIDX")


def xi_sticker(sid, color, x, y, sx, sy, rot, part, flip):
    return struct.pack('<qIHHHHHBB', int(sid), int(color) & 0xffffffff, int(x), int(y), int(sx), int(sy), int(rot),
                       int(part) & 0xff, int(flip) & 0xff)


# Sticker Glue (drift shop, VisualItem category 20 STICKERLICENSE): i_d_sticker_l1 / _l3 / _l6 allow that
# many stickers per car (user, 2026-10-13); the plain i_d_sticker has no number and allows the most
# (Etc.MaxStickerAttach, 6). Without Glue the client draws no stickers at all: 0x5dd BonusUpdate's sticker
# field sets the flag 0x5403d0 checks before putting the player's stickers on its car.
GLUE_CATEGORY = 20


def glue_limit(p):
    most = int(context.data.contents.get('Etc.MaxStickerAttach', 6))
    limit = 0
    for v in p.vsitems:
        vis = context.data.visuals.get(v.table_idx)
        if vis and vis.category == GLUE_CATEGORY:
            n = vis.item_id.rpartition('_l')[2]
            limit = max(limit, int(n) if n.isdigit() else most)
    return min(limit, most)


async def items_of(cid):
    db = context.db
    return await db.rows(ITEMS_SQL, (db.server_id, cid))


def my_item(r):
    inven, car, sid, name, color, x, y, sx, sy, rot, flip, part = r
    return (struct.pack('<II', int(car), int(inven)) + (name or '').encode('latin-1', 'replace')[:31].ljust(32, b'\0')
            + xi_sticker(sid, color or 0, x or 0, y or 0, sx or 0, sy or 0, rot or 0, part or 0, flip or 0))


@on(SVC, C2S, 0x546)
async def my_sticker_list(session, frame):
    from .login import LIST_FULL
    p = session.state.get('player')
    rows = await items_of(p.char.cid) if p else []
    send(session, Frame(0x547, struct.pack('<II', len(rows), LIST_FULL) + b''.join(my_item(r) for r in rows)))


async def info_frame(session):
    """0x324 for the session's player and the car it drives (None without stickers)."""
    p = session.state.get('player')
    car = p.car if p else None
    if not car:
        return None
    rows = [r for r in await items_of(p.char.cid) if int(r[1]) == car.car_id][:glue_limit(p)]
    if not rows:
        return None
    return Frame(0x324, struct.pack('<HHIH', session.state.get('serial', 0), session.state.get('visual_age', 1) & 0xffff,
                                    car.car_id, len(rows))
                 + b''.join(xi_sticker(r[2], r[4] or 0, r[5] or 0, r[6] or 0, r[7] or 0, r[8] or 0, r[9] or 0,
                                       r[11] or 0, r[10] or 0) for r in rows))


async def show_to_channel(session):
    f = await info_frame(session)
    if not f:
        return
    for s in list(sessions.values()):
        if s is not session and s.state.get('player') and s.state.get('channel') == session.state.get('channel'):
            send(s, f)


def bump_age(session):
    session.state['visual_age'] = session.state.get('visual_age', 1) + 1
    return session.state['visual_age'] & 0xffff


@on(SVC, C2S, 0x548)
async def attach(session, frame):
    from .items import add_money
    p = session.state.get('player')
    b = frame.payload
    if not p or len(b) < 0xb4:
        return
    db, c = context.db, p.char
    car_id, = struct.unpack_from('<I', b)
    sid, color, x, y, sx, sy, rot, part, flip = struct.unpack_from('<qIHHHHHBB', b, 4)
    sticker_id, = struct.unpack_from('<q', b, 0x1c)
    name = read_wstr(b, 0x24, 64)
    creator, = struct.unpack_from('<q', b, 0x64)
    creator_name = read_wstr(b, 0x6c, 64)
    if not any(k.car_id == car_id for k in c.cars):
        return error(session, '20025')
    from .. import admin
    limit = glue_limit(p)
    if not limit:
        return admin.message(session, 'You need Sticker Glue (Drift Shop) to apply stickers.')
    rows = await items_of(c.cid)
    if sum(1 for r in rows if int(r[1]) == car_id) >= limit:
        msg = context.data.server_text.get('20239', 'You can only use a total of %d stickers per car.').replace('%d', str(limit))
        return admin.message(session, msg)
    price = int(context.data.contents.get('Etc.StickerPrice', 2000))
    if creator != c.cid and not await add_money(c, -price):
        return error(session, '20092')
    if creator == c.cid:
        price = 0
    inven = max([int(r[0]) for r in rows] + [0]) + 1
    await db.execute("INSERT INTO SKID_STITEM_TB(SERVERID, CID, CNAME, INVENIDX, CARID, STICKERID, STICKERNAME, COLOR, POSX,"
                     " POSY, SCALEX, SCALEY, ROTATE, FLIP, PART, CDATE) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,GetDate())",
                     (db.server_id, c.cid, c.name, inven, car_id, sid, name[:32], color, x, y, sx, sy, rot, flip, part))
    await db.execute("UPDATE SKID_STICKERCATALOG_TB SET ATTACHCNT = ATTACHCNT + 1, LASTDATE = GetDate() WHERE STICKERID = %s",
                     (sticker_id,))
    if price and creator:
        royalty = price // 2
        await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD = GOLD + %s WHERE SERVERID = %s AND CID = %s",
                         (royalty, db.server_id, creator))
        maker = next((s for s in list(sessions.values()) if s.state.get('player')
                      and s.state['player'].char.cid == creator), None)
        if maker:
            maker.state['player'].char.mito += royalty
            send(maker, Frame(0x54c, struct.pack('<q', sticker_id) + name.encode('utf-16-le')[:62].ljust(64, b'\0')
                              + struct.pack('<q', creator) + creator_name.encode('utf-16-le')[:62].ljust(64, b'\0')
                              + struct.pack('<q', royalty)))
    session.log.note(f'sticker {name!r} ({sticker_id}) on car {car_id}, index {inven}, {price} Mito')
    # XiSticker's id is the image the client draws (the catalog's big image), not the catalog id; the
    # first version stored the catalog id (user: stickers applied but not shown)
    row = (inven, car_id, sid, name, color, x, y, sx, sy, rot, flip, part)
    send(session, Frame(0x549, struct.pack('<iH', 1, bump_age(session)) + my_item(row)
                        + struct.pack('<qqq', price, creator, sticker_id)))
    await show_to_channel(session)


@on(SVC, C2S, 0x54a)
async def detach(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 4:
        return
    db, c = context.db, p.char
    inven, = struct.unpack_from('<I', frame.payload)
    r = await db.row("SET NOCOUNT ON; DELETE FROM SKID_STITEM_TB WHERE SERVERID = %s AND CID = %s AND INVENIDX = %s;"
                     " SELECT @@ROWCOUNT", (db.server_id, c.cid, inven))
    if not (r and r[0]):
        from .. import admin
        return admin.message(session, 'Wrong StickerIndex')
    send(session, Frame(0x54b, struct.pack('<IHi', inven, bump_age(session), 1)))
    await show_to_channel(session)


# ---- reports and bad stickers --------------------------------------------------------------------------
# The 2011 client has no report button: players type "/report <sticker name> [reason]" in chat (it goes out
# as 0x82 GameStream, like the GM commands). Reports are kept in SKID_STLOG_TB (LOGNAME 'REPORT',
# N1ARG = sticker id, TXTCONTENT = reason). GM commands: gmreports (the open reports), gmbadsticker
# <name> (blocks it: STICKERTYPE 2, out of the catalog, taken off every car, 0x61 NotifyBadSticker (u32 n,
# i64 ids) to every lobby connection so clients drop it (lobby handler 0x5284a0), gmgoodsticker <name>
# (back into the catalog).
BLOCKED = 2


async def find_sticker(name):
    db = context.db
    return await db.row("SELECT STICKERID, STICKERNAME, CNAME, STICKERTYPE FROM SKID_STICKERCATALOG_TB"
                        " WHERE SERVERID = %s AND USTICKERNAME = UPPER(%s)", (db.server_id, name))


async def report(session, args):
    from .. import admin
    p = session.state.get('player')
    if not p or not args:
        return admin.message(session, 'Usage: /report <sticker name> [reason]')
    r = await find_sticker(args[0])
    if not r:
        return admin.message(session, f'There is no sticker named {args[0]}.')
    db, c = context.db, p.char
    await db.execute("INSERT INTO SKID_STLOG_TB(LOGNAME, LOGKEY, SERVERID, CID, CNAME, CREATEDATE, N1ARG, N2ARG, N3ARG,"
                     " TXTCONTENT) VALUES ('REPORT', %s, %s, %s, %s, GetDate(), %s, 0, 0, %s)",
                     (int(r[0]), db.server_id, c.cid, c.name, int(r[0]), ' '.join(args[1:])[:64]))
    session.log.note(f'sticker report: {r[1]!r} ({r[0]}) by {c.name!r}: {" ".join(args[1:])!r}')
    admin.message(session, f'Thank you, the sticker {r[1]} has been reported to the GMs.')
    for s in list(sessions.values()):                 # GMs online are told at once
        from .misc import is_admin
        if s is not session and s.state.get('player') and is_admin(s):
            admin.message(s, f'Sticker report: {r[1]} (by {r[2]}) reported by {c.name}. gmbadsticker {r[1]} to block it.')


async def gm_command(session, cmd, args):
    from .. import admin
    from ...proxy import live
    db = context.db
    if cmd == 'gmreports':
        rows = await db.rows("SELECT TOP 10 c.STICKERNAME, COUNT(*), MAX(l.TXTCONTENT) FROM SKID_STLOG_TB l JOIN"
                             " SKID_STICKERCATALOG_TB c ON c.STICKERID = l.N1ARG WHERE l.LOGNAME = 'REPORT'"
                             " AND c.STICKERTYPE <> %s GROUP BY c.STICKERNAME ORDER BY COUNT(*) DESC", (BLOCKED,))
        return admin.message(session, 'Reported stickers: ' + (', '.join(f'{n} ({k}x: {t})' for n, k, t in rows) or 'none'))
    if not args:
        return admin.message(session, f'Usage: {cmd} <sticker name>')
    r = await find_sticker(args[0])
    if not r:
        return admin.message(session, f'There is no sticker named {args[0]}.')
    sid = int(r[0])
    if cmd == 'gmgoodsticker':
        await db.execute("UPDATE SKID_STICKERCATALOG_TB SET STICKERTYPE = 0 WHERE STICKERID = %s", (sid,))
        await db.execute("DELETE FROM SKID_STLOG_TB WHERE LOGNAME = 'REPORT' AND N1ARG = %s", (sid,))
        return admin.message(session, f'Sticker {r[1]} is back in the catalog.')
    await db.execute("UPDATE SKID_STICKERCATALOG_TB SET STICKERTYPE = %s WHERE STICKERID = %s", (BLOCKED, sid))
    await db.execute("DELETE FROM SKID_STITEM_TB WHERE STICKERID = %s", (sid,))
    notice = Frame(0x61, struct.pack('<Iq', 1, sid))
    for s in list(live.values()):
        if s.service == 'lobby':
            s.to_client(notice)
    session.log.note(f'GM blocks sticker {r[1]!r} ({sid})')
    admin.message(session, f'Sticker {r[1]} is blocked: out of the catalog and off every car.')
