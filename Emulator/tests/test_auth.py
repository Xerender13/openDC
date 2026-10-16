import unittest

from dcemu.handlers import auth
from dcemu.wire import Frame, read_wstr
from tools.probe_login import login_2011


class Log:
    def __init__(self):
        self.notes = []

    def note(self, text):
        self.notes.append(text)


class Session:
    def __init__(self):
        self.log, self.state = Log(), {}


class LoginTest(unittest.TestCase):
    def test_2011_login_becomes_2008(self):
        s = Session()
        out = auth.login(s, Frame(0x14, login_2011('admin', 'admin')))
        self.assertEqual(len(out.encode()), 152)
        self.assertEqual(read_wstr(out.payload, auth.ID_AT, auth.ID_SIZE), 'admin')
        self.assertEqual(out.payload[auth.PWD_AT:auth.PWD_AT + 33], b'21232f297a57a5a743894a0e4a801fc3\0')
        self.assertEqual(s.state['user'], 'admin')

    def test_password_encodings(self):
        self.assertEqual(auth.read_password('pw1'.encode('utf-16-le') + bytes(10)), 'pw1')
        self.assertEqual(auth.read_password(b'pw1' + bytes(10)), 'pw1')

    def test_server_list_2011(self):
        e = bytearray(auth.ENTRY_2008)
        e[0x60:0x70] = bytes([127, 0, 0, 1]) * 4
        e[0x70:0x7c] = b''.join(p.to_bytes(2, 'little') for p in (11021, 11011, 11031, 11041, 11400, 11401))
        ack = bytes(auth.ACK_BODY) + (0x17).to_bytes(2, 'little') + (1).to_bytes(4, 'little') + bytes(e)
        out = auth.login_ack(Session(), Frame(0x16, ack)).payload
        body = out[auth.ACK_BODY + 2:]
        self.assertEqual(len(body) + 2, 6 + 0x88)          # what the 2011 0x17 handler consumes
        self.assertEqual(body[4 + 0x64:4 + 0x78], bytes([127, 0, 0, 1]) * 5)
        self.assertEqual(int.from_bytes(body[4 + 0x7a:4 + 0x7c], 'little'), 11011)

    def test_short_login_passes(self):
        s = Session()
        f = Frame(0x14, b'\0' * 20)
        self.assertIs(auth.login(s, f), f)
        self.assertTrue(s.log.notes)


if __name__ == '__main__':
    unittest.main()
