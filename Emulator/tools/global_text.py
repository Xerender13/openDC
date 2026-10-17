"""Read or change the 2011 client's texts, Localize\\GlobalText.xlt (keyed by number or name; the US client reads
the column Value_US), e.g. 11413 "[Team] %s has logged on." (the crew logon notice).

The table is in Client/Patch/Patch.006. `set` rewrites that pack with the changed texts and copies the
original header bytes 20-31 back (as global_content.py); the original pack is kept as
Emulator/client_backup/Patch.006.orig and `reset` puts it back (the vanilla client). The client reads the
packs when it starts.

usage: python3 Emulator/tools/global_text.py [client dir] show TEXT          rows whose key or US text contains TEXT
       python3 Emulator/tools/global_text.py [client dir] set KEY=VALUE ...
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


def write_pack(client, files):
    """The pack with these files, its header bytes 20-31 as in the original."""
    path = os.path.join(client, PACK)
    orig = open(BACKUP if os.path.exists(BACKUP) else path, 'rb').read(32)
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
    if not args or args[0] not in ('show', 'set', 'reset'):
        sys.exit(__doc__)
    if args[0] == 'reset':
        if os.path.exists(BACKUP):
            shutil.copy2(BACKUP, os.path.join(client, PACK))
            print('original pack restored')
        return
    _, files = agt.read(os.path.join(client, PACK))
    text = dict(files)[ENTRY].decode('utf-16')
    records = RECORD.split(text)
    col = records[0].split('\r\n')[2].split('\t').index(COLUMN)
    if args[0] == 'show':
        for r in records[1:]:
            f = r.split('\t')
            if len(f) > col and (len(args) < 2 or args[1].lower() in (f[3] + f[col]).lower()):
                print(f'{f[3]:12} {f[col]!r}')
        return
    want = dict(a.split('=', 1) for a in args[1:])
    for i, r in enumerate(records):
        f = r.split('\t')
        if i and len(f) > col and f[3] in want:
            print(f'{f[3]}: {f[col]!r} -> {want[f[3]]!r}')
            f[col] = want.pop(f[3])
            records[i] = '\t'.join(f)
    if want:
        sys.exit(f'no such key: {", ".join(want)} (nothing written)')
    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copy2(os.path.join(client, PACK), BACKUP)
        print('original pack kept as', os.path.normpath(BACKUP))
    new = b'\xff\xfe' + '\r\n'.join(records).encode('utf-16-le')
    write_pack(client, [(n, new if n == ENTRY else d) for n, d in files])


if __name__ == '__main__':
    main()
