"""Prepare a separate experimental 2016 server data directory.

python -m tools.prepare2016 [--client '../DriftCity Dev Ed'] [--out server_data_2016]

Copies server defaults from server_data, then overlays the 2016 client's effective
tables and traffic. Refuses an existing destination so tuning is never overwritten.
This does not change the running emulator, client files, database, or version switch.
"""
import argparse
from pathlib import Path
import shutil
import tempfile

from .sync_data import HERE, sync


def prepare(client, baseline, out):
    client, baseline, out = map(Path, (client, baseline, out))
    if out.exists():
        raise ValueError(f'destination already exists: {out}')
    if not client.is_dir() or not baseline.is_dir():
        raise ValueError('client and baseline data directories must exist')
    # Build alongside the destination; a failed extraction cannot leave a usable-looking port.
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.prepare2016-', dir=out.parent) as tmp:
        staged = Path(tmp) / 'data'
        shutil.copytree(baseline, staged)
        # Do not silently retain 2011 client tables if the selected client is incomplete.
        from .client_tables import Client
        source = Client(str(client))
        for table in ('VehicleList.xlt', 'VehicleUpgrade.xlt', 'ItemClient.tdf', 'UseItemClient.tdf',
                      'VisualItem.xlt', 'VShopItem.xlt', 'QuestClient.tdf'):
            if source.find(table) is None:
                raise ValueError(f'2016 client is missing required table {table}')
        sync(str(client), str(staged))
        (staged / 'serverlist.txt').write_text(
            '2016 Dev2016 127.0.0.1 11111\t127.0.0.1 11121\t'
            '127.0.0.1 11131\t127.0.0.1 11141\t100\n', encoding='utf-8')
        from dcemu.native.data import Tables
        data = Tables(str(staged), str(staged / 'tables'), str(staged / 'adminlist.txt'))
        print(f'Validated {len(data.vehicles)} vehicles, {len(data.items)} parts, {len(data.quests)} quests')
        staged.rename(out)
    print(f'2016 data ready: {out}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, default=Path(HERE).parent / 'DriftCity Dev Ed')
    parser.add_argument('--baseline', type=Path, default=Path(HERE) / 'server_data')
    parser.add_argument('--out', type=Path, default=Path(HERE) / 'server_data_2016')
    args = parser.parse_args()
    prepare(args.client, args.baseline, args.out)


if __name__ == '__main__':
    main()
