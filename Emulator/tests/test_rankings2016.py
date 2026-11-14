"""The 2016 RANKING window's server side (dcemu/native/game/rankings.py).

Layouts: docs/neo_work/RANK_PROTOCOL.md sections 1-7 (0xfa3 / 0xfa5 / 0xfab / 0xfad / 0xfaf / 0xfb1
reply sizes and header offsets, 12 entries a page, the 0x00ff0000 / 0x0000ff01 signatures, 0xfb2 codes
2 and 4). The data itself is ours (see the module docstring) and comes from a stub database.
"""
import asyncio
import struct
import unittest
from unittest.mock import Mock

from dcemu.native import context, version
from dcemu.native.game import rankings
from dcemu.wire import Frame

CHARS = [(101 + i, f'Driver{i:02d}', 10 + i, 5000 - i * 10) for i in range(13)]
TEAMS = [(900 + i, 1 + i, f'Crew{i:02d}', 1000 - i, 5 + i, 7 + i, f'Master{i:02d}', f'202601{i + 1:02d}')
         for i in range(13)]
CHAR_REC, TEAM_REC = 0xc4, 0x96


class FakeDb:
    """SKID_CHARACTER_TB / SKID_TEAM_TB rows only; the handlers' SQL is already ordered."""
    server_id = 2016

    def __init__(self, chars=(), teams=()):
        self.chars = list(chars)
        self.teams = list(teams)
        self.calls = []

    async def execute(self, sql, params=()):
        return True

    async def row(self, sql, params=()):
        return None

    async def rows(self, sql, params=()):
        self.calls.append(sql)
        return list(self.teams if 'SKID_TEAM_TB' in sql else self.chars)


class Session:
    def __init__(self):
        self.state = {}
        self.log = Mock()
        self.sent = []

    def to_client(self, frame):
        self.sent.append(frame)


def dword(frame, frame_off):
    """A u32 at an offset counted from the start of the frame (type included)."""
    return struct.unpack_from('<I', frame.payload, frame_off - 2)[0]


def text(frame, frame_off, size):
    return frame.payload[frame_off - 2:frame_off - 2 + size].split(b'\0', 1)[0]


