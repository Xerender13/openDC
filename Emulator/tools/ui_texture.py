"""Read or change one interface picture of the 2011 US client. The UI controls in Data_US/gameui/game.nui
name their pictures "x,y~x2,y2_<texture>.dds" (e.g. the battle zone tooltip ID_PVPNEW_RMLOBBY_TOOLTIP_1ST:
"636,540~806,607_ui_contents30.dds"); each such piece is a small DDS of its own inside one of the
containers tex\\0.ntx .. tex\\F.ntx of Data_US/gameui/uitex.agt. A container entry: char[64] name, u32 size,
u32 tag (not a CRC / Adler / byte sum of the data; kept as it is), the DDS file.

`replace` writes the pack with the new DDS (same name; any size), copies the original header bytes 20-31
back (as global_content.py; see client_backup) and keeps the original pack as
Emulator/client_backup/uitex.agt.orig; `reset` puts it back (the vanilla client). The client reads the pack
when it starts.

usage: python3 Emulator/tools/ui_texture.py [client dir] find TEXT          pieces whose name contains TEXT
       python3 Emulator/tools/ui_texture.py [client dir] extract NAME OUT.dds
       python3 Emulator/tools/ui_texture.py [client dir] replace NAME IN.dds
       python3 Emulator/tools/ui_texture.py [client dir] reset
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402

PACK = os.path.join('Data_US', 'gameui', 'uitex.agt')
BACKUP = os.path.join(HERE, '..', 'client_backup', 'uitex.agt.orig')


def entries(ntx):
    """(name, offset of the entry, size) of each piece in a container."""
    off = 0
    while off + 72 <= len(ntx):
        name = ntx[off:off + 64].split(b'\0')[0].decode('latin-1')
        size = struct.unpack_from('<I', ntx, off + 64)[0]
        yield name, off, size
        off += 72 + size


def find(files, name):
    for i, (n, d) in enumerate(files):
        if n.lower().endswith('.ntx'):
            for e, off, size in entries(d):
                if e.lower() == name.lower():
                    return i, off, size
    sys.exit(f'no piece named {name}')


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
    if not args or args[0] not in ('find', 'extract', 'replace', 'reset'):
        sys.exit(__doc__)
    if args[0] == 'reset':
        if os.path.exists(BACKUP):
            shutil.copy2(BACKUP, os.path.join(client, PACK))
            print('original pack restored')
        return
    _, files = agt.read(os.path.join(client, PACK))
    if args[0] == 'find':
        for n, d in files:
            if n.lower().endswith('.ntx'):
                for e, _, size in entries(d):
                    if len(args) < 2 or args[1].lower() in e.lower():
                        print(f'{n}  {e}  {size}')
        return
    i, off, size = find(files, args[1])
    name, ntx = files[i]
    if args[0] == 'extract':
        open(args[2], 'wb').write(ntx[off + 72:off + 72 + size])
        print(f'{args[1]} ({name}, {size} bytes) -> {args[2]}')
        return
    new = open(args[2], 'rb').read()
    if new[:4] != b'DDS ':
        sys.exit(f'{args[2]} is not a DDS file')
    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copy2(os.path.join(client, PACK), BACKUP)
        print('original pack kept as', os.path.normpath(BACKUP))
    ntx = ntx[:off + 64] + struct.pack('<I', len(new)) + ntx[off + 68:off + 72] + new + ntx[off + 72 + size:]
    files[i] = (name, ntx)
    write_pack(client, files)
    print(f'{args[1]} ({name}): {size} -> {len(new)} bytes')


if __name__ == '__main__':
    main()
