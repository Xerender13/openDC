import struct
import unittest

from dcemu.wire import Frame, FrameReader, Raw, read_wstr, write_wstr


class FrameReaderTest(unittest.TestCase):
    def test_split_and_join(self):
        a, b = Frame(0x14, b'abc'), Frame(0x17, b'')
        data = a.encode() + b.encode()
        r = FrameReader()
        self.assertEqual(r.feed(data[:5]), [])
        self.assertEqual(r.feed(data[5:]), [a, b])

    def test_handshake(self):
        r = FrameReader(handshake=56)
        f = Frame(0x7b, b'xy')
        self.assertEqual(r.feed(b'h' * 40), [])
        out = r.feed(b'h' * 16 + f.encode())
        self.assertEqual(out, [Raw(b'h' * 56, 'handshake'), f])

    def test_bad_length_goes_raw(self):
        r = FrameReader()
        out = r.feed(struct.pack('<HH', 2, 1) + b'zz')
        self.assertIsInstance(out[0], Raw)
        self.assertEqual(r.feed(b'more'), [Raw(b'more', 'unframed')])

    def test_huge_length_goes_raw(self):
        r = FrameReader()
        out = r.feed(struct.pack('<HH', 0xfff0, 1) + b'zz')
        self.assertIsInstance(out[0], Raw)       # passed on at once, not buffered

    def test_wstr(self):
        buf = bytearray(16)
        write_wstr(buf, 2, 10, 'abc')
        self.assertEqual(read_wstr(buf, 2, 10), 'abc')
        write_wstr(buf, 2, 10, 'abcde')          # fills the field: no terminator
        self.assertEqual(read_wstr(buf, 2, 10), 'abcde')
        with self.assertRaises(ValueError):
            write_wstr(buf, 2, 10, 'abcdef')


if __name__ == '__main__':
    unittest.main()
