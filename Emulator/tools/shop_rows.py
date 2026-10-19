"""Drift shop (F4) rows changed in the clients: emulator.ini [vshop] (hidden = rows off sale, sell.<UniqueId> = columns
set; dcemu/native/game/vshop.row_changes reads it, the server applies the same changes to its own rows at start).

The client lists a VShopItem row only when its SellStage (column 14, % 1000, < 1 -> 100) is at most the content flag
Etc.VShopOpenStage (1, Contents.ini) and Etc.VShopCloseStage is below its CloseStage (client 0x5c7196 / 0x6475d4 /
0x64ae7c; the table is read by 0x846e10), and shows the prices of its own copy. `apply` writes, starting from the
original table each time (a row taken out of the section gets its own values back):
  - hidden rows: SellStage 99 (the value the unsold passive assist rows have);
  - sell.<UniqueId> rows: the columns given (by the table's header names).
Packs (header bytes 20-31 kept; the first original kept in client_backup/):
  - Client US/Data_US/Init_us.agt              (client_backup/Init_us.agt.orig)
  - Client EU/Data_EU_<lang>/Init_<s>.agt      (client_backup/Init_<s>_ClientEU.agt.orig; eu_client.py setup copies
                                                 Init_us.agt there, so after a setup the EU client has the US rows)
The clients read the packs when they start. `reset` puts the original packs back.

usage: python3 Emulator/tools/shop_rows.py [apply|show|reset]
"""
import configparser
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import agt  # noqa: E402
from eu_client import FOLDER, SUFFIX  # noqa: E402
from dcemu.native.game.vshop import row_changes  # noqa: E402

ROOT = os.path.join(HERE, '..', '..')
ENTRY, UID, NAME, STAGE, HIDDEN_STAGE = 'Init\\VShopItem.xlt', 2, 4, 14, '99'


def packs():
    """-> [(pack path, backup path)] of the clients that are here."""
    out = [(os.path.join(ROOT, 'Client US', 'Data_US', 'Init_us.agt'),
            os.path.join(HERE, '..', 'client_backup', 'Init_us.agt.orig'))]
    for lang, folder in FOLDER.items():
        out.append((os.path.join(ROOT, 'Client EU', folder, f'Init_{SUFFIX[lang]}.agt'),
                    os.path.join(HERE, '..', 'client_backup', f'Init_{SUFFIX[lang]}_ClientEU.agt.orig')))
    return [(p, b) for p, b in out if os.path.exists(p)]


def wanted():
    """-> {UniqueId: {column: value}} for the clients (hidden rows: SellStage 99)."""
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    cp.read(os.path.join(HERE, '..', 'emulator.ini'))
    hidden, changes = row_changes(cp['vshop'] if cp.has_section('vshop') else {})
    for uid in hidden:
        changes.setdefault(uid, {})['SellStage'] = HIDDEN_STAGE
    return changes


def table(files):
    return dict(files)[ENTRY].decode('utf-16').split('\r\n')


def write_pack(path, backup, files):
    orig = open(backup, 'rb').read(32)
    tmp = path + '.new'
    agt.write(tmp, orig, files)
    raw = bytearray(open(tmp, 'rb').read())
    raw[20:32] = orig[20:32]
    open(tmp, 'wb').write(bytes(raw))
    os.replace(tmp, path)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd not in ('apply', 'show', 'reset'):
        sys.exit(__doc__)
    want = wanted()
    for path, backup in packs():
        print(os.path.normpath(path))
        if cmd == 'reset':
            if os.path.exists(backup):
                shutil.copy2(backup, path)
                print('  original pack restored')
            continue
        header, files = agt.read(path)
        lines = table(files)
        col = {n: i for i, n in reversed(list(enumerate(lines[2].split('\t'))))}
        if cmd == 'show':
            for line in lines[3:]:
                f = line.split('\t')
                if len(f) > STAGE and f[UID].isdigit() and int(f[UID]) in want:
                    print(f'  {f[UID]:>6} {f[NAME][:40]:40} ' + ', '.join(f'{c}={f[col[c]]}' for c in want[int(f[UID])] if c in col))
            continue
        bad = {c for cols in want.values() for c in cols if c not in col}
        if bad:
            sys.exit(f'  no such column: {", ".join(sorted(bad))} (nothing written)')
        if not os.path.exists(backup):
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copy2(path, backup)
            print('  original pack kept as', os.path.normpath(backup))
        _, orig_files = agt.read(backup)
        lines, found = table(orig_files), set()
        for i, line in enumerate(lines):
            f = line.split('\t')
            if len(f) > STAGE and f[UID].isdigit() and int(f[UID]) in want:
                for c, v in want[int(f[UID])].items():
                    f[col[c]] = v
                lines[i] = '\t'.join(f)
                found.add(int(f[UID]))
                print(f'  {f[UID]:>6} {f[NAME][:40]:40} ' + ', '.join(f'{c}={v}' for c, v in want[int(f[UID])].items()))
        if set(want) - found:
            print('  not in the table:', ', '.join(map(str, sorted(set(want) - found))))
        # rows other tools added to the pack (tools/port2016.py: the 2016 cars' aero sets) stay
        orig_uids = {f.split('\t')[UID] for f in lines[3:] if len(f.split('\t')) > STAGE}
        extra = [l for l in table(files)[3:] if len(l.split('\t')) > STAGE and l.split('\t')[UID].isdigit()
                 and l.split('\t')[UID] not in orig_uids]
        if extra:
            last = max(i for i, l in enumerate(lines) if l.split('\t')[0].strip().isdigit())
            lines[last + 1:last + 1] = extra
            head = lines[1].split('\t')
            head[1] = str(sum(1 for l in lines[3:] if l.split('\t')[0].strip().isdigit()))
            head[3] = str(max(int(l.split('\t')[UID]) for l in lines[3:]
                              if len(l.split('\t')) > STAGE and l.split('\t')[UID].isdigit()) + 1)
            lines[1] = '\t'.join(head)
            print(f'  {len(extra)} added rows kept')
        new = b'\xff\xfe' + '\r\n'.join(lines).encode('utf-16-le')
        write_pack(path, backup, [(n, new if n == ENTRY else d) for n, d in files])
        print('  written')


if __name__ == '__main__':
    main()
