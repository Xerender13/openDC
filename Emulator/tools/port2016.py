"""Content of the 2016 client (DriftCity Dev Ed, exe 2016-02; loose files) added to the 2011 US client.

`tracks` (user, 2026-10-19: "Port the tracks"): the battle zone tracks of the 2016 PVPTrackInfo.xlt that the 2011 one
lacks, 9 rows (map ids 93-102):
  - with new files: Oros Track19 (id 98), Koinonia Track24 / Track25 (101 / 102, a track and its reverse), Cras Track24 /
    Track25 (99 / 100). Their folders (Data/World/<City>/Track<N>: terrain, objects, hit meshes, camera, AI path),
    Path/PVP_map<city>_<N>.chpath and the city's Obj files the 2016 client has and 2011 lacks go into the city's pack
    (Data/World/<city>.agt). The models are the same Gamebryo 20.0.0.4 files as 2011's.
  - with files already in the 2011 client: Taipei Track3 / Track5 / Track7 (93 / 96 / 97; the folders and
    PVP_map5_03/05/07 were in the 2011 taipei.agt, unused) and Koinonia Track23 (95).
  The rows go to Init/PVPTrackInfo.xlt (Data_US/Init_us.agt) after the last track (a block = the track's row + its
  gate rows; Index renumbered, the header's Count / TrackCnt updated). The track pictures of the battle zone windows
  are found by name (PVPTrackInfo "name", e.g. cras_track24, cras_track24_r): their controls are copied from the 2016
  game.nui dialogs 1170000 / 1180000 / 1190000 to the 2011 ones 1060000 / 1070000 / 1080000 (the same windows),
  with the picture pieces they use (uitex.agt; see `pieces`).
  The server copy (server_data/Init/PVPTrackInfo.xlt) is written too; restart the emulator.
  Not done: race traffic on the new tracks (the 2008 server's PVP_map*.index files exist only for 2008 tracks).

`cars` (user: "all the new cars that are absent in 2011 (player cars only)"): the 218 player cars of the 2016
VehicleList whose Unique Id the 2011 one lacks (94, 127, 198-442, ...):
  - Data/vehicles.agt: their models / textures / neon (vehicle\\player, texture, neon) and 20 tire models
    (vehicle\\player\\wheel) with the textures the models name; Data_US/audio/engine: idle<uid>.wav / mid<uid>.wav.
  - Data_US/Init_us.agt: VehicleList (rows after the last player car; the 2016 column 77 "Color Group Name" left
    out), VehicleUpgrade (9 rows per car: the client groups rows by 9), VehicleDisplay (2016 "Category" left out),
    TireList, VisualItem (a car column each: row 2 is the car's Unique Id = its byte in the client's item record;
    values from the 2016 table for the same item, matched by the 2016 Unique Id; the cars' aero sets pc_XXXXs_0N
    as rows), VShopItem (the aero sets' rows, Unique Ids 20622-21749 as in 2016; tools/shop_rows.py keeps them).
  - UseItemClient.tdf where the client reads it (Patch/Patch.004): the car keys (column 9 = the Unique Id).
  - game.nui / uitex.agt: the cars' pictures found by name (key icon 1800000, name images 2610000 / 2620000 /
    2630000) and the aero icons (2650000), from the 2016 dialogs 1990000 / 2840000-2860000 / 2880000. The 2016 Dev Ed
    files lack many of those pieces; they come from the Drift City World client's uitex.agt (WORLD_UITEX).
  - Unique Ids 300-303 become 102-105 (UID_MAP): bytes +0x7c+300..303 of the item record are its float at +0x1a8.
  - Client US/DriftCityUS.exe: the car limit raised (`exe`, below). server_data gets the same tables.
`exe`: the 2011 client keeps, per VisualItem item, one byte per car Unique Id at +0x7c of a 0x1ac-byte record (Ids <
  300; LoadVisualItemList 0x84ad00, manager 0x7690c0-0x769f00, cache of 300 x 56 default parts at manager +0x710).
  The patch (EXE_PATCHES, code in tools/p16_cars.s, section .p16 at 0xa1e000): records of 0x27c bytes (Ids < 512),
  the loader with its column map / record in .p16 (1024 columns), the cache used for Ids < 300 only (0x7694e0 for the
  others), the Ids < 300 checks of 0x7694a8 / 0x7694f6 / 0x769bd9 / 0x679b7d / 0x602202 / 0x67dbf9 / 0x68ed76 raised
  to 512. tools/eu_client.py `us` and `setup` apply it again when the US tables hold the 2016 cars.

Packs are rewritten with header bytes 20-31 kept; the first original of each is kept in client_backup/ (same name +
.orig). Entries already in a pack are replaced, so running again is safe. `reset` puts the originals back.

`eu` before the command does the same for the European client (Client EU: its own packs, Data_EU_eng/World.agt for the
keys, DriftCityEU.exe; backups <name>_ClientEU...orig); its server tables are the US run's.

`tires`: the ported tires' icons (game.nui 2650000 + uitex pieces; `cars` left them out), see port_tire_icons.

usage: .venv/bin/python -m tools.port2016 [us|eu] tracks | cars [dry-run folder] | exe [exe] | small | tires | reset
       (small: the ported small ST cars labelled SMALL in VehicleList, see small_cars)
"""
import os
import re
import shutil
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402
from ui_texture import entries  # noqa: E402

ROOT = os.path.join(HERE, '..', '..')
CLIENT = os.path.join(ROOT, 'Client US')
# the client a run changes (`eu` on the command line: the European client, tools/eu_client.py's folder). The EU client has
# its own copies of the packs (Data/vehicles.agt, Data/World/*.agt, Data_EU_eng/*) and reads UseItemClient.tdf from
# Data_EU_eng/World.agt (setup folds the US patch tables in there); the server tables are the US run's.
TARGETS = {
    'us': dict(name='Client US', root=CLIENT, data='Data_US', init='Init_us.agt', exe='DriftCityUS.exe', server=True,
               keys=None),
    'eu': dict(name='Client EU', root=os.path.join(ROOT, 'Client EU'), data='Data_EU_eng', init='Init_eueng.agt',
               exe='DriftCityEU.exe', server=False, keys=(os.path.join('Data_EU_eng', 'World.agt'), 'World\\data\\UseItemClient.tdf')),
}
T = TARGETS['us']


def backup_path(path):
    """client_backup/ name of a pack's first original: <name>.orig for the US client; for the EU client the name its
    tools already use (<stem>_ClientEU<ext>.orig, or <stem>_Data_EU_eng<ext>.orig for uitex / game.nui / World),
    never DriftCityEU.exe.orig (the vanilla unpacked exe tools/eu_client.py builds both exes from)."""
    base = os.path.basename(path)
    if T is TARGETS['us']:
        return os.path.join(BACKUPS, base + '.orig')
    stem, ext = os.path.splitext(base)
    cands = [os.path.join(BACKUPS, f'{stem}_ClientEU{ext}.orig'), os.path.join(BACKUPS, f'{stem}_{T["data"]}{ext}.orig')]
    return next((c for c in cands if os.path.exists(c)), cands[0])


def tpath(*parts):
    """A path in the target client: tpath('DATA', 'gameui', 'game.nui') -> .../Data_US|Data_EU_eng/gameui/game.nui."""
    return os.path.join(T['root'], *[T['data'] if x == 'DATA' else x for x in parts])
