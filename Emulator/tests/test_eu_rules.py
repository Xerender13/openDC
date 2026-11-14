"""tools/eu_rules.py: the client's files per setting (user, 2026-11-14: one US client for both rule sets; EU = V-grade
parts, battle zone by grade, channel battle by grade; and the client shows km/h, SPEED_UNITS.md section 6).

The client is a copy of the real Client US files (the patch packs, and for the km/h files Data_US/World.agt with
Assist_Client.tdf, Data_US/gameui/game.nui and Data_US/gameui/uitex.agt) in a temp dir, or none: nothing of a real
client is read except those files, and nothing is written to it.
"""
import hashlib
import os
import shutil
import tempfile
import unittest

from dcemu.native.data import part_grade_rule, part_tiers, read_tdf
from tools import agt, eu_rules, global_text
from tools.ui_texture import entries

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_US = os.path.join(HERE, '..', 'Client US')
PACKS = ('Patch.000', 'Patch.003', 'Patch.006')
ASSIST = 'Data_US/World.agt'
NUI = 'Data_US/gameui/game.nui'
UITEX = 'Data_US/gameui/uitex.agt'
SPEEDO_PIECE = eu_rules.SPEEDO_PIECE
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
EU_RULES_11 = '"Semi-channel 1: V1-V3, no level limit'


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def present(*rels):
    return all(os.path.exists(os.path.join(CLIENT_US, *rel.split('/'))) for rel in rels)


def pack_entry(path, name):
    return dict(agt.read(path)[1])[name]


