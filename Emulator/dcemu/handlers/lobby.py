"""Lobby port (11011).

User info 0x3d, S>C (answer to 0x3c): the account's characters.
    2008 (PacketParser::Cmd_UserInfo 0x619380): u32 @0, u32 count @4, count x 0x78-byte
         character entries @8
    2011 (client handler 0x528e40, size 0x4a + count * 0x78 from the type): the same with a
         64-byte UTF-16 string inserted @8, before the entries
The client compares the string with one it keeps (empty at first) and, when they match and there
are characters, says "We apologize for the inconvenience. Please log-in again." (text 10988).
What the real server put there is unknown; a value that never matches is sent.
"""
import secrets

from ..protocol import C2S, S2C
from ..wire import Frame
from . import on

USER_INFO_ACK = 0x3d
STRING_AT, STRING_SIZE = 8, 64


@on('lobby', S2C, USER_INFO_ACK)
def user_info_ack(session, frame):
    p = frame.payload
    token = secrets.token_hex(8).encode('utf-16-le').ljust(STRING_SIZE, b'\0')
    session.log.note(f'user info: {int.from_bytes(p[4:8], "little")} characters, 64-byte string inserted')
    return Frame(frame.type, p[:STRING_AT] + token + p[STRING_AT:])


CHECK_IN_LOBBY, CHECK_IN_2008 = 0x29, 0x9e


@on('lobby', C2S, CHECK_IN_LOBBY)
def check_in_lobby(session, frame):
    """0x29: 2008 BS_PktCheckInLobby is 0x9e bytes (version, ticket, ID, time, session ticket);
    the 2011 client adds 10 (starting 47 7e, like the login). Cut to the 2008 size."""
    return Frame(frame.type, frame.payload[:CHECK_IN_2008 - 2])