DEV = os.path.join(ROOT, 'DriftCity Dev Ed')


def dev_path(*parts):
    """A 2016 client file: its loose copy (moved out by tools/pack_client.py clean, the packs being the client's copy)."""
    from pack_client import loose_path
    return loose_path(DEV, *parts)
BACKUPS = os.path.join(HERE, '..', 'client_backup')
SERVER_DATA = os.path.join(HERE, '..', 'server_data')

# (city folder in Data/World, pack, track folders with new files, Path files)
TRACK_FILES = [
    ('Oros', 'oros', ['Track19'], ['PVP_map4_19.chpath']),
    ('Koinonia', 'koinonia', ['Track24', 'Track25'], ['PVP_map2_24.chpath', 'PVP_map2_25.chpath']),
    ('Cras', 'cras', ['Track24', 'Track25'], ['PVP_map3_24.chpath', 'PVP_map3_25.chpath']),
]
NEW_TRACK_IDS = {93, 95, 96, 97, 98, 99, 100, 101, 102}
TRACK_DIALOGS = {'1170000': '1060000', '1180000': '1070000', '1190000': '1080000'}   # 2016 -> 2011 game.nui


# ---- packs ------------------------------------------------------------------------------------------------------

def _xor(data, pos):
    """data XORed with the pack key from absolute position pos (positions below 32 are the plain header)."""
    k, n = agt.KEY, len(agt.KEY)
    out = bytearray()
    step = n * 100000
    for i in range(0, len(data), step):
        part = data[i:i + step]
        p = pos + i
        ks = (k[p % n:] + k * (len(part) // n + 2))[:len(part)]
        out += (int.from_bytes(part, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(len(part), 'little')
    return bytes(out)


def _blob(data, chunk=16384):
    chunks = [zlib.compress(data[i:i + chunk], 6) for i in range(0, len(data), chunk)] or [zlib.compress(b'')]
    return len(chunks), struct.pack(f'<{len(chunks)}H', *map(len, chunks)) + b''.join(chunks)


def pack_update(path, add):
    """Write the pack at path with the entries of add {name: data} added (replacing entries of the same name, case
    ignored). The other entries' compressed data is copied as it is. Header bytes 20-31 kept; first original kept."""
    backup = backup_path(path)
    if not os.path.exists(backup):
        os.makedirs(BACKUPS, exist_ok=True)
        shutil.copy2(path, backup)
        print('  original kept as', os.path.normpath(backup))
    raw, ents = agt.index(path)
    names = {n.lower() for n in add}
    keep = []
    for name, hp, cc, dlen in ents:
        if name.lower() in names:
            continue
        lens = struct.unpack_from(f'<{cc}H', agt.xor_range(raw, hp, hp + 2 * cc))
        keep.append((name, cc, dlen, hp, 2 * cc + sum(lens)))
    new = []
    for name, data in add.items():
        cc, blob = _blob(data)
        new.append((name, cc, len(data), blob))
    table_len = sum(16 + len(e[0].encode('latin-1')) for e in keep + new)
    off = 32 + table_len
    table = bytearray()
    for name, cc, dlen, hp, blen in keep:
        table += struct.pack('<4i', off, cc, dlen, len(name.encode('latin-1'))) + name.encode('latin-1')
        off += blen
    for name, cc, dlen, blob in new:
        table += struct.pack('<4i', off, cc, dlen, len(name.encode('latin-1'))) + name.encode('latin-1')
        off += len(blob)
    if off >= 2 ** 31:
        sys.exit(f'{path}: would pass 2 GB (nothing written)')
    header = bytearray(raw[:32])
    struct.pack_into('<i', header, 16, len(keep) + len(new))
    tmp = path + '.new'
    with open(tmp, 'wb') as f:
        f.write(header)
        pos = 32
        f.write(_xor(bytes(table), pos))
        pos += len(table)
        for name, cc, dlen, hp, blen in keep:
            f.write(_xor(agt.xor_range(raw, hp, hp + blen), pos))
            pos += blen
        for name, cc, dlen, blob in new:
            f.write(_xor(blob, pos))
            pos += len(blob)
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    print(f'  {os.path.relpath(path, ROOT)}: {len(keep)} entries kept, {len(new)} added / replaced')


def pack_entries(path):
    raw, ents = agt.index(path)
    return {e[0].lower(): e[0] for e in ents}


def read_entry(path, name):
    raw, ents = agt.index(path)
    for e in ents:
        if e[0].lower() == name.lower():
            return agt.extract(raw, e)
    return None


# ---- tables -----------------------------------------------------------------------------------------------------

def xlt_lines(data):
    return data.decode('utf-16-le').lstrip('﻿').split('\r\n')


def xlt_bytes(lines):
    return b'\xff\xfe' + '\r\n'.join(lines).encode('utf-16-le')


def track_blocks(lines):
    """[(track id or None, [line indexes])] of a PVPTrackInfo.xlt: a track = its row (city filled) + the gate rows."""
    blocks = []
    for i, line in enumerate(lines[3:], 3):
        f = line.split('\t')
        if not f[0].strip().isdigit():
            continue
        if len(f) > 4 and f[2].strip():
            blocks.append((int(f[4]), [i]))
        elif blocks:
            blocks[-1][1].append(i)
    return blocks


def ported_tracks(old, dev):
    """The 2011 PVPTrackInfo lines with the 2016 tracks of NEW_TRACK_IDS (again) after its last track."""
    lines = list(old)
    drop = {i for tid, idx in track_blocks(lines) if tid in NEW_TRACK_IDS for i in idx}
    lines = [l for i, l in enumerate(lines) if i not in drop]
    blocks = track_blocks(lines)
    at = blocks[-1][1][-1] + 1
    add = []
    for tid, idx in track_blocks(dev):
        if tid in NEW_TRACK_IDS:
            add += [dev[i] for i in idx]
    lines[at:at] = add
    n = 0
    for i, line in enumerate(lines[3:], 3):
        f = line.split('\t')
        if f[0].strip().isdigit():
            f[0] = str(n)
            n += 1
            lines[i] = '\t'.join(f)
    tracks = len(track_blocks(lines))
    f = lines[1].split('\t')
    f[1], f[2] = str(n), str(tracks)
    lines[1] = '\t'.join(f)
    return lines, len(add), tracks


# ---- interface: game.nui controls and uitex.agt pieces ----------------------------------------------------------

def container_of(piece):
    """uitex.agt keeps a piece in tex\\<h>.ntx, h = the byte sum of its lower-case atlas name (after the first '_')
    % 16 (true for 8526 of the 8533 pieces of the 2011 pack)."""
    return sum(piece.split('_', 1)[1].lower().encode('latin-1')) % 16


WORLD_UITEX = os.environ.get('DC_WORLD_UITEX', os.path.expanduser(
    os.path.join('~', 'Drift City World', 'DriftCity', 'Data_US', 'gameui', 'uitex.agt')))
_world = None


def dev_piece(name):
    """A picture piece by name: the 2016 client's loose tex\\*.ntx, else the Drift City World client's uitex.agt
    (WORLD_UITEX; the 2016 Dev Ed files lack many pieces its own game.nui names, e.g. most car name images)."""
    global _world
    path = dev_path('Data_US', 'gameui', 'tex', '%x.ntx' % container_of(name))
    for cand in [path] + [dev_path('Data_US', 'gameui', 'tex', '%x.ntx' % h) for h in range(16)]:
        if not os.path.exists(cand):
            continue
        ntx = open(cand, 'rb').read()
        for e, off, size in entries(ntx):
            if e.lower() == name.lower():
                return ntx[off + 72:off + 72 + size]
    if _world is None:
        _world = {}
        if os.path.exists(WORLD_UITEX):
            for n, d in agt.read(WORLD_UITEX)[1]:
                if n.lower().endswith('.ntx'):
                    for e, off, size in entries(d):
                        _world.setdefault(e.lower(), d[off + 72:off + 72 + size])
    return _world.get(name.lower())


class Interface:
    """game.nui (text, euc-kr) and uitex.agt of the 2011 US client, changed together."""

    def __init__(self):
        self.nui_path = tpath('DATA', 'gameui', 'game.nui')
        self.tex_path = tpath('DATA', 'gameui', 'uitex.agt')
        self.nui = open(self.nui_path, 'rb').read().decode('cp949')
        self.dev_nui = open(dev_path('Data_US', 'gameui', 'game.nui'), 'rb').read().decode('cp949')
        header, files = agt.read(self.tex_path)
        self.tex_header, self.tex_files = header, files
        self.pieces = {}
        for i, (n, d) in enumerate(files):
            if n.lower().endswith('.ntx'):
                for e, off, size in entries(d):
                    self.pieces[e.lower()] = (i, d[off + 72:off + 72 + size])
        self.add_pieces = {}          # piece name -> data
        self.changed = False

    def dialog(self, text, dlg):
        m = re.search(r'<DIALOG C="%s"[^>]*>.*?</DIALOG>' % dlg, text, re.S)
        return m

    def controls(self, text, dlg):
        """{NM: control xml} of a dialog."""
        m = self.dialog(text, dlg)
        out = {}
        for c in re.finditer(r'[ \t]*<CONTROL B="\d+"[^>]*>.*?</CONTROL>\r?\n?', m.group(0), re.S):
            nm = re.search(r'NM="([^"]*)"', c.group(0))
            if nm:
                out.setdefault(nm.group(1), c.group(0))
        return out

    def piece_for(self, name):
        """A picture piece of the 2016 client for the 2011 pack -> (the name to use, data to add or None), or None when
        the 2016 pack has no such piece. The same name when the 2011 pack has no such piece or the same picture; else a
        renamed copy, kept in the container its new name hashes to."""
        data = dev_piece(name)
        if data is None:
            return None
        have = self.pieces.get(name.lower())
        if have is None:
            return name, data
        if have[1] == data:
            return name, None
        coords, atlas = name.split('_', 1)
        new = f'{coords}_p16{atlas}'
        if new.lower() in self.pieces and self.pieces[new.lower()][1] == data:
            return new, None
        return new, data

    def place_tracks(self, dlg):
        """The controls this tool added to a battle zone track dialog moved to just after its last original track
        picture (the original controls keep their order): the client shows the selected track's picture among the
        controls before the dialog's other ones (user: after the port every track showed the same picture, the added
        ones were after the dialog's other controls and stayed drawn on top). -> True when moved."""
        orig_ids = set(re.findall(r'<CONTROL B="(\d+)"', self.dialog(self.orig_nui(), dlg).group(0)))
        m = self.dialog(self.nui, dlg)
        block = m.group(0)
        ctl = list(re.finditer(r'[ \t]*<CONTROL B="\d+"[^>]*>.*?</CONTROL>\r?\n?', block, re.S))
        cid = lambda c: re.search(r'<CONTROL B="(\d+)"', c.group(0)).group(1)
        is_track = lambda c: bool(re.search(r'NM="[a-z]+_(track|laptime|tutorial)', c.group(0), re.I))
        old = [c for c in ctl if cid(c) in orig_ids]
        added = [c.group(0) for c in ctl if cid(c) not in orig_ids]
        last = max((i for i, c in enumerate(old) if is_track(c)), default=len(old) - 1)
        order = [c.group(0) for c in old[:last + 1]] + added + [c.group(0) for c in old[last + 1:]]
        if [c.group(0) for c in ctl] == order:
            return False
        head, tail = block[:ctl[0].start()], block[ctl[-1].end():]
        self.nui = self.nui[:m.start()] + head + ''.join(order) + tail + self.nui[m.end():]
        self.changed = True
        return True

    def orig_nui(self):
        if not hasattr(self, '_orig'):
            b = backup_path(self.nui_path)
            self._orig = open(b if os.path.exists(b) else self.nui_path, 'rb').read().decode('cp949')
        return self._orig

    def copy_controls(self, dev_dlg, dlg, names):
        """Copy the 2016 dialog's controls named names into the 2011 dialog (new B ids; missing ones only, a 2011
        control of that name whose picture differs gets the 2016 picture; controls whose picture the 2016 pack lacks
        are left out). -> names copied."""
        have = self.controls(self.nui, dlg)
        dev = self.controls(self.dev_nui, dev_dlg)
        m = self.dialog(self.nui, dlg)
        block = m.group(0)
        ids = [int(b) for b in re.findall(r'<CONTROL B="(\d+)"', block)]
        next_id = max(ids) + 1
        done = []
        self.skipped = getattr(self, 'skipped', [])
        for nm in names:
            if nm not in dev:
                continue
            xml = dev[nm]
            uses = {pic: self.piece_for(pic) for pic in set(re.findall(r'I1_\d="([^"]+\.dds)"', xml))}
            if any(u is None for u in uses.values()):
                self.skipped.append(nm)
                continue
            for pic, (use, _) in uses.items():
                xml = xml.replace(f'"{pic}"', f'"{use}"')
            if nm in have:
                old_pics = set(re.findall(r'I1_\d="([^"]+\.dds)"', have[nm]))
                if old_pics == {use for use, _ in uses.values()}:
                    continue
                for use, data in uses.values():
                    if data is not None:
                        self.add_pieces[use] = data
                b = re.search(r'<CONTROL B="(\d+)"', have[nm]).group(1)        # in place, with its own id
                block = block.replace(have[nm], re.sub(r'<CONTROL B="\d+"', f'<CONTROL B="{b}"', xml, count=1))
                done.append(nm)
                continue
            for use, data in uses.values():
                if data is not None:
                    self.add_pieces[use] = data
            xml = re.sub(r'<CONTROL B="\d+"', f'<CONTROL B="{next_id}"', xml, count=1)
            next_id += 1
            end = block.rfind('</DIALOG>')
            line_start = block.rfind('\n', 0, end) + 1
            block = block[:line_start] + xml + block[line_start:]
            done.append(nm)
        if done:
            self.nui = self.nui[:m.start()] + block + self.nui[m.end():]
            self.changed = True
        return done

    def save(self):
        if self.changed:
            backup = backup_path(self.nui_path)
            if not os.path.exists(backup):
                shutil.copy2(self.nui_path, backup)
                print('  original kept as', os.path.normpath(backup))
            tmp = self.nui_path + '.new'
            open(tmp, 'wb').write(self.nui.encode('cp949'))
            os.replace(tmp, self.nui_path)
            print(f'  {os.path.relpath(self.nui_path, ROOT)} written')
        if self.add_pieces:
            backup = backup_path(self.tex_path)
            if not os.path.exists(backup):
                shutil.copy2(self.tex_path, backup)
            files = list(self.tex_files)
            idx = {n.lower(): i for i, (n, _) in enumerate(files)}
            for name, data in self.add_pieces.items():
                i = idx.get('tex\\%x.ntx' % container_of(name))
                if i is None:
                    sys.exit(f'uitex.agt: no container for {name}')
                n, ntx = files[i]
                for e, off, size in entries(ntx):
                    if e.lower() == name.lower():
                        ntx = ntx[:off] + ntx[off + 72 + size:]
                        break
                entry = name.encode('latin-1')[:63].ljust(64, b'\0') + struct.pack('<II', len(data), 0) + data
                files[i] = (n, ntx + entry)
            tmp = self.tex_path + '.new'
            agt.write(tmp, self.tex_header, files)
            raw = bytearray(open(tmp, 'rb').read())
            raw[20:32] = self.tex_header[20:32]
            open(tmp, 'wb').write(bytes(raw))
            os.replace(tmp, self.tex_path)
            print(f'  {os.path.relpath(self.tex_path, ROOT)}: {len(self.add_pieces)} picture pieces added')


# ---- tracks -----------------------------------------------------------------------------------------------------

def port_tracks():
    if not os.path.isdir(DEV):
        sys.exit(f'no 2016 client at {os.path.normpath(DEV)}')
    # files
    for city, pack, folders, paths in TRACK_FILES:
        path = tpath('Data', 'World', pack + '.agt')
        have = pack_entries(path)
        prefix = next(iter(have.values())).split('\\')[0]          # the pack's own spelling of the city
        src = dev_path('Data', 'World', city)
        add = {}
        for folder in folders:
            for f in sorted(os.listdir(os.path.join(src, folder))):
                add[f'{prefix}\\{folder}\\{f}'] = open(os.path.join(src, folder, f), 'rb').read()
        for f in paths:
            add[f'{prefix}\\Path\\{f}'] = open(os.path.join(src, 'Path', f), 'rb').read()
        obj = os.path.join(src, 'Obj')
        extra = [f for f in sorted(os.listdir(obj)) if f'{prefix}\\obj\\{f}'.lower() not in have]
        for f in extra:
            add[f'{prefix}\\Obj\\{f}'] = open(os.path.join(obj, f), 'rb').read()
        print(f'{city}: {", ".join(folders)}, {len(paths)} paths, {len(extra)} Obj files')
        pack_update(path, add)
    # PVPTrackInfo
    init = tpath('DATA', T['init'])
    old = xlt_lines(read_entry(init, 'Init\\PVPTrackInfo.xlt'))
    dev = xlt_lines(open(dev_path('Data', 'Init', 'PVPTrackInfo.xlt'), 'rb').read())
    lines, n, tracks = ported_tracks(old, dev)
    data = xlt_bytes(lines)
    print(f'PVPTrackInfo.xlt: {n} rows of {len(NEW_TRACK_IDS)} tracks added, {tracks} tracks')
    pack_update(init, {'Init\\PVPTrackInfo.xlt': data})
    if T['server']:
        open(os.path.join(SERVER_DATA, 'Init', 'PVPTrackInfo.xlt'), 'wb').write(data)
        print('  server_data/Init/PVPTrackInfo.xlt written (restart the emulator)')
    # pictures
    names = set()
    for tid, idx in track_blocks(dev):
        if tid in NEW_TRACK_IDS:
            names.add(dev[idx[0]].split('\t')[31])
    ui = Interface()
    for dev_dlg, dlg in TRACK_DIALOGS.items():
        done = ui.copy_controls(dev_dlg, dlg, sorted(names))
        moved = ui.place_tracks(dlg)
        print(f'game.nui dialog {dlg}: {", ".join(done) or "nothing new"}' + (' (track pictures first)' if moved else ''))
    ui.save()


# ---- the client's car limit (exe) ------------------------------------------------------------------------------

P16_VA = 0xa1e000                     # the added section .p16 (RVA 0x61e000): tools/p16_cars.s
P16_LOAD, P16_CACHE = 0xa1e000, 0xa1e20d
P16_VSIZE = 0x2000
P16_CODE = bytes.fromhex(
    '5589e5535657ff7508b8e0978400ffd083c40489c685f67d11688c988f006a01b8302c4000ffd083c40831c0b9000400'
    '008d3de0e4a100f3abc70550e2a10000000000c70554e2a100000000006854e2a1006850e2a1006818cb8c0056b8c08e'
    '8400ffd083c41031ff3b3d54e2a1007d3b81ff000400007d33c7055ce2a10000000000685ce2a1006878b18c008d4f07'
    '5156b880908400ffd083c4108b155ce2a1008914bde0e4a10047ebbd6a0456b8508e8400ffd083c408c70558e2a10000'
    '000000a158e2a1003b0550e2a1000f8d2901000031c0b99f0000008d3d60e2a100f3abc70508e4a100000080bf6860e2'
    'a1006878b18c006a0156b880908400ffd06864e2a1006878b18c006a0256b880908400ffd06890e2a1006828b48c006a'
    '0356b880908400ffd068b0e2a10068e8858d006a0456b880908400ffd083c44068b4e2a1006828b48c006a0556b88090'
    '8400ffd0c605dbe2a100006868e2a1006828b48c006a0656b880908400ffd083c42031ff3b3d54e2a1007d4881ff0004'
    '00007d40c7055ce2a10000000000685ce2a1006878b18c008d4f075156b880908400ffd083c4108b14bde0e4a10081fa'
    '00020000730ba05ce2a1008882dce2a10047ebb08d0d60e2a100b8e0c58400ffd08b4d0c8b116860e2a100a160e2a100'
    '4850ff52046a0156b8508e8400ffd083c408ff0558e2a100e9c6feffff56b8d09a8400ffd083c4045f5e5b5dc33d2c01'
    '00007d06688f907600c33d000200007d208b54240885d27c1883fa377f135250b8e0947600ffd085c074068b4004c208'
    '0031c0c208')


def _jmp(at, to):
    return b'\xe9' + struct.pack('<i', to - (at + 5))


# (VA, original bytes, new bytes). VisualItem records 0x1ac -> 0x27c bytes (rep movs 0x6b -> 0x9f dwords), the
# Unique Id checks 300 -> 512, the loader and the default part cache getter to .p16.
EXE_PATCHES = [
    (0x7690d3, '69c0ac010000', '69c07c020000'), (0x769108, 'b96b000000', 'b99f000000'),
    (0x769113, '05ac010000', '057c020000'),       # 0x7690c0 grow
    (0x769141, '69c0ac010000', '69c07c020000'), (0x769168, 'b96b000000', 'b99f000000'),
    (0x769173, '05ac010000', '057c020000'),       # 0x769130 fit
    (0x7691c6, '69ffac010000', '69ff7c020000'), (0x7691d3, 'b96b000000', 'b99f000000'),   # 0x769190 append
    (0x769229, '69d2ac010000', '69d27c020000'), (0x76922f, '8d841054feffff', '8d841084fdffff'),   # 0x769200
    (0x769299, '69c0ac010000', '69c07c020000'), (0x76929f, '8d840154feffff', '8d840184fdffff'),
    (0x7692fe, '81c3ac010000', '81c37c020000'),
    (0x76948f, '69c9ac010000', '69c97c020000'), (0x769495, '8d840854feffff', '8d840884fdffff'),   # IsCompatible
    (0x7694a8, '81f92c010000', '81f900020000'),
    (0x7694f6, '81ff2c010000', '81ff00020000'), (0x76951a, '81c2ac010000', '81c27c020000'),       # FindDefaultPart
    (0x76952b, '69c0ac010000', '69c07c020000'),
    (0x7695c2, '69c0ac010000', '69c07c020000'),
    (0x769bd9, '81fe2c010000', '81fe00020000'),   # IsCompatible(carId, uid)
    (0x769ea5, '81c7ac010000', '81c77c020000'),   # 0x769df0 (the id map)
    (0x679b7d, '81f92c010000', '81f900020000'),   # two items fitting one car
    (0x602202, '81f92c010000', '81f900020000'),   # garage / shop checks of the current car
    (0x67dbf9, '8178042c010000', '81780400020000'),
    (0x68ed76, '8178042c010000', '81780400020000'),
    (0x769088, '3d2c0100007d23', (_jmp(0x769088, P16_CACHE) + b'\x90\x90').hex()),
    (0x84ad00, '558bec83e4', _jmp(0x84ad00, P16_LOAD).hex()),
]


def patch_exe(path):
    """Client US/DriftCityUS.exe (or the EU exe: the same program) with the car limit raised (P16 section + patches).
    -> True when changed. The first original is kept in client_backup/<name>.orig."""
    exe = bytearray(open(path, 'rb').read())
    pe = struct.unpack_from('<I', exe, 0x3c)[0]
    nsec = struct.unpack_from('<H', exe, pe + 6)[0]
    opt = struct.unpack_from('<H', exe, pe + 20)[0]
    sec = pe + 24 + opt
    names = [exe[sec + 40 * i:sec + 40 * i + 8].rstrip(b'\0') for i in range(nsec)]
    text_va = struct.unpack_from('<I', exe, sec + 12)[0] + 0x400000
    text_raw = struct.unpack_from('<I', exe, sec + 20)[0]

    def off(va):
        return va - text_va + text_raw
    done = b'.p16' in names
    for va, old, new in EXE_PATCHES:
        cur = exe[off(va):off(va) + len(bytes.fromhex(old))].hex()
        if cur != (new if done else old):
            sys.exit(f'{path}: unexpected bytes at {va:#x}: {cur} (nothing written)')
    if done:
        print(f'{os.path.basename(path)}: car limit already raised')
        return False
    backup = backup_path(path)
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print('  original kept as', os.path.normpath(backup))
    for va, old, new in EXE_PATCHES:
        n = bytes.fromhex(new)
        exe[off(va):off(va) + len(n)] = n
    # the section: header after the last one, raw data at the end of the file
    if sec + 40 * (nsec + 1) > struct.unpack_from('<I', exe, sec + 20)[0]:
        sys.exit('no room for a section header')
    raw = (len(exe) + 0x1ff) & ~0x1ff
    exe += bytes(raw - len(exe))
    data = P16_CODE + bytes((-len(P16_CODE)) % 0x200)
    rva = P16_VA - 0x400000
    struct.pack_into('<8sIIIIIIHHI', exe, sec + 40 * nsec, b'.p16', P16_VSIZE, rva, len(data), raw, 0, 0, 0, 0,
                     0xE0000060)
    exe += data
    struct.pack_into('<H', exe, pe + 6, nsec + 1)
    struct.pack_into('<I', exe, pe + 24 + 56, rva + P16_VSIZE)          # SizeOfImage
    tmp = path + '.tmp'
    open(tmp, 'wb').write(bytes(exe))
    shutil.copymode(path, tmp)
    os.replace(tmp, path)
    print(f'{os.path.basename(path)}: car limit raised (VisualItem car Unique Ids up to 511; .p16 section added)')
    return True


# ---- cars -------------------------------------------------------------------------------------------------------

UID_MAP = {300: 102, 301: 103, 302: 104, 303: 105}   # 300-303 would share bytes with the record's float (+0x1a8)
CAR_DIALOGS = {'1990000': '1800000', '2840000': '2610000', '2850000': '2620000', '2860000': '2630000'}
AERO_DIALOGS = {'2880000': '2650000'}
INIT_ENTRY = 'Init\\%s.xlt'


def dev_xlt(name):
    return xlt_lines(open(dev_path('Data', 'Init', name + '.xlt'), 'rb').read())


def cells(line):
    return line.split('\t')


def clip(text, n):
    """text cut to n bytes as the client reads it (cp949): the 2011 readers keep names in fixed buffers, e.g.
    VehicleDisplay Car Name / UI Name in 32-byte stack buffers next to the stack cookie (0x84a240: a 36-byte 2016
    name, "MITSUBISHI LANCER Evolution III 1995", stopped the client at start with __security_error_handler)."""
    b = text.encode('cp949', 'replace')
    return text if len(b) <= n else b[:n].decode('cp949', 'ignore')


NAME_BYTES = 31                       # VehicleList / VehicleUpgrade / VehicleDisplay names (32-byte buffers)
ITEM_NAME_BYTES = 34                  # VisualItem / VShopItem names: the longest the 2011 tables have


def new_cars(vl11, vl16):
    """The 2016 player cars (VehicleList Vehicle 0) whose Unique Id the 2011 table lacks: [(2016 cells, new uid)]."""
    have = {cells(l)[9] for l in vl11[4:] if len(cells(l)) > 9}
    out = []
    for l in vl16[4:]:
        f = cells(l)
        if len(f) > 9 and f[0].strip() and f[2] == '0' and f[9] not in have:
            out.append((f, UID_MAP.get(int(f[9]), int(f[9]))))
    return out


def renumber(lines, first, col=0):
    """Index column renumbered from 0 over the data lines (from line first); -> the count."""
    n = 0
    for i in range(first, len(lines)):
        f = cells(lines[i])
        if f[col].strip().isdigit():
            f[col] = str(n)
            lines[i] = '\t'.join(f)
            n += 1
    return n


def set_header(lines, row, values):
    f = cells(lines[row])
    for col, v in values.items():
        f[col] = str(v)
    lines[row] = '\t'.join(f)


def strip_ported(lines, first, key_col, keys):
    return lines[:first] + [l for l in lines[first:] if not (len(cells(l)) > key_col and cells(l)[key_col] in keys)]


def small_cars(lines):
    """VehicleList lines with column 21 "GOTCHA_SMALL" -> "SMALL" where the size (columns 24-26) is a percentage of the
    base car (column 12): the 2011 client scales a car's collision box and model from its base car only for "SMALL"
    (strcmpi at 0x4c6xxx, 0x4d2xxx, 0x4a9800; loader 0x84a4f5 keeps column 12 at +0x218); 2016 also takes
    "GOTCHA_SMALL" there (0x4b3f16 / 0x4b3f25 ...). Unchanged, the 2016 ST cars got an 80 mm box and drove through
    lamps and trees (user, 2026-10-19). PRANA ST (a real size, 4310) keeps its label. -> (lines, cars changed)."""
    out, n = [], 0
    for line in lines:
        c = cells(line)
        if len(c) > 26 and c[21] == 'GOTCHA_SMALL' and c[24].strip().isdigit() and int(c[24]) < 1000:
            c[21] = 'SMALL'
            line, n = '\t'.join(c), n + 1
        out.append(line)
    return out, n


def apply_small():
    """small_cars on the target client's Init pack (and server_data for the US run)."""
    init = tpath('DATA', T['init'])
    lines, n = small_cars(xlt_lines(read_entry(init, INIT_ENTRY % 'VehicleList')))
    if n:
        pack_update(init, {INIT_ENTRY % 'VehicleList': xlt_bytes(lines)})
    print(f'  {T["name"]}: {n} small cars labelled SMALL')
    if T['server']:
        path = os.path.join(SERVER_DATA, 'Init', 'VehicleList.xlt')
        lines, n = small_cars(xlt_lines(open(path, 'rb').read()))
        if n:
            open(path, 'wb').write(xlt_bytes(lines))
        print(f'  server_data: {n} small cars labelled SMALL (restart the emulator)')


def port_vehicle_list(vl11, cars):
    uids = {str(u) for _, u in cars}
    lines = strip_ported(vl11, 4, 9, uids)
    last = max(i for i, l in enumerate(lines) if len(cells(l)) > 9 and cells(l)[2] == '0')
    ncols = len(cells(lines[3]))
    add = []
    for f, uid in cars:
        f = f[:77] + f[78:]                       # 2016 column 77 "Color Group Name"
        f[9] = str(uid)
        for c in (3, 4, 5, 6):
            f[c] = clip(f[c], NAME_BYTES)
        add.append('\t'.join((f + [''] * ncols)[:ncols]))
    lines[last + 1:last + 1] = small_cars(add)[0]
    n = renumber(lines, 4)
    players = sum(1 for l in lines[4:] if len(cells(l)) > 9 and cells(l)[0].strip() and cells(l)[2] == '0')
    set_header(lines, 1, {1: n, 3: players})
    return lines


def port_upgrades(vu11, vu16, cars):
    old = {str(int(f[9])): str(u) for f, u in cars}
    lines = strip_ported(vu11, 3, 1, set(old.values()))
    blocks = {}
    for l in vu16[3:]:
        f = cells(l)
        if len(f) > 1 and f[0].strip().isdigit() and f[1] in old:
            blocks.setdefault(f[1], []).append(f)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    add = []
    for f0, uid in cars:
        rows = blocks.get(str(int(f0[9])), [])
        if len(rows) != 9:
            sys.exit(f'VehicleUpgrade: car {f0[9]} has {len(rows)} rows, not 9')
        for f in rows:
            f = list(f)
            f[1] = str(uid)
            for c in (2, 3, 4):
                f[c] = clip(f[c], NAME_BYTES)
            add.append('\t'.join(f))
    lines[last + 1:last + 1] = add
    set_header(lines, 1, {2: renumber(lines, 3)})   # Value, '', Cnt, BundleCnt
    return lines


def port_display(vd11, vd16, cars):
    old = {str(int(f[9])): str(u) for f, u in cars}
    lines = strip_ported(vd11, 4, 3, set(old.values()))
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    ncols = len(cells(lines[3]))
    add = []
    for l in vd16[4:]:
        f = cells(l)
        if len(f) > 3 and f[0].strip().isdigit() and f[3] in old:
            f[3] = old[f[3]]
            f[1], f[2] = clip(f[1], NAME_BYTES), clip(f[2], NAME_BYTES)
            add.append('\t'.join(f[:ncols]))
    lines[last + 1:last + 1] = add
    set_header(lines, 1, {1: renumber(lines, 4)})
    return lines


def port_tires(tl11, tl16, cars):
    have = {cells(l)[1] for l in tl11[3:] if len(cells(l)) > 1}
    need = {t.strip() for f, _ in cars for t in f[46:56] if t.strip() not in ('-1', '')}
    lines = list(tl11)
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    add = [l for l in tl16[3:] if len(cells(l)) > 7 and cells(l)[1] in need - have]
    lines[last + 1:last + 1] = add
    set_header(lines, 1, {1: renumber(lines, 3)})
    return lines, [cells(l)[7] for l in add]


def port_visuals(vi11, vi16, cars):
    """VisualItem.xlt: a car column per new car (row 2 = its Unique Id: the byte of the client's record), values from
    the 2016 table for the same item (its column found by the 2016 Unique Id in row 2); the new cars' own rows (their
    aero sets pc_XXXXs_0N, ...) added after the last row of their category. A car the 2016 table has no column for
    gets its own items and the items (nearly) every 2016 car fits (>= 90 %). -> (lines, items added, cars without a
    2016 column)."""
    bases = {f[7].lower()[:-4] for f, _ in cars}
    h16 = [cells(l) for l in vi16[:6]]
    col16 = {}                                    # 2016 Unique Id -> 2016 column
    for i in range(7, len(h16[2])):
        if h16[2][i].strip().isdigit():
            col16.setdefault(int(h16[2][i]), i)
    file16 = {h16[4][i].lower(): i for i in range(7, len(h16[4])) if h16[4][i]}
    all16 = sorted(set(col16.values()))
    rows16 = {cells(l)[3]: cells(l) for l in vi16[6:] if len(cells(l)) > 4 and cells(l)[3]}

    def value(src, car16, base):
        """The 'Exist' of a 2016 item row for a car (2016 Unique Id; base = its file without .nif)."""
        if src is None:
            return '0'
        i = col16.get(car16)
        if i is not None:
            return src[i] if i < len(src) and src[i].strip() else '0'
        if src[3].lower().rsplit('_', 1)[0] == base:
            return '1'
        ones = sum(1 for j in all16 if j < len(src) and src[j].strip() == '1')
        return '1' if ones >= 0.9 * len(all16) else '0'

    new_uids = {u for _, u in cars}
    lines = [cells(l) for l in vi11]
    # drop the columns / rows of an earlier run
    keep = [i for i, v in enumerate(lines[2]) if i < 7 or not ((v.strip().isdigit() and int(v) in new_uids)
                                                              or (not v.strip() and not lines[4][i].strip()))]
    lines = [[c for i, c in enumerate(r) if i in keep] for r in lines]
    lines = lines[:6] + [r for r in lines[6:] if not (len(r) > 3 and r[3].lower().rsplit('_', 1)[0] in bases)]
    width = len(lines[2])
    while width > 7 and all(len(r) <= width - 1 or not r[width - 1] for r in lines):
        width -= 1                                # trailing empty columns
    lines = [(r + [''] * width)[:width] for r in lines]
    # the 2011 columns -> their car in the 2016 table (by Unique Id, else by file name)
    old_cols = []
    for i in range(7, width):
        uid = int(lines[2][i]) if lines[2][i].strip().isdigit() else None
        if uid in col16:
            old_cols.append((i, uid))
        elif lines[4][i].lower() in file16:
            j = file16[lines[4][i].lower()]
            old_cols.append((i, int(h16[2][j]) if h16[2][j].strip().isdigit() else None))
    for r_i in range(6):
        for f, uid in cars:
            i = col16.get(int(f[9]))
            if r_i == 2:
                v = str(uid)
            elif r_i == 5:
                v = 'Exist'
            elif i is not None:
                v = h16[r_i][i]
            else:
                v = {3: f[6], 4: f[7]}.get(r_i, '')
            lines[r_i].append(v)
    for r in lines[6:]:
        src = rows16.get(r[3]) if r[3] else None
        for f, uid in cars:
            r.append(value(src, int(f[9]), f[7].lower()[:-4]) if r[3] else '')
    added = []
    for item, src in rows16.items():
        if item.lower().rsplit('_', 1)[0] not in bases:
            continue
        row = [''] + list(src[1:7]) + [''] * (width - 7)
        row[5] = clip(row[5], ITEM_NAME_BYTES)
        for i, uid16 in old_cols:
            row[i] = value(src, uid16, None) if uid16 is not None else '0'
        for i in range(7, width):
            row[i] = row[i] or '0'
        for f, uid in cars:
            row.append(value(src, int(f[9]), f[7].lower()[:-4]))
        added.append(row)
    # after the category's last car-specific row (pc_NNNN...): the generic rows behind them (pc_Aeroset1, pc_Aero, ...
    # Index 0) fit every car too, and the client's FindDefaultPart (0x7694e0) takes the first row that fits as the
    # car's default part: the basic aero set is the car's body (user: new cars showed only wheels)
    for row in sorted(added, key=lambda r: (int(r[1]), int(r[2]))):
        same = [i for i, r in enumerate(lines) if len(r) > 3 and r[1] == row[1]]
        own = [i for i in same if re.match(r'pc_\d{4}', lines[i][3])]
        lines.insert((own or same)[-1] + 1, row)
    count = sum(1 for r in lines[6:] if len(r) > 4 and r[3])
    max_uid = max(int(r[4]) for r in lines[6:] if len(r) > 4 and r[4].strip().isdigit())
    ncars = len(lines[2]) - 7                    # the loader reads this many columns from column 7
    lines[1][1], lines[1][2], lines[1][3] = str(count), str(ncars), str(max_uid + 1)
    missing = [f[7] for f, _ in cars if int(f[9]) not in col16]
    return ['\t'.join(r) for r in lines], [r[3] for r in added], missing


def port_vshop(vs11, vs16, items):
    items = set(items)
    lines = strip_ported(vs11, 3, 3, items)
    add = []
    for l in vs16[3:]:
        f = cells(l)
        if len(f) > 4 and f[3] in items:
            f[4] = clip(f[4], ITEM_NAME_BYTES)
            add.append('\t'.join(f))
    last = max(i for i, l in enumerate(lines) if cells(l)[0].strip().isdigit())
    lines[last + 1:last + 1] = add
    n = renumber(lines, 3)
    uids = [int(cells(l)[2]) for l in lines[3:] if len(cells(l)) > 2 and cells(l)[2].strip().isdigit()]
    set_header(lines, 1, {1: n, 3: max(uids) + 1})
    return lines


def tdf_append(data, rows):
    """A .tdf with rows (lists of strings, the table's column count) added at the end."""
    bmp, = struct.unpack_from('<I', data, 2)
    t = data[bmp:]
    cols, n = struct.unpack_from('<II', t, 16)
    offs = list(struct.unpack_from(f'<{cols * n}I', t, 24))
    start = 24 + cols * n * 4
    if min(offs) < start:
        sys.exit('tdf: strings before the cell table')
    delta = cols * len(rows) * 4
    blob = bytearray(t[start:])
    at = {}
    new = [o + delta for o in offs]
    for r in rows:
        if len(r) != cols:
            sys.exit(f'tdf: a row of {len(r)} cells, table has {cols}')
        for v in r:
            if v not in at:
                at[v] = start + delta + len(blob)
                blob += v.encode('utf-16-le') + b'\0\0'
            new.append(at[v])
    head = bytearray(t[:24])
    struct.pack_into('<I', head, 20, n + len(rows))
    out = head + struct.pack(f'<{len(new)}I', *new) + blob
    struct.pack_into('<I', out, 12, len(out))
    return data[:bmp] + bytes(out)


def port_cars(dry=None):
    """dry: a folder to write the built tables into instead of the client / server."""
    if not os.path.isdir(DEV):
        sys.exit(f'no 2016 client at {os.path.normpath(DEV)}')
    from client_tables import Client
    sys.path.insert(0, os.path.join(HERE, '..'))
    from dcemu.native.data import read_tdf
    init = tpath('DATA', T['init'])
    t11 = {n: xlt_lines(read_entry(init, INIT_ENTRY % n)) for n in
           ('VehicleList', 'VehicleUpgrade', 'VehicleDisplay', 'TireList', 'VisualItem', 'VShopItem')}
    vanilla = backup_path(init)                                    # the cars are chosen against the original table,
    base = xlt_lines(read_entry(vanilla, INIT_ENTRY % 'VehicleList')) if os.path.exists(vanilla) else t11['VehicleList']
    cars = new_cars(base, dev_xlt('VehicleList'))                  # so a run again rebuilds all of them
    print(f'{len(cars)} new player cars (Unique Ids {min(u for _, u in cars)}-{max(u for _, u in cars)}; '
          f'renumbered {UID_MAP})')
    tables = {}
    tables['VehicleList'] = port_vehicle_list(t11['VehicleList'], cars)
    tables['VehicleUpgrade'] = port_upgrades(t11['VehicleUpgrade'], dev_xlt('VehicleUpgrade'), cars)
    tables['VehicleDisplay'] = port_display(t11['VehicleDisplay'], dev_xlt('VehicleDisplay'), cars)
    tables['TireList'], tire_files = port_tires(t11['TireList'], dev_xlt('TireList'), cars)
    tables['VisualItem'], aero, missing = port_visuals(t11['VisualItem'], dev_xlt('VisualItem'), cars)
    if missing:
        print('  no 2016 VisualItem column for', ', '.join(missing))
    tables['VShopItem'] = port_vshop(t11['VShopItem'], dev_xlt('VShopItem'), aero)
    print(f'  tables: {len(cars)} VehicleList rows, {9 * len(cars)} VehicleUpgrade rows, {len(tire_files)} tires, '
          f'{len(aero)} aero items')
    # car keys (UseItemClient.tdf: where the client reads it from, a patch pack)
    if T['keys']:
        pack_rel, entry = T['keys']
        key_data = read_entry(os.path.join(T['root'], pack_rel), entry)
    else:
        c = Client(T['root'])
        path = c.find('UseItemClient.tdf')
        pack_rel = c.files[path][0]
        entry = c.files[path][2][0]
        key_data = c.read('UseItemClient.tdf')
    have_keys = {r[0] for r in _tdf_rows(key_data)}
    dev_keys = {r[0]: r for r in read_tdf(dev_path('Data', 'World', 'Data', 'UseItemClient.tdf'))}
    keys = []
    for f, uid in cars:
        k = f[7][:-4]
        if k in dev_keys and k not in have_keys:
            r = list(dev_keys[k])
            r[9] = str(uid)
            keys.append(r)
    key_data = tdf_append(key_data, keys) if keys else key_data
    print(f'  {len(keys)} car keys -> {pack_rel} {entry}')
    # files: models, textures, neon, tires
    vdir = dev_path('Data', 'vehicle')
    index = {}
    for root, _, fs in os.walk(vdir):
        for f in fs:
            index.setdefault(f.lower(), os.path.join(root, f))
    pack = tpath('Data', 'vehicles.agt')
    have = {n.split('\\')[-1] for n in pack_entries(pack)}
    want = set()
    for f, _ in cars:
        base = f[7].lower()[:-4]
        want |= {n for n in index if base in n}
    want |= {t.lower() for t in tire_files} | {t.lower()[:-4] + '.dds' for t in tire_files}
    for n in list(want):                          # textures the models name
        if n.endswith('.nif') and n in index:
            for r in re.findall(rb'[\w\-.]+\.dds', open(index[n], 'rb').read(), re.I):
                want.add(r.decode('latin-1').lower())
    add = {}
    for n in sorted(want):
        if n in index and n not in have:
            rel = os.path.relpath(index[n], dev_path('Data')).replace(os.sep, '\\')
            add[rel] = open(index[n], 'rb').read()
    print(f'  {len(add)} vehicle files ({sum(map(len, add.values())) // 1000000} MB)')
    # interface: car pictures and aero icons
    ui = Interface()
    names = sorted({f[7][:-4] for f, _ in cars})
    for dev_dlg, dlg in CAR_DIALOGS.items():
        print(f'  game.nui dialog {dlg}: {len(ui.copy_controls(dev_dlg, dlg, names))} car pictures')
    for dev_dlg, dlg in AERO_DIALOGS.items():
        print(f'  game.nui dialog {dlg}: {len(ui.copy_controls(dev_dlg, dlg, sorted(aero)))} aero icons')
    if dry:
        os.makedirs(dry, exist_ok=True)
        for n, lines in tables.items():
            open(os.path.join(dry, n + '.xlt'), 'wb').write(xlt_bytes(lines))
        open(os.path.join(dry, 'UseItemClient.tdf'), 'wb').write(key_data)
        open(os.path.join(dry, 'files.txt'), 'w').write('\n'.join(sorted(add)))
        open(os.path.join(dry, 'game.nui'), 'wb').write(ui.nui.encode('cp949'))
        print('  dry run: tables in', dry, '; pieces', len(ui.add_pieces))
        return
    # write
    patch_exe(tpath(T['exe']))
    if add:
        pack_update(pack, add)
    pack_update(init, {INIT_ENTRY % n: xlt_bytes(lines) for n, lines in tables.items()})
    pack_update(os.path.join(T['root'], pack_rel), {entry: key_data})
    ui.save()
    # engine sounds (loose files)
    adir, out_dir = dev_path('Data', 'audio', 'engine'), tpath('DATA', 'audio', 'engine')
    sounds = 0
    for f, uid in cars:
        for kind in ('idle', 'mid'):
            src = os.path.join(adir, f'{kind}{int(f[9])}.wav')
            dst = os.path.join(out_dir, f'{kind}{uid}.wav')
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copyfile(src, dst)
                sounds += 1
    print(f'  {sounds} engine sounds -> {os.path.relpath(out_dir, ROOT)}')
    if not T['server']:
        return print(f'  {T["name"]}: done (the server tables are the US run\'s)')
    for n, lines in tables.items():
        open(os.path.join(SERVER_DATA, 'Init', n + '.xlt'), 'wb').write(xlt_bytes(lines))
    open(os.path.join(SERVER_DATA, 'tables', 'UseItemClient.tdf'), 'wb').write(key_data)
    print('  server_data: the tables written (restart the emulator)')


def cars_ported(client=CLIENT):
    """True when the client's VehicleList (Data_US/Init_us.agt) has car Unique Ids the unpatched exe cannot hold."""
    data = read_entry(os.path.join(client, 'Data_US', 'Init_us.agt'), INIT_ENTRY % 'VehicleList')
    return any(len(cells(l)) > 9 and cells(l)[2] == '0' and cells(l)[9].strip().isdigit() and int(cells(l)[9]) >= 300
               for l in xlt_lines(data)[4:]) if data else False


def _tdf_rows(data):
    bmp, = struct.unpack_from('<I', data, 2)
    t = data[bmp:]
    cols, n = struct.unpack_from('<II', t, 16)
    offs = struct.unpack_from(f'<{cols * n}I', t, 24)

    def s(o):
        e = t.index(b'\0\0', o)
        while (e - o) % 2:
            e = t.index(b'\0\0', e + 1)
        return t[o:e].decode('utf-16-le')
    return [[s(offs[r * cols + c]) for c in range(cols)] for r in range(n)]


def reset():
    """The packs this tool changed back to their first originals (Init_us.agt.orig is the vanilla pack: rerun
    tools/shop_rows.py apply afterwards)."""
    paths = [tpath('Data', 'World', p + '.agt') for _, p, _, _ in TRACK_FILES]
    paths += [tpath('DATA', T['init']), tpath('DATA', 'gameui', 'game.nui'), tpath('Data', 'vehicles.agt'), tpath(T['exe'])]
    for path in paths:
        b = backup_path(path)
        if os.path.exists(b):
            shutil.copy2(b, path)
            print('restored', os.path.relpath(path, ROOT))
    print('uitex.agt: run tools/semi_tooltips.py / ui_texture.py reset as needed (the added pieces are harmless)')


def port_tire_icons():
    """The icons of the tires `cars` added to TireList (user, 2026-10-19: the new wheels showed in the shop without
    icons and buying one crashed the client). A Tire Wheel item (i_g_tire_*) lists the TireList rows with Listing 1
    and shows each by its UIIconID (GTire_PlyNNNN_1), a control of game.nui dialog 2650000 like the drift shop icons
    (GTire_PlyNNNN); `cars` copied only the aero icons from the 2016 dialog 2880000. Only tires the 2011 TireList
    lacks; the 2016 client has no icon for PANZER / PIETAS / AQUA / ACROBAT (Listing 0, never listed)."""
    init = tpath('DATA', T['init'])
    orig = read_entry(backup_path(init), INIT_ENTRY % 'TireList')
    cur = read_entry(init, INIT_ENTRY % 'TireList')
    old = {cells(l)[1] for l in xlt_lines(orig)[3:] if len(cells(l)) > 1}
    names = set()
    for l in xlt_lines(cur)[3:]:
        c = cells(l)
        if len(c) > 10 and c[1] not in old and c[10].strip():
            icon = c[10].strip()
            names |= {icon, icon[:-2] if icon.endswith('_1') else icon}
    ui = Interface()
    done = ui.copy_controls('2880000', '2650000', sorted(names))
    print(f'  game.nui dialog 2650000: {len(done)} tire icons ({", ".join(done) or "nothing new"})')
    if getattr(ui, 'skipped', None):
        print('  no picture for', ', '.join(ui.skipped))
    ui.save()


def main():
    global T
    if len(sys.argv) > 1 and sys.argv[1] in TARGETS:
        T = TARGETS[sys.argv.pop(1)]
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'tracks':
        return port_tracks()
    if cmd == 'cars':
        return port_cars(sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != '' else None)
    if cmd == 'exe':
        return patch_exe(sys.argv[2] if len(sys.argv) > 2 else tpath(T['exe']))
    if cmd == 'small':
        return apply_small()
    if cmd == 'tires':
        return port_tire_icons()
    if cmd == 'reset':
        return reset()
    sys.exit(__doc__)


if __name__ == '__main__':
    main()
