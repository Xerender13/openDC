"""Battle-zone race traffic emulator.

The original package lacks the program that fed race traffic to ZoneServer, so races have
no traffic. This relay sits in front of the BArea TCP port, forwards every message
unchanged, and adds the traffic snapshots that ZoneServer would otherwise relay. A second,
read-only relay in front of the Game port picks up each player's traffic level setting.

Wire format (plain): [u16 len incl. header][u16 type][payload], little endian.
BArea:
  C>S 0x232  join race    u16 char, 42 bytes name (UTF-16), u32 room, ...
  C>S 0x21d  own state    u16 char, ..., u32 server tick @12, f32 x, y, z @16
  C>S 0x220, 0x223        collision with a traffic car / its physics while pushed: u16 car
                          id, u16 char, u32, f32 x @8, y @12; 80 and 52 byte bodies. One
                          packet may hold several: [len][type][body][type][body]...
                          ZoneServer would relay them to racers within 300 m, but drops
                          them because its own race traffic table is empty; we relay them.
  C>S 0x238  race start   u16 track number (tracknum in PVPTrackInfo.xlt); sent by the room
                          owner only, about 6 s before the countdown ends;
                          traffic starts here and the other racers in the room join it
  C>S 0x234  leave race   u32 room
  S>C 0x21c, 0x233, 0x323 carry the server tick (u32 @4, @12, @4)
  S>C 0x21e  traffic car  u32 tick, f32 progress, f16 speed m/s, f16 acceleration m/s2,
                          u16 car id, u16 model (vehicle id - 20001), u16 path
             The client extrapolates with speed and acceleration. A cruising car sends
             +top speed / 10 (the client caps the speed at ten times that), a waiting car
             a negative value, and a wrecked car -100; this matches the reference server.
Game (each direction starts with an unframed 56-byte handshake):
  C>S 0x7b   login        character name (UTF-16) first
  0x26c      room options u8 flags @6 (owner sends it, server sends it to the room)
  S>C 0x1ce  room info    room name (UTF-16, 0-terminated) @8, then the same flags byte
  Traffic in the flags: 0x04 low, 0x08 medium, 0x10 high, none of them = random.
Progress is travel time along the path at 100 km/h (path length / 27.78), the unit of the
totals in the .index files; the client places the car by interpolating the path points.
Cars within 320 m of a player are sent once a second, as the reference server does.

usage: traffic_server.py <data dir> <upstream host> <BArea listen:port> <Game listen:port>
"""
import asyncio, bisect, collections, configparser, math, os, random, struct, sys, time

RANGE = 320.0          # metres, same radius ZoneServer uses for 0x21e
PERIOD = 1.0           # seconds between snapshots
TICK = 0.2             # simulation step, seconds
CAR_GAP = (25, 35)     # metres between cars of one group when placed
GROUP = (1, 2, 2, 3)   # group sizes to pick from
CLEAR = 3.0            # metres: a car closer than this to a point ahead blocks it (paths are
                       # single lanes about 4.3 m apart, so neighbouring lanes stay free)
LOOK = 12.0            # metres checked beyond the braking distance
STOP_GAP = 7.0         # metres left to the car ahead when stopped behind it
JUNCTION = 2.5         # metres: two paths closer than this (at an angle) cross or merge
MAX_GREEN = 3.0        # seconds an intersection keeps one road green while others wait
DEMAND = 3.0           # seconds: a green road with no car arriving within this switches
BRAKE = 8.0            # m/s2
DZ = 3.0               # metres of height difference that separates two roads (bridges)
START_CLEAR = 350.0    # metres around the start line kept free of cars at race start; beyond
                       # RANGE, so cars waiting at its edge during the countdown are not visible
GRID_HOLD = 30.0       # seconds after 0x238 that cars wait outside START_CLEAR ...
GRID_LEFT = 150.0      # ... unless a racer is already this far from the start
WRECKED = 6.0          # seconds a hit car stays (acceleration -100), then it respawns
IDLE_TIMEOUT = 60.0    # forget a racer that sent no position for this long
COLLISION = {0x220: 80, 0x223: 52}             # collision command -> body size

def traffic_level(flags):
    """Room option flags -> TrafficServer.ini level name, or 'Random'."""
    if flags is None:
        return None
    for bit, name in ((0x10, 'ALot'), (0x08, 'Medium'), (0x04, 'ABit')):
        if flags & bit:
            return name
    return 'Random'

