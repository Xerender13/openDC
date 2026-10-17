"""Turn Client/DriftCityEU.exe into the European client and give it its data folder.

DriftCityEU.exe is the 2011-10-27 GamesCampus build (the same program as DriftCity.exe, the same addresses),
already unpacked (no ASProtect: its code can be read and changed on disk). The program serves every publisher; a
nation number picks the rules, texts, data folder and login server (client 0x4e9360 GetNation, global 0x94d880):
    1 US (Data_US)   7 EU de (Data_EU_de)   8 EU eng (Data_EU_eng)   9 EU fr (Data_EU_fr)   10 EU es (Data_EU_es)
The nation is not read from any file: the options object's constructor (0x4e4090, object 0x94d2c0) sets it to 1
(US) at 0x4e4106, in the object (+0x16c, read by the data path setup 0x4e6cf0) and in the global. `setup` rewrites
those 22 bytes so both get the EU nation and eax is 1 again afterwards (the code after them stores al):
    b8 01 00 00 00     mov eax, 1                ->  6a NN 58           push NN; pop eax
    88 9e 68 01 00 00  mov [esi+0x168], bl           (same)
    89 86 6c 01 00 00  mov [esi+0x16c], eax          (same)
    a3 80 d8 94 00     mov [0x94d880], eax           (same)
                                                      b0 01              mov al, 1
The file check: at start (0x4eebed, again at 0x4f01a7 for nations 7-10) 0x4ed620 compares the files of the nation's
data folder (\\Data_EU_eng, ...) with the list in Client\\dname.chk (encrypted, layered key rounds 0x4f4940); that
list is the US client's, so the EU folder fails it ("Invalid Files Detected.", 0x4f0a70). `setup` makes 0x4ed620
report the files as good:
    55 8b ec           push ebp; mov ebp, esp     ->  31 c0 c3           xor eax, eax; ret
What an EU nation changes, as far as read (client addresses):
  - data: ../Data_EU_<lang>/Init_<s>.agt, World.agt, vehicles_<s>.agt, game_<s>.agt, effects_<s>.agt,
    gameui/uitex.agt (0x4ef9dd..; s = eueng / eufr / eues / de); a missing one stops the start ("Nation Data File
    Not Exist"). Texts: GlobalText.xlt's EU columns (DE / ENG / FR / ES).
  - login server: hard-coded 62.146.191.136 (live) / .135 (alpha) at 0x8daa14 / 0x8daa24 (0x538ff0); the launcher
    writes the configured address over every nation's slot.
  - start: `/runsw <token>` as the US, but token = md5("eu_%d_plz_do_not_hack" % (t - t % 300000)) (0x5095a0; the
    US check 0x509980 hashes "%d"); the launcher picks it when the exe holds an EU nation.
  - protection: nation class 0 (table 0x4e1210), the object whose checks all succeed: no GameGuard.
  - login: the same 0x14 as the US, the password as UTF-8 (0x538807); after it an extra 0x7cf (u32 nation) on the
    auth connection (0x7feaf0).
  - the US client's LoginAck success path is shared (0x50cb10); error codes map to other texts.
  - many rules branch on the nation (460 GetNation calls), e.g. EU-only checks in the item code (0x5fa8ed).

The data folder is made from Data_US (the only data we have): the packs under their EU names (hard links where
unchanged; Client EU has no Data_US of its own since 2026-10-17, so ../Client US/Data_US is used), and World.agt
with the Data_US tables of the patch packs folded in (the patches name them
"Data_US\\World\\data\\...", which an EU client never looks up; ItemUpgradeClient, ArbeitClient, ItemClient,
UseItemClient, Instant_Client). Run `setup` again after a client patch.

`us` writes Client US/DriftCityUS.exe for the US client instead of the ASProtect DriftCity.exe: the unpacked exe as it
came (nation 1, Data_US, the dname.chk check left on: the US folder is the one listed), with GameGuard off on disk:
the protection class of nation 1 (table 0x4e1210, byte 0x4e1211) 2 (GameGuard) -> 0 (the object whose checks all
succeed, as the EU nations get). No ASProtect, so the launcher's code-checked workarounds are not needed for it
(its breakpoint finds the class already 0). Select it with DriftCityLauncher.ini [client] exe = DriftCityUS.exe.

F2 car panel (asked by the user, 2026-10-17; the one exception to keeping the EU design): the F2 user information
window draws the car-name image and V grade (0x551ce0: 0x564820 by car type, 0x563f30 the grade) only for nations
1-3 and 6; 0x56ffd6 picks by the table at 0x570010 (index nation - 4: 0 0 1 0 0 0 0), so EU nations left the box
black. `setup` (or `f2 on`) sets the EU nations' bytes 0x570013-0x570016 to 1, the US path; `f2 off` puts 0 back.

Speedometer (asked by the user, 2026-10-17): the classic HUD's dial picture (game.nui control 210001, piece
"272,267~512,512_ui_play01.dds" in gameui/uitex.agt) says MPH. `speedo [TW client dir]` puts the 2008 Taiwan client's
dial there (Data_TW.agt, picture "406" of its 2008 .ntx, same 240x245 area: "Km/h" and the RPM numbers 0-10) in the
EU folder's own pack only (Data_EU_<lang>/gameui/uitex.agt, header bytes 20-31 kept; the first original kept as
client_backup/uitex_<folder>.agt.orig; `speedo mph` puts it back). The TW picture is kept as
client_backup/tw_speedometer_406.dds; `setup` applies it again when that file is there.

Part requirements by V grade (user, 2026-10-17: the EU tooltip must show "Required Grade", not the level): the item
tooltip (0x657442) shows "Required Level" when ItemClient column 7 (+0x120) is not 0, else "Required Grade" column 8
(+0x124), for every nation; the EU client's tables (also the user's older EU ItemClient.tdf) have 0 in column 8.
`grades` (part of setup) writes the emulator's EU rule (dcemu.native.data.part_grade_rule: parts N V1-3 / S V4-6 /
H V7-9 by tier, options and docking N V1 / S V4 / H V7) into Data_EU_<lang>/World.agt's ItemClient.tdf: column 7 0,
column 8 the grade (the changed cells point at existing strings of the table; the table header's u32 @4 is the same
in every table, not a checksum). The first original is kept as client_backup/World_<folder>.agt.orig.

Speed unit texts (user, 2026-10-17: "any MPH changed to KPH"): `kph` (part of setup) sets the HUD speed labels of
Data_EU_<lang>/gameui/game.nui (six controls, T1="MPH" / "mph", NM "..._km/h") to KPH / kph (first original:
client_backup/game_<folder>.nui.orig). GlobalText 11874 "mph" (the only speed unit in the EU text column):
tools/global_text.py "../Client EU" --column EU_eng set 11874=kph (Patch.006, a shared pack: not part of setup).

The client dir defaults to ../Client EU (../Client US for `us`).

usage: python3 Emulator/tools/eu_client.py [client dir] setup [de|eng|fr|es]   (default eng)
       python3 Emulator/tools/eu_client.py [client dir] us            DriftCityUS.exe: the unpacked US client
       python3 Emulator/tools/eu_client.py [client dir] f2 on|off     the F2 car panel for EU nations
       python3 Emulator/tools/eu_client.py [client dir] speedo [TW client dir | mph]   the dial with Km/h
       python3 Emulator/tools/eu_client.py [client dir] grades        part tooltips with the required V grade
       python3 Emulator/tools/eu_client.py [client dir] kph           the HUD speed labels KPH instead of MPH
       python3 Emulator/tools/eu_client.py [client dir] status
       python3 Emulator/tools/eu_client.py [client dir] reset         the original exe back (the data folder stays)
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agt  # noqa: E402

EXE = 'DriftCityEU.exe'
BACKUP = os.path.join(HERE, '..', 'client_backup', 'DriftCityEU.exe.orig')
NATION_AT = 0x4e4106                      # virtual address of the 22 bytes
ORIGINAL = bytes.fromhex('b801000000' '889e68010000' '89866c010000' 'a380d89400')
FILECHECK_AT, FILECHECK, FILECHECK_OFF = 0x4ed620, bytes.fromhex('558bec'), bytes.fromhex('31c0c3')
SPEEDO_PIECE = '272,267~512,512_ui_play01.dds'
TW_PICTURE = '406'
TW_SAVED = os.path.join(HERE, '..', 'client_backup', 'tw_speedometer_406.dds')
TW_CLIENT = os.path.join(HERE, '..', '..', '..', 'Drift City 0.02 TW', 'Client')
F2_AT, F2_EU, F2_US = 0x570013, bytes(4), bytes([1] * 4)   # F2 car panel table entries of nations 7-10
US_EXE = 'DriftCityUS.exe'
GG_CLASS_AT = 0x4e1210 + 1                 # protection class of nation 1: 2 GameGuard, 0 none
NATIONS = {'us': 1, 'de': 7, 'eng': 8, 'fr': 9, 'es': 10}
FOLDER = {'de': 'Data_EU_de', 'eng': 'Data_EU_eng', 'fr': 'Data_EU_fr', 'es': 'Data_EU_es'}
SUFFIX = {'de': 'de', 'eng': 'eueng', 'fr': 'eufr', 'es': 'eues'}
US_PACKS = {'Init_us.agt': 'Init_{s}.agt', 'vehicles_us.agt': 'vehicles_{s}.agt', 'game_us.agt': 'game_{s}.agt',
            'effects_us.agt': 'effects_{s}.agt', 'World.agt': 'World.agt'}


def patched(nation):
    return bytes([0x6a, nation, 0x58]) + ORIGINAL[5:] + b'\xb0\x01'


def file_offset(exe, va):
    """File offset of a virtual address (section table of the PE header)."""
    pe = struct.unpack_from('<I', exe, 0x3c)[0]
    count, opt = struct.unpack_from('<HxxxxxxxxxxxxH', exe, pe + 6)
    base = struct.unpack_from('<I', exe, pe + 24 + 28)[0]
    rva = va - base
    for i in range(count):
        s = pe + 24 + opt + 40 * i
        vsize, vaddr, rsize, raw = struct.unpack_from('<4I', exe, s + 8)
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raw + rva - vaddr
    raise ValueError(f'{va:#x} is in no section')


def nation_of(exe):
    """The nation the exe sets, or None for code we do not know."""
    at = file_offset(exe, NATION_AT)
    cur = exe[at:at + len(ORIGINAL)]
    if cur == ORIGINAL:
        return 1
    if cur[:1] == b'\x6a' and cur == patched(cur[1]):
        return cur[1]
    return None


def set_nation(client, nation):
    path = os.path.join(client, EXE)
    exe = bytearray(open(path, 'rb').read())
    now = nation_of(exe)
    if now is None:
        sys.exit(f'{EXE}: unknown code at {NATION_AT:#x}; not the build this tool knows (nothing written)')
    if not os.path.exists(BACKUP):
        if now != 1:
            sys.exit(f'{EXE} is already changed and there is no backup at {os.path.normpath(BACKUP)}')
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copy2(path, BACKUP)
        print('original exe kept as', os.path.normpath(BACKUP))
    if now == nation:
        print(f'{EXE}: nation already {nation}')
        return
    at = file_offset(exe, NATION_AT)
    exe[at:at + len(ORIGINAL)] = ORIGINAL if nation == 1 else patched(nation)
    write_exe(path, exe)
    print(f'{EXE}: nation {now} -> {nation}')


def set_f2(client, on):
    """on: the F2 window draws the car-name image and V grade for EU nations too (the US path)."""
    path = os.path.join(client, EXE)
    exe = bytearray(open(path, 'rb').read())
    at = file_offset(exe, F2_AT)
    if exe[at - 3:at] != bytes([0, 0, 1]):          # nations 4-6 of the table, never changed
        sys.exit(f'{EXE}: unknown table at {F2_AT - 3:#x} (nothing written)')
    want, other = (F2_US, F2_EU) if on else (F2_EU, F2_US)
    if exe[at:at + 4] == want:
        return
    if exe[at:at + 4] != other:
        sys.exit(f'{EXE}: unknown bytes at {F2_AT:#x} (nothing written)')
    exe[at:at + 4] = want
    write_exe(path, exe)
    print(f'{EXE}: F2 car panel for EU nations {"on" if on else "off (EU design)"}')


def eu_folder(client):
    """The client's EU data folder (Data_EU_*), or None."""
    return next((f for f in FOLDER.values() if os.path.isdir(os.path.join(client, f))), None)


