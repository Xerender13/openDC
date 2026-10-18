"""Native area (city, 11031) and BArea (race, 11041) services: the 2008 server's BS_Area.

No handshake on these ports. Both the 2011 client and TrafficAgent.exe (the city traffic program,
Server/server/TrafficAgent.ini) connect here; the agent identifies itself with 0x2c1 RegisterAgent.
Each service has its own areas (0-99, BS_AreaGet); a car is in at most one.

Client (sizes from the type, 2011; the 2008 handlers in Server/tools/dev/dispatch_2008.txt):
  0x232 EnterArea (0x3a): u16 serial, name wchar[21], i32 area @0x2c, i32 group @0x30,
        i32 local time @0x34 -> 0x233 EnterAreaAck: area, result 1, local time, server tick,
        i16 message length 0 + wchar[1]
  0x234 ExitArea (6): u32 area.            0x21c TimeSync (10) -> [0x323 TimeSyncByUDP,] 0x21c: local
        time, server tick (see time_sync)
  0x2aa AreaStatus (2) -> 0x2ab: u32 cars per area x 100
  0x21d MoveVehicle (0x64): XiCarMove (2011: 0x36, 4 more bytes after XiCarAttr; position @0x14)
        + XiCarState (0x2c). The 2008 server relays it to the cars within 300 m (AOI SpaceGrid
        GatherAllMove / PlayerVehicleMove); here as 0x221 MoveVehicleExt (move, state, u32 IP,
        u16 port = 0)  *(guess: which of 0x221/0x224 the 2008 dispatch picks per observer is not
        read yet; only one player has been tested)*. Leaving cars go out as 0x226 RemoveVehicle.
  Moves whose XiCarMove (u16 serial @0, u16 car sort @2) is not the player's own car (the sort of its first
        move in the area; 1 for every player, from 0x7e) are objects the client drives for the game, e.g. the rush boss HUV of its controller
        (car sort from rush.py's pool): kept apart from the player's car (they used to overwrite its position)
        and relayed by their own position. A rush HUV's move carries its 0x45e number at +4 (u16; the player's
        car has 0 there) and its type at +6 (11001 Grime, 10001.. escorts); +2 is a local id of the driving client
        (1357, 15876, 0, 50264...): relayed with +2 = the +4 number, which the other clients know it by.
  0x23d RequestCar (8 + 4 n: u16 n, n x (u16 serial, u16 car sort), 4 bytes; 2008 PacketParser::Cmd_RequestCar 0x5e6cb0)
        -> 0x23e ResponseCar (XiCarMove of that car, 0x36) for each car known: a client asks for a car it gets
        moves of but does not know (the rush boss; unknown here until 2026-10-15, so it asked thousands of
        times and the frames' rest was dropped).
  0x2d0 ObjectUpdate (0x22): relayed to the area as it is.
  0x220 JumpFreeTrafficVehicle (0x52), 0x223 MoveFreeTrafficVehicle (0x36): a traffic car the
        player hit or pushes (thousands per session); relayed as they are to the cars within 300 m.
  0x336 ObserveMode (0xe: i32 on, i32 area, 4 bytes; a battle zone spectator, on BArea): the spectator gets the
        race's moves (0x221 / 0x225 / 0x226) without racing in it: World.observers (user, 2026-10-15: a spectator
        saw nothing; it was dropped, and with the size 0x10 the rest of its frame too).
  0x239 BlockList (6), 0x07 ping (6): accepted, nothing answered.
Undercity areas 100-103 (UC_AREAS; the client loads one after 0xff UnderCityLoad): each party has its own instance
(game/undercity.uc_area_key), without city traffic.
BArea (races): the area is the room id (e.g. 909, any value); moves go to everyone in the room
(the 2008 server's PvP areas: HashedVector::Scan<PvpMove>, no distance).
  0x238 SetAreaMap (0x2c, sent by the room owner at the start): u16 map (track number), u16 max
        traffic, i32 traffic mode, u16 city, char[32] battle string (2011: same layout; the
        string is not initialised); starts the room's race traffic (race.py). 0x23a ClearAreaMap
        (sent on joining and at the end) stops it for this racer.
  0x21e MoveTrafficVehicle (S>C, 20): race traffic from race.py, once a second.
  0x225 JumpVehicle (0x84: XiCarMove, XiCarState, XiVec4 start position, velocity) and 0x226
        RemoveVehicle (0x38: XiCarMove): relayed to the room as they are.
Only the area/barea/UDP handlers of the 2008 server touch its areas (BS_AreaGet, GetArea,
GetAreaDispatch callers), so race results (game port) do not depend on BArea.
City traffic: native (city_traffic.py, emulator.ini [traffic] city = native): each player gets the traffic
cars and signal lamps near it once a second (0x2bd / 0x2c2); a TrafficAgent that still connects is ignored.
With [traffic] city = agent, TrafficAgent.exe does it, relayed here
(the 2008 layouts; it simulates every city car and sends ~30,000 commands a second):
  0x2c1 RegisterAgent (6): i32 area. 0x21c TimeSync (as the client, once a second).
  0x2be CastTCS (0x24): i32 area, f32 x, y, XiTCSCarMove (22)      -> 0x2bd to cars within 320 m
  0x2c3 CastTCSSignal (0x1a): i32 area, f32 x, y, XiTCSSignal (12) -> 0x2c2
  0x2bc CastTraffic (0x20): i32 area, f32 x, y, XiTrafficCarMove (18) -> 0x21e
  0x2c0 FlushCast (2): what was cast since the last flush goes out, one frame per car.
The agent's frames are not logged one by one (a count every minute instead).
Server ticks (0x233, 0x21c) are milliseconds since the emulator started (native.tick).
"""
import asyncio
import socket
import struct
import time

