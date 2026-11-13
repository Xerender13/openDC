#!/usr/bin/env python3
"""C>S message types and body sizes of both Drift City clients, against the emulator's handlers.

A 2011/2016 sender allocates its message with
    push SIZE ; (mov ecx, ...) ; call 0x807450          (2016: call 0x86c800)
and writes the type into the returned buffer:
    mov WORD PTR [reg],0xNNN
So: every alloc call is paired with the nearest following type write in the same function (functions
end at int3 padding); the size is the nearest push before the alloc (imm -> size, register/memory ->
'var', none found -> '?'). Type writes with no alloc before them in the function (body built in a
helper) and allocs with no type write after them are reported too.

Usage:
  python3 Emulator/tools/re2016/sender_sizes.py --dis11 us.dis --dis16 dev.dis --out DIR
Writes DIR/senders.json and DIR/report.txt. The emulator handlers come from the @on(...) decorators
and on(...)(handler) registrations under --src (default: dcemu next to this tool).

Evidence, not guesses: every size/address in the report is an instruction address in the given .dis
files; every handler is a registration in the emulator sources at the time of the run.
"""
import argparse
import ast
import json
import os
import re
import sys

ALLOC = {'11': 0x807450, '16': 0x86c800}          # the client's message allocator (call target)
TYPE_RE = re.compile(r'^mov WORD PTR \[([a-z][a-z0-9]*)(?:\+0x0)?\],(0x[0-9a-f]+)$')
PUSH_IMM = re.compile(r'^push (0x[0-9a-f]+)$')
SKIP_BACK = ('mov ', 'lea ', 'xor ', 'and ', 'or ', 'cmp ', 'test ', 'movzx ', 'movsx ', 'inc ', 'dec ')
VAR, UNKNOWN = 'var', '?'


def instructions(path):
    """(addr, nbytes, text) of every instruction line of an objdump -D -M intel disassembly.
    objdump wraps a long instruction's bytes onto the next line: those bytes belong to the
    instruction above (their absence used to look like an address gap)."""
    pending = None
    with open(path, 'r', errors='replace') as f:
        for line in f:
            parts = line.split('\t')
            head = parts[0].strip()
            if not head.endswith(':'):
                continue
            try:
                addr = int(head[:-1], 16)
            except ValueError:
                continue
            if len(parts) < 3:                 # continuation of the bytes above
                if pending:
                    pending[1] += len(parts[1].split())
                continue
            text = ' '.join(parts[2].split())
            if pending:
                yield tuple(pending)
                pending = None
            if text:
                pending = [addr, len(parts[1].split()), text]
    if pending:
        yield tuple(pending)


def size_before(prev, i):
    """The size pushed for the alloc at index i: the nearest push before it, not across a call or a
    branch. prev is the instruction list of the current function."""
    j = i - 1
    steps = 0
    while j >= 0 and steps < 6:
        t = prev[j][2]
        m = PUSH_IMM.match(t)
        if m:
            return int(m.group(1), 16)
        if t.startswith('push '):
            return VAR
        if 'call ' in t or t.startswith('ret') or t.startswith('j') or t.startswith('int3') \
                or t.startswith('loop'):
            return UNKNOWN
        if not t.startswith(SKIP_BACK):
            return UNKNOWN
        j -= 1
        steps += 1
    return UNKNOWN


def scan_senders(path, alloc):
    """{type: [(size, sender_addr, alloc_addr)]} plus allocs with no type, from one client's .dis."""
    senders = {}
    unpaired = []
    cur = []                       # instructions of the current function
    prev_end = None

    def flush():
        # pair: each type write takes the nearest preceding alloc of the function not yet used by an
        # earlier type write (two writes in one buffer share the alloc); allocs left over have no type
        pending = []               # [(addr, size, claimed)]
        for idx, (addr, _n, text) in enumerate(cur):
            if text.startswith('call ') and text[5:].strip() == hex(alloc):
                pending.append([addr, size_before(cur, idx), False])
            else:
                m = TYPE_RE.match(text)
                if m:
                    t = int(m.group(2), 16)
                    if pending:
                        pick = next((p for p in reversed(pending) if not p[2]), pending[-1])
                        pick[2] = True
                        senders.setdefault(t, []).append((pick[1], addr, pick[0]))
                    else:                  # body built elsewhere (helper): type known, size not
                        senders.setdefault(t, []).append((UNKNOWN, addr, 0))
        for addr, sz, claimed in pending:
            if not claimed:
                unpaired.append((addr, sz))

    for addr, n, text in instructions(path):
        if prev_end is not None and (addr != prev_end or cur and cur[-1][2] == 'int3'):
            flush()
            cur = []
        cur.append((addr, n, text))
        prev_end = addr + n
    if cur:
        flush()
    for t in senders:
        senders[t] = sorted(set(senders[t]), key=lambda r: (r[1], str(r[0])))
    return senders, sorted(set(unpaired))