def tw_speedometer(tw_client):
    """The 2008 Taiwan client's dial picture (DDS), kept in client_backup once read."""
    if os.path.exists(TW_SAVED):
        return open(TW_SAVED, 'rb').read()
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'Server2008', 'tools'))
    pack = os.path.join(tw_client, 'Data_TW.agt')
    if not os.path.exists(pack):
        sys.exit(f'no {pack}: give the 0.02 TW client folder (speedo DIR)')
    raw, es = agt.index(pack)
    for e in es:
        if e[0].lower().endswith('.ntx'):
            d, p = agt.extract(raw, e), 0
            while p + 20 <= len(d):                 # 2008 .ntx: char[16] name, u32 size, the image
                name = d[p:p + 16].split(b'\0', 1)[0].decode('latin-1')
                size = struct.unpack_from('<I', d, p + 16)[0]
                if not name or not size:
                    break
                if name == TW_PICTURE:
                    img = d[p + 20:p + 20 + size]
                    os.makedirs(os.path.dirname(TW_SAVED), exist_ok=True)
                    open(TW_SAVED, 'wb').write(img)
                    return img
                p += 20 + size
    sys.exit(f'{pack}: no picture {TW_PICTURE}')


def set_speedometer(client, img):
    """img (DDS bytes) as the dial piece of the EU folder's uitex.agt; None = the original piece back."""
    from ui_texture import entries
    folder = eu_folder(client)
    if not folder:
        sys.exit('no EU data folder: run setup first')
    path = os.path.join(client, folder, 'gameui', 'uitex.agt')
    backup = os.path.join(HERE, '..', 'client_backup', f'uitex_{folder}.agt.orig')
    if img is None:
        _, orig = agt.read(backup if os.path.exists(backup) else path)
        img = next(d[off + 72:off + 72 + size] for n, d in orig if n.lower().endswith('.ntx')
                   for e, off, size in entries(d) if e.lower() == SPEEDO_PIECE.lower())
    header, files = agt.read(path)
    for i, (n, d) in enumerate(files):
        if not n.lower().endswith('.ntx'):
            continue
        for e, off, size in entries(d):
            if e.lower() == SPEEDO_PIECE.lower():
                if d[off + 72:off + 72 + size] == img:
                    return print(f'{folder}/gameui/uitex.agt: dial already so')
                if not os.path.exists(backup):
                    shutil.copy2(path, backup)
                    print('original pack kept as', os.path.normpath(backup))
                files[i] = (n, d[:off + 64] + struct.pack('<I', len(img)) + d[off + 68:off + 72] + img + d[off + 72 + size:])
                tmp = path + '.new'
                agt.write(tmp, header, files)
                raw = bytearray(open(tmp, 'rb').read())
                raw[20:32] = header[20:32]
                open(tmp, 'wb').write(bytes(raw))
                os.replace(tmp, path)
                return print(f'{folder}/gameui/uitex.agt: dial {SPEEDO_PIECE} -> {len(img)} bytes')
    sys.exit(f'{path}: no piece {SPEEDO_PIECE}')