from ..handlers import on, on_open, whole_frames
from ..protocol import C2S
from ..wire import Frame, read_wstr
from . import context, now, tick
from .city_traffic import frames
from .race import feed

AREAS = 100
UC_AREAS = range(100, 104)  # the Undercity (Moon Palace .. Oros, client 0x765950): one instance per party, no traffic
MOVE_RANGE = 300.0          # metres: BS_AreaDispatch move relay (MoveInArea, 0x43960000)
CAST_RANGE = 320.0          # metres: CastTask (0x43a00000)
KEEPALIVE_SECONDS = 3
AGENT_LOG_SECONDS = 60
MOVE_SIZE, CARMOVE_SIZE = 0x62, 0x36   # 0x21d payload (2011); XiCarMove (2011)
POS = 0x14                  # position in the 2011 XiCarMove

# 2011 command sizes from the type, for walking frames that hold several commands
SIZES = {0x236: 6, 0x237: 2, 0x23c: 0x22, 0x23f: 0xa,
         0x232: 0x3a, 0x234: 6, 0x21c: 10, 0x2aa: 2, 0x2ac: 2, 0x21d: 0x64, 0x2d0: 0x22, 0x239: 6,
         0x23a: 2, 0x238: 0x2c, 0x336: 0xe, 0x07: 6, 0x220: 0x52, 0x223: 0x36, 0x225: 0x84, 0x226: 0x38,
         0x23b: 0x3c, 0x2c1: 6, 0x2be: 0x24, 0x2c3: 0x1a, 0x2bc: 0x20, 0x2c0: 2, 0x21f: 0x6c}
CASTS = {0x2be: (0x2bd, 0x24), 0x2c3: (0x2c2, 0x1a), 0x2bc: (0x21e, 0x20)}   # agent -> client type, size


class Car:
    def __init__(self, session, serial, name):
        self.session, self.serial, self.name = session, serial, name
        self.area = None
        self.pos = None             # (x, y) of the last move
        self.move = None            # last 0x21d payload
        self.cast = []              # cast traffic waiting for FlushCast
        self.race = None            # barea: race.py traffic of the room
        self.started, self.tracknum = False, None
        self.group = -1             # party id (EnterGroup), for the party combos
        self.objects = {}           # car sort -> last 0x21d payload of an object this client drives (rush boss)
        self.sort = None            # the player's own car sort (its first move in the area)


