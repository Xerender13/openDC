"""First start: the server tables that come from the game client (not in git), copied from the user's client.

python -m tools.client_setup [-c emulator.ini] [--client DIR] [--check] [--refresh]

The repository holds only the tables the client does not have (the 2008 server's own, and server_data/Init plus
UseItemClient.tdf, which tools/port2016.py wrote). The rest of tables/ (ItemClient.tdf, QuestClient.tdf, ...,
the city traffic) and teammark/ are copied from a client: the 2011 US client for [client] version = 2011
(server_data), the 2016 client (DriftCity Dev Ed) for version = 2016 (data_2016). The config picks which.

If those files are there, nothing happens. Otherwise the client folder is asked for (in a terminal), or taken
from --client, $DCEMU_CLIENT, /client (the Docker container's mount) or the default folder next to Emulator/.
The tables are extracted to a temporary folder and only missing files are copied: a file in git is never
replaced. --refresh (after a client patch) also replaces the copied client files, still not the ones in git.
--check only reports: exit status 0 when the tables are complete, 1 when they are missing.
"""
import argparse
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time

from .sync_data import HERE, sync

# client-derived files that are in git and keep their ported version (tools/port2016.py)
PORTED = {'UseItemClient.tdf'}
# files that show a complete copy; the server stops without them
REQUIRED = ['ItemClient.tdf', 'QuestClient.tdf', 'Instant_Client.tdf', 'Tutorial.tdf']
GAME_EXES = ['DriftCityUS.exe', 'DriftCityEU.exe', 'DriftCity.exe']
DEFAULT_CLIENT = {'2011': Path(HERE).parent / 'Client US', '2016': Path(HERE).parent / 'DriftCity Dev Ed'}


def paths(config):
    """(version, data dir, tables dir) of an emulator config, as the emulator resolves them."""
    from dcemu.__main__ import load_config
    cp = load_config(config)
    version = cp['client']['version'].strip()
    if version == '2016':
        data = Path(HERE) / cp['client']['data_2016']
        return version, data, data / 'tables'
    return '2011', Path(HERE) / cp['native']['data'], Path(HERE) / cp['native']['server_data']


def missing(data, tables):
    out = [f'tables/{n}' for n in REQUIRED if not (tables / n).is_file()]
    marks = data / 'teammark'
    if not marks.is_dir() or not any(marks.iterdir()):
        out.append('teammark/')
    return out


def exe_year(client):
    """Build year of the client's game exe (PE header time stamp), or None."""
    for name in GAME_EXES:
        path = Path(client) / name
        if path.is_file():
            with open(path, 'rb') as f:
                head = f.read(4096)
            try:
                pe = struct.unpack_from('<I', head, 0x3c)[0]
                return time.gmtime(struct.unpack_from('<I', head, pe + 8)[0]).tm_year
            except struct.error:
                return None
    return None


def check_client(client, version):
    """None if the folder is a usable client for this version, else why not. Warnings are printed."""
    client = Path(client)
    if not client.is_dir():
        return f'{client} is not a folder'
    from .client_tables import Client
    try:
        c = Client(str(client))
    except Exception as e:     # a damaged or foreign archive
        return f'cannot read the client packs in {client}: {e}'
    lost = [n for n in REQUIRED + ['VehicleList.xlt'] if c.find(n) is None]
    if lost:
        return f'{client} does not look like a Drift City client (no {", ".join(lost)})'
    year = exe_year(client)
    if year is not None and (year >= 2016) != (version == '2016'):
        return f'{client} is a {year} client, but the server is set to version {version} ([client] version)'
    if not (client / 'Data_US').is_dir():
        print(f'note: {client} has no Data_US folder; the tables come from its base packs (the US client is the '
              f'reference for the server)')
    return None


def candidates(version, given):
    if given:
        return [Path(given)]
    out = [Path(p) for p in (os.environ.get('DCEMU_CLIENT'), '/client') if p]
    return out + [DEFAULT_CLIENT[version]]


def ask_client(version, given):
    """The client folder: the first usable candidate, confirmed or replaced in a terminal."""
    found = None
    for c in candidates(version, given):
        if c.is_dir() and check_client(c, version) is None:
            found = c
            break
    if given or not sys.stdin.isatty():
        if found is None:
            why = check_client(candidates(version, given)[0], version)
            raise SystemExit(f'client_setup: no usable {version} client folder ({why}).\n'
                             f'Run it in a terminal to be asked, or pass --client DIR '
                             f'(Docker: set DCEMU_CLIENT_DIR to the client folder).')
        return found
    print(f'The server needs the tables of the Drift City {version} client (they are not in git).')
    while True:
        hint = f' [{found}]' if found else ''
        answer = input(f'Client folder{hint}: ').strip().strip('"\'')
        if not answer and found:
            return found
        if not answer:
            continue
        why = check_client(Path(answer).expanduser(), version)
        if why is None:
            return Path(answer).expanduser()
        print(why)


def install(client, data, refresh):
    """Extract the client's tables next to data and copy them in: missing files, or (refresh) all but git's."""
    data.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.client_setup-', dir=data.parent) as tmp:
        staged = Path(tmp) / 'data'
        sync(str(client), str(staged))
        added = replaced = 0
        for sub in ('tables', 'teammark'):       # never Init/: it is in git (the port2016 tables)
            for src in sorted((staged / sub).rglob('*')):
                if not src.is_file():
                    continue
                dst = data / src.relative_to(staged)
                if dst.exists() and (not refresh or (sub == 'tables' and src.name in PORTED)):
                    continue
                replaced += dst.exists()
                added += not dst.exists()
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
    print(f'{added} files added, {replaced} replaced in {data}')


def validate(data, tables):
    from dcemu.native.data import Tables
    t = Tables(str(data), str(tables), str(data / 'adminlist.txt'))
    print(f'tables ok: {len(t.vehicles)} vehicles, {len(t.items)} parts, {len(t.quests)} quests')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', '--config', default=os.path.join(HERE, 'emulator.ini'))
    parser.add_argument('--client', help='the client folder (default: ask, or the usual folder)')
    parser.add_argument('--check', action='store_true', help='only report whether the tables are complete')
    parser.add_argument('--refresh', action='store_true', help='copy the tables again (after a client patch)')
    args = parser.parse_args()
    version, data, tables = paths(args.config)
    lost = missing(data, tables)
    if args.check:
        print(f'client tables ({version}, {data.name}): ' + (f'missing {", ".join(lost)}' if lost else 'complete'))
        sys.exit(1 if lost else 0)
    if not lost and not args.refresh:
        return
    if version == '2016' and not (data / 'Init' / 'VehicleList.xlt').is_file():
        raise SystemExit(f'client_setup: {data} has no Init tables; they are in git (git checkout), '
                         f'or build the folder with python -m tools.prepare2016')
    if lost:
        print(f'client tables ({version}) missing in {data}: {", ".join(lost)}')
    client = ask_client(version, args.client)
    print(f'copying the tables of {client}')
    install(client, data, args.refresh)
    validate(data, tables)


if __name__ == '__main__':
    main()
