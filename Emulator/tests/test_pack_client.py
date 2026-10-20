"""tools/pack_client.py: packs written from loose folders read back the same; the NiSystem pack-only patch."""
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from tools import agt, pack_client

STUB = b'NayaPack' + struct.pack('<iHHi', 0, 1, 1, 0) + bytes.fromhex('075135190406050206472b0f')
DLL = Path(pack_client.ROOT) / 'Emulator/client_backup/DriftCity_Dev_Ed/NiSystem20VC71.dll.orig'


class PackTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / 'Data/World/Cras/Obj').mkdir(parents=True)
        (self.root / 'Data/World/cras.agt').write_bytes(agt.xor(bytearray(STUB)))
        self.files = {'Data/World/Cras/Obj/a.dds': bytes(range(256)) * 300,         # several 16 KiB chunks
                      'Data/World/Cras/b.nif': b'', 'Data/World/Cras/c.LBF': b'x' * 10}
        for name, data in self.files.items():
            (self.root / name).write_bytes(data)
        (self.root / 'Data/World/Cras/cras.ufm').write_bytes(b'kept loose')
        (self.root / 'Data/World/Cras/b.nif.orig').write_bytes(b'backup')
        (self.root / 'Data/World/hitbox.nif').write_bytes(b'no pack')

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_round_trip_keeps_header_and_skips_loose_kinds(self):
        name, n, raw, size = pack_client.pack_one((self.root, 'Data/World/cras.agt', 'Data/World/Cras'))
        self.assertEqual(n, 3)
        pack = self.root / 'Data/World/cras.agt'
        data = pack.read_bytes()
        self.assertEqual(agt.xor_range(data, 0, 32)[20:32], STUB[20:32])        # header 20-31 kept
        raw, entries = agt.index(pack)
        got = {e[0]: agt.extract(raw, e) for e in entries}
        self.assertEqual(got, {'Cras\\' + k.split('Cras/', 1)[1].replace('/', '\\'): v for k, v in self.files.items()})
        self.assertEqual(pack_client.verify_one((self.root, 'Data/World/cras.agt', 'Data/World/Cras'))[2], [])
        self.assertTrue(pack_client.replace_entry(pack, 'cras\\c.lbf', b'new'))
        raw, entries = agt.index(pack)
        self.assertEqual({e[0]: agt.extract(raw, e) for e in entries}['Cras\\c.LBF'], b'new')

    def test_folder_table_is_exact_folders(self):
        table = pack_client.folder_table().split(b'\0')
        self.assertIn(b'\\data\\world\\cras\\', table)
        self.assertNotIn(b'\\data\\world\\', table)                             # Data/World/*.nif stay loose
        self.assertEqual(pack_client.folder_table()[-2:], b'\0\0')

    @unittest.skipUnless(DLL.exists() and shutil.which('as'), 'needs the Dev Ed DLL backup and GNU as')
    def test_patch_changes_only_the_hook_cave_table_and_sizes(self):
        orig = DLL.read_bytes()
        new = pack_client.patched_image(orig, *pack_client.build_cave())
        _, secs = pack_client.sections(new)
        text = pack_client.section_of(secs, pack_client.HOOK)
        hook = text['roff'] + pack_client.HOOK - text['va']
        self.assertEqual(new[hook], 0xe9)
        self.assertEqual(struct.unpack_from('<i', new, hook + 1)[0], pack_client.CAVE - pack_client.HOOK - 5)
        changed = [i for i in range(len(orig)) if orig[i] != new[i]]
        with self.assertRaises(ValueError):                                         # not twice
            pack_client.patched_image(new, *pack_client.build_cave())
        self.assertLess(len(changed), 800)
