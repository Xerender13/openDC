"""openDC Launcher: the Auction House, on the server's own tables (as dcemu/native/game/auction.py does in the game).

Listings: SKID_AUCTION_TB (items), SKID_AUCTIONCAR_TB (cars), SKID_AUCTIONVS_TB (drift items); SKID_AUCTIONMILEAGE_TB
the sellers' counters. States: 1 on sale, 2 sold (the seller collects the money), 3 expired (the seller takes the item
back). A registered item / key / drift item stays with the seller in state 4. Rules and fees from emulator.ini
[auction] (days, min_level, item_fee, cars, car_fee, drift_items, drift_fee).

The game must be closed for the character that buys / registers / collects (the launcher checks that): the server reads
the listings from the database on every request, and a seller in the game collects with the game's own window.
"""
import configparser
import datetime
import os

from odc_inv import Data

ON_SALE, SOLD, EXPIRED, LOCKED = 1, 2, 3, 4
TABLES = {'item': 'skid_auction_tb', 'car': 'skid_auctioncar_tb', 'drift': 'skid_auctionvs_tb'}
VS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS SKID_AUCTIONVS_TB(SERVERID numeric(18,0) NOT NULL,
  CID numeric(18,0) NOT NULL, CNAME citext NOT NULL, REGID numeric(18,0) NOT NULL, ITEMID citext NOT NULL,
  INVENIDX numeric(18,0) NOT NULL, ITEM_DATA citext NULL, PERIOD numeric(18,0) NOT NULL,
  CTIME numeric(18,0) NOT NULL, UTIME numeric(18,0) NOT NULL, PRICE numeric(18,0) NOT NULL,
  STATE numeric(18,0) NOT NULL, REGDATE timestamp(3) NULL DEFAULT getdate(),
  PRIMARY KEY (CID, SERVERID, REGID))"""
NEXT_GID_SQL = 'UPDATE skid_sequence_tb SET item_sq1 = item_sq1 + 1 RETURNING item_sq1'
INSERT_ITEM_SQL = 'SELECT pc_skid_insertitem(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
AUCTION_MIN = 20000


def rules():
    c = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    try:
        c.read('emulator.ini', encoding='utf-8')
    except (OSError, configparser.Error):
        pass
    a = c['auction'] if c.has_section('auction') else {}
    g = lambda k, d: int(str(a.get(k, d)).strip() or d)
    return {'days': g('days', 7), 'min_level': g('min_level', 1), 'item_fee': g('item_fee', 7), 'cars': g('cars', 1),
            'car_fee': g('car_fee', 10), 'drift': g('drift_items', 0), 'drift_fee': g('drift_fee', 10)}


def fee(price, pct):
    return max(1, int(price * pct / 100))


def run(cmd, req, sid, cid, cur, rows, one):
    D = Data()
    R = rules()
    secs = R['days'] * 86400
    cur.execute(VS_TABLE_SQL)
    for t in TABLES.values():           # XiAuctionMgr::UpdateAuctionPeriod: past their period -> expired
        cur.execute(f'UPDATE {t} SET state = 3 WHERE serverid = %s AND state = 1 AND '
                    f'extract(epoch FROM GetDate() - regdate)::bigint >= %s', (sid, secs))
    vis = D.visuals()
    names = {}

    def counters(c):
        if c not in names:
            r = one('SELECT regnum, buynum, sellnum FROM skid_auctionmileage_tb WHERE serverid = %s AND cid = %s', (sid, c))
            names[c] = [int(x or 0) for x in r] if r else [0, 0, 0]
        return names[c]

    def count_up(c, cname, col):
        cur.execute('INSERT INTO skid_auctionmileage_tb(serverid, cid, cname, regnum, buynum, sellnum) SELECT %s, %s, %s, 0, 0, 0'
                    ' WHERE NOT EXISTS (SELECT 1 FROM skid_auctionmileage_tb WHERE serverid = %s AND cid = %s)', (sid, c, cname, sid, c))
        cur.execute(f'UPDATE skid_auctionmileage_tb SET {col} = {col} + 1 WHERE serverid = %s AND cid = %s', (sid, c))

    def listing_rows(kind, where='', params=()):
        t = TABLES[kind]
        cols = {'item': 'cid, cname, regid, itemid, itemnum, nrandom, nupgrade, invenidx, price, state',
                'car': 'cid, cname, regid, itemid, invenidx, carid, cartype, basecolor, ngrade, price, state',
                'drift': 'cid, cname, regid, itemid, invenidx, item_data, period, ctime, price, state'}[kind]
        out = []
        for r in rows(f'SELECT {cols}, extract(epoch FROM GetDate() - regdate)::bigint FROM {t} WHERE serverid = %s{where} ORDER BY regid DESC',
                      (sid, *params)):
            r = list(r)
            x = {'kind': kind, 'cid': int(r[0]), 'seller': str(r[1]), 'serial': int(r[2]), 'id': str(r[3]),
                 'left': max(0, R['days'] - int(r[-1] or 0) // 86400)}
            if kind == 'item':
                i = D.info(x['id'])
                x.update(name=i['name'], level=i['level'], grade=i['grade'], count=int(r[4] or 1), random=int(r[5] or 0),
                         upgrade=int(r[6] or 0), inv=int(r[7]), price=int(r[8]), state=int(r[9]), value=i['value'] + int(r[5] or 0),
                         icon='item:' + x['id'].lower(), type=i['type'], desc=D.desc(x['id']))
            elif kind == 'car':
                v = D.cars.get(int(r[6]), {})
                x.update(name=v.get('name', f'#{r[6]}'), level=int(r[8] or 0), count=1, inv=int(r[4]), car=int(r[5]), type=int(r[6]),
                         color=int(r[7] or 0), grade=int(r[8] or 0), price=int(r[9]), state=int(r[10]),
                         icon='logo:' + v.get('model', '').lower(), model=v.get('model', '').lower())
            else:
                v = vis.get(x['id'], {})
                nm, desc = D.vshop(v.get('item', ''))
                x.update(name=nm or v.get('item') or x['id'], level=0, count=1, inv=int(r[4]), data=str(r[5] or ''),
                         period=int(r[6] or 0), ctime=int(r[7] or 0), price=int(r[8]), state=int(r[9]), cat=v.get('cat', 0),
                         catName=v.get('catName', ''), icon='item:' + v.get('item', '').lower(), desc=desc)
            x['hist'] = counters(x['cid'])
            out.append(x)
        return out

    me = one('SELECT cname, nlevel, gold, curcar, partinvenidx FROM skid_character_tb WHERE serverid = %s AND cid = %s', (sid, cid)) \
        if cid else None

    if cmd == 'auc_list':
        kind = req.get('kind', 'item')
        if kind not in TABLES:
            return {'error': 'bad_kind'}
        found = [x for x in listing_rows(kind, ' AND state = 1')]
        return {'list': found, 'rules': R, 'mito': int(me[2]) if me else 0, 'level': int(me[1]) if me else 0}

    if not me:
        return {'error': 'no_char'}
    cname, level, gold, cur_car, part_inv = str(me[0]), int(me[1]), int(me[2]), int(me[3] or 0), int(me[4] or 0)

    if cmd == 'auc_mine':
        out = []
        for k in TABLES:
            out += listing_rows(k, ' AND cid = %s', (cid,))
        return {'mine': out, 'rules': R, 'mito': gold}

    if level < R['min_level']:
        return {'error': 'auc_level'}

    def pay(n):
        r = one('UPDATE skid_character_tb SET gold = gold + %s WHERE serverid = %s AND cid = %s AND gold + %s >= 0 RETURNING gold',
                (n, sid, cid, n))
        return r is not None

    def new_item(item_id, count, random=0):
        nonlocal part_inv
        gid = int(one(NEXT_GID_SQL)[0])
        top = one('SELECT max(invenidx) FROM skid_item_tb WHERE serverid = %s AND cid = %s', (sid, cid))
        part_inv = max(part_inv, int(top[0] or 0) if top else 0) + 1
        cur.execute(INSERT_ITEM_SQL, (sid, cid, cname, gid, 0, part_inv, item_id, count, random, 0, 0, 0, '', '', 0))
        return part_inv

    if cmd == 'auc_buy':
        kind, serial = req.get('kind'), int(req.get('serial', 0))
        found = listing_rows(kind, ' AND regid = %s', (serial,)) if kind in TABLES else []
        x = found[0] if found else None
        if not x or x['state'] != ON_SALE:
            return {'error': 'auc_gone'}
        if x['cid'] == cid:
            return {'error': 'auc_own'}
        if kind == 'car' and not R['cars'] or kind == 'drift' and not R['drift']:
            return {'error': 'auc_closed'}
        if x['price'] > gold:
            return {'error': 'no_mito'}
        if kind == 'car':
            floors = 1 + int((one('SELECT hancoingarage FROM skid_character_tb WHERE serverid = %s AND cid = %s', (sid, cid)) or [0])[0] or 0)
            g_uid = next((v['uid'] for v in vis.values() if v.get('item') == 'i_d_garage'), '-')
            floors += int((one("SELECT count(*) FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND itemid IN (%s, %s)",
                               (sid, cid, 'i_d_garage', g_uid)) or [0])[0])
            ncars = int(one('SELECT count(*) FROM skid_car_tb WHERE serverid = %s AND cid = %s', (sid, cid))[0])
            if ncars >= floors * 8:
                return {'error': 'garage_full'}
        r = one(f"UPDATE {TABLES[kind]} SET state = 2 WHERE serverid = %s AND regid = %s AND state = 1 RETURNING 1", (sid, serial))
        if not r:
            return {'error': 'auc_gone'}
        if not pay(-x['price']):
            return {'error': 'no_mito'}
        count_up(cid, cname, 'buynum')
        count_up(x['cid'], x['seller'], 'sellnum')
        if kind == 'item':
            src = one('SELECT nrandom, nupgrade, assist_a, assist_b, box, ctime FROM skid_auction_tb WHERE serverid = %s AND regid = %s',
                      (sid, serial))
            info = D.info(x['id'])
            pile = None
            if info['type'] == 5:           # a usable item joins a stack with room (as BuyItem)
                pile = one('SELECT invenidx, stacknum FROM skid_item_tb WHERE serverid = %s AND cid = %s AND itemid = %s AND state = 0'
                           ' AND carid = 0 AND stacknum + %s <= %s ORDER BY invenidx LIMIT 1', (sid, cid, x['id'], x['count'], info['stack'] or 999))
            if pile:
                cur.execute('UPDATE skid_item_tb SET stacknum = stacknum + %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (x['count'], sid, cid, int(pile[0])))
            else:
                inv = new_item(x['id'], x['count'], int(src[0] or 0))
                box = int(src[4] or 0) if x['id'].startswith('dock_') else 0
                cur.execute('UPDATE skid_item_tb SET nrandom = %s, nupgrade = %s, assist_a = %s, assist_b = %s, box = %s, ctime = %s'
                            ' WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (int(src[0] or 0), int(src[1] or 0), src[2] or '', src[3] or '', box, src[5] or 0, sid, cid, inv))
        elif kind == 'drift':
            gid = int(one(NEXT_GID_SQL)[0])
            inv = max([int(r[0]) for r in rows('SELECT invenidx FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s', (sid, cid))] + [61]) + 1
            cur.execute('INSERT INTO skid_vsitem_tb(serverid, cid, cname, gid, itemid, invenidx, carid, state, item_data, period, ctime, utime)'
                        ' VALUES (%s,%s,%s,%s,%s,%s,0,0,%s,%s,%s,%s)', (sid, cid, cname, gid, x['id'], inv, x['data'], x['period'], x['ctime'], x['ctime']))
        else:
            src = one('SELECT cartype, basecolor, ngrade, nslot, fmitron, fkmh, itemid FROM skid_auctioncar_tb WHERE serverid = %s AND regid = %s',
                      (sid, serial))
            r = one('SELECT pc_skid_createcar(%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    (sid, cid, cname, int(src[0]), int(src[1] or 0), int(src[2] or 1), 1, int(src[4] or 0), int(src[5] or 0)))
            car_id = int(r[0] or -1) if r else -1
            if car_id <= 0:
                return {'error': 'auc_gone'}
            cur.execute('UPDATE skid_car_tb SET slot = %s WHERE serverid = %s AND cid = %s AND carid = %s', (int(src[3] or 0), sid, cid, car_id))
            new_item(str(src[6]), 1, car_id)          # its key, naming the car (NRANDOM = CarID)
        return {'bought': x['name'], 'price': x['price']}

    if cmd == 'auc_on':
        kind, price = req.get('kind', 'item'), int(req.get('price', 0) or 0)
        if price <= 0:
            return {'error': 'auc_price'}
        if kind == 'item':
            inv, count = int(req.get('inv', -1)), int(req.get('count', 1) or 1)
            it = one('SELECT itemid, stacknum, carid, state, nrandom, nupgrade, assist_a, assist_b, box, ctime, belonging FROM skid_item_tb'
                     ' WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
            if not it:
                return {'error': 'no_item'}
            iid, stack = str(it[0]), int(it[1] or 1)
            info = D.info(iid)
            r = D.parts.get(iid) or D.use.get(iid)
            col = 17 if iid in D.parts else 15
            tradeable = not r or len(r) <= col or str(r[col]).strip() not in ('0', 'n/a', '')
            if int(it[2] or 0) or (int(it[3] or 0) & 0xffff) != 0 or count < 1 or count > max(stack, 1) or info['kind'] == 'car':
                return {'error': 'auc_item'}
            if int(it[10] or 0) or int(it[5] or 0) < 0:
                return {'error': 'auc_item'}
            if (info['grade'] == 'H' or not tradeable) and not (int(it[8] or 0) and not iid.startswith('dock_')):
                return {'error': 'auc_box'}
            f = fee(price, R['item_fee'])
            if not pay(-f):
                return {'error': 'no_mito'}
            if info['type'] == 5 and count < stack:      # split the registered count off the stack
                cur.execute('UPDATE skid_item_tb SET stacknum = %s WHERE serverid = %s AND cid = %s AND invenidx = %s', (stack - count, sid, cid, inv))
                inv = new_item(iid, count)
                cur.execute('UPDATE skid_item_tb SET state = 4 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
                rnd, upg, aa, ab, box, ct = 0, 0, '', '', 0, 0
            else:
                cur.execute('UPDATE skid_item_tb SET state = 4 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
                rnd, upg, aa, ab, box, ct = int(it[4] or 0), int(it[5] or 0), it[6] or '', it[7] or '', int(it[8] or 0), it[9] or 0
                count = max(stack, 1)
            serial = int(one('SELECT coalesce(max(regid), 0) + 1 FROM skid_auction_tb WHERE serverid = %s', (sid,))[0])
            cur.execute('INSERT INTO skid_auction_tb(serverid, cid, cname, regid, itemid, itemnum, nrandom, nupgrade, invenidx, price, state,'
                        ' assist_a, assist_b, box, ctime) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',
                        (sid, cid, cname, serial, iid, count, rnd, upg, inv, price, aa, ab, box, ct))
        elif kind == 'drift':
            if not R['drift']:
                return {'error': 'auc_closed'}
            inv = int(req.get('inv', -1))
            v = one('SELECT itemid, item_data, period, ctime, utime, state FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND invenidx = %s',
                    (sid, cid, inv))
            if not v or int(v[5] or 0) != 0:
                return {'error': 'auc_item'}
            f = fee(price, R['drift_fee'])
            if not pay(-f):
                return {'error': 'no_mito'}
            cur.execute('UPDATE skid_vsitem_tb SET state = 4 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
            serial = int(one('SELECT coalesce(max(regid), 0) + 1 FROM skid_auctionvs_tb WHERE serverid = %s', (sid,))[0])
            cur.execute('INSERT INTO skid_auctionvs_tb(serverid, cid, cname, regid, itemid, invenidx, item_data, period, ctime, utime, price, state)'
                        ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)', (sid, cid, cname, serial, v[0], inv, v[1] or '', int(v[2] or 0),
                                                                       int(v[3] or 0), int(v[4] or 0), price))
        elif kind == 'car':
            if not R['cars']:
                return {'error': 'auc_closed'}
            car_id = int(req.get('car', 0))
            car = one('SELECT cartype, color, nupgrade, slot, mitron, km, auctioncnt FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s',
                      (sid, cid, car_id))
            if not car:
                return {'error': 'no_car'}
            if car_id == cur_car or one('SELECT 1 FROM skid_auctioncar_tb WHERE serverid = %s AND carid = %s AND cid = %s', (sid, car_id, cid)):
                return {'error': 'auc_car_use'}
            if int(car[6] or 0):
                return {'error': 'auc_car_twice'}
            if one('SELECT 1 FROM skid_item_tb WHERE serverid = %s AND cid = %s AND carid = %s AND (state::bigint & 65535) = 1', (sid, cid, car_id)):
                return {'error': 'car_parts'}
            model = D.cars.get(int(car[0]), {}).get('model', '')
            key = one('SELECT invenidx, itemid FROM skid_item_tb WHERE serverid = %s AND cid = %s AND state = 0 AND lower(itemid) = lower(%s)'
                      ' AND nrandom IN (%s, 0) ORDER BY nrandom DESC LIMIT 1', (sid, cid, model, car_id))
            if not key:
                return {'error': 'auc_no_key'}
            f = fee(price, R['car_fee'])
            if not pay(-f):
                return {'error': 'no_mito'}
            cur.execute('UPDATE skid_item_tb SET state = 4 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, int(key[0])))
            cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s AND state = 1', (sid, cid, car_id))
            serial = int(one('SELECT coalesce(max(regid), 0) + 1 FROM skid_auctioncar_tb WHERE serverid = %s', (sid,))[0])
            cur.execute('INSERT INTO skid_auctioncar_tb(serverid, cid, cname, regid, itemid, invenidx, carid, cartype, basecolor, ngrade, nslot,'
                        ' fmitron, fkmh, price, state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)',
                        (sid, cid, cname, serial, str(key[1]), int(key[0]), car_id, int(car[0]), int(car[1] or 0), int(car[2] or 1),
                         int(car[3] or 0), int(car[4] or 0), int(car[5] or 0), price))
        else:
            return {'error': 'bad_kind'}
        count_up(cid, cname, 'regnum')
        return {'serial': serial, 'fee': f}

    if cmd in ('auc_cancel', 'auc_collect'):
        kind, serial = req.get('kind'), int(req.get('serial', 0))
        found = listing_rows(kind, ' AND regid = %s AND cid = %s', (serial, cid)) if kind in TABLES else []
        x = found[0] if found else None
        if not x:
            return {'error': 'auc_gone'}
        t = TABLES[kind]
        if cmd == 'auc_cancel':
            if x['state'] not in (ON_SALE, EXPIRED):
                return {'error': 'auc_sold'}
            cur.execute(f'DELETE FROM {t} WHERE serverid = %s AND regid = %s', (sid, serial))
            if kind == 'drift':
                cur.execute('UPDATE skid_vsitem_tb SET state = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, x['inv']))
            else:
                cur.execute('UPDATE skid_item_tb SET state = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, x['inv']))
            return {'back': x['name']}
        if x['state'] != SOLD:
            return {'error': 'auc_not_sold'}
        cur.execute(f'DELETE FROM {t} WHERE serverid = %s AND regid = %s', (sid, serial))
        pay(x['price'])
        if kind == 'drift':
            cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, x['inv']))
        else:
            cur.execute('DELETE FROM skid_item_tb WHERE serverid = %s AND cid = %s AND invenidx = %s AND (state::bigint & 65535) = 4', (sid, cid, x['inv']))
        if kind == 'car':
            cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, x['car']))
            cur.execute('DELETE FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, x['car']))
            cur.execute('UPDATE skid_character_tb SET numcar = numcar - 1 WHERE serverid = %s AND cid = %s AND numcar > 0', (sid, cid))
        return {'collected': x['price']}

    return {'error': 'unknown_command'}
