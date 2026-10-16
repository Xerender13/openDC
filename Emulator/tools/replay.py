"""Replay one recorded client connection against a server port and record the replies; compare
two recordings. Used to check a native service against the 2008 server (through the proxy).

usage: python3 -m tools.replay LOG CONN PORT OUT.json   send connection #CONN's client messages
                                                         (as received) from LOG to PORT
       python3 -m tools.replay --compare A.json B.json   per message type: same, or where they differ
Run a second emulator with other ports for the side under test (-c test.ini, see the notes).
0x484 is not sent (the 2008 server does not know it).
"""
import json
import socket
import sys
import time
from collections import defaultdict

from dcemu.wire import Frame, FrameReader

SKIP = {0x484}


def client_messages(log, conn):
    out = []
    for line in open(log, encoding='utf-8', errors='replace'):
        f = line.split()
        if len(f) > 4 and f[1] == '#' + conn and f[3] == 'C>S' and f[4] != 'raw':
            t = int(f[4], 16)
            p = bytes.fromhex(f[-1]) if f[-2].isdigit() and int(f[-2]) == len(f[-1]) // 2 + 4 else b''
            out.append((t, p))
    return out


def replay(log, conn, port, out_path, gap=0.25):
    s = socket.create_connection(('127.0.0.1', port), timeout=5)
    s.recv(56, socket.MSG_WAITALL)
    s.sendall(bytes(56))
    s.settimeout(0.3)
    reader, got = FrameReader(), []

    def drain(sec):
        end = time.time() + sec
        while time.time() < end:
            try:
                d = s.recv(65536)
            except socket.timeout:
                continue
            if not d:
                return
            got.extend((fr.type, fr.payload.hex()) for fr in reader.feed(d))

    msgs = [m for m in client_messages(log, conn) if m[0] not in SKIP]
    for t, p in msgs:
        s.sendall(Frame(t, p).encode())
        drain(gap)
    drain(2)
    json.dump(got, open(out_path, 'w'))
    print(len(msgs), 'sent', len(got), 'received:', ' '.join(hex(t) for t, _ in got if t != 2))


def compare(a_path, b_path):
    sides = []
    for path in (a_path, b_path):
        d = defaultdict(list)
        for t, h in json.load(open(path)):
            if t != 2:
                d[t].append(bytes.fromhex(h))
        sides.append(d)
    A, B = sides
    for t in sorted(set(A) | set(B)):
        for k in range(max(len(A[t]), len(B[t]))):
            a = A[t][k] if k < len(A[t]) else None
            b = B[t][k] if k < len(B[t]) else None
            if a == b:
                print(f'0x{t:x}#{k} same ({len(a)})')
            elif a is None or b is None:
                print(f'0x{t:x}#{k} only in', 'B' if a is None else 'A', len(a or b))
            else:
                runs = []
                for i in range(max(len(a), len(b))):
                    if i >= len(a) or i >= len(b) or a[i] != b[i]:
                        if runs and i == runs[-1][1] + 1:
                            runs[-1][1] = i
                        else:
                            runs.append([i, i])
                print(f'0x{t:x}#{k} len {len(a)}/{len(b)} differs at', ' '.join(f'{x:x}-{y:x}' for x, y in runs[:12]))


if __name__ == '__main__':
    if sys.argv[1] == '--compare':
        compare(sys.argv[2], sys.argv[3])
    else:
        replay(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