# --- the emulator's C>S handlers ------------------------------------------------------------------

UNRESOLVED = object()


def literal(node, consts):
    try:
        v = ast.literal_eval(node)
    except Exception:
        if isinstance(node, ast.Name) and node.id in consts:
            return consts[node.id]
        return UNRESOLVED
    return v


def module_consts(tree):
    c = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            val = literal(node.value, {})
            if val is UNRESOLVED:
                continue
            for t in targets:
                if isinstance(t, ast.Name):
                    c[t.id] = val
                elif isinstance(t, ast.Tuple) and isinstance(val, (tuple, list)) \
                        and len(t.elts) == len(val):
                    for tt, vv in zip(t.elts, val):
                        if isinstance(tt, ast.Name):
                            c[tt.id] = vv
    for _ in range(2):             # A = B chains
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) \
                    and node.value.id in c:
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in c:
                        c[t.id] = c[node.value.id]
    return c


def is_c2s(node):
    return (isinstance(node, ast.Name) and node.id == 'C2S') or \
           (isinstance(node, ast.Attribute) and node.attr == 'C2S')


def is_on_call(node):
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == 'on') or
        (isinstance(node.func, ast.Attribute) and node.func.attr == 'on'))


def ev(node, env, consts):
    """All values of a small expression (int literal, constant name, loop/param binding, +-)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return [node.value]
    if isinstance(node, ast.Name):
        if node.id in env:
            v = env[node.id]
            vals = v if isinstance(v, (list, tuple)) else [v]
            return [x for x in vals if isinstance(x, int)]
        if node.id in consts:
            v = consts[node.id]
            vals = v if isinstance(v, (list, tuple)) else [v]
            return [x for x in vals if isinstance(x, int)]
        return []
    if isinstance(node, ast.BinOp):
        left, right = ev(node.left, env, consts), ev(node.right, env, consts)
        if not left or not right:
            return []
        out = []
        for a in left:
            for b in right:
                if isinstance(node.op, ast.Add):
                    out.append(a + b)
                elif isinstance(node.op, ast.Sub):
                    out.append(a - b)
        return out
    v = literal(node, consts)
    return [v] if isinstance(v, int) else []


def eval_int(node, env, consts):
    vals = ev(node, env, consts)
    return vals[0] if len(vals) == 1 else None


def iterable_values(node, env, consts):
    v = literal(node, consts) if not isinstance(node, ast.Name) else (
        env.get(node.id, consts.get(node.id, UNRESOLVED)))
    if v is UNRESOLVED or isinstance(v, int):
        return None
    if isinstance(v, dict):
        return list(v.keys())
    if isinstance(v, (tuple, list, set, frozenset)):
        return list(v)
    return None


def len_checks(fn, env, consts):
    """'len(frame.payload) < N' checks in this function's own body (nested defs skipped)."""
    found = []

    def visit(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and n is not fn:
            return
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Lt) \
                and isinstance(n.left, ast.Call) and isinstance(n.left.func, ast.Name) \
                and n.left.func.id == 'len' and n.left.args \
                and isinstance(n.left.args[0], ast.Attribute) and n.left.args[0].attr == 'payload':
            expr = ast.unparse(n.comparators[0])
            val = eval_int(n.comparators[0], env, consts)
            found.append((val, expr))
        for ch in ast.iter_child_nodes(n):
            visit(ch)

    for ch in fn.body:
        visit(ch)
    return found


