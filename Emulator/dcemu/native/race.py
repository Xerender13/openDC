"""Race traffic for the native BArea (area.py): the program that fed race traffic to the 2008
server is missing from its package; the TW project replaced it with Server/tools/traffic_server.py
(a relay in the server container, see "Traffic" in the TW project's Server/README.md). Its
simulation (Race: cars along the track's .index paths, junctions, start line kept clear, respawns,
wrecked cars) is used here as it is, loaded from emulator.ini [native] race_traffic_engine; its
data (TrafficServer.ini, PVP_map*/LapTime*.index, trafficCarSettingForTrack_N.txt) from
race_traffic_data (the 2008 server's folder: these files exist only on the server side).

The tracks come from the 2011 client's PVPTrackInfo.xlt, by column name (the 2011 table has more
columns than TW's: New, AI, a 3-column pos_start): the track's first row has Id, pos_start x/y,
CityType (1 city race: PVP_map<city>_<tracknum>.index, cars of track file <city>; 4 lap time:
LapTime<city>_<tracknum>.index, cars of track file 5 + city), city, tracknum.

As in traffic_server.py: the room owner's 0x238 SetAreaMap starts the race (map = track number:
a forward track and its reverse share a start); the track is the one starting within 80 m of the
racer; the other racers join on their next move. Each racer gets 0x21e for the cars within 320 m
once a second; collisions (0x220, 0x223: u16 car id first) wreck the car. Traffic level: the room's
map flags (room_traffic_level; the room's Traffic None / Light / Normal / Heavy / Random option), else
the engine's default (Medium: practice runs without a room, lap time).
"""
import asyncio
import importlib.util
import math
import os
import struct

from ..wire import Frame
from .data import read_xlt

PERIOD = 1.0
START_RANGE = 80.0          # metres from a track's start (traffic_server.find_track)


class RaceTraffic:
    def __init__(self, engine_path, data_dir, track_table, log=lambda s: print(s, flush=True)):
        spec = importlib.util.spec_from_file_location('traffic_engine', engine_path)
        self.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.engine)
        self.engine.log = lambda *a: log(' '.join(map(str, a)))
        self.data = data_dir
        self.tracks = load_tracks(track_table, data_dir)
        self.races = {}             # room -> engine Race
        log(f'race traffic: {len(self.tracks)} tracks with traffic paths')

    def find_track(self, x, y, num):
        tracks = [t for t in self.tracks if t[5] == num and math.dist(t[3:5], (x, y)) < START_RANGE] or self.tracks
        best = min(tracks, key=lambda t: (t[3] - x) ** 2 + (t[4] - y) ** 2, default=None)
        return best if best and math.dist(best[3:5], (x, y)) < START_RANGE else None

    def attach(self, car, room, tracknum):
        """Put the car into its room's race, starting it if needed; False if no track is near."""
        race = self.races.get(room)
        if race is None:
            if not car.pos or tracknum is None:
                return False
            track = self.find_track(*car.pos, tracknum)
            if track is None:
                return False
            race = self.races[room] = self.engine.Race(room, track, self.data, room_traffic_level(room))
            self.engine.log(f'race traffic for area {room}: level {race.level}, {len(race.cars)} cars')
        race.racers.add(car)
        car.race = race
        return True

    def attach_map(self, car, room, map_id):
        """Lap time: the arena's track by its map id (PVPTrackInfo Id); nobody sends 0x238 there, and the
        racers start anywhere on the lap, so the start-position search does not apply."""
        race = self.races.get(room)
        if race is not None and getattr(race, 'map_id', None) != map_id:
            for c in list(race.racers):
                self.detach(c)
            race = None
        if race is None:
            track = next((t for t in self.tracks if t[0] == map_id), None)
            if track is None:
                return False
            race = self.races[room] = self.engine.Race(room, track, self.data, None)
            race.map_id = map_id
        race.racers.add(car)
        car.race = race
        return True

    def lap_track_at(self, pos, default):
        """The lap time track (LapTime*.index) whose start is nearest to pos (within 3 km), else default."""
        laps = [t for t in self.tracks if t[1].startswith('LapTime')]
        best = min(laps, key=lambda t: math.dist(t[3:5], pos[:2]), default=None)
        return best[0] if best and math.dist(best[3:5], pos[:2]) < 3000 else default

    def detach(self, car):
        race = getattr(car, 'race', None)
        if race:
            race.racers.discard(car)
            if not race.racers:
                race.close()
                self.races.pop(race.room, None)
        car.race = None

    @staticmethod
    def hit(car, car_id):
        if getattr(car, 'race', None):
            car.race.hit(car_id)

    @staticmethod
    def snapshot(car, tick):
        """0x21e commands for the cars near this racer, as one frame (or None)."""
        if not getattr(car, 'race', None) or not car.pos:
            return None
        msgs = car.race.snapshot(*car.pos, tick)
        if not msgs:
            return None
        data = b''.join(m[2:] for m in msgs)          # [type][body]... without the lengths
        return Frame(0x21e, data[2:])


