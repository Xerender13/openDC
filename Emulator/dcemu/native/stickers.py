"""Stickers, lobby side (11011): uploading a sticker, the sticker catalog and the image transfer, as the 2008
server's lobby does it (PacketParser::Cmd_StickerNameCheck, Cmd_PushImageData, Cmd_StickerUpload,
Cmd_StickerSmallImage, Cmd_StickerList, Cmd_StickerSearch, Cmd_GetImage, Cmd_DeleteStickerCatalog). The
2011 client uses the 2008 layouts here (its handler sizes match). Tables: SKID_IMAGE_TB (IMGID,
SERVERID, IMGTYPE, IMGSIZE, IMGCOLORKEY, IMGDATA), SKID_STICKERCATALOG_TB (STICKERID, BIGIMGID, ...,
STICKERTYPE 0 public / 1 private, ATTACHCNT).
Private stickers: uploaded in category 13 ("My Sticker"); listed and found only for their creator and GMs (account
in server_data/adminlist.txt). Until 2026-10-14 every upload was public: the "All" list showed a private sticker
to everyone, and the client offered its remove button there (the server refuses others' deletes: user).

Upload (the client's sticker editor):
  0x5d StickerNameCheck (i64 cid, wchar[32] char name, wchar[32] sticker name, i32 category) -> 0x5e
       (wchar[32] name, i64 cid, i32 category, i32 result: 1 = free). Errors 20290 (empty / too long),
       20291 (name taken).
  0x43 PushImageData (u32 offset, u32 size, u32 total, data), repeated: the image collects in the
       connection (at most 64 KB).
  0x47 StickerUpload (u32 index, u32 image attr, u32 colour key, wchar[32] name, i64 cid, wchar[32] char
       name, i32 category): the collected image becomes the sticker's big image; catalog row made ->
       0x48 (i32 result 1, wchar[32] name, i64 image id).
  0x4b StickerSmallImage (u32 index, u32 attr, u32 colour key): the collected image is the sticker's
       image of that index. Recorded from the client: push 32x32 + 0x4b index 0, push 64x64 + 0x4b index
       1, push 128x128 + 0x47 index 2. Image ids: sticker id (a multiple of 4) + index; BIGIMGID = the
       0x47 image.
Catalog:
  0x49 StickerList (i64 cid, wchar[32] name, i32 category, i32 sort, i32 reverse, u32 offset, u32 size, u32
       time) and 0x4d StickerSearch (i64 cid, wchar[32] text, wchar[32] name, the same) -> 0x4a (i32
       category, u32 offset, u32 total, u32 time, u32 n, n x XiStickerCatalog 160: i64 sticker id, i64 big
       image id, wchar[32] name, i32 category, u32 uses, i64 creator cid, wchar[32] creator).
       Category 13 (0xd) = the player's own stickers *(as Cmd_StickerList tests 0xd)*.
  0x40 GetImage (i32 act: 0x3f6 a character's picture, 0x3f5 a crew mark (crews.py), ...; i64 object id, i64 image id)
       -> 0x41 GetImageAck (act, i32 result 1 / -1, i64
       image, i64 object, u32 colour key, u32 attr, i32 page, i32 size, i32 total, data); the image goes
       in parts of 4000: 0x44 GetImageData (act, i32 page, i32 size, data) for all but the last, 0x41 last
       (the client checks the whole image only on 0x41; page 0 empties its buffer).
  0x5f DeleteStickerCatalog (i64 cid, i64 sticker id) -> 0x60 (cid, sticker id, i32 result 1); own
       stickers only.
*(Written from the 2008 handlers and layouts; not yet seen with the real client.)*
"""
import struct

import pytds

from ..handlers import on
from ..protocol import C2S
from ..wire import Frame, read_wstr
from . import context

SVC = 'native:lobby'
NAME = 64
MAX_IMAGE, PAGE = 0x10000, 4000
MINE = 13                               # "My Sticker": uploads in it are private
PUBLIC, PRIVATE = 0, 1                  # STICKERTYPE
CATALOG_SQL = ("SELECT STICKERID, BIGIMGID, STICKERNAME, STICKERCATEGORY, ATTACHCNT, CID, CNAME FROM SKID_STICKERCATALOG_TB"
               " WHERE SERVERID = %s AND {} ORDER BY {}")


