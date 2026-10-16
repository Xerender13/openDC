"""Area (city, 11031) and BArea (race, 11041) ports.

Move vehicle 0x21d, C>S: the client's own car state, several per frame, many per second.
    2008 BS_PktMoveVehicle (0x60 bytes from the type): XiCarMove @2 = u16 m_Serial, u16 m_Age,
         XiCarAttr m_CarAttr (8), long m_dwGlobalTime, XiVec4 m_Pos @0x10 (payload), XiVec4 m_Vel,
         u16 m_Progress; XiCarState @0x34.
    2011 (0x64 bytes): 4 more bytes after m_CarAttr (always cc cc cc 80 so far: filler), so the
         position is at payload 0x14.
The 2008 server read the 4 extra bytes as the next command: mostly "Wrong Command", but some
values hit real handlers (0x582 NotifyDelCharacter: "Delete Character:hack detected" in the debug
log, and a delete notice over UDP). The race traffic relay (Server/tools/traffic_server.py) reads
the position at payload 0x10, so it saw garbage with the 2011 layout.
Frames hold several commands: 0x21d and 0x239 (6 bytes) are walked here; anything else in the
frame stops the walk and the rest is passed on unchanged.

TrafficAgent.exe (the city traffic, in the server container) connects to the emulator's area port
too (Server/server/TrafficAgent.ini Host=169.254.1.2, the host seen from the container), so the
same setup works with the area proxied or native (dcemu/native/area.py). It sends ~30,000 commands
a second; after its 0x2c1 RegisterAgent its connection is no longer written to the message log.
"""
import struct

from ..protocol import C2S
from ..wire import Frame
from . import on

MOVE, MOVE_2011, MOVE_2008, EXTRA_AT = 0x21d, 0x64, 0x60, 0x0e   # EXTRA_AT: from the type
SIZES_2011 = {MOVE: MOVE_2011, 0x239: 6}


def convert_frame(data):
    """Bytes from the first type to the end of the frame -> (2008 bytes, moves converted)."""
    out, o, n = bytearray(), 0, 0
    while o + 2 <= len(data):
        t = struct.unpack_from('<H', data, o)[0]
        size = SIZES_2011.get(t)
        if not size or o + size > len(data):
            break
        cmd = data[o:o + size]
        if t == MOVE:
            cmd = cmd[:EXTRA_AT] + cmd[EXTRA_AT + 4:]
            n += 1
        out += cmd
        o += size
    return bytes(out + data[o:]), n


def move_vehicle(session, frame):
    data, n = convert_frame(struct.pack('<H', frame.type) + frame.payload)
    if not n:
        return frame
    return Frame(frame.type, data[2:])


def register_agent(session, frame):
    if session.log_frames:
        session.log_frames = False
        session.log.note('TrafficAgent: its frames are not logged')
    return frame


for service in ('area', 'barea'):
    on(service, C2S, MOVE)(move_vehicle)
    on(service, C2S, 0x2c1)(register_agent)
