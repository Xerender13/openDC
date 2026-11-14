"""Build the EU copies of the US client's rule tables, plus the manifest the launcher swaps them by.

The US client can be played with the EU rules (user, 2026-11-14: one US client for both rule sets, the EU client
retired; EU = V-grade parts, battle zone by car grade, channel battle by car grade). The server learns the rules
from the nation message 0x7cf (dcemu/native/nation.py, Launcher/eurules.go); what the client itself checks is in
its own tables, so it gets EU copies of them:
  ItemClient.tdf      column 7 = 0 and column 8 = the V grade (the tooltip's "Required Grade"): the same rule as
                      tools/eu_client.py grades, dcemu.native.data.part_grade_rule(row 0 kind, row 6 grade, row 7
                      level, part_tiers(rows)); rows whose rule gives 0 stay as they are
  GlobalContent.xlt   the US column Value_US only (key in column 3, header in line index 2): the battle zone
                      sections by car grade from emulator.ini [battlezone] eu.section.11 (Newbie) and .12 (Pro)
                      -> MinBattleNEWBIEGrade / MaxBattleNEWBIEGrade / MinBattlePROGrade / MaxBattlePROGrade and
                      levels 1..1000 (no level limits, as the EU client's own table); the Pro EXP tiers from dcemu.native.game.rooms.PRO_TIERS_EU
                      -> MinBattle4XGrade11New ... MinBattle16XLevel11New; the channel battle's minimum grades from
                      [cbattle] eu.main / eu.semi.1-10 -> MinChBattleGrade / MinSemi<N>ChBattleGrade (0 = no line)
  GlobalText.xlt      the US English column (Value_US): keys 11411 (the Semi-channels' rules) and 11409 (their tax),
                      the texts tools/eu_client.py set_cbattle builds for EU_eng from the same eu.semi lines

The files are found with tools/client_tables.py (the archives, loose tables and patch packs -> the effective table),
so the same command builds both clients; the packs client_tables does not index are searched for the tables as well
(2016 Data/Localize.agt holds both Localize tables, and the engine asks the packs before a loose file):
  2011 "Client US":        Patch/Patch.003 (ItemClient), Patch/Patch.000 (GlobalContent), Patch/Patch.006
                           (GlobalText)
  2016 "DriftCity Dev Ed": Data/World/data.agt (ItemClient), Data/Localize.agt (GlobalContent, GlobalText)

For each source file X (relative to the client root) this writes X.eu next to it (X.eu.new, then os.replace) and
never changes X. A pack is rebuilt once for all its changed tables, with its header bytes 20-31 kept (agt.write
zeroes them; without them other players' car thumbnails in battle zone rooms vanished, user 2026-10-13,
tools/global_content.py). A loose table is written out as a whole file.

Swap protocol (the launcher, Launcher/eurules.go): EU mode renames X -> X.us and copies X.eu over X; afterwards (at
every start, after a crash, and on `remove`) X.us goes back to X. <client>/EURules.txt lists one file per line,
"<path with forward slashes>\t<sha256 of X when X.eu was made>" (lines starting with ';' are comments). The launcher
refuses a file whose current hash differs from the manifest (its tables changed since: build again), so the hash is
of X, not of X.eu. When X.us exists (a swap is in place, X is the EU copy) the copy is built from X.us and X.us is
hashed.

usage: python -m tools.eu_rules [--config emulator.ini] build  [client dir]   write the X.eu files and EURules.txt
       python -m tools.eu_rules status [client dir]    ok / stale / missing .eu for every manifest entry
       python -m tools.eu_rules remove [client dir]    X.us back as X, then the X.eu files and EURules.txt gone

The client dir defaults to ../Client US for [client] version 2011 and ../DriftCity Dev Ed for 2016 (as the config
says); an explicit dir wins. The config is Emulator/emulator.ini unless --config names another.
"""
import configparser
import hashlib
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # Emulator/
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)                           # dcemu
import agt  # noqa: E402
import client_tables  # noqa: E402
import eu_client  # noqa: E402
import global_text  # noqa: E402

CONFIG = os.path.join(ROOT, 'emulator.ini')
TABLES = ('itemclient.tdf', 'globalcontent.xlt', 'globaltext.xlt')
MANIFEST = 'EURules.txt'
COLUMN = 'Value_US'                                # the US English column of both .xlt tables
LEVELS = (1, 1000)                                 # Min/MaxBattle*Level: no level limits (1 as the EU client)
OURS = ('.eu', '.us', '.new', '.tmp')              # the EU copies and staging files, not the client's tables
HEADER = ('; EU copies of the US client\'s rule tables, from tools/eu_rules.py build (see its module text).',
          '; path<TAB>sha256 of X when X.eu was made; the launcher swaps X -> X.us and X.eu -> X, and refuses a '
          'stale copy.')