def set_filecheck(client, off):
    """off: 0x4ed620 reports the data folder's files as good (the EU folder is not in dname.chk)."""
    path = os.path.join(client, EXE)
    exe = bytearray(open(path, 'rb').read())
    at = file_offset(exe, FILECHECK_AT)
    want, other = (FILECHECK_OFF, FILECHECK) if off else (FILECHECK, FILECHECK_OFF)
    if exe[at:at + 3] == want:
        return
    if exe[at:at + 3] != other:
        sys.exit(f'{EXE}: unknown code at {FILECHECK_AT:#x} (nothing written)')
    exe[at:at + 3] = want
    write_exe(path, exe)
    print(f'{EXE}: data file check (dname.chk) {"skipped" if off else "on"}')


def write_exe(path, exe):
    tmp = path + '.tmp'
    open(tmp, 'wb').write(bytes(exe))
    shutil.copymode(path, tmp)
    os.replace(tmp, path)


def link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def us_patches(client):
    """{entry name inside Data_US\\World.agt (e.g. World\\data\\ItemClient.tdf): data} from Patch.000-010, the
    latest patch winning (the order the client applies them)."""
    out, pdir = {}, os.path.join(client, 'Patch')
    for f in sorted(os.listdir(pdir)):
        if not f.lower().startswith('patch.0'):
            continue
        raw, entries = agt.index(os.path.join(pdir, f))
        for e in entries:
            name = e[0]
            if name.lower().startswith('data_us\\'):
                rest = name[len('Data_US\\'):]
                if not rest.lower().startswith('world\\'):
                    print(f'  warning: {f} {name}: not in World.agt, left out')
                    continue
                out[rest.lower()] = (rest, agt.extract(raw, e), f)
    return out


