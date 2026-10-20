"""Pack a client's loose assets back into its .agt packs, and make the client read only from the packs there.

python -m tools.pack_client pack   [--client DIR] [--jobs N]   the loose files of each packed folder -> its .agt
python -m tools.pack_client verify [--client DIR]              every entry against its loose file (SHA-1)
python -m tools.pack_client patch  [--client DIR] [--undo]     NiSystem20VC71.dll: no loose files in packed folders
python -m tools.pack_client clean  [--client DIR] [--undo]     loose copies of packed files out of the client
python -m tools.pack_client status [--client DIR]

Made for the 2016 client (DriftCity Dev Ed, default): it ships every .agt as a 32-byte empty NayaPack and the assets
loose (Data 4.4 GB). The engine already prefers the packs: NiFile::NiFile (NiSystem 0x10004580; the 2011 and Dev Ed
DLLs have the same code) asks CNPacker::Find (0x10009210, the _fullpath of the name) first and calls fopen only when
the packs lack the file. So packing alone changes nothing the client sees; the patch then refuses the fopen fallback
for files inside the packed folders (tools/packonly/cave.s), so a loose copy there is never read.

A pack holds the files under its own folder, named relative to the folder the .agt is in (as the 2011 packs:
Data/World/cras.agt -> "Cras\\...", Data_US/gameui/uitex.agt -> "tex\\..."). Kept loose, as in the 2011 client, and allowed
by the patch: *.ini (Data/Init, the client writes goption.ini), *.ufm (Data/World/<city>), the .agt files, and every
folder without a pack (Data/World itself: hitbox.nif, *shader*.nif; Data/audio, miles, Sticker, GameUI/cursor, fonts,
teammark, adcar, adland, Data_US/gameui/game.nui ...). Backups (*.orig, *.bak, *.tmp, *.before*) are not packed. The patch packs (Patch/*.000-010) stay as they are.

Each pack is written to <pack>.tmp and swapped in; header bytes 20-31 are the old file's (CLAUDE.md), the entry count
is new. The first pack run copies the original packs to Emulator/client_backup/<client>/packs/; patch copies the DLL to
client_backup/<client>/NiSystem20VC71.dll.orig. The loose files stay where they are (after the patch they are unused).
After editing a loose file in a packed folder, run pack again (or the tool that made the edit writes the pack too:
tools/tutorial_flow.py).

clean (user, 2026-10-20: no duplicates outside the packs): every loose file whose pack entry is byte-identical moves to
the sibling folder "<client> (loose)" (same tree; a rename on the same disk), and the folders left empty go, except each
pack's own folder (the 2011 client keeps Data/World/<city> for its .ufm files). A loose file that differs from its pack
entry stays and is listed: pack again first. --undo moves them back. The packs are then the only copy in the client;
tools that read the 2016 client's files look in the sibling folder first (loose_path: tools/port2016.py,
semi_tooltips.py); the launcher and tutorial_flow read GlobalContent.xlt from Data/Localize.agt.
"""
import argparse
import hashlib
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

try:
    from . import agt
except ImportError:                     # imported as a plain module (tools/ on sys.path: port2016.py)
    import agt

ROOT = Path(__file__).resolve().parents[2]
BACKUPS = ROOT / 'Emulator' / 'client_backup'
CHUNK = 16384                       # the 2011 packs' chunk size
# (pack, folder it holds): the packs the 2016 exe mounts (0x4ffe..0x5015) and the 2011 packs' contents
PACKS = [('Data/Init.agt', 'Data/Init'), ('Data/Localize.agt', 'Data/Localize'), ('Data/Option.agt', 'Data/Option'),
         ('Data/decal.agt', 'Data/decal'), ('Data/effects.agt', 'Data/effects'), ('Data/game.agt', 'Data/Game'),
         ('Data/shader.agt', 'Data/shader'), ('Data/vehicles.agt', 'Data/vehicle'),
         ('Data/GameUI/uitex.agt', 'Data/GameUI/tex'),
         ('Data/World/autoshop.agt', 'Data/World/AutoShop'), ('Data/World/cras.agt', 'Data/World/Cras'),
         ('Data/World/data.agt', 'Data/World/Data'), ('Data/World/garage.agt', 'Data/World/Garage'),
         ('Data/World/koinonia.agt', 'Data/World/Koinonia'), ('Data/World/moonpalace.agt', 'Data/World/MoonPalace'),
         ('Data/World/neodata.agt', 'Data/World/NeoData'), ('Data/World/neoobject.agt', 'Data/World/NeoObject'),
         ('Data/World/neooros.agt', 'Data/World/NeoOros'), ('Data/World/oros.agt', 'Data/World/Oros'),
         ('Data/World/parkinglot.agt', 'Data/World/parkinglot'), ('Data/World/taipei.agt', 'Data/World/Taipei'),
         ('Data_US/Init_us.agt', 'Data_US/Init'), ('Data_US/World.agt', 'Data_US/World'),
         ('Data_US/effects_us.agt', 'Data_US/effects'), ('Data_US/game_us.agt', 'Data_US/Game'),
         ('Data_US/vehicles_us.agt', 'Data_US/vehicle'), ('Data_US/gameui/uitex.agt', 'Data_US/gameui/tex')]
