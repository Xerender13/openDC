"""Build the client's files per setting (EU rules, km/h), plus the manifest the launcher swaps them by.

The US client can be played with the EU rules (user, 2026-11-14: one US client for both rule sets, the EU client
retired; EU = V-grade parts, battle zone by car grade, channel battle by car grade) and with km/h (user, 2026-11-14:
the client shows km/h without changing the region; Emulator/docs/neo_work/SPEED_UNITS.md). The server learns both
from the nation message 0x7cf (dcemu/native/nation.py, Launcher/eurules.go); what the client itself checks is in its
own files, so it gets copies of them:
  eu:
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
  kph (SPEED_UNITS.md section 6):
  GlobalText.xlt      Value_US 11874 "KPH", 11527 "under %d km/h", 11977 "[party option] speed +3km/h", 10403 /
                      10729 / 10730 / 10216 / 10215 (the distance and fuel texts) and 2016's 12607 "km/h"
  Assist_Client.tdf   the English text column in km/h, as tools/eu_client.py set_assist_kph (the values are km/h)
  gameui/game.nui     the ADV HUD's speed unit label T1="MPH" -> "KPH" (control ID_SPEEDMETER_ADV_SPEED: 2011
                      220057, 2016 230057)
  gameui/uitex.agt    the classic dial picture "272,267~512,512_ui_play01.dds" (MPH painted into it) replaced by
                      client_backup/tw_speedometer_406.dds, as tools/eu_client.py set_speedometer (the pack's header
                      bytes 20-31 kept)

The files are found with tools/client_tables.py (the archives, loose tables and patch packs -> the effective table),
so the same command builds both clients; the packs client_tables does not index are searched for the tables as well
(2016 Data/Localize.agt holds both Localize tables, and the engine asks the packs before a loose file):
  2011 "Client US":        Patch/Patch.003 (ItemClient), Patch/Patch.000 (GlobalContent), Patch/Patch.006
                           (GlobalText), Data_US/World.agt (Assist_Client; Patch.010's copy is the Korean base one),
                           Data_US/gameui/game.nui, Data_US/gameui/uitex.agt
  2016 "DriftCity Dev Ed": Data/World/data.agt (ItemClient, Assist_Client), Data/Localize.agt (GlobalContent,
                           GlobalText), Data_US/gameui/game.nui, Data_US/gameui/uitex.agt

For each source file X (relative to the client root) this writes one copy per non-empty subset of the settings that
change X, in the order eu, kph: X.eu, X.kph, X.eu.kph (the last has both sets of changes), each staged as X.<n>.new
and os.replace'd, and never changes X. A pack is rebuilt once per copy for all its changed tables, with its header
bytes 20-31 kept (agt.write zeroes them; without them other players' car thumbnails in battle zone rooms vanished,
user 2026-10-13, tools/global_content.py). A loose file is written out as a whole file.

Swap protocol (the launcher, Launcher/eurules.go): for the chosen settings it renames X -> X.us and copies X.<the
settings in the manifest> over X; afterwards (at every start, after a crash, and on `remove`) X.us goes back to X.
<client>/ClientModes.txt lists one file per line, "<path with forward slashes>\t<sha256 of X when the copies were
made>\t<settings that change X: eu, kph or eu,kph>" (lines starting with ';' are comments). An older EURules.txt (two
columns) means eu and is replaced by the build. The launcher refuses a file whose current hash differs from the
manifest (its tables changed since: build again), so the hash is of X, not of the copies. When X.us exists (a swap is
in place, X is a copy) the copies are built from X.us and X.us is hashed.

usage: python -m tools.eu_rules [--config emulator.ini] build  [client dir]   write the copies and ClientModes.txt
       python -m tools.eu_rules status [client dir]    ok / stale / missing for every copy of every manifest entry
       python -m tools.eu_rules remove [client dir]    X.us back as X, then the copies and the manifests gone

The client dir defaults to ../Client US for [client] version 2011 and ../DriftCity Dev Ed for 2016 (as the config
says); an explicit dir wins. The config is Emulator/emulator.ini unless --config names another.
"""
import configparser
import hashlib
import itertools
import os
import re
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
TABLES = ('itemclient.tdf', 'globalcontent.xlt', 'globaltext.xlt', 'assist_client.tdf')
MODES = {'itemclient.tdf': ('eu',), 'globalcontent.xlt': ('eu',), 'globaltext.xlt': ('eu', 'kph'),
         'assist_client.tdf': ('kph',), 'game.nui': ('kph',), 'uitex.agt': ('kph',)}
                                                  # the settings that change each table or file