class World:
    """One service's areas: area id -> {session id: Car}, and the agent of each area. pvp: moves go
    to the whole area (races) instead of the cars within MOVE_RANGE."""
    def __init__(self, pvp=False):
        self.areas = {}
        self.agents = {}
        self.maps = {}              # area -> SetAreaMap (map, max traffic, mode, city)
        self.pvp = pvp
        self.group_combo = {}       # group (party) id -> combos counted (BS_GroupMgr)
        self.observers = {}         # area -> {session id: Car} of spectators (0x336)

    def cars(self, area):
        return self.areas.get(area, {})

    def enter(self, car, area):
        self.leave(car)
        car.area = area
        self.areas.setdefault(area, {})[car.session.id] = car

    def leave(self, car):
        if car.area is None:
            return
        others = self.areas.get(car.area, {})
        others.pop(car.session.id, None)
        if car.move:
            gone = Frame(0x226, car.move[:CARMOVE_SIZE])
            for o in others.values():
                o.session.to_client(gone)
        if not others and car.area in self.maps:
            del self.maps[car.area]
        if context.race_traffic:
            context.race_traffic.detach(car)
        car.started, car.tracknum = False, None
        car.area, car.pos, car.move = None, None, None
        car.objects, car.sort = {}, None

    def receivers(self, car, r=MOVE_RANGE):
        """The other cars that see this car's moves (and the area's spectators)."""
        others = [c for c in self.cars(car.area).values() if c is not car]
        spectators = [c for c in self.observers.get(car.area, {}).values() if c is not car]
        return (others if self.pvp or not others or not car.pos else list(near(others, *car.pos, r))) + spectators

    def observe(self, car, area):
        """0x336: watch this area's race (None: stop)."""
        for watched in list(self.observers):
            self.observers[watched].pop(car.session.id, None)
            if not self.observers[watched]:
                del self.observers[watched]
        if area is not None:
            self.observers.setdefault(area, {})[car.session.id] = car
            for o in self.cars(area).values():      # the racers as they are now
                if o.move and o is not car:
                    car.session.to_client(Frame(0x221, o.move + bytes(6)))


worlds = {'area': World(), 'barea': World(pvp=True)}


def near(cars, x, y, r):
    r2 = r * r
    for c in cars:
        if c.pos and (c.pos[0] - x) ** 2 + (c.pos[1] - y) ** 2 <= r2:
            yield c


def world_of(session):
    return worlds[session.service]


def car_of(session):
    return session.state.get('car')


def enter_area(session, p):
    serial, = struct.unpack_from('<H', p)
    name = read_wstr(p, 2, 42)
    area, group, local = struct.unpack_from('<iii', p, 0x2c)
    uc = area in UC_AREAS and not world_of(session).pvp
    if area < 0 or (area >= AREAS and not world_of(session).pvp and not uc):
        session.log.note(f'enter area {area}: no such area')
        return
    car = car_of(session) or session.state.setdefault('car', Car(session, serial, name))
    car.serial, car.name = serial, name
    if group >= 0:
        car.group = group
    key = area
    if uc:                                      # the Undercity: the party's own instance (game/undercity.py)
        from .game.undercity import uc_area_key
        key = uc_area_key(serial, area)
    world_of(session).enter(car, key)
    session.log.note(f'{name!r} (serial {serial}) enters area {area}, group {group}' + (f' ({key})' if uc else ''))
    if session.service == 'area' and context.city_traffic and not uc:
        context.city_traffic.touch(area)
    session.to_client(Frame(0x233, struct.pack('<iiII', area, 1, local & 0xffffffff, tick()) + bytes(4)))


def exit_area(session, p):
    car = car_of(session)
    if car:
        world_of(session).leave(car)


def time_sync(session, p):
    """0x21c, and for a client first 0x323 TimeSyncByUDP (local time, tick, u32 IP, u16 port). The 2008
    server sends 0x323 over this connection when the client's UDP time sync (UDP 11400) arrives; the
    2011 client counts them and, after more than 3 time syncs without one, stops part of its city
    update (0x5408fc: [+0x3d304] > 3 and [+0x3d30c] == 0; what that changes is not known).
    UDP still goes to the container, so the area answers it here: the client's
    address as seen on this connection, port 0 (the 2008 server put its own container's view)."""
    t = tick()
    if 'agent' not in session.state:
        ip = session.client_w.get_extra_info('peername')[0] if hasattr(session, 'client_w') else '0.0.0.0'
        session.to_client(Frame(0x323, p[:4] + struct.pack('<I', t) + socket.inet_aton(ip) + bytes(2)))
    session.to_client(Frame(0x21c, p[:4] + struct.pack('<I', t)))


