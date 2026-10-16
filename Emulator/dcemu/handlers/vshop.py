"""Item shop (drift shop, F4) and visual items (paint, aero, plates...), game port.

XiStrMyVSItem, one owned visual item: 2008 48 bytes, 2011 116 (client: list 0x4b1 handler
0x51b2b0, entries 0x74; changes 0x4b2 handler 0x51b320, entries 0x78 with State):
    @0    CarID, ItemState, TableIdx, InvenIdx                as 2008
    @0x10 PlateName: 2008 20 bytes (10 UTF-16 chars), 2011 40 (20)
    then  Period, UpdateTime, CreateTime                    (2008 @0x24, 2011 @0x38)
    2011: 48 more bytes (unknown, sent as 0) -> 0x74
The 2011 paints carry their colour in PlateName: 10 spaces (the unused name part) and a 9-digit
colour code, 19 characters, too long for the 2008 field (the server says "Unreliable data.").
The server gets the code alone; the client gets the spaces back.

Buy visual item 0x4b3, C>S: 2008 BS_PktBuyVisualItem = TableIdx, CarID, PlateName (20),
PeriodIdx, bool UseMileage, int64 CurCash (0x2b from the type); 2011 has a 40-byte PlateName and
5 more bytes at the end (0 so far).

Visual update 0x425, S>C (BS_PktVisualUpdate: Serial, Age, CarId, XiStrCarInfo): the car record
is 4 bytes longer in 2011 (as in 0x7c, see game.car_2011); without it the client misread the
update (bought wings did not show).

Instant mission start ack 0x3e1, S>C (BS_PktInstantStartAck: TableIdx): the 2011 client (handler
0x51fb40) also reads a u32 @6 and a byte @0xa from the type; without them it read the next bytes
of the stream (and started a party patrol). They are sent as 0.
"""
import struct

from ..protocol import C2S, S2C
from ..wire import Frame
from . import on
from .game import car_2011

VSITEM_2008, VSITEM_2011 = 48, 116
PLATE_2008, PLATE_2011 = 20, 40
PAINT_PAD = 10


def plate_text(raw):
    t = raw.decode('utf-16-le', 'replace')
    return t.split('\0', 1)[0]


def plate_bytes(text, size):
    return text.encode('utf-16-le')[:size - 2].ljust(size, b'\0')


def plate_to_2011(raw):
    t = plate_text(raw)
    if t.isdigit():                               # a paint colour code
        t = ' ' * PAINT_PAD + t
    return plate_bytes(t, PLATE_2011)


def plate_to_2008(raw):
    t = plate_text(raw)
    if len(t) > PAINT_PAD and not t[:PAINT_PAD].strip() and t[PAINT_PAD:].isdigit():
        t = t[PAINT_PAD:]
    return plate_bytes(t, PLATE_2008)


def vsitem_2011(e):
    return e[:0x10] + plate_to_2011(e[0x10:0x24]) + e[0x24:0x30] + bytes(VSITEM_2011 - 0x44)


def entries(blob, size, tail, n):
    """n entries of `size` bytes (a 48-byte item + `tail` bytes) -> 2011 entries"""
    return b''.join(vsitem_2011(blob[k * size:k * size + VSITEM_2008]) + blob[k * size + VSITEM_2008:(k + 1) * size]
                    for k in range(n))


@on('game', S2C, 0x4b1)
def visual_item_list(session, frame):
    p = frame.payload                    # ListUpdate, ItemNum, items
    n = struct.unpack_from('<I', p, 4)[0]
    if len(p) != 8 + n * VSITEM_2008:
        session.log.note(f'visual item list: {n} items in {len(p) - 8} bytes, unchanged')
        return frame
    return Frame(frame.type, p[:8] + entries(p[8:], VSITEM_2008, 0, n))


@on('game', S2C, 0x4b2)
def visual_item_mod_list(session, frame):
    p = frame.payload                    # ItemNum, (item, State) * n
    n = struct.unpack_from('<I', p, 0)[0]
    if len(p) != 4 + n * (VSITEM_2008 + 4):
        session.log.note(f'visual item changes: {n} items in {len(p) - 4} bytes, unchanged')
        return frame
    return Frame(frame.type, p[:4] + entries(p[4:], VSITEM_2008 + 4, 4, n))


@on('game', C2S, 0x4b3)
def buy_visual_item(session, frame):
    p = frame.payload
    if len(p) != 66:
        return frame
    plate = plate_to_2008(p[8:8 + PLATE_2011])
    session.log.note(f'buy visual item {struct.unpack_from("<I", p)[0]:#x}: data {plate_text(p[8:48])!r} -> {plate_text(plate)!r}')
    return Frame(frame.type, p[:8] + plate + p[48:61])


@on('game', S2C, 0x425)
def visual_update(session, frame):
    p = frame.payload                    # Serial, Age, CarId, XiStrCarInfo
    if len(p) != 8 + 45:
        return frame
    return Frame(frame.type, p[:8] + car_2011(p[8:]))


@on('game', S2C, 0x3e1)
def instant_start_ack(session, frame):
    if len(frame.payload) != 4:
        return frame
    return Frame(frame.type, frame.payload + bytes(5))