def us_data(client):
    """The Data_US folder to build from: the client's own, else ../Client US/Data_US (Client EU keeps only
    Data_EU_eng since 2026-10-17: its Data_US was deleted to save space, user)."""
    own = os.path.join(client, 'Data_US')
    if os.path.isdir(own):
        return own
    other = os.path.join(client, '..', 'Client US', 'Data_US')
    if not os.path.isdir(other):
        sys.exit(f'no Data_US in {client} or {os.path.normpath(other)}: needed to build the EU folder')
    return other


def make_world(client, dst):
    """Data_US/World.agt with the patch packs' Data_US tables in it, header bytes 20-31 kept."""
    src = os.path.join(us_data(client), 'World.agt')
    header, files = agt.read(src)
    patches = us_patches(client)
    names = {n.lower(): i for i, (n, _) in enumerate(files)}
    for key, (rest, data, pack) in sorted(patches.items()):
        if key in names:
            files[names[key]] = (files[names[key]][0], data)
        else:
            files.append((rest, data))
        print(f'  World.agt: {rest} from {pack}')
    tmp = dst + '.new'
    agt.write(tmp, header, files)
    raw = bytearray(open(tmp, 'rb').read())
    raw[20:32] = header[20:32]
    open(tmp, 'wb').write(bytes(raw))
    os.replace(tmp, dst)