def wname(text, size=NAME):
    return (text or '').encode('utf-16-le')[:size - 2].ljust(size, b'\0')


TEXTS = {'20290': 'Please enter a sticker name of up to 32 characters.',
         '20291': 'That sticker name is already in use.',
         '20292': 'You have reached today\'s sticker upload limit.'}   # the US text table has these keys empty


def text_error(session, key):
    t = (context.data.server_text.get(key) or TEXTS.get(key, key)).encode('utf-16-le') + b'\0\0'
    session.to_client(Frame(0x0001, struct.pack('<H', len(t)) + t))


# The client's sticker cache (0x447a10) loads ids below 100000 from its own files (effects\realmatch\
# real_%05d.dds, the Real Match liveries) and asks the server (0x40) only for ids from 100000 on; 99999 is
# its "no sticker". Uploaded stickers started at 1000 at first and showed the error image on cars.
FIRST_ID = 100000
CREW_MARK = 0x3f5                # 0x40 act of a crew mark (object = the crew, image = its TMARKID; client 0x448aec)


async def next_id():
    db = context.db
    r = await db.row("SELECT ISNULL(MAX(IMGID), 0) FROM SKID_IMAGE_TB")
    r2 = await db.row("SELECT ISNULL(MAX(STICKERID), 0) FROM SKID_STICKERCATALOG_TB")
    n = max(int(r[0]), int(r2[0]), FIRST_ID - 1) + 1
    return (n + 3) & ~3                 # image ids of one sticker: base + 0..3 (GetStickerImageId)


async def image_id(session, index):
    """GetStickerImageId 0x618fb0: index 0 starts a new sticker (a new base id kept in the connection), the
    following images of the same sticker are base + index."""
    if index == 0 or 'sticker_base' not in session.state:
        session.state['sticker_base'] = await next_id()
    return session.state['sticker_base'] + min(index, 3)


@on(SVC, C2S, 0x5d)
async def name_check(session, frame):
    p = frame.payload
    if len(p) < 0x8c:
        return
    cid, = struct.unpack_from('<q', p)
    name = read_wstr(p, 0x48, NAME).strip()
    category, = struct.unpack_from('<i', p, 0x88)
    db = context.db
    ok = 0 < len(name) <= 0x20
    if not ok:
        return text_error(session, '20290')
    if await db.row("SELECT STICKERID FROM SKID_STICKERCATALOG_TB WHERE USTICKERNAME = UPPER(%s)", (name,)):
        return text_error(session, '20291')
    member = (session.state.get('member') or '').lower()
    if context.sticker_upload == 'gm' and member not in context.data.admins:
        return text_error(session, 'Only GMs can upload stickers on this server.')
    if context.sticker_daily_limit:
        r = await db.row("SELECT COUNT(*) FROM SKID_STICKERCATALOG_TB WHERE SERVERID = %s AND CID = %s"
                         " AND CDATE >= CAST(GetDate() AS date)", (db.server_id, cid))
        if r and int(r[0]) >= context.sticker_daily_limit:
            return text_error(session, '20292')
    session.state['sticker'] = dict(cid=cid, name=name, category=category, cname=read_wstr(p, 8, NAME))
    session.log.note(f'sticker name {name!r} free (category {category})')
    session.to_client(Frame(0x5e, wname(name) + struct.pack('<qii', cid, category, 1)))


@on(SVC, C2S, 0x43)
async def push_image(session, frame):
    p = frame.payload
    if len(p) < 12:
        return
    offset, size, total = struct.unpack_from('<III', p)
    if total > MAX_IMAGE:
        return text_error(session, 'Sticker size too big.')
    buf = session.state.setdefault('image', bytearray())
    if offset == 0:
        buf.clear()
    if offset != len(buf):
        return text_error(session, 'Sticker offset error.')
    buf += p[12:12 + size]


async def put_image(session, image_id, attr, colorkey):
    data = bytes(session.state.pop('image', b''))
    if not data:
        text_error(session, 'Sticker size 0.')
        return False
    db = context.db
    await db.execute("INSERT INTO SKID_IMAGE_TB(IMGID, SERVERID, IMGTYPE, IMGSIZE, IMGCOLORKEY, IMGDATA, CDATE)"
                     " VALUES (%s, %s, %s, %s, %s, %s, GetDate())", (image_id, db.server_id, attr, len(data), colorkey, pytds.Binary(data)))
    return True


