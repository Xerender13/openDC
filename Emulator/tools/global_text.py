"""Read or change the 2011 client's texts, Localize\\GlobalText.xlt (keyed by number or name; the US client reads
the column Value_US), e.g. 11413 "[Team] %s has logged on." (the crew logon notice).

The table is in Client/Patch/Patch.006. `set` rewrites that pack with the changed texts and copies the
original header bytes 20-31 back (as global_content.py); the original pack is kept as
Emulator/client_backup/Patch.006.orig and `reset` puts it back (the vanilla client). The client reads the
packs when it starts.

`--column` picks another language column: Value_US (default) ... or EU_de / EU_eng / EU_fr / EU_es (the EU columns
are all headed "Value": columns 11-14, by nation 7-10). A client folder other than Client US keeps its own first
pack as client_backup/Patch.006_<folder>.orig.

usage: python3 Emulator/tools/global_text.py [client dir] [--column NAME] show TEXT   rows whose key or text contains TEXT
       python3 Emulator/tools/global_text.py [client dir] [--column NAME] set KEY=VALUE ...
       python3 Emulator/tools/global_text.py [client dir] reset
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402

PACK, ENTRY, COLUMN = os.path.join('Patch', 'Patch.006'), 'Data\\Localize\\GlobalText.xlt', 'Value_US'
BACKUP = os.path.join(HERE, '..', 'client_backup', 'Patch.006.orig')
RECORD = re.compile(r'\r\n(?=\d+\t\d+\tstring\t)')     # texts may hold line breaks inside quotes


EU_COLUMNS = {'EU_de': 11, 'EU_eng': 12, 'EU_fr': 13, 'EU_es': 14}


def backup_of(client):
    name = os.path.basename(os.path.normpath(os.path.abspath(client)))
    if name == 'Client US':
        return BACKUP
    return os.path.join(HERE, '..', 'client_backup', f'Patch.006_{name.replace(" ", "")}.orig')


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
    _, files = agt.read(os.path.join(client, PACK))
    text = dict(files)[ENTRY].decode('utf-16')
    records = RECORD.split(text)
    col = EU_COLUMNS.get(column) or records[0].split('\r\n')[2].split('\t').index(column)
    if args[0] == 'show':
        for r in records[1:]:
            f = r.split('\t')
            if len(f) > col and (len(args) < 2 or args[1].lower() in (f[3] + f[col]).lower()):
                print(f'{f[3]:12} {f[col]!r}')
        return
    want = dict(a.split('=', 1) for a in args[1:])
    missing = set_texts(client, column, want, records, files)
    if missing:
        sys.exit(f'no such key: {", ".join(missing)} (nothing written)')


def set_texts(client, column, want, records=None, files=None):
    """Write texts {key: text} into the pack's column (also for other tools) -> the keys not found (then nothing is
    written)."""
    want = dict(want)
    backup = backup_of(client)
    if records is None:
        _, files = agt.read(os.path.join(client, PACK))
        records = RECORD.split(dict(files)[ENTRY].decode('utf-16'))
    col = EU_COLUMNS.get(column) or records[0].split('\r\n')[2].split('\t').index(column)
    for i, r in enumerate(records):
        f = r.split('\t')
        if i and len(f) > col and f[3] in want:
            print(f'{f[3]}: {f[col]!r} -> {want[f[3]]!r}')
            f[col] = want.pop(f[3])
            records[i] = '\t'.join(f)
    if want:
        return list(want)
    if not os.path.exists(backup):
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(os.path.join(client, PACK), backup)
        print('original pack kept as', os.path.normpath(backup))
    new = b'\xff\xfe' + '\r\n'.join(records).encode('utf-16-le')
    write_pack(client, [(n, new if n == ENTRY else d) for n, d in files])
    return []


if __name__ == '__main__':
    main()