def make_folder(client, lang):
    us, eu = us_data(client), os.path.join(client, FOLDER[lang])
    print(f'{FOLDER[lang]}: from {os.path.normpath(us)}')
    for root, dirs, files in os.walk(us):
        rel = os.path.relpath(root, us)
        os.makedirs(os.path.join(eu, rel), exist_ok=True)
        for f in files:
            if rel == '.' and f in US_PACKS:
                continue
            link_or_copy(os.path.join(root, f), os.path.join(eu, rel, f))
    for src, dst in US_PACKS.items():
        dst = dst.format(s=SUFFIX[lang])
        if src == 'World.agt':
            make_world(client, os.path.join(eu, dst))
        else:
            link_or_copy(os.path.join(us, src), os.path.join(eu, dst))
        print(f'  {dst} <- Data_US/{src}')


def tdf_set(data, changes):
    """A .tdf (bitmap + table) with cells changed: {(row, col): text}. Changed cells point at a string already in
    the table when there is one, else at a new one appended (the table's size @12 grows)."""
    bmp, = struct.unpack_from('<I', data, 2)
    t = bytearray(data[bmp:])
    cols, n = struct.unpack_from('<II', t, 16)
    offs = list(struct.unpack_from(f'<{cols * n}I', t, 24))

    def text(o):
        e = t.index(b'\0\0', o)
        while (e - o) % 2:
            e = t.index(b'\0\0', e + 1)
        return t[o:e].decode('utf-16-le')
    at = {}
    for o in offs:
        at.setdefault(text(o), o)
    for (r, c), v in changes.items():
        if v not in at:
            at[v] = len(t)
            t += v.encode('utf-16-le') + b'\0\0'
        offs[r * cols + c] = at[v]
    struct.pack_into(f'<{cols * n}I', t, 24, *offs)
    struct.pack_into('<I', t, 12, len(t))
    return data[:bmp] + bytes(t)


