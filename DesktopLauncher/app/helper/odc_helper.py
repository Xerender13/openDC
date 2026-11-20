"""openDC Launcher helper: account and character data straight from the openDC PostgreSQL database
(the same tables the emulator uses: MEUSERMT, SKID_CHARACTER_TB, SKID_CAR_TB, SKID_ITEM_TB, SKID_UNALISCOIN_TB)
and the admin list. Runs with the launcher's portable Python from the Emulator folder.

stdin: one JSON object {"db": {...}, "cmd": "...", ...}; stdout: one JSON object {"ok": true, ...} or {"ok": false, "error": ...}.
"""
import hashlib
import json
import os
import re
import sys

import pg8000.dbapi as pg

ID_RE = re.compile(r'^[A-Za-z0-9_.-]{1,32}$')
NAME_RE = re.compile(r'^[A-Za-z0-9_]{2,16}$')


def connect(d):
    return pg.connect(host='127.0.0.1', port=int(d['port']), user=d['user'], password=d['pass'], database=d['name'])


def admins(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return [l.strip() for l in f if l.strip() and not l.strip().startswith(('#', ';'))]
    except OSError:
        return []


def set_admin(path, member, on):
    lines = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        pass
    low = member.lower()
    lines = [l for l in lines if l.strip().lower() != low]
    if on:
        lines.append(member)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def car_names():
    """car type (Unique Id) -> shown name, from the server's VehicleList.xlt."""
    out = {}
    for base in ('server_data_2016', 'server_data'):
        p = os.path.join(base, 'Init', 'VehicleList.xlt')
        if not os.path.exists(p):
            continue
        with open(p, 'rb') as f:
            rows = [l.split('\t') for l in f.read().decode('utf-16-le').lstrip('﻿').split('\r\n')]
        for r in rows[4:]:
            if len(r) > 9 and r[9].strip().isdigit():
                out[int(r[9])] = (r[6].strip() or r[5].strip())
        break
    return out


# Export / import: a character is its rows in these tables (all keyed by SERVERID + CID). Logs, friends, crews,
# auctions and stickers stay behind (they point at other players or at shared data).
CHAR_TABLES = ['skid_character_tb', 'skid_car_tb', 'skid_item_tb', 'skid_vsitem_tb', 'skid_quest_tb', 'skid_instant_tb',
               'skid_playmode_tb', 'skid_couponvalue_tb', 'skid_couponstamp_tb', 'skid_couponparamvalue_tb',
               'skid_auctionmileage_tb']
FORMAT = 'opendc-export'


def plain(v):
    """a database value -> JSON (numbers stay exact as text, dates as ISO text)."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if hasattr(v, 'isoformat'):
        return v.isoformat(sep=' ')
    return str(v)


def main():
    req = json.loads(sys.stdin.read())
    d, cmd, sid = req['db'], req['cmd'], int(req['db'].get('server_id', 100))
    adm = req.get('admin_list', 'server_data/adminlist.txt')
    con = connect(d)
    cur = con.cursor()

    def rows(sql, args=()):
        cur.execute(sql, args)
        return cur.fetchall()

    def one(sql, args=()):
        r = rows(sql, args)
        return r[0] if r else None

    if cmd == 'accounts':
        gm = {a.lower() for a in admins(adm)}
        out = []
        for m, valid, joined, coin, n in rows("""
                SELECT m.memberid, m.valid, m.joindate, COALESCE(c.coin, 0),
                       (SELECT count(*) FROM skid_character_tb ch WHERE ch.memberid = m.memberid AND ch.serverid = %s AND ch.state <> 'D')
                FROM meusermt m LEFT JOIN skid_unaliscoin_tb c ON c.memberid = m.memberid ORDER BY m.joindate, m.memberid""", (sid,)):
            out.append({'id': str(m), 'banned': str(valid or 'y').lower() != 'y', 'joined': str(joined)[:10],
                        'coin': int(coin), 'chars': int(n), 'gm': str(m).lower() in gm})
        return {'accounts': out}

    def table_rows(table, where, args):
        cur.execute(f'SELECT * FROM "{table}" WHERE {where}', args)
        cols = [c[0] for c in cur.description]
        return [{k: plain(v) for k, v in zip(cols, r)} for r in cur.fetchall()]

    def export_char(cid):
        return {t: table_rows(t, 'serverid = %s AND cid = %s', (sid, cid)) for t in CHAR_TABLES}

    def name_taken(name):
        return bool(one("SELECT 1 FROM skid_character_tb WHERE serverid = %s AND ucname = UPPER(%s) AND state <> 'D'", (sid, name)))

    def insert(table, row):
        cols = list(row)
        cur.execute(f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(["%s"] * len(cols))})', [row[c] for c in cols])

    def import_char(data, member, name, gm):
        ch = dict(data['skid_character_tb'][0])
        ch.pop('cid', None)
        ch.update(serverid=sid, memberid=member, cname=name, ucname=name.upper(), state='P', ptype='A' if gm else 'N',
                  teamid=-1, teamrank=-1, teamclosedate=None, teamleavedate=None, teamjoindate=None)
        cols = list(ch)
        cur.execute(f'INSERT INTO skid_character_tb ({", ".join(cols)}) VALUES ({", ".join(["%s"] * len(cols))}) RETURNING cid',
                    [ch[c] for c in cols])
        cid = int(cur.fetchone()[0])
        for t in CHAR_TABLES[1:]:
            for r in data.get(t, []):
                r = dict(r)
                r.update(serverid=sid, cid=cid)
                if 'cname' in r:
                    r['cname'] = name
                if 'memberid' in r:
                    r['memberid'] = member
                insert(t, r)
        return cid

    def check_file(f):
        if not isinstance(f, dict) or f.get('format') != FORMAT:
            return 'bad_file'
        if int(f.get('server_id', sid)) != sid:
            return 'other_client'
        return None

    if cmd == 'export':
        member = req.get('id', '')
        acc = one('SELECT 1 FROM meusermt WHERE memberid = %s', (member,))
        if not acc:
            return {'ok': False, 'error': 'no_account'}
        cid = req.get('cid')
        q = "SELECT cid, cname FROM skid_character_tb WHERE serverid = %s AND memberid = %s AND state <> 'D'"
        chars = rows(q + (' AND cid = %s' if cid else '') + ' ORDER BY cid', (sid, member, int(cid)) if cid else (sid, member))
        if cid and not chars:
            return {'ok': False, 'error': 'no_char'}
        out = {'format': FORMAT, 'version': 1, 'kind': 'char' if cid else 'account', 'server_id': sid,
               'client': req.get('client', ''), 'chars': [export_char(int(c)) for c, _ in chars]}
        if not cid:
            out['account'] = {'meusermt': table_rows('meusermt', 'memberid = %s', (member,)),
                              'skid_member_tb': table_rows('skid_member_tb', 'memberid = %s', (member,)),
                              'skid_unaliscoin_tb': table_rows('skid_unaliscoin_tb', 'memberid = %s', (member,)),
                              'gm': member.lower() in {a.lower() for a in admins(adm)}}
        return {'data': out}

    if cmd == 'import_check':
        f = req.get('data')
        bad = check_file(f)
        if bad:
            return {'ok': False, 'error': bad}
        names = [str(c['skid_character_tb'][0]['cname']) for c in f['chars'] if c.get('skid_character_tb')]
        info = {'kind': f['kind'], 'names': names, 'taken': [n for n in names if name_taken(n)]}
        if f['kind'] == 'account':
            mid = str(f['account']['meusermt'][0]['memberid'])
            info.update(id=mid, exists=bool(one('SELECT 1 FROM meusermt WHERE memberid = %s', (mid,))))
        return {'info': info}

    if cmd == 'import':
        f = req.get('data')
        bad = check_file(f)
        if bad:
            return {'ok': False, 'error': bad}
        renames = req.get('names') or {}
        if f['kind'] == 'account':
            member = req.get('new_id') or str(f['account']['meusermt'][0]['memberid'])
            if not ID_RE.match(member):
                return {'ok': False, 'error': 'bad_id'}
            if one('SELECT 1 FROM meusermt WHERE memberid = %s', (member,)):
                return {'ok': False, 'error': 'exists'}
            gm = bool(f['account'].get('gm'))
            for t in ('meusermt', 'skid_member_tb', 'skid_unaliscoin_tb'):
                for r in f['account'].get(t, []):
                    insert(t, dict(r, memberid=member))
        else:
            member = req.get('id', '')
            if not one('SELECT 1 FROM meusermt WHERE memberid = %s', (member,)):
                return {'ok': False, 'error': 'no_account'}
            gm = member.lower() in {a.lower() for a in admins(adm)}
        done = []
        for c in f['chars']:
            if not c.get('skid_character_tb'):
                continue
            old = str(c['skid_character_tb'][0]['cname'])
            name = renames.get(old) or old
            if not NAME_RE.match(name):
                con.rollback()
                return {'ok': False, 'error': 'bad_name', 'name': old}
            if name_taken(name):
                con.rollback()
                return {'ok': False, 'error': 'name_taken', 'name': old}
            import_char(c, member, name, gm)
            done.append(name)
        if f['kind'] == 'account' and gm:
            set_admin(adm, member, True)
        con.commit()
        return {'id': member, 'chars': done}

    member = req.get('id', '')
    if cmd == 'create':
        pw = req.get('password', '')
        if not ID_RE.match(member):
            return {'ok': False, 'error': 'bad_id'}
        if not pw or len(pw.encode()) > 63 or ' ' in pw:
            return {'ok': False, 'error': 'bad_password'}
        if one('SELECT 1 FROM meusermt WHERE memberid = %s', (member,)):
            return {'ok': False, 'error': 'exists'}
        cur.execute("INSERT INTO meusermt (memberid, password, valid, joindate) VALUES (%s, %s, 'y', GetDate())",
                    (member, hashlib.md5(pw.encode()).hexdigest()))
        if req.get('gm'):
            set_admin(adm, member, True)
        con.commit()
        return {}

    if not one('SELECT 1 FROM meusermt WHERE memberid = %s', (member,)):
        return {'ok': False, 'error': 'no_account'}

    if cmd == 'account':
        valid, joined = one('SELECT valid, joindate FROM meusermt WHERE memberid = %s', (member,))
        coin = one('SELECT coin FROM skid_unaliscoin_tb WHERE memberid = %s', (member,))
        chars = [{'cid': int(c), 'name': str(n), 'level': int(l), 'mito': int(g), 'state': str(s), 'last': str(ld)[:16]}
                 for c, n, l, g, s, ld in rows("""SELECT cid, cname, nlevel, gold, state, lastdate FROM skid_character_tb
                     WHERE serverid = %s AND memberid = %s AND state <> 'D' ORDER BY cid""", (sid, member))]
        return {'account': {'id': member, 'banned': str(valid or 'y').lower() != 'y', 'joined': str(joined)[:10],
                            'coin': int(coin[0]) if coin else 0, 'gm': member.lower() in {a.lower() for a in admins(adm)},
                            'chars': chars}}
    if cmd == 'password':
        pw = req.get('password', '')
        if not pw or len(pw.encode()) > 63 or ' ' in pw:
            return {'ok': False, 'error': 'bad_password'}
        cur.execute('UPDATE meusermt SET password = %s WHERE memberid = %s', (hashlib.md5(pw.encode()).hexdigest(), member))
    elif cmd == 'gm':
        on = bool(req.get('on'))
        set_admin(adm, member, on)
        cur.execute("UPDATE skid_character_tb SET ptype = %s WHERE serverid = %s AND memberid = %s AND state <> 'D'",
                    ('A' if on else 'N', sid, member))
    elif cmd == 'ban':
        cur.execute('UPDATE meusermt SET valid = %s WHERE memberid = %s', ('n' if req.get('on') else 'y', member))
    elif cmd == 'coin':
        n = max(0, int(req.get('coin', 0)))
        if one('SELECT 1 FROM skid_unaliscoin_tb WHERE memberid = %s', (member,)):
            cur.execute("UPDATE skid_unaliscoin_tb SET coin = %s, lastaction = 'GM', lastdate = GetDate() WHERE memberid = %s", (n, member))
        else:
            cur.execute("INSERT INTO skid_unaliscoin_tb (memberid, coin, lastaction, lastdate) VALUES (%s, %s, 'GM', GetDate())", (member, n))
    elif cmd == 'delete':
        cur.execute("UPDATE skid_character_tb SET state = 'D', deldate = GetDate() WHERE serverid = %s AND memberid = %s AND state <> 'D'",
                    (sid, member))
        cur.execute('DELETE FROM skid_unaliscoin_tb WHERE memberid = %s', (member,))
        cur.execute('DELETE FROM meusermt WHERE memberid = %s', (member,))
        set_admin(adm, member, False)
    elif cmd in ('char', 'rename', 'char_delete', 'char_stats'):
        cid = int(req.get('cid', 0))
        ch = one("""SELECT cname, nlevel, gold FROM skid_character_tb WHERE serverid = %s AND cid = %s AND memberid = %s
                    AND state <> 'D'""", (sid, cid, member))
        if not ch:
            return {'ok': False, 'error': 'no_char'}
        if cmd == 'char':
            names = car_names()
            cars = [{'id': int(c), 'type': int(t), 'name': names.get(int(t), f'#{int(t)}'), 'grade': int(u), 'km': int(km)}
                    for c, t, u, km in rows("""SELECT carid, cartype, nupgrade, km FROM skid_car_tb
                        WHERE serverid = %s AND cid = %s ORDER BY carid""", (sid, cid))]
            items = [{'slot': int(i), 'item': str(it), 'count': int(n), 'state': int(s)}
                     for i, it, n, s in rows("""SELECT invenidx, itemid, stacknum, state FROM skid_item_tb
                         WHERE serverid = %s AND cid = %s ORDER BY invenidx LIMIT 300""", (sid, cid))]
            return {'char': {'cid': cid, 'name': str(ch[0]), 'level': int(ch[1]), 'mito': int(ch[2]), 'cars': cars, 'items': items}}
        if cmd == 'rename':
            new = req.get('name', '')
            if not NAME_RE.match(new):
                return {'ok': False, 'error': 'bad_name'}
            if one("SELECT 1 FROM skid_character_tb WHERE serverid = %s AND ucname = UPPER(%s) AND state <> 'D'", (sid, new)):
                return {'ok': False, 'error': 'name_taken'}
            # every table that keeps the character's name next to its CID
            for (t,) in rows("""SELECT a.table_name FROM information_schema.columns a JOIN information_schema.columns b
                    ON a.table_name = b.table_name AND a.table_schema = b.table_schema
                    WHERE a.table_schema = 'public' AND a.column_name = 'cname' AND b.column_name = 'cid'"""):
                cur.execute(f'UPDATE "{t}" SET cname = %s WHERE cid = %s', (new, cid))
            cur.execute('UPDATE skid_character_tb SET ucname = UPPER(%s) WHERE serverid = %s AND cid = %s', (new, sid, cid))
        elif cmd == 'char_delete':
            cur.execute("UPDATE skid_character_tb SET state = 'D', deldate = GetDate() WHERE serverid = %s AND cid = %s", (sid, cid))
        elif cmd == 'char_stats':
            cur.execute('UPDATE skid_character_tb SET gold = %s WHERE serverid = %s AND cid = %s',
                        (max(0, int(req.get('mito', ch[2]))), sid, cid))
    else:
        return {'ok': False, 'error': 'unknown_command'}
    con.commit()
    return {}


if __name__ == '__main__':
    try:
        r = main()
        r.setdefault('ok', True)
    except Exception as e:  # report, never a traceback on stdout
        r = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    sys.stdout.write(json.dumps(r, ensure_ascii=False, default=str))
