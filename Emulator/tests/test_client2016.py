"""Validate the real Dev Ed port patch without changing any game files."""
from pathlib import Path
import struct
import unittest

from tools import carlimit2016, laa
from tools.client2016 import IMAGE_SHA256, PORT_DATA, PORT_STORE, ROOT, patch_image


class ClientPatch(unittest.TestCase):
    def test_unknown_build_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            patch_image(b'not the supported client')

    @unittest.skipUnless((ROOT/'DriftCity Dev Ed/DriftCity.exe').exists(), 'requires Dev Ed client')
    def test_only_socket_port_changes(self):
        original = carlimit2016.strip((ROOT/'DriftCity Dev Ed/DriftCity.exe').read_bytes())
        import hashlib
        self.assertEqual(hashlib.sha256(laa.normalised(original)).hexdigest(), IMAGE_SHA256)
        patched = patch_image(original)
        self.assertEqual(len(patched), len(original))
        self.assertEqual({i for i, (a, b) in enumerate(zip(original, patched)) if a != b},
                         {PORT_STORE+7, PORT_STORE+8, PORT_DATA, PORT_DATA+1})
        self.assertEqual(struct.unpack_from('<H', patched, PORT_STORE+7)[0], 11105)
        self.assertEqual(struct.unpack_from('<H', patched, PORT_DATA)[0], 11105)
        for va in (0x4b8372, 0x4b8832, 0x4b886c):
            off = va-0x400c00
            self.assertEqual(patched[off:off+5], b'\x68'+struct.pack('<I', 11005))

    @unittest.skipUnless((ROOT/'DriftCity Dev Ed/DriftCity.exe').exists(), 'requires Dev Ed client')
    def test_guided_start_changes_only_the_lobby_comparison(self):
        from tools.tutorial_flow import START_BRANCH, patch_start_branch
        original = carlimit2016.strip((ROOT/'DriftCity Dev Ed/DriftCity.exe').read_bytes())
        ports = patch_image(original)
        guided = patch_image(original, guided=True)
        off, expected = START_BRANCH[2016]
        self.assertEqual(ports[off:off+5], expected)
        self.assertEqual({i for i, (a, b) in enumerate(zip(ports, guided)) if a != b}, {off+2})
        self.assertEqual(guided[off:off+5], bytes.fromhex('83f8017522'))
        self.assertEqual(patch_start_branch(guided, 2016, 4), ports)
        bad = bytearray(ports)
        bad[off] = 0
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            patch_start_branch(bad, 2016, 1)

    @unittest.skipUnless((ROOT/'DriftCity Dev Ed/DriftCity.exe').exists(), 'requires Dev Ed client')
    def test_car_limit_patch_round_trip(self):
        """tools/carlimit2016.py: only the listed sites and the new section change, strip() gives the original back,
        the section bytes are tools/p20_cars.s, and client2016 keeps the patch."""
        original = carlimit2016.strip((ROOT/'DriftCity Dev Ed/DriftCity.exe').read_bytes())
        import hashlib
        self.assertEqual(hashlib.sha256(laa.normalised(original)).hexdigest(), IMAGE_SHA256)
        patched = carlimit2016.apply(original)
        self.assertTrue(carlimit2016.applied(patched) and not carlimit2016.applied(original))
        self.assertEqual(carlimit2016.strip(patched), original)
        self.assertEqual(carlimit2016.apply(patched), patched)
        allowed = set()
        for va, old, new in carlimit2016.PATCHES:
            allowed |= set(range(va-0x401000+0x400, va-0x401000+0x400+len(old)//2))
        changed = {i for i, (a, b) in enumerate(zip(original, patched)) if a != b}
        self.assertTrue(changed - allowed <= set(range(0x100, 0x400)))          # + the PE header fields
        self.assertEqual(patched[len(original):len(original)+len(carlimit2016.P20_CODE)], carlimit2016.P20_CODE)
        built = carlimit2016.build_code()
        if built is not None:
            self.assertEqual(built, carlimit2016.P20_CODE)
        both = patch_image(patched)
        self.assertTrue(carlimit2016.applied(both))
        self.assertEqual(carlimit2016.strip(both), patch_image(original))
        bad = bytearray(original)
        bad[0x7c68a8-0x401000+0x400] ^= 1
        with self.assertRaisesRegex(ValueError, 'unexpected bytes'):
            carlimit2016.apply(bytes(bad))
