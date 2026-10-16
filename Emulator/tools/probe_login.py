"""Log in the way the 2011 client does (plain password, 4 extra bytes) and print the replies:
checks the emulator's login path without starting the game.

usage: python3 -m tools.probe_login [user] [password] [host] [port]   (from Emulator/)
"""
import socket
import struct
import sys

from dcemu.protocol import HANDSHAKE, name
from dcemu.wire import Frame, FrameReader, write_wstr

VERSION = 10135


def login_2011(user, password):
    """A 0x14 payload as the 2011 client sends it. The 4 extra bytes start 47 7e (the
    server's "Wrong Command: 32327"); the rest of them is a guess."""
    p = bytearray(148)
    struct.pack_into('<I', p, 0, VERSION)
    write_wstr(p, 4, 80, user)
    write_wstr(p, 0x54, 64, password)
    return bytes(p) + b'\x47\x7e\0\0'


def main():
    args, defaults = sys.argv[1:5], ['admin', 'admin', '127.0.0.1', '11005']
    user, password, host, port = args + defaults[len(args):]
    s = socket.create_connection((host, int(port)), timeout=5)
    s.recv(HANDSHAKE, socket.MSG_WAITALL)        # the server's key
    s.sendall(bytes(HANDSHAKE))                  # ours: cipher type 0, plain traffic
    s.sendall(Frame(0x14, login_2011(user, password)).encode())
    r = FrameReader()
    try:
        while data := s.recv(65536):
            for f in r.feed(data):
                print(f'0x{f.type:04x} {name(f.type):12} {f.payload.hex()}')
                if f.type == 0x16:
                    print('result', int.from_bytes(f.payload[4:8], 'little', signed=True))
    except (socket.timeout, TimeoutError):
        pass


if __name__ == '__main__':
    main()