def room_flags(info):
    """Option flags from a 0x1ce body: they follow the 0-terminated UTF-16 room name at 8."""
    for i in range(8, len(info) - 2, 2):
        if info[i:i + 2] == b'\0\0':
            return info[i + 2]
    return None

def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)

def utf16_name(b):
    s = b.decode('utf-16-le', 'replace')
    return s.split('\0', 1)[0]

# ---------------------------------------------------------------- data files

def read_utf16_table(path):
    rows = open(path, encoding='utf-16').read().splitlines()
    return [r.split('\t') for r in rows]

def load_tracks(data):
    """PVPTrackInfo.xlt -> list of (track id, index file, car settings file, start x, y,
    track number within its city)."""
    tracks = []
    for r in read_utf16_table(os.path.join(data, 'Data_TW', 'init', 'PVPTrackInfo.xlt'))[3:]:
        if len(r) < 27 or not r[2].strip() or r[4].strip() == '':
            continue
        tid, city_type, city, num = int(r[4]), int(r[21]), int(r[22]), int(r[23])
        if city_type == 1:
            index, cars = f'PVP_map{city}_{num:02}.index', f'trafficCarSettingForTrack_{city}.txt'
        elif city_type == 4:
            index, cars = f'LapTime{city}_{num:02}.index', f'trafficCarSettingForTrack_{5 + city}.txt'
        else:
            continue
        if os.path.exists(os.path.join(data, index)):
            tracks.append((tid, index, cars, float(r[10]), float(r[11]), num))
    return tracks

class Path:
    def __init__(self, total, pts):
        self.total, self.pts = total, pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(a[:2], b[:2]))
        self.length = self.cum[-1]

    def at(self, progress):
        """x, y, z at a progress value (fraction of total along the polyline)."""
        if len(self.pts) < 2 or self.length == 0:
            return self.pts[0]
        d = min(max(progress, 0.0), self.total) / self.total * self.length
        k = min(max(bisect.bisect_right(self.cum, d) - 1, 0), len(self.pts) - 2)
        seg = self.cum[k + 1] - self.cum[k]
        f = (d - self.cum[k]) / seg if seg else 0.0
        a, b = self.pts[k], self.pts[k + 1]
        return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))

    def metres(self, m):
        """Progress units for a distance in metres along this path."""
        return m / self.length * self.total if self.length else 0.0

def load_paths(path):
    lines = [l.strip() for l in open(path, errors='replace')]
    n, i, paths = int(lines[3]), 4, []
    for _ in range(n):
        head = lines[i].split(); i += 1
        cnt = int(head[5])
        pts = [tuple(map(float, lines[i + k].split()[:3])) for k in range(cnt)]; i += cnt
        start, end = float(head[1]), float(head[2])     # 'start end' (or the total twice)
        paths.append(Path(end - start if end > start else start, pts))
    return paths

_track_cache = {}

def load_track(data, index):
    """Paths and junctions of an index file, computed once per file."""
    if index not in _track_cache:
        paths = load_paths(os.path.join(data, index))
        _track_cache[index] = (paths, find_junctions(paths))
    return _track_cache[index]

class Junction:
    """An intersection: crossings and merges of paths whose stretches overlap. It works like
    a traffic light: a set of paths that do not touch each other here is green, the others
    wait, and the green moves on when the green paths are empty or after MAX_GREEN."""
    __slots__ = ('ranges', 'conflicts', 'green', 'since', 'waiting')
    def __init__(self, ranges, conflicts):
        self.ranges = ranges              # {path: (from m, to m)}
        self.conflicts = conflicts        # {path: set of paths it crosses or merges with here}
        self.green, self.since, self.waiting = set(), 0.0, {}