def file_sum(path):
    """sha256 of a file, hex."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def section_rule(text):
    """emulator.ini eu.section line "name, min grade, max grade, exp" -> (min grade, max grade)."""
    f = [x.strip() for x in text.split(',')]
    if len(f) < 3:
        raise SystemExit(f'emulator.ini eu.section: "{text}" is not "name, min grade, max grade, exp"')
    return int(float(f[1])), int(float(f[2]))


def cbattle_rules(cp):
    """emulator.ini [cbattle] eu.main / eu.semi.N -> (main (max level, min grade, max grade), {N: (...)}), read as
    tools/eu_client.cbattle_rules does (the two defaults when there are no eu.semi lines)."""
    sec = cp['cbattle'] if cp.has_section('cbattle') else {}
    nums = lambda v: tuple(int(float(x)) for x in v.replace(',', ' ').split())[:3]
    main = nums(sec.get('eu.main', '0, 6, 0'))
    semi = {int(k[8:]): nums(v) for k, v in sec.items() if k.startswith('eu.semi.') and k[8:].isdigit()}
    return main, semi or {1: (0, 1, 3), 2: (0, 1, 6)}


def rules(config=CONFIG):
    """The emulator.ini settings the EU tables hold."""
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    if not cp.read(config):
        raise SystemExit(f'{config}: not found (--config names the emulator.ini)')
    bz = cp['battlezone'] if cp.has_section('battlezone') else {}
    main, semi = cbattle_rules(cp)
    return {'newbie': section_rule(bz.get('eu.section.11', 'Newbie, 1, 3, 3')),
            'pro': section_rule(bz.get('eu.section.12', 'Pro, 4, 9, 4')),
            'cbattle': (main, semi)}


def content_values(theme):
    """{GlobalContent.xlt key: Value_US value} of the EU rules."""
    from dcemu.native.game.rooms import PRO_TIERS_EU
    vals = {'MinBattleNEWBIEGrade': theme['newbie'][0], 'MaxBattleNEWBIEGrade': theme['newbie'][1],
            'MinBattleNEWBIELevel': LEVELS[0], 'MaxBattleNEWBIELevel': LEVELS[1],
            'MinBattlePROGrade': theme['pro'][0], 'MaxBattlePROGrade': theme['pro'][1],
            'MinBattlePROLevel': LEVELS[0], 'MaxBattlePROLevel': LEVELS[1]}
    for name, low, high, _exp, _lo, _hi in PRO_TIERS_EU.values():
        n = name.split()[1]                        # "4X" of "Pro 4X"
        vals[f'MinBattle{n}Grade11New'], vals[f'MaxBattle{n}Grade11New'] = low, high
        vals[f'MinBattle{n}Level11New'], vals[f'MaxBattle{n}Level11New'] = LEVELS
    main, semi = theme['cbattle']
    vals['MinChBattleGrade'] = main[1]
    for n in range(1, 11):
        vals[f'MinSemi{n}ChBattleGrade'] = semi[n][1] if n in semi else 0
    return {k: str(v) for k, v in vals.items()}


def cbattle_texts(semi):
    """GlobalText 11411 / 11409 as tools/eu_client.py set_cbattle builds them for EU_eng."""
    def limits(r):
        lvl, low, high = r
        parts = [f'V{low or 1}-V{high}' if high else (f'V{low} and up' if low else 'all vehicles'),
                 f'Lv {lvl} or lower' if lvl else 'no level limit']
        return ', '.join(parts)
    rules = '\n'.join(f'Semi-channel {n}: {limits(semi[n])}' for n in sorted(semi))
    taxes = ', '.join(str(n) for n in sorted(semi))
    return {'11411': f'"{rules}"',
            '11409': f'"Semi-channel {taxes}: Mittron charging fees <COLOR #FFC38B1A> 1 %</COLOR>\n'
                     f'<COLOR #FF407F94>The charging fees apply to all players.</COLOR>"'}


def set_column(data, column, values):
    """An .xlt table with cells changed: {key (column 3): text} in column (a header name in line index 2).
    -> (the new table, the keys not found). Every other cell stays as it is."""
    lines = data.decode('utf-16').lstrip('\ufeff').split('\r\n')
    try:
        col = lines[2].split('\t').index(column)
    except (IndexError, ValueError):
        raise SystemExit(f'{column}: no such .xlt column (header line: {lines[2][:120] if len(lines) > 2 else "?"})')
    want = dict(values)
    for i, line in enumerate(lines):
        f = line.split('\t')
        if len(f) > col and f[3] in want:
            f[col] = want.pop(f[3])
            lines[i] = '\t'.join(f)
    return b'\xff\xfe' + '\r\n'.join(lines).encode('utf-16-le'), want


def set_texts(data, column, values):
    """A GlobalText.xlt with texts changed: {key: text} in column, as tools/global_text.set_texts writes them (a
    text may hold line breaks inside its quotes: the records are split by global_text.RECORD).
    -> (the new table, the keys not found)."""
    records = global_text.RECORD.split(data.decode('utf-16').lstrip('\ufeff'))
    head = records[0].split('\r\n')
    try:
        col = head[2].split('\t').index(column)
    except (IndexError, ValueError):
        raise SystemExit(f'{column}: no such GlobalText column (header line: {head[2] if len(head) > 2 else "?"})')
    want = dict(values)
    for i, r in enumerate(records):
        f = r.split('\t')
        if i and len(f) > col and f[3] in want:
            f[col] = want.pop(f[3])
            records[i] = '\t'.join(f)
    return b'\xff\xfe' + '\r\n'.join(records).encode('utf-16-le'), want


def item_table(data):
    """ItemClient.tdf with the EU rule in it (tools/eu_client.py set_grades): -> (the new table, rows changed)."""
    from dcemu.native.data import part_grade_rule, part_tiers, read_tdf
    with tempfile.TemporaryDirectory() as tmp:          # read_tdf takes a path
        path = os.path.join(tmp, 'ItemClient.tdf')
        with open(path, 'wb') as f:
            f.write(data)
        rows = read_tdf(path)
    tiers = part_tiers(rows)
    changes = {}
    for r, row in enumerate(rows):
        if len(row) < 9:
            continue
        level = int(float(row[7])) if row[7].replace('.', '', 1).isdigit() else 0
        grade = part_grade_rule(row[0], row[6], level, tiers)
        if grade and (row[7] != '0' or row[8] != str(grade)):
            changes[(r, 7)], changes[(r, 8)] = '0', str(grade)
    return (eu_client.tdf_set(data, changes) if changes else data), len(changes) // 2


def content_table(data, theme):
    """GlobalContent.xlt with the battle zone / channel battle grades in its Value_US column."""
    new, missing = set_column(data, COLUMN, content_values(theme))
    if missing:
        raise SystemExit(f'GlobalContent.xlt: no such key: {", ".join(sorted(missing))} (nothing written)')
    return new


def text_table(data, theme):
    """GlobalText.xlt with the Semi-channel rules and tax texts in its Value_US column."""
    new, missing = set_texts(data, COLUMN, cbattle_texts(theme['cbattle'][1]))
    if missing:
        raise SystemExit(f'GlobalText.xlt: no such key: {", ".join(sorted(missing))} (nothing written)')
    return new


def change(name, data, theme):
    """One table's new bytes and a note about what changed."""
    if name == 'itemclient.tdf':
        new, n = item_table(data)
        return new, (f'ItemClient.tdf: {n} items show the required V grade (level 0)' if n
                     else 'ItemClient.tdf: grades already set')
    if name == 'globalcontent.xlt':
        return content_table(data, theme), 'GlobalContent.xlt: Value_US (battle zone / channel battle grades)'
    return text_table(data, theme), 'GlobalText.xlt: Value_US 11411 / 11409 (Semi-channel rules and tax)'


