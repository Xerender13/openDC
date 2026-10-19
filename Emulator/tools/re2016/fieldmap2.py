"""fieldmap2.py GETTER2011 [maxoff] [reg]: like fieldmap, but only [eax+X] reads right after `call GETTER` (until eax is
written), so the offsets are fields of the getter's result."""
import re, sys, difflib
from collections import Counter, defaultdict
import fmap
getter = int(sys.argv[1], 16)
maxoff = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x400
def uses(ins, k):
    """indices of the instructions after k that read [eax+X] before eax is written."""
    out = []
    for j in range(k + 1, min(k + 12, len(ins))):
        t = ins[j][2]
        if re.search(r'\[eax\+0x[0-9a-f]+\]', t):
            out.append(j)
        dst = t.split(' ', 1)[1].split(',')[0] if ' ' in t else ''
        if dst.strip() in ('eax', 'ax', 'al') or t.startswith('call') or t.startswith('ret') or t.startswith('j'):
            break
    return out
callers = sorted({fmap.start_of(a) for f in fmap.F11.values() for a, _, i in f if i == f'call {getter:#x}'} - {None})
pairs = defaultdict(Counter); done = 0
for a in callers:
    b, r = fmap.match(a)
    if not b or r < 0.8:
        continue
    done += 1
    L, R = fmap.F11[a], fmap.F16[b]
    sm = difflib.SequenceMatcher(None, fmap.shapes(L), fmap.shapes(R), autojunk=False)
    amap = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                amap[i1 + k] = j1 + k
    for k, (_, _, t) in enumerate(L):
        if t != f'call {getter:#x}' or k not in amap:
            continue
        for j in uses(L, k):
            if j not in amap:
                continue
            x = re.findall(r'\[eax\+0x([0-9a-f]+)\]', L[j][2]); y = re.findall(r'\[eax\+0x([0-9a-f]+)\]', R[amap[j]][2])
            if x and y and int(x[0], 16) < maxoff:
                pairs[int(x[0], 16)][int(y[0], 16)] += 1
print(f'{len(callers)} callers, {done} matched')
for x in sorted(pairs):
    top = pairs[x].most_common(2)
    print(f'  {x:#06x} -> ' + ', '.join(f'{y:#06x} ({n})' for y, n in top) + f'   {top[0][0] - x:+#x}')
