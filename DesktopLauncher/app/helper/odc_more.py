"""openDC Launcher: the More windows on the server's own tables, as the game keeps them (dcemu/native/game):

community  SKID_FRIEND_TB (FSTATE 'F' friend, 'R' asked by me, 'C' asking me, 'B' blocked) and SKID_MSG_TB (social.py,
           mail.py: state 'N' new, 'R' read, 'K' kept)
ranking    experience and distance of every character of the server (rankings.py), the open crews (SKID_TEAM_TB)
coupon     Coupon.xlt with the counters (SKID_COUPONVALUE_TB columns, SKID_COUPONPARAMVALUE_TB 11 / 14) and the stamps
           (SKID_COUPONSTAMP_TB: 1 marked, 2 opened, 3 coupon taken) (coupons.py)
license    License.xlt; held = SKID_PLAYMODE_TB 'LIC_<LicenseID>' (licenses.py)
skill      Alchemy_SkillBook.xlt; learned = 'SKB_<SkillBookID>', manufacturing EXP = 'ALCHEMY' POINT (alchemy.py)
shop       VShopItem.xlt; a purchase is a SKID_VSITEM_TB row (on the car for the car categories, the one of the same slot
           replaced; drinks add days to the one held), paid in Mito or the account's G Coin (SKID_UNALISCOIN_TB) (vshop.py)
gotcha     the 2016 car machines: RewardGroup rw_cash_gacha_2015 / rw_mito_gacha_2015 rolled as the game rolls them
           (driftuse.roll): a slot car's V1 gift box or 10 Capsule Points, for 300 G Coin / 50000 Mito (gotcha.py)

Changes need the game closed for that character (the launcher checks it), as the inventory's.
"""
import re
import configparser
import os
import random
import time

from odc_inv import Data, read_xlt, num, DRIFT_EQUIP, DRIFT_FIXED, repair_vs, look_entry

COUPON_COLS = ['pvpbattle', 'quickservice', 'chasing', 'combo', 'drivetime', 'drift', 'artdrive', 'jump', 'revdrive']
EXTENDS = (15, 17, 18, 20, 21, 24, 28, 29, 49)
NEXT_GID_SQL = 'UPDATE skid_sequence_tb SET item_sq1 = item_sq1 + 1 RETURNING item_sq1'
INSERT_ITEM_SQL = 'SELECT pc_skid_insertitem(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
PLAYMODE_ADD = ("INSERT INTO skid_playmode_tb(serverid, cid, cname, modeid, cdate, lastdate, trycnt, wincnt, point, playtime, nexp,"
                " gamemoney, bestcnt, retirecnt) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),0,0,%s,0,0,0,0,0)")


def ini():
    c = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), strict=False, interpolation=None)
    try:
        c.read('emulator.ini', encoding='utf-8')
    except (OSError, configparser.Error):
        pass
    return c


def xlt(D, name):
    try:
        return read_xlt(os.path.join(D.base, 'Init', name))
    except OSError:
        return []


def vis_table(D):
    """VisualItem.xlt with the car types each row fits (header row 2: a car type per column from 7, '1' = fits)."""
    x = xlt(D, 'VisualItem.xlt')
    if len(x) < 5:
        return {}
    hdr = x[2]
    types = {i: int(h) for i, h in enumerate(hdr) if i >= 7 and str(h).strip().isdigit()}
    out = {}
    for r in x[4:]:
        if len(r) > 6 and r[4].strip().isdigit() and r[1].strip().isdigit():
            e = {'vid': r[4].strip(), 'cat': int(r[1]), 'index': num(r[2]), 'item': r[3].strip(), 'name': r[5].strip(),
                 'value': r[6].strip(), 'cars': {t for i, t in types.items() if i < len(r) and r[i].strip() == '1'}}
            out[r[4].strip()] = e
            out.setdefault('#' + r[3].strip(), e)        # by the item name (what SKID_VSITEM_TB.ITEMID holds)
    return out


def look_lists(D):
    """The looks chosen at the purchase of the 2011 stat items: SpoilerList (AeroWing: type 1, BoosterWing: type 2) and
    TireList (TireWheel: the listed tires), as dcemu misc.visual_item reads the item text (the Spoiler / Tire ID)."""
    wings, tires = [], []
    for r in xlt(D, 'SpoilerList.xlt')[3:]:
        if len(r) > 7 and r[1].strip().isdigit() and r[3].strip() == '1':
            wings.append({'id': int(r[1]), 'name': r[2].strip(), 'type': num(r[6]), 'file': r[7].strip().lower()})
    for r in xlt(D, 'TireList.xlt')[3:]:
        if len(r) > 10 and r[1].strip().isdigit() and r[3].strip() == '1':
            tires.append({'id': int(r[1]), 'name': r[2].strip(), 'file': r[7].strip().lower().rsplit('.', 1)[0], 'icon': r[10].strip()})
    return wings, tires


