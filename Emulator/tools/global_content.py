"""Read or change the 2011 client's own settings table Localize\\GlobalContent.xlt (named values the
client looks up with 0x83aa50: battle zone section limits MaxBattle2XLevel ..., BattleRoomAI (the AI option
in the room seats of the Amateur..SuperStar sections), Select_Gate_MainEX, ...). The US client reads the
column Value_US, the EU clients Value_EU_de / Value_EU_eng / Value_EU_fr / Value_EU_es (the columns follow the
nation numbers 0-10): `--column NAME` picks the column (default Value_US).

The table is in Client/Patch/Patch.000. `set` rewrites that pack with the changed table and copies the
original header bytes 20-31 back (agt.write zeroes them; without them other players' car thumbnails in
battle zone rooms vanished, user 2026-10-13; with them everything works). The client ignores tables put
into PatchMod.000. The original pack is kept as Emulator/client_backup/Patch.000.orig; `reset` puts it
back (the vanilla client). Another client folder (e.g. Client EU) keeps its first pack as
client_backup/Patch.000_<folder>.orig instead. The client reads the packs when it starts.

usage: python3 Emulator/tools/global_content.py [client dir] [--column NAME] show [text]   rows whose key contains text
       python3 Emulator/tools/global_content.py [client dir] [--column NAME] set KEY=VALUE ...
       python3 Emulator/tools/global_content.py [client dir] reset           the original pack again
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402

PACK, ENTRY, COLUMN = os.path.join('Patch', 'Patch.000'), 'Data\\Localize\\GlobalContent.xlt', 'Value_US'
BACKUP = os.path.join(HERE, '..', 'client_backup', 'Patch.000.orig')


def load(client):
    header, files = agt.read(os.path.join(client, PACK))
    return files, dict(files)[ENTRY].decode('utf-16')


def backup_of(client):
    """Client US: BACKUP; another folder: its own copy (client_backup/Patch.000_<folder without spaces>.orig)."""
    name = os.path.basename(os.path.normpath(os.path.abspath(client)))
    if name == 'Client US':
        return BACKUP
    return os.path.join(HERE, '..', 'client_backup', f'Patch.000_{name.replace(" ", "")}.orig')


def write_pack(client, files):
    """The pack with these files, its header bytes 20-31 as in the original."""
    path = os.path.join(client, PACK)
    backup = backup_of(client)
    orig = open(backup if os.path.exists(backup) else path, 'rb').read(32)
    tmp_pack = path + '.new'
    agt.write(tmp_pack, orig, files)
    raw = bytearray(open(tmp_pack, 'rb').read())
    raw[20:32] = orig[20:32]
    open(tmp_pack, 'wb').write(bytes(raw))
    os.replace(tmp_pack, path)


def main():
    args = sys.argv[1:]
    client = os.path.join(HERE, '..', '..', 'Client US')
    if args and os.path.isdir(args[0]):
        client, args = args[0], args[1:]
    column = COLUMN
    if len(args) >= 2 and args[0] == '--column':
        column, args = args[1], args[2:]
    if not args or args[0] not in ('show', 'set', 'reset'):
        sys.exit(__doc__)
    backup = backup_of(client)
    if args[0] == 'reset':
        if os.path.exists(backup):
            shutil.copy2(backup, os.path.join(client, PACK))
            print('original pack restored')
        return
    files, text = load(client)
    lines = text.split('\r\n')
    col = lines[2].split('\t').index(column)
    if args[0] == 'show':
        for line in lines[3:]:
            f = line.split('\t')
            if len(f) > col and (len(args) < 2 or args[1].lower() in f[3].lower()):
                print(f'{f[3]:28} {f[col]}')
        return
    want = dict(a.split('=', 1) for a in args[1:])
    missing = set_values(client, column, want, files, lines)
    if missing:
        sys.exit(f'no such key: {", ".join(missing)} (nothing written)')


def set_values(client, column, want, files=None, lines=None):
    """Write values {key: value} into the table's column (also for other tools) -> the keys not found (then nothing is
    written)."""
    want = {k: str(v) for k, v in want.items()}
    backup = backup_of(client)
    if lines is None:
        files, text = load(client)
        lines = text.split('\r\n')
    col = lines[2].split('\t').index(column)
    for i, line in enumerate(lines):
        f = line.split('\t')
        if len(f) > col and f[3] in want:
            print(f'{f[3]}: {f[col]} -> {want[f[3]]}')
            f[col] = want.pop(f[3])
            lines[i] = '\t'.join(f)
    if want:
        return list(want)
    if not os.path.exists(backup):
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(os.path.join(client, PACK), backup)
        print('original pack kept as', os.path.normpath(backup))
    new = b'\xff\xfe' + '\r\n'.join(lines).encode('utf-16-le')
    write_pack(client, [(n, new if n == ENTRY else d) for n, d in files])
    print('written:', os.path.normpath(os.path.join(client, PACK)))
    return []


if __name__ == '__main__':
    main()