def set_grades(client):
    """Data_EU_<lang>/World.agt: ItemClient.tdf column 7 = 0 and column 8 = the EU V grade (see the module text)."""
    sys.path.insert(0, os.path.join(HERE, '..'))
    from dcemu.native.data import part_grade_rule, part_tiers
    for folder in FOLDER.values():
        path = os.path.join(client, folder, 'World.agt')
        if not os.path.exists(path):
            continue
        backup = os.path.join(HERE, '..', 'client_backup', f'World_{folder}.agt.orig')
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
            print(f'{folder}/World.agt: original kept as {os.path.normpath(backup)}')
        from dcemu.native.data import read_tdf

        def item_table(pack):
            header, files = agt.read(pack)
            k = next(i for i, (name, _) in enumerate(files) if name.lower() == 'world\\data\\itemclient.tdf')
            tmp = os.path.join(client, folder, 'ItemClient.tdf.tmp')
            open(tmp, 'wb').write(files[k][1])
            rows = read_tdf(tmp)
            os.remove(tmp)
            return header, files, k, rows
        header, files, k, rows = item_table(path)
        data = files[k][1]
        # the levels (and so the tiers) from a table this step has not changed yet: the current one when it still has
        # levels, else the first original (a second run must not read the zeroed levels)
        has_levels = any(r[7] not in ('0', '') for r in rows if len(r) > 8 and r[0] in ('speed', 'accel'))
        source = rows if has_levels else item_table(backup)[3]
        by_id = {r[2]: r for r in source if len(r) > 8}
        tiers = part_tiers(source)
        changes, count = {}, 0
        for r, row in enumerate(rows):
            if len(row) < 9:
                continue
            src = by_id.get(row[2], row)
            level = int(float(src[7])) if src[7].replace('.', '', 1).isdigit() else 0
            grade = part_grade_rule(row[0], row[6], level, tiers)
            if grade and (row[7] != '0' or row[8] != str(grade)):
                changes[(r, 7)], changes[(r, 8)] = '0', str(grade)
                count += 1
        if not changes:
            print(f'{folder}/World.agt: ItemClient.tdf grades already set')
            continue
        files[k] = (files[k][0], tdf_set(data, changes))
        tmp = path + '.new'
        agt.write(tmp, header, files)
        raw = bytearray(open(tmp, 'rb').read())
        raw[20:32] = header[20:32]
        open(tmp, 'wb').write(bytes(raw))
        os.replace(tmp, path)
        print(f'{folder}/World.agt: ItemClient.tdf: {count} items show the required V grade (level 0)')


def set_kph(client):
    """Data_EU_<lang>/gameui/game.nui: the HUD speed labels T1="MPH" / "mph" -> "KPH" / "kph"."""
    for folder in FOLDER.values():
        path = os.path.join(client, folder, 'gameui', 'game.nui')
        if not os.path.exists(path):
            continue
        d = open(path, 'rb').read()
        n = d.count(b'T1="MPH"') + d.count(b'T1="mph"')
        if not n:
            print(f'{folder}/gameui/game.nui: speed labels already KPH')
            continue
        backup = os.path.join(HERE, '..', 'client_backup', f'game_{folder}.nui.orig')
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        tmp = path + '.new'
        open(tmp, 'wb').write(d.replace(b'T1="MPH"', b'T1="KPH"').replace(b'T1="mph"', b'T1="kph"'))
        os.replace(tmp, path)
        print(f'{folder}/gameui/game.nui: {n} speed labels KPH')


