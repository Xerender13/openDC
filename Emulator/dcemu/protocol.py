"""Message types we know, for the logs. Add names as they are identified (the 2008 handler
list is in Server/tools/dev/handlers_2008.txt)."""

C2S, S2C = 'C>S', 'S>C'

# Auth, lobby, game and ranking connections start with an unframed 56-byte key exchange in each
# direction (the server sends first); area and barea do not (their first bytes are frames:
# 0x21c time sync, 0x0002 ping). The exchange: two 28-byte units of u64 + 4 x u32 + u32 cipher type (BS_Cipher::RecvKey,
# MergeKey). The keys are XORed; the cipher type comes from the unit received, and type 0
# leaves the traffic plain (CStreamCipher::Encrypt returns the data unchanged).
HANDSHAKE = 56

# service name -> default ports: client-facing (what the 2011 client and serverlist.txt use),
# upstream (the 2008 ZoneServer, moved by docker-compose.yml), handshake bytes per direction
SERVICES = {
    'auth':  (11005, 12005, HANDSHAKE),
    'lobby': (11011, 12011, HANDSHAKE),
    'game':  (11021, 12021, HANDSHAKE),
    'area':  (11031, 12031, 0),
    'barea': (11041, 12041, 0),
    'ranking': (11051, 0, HANDSHAKE),   # 2011 only (RankingTCP): local, the 2008 server has none
}

# The port of the 2011 ranking service, sent as the 7th port of the server list
RANKING_PORT = SERVICES['ranking'][0]

NAMES = {
    0x14: 'Login',
    0x16: 'LoginAck',
    0x17: 'ServerList',
    0x7b: 'GameLogin',
    0x1b5: 'Unknown437',      # 2011 client, auth port; the 2008 server says "Wrong Command: 437"
    0x1c7: 'RealMatchCarInfo',
    0x1ce: 'RoomInfo',
    0x21c: 'RaceTick',
    0x21d: 'RaceState',
    0x21e: 'RaceTraffic',
    0x220: 'TrafficHit',
    0x223: 'TrafficPush',
    0x232: 'RaceJoin',
    0x234: 'RaceLeave',
    0x238: 'RaceStart',
    0x26c: 'RoomOptions',
    0x2bd: 'CityCar',
}


def name(t):
    return NAMES.get(t, '')
