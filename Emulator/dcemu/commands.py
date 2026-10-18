"""Commands inside a frame. The 2008 server packs several commands into one frame
([len][type][body][type][body]...); the client splits them by the byte count each of its
handlers returns. To rewrite one command we split the frame the same way, with the 2008 sizes:
data/packets_2008.tsv (type, BS_Pkt struct, sizeof incl. the 2-byte type; made by
Server/tools/dev/pkt_table.py from ZoneServer.pdb) plus the rules below for variable-length
commands. A split is used only if it covers the frame exactly."""
import os
import struct

from .wire import Frame


def _u32(b, o):
    return struct.unpack_from('<I', b, o)[0] if len(b) >= o + 4 else None


def _load():
    sizes = {}
    path = os.path.join(os.path.dirname(__file__), 'data', 'packets_2008.tsv')
    for line in open(path, encoding='utf-8'):
        t, name, size = line.rstrip('\n').split('\t')
        if size != 'None':
            sizes[int(t, 16)] = (name, int(size))
    return sizes


SIZES = _load()
SIZES[0x16] = ('BS_PktUserAuthAck', 0x4e)     # Cmd_UserAuth's ack; its server list follows
SIZES.setdefault(0x3e1, ('BS_PktInstantStartAck', 6))
# Undercity commands the client sends (2011 senders, ../DriftCityEU-decomp src/re/net_send.c; = the 2008 BS_Pkt sizes):
# the client buffers them, so several can come in one frame (native/game/undercity.py)
for _t, _n, _size in ((0xfa, 'BS_PktUnderCityStage', 0xe), (0x101, 'BS_PktExitUnderCity', 2),
                      (0xbb8, 'BS_PktUCPatrolStart', 0xa), (0xbba, 'BS_PktUCPatrolGiveUp', 6),
                      (0xbbc, 'BS_PktUCPatrolGoalPlace', 0xe), (0xbc2, 'BS_PktUCBossPatrolStart', 0xa),
                      (0xbc4, 'BS_PktUCBossPatrolGiveUp', 6), (0xbc6, 'BS_PktUCBossPatrolGoalPlace', 0x12),
                      (0xc2, 'BS_PktHuvParam', 0x12)):
    SIZES.setdefault(_t, (_n, _size))

# type -> size from the command bytes (b starts at the type), for 2008 commands with a count
VARIABLE = {
    0x17: lambda b: 6 + _u32(b, 2) * 124,       # server list: u32 count, 124-byte entries
    0x3d: lambda b: 0x0a + _u32(b, 6) * 0x78,   # BS_PktUserInfoAck: CharNameNum @6, XiStrCharKey
    0x7c: lambda b: 0xf7 + _u32(b, 0xf3) * 0x2d,  # BS_PktLoadCharAck: m_nCarSize @0xf3, XiStrCarInfo
    0x191: lambda b: 0x0a + _u32(b, 6) * 0x34,  # BS_PktItemListAck: ItemNum @6, XiStrMyItem
    0x192: lambda b: 0x06 + _u32(b, 2) * 0x38,  # BS_PktItemModList: ItemNum @2, XiStrMyItemMod
    0x547: lambda b: 0x0a + _u32(b, 2) * 0x40,  # BS_PktMyStickerListAck: m_nSize @2, XiStrMySTItem
    0x4b1: lambda b: 0x0a + _u32(b, 6) * 0x30,  # BS_PktVisualItemListAck: ItemNum @6, XiStrMyVSItem
    0x4b2: lambda b: 0x06 + _u32(b, 2) * 0x34,  # BS_PktVSItemModList: ItemNum @2, XiStrMyVSItemMod
    0x1a5: lambda b: 0x06 + _u32(b, 2) * 0x24,  # BS_PktItemDataList: ItemNum @2, XiStrIData (sent after 0x191)
    0x1ce: lambda b: 0xb2 + _u32(b, 0xae) * 0x35,  # BS_PktRoomState: m_Size @0xae, Unit (53)
    0x1d0: lambda b: 0x12 + _u32(b, 0xa) * 0x68,   # BS_PktRoomListAck: m_Size @0xa, XiPvpRoomInfo (104)
    0xbe: lambda b: 0x0a + _u32(b, 6) * 0xe,       # BS_PktHuvReq (C>S): m_Size @6, XiHuvInfo (14)
}


def size_2008(b):
    t = struct.unpack_from('<H', b)[0]
    if t in VARIABLE:
        try:
            return VARIABLE[t](b)
        except TypeError:          # count cut off
            return None
    return SIZES.get(t, (None, None))[1]


def split(frame):
    """Frame -> list of single-command Frames, or None if a size is unknown or does not fit."""
    data = struct.pack('<H', frame.type) + frame.payload
    out, o = [], 0
    while o < len(data):
        if len(data) - o < 2:
            return None
        n = size_2008(data[o:])
        if not n or n < 2 or o + n > len(data):
            return None
        out.append(Frame(struct.unpack_from('<H', data, o)[0], data[o + 2:o + n]))
        o += n
    return out


def join(frames):
    first, rest = frames[0], frames[1:]
    return Frame(first.type, first.payload + b''.join(struct.pack('<H', f.type) + f.payload for f in rest))