def find_junctions(paths):
    """Junctions between paths, and per path a list of (from m, to m, junction) by distance."""
    samples, grid = [], collections.defaultdict(list)
    for i, p in enumerate(paths):
        d = 0.0
        while d < p.length:
            a, b = p.at(p.metres(d)), p.at(p.metres(min(d + 2.0, p.length)))
            s = (i, d, a, math.atan2(b[1] - a[1], b[0] - a[0]))
            samples.append(s); grid[(int(a[0] // 4), int(a[1] // 4))].append(s)
            d += 2.0
    hits = collections.defaultdict(list)
    for i, d, a, h in samples:
        cx, cy = int(a[0] // 4), int(a[1] // 4)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j, e, b, k in grid.get((cx + dx, cy + dy), ()):
                    if j <= i or abs(a[2] - b[2]) > DZ or math.dist(a[:2], b[:2]) > JUNCTION:
                        continue
                    hits[(i, j)].append((d, e, abs((h - k + math.pi) % (2 * math.pi) - math.pi) < 0.35))
    pieces = []
    for (i, j), pts in hits.items():
        pts.sort(); run = [pts[0]]
        for q in pts[1:] + [None]:
            if q and q[0] - run[-1][0] <= 6.0:
                run.append(q); continue
            ds, es = [x[0] for x in run], [x[1] for x in run]
            if all(x[2] for x in run):
                # same direction: the paths share a stretch of road; only where they come
                # together needs right of way (following handles the rest), and where two
                # routes just leave a common start there is nothing to give way to
                rng = {i: (min(ds) - 3, min(ds) + 6), j: (min(es) - 3, min(es) + 6)} \
                    if min(ds) > 4 and min(es) > 4 else None
            else:
                rng = {i: (min(ds) - 3, max(ds) + 3), j: (min(es) - 3, max(es) + 3)}
            if rng:
                pieces.append(rng)
            if q:
                run = [q]
    # merge crossings whose stretches overlap on some path into one intersection
    parent = list(range(len(pieces)))
    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]; k = parent[k]
        return k
    by_path = collections.defaultdict(list)
    for k, rng in enumerate(pieces):
        for path, (lo, hi) in rng.items():
            by_path[path].append((lo, hi, k))
    for spans in by_path.values():
        spans.sort()
        end, last = None, None
        for lo, hi, k in spans:
            if end is not None and lo <= end + 4.0:
                parent[root(k)] = root(last)
            if end is None or hi > end:
                end, last = hi, k
    groups = collections.defaultdict(dict)
    conflicts = collections.defaultdict(lambda: collections.defaultdict(set))
    for k, rng in enumerate(pieces):
        g = groups[root(k)]
        for path, (lo, hi) in rng.items():
            a, b = g.get(path, (lo, hi))
            g[path] = (min(a, lo), max(b, hi))
        i, j = rng
        conflicts[root(k)][i].add(j); conflicts[root(k)][j].add(i)
    per_path = collections.defaultdict(list)
    for k, rng in groups.items():
        jn = Junction(rng, dict(conflicts[k]))
        for path, (lo, hi) in rng.items():
            per_path[path].append((lo, hi, jn))
    for v in per_path.values():
        v.sort(key=lambda x: x[0])
    return per_path

def native_mode(data):
    """TrafficServer.ini Mode=native: ZoneServer's own race traffic (XiTrafficControl) runs and
    this only relays and logs it; Mode=emulate (default) adds the emulated traffic."""
    cfg = configparser.ConfigParser(inline_comment_prefixes=(';',))
    try:
        cfg.read(os.path.join(data, 'TrafficServer.ini'))
    except configparser.Error:
        return False
    return cfg.get('Traffic', 'Mode', fallback='emulate').strip().lower() == 'native'

def load_config(data):
    """TrafficServer.ini next to the server files -> speed min, max (m/s), cars per km by level."""
    speed, density = [50.0, 140.0], {'ABit': 1.7, 'Medium': 3.6, 'ALot': 4.8}
    cfg = configparser.ConfigParser(inline_comment_prefixes=(';',))
    cfg.optionxform = str
    try:
        cfg.read(os.path.join(data, 'TrafficServer.ini'))
    except configparser.Error as e:
        log(f'TrafficServer.ini: {e}; using defaults')
    for i, key in enumerate(('SpeedMin', 'SpeedMax')):
        try:
            speed[i] = max(cfg.getfloat('Traffic', key, fallback=speed[i]), 0.0)
        except ValueError as e:
            log(f'TrafficServer.ini {key}: {e}; using {speed[i]:g}')
    for name in density:
        key = 'CarsPerKm' + name
        try:
            density[name] = max(cfg.getfloat('Traffic', key, fallback=density[name]), 0.0)
        except ValueError as e:
            log(f'TrafficServer.ini {key}: {e}; using {density[name]:g}')
    lo, hi = sorted(speed)
    return lo / 3.6, hi / 3.6, density

def load_models(path):
    """Car settings: first line is the car limit, then 'vehicle id <tab> weight'."""
    limit, models = 500, []
    for k, line in enumerate(open(path, errors='replace')):
        f = line.split('//')[0].split()
        if not f:
            continue
        if k == 0:
            limit = int(f[0])
        elif len(f) >= 2:
            models.append((int(f[0]) - 20001, int(f[1])))
    return limit, models

# ---------------------------------------------------------------- simulation

class Car:
    __slots__ = ('id', 'path', 'progress', 'top', 'v', 'a', 'model', 'wrecked_until',
                 'parked', 'pos', 'go')

class Grid:
    """Cars bucketed by 16 m cells for neighbour lookups."""
    def __init__(self):
        self.cells = collections.defaultdict(list)

    def add(self, car, p):
        self.cells[(int(p[0] // 16), int(p[1] // 16))].append((car, p))

    def near(self, p, r):
        cx, cy = int(p[0] // 16), int(p[1] // 16)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for car, q in self.cells.get((cx + dx, cy + dy), ()):
                    if abs(q[2] - p[2]) < DZ and (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < r * r:
                        yield car

class Race:
    """Traffic for one race room; shared by every racer in the room."""
    def __init__(self, room, track, data, level):
        self.room, self.track = room, track
        tid, index, cars_file, sx, sy = track[:5]
        self.paths, self.junctions = load_track(data, index)
        limit, self.models = load_models(os.path.join(data, cars_file))
        self.speed_min, self.speed_max, density = load_config(data)
        level_name = level or 'Medium'
        if level_name == 'Random':
            level_name = random.choice(('ABit', 'Medium', 'ALot'))
        self.level = level_name
        km = sum(p.length for p in self.paths) / 1000
        # 'None': the 2011 room's "Traffic: None" (dcemu race.room_traffic_level)
        wanted = 0 if level_name == 'None' else min(int(density[level_name] * km), limit)
        self.start = (sx, sy)
        self.cars, self.racers = [], set()
        grid, next_id = Grid(), 1
        for p, path in enumerate(self.paths):
            n = round(wanted * path.length / (km * 1000)) if km else 0
            if n == 0:
                continue
            spacing = path.length / n
            d = random.uniform(0, spacing)
            while d < path.length and n > 0:
                size, speed = random.choice(GROUP), self.cruise()
                for _ in range(size):
                    if d >= path.length or n == 0:
                        break
                    prog = path.metres(d)
                    pos = path.at(prog)
                    if math.dist(pos[:2], self.start) >= START_CLEAR and not any(grid.near(pos, 8.0)):
                        c = self.new_car(next_id, p, prog, speed); next_id += 1
                        grid.add(c, pos); n -= 1
                    d += random.uniform(*CAR_GAP)
                d += spacing * size
        self.by_id = {c.id: c for c in self.cars}
        self.hold_until = time.monotonic() + GRID_HOLD
        try:
            self.task = asyncio.get_running_loop().create_task(self.run())
        except RuntimeError:
            self.task = None              # no event loop (offline tests drive step() directly)
        log(f'room {room}: track {tid} ({index}), {len(self.paths)} paths, {km:.0f} km of road, '
            f'traffic {level_name} (room setting {level}), {len(self.cars)} cars, '
            f'{self.speed_min * 3.6:.0f}-{self.speed_max * 3.6:.0f} km/h')

    def cruise(self):
        return random.uniform(self.speed_min, self.speed_max)

    def new_car(self, cid, path, progress, speed):
        c = Car(); c.id, c.path, c.progress, c.top, c.v, c.a = cid, path, progress, speed, speed, speed / 10
        c.model, c.wrecked_until, c.parked, c.go = self.pick_model(), 0.0, False, False
        c.pos = self.paths[path].at(progress)
        self.cars.append(c)
        return c

    def pick_model(self):
        if not self.models:
            return 0
        return random.choices([m for m, _ in self.models], [w for _, w in self.models])[0]

    def grid_occupied(self, now):
        """True while the racers may still be waiting on the grid."""
        if now > self.hold_until:
            return False
        return all(r.pos is None or math.dist(r.pos, self.start) < GRID_LEFT for r in self.racers)

    def racer_near(self, pos, r):
        return any(x.pos and math.dist(x.pos, pos[:2]) < r for x in self.racers)

    async def run(self):
        last = time.monotonic()
        while True:
            await asyncio.sleep(TICK)
            now = time.monotonic()
            self.step(now, min(now - last, 1.0)); last = now

    def first_blocker(self, c, grid, until):
        """(distance, car) of the nearest car within CLEAR of c's path ahead, up to `until` m."""
        path, m = self.paths[c.path], 2.0
        while m <= until:
            prog = c.progress + path.metres(m)
            if prog > path.total:
                break
            for o in grid.near(path.at(prog), CLEAR):
                if o is not c:
                    return m, o
            m += 2.0
        return None, None

    def metres_along(self, c):
        path = self.paths[c.path]
        return c.progress / path.total * path.length

    def junction_gaps(self, now, ahead):
        """Metres to the intersection each car must stop at (see Junction). Only the front
        car of each path is checked; the cars behind it follow it."""
        front = collections.defaultdict(dict)         # junction -> path -> (d, car)
        for c in ahead:
            d = self.metres_along(c)
            horizon = d + c.v * 4 + 30
            for lo, hi, jn in self.junctions.get(c.path, ()):
                if hi <= d:
                    continue
                if lo > horizon:
                    break
                best = front[jn].get(c.path)
                if best is None or d > best[0]:
                    front[jn][c.path] = (d, c)
                break                                 # only the next intersection matters
        waits = {}
        for jn, cars in front.items():
            inside, ready, eta = set(), {}, {}
            for p, (d, c) in cars.items():
                lo, hi = jn.ranges[p]
                if d > lo or (c.go and c.v * c.v / (2 * BRAKE) >= lo - d - 1.0):
                    inside.add(p); continue       # in it, or cleared and too close to stop
                gap, b = ahead[c]
                ready[p] = gap is None or b.v > 1.0 or gap > hi - d + 5.0   # room to clear it
                eta[p] = (lo - d) / max(c.v, 1.0)
            for p in eta:
                if p not in jn.green:
                    jn.waiting.setdefault(p, now)
            for p in list(jn.waiting):
                if p not in eta or p in jn.green:
                    del jn.waiting[p]
            demand = any(eta.get(p, 99) < DEMAND and ready.get(p) for p in jn.green)
            others = [p for p in jn.waiting if ready.get(p)]
            if others and (not demand or now - jn.since > MAX_GREEN):
                first = min(others, key=lambda p: (jn.waiting[p], eta[p]))
                green = {first}
                for p in sorted(others, key=lambda p: jn.waiting[p]):
                    if not (jn.conflicts.get(p, set()) & green):
                        green.add(p)
                jn.green, jn.since = green, now
                for p in green:
                    jn.waiting.pop(p, None)
            for p, (d, c) in cars.items():
                if p in inside:
                    continue
                busy = jn.conflicts.get(p, set()) & inside   # a crossing car is still inside
                if p not in jn.green or busy or not ready[p]:
                    waits[c] = jn.ranges[p][0] - d
        for c in ahead:
            c.go = c not in waits
        return waits

    def step(self, now, dt):
        hold = self.grid_occupied(now)
        grid = Grid()
        for c in self.cars:
            if not c.parked:
                grid.add(c, c.pos)
        ahead = {}
        for c in self.cars:
            if not c.parked and c.wrecked_until <= now:
                ahead[c] = self.first_blocker(c, grid, c.v * dt + c.v * c.v / (2 * BRAKE) + LOOK)
        waits = self.junction_gaps(now, ahead)
        for c in self.cars:
            if c.parked:
                self.respawn(c, grid)
                continue
            if c.wrecked_until:
                if c.wrecked_until <= now:
                    c.parked, c.wrecked_until = True, 0.0     # tow it away; respawns out of sight
                continue
            path = self.paths[c.path]
            gap, o = ahead.get(c, (None, None))
            if o is not None and o.path != c.path and ahead.get(o, (None, None))[1] is c and c.id < o.id:
                gap = None                    # two cars meeting at one spot: lower id goes first
            want = c.top
            if gap is not None:
                room = gap - STOP_GAP
                safe = math.sqrt(2 * BRAKE * room) * 0.5 if room > 0 else 0.0
                lead = o.v if o.path == c.path and room > 0 else 0.0   # follow the car ahead in this lane
                want = min(c.top, max(safe, lead))
            jgap = waits.get(c)
            if jgap is not None:
                room = jgap - 1.0             # stop line just before the junction
                want = min(want, math.sqrt(2 * BRAKE * room) * 0.5 if room > 0 else 0.0)
            if hold and math.dist(c.pos[:2], self.start) >= START_CLEAR:
                edge = path.at(c.progress + path.metres(c.v * c.v / (2 * BRAKE) + LOOK))
                if math.dist(edge[:2], self.start) < START_CLEAR:
                    want = 0.0                # wait outside the clear zone during the countdown
            accel = c.top / 10
            if c.v < want:
                v, c.a = min(want, c.v + accel * dt), accel
            elif c.v > want:
                v = max(want, c.v - BRAKE * dt)
                c.a = -min(BRAKE, max(c.v - want, 0.5))   # the braking the client should apply
            else:
                v, c.a = c.v, (accel if c.v > 0 else -accel)
            nxt = c.progress + (c.v + v) / 2 * dt / 27.78
            c.v = v
            if nxt >= path.total:
                c.parked = True               # route finished; respawn out of sight
                continue
            c.progress, c.pos = nxt, path.at(nxt)

    def respawn(self, c, grid):
        """Put a finished car back at its route start once nobody can see that spot."""
        path = self.paths[c.path]
        pos = path.at(0.0)
        if self.racer_near(pos, RANGE + 30) or any(grid.near(pos, 40.0)):
            return
        c.parked, c.progress, c.pos = False, 0.0, pos
        c.top, c.v = self.cruise(), 0.0; c.a = c.top / 10   # pulls away from standstill
        c.model = self.pick_model()
        grid.add(c, pos)

    def hit(self, car_id):
        c = self.by_id.get(car_id)
        if c and not c.parked and not c.wrecked_until:
            c.wrecked_until, c.v, c.a = time.monotonic() + WRECKED, 0.0, -100.0

    def snapshot(self, x, y, tick):
        """Messages for the cars within RANGE of (x, y)."""
        out = []
        for c in self.cars:
            if c.parked or (c.pos[0] - x) ** 2 + (c.pos[1] - y) ** 2 > RANGE * RANGE:
                continue
            body = struct.pack('<Ifee3H', tick & 0xffffffff, c.progress, c.v, c.a,
                               c.id, c.model, c.path)
            out.append(struct.pack('<HH', 4 + len(body), 0x21e) + body)
        return out

    def close(self):
        if self.task:
            self.task.cancel()

# ---------------------------------------------------------------- relays

def messages(buf):
    """Pop complete [len][type][payload] messages from buf; drop data that does not frame."""
    while len(buf) >= 4:
        n = int.from_bytes(buf[:2], 'little')
        if n < 4 or n > 16384:
            buf.clear(); return
        if len(buf) < n:
            return
        yield int.from_bytes(buf[2:4], 'little'), bytes(buf[4:n]), bytes(buf[:n])
        del buf[:n]

class Server:
    def __init__(self, data, host):
        self.data, self.host = data, host
        self.tracks = load_tracks(data)
        self.races = {}
        self.levels = {}                 # character name -> room traffic level (Game port)
        self.racers = set()              # every BArea connection
        self.tick_offset = None          # server tick - local ms
        self.native = native_mode(data)
        log(f'{len(self.tracks)} tracks with traffic paths; ' +
            ('ZoneServer runs the traffic (Mode=native)' if self.native else 'emulated traffic'))

    def server_tick(self):
        return int(time.monotonic() * 1000 + (self.tick_offset or 0))

    def saw_tick(self, tick):
        self.tick_offset = tick - time.monotonic() * 1000

    def native_cars(self, body):
        """Mode=native: log ZoneServer's own traffic snapshots (0x21e) to native_traffic.log,
        one line per car record, and a count every 10 s to the console."""
        now = time.monotonic()
        st = self.__dict__.setdefault('native_stats', {'t': now, 'msgs': 0, 'cars': set()})
        if 'native_log' not in self.__dict__:
            self.native_log = open(os.path.join(self.data, 'native_traffic.log'), 'a', buffering=1)
        st['msgs'] += 1
        o, ty = 0, 0x21e
        while ty == 0x21e and o + 18 <= len(body):       # [record] ([0x21e][record])...
            tick, prog = struct.unpack_from('<If', body, o)
            v, a = (struct.unpack_from('<e', body, o + k)[0] for k in (8, 10))
            car, model, path = struct.unpack_from('<3H', body, o + 12)
            st['cars'].add(car)
            self.native_log.write(f'{time.strftime("%H:%M:%S")} tick {tick} car {car} model {model} '
                                  f'path {path} progress {prog:.3f} speed {v:.2f} acc {a:.2f}\n')
            o += 18
            if o + 2 <= len(body):
                ty = struct.unpack_from('<H', body, o)[0]; o += 2
        if o < len(body):
            self.native_log.write(f'{time.strftime("%H:%M:%S")} rest of frame: type {ty:#x} {body[o:o + 64].hex()}\n')
        if now - st['t'] >= 10:
            log(f"ZoneServer traffic: {st['msgs']} snapshots, {len(st['cars'])} cars in 10 s")
            st.update(t=now, msgs=0, cars=set())

    QUIET = (0x21c, 0x21d, 0x323, 0x233)

    def native_message(self, way, ty, body):
        """Mode=native: other BArea messages to native_traffic.log (not position/time sync)."""
        if ty in self.QUIET:
            return
        if 'native_log' not in self.__dict__:
            self.native_log = open(os.path.join(self.data, 'native_traffic.log'), 'a', buffering=1)
        self.native_log.write(f'{time.strftime("%H:%M:%S")} {way} {ty:#x} len {len(body)} {body[:96].hex()}\n')

    def find_track(self, x, y, num=None):
        """The track starting at (x, y); a forward track and its reverse share a start, so the
        track number from 0x238 picks between them."""
        tracks = [t for t in self.tracks if t[5] == num and math.dist(t[3:5], (x, y)) < 80] or self.tracks
        best = min(tracks, key=lambda t: (t[3] - x) ** 2 + (t[4] - y) ** 2, default=None)
        if best and math.dist((best[3], best[4]), (x, y)) < 80:
            return best
        return None

    async def pipe(self, reader, writer, watch=None, skip=0):
        """Forward bytes unchanged; feed whole messages to watch (after `skip` raw bytes)."""
        buf = bytearray()
        while data := await reader.read(65536):
            if skip:
                writer.write(data); await writer.drain()
                n = min(skip, len(data)); skip -= n; data = data[n:]
                if not data:
                    continue
                buf += data
                for ty, body, _ in messages(buf) if watch else ():
                    watch(ty, body)
                continue
            writer.write(data)
            await writer.drain()
            if watch:
                buf += data
                for ty, body, _ in messages(buf):
                    watch(ty, body)

    async def connect(self, port, cwriter):
        try:
            return await asyncio.open_connection(self.host, port)
        except OSError as e:
            log(f'upstream {port} connect failed: {e}'); cwriter.close()
            return None, None

    async def handle_game(self, creader, cwriter, port):
        ureader, uwriter = await self.connect(port, cwriter)
        if not ureader:
            return
        player = {'name': None}

        def from_client(ty, body):
            if ty == 0x7b and len(body) >= 4:
                player['name'] = utf16_name(body[:42])
            elif ty == 0x26c and len(body) >= 8:
                self.set_level(player['name'], traffic_level(body[6]))

        def from_server(ty, body):
            if ty == 0x1ce:
                self.set_level(player['name'], traffic_level(room_flags(body)))
            elif ty == 0x26c and len(body) >= 8:
                self.set_level(player['name'], traffic_level(body[6]))

        tasks = [asyncio.create_task(self.pipe(creader, uwriter, from_client, skip=56)),
                 asyncio.create_task(self.pipe(ureader, cwriter, from_server, skip=56))]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in tasks:
            t.cancel()
        for w in (uwriter, cwriter):
            w.close()

    def room_racers(self, room):
        return [r for r in self.racers if r.room == room]

    def set_level(self, name, level):
        if name and self.levels.get(name) != level:
            self.levels[name] = level
            log(f'{name}: room traffic {level}')

    async def handle_barea(self, creader, cwriter, port):
        ureader, uwriter = await self.connect(port, cwriter)
        if not ureader:
            return
        peer = cwriter.get_extra_info('peername')
        racer = Racer(self, cwriter)
        self.racers.add(racer)
        log(f'{peer}: connected')
        tasks = [asyncio.create_task(self.pipe(creader, uwriter, racer.client_message)),
                 asyncio.create_task(self.barea_to_client(ureader, cwriter)),
                 asyncio.create_task(racer.run())]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in tasks:
            t.cancel()
        racer.leave()
        self.racers.discard(racer)
        for w in (uwriter, cwriter):
            w.close()
        log(f'{peer}: closed')

    async def barea_to_client(self, reader, writer):
        """Forward whole messages only, so injected snapshots never split one."""
        buf, framed = bytearray(), True
        while data := await reader.read(65536):
            if not framed:
                writer.write(data); await writer.drain(); continue
            buf += data
            while len(buf) >= 4:
                n = int.from_bytes(buf[:2], 'little')
                if n < 4:
                    log('unexpected server framing; plain relay from now on')
                    framed = False; writer.write(bytes(buf)); buf.clear(); break
                if len(buf) < n:
                    break
                ty, body = int.from_bytes(buf[2:4], 'little'), bytes(buf[4:n])
                if ty == 0x21e:
                    self.native_cars(body)
                elif self.native:
                    self.native_message('S>C', ty, body)
                if ty in (0x21c, 0x323) and len(body) >= 8:
                    self.saw_tick(struct.unpack_from('<I', body, 4)[0])
                elif ty == 0x233 and len(body) >= 16:
                    self.saw_tick(struct.unpack_from('<I', body, 12)[0])
                writer.write(bytes(buf[:n])); del buf[:n]
            await writer.drain()

class Racer:
    def __init__(self, server, writer):
        self.server, self.writer = server, writer
        self.room = self.race = self.pos = self.name = None
        self.started, self.last_seen, self.tracknum = False, 0.0, None

    def client_message(self, ty, body):
        if ty == 0x232 and len(body) >= 48:
            self.leave()
            self.name = utf16_name(body[2:44])
            self.room = struct.unpack_from('<I', body, 44)[0]
            self.server.native = native_mode(self.server.data)     # TrafficServer.ini Mode
            log(f'{self.name}: join room {self.room}' + (' (native traffic)' if self.server.native else ''))
        elif ty == 0x234:
            self.leave()
        elif ty == 0x21d and len(body) >= 28 and self.room is not None:
            x, y, _ = struct.unpack_from('<3f', body, 16)
            self.pos, self.last_seen = (x, y), time.monotonic()
            # only the room owner sends 0x238; the others join once the room's race runs
            if self.race is None and (self.started or self.room in self.server.races):
                self.attach(x, y)
        elif ty == 0x238:
            log(f'{self.name}: race start {body[:12].hex()}')
        if self.server.native:
            self.server.native_message('C>S', ty, body)
            return
        if ty == 0x238 and self.room is not None:
            self.started = True
            if len(body) >= 2:
                self.tracknum = struct.unpack_from('<H', body, 0)[0]
            if self.pos and self.race is None:
                self.attach(*self.pos)
        elif ty in COLLISION and self.race:
            self.collisions(ty, body)

    def collisions(self, ty, rest):
        """Mark the hit cars and relay each collision command to the other racers nearby."""
        while ty in COLLISION and len(rest) >= COLLISION[ty]:
            body, rest = rest[:COLLISION[ty]], rest[COLLISION[ty]:]
            car, = struct.unpack_from('<H', body, 0)
            x, y = struct.unpack_from('<2f', body, 8)
            self.race.hit(car)
            msg = struct.pack('<HH', 4 + len(body), ty) + body
            for r in self.race.racers:
                if r is not self and r.pos and math.dist(r.pos, (x, y)) < 300.0:
                    r.writer.write(msg)
            if len(rest) < 2:
                break
            ty, rest = struct.unpack_from('<H', rest, 0)[0], rest[2:]

    def attach(self, x, y):
        race = self.server.races.get(self.room)
        if race is None:
            track = self.server.find_track(x, y, self.tracknum)
            if track is None:
                return            # not at a start line yet; retry on the next position
            level = self.server.levels.get(self.name)
            if level is None:             # fall back to another racer of the room
                level = next((self.server.levels[r.name] for r in self.server.room_racers(self.room)
                              if r.name in self.server.levels), None)
            race = self.server.races[self.room] = Race(self.room, track, self.server.data, level)
        race.racers.add(self); self.race = race

    def leave(self):
        if self.race:
            self.race.racers.discard(self)
            if not self.race.racers:
                self.race.close()
                self.server.races.pop(self.room, None)
                log(f'room {self.room}: traffic stopped')
        self.room = self.race = self.pos = None
        self.started = False

    async def run(self):
        while True:
            await asyncio.sleep(PERIOD)
            if not self.race or not self.pos:
                continue
            if time.monotonic() - self.last_seen > IDLE_TIMEOUT:
                self.leave(); continue
            msgs = self.race.snapshot(*self.pos, self.server.server_tick())
            if msgs:
                self.writer.write(b''.join(msgs))
                await self.writer.drain()

async def main():
    data, host = sys.argv[1], sys.argv[2]
    (bl, bp), (gl, gp) = [tuple(map(int, a.split(':'))) for a in sys.argv[3:5]]
    server = Server(data, host)
    barea = await asyncio.start_server(lambda r, w: server.handle_barea(r, w, bp), '0.0.0.0', bl)
    game = await asyncio.start_server(lambda r, w: server.handle_game(r, w, gp), '0.0.0.0', gl)
    log(f'traffic relay on :{bl} -> {host}:{bp}, game watch on :{gl} -> {host}:{gp}')
    async with barea, game:
        await asyncio.gather(barea.serve_forever(), game.serve_forever())

if __name__ == '__main__':
    asyncio.run(main())
