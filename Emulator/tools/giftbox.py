"""Gift boxes: usable inventory items that give a car and/or items when used (right-click), like the 2011
"Serpens GiftBox (V1)" rows. Used by the Server Workshop editor (Items tab > New gift box) and from the shell.

A gift box is three things the client and the server must agree on:
  - a UseItemClient.tdf row (kind "giftbox", column 3 = its RewardGroup, column 9 = the level shown, as the Serpens
    boxes: the car grade's level, else 1), appended at the end. Items travel as row indexes, so the row goes to the
    server copy (server_data/tables) and to both clients' copies at the same place: US Patch/Patch.004, EU
    Data_EU_eng/World.agt (row-for-row the same tables; checked first, nothing is written otherwise);
  - its RewardGroup.xlt group rw_<id>. driftuse.roll gives every row of Probability 100 and ONE weighted pick of the
    rows below 100 ("n/a" rows = nothing). So each content line with its own chance c % (rolled on its own) becomes a
    small group rw_<id>_<n> = [the item c, n/a 100 - c], linked from rw_<id> by a RewardGroup row of 100; a 100 %
    line stands in rw_<id> itself. Line kinds: car (its key item, VehicleList File Name without ".nif", Etc_Value =
    the grade: driftuse.give makes the car with full Mittron and the key; needs garage space), item (an inventory
    item: ItemClient / UseItemClient id, count), drift (a drift item: VisualItem id, days, 0 = for good), mito, exp.
    Written to server_data/Init and both clients' Init packs (Init_us.agt / Init_eueng.agt);
  - its icon: a game.nui dialog 270000 control named after the item: the generic gift box picture of the Serpens
    boxes (640,960~704,1024_ui_item_normal.dds) with a short label written on it (T1), in both clients' game.nui.
Pack writes keep header bytes 20-31 and the first original in client_backup/ (port2016.pack_update). Restart the
emulator and the clients to see a new box.

usage: .venv/bin/python -m tools.giftbox cars [words]       cars that can go in a box (unique id, name, key, grades)
       .venv/bin/python -m tools.giftbox boxes              the gift boxes there are
       .venv/bin/python -m tools.giftbox car CAR-UNIQUE-ID GRADE [--price MITO] [--trial]
       .venv/bin/python -m tools.giftbox make ID "NAME" LABEL LINE... [--price MITO]
            LINE = car:UNIQUE-ID:GRADE[:%] | item:ITEM-ID[:COUNT[:%]] | drift:ITEM-ID[:DAYS[:%]] | mito:N[:%] | exp:N[:%]
            e.g. make lucky1 "Lucky Box" Lucky item:i_n_00058:10 item:i_n_00027:1:25 mito:50000:50
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMU = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, EMU)
import port2016 as p16                                   # noqa: E402
from client_tables import Client                         # noqa: E402

SERVER_USE = os.path.join(EMU, 'server_data', 'tables', 'UseItemClient.tdf')
SERVER_PARTS = os.path.join(EMU, 'server_data', 'tables', 'ItemClient.tdf')
SERVER_INIT = os.path.join(EMU, 'server_data', 'Init')
SERVER_REWARD = os.path.join(SERVER_INIT, 'RewardGroup.xlt')
TEMPLATE = 'giftbox_Serpens_v1'                          # the row and icon a new box is copied from
ICON_DIALOG = '270000'
REWARD_ENTRY = 'Init\\RewardGroup.xlt'
KINDS = ('car', 'item', 'drift', 'mito', 'exp')
ID = re.compile(r'[A-Za-z0-9_]{1,40}')


def _xlt(path):
    return p16.xlt_lines(open(path, 'rb').read())


def _use_rows():
    return p16._tdf_rows(open(SERVER_USE, 'rb').read())


def cars(words=''):
    """[(unique id, shown name, key item id, [grades with a real VehicleUpgrade row])] of the player cars with a key."""
    keys = {r[0] for r in _use_rows()}
    grades = {}
    for line in _xlt(os.path.join(SERVER_INIT, 'VehicleUpgrade.xlt'))[3:]:
        c = p16.cells(line)
        if len(c) > 19 and c[1].strip().isdigit() and c[19].strip().isdigit() and c[15].strip() not in ('', '0'):
            grades.setdefault(int(c[1]), []).append(int(c[19]))
    out = []
    for line in _xlt(os.path.join(SERVER_INIT, 'VehicleList.xlt'))[3:]:
        c = p16.cells(line)
        if len(c) < 10 or c[3] != 'PlayerCar' or not c[9].strip().isdigit():
            continue
        uid, key = int(c[9]), c[7].rsplit('.', 1)[0]
        if key in keys and grades.get(uid) and all(w in f'{c[6]} {c[5]} {key} {uid}'.lower() for w in words.lower().split()):
            out.append((uid, c[6], key, sorted(grades[uid])))
    return sorted(out, key=lambda r: r[1].lower())


def items():
    """{'item': {id: name}, 'drift': {id: name}}: what a box can hold (inventory items: parts and usable items; drift
    items: VisualItem)."""
    inv = {r[2]: r[4] for r in p16._tdf_rows(open(SERVER_PARTS, 'rb').read()) if len(r) > 4 and r[2]}
    inv.update({r[0]: r[2] for r in _use_rows() if r[0]})
    drift = {}
    for line in _xlt(os.path.join(SERVER_INIT, 'VisualItem.xlt'))[3:]:
        c = p16.cells(line)
        if len(c) > 5 and c[3].strip() and c[4].strip().isdigit():
            drift[c[3]] = c[5]
    return {'item': inv, 'drift': drift}


def boxes():
    """[(row, item id, name)] of the gift box rows."""
    return [(i, r[0], r[2]) for i, r in enumerate(_use_rows()) if r[1] == 'giftbox']


def _req_level(uid, grade):
    for line in _xlt(os.path.join(SERVER_INIT, 'VehicleUpgrade.xlt'))[3:]:
        c = p16.cells(line)
        if len(c) > 19 and c[1].strip() == str(uid) and c[19].strip() == str(grade):
            return int(c[16]) if c[16].strip().isdigit() else 1
    return 1


def check(lines):
    """Content lines [{kind, id, count, days, grade, chance}] -> [(Reward_Type, Reward_Description, ItemId, period,
    count, Etc_Value, chance)]; raises ValueError for anything the server could not give."""
    if not lines:
        raise ValueError('a gift box needs at least one line')
    known, car_by_id = items(), {c[0]: c for c in cars()}
    out = []
    for n, l in enumerate(lines, 1):
        kind, chance = l.get('kind'), float(l.get('chance', 100))
        if not 0 < chance <= 100:
            raise ValueError(f'line {n}: chance must be above 0 and at most 100 %')
        if kind == 'car':
            car = car_by_id.get(int(l['id']))
            grade = int(l.get('grade', 1))
            if not car:
                raise ValueError(f'line {n}: no player car {l["id"]} with a key item')
            if grade not in car[3]:
                raise ValueError(f'line {n}: {car[1]} has no V{grade} row (V{car[3][0]}-V{car[3][-1]})')
            out.append(('NormalItem', f'{car[1]} key', car[2], 0, 1, grade, chance))
        elif kind in ('item', 'drift'):
            item, count, days = str(l['id']), max(int(l.get('count', 1)), 1), max(int(l.get('days', 0)), 0)
            if item not in known[kind]:
                raise ValueError(f'line {n}: no {"inventory" if kind == "item" else "drift"} item {item!r}')
            if kind == 'item':
                out.append(('NormalItem', known['item'][item], item, 0, count, 0, chance))
            else:
                out.append(('SkidItem', known['drift'][item], item, days, count, 0, chance))
        elif kind in ('mito', 'exp'):
            amount = int(l.get('count', 0))
            if amount <= 0:
                raise ValueError(f'line {n}: {kind} needs an amount above 0')
            out.append(('Mito' if kind == 'mito' else 'Exp', kind.capitalize(), 'n/a', 0, amount, 0, chance))
        else:
            raise ValueError(f'line {n}: kind must be one of {", ".join(KINDS)}')
    return out


def _reward_lines(lines, group, desc, rows):
    """RewardGroup.xlt lines with the box's groups appended (Idx numbered on, the Count cell raised)."""
    lines = list(lines)
    while lines and not lines[-1].strip():
        lines.pop()
    width = len(p16.cells(lines[2]))
    idx = max((int(p16.cells(l)[0]) for l in lines[3:] if p16.cells(l)[0].strip().isdigit()), default=0)
    new, sub = [], 0
    for kind, what, item, period, count, etc, chance in rows:
        cell = [kind, what, item, str(period), str(count), str(etc), 'n/a']
        if chance >= 100:
            new.append([group, desc] + cell + ['100'])
        else:
            sub += 1
            name = f'{group}_{sub}'
            new.append([group, desc, 'RewardGroup', f'{what} ({chance:g} %)', name, '0', '1', '0', 'n/a', '100'])
            new.append([name, desc] + cell + [f'{chance:g}'])
            if chance < 100:
                new.append([name, desc, 'n/a', 'nothing', 'n/a', '0', '0', '0', 'n/a', f'{100 - chance:g}'])
    for r in new:
        idx += 1
        lines.append('\t'.join([str(idx)] + r + [''] * (width - 1 - len(r))))
    head = p16.cells(lines[1])
    head[2] = str(int(head[2]) + len(new)) if head[2].strip().isdigit() else head[2]
    lines[1] = '\t'.join(head)
    return lines + ['']