def collect_handlers(src):
    """type -> [{'module', 'function', 'checks'}] and the registrations that could not be resolved."""
    handlers, unresolved = {}, []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for fn in sorted(files):
            if not fn.endswith('.py'):
                continue
            path = os.path.join(root, fn)
            try:
                tree = ast.parse(open(path, encoding='utf-8').read(), path)
            except (SyntaxError, UnicodeDecodeError) as e:
                print(f'warning: {path}: {e}', file=sys.stderr)
                continue
            mod = os.path.relpath(path, src).replace(os.sep, '.')[:-3]
            consts = module_consts(tree)
            funcs = {}
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.setdefault(n.name, []).append(n)
            bindings = {}          # function name -> [ {param: value} ]
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                        and n.func.id in funcs:
                    args = [literal(x, consts) for x in n.args]
                    if not args or all(x is UNRESOLVED for x in args):
                        continue
                    for f in funcs[n.func.id]:
                        params = [x.arg for x in f.args.args]
                        if len(params) >= len(args):
                            bindings.setdefault(n.func.id, []).append(
                                {p: v for p, v in zip(params, args) if v is not UNRESOLVED})

            def record(call, env, handler_name, fn_node, body_env):
                if len(call.args) < 3 or not is_c2s(call.args[1]):
                    return
                types = ev(call.args[2], env, consts)
                if not types:
                    unresolved.append({'module': mod, 'function': handler_name,
                                       'type_expr': ast.unparse(call.args[2])})
                    return
                checks = len_checks(fn_node, body_env, consts) if fn_node else []
                for t in types:
                    handlers.setdefault(t, []).append({
                        'module': mod, 'function': handler_name,
                        'checks': [f'len(frame.payload) < {e}' + (f' = {v}' if v is not None else '')
                                   for v, e in checks]})

            def walk(body, env, cur_func):
                for stmt in body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for b in bindings.get(stmt.name) or [{}]:
                            fenv = {**env, **b}
                            for dec in stmt.decorator_list:
                                if is_on_call(dec):
                                    record(dec, env, stmt.name, stmt, fenv)
                            walk(stmt.body, fenv, stmt.name)
                        continue
                    if isinstance(stmt, ast.For):
                        vals = iterable_values(stmt.iter, env, consts)
                        if vals and isinstance(stmt.target, ast.Name):
                            for v in vals:
                                walk(stmt.body, {**env, stmt.target.id: v}, cur_func)
                        else:
                            walk(stmt.body, env, cur_func)
                        walk(stmt.orelse, env, cur_func)
                        continue
                    if isinstance(stmt, (ast.If, ast.While)):
                        walk(stmt.body, env, cur_func)
                        walk(stmt.orelse, env, cur_func)
                        continue
                    if isinstance(stmt, ast.Try):
                        walk(stmt.body, env, cur_func)
                        for h in stmt.handlers:
                            walk(h.body, env, cur_func)
                        walk(stmt.finalbody, env, cur_func)
                        continue
                    for n in ast.walk(stmt):
                        if not is_on_call(n):
                            continue
                        name, node = cur_func, None
                        for p in ast.walk(stmt):    # on(...)(handler)
                            if isinstance(p, ast.Call) and p.func is n and p.args:
                                a = p.args[0]
                                name = a.id if isinstance(a, ast.Name) else (
                                    a.func.id if isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                                    else '<expr>')
                                node = (funcs.get(name) or [None])[0]
                                break
                        record(n, env, name or '<module>', node, env)

            walk(tree.body, {}, None)
    for t in handlers:
        seen, out = set(), []
        for h in handlers[t]:
            k = (h['module'], h['function'])
            if k not in seen:
                seen.add(k)
                out.append(h)
        handlers[t] = out
    for t in handlers:
        handlers[t].sort(key=lambda h: (h['module'], h['function']))
    return handlers, unresolved


# --- comparison and report ------------------------------------------------------------------------

def fmt_size(s):
    if s == VAR or s == UNKNOWN:
        return s
    return f'0x{s:x} ({s})'


def size_sets(senders):
    return {s for s, _a, _b in senders}