@on(SVC, C2S, 0x47)
async def upload(session, frame):
    p = frame.payload
    if len(p) < 0x98:
        return
    index, attr, colorkey = struct.unpack_from('<III', p)
    name = read_wstr(p, 0xc, NAME).strip()
    cid, = struct.unpack_from('<q', p, 0x4c)
    cname = read_wstr(p, 0x54, NAME)
    category, = struct.unpack_from('<i', p, 0x94)
    db = context.db
    big_id = await image_id(session, index)
    sticker_id = session.state['sticker_base']
    if not await put_image(session, big_id, attr, colorkey):
        return
    await db.execute("INSERT INTO SKID_STICKERCATALOG_TB(STICKERID, BIGIMGID, SERVERID, CID, CNAME, STICKERTYPE, CDATE,"
                     " LASTDATE, STICKERCATEGORY, STICKERNAME, USTICKERNAME, ATTACHCNT)"
                     " VALUES (%s, %s, %s, %s, %s, %s, GetDate(), GetDate(), %s, %s, UPPER(%s), 0)",
                     (sticker_id, big_id, db.server_id, cid, cname[:16], PRIVATE if category == MINE else PUBLIC,
                      category, name[:32], name[:32]))
    session.state.pop('sticker_base', None)
    session.log.note(f'sticker {name!r} uploaded: id {sticker_id}, big image {big_id}')
    # the image id in the ack is the sticker's base id (Cmd_StickerUpload: (id >> 2) << 2); with the big
    # image's id the client showed its error picture (user, 2026-10-13)
    session.to_client(Frame(0x48, struct.pack('<i', 1) + wname(name) + struct.pack('<q', sticker_id)))


@on(SVC, C2S, 0x4b)
async def small_image(session, frame):
    """The smaller images of the sticker being uploaded (index 0, 1; the client sends three sizes, the
    biggest with 0x47)."""
    p = frame.payload
    if len(p) < 12:
        return
    index, attr, colorkey = struct.unpack_from('<III', p)
    await put_image(session, await image_id(session, index), attr, colorkey)


def catalog_entry(r):
    sid, big, name, category, uses, cid, cname = r
    return struct.pack('<qq', int(sid), int(big or 0)) + wname(name) + struct.pack('<iIq', int(category or 0),
                                                                                   int(uses or 0), int(cid)) + wname(cname)


def is_gm(session):
    return (session.state.get('member') or '').lower() in context.data.admins


async def send_list(session, cid, category, offset, size, where, args, order):
    """The catalog rows matching where; private stickers only for their creator (cid) and GMs."""
    db = context.db
    if not is_gm(session):
        where, args = f'({where}) AND (STICKERTYPE = {PUBLIC} OR CID = %s)', (*args, cid)
    rows = await db.rows(CATALOG_SQL.format(where, order), (db.server_id, *args))
    part = rows[offset:offset + max(1, min(size, 50))]
    session.to_client(Frame(0x4a, struct.pack('<iIIII', category, offset, len(rows), 0, len(part))
                            + b''.join(catalog_entry(r) for r in part)))


ORDERS = {0: 'CDATE DESC', 1: 'ATTACHCNT DESC', 2: 'STICKERNAME', 3: 'CNAME'}


@on(SVC, C2S, 0x49)
async def sticker_list(session, frame):
    p = frame.payload
    if len(p) < 0x60:
        return
    cid, = struct.unpack_from('<q', p)
    category, sort, reverse, offset, size, _ = struct.unpack_from('<iiiIII', p, 0x48)
    order = ORDERS.get(sort, 'CDATE DESC')
    if category == MINE:
        await send_list(session, cid, category, offset, size, 'CID = %s', (cid,), order)
    elif category > 0:
        await send_list(session, cid, category, offset, size, 'STICKERCATEGORY = %s', (category,), order)
    else:
        await send_list(session, cid, category, offset, size, '1 = 1', (), order)


@on(SVC, C2S, 0x4d)
async def sticker_search(session, frame):
    p = frame.payload
    if len(p) < 0xa0:
        return
    cid, = struct.unpack_from('<q', p)
    text = read_wstr(p, 8, NAME).strip()
    category, sort, reverse, offset, size, _ = struct.unpack_from('<iiiIII', p, 0x88)
    await send_list(session, cid, category, offset, size, 'USTICKERNAME LIKE UPPER(%s) OR CNAME LIKE %s',
                    (f'%{text}%', f'%{text}%'), ORDERS.get(sort, 'CDATE DESC'))


