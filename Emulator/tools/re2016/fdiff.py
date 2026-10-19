"""fdiff.py ADDR2011 ADDR2016 [len2011 len2016]: side-by-side diff of two functions (addresses normalized)."""
import sys, re, difflib, bisect, pickle, os
def lines_of(dis, start, end):
    lines = open(dis, errors='replace').read().split('\n') if dis not in cache else cache[dis]
    cache[dis] = lines
    idx = dis + '.idx'
    if idx in icache: addrs = icache[idx]
    elif os.path.exists(idx): addrs = icache[idx] = pickle.load(open(idx, 'rb'))
    else:
        addrs = []; last = -1
        for l in lines:
            m = re.match(r'\s+([0-9a-f]+):\t', l)
            if m: last = int(m.group(1), 16)
            addrs.append(last)
        pickle.dump(addrs, open(idx, 'wb')); icache[idx] = addrs
    i = bisect.bisect_left(addrs, start); j = bisect.bisect_left(addrs, end)
    return [l for l in lines[i:j] if '\t' in l and 'int3' not in l]
cache, icache = {}, {}
def norm(l):
    ins = l.split('\t')[-1].strip()
    ins = re.sub(r'0x[0-9a-f]{6,8}\b', 'ADDR', ins)       # absolute addresses / call targets
    return re.sub(r'\s+', ' ', ins)
def func_end(dis, start, maxlen=0x2000):
    ls = lines_of(dis, start, start + maxlen)
    for k, l in enumerate(ls):
        if re.search(r'\tc3\s|\tc2 [0-9a-f]{2} 00', l) and k + 1 < len(ls):
            nxt = int(ls[k + 1].split(':')[0], 16)
            # padding follows (int3 removed): a gap in addresses
            cur = int(l.split(':')[0], 16) + len(l.split('\t')[1].split())
            if nxt != cur: return cur
    return start + maxlen
a11, a16 = int(sys.argv[1], 16), int(sys.argv[2], 16)
e11 = a11 + int(sys.argv[3], 16) if len(sys.argv) > 3 else func_end('text.dis', a11)
e16 = a16 + int(sys.argv[4], 16) if len(sys.argv) > 4 else func_end('dev.dis', a16)
L = lines_of('text.dis', a11, e11); R = lines_of('dev.dis', a16, e16)
nl, nr = [norm(x) for x in L], [norm(x) for x in R]
sm = difflib.SequenceMatcher(None, nl, nr, autojunk=False)
print(f'2011 {a11:#x}-{e11:#x} ({len(L)} ins) vs 2016 {a16:#x}-{e16:#x} ({len(R)} ins), ratio {sm.ratio():.2f}')
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == 'equal': continue
    for k in range(max(i2 - i1, j2 - j1)):
        left = L[i1 + k].split(':')[0].strip() + ' ' + nl[i1 + k] if i1 + k < i2 else ''
        right = R[j1 + k].split(':')[0].strip() + ' ' + nr[j1 + k] if j1 + k < j2 else ''
        print(f'  {left[:70]:70} | {right[:70]}')