def area_status(session, p):
    w = world_of(session)
    session.to_client(Frame(0x2ab, struct.pack(f'<{AREAS}I', *(len(w.cars(a)) for a in range(AREAS)))))


def move(session, p):
    car = car_of(session)
    if not car or car.area is None:
        return
    sort, huv = struct.unpack_from('<HH', p, 2)
    if car.sort is None and not huv:
        car.sort = sort
    if huv or sort != car.sort:                 # an object this client drives (rush boss, escorts): relayed by its
        if huv:                                 # position, under its HUV number (+4, from 0x45e; +2 is a local id
            p = p[:2] + struct.pack('<H', huv) + p[4:]     # of the client's: 1357, 15876, 0, 50264, ...)
            sort = huv
        car.objects[sort] = p
        w = world_of(session)
        others = [c for c in w.cars(car.area).values() if c is not car]
        out = Frame(0x221, p + bytes(6))
        for o in (others if w.pvp else near(others, *struct.unpack_from('<ff', p, POS), MOVE_RANGE)):
            o.session.to_client(out)
        for o in w.observers.get(car.area, {}).values():
            if o is not car:
                o.session.to_client(out)
        return
    car.move = p
    car.pos = struct.unpack_from('<ff', p, POS)
    receivers = world_of(session).receivers(car)
    if receivers:
        out = Frame(0x221, p + bytes(6))
        for o in receivers:
            o.session.to_client(out)


def request_car(session, p):
    """0x23d -> 0x23e ResponseCar for every requested car this service knows (its last XiCarMove)."""
    n, = struct.unpack_from('<H', p)
    w = world_of(session)
    for k in range(n):
        if 2 + 4 * k + 4 > len(p):
            break
        serial, sort = struct.unpack_from('<HH', p, 2 + 4 * k)
        car = car_of(session)
        watched = next((a for a, obs in w.observers.items() if car and car.session.id in obs), None)
        for c in w.cars(car.area if car and car.area is not None else watched).values():
            m = c.move if sort == c.sort else c.objects.get(sort)
            if c.serial == serial and m:
                session.to_client(Frame(0x23e, m[:CARMOVE_SIZE]))
                break


def object_update(session, p):
    car = car_of(session)
    if car and car.area is not None:
        out = Frame(0x2d0, p)
        for o in world_of(session).cars(car.area).values():
            if o is not car:
                o.session.to_client(out)


def relay_near(t):
    """Relay a command as it is to the cars that see this car (barea: the whole room). Collisions
    with traffic (0x220, 0x223: u16 traffic car id first) also wreck that race traffic car."""
    def relay(session, p):
        car = car_of(session)
        if not car or car.area is None:
            return
        if t in (0x220, 0x223) and context.race_traffic:
            context.race_traffic.hit(car, struct.unpack_from('<H', p)[0])
        if t in (0x220, 0x223) and session.service == 'area' and context.city_traffic:
            context.city_traffic.hit(car.area, struct.unpack_from('<H', p)[0])     # Taipei's path traffic
        receivers = world_of(session).receivers(car)
        if receivers:
            out = Frame(t, p)
            for o in receivers:
                o.session.to_client(out)
    return relay


def set_area_map(session, p):
    car = car_of(session)
    if car and car.area is not None:
        m = struct.unpack_from('<HHiH', p)
        world_of(session).maps[car.area] = m
        session.log.note(f'area {car.area}: map {m[0]}, max traffic {m[1]}, traffic mode {m[2]}, city {m[3]}')
        if session.service == 'barea' and context.race_traffic:
            car.started, car.tracknum = True, m[0]
            if context.race_traffic.attach(car, car.area, m[0]):
                session.log.note(f'race traffic: track {car.race.track[0]} ({car.race.track[1]}), {len(car.race.cars)} cars')
            else:
                session.log.note('race traffic: no track starts here yet (tried again each second)')