@on(SVC, C2S, 0x40)
async def get_image(session, frame):
    p = frame.payload
    if len(p) < 20:
        return
    act, obj, image = struct.unpack_from('<iqq', p)
    db = context.db
    r = await db.row("SELECT IMGTYPE, IMGCOLORKEY, IMGDATA FROM SKID_IMAGE_TB WHERE IMGID = %s", (image,))
    if not r and act == CREW_MARK and 0 < image < 100:     # the built-in crew marks (game.crews.builtin_mark)
        from .game.crews import builtin_mark
        data = builtin_mark(image)
        r = (0, 0, data) if data else None
    if not r:
        # "none" is -1 for stickers, but 0 for a crew mark: the client's 0x41 handler (0x528a50) gives -1 to the sticker
        # cache (0x447270) and 0 to the mark cache (0x448770), whose busy flag [+0x10] (one request at a time, 0x448ab3)
        # only clears that way; with -1 a client asked for no crew mark any more (user, 2026-10-15: no mark for others)
        result = 0 if act == CREW_MARK else -1
        session.to_client(Frame(0x41, struct.pack('<iiqqIIiii', act, result, image, obj, 0, 0, 0, 0, 0)))
        return
    attr, key, data = int(r[0] or 0), int(r[1] or 0), bytes(r[2] or b'')
    # The client (0x528a50 / 0x5289e0) appends every part to one buffer (page 0 empties it) and checks for a
    # whole image only on 0x41, so 0x44 carries the first parts and 0x41 the last one (sent first, the
    # image was checked after 4000 bytes and stayed empty on the car).
    pages = [data[o:o + PAGE] for o in range(0, len(data), PAGE)] or [b'']
    for page, chunk in enumerate(pages[:-1]):
        session.to_client(Frame(0x44, struct.pack('<iii', act, page, len(chunk)) + chunk))
    last = pages[-1]
    session.to_client(Frame(0x41, struct.pack('<iiqqIIiii', act, 1, image, obj, key, attr, len(pages) - 1, len(last),
                                              len(data)) + last))


@on(SVC, C2S, 0x5f)
async def delete_catalog(session, frame):
    p = frame.payload
    if len(p) < 16:
        return
    cid, sticker_id = struct.unpack_from('<qq', p)
    db = context.db
    r = await db.row("SELECT BIGIMGID FROM SKID_STICKERCATALOG_TB WHERE STICKERID = %s AND CID = %s", (sticker_id, cid))
    ok = 0
    if r:
        await db.execute("DELETE FROM SKID_STICKERCATALOG_TB WHERE STICKERID = %s", (sticker_id,))
        # all of the sticker's images: base + 0..3 (the 64 px one was left behind at first)
        await db.execute("DELETE FROM SKID_IMAGE_TB WHERE IMGID BETWEEN %s AND %s OR IMGID = %s",
                         (sticker_id, sticker_id + 3, int(r[0] or 0)))
        ok = 1
    session.to_client(Frame(0x60, struct.pack('<qqi', cid, sticker_id, ok)))


@on(SVC, C2S, 0x4c)
async def report_attach(session, frame):
    """0x4c StickerReportAttach (i64 cid, u32 car, XiSticker (its id = the image drawn), i64 sticker id,
    wchar[32] name, i64 creator, wchar[32] creator name): the first step of putting a sticker on a car
    (recorded from the client, sent from the sticker shop). -> 0x4f ReportAttachAck: the same + i64 sales
    (the catalog's use count); the client then sends 0x548 AttachSticker on the game port."""
    p = frame.payload
    if len(p) < 0xb4:
        return
    sticker_id, = struct.unpack_from('<q', p, 0x24)
    db = context.db
    r = await db.row("SELECT ATTACHCNT, STICKERTYPE FROM SKID_STICKERCATALOG_TB WHERE STICKERID = %s", (sticker_id,))
    if not r or int(r[1] or 0) == 2:
        return text_error(session, 'This sticker is not available.')
    session.log.note(f'sticker {sticker_id}: attach requested')
    session.to_client(Frame(0x4f, p[:0xb4] + struct.pack('<q', int(r[0] or 0))))
