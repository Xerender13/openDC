"""Read-only car-table inventory of the Origin (Skid Rush) client packs.

python -m tools.reorigin.cars_inventory --client '~/Drift City Origin/Client' --out DIR

Reads the NayaPack (.agt) packs with agt.ORIGIN_KEY, lists them, extracts the newest
version of the car tables (later patches override earlier patches and the base packs),
compares them with Emulator/server_data_2016/Init, and writes report.txt and
missing_cars.tsv into --out.  Writes nothing outside --out, never launches or modifies
the client, and never allocates a whole pack: indexing and extraction are streamed and
entry headers are bounds-checked before any length from them is used.
"""
import argparse
from collections import Counter
import re
import struct
import zlib
from pathlib import Path

from tools import agt, port2016

KEY = agt.ORIGIN_KEY
MAX_ENTRIES = 200_000          # the largest Origin pack holds 4122 entries
MAX_NAME = 1024
MAX_ENTRY_BYTES = 512 * 1024 * 1024
MAX_CHUNKS = 100_000

ROOT = Path(__file__).resolve().parents[2]          # Emulator/
REF_DIR = ROOT / 'server_data_2016' / 'Init'
ASSET_ROOTS = ('vehicle\\player\\', 'vehicle\\texture\\', 'vehicle\\neon\\')

TABLES = ('VehicleList.xlt', 'VehicleUpgrade.xlt', 'VehicleDisplay.xlt', 'VisualItem.xlt',
          'VShopItem.xlt', 'TireList.xlt', 'UseItemClient.tdf', 'ItemClient.tdf')


