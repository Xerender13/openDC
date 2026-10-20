"""The Semi-channel tooltips of the channel battle window, drawn from the server's entry rules.

The window (client 0x6a3330) shows game.nui dialog 2030000 while the Semi-channel list is open (every nation but
JP, nation 2) and the tooltip of the Semi-channel button under the mouse: controls 2030001-2030005,
ID_TC_SEMICHANNEL_TOOLTIP_1..5, pictures "3,625~179,697_ui_contents56.dds" .. "3,917~179,989_ui_contents56.dds"
(176 x 72 of a 256 x 128 DXT5 piece). The 2011 US uitex.agt (and the EU folder made from it) has the wrong pictures
under those names: pieces of the kill counter's digits (0 5 / 1 6 / 2 7 ...), so hovering Semi-channel 1 drew a red
"05 16" next to the list (user, 2026-10-19). The 2016 client (DriftCity Dev Ed, Data_US/gameui/tex/F.ntx) has the
real ones: a speech bubble with "Crew Member / with V3 ~ V6 Vehicle / level 40 or less" (2016 rules, not 2011's).

`apply` writes one tooltip per Semi-channel into a client's uitex.agt: the 2016 bubble (kept as
client_backup/semi_tooltip_N.dds once read; a plain drawn bubble when neither is there) with its text cleared and
the rules of emulator.ini [cbattle] written in (US: semi.N, EU: eu.semi.N), in the 2016 colours. Semi-channels
without a rule get a fully transparent piece: their buttons are hidden (eu_client.set_semi_buttons), but the window
still shows the tooltip of the spot under the mouse, so a blank bubble appeared below the EU Semi Channel 2 button,
where the hidden Semi-channel 3 sits (user screenshot, 2026-10-19). The pack is rewritten with header bytes 20-31 kept;
the first original is kept in client_backup/ (uitex.agt.orig, uitex_<folder>.agt.orig), `reset` puts it back.
tools/eu_client.py cbattle runs it for the EU folder. Needs Pillow (the emulator's .venv has it).

usage: .venv/bin/python -m tools.semi_tooltips [us|eu|all]      (default all)
       .venv/bin/python -m tools.semi_tooltips reset [us|eu|all]
       .venv/bin/python -m tools.semi_tooltips preview OUT.png   the US and EU tooltips side by side
"""
import io
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402
from ui_texture import entries  # noqa: E402

ROOT = os.path.join(HERE, '..', '..')
BACKUPS = os.path.join(HERE, '..', 'client_backup')
INI = os.path.join(HERE, '..', 'emulator.ini')
DEV_ED = os.path.join(ROOT, 'DriftCity Dev Ed', 'Data_US', 'gameui', 'tex', 'F.ntx')
if not os.path.exists(DEV_ED):            # moved out of the client by tools/pack_client.py clean (packs only)
    DEV_ED = os.path.join(ROOT, 'DriftCity Dev Ed (loose)', 'Data_US', 'gameui', 'tex', 'F.ntx')
PIECES = ['3,625~179,697_ui_contents56.dds', '3,698~179,770_ui_contents56.dds', '3,771~179,843_ui_contents56.dds',
          '3,844~179,916_ui_contents56.dds', '3,917~179,989_ui_contents56.dds']
COLOURS = [(214, 85, 255), (90, 190, 247), (140, 235, 16), (255, 162, 0), (222, 44, 173)]   # the 2016 text colours
FILL, BORDER = (0, 0, 0, 191), (255, 255, 255, 115)
TEXT_BOX = (42, 10, 173, 64)               # the bubble's inside (the 2016 text: x 50.., lines at y 16 / 28 / 40)
FONTS = ['/usr/share/fonts/noto/NotoSans-Bold.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/tahomabd.ttf',
         'C:/Windows/Fonts/arialbd.ttf']
CLIENTS = {'us': ('Client US', 'Data_US', 'uitex.agt.orig'),
           'eu': ('Client EU', 'Data_EU_eng', 'uitex_Data_EU_eng.agt.orig')}


