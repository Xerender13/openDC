"""Auth port (11005): the 2011 client's login, made acceptable to the 2008 server.

Login 0x14, C>S. Payload offsets (message offsets are 4 more):
    @0      u32      client version (10135 for the 2011 client)
    @4      80 bytes ID, UTF-16
    @0x54   64 bytes password
The 2008 server (PacketParser::Cmd_UserAuth, which returns 0x96 = type + 148 payload bytes)
reads the password field as a narrow string (strncpy 32 chars in the getAccInfo query object,
0x421e40) and getAccInfo compares it with MEUSERMT.PASSWORD: so 32 lowercase MD5 hex chars in
ASCII. The ack 0x16 has the ticket @0 and the getAccInfo result @4 (0 OK, -1 unknown ID,
-2 wrong password), and the server list 0x17 follows in the same frame either way.
The 2011 client sends the password in plain text (ASCII or UTF-16: not yet seen, both are
read), and 4 more bytes after the 148 (they start 47 7e: the server's "Wrong Command: 32327").
"""
import hashlib

from ..protocol import C2S, RANKING_PORT, S2C
from ..wire import Frame, read_wstr
from . import on

LOGIN, LOGIN_ACK = 0x14, 0x16
RESULTS = {0: 'OK', -1: 'unknown ID', -2: 'wrong password', -3: 'suspended', -4: 'server error'}
PAYLOAD_2008 = 148
ID_AT, ID_SIZE = 4, 80
PWD_AT, PWD_SIZE = 0x54, 64


def md5_hex(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()


def read_password(field):
    """Plain password from the field, UTF-16 if it looks like it (ASCII text has no 0 byte
    after its first character), else a narrow string."""
    if len(field) >= 2 and field[0] and not field[1]:
        return read_wstr(field, 0, len(field))
    return bytes(field).split(b'\0', 1)[0].decode('latin-1')


@on('auth', C2S, LOGIN)
def login(session, frame):
    p = frame.payload
    if len(p) < PAYLOAD_2008:
        session.log.note(f'login payload is {len(p)} bytes, expected >= {PAYLOAD_2008}; passed on unchanged')
        return frame
    user = read_wstr(p, ID_AT, ID_SIZE)
    password = read_password(p[PWD_AT:PWD_AT + PWD_SIZE])
    out = bytearray(p[:PAYLOAD_2008])
    out[PWD_AT:PWD_AT + PWD_SIZE] = md5_hex(password).encode().ljust(PWD_SIZE, b'\0')
    session.state['user'] = user
    extra = p[PAYLOAD_2008:]
    session.log.note(f'login {user!r} version {int.from_bytes(p[:4], "little")}: password hashed, '
                     f'{len(extra)} extra bytes dropped ({extra.hex()})')
    return Frame(frame.type, bytes(out))


# Server list 0x17: u32 count, then one entry per server. The 2008 server packs it into the
# login ack's frame, after the 0x16 body (ACK_BODY bytes; the 2011 client's 0x16 handler
# 0x50cb10 also returns 0x4e = type + ACK_BODY). Entry, 2008 (124 bytes) -> 2011 (136 bytes):
#   @0     64 bytes name (UTF-16)        same
#   @0x40  u32 id, f32 load, f32 max, u32 status (0xc8 / 0x64 / 0x12c are special)   same
#   @0x50  4 x u32 (user counts)         5 x u32: the 5th is new (0 here)
#   @0x60  4 x IPv4                      @0x64 5 x IPv4: the 5th is new (copy of the 1st)
#   @0x70  6 x u16 ports: game, lobby, area, barea, udp, udp
#                                        @0x78 7 x u16: the 7th is new, then 2 pad
# The new IP and port are the ranking server's (the client has a RankingTCP connection and says
# "Server not on ranking" without it); the emulator serves it (protocol.RANKING_PORT).
# Read from the 2011 client: 0x17 handler 0x50e230 (size 6 + count * 0x88), the connect on
# server select 0x536a70 (IPs @0x64-0x74, ports @0x78-0x84).
SERVER_LIST = 0x17
ACK_BODY = 0x4c
ENTRY_2008, ENTRY_2011 = 124, 136


def entry_2011(e):
    return (e[:0x60] + bytes(4)                     # counts + the new one
            + e[0x60:0x70] + e[0x60:0x64]           # IPs + the ranking server's (= the first)
            + e[0x70:0x7c] + RANKING_PORT.to_bytes(2, 'little') + bytes(2))


def server_list_2011(body, log):
    """2008 0x17 body (after its type) -> 2011 body."""
    n = int.from_bytes(body[:4], 'little')
    entries = body[4:]
    if len(entries) != n * ENTRY_2008:
        log.note(f'server list: {n} entries in {len(entries)} bytes, not {ENTRY_2008} each; unchanged')
        return body
    out = bytearray(body[:4])
    for i in range(n):
        e = entries[i * ENTRY_2008:(i + 1) * ENTRY_2008]
        out += entry_2011(e)
        ports = [int.from_bytes(e[0x70 + 2 * k:0x72 + 2 * k], 'little') for k in range(6)]
        log.note(f'server {int.from_bytes(e[0x40:0x44], "little")} {read_wstr(e, 0, 64)!r} '
                 f'ip {".".join(map(str, e[0x60:0x64]))} ports {ports}')
    return bytes(out)


@on('auth', S2C, LOGIN_ACK)
def login_ack(session, frame):
    p = frame.payload
    r = int.from_bytes(p[4:8], 'little', signed=True)
    session.log.note(f'login result {r} ({RESULTS.get(r, "?")})')
    if len(p) > ACK_BODY + 2 and int.from_bytes(p[ACK_BODY:ACK_BODY + 2], 'little') == SERVER_LIST:
        tail = server_list_2011(p[ACK_BODY + 2:], session.log)
        return Frame(frame.type, p[:ACK_BODY + 2] + tail)
    return frame


@on('auth', S2C, SERVER_LIST)
def server_list(session, frame):
    return Frame(frame.type, server_list_2011(frame.payload, session.log))
