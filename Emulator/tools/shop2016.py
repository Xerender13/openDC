"""Restore 2016 HOME, drive skills and drift-item auction controls.

Usage: python -m tools.shop2016 [2016 client directory [Origin client directory]]. The auction layout
reads the Origin client (/home/deck/Drift City Origin/Client; never written). Backups are kept in
client_backup/shop2016; unrelated entries and archive bytes20..31 are preserved.
Restart the client after applying. Never operates on a 2011 client.
"""
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from . import agt
from .client_tables import Client

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / 'Emulator/client_backup/shop2016'


def table(raw, key_col, key, changes):
    lines = raw.decode('utf-16').splitlines(keepends=True)
    found = False
    for i, line in enumerate(lines[3:], 3):
        ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
        f = line.rstrip('\r\n').split('\t')
        if len(f) > key_col and f[key_col] == key:
            for col, value in changes.items():
                f[col] = str(value)
            lines[i] = '\t'.join(f) + ending
            found = True
    if not found:
        raise ValueError(f'missing table row: {key}')
    return b'\xff\xfe' + ''.join(lines).encode('utf-16-le')


# The drift-item auction layout (user 2026-10-20: the session 36 layout broke with the Drift Items tab: list wider
# than the 700 px frame, white header boxes) follows the Origin client's game.nui, whose dialog 1360000 has the full
# drift design: an 817 px frame (two ui_contents28 pieces, copied into the 2016 uitex.agt) and positions for every
# control. Kept from 2016: the pictures of all other controls, the normal header pictures, and the drift header
# columns of the 2016 row renderer 0x5f7ab0 (Origin's own headers are placed for Origin's renderer, and two of
# them mean other things there: 1360032 "Option", 1360033 a Korean term picture).
ORIGIN = Path('/home/deck/Drift City Origin/Client')
FRAME_PIECES = ('3,771~820,905_ui_contents28.dds', '3,908~820,980_ui_contents28.dds')
FRAME_CONTAINER = 'tex\\E.ntx'            # where both clients keep the ui_contents28 pieces
LIST_X = 227                               # Origin's list 1360008 (761 px: the 2016 drift rows need 755)
NORMAL_HEADERS = {1360010: 2, 1360011: 2, 1360012: 133, 1360013: 304, 1360014: 378, 1360015: 473,
                  1360016: 558}            # 2016's own offsets from its list (x 342)
# 2016 drift sort controls (0x5f99c0..0x5f9b99): label, offset from the list, width. 1360032 / 1360033 sort by
# listing days left (14 / 15) and the item's remaining lifetime (16 / 17); a 12 px spacer before the seller.
DRIFT_HEADERS = {1360031: ('Item', 23, 181), 1360032: ('Days', 204, 30), 1360033: ('Remaining', 234, 96),
                 1360034: ('Price', 330, 121), 1360035: ('Count', 451, 51), 1360036: ('Seller', 514, 162),
                 1360037: ('Sales', 676, 61)}
HEADER_COLOUR = 'FFC68200'                 # the text colour of Origin's header pictures
FROM_ORIGIN = (1360057, 1360058, 1360059)  # Drift Item checkbox, its label, the option search box
OWN_PICTURE = (1360041,)                   # NPC: Origin crops another part of ch_00000.dds


def controls_of(text, dialog=1360000):
    m = re.search(r'<DIALOG C="%d"[^>]*>(.*?)</DIALOG>' % dialog, text, re.S)
    return {int(c[1]): c for c in re.finditer(r'<CONTROL\b[^>]* B="(\d+)"[^>]*>.*?</CONTROL>', m[1], re.S)}, m.start(1)


def origin_controls(origin_nui):
    """Origin's auction controls as elements, without the (Korean) name attributes."""
    text = origin_nui.decode('cp949', 'replace')
    found, _ = controls_of(text)
    out = {}
    for number, m in found.items():
        node = ET.fromstring(m[0])
        for el in node.iter():
            for attr in ('NM', 'D'):
                el.attrib.pop(attr, None)
        out[number] = node
    return out