def size_groups(senders):
    """[(size, [sender addresses])], ints first ascending, then var, then '?'."""
    g = {}
    for sz, addr, _alloc in senders:
        g.setdefault(sz, []).append(addr)
    order = sorted((s for s in g if isinstance(s, int))) + \
        [s for s in (VAR, UNKNOWN) if s in g]
    return [(s, sorted(g[s])) for s in order]


def fmt_groups(senders):
    return '; '.join(f'{fmt_size(sz)} @ ' + ', '.join(f'0x{a:x}' for a in addrs)
                     for sz, addrs in size_groups(senders))


def fmt_handler(hs):
    if not hs:
        return 'MISSING'
    out = []
    for h in hs:
        s = f'{h["module"]}:{h["function"]}'
        if h['checks']:
            s += ' [' + '; '.join(h['checks']) + ']'
        out.append(s)
    return ', '.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dis11', required=True, help='objdump -M intel of the 2011 client')
    ap.add_argument('--dis16', required=True, help='objdump -M intel of the 2016 client')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--src', default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  '..', '..', 'dcemu'),
                    help='emulator sources to scan for C>S handlers (default: ../../dcemu)')
    a = ap.parse_args(argv)

    if not os.path.isdir(a.out):
        os.makedirs(a.out)
    all11, u11 = scan_senders(a.dis11, ALLOC['11'])
    all16, u16 = scan_senders(a.dis16, ALLOC['16'])
    # A-E compare senders whose size is known (an alloc was found); F lists the type writes with no
    # alloc in their function (body built elsewhere / not a sender at all)
    s11 = {t: [r for r in v if r[2]] for t, v in all11.items() if any(r[2] for r in v)}
    s16 = {t: [r for r in v if r[2]] for t, v in all16.items() if any(r[2] for r in v)}
    q11 = {t: [r for r in v if not r[2]] for t, v in all11.items() if any(not r[2] for r in v)}
    q16 = {t: [r for r in v if not r[2]] for t, v in all16.items() if any(not r[2] for r in v)}
    handlers, unresolved = collect_handlers(os.path.abspath(a.src))

    types11, types16 = set(s11), set(s16)
    both = sorted(types11 & types16)
    diff = [t for t in both if size_sets(s11[t]) != size_sets(s16[t])]
    same = [t for t in both if size_sets(s11[t]) == size_sets(s16[t])]
    only16 = sorted(types16 - types11)
    only11 = sorted(types11 - types16)
    unhandled_same = [t for t in same if t not in handlers]

    lines = []
    w = lines.append
    w('C>S message types and body sizes: 2011 client vs 2016 client vs emulator handlers')
    w(f'2011 disassembly: {a.dis11}   (allocator 0x{ALLOC["11"]:x})')
    w(f'2016 disassembly: {a.dis16}   (allocator 0x{ALLOC["16"]:x})')
    w(f'emulator sources: {os.path.abspath(a.src)}')
    w('Sizes include the 2-byte type, as allocated. "var" = size pushed from a register.')
    w('"?" entries (no alloc before the type write in the function) are only in F, not in A-E.')
    w('')

    def row(t, extra=None):
        w(f'  0x{t:04x} ({t})')
        w(f'    2011: {fmt_groups(s11[t]) if t in s11 else "-"}')
        w(f'    2016: {fmt_groups(s16[t]) if t in s16 else "-"}')
        w(f'    emulator: {fmt_handler(handlers.get(t))}')
        if extra:
            w(f'    {extra}')

    w('A) sent by both clients, DIFFERENT sizes ---------------------------------------------')
    w(f'   {len(diff)} types')
    for t in diff:
        row(t)
    w('')

    w('B) sent only by 2016 ------------------------------------------------------------------')
    w(f'   {len(only16)} types')
    for t in only16:
        row(t)
    w('')

    w('C) sent by both, same size, emulator does NOT handle ---------------------------------')
    w(f'   {len(unhandled_same)} types')
    for t in unhandled_same:
        row(t)
    w('')

    w('D) sent only by 2011 ------------------------------------------------------------------')
    w(f'   {len(only11)} types')
    for t in only11:
        w(f'  0x{t:04x} ({t})  {fmt_groups(s11[t])}  emulator: {fmt_handler(handlers.get(t))}')
    w('')

    w('E) counts -----------------------------------------------------------------------------')
    w(f'  types with a size: 2011 {len(types11)}, 2016 {len(types16)}, both {len(both)}')
    w(f'  both same size {len(same)} (of them unhandled {len(unhandled_same)}), different {len(diff)}')
    w(f'  only 2016 {len(only16)}, only 2011 {len(only11)}')
    w(f'  emulator C>S handler types {len(handlers)}')
    w(f'  alloc calls with no type write after them in the function: 2011 {len(u11)}, 2016 {len(u16)}')
    if u11:
        w('  2011: ' + ', '.join(f'0x{a:x}({fmt_size(s)})' for a, s in u11))
    if u16:
        w('  2016: ' + ', '.join(f'0x{a:x}({fmt_size(s)})' for a, s in u16))
    w(f'  type writes with no alloc in their function (size "?", section F): 2011 {len(q11)}, 2016 {len(q16)}')
    w('')
    w('F) type writes with no alloc in their function: size UNKNOWN ---------------------------')
    w('   Not in A-E (a sender needs an alloc). Either the body is allocated in a helper, or the')
    w('   write is not a message type: 0x0-0x3/0x20 are value writers (e.g. 0x4105xx writes')
    w('   1,2,3 at [eax] while walking the buffer); 0x7cf is Nation (C>S, dcemu/protocol.py) and')
    w('   0x1be RoomState (S>C, dcemu/handlers/room.py). Addresses are the type write.')
    for t in sorted(set(q11) | set(q16)):
        a11 = ' '.join(f'0x{x[1]:x}' for x in q11.get(t, []))
        a16 = ' '.join(f'0x{x[1]:x}' for x in q16.get(t, []))
        w(f'  0x{t:04x} ({t})  2011: {a11 or "-"}   2016: {a16 or "-"}')
    w('')
    if unresolved:
        w(f'  registrations not resolved: {len(unresolved)}')
        for u in unresolved:
            w(f'    {u["module"]}:{u["function"]}  type {u["type_expr"]}')

    report = os.path.join(a.out, 'report.txt')
    with open(report, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    data = {
        'dis11': a.dis11, 'dis16': a.dis16, 'alloc': {k: hex(v) for k, v in ALLOC.items()},
        '2011': {f'{t:#x}': [{'size': s, 'sender': f'{a2:#x}', 'alloc': f'{a3:#x}', 'sized': bool(a3)}
                             for s, a2, a3 in all11[t]] for t in sorted(all11)},
        '2016': {f'{t:#x}': [{'size': s, 'sender': f'{a2:#x}', 'alloc': f'{a3:#x}', 'sized': bool(a3)}
                             for s, a2, a3 in all16[t]] for t in sorted(all16)},
        'unpaired_allocs': {'2011': [{'addr': f'{x:#x}', 'size': s} for x, s in u11],
                            '2016': [{'addr': f'{x:#x}', 'size': s} for x, s in u16]},
        'handlers': {f'{t:#x}': handlers[t] for t in sorted(handlers)},
        'unresolved_registrations': unresolved,
        'sections': {'A': [f'{t:#x}' for t in diff], 'B': [f'{t:#x}' for t in only16],
                     'C': [f'{t:#x}' for t in unhandled_same], 'D': [f'{t:#x}' for t in only11],
                     'F': {f'{t:#x}': {'2011': [f'{x[1]:#x}' for x in q11.get(t, [])] or None,
                                       '2016': [f'{x[1]:#x}' for x in q16.get(t, [])] or None}
                           for t in sorted(set(q11) | set(q16))},
                     'E': {'types11': len(types11), 'types16': len(types16), 'both': len(both),
                           'same': len(same), 'diff': len(diff), 'only16': len(only16),
                           'only11': len(only11), 'handlers': len(handlers),
                           'unpaired11': len(u11), 'unpaired16': len(u16),
                           'unknown_size11': len(q11), 'unknown_size16': len(q16)}},
    }
    with open(os.path.join(a.out, 'senders.json'), 'w') as f:
        json.dump(data, f, indent=1, sort_keys=False)
    print('\n'.join(lines[lines.index('E) counts -----------------------------------------------------------------------------'):]))
    print(f'\nwrote {report} and {os.path.join(a.out, "senders.json")}')


if __name__ == '__main__':
    main()
