import unittest

from dcemu.handlers import lobby
from dcemu.wire import Frame
from tests.test_auth import Session


class UserInfoTest(unittest.TestCase):
    def test_string_inserted(self):
        entry = bytes(range(0x78))
        p = (0).to_bytes(4, 'little') + (1).to_bytes(4, 'little') + entry
        out = lobby.user_info_ack(Session(), Frame(0x3d, p)).payload
        self.assertEqual(len(out) + 2, 0x4a + 0x78)       # what the 2011 handler consumes
        self.assertNotEqual(out[8:10], b'\0\0')           # never the client's empty string
        self.assertEqual(out[8 + 64:], entry)


if __name__ == '__main__':
    unittest.main()


class GameTest(unittest.TestCase):
    def test_load_char_frame(self):
        from dcemu import commands
        from dcemu.handlers import game
        from dcemu.proxy import Session as ProxySession
        char = bytearray(game.CHAR_2008); char[0xb9] = 7
        car = bytes(range(game.CAR_2008))
        cmd_7c = (bytes(8) + bytes(char) + (1).to_bytes(4, 'little') + car)
        frame = Frame(0x32a, bytes(136) + (0x7c).to_bytes(2, 'little') + cmd_7c
                      + (0x1e).to_bytes(2, 'little') + bytes(64))

        class ML:
            def item(self, *a, **k): pass
            def session(self, sid, svc): return Session().log
        import asyncio
        out, changed = asyncio.run(ProxySession('game', None, object(), ML()).handle('S>C', frame))
        data = (0x32a).to_bytes(2, 'little') + out[0].payload
        # 2011 sizes: 0x32a 138, 0x7c 0x129 + 0x31, 0x1e 0x62
        self.assertEqual(len(data), 138 + 0x129 + 0x31 + 0x62)
        c = data[138:]
        self.assertEqual(int.from_bytes(c[:2], 'little'), 0x7c)
        self.assertEqual(c[0x0a + 0xc1], 7)                      # CurCarId moved by 8
        self.assertEqual(int.from_bytes(c[0x125:0x129], 'little'), 1)
        self.assertEqual(c[0x129 + 0x28:0x129 + 0x31], car[0x24:])   # Mitron... after 4 new bytes
        self.assertEqual(int.from_bytes(data[138 + 0x129 + 0x31:][:2], 'little'), 0x1e)