def auction_ui(raw, origin):
    """The 2016 game.nui with the auction dialog laid out as above; origin = origin_controls(...)."""
    text = raw.decode('cp949')
    found, base = controls_of(text)
    replacements = {}
    for number, m in found.items():
        node = ET.fromstring(m[0])
        info, nation = node.find('INFO'), node.find('NATION')
        o = origin.get(number)
        if number in FROM_ORIGIN:
            node = o
        elif number in NORMAL_HEADERS:
            nation.set('H', f'{LIST_X + NORMAL_HEADERS[number]} 149')
        elif number in DRIFT_HEADERS:
            label, offset, width = DRIFT_HEADERS[number]
            node = ET.fromstring(
                f'<CONTROL B="{number}"><INFO TYPE="2" EC="2" SZ1="{width} 38" POS1="0 0" C1_1="FFFFFF" '
                f'C1_2="FFFFFF" C1_3="FFFFFF" C1_4="FFFFFF" C1_5="FFFFFF" T1="{label}" FN1="Tahoma 12 700" '
                f'FC1_1="{HEADER_COLOUR}" FO1_1="1" FOC1_1="FF000000" TA1="5" />'
                f'<NATION C="0" H="{LIST_X + offset} 149" /></CONTROL>')
        elif o is not None and nation is not None and o.find('NATION') is not None:
            nation.set('H', o.find('NATION').get('H'))
            if number in (1360001, 1360002):          # the frame: Origin's pictures
                for attr in [a for a in info.attrib if a[:2] in ('I1', 'UV', 'SZ', 'PO')]:
                    del info.attrib[attr]
                info.attrib.update({a: v for a, v in o.find('INFO').attrib.items() if a[:2] in ('I1', 'UV', 'SZ', 'PO')})
            elif number not in OWN_PICTURE and info.get('SZ1') and o.find('INFO').get('SZ1'):
                info.set('SZ1', o.find('INFO').get('SZ1'))
        else:
            continue
        replacements[number] = ET.tostring(node, encoding='unicode')
    for number in sorted(replacements, key=lambda n: found[n].start(), reverse=True):
        m = found[number]
        text = text[:base + m.start()] + replacements[number] + text[base + m.end():]
    ET.fromstring(text[text.index('<document'):] if '<document' in text else text)
    return text.encode('cp949')


def frame_pieces(origin_uitex):
    """Origin's frame pieces as container entries (char[64] name, u32 size, u32 tag, DDS), by name."""
    from .ui_texture import entries
    raw, found = agt.index(str(origin_uitex), agt.ORIGIN_KEY)
    out = {}
    for e in found:
        if e[0].lower() == FRAME_CONTAINER.lower():
            data = agt.extract(raw, e, agt.ORIGIN_KEY)
            for name, off, size in entries(data):
                if name.lower() in FRAME_PIECES:
                    out[name.lower()] = data[off:off + 72 + size]
    missing = set(FRAME_PIECES) - set(out)
    if missing:
        raise SystemExit(f'Origin uitex.agt lacks {sorted(missing)}')
    return out


def add_pieces(pieces):
    """A container transform appending the pieces it does not hold yet."""
    def transform(ntx):
        from .ui_texture import entries
        have = {name.lower() for name, _, _ in entries(ntx)}
        return ntx + b''.join(data for name, data in sorted(pieces.items()) if name not in have)
    return transform


def backup(path, name):
    BACKUP.mkdir(parents=True, exist_ok=True)
    target = BACKUP / name
    if not target.exists():
        shutil.copy2(path, target)


def pack(path, entry, transform, name):
    header, files = agt.read(str(path))
    old = dict(files)[entry]
    new = transform(old)
    if new == old:
        return
    backup(path, name)
    changed = [(n, new if n == entry else d) for n, d in files]
    temp = str(path) + '.shop2016.new'
    agt.write(temp, header, changed)
    data = bytearray(Path(temp).read_bytes())
    data[20:32] = header[20:32]
    Path(temp).write_bytes(data)
    checked_header, checked = agt.read(temp)
    assert checked_header[20:32] == header[20:32] and checked == changed
    Path(temp).replace(path)
    print('updated:', path, entry)


def main():
    client = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'DriftCity Dev Ed'
    if not (client / 'DriftCity2016Test.exe').exists():
        raise SystemExit('Expected the 2016 Dev Ed client (DriftCity2016Test.exe).')
    _, source = Client(str(client)).source('VShopCategory.xlt')
    _, entries = agt.index(str(client / source))
    entry = next(e[0] for e in entries if e[0].lower().endswith('vshopcategory.xlt'))
    def categories(raw):
        # HOME top tab only: retired plain-paint categories stay disabled.
        raw = table(raw, 1, '0', {7: 1})
        return table(raw, 0, '100', {7: 1, 8: 1})
    pack(client / source, entry, categories, '2016_Init.agt.before')
    pack(client / 'Data/Localize.agt', 'Localize\\GlobalContent.xlt',
         lambda r: table(r, 3, 'AuctionVSItem', {5: 1}), '2016_Localize.agt.before')
    origin = Path(sys.argv[2]) if len(sys.argv) > 2 else ORIGIN
    if not (origin / 'Data/GameUI/game.nui').exists():
        raise SystemExit(f'The auction layout needs the Origin client (read only): {origin}')
    pack(client / 'Data_US/gameui/uitex.agt', FRAME_CONTAINER,
         add_pieces(frame_pieces(origin / 'Data/GameUI/uitex.agt')), '2016_uitex.agt.before')
    nui = client / 'Data_US/gameui/game.nui'
    old = nui.read_bytes()
    new = auction_ui(old, origin_controls((origin / 'Data/GameUI/game.nui').read_bytes()))
    if new != old:
        backup(nui, '2016_game.nui.before')
        temp = nui.with_name(nui.name + '.shop2016.tmp')
        temp.write_bytes(new)
        temp.replace(nui)
        print('updated:', nui)
    print('Restart the 2016 client to load the settings and layout.')


if __name__ == '__main__':
    main()