def clear_area_map(session, p):
    car = car_of(session)
    if car and car.area is not None:
        world_of(session).maps.pop(car.area, None)
        if context.race_traffic:
            context.race_traffic.detach(car)
        car.started = False


def register_agent(session, p):
    area, = struct.unpack_from('<i', p)
    st = session.state
    if not st.get('agent'):
        st['agent'] = set()
        session.log_frames = False
        session.log.note('TrafficAgent: its frames are counted, not logged'
                         + (' (and ignored: the city traffic is native)' if context.city_traffic else ''))
    st['agent'].add(area)
    if not context.city_traffic:
        world_of(session).agents[area] = session


def flush_cast(session):
    """FlushCast: each car near the cast traffic gets what was cast for it, in as few frames as fit
    (cut between commands: a 4096-byte cut split a command over two frames)."""
    for car in session.state.pop('cast_to', {}).values():
        commands, car.cast = car.cast, []
        for f in frames(commands):
            car.session.to_client(f)


def cast(session, data, o, t):
    """One CastTCS / CastTCSSignal / CastTraffic at data[o:]: queued for the cars within 320 m."""
    if context.city_traffic:
        return
    out_type, size = CASTS[t]
    area, x, y = struct.unpack_from('<iff', data, o + 2)
    if t == 0x2be:          # the traffic cars the agent drives per area (u16 car id @12 of XiTCSCarMove), for the log
        session.state.setdefault('agent_cars', {}).setdefault(area, set()).add(struct.unpack_from('<H', data, o + 0xe + 12)[0])
    cars = world_of(session).areas.get(area)
    if not cars:
        return
    hit = list(near(cars.values(), x, y, CAST_RANGE))
    if hit:
        body = struct.pack('<H', out_type) + data[o + 0xe:o + size]
        pending = session.state.setdefault('cast_to', {})
        for c in hit:
            c.cast.append(body)
            pending[c.session.id] = c


def area_chat(session, p):
    """0x23b AreaChat (wchar[10] "area", wchar[16] player @0x14, u32 colour @0x34, u16 length @0x38, text):
    the city chat (Cmd_AreaChat 0x5e90f0): to every car in the area, the sender's name filled in."""
    car = car_of(session)
    if not car or car.area is None:
        return
    out = Frame(0x23b, p[:0x14] + car.name.encode('utf-16-le')[:30].ljust(32, b'\0') + p[0x34:])
    for o in world_of(session).cars(car.area).values():
        o.session.to_client(out)


# ---- party combos (2008 Cmd_EnterGroup, Cmd_ExitGroup, Cmd_GroupCombo, Cmd_GroupComboReset, BS_GroupMgr) -----
# 0x236 EnterGroup (i32 group = the party id) -> 0x242 (i32 group, u32 the group's combo count); 0x237
# ExitGroup. 0x23c GroupCombo (i32 serial, i32 group, i32 combo type, i32 combo time, f32 turbo bonus, i32
# turbo timer, u32 my total combo, u32 my party combo; 34 bytes, in 2011 too: it comes in one frame with a
# 0x21d move, and without its size here the whole frame, move included, was dropped): the group's count
# + 1, and the message goes to every car of the group with the count as "my party combo" @0x1e. 0x23f
# GroupComboReset (serial, group): the count back to 0. Groups 0 .. 29999 (user, 2026-10-13: party combos
# did not work).
MAX_GROUP = 30000


def group_cars(world, group):
    return [c for cars in world.areas.values() for c in cars.values() if c.group == group]


def enter_group(session, p):
    car = car_of(session)
    group, = struct.unpack_from('<i', p)
    if car:
        car.group = group
    if 0 <= group < MAX_GROUP:
        session.to_client(Frame(0x242, struct.pack('<iI', group, world_of(session).group_combo.get(group, 0))))


def exit_group(session, p):
    car = car_of(session)
    if car:
        w, group = world_of(session), car.group
        car.group = -1
        if group >= 0 and not group_cars(w, group):
            w.group_combo.pop(group, None)


