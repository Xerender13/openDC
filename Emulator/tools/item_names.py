"""English names for usable items whose 2011 client tables kept the Korean name (shown as "?? ??" by the US and EU
clients, whose fonts have no Korean), e.g. random_skb_bust "쓸모 없는 스킬북" (user, 2026-10-17: a broken item in
Xerander's inventory). Also other cells of chosen items (CELLS: the parts shop column).

UseItemClient.tdf: column 0 the item id, 2 the name, 6 the description. The tables written:
  - Client US/Patch/Patch.004 "Data_US\\World\\data\\UseItemClient.tdf" (the US client's newest copy; the EU
    client's World.agt is built from it by eu_client.py setup), first original client_backup/Patch.004.orig
  - Client EU/Data_EU_<lang>/World.agt "World\\data\\UseItemClient.tdf" (first original
    client_backup/World_<folder>.agt.orig, shared with eu_client.py grades)
  - Emulator/server_data/tables/UseItemClient.tdf (the server's names, e.g. in its messages)
Packs are rewritten with their header bytes 20-31 kept; the changed cells point at new strings appended to the
table (eu_client.tdf_set). The clients read the packs when they start.

usage: python3 Emulator/tools/item_names.py [apply|show]
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import agt  # noqa: E402
from eu_client import FOLDER, tdf_set  # noqa: E402
from dcemu.native.data import read_tdf  # noqa: E402

NAMES = {   # item id -> (name, description)
    'random_skb_bust': ('Useless Skill Book', 'A skill book too old to be of any use.'),
}
# other cells: item id -> {column: text}. Column 13 = sold in the parts shop (the client lists the shop's items by it,
# the server sells by it: items.buy_item)
CELLS = {
    'i_n_00062': {13: 'True'},      # Tatiana Call Unit (Virtual HUV, vchase.py; 1000 Mito): in the parts shop (user, 2026-10-18)
}
ROOT = os.path.join(HERE, '..', '..')
BACKUPS = os.path.join(HERE, '..', 'client_backup')


def rows_of(data):
    tmp = os.path.join(BACKUPS, '.item_names.tmp')
    open(tmp, 'wb').write(data)
    try:
        return read_tdf(tmp)
    finally:
        os.remove(tmp)


def renamed(data):
    """The table with NAMES applied, or None when nothing changes."""
    changes = {}
    for r, row in enumerate(rows_of(data)):
        if row and row[0] in NAMES:
            name, desc = NAMES[row[0]]
            if row[2] != name:
                changes[(r, 2)] = name
            if len(row) > 6 and row[6] != desc:
                changes[(r, 6)] = desc
        for col, text in CELLS.get(row[0], {}).items() if row else ():
            if len(row) > col and row[col] != text:
                changes[(r, col)] = text
    return tdf_set(data, changes) if changes else None


def write_pack(path, header, files, backup):
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print('  original kept as', os.path.normpath(backup))
    tmp = path + '.new'
    agt.write(tmp, header, files)
    raw = bytearray(open(tmp, 'rb').read())
    raw[20:32] = header[20:32]
    open(tmp, 'wb').write(bytes(raw))
    os.replace(tmp, path)


def apply_pack(path, entry, backup, show):
    if not os.path.exists(path):
        return
    header, files = agt.read(path)
    k = next((i for i, (n, _) in enumerate(files) if n.lower() == entry.lower()), None)
    if k is None:
        return print(f'{os.path.normpath(path)}: no {entry}')
    new = renamed(files[k][1])
    if show or new is None:
        return print(f'{os.path.normpath(path)}:', 'names already English' if new is None else 'would change')
    files[k] = (files[k][0], new)
    write_pack(path, header, files, backup)
    print(f'{os.path.normpath(path)}: {entry} names written')


def main():
    show = sys.argv[1:2] == ['show']
    if sys.argv[1:2] not in (['show'], ['apply']):
        sys.exit(__doc__)
    apply_pack(os.path.join(ROOT, 'Client US', 'Patch', 'Patch.004'), 'Data_US\\World\\data\\UseItemClient.tdf',
               os.path.join(BACKUPS, 'Patch.004.orig'), show)
    for folder in FOLDER.values():
        apply_pack(os.path.join(ROOT, 'Client EU', folder, 'World.agt'), 'World\\data\\UseItemClient.tdf',
                   os.path.join(BACKUPS, f'World_{folder}.agt.orig'), show)
    path = os.path.join(HERE, '..', 'server_data', 'tables', 'UseItemClient.tdf')
    new = renamed(open(path, 'rb').read())
    if show or new is None:
        return print(f'{os.path.normpath(path)}:', 'names already English' if new is None else 'would change')
    open(path + '.new', 'wb').write(new)
    os.replace(path + '.new', path)
    print(f'{os.path.normpath(path)}: names written')


if __name__ == '__main__':
    main()