LOOSE_EXT = ('.ini', '.ufm', '.agt')                       # cave.s allows these in the packed folders too
SKIP = ('.orig', '.bak', '.tmp')


def find(base, rel):
    """rel under base, matching each part without case (Windows paths) -> Path or None."""
    p = Path(base)
    for part in Path(rel).parts:
        if not p.is_dir():
            return None
        hit = next((c for c in p.iterdir() if c.name.lower() == part.lower()), None)
        if hit is None:
            return None
        p = hit
    return p


def packed_files(client, pack, folder):
    """[(entry name, path)] of one pack's folder, sorted."""
    pack_path, src = find(client, pack), find(client, folder)
    if pack_path is None or src is None or not src.is_dir():
        return []
    out = []
    for dirpath, dirs, files in os.walk(src):
        dirs.sort()
        for f in sorted(files):
            low = f.lower()
            if low.endswith(LOOSE_EXT) or low.endswith(SKIP) or '.before' in low:
                continue
            path = Path(dirpath) / f
            out.append((str(path.relative_to(pack_path.parent)).replace('/', '\\'), path))
    return out


class XorWriter:
    """Writes at absolute file positions with the NayaPack XOR key (every byte after the 32-byte header)."""
    def __init__(self, f):
        self.f, self.k = f, len(agt.KEY)

    def write_at(self, pos, data):
        self.f.seek(pos)
        if pos < 32:
            head = 32 - pos
            self.f.write(data[:head])
            data, pos = data[head:], 32
        if data:
            n = len(data)
            ks = (agt.KEY[pos % self.k:] + agt.KEY * (n // self.k + 2))[:n]
            self.f.write((int.from_bytes(data, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little'))


def write_pack(path, files, header):
    """Streams files [(name, path or bytes)] into the NayaPack path (via path.tmp); header: the old 32 bytes (20-31
    kept)."""
    names = [n.encode('latin-1') for n, _ in files]
    table_end = 32 + sum(16 + len(n) for n in names)
    tmp = Path(str(path) + '.tmp')
    entries, pos = [], table_end
    with open(tmp, 'wb') as f:
        w = XorWriter(f)
        for (name, src), raw_name in zip(files, names):
            data = src if isinstance(src, bytes) else src.read_bytes()
            chunks = [zlib.compress(data[i:i + CHUNK], 6) for i in range(0, len(data), CHUNK)] or [zlib.compress(b'')]
            block = struct.pack(f'<{len(chunks)}H', *map(len, chunks)) + b''.join(chunks)
            w.write_at(pos, block)
            entries.append(struct.pack('<4i', pos, len(chunks), len(data), len(raw_name)) + raw_name)
            pos += len(block)
        hdr = bytearray(header[:32])
        struct.pack_into('<i', hdr, 16, len(files))
        w.write_at(0, bytes(hdr) + b''.join(entries))
    os.replace(tmp, path)
    return pos


def replace_entry(path, name, data):
    """One existing entry of a pack replaced, the others kept. -> False when the pack has no such entry."""
    raw, entries = agt.index(path)
    if not any(e[0].lower() == name.lower() for e in entries):
        return False
    write_pack(path, [(e[0], data if e[0].lower() == name.lower() else agt.extract(raw, e)) for e in entries], raw[:32])
    return True


def pack_one(job):
    client, pack, folder = job
    path = find(client, pack)
    files = packed_files(client, pack, folder)
    if path is None:
        return pack, None, 0, 0
    header = path.read_bytes()[:32]
    if header[:8] != b'NayaPack':
        raise ValueError(f'{path} is not a NayaPack file')
    size = write_pack(path, files, header)
    return pack, len(files), sum(p.stat().st_size for _, p in files), size


def loose_dir(client):
    return Path(client).parent / (Path(client).name + ' (loose)')


def loose_path(client, *parts):
    """A file or folder of the client as a tool reads it: its loose copy moved out by clean, else the client's own."""
    moved = os.path.join(loose_dir(client), *parts)
    return moved if os.path.exists(moved) else os.path.join(client, *parts)


def clean(client, undo=False):
    out = loose_dir(client)
    if undo:
        n = 0
        for dirpath, dirs, files in os.walk(out):
            for f in files:
                src = Path(dirpath) / f
                dst = Path(client) / src.relative_to(out)
                if dst.exists():
                    print(f'kept (the client has one): {dst.relative_to(client)}')
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.replace(src, dst)
                n += 1
        for dirpath, dirs, files in sorted(os.walk(out), key=lambda w: -len(w[0])):
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        print(f'{n} files back in {client}')
        return
    moved, differ, size = 0, [], 0
    for pack, folder in PACKS:
        path = find(client, pack)
        if path is None:
            continue
        raw, entries = agt.index(path)
        packed = {e[0].lower(): e for e in entries}
        for name, src in packed_files(client, pack, folder):
            e = packed.get(name.lower())
            if e is None or agt.extract(raw, e) != src.read_bytes():
                differ.append(str(src.relative_to(client)))
                continue
            dst = out / src.relative_to(client)
            dst.parent.mkdir(parents=True, exist_ok=True)
            size += src.stat().st_size
            os.replace(src, dst)
            moved += 1
        root = find(client, folder)
        if root is not None:
            for dirpath, dirs, files in sorted(os.walk(root), key=lambda w: -len(w[0])):
                if Path(dirpath) != root and not os.listdir(dirpath):
                    os.rmdir(dirpath)
    print(f'{moved} loose files ({size >> 20} MB) moved to {out}')
    if differ:
        print(f'{len(differ)} differ from their pack and stayed (run pack first): {differ[:10]}')


def backup_dir(client):
    return BACKUPS / Path(client).name.replace(' ', '_')


def pack(client, jobs):
    # after clean the packs are the only copy (the loose folder was deleted 2026-10-20): packing the few loose files
    # left would drop every other entry. Tools change single entries with replace_entry instead.
    for p, f in PACKS:
        path = find(client, p)
        if path is not None and len(agt.index(path)[1]) > len(packed_files(client, p, f)):
            raise SystemExit(f'{p}: the pack has entries that are not loose files in the client (cleaned): not packed')
    dest = backup_dir(client) / 'packs'
    for p, _ in PACKS:
        path = find(client, p)
        if path is not None and not (dest / p).exists():
            (dest / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest / p)
    # the big folders first, so the pool stays busy
    order = sorted(PACKS, key=lambda pf: -sum(s.stat().st_size for _, s in packed_files(client, *pf)))
    with ProcessPoolExecutor(jobs) as pool:
        for name, n, raw, size in pool.map(pack_one, [(client, p, f) for p, f in order]):
            if n is None:
                print(f'{name}: no such pack, skipped')
            else:
                print(f'{name}: {n} files, {raw >> 20} MB -> {size >> 20} MB', flush=True)


def verify_one(job):
    client, pack, folder = job
    path = find(client, pack)
    want = {n.lower(): p for n, p in packed_files(client, pack, folder)}
    if path is None:
        return pack, 0, []
    raw, entries = agt.index(path)
    bad = []
    for e in entries:
        src = want.pop(e[0].lower(), None)
        if src is None or hashlib.sha1(agt.extract(raw, e)).digest() != hashlib.sha1(src.read_bytes()).digest():
            bad.append(e[0])
    return pack, len(entries), bad + [f'missing: {n}' for n in want]


def verify(client, jobs):
    ok = True
    with ProcessPoolExecutor(jobs) as pool:
        for name, n, bad in pool.map(verify_one, [(client, p, f) for p, f in PACKS]):
            print(f'{name}: {n} entries' + (f', {len(bad)} wrong: {bad[:5]}' if bad else ', all match the loose files'))
            ok &= not bad
    return ok


# ---- the NiSystem20VC71.dll patch (tools/packonly/cave.s)
DLL = 'NiSystem20VC71.dll'
HOOK, CAVE, TABLE = 0x10004650, 0x10012da0, 0x1001c240
HOOK_ORIG = bytes.fromhex('3bc389460c7537')               # cmp eax, ebx; mov [esi+0xc], eax; jne 0x1000468e


def sections(b):
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    n, opt = struct.unpack_from('<H', b, pe + 6)[0], struct.unpack_from('<H', b, pe + 20)[0]
    base = struct.unpack_from('<I', b, pe + 52)[0]
    out = []
    for i in range(n):
        o = pe + 24 + opt + 40 * i
        name, vsize, va, rsize, roff = struct.unpack_from('<8sIIII', b, o)
        out.append(dict(name=name.rstrip(b'\0').decode(), hdr=o, vsize=vsize, va=base + va, rsize=rsize, roff=roff))
    return base, out


def section_of(secs, addr):
    return next(s for s in secs if s['va'] <= addr < s['va'] + s['rsize'])


def folder_table():
    """The packed folders as cave.s compares them: lower case, backslashes, "\\data\\world\\cras\\"; one NUL each, a
    NUL at the end. Exact folders: Data/World itself also holds loose models no pack has (hitbox.nif, env_shader.nif,
    shader_terrain.nif, pc_shader.nif, as in the 2011 client); refusing all of Data/World crashed the client after
    "Vehicle Texture Load" (NiMain +0x2825a)."""
    return b''.join(('\\' + f.lower().replace('/', '\\') + '\\').encode() + b'\0' for _, f in PACKS) + b'\0'


def build_cave():
    """Assemble cave.s (GNU as / ld / objcopy) -> (code, table)."""
    src = Path(__file__).with_name('packonly') / 'cave.s'
    with tempfile.TemporaryDirectory() as d:
        run = lambda *a: subprocess.run(a, check=True, capture_output=True, cwd=d)
        run('as', '--32', '-o', 'cave.o', str(src))
        run('ld', '-m', 'elf_i386', f'-Ttext={CAVE:#x}', '-o', 'cave.elf', 'cave.o')
        run('objcopy', '-O', 'binary', '-j', '.text', 'cave.elf', 'code.bin')
        return (Path(d) / 'code.bin').read_bytes(), folder_table()


def patched_image(orig, code, table):
    b = bytearray(orig)
    base, secs = sections(b)
    off = lambda a: section_of(secs, a)['roff'] + a - section_of(secs, a)['va']
    if b[off(HOOK):off(HOOK) + 7] != HOOK_ORIG:
        raise ValueError(f'{DLL}: unexpected code at {HOOK:#x}; refusing to patch')
    for addr, blob in ((CAVE, code), (TABLE, table)):
        s = section_of(secs, addr)
        if addr < s['va'] + s['vsize'] or addr + len(blob) > s['va'] + s['rsize']:
            raise ValueError(f'{DLL}: no room at {addr:#x} in {s["name"]}')
        if any(b[off(addr):off(addr) + len(blob)].strip(b'\0\xcc')):
            raise ValueError(f'{DLL}: {addr:#x} is not empty')
        b[off(addr):off(addr) + len(blob)] = blob
        struct.pack_into('<I', b, s['hdr'] + 8, addr + len(blob) - s['va'])      # VirtualSize covers it
    jump = b'\xe9' + struct.pack('<i', CAVE - (HOOK + 5)) + b'\x90\x90'
    b[off(HOOK):off(HOOK) + 7] = jump
    return bytes(b)


def patch(client, undo=False):
    path = find(client, DLL)
    backup = backup_dir(client) / (DLL + '.orig')
    if undo:
        if not backup.exists():
            raise SystemExit(f'no backup {backup}')
        shutil.copy2(backup, path)
        print(f'{path}: original restored')
        return
    current = path.read_bytes()
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    orig = backup.read_bytes()
    new = patched_image(orig, *build_cave())
    if current not in (orig, new):
        raise SystemExit(f'{path} differs from its backup and from the patched image; refusing to overwrite it')
    tmp = Path(str(path) + '.tmp')
    tmp.write_bytes(new)
    tmp.chmod(path.stat().st_mode)
    tmp.replace(path)
    print(f'{path}: packed folders read only from the packs (backup {backup})')


def status(client):
    for p, f in PACKS:
        path = find(client, p)
        n = len(agt.index(path)[1]) if path else None
        print(f'{p:28} {"missing" if n is None else f"{n} entries"}, {len(packed_files(client, p, f))} loose files')
    path = find(client, DLL)
    b = path.read_bytes() if path else b''
    if b:
        _, secs = sections(b)
        s = section_of(secs, HOOK)
        at = b[s['roff'] + HOOK - s['va']:][:7]
        print(f'{DLL}: ' + ('pack-only patch on' if at[0] == 0xe9 else 'original' if at == HOOK_ORIG else f'unknown {at.hex()}'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('action', choices=('pack', 'verify', 'patch', 'clean', 'status'))
    ap.add_argument('--client', type=Path, default=ROOT / 'DriftCity Dev Ed')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--undo', action='store_true', help='patch: the original DLL back; clean: the loose files back')
    a = ap.parse_args()
    client = a.client.resolve()
    if a.action == 'pack':
        pack(client, a.jobs)
    elif a.action == 'verify':
        sys.exit(0 if verify(client, a.jobs) else 1)
    elif a.action == 'patch':
        patch(client, a.undo)
    elif a.action == 'clean':
        clean(client, a.undo)
    else:
        status(client)


if __name__ == '__main__':
    main()
