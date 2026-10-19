"""Function index of a disassembly: start -> list of (addr, shape, text). Shape = the instruction with numbers
masked, so the same code with other field offsets / addresses matches."""
import re, pickle, os, sys
def build(dis, out):
    funcs = {}
    cur, prev_pad = None, True
    for l in open(dis, errors='replace'):
        m = re.match(r'\s+([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(.*)$', l)
        if not m:
            continue
        addr, ins = int(m.group(1), 16), m.group(3).strip()
        if ins in ('int3', 'nop') or ins.startswith('lea    esi,[esi') or ins.startswith('lea    ecx,[ecx+0x0]'):
            prev_pad = True
            continue
        if prev_pad:
            cur = addr
            funcs[cur] = []
            prev_pad = False
        text = re.sub(r'\s+', ' ', ins)
        shape = re.sub(r'0x[0-9a-f]+', '#', text)
        funcs[cur].append((addr, shape, text))
        if re.match(r'(ret|jmp )', text) and False:
            pass
    pickle.dump(funcs, open(out, 'wb'))
    return funcs
if __name__ == '__main__':
    for dis, out in (('text.dis', 'f2011.pkl'), ('dev.dis', 'f2016.pkl')):
        if not os.path.exists(out):
            f = build(dis, out)
            print(out, len(f))
