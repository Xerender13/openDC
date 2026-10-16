"""City traffic of the native area service: what TrafficAgent.exe (the 2008 server's traffic program, under
Wine in a container) did, done here.

The agent connected to the area port like a client, registered 40 areas (0x2c1: 4-13, 28-37, 52-61,
76-85), drove up to CarSize cars per area on its own copy of the cities' .tcs files and sent every car
and lamp every second (0x2be CastTCS / 0x2c3 CastTCSSignal, ~30,000 commands a second); the area relayed
those within 320 m of each player as 0x2bd / 0x2c2. Measured from its output (2026-10-15, 6 minutes):
  0x2bd XiTCSCarMove (22): i32 time (the server tick), f32 position on the lane (lane units: travel time
        at 100 km/h, 1 = 27.78 m), f16 speed (m/s, the lane's max 19.44 = 70 km/h), f16 acceleration
        (m/s2: +max/10 while speeding up, also at full speed; braking never more than the speed, so the
        client's extrapolation over the next second does not go backwards; -100 = stopped), u16 car id,
        u16 model (VehicleList Unique Id - 20001), i16 lane, i16 next lane (-1 until ~200 m before the
        lane's end), i16 third lane (always -1).
  0x2c2 XiTCSSignal (12): i32 time (0), i32 lamp (the .tcs lamp id, not the signal id), i32 state
        (1 green, 0 red; nothing else seen). The client (0x5375e0) keeps state != 0 as 2 (go) and the time as
        the lamp's last change, and draws (0x41f840) amber (node T_light_Y01) for 4 s after a change to stop
        and 1 s after a change to go, then red (T_light_R01) / green (T_light_G01, + T_light_A01 on 4-lamp
        signals; crosswalks T_light_stop01 / walk01). With the agent's time 0 it never showed amber; here
        the time is the tick of the last change (not the current tick: that would keep it amber).
  Signals: at an intersection one road of its controller is green at a time, 15 s of every 30 s slot
  (road i at i x 30 s of a roads x 30 s cycle); the signals between intersections (crosswalks) are red
  30 s, green 28 s. Here cars stop for amber when they can do so comfortably and wait out the 1 s amber
  before green. Cars stop ~4 m before a red signal and ~7.5 m behind a stopped car; at a lane's end
  a joint's out lane is picked at random; a dead end puts the car on another lane. Cars per area:
  Moon Palace 300, Koinonia 400, Cras 438, Oros 380 (its ini: 300 / 400 / 500 / 500).
The agent had the cities wrong: areas 52-61 (where the 2011 client drives Oros) got Cras's lanes and
cars, 76-85 (Cras) Oros's. Here an area's city follows the client: area = 4 + 24 x (block - 1) +
channel, blocks 1 Moon Palace, 2 Koinonia, 3 Oros, 4 Cras (5: Taipei, guessed). Areas 0-3 (the
tutorial) have none, as under the 2008 server.

The cities' files are the client's, by its world numbering (0x44e840: 1 MOONPALACE, 2 KOINONIA, 3 CRAS,
4 OROS, 5 TAIPEI, 6 NEOOROS; TrafficFlowControl.xlt's "N차도시" blocks use the same order):
server_data/tables/<City>/<city>.tcs (tools/sync_data.py) and the car models of Init/TrafficFlowControl.xlt
(weighted by its frequency column 1 / 3 / 6). Taipei has no .tcs (path_taipei.chpath + .signal: path
traffic like the races' 0x21e), so it has no city traffic yet.

An area's traffic runs while players are in it (and a while after), stepped once a second; each player
gets the cars and lamps within 320 m once a second, in frames split at command boundaries.
"""
import asyncio
import bisect
import math
import os
import random
import struct
import time

from ..wire import Frame
from . import tick
from .data import read_xlt
from .tcs import UNIT, Tcs

CAST_RANGE = 320.0          # metres (the 2008 CastTask)
PERIOD = 1.0                # seconds between steps and snapshots
IDLE_SECONDS = 120          # an area's traffic stops this long after its last player left
MAX_OUT = 4096              # bytes of commands per frame to a client
SLOT, GREEN = 30.0, 15.0    # intersection: each road green GREEN s of a SLOT s slot
WALK_RED, WALK_GREEN = 30.0, 28.0   # crosswalk signals
AMBER_STOP, AMBER_GO = 4.0, 1.0     # seconds the client shows amber after a change to stop / to go
STOP_GAP = 7.5              # metres to a stopped car ahead
SIGNAL_GAP = 4.0            # metres before a red signal
COMFORT = 2.0               # braking up to this many times the acceleration counts as normal
ANNOUNCE = 200.0            # metres before a lane's end the next lane is sent
STOPPED = -100.0            # acceleration sent for a stopped car