def xor_at(buf, start):
    """buf XORed with ORIGIN_KEY at absolute pack offset start (same scheme as agt.xor_range)."""
    n, k = len(buf), len(KEY)
    if not n:
        return b''
    ks = (KEY[start % k:] + KEY * (n // k + 2))[:n]
    return (int.from_bytes(buf, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little')


def index_pack(path):
    """Streamed index: [(name, header_offset, chunk_count, data_length)]. Bounded reads only."""
    size = path.stat().st_size
    with path.open('rb') as f:
        head = f.read(32)
        if len(head) < 32 or head[:8] != b'NayaPack':
            raise ValueError(f'{path}: not a NayaPack file')
        count = struct.unpack_from('<i', head, 16)[0]
        if not 0 <= count <= MAX_ENTRIES:
            raise ValueError(f'{path}: implausible entry count {count} (wrong key or damaged pack)')
        entries, pos = [], 32
        for i in range(count):
            if pos + 16 > size:
                raise ValueError(f'{path}: entry {i} header past end of file at {pos:#x}')
            f.seek(pos)
            hp, cc, dlen, plen = struct.unpack('<4i', xor_at(f.read(16), pos))
            if not (0 < plen <= MAX_NAME and 32 <= hp < size and 0 <= cc <= MAX_CHUNKS
                    and 0 <= dlen < MAX_ENTRY_BYTES and hp + 2 * cc <= size):
                raise ValueError(f'{path}: implausible entry header {i} at {pos:#x} '
                                 f'(hp={hp} chunks={cc} len={dlen} name={plen}; wrong key?)')
            name_at = pos + 16
            if name_at + plen > size:
                raise ValueError(f'{path}: entry {i} name past end of file at {name_at:#x}')
            f.seek(name_at)
            name = xor_at(f.read(plen), name_at).decode('latin-1')
            pos = name_at + plen
            entries.append((name, hp, cc, dlen))
    return size, entries


def probe_variant(path):
    """PatchMod.* files use a shorter record (u32 offset + name, no chunk table/size).

    Returns (count, note) so the pack is still listed; its payload is not readable with the
    standard index and is never needed for the tables.  Bounded reads only.
    """
    size = path.stat().st_size
    with path.open('rb') as f:
        head = f.read(32)
        if len(head) < 32 or head[:8] != b'NayaPack':
            return None
        count = struct.unpack_from('<i', head, 16)[0]
        if not 0 <= count <= MAX_ENTRIES:
            return None
        if count == 0:
            return 0, 'NayaPack header with 0 entries'
        f.seek(32)
        tail = xor_at(f.read(min(size - 32, 256)), 32)
    text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in tail)
    return count, ('non-standard record layout (u32 offset + name, no chunk table/size); '
                   f'{size} bytes, decoded head {text[:110]!r}')


def read_entry(path, entry):
    """Streamed agt.extract for one indexed entry."""
    name, hp, cc, dlen = entry
    with path.open('rb') as f:
        f.seek(hp)
        lengths = struct.unpack(f'<{cc}H', xor_at(f.read(2 * cc), hp))
        blob_at = hp + 2 * cc
        total = sum(lengths)
        if blob_at + total > path.stat().st_size:
            raise ValueError(f'{path}: {name}: chunk table past end of file')
        f.seek(blob_at)
        blob = xor_at(f.read(total), blob_at)
    data, q = bytearray(), 0
    for length in lengths:
        data += zlib.decompressobj().decompress(blob[q:q + length])
        q += length
    if len(data) != dlen:
        raise ValueError(f'{path}: {name}: expected {dlen} bytes, got {len(data)}')
    return bytes(data)


def norm(name):
    """Override key: case-folded path without a leading 'Data\\' and with '/' -> '\\'."""
    n = name.replace('/', '\\')
    while n.lower().startswith('data\\'):
        n = n[5:]
    return n.lower()


def sources(client):
    """(rank, path): base packs first, then patch.000..NNN ascending, then PatchMod files."""
    found = [(0, p) for p in sorted(client.rglob('*.agt'))]
    for p in sorted((client / 'Patch').iterdir()):
        m = re.fullmatch(r'patch\.(\d+)', p.name, re.I)
        if m:
            found.append((1 + int(m.group(1)), p))
        elif p.name.lower().startswith('patchmod'):
            found.append((10 ** 6, p))
    found.sort(key=lambda rp: rp[0])
    return found


def scan(client):
    packs, effective = [], {}
    for rank, path in sources(client):
        try:
            size, entries = index_pack(path)
            note = ''
        except ValueError:
            hit = probe_variant(path) if path.name.lower().startswith('patchmod') else None
            if hit is None:
                raise
            size = path.stat().st_size
            count, note = hit
            entries = []
        else:
            count = len(entries)
        packs.append({'rank': rank, 'path': path, 'size': size, 'count': count, 'note': note})
        for e in entries:
            key = norm(e[0])
            effective.pop(key, None)      # newest effective definition, including duplicates
            effective[key] = (rank, path, e)
    return packs, effective


def pick_table(effective, basename):
    hits = [v for k, v in effective.items() if k.rsplit('\\', 1)[-1] == basename.lower()]
    if not hits:
        return None
    return max(hits, key=lambda v: (v[0], v[2][0]))


def out_path_for(name):
    n = name.replace('/', '\\')
    if n.lower().startswith('data\\'):
        n = n[5:]
    return Path(*n.split('\\'))


def cells(line):
    return line.split('\t')


def header_row(lines):
    """The Drift City xlt layout has Preset/Value[/Type] rows then a names row starting 'Index'/'Idx'."""
    for i in range(2, min(len(lines), 8)):
        c = [x.strip() for x in cells(lines[i])]
        if c and c[0].lower() in ('index', 'idx'):
            return i
    return None


def data_rows(lines, hdr):
    return [cells(l) for i, l in enumerate(lines) if i > hdr and l.strip()]


def ints(values):
    good, bad = [], []
    for v in values:
        s = v.strip()
        if s.lstrip('-').isdigit():
            good.append(int(s))
        else:
            bad.append(s)
    return good, bad


def counter_diff(a, b):
    ca, cb = Counter(a), Counter(b)
    added, removed = sorted((cb - ca).elements()), sorted((ca - cb).elements())
    return added, removed


def fmt_names(names):
    if not names:
        return '(none)'
    counted = Counter(names)
    return ', '.join(f'{n or "<empty>"}' + (f' x{c}' if c > 1 else '') for n, c in sorted(counted.items()))


def compare_simple(title, tname, origin_lines, ref_lines):
    """Column names + row counts for the tables that have a real header row."""
    out = [f'{title} ({tname})']
    ho, hr = header_row(origin_lines), header_row(ref_lines)
    if ho is None or hr is None:
        out.append(f'  header row not found (origin={ho}, 2016={hr}); '
                   f'lines {len(origin_lines)} vs {len(ref_lines)}')
        return out
    ocols = [c.strip() for c in cells(origin_lines[ho])]
    rcols = [c.strip() for c in cells(ref_lines[hr])]
    orows, rrows = data_rows(origin_lines, ho), data_rows(ref_lines, hr)
    added, removed = counter_diff(ocols, rcols)
    out.append(f'  header row: origin line {ho + 1}, 2016 line {hr + 1}')
    out.append(f'  columns: origin {len(ocols)}, 2016 {len(rcols)}')
    out.append(f'  columns only in 2016: {fmt_names(added)}')
    out.append(f'  columns only in origin: {fmt_names(removed)}')
    out.append(f'  data rows: origin {len(orows)}, 2016 {len(rrows)} '
               f'(difference {len(orows) - len(rrows):+d})')
    return out


def compare_vehiclelist(origin_lines, ref_lines):
    out = ['VehicleList.xlt']
    ho, hr = header_row(origin_lines), header_row(ref_lines)
    ocols = [c.strip() for c in cells(origin_lines[ho])]
    rcols = [c.strip() for c in cells(ref_lines[hr])]
    orows, rrows = data_rows(origin_lines, ho), data_rows(ref_lines, hr)
    added, removed = counter_diff(ocols, rcols)
    out += [f'  header row: origin line {ho + 1}, 2016 line {hr + 1}',
            f'  columns: origin {len(ocols)}, 2016 {len(rcols)}',
            f'  columns only in 2016: {fmt_names(added)}',
            f'  columns only in origin: {fmt_names(removed)}',
            f'  data rows: origin {len(orows)}, 2016 {len(rrows)}']

    def column(header, label):
        if label not in header:
            raise SystemExit(f'VehicleList: no {label!r} column')
        return header.index(label)

    io, ir = column(ocols, 'Unique Id'), column(rcols, 'Unique Id')
    oid = [r[io].strip() for r in orows if len(r) > io]
    rid = [r[ir].strip() for r in rrows if len(r) > ir]
    oints, obad = ints(oid)
    rints, rbad = ints(rid)
    out.append(f'  Unique Id column: origin index {io}, 2016 index {ir}')
    out.append(f'  Unique Id range: origin {min(oints)}..{max(oints)} ({len(oints)} numeric, '
               f'{len(obad)} non-numeric); 2016 {min(rints)}..{max(rints)} '
               f'({len(rints)} numeric, {len(rbad)} non-numeric)')
    if obad:
        out.append(f'  non-numeric Origin Unique Ids: {fmt_names(obad)}')
    if rbad:
        out.append(f'  non-numeric 2016 Unique Ids: {fmt_names(rbad)}')
    out.append(f'  distinct Unique Ids: origin {len(set(oid))}, 2016 {len(set(rid))}; '
               f'duplicates in origin: {len(oid) - len(set(oid))}')

    tset = set(rid)
    missing = [r for r in orows if len(r) > io and r[io].strip() not in tset]
    extra = sorted(set(rid) - set(oid), key=lambda s: int(s) if s.lstrip('-').isdigit() else 0)
    out.append(f'  Origin rows whose Unique Id is absent from 2016: {len(missing)}')
    out.append(f'  2016 Unique Ids absent from Origin: {len(extra)}')

    desc_col = ocols.index('Desc') if 'Desc' in ocols else None
    if desc_col is not None:
        out.append(f'  vehicle-type column: {ocols[desc_col]!r} (origin column {desc_col + 1})')
        out.append(f'  Origin values of {ocols[desc_col]!r}: '
                   f'{fmt_names([r[desc_col].strip() for r in orows if len(r) > desc_col])}')
        out.append('  missing cars by that column: '
                   f'{fmt_names([r[desc_col].strip() for r in missing
                                 if len(r) > desc_col])}')
        kinds = Counter(r[desc_col].strip() for r in missing if len(r) > desc_col)
        players = sum(v for k, v in kinds.items() if k in ('PlayerCar', 'Player'))
        traffic = sum(v for k, v in kinds.items() if k in ('Traffic', 'NPC'))
        out.append(f'  of the missing: player cars {players}, traffic/AI {traffic}, '
                   f'other {len(missing) - players - traffic}')
    return out, missing, ocols


def compare_visualitem(origin_lines, ref_lines):
    """VisualItem is transposed: rows are items, columns are cars; row 2 holds the car Unique Ids."""
    out = ['VisualItem.xlt (transposed: rows are items/attributes, columns are cars)']
    ocols, rcols = len(cells(origin_lines[0])), len(cells(ref_lines[0]))
    orows = [cells(l) for l in origin_lines]
    rrows = [cells(l) for l in ref_lines]
    out.append(f'  rows: origin {len(orows)}, 2016 {len(rrows)}; '
               f'columns: origin {ocols}, 2016 {rcols}')

    def labels(rows, limit=5):
        return [f'row {i + 1}: col0={rows[i][0]!r} col5={rows[i][5]!r}'
                for i in range(min(limit, len(rows)))]

    for line in labels(orows):
        out.append(f'  origin   {line}')
    for line in labels(rrows):
        out.append(f'  2016     {line}')

    def car_columns(rows):
        if len(rows) < 3:
            return 0, 0, None
        r = [c.strip() for c in rows[2]]
        nums = [int(c) for c in r if c.lstrip('-').isdigit()]
        first = next((i for i, c in enumerate(r) if c.lstrip('-').isdigit()), None)
        return len(nums), (max(nums) if nums else 0), first

    ocount, omax, ofirst = car_columns(orows)
    rcount, rmax, rfirst = car_columns(rrows)
    out.append(f'  car Unique Id columns in row 2: origin {ocount} (first at column '
               f'{ofirst + 1 if ofirst is not None else "-"}, largest {omax}); '
               f'2016 {rcount} (first at column {rfirst + 1 if rfirst is not None else "-"}, '
               f'largest {rmax})')

    onames = [r[5].strip().strip('"') for r in orows[6:] if len(r) > 5 and r[5].strip()]
    rnames = [r[5].strip().strip('"') for r in rrows[6:] if len(r) > 5 and r[5].strip()]
    out.append(f'  item rows (non-empty col5 after row 6): origin {len(onames)}, 2016 {len(rnames)}')
    out.append(f'  distinct item names: origin {len(set(onames))}, 2016 {len(set(rnames))}')
    added, removed = counter_diff(onames, rnames)
    out.append(f'  item names only in 2016: {len(added)}; only in origin: {len(removed)}')
    if removed:
        out.append(f'    e.g. only in origin: {", ".join(sorted(set(removed))[:15])}')
    if added:
        out.append(f'    e.g. only in 2016: {", ".join(sorted(set(added))[:15])}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--client', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    client, outdir = args.client.resolve(), args.out.resolve()
    if not (client / 'Data').is_dir():
        raise SystemExit(f'{client}: no Data directory; is this the Origin client root?')

    print('indexing packs ...', flush=True)
    packs, effective = scan(client)

    report = ['Origin client pack inventory (read-only)', f'client: {client}',
              f'key: agt.ORIGIN_KEY; entry index streamed and bounds-checked', '',
              'PACKS (rank order; higher rank overrides lower on the same path)', '']
    for pack in packs:
        rel = pack['path'].relative_to(client).as_posix()
        report.append(f'{rel}\t{pack["size"]}\t{pack["count"]}\trank {pack["rank"]}'
                      + (f'\t{pack["note"]}' if pack['note'] else ''))
        print(f'  {rel}: {pack["count"]} entries, {pack["size"]} bytes', flush=True)
    report.append(f'TOTAL {len(packs)} pack files, {sum(p["count"] for p in packs)} entries')
    report.append(f'effective (deduplicated) entries: {len(effective)}')

    # ---- 2. extract the newest table versions ------------------------------------------------
    (outdir / 'tables').mkdir(parents=True, exist_ok=True)
    report += ['', 'EXTRACTED TABLES (newest source wins)', '']
    extracted = {}
    print('\nextracting tables ...', flush=True)
    for name in TABLES:
        hit = pick_table(effective, name)
        if hit is None:
            report.append(f'{name}\tMISSING in every pack')
            print(f'  {name}: MISSING', flush=True)
            continue
        rank, path, entry = hit
        data = read_entry(path, entry)
        rel = out_path_for(entry[0])
        dst = outdir / 'tables' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        extracted[name] = (data, path.relative_to(client).as_posix(), entry[0])
        report.append(f'{name}\t<- {path.relative_to(client).as_posix()} '
                      f'(entry {entry[0]}, {len(data)} bytes) -> tables/{rel.as_posix()}')
        print(f'  {name} <- {path.relative_to(client).as_posix()} '
              f'({entry[0]}, {len(data)} bytes)', flush=True)

    # ---- 3. comparisons ----------------------------------------------------------------------
    def load(name):
        data, src, _ = extracted[name]
        if name.lower().endswith('.xlt'):
            return port2016.xlt_lines(data)
        return None

    report += ['', 'COMPARISON WITH server_data_2016/Init', '']
    missing_cars, vlist_header = [], []

    for name in ('VehicleList.xlt', 'VehicleUpgrade.xlt', 'VehicleDisplay.xlt',
                 'VisualItem.xlt', 'VShopItem.xlt', 'TireList.xlt'):
        ref_path = REF_DIR / name
        if name not in extracted:
            report.append(f'{name}: not in the Origin client')
            continue
        if not ref_path.exists():
            report.append(f'{name}: no 2016 reference at {ref_path}')
            continue
        olines = load(name)
        rlines = port2016.xlt_lines(ref_path.read_bytes())
        if name == 'VisualItem.xlt':
            report += compare_visualitem(olines, rlines)
        elif name == 'VehicleList.xlt':
            sec, missing_cars, vlist_header = compare_vehiclelist(olines, rlines)
            report += sec
        else:
            report += compare_simple('Comparison', name, olines, rlines)
        report.append('')

    # .tdf tables: shape only (no 2016 xlt counterpart is asked for)
    report += ['TDF TABLES (shape of the extracted files)', '']
    for name in ('ItemClient.tdf', 'UseItemClient.tdf'):
        if name not in extracted:
            report.append(f'{name}: not in the Origin client')
            continue
        data, src, entry = extracted[name]
        try:
            rows = port2016._tdf_rows(data)
            shape = f'{len(rows)} rows x {len(rows[0]) if rows else 0} columns'
        except Exception as exc:                          # noqa: BLE001 - report, do not guess
            shape = f'not parsed: {exc}'
        report.append(f'{name}\t{src}\t{len(data)} bytes\t{shape}')

    # ---- 3b. the missing cars, with their name columns ---------------------------------------
    missing_table = []
    if vlist_header and missing_cars:
        io = vlist_header.index('Unique Id')
        icol = {label: vlist_header.index(label) for label in
                ('Desc', 'Maker', 'Car Name', 'UI Name', 'File Name') if label in vlist_header}

        def get(row, label):
            i = icol.get(label)
            return row[i].strip() if i is not None and len(row) > i else ''

        for r in missing_cars:
            missing_table.append({'Unique Id': r[io].strip(),
                                  **{l: get(r, l) for l in
                                     ('Desc', 'Maker', 'Car Name', 'UI Name', 'File Name')}})
        missing_table.sort(key=lambda d: int(d['Unique Id']) if d['Unique Id'].isdigit() else 0)
        report += ['', 'ORIGIN CARS WHOSE UNIQUE ID IS ABSENT FROM THE 2016 VEHICLELIST', '',
                   'Unique Id\tDesc\tMaker\tCar Name\tUI Name\tFile Name']
        for row in missing_table:
            report.append('\t'.join(row[k] for k in
                                    ('Unique Id', 'Desc', 'Maker', 'Car Name', 'UI Name',
                                     'File Name')))

    # ---- 4. asset files for the missing cars -------------------------------------------------
    assets = [(k, v[2][0], v[2][3]) for k, v in effective.items()
              if k.startswith(ASSET_ROOTS)]
    report += ['', 'VEHICLE, TEXTURE AND NEON FILES OF THE MISSING CARS', '']
    report.append(f'searched effective entries under {", ".join(ASSET_ROOTS)} '
                  f'in the base vehicles.agt and the patches: {len(assets)} files')
    report.append('a file "carries" a model name when its file name contains that name and the '
                  'characters on both sides are not alphanumeric (so pc_0000c does not match '
                  'pc_0000c2, but pc_0000c_s.nif and neon_pc_0000c.nif do); one line per '
                  'effective file, so an overridden duplicate is counted once')

    def carries(basename, stem):
        b, s, i = basename.lower(), stem.lower(), 0
        while True:
            i = b.find(s, i)
            if i < 0:
                return False
            before = b[i - 1] if i else ''
            after = b[i + len(s)] if i + len(s) < len(b) else ''
            if not before.isalnum() and not after.isalnum():
                return True
            i += 1

    for row in missing_table:
        fname = row['File Name']
        stem = fname.rsplit('.', 1)[0] if fname else ''
        hits = [size for _, n, size in assets
                if stem and carries(n.rsplit('\\', 1)[-1], stem)]
        row['files'], row['bytes'] = len(hits), sum(hits)

    report.append('Unique Id\tfiles\tbytes')
    for row in missing_table:
        report.append(f'{row["Unique Id"]}\t{row["files"]}\t{row["bytes"]}')

    if missing_table:
        report.append(f'missing cars with no matching file: '
                      f'{sum(1 for row in missing_table if row["files"] == 0)}')
        tsv = ['Unique Id\tDesc\tMaker\tCar Name\tUI Name\tFile Name\tfiles\tbytes']
        for row in missing_table:
            tsv.append('\t'.join(str(row[k]) for k in
                                 ('Unique Id', 'Desc', 'Maker', 'Car Name', 'UI Name',
                                  'File Name', 'files', 'bytes')))
        (outdir / 'missing_cars.tsv').write_text('\n'.join(tsv) + '\n')
        total_files = sum(row['files'] for row in missing_table)
        report.append(f'missing cars: {len(missing_table)}; matching asset files: {total_files}; '
                      f'total size: {sum(row["bytes"] for row in missing_table)} bytes')
        print(f'\n{len(missing_table)} missing cars, {total_files} matching asset files',
              flush=True)

    report += ['', 'NOTES', '',
               'Column meanings are not inferred: labels quoted above are the table cells.',
               'Row counts skip blank lines; the 2016 xlt files use quoted cells that contain '
               'CRLF, which the line splitter used by both tools counts as extra rows.',
               'File offsets and sizes come from the pack index; no client file was modified.']

    (outdir / 'report.txt').write_text('\n'.join(report) + '\n')
    print(f'\nreport: {outdir / "report.txt"}', flush=True)
    print(f'missing cars: {outdir / "missing_cars.tsv"}', flush=True)


if __name__ == '__main__':
    main()
