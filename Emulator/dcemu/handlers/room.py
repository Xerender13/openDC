"""Battle zone rooms (game port 11021): the 2011 client's room messages <-> the 2008 server's.

Offsets are from the type (as the client handlers and the 2008 BS_Pkt structs count them).

XiPvpUserInfo: 2008 (8) u16 Level, u16 Port, u32 Ip. 2011 (12): u32 ? @0 (0x0001a132, 0x00010c5a
    seen), u16 ? @4 (0), u16 port @6, u32 IP @8 (the UDP address the client got in 0x323). Converted
    port/IP across; the 2008 Level from 2011 @2 (always 1 so far) *(guess)*; the client's own
    12 bytes are kept and given back in its 0x1cd.
Room type: 2008 short (bits 0x80 normal room; 0x100 without 0x200 = Real Match, checked by
    Cmd_RoomCreate), 2011 u32 (0x80, 0x580 seen; the client's 0x1cd handler tests 0xc00 and
    0x10000). The server gets the 2008 bits (& 0x3ff), the client the full value back.

0x1cc RoomCreate, C>S: 2008 0x8a: UserInfo @2, i16 RoomType @0xa, u16 MapId @0xc, u16
    PlayerCapacity @0xe, u16 MapFlag @0x10, wchar[30] RoomName @0x12, RoomPass @0x4e.
    2011 0xa4 (builder 0x7e87f0): UserInfo(12) @2, u32 RoomType @0xe, MapId @0x12, PlayerCapacity
    @0x14, MapFlag @0x16 (room options: 0x04/0x08/0x10 traffic low/medium/high), u32 @0x18,
    u32 @0x1c, RoomName @0x20, RoomPass @0x5c, 12 bytes @0x98.
0x1cd RoomCreateAck, S>C: 2008 0x1c: UserInfo @2, i32 Result @0xa, RoomId @0xe, RoomLifeId @0x12,
    i16 RoomType @0x16, MapId @0x18, MapFlag @0x1a. 2011 0x22 (handler 0x52a740): UserInfo(12),
    Result @0xe, RoomId @0x12, RoomLifeId @0x16, u32 RoomType @0x1a, MapId @0x1e, MapFlag @0x20.
0x1ce RoomState (2008, S>C) has no 2011 handler ("Wrong Command: 462", and the rest of the
    frame was lost); **2011 uses 0x1be** (handler 0x52d000, opens the room dialog [ui+0x170]:
    [ui+0x16c] for room type 0x40, else [ui+0x168]):
    2008: Result @2, RoomId @6, RoomLifeId @0xa, MapId @0xe, MapFlag @0x10, i16 RoomType @0x12,
          State @0x14, i16 AreaId @0x16, PlayerCapacity @0x18, ViewerCount @0x1a, RoomReady @0x1c,
          wchar[40] RoomName @0x1e, XiPvpRoomSlot (64) @0x6e, u32 Size @0xae, Unit[Size] @0xb2
          (53: u16 Serial, u16 Age, UserInfo, bool Ready, XiCarAttr, wchar[16] Name).
    2011: the same to @0x12, u32 RoomType @0x12, then the 2008 fields from State on, 2 bytes
          later: State @0x16 ... RoomReady @0x1e, RoomName @0x20, seats u32[32] @0x70, u32 Size @0xf0, Unit[Size] @0xf4 (63: u32 Serial, u16 Age,
          UserInfo(12), bool Ready, XiCarAttr + 4 bytes (12), wchar[16] Name).
Room settings (track, options, slots locked/open): 2011 0x26d both ways (builder 0x7e8b4e, handler
    0x52a7c0 -> room dialog vfunc 0x150), 2008 0x26c both ways (Cmd_RoomModify: applies, then
    sends 0x26c to the room). The 2008 server answered 0x26d with "Wrong Command: 621" (tracks
    and slots could not be changed).
    2008 0x4c: u32 RoomId @2, u16 MapId @6, u16 MapFlag @8, u16 PlayerCapacity @0xa, slots @0xc.
    2011 0x8e: RoomId @2, MapId @6, u32 MapFlag @8, PlayerCapacity @0xc, seats u32[32] @0xe.
XiPvpRoomSlot (seats): 2008 u16[32], 2011 **u32[32]** (64 -> 128 bytes): a player's
    serial, 0 open, 0xffff / 0xffffffff locked. Passing the 2008 table unconverted made a 16-player
    room show 8 seats (seats 1-7 open, 8-15 read as the 0xffff pairs); the client's own changes
    toggled two u16 at a time, which is how the u32 seats showed.
0x1ec PvpResult (race result), S>C: 2008 0x1a + Num x XiPvpResult (52: EndType, Serial, DeltaMoney,
    u64 Money, DeltaExp, Record, u16 Rank, u16 Level @0x1e, XiStrExpInfo @0x20, Point, Flag);
    2011 (handler 0x52ced0 -> room dialog vfunc 0x12c = 0x778980) the same header and 60-byte
    entries: the 2008 fields, then 8 bytes (u32 @0x38 read, -> entry + 0x98 in the dialog). The
    parser compares Level with the character's and plays the level-up when they differ. Unconverted,
    the message was 8 bytes short ("Wrong Packet Size. CMD(492) CmdLen 86, AnalysisSize 80").
0x1b9 RegisterRoomObserverAck (the battle zone lobby), S>C: 2008 0x1a; 2011 0x26: three more
    fields read @0x1a (u32, as a bool), @0x1e, @0x22 (u32 each), passed to the lobby dialog: 0.
"""
import struct

