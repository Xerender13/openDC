"""2011 -> 2016 protocol check against the client build timeline (https://timeline.slide.town/).

The timeline page embeds a JSON list of client builds with, per build, the message handlers added / removed and the
handler size checks that changed since its base build. Our clients are two of them: 2011-10-27 US 0.29c (Client US,
Client EU: same PE date) and 2016-02-16 US 0.77a QA (DriftCity Dev Ed). Walking the base chain between them gives the
net size change of every S>C message; this tool prints each one with its type (handlers_2016.json) and, for the types
the 2016 server has sent, whether the newest log that has them agrees.

    .venv/bin/python -m tools.re2016.timeline_audit [--data timeline.html|data.json] [--logs 'logs/2016/*.msgs.txt']

Without --data the page is downloaded. Logged sizes include the 2-byte length (dataset size = logged - 2). A logged
frame can be a bundle under its first type's name (0x191 + 0x1a5, the game service's 0x1e), so check a mismatch in
the code before believing it. Also listed: messages new between the two builds that the emulator never builds.
"""
import argparse
import collections
import glob
import json
import os
import re
import urllib.request

URL = 'https://timeline.slide.town/'
OLD, NEW = '2011-10-27', '2016-02-16'
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load(path):
    text = open(path, encoding='utf-8').read() if path else urllib.request.urlopen(URL).read().decode('utf-8')
    if text.lstrip().startswith('{'):
        return json.loads(text)
    return json.loads(re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', text, re.S).group(1))


def chain(data):
    builds = {b['label']: b for b in data['builds']}
    out, label = [], NEW
    while label != OLD:
        out.append(builds[label])
        label = builds[label]['base']
    return out[::-1]


def net_sizes(steps):
    net = {}
    for b in steps:
        for name, way, old, new in b['diff'].get('sizes', []):
            net.setdefault((name, way), [old, new])[1] = new
    return net


def fits(size, expr):
    """'0x60*n + 0xa' or '54', alternatives split by ' / '."""
    for alt in expr.split(' / '):
        m = re.match(r'0x([0-9a-f]+)\*n \+ 0x([0-9a-f]+)$', alt.strip())
        if m:
            k, c = int(m[1], 16), int(m[2], 16)
            if size >= c and (size - c) % k == 0:
                return True
        elif int(alt) == size:
            return True
    return False


def newest_sizes(pattern):
    """(type) -> (log name, Counter of sizes) from the newest log that has the type, game service S>C only."""
    rx = re.compile(r'#\d+ game +S>C\*? +0x([0-9a-f]{4}) +(\d+)')
    latest = {}
    for path in sorted(glob.glob(pattern)):
        seen = collections.defaultdict(collections.Counter)
        for line in open(path, errors='replace'):
            m = rx.search(line)
            if m:
                seen[int(m[1], 16)][int(m[2]) - 2] += 1
        for t, sizes in seen.items():
            latest[t] = (os.path.basename(path), sizes)
    return latest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data')
    ap.add_argument('--logs', default=os.path.join(ROOT, 'logs/2016/*.msgs.txt'))
    args = ap.parse_args()
    steps = chain(load(args.data))
    handlers = json.load(open(os.path.join(HERE, 'handlers_2016.json')))
    types = {name: int(t, 16) for t, (_, name) in handlers.items()}
    src = ''.join(open(f).read() for f in glob.glob(os.path.join(ROOT, 'dcemu/**/*.py'), recursive=True))
    built = lambda t: re.search(r'Frame\(\s*0x0*%x\b' % t, src) is not None
    logged = newest_sizes(args.logs)

    print(f'S>C size changes {OLD} -> {NEW} (via {", ".join(b["label"] for b in steps[:-1])})')
    for (name, way), (old, new) in sorted(net_sizes(steps).items()):
        t = int(name[1:]) if name.startswith('#') else types.get(name)
        if way != 'in' or t is None:
            continue
        if t in logged:
            log, sizes = logged[t]
            bad = {s: n for s, n in sizes.items() if not fits(s, new)}
            state = f'MISMATCH {dict(bad)} ({log})' if bad else 'ok in log'
        else:
            state = 'built, not in a log' if built(t) else 'not built'
        print(f'  {t:#06x} {name:34s} {old:>14s} -> {new:<14s} {state}')
    print('\nS>C messages new since 2011 that the emulator never builds:')
    for b in steps:
        for name in b['diff'].get('recvAdded', []):
            t = types.get(name)
            if t is not None and not built(t):
                print(f'  {b["label"]} {t:#06x} {name}')


if __name__ == '__main__':
    main()
