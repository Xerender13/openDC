"""Player cars that are on sale but have no model in the client's vehicles.agt: hide them.

The 2016 VehicleList lists cars whose "Support" column is 0; six of those rows (Unique Ids 43, 49, 64, 67, 68, 74)
are still marked Sellable 1, but no `pc_XXXXs.nif` for them exists in any client we hold (2016, 2011, the 2025
Origin client, the newer Skid Rush build), so the dealership offers a car the client cannot draw. The Zorro
(Unique Id 74, BMW Z4 Coupe, `pc_0054s.nif`) is the one the user hit.

usage (from Emulator/):
    python -m tools.no_model_cars            list them
    python -m tools.no_model_cars apply      set their Sellable to 0 (server_data_2016 and the client's Data/Init.agt)

`apply` rewrites VehicleList in the client pack through port2016.pack_update, which keeps the pack's header bytes and
the first original in client_backup/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import agt                                    # noqa: E402
import port2016 as p                          # noqa: E402
from port2016 import xlt_lines, xlt_bytes     # noqa: E402
from portorigin import backup_path, BACKUPS, ROOT   # noqa: E402

CLIENT = os.path.join(ROOT, 'DriftCity Dev Ed')
SERVER_TABLE = os.path.join(HERE, '..', 'server_data_2016', 'Init', 'VehicleList.xlt')
PACK = os.path.join(CLIENT, 'Data', 'Init.agt')
ENTRY = 'init\\vehiclelist.xlt'


def pack_models():
    """The model file names the client's vehicles.agt holds. A car's `pc_XXXXs.nif` is stored as its variants
    (`pc_XXXXs_s.nif`, `_01`, `_02`, `_dm`, ...), so a car counts as modelled when any name starts with its base."""
    _, entries = agt.index(os.path.join(CLIENT, 'Data', 'vehicles.agt'))
    return [e[0].lower().rsplit('\\', 1)[-1] for e in entries]


def columns(lines):
    header = next(i for i, l in enumerate(lines) if l.startswith('Index\t'))
    return header, lines[header].split('\t')


def missing(lines, models):
    """[(line index, Unique Id, UI name, file)]: PlayerCar rows whose model is absent and that are still on sale."""
    header, cols = columns(lines)
    i_desc, i_file = cols.index('Desc'), cols.index('File Name')
    i_uid, i_ui, i_sell = cols.index('Unique Id'), cols.index('UI Name'), cols.index('Sellable')
    out = []
    for n in range(header + 1, len(lines)):
        c = lines[n].split('\t')
        if len(c) <= i_sell or c[i_desc].strip() != 'PlayerCar':
            continue
        f = c[i_file].strip().lower()
        base = f[:-4] if f.endswith('.nif') else f
        if base and not any(m.startswith(base) for m in models) and c[i_sell].strip() not in ('0', ''):
            out.append((n, c[i_uid].strip(), c[i_ui].strip(), f))
    return out


def hide(lines, found):
    header, cols = columns(lines)
    i_sell = cols.index('Sellable')
    for n, _uid, _name, _file in found:
        c = lines[n].split('\t')
        c[i_sell] = '0'
        lines[n] = '\t'.join(c)


def main(argv):
    models = pack_models()
    lines = xlt_lines(open(SERVER_TABLE, 'rb').read())
    found = missing(lines, models)
    print(f'{len(found)} player car(s) on sale with no model in vehicles.agt:')
    for _n, uid, name, f in found:
        print(f'   Unique Id {uid:>4}  {name:16} {f}')
    if argv[:1] != ['apply'] or not found:
        return
    hide(lines, found)
    open(SERVER_TABLE, 'wb').write(xlt_bytes(lines))
    print(f'  server_data_2016/Init/VehicleList.xlt: {len(found)} row(s) Sellable = 0')
    raw, entries = agt.index(PACK)
    entry = next(e for e in entries if e[0].lower() == ENTRY)
    plines = xlt_lines(agt.extract(raw, entry))
    pmissing = missing(plines, models)
    if pmissing:
        hide(plines, pmissing)
        p.backup_path, p.BACKUPS, p.ROOT = backup_path, BACKUPS, ROOT
        p.pack_update(PACK, {'Init\\VehicleList.xlt': xlt_bytes(plines)})
        print(f'  client Data/Init.agt: {len(pmissing)} row(s) Sellable = 0')


if __name__ == '__main__':
    main(sys.argv[1:])
