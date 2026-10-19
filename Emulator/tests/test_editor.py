"""Data integrity and account administration checks; no live DB/client writes."""
import asyncio
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from tools.editor.data import ROOT, Document, atomic_save, sources
from dcemu.native import mode_tuning


class Documents(unittest.TestCase):
    def test_all_sources_round_trip_without_changes(self):
        for paths in sources().values():
            for path in paths:
                with self.subTest(path=path.name):
                    doc=Document(path)
                    self.assertEqual(doc.encoded(),doc.original)

    def test_tdf_edit_preserves_other_cells_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ItemClient.tdf'
            original=(ROOT/'server_data/tables/ItemClient.tdf').read_bytes()
            path.write_bytes(original)
            doc=Document(path)
            before=doc.rows
            doc.set(0,12,'12345')
            backup=doc.save(Path(tmp)/'backups')
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(doc.rows[0][12],'12345')
            for r,row in enumerate(before):
                for c,v in enumerate(row):
                    if (r,c)!=(0,12): self.assertEqual(doc.rows[r][c],v)

    def test_xlt_unicode_and_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'VehicleUpgrade.xlt'
            path.write_bytes((ROOT/'server_data/Init/VehicleUpgrade.xlt').read_bytes())
            d=Document(path)
            d.set(3,4,'Test Ω V1')
            d.save(Path(tmp)/'backups')
            self.assertEqual(d.rows[3][4],'Test Ω V1')
            self.assertTrue(d.original.startswith(b'\xff\xfe'))

    def test_ids_and_numeric_values_validated(self):
        d=Document(ROOT/'server_data/tables/ItemClient.tdf')
        for col,value in [(2,'other_id'),(12,'invalid'),(12,'nan'),(12,'1.5'),(15,'maybe')]:
            with self.subTest(col=col,value=value), self.assertRaises(ValueError):
                d.set(0,col,value)

    def test_conflicting_write_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test'
            p.write_bytes(b'newer')
            with self.assertRaises(ValueError): atomic_save(p,b'old',b'changed',Path(tmp)/'backups')
            self.assertEqual(p.read_bytes(),b'newer')

    def test_ini_comments_secrets_and_bom_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'emulator.ini'
            original=b'\xef\xbb\xbf[database]\r\npassword = private\r\n[vchase]\r\n; match seconds\r\nseconds_4 = 300 ; note\r\n'
            p.write_bytes(original)
            d=Document(p)
            self.assertEqual(d.rows,[['vchase','seconds_4','300']])
            d.set(0,2,'400')
            encoded=d.encoded()
            self.assertEqual(encoded,original.replace(b'300',b'400'))
            self.assertIn('match seconds',d.hints[0])

    def test_legacy_korean_encoding(self):
        p=ROOT/'server_data/laptimeinfo.txt'
        d=Document(p)
        for i,r in enumerate(d.rows):
            if r[0]=='V1':
                d.set(i,2,'123')
                self.assertIn('123',d.encoded().decode('cp949'))
                return
        self.fail('V1 Lap Time row not found')

    def test_duplicate_reward_adds_prize_without_reordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'patrol_rewards.txt'
            p.write_text('# patrol\titem\tcount\n5\ti_n_00003\t1\n')
            d=Document(p)
            d.duplicate(0)
            d.set(1,1,'i_n_00044')
            d.save(Path(tmp)/'backups')
            self.assertEqual(d.rows,[['5','i_n_00003','1'],['5','i_n_00044','1']])

    def test_tuning_validation_and_shape(self):
        defaults={('undercity','BOSS_SECONDS',()):900,('undercity','BOSS_SHARE',('2',)):0.25}
        for text in ['undercity\tBOSS_SECONDS\t-\t0','undercity\tBOSS_SHARE\t2\t2.5','undercity\tUNIT\t-\t2']:
            with self.assertRaises(ValueError): mode_tuning.parse(text,defaults)
        d={1:(3,4),2:(5,6)}
        updated=mode_tuning.replace(d,('2','1'),99)
        self.assertEqual(updated,{1:(3,4),2:(5,99)})
        self.assertEqual(d,{1:(3,4),2:(5,6)})

    def test_default_tuning_does_not_change_gameplay(self):
        import importlib
        modules={n:importlib.import_module('dcemu.native.game.'+n) for n in mode_tuning.FIELDS}
        before={(n,f):getattr(modules[n],f) for n,fields in mode_tuning.FIELDS.items() for f in fields}
        mode_tuning.apply(ROOT/'server_data')
        after={(n,f):getattr(modules[n],f) for n,f in before}
        self.assertEqual(before,after)


