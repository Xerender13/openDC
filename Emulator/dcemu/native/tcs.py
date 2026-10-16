"""Reader for the 2011 client's traffic control system files (server_data/tables/<City>/<city>.tcs), the lanes and
signals of a city's traffic (city_traffic.py).

Layout after github.com/amPerl/slidetown (crates/slidetown/src/parsers/tcs.rs): a header ("TCS\\0", u16
'B', u32 version date, "TRAFFIC-CONTROL-SYSTEM", "NHN-AG", "JC") and nested chunks {u32 id, u32 length
incl. this head, body}. Read here (the rest is the client's: road graph, time keys, road shapes):
  0xA0030 signal: i32 area, id, f32 position on its lane, f32 distance, i32 default state, i32 lane
  0xA0040 the signals between intersections (crosswalks): i32 n, n x i32 signal
  0xA6000 lamps (the client's traffic lights): 0xA6010 i32 n, n x (id, signal), 0xA6030 i32 n,
          n x (i32 lamp id, i32 kind, i32 control, i32 signal). The lamp id is what 0x2c2 names.
  0x70200 lane: i32 area, id, type (0 forward, 1 right, 2 left, 3 / 4 left / right forward), f32 start,
          end (positions: travel time at 100 km/h, so 1 = 27.78 m), max speed (m/s), stop distance,
          cruise distance, total distance (m), i32 time keys, dec, inc, before type, before id, next
          type (0 lane, 1 joint, 2 none), next id, i32 n, n x i32 signal
  0x70300 lane points: i32 area, id, f32 delta (position step between points), i32 n, n x (x, y, z)
  0x75200 joint: i32 area, id, type, i32 in count, i32 out count, the in lanes, the out lanes, node, arc
  0x12200 intersection: i32 area, id, node, i32 n, n x road, i32 n, n x lane, i32 signal controller
  0xA5030 signal controller: i32 area, id, i32 roads, per road i32 n, n x signal (one road green at a time)
"""
import struct

UNIT = 100 / 3.6            # metres per lane position unit


class Lane:
    __slots__ = ('id', 'type', 'end', 'max_speed', 'next_type', 'next_id', 'signals', 'delta', 'points',
                 'outs', 'cars')

    def __init__(self, lid, ltype, end, max_speed, next_type, next_id, signals):
        self.id, self.type, self.end, self.max_speed = lid, ltype, end, max_speed
        self.next_type, self.next_id, self.signals = next_type, next_id, signals
        self.delta, self.points, self.outs, self.cars = 1.0, [], [], []

    def at(self, pos):
        """x, y of a position on the lane (the points are delta apart)."""
        pts = self.points
        if not pts:
            return 0.0, 0.0
        f = max(pos, 0.0) / self.delta
        k = min(int(f), len(pts) - 2)
        if k < 0:
            return pts[0][0], pts[0][1]
        f = min(f - k, 1.0)
        a, b = pts[k], pts[k + 1]
        return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


class Tcs:
    def __init__(self, data):
        if data[:4] != b'TCS\0' or data[4:6] != b'B\0':
            raise ValueError('not a binary TCS file')
        self.version, = struct.unpack_from('<I', data, 6)
        self.lanes = {}             # id -> Lane
        self.signals = {}           # id -> (lane, position)
        self.crosswalks = []        # signals between intersections
        self.lamps = []             # (lamp id, signal)
        self.controllers = {}       # id -> [[signal, ...] per road]
        self.joints = {}            # id -> out lanes
        o = 10
        for _ in range(3):
            o = data.index(b'\0', o) + 1
        self._walk(data, o, len(data))
        for lane in self.lanes.values():
            if lane.next_type == 0 and lane.next_id in self.lanes:
                lane.outs = [lane.next_id]
            elif lane.next_type == 1:
                lane.outs = [x for x in self.joints.get(lane.next_id, ()) if x in self.lanes]
            lane.signals = sorted((self.signals[s][1], s) for s in lane.signals if s in self.signals)

    def _walk(self, d, o, end):
        while o + 8 <= end:
            cid, ln = struct.unpack_from('<II', d, o)
            if ln < 8 or o + ln > end:
                raise ValueError(f'bad TCS chunk {cid:#x} at {o}')
            b = o + 8
            if cid in (0x5, 0x90000, 0xA0000, 0x70000, 0xA5000, 0x10000, 0x20000, 0x50000, 0x75000):
                if cid != 0x90000:              # the time keys: the client's
                    self._walk(d, b, o + ln)
            elif cid == 0xA0030:
                _, sid, pos, _, _, lane = struct.unpack_from('<iiffii', d, b)
                self.signals[sid] = (lane, pos)
            elif cid == 0xA0040:
                n, = struct.unpack_from('<i', d, b)
                self.crosswalks = list(struct.unpack_from(f'<{n}i', d, b + 4))
            elif cid == 0xA6000:
                q = b + struct.unpack_from('<I', d, b + 4)[0]      # past 0xA6010 (the controls)
                if struct.unpack_from('<I', d, q)[0] == 0xA6030:
                    n, = struct.unpack_from('<i', d, q + 8)
                    self.lamps = [struct.unpack_from('<iiii', d, q + 12 + 16 * i)[::3] for i in range(n)]
            elif cid == 0x70200:
                v = struct.unpack_from('<iiiffffffiiiiiiii', d, b)
                self.lanes[v[1]] = Lane(v[1], v[2], v[4], v[5], v[14], v[15],
                                        list(struct.unpack_from(f'<{v[16]}i', d, b + 68)))
            elif cid == 0x70300:
                _, lid, delta, n = struct.unpack_from('<iifi', d, b)
                lane = self.lanes.get(lid)
                if lane:
                    p = struct.unpack_from(f'<{3 * n}f', d, b + 16)
                    lane.delta, lane.points = delta or 1.0, [p[i:i + 3] for i in range(0, 3 * n, 3)]
            elif cid == 0x75200:
                _, jid, _, ni, no = struct.unpack_from('<iiiii', d, b)
                self.joints[jid] = list(struct.unpack_from(f'<{no}i', d, b + 20 + 4 * ni))
            elif cid == 0xA5030:
                _, cid2, nroads = struct.unpack_from('<iii', d, b)
                q, roads = b + 12, []
                for _ in range(nroads):
                    n, = struct.unpack_from('<i', d, q)
                    roads.append(list(struct.unpack_from(f'<{n}i', d, q + 4)))
                    q += 4 + 4 * n
                self.controllers[cid2] = roads
            o += ln
