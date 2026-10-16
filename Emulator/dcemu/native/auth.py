"""Native auth service (11005): login and the server list, in the 2011 client's layouts.

Login 0x14, C>S (2011, 0x9a from the type): u32 version @0 (payload), UTF-16 ID @4 (80 bytes),
password @0x54 (64 bytes, plain text, ASCII), 4 more bytes. Checked like the 2008 server's
getAccInfo: MEUSERMT row for the ID, PASSWORD = lowercase MD5 hex of the password, VALID = 'y'.
An ID without a row is registered with the password typed (emulator.ini [auth] auto_register): the
login then goes on as for an existing account. Empty passwords and IDs outside REGISTER_ID are refused.

Reply: one frame with
    0x16 LoginAck  (0x4e from the type): u32 ticket, i32 result, 68 bytes (0 from the 2008 server).
                   Result codes of the 2011 US client (nation 1; client 0x50cb10, texts GlobalText):
                   0 OK, 1 wrong password (10046), 2 unknown ID (10047), 4 no ID / password (10049),
                   12 account blocked (11417); any other code shows "Authentication system
                   abnormal.(%d)" (10045), as the 2008 server's -1 / -2 / -3 did (user, 2026-10-13).
    0x17 ServerList: u32 count, entries of 0x88 bytes (layout in handlers/auth.py), built from the
                   2008 server's serverlist.txt plus our ranking service. Its 127.0.0.1 addresses go out
                   as the address the client connected to (a client on the network gets the host's
                   network address, the local one 127.0.0.1).
The ticket is checked again by the lobby (check-in 0x29).
"""
import hashlib
import os
import re
import secrets
import socket
import struct
from dataclasses import dataclass

from ..handlers import on
from ..protocol import C2S
from ..wire import Frame, read_wstr
from ..handlers.auth import read_password
from . import context, ticket_for

LOGIN, LOGIN_ACK, SERVER_LIST = 0x14, 0x16, 0x17
OK, WRONG_PASSWORD, UNKNOWN_ID, NO_ID, SUSPENDED = 0, 1, 2, 4, 12
REGISTER_ID = re.compile(r'[A-Za-z0-9_.-]{1,32}')   # MEMBERID is varchar(32); '$' marks deleted characters' owners
REGISTER_SQL = """SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM MEUSERMT WHERE MEMBERID=%s)
  INSERT INTO MEUSERMT (MEMBERID, PASSWORD, VALID, JOINDATE) VALUES (%s, %s, 'y', GETDATE());
SELECT @@ROWCOUNT"""


@dataclass
class ServerEntry:
    server_id: int
    name: str
    lobby: tuple
    game: tuple
    area: tuple
    barea: tuple
    udp_ports: tuple = (11400, 11401)

    def encode(self, ranking_port, host=None):
        """host: the address the client reached us at. Loopback addresses of serverlist.txt are sent as
        that address, so the same list serves the local client and clients on the network."""
        ip = lambda a: socket.inet_aton(host if host and a[0].startswith('127.') else a[0])
        e = self.name.encode('utf-16-le')[:62].ljust(64, b'\0')
        e += struct.pack('<Iff', self.server_id, 0.0, 100.0)
        e += struct.pack('<I', 1)                                  # status: open
        e += bytes(4 * 5)                                          # user counts
        e += ip(self.game) + ip(self.lobby) + ip(self.area) + ip(self.barea) + ip(self.lobby)  # + ranking
        e += struct.pack('<7H', self.game[1], self.lobby[1], self.area[1], self.barea[1],
                         *self.udp_ports, ranking_port)
        return e + bytes(2)


def load_server_list(path):
    """serverlist.txt (2008 server): `id name lobby-ip port<TAB>game-ip port<TAB>area-ip port<TAB>
    barea-ip port<TAB>max`, one server per line."""
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        f = line.replace('\t', ' ').split()
        if len(f) >= 10 and f[0].isdigit():
            addr = [(f[i], int(f[i + 1])) for i in (2, 4, 6, 8)]
            out.append(ServerEntry(int(f[0]), f[1], *addr))
    return out


async def check_login(member, password):
    if not member or not password:
        return NO_ID
    row = await context.db.row('SELECT PASSWORD, VALID FROM MEUSERMT WHERE MEMBERID=%s', (member,))
    if not row:
        return await register(member, password)
    stored, valid = row
    if (stored or '').lower() != hashlib.md5(password.encode('utf-8')).hexdigest():
        return WRONG_PASSWORD
    if (valid or 'y').strip().lower() != 'y':
        return SUSPENDED
    return OK


async def register(member, password):
    """A new account for an unknown ID (password already checked as not empty)."""
    if not context.auto_register or not REGISTER_ID.fullmatch(member):
        return UNKNOWN_ID
    md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
    added, = await context.db.row(REGISTER_SQL, (member, member, md5))
    print(f'auth: registered account {member!r}' if added else f'auth: account {member!r} appeared meanwhile', flush=True)
    return OK if added else await check_login(member, password)


@on('native:auth', C2S, LOGIN)
async def login(session, frame):
    p = frame.payload
    member = read_wstr(p, 4, 80)
    password = read_password(p[0x54:0x94])
    result = await check_login(member, password)
    ticket = ticket_for(member) if result == OK else secrets.randbits(31) | 1
    session.log.note(f'login {member!r}: result {result}')
    ack = struct.pack('<Ii', ticket, result) + bytes(0x4c - 8)
    host = session.client_w.get_extra_info('sockname')[0]
    servers = b''.join(s.encode(context.ranking_port, host) for s in context.server_list)
    body = ack + struct.pack('<HI', SERVER_LIST, len(context.server_list)) + servers
    session.to_client(Frame(LOGIN_ACK, body))


@on('native:auth', C2S, 0x18)
async def auth_close(session, frame):
    session.log.note('0x18 (after the login)')


@on('native:auth', C2S, 0x1b5)
async def unknown_437(session, frame):
    pass