# world city id -> (folder, .tcs file); the area block -> world city id
CITIES = {1: ('MoonPalace', 'moonpalace.tcs'), 2: ('Koinonia', 'koinonia.tcs'), 3: ('Cras', 'Cras.tcs'),
          4: ('Oros', 'Oros.tcs'), 5: ('Taipei', None)}
AREA_CITY = {1: 1, 2: 2, 3: 4, 4: 3, 5: 5}
CAR_COUNT = {1: 300, 2: 400, 3: 438, 4: 380}    # what TrafficAgent drove per area


def area_city(area):
    """World city id of a city area, or None (the tutorial areas 0-3, battle areas)."""
    if area < 4:
        return None
    return AREA_CITY.get((area - 4) // 24 + 1)


def car_models(path):
    """TrafficFlowControl.xlt -> {world city id: [(model, weight)]}: each "N차도시" block's rows
    (Index, City Index, Unique Id, frequency, ...); model = Unique Id - 20001."""
    models = {}
    for row in read_xlt(path):
        if len(row) > 3 and row[0].strip().isdigit() and row[1].strip().isdigit() and row[2].strip().isdigit():
            models.setdefault(int(row[1]) + 1, []).append((int(row[2]) - 20001, int(row[3] or 1)))
    return models


class City:
    """A city's lanes and signals (shared by its areas)."""
    def __init__(self, tcs, models):
        self.tcs = tcs
        self.lanes = tcs.lanes
        self.spawn = [l for l in self.lanes.values() if l.type == 0 and len(l.points) > 1 and l.end > 0]
        self.spawn_weight = list(_cumulative(l.end for l in self.spawn))
        self.models = [m for m, _ in models] or [0]
        self.model_weight = list(_cumulative(w for _, w in models)) or [1]
        # signal -> (road, roads) of its intersection's controller; crosswalk signals -> None
        self.phase = {}
        for roads in tcs.controllers.values():
            for i, road in enumerate(roads):
                for s in road:
                    self.phase[s] = (i, len(roads))
        self.lamps = []             # (lamp id, signal, x, y)
        for lamp, sig in tcs.lamps:
            lane, pos = tcs.signals.get(sig, (None, 0))
            if lane in self.lanes:
                self.lamps.append((lamp, sig, *self.lanes[lane].at(pos)))

    def state(self, sig, t):
        """(go, seconds since the last change) of a signal at signal time t."""
        ph = self.phase.get(sig)
        if ph is None:                              # crosswalk: red, then green
            cycle, start, end = WALK_RED + WALK_GREEN, WALK_RED, WALK_RED + WALK_GREEN
        else:
            road, roads = ph
            cycle, start, end = roads * SLOT, road * SLOT, road * SLOT + GREEN
        p = t % cycle
        if start <= p < end:
            return True, p - start
        return False, (p - end) % cycle

    def green(self, sig, t):
        return self.state(sig, t)[0]

    def light(self, sig, t):
        """What the client shows: 'G', 'A' (amber) or 'R'."""
        go, since = self.state(sig, t)
        if since < (AMBER_GO if go else AMBER_STOP):
            return 'A'
        return 'G' if go else 'R'

    def random_lane(self, rng):
        return self.spawn[bisect.bisect_left(self.spawn_weight, rng.random() * self.spawn_weight[-1])]

    def random_model(self, rng):
        return self.models[bisect.bisect_left(self.model_weight, rng.random() * self.model_weight[-1])]


def _cumulative(values):
    s = 0.0
    for v in values:
        s += v
        yield s


class TrafficCar:
    __slots__ = ('id', 'model', 'lane', 'pos', 'v', 'a', 'next', 'stopped')

    def __init__(self, cid, model):
        self.id, self.model = cid, model
        self.lane, self.pos, self.v, self.a, self.next, self.stopped = None, 0.0, 0.0, 0.0, None, False


class AreaTraffic:
    """The traffic cars of one area."""
    def __init__(self, area, city, count, seed=None):
        self.area, self.city = area, city
        self.rng = random.Random(seed)
        self.t = 0.0                # seconds of signal time
        self.cars = []
        self.lane_cars = {}         # lane id -> cars on it, by position
        self.idle_since = None
        self.xy = []                # (car, x, y) after the last step
        for cid in range(count):
            car = TrafficCar(cid, city.random_model(self.rng))
            self.place(car, self.rng.random())
            car.v = car.lane.max_speed * self.rng.choice((0.0, 0.5, 1.0))
            self.cars.append(car)
        self.replan()

    # ---- placement -------------------------------------------------------------------------------
    def place(self, car, frac=0.0):
        """Put a car on a random forward lane (at frac of its length), one with no car near that spot if
        one is found."""
        for _ in range(20):
            lane = self.city.random_lane(self.rng)
            pos = lane.end * frac
            if all(abs(o.pos - pos) * UNIT > 2 * STOP_GAP for o in self.lane_cars.get(lane.id, ())):
                break
        self.move_to(car, lane, pos)
        car.v, car.stopped = 0.0, False

    def move_to(self, car, lane, pos):
        if car.lane is not None:
            cs = self.lane_cars.get(car.lane.id)
            if cs and car in cs:
                cs.remove(car)
        car.lane, car.pos = lane, pos
        car.next = self.rng.choice(lane.outs) if lane.outs else None
        cs = self.lane_cars.setdefault(lane.id, [])
        k = 0
        while k < len(cs) and cs[k].pos <= pos:
            k += 1
        cs.insert(k, car)

    # ---- one step -------------------------------------------------------------------------------
    def obstacle(self, car, look):
        """Metres to where the car must stand still at the latest (a red signal or the car ahead),
        looking `look` metres ahead on its lane and the next one; None if the way is free."""
        best = None
        lane, pos, base = car.lane, car.pos, 0.0
        for depth in (0, 1):
            if lane is None or base > look:
                break
            for spos, sig in lane.signals:
                light = self.city.light(sig, self.t) if spos > pos else 'G'
                if light != 'G':
                    d = base + (spos - pos) * UNIT - SIGNAL_GAP
                    # amber: stop if that is comfortable, else go on; red: stop unless it is too late even
                    # braking hard (a light that turned while the car was right at it)
                    brake = COMFORT * lane.max_speed / 10 if light == 'A' else 0.5 * lane.max_speed
                    if d >= car.v * car.v / (2 * brake) - 1:
                        best = d if best is None else min(best, d)
                    break
            for o in self.lane_cars.get(lane.id, ()):
                if o is not car and o.pos > pos:
                    d = base + (o.pos - pos) * UNIT - STOP_GAP
                    best = d if best is None else min(best, d)
                    break
            base += (lane.end - pos) * UNIT
            lane = self.city.lanes.get(car.next) if depth == 0 and car.next is not None else None
            pos = -1.0
        return best

    def plan(self, car):
        """The acceleration for the next PERIOD (the agent's rules, see the module text)."""
        top = car.lane.max_speed
        inc = top / 10
        look = car.v * car.v / (2 * inc) + top * PERIOD + 30
        d = self.obstacle(car, look)
        v = car.v
        if d is None:
            return inc, False
        if v <= 0.01:
            return (inc, False) if d > inc * PERIOD * PERIOD else (0.0, True)
        v1 = min(v + inc * PERIOD, top)
        # speed up (or keep the top speed) if the car can still stop comfortably after that
        if v1 * v1 / (2 * COMFORT * inc) <= d - (v + v1) / 2 * PERIOD:
            return inc, False
        need = v * v / (2 * max(d, 0.5))
        return -min(max(need, inc / 2), v / PERIOD, top / 2), False

    def step(self):
        """One PERIOD: every car moves with the acceleration it was sent last time, then plans the next
        one (sent with this snapshot, so the client's extrapolation is what happens here)."""
        self.t += PERIOD
        for car in self.cars:
            if car.stopped:
                continue
            v0 = car.v
            v1 = min(max(v0 + car.a * PERIOD, 0.0), car.lane.max_speed)
            self.advance(car, (v0 + v1) / 2 * PERIOD / UNIT)
            car.v = v1
        for cs in self.lane_cars.values():
            cs.sort(key=lambda c: c.pos)
        self.replan()

    def replan(self):
        plans = [(car, *self.plan(car)) for car in self.cars]
        for car, a, stop in plans:
            if stop:
                car.v, car.a, car.stopped = 0.0, STOPPED, True
            else:
                car.a, car.stopped = a, False
        self.xy = [(car, *car.lane.at(car.pos)) for car in self.cars]

    def advance(self, car, units):
        pos = car.pos + units
        while pos >= car.lane.end:
            nxt = self.city.lanes.get(car.next) if car.next is not None else None
            if nxt is None:                     # a dead end: the car goes on elsewhere
                self.place(car)
                return
            pos -= car.lane.end
            self.move_to(car, nxt, pos)
        car.pos = pos

    # ---- what a player sees ------------------------------------------------------------------------
    def car_move(self, car, now):
        nxt = car.next if car.next is not None and (car.lane.end - car.pos) * UNIT <= ANNOUNCE else -1
        return struct.pack('<HIfeeHHhhh', 0x2bd, now, car.pos, car.v, car.a, car.id,
                           car.model, car.lane.id, nxt, -1)

    def commands_near(self, x, y, now):
        """The car moves and lamps within CAST_RANGE of (x, y); now = the server tick of this step."""
        r2 = CAST_RANGE * CAST_RANGE
        out = []
        for car, cx, cy in self.xy:
            if (cx - x) ** 2 + (cy - y) ** 2 <= r2:
                out.append(self.car_move(car, now))
        for lamp, sig, lx, ly in self.city.lamps:
            if (lx - x) ** 2 + (ly - y) ** 2 <= r2:
                go, since = self.city.state(sig, self.t)
                changed = (now - int(since * 1000)) & 0xffffffff if since * 1000 < now else 0
                out.append(struct.pack('<HIii', 0x2c2, changed, lamp, 1 if go else 0))
        return out


def frames(commands):
    """Commands ([u16 type][body] each) packed into frames of at most MAX_OUT bytes, cut between commands."""
    out, chunk, size = [], [], 0
    for c in commands:
        if chunk and size + len(c) > MAX_OUT:
            out.append(chunk)
            chunk, size = [], 0
        chunk.append(c)
        size += len(c)
    if chunk:
        out.append(chunk)
    return [Frame(struct.unpack_from('<H', ch[0])[0], b''.join(ch)[2:]) for ch in out]


class CityTraffic:
    """The city traffic of the native area service (emulator.ini [traffic] city = native)."""
    def __init__(self, data_dir, counts=None, log=lambda s: print(s, flush=True)):
        self.data, self.log = data_dir, log
        self.counts = {**CAR_COUNT, **(counts or {})}
        self.cities = {}            # world city id -> City (loaded on first use), None if it has no .tcs
        self.areas = {}             # area -> AreaTraffic
        self.models = car_models(os.path.join(data_dir, 'Init', 'TrafficFlowControl.xlt'))
        self.task = None

    def city(self, cid):
        if cid not in self.cities:
            folder, name = CITIES.get(cid, (None, None))
            path = os.path.join(self.data, 'tables', folder, name) if name else None
            if path and os.path.exists(path):
                with open(path, 'rb') as f:
                    self.cities[cid] = City(Tcs(f.read()), self.models.get(cid, []))
                c = self.cities[cid]
                self.log(f'city traffic: {folder}: {len(c.lanes)} lanes, {len(c.lamps)} lamps, '
                         f'{len(c.tcs.controllers)} intersections with signals, {len(self.models.get(cid, []))} car models')
            else:
                self.cities[cid] = None
                self.log(f'city traffic: no lanes for city {cid} ({path or "no .tcs: path traffic not done yet"})')
        return self.cities[cid]

    def touch(self, area):
        """A player is in the area: its traffic runs (started if needed)."""
        cid = area_city(area)
        if cid is None or self.counts.get(cid, 0) <= 0:
            return None
        at = self.areas.get(area)
        if at is None:
            city = self.city(cid)
            if city is None or not city.spawn:
                return None
            at = self.areas[area] = AreaTraffic(area, city, self.counts[cid])
            self.log(f'city traffic: area {area} ({CITIES[cid][0]}) starts, {len(at.cars)} cars')
        at.idle_since = None
        if self.task is None or self.task.done():
            self.task = asyncio.get_running_loop().create_task(self.run())
        return at

    async def run(self):
        from .area import worlds
        next_t = time.monotonic()
        while self.areas:
            next_t += PERIOD
            await asyncio.sleep(max(0.0, next_t - time.monotonic()))
            now = tick()
            w = worlds['area']
            for area, at in list(self.areas.items()):
                players = [c for c in w.cars(area).values() if c.pos]
                if not w.cars(area):
                    at.idle_since = at.idle_since or time.monotonic()
                    if time.monotonic() - at.idle_since > IDLE_SECONDS:
                        del self.areas[area]
                        self.log(f'city traffic: area {area} stops (no players)')
                    continue
                try:
                    at.step()
                    for p in players:
                        for f in frames(at.commands_near(*p.pos, now)):
                            p.session.to_client(f)
                except Exception as e:      # a broken step must not stop the other areas
                    self.log(f'city traffic: area {area}: {e!r}')