def pack_names(path, limit=4 << 20):
    """The entry names of a pack, from its table at the start (no data read). None when the file is not a NayaPack
    or its name table does not fit in limit bytes (the big asset packs hold no table we need)."""
    with open(path, 'rb') as f:
        head = f.read(limit)
    if head[:8] != b'NayaPack' or len(head) < 32:
        return None
    n, = struct.unpack_from('<i', head, 16)
    names, pos = [], 32
    for _ in range(n):
        if pos + 16 > len(head):
            return None
        hp, cc, dlen, plen = struct.unpack_from('<4i', agt.xor_range(head, pos, pos + 16))
        pos += 16
        if not (0 < plen < 1024) or pos + plen > len(head):
            return None
        names.append(agt.xor_range(head, pos, pos + plen).decode('latin-1'))
        pos += plen
    return names


def patch_folder(client):
    """The client's Patch folder (case-insensitively), or None."""
    found = next((n for n in sorted(os.listdir(client)) if n.lower() == 'patch'), None)
    return os.path.join(client, found) if found and os.path.isdir(os.path.join(client, found)) else None


def table_sources(client):
    """client_tables.Client's map, with the patch packs indexed again here: X.eu / X.us sit beside X in Patch/ and
    also start with "Patch.0", so client_tables would take them for the client's packs (and X.eu is not the
    client's table). A pack that is only there as X.us counts as X (a swap that stopped between the rename and the
    copy)."""
    c = client_tables.Client(client)
    files = {k: v for k, v in c.files.items() if not v[0].lower().endswith(OURS)}
    folder = patch_folder(client)
    for name in (sorted(os.listdir(folder)) if folder else ()):
        low = name.lower()
        if not low.startswith('patch.0') or (low.endswith(OURS) and not low.endswith('.us')):
            continue
        if low.endswith('.us'):
            if os.path.exists(os.path.join(folder, name[:-3])):
                continue                            # X is there: the .us is the EU swap's backup of it
            name = name[:-3]                        # X.us alone: its pack is X's
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            path += '.us'
        raw, entries = agt.index(path)
        for e in entries:
            files[e[0].lower()] = (os.path.relpath(os.path.join(folder, name), client), raw, e)
    return files