def rules(eu):
    """{Semi-channel N: (max level, min grade, max grade)} of emulator.ini [cbattle] (US semi.N / EU eu.semi.N)."""
    import configparser
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    cp.read(INI)
    sec = cp['cbattle'] if cp.has_section('cbattle') else {}
    prefix = 'eu.semi.' if eu else 'semi.'
    nums = lambda v: tuple(int(float(x)) for x in v.replace(',', ' ').split())[:3]
    out = {int(k[len(prefix):]): nums(v) for k, v in sec.items()
           if k.startswith(prefix) and k[len(prefix):].isdigit()}
    return out or ({1: (0, 1, 3), 2: (0, 1, 6)} if eu else {1: (40, 0, 0), 2: (60, 0, 0), 3: (70, 0, 0)})


def lines(rule):
    """The tooltip's text, worded as the 2016 tooltips: Crew Member / with V3 ~ V6 Vehicle / level 40 or less."""
    level, low, high = rule
    out = ['Crew Member']
    if high:
        out.append(f'with V{low or 1} ~ V{high} Vehicle')
    elif low > 1:
        out.append(f'with V{low} Vehicle or Higher')
    if level:
        out.append(('/ ' if len(out) > 1 else '') + f'level {level} or less')
    elif len(out) > 1:
        out.append('/ no level limit')
    if len(out) == 1:
        out.append('No Limit')
    return out


