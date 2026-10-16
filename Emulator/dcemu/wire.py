"""Drift City wire format (TCP, plain, little endian).

A frame is [u16 length incl. header][u16 type][payload]. One frame may hold several commands
back to back ([len][type][body][type][body]...): the 2008 server splits them by the size each
handler returns. Some ports start each direction with an unframed 56-byte handshake (protocol.py).
"""
import struct
from dataclasses import dataclass

HEADER = 4
MAX_FRAME = 0xFFFF
SANE_FRAME = 0x4000     # longer "frames" mean we lost the framing: pass bytes on, never wait


@dataclass
class Frame:
    type: int
    payload: bytes

    def encode(self):
        n = HEADER + len(self.payload)
        if n > MAX_FRAME:
            raise ValueError(f'frame 0x{self.type:x} too long ({n} bytes)')
        return struct.pack('<HH', n, self.type) + self.payload


@dataclass
class Raw:
    """Bytes outside the framing: a handshake, or the rest of a stream we lost sync on."""
    data: bytes
    reason: str

    def encode(self):
        return self.data


class FrameReader:
    """Cuts a byte stream into Frames. After a bad length (too short, or too long to be real)
    it stops framing and passes the rest of the stream on as Raw, so a misunderstanding never
    corrupts or stalls the connection."""

    def __init__(self, handshake=0):
        self.buf = bytearray()
        self.handshake = handshake
        self.lost = False

    def feed(self, data):
        self.buf += data
        out = []
        if self.handshake:
            if len(self.buf) < self.handshake:
                return out
            out.append(Raw(bytes(self.buf[:self.handshake]), 'handshake'))
            del self.buf[:self.handshake]
            self.handshake = 0
        if self.lost:
            if self.buf:
                out.append(Raw(bytes(self.buf), 'unframed'))
                self.buf.clear()
            return out
        while len(self.buf) >= HEADER:
            n, t = struct.unpack_from('<HH', self.buf)
            if n < HEADER or n > SANE_FRAME:
                self.lost = True
                out.append(Raw(bytes(self.buf), f'bad length {n}'))
                self.buf.clear()
                break
            if len(self.buf) < n:
                break
            out.append(Frame(t, bytes(self.buf[HEADER:n])))
            del self.buf[:n]
        return out


def read_wstr(buf, off, size):
    """A 0-terminated UTF-16 string from a fixed field of `size` bytes."""
    field = bytes(buf[off:off + size])
    for i in range(0, len(field) - 1, 2):
        if field[i:i + 2] == b'\0\0':
            field = field[:i]
            break
    return field.decode('utf-16-le', 'replace')


def write_wstr(buf, off, size, s):
    """Write `s` as UTF-16 into a fixed field of `size` bytes, 0-padded (no terminator if it
    fills the field exactly, as the 2008 client does for the 32-char password hash)."""
    data = s.encode('utf-16-le')
    if len(data) > size:
        raise ValueError(f'{s!r} does not fit in {size} bytes')
    buf[off:off + size] = data.ljust(size, b'\0')
