"""Copy the 2011 client's effective tables (patches applied, US over base) to the native
server's data directory (server_data), unchanged: Init/*.xlt -> Init/ and World/*.tdf -> tables/ (next to
the 2008 server's own tables); and the cities' traffic data
(city_traffic.py) from the city packs Data/World/<city>.agt: tables/<City>/<city>.tcs (lanes and
signals) and tables/<City>/Path/*.chpath / *.signal (path traffic; Taipei has no .tcs), a patch's
version where Patch.0xx has one; the built-in crew marks Data_US/gameui/teammark/01-10 -> teammark/ (crews.py).

usage: python3 -m tools.sync_data [client dir, default ../Client] [data dir, default server_data]
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'tools'))
from client_tables import Client   # noqa: E402
import agt                         # noqa: E402


def main():
    client = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'Client')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'server_data')
    c = Client(client)
    names = {p.rsplit('\\', 1)[-1] for p in c.files if p.endswith(('.xlt', '.tdf'))
             and ('\\init\\' in p or '\\world\\data\\' in p)}
    n = 0
    for name in sorted(names):
        path = c.find(name)
        sub = 'Init' if '\\init\\' in path else 'tables'
        os.makedirs(os.path.join(out, sub), exist_ok=True)
        real = c.files[path][2][0].rsplit('\\', 1)[-1]     # the client's spelling (the index is lower case)
        open(os.path.join(out, sub, real), 'wb').write(c.read(name))
        n += 1
    print(f'{n} tables -> {out}')
    print(f'{sync_traffic(client, c, out)} city traffic files -> {os.path.join(out, "tables")}')
    marks = os.path.join(client, 'Data_US', 'gameui', 'teammark')
    if os.path.isdir(marks):
        import shutil
        os.makedirs(os.path.join(out, 'teammark'), exist_ok=True)
        for f in sorted(os.listdir(marks)):
            shutil.copyfile(os.path.join(marks, f), os.path.join(out, 'teammark', f))
        print(f'{len(os.listdir(marks))} crew marks -> {os.path.join(out, "teammark")}')


CITY_PACKS = ['moonpalace', 'koinonia', 'cras', 'oros', 'neooros', 'taipei']


def sync_traffic(client, c, out):
    n = 0
    for pack in CITY_PACKS:
        path = os.path.join(client, 'Data', 'World', pack + '.agt')
        if not os.path.exists(path):
            continue
        raw, entries = agt.index(path)
        for e in entries:
            name = e[0]
            if not name.lower().endswith(('.tcs', '.chpath', '.signal')):
                continue
            patched = c.files.get(('data\\world\\' + name).lower())
            data = agt.extract(patched[1], patched[2]) if patched else agt.extract(raw, e)
            dst = os.path.join(out, 'tables', *name.split('\\'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(data)
            n += 1
    return n


if __name__ == '__main__':
    main()