OPTIONAL = ('assist_client.tdf',)                  # a client without it keeps its own texts
SETTINGS = ('eu', 'kph')                           # copy names: .eu, .kph, .eu.kph (in this order)
GUI = ('game.nui', 'uitex.agt')                    # Data_US/gameui, km/h only; uitex.agt is a pack
PACKED = ('uitex.agt',)                            # the GUI files that are NayaPacks
SPEEDO_PIECE = '272,267~512,512_ui_play01.dds'
SPEEDO_IMAGE = os.path.join(ROOT, 'client_backup', 'tw_speedometer_406.dds')
MANIFEST = 'ClientModes.txt'
OLD_MANIFEST = 'EURules.txt'                       # eu only (two columns)
COLUMN = 'Value_US'                                # the US English column of both .xlt tables
LEVELS = (1, 1000)                                 # Min/MaxBattle*Level: no level limits (1 as the EU client)
OURS = ('.eu', '.kph', '.us', '.new', '.tmp')      # the copies and staging files, not the client's own files
MPH_TEXT = re.compile(r'(\+?)\s*[0-9.]+\s*mph', re.I)
HEADER = ('; the client\'s rule tables and km/h files, from tools/eu_rules.py build (see its module text).',
          '; path<TAB>sha256 of X when the copies were made<TAB>the settings that change X; the launcher swaps '
          'X -> X.us and X.<settings> -> X, and refuses a stale copy.')


