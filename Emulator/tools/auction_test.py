"""Scripted test of dcemu/native/game/auction.py against the database: seller = the character named on the command
line (default DCLoverN; it must be offline), buyer = NewChar. Usage: .venv/bin/python tools/auction_test.py [seller]
Only what the test makes is removed at the end (items, cars, drift items, auction rows made after the start); the
characters' money, item states, car counters and earlier listings are put back as they were."""
import asyncio, configparser, os, struct, sys
sys.path.insert(0, '.')
from dcemu.native import context
from dcemu.native.db import Database
from dcemu.native.data import Tables
from dcemu.wire import Frame

cp = configparser.ConfigParser(inline_comment_prefixes=(';',)); cp.read('emulator.ini'); d = cp['database']
context.db = Database(d['host'], int(d['port']), d['user'], d['password'], d['name'], int(d['server_id']))
context.data = Tables('server_data', 'server_data/tables', 'server_data/adminlist.txt')
context.auction_drift = True
SNAME = sys.argv[1] if len(sys.argv) > 1 else 'DCLoverN'      # the seller (was Newbie, cid 100009, on the first machine)
BCID = 100005                                                 # the buyer, NewChar
from dcemu.native.game import auction, items, login, player, vshop, cars, driftuse  # noqa
SENT = {}


class Log:
    def note(self, t): print('    note:', t)


class S:
    def __init__(self, p, sid):
        self.state = {'player': p}; self.log = Log(); self.out = []; self.id = sid

    def to_client(self, f): self.out.append(f)


def fake_send(s, *fs):
    for f in fs: s.out.append(f)


for m in (auction, items, login, vshop, cars, driftuse):
    if hasattr(m, 'send'): m.send = fake_send


def show(s, label):
    print(f'  {label}:', [(hex(f.type), len(f.payload) + 2, f.payload[:40].decode('utf-16-le', 'replace') if f.type == 1 else '') for f in s.out])
    out = list(s.out); s.out.clear(); return out


def F(t, *vals, raw=b''):
    return Frame(t, struct.pack(f'<{len(vals)}I', *vals) + raw)


