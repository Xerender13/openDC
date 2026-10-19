"""Message sizes, 2011 against 2016: the size each S>C handler returns (mov ax, imm), for every type in both exes.
Needs handlers_2011.json (2011 registrations) and handlers_2016.json in the working folder (see README.md)."""
import os, re, struct, json
ROOT = os.environ.get('DC_ROOT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
def load(path, secs):
    d = open(path, 'rb').read()
    def off(va):
        for vs, fo, sz in secs:
            if vs <= va < vs + sz: return va - vs + fo
    return d, off
def body(d, o):
    """bytes of the function at file offset o: up to a run of int3 / padding."""
    e = d.find(b'\xcc\xcc', o)
    e2 = d.find(b'\x90\x90\x90', o)
    ends = [x for x in (e, e2) if x > o]
    return d[o:min(ends) if ends else o + 0x800][:0x1000]
def sizes(d, off, h):
    b = body(d, off(h))
    vals = sorted({struct.unpack_from('<H', b, m.start() + 2)[0] for m in re.finditer(rb'\x66\xb8..', b, re.S)})
    return vals, len(b)
us = load(os.path.join(ROOT, 'Client US', 'DriftCityUS.exe'), [(0x401000, 0x400, 0x4c5c00)])
dev = load(os.path.join(ROOT, 'DriftCity Dev Ed', 'DriftCity.exe'),
           [(0x401000, 0x400, 0x540a00), (0x942000, 0x540e00, 0x79000)])
h11 = {int(k): v for k, v in json.load(open('handlers_2011.json')).items()}
h16 = {int(k, 16): (int(v[0], 16), v[1]) for k, v in json.load(open('handlers_2016.json')).items()}
rows = []
for t in sorted(set(h11) | set(h16)):
    s11 = sizes(*us, h11[t])[0] if t in h11 else None
    s16 = sizes(*dev, h16[t][0])[0] if t in h16 else None
    rows.append((t, h16[t][1] if t in h16 else '', s11, s16))
json.dump(rows, open('size_cmp.json', 'w'))
only11 = [r for r in rows if r[2] is not None and r[3] is None]
only16 = [r for r in rows if r[3] is not None and r[2] is None]
both = [r for r in rows if r[2] is not None and r[3] is not None]
same = [r for r in both if r[2] == r[3]]
diff = [r for r in both if r[2] != r[3]]
print(f'types: 2011 {len(h11)}, 2016 {len(h16)}, both {len(both)}, same sizes {len(same)}, different {len(diff)}, '
      f'only 2011 {len(only11)}, only 2016 {len(only16)}')
print('DIFF:'); [print(f'  {r[0]:#06x} {r[1]:32} 2011 {[hex(x) for x in r[2]]} 2016 {[hex(x) for x in r[3]]}') for r in diff]
print('ONLY 2016:', ', '.join(f'{r[0]:#x} {r[1]}' for r in only16))
print('ONLY 2011:', ', '.join(f'{r[0]:#x}' for r in only11))
