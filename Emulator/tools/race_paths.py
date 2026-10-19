"""Race traffic paths for the battle zone tracks that have none: server_data/race/PVP_map<city>_<NN>.index from the
client's own Data/World/<city>.agt PVP_map<city>_<NN>.chpath (the client places the 0x21e cars on that file, path by
path, so the server's paths must be the same ones in the same order).

The 2008 server's .index files exist for the 2008 tracks only; Server2008/tools/make_traffic_paths.py made the others
from the client, but its fixed-offset chpath reader breaks on the chunked layout of the newer files (2011 tracks
koinonia_track11 / 12, cras_track11 / 12, oros_track9 / 10, moonpalace_track12_r, the Taipei tracks, and the 2016
tracks ported by port2016.py). Here: the chunked layout (city_traffic.read_chpath's walk: chunk 0x200 per path, 0x211
+12 = total progress, 0x220 = u32 count + (progress, x, y, z) floats), points resampled to one per progress unit as
make_traffic_paths does (progress = travel time at 100 km/h, the .index unit). Only tracks without an .index are
written (the existing files stay); a chpath without paths (taipei_track2, PVP_map5_03) gets none.

Taipei (city 5) also needs trafficCarSettingForTrack_5.txt (the 2008 server had none: no Taipei): the models of
TrafficFlowControl.xlt's Taipei block (city_traffic.car_models, as the Taipei city traffic), 500 cars at most.

usage: python3 -m tools.race_paths [client dir, default ../Client US] [--all]   (--all rewrites every chunked file)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'tools'))
import agt                                                    # noqa: E402
from dcemu.native.city_traffic import car_models             # noqa: E402

WORLDS = {1: 'moonpalace', 2: 'koinonia', 3: 'cras', 4: 'oros', 5: 'taipei'}
OUT = os.path.join(HERE, 'server_data', 'race')


def read_chpath(data):
    """Chunked .chpath -> [(total, [(progress, x, y, z), ..])] by path index."""
    def chunks(o, end):
        while o + 7 <= end:
            tag, _, size = struct.unpack_from('<HBI', data, o)
            if size < 7:
                return
            yield tag, o + 7, o + size
            o += size
    paths = []
    for tag, a, b in chunks(0x2a, len(data)):
        if tag != 0x200:
            continue
        sub = {t: (x, y) for t, x, y in chunks(a + 1, b)}
        total, = struct.unpack_from('<f', data, sub[0x211][0] + 12)
        o = sub[0x220][0]
        n, = struct.unpack_from('<I', data, o)
        paths.append((total, [struct.unpack_from('<4f', data, o + 4 + 16 * i) for i in range(n)]))
    return paths


def resample(total, pts):
    """x, y, z at progress 0, 1, 2, ... up to total, interpolated on the points' progress (make_traffic_paths)."""
    out, k = [], 0
    for t in range(int(total) + 1):
        while k < len(pts) - 2 and pts[k + 1][0] <= t:
            k += 1
        a, b = pts[k], pts[min(k + 1, len(pts) - 1)]
        f = min(max((t - a[0]) / (b[0] - a[0]), 0.0), 1.0) if b[0] > a[0] else 0.0
        out.append(tuple(a[i] + (b[i] - a[i]) * f for i in (1, 2, 3)))
    return out


def write_index(path, src, paths):
    lines = [f'// traffic paths generated from client {src} (tools/race_paths.py)', '//',
             '// id start end unused unused points', str(len(paths))]
    for i, (total, pts) in enumerate(paths):
        pts = resample(total, pts) if len(pts) > 1 else [p[1:] for p in pts]
        lines.append(f'{i} 0.0000 {total:.4f} 0 0 {len(pts)}')
        lines += [f'{x:.3f} {y:.3f} {z:.3f}' for x, y, z in pts]
    with open(path, 'w', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')


def taipei_cars():
    path = os.path.join(OUT, 'trafficCarSettingForTrack_5.txt')
    if os.path.exists(path):
        return None
    models = car_models(os.path.join(HERE, 'server_data', 'Init', 'TrafficFlowControl.xlt')).get(5) or []
    if not models:
        return None
    with open(path, 'w', newline='\r\n') as f:
        f.write('500  // Taipei: TrafficFlowControl.xlt (tools/race_paths.py)\n')
        f.write(''.join(f'{m + 20001}\t{w}\n' for m, w in models))
    return path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    client = args[0] if args else os.path.join(HERE, '..', 'Client US')
    rewrite = '--all' in sys.argv
    written, empty = [], []
    for city, name in WORLDS.items():
        _, files = agt.read(os.path.join(client, 'Data', 'World', name + '.agt'))
        for entry, data in files:
            base = entry.rsplit('\\', 1)[-1]
            if not base.lower().startswith(f'pvp_map{city}_') or not base.lower().endswith('.chpath'):
                continue
            out = os.path.join(OUT, f'PVP_map{city}_{base[9:-7]}.index')
            if os.path.exists(out) and not (rewrite and 'race_paths' in open(out, errors='replace').readline()):
                continue
            try:
                paths = read_chpath(data)
            except (KeyError, struct.error, IndexError):
                paths = []
            if not paths:
                empty.append(base)
                continue
            write_index(out, entry, paths)
            written.append(f'{os.path.basename(out)} ({len(paths)} paths)')
    cars = taipei_cars()
    print(len(written), 'written:', ', '.join(written) or '-')
    if empty:
        print('no paths in:', ', '.join(empty))
    if cars:
        print('written:', os.path.basename(cars))


if __name__ == '__main__':
    main()