def bubble(n):
    """The 2016 bubble of tooltip n (0-4) as an RGBA image, its text cleared; a drawn one without the 2016 client."""
    from PIL import Image, ImageDraw
    saved = os.path.join(BACKUPS, f'semi_tooltip_{n + 1}.dds')
    data = open(saved, 'rb').read() if os.path.exists(saved) else None
    if data is None and os.path.exists(DEV_ED):
        ntx = open(DEV_ED, 'rb').read()
        for name, off, size in entries(ntx):
            if name.lower() == PIECES[n].lower():
                data = ntx[off + 72:off + 72 + size]
                os.makedirs(BACKUPS, exist_ok=True)
                open(saved, 'wb').write(data)
    if data:
        im = Image.open(io.BytesIO(data)).convert('RGBA')
    else:                                   # the same shape drawn: rounded box, tail at the bottom left
        im = Image.new('RGBA', (256, 128), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.polygon([(4, 69), (40, 46), (40, 62)], fill=FILL, outline=BORDER)
        d.rounded_rectangle((38, 3, 177, 69), 8, fill=FILL, outline=BORDER, width=2)
    ImageDraw.Draw(im).rectangle(TEXT_BOX, fill=FILL)
    return im


def font(size):
    from PIL import ImageFont
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def picture(n, rule):
    """Tooltip n (0-4) for this rule (None: nothing drawn, transparent) as RGBA."""
    from PIL import Image, ImageDraw
    im = bubble(n)
    if not rule:
        return Image.new('RGBA', im.size, (0, 0, 0, 0))
    text = lines(rule)
    size = 11
    while size > 8 and max(font(size).getlength(t) for t in text) > TEXT_BOX[2] - 48:
        size -= 1
    f, step = font(size), size + 1
    y = (TEXT_BOX[1] + TEXT_BOX[3]) // 2 - step * len(text) // 2 - 1
    d = ImageDraw.Draw(im)
    for t in text:
        d.text((50, y), t, font=f, fill=COLOURS[n] + (255,))
        y += step
    return im


def dds(im, original):
    """The picture as DXT5 with the original piece's header (same size and format: 256 x 128 DXT5, no mipmaps)."""
    out = io.BytesIO()
    im.save(out, format='DDS', pixel_format='DXT5')
    new = out.getvalue()
    if original[:4] == b'DDS ' and len(original) == len(new):
        return original[:128] + new[128:]
    return new


def apply(key):
    client, folder, backup_name = CLIENTS[key]
    path = os.path.join(ROOT, client, folder, 'gameui', 'uitex.agt')
    if not os.path.exists(path):
        return print(f'{client}/{folder}/gameui/uitex.agt: not there, skipped')
    semi = rules(key == 'eu')
    header, files = agt.read(path)
    changed = []
    for i, (name, ntx) in enumerate(files):
        if not name.lower().endswith('.ntx'):
            continue
        found = {e.lower(): (off, size) for e, off, size in entries(ntx)}
        for n, piece in enumerate(PIECES):
            if piece.lower() not in found:
                continue
            off, size = found[piece.lower()]
            new = dds(picture(n, semi.get(n + 1)), ntx[off + 72:off + 72 + size])
            if new != ntx[off + 72:off + 72 + size]:
                ntx = ntx[:off + 64] + struct.pack('<I', len(new)) + ntx[off + 68:off + 72] + new + ntx[off + 72 + size:]
                found = {e.lower(): (o, s) for e, o, s in entries(ntx)}
                changed.append(n + 1)
        files[i] = (name, ntx)
    if not changed:
        return print(f'{client}/{folder}/gameui/uitex.agt: Semi-channel tooltips already so')
    backup = os.path.join(BACKUPS, backup_name)
    if not os.path.exists(backup):
        os.makedirs(BACKUPS, exist_ok=True)
        shutil.copy2(path, backup)
        print('original pack kept as', os.path.normpath(backup))
    tmp = path + '.new'
    agt.write(tmp, header, files)
    raw = bytearray(open(tmp, 'rb').read())
    raw[20:32] = header[20:32]
    open(tmp, 'wb').write(bytes(raw))
    os.replace(tmp, path)
    text = '; '.join(f'{n}: ' + ' '.join(lines(semi[n])) for n in sorted(semi))
    print(f'{client}/{folder}/gameui/uitex.agt: Semi-channel tooltips {changed} ({text}); restart the client')


def reset(key):
    """The tooltip pieces of the original pack back (the rest of the pack as it is now)."""
    client, folder, backup_name = CLIENTS[key]
    path, backup = os.path.join(ROOT, client, folder, 'gameui', 'uitex.agt'), os.path.join(BACKUPS, backup_name)
    if not os.path.exists(path) or not os.path.exists(backup):
        return print(f'{client}: no pack or no backup, nothing to do')
    orig = {}
    for name, ntx in agt.read(backup)[1]:
        if name.lower().endswith('.ntx'):
            for e, off, size in entries(ntx):
                if e.lower() in [p.lower() for p in PIECES]:
                    orig[e.lower()] = ntx[off + 72:off + 72 + size]
    header, files = agt.read(path)
    for i, (name, ntx) in enumerate(files):
        if not name.lower().endswith('.ntx'):
            continue
        for piece in PIECES:
            for e, off, size in entries(ntx):
                if e.lower() == piece.lower() and piece.lower() in orig:
                    new = orig[piece.lower()]
                    ntx = ntx[:off + 64] + struct.pack('<I', len(new)) + ntx[off + 68:off + 72] + new + ntx[off + 72 + size:]
                    break
        files[i] = (name, ntx)
    tmp = path + '.new'
    agt.write(tmp, header, files)
    raw = bytearray(open(tmp, 'rb').read())
    raw[20:32] = header[20:32]
    open(tmp, 'wb').write(bytes(raw))
    os.replace(tmp, path)
    print(f'{client}/{folder}/gameui/uitex.agt: original Semi-channel tooltip pieces back')


def preview(out):
    from PIL import Image
    sheet = Image.new('RGBA', (2 * 190, 5 * 76), (70, 70, 70, 255))
    for col, eu in enumerate((False, True)):
        semi = rules(eu)
        for n in range(5):
            sheet.alpha_composite(picture(n, semi.get(n + 1)).crop((0, 0, 182, 74)), (col * 190, n * 76))
    sheet.save(out)
    print('preview ->', out)


def main():
    args = sys.argv[1:]
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit('semi_tooltips needs Pillow: run it with the emulator .venv (.venv/bin/python -m tools.semi_tooltips)')
    if args and args[0] == 'preview':
        return preview(args[1] if len(args) > 1 else 'semi_tooltips.png')
    do = reset if args and args[0] == 'reset' else apply
    if args and args[0] == 'reset':
        args = args[1:]
    which = args[0] if args else 'all'
    if which not in ('us', 'eu', 'all'):
        sys.exit(__doc__)
    for key in (('us', 'eu') if which == 'all' else (which,)):
        do(key)


if __name__ == '__main__':
    main()