class EnglishDisplay(unittest.TestCase):
    def test_item_translations_never_become_implicit_edits(self):
        from tools.editor.translations import HANGUL
        translated=0
        for paths in sources().values():
            for path in paths:
                if path.name not in ('ItemClient.tdf','UseItemClient.tdf','VisualItem.xlt','VShopItem.xlt'):
                    continue
                d=Document(path)
                for row,cells in enumerate(d.rows[d.start:],d.start):
                    for col,raw in enumerate(cells):
                        if not HANGUL.search(raw): continue
                        display=d.display_value(row,col)
                        self.assertFalse(HANGUL.search(display),(path.name,raw,display))
                        d.set_display(row,col,display)
                        translated+=1
                self.assertEqual(d.changes,{})
                self.assertEqual(d.encoded(),d.original)
        self.assertGreater(translated,300)

    def test_korean_headings_are_english(self):
        from tools.editor.translations import HANGUL
        for paths in sources().values():
            for path in paths:
                d=Document(path)
                for col,header in enumerate(d.headers):
                    if HANGUL.search(header):
                        self.assertFalse(HANGUL.search(d.label(col)),(path.name,header))

    def test_english_search_and_original_view(self):
        d=Document(ROOT/'server_data/tables/UseItemClient.tdf')
        row=next(i for i,r in enumerate(d.rows) if r[2]=='개인 수리 키트 Ⅰ')
        self.assertEqual(d.title(row),'Personal Repair Kit Ⅰ')
        self.assertEqual(d.display_value(row,2,True),'개인 수리 키트 Ⅰ')
        self.assertTrue(d.matches(row,'personal repair kit'))
        self.assertTrue(d.matches(row,'개인 수리'))
        d.set_display(row,2,'My Repair Kit')
        self.assertEqual(d.changes,{(row,2):'My Repair Kit'})

    def test_quantities_placeholders_and_unknown_text(self):
        from tools.editor.translations import english
        self.assertEqual(english('Right-click %d times.'),'Right-click %d times.')
        self.assertEqual(english('unmapped 꿻'),'unmapped 꿻')
        self.assertEqual(english('자신의 레벨을 60으로 다운 시켜준다.'),'Reduces your level to 60.')
        self.assertEqual(english('사용시 부스터 게이지 30 충전 (플라즈마 무기 기준)'),
                         'Restores 30 boost gauge (for plasma weapons).')


class Accounts(unittest.IsolatedAsyncioTestCase):
    async def test_password_reset_uses_md5_and_requires_offline(self):
        from dcemu.native import context,editor_admin,admin
        db=type('DB',(),{'row':AsyncMock(return_value=('test','y',None)),'execute':AsyncMock()})()
        with patch.object(context,'db',db),patch.object(admin,'connections',return_value=[object()]):
            ok,text=await editor_admin.command('account-password',['test','newpass'])
            self.assertFalse(ok)
            db.execute.assert_not_awaited()
        with patch.object(context,'db',db),patch.object(admin,'connections',return_value=[]):
            ok,text=await editor_admin.command('account-password',['test','newpass'])
            self.assertTrue(ok)
            params=db.execute.await_args.args[1]
            import hashlib
            self.assertEqual(params[0],hashlib.md5(b'newpass').hexdigest())
            self.assertNotIn('newpass',text)

    async def test_control_log_redacts_password(self):
        from dcemu.native import admin
        reader=type('R',(),{'readline':AsyncMock(return_value=b'account-password test PRIVATE\n')})()
        class Writer:
            def write(self,data): self.data=data
            async def drain(self): pass
            def close(self): pass
        output=io.StringIO()
        with patch.object(admin,'command',AsyncMock(return_value=(True,'password reset'))),redirect_stdout(output):
            await admin.control(reader,Writer())
        self.assertNotIn('PRIVATE',output.getvalue())
        self.assertIn('<redacted>',output.getvalue())



class GiftBoxes(unittest.TestCase):
    def test_lines_checked_and_chances_become_groups(self):
        from tools import giftbox
        rows=giftbox.check([dict(kind='car',id=249,grade=9),dict(kind='item',id='i_n_00027',count=2,chance=25),
                            dict(kind='mito',count=50000,chance=50)])
        for bad in (dict(kind='car',id=249,grade=0),dict(kind='item',id='nope'),dict(kind='exp',count=5,chance=0)):
            with self.assertRaises(ValueError): giftbox.check([bad])
        lines=giftbox._reward_lines(giftbox._xlt(giftbox.SERVER_REWARD),'rw_t','T',rows)
        new=[l.split('\t') for l in lines[-8:-1]]
        self.assertEqual([r[3] for r in new],['NormalItem','RewardGroup','NormalItem','n/a','RewardGroup','Mito','n/a'])
        self.assertEqual([r[10] for r in new],['100','100','25','75','100','50','50'])
        self.assertEqual(new[0][5],'pc_0249s'); self.assertEqual(new[0][8],'9')


if __name__=='__main__': unittest.main()
