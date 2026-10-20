"""The 2016 UI transformation keeps native control types and unrelated layout."""
import unittest
from tools.shop2016 import auction_ui, table


class Shop2016Test(unittest.TestCase):
    def test_table_changes_only_selected_fields_and_keeps_line_endings(self):
        raw = ('a\r\nb\r\nc\r\n0\t0\tx\t0\r\n1\t1\ty\t0\r\n').encode('utf-16')
        out = table(raw, 1, '0', {3: 1})
        self.assertEqual(out.decode('utf-16'), 'a\r\nb\r\nc\r\n0\t0\tx\t1\r\n1\t1\ty\t0\r\n')
        self.assertEqual(table(out, 1, '0', {3: 1}), out)
        with self.assertRaises(ValueError):
            table(raw, 1, 'missing', {3: 1})

    def test_auction_follows_origin_layout_with_2016_columns(self):
        import xml.etree.ElementTree as ET
        from tools.shop2016 import origin_controls, add_pieces, LIST_X

        def control(n, extra=''):
            return (f'<CONTROL B="{n}"><INFO TYPE="1" EC="1" SZ1="1 1" I1_1="0,0~1,1_x.dds" {extra}/>'
                    '<NATION C="0" H="0 0"/></CONTROL>')
        numbers = [1360001, 1360008, 1360012, 1360021, 1360031, 1360032, 1360041, 1360057, 1360058, 1360059]
        own = '<document><DIALOG C="1360000">' + ''.join(control(n) for n in numbers) + '</DIALOG></document>'
        theirs = ('<document><DIALOG C="1360000">' + ''.join(
            f'<CONTROL B="{n}" D="x"><INFO TYPE="3" NM="x" SZ1="9 9" I1_1="5,5~9,9_y.dds"/>'
            f'<NATION C="0" H="{n % 1000} 7"/></CONTROL>' for n in numbers) + '</DIALOG></document>')
        new = auction_ui(own.encode('cp949'), origin_controls(theirs.encode('cp949')))
        self.assertEqual(auction_ui(new, origin_controls(theirs.encode('cp949'))), new)
        got = {int(n.get('B')): n for n in ET.fromstring(new.decode('cp949')).iter('CONTROL')}
        self.assertEqual(got[1360001].find('INFO').get('I1_1'), '5,5~9,9_y.dds')     # Origin frame
        self.assertEqual(got[1360008].find('NATION').get('H'), '8 7')                 # Origin position
        self.assertEqual(got[1360021].find('INFO').get('I1_1'), '0,0~1,1_x.dds')     # own picture
        self.assertEqual(got[1360041].find('INFO').get('SZ1'), '1 1')                 # own NPC crop
        self.assertEqual(got[1360057].find('INFO').get('TYPE'), '3')                  # Origin control
        self.assertIsNone(got[1360057].find('INFO').get('NM'))
        self.assertEqual(got[1360012].find('NATION').get('H'), f'{LIST_X + 133} 149')
        self.assertEqual(got[1360032].find('INFO').get('T1'), 'Days')
        self.assertEqual(got[1360032].find('INFO').get('C1_1'), 'FFFFFF')             # no fill (was white)

    def test_pieces_are_appended_once(self):
        from tools.shop2016 import add_pieces
        import struct
        piece = b'a.dds'.ljust(64, b'\0') + struct.pack('<II', 3, 0) + b'DDS'
        add = add_pieces({'a.dds': piece})
        self.assertEqual(add(b''), piece)
        self.assertEqual(add(piece), piece)