def group_combo(session, p):
    w = world_of(session)
    group, = struct.unpack_from('<i', p, 4)
    if not car_of(session) or not 0 <= group < MAX_GROUP:
        return
    w.group_combo[group] = count = w.group_combo.get(group, 0) + 1
    out = Frame(0x23c, p[:0x1c] + struct.pack('<I', count))
    for c in group_cars(w, group):
        c.session.to_client(out)


def group_combo_reset(session, p):
    group, = struct.unpack_from('<i', p, 4)
    if 0 <= group < MAX_GROUP:
        world_of(session).group_combo[group] = 0


HANDLERS = {0x23d: request_car, 0x236: enter_group, 0x237: exit_group, 0x23c: group_combo, 0x23f: group_combo_reset,
            0x23b: area_chat, 0x232: enter_area, 0x234: exit_area, 0x21c: time_sync, 0x2aa: area_status, 0x21d: move,
            0x2d0: object_update, 0x2c1: register_agent, 0x220: relay_near(0x220), 0x223: relay_near(0x223),
            0x225: relay_near(0x225), 0x226: relay_near(0x226), 0x21f: relay_near(0x21f), 0x238: set_area_map, 0x23a: clear_area_map}

def observe_mode(session, p):
    on, area = struct.unpack_from('<ii', p)
    car = car_of(session) or session.state.setdefault('car', Car(session, 0, ''))
    world_of(session).observe(car, area if on else None)
    session.log.note(f'spectator view {"on" if on else "off"}: area {area}')


HANDLERS[0x336] = observe_mode
IGNORED = {0x239, 0x07, 0x2ac}


def dispatch(session, frame):
    """Walk the commands of a frame by their 2011 sizes; stop at an unknown one."""
    data = struct.pack('<H', frame.type) + frame.payload
    o, n = 0, len(data)
    while o + 2 <= n:
        t = struct.unpack_from('<H', data, o)[0]
        size = SIZES.get(t)
        if t == 0x23b and o + 0x3c <= n:            # AreaChat: 0x3c + u16 characters @0x3a
            size = 0x3c + 2 * struct.unpack_from('<H', data, o + 0x3a)[0]
        if t == 0x23d and o + 4 <= n:               # RequestCar: 8 + 4 x u16 count @2
            size = 8 + 4 * struct.unpack_from('<H', data, o + 2)[0]
        if not size or o + size > n:
            session.log.note(f'unknown or cut command 0x{t:04x} at {o} of {n}: rest dropped')
            break
        if t in CASTS:
            cast(session, data, o, t)
        elif t == 0x2c0:
            flush_cast(session)
        elif t in HANDLERS:
            HANDLERS[t](session, data[o + 2:o + size])
        if 'agent' in session.state:
            session.state['agent_cmds'] = session.state.get('agent_cmds', 0) + 1
        o += size


async def keepalive(session):
    """0x02 (time_t) every 3 s, as the 2008 area port; the agent's command count once a minute;
    the car leaves its area when the connection closes."""
    last = time.monotonic()
    try:
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            session.to_client(Frame(0x02, struct.pack('<I', now() & 0xffffffff)))
            if 'agent' in session.state and time.monotonic() - last >= AGENT_LOG_SECONDS:
                last = time.monotonic()
                per_area = {a: len(c) for a, c in sorted(session.state.pop('agent_cars', {}).items())}
                session.log.note(f'TrafficAgent: {session.state.pop("agent_cmds", 0)} commands '
                                 f'in the last {AGENT_LOG_SECONDS} s, areas {sorted(session.state["agent"])}, '
                                 f'traffic cars per area {per_area}')
    finally:
        w = world_of(session)
        car = car_of(session)
        if car:
            w.leave(car)
            w.observe(car, None)
        for a in session.state.get('agent', ()):
            if w.agents.get(a) is session:
                del w.agents[a]


async def race_feed(session):
    if context.race_traffic:
        await feed(session, context.race_traffic, tick)


on_open('native:barea')(race_feed)
for _svc in ('area', 'barea'):
    _key = 'native:' + _svc
    whole_frames(_key)
    on_open(_key)(keepalive)
    for _t in SIZES:
        on(_key, C2S, _t)(dispatch)