def _icon(nui, box_id, label):
    """game.nui text with the box's icon control added to dialog 270000 (a copy of the template's), or None if there."""
    if f'NM="{box_id}"' in nui:
        return None
    dlg = re.search(r'<DIALOG C="%s"[^>]*>.*?</DIALOG>' % ICON_DIALOG, nui, re.S)
    tpl = re.search(r'[ \t]*<CONTROL B="(\d+)"[^>]*>\s*<INFO [^>]*NM="%s".*?</CONTROL>\r?\n' % TEMPLATE, dlg.group(0), re.S)
    top = max(int(b) for b in re.findall(r'<CONTROL B="(\d+)"', dlg.group(0)))
    ctl = tpl.group(0).replace(f'B="{tpl.group(1)}"', f'B="{top + 1}"').replace(f'NM="{TEMPLATE}"', f'NM="{box_id}"')
    ctl = re.sub(r'T1="[^"]*"', 'T1="%s"' % label.replace('"', "'"), ctl)
    end = dlg.end() - len('</DIALOG>')
    end = nui.rfind('\n', 0, end) + 1
    return nui[:end] + ctl + nui[end:]


def targets():
    """[(nation key, UseItemClient (pack, entry), Init pack, game.nui)] of the clients that are there."""
    out = []
    us = os.path.join(p16.ROOT, 'Client US')
    if os.path.isdir(us):
        c = Client(us)
        f = c.files[c.find('UseItemClient.tdf')]
        out.append(('us', (os.path.join(us, f[0]), f[2][0]), os.path.join(us, 'Data_US', 'Init_us.agt'),
                    os.path.join(us, 'Data_US', 'gameui', 'game.nui')))
    eu = os.path.join(p16.ROOT, 'Client EU')
    if os.path.isdir(eu):
        out.append(('eu', (os.path.join(eu, 'Data_EU_eng', 'World.agt'), 'World\\data\\UseItemClient.tdf'),
                    os.path.join(eu, 'Data_EU_eng', 'Init_eueng.agt'), os.path.join(eu, 'Data_EU_eng', 'gameui', 'game.nui')))
    return out