def extra_packs(client):
    """Packs of the client root and its sub-folders (Data/Localize.agt and the like)."""
    out = [os.path.join(client, n) for n in sorted(os.listdir(client)) if n.lower().endswith('.agt')]
    for sub in sorted(os.listdir(client)):
        folder = os.path.join(client, sub)
        if os.path.isdir(folder):
            out += [os.path.join(folder, n) for n in sorted(os.listdir(folder)) if n.lower().endswith('.agt')]
    return out


def located(client):
    """{table file name (lower): (source relative path, pack raw or None, entry)} of the effective tables: what
    tools/client_tables.Client resolves, plus the packs it does not index (2016 Data/Localize.agt) when they hold
    one; a patch pack or an archive wins over them (the engine asks the packs first, tools/pack_client.py)."""
    files = table_sources(client)
    covered = {src.lower().replace('\\', '/') for src, raw, _ in files.values() if raw is not None}
    for path in extra_packs(client):
        rel = os.path.relpath(path, client)
        if rel.replace(os.sep, '/').lower() in covered:
            continue
        names = pack_names(path)
        if not names or not {n.lower().rsplit('\\', 1)[-1] for n in names} & set(TABLES):
            continue
        prefix = os.path.dirname(rel).replace(os.sep, '\\') + '\\' if os.path.dirname(rel) else ''
        raw, entries = agt.index(path)
        for e in entries:
            files.setdefault((prefix + e[0]).lower(), (rel, raw, e))
    out = {}
    for name in TABLES:
        hits = [p for p in files if p.rsplit('\\', 1)[-1] == name]
        us = [p for p in hits if p.startswith('data_us\\')]
        for group in (us, [p for p in hits if p not in us]):
            if group:
                best = max(group, key=lambda p: list(files).index(p))
                out[name] = files[best]
                break
        else:
            raise SystemExit(f'{name}: not in {client} (tools/client_tables.py lists the tables it reads)')
    return out


def write_file(path, data, like):
    """Atomic write (path + '.new', then os.replace) with the mode of like."""
    tmp = path + '.new'
    with open(tmp, 'wb') as f:
        f.write(data)
    try:
        shutil.copymode(like, tmp)
    except OSError:
        pass
    os.replace(tmp, path)


def write_pack(path, header, files):
    """A pack with these entries, its original header bytes 20-31 put back (agt.write zeroes them;
    tools/global_content.py explains why they matter)."""
    tmp = path + '.new'
    agt.write(tmp, header, files)
    with open(tmp, 'r+b') as f:
        f.seek(20)
        f.write(header[20:32])
    os.replace(tmp, path)


def write_manifest(client, entries):
    """<client>/EURules.txt: the 2 comment lines, then one "path<TAB>sha256" line per file."""
    text = '\n'.join(HEADER) + '\n' + ''.join(f'{rel}\t{digest}\n' for rel, digest in entries)
    path = os.path.join(client, MANIFEST)
    tmp = path + '.new'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def read_manifest(client):
    """[(relative path with forward slashes, sha256)] of <client>/EURules.txt."""
    path = os.path.join(client, MANIFEST)
    if not os.path.exists(path):
        raise SystemExit(f'no {path}: run `python -m tools.eu_rules build` first')
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            rel, _, digest = line.partition('\t')
            out.append((rel.strip(), digest.strip()))
    return out