from ..protocol import C2S, S2C
from ..wire import Frame
from . import on

ROOM_MODIFY_2008, ROOM_MODIFY_2011 = 0x26c, 0x26d
SLOT_2008, SEATS = 64, 32


def seats_2011(b):
    return struct.pack('<32I', *(0xffffffff if v == 0xffff else v for v in struct.unpack('<32H', b)))


def seats_2008(b):
    return struct.pack('<32H', *(0xffff if v == 0xffffffff else v & 0xffff for v in struct.unpack('<32I', b)))

ROOM_CREATE, ROOM_CREATE_ACK, ROOM_STATE_2008, ROOM_STATE_2011, OBSERVER_ACK = 0x1cc, 0x1cd, 0x1ce, 0x1be, 0x1b9
TYPE_2008_BITS = 0x3ff
UNIT_2008, UNIT_2011 = 53, 63


def user_info_2008(ui):
    """2011 XiPvpUserInfo (12) -> 2008 (8)."""
    _, level, _, port, ip = struct.unpack('<HHHHI', ui)
    return struct.pack('<HHI', level, port, ip)


def user_info_2011(ui):
    level, port, ip = struct.unpack('<HHI', ui)
    return struct.pack('<HHHHI', 0, level, 0, port, ip)


@on('game', C2S, ROOM_CREATE)
def room_create(session, frame):
    p = frame.payload
    if len(p) != 0xa4 - 2:
        return frame
    ui = p[0:12]
    room_type, map_id, capacity, map_flag = struct.unpack_from('<IHHH', p, 0xc)
    name, password = p[0x1e:0x5a], p[0x5a:0x96]
    session.state['pvp_user_info'] = ui
    session.state['room_type'] = room_type
    session.log.note(f'room create: type {room_type:#x}, map {map_id}, capacity {capacity}, flags {map_flag:#x}, '
                     f'name {name.decode("utf-16-le", "replace").split(chr(0))[0]!r}')
    out = (user_info_2008(ui) + struct.pack('<hHHH', room_type & TYPE_2008_BITS, map_id, capacity, map_flag)
           + name + password)
    return Frame(frame.type, out)


