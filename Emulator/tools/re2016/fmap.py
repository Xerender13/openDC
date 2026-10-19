"""fmap.py ADDR2011...: the matching 2016 function and the instructions that differ only in their numbers."""
import pickle, difflib, sys
from collections import defaultdict
F11 = pickle.load(open('f2011.pkl', 'rb'))
F16 = pickle.load(open('f2016.pkl', 'rb'))
IDX = defaultdict(list)
for a, ins in F16.items():
    IDX[tuple(s for _, s, _ in ins[:5])].append(a)
def shapes(ins): return [s for _, s, _ in ins]
import bisect
_K11 = sorted(F11)
def start_of(addr):
    i = bisect.bisect_right(_K11, addr) - 1
    return _K11[i] if i >= 0 else None
def match(a):
    a = a if a in F11 else start_of(a)
    ins = F11.get(a)
    if not ins:
        return None, 0.0
    sh = shapes(ins)
    cands = IDX.get(tuple(sh[:5]), [])
    if len(cands) > 400 or not cands:
        cands = [b for b, i in F16.items() if abs(len(i) - len(ins)) <= max(3, len(ins) // 5)
                 and i[:2] and [s for _, s, _ in i[:2]] == sh[:2]]
    best, br = None, 0.0
    for b in cands:
        r = difflib.SequenceMatcher(None, sh, shapes(F16[b]), autojunk=False).ratio()
        if r > br:
            best, br = b, r
    return best, br
def offsets(a, b):
    L, R = F11[a], F16[b]
    sm = difflib.SequenceMatcher(None, shapes(L), shapes(R), autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                if L[i1 + k][2] != R[j1 + k][2]:
                    out.append((L[i1 + k][0], L[i1 + k][2], R[j1 + k][0], R[j1 + k][2]))
    return out
if __name__ == '__main__':
    for x in sys.argv[1:]:
        a = int(x, 16)
        a = a if a in F11 else start_of(a)
        b, r = match(a)
        print(f'== {a:#x} -> {b and hex(b)} ({r:.2f})')
        if b:
            for la, lt, ra, rt in offsets(a, b):
                if 'ADDR' in lt or ('call' in lt or 'j' == lt[0]):
                    continue
                print(f'   {la:#x} {lt:45} | {ra:#x} {rt}')
