"""A scripted 2011 client for tests: login, lobby check-in, character creation, entering the game.

    from tools.client import Client
    c = Client('admin', 'admin', ports=TEST_PORTS)      # logs in (c.login_result), checks in to the lobby
    c.create('ZzTest1')                                  # a throwaway character (car type 1)
    c.enter('ZzTest1')                                   # game check-in + LoadChar + JoinChannel
    c.send(0x1b8, payload); frames = c.recv()            # game port

Ports are (auth, lobby, game, area, barea); TEST_PORTS is tools/test_ports.ini's.
"""
import socket
import struct
import time

from dcemu.wire import Frame, FrameReader, write_wstr
from tools.probe_login import login_2011

PORTS = (11005, 11011, 11021, 11031, 11041)
TEST_PORTS = (11105, 11111, 11121, 11131, 11141)
NAME_BYTES = 0x2a


def connect(port, handshake=True, host='127.0.0.1'):
    s = socket.create_connection((host, port), timeout=4)
    if handshake:
        s.recv(56, socket.MSG_WAITALL)
        s.sendall(bytes(56))
    return s


def split(frame, sizes):
    """The commands of a frame, by `sizes` (type -> bytes from the type, or a function of the
    command's bytes); the rest of the frame stays with the first unknown command."""
    data = struct.pack('<H', frame.type) + frame.payload
    out, o = [], 0
    while o + 2 <= len(data):
        t = struct.unpack_from('<H', data, o)[0]
        n = sizes.get(t)
        n = n(data[o:]) if callable(n) else n
        if not n or o + n > len(data):
            out.append(Frame(t, data[o + 2:]))
            break
        out.append(Frame(t, data[o + 2:o + n]))
        o += n
    return out


class Conn:
    def __init__(self, port, handshake=True, host='127.0.0.1'):
        self.sock = connect(port, handshake, host)
        self.reader = FrameReader()
        self.closed = False

    def send(self, msg_type, payload=b''):
        self.sock.sendall(Frame(msg_type, payload).encode())

    def recv(self, wait=0.6):
        """Frames received within `wait` seconds (keepalives 0x02 left out)."""
        out, end = [], time.time() + wait
        while time.time() < end and not self.closed:
            self.sock.settimeout(max(0.01, end - time.time()))
            try:
                data = self.sock.recv(65536)
            except (socket.timeout, TimeoutError):
                break
            except OSError:
                data = b''
            if not data:
                self.closed = True
                break
            out += [f for f in self.reader.feed(data) if isinstance(f, Frame) and f.type != 0x02]
        return out

    def close(self):
        self.sock.close()


class Client:
    def __init__(self, member, password, ports=PORTS, host='127.0.0.1'):
        self.member, self.ports, self.host = member, ports, host
        auth = Conn(ports[0], host=host)
        auth.send(0x14, login_2011(member, password))
        ack = next(f for f in auth.recv(1.5) if f.type == 0x16).payload
        self.ticket, self.login_result = struct.unpack_from('<Ii', ack)
        auth.close()
        self.lobby = self.game = self.area = None
        self.serial = 0
        self.name = None
        self.lobby_ok = False
        if self.login_result == 0:
            self.check_in()

    def check_in(self):
        self.lobby = Conn(self.ports[1], host=self.host)
        p = bytearray(166)
        struct.pack_into('<II', p, 0, 10135, self.ticket)
        write_wstr(p, 8, 80, self.member)
        self.lobby.send(0x29, bytes(p))
        ack = [f for f in self.lobby.recv() if f.type == 0x2a]
        self.lobby_ok = bool(ack) and struct.unpack_from('<I', ack[0].payload)[0] == 0
        return self.lobby_ok

    def create(self, name, car_type=1):
        p = bytearray(NAME_BYTES)
        write_wstr(p, 0, NAME_BYTES, name)
        self.lobby.send(0x52, bytes(p) + struct.pack('<HII', 1, car_type, 0))
        ack = next(f for f in self.lobby.recv(2.0) if f.type == 0x53).payload
        return struct.unpack_from('<qi', ack, NAME_BYTES)

    def enter(self, name, channel='speeding'):
        """-> the frames answered to LoadChar (0x7c ... or an error 0x0001)."""
        self.name = name
        self.game = g = Conn(self.ports[2], host=self.host)
        p = bytearray(0x76)
        write_wstr(p, 8, 80, self.member)
        g.send(0x78, bytes(p))
        g.recv(0.3)
        n = bytearray(NAME_BYTES)
        write_wstr(n, 0, NAME_BYTES, name)
        g.send(0x7b, bytes(n) + struct.pack('<I', 1))
        loaded = g.recv(1.5)
        if any(f.type == 0x32a for f in loaded):
            g.send(0x7d, channel.encode('utf-16-le').ljust(20, b'\0') + struct.pack('<I', 0))
            for f in g.recv(0.5):
                if f.type == 0x7e:
                    self.serial, = struct.unpack_from('<H', f.payload, 20 + 32)
        return loaded

    def send(self, msg_type, payload=b''):
        self.game.send(msg_type, payload)

    def recv(self, wait=0.6):
        return self.game.recv(wait)

    def enter_area(self, area, barea=False):
        self.area = Conn(self.ports[4 if barea else 3], handshake=False, host=self.host)
        p = bytearray(0x38)
        struct.pack_into('<H', p, 0, self.serial)
        write_wstr(p, 2, 42, self.name)
        struct.pack_into('<iii', p, 0x2c - 2, area, 0, 0)
        self.area.send(0x232, bytes(p))
        return self.area.recv(0.4)

    def close(self):
        for c in (self.lobby, self.game, self.area):
            if c:
                c.close()


def error_text(frame):
    """The text of a 0x0001."""
    n, = struct.unpack_from('<H', frame.payload)
    return frame.payload[2:2 + n].decode('utf-16-le', 'replace').rstrip('\0')