class Rankings2016Test(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        self.db = FakeDb(CHARS, TEAMS)
        context.db = self.db
        rankings._char_cache, rankings._team_cache = (0, []), (0, [])
        self.s = Session()

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)
        version.configure({'version': '2011'})

    # ---- requests ----------------------------------------------------------------------------------------------------

    def ask(self, handler, msg_type, payload):
        asyncio.run(handler(self.s, Frame(msg_type, payload)))
        self.assertEqual(len(self.s.sent), 1, 'every request needs exactly one answer')
        return self.s.sent[0]

    def char_page(self, page=0, measure=0):
        return self.ask(rankings.ranking_page, 0xfa2, struct.pack('<iIII', -1, page, 12, measure))

    def char_search(self, name, flag=0, measure=0):
        return self.ask(rankings.ranking_search, 0xfa4,
                        struct.pack('<iI', -1, 12) + name.encode('ascii')[:20].ljust(21, b'\0')
                        + bytes(21) + bytes([flag]) + struct.pack('<I', measure))

    def team_page(self, page=0):
        return self.ask(rankings.team_page_request, 0xfaa, struct.pack('<II', page, 12))

    def team_search(self, name):
        return self.ask(rankings.team_search_request, 0xfac,
                        struct.pack('<I', 12) + name.encode('ascii')[:12].ljust(13, b'\0') + bytes(13))

    def honor_page(self, page=0):
        return self.ask(rankings.honor_page_request, 0xfae, struct.pack('<iII', -1, page, 12))

    def honor_search(self, name):
        return self.ask(rankings.honor_search_request, 0xfb0,
                        struct.pack('<iI', -1, 12) + name.encode('ascii')[:20].ljust(21, b'\0') + bytes(21))

    # ---- character page 0xfa2 -> 0xfa3 --------------------------------------------------------------------------

    def test_char_page_sizes(self):
        """0xfa3: (n-1)*0xc4+0xda, i.e. 0x16 + n*0xc4 (0x53f2e0); 12 a page, pages = ceil(n/12)."""
        self.db.chars = []
        rankings._char_cache = (0, [])
        f = self.char_page()
        self.assertEqual(f.type, 0xfa3)
        self.assertEqual(dword(f, 0x0a), 0)                 # n
        self.assertEqual(dword(f, 0x06), 0)                 # pages
        self.assertEqual(len(f.payload) + 2, 0x16)

        self.db.chars = CHARS[:1]
        rankings._char_cache = (0, [])
        self.s.sent.clear()
        f = self.char_page()
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(dword(f, 0x06), 1)
        self.assertEqual(len(f.payload) + 2, 0x16 + CHAR_REC)

        self.db.chars = CHARS
        rankings._char_cache = (0, [])
        self.s.sent.clear()
        f0 = self.char_page(0)
        self.s.sent.clear()
        f1 = self.char_page(1)
        self.assertEqual(dword(f0, 0x06), 2)
        self.assertEqual(dword(f0, 0x0a), 12)
        self.assertEqual(len(f0.payload) + 2, 0x16 + 12 * CHAR_REC)
        self.assertEqual(dword(f1, 0x02), 1)
        self.assertEqual(dword(f1, 0x0a), 1)
        self.assertEqual(len(f1.payload) + 2, 0x16 + CHAR_REC)

    def test_char_page_header(self):
        """page @2, pages @6, n @0xa, 0x00ff0000 @0xe, the request's measure echoed @0x12."""
        f = self.char_page(measure=1)
        self.assertEqual(dword(f, 0x02), 0)
        self.assertEqual(dword(f, 0x0e), 0x00ff0000)
        self.assertEqual(dword(f, 0x12), 1)
        self.assertEqual(f.payload[0x0e - 2:0x12 - 2], b'\x00\x00\xff\x00')

    def test_char_page_record(self):
        """0xc4: CID @0, rank @4, level @8, name @0xc, CID @0xa4, level @0xa8, EXP @0xac and @0xb4."""
        f = self.char_page()
        base = 0x16
        cid, name, level, exp = CHARS[0]
        self.assertEqual(dword(f, base + 0x00), cid)
        self.assertEqual(dword(f, base + 0x04), 1)
        self.assertEqual(dword(f, base + 0x08), level)
        self.assertEqual(text(f, base + 0x0c, 42).decode('cp949'), name)
        self.assertEqual(f.payload[base + 0x36 - 2:base + 0x5c - 2], bytes(0x26))    # no licence
        self.assertEqual(f.payload[base + 0x5c - 2:base + 0x9c - 2], bytes(0x40))    # no car
        self.assertEqual(dword(f, base + 0xa4), cid)
        self.assertEqual(dword(f, base + 0xa8), level)
        self.assertEqual(dword(f, base + 0xac), exp)
        self.assertEqual(dword(f, base + 0xb0), 0)
        self.assertEqual(dword(f, base + 0xb4), exp)
        self.assertEqual(dword(f, base + 0xb8), 0)
        self.assertEqual(dword(f, base + 0xc0), 0)
        self.assertEqual(dword(f, base + CHAR_REC - 4), 0)     # nothing past 0xc0

    def test_char_page_out_of_range(self):
        """page >= pages (pages > 0) -> 0xfb2 (0x53f190) with code 2 (0x53f2b8; "Bad page request")."""
        f = self.char_page(page=2)
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(len(f.payload) + 2, 6)
        self.assertEqual(dword(f, 0x02), 2)

    def test_char_page_empty_server_still_answers(self):
        self.db.chars = []
        rankings._char_cache = (0, [])
        f = self.char_page(page=0)
        self.assertEqual(f.type, 0xfa3)
        self.assertEqual(dword(f, 0x0a), 0)
        self.assertEqual(len(f.payload) + 2, 0x16)

    def test_char_search_hit(self):
        """0xfa5: keys @2/@6 (= record +0/+4), page @0xa, pages @0xe, n @0x12, 0x0000ff01 @0x16,
        measure @0x1a, records @0x1e (0x53f360)."""
        f = self.char_search('driver12')               # case-insensitive; rank 13 lives on page 1
        self.assertEqual(f.type, 0xfa5)
        self.assertEqual(dword(f, 0x02), CHARS[12][0])
        self.assertEqual(dword(f, 0x06), 13)
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(dword(f, 0x0e), 2)
        self.assertEqual(dword(f, 0x12), 1)
        self.assertEqual(dword(f, 0x16), 0x0000ff01)
        self.assertEqual(dword(f, 0x1a), 0)
        self.assertEqual(len(f.payload) + 2, 0x1e + CHAR_REC)
        self.assertEqual(dword(f, 0x1e + 0x00), CHARS[12][0])
        self.assertEqual(dword(f, 0x1e + 0x04), 13)

    def test_char_search_hit_first_page(self):
        f = self.char_search('Driver00', measure=1)
        self.assertEqual(dword(f, 0x0a), 0)
        self.assertEqual(dword(f, 0x12), 12)
        self.assertEqual(dword(f, 0x1a), 1)
        self.assertEqual(len(f.payload) + 2, 0x1e + 12 * CHAR_REC)

    def test_char_search_miss(self):
        """Not on the ranking -> 0xfb2 code 4 (0x53f2c5; "The user is not on the ranking")."""
        f = self.char_search('nobody')
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(dword(f, 0x02), 4)

    def test_char_search_locate_me_miss(self):
        """flag 1 (the tab's own ask, 0x6b1519): page 0 with key1/key2 = 0."""
        f = self.char_search('nobody', flag=1)
        self.assertEqual(f.type, 0xfa5)
        self.assertEqual(dword(f, 0x02), 0)
        self.assertEqual(dword(f, 0x06), 0)
        self.assertEqual(dword(f, 0x0a), 0)
        self.assertEqual(dword(f, 0x0e), 2)
        self.assertEqual(dword(f, 0x12), 12)

    def test_char_search_locate_me_empty_server(self):
        self.db.chars = []
        rankings._char_cache = (0, [])
        f = self.char_search('nobody', flag=1)
        self.assertEqual(f.type, 0xfa5)
        self.assertEqual(dword(f, 0x12), 0)
        self.assertEqual(len(f.payload) + 2, 0x1e)

    # ---- team page 0xfaa -> 0xfab --------------------------------------------------------------------------------

    def test_team_page_sizes_and_header(self):
        """0xfab: (n-1)*0x96+0xa8 -> 0x12 + n*0x96; page @2, pages @6, n @0xa, 0x00ff0000 @0xe."""
        f = self.team_page()
        self.assertEqual(f.type, 0xfab)
        self.assertEqual(dword(f, 0x02), 0)
        self.assertEqual(dword(f, 0x06), 2)
        self.assertEqual(dword(f, 0x0a), 12)
        self.assertEqual(dword(f, 0x0e), 0x00ff0000)
        self.assertEqual(len(f.payload) + 2, 0x12 + 12 * TEAM_REC)

        self.s.sent.clear()
        f = self.team_page(1)
        self.assertEqual(dword(f, 0x02), 1)
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(len(f.payload) + 2, 0x12 + TEAM_REC)

        self.db.teams = []
        rankings._team_cache = (0, [])
        self.s.sent.clear()
        f = self.team_page()
        self.assertEqual(dword(f, 0x06), 0)
        self.assertEqual(dword(f, 0x0a), 0)
        self.assertEqual(len(f.payload) + 2, 0x12)

        self.db.teams = TEAMS[:1]
        rankings._team_cache = (0, [])
        self.s.sent.clear()
        f = self.team_page()
        self.assertEqual(len(f.payload) + 2, 0x12 + TEAM_REC)

    def test_team_page_record(self):
        """0x96: TEAMPOINT @8, CHANNELWINCNT @0xc, TEAMNAME @0x10, TMARKID @0x2a, TID @0x2e,
        member count @0x36, master @0x46, rank @0x72, CREATEDATE @0x7e (section 5.2)."""
        f = self.team_page()
        base = 0x12
        rank, tid, mark, name, point, wins, members, master, created = (1,) + TEAMS[0]
        self.assertEqual(dword(f, base + 0x08), point)
        self.assertEqual(dword(f, base + 0x0c), wins)
        self.assertEqual(text(f, base + 0x10, 26).decode('cp949'), name)
        self.assertEqual(dword(f, base + 0x2a), mark)
        self.assertEqual(dword(f, base + 0x2e), tid)
        self.assertEqual(dword(f, base + 0x32), 0)
        self.assertEqual(struct.unpack_from('<Q', f.payload, base + 0x36 - 2)[0], members)
        self.assertEqual(text(f, base + 0x46, 42).decode('cp949'), master)
        self.assertEqual(f.payload[base + 0x70 - 2:base + 0x72 - 2], bytes(2))
        self.assertEqual(dword(f, base + 0x72), rank)
        self.assertEqual(struct.unpack_from('<Q', f.payload, base + 0x76 - 2)[0], 0)
        self.assertEqual(text(f, base + 0x7e, 24).decode('ascii'), created)
        self.assertEqual(dword(f, base + TEAM_REC - 4), 0)

    def test_team_page_out_of_range(self):
        f = self.team_page(2)
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(dword(f, 0x02), 2)

    def test_team_search_hit_and_miss(self):
        """0xfad: keys @2/@6 = record +0x2a/+0x2e (0x53f4c8); miss -> code 4."""
        f = self.team_search('crew12')                  # rank 13, page 1
        self.assertEqual(f.type, 0xfad)
        self.assertEqual(dword(f, 0x02), TEAMS[12][1])  # TMARKID
        self.assertEqual(dword(f, 0x06), TEAMS[12][0])  # TID
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(dword(f, 0x0e), 2)
        self.assertEqual(dword(f, 0x12), 1)
        self.assertEqual(dword(f, 0x16), 0x0000ff01)
        self.assertEqual(len(f.payload) + 2, 0x1a + TEAM_REC)
        self.assertEqual(dword(f, 0x1a + 0x2a), TEAMS[12][1])
        self.assertEqual(dword(f, 0x1a + 0x2e), TEAMS[12][0])

        self.s.sent.clear()
        f = self.team_search('no crew')
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(dword(f, 0x02), 4)

    # ---- honor 0xfae -> 0xfaf, 0xfb0 -> 0xfb1 --------------------------------------------------------------------

    def test_honor_page(self):
        """0xfaf: (n-1)*0xc4+0xd6 = 0x12 + n*0xc4; the level stands in at +0xac (ours)."""
        f = self.honor_page()
        self.assertEqual(f.type, 0xfaf)
        self.assertEqual(dword(f, 0x06), 2)
        self.assertEqual(dword(f, 0x0a), 12)
        self.assertEqual(dword(f, 0x0e), 0x00ff0000)
        self.assertEqual(len(f.payload) + 2, 0x12 + 12 * CHAR_REC)
        base = 0x12
        self.assertEqual(dword(f, base + 0x00), CHARS[0][0])
        self.assertEqual(dword(f, base + 0x04), 1)
        self.assertEqual(dword(f, base + 0xa4), CHARS[0][0])
        self.assertEqual(dword(f, base + 0xac), CHARS[0][2])            # level
        self.assertEqual(dword(f, base + 0x08), CHARS[0][2])

        self.s.sent.clear()
        f = self.honor_page(1)
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(len(f.payload) + 2, 0x12 + CHAR_REC)

        self.db.chars = []
        rankings._char_cache = (0, [])
        self.s.sent.clear()
        f = self.honor_page()
        self.assertEqual(dword(f, 0x0a), 0)
        self.assertEqual(len(f.payload) + 2, 0x12)

    def test_honor_page_out_of_range(self):
        f = self.honor_page(2)
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(dword(f, 0x02), 2)

    def test_honor_search_hit_and_miss(self):
        """0xfb1: keys @2/@6 = record +0/+4; miss -> code 4."""
        f = self.honor_search('DRIVER12')
        self.assertEqual(f.type, 0xfb1)
        self.assertEqual(dword(f, 0x02), CHARS[12][0])
        self.assertEqual(dword(f, 0x06), 13)
        self.assertEqual(dword(f, 0x0a), 1)
        self.assertEqual(dword(f, 0x0e), 2)
        self.assertEqual(dword(f, 0x12), 1)
        self.assertEqual(dword(f, 0x16), 0x0000ff01)
        self.assertEqual(len(f.payload) + 2, 0x1a + CHAR_REC)

        self.s.sent.clear()
        f = self.honor_search('nobody')
        self.assertEqual(f.type, 0xfb2)
        self.assertEqual(dword(f, 0x02), 4)

    # ---- C>S 0xfa1 ------------------------------------------------------------------------------------------------

    def test_fa1_is_answered_with_the_login_frame(self):
        """C>S 0xfa1 (0x9a6) -> the login's empty 0xfa1 (0x53f0f0; -1 at +0xd2, login.info_fa0)."""
        f = self.ask(rankings.my_rank_refresh, 0xfa1, struct.pack('<I', 101) + bytes(0x9a4 - 4))
        self.assertEqual(f.type, 0xfa1)
        self.assertEqual(len(f.payload) + 2, 0x9a6)
        self.assertEqual(struct.unpack_from('<i', f.payload, 0xd2 - 2)[0], -1)

    # ---- 2011 -----------------------------------------------------------------------------------------------------

    def test_2011_gets_nothing(self):
        """The 2011 client's 0xfa1 is 0x8b2 and it has no 0xfa2+ (login.info_fa0 keeps the split)."""
        version.configure({'version': '2011'})
        payloads = [(rankings.ranking_page, 0xfa2, struct.pack('<iIII', -1, 0, 12, 0)),
                    (rankings.ranking_search, 0xfa4, struct.pack('<iI', -1, 12) + bytes(21) + bytes(21) + bytes(1)
                     + bytes(4)),
                    (rankings.team_page_request, 0xfaa, struct.pack('<II', 0, 12)),
                    (rankings.team_search_request, 0xfac, struct.pack('<I', 12) + bytes(13) + bytes(13)),
                    (rankings.honor_page_request, 0xfae, struct.pack('<iII', -1, 0, 12)),
                    (rankings.honor_search_request, 0xfb0, struct.pack('<iI', -1, 12) + bytes(21) + bytes(21)),
                    (rankings.my_rank_refresh, 0xfa1, struct.pack('<I', 101) + bytes(0x9a4 - 4))]
        for handler, msg_type, payload in payloads:
            asyncio.run(handler(self.s, Frame(msg_type, payload)))
        self.assertEqual(self.s.sent, [])


if __name__ == '__main__':
    unittest.main()