def run(cmd, req, sid, cid, cur, rows, one):
    D = Data()
    ch = one('SELECT cname, nlevel, gold, curcar, memberid, partinvenidx, nexp, km FROM skid_character_tb WHERE serverid = %s AND cid = %s',
             (sid, cid))
    cname, level, gold, cur_car, member = str(ch[0]), int(ch[1]), int(ch[2]), int(ch[3] or 0), str(ch[4])
    part_inv = int(ch[5] or 0)
    coin_row = one('SELECT coin FROM skid_unaliscoin_tb WHERE memberid = %s', (member,))
    coin = int(coin_row[0] or 0) if coin_row else 0
    what = cmd[5:]                       # more_<what>

    def pay(mito=0, cc=0):
        if mito:
            r = one('UPDATE skid_character_tb SET gold = gold - %s WHERE serverid = %s AND cid = %s AND gold >= %s RETURNING gold',
                    (mito, sid, cid, mito))
            if not r:
                return False
        if cc:
            r = one('UPDATE skid_unaliscoin_tb SET coin = coin - %s, lastaction = %s, lastcname = %s, lastdate = GetDate()'
                    ' WHERE memberid = %s AND coin >= %s RETURNING coin', (cc, 'LAUNCHER', cname, member, cc))
            if not r:
                return False
        return True

    def new_item(item_id, count, random_=0):
        nonlocal part_inv
        gid = int(one(NEXT_GID_SQL)[0])
        top = one('SELECT max(invenidx) FROM skid_item_tb WHERE serverid = %s AND cid = %s', (sid, cid))
        part_inv = max(part_inv, int(top[0] or 0) if top else 0) + 1
        cur.execute(INSERT_ITEM_SQL, (sid, cid, cname, gid, 0, part_inv, item_id, count, random_, 0, 0, 0, '', '', 0))
        return part_inv

    def give_item(item_id, count):
        """a usable item onto a pile with room, else a new one."""
        info = D.info(item_id)
        if info['type'] == 5:
            pile = one('SELECT invenidx FROM skid_item_tb WHERE serverid = %s AND cid = %s AND itemid = %s AND state = 0 AND carid = 0'
                       ' AND stacknum + %s <= %s ORDER BY invenidx LIMIT 1', (sid, cid, item_id, count, info['stack'] or 999))
            if pile:
                cur.execute('UPDATE skid_item_tb SET stacknum = stacknum + %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                            (count, sid, cid, int(pile[0])))
                return
        new_item(item_id, count)

    def char_id(name):
        r = one("SELECT cid, cname FROM skid_character_tb WHERE serverid = %s AND ucname = upper(%s) AND state = 'P'", (sid, (name or '').strip()))
        return (int(r[0]), str(r[1])) if r else (None, None)

    def playmodes(prefix):
        return {str(m).strip(): int(p or 0) for m, p in rows('SELECT modeid, point FROM skid_playmode_tb WHERE serverid = %s AND cid = %s'
                                                              ' AND modeid LIKE %s', (sid, cid, prefix + '%'))}

    base = {'mito': gold, 'cc': coin, 'level': level, 'name': cname}

    # ---------------------------------------------------------------- community
    if what == 'community':
        online = set(n.lower() for n in req.get('online', []))
        friends = []
        for fcid, st, name, lv, team in rows("""SELECT f.fcid, f.fstate, c.cname, c.nlevel, t.teamname FROM skid_friend_tb f
                JOIN skid_character_tb c ON c.serverid = f.serverid AND c.cid = f.fcid
                LEFT JOIN skid_team_tb t ON t.serverid = c.serverid AND t.tid = c.teamid
                WHERE f.serverid = %s AND f.cid = %s ORDER BY c.cname""", (sid, cid)):
            friends.append({'cid': int(fcid), 'state': str(st).strip(), 'name': str(name), 'level': int(lv or 0), 'team': str(team) if team else '',
                            'online': str(name).lower() in online})
        msgs = [{'mid': int(m), 'from': str(sn or ''), 'kind': int(k or 0), 'state': str(s or 'N').strip(), 'subject': str(su or ''),
                 'text': str(tx or ''), 'gold': int(g or 0), 'item': str(it or ''), 'date': str(d)[:16] if d else ''}
                for m, sn, k, s, su, tx, g, it, d in rows("""SELECT mid, sname, msgkind, msgstate, subject, content, gold, item, senddate
                    FROM skid_msg_tb WHERE serverid = %s AND receiver_id = %s ORDER BY senddate DESC""", (sid, cid))]
        return dict(base, friends=friends, msgs=[m for m in msgs if m['kind'] & 0xffff in (0, 300)])

    if what in ('friend_add', 'friend_del', 'block', 'unblock'):
        oid, oname = char_id(req.get('name'))
        if not oid or oid == cid:
            return {'error': 'no_runner'}
        if what == 'friend_add':
            if one("SELECT 1 FROM skid_friend_tb WHERE serverid = %s AND cid = %s AND fcid = %s AND fstate = 'F'", (sid, cid, oid)):
                return {'error': 'already_friend'}
            cur.execute('DELETE FROM skid_friend_tb WHERE serverid = %s AND ((cid = %s AND fcid = %s) OR (cid = %s AND fcid = %s)) AND fstate <> %s',
                        (sid, cid, oid, oid, cid, 'B'))
            cur.execute("INSERT INTO skid_friend_tb(serverid, cid, fcid, fstate) VALUES (%s,%s,%s,'R'), (%s,%s,%s,'C')", (sid, cid, oid, sid, oid, cid))
        elif what == 'friend_del':
            cur.execute("DELETE FROM skid_friend_tb WHERE serverid = %s AND ((cid = %s AND fcid = %s) OR (cid = %s AND fcid = %s)) AND fstate <> 'B'",
                        (sid, cid, oid, oid, cid))
        elif what == 'block':
            cur.execute('DELETE FROM skid_friend_tb WHERE serverid = %s AND cid = %s AND fcid = %s', (sid, cid, oid))
            cur.execute("DELETE FROM skid_friend_tb WHERE serverid = %s AND cid = %s AND fcid = %s AND fstate <> 'B'", (sid, oid, cid))
            cur.execute("INSERT INTO skid_friend_tb(serverid, cid, fcid, fstate) VALUES (%s,%s,%s,'B')", (sid, cid, oid))
        else:
            cur.execute("DELETE FROM skid_friend_tb WHERE serverid = %s AND cid = %s AND fcid = %s AND fstate = 'B'", (sid, cid, oid))
        return {'name': oname}

    if what == 'friend_accept':
        oid = int(req.get('fcid', 0))
        cur.execute("UPDATE skid_friend_tb SET fstate = 'F' WHERE serverid = %s AND ((cid = %s AND fcid = %s) OR (cid = %s AND fcid = %s))",
                    (sid, cid, oid, oid, cid))
        return {}

    if what == 'msg_send':
        oid, oname = char_id(req.get('name'))
        if not oid:
            return {'error': 'no_runner'}
        if one("SELECT 1 FROM skid_friend_tb WHERE serverid = %s AND cid = %s AND fcid = %s AND fstate = 'B'", (sid, oid, cid)):
            return {'error': 'msg_blocked'}
        text = (req.get('text') or '').strip()[:200] or ' '
        cur.execute("""INSERT INTO skid_msg_tb(serverid, receiver_id, sender_id, sname, msgkind, msgstate, subject, content, gold, item, senddate)
                       VALUES (%s,%s,%s,%s,0,'N',%s,%s,0,'',GetDate())""", (sid, oid, cid, cname, text[:20], text))
        return {'name': oname}

    if what in ('msg_read', 'msg_keep', 'msg_del'):
        mid = int(req.get('mid', 0))
        if what == 'msg_del':
            cur.execute('DELETE FROM skid_msg_tb WHERE serverid = %s AND receiver_id = %s AND mid = %s', (sid, cid, mid))
        else:
            cur.execute('UPDATE skid_msg_tb SET msgstate = %s WHERE serverid = %s AND receiver_id = %s AND mid = %s',
                        ('R' if what == 'msg_read' else 'K', sid, cid, mid))
        return {}

    # ---------------------------------------------------------------- ranking
    if what == 'ranking':
        allc = rows("""SELECT c.cid, c.cname, c.nlevel, c.nexp, c.km, c.curcar, (SELECT cartype FROM skid_car_tb k WHERE k.serverid = c.serverid
                AND k.cid = c.cid AND k.carid = c.curcar), (SELECT nupgrade FROM skid_car_tb k WHERE k.serverid = c.serverid AND k.cid = c.cid
                AND k.carid = c.curcar) FROM skid_character_tb c WHERE c.serverid = %s AND c.state = 'P'""", (sid,))
        me = next((r for r in allc if int(r[0]) == cid), None)
        car = D.cars.get(int(me[6] or 0), {}).get('name', '') if me else ''
        out = []
        for key, col in (('exp', 3), ('km', 4)):
            order = sorted(allc, key=lambda r: (-int(r[col] or 0), -int(r[2] or 0), int(r[0])))
            pos = next((i + 1 for i, r in enumerate(order) if int(r[0]) == cid), 0)
            top = [{'name': str(r[1]), 'level': int(r[2] or 0), 'value': int(r[col] or 0)} for r in order[:10]]
            out.append({'key': key, 'pos': pos if me and int(me[col] or 0) > 0 else 0, 'value': int(me[col] or 0) if me else 0, 'top': top})
        for key in ('make', 'ss', 'mission', 'gs', 'huv', 'gt', 'neohuv', 'mvp'):
            out.append({'key': key, 'pos': 0, 'value': 0, 'top': []})
        teams = [{'name': str(n), 'master': str(m or ''), 'members': int(c or 0), 'points': int(p or 0), 'wins': int(w or 0), 'level': int(l or 0),
                  'created': str(d)[:10] if d else ''} for n, m, c, p, w, l, d in rows(
                      """SELECT teamname, cname, membercnt, teampoint, channelwincnt, teamlevel, createdate FROM skid_team_tb
                         WHERE serverid = %s AND teamstate = 'A' ORDER BY teampoint DESC, channelwincnt DESC, tid""", (sid,))]
        return dict(base, cats=out, car=car, grade=int(me[7] or 0) if me else 0, teams=teams)

    # ---------------------------------------------------------------- coupons
    if what in ('coupon', 'coupon_give'):
        rows_, kind = [], -1
        for r in xlt(D, 'Coupon.xlt')[4:]:
            if len(r) < 11 or not r[1].strip().lstrip('-').isdigit():
                continue
            if r[0].strip():
                kind += 1
            car_name = D.cars.get(num(r[6]), {}).get('name') or r[5].strip()     # the car's own name ('SS' rows: the quest cars)
            if any(x['carId'] == num(r[6]) and x['grade'] == num(r[8]) and x['dbType'] == num(r[9]) and x['dbIdx'] == num(r[10]) for x in rows_):
                continue
            rows_.append({'type': kind, 'index': num(r[1]), 'count': num(r[3]), 'minutes': num(r[4]), 'car': car_name, 'carId': num(r[6]),
                          'item': r[7].strip(), 'grade': num(r[8]), 'dbType': num(r[9]), 'dbIdx': num(r[10])})
        if what == 'coupon_give':
            c = next((x for x in rows_ if x['dbType'] == int(req.get('dbType', -1)) and x['dbIdx'] == int(req.get('dbIdx', -1))), None)
            if not c:
                return {'error': 'no_item'}
            if one('SELECT 1 FROM skid_couponstamp_tb WHERE serverid = %s AND cid = %s AND ctype = %s AND stampidx = %s AND state = 3',
                   (sid, cid, c['dbType'], c['dbIdx'])):
                return {'error': 'coupon_taken'}
            cur.execute('DELETE FROM skid_couponstamp_tb WHERE serverid = %s AND cid = %s AND ctype = %s AND stampidx = %s', (sid, cid, c['dbType'], c['dbIdx']))
            cur.execute('INSERT INTO skid_couponstamp_tb(serverid, cid, cname, ctype, stampidx, state) VALUES (%s,%s,%s,%s,%s,3)',
                        (sid, cid, cname, c['dbType'], c['dbIdx']))
            give_item(c['item'], 1)
            return {'item': c['item']}
        vals = one('SELECT ' + ', '.join(COUPON_COLS + ['undercity']) + ' FROM skid_couponvalue_tb WHERE serverid = %s AND cid = %s', (sid, cid))
        vals = [float(v or 0) for v in vals] if vals else [0.0] * 10
        params = {int(t): float(v or 0) for t, v in rows('SELECT ctype, value FROM skid_couponparamvalue_tb WHERE serverid = %s AND cid = %s',
                                                         (sid, cid)) if str(t).strip().lstrip('-').isdigit()}
        stamps = {(int(t), int(i)): int(s) for t, i, s in rows('SELECT ctype, stampidx, state FROM skid_couponstamp_tb WHERE serverid = %s AND cid = %s',
                                                               (sid, cid))}
        for c in rows_:
            if c['dbType'] in (11, 14, 15):
                now_ = params.get(c['dbType'], 0)
            elif c['type'] < 9:
                now_ = vals[c['type']] / 60 if c['minutes'] != -1 else vals[c['type']]
            elif c['type'] == 9 and c['index'] == 0:
                now_ = vals[9]
            else:
                now_ = 0
            car = D.cars.get(c['carId'], {})
            up = D.upgrade.get((c['carId'], c['grade'])) or {}
            c.update(model=car.get('model', '').lower(), tire=D.tires.get(car.get('tire', ''), ''), tire_scale=car.get('tire_scale'), tire_width=car.get('tire_width'),
                     lvl=car.get('lvl', 1), stats=[up.get('Speed', 0), up.get('Accel', 0), up.get('Crash', 0), up.get('Boost', 0)],
                     price=up.get('Price', 0))
            c['now'] = int(now_)
            c['state'] = stamps.get((c['dbType'], c['dbIdx']), 0)
        return dict(base, coupons=rows_)

    # ---------------------------------------------------------------- licenses
    if what in ('license', 'license_set'):
        x = xlt(D, 'License.xlt')
        hdr = next((i for i, r in enumerate(x) if 'LicenseID' in r), 2)
        col = {n: i for i, n in enumerate(x[hdr])}
        lics = []
        for r in x[hdr + 1:]:
            if len(r) <= col.get('MountEffectText', 13) or not r[col['LicenseID']].strip().isdigit():
                continue
            if r[col['Support']].strip() != '1' or r[col['Visible']].strip() != '1':
                continue
            lics.append({'id': int(r[col['LicenseID']]), 'icon': r[col['LicenseIDName']].strip(), 'grade': num(r[col['Grade']]), 'name': r[col['LicenseName']].strip(),
                         'info': r[col['LicenseInfo']].strip().strip('"'), 'cond': r[col['GainConditionText']].strip().strip('"'),
                         'effect': r[col['MountEffectText']].strip().strip('"'), 'order': num(r[col['DisplayOrder']]),
                         'cat': r[col['Category']].strip()})
        if what == 'license_set':
            lid, on = int(req.get('lid', 0)), bool(req.get('on'))
            if not any(l['id'] == lid for l in lics):
                return {'error': 'no_item'}
            cur.execute('DELETE FROM skid_playmode_tb WHERE serverid = %s AND cid = %s AND modeid = %s', (sid, cid, f'LIC_{lid}'))
            if on:
                cur.execute(PLAYMODE_ADD, (sid, cid, cname, f'LIC_{lid}', 1))
            return {}
        held = playmodes('LIC_')
        for l in lics:
            l['held'] = f"LIC_{l['id']}" in held
        return dict(base, licenses=sorted(lics, key=lambda l: (l['grade'], l['order'])),
                    money=sum(l['grade'] for l in lics if l['held']))

    # ---------------------------------------------------------------- manufacturing
    if what in ('skill', 'skill_set'):
        x = xlt(D, 'Alchemy_SkillBook.xlt')
        books = []
        for r in x[3:]:
            if len(r) > 16 and r[1].strip() and r[0].strip().isdigit():
                mats = [(r[i].strip(), num(r[i + 1])) for i in (6, 8, 10, 12) if r[i].strip()]
                books.append({'id': r[1].strip(), 'req': num(r[2]), 'group': r[3].strip(), 'name': r[4].strip(),
                              'mats': [[D.info(m)['name'], n, m] for m, n in mats], 'result': r[14].strip(), 'resultName': D.info(r[14].strip())['name'],
                              'count': num(r[15])})
        if what == 'skill_set':
            bid, on = req.get('book', ''), bool(req.get('on'))
            if not any(b['id'] == bid for b in books):
                return {'error': 'no_item'}
            cur.execute('DELETE FROM skid_playmode_tb WHERE serverid = %s AND cid = %s AND modeid = %s', (sid, cid, f'SKB_{bid}'))
            if on:
                cur.execute(PLAYMODE_ADD, (sid, cid, cname, f'SKB_{bid}', 1))
            return {}
        pm = playmodes('SKB_')
        exp = (playmodes('ALCHEMY').get('ALCHEMY') or 0)
        levels = [(num(r[1]), num(r[2]), r[3].strip()) for r in xlt(D, 'Alchemy_LevelModify.xlt')[3:] if len(r) > 3 and r[1].strip().isdigit()]
        lv, name, pct, prev = 1, levels[0][2] if levels else '', 0, 0
        for mx, l, n in levels:
            if exp < mx:
                lv, name, pct = l, n, int((exp - prev) * 100 / max(1, mx - prev))
                break
            prev = mx
        else:
            if levels:
                lv, name, pct = levels[-1][1], levels[-1][2], 100
        for b in books:
            b['learned'] = f"SKB_{b['id']}" in pm
        return dict(base, books=books, skLevel=lv, skName=name, skPct=pct, skExp=exp)

    # ---------------------------------------------------------------- drift shop
    vis = D.visuals()
    by_name = {v['item'].lower(): (v['uid'], v) for v in vis.values()}
    if what in ('shop', 'shop_buy'):
        repair_vs(cur, rows, sid, cid, vis)
    if what in ('shop', 'shop_buy'):
        x = xlt(D, 'VShopItem.xlt')
        col = {n: i for i, n in enumerate(x[2])} if len(x) > 2 else {}
        P = lambda r, k: num(r[col[k]]) if k in col and len(r) > col[k] else 0
        items, onsale = [], set()
        for r in x[3:]:
            # the client lists a row with SellStage <= Etc.VShopOpenStage (1) (dcemu vshop.row_changes)
            if len(r) < 56:
                continue
            # SellStage % 1000 (0 -> 100) must be <= 1: the rows 1 and 1001 (the car's own aero kits, the Aero sets)
            try:
                stage = int(r[col['SellStage']].strip() or 0) % 1000
            except ValueError:
                continue
            if r[col['Support']].strip() == '1' and stage == 1:
                onsale.add(r[col['ItemName']].strip().lower())
            if r[col['Support']].strip() != '1' or not r[col['ItemName']].strip() or stage != 1:
                continue
            iname = r[col['ItemName']].strip()
            v = by_name.get(iname.lower())
            if not v:
                continue
            # a car's own aero kits (pc_0071s_02 ...) are not rows of the list: the game's Aero tab has the three Aero
            # sets, and the car's kits are the A / B / C types in the bar under the car
            if v[1]['cat'] == 6 and iname.lower().startswith('pc_0'):
                continue
            # the single wings (SPOILER rows: i_d_s_..., <car>_sp01) are the picks of the Aero Wing / Booster Wing bar,
            # not rows of the list (the game's Aero Wing tab lists the four AeroWing items)
            if r[col['Category']].strip() == 'SPOILER':
                continue
            # as the game's list: paint / neon only the colour-window items (Paint S15, C15, S25+, C25+ ...), tire
            # wheel only the four Tire items (their bar picks the wheel); the single tires are not rows
            sub = r[col['Category']].strip()
            if sub in ('TIRE', 'GLOSSTIRE'):
                continue
            if sub in ('PAINT', 'PAINTHIGHGLOSS', 'UNDERNEON') and not re.search(r'_[SC]\d+\+?$', iname, re.I):
                continue
            prices = []
            if P(r, 'UseHancoin'):
                for d in ('7D', '30D', '90D', '365D', '0D'):
                    if P(r, '$Price ' + d):
                        prices.append({'days': 0 if d == '0D' else P(r, 'Period ' + d) or int(d[:-1]), 'cc': P(r, '$Price ' + d)})
            if P(r, 'Use Mito'):
                for d in ('7D', '30D', '90D', '365D', '0D'):
                    if P(r, 'Mito Price' + d):
                        prices.append({'days': 0 if d == '0D' else P(r, 'Period ' + d) or int(d[:-1]), 'mito': P(r, 'Mito Price' + d)})
                if not prices and P(r, 'Mito Price'):
                    prices.append({'days': 0, 'mito': P(r, 'Mito Price')})
            if not prices:
                continue
            items.append({'uid': r[col['UniqueId']].strip(), 'id': iname, 'vid': v[0], 'cat': v[1]['cat'], 'name': r[col['MarketName']].strip() or iname,
                          'desc': r[col['Desc (Tooltip)']].strip().replace('\\n', '\n'), 'top': r[col['Top Category']].strip(),
                          'sub': r[col['Category']].strip(), 'prices': prices, 'order': P(r, 'Display Order'),
                          'bonus': [P(r, 'Bonus Speed'), P(r, 'Bonus Accel'), P(r, 'Bonus Crash'), P(r, 'Bonus Boost')]})
        if what == 'shop':
            VT = vis_table(D)
            VT = {k: v for k, v in VT.items() if not k.startswith('#')}
            VN = {v['item']: v for v in VT.values()}
            VNL = {k.lower(): v for k, v in VN.items()}
            wings, tires = look_lists(D)
            for it in items:
                v = VT.get(it['vid']) or {}
                it['index'] = v.get('index', 0)
                it['value'] = v.get('value', '')
                low = it['id'].lower()
                # the options bar: a look picked at the purchase (generic aero sets, aero / booster wings, tire wheels)
                if it['cat'] in (1, 32, 2, 3):
                    le = look_entry(dict(vis.get(it['vid']) or {}, cat=it['cat'], item=it['id'], index=it['index']), '', [], [], vis)
                    it['rgb'], it['pal'] = le.get('rgb'), le.get('pal')
                it['pick'] = ('aero' if it['cat'] == 6 and not it['index'] else 'aerowing' if low.startswith('i_g_aerowing')
                              else 'boosterwing' if low.startswith('i_g_boosterwing') else 'tirewheel' if low.startswith('i_g_tire') else '')
            cars = []
            for c, t, g, col in rows('SELECT carid, cartype, nupgrade, color FROM skid_car_tb WHERE serverid = %s AND cid = %s ORDER BY carid', (sid, cid)):
                t = int(t)
                info = D.cars.get(t, {})
                aero = [{'vid': v['vid'], 'name': v['name'], 'file': v['item'].lower()} for v in sorted(VT.values(), key=lambda v: v['index'])
                        if v['cat'] == 6 and v['index'] and t in v['cars'] and not v['item'].lower().endswith('_c')
                        and (v['item'].lower().endswith('_01') or v['item'].lower() in onsale)]
                # A Type is the car's basic look; B / C only the kits whose shop row is on sale (Dragoon: A only)
                # the Aero sets (pc_Aero ...) fit every car: its A type is the car's own look, B / C its kits
                fits = [it['uid'] for it in items if it['cat'] not in DRIFT_EQUIP or t in (VT.get(it['vid']) or {}).get('cars', ())
                        or it.get('pick') == 'aero']
                on = [{'vid': (VN.get(str(i).strip()) or {}).get('vid', ''), 'text': str(tx or ''), 'cat': (VN.get(str(i).strip()) or {}).get('cat'),
                       'item': str(i).strip().lower(), 'index': (VN.get(str(i).strip()) or {}).get('index', 0)}
                      for i, tx in rows('SELECT itemid, item_data FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s AND state = 1',
                                        (sid, cid, int(c)))]
                wl, tl = D.look_lists()
                look = []
                for i, tx in rows('SELECT itemid, item_data FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s AND state = 1', (sid, cid, int(c))):
                    v = vis.get(str(i).strip())
                    if v:
                        look.append(dict(look_entry(v, str(tx or ''), wl, tl, vis), uid=v['uid']))
                # the wings this car may take: VisualItem's car list (the classic ones fit all, ASTRO / Squall /
                # HYKAN and the <car>_sp01 wings only their cars)
                wfit = [w['id'] for w in wings if t in (VNL.get(w['file']) or {}).get('cars', ())]
                # a timed car upgrade on it (category 38): the car is that V while it lasts (shown right after buying)
                boost = 0
                for i, per, ct in rows('SELECT itemid, period, ctime FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s'
                                       ' AND state = 1', (sid, cid, int(c))):
                    v = vis.get(str(i).strip())
                    if not v or v['cat'] != 38:
                        continue
                    if int(per or 0) > 0 and ct:
                        try:
                            import datetime
                            t0 = ct if isinstance(ct, datetime.datetime) else datetime.datetime.fromtimestamp(int(ct))
                            if (datetime.datetime.now() - t0).days >= int(per):
                                continue
                        except (TypeError, ValueError, OverflowError, OSError):
                            pass
                    boost = max(boost, D.upgrade_grade(v['item']))
                cars.append({'id': int(c), 'type': t, 'look': look, 'wings': wfit, 'grade': max(int(g), boost), 'name': info.get('name', f'#{t}'), 'model': info.get('model', '').lower(),
                             'tire': D.tires.get(info.get('tire', ''), ''), 'tire_scale': info.get('tire_scale'), 'tire_width': info.get('tire_width'),
                             'color': int(col or 0) & 0xffffffff, 'current': int(c) == cur_car, 'fits': fits, 'aero': aero, 'on': on,
                             'up': [[(D.upgrade.get((t, v)) or {}).get(k, 0) for k in ('Speed', 'Accel', 'Crash', 'Boost')] for v in range(1, 10)]})
            return dict(base, items=items, cars=cars, wings=wings, tires=tires,
                        palette_items={it['vid']: it['index'] for it in items if it['cat'] in (1, 2, 3, 32)})
        it = next((i for i in items if i['uid'] == str(req.get('uid'))), None)
        if not it:
            return {'error': 'no_item'}
        price = next((p for p in it['prices'] if p['days'] == int(req.get('days', -1)) and ('cc' in p) == (req.get('cur') == 'cc')), None)
        if not price:
            return {'error': 'shop_price'}
        car = int(req.get('car', 0) or 0)
        text = str(req.get('text') or '')[:20]
        if it['cat'] in DRIFT_EQUIP and not one('SELECT 1 FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car)):
            return {'error': 'no_car'}
        # a permanent V upgrade (category 14, i_d_u_01 V2 .. i_d_u_08 V9): as the game's drift shop, buying it raises the
        # chosen car one grade at once (dcemu cars.upgrade_car: grade + 1, the level of that grade, not on auction);
        # no drift item is made
        if it['cat'] == 14:
            grade = D.upgrade_grade(it['id'])
            row = one('SELECT nupgrade FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car))
            if not row:
                return {'error': 'no_car'}
            if int(row[0]) + 1 != grade:
                return {'error': 'upgrade_grade', 'grade': int(row[0])}
            if one('SELECT 1 FROM information_schema.tables WHERE lower(table_name) = %s', ('skid_auctioncar_tb',)) and \
                    one('SELECT 1 FROM skid_auctioncar_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car)):
                return {'error': 'car_auction'}
            ctype = int(one('SELECT cartype FROM skid_car_tb WHERE serverid = %s AND cid = %s AND carid = %s', (sid, cid, car))[0])
            up = D.upgrade.get((ctype, grade))
            lvl = one('SELECT nlevel FROM skid_character_tb WHERE serverid = %s AND cid = %s', (sid, cid))
            if not up or (lvl and int(lvl[0]) < int(up.get('Req Level') or 0)):
                return {'error': 'upgrade_level'}
            if not pay(mito=price.get('mito', 0), cc=price.get('cc', 0)):
                return {'error': 'no_mito' if 'mito' in price else 'no_cc'}
            cur.execute(f'UPDATE skid_car_tb SET nupgrade = %s, up{grade}_date = GetDate() WHERE serverid = %s AND cid = %s AND carid = %s',
                        (grade, sid, cid, car))
            return {'bought': it['name'], 'grade': grade}
        if not pay(mito=price.get('mito', 0), cc=price.get('cc', 0)):
            return {'error': 'no_mito' if 'mito' in price else 'no_cc'}
        now = int(time.time())
        held = None
        if it['cat'] in EXTENDS and price['days']:
            held = one('SELECT invenidx, period, ctime FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND itemid = %s AND state <> 4'
                       ' ORDER BY invenidx LIMIT 1', (sid, cid, it['id']))
        if held and int(held[1] or 0) > 0:
            cur.execute('UPDATE skid_vsitem_tb SET period = period + %s WHERE serverid = %s AND cid = %s AND invenidx = %s',
                        (price['days'], sid, cid, int(held[0])))
            return {'bought': it['name'], 'extended': True}
        on_car = it['cat'] in DRIFT_EQUIP
        if on_car:
            same = {1: {1, 32}, 32: {1, 32}}.get(it['cat'], {it['cat']})
            for inv, cat in [(int(a), vis.get(str(b).strip(), {}).get('cat')) for a, b in rows(
                    'SELECT invenidx, itemid FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND carid = %s AND state = 1', (sid, cid, car))]:
                if cat in same:
                    if cat in DRIFT_FIXED:
                        cur.execute('DELETE FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
                    else:
                        cur.execute('UPDATE skid_vsitem_tb SET state = 0 WHERE serverid = %s AND cid = %s AND invenidx = %s', (sid, cid, inv))
        gid = int(one(NEXT_GID_SQL)[0])
        inv = max([int(r[0]) for r in rows('SELECT invenidx FROM skid_vsitem_tb WHERE serverid = %s AND cid = %s', (sid, cid))] + [61]) + 1
        cur.execute('INSERT INTO skid_vsitem_tb(serverid, cid, cname, gid, itemid, invenidx, carid, state, item_data, period, ctime, utime)'
                    ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (sid, cid, cname, gid, it['id'], inv, car if on_car else 0, 1 if on_car else 0, text, price['days'], now, 0))
        return {'bought': it['name']}

    # ---------------------------------------------------------------- gotcha
    if what in ('gotcha', 'gotcha_info'):
        c = ini()
        g = c['gotcha'] if c.has_section('gotcha') else {}
        machine = 'cash' if req.get('machine') == 'cc' else 'mito'
        price = num(str(g.get('coin_price' if machine == 'cash' else 'mito_price', '0'))) or (300 if machine == 'cash' else 50000)
        groups = {}
        for r in xlt(D, 'RewardGroup.xlt')[3:]:
            if len(r) > 11 and r[1].strip():
                groups.setdefault(r[1].strip(), []).append((r[3].strip(), r[5].strip(), num(r[7]), num(r[11].strip() or '0'), r[4].strip(),
                                                            r[2].strip().strip('"')))

        def car_of(desc):
            """'440 441' (Reward_Description of a slot's box): the car type the box holds."""
            ids = [int(x) for x in desc.split() if x.isdigit()]
            t = ids[-1] if ids else 0
            car = D.cars.get(t)
            if not car:
                return None
            up = D.upgrade.get((t, 1)) or {}
            return {'type': t, 'name': car['name'], 'model': car['model'].lower(), 'tire': D.tires.get(car.get('tire', ''), ''),
                    'tire_scale': car['tire_scale'], 'tire_width': car['tire_width'],
                    'stats': [up.get('Speed', 0), up.get('Accel', 0), up.get('Crash', 0), up.get('Boost', 0)]}

        def roll(group, depth=0):
            rs = groups.get(group, [])
            sure = [r for r in rs if r[3] >= 100]
            chance = [r for r in rs if 0 < r[3] < 100]
            won = list(sure) + ([random.choices(chance, weights=[r[3] for r in chance])[0]] if chance else [])
            out = []
            for kind, item, count, _, desc, _ in won:
                if kind == 'RewardGroup' and depth < 5:
                    for _ in range(max(count, 1)):
                        out += roll(item, depth + 1)
                elif kind == 'NormalItem':
                    out.append((item, max(count, 1), desc))
            return out
        group = f'rw_{machine}_gacha_2015'
        if group not in groups:
            return {'error': 'gotcha_off'}
        if what == 'gotcha_info':
            slots = []
            for kind, item, count, chance, desc, text in groups[group]:
                if kind != 'RewardGroup' or 'slot' not in item:
                    continue
                text = text.replace('<Example>', '').strip()
                variants = [dict(car_of(d) or {}, chance=ch, box=it) for k, it, n, ch, d, _ in groups.get(item, []) if k == 'NormalItem']
                slots.append({'group': item, 'chance': chance, 'text': text, 'cars': variants})
            total = sum(x[3] for x in groups[group]) or 1
            return dict(base, slots=slots, price=price, total=total)
        if not pay(mito=price if machine == 'mito' else 0, cc=price if machine == 'cash' else 0):
            return {'error': 'no_mito' if machine == 'mito' else 'no_cc'}
        won = roll(group)
        for item, count, _ in won:
            give_item(item, count)
        return {'won': [{'id': i, 'name': D.info(i)['name'], 'count': n, 'car': car_of(d) if D.info(i)['kind'] == 'giftbox_car' else None}
                        for i, n, d in won], 'price': price}

    if what == 'info':
        return base
    return {'error': 'unknown_command'}
