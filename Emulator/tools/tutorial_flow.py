"""Select the guided apprentice tutorial in the local 2011/2016 clients.

python -m tools.tutorial_flow [--mode 1|4] [--only 2011|2016]
Mode 1: drive through Driver Dome and follow the tutorial prompts.
Mode 4 (the shipped US/Dev Ed value): jump directly to Battle Zone, bypass the opening prompts.
The server's Main.Apprentice flag still decides whether new drivers use apprentice training at all.
Backs up each current target under client_backup/tutorial_flow before the first write. Restart the
client to reload its GlobalContent table. Patches one comparison byte in the local 2011 exes and 2016 test copy so guided
Battle Zone entry skips the Tutorial button. The 2016 original and Origin stay untouched.
The table and the exe byte must agree: a guided exe with table mode 4 opens the Battle Zone window as soon
as the training car is in Driver Dome (2016 0x5ca8ed jne -> 0x5ca914). --only changes one client version.
"""
import argparse
from pathlib import Path
import shutil

from . import global_content

ROOT = Path(__file__).resolve().parents[2]
BACKUPS = ROOT / 'Emulator/client_backup/tutorial_flow'
COLUMNS = ('Value_US', 'Value_EU_de', 'Value_EU_eng', 'Value_EU_fr', 'Value_EU_es')


def change_table(data, mode):
    if mode not in (1, 4):
        raise ValueError('tutorial flow mode must be 1 (guided) or 4 (direct)')
    text = data.decode('utf-16-le')
    lines = text.split('\r\n')
    header = lines[2].split('\t')
    columns = [header.index(name) for name in COLUMNS]
    found = 0
    for i, line in enumerate(lines):
        cells = line.split('\t')
        if len(cells) > max(columns) and cells[3] == 'ApprenticeFlowType':
            for col in columns:
                cells[col] = str(mode)
            lines[i] = '\t'.join(cells)
            found += 1
    if found != 1:
        raise ValueError('expected exactly one ApprenticeFlowType row')
    return '\r\n'.join(lines).encode('utf-16-le')


def backup(path, label):
    dest = BACKUPS / label
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(path, dest)


# Select the existing native race-start branch when guided mode reaches Battle Zone.
# Driver Dome routing and in-race prompts still read mode1. Mode4 keeps its original branch.
START_BRANCH = {2011: (0x5a3a86-0x400c00, bytes.fromhex('83f8047518')),
                2016: (0x5ca8ed-0x400c00, bytes.fromhex('83f8047522'))}


def patch_start_branch(data, year, mode=1):
    off, expected = START_BRANCH[year]
    current = data[off:off+len(expected)]
    if current not in (expected, expected[:2]+b'\x01'+expected[3:]):
        raise ValueError(f'unsupported {year} apprentice start branch')
    out = bytearray(data)
    out[off+2] = mode
    return bytes(out)


ENTRY_2016 = 'Localize\\GlobalContent.xlt'       # in Data/Localize.agt (tools/pack_client.py)


def packed_table(client):
    """The 2016 client's GlobalContent.xlt in Data/Localize.agt, or None (the shipped empty pack)."""
    from . import agt
    pack = Path(client)/'Data/Localize.agt'
    if not pack.exists():
        return None
    raw, entries = agt.index(pack)
    return next((agt.extract(raw, e) for e in entries if e[0].lower() == ENTRY_2016.lower()), None)


def guided_mode(client):
    """ApprenticeFlowType (Value_US) as the client reads it: the packed table first (NiFile::NiFile), else the loose one."""
    table = Path(client)/'Data/Localize/GlobalContent.xlt'
    data = packed_table(client)
    lines = (data if data is not None else table.read_bytes()).decode('utf-16-le').split('\r\n')
    col = lines[2].split('\t').index('Value_US')
    row = next(l.split('\t') for l in lines if len(l.split('\t')) > col
               and l.split('\t')[3] == 'ApprenticeFlowType')
    return int(row[col])


def patch_executable(path, year, mode):
    if not path.exists():
        return
    current = path.read_bytes()
    updated = patch_start_branch(current, year, mode)
    if current != updated:
        backup(path, path.parent.name.replace(' ', '_')+'_'+path.name+'.before_start_skip')
        tmp = path.with_suffix('.exe.tmp')
        tmp.write_bytes(updated)
        tmp.chmod(path.stat().st_mode)
        tmp.replace(path)
    print(f'{path.name}: guided Battle Zone button bypass {mode == 1}')


def apply(mode=1, only=None):
    for name in ('Client US', 'Client EU') if only != 2016 else ():
        client = ROOT / name
        path = client / global_content.PACK
        if not path.exists():
            continue
        files, _ = global_content.load(str(client))
        current = dict(files)[global_content.ENTRY]
        updated = change_table(current, mode)
        if current != updated:
            backup(path, name.replace(' ', '_') + '_Patch.000.before')
            old_header = path.read_bytes()[20:32]
            global_content.write_pack(str(client), [(n, updated if n == global_content.ENTRY else b)
                                                   for n, b in files])
            assert path.read_bytes()[20:32] == old_header
        print(f'{name}: apprentice flow {mode}')
        exe = 'DriftCityUS.exe' if name == 'Client US' else 'DriftCityEU.exe'
        patch_executable(client/exe, 2011, mode)
    dev = ROOT / 'DriftCity Dev Ed'
    path = dev / 'Data/Localize/GlobalContent.xlt'
    packed = packed_table(dev) if dev.exists() else None
    if (path.exists() or packed is not None) and only != 2011:
        # the packed copy is the one the client reads (tools/pack_client.py); a loose one (before pack_client clean)
        # is kept the same
        if packed is not None:
            updated = change_table(packed, mode)
            if updated != packed:
                from .pack_client import replace_entry
                backup(dev / 'Data/Localize.agt', '2016_Localize.agt.before')
                replace_entry(dev / 'Data/Localize.agt', ENTRY_2016, updated)
        if path.exists():
            current = path.read_bytes()
            updated = change_table(current, mode)
            if current != updated:
                backup(path, '2016_GlobalContent.xlt.before')
                tmp = path.with_suffix('.xlt.tmp')
                tmp.write_bytes(updated)
                tmp.replace(path)
        print(f'Dev Ed 2016: apprentice flow {mode}')
        patch_executable(ROOT/'DriftCity Dev Ed/DriftCity2016Test.exe', 2016, mode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', type=int, choices=(1, 4), default=1)
    parser.add_argument('--only', type=int, choices=(2011, 2016), help='change only this client version')
    args = parser.parse_args()
    apply(args.mode, args.only)