@on('game', S2C, ROOM_CREATE_ACK)
def room_create_ack(session, frame):
    p = frame.payload
    if len(p) != 0x1c - 2:
        return frame
    result, room_id, life_id, room_type, map_id, map_flag = struct.unpack_from('<iIIhHH', p, 8)
    room_type = session.state.get('room_type', room_type & 0xffff)
    ui = session.state.get('pvp_user_info') or user_info_2011(p[0:8])
    return Frame(frame.type, ui + struct.pack('<iIIIHH', result, room_id, life_id, room_type, map_id, map_flag))


@on('game', S2C, ROOM_STATE_2008)
def room_state(session, frame):
    p = frame.payload
    if len(p) < 0xb2 - 2:
        return frame
    count, = struct.unpack_from('<I', p, 0xac)
    if len(p) != 0xb0 + count * UNIT_2008:
        return frame
    room_type, = struct.unpack_from('<h', p, 0x10)
    if session.state.get('room_type') is not None and room_type & TYPE_2008_BITS == session.state['room_type'] & TYPE_2008_BITS:
        room_type = session.state['room_type']
    out = bytearray(p[0:0x10] + struct.pack('<I', room_type & 0xffffffff) + p[0x12:0x6c] + seats_2011(p[0x6c:0xac])
                    + struct.pack('<I', count))
    for k in range(count):
        u = p[0xb0 + k * UNIT_2008:0xb0 + (k + 1) * UNIT_2008]
        serial, age = struct.unpack_from('<HH', u)
        out += (struct.pack('<IH', serial, age) + user_info_2011(u[4:12]) + u[12:13] + u[13:21] + bytes(4) + u[21:53])
    session.log.note(f'room state 0x1ce -> 0x1be: room {struct.unpack_from("<I", p, 4)[0]}, {count} members')
    return Frame(ROOM_STATE_2011, bytes(out))


@on('game', S2C, OBSERVER_ACK)
def observer_ack(session, frame):
    if len(frame.payload) != 0x1a - 2:
        return frame
    return Frame(frame.type, frame.payload + bytes(12))


@on('game', C2S, ROOM_MODIFY_2011)
def room_modify(session, frame):
    p = frame.payload
    if len(p) != 0x8e - 2:
        return frame
    room_id, map_id, map_flag, capacity = struct.unpack_from('<IHIH', p)
    session.log.note(f'room modify: room {room_id}, map {map_id}, flags {map_flag:#x}, capacity {capacity}')
    return Frame(ROOM_MODIFY_2008, struct.pack('<IHHH', room_id, map_id, map_flag & 0xffff, capacity)
                 + seats_2008(p[0xc:0xc + 2 * SLOT_2008]))


@on('game', S2C, ROOM_MODIFY_2008)
def room_modify_ack(session, frame):
    p = frame.payload
    if len(p) != 0x4c - 2:
        return frame
    room_id, map_id, map_flag, capacity = struct.unpack_from('<IHHH', p)
    return Frame(ROOM_MODIFY_2011, struct.pack('<IHIH', room_id, map_id, map_flag, capacity) + seats_2011(p[0xa:0xa + SLOT_2008]))


PVP_RESULT, RESULT_HEAD, RESULT_2008, RESULT_2011 = 0x1ec, 0x1a, 52, 60


@on('game', S2C, PVP_RESULT)
def pvp_result(session, frame):
    p = frame.payload
    head = RESULT_HEAD - 2
    if len(p) < head:
        return frame
    n, = struct.unpack_from('<i', p, 0x16 - 2)
    if n < 0 or len(p) != head + n * RESULT_2008:
        return frame
    units = [p[head + k * RESULT_2008:head + (k + 1) * RESULT_2008] for k in range(n)]
    for u in units:
        serial, = struct.unpack_from('<I', u, 4)
        level, = struct.unpack_from('<H', u, 0x1e)
        session.log.note(f'race result: serial {serial}, rank {struct.unpack_from("<H", u, 0x1c)[0]}, level {level}, '
                         f'+{struct.unpack_from("<I", u, 8)[0]} mito, +{struct.unpack_from("<I", u, 0x14)[0]} exp')
    return Frame(frame.type, p[:head] + b''.join(u + bytes(RESULT_2011 - RESULT_2008) for u in units))