def load_tracks(path, data_dir):
    """(id, index file, car settings file, start x, y, track number) of the tracks whose path file
    exists, from the 2011 PVPTrackInfo.xlt."""
    rows = read_xlt(path)
    head = rows[2]
    col = {}
    for i, name in enumerate(head):
        col.setdefault(name, []).append(i)
    c_id, c_pos, c_type = col['Id'][0], col['pos_start'][0], col['CityType'][0]
    c_city, c_num = col['city'][-1], col['tracknum'][0]
    tracks = []
    for r in rows[3:]:
        if len(r) <= c_num or not r[c_id].strip() or not r[c_type].strip():
            continue
        try:
            tid, ctype, city, num = int(r[c_id]), int(r[c_type]), int(r[c_city]), int(r[c_num])
            x, y = float(r[c_pos]), float(r[c_pos + 1])
        except ValueError:
            continue
        if ctype == 1:
            index, cars = f'PVP_map{city}_{num:02}.index', f'trafficCarSettingForTrack_{city}.txt'
        elif ctype == 4:
            index, cars = f'LapTime{city}_{num:02}.index', f'trafficCarSettingForTrack_{5 + city}.txt'
        else:
            continue
        if os.path.exists(os.path.join(data_dir, index)):
            tracks.append((tid, index, cars, x, y, num))
    return tracks


# room map flag bits -> engine level: the client's traffic buttons None / Light / Normal / Heavy / Random are 4 / 8 /
# 0x10 / 0x20 / no bit (0x5bb5f0 -> 0x5bb2c0 selects button 0-4; user: "None" still gave traffic with the Taiwan
# server's mapping, 4 Light ... 0x10 Heavy)
TRAFFIC_BITS = ((0x04, 'None'), (0x08, 'ABit'), (0x10, 'Medium'), (0x20, 'ALot'))


def room_traffic_level(area):
    """The traffic level its room's host chose for the race in this BArea (None: no room)."""
    from .game.rooms import AREA_BASE, rooms
    room = rooms.get(area - AREA_BASE)
    if room is None:
        return None
    return next((name for bit, name in TRAFFIC_BITS if room.map_flag & bit), 'Random')


def lap_map_of(area):
    """The track of the lap time arena racing in this BArea, or None."""
    from .game.rooms import AREA_BASE, rooms
    room = rooms.get(area - AREA_BASE)
    return room.map_id if room is not None and getattr(room, 'lap', None) else None


async def feed(session, traffic, tick):
    """Each second: join the room's race (the owner after its 0x238, the others once the race runs)
    and send the racer the traffic near it (0x21e)."""
    while True:
        await asyncio.sleep(PERIOD)
        car = session.state.get('car')
        if not car or car.area is None:
            continue
        lap_map = lap_map_of(car.area)
        if lap_map is not None and car.pos:
            # the client does not always drive the lap track the server named in 0x528 (user, 2026-10-14: map 70
            # Moon Palace sent, the client raced Cras' 72): the traffic follows the lap track the car is on
            lap_map = traffic.lap_track_at(car.pos, lap_map)
        if lap_map is not None:
            if car.race is None or getattr(car.race, 'map_id', None) != lap_map:
                traffic.detach(car)
                traffic.attach_map(car, car.area, lap_map)
        elif car.race is None and (car.started or car.area in traffic.races):
            traffic.attach(car, car.area, car.tracknum)
        f = traffic.snapshot(car, tick())
        if f:
            session.to_client(f)
            from .area import recorders
            rec = recorders.get(car.area)
            if rec is not None and getattr(rec, 'pov', None) == car.serial:     # one racer's traffic for a replay
                rec(0x21e, f.payload)