async def main():
    db = context.db
    sid = db.server_id
    SCID = int((await db.row("SELECT CID FROM SKID_CHARACTER_TB WHERE CNAME=%s AND STATE='P'", (SNAME,)))[0])
    cids = (BCID, SCID)
    snap = {}
    for cid in cids:
        snap[cid] = dict(
            char=await db.row("SELECT GOLD, PARTINVENIDX, NUMCAR, NEXTCAR, CURCAR FROM SKID_CHARACTER_TB WHERE CID=%s", (cid,)),
            items=await db.rows("SELECT INVENIDX, STATE, BOX, STACKNUM FROM SKID_ITEM_TB WHERE CID=%s", (cid,)),
            cars={int(r[0]) for r in await db.rows("SELECT CARID FROM SKID_CAR_TB WHERE CID=%s", (cid,))},
            vs={int(r[0]) for r in await db.rows("SELECT INVENIDX FROM SKID_VSITEM_TB WHERE CID=%s", (cid,))},
            mileage=await db.row("SELECT REGNUM, BUYNUM, SELLNUM FROM SKID_AUCTIONMILEAGE_TB WHERE CID=%s", (cid,)))
    regs = {tb: int((await db.row(f"SELECT ISNULL(MAX(REGID), 0) FROM {tb}"))[0])
            for tb in ('SKID_AUCTION_TB', 'SKID_AUCTIONCAR_TB', 'SKID_AUCTIONVS_TB')}
    await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD=5000000 WHERE CID IN (%s, %s)", cids)
    try:
        sp = await player.load(SNAME); bp = await player.load('NewChar')
        s, b = S(sp, 1), S(bp, 2)
        login.sessions.clear(); login.sessions.update({1: s, 2: b})
        t = context.data
        # test items for the seller
        hyper = await items.new_item(sp, t.item_info(t.item_index['i_s_000003']), 1)
        box = await items.new_item(sp, t.item_info(t.item_index['i_n_00026']), 2)
        stack = await items.new_item(sp, t.item_info(t.item_index['i_n_00019']), 5)
        part = await items.new_item(sp, t.item_info(t.item_index['i_s_000001']), 1)
        print('1. register a part for 1000 (fee 7%)')
        await auction.auction_on(s, F(0x246, part.table_idx, part.inven_idx, 1, 1000)); o = show(s, 'seller')
        assert o[-1].type == 0x247 and len(o[-1].payload) + 2 == 110, 'ack size'
        assert struct.unpack_from('<I', o[-1].payload, 4)[0] == 70
        print('2. hyper part: refused, then boxed, then registered')
        await auction.auction_on(s, F(0x246, hyper.table_idx, hyper.inven_idx, 1, 50000)); show(s, 'seller (refused)')
        await items.item_use_ex(s, F(0x1a3, hyper.inven_idx, box.inven_idx, 0)); show(s, 'parts box')
        assert hyper.box == 1 and box.stack == 1
        await auction.auction_on(s, F(0x246, hyper.table_idx, hyper.inven_idx, 1, 50000)); show(s, 'seller')
        print('3. 2 of a stack of 5')
        await auction.auction_on(s, F(0x246, stack.table_idx, stack.inven_idx, 2, 300)); o = show(s, 'seller')
        assert stack.stack == 3
        print('4. lists')
        for typ, label in ((1, "speed parts"), (5, "general"), (0, "all")):
            await call(0x24c, b, F(0x24c, 0, 13, typ, 7, 0, 0)); o = show(b, f'list {label}')
            total, n = struct.unpack_from('<II', o[-1].payload)
            print('    total', total, 'n', n, 'size', len(o[-1].payload) + 2, '== 10 + n * 0xa2:', len(o[-1].payload) + 2 == 10 + n * 0xa2)
        raw = struct.pack('<5I', 0, 13, 0, 0, 3) + 'Sma'.encode('utf-16-le').ljust(256, b'\0') + bytes(256) + struct.pack('<II', 0, 0)
        await call(0x253, b, Frame(0x253, raw)); o = show(b, 'search "Sma"')
        print('    found', struct.unpack_from('<II', o[-1].payload))
        mine = await auction.listings(auction.ITEMS, ' AND a.CID=%s', (SCID,))
        serial = {x.item_id: x.serial for x in mine}
        print('5. buyer buys the part; the seller cannot buy their own')
        await auction.auction_buy(s, F(0x250, serial['i_s_000001'])); show(s, 'seller buys own')
        await auction.auction_buy(b, F(0x250, serial['i_s_000001'])); show(b, 'buyer'); show(s, 'seller told')
        await auction.auction_buy(b, F(0x250, serial['i_s_000001'])); show(b, 'buyer again (sold)')
        print('6. my list, complete, cancel; boxed part bought -> out of its box')
        await call(0x244, s, F(0x244)); o = show(s, 'my list')
        n = struct.unpack_from('<I', o[-1].payload, 4)[0]
        print('    n', n, 'size ok', len(o[-1].payload) + 2 == 10 + n * 0x64,
              [struct.unpack_from('<6Ii', o[-1].payload, 8 + k * 0x64) for k in range(n)])
        g0 = sp.char.mito
        await auction.auction_complete(s, F(0x24a, serial['i_s_000001'])); show(s, 'complete')
        print('    money', g0, '->', sp.char.mito)
        await auction.auction_buy(b, F(0x250, serial['i_s_000003'])); show(b, 'buyer (hyper)')
        bh = next(i for i in bp.items if i.item_id == 'i_s_000003'); print('    bought hyper box =', bh.box)
        await auction.auction_cancel(s, F(0x248, serial['i_n_00019'])); show(s, 'cancel usable')
        print('    stack back to', stack.stack, [i.inven_idx for i in sp.items if i.item_id == 'i_n_00019'])
        print('7. expiry')
        await auction.auction_on(s, F(0x246, stack.table_idx, stack.inven_idx, 1, 10)); show(s, 'register 1')
        x = [x for x in await auction.listings(auction.ITEMS, ' AND a.CID=%s', (SCID,)) if x.state == 1][-1]
        await db.execute("UPDATE SKID_AUCTION_TB SET REGDATE=DATEADD(day, -7, GETDATE()) WHERE REGID=%s", (x.serial,))
        await call(0x24c, b, F(0x24c, 0, 13, 5, 0, 0, 0)); o = show(b, 'public list')
        print('    public total', struct.unpack_from('<I', o[-1].payload)[0])
        await auction.auction_buy(b, F(0x250, x.serial)); show(b, 'buy expired')
        await call(0x244, s, F(0x244)); o = show(s, 'my list')
        print('    unit', struct.unpack_from('<6Ii', o[-1].payload, 8))
        await db.execute("UPDATE SKID_AUCTION_TB SET REGDATE=DATEADD(hour, -30, GETDATE()) WHERE REGID=%s", (x.serial,))
        await auction.auction_cancel(s, F(0x248, x.serial)); show(s, 'cancel expired')
        print('8. cars')
        r = await db.row("SET NOCOUNT ON; DECLARE @carid numeric; EXEC PC_SKID_CREATECAR %s, %s, %s, 80, 0, 3, 0, 100, 0, @carid OUTPUT; SELECT @carid", (sid, SCID, SNAME))
        sp2 = await player.load(SNAME); s.state['player'] = sp = sp2
        car = next(c for c in sp.char.cars if c.car_id == int(r[0]))
        v = t.vehicles[80]; key = await items.new_item(sp, t.item_info(t.item_index[v['File Name'].rsplit('.', 1)[0]]), 1)
        cur = next(c for c in sp.char.cars if c.car_id == sp.char.cur_car)
        await auction.auction_car_on(s, F(0x6a6, key.table_idx, key.inven_idx, cur.car_id, 9000)); show(s, 'current car (refused)')
        await auction.auction_car_on(s, F(0x6a6, key.table_idx, key.inven_idx, car.car_id, 9000)); o = show(s, 'car on')
        assert o[-1].type == 0x6a7 and len(o[-1].payload) + 2 == 70
        await cars.select_car(s, F(0x59, car.car_id)); show(s, 'select car on auction')
        await call(0x6ac, b, F(0x6ac, 0, 13, 0, 0, 0, 0)); o = show(b, 'car list (all)')
        print('    total', struct.unpack_from('<II', o[-1].payload), 'size ok', len(o[-1].payload) + 2 == 10 + struct.unpack_from('<I', o[-1].payload, 4)[0] * 0x7a)
        cx = [x for x in await auction.listings(auction.CARS, ' AND a.CID=%s', (SCID,))][-1]
        await auction.auction_car_buy(b, F(0x6ae, cx.serial, 80, 3, 9000)); o = show(b, 'buyer')
        print('    buy ack size', len(o[-1].payload) + 2, 'buyer cars', [(c.car_id, c.car_type, c.grade, c.auction_cnt) for c in bp.char.cars])
        show(s, 'seller told')
        await auction.auction_car_complete(s, F(0x6aa, cx.serial)); show(s, 'car complete')
        print('    seller cars', [c.car_id for c in sp.char.cars])
        bought = next(c for c in bp.char.cars if c.auction_cnt)
        bkey = next(i for i in bp.items if i.item_id == key.item_id)
        await auction.auction_car_on(b, F(0x6a6, bkey.table_idx, bkey.inven_idx, bought.car_id, 9000)); show(b, 'resell bought car (refused)')
        print('9. drift items')
        vrow = next(r for k, r in t.vshop.items() if r.get('UseHancoin') == '1' and t.visuals.get(k) and t.visuals[k].category == 15)
        vid = int(vrow['UniqueId']); vis = t.visuals[vid]
        from dcemu.native.game.records import VisualItem
        from dcemu.native import now
        gid = int((await db.row(items.NEXT_GID_SQL))[0]); inv = max([o.inven_idx for o in sp.vsitems] + [61]) + 1
        vv = VisualItem(gid, vis.item_id, inv, 0, 0, '', 7, now(), 0, vid); sp.vsitems.append(vv)
        await db.execute(vshop.INSERT_SQL, (sid, SCID, SNAME, gid, vis.item_id, inv, 0, 0, '', 7, vv.ctime, 0))
        await auction.auction_vs_on(s, F(0x642, vid, inv, 1, 777)); o = show(s, 'drift on')
        assert o[1].type == 0x643 and len(o[1].payload) + 2 == 104
        await call(0x648, b, F(0x648, 0, 13, 0, 0, 0, 0)); o = show(b, 'drift list')
        print('    total', struct.unpack_from('<II', o[-1].payload), 'size ok', len(o[-1].payload) + 2 == 10 + struct.unpack_from('<I', o[-1].payload, 4)[0] * 0x9c)
        dx = (await auction.listings(auction.DRIFT, ' AND a.CID=%s', (SCID,)))[-1]
        await auction.auction_vs_buy(b, F(0x64c, dx.serial)); show(b, 'buyer'); show(s, 'seller told')
        await call(0x640, s, F(0x640)); o = show(s, 'my drift list')
        print('    size ok', len(o[-1].payload) + 2 == 10 + struct.unpack_from('<I', o[-1].payload, 4)[0] * 0x5e)
        await auction.auction_vs_complete(s, F(0x646, dx.serial)); show(s, 'drift complete')
        print('10. usable items join the buyer stack; split stacks merge at login')
        info = t.item_info(t.item_index['i_n_00019'])
        mine = await items.new_item(bp, info, 3)
        await auction.auction_on(s, F(0x246, stack.table_idx, stack.inven_idx, 1, 10)); show(s, 'register 1')
        x = [x for x in await auction.listings(auction.ITEMS, ' AND a.CID=%s', (SCID,)) if x.state == 1][-1]
        await auction.auction_buy(b, F(0x250, x.serial)); show(b, 'buyer')
        rows = [i for i in bp.items if i.item_id == 'i_n_00019']
        print('    buyer stacks', [(i.inven_idx, i.stack) for i in rows]); assert len(rows) == 1 and rows[0].stack == 4
        extra = await items.new_item(bp, info, 2)
        print('    removed', await items.merge_stacks(bp), [(i.inven_idx, i.stack) for i in bp.items if i.item_id == 'i_n_00019'])
        db_rows = await db.rows("SELECT INVENIDX, STACKNUM FROM SKID_ITEM_TB WHERE CID=100005 AND ITEMID='i_n_00019'")
        print('    in the DB', db_rows); assert len(db_rows) == 1 and int(db_rows[0][1]) == 6
        print('ALL DONE')
    finally:
        print('cleanup')
        for tb, top in regs.items():
            await db.execute(f"DELETE FROM {tb} WHERE REGID>%s AND CID IN (%s, %s)", (top, *cids))
        for cid in cids:
            sn = snap[cid]
            gold, pinv, numcar, nextcar, curcar = sn['char']
            await db.execute("DELETE FROM SKID_ITEM_TB WHERE CID=%s AND INVENIDX>%s", (cid, pinv))
            for inven, state, box, stack in sn['items']:
                await db.execute("UPDATE SKID_ITEM_TB SET STATE=%s, BOX=%s, STACKNUM=%s WHERE CID=%s AND INVENIDX=%s",
                                 (state, box, stack, cid, inven))
            for (carid,) in await db.rows("SELECT CARID FROM SKID_CAR_TB WHERE CID=%s", (cid,)):
                if int(carid) not in sn['cars']:
                    await db.execute("DELETE FROM SKID_CAR_TB WHERE CID=%s AND CARID=%s", (cid, carid))
            for (inven,) in await db.rows("SELECT INVENIDX FROM SKID_VSITEM_TB WHERE CID=%s", (cid,)):
                if int(inven) not in sn['vs']:
                    await db.execute("DELETE FROM SKID_VSITEM_TB WHERE CID=%s AND INVENIDX=%s", (cid, inven))
            await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD=%s, PARTINVENIDX=%s, NUMCAR=%s, NEXTCAR=%s, CURCAR=%s"
                             " WHERE CID=%s", (gold, pinv, numcar, nextcar, curcar, cid))
            if sn['mileage']:
                await db.execute("UPDATE SKID_AUCTIONMILEAGE_TB SET REGNUM=%s, BUYNUM=%s, SELLNUM=%s WHERE CID=%s",
                                 (*sn['mileage'], cid))
            else:
                await db.execute("DELETE FROM SKID_AUCTIONMILEAGE_TB WHERE CID=%s", (cid,))


async def call(t, s, f):
    from dcemu.handlers import handlers_for
    from dcemu.protocol import C2S
    for h in handlers_for(login.SVC, C2S, t):
        await h(s, f)

asyncio.run(main())