def file_sum(path):
    """sha256 of a file, hex."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def subsets(modes):
    """Every non-empty subset of these settings, in the copy-name order (eu, kph, eu.kph)."""
    return [c for n in range(1, len(modes) + 1) for c in itertools.combinations(modes, n)]


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


def eu_texts(semi):
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


def kph_texts():
    """GlobalText Value_US texts for km/h (SPEED_UNITS.md section 6), written as the file has them (10403 is one
    quoted text with the line breaks inside the quotes). 12607 is 2016 only: a key a client lacks is skipped."""
    return {'11874': 'KPH',
            '11527': 'under %d km/h',
            '11977': '[party option] speed +3km/h',
            '10403': '"Driving distance %dkm\nFuel tank %dL\nFuel consumption %.3fkm"',
            '10729': '%u km',
            '10730': '%.0f km',
            '10216': 'Distance remaining %4.1f km',
            '10215': 'Distance remaining %4d M',
            '12607': 'km/h'}


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
    rows = read_tdf_bytes(data, 'ItemClient.tdf')
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


def read_tdf_bytes(data, name):
    """dcemu.native.data.read_tdf on these bytes (it takes a path)."""
    from dcemu.native.data import read_tdf
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, name)
        with open(path, 'wb') as f:
            f.write(data)
        return read_tdf(path)


def assist_table(data):
    """Assist_Client.tdf with its English texts in km/h, as tools/eu_client.py set_assist_kph: the value (column 5)
    is km/h in both clients (column 6 says so; Speed Up 6 = 6 km/h), the English text (column 4) prints it as mph
    ("Increase speed by 3.6 mph" -> "Increase speed by 6 km/h"). a_11111-11113 ("Test Option Speed Up", value 0)
    are left as they are. -> (the new table, rows changed)."""
    rows = read_tdf_bytes(data, 'Assist_Client.tdf')
    changes = {}
    for r, row in enumerate(rows):
        if len(row) < 7 or row[6] != 'km/h' or not MPH_TEXT.search(row[4]):
            continue
        try:
            value = float(row[5])
        except ValueError:
            continue
        if not value:
            continue
        shown = f'{value:g}'
        changes[(r, 4)] = MPH_TEXT.sub(lambda m: f'{m.group(1) or " "}{shown} km/h'.replace('  ', ' '), row[4], 1)
    return (eu_client.tdf_set(data, changes) if changes else data), len(changes)


def nui_table(data):
    """game.nui with the ADV HUD's speed unit label changed: the ID_SPEEDMETER_ADV_SPEED control's T1="MPH" ->
    T1="KPH" (2011 220057, 2016 230057; SPEED_UNITS.md 6.3), and no other control. -> (the new file, a note)."""
    out = bytearray(data)
    n, pos = 0, 0
    while True:
        i = out.find(b'E="ID_SPEEDMETER_ADV_SPEED"', pos)
        if i < 0:
            break
        end = out.find(b'</CONTROL>', i)
        j = out.find(b'T1="MPH"', i, len(out) if end < 0 else end)
        if j >= 0:
            out[j:j + len(b'T1="MPH"')] = b'T1="KPH"'
            n += 1
        pos = len(out) if end < 0 else end + 1
    if not n:
        return bytes(out), 'game.nui: speed label already KPH'
    return bytes(out), 'game.nui: ID_SPEEDMETER_ADV_SPEED T1="MPH" -> "KPH"'


def dial_image():
    """The km/h dial picture (the 2008 TW client's 406 picture), or None when the backup is not there."""
    if not os.path.exists(SPEEDO_IMAGE):
        return None
    with open(SPEEDO_IMAGE, 'rb') as f:
        return f.read()


def speedometer(files, img):
    """A uitex.agt's files with the dial piece replaced by img, as tools/eu_client.py set_speedometer: the piece's
    header 64 bytes kept, u32 size at +64, image at +72. -> (the new files, a note)."""
    from ui_texture import entries
    for i, (n, d) in enumerate(files):
        if not n.lower().endswith('.ntx'):
            continue
        for e, off, size in entries(d):
            if e.lower() != SPEEDO_PIECE.lower():
                continue
            if d[off + 72:off + 72 + size] == img:
                return files, f'uitex.agt: dial {SPEEDO_PIECE} already km/h'
            new = d[:off + 64] + struct.pack('<I', len(img)) + d[off + 68:off + 72] + img + d[off + 72 + size:]
            out = list(files)
            out[i] = (n, new)
            return out, f'uitex.agt: dial {SPEEDO_PIECE} -> {len(img)} bytes'
    raise SystemExit(f'uitex.agt: no piece {SPEEDO_PIECE} (nothing written)')


def content_table(data, theme):
    """GlobalContent.xlt with the battle zone / channel battle grades in its Value_US column."""
    new, missing = set_column(data, COLUMN, content_values(theme))
    if missing:
        raise SystemExit(f'GlobalContent.xlt: no such key: {", ".join(sorted(missing))} (nothing written)')
    return new


def text_table(data, theme, modes):
    """GlobalText.xlt with the Value_US texts of these settings: the Semi-channel rules (eu) and the km/h texts.
    A kph key this client does not have (2011 has no 12607) is skipped and named in the note."""
    notes = []
    if 'eu' in modes:
        data, missing = set_texts(data, COLUMN, eu_texts(theme['cbattle'][1]))
        if missing:
            raise SystemExit(f'GlobalText.xlt: no such key: {", ".join(sorted(missing))} (nothing written)')
        notes.append('GlobalText.xlt: Value_US 11411 / 11409 (Semi-channel rules and tax)')
    if 'kph' in modes:
        data, missing = set_texts(data, COLUMN, kph_texts())
        notes.append('GlobalText.xlt: Value_US 11874 / 11527 / 11977 / 10403 / 10729 / 10730 / 10216 / 10215'
                     ' (km/h texts)'
                     + (f', not in this client: {", ".join(sorted(missing))}' if missing else ''))
    return data, '; '.join(notes)


def change(name, data, theme, modes):
    """One table's (or loose file's) new bytes for these settings, and a note about what changed."""
    if name == 'itemclient.tdf':
        new, n = item_table(data)
        return new, (f'ItemClient.tdf: {n} items show the required V grade (level 0)' if n
                     else 'ItemClient.tdf: grades already set')
    if name == 'globalcontent.xlt':
        return content_table(data, theme), 'GlobalContent.xlt: Value_US (battle zone / channel battle grades)'
    if name == 'globaltext.xlt':
        return text_table(data, theme, modes)
    if name == 'assist_client.tdf':
        new, n = assist_table(data)
        return new, (f'Assist_Client.tdf: {n} texts in km/h' if n else 'Assist_Client.tdf: texts already km/h')
    if name == 'game.nui':
        return nui_table(data)
    raise SystemExit(f'{name}: no such file to change')


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


def child(path, name):
    """<path>/<name> (the name in any case), or None."""
    if not os.path.isdir(path):
        return None
    found = next((n for n in sorted(os.listdir(path)) if n.lower() == name.lower()), None)
    return os.path.join(path, found) if found is not None else None


def table_sources(client):
    """client_tables.Client's map, with the patch packs indexed again here: X.eu / X.kph / X.us sit beside X in
    Patch/ and Patch.0<NN>.<setting> still starts with "Patch.0", so client_tables would take them for the client's
    packs (and X.eu is not the client's table). A file that is only there as X.us counts as X (a swap that stopped
    between the rename and the copy)."""
    c = client_tables.Client(client)
    files = {k: v for k, v in c.files.items() if not v[0].lower().endswith(OURS)}
    for archive, prefix in client_tables.PACKS:         # a swapped archive: X.us alone
        path = os.path.join(client, *archive.split('/'))
        if os.path.exists(path) or not os.path.exists(path + '.us'):
            continue
        raw, entries = agt.index(path + '.us')
        for e in entries:
            files[(prefix + e[0]).lower()] = (archive, raw, e)
    for parts in (('Data', 'Init'), ('Data', 'World', 'Data'),
                  ('Data_US', 'Init'), ('Data_US', 'World', 'Data')):    # a swapped loose table: X.us alone
        path = client
        for part in parts:
            path = child(path, part) if path else None
        if not path:
            continue
        for name in sorted(os.listdir(path)):
            low = name.lower()
            if not low.endswith('.us') or not low[:-3].endswith(('.xlt', '.tdf')):
                continue
            base = os.path.join(path, name[:-3])
            if os.path.exists(base):
                continue
            rel = os.path.relpath(base, client)
            full = rel.replace(os.sep, '\\')
            files[full.lower()] = (rel, None, (full,))
    folder = patch_folder(client)
    for name in (sorted(os.listdir(folder)) if folder else ()):
        low = name.lower()
        if not low.startswith('patch.0') or (low.endswith(OURS) and not low.endswith('.us')):
            continue
        if low.endswith('.us'):
            if os.path.exists(os.path.join(folder, name[:-3])):
                continue                            # X is there: the .us is the swap's backup of it
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
    one; a patch pack or an archive wins over them (the engine asks the packs first, tools/pack_client.py). A
    client without an OPTIONAL table (Assist_Client.tdf) is left without it."""
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
            if name in OPTIONAL:
                continue
            raise SystemExit(f'{name}: not in {client} (tools/client_tables.py lists the tables it reads)')
    return out


def gui_file(client, name):
    """<client>/Data_US/gameui/<name>, any case of the folder and file names; None when it is not there."""
    path = client
    for part in ('Data_US', 'gameui', name):
        path = child(path, part) if path else None
    return path if path and os.path.isfile(path) else None


def sources(client):
    """{source relative path: {'pack': bool, 'tables': [(table name, entry or None)]}} of the files the settings
    change: the effective tables, plus the HUD layout and the interface pack when the client has them."""
    out = {}
    for name, (rel, raw, entry) in located(client).items():
        out.setdefault(rel, {'pack': raw is not None, 'tables': []})['tables'].append((name, entry))
    for name in GUI:
        path = gui_file(client, name)
        if path is None:
            print(f'note: Data_US/gameui/{name}: not in {client}, left out')
            continue
        out.setdefault(os.path.relpath(path, client),
                       {'pack': name in PACKED, 'tables': []})['tables'].append((name, None))
    return out


def transform_pack(files, tables, modes, theme, img):
    """A pack's files with the changes of these settings (a table whose settings are off stays as it is).
    -> (the new files, a note)."""
    files = list(files)
    notes = []
    for name, entry in tables:
        if name == 'uitex.agt':
            if 'kph' in modes:
                files, note = speedometer(files, img)
                notes.append(note)
            continue
        if not set(MODES.get(name, ())) & set(modes):
            continue
        i = next((k for k, (n, _) in enumerate(files) if n.lower() == entry[0].lower()), None)
        if i is None:
            raise SystemExit(f'{entry[0]}: the pack has no such entry any more')
        new, note = change(name, files[i][1], theme, modes)
        if new != files[i][1]:
            files[i] = (files[i][0], new)
        notes.append(note)
    return files, '; '.join(n for n in notes if n)


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
    """<client>/ClientModes.txt: the 2 comment lines, then "path<TAB>sha256<TAB>settings" per file; an older
    EURules.txt (eu only) goes."""
    text = '\n'.join(HEADER) + '\n' + ''.join(f'{rel}\t{digest}\t{",".join(modes)}\n'
                                              for rel, digest, modes in entries)
    path = os.path.join(client, MANIFEST)
    tmp = path + '.new'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)
    old = os.path.join(client, OLD_MANIFEST)
    if os.path.exists(old):
        os.remove(old)
        print(f'{OLD_MANIFEST}: removed (replaced by {MANIFEST})')


def read_manifest(client):
    """[(relative path with forward slashes, sha256, settings)] of <client>/ClientModes.txt, or of an older
    EURules.txt (two columns: eu)."""
    path = os.path.join(client, MANIFEST)
    if not os.path.exists(path):
        path = os.path.join(client, OLD_MANIFEST)
        if not os.path.exists(path):
            raise SystemExit(f'no {MANIFEST} in {client}: run `python -m tools.eu_rules build` first')
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            rel, _, rest = line.partition('\t')
            digest, _, modes = rest.partition('\t')
            chosen = tuple(m.strip() for m in modes.split(',') if m.strip()) or ('eu',)
            out.append((rel.strip(), digest.strip(), chosen))
    return out


def build(client, config=CONFIG):
    """Write the copies of every changed file for every setting combination, and <client>/ClientModes.txt.
    -> the manifest entries."""
    theme = rules(config)
    plan = sources(client)
    img = dial_image()
    manifest = []
    for rel in sorted(plan):
        tables = plan[rel]['tables']
        modes = tuple(m for m in SETTINGS if any(m in MODES.get(n, ()) for n, _e in tables))
        names = [n for n, _e in tables]
        if 'uitex.agt' in names and img is None:
            print(f'note: {rel}: {SPEEDO_IMAGE} is missing, no km/h dial copy')
            continue
        base = os.path.join(client, rel)
        active = os.path.exists(base + '.us')
        source = base + '.us' if active else base
        if not os.path.exists(source):
            raise SystemExit(f'{rel}: neither it nor {rel}.us exists')
        note = ''
        copies = ['.'.join(s) for s in subsets(modes)]
        if plan[rel]['pack']:
            header, files = agt.read(source)
            for subset in subsets(modes):
                new_files, note = transform_pack(files, tables, subset, theme, img)
                write_pack(base + '.' + '.'.join(subset), header, new_files)
        else:
            with open(source, 'rb') as f:
                data = f.read()
            for subset in subsets(modes):
                new, note = change(names[0], data, theme, subset)
                write_file(base + '.' + '.'.join(subset), new, source)
        manifest.append((rel.replace(os.sep, '/'), file_sum(source), modes))
        shown = ', '.join('.' + c for c in copies)
        print(f'{rel}: {shown} ({", ".join(modes)})'
              + (f': {note}' if note else '')
              + (f'  [from {rel}.us: a copy is in place]' if active else ''))
    write_manifest(client, manifest)
    print(f'{MANIFEST}: {len(manifest)} files (sha256 of the US file, not of the copies)')
    return manifest


def status(client):
    """ok / stale / missing for every copy of every manifest entry, and whether a copy is in place (X.us).
    -> [(relative path, state)]."""
    entries = read_manifest(client)
    if not entries:
        print(f'{MANIFEST}: no files (build it with tools.eu_rules build)')
        return []
    states = []
    for rel, digest, modes in entries:
        path = os.path.join(client, *rel.split('/'))
        active = os.path.exists(path + '.us')
        now = path + '.us' if active else path
        copies = ['.'.join(s) for s in subsets(modes)]
        missing = [c for c in copies if not os.path.exists(f'{path}.{c}')]
        if not os.path.exists(now):
            state = 'missing file'
        elif file_sum(now) != digest:
            state = 'stale'
        elif missing:
            state = 'missing ' + ' '.join('.' + c for c in missing)
        else:
            state = 'ok'
        states.append((rel, state))
        shown = ', '.join('.' + c for c in copies)
        print(f'{state:20} {rel} ({shown})' + ('  (a copy is active: X.us exists)' if active else ''))
    return states


def remove(client):
    """X.us back as X (the US files), then every copy and both manifests gone."""
    entries = read_manifest(client)
    restored = 0
    for rel, _digest, _modes in entries:
        path = os.path.join(client, *rel.split('/'))
        if os.path.exists(path + '.us'):
            os.replace(path + '.us', path)
            restored += 1
            print(f'{rel}: X.us back as X')
    removed = 0
    for rel, _digest, _modes in entries:
        path = os.path.join(client, *rel.split('/'))
        for subset in subsets(SETTINGS):
            copy = path + '.' + '.'.join(subset)
            for p in (copy, copy + '.new'):
                if os.path.exists(p):
                    os.remove(p)
                    removed += 1
    gone = [name for name in (MANIFEST, OLD_MANIFEST) if os.path.exists(os.path.join(client, name))]
    for name in gone:
        os.remove(os.path.join(client, name))
    print(f'{", ".join(gone) or MANIFEST}: removed ({len(entries)} files, {restored} copies put back, '
          f'{removed} copies deleted)')


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
