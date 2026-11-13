"""The 2016 Gotcha window's seven car slots, from emulator.ini [gotcha] car_slot_1..7 (2016 client only).

python -m tools.gotcha_slots [show | apply | reset] [--client DIR] [-c emulator.ini]

The window takes each slot's car from the client's own Init/RewardGroup.xlt (Data/Init.agt): the rows of
rw_cash_gacha_2015 (G Coin) and rw_mito_gacha_2015 (Mito), column Reward_Description = the car's Unique Id, column
Group_Description = the slot's text (client 0x6c0d32-0x6c0e03; dcemu/native/game/gotcha.py). The server reads the
setting itself and gives the car; this tool makes the window show it:
  apply: slot rows of configured slots get the car and a text built from its V9 row (VehicleUpgrade); the other
         slots get their original row back. Written to the client pack and to server_data_2016 (the same table).
  reset: every slot as shipped.   show: the slots as configured / as the client has them.
The first original table is kept as client_backup/2016/gotcha/RewardGroup.xlt.orig. Restart the client afterwards
(and the emulator after changing emulator.ini).
"""
import argparse
import configparser
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import port2016 as p  # noqa: E402
from port2016 import cells, xlt_lines, xlt_bytes  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SERVER = os.path.join(HERE, '..', 'server_data_2016')
BACKUP = os.path.join(HERE, '..', 'client_backup', '2016', 'gotcha')
ENTRY = 'Init\\RewardGroup.xlt'
GROUPS = ('rw_cash_gacha_2015', 'rw_mito_gacha_2015')


def settings(ini):
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read(ini, encoding='utf-8')
    values = {k: v for k, v in (cp['gotcha'].items() if cp.has_section('gotcha') else [])}
    if cp.has_section('2016'):
        values.update({k[len('gotcha.'):]: v for k, v in cp['2016'].items() if k.startswith('gotcha.')})
    return values


def vehicles():
    from dcemu.native.data import read_xlt
    rows = read_xlt(os.path.join(SERVER, 'Init', 'VehicleList.xlt'))
    names = rows[3]
    return {int(r[9]): {n: r[i].strip() for i, n in enumerate(names) if n and i < len(r)}
            for r in rows[4:] if len(r) > 9 and r[0].strip() and r[9].strip().isdigit()}


def text_for(uid, cars):
    from dcemu.native.data import read_xlt
    rows = [r for r in read_xlt(os.path.join(SERVER, 'Init', 'VehicleUpgrade.xlt'))[3:] if len(r) > 19 and r[1].strip() == str(uid)]
    r = rows[-1]
    return (f'"<Example>\n{cars[uid]["UI Name"]} ({r[18].strip() or "V"}{r[19].strip()})\n· Accel : {r[6].strip()}\n'
            f'· Speed : {r[7].strip()}\n· Durability : {r[8].strip()}\n· Boost : {r[9].strip()}"')


def slot_rows(lines):
    """{(group, slot): line index} of the seven slot rows of each group."""
    out = {}
    for i, l in enumerate(lines):
        c = cells(l)
        if len(c) > 5 and c[1] in GROUPS and c[5].startswith(f'rw_{c[1].split("_")[1]}_gacha_slot_'):
            out[(c[1], int(c[5].rsplit('_', 1)[1]))] = i
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('action', nargs='?', default='show', choices=('show', 'apply', 'reset'))
    ap.add_argument('--client', default=os.path.join(ROOT, 'DriftCity Dev Ed'))
    ap.add_argument('-c', '--config', default=os.path.join(HERE, '..', 'emulator.ini'))
    a = ap.parse_args()
    from dcemu.native.game.gotcha import parse_slots
    cars = vehicles()
    slots = {} if a.action == 'reset' else parse_slots(settings(a.config), cars)
    pack = os.path.join(a.client, 'Data', 'Init.agt')
    keep = os.path.join(BACKUP, 'RewardGroup.xlt.orig')
    current = p.read_entry(pack, ENTRY)
    orig = xlt_lines(open(keep, 'rb').read() if os.path.exists(keep) else current)
    lines = xlt_lines(current)
    at, at0 = slot_rows(lines), slot_rows(orig)
    for (group, n), i in sorted(at.items()):
        c = cells(orig[at0[(group, n)]])
        uid = slots[n][0 if group == GROUPS[0] else 1] if n in slots else None
        if uid is not None:
            c[2], c[4] = text_for(uid, cars), str(uid)
        shown = int(c[4].split()[0]) if c[4].split() and c[4].split()[0].isdigit() else 0
        print(f'  {group} slot {n}: {shown} {cars.get(shown, {}).get("UI Name", "?")}' + (' (emulator.ini)' if uid else ''))
        lines[i] = '\t'.join(c)
    if a.action == 'show':
        return
    data = xlt_bytes(lines)
    if data == current:
        return print('nothing to change')
    os.makedirs(BACKUP, exist_ok=True)
    if not os.path.exists(keep):
        open(keep, 'wb').write(current)
    p.backup_path = lambda path: os.path.join(BACKUP, os.path.basename(path) + '.orig')
    p.BACKUPS, p.ROOT = BACKUP, ROOT
    p.pack_update(pack, {ENTRY: data})
    open(os.path.join(SERVER, 'Init', 'RewardGroup.xlt'), 'wb').write(data)
    print('written: the client pack and server_data_2016/Init/RewardGroup.xlt. Restart the client and the emulator.')


if __name__ == '__main__':
    main()