def build(client, config=CONFIG):
    """Write X.eu for every table source and <client>/EURules.txt. -> the manifest entries."""
    theme = rules(config)
    plan = located(client)
    by_source = {}
    for name, (rel, raw, entry) in plan.items():
        by_source.setdefault(rel, []).append((name, raw, entry))
    manifest = []
    for rel in sorted(by_source):
        base = os.path.join(client, rel)
        active = os.path.exists(base + '.us')
        source = base + '.us' if active else base
        if not os.path.exists(source):
            raise SystemExit(f'{rel}: neither it nor {rel}.us exists')
        notes = []
        if by_source[rel][0][1] is None:                     # a loose table: the file is the table
            name, _raw, _entry = by_source[rel][0]
            with open(source, 'rb') as f:
                data = f.read()
            new, note = change(name, data, theme)
            write_file(base + '.eu', new, source)
            notes.append(note)
        else:
            header, files = agt.read(source)
            for name, _raw, entry in by_source[rel]:
                i = next((k for k, (n, _) in enumerate(files) if n.lower() == entry[0].lower()), None)
                if i is None:
                    raise SystemExit(f'{rel}: no entry {entry[0]} any more')
                new, note = change(name, files[i][1], theme)
                if new != files[i][1]:
                    files[i] = (files[i][0], new)
                notes.append(note)
            write_pack(base + '.eu', header, files)
        manifest.append((rel.replace(os.sep, '/'), file_sum(source)))
        print(f'{rel}.eu: {"; ".join(notes)}'
              + (f'  [from {rel}.us: the EU copy is in place]' if active else ''))
    write_manifest(client, manifest)
    print(f'{MANIFEST}: {len(manifest)} files (sha256 of the US file, not of the .eu)')
    return manifest


def status(client):
    """ok / stale / missing .eu for every manifest entry, and whether the EU copy is in place (X.us)."""
    entries = read_manifest(client)
    if not entries:
        print(f'{MANIFEST}: no files (build it with tools.eu_rules build)')
        return
    for rel, digest in entries:
        path = os.path.join(client, *rel.split('/'))
        eu = path + '.eu'
        active = os.path.exists(path + '.us')
        now = path + '.us' if active else path
        if not os.path.exists(eu):
            state = 'missing .eu'
        elif not os.path.exists(now):
            state = 'missing file'
        elif file_sum(now) != digest:
            state = 'stale'
        else:
            state = 'ok'
        print(f'{state:11} {rel}{"  (EU active: X.us exists)" if active else ""}')


def remove(client):
    """X.us back as X (the US tables), then the X.eu files and EURules.txt gone."""
    entries = read_manifest(client)
    restored = 0
    for rel, _digest in entries:
        path = os.path.join(client, *rel.split('/'))
        if os.path.exists(path + '.us'):
            os.replace(path + '.us', path)
            restored += 1
            print(f'{rel}: X.us back as X')
    removed = 0
    for rel, _digest in entries:
        for path in (os.path.join(client, *rel.split('/')) + '.eu', os.path.join(client, *rel.split('/')) + '.eu.new'):
            if os.path.exists(path):
                os.remove(path)
                removed += 1
    os.remove(os.path.join(client, MANIFEST))
    print(f'{MANIFEST}: removed ({len(entries)} files, {restored} EU copies put back, {removed} .eu files deleted)')


def default_client(config=CONFIG):
    """../Client US for [client] version 2011, ../DriftCity Dev Ed for 2016."""
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    cp.read(config)
    version = cp.get('client', 'version', fallback='2011').strip()
    return os.path.join(ROOT, '..', 'DriftCity Dev Ed' if version == '2016' else 'Client US')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    config = CONFIG
    if '--config' in args:
        i = args.index('--config')
        if i + 1 >= len(args):
            raise SystemExit('--config needs an emulator.ini')
        config, args = args[i + 1], args[:i] + args[i + 2:]
    if not args or args[0] not in ('build', 'status', 'remove'):
        raise SystemExit(__doc__)
    cmd, rest = args[0], args[1:]
    if len(rest) > 1:
        raise SystemExit(f'{cmd}: at most one client dir')
    client = rest[0] if rest else default_client(config)
    if not os.path.isdir(client):
        raise SystemExit(f'{client}: no such client dir')
    if cmd == 'build':
        return build(client, config)
    return status(client) if cmd == 'status' else remove(client)


if __name__ == '__main__':
    main()