@unittest.skipUnless(present(*[f'Patch/{p}' for p in PACKS]), 'requires the Client US patch packs')
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

    def real(self, rel):
        """A real client file copied into the temp client (Data_US/...), or None when the real client lacks it."""
        src = os.path.join(CLIENT_US, *rel.split('/'))
        if not os.path.exists(src):
            return None
        dst = os.path.join(self.client, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    def path(self, kind, suffix=''):
        rel, _raw, _entry = eu_rules.located(self.client)[kind]
        return os.path.join(self.client, rel + suffix)

    def entry(self, kind, suffix=''):
        """One table's bytes from its pack (or pack copy)."""
        _rel, _raw, entry = eu_rules.located(self.client)[kind]
        return pack_entry(self.path(kind, suffix), entry[0])

    def values(self, kind='globalcontent.xlt', suffix='.eu'):
        """An .xlt copy's Value_US column: {key: value}."""
        lines = self.entry(kind, suffix).decode('utf-16').lstrip('\ufeff').split('\r\n')
        col = lines[2].split('\t').index('Value_US')
        return {r[3]: r[col] for r in (line.split('\t') for line in lines[3:]) if len(r) > col}

    def text(self, key, suffix='.eu', kind='globaltext.xlt'):
        """One GlobalText copy's Value_US text (a text may hold line breaks inside its quotes)."""
        records = global_text.RECORD.split(self.entry(kind, suffix).decode('utf-16').lstrip('\ufeff'))
        col = records[0].split('\r\n')[2].split('\t').index('Value_US')
        return next(f[col] for f in (r.split('\t') for r in records[1:])
                    if len(f) > col and f[3] == key)

    def rows(self, pack):
        path = os.path.join(self.tmp, 'table.tdf')
        with open(path, 'wb') as f:
            f.write(pack)
        return read_tdf(path)

    def manifest(self):
        return {rel: (digest, modes) for rel, digest, modes in eu_rules.read_manifest(self.client)}

    def test_build(self):
        with open(os.path.join(self.client, eu_rules.OLD_MANIFEST), 'w') as f:      # an older manifest goes
            f.write('; old\nPatch/Patch.000\t' + '0' * 64 + '\n')
        eu_rules.build(self.client, self.ini)
        located = eu_rules.located(self.client)
        for name in located:
            self.assertTrue(os.path.exists(self.path(name, '.eu')), name)
        # the settings that change a file: GlobalText (eu and kph) gets the three copies, the rest one
        self.assertFalse(os.path.exists(self.path('globalcontent.xlt', '.kph')))
        self.assertFalse(os.path.exists(self.path('itemclient.tdf', '.eu.kph')))
        for suffix in ('.eu', '.kph', '.eu.kph'):
            self.assertTrue(os.path.exists(self.path('globaltext.xlt', suffix)), suffix)
        self.assertFalse(os.path.exists(os.path.join(self.client, eu_rules.OLD_MANIFEST)))
        for name in PACKS:
            path = os.path.join(self.client, 'Patch', name)
            self.assertEqual(sha(path), self.before[name], f'{name} changed')          # X stays as it was
            for suffix in (('.eu', '.kph', '.eu.kph') if name == 'Patch.006' else ('.eu',)):
                with open(path, 'rb') as f, open(path + suffix, 'rb') as g:
                    self.assertEqual(f.read()[20:32], g.read()[20:32], f'{name}{suffix}: header bytes 20-31')
        manifest = self.manifest()
        self.assertEqual(set(manifest), {'Patch/Patch.000', 'Patch/Patch.003', 'Patch/Patch.006'})
        self.assertEqual(manifest['Patch/Patch.000'][1], ('eu',))
        self.assertEqual(manifest['Patch/Patch.006'][1], ('eu', 'kph'))
        for rel, (digest, _modes) in manifest.items():
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
        # the EU texts in the .eu copy, the km/h texts in the .kph one, both in .eu.kph
        self.assertEqual(self.text('11874', '.eu'), 'MPH')
        self.assertEqual(self.text('11874', '.kph'), 'KPH')
        self.assertEqual(self.text('11874', '.eu.kph'), 'KPH')
        self.assertEqual(self.text('11527', '.kph'), 'under %d km/h')
        self.assertIn('distance', self.text('10403', '.kph').lower())
        self.assertIn(EU_RULES_11, self.text('11411', '.eu.kph'))
        self.assertNotIn('Semi-channel 1:', self.text('11411', '.kph'))
        before, after = self.rows(self.entry('itemclient.tdf')), self.rows(self.entry('itemclient.tdf', '.eu'))
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
        # the .eu copy of GlobalText has no km/h text (the settings are independent)
        self.assertIn('To Goal', self.text('10216', '.eu'))
        states = eu_rules.status(self.client)
        self.assertEqual([state for _rel, state in states], ['ok'] * len(states))

    def test_remove_restores_the_us_files(self):
        for rel in (ASSIST, NUI, UITEX):
            self.real(rel)
        eu_rules.build(self.client, self.ini)
        # the launcher's choice: the copy with every setting that changes the file
        for rel, _digest, modes in eu_rules.read_manifest(self.client):
            x = os.path.join(self.client, *rel.split('/'))
            copy = x + '.' + '.'.join(modes)
            os.replace(x, x + '.us')
            shutil.copy2(copy, x)
        eu_rules.remove(self.client)
        for name in PACKS:
            path = os.path.join(self.client, 'Patch', name)
            self.assertEqual(sha(path), self.before[name], f'{name} not put back')
            self.assertFalse(os.path.exists(path + '.us'))
        for rel in (ASSIST, NUI, UITEX):
            if not present(rel):
                continue
            path = os.path.join(self.client, *rel.split('/'))
            self.assertTrue(os.path.exists(path), f'{rel} not put back')
            self.assertFalse(os.path.exists(path + '.us'))
        for rel in ('Patch/Patch.000', 'Patch/Patch.003', 'Patch/Patch.006', ASSIST, NUI, UITEX):
            for suffix in ('.eu', '.kph', '.eu.kph'):
                self.assertFalse(os.path.exists(os.path.join(self.client, *rel.split('/')) + suffix),
                                 f'{rel}{suffix} left behind')
        self.assertFalse(os.path.exists(os.path.join(self.client, eu_rules.MANIFEST)))
        self.assertFalse(os.path.exists(os.path.join(self.client, eu_rules.OLD_MANIFEST)))

    def test_build_reads_x_us_when_a_copy_is_in_place(self):
        """The copies have the grades already (no levels left in ItemClient): building from X would give the level-0
        base grades, building from X.us gives the same tables again and hashes X.us."""
        eu_rules.build(self.client, self.ini)
        located = eu_rules.located(self.client)
        first = {name: self.entry(name, '.eu') for name in located}
        kph = {name: self.entry(name, '.kph') for name in located
               if name in ('globaltext.xlt', 'assist_client.tdf')}
        entries = eu_rules.read_manifest(self.client)
        for rel, _digest, modes in entries:
            x = os.path.join(self.client, *rel.split('/'))
            os.replace(x, x + '.us')
            shutil.copy2(x + '.' + '.'.join(modes), x)
        active = {rel: sha(os.path.join(self.client, *rel.split('/'))) for rel, _d, _m in entries}
        manifest = {rel: (digest, modes) for rel, digest, modes in eu_rules.build(self.client, self.ini)}
        for rel, (digest, _modes) in manifest.items():
            x = os.path.join(self.client, *rel.split('/'))
            self.assertEqual(digest, sha(x + '.us'), f'{rel}: manifest is not the hash of X.us')
            self.assertNotEqual(digest, sha(x), f'{rel}: a copy was hashed')
            self.assertEqual(sha(x), active[rel], f'{rel}: X was touched')
        for name in located:
            self.assertEqual(self.entry(name, '.eu'), first[name], f'{name}.eu was not rebuilt from X.us')
        for name, data in kph.items():
            self.assertEqual(self.entry(name, '.kph'), data, f'{name}.kph was not rebuilt from X.us')
        rows = self.rows(self.entry('itemclient.tdf', '.eu'))
        self.assertTrue(any(r[8] not in ('0', '1', '4', '7') for r in rows if len(r) > 8))

    @unittest.skipUnless(present(ASSIST, NUI), 'requires the Client US Assist table and HUD layout')
    def test_kph_files(self):
        """Data_US/World.agt (Assist_Client.tdf) and Data_US/gameui/game.nui: kph copies only."""
        self.real(ASSIST)
        self.real(NUI)
        eu_rules.build(self.client, self.ini)
        manifest = self.manifest()
        self.assertEqual(manifest[ASSIST][1], ('kph',))
        self.assertEqual(manifest[NUI][1], ('kph',))
        self.assertEqual(manifest[ASSIST][0], sha(os.path.join(self.client, *ASSIST.split('/'))))
        for rel in (ASSIST, NUI):
            path = os.path.join(self.client, *rel.split('/'))
            self.assertTrue(os.path.exists(path + '.kph'), rel)
            self.assertFalse(os.path.exists(path + '.eu'), rel)
            self.assertFalse(os.path.exists(path + '.eu.kph'), rel)
        # the Assist table: the rows that said mph now print the value in km/h
        _rel, _raw, entry = eu_rules.located(self.client)['assist_client.tdf']
        before = self.rows(pack_entry(os.path.join(self.client, *ASSIST.split('/')), entry[0]))
        after = self.rows(pack_entry(os.path.join(self.client, *ASSIST.split('/')) + '.kph', entry[0]))
        self.assertEqual(len(before), len(after))
        changed = [i for i, r in enumerate(before)
                   if len(r) > 6 and r[6] == 'km/h' and 'mph' in r[4].lower()]
        self.assertTrue(changed)
        i = next(i for i in changed if before[i][5] not in ('0', ''))
        self.assertNotIn('mph', after[i][4].lower(), f'row {i}: text still mph')
        self.assertIn(f'{float(before[i][5]):g} km/h', after[i][4])
        self.assertTrue(any(r[6] == 'km/h' and 'mph' in r[4].lower() for r in after))   # value 0 rows stay
        # the HUD: only the ADV speed unit label of the control, bytes unchanged
        path = os.path.join(self.client, *NUI.split('/'))
        with open(path, 'rb') as f, open(path + '.kph', 'rb') as g:
            old, new = f.read(), g.read()
        self.assertEqual(len(old), len(new))
        self.assertEqual(new.count(b'T1="MPH"'), 0)
        self.assertEqual(new.count(b'T1="mph"'), old.count(b'T1="mph"'))    # the other labels are untouched
        self.assertEqual(new.count(b'T1="KPH"'), old.count(b'T1="KPH"') + 1)
        control = new.split(b'<CONTROL B="220057" E="ID_SPEEDMETER_ADV_SPEED">')[1].split(b'</CONTROL>')[0]
        self.assertIn(b'T1="KPH"', control)
        states = eu_rules.status(self.client)
        self.assertEqual([state for _rel, state in states].count('ok'), len(states))

    @unittest.skipUnless(present(UITEX), 'requires the Client US uitex.agt')
    def test_kph_dial(self):
        """Data_US/gameui/uitex.agt: the dial piece (MPH painted in it) replaced, header bytes 20-31 kept."""
        self.real(UITEX)
        src = os.path.join(self.client, *UITEX.split('/'))
        before = sha(src)
        eu_rules.build(self.client, self.ini)
        self.assertEqual(sha(src), before, 'uitex.agt changed')
        self.assertEqual(self.manifest()[UITEX][1], ('kph',))
        header, files = agt.read(src)
        header2, new_files = agt.read(src + '.kph')
        with open(os.path.join(HERE, 'client_backup', 'tw_speedometer_406.dds'), 'rb') as f:
            img = f.read()
        self.assertEqual(header[20:32], header2[20:32])
        self.assertEqual([n for n, _d in files], [n for n, _d in new_files])

        def piece(entries_):
            for n, d in entries_:
                if n.lower().endswith('.ntx'):
                    for e, off, size in entries(d):
                        if e.lower() == SPEEDO_PIECE.lower():
                            return d[off + 72:off + 72 + size]
            return None
        self.assertNotEqual(piece(files), img)
        self.assertEqual(piece(new_files), img)


if __name__ == '__main__':
    unittest.main()
