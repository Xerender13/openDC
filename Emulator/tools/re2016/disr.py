import sys, re, bisect, pickle, os
f = sys.argv[3] if len(sys.argv) > 3 else 'text.dis'
idx = f + '.idx'
lines = open(f, errors='replace').read().split('\n')
if os.path.exists(idx):
    addrs = pickle.load(open(idx, 'rb'))
else:
    addrs = []
    for i, l in enumerate(lines):
        m = re.match(r'\s+([0-9a-f]+):\t', l)
        addrs.append(int(m.group(1), 16) if m else -1)
    # make monotone for bisect
    last = -1
    for i, a in enumerate(addrs):
        if a < 0: addrs[i] = last
        else: last = a
    pickle.dump(addrs, open(idx, 'wb'))
s, e = int(sys.argv[1], 16), int(sys.argv[2], 16)
i = bisect.bisect_left(addrs, s); j = bisect.bisect_left(addrs, e)
print('\n'.join(lines[i:j]))