def make_us(client):
    """Client/DriftCityUS.exe: the original unpacked exe (the backup, else DriftCityEU.exe while unchanged), nation 1,
    GameGuard class 0."""
    src = BACKUP if os.path.exists(BACKUP) else os.path.join(client, EXE)
    if not os.path.exists(src):
        sys.exit(f'no unpacked exe: {os.path.normpath(BACKUP)} (or {EXE} in {client}) is needed')
    exe = bytearray(open(src, 'rb').read())
    if nation_of(exe) != 1:
        sys.exit(f'{src}: not the original nation 1 code (nothing written)')
    at = file_offset(exe, GG_CLASS_AT)
    if exe[at] not in (0, 2):
        sys.exit(f'{src}: unknown protection class {exe[at]} at {GG_CLASS_AT:#x} (nothing written)')
    exe[at] = 0
    dst = os.path.join(client, US_EXE)
    tmp = dst + '.tmp'
    open(tmp, 'wb').write(bytes(exe))
    shutil.copymode(src, tmp)
    os.replace(tmp, dst)
    print(f'{US_EXE}: from {os.path.basename(src)}, nation 1 (US), GameGuard off')


def main():
    args = sys.argv[1:]
    client = os.path.join(HERE, '..', '..', 'Client EU')
    if args and os.path.isdir(args[0]):
        client, args = args[0], args[1:]
    elif args and args[0] == 'us':
        client = os.path.join(HERE, '..', '..', 'Client US')
    if not args or args[0] not in ('setup', 'status', 'reset', 'us', 'f2', 'speedo', 'grades', 'kph'):
        sys.exit(__doc__)
    if args[0] == 'status':
        n = nation_of(open(os.path.join(client, EXE), 'rb').read())
        name = {v: k for k, v in NATIONS.items()}.get(n, '?')
        print(f'{EXE}: nation {n} ({name})' if n else f'{EXE}: unknown code at {NATION_AT:#x}')
        exe = open(os.path.join(client, EXE), 'rb').read()
        at = file_offset(exe, FILECHECK_AT)
        print(f'{EXE}: data file check (dname.chk)', 'skipped' if exe[at:at + 3] == FILECHECK_OFF else 'on')
        at = file_offset(exe, F2_AT)
        print(f'{EXE}: F2 car panel for EU nations', 'on' if exe[at:at + 4] == F2_US else 'off (EU design)')
        for lang, folder in FOLDER.items():
            if os.path.isdir(os.path.join(client, folder)):
                print(f'{folder}: present')
        return
    if args[0] == 'speedo':
        if len(args) > 1 and args[1].lower() == 'mph':
            return set_speedometer(client, None)
        return set_speedometer(client, tw_speedometer(args[1] if len(args) > 1 else TW_CLIENT))
    if args[0] == 'f2':
        if len(args) < 2 or args[1] not in ('on', 'off'):
            sys.exit('f2 on|off')
        return set_f2(client, args[1] == 'on')
    if args[0] == 'us':
        return make_us(client)
    if args[0] == 'grades':
        return set_grades(client)
    if args[0] == 'kph':
        return set_kph(client)
    if args[0] == 'reset':
        if not os.path.exists(BACKUP):
            sys.exit('no backup: the exe was never changed by this tool')
        shutil.copy2(BACKUP, os.path.join(client, EXE))
        print('original exe restored (nation 1, US)')
        return
    lang = args[1].lower() if len(args) > 1 else 'eng'
    if lang not in FOLDER:
        sys.exit(f'language: one of {", ".join(FOLDER)}')
    make_folder(client, lang)
    set_grades(client)
    set_kph(client)
    set_nation(client, NATIONS[lang])
    set_filecheck(client, True)
    set_f2(client, True)
    if os.path.exists(TW_SAVED):                         # the Km/h dial, once taken from the TW client
        set_speedometer(client, open(TW_SAVED, 'rb').read())


if __name__ == '__main__':
    main()
