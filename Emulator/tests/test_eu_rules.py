"""tools/eu_rules.py: the EU copies of the US client's rule tables (user, 2026-11-14: one US client for both rule
sets; EU = V-grade parts, battle zone by grade, channel battle by grade).

The client is a copy of the real Client US patch packs (the three tables) in a temp dir, or none: nothing of a real
client is read except those packs, and nothing is written to it.
"""
import hashlib
import os
import shutil
import tempfile
import unittest

from dcemu.native.data import part_grade_rule, part_tiers, read_tdf
from tools import agt, eu_rules, global_text

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_US = os.path.join(HERE, '..', 'Client US')
PACKS = ('Patch.000', 'Patch.003', 'Patch.006')
INI = """[client]
version = 2011
[battlezone]
eu.section.11 = Newbie, 1, 3, 3
eu.section.12 = Pro, 4, 9, 4
[cbattle]
eu.main = 0, 6, 0
eu.semi.1 = 0, 1, 3
eu.semi.2 = 0, 1, 6
"""


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


@unittest.skipUnless(all(os.path.exists(os.path.join(CLIENT_US, 'Patch', p)) for p in PACKS),
                     'requires the Client US patch packs')
class EURulesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.client = os.path.join(self.tmp, 'Client US')
        os.makedirs(os.path.join(self.client, 'Patch'))
        for name in PACKS:
            shutil.copy2(os.path.join(CLIENT_US, 'Patch', name), os.path.join(self.client, 'Patch', name))
        self.ini = os.path.join(self.tmp, 'emulator.ini')
        with open(self.ini, 'w') as f:
            f.write(INI)
        self.before = {name: sha(os.path.join(self.client, 'Patch', name)) for name in PACKS}

    def path(self, kind, eu=False):
        rel, _raw, _entry = eu_rules.located(self.client)[kind]
        return os.path.join(self.client, rel + ('.eu' if eu else ''))

    def entry(self, kind, eu=False):
        """One table's bytes from its pack (or pack copy)."""
        _rel, _raw, entry = eu_rules.located(self.client)[kind]
        return dict(agt.read(self.path(kind, eu))[1])[entry[0]]

    def values(self, kind='globalcontent.xlt', eu=True):
        """The EU copy's Value_US column: {key: value}."""
        lines = self.entry(kind, eu).decode('utf-16').lstrip('\ufeff').split('\r\n')
        col = lines[2].split('\t').index('Value_US')
        return {r[3]: r[col] for r in (line.split('\t') for line in lines[3:]) if len(r) > col}

    def text(self, key):
        """GlobalText 11411 / 11409 of the EU copy (a text may hold line breaks inside its quotes)."""
        records = global_text.RECORD.split(self.entry('globaltext.xlt', True).decode('utf-16').lstrip('\ufeff'))
        col = records[0].split('\r\n')[2].split('\t').index('Value_US')
        return next(f[col] for f in (r.split('\t') for r in records[1:])
                    if len(f) > col and f[3] == key)

    def rows(self, pack):
        path = os.path.join(self.tmp, 'table.tdf')
        with open(path, 'wb') as f:
            f.write(pack)
        return read_tdf(path)

    def test_build(self):
        eu_rules.build(self.client, self.ini)
        located = eu_rules.located(self.client)
        for name in located:
            self.assertTrue(os.path.exists(self.path(name, True)), name)
        for name in PACKS:
            path = os.path.join(self.client, 'Patch', name)
            self.assertEqual(sha(path), self.before[name], f'{name} changed')          # X stays as it was
            with open(path, 'rb') as f, open(path + '.eu', 'rb') as g:
                self.assertEqual(f.read()[20:32], g.read()[20:32], f'{name}.eu: header bytes 20-31')
        manifest = dict(eu_rules.read_manifest(self.client))
        self.assertEqual(set(manifest), {'Patch/Patch.000', 'Patch/Patch.003', 'Patch/Patch.006'})
        for rel, digest in manifest.items():
            self.assertEqual(digest, sha(os.path.join(self.client, *rel.split('/'))))
        values = self.values()
        self.assertEqual(values['MinChBattleGrade'], '6')                 # [cbattle] eu.main's min grade
        self.assertEqual(values['MinSemi1ChBattleGrade'], '1')            # eu.semi.1's min grade
        self.assertEqual(values['MinSemi2ChBattleGrade'], '1')
        self.assertEqual(values['MinSemi3ChBattleGrade'], '0')            # no line: no limit
        self.assertEqual(values['MaxBattleNEWBIELevel'], '1000')          # eu.section.11: no level limits
        self.assertEqual(values['MinBattleNEWBIEGrade'], '1')
        self.assertEqual(values['MaxBattleNEWBIEGrade'], '3')
        self.assertEqual(values['MinBattlePROGrade'], '4')                # eu.section.12
        self.assertEqual(values['MinBattlePROLevel'], '1')
        self.assertEqual(values['MinBattle4XGrade11New'], '4')            # rooms.PRO_TIERS_EU
        self.assertEqual(values['MaxBattle16XGrade11New'], '9')
        self.assertEqual(values['MaxBattle8XLevel11New'], '1000')
        self.assertIn('Semi-channel 1: V1-V3, no level limit', self.text('11411'))
        self.assertIn('Mittron charging fees', self.text('11409'))
        before, after = self.rows(self.entry('itemclient.tdf')), self.rows(self.entry('itemclient.tdf', True))
        self.assertEqual(len(before), len(after))
        levels = [i for i, r in enumerate(before) if len(r) > 8 and r[7] not in ('0', '')
                  and r[0] in ('speed', 'accel', 'crash', 'boost')]
        self.assertTrue(levels)                                           # part rows the EU rule covers
        tiers = part_tiers(before)
        for i in levels:
            self.assertEqual(after[i][7], '0', f'row {i}: level not cleared')
        i = levels[-1]
        want = part_grade_rule(before[i][0], before[i][6], int(float(before[i][7])), tiers)
        self.assertEqual(after[i][8], str(want), f'row {i}: V grade')
        self.assertNotEqual(before[i][7], after[i][7])                    # the US table itself is not changed

    def test_remove_restores_the_us_tables(self):
        eu_rules.build(self.client, self.ini)
        # the launcher's EU mode: X -> X.us, X.eu copied over X
        for rel, _digest in eu_rules.read_manifest(self.client):
            x = os.path.join(self.client, *rel.split('/'))
            os.replace(x, x + '.us')
            shutil.copy2(x + '.eu', x)
        eu_rules.remove(self.client)
        for name in PACKS:
            path = os.path.join(self.client, 'Patch', name)
            self.assertEqual(sha(path), self.before[name], f'{name} not put back')
            self.assertFalse(os.path.exists(path + '.us'))
            self.assertFalse(os.path.exists(path + '.eu'))
        self.assertFalse(os.path.exists(os.path.join(self.client, eu_rules.MANIFEST)))

    def test_build_reads_x_us_when_the_eu_copy_is_in_place(self):
        """The EU copy has the grades already (no levels left in ItemClient): building from X would give the level-0
        base grades, building from X.us gives the same tables again and hashes X.us."""
        eu_rules.build(self.client, self.ini)
        located = eu_rules.located(self.client)
        first = {name: self.entry(name, True) for name in located}
        entries = eu_rules.read_manifest(self.client)
        for rel, _digest in entries:
            x = os.path.join(self.client, *rel.split('/'))
            os.replace(x, x + '.us')
            shutil.copy2(x + '.eu', x)
        active = {rel: sha(os.path.join(self.client, *rel.split('/'))) for rel, _ in entries}
        manifest = dict(eu_rules.build(self.client, self.ini))
        for rel, digest in manifest.items():
            x = os.path.join(self.client, *rel.split('/'))
            self.assertEqual(digest, sha(x + '.us'), f'{rel}: manifest is not the hash of X.us')
            self.assertNotEqual(digest, sha(x), f'{rel}: the EU copy was hashed')
            self.assertEqual(sha(x), active[rel], f'{rel}: X was touched')
        for name in located:
            self.assertEqual(self.entry(name, True), first[name], f'{name}.eu was not rebuilt from X.us')
        rows = self.rows(self.entry('itemclient.tdf', True))
        self.assertTrue(any(r[8] not in ('0', '1', '4', '7') for r in rows if len(r) > 8))


if __name__ == '__main__':
    unittest.main()