def describe(rows):
    parts = []
    for kind, what, item, period, count, etc, chance in rows:
        if kind == 'NormalItem' and etc:
            text = f'V{etc} {what[:-4]}'
        elif kind in ('Mito', 'Exp'):
            text = f'{count:,} {"Mito" if kind == "Mito" else "EXP"}'
        else:
            days = f' ({period} days)' if period and 'day' not in what.lower() else ''
            text = (f'{count} x ' if count > 1 else '') + what + days
        parts.append(text + (f' ({chance:g} %)' if chance < 100 else ''))
    return 'This item includes ' + ', '.join(parts) + '. (Right-Click to Use)'


def make(slug, name, label, lines, price=0, description=None, log=print):
    """Add gift box giftbox_<slug> with these content lines everywhere -> its item id. Raises ValueError (nothing
    written) when a line is wrong, the box exists, or the tables differ between the server and a client."""
    if not ID.fullmatch(slug or ''):
        raise ValueError('the id takes 1-40 letters, digits or _')
    if not name or not name.strip() or '\t' in name:
        raise ValueError('the box needs a name')
    rows = check(lines)
    box_id, group = f'giftbox_{slug}', f'rw_{slug}'
    server_use = open(SERVER_USE, 'rb').read()
    use = p16._tdf_rows(server_use)
    if any(r[0] == box_id for r in use):
        raise ValueError(f'{box_id} exists already')
    if any(p16.cells(l)[1:2] == [group] for l in _xlt(SERVER_REWARD)[3:]):
        raise ValueError(f'reward group {group} exists already')
    tpl = next((r for r in use if r[0] == TEMPLATE), None)
    if not tpl:
        raise ValueError(f'no template row {TEMPLATE}')
    level = max([_req_level(int(l['id']), int(l.get('grade', 1))) for l in lines if l['kind'] == 'car'] or [1])
    row = list(tpl)
    row[0], row[2], row[3], row[6] = box_id, name.strip(), group, (description or describe(rows)).replace('\t', ' ')
    row[7], row[8], row[9] = str(int(price)), str(int(price) // 5), str(level)
    label = (label or name).strip()[:16]
    plans = []                                  # (nation, path, entry or None, new bytes)
    for which, (use_pack, use_entry), init_pack, nui_path in targets():
        data = p16.read_entry(use_pack, use_entry)
        if data is None or [r[0] for r in p16._tdf_rows(data)] != [r[0] for r in use]:
            raise ValueError(f'{which}: its UseItemClient.tdf rows differ from server_data (nothing written)')
        plans.append((which, use_pack, use_entry, p16.tdf_append(data, [row])))
        rdata = p16.read_entry(init_pack, REWARD_ENTRY)
        plans.append((which, init_pack, REWARD_ENTRY, p16.xlt_bytes(_reward_lines(p16.xlt_lines(rdata), group, name, rows))))
        nui = _icon(open(nui_path, 'rb').read().decode('cp949'), box_id, label)
        if nui is not None:
            plans.append((which, nui_path, None, nui.encode('cp949')))
    for which, path, entry, data in plans:
        p16.T = p16.TARGETS[which]              # backups named as the other tools name them
        if entry is None:
            backup = p16.backup_path(path)
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            tmp = path + '.new'
            open(tmp, 'wb').write(data)
            os.replace(tmp, path)
            log(f'  {os.path.relpath(path, p16.ROOT)}: icon {box_id}')
        else:
            p16.pack_update(path, {entry: data})
    p16.T = p16.TARGETS['us']
    for path, data in ((SERVER_USE, p16.tdf_append(server_use, [row])),
                       (SERVER_REWARD, p16.xlt_bytes(_reward_lines(_xlt(SERVER_REWARD), group, name, rows)))):
        tmp = path + '.new'
        open(tmp, 'wb').write(data)
        os.replace(tmp, path)
    log(f'{box_id} ("{name}", item row {len(use)}): {row[6]} Restart the emulator and the clients.')
    return box_id


def make_car(uid, grade, price=0, trial=False, log=print):
    """A Serpens-style car box: the car at grade (+ the 7-day trial of the next V upgrade) -> its item id."""
    car = next((c for c in cars() if c[0] == uid), None)
    if not car:
        raise ValueError(f'no player car {uid} with a key item')
    lines = [dict(kind='car', id=uid, grade=grade)]
    if trial and grade < 9:
        lines.append(dict(kind='drift', id=f'i_d_u_1{grade}', days=7))
    return make(f'{car[2]}_v{grade}', f'{car[1]} GiftBox（V{grade}）', car[1], lines, price, log=log)


def parse_line(text):
    """'item:i_n_00058:10:25' -> a content line (see usage)."""
    f = text.split(':')
    kind = f[0].lower()
    num = lambda i, d: float(f[i]) if len(f) > i and f[i] else d       # noqa: E731
    if kind == 'car':
        return dict(kind=kind, id=int(f[1]), grade=int(num(2, 1)), chance=num(3, 100))
    if kind in ('item', 'drift'):
        return dict(kind=kind, id=f[1], count=int(num(2, 1)) if kind == 'item' else 1,
                    days=int(num(2, 0)) if kind == 'drift' else 0, chance=num(3, 100))
    if kind in ('mito', 'exp'):
        return dict(kind=kind, count=int(num(1, 0)), chance=num(2, 100))
    raise ValueError(f'unknown line {text!r}')


def main():
    a = sys.argv[1:]
    price = int(a[a.index('--price') + 1]) if '--price' in a else 0
    try:
        if not a or a[0] == 'cars':
            for uid, shown, key, grades in cars(' '.join(a[1:])):
                print(f'{uid:4}  {shown:24} {key:10} V{grades[0]}-V{grades[-1]}')
        elif a[0] == 'boxes':
            for i, box, name in boxes():
                print(f'{i:5}  {box:32} {name}')
        elif a[0] == 'car' and len(a) >= 3:
            make_car(int(a[1]), int(a[2].lower().lstrip('v')), price, '--trial' in a)
        elif a[0] == 'make' and len(a) >= 5:
            words = [w for i, w in enumerate(a) if not w.startswith('--') and (i == 0 or a[i - 1] != '--price')]
            make(words[1], words[2], words[3], [parse_line(t) for t in words[4:]], price)
        else:
            sys.exit(__doc__)
    except (ValueError, IndexError) as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
