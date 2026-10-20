"""2016 driving skills use the client's existing category-58 Visual Item slot (20)."""
import asyncio
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from dcemu.native import context, version
from dcemu.native.data import Tables
from dcemu.native.game import driftuse, vshop
from dcemu.native.game.records import Car, VisualItem
from dcemu.wire import Frame


@unittest.skipUnless(os.path.exists('server_data_2016/tables/ItemClient.tdf'), 'needs 2016 tables')
class DriveSkills2016Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = Tables('server_data_2016', 'server_data_2016/tables', 'server_data_2016/adminlist.txt')

    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.data = self.tables
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock(), row=AsyncMock(return_value=(12345,)))
        self.a, self.b = Car(1, 213, 2, 9, 0, 100, 0, 0), Car(2, 213, 2, 9, 0, 100, 0, 0)
        self.p = SimpleNamespace(char=SimpleNamespace(cid=7, name='T', cur_car=1, cars=[self.a, self.b]),
                                 car=self.a, vsitems=[], items=[], apply_paints=Mock())
        self.s = SimpleNamespace(state={'player': self.p}, log=SimpleNamespace(note=Mock()), to_client=Mock())

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def skill(self, uid=20784, inven=62, car=1, state=1):
        vis = self.tables.visuals[uid]
        return VisualItem(1000+inven, vis.item_id, inven, car, state, '', 90, driftuse.now(), 0, uid)

    def test_purchase_binds_and_equips_on_current_car(self):
        vis = self.tables.visuals[20784]
        v, held, changed, gone = asyncio.run(vshop.grant(self.p, vis, 20784, self.b, '', 90))
        self.assertEqual((v.car_id, v.state, held, gone), (1, 1, None, []))
        self.assertEqual(changed, [v])
        args = next(c.args[1] for c in context.db.execute.await_args_list if c.args[0] == vshop.INSERT_SQL)
        self.assertEqual(args[6:8], (1, 1))
        slots = struct.unpack_from('<10I', v.assist_slots(), 8)
        from dcemu.native.game.convert import assist_index
        self.assertEqual(slots[0], assist_index('a_00002'))
        self.assertTrue(all(x == 0 for x in slots[1:]))

    def test_replacement_deletes_previous_skill_only_on_same_car(self):
        old, other, new = self.skill(), self.skill(20787, 63, 2), self.skill(20785, 64, 0, 0)
        self.p.vsitems = [old, other, new]
        changed, gone = vshop.put_on(self.p, new, 1)
        self.assertEqual((changed, gone), ([new], [old]))
        self.assertEqual((new.car_id, new.state, other.state), (1, 1, 1))

    def test_replacement_also_deletes_unequipped_bound_skill(self):
        old, new = self.skill(state=0), self.skill(20785, 63, 0, 0)
        self.p.vsitems = [old, new]
        changed, gone = vshop.put_on(self.p, new, 1)
        self.assertEqual((changed, gone), ([new], [old]))

    def test_purchase_persists_replacement_deletion(self):
        old = self.skill(state=0)
        self.p.vsitems = [old]
        vis = self.tables.visuals[20785]
        new, held, changed, gone = asyncio.run(vshop.grant(self.p, vis, 20785, self.a, '', 7))
        self.assertEqual((self.p.vsitems, gone, changed), ([new], [old], [new]))
        self.assertEqual((new.car_id, new.state), (1, 1))
        self.assertTrue(any(c.args[0] == vshop.DELETE_SQL and c.args[1][-1] == old.inven_idx
                            for c in context.db.execute.await_args_list))

    def test_skill_can_be_taken_off_and_put_back_on_bound_car(self):
        v = self.skill()
        self.p.vsitems = [v]
        sent = []
        with patch.object(vshop, 'after_change'), patch.object(vshop, 'send', lambda s, *f: sent.extend(f)):
            asyncio.run(vshop.unequip_visual_item(self.s, Frame(0x4b7, struct.pack('<II', 62, 1))))
            self.assertEqual((v.car_id, v.state), (1, 0))
            asyncio.run(vshop.equip_visual_item(self.s, Frame(0x4b5, struct.pack('<IiI', 62, -1, 1))))
            self.assertEqual((v.car_id, v.state), (1, 1))
        self.assertEqual([f.type for f in sent], [0x4b8, 0x4b2, 0x4b6, 0x4b2])

    def test_bound_skill_cannot_move_to_another_car(self):
        v = self.skill(state=0)
        self.p.vsitems = [v]
        with patch.object(vshop, 'error') as err:
            asyncio.run(vshop.equip_visual_item(self.s, Frame(0x4b5, struct.pack('<IiI', 62, -1, 2))))
        err.assert_called_once_with(self.s, '20027')
        self.assertEqual((v.car_id, v.state), (1, 0))
        context.db.execute.assert_not_awaited()

    def test_login_keeps_skill_binding(self):
        v = self.skill()
        self.p.vsitems = [v]
        with patch.object(driftuse, 'one_paint_per_car', AsyncMock()), \
                patch('dcemu.native.game.gifts.return_upgrades', AsyncMock()):
            asyncio.run(driftuse.convert_bundles(self.s, self.p))
        self.assertEqual((v.car_id, v.state), (1, 1))
        context.db.execute.assert_not_awaited()

    def test_buy_without_current_car_cannot_charge(self):
        self.p.car = None
        payload = struct.pack('<II', 20784, 0) + bytes(40) + struct.pack('<IB', 3, 0)
        with patch.object(vshop, 'charge', AsyncMock()) as charge, patch.object(vshop, 'error') as err:
            asyncio.run(vshop.buy_visual_item(self.s, Frame(0x4b3, payload)))
        charge.assert_not_awaited()
        err.assert_called_once_with(self.s, '20050')

    def test_login_repairs_old_unbound_purchase_without_restarting_its_term(self):
        old, latest, other = self.skill(car=0, state=0), self.skill(20785, 63, 0, 0), self.skill(20787, 64, 2)
        latest.ctime += 1
        stamp = latest.ctime
        self.p.vsitems = [old, latest, other]
        asyncio.run(driftuse.restore_drive_skills(self.s, self.p))
        self.assertEqual(self.p.vsitems, [latest, other])
        self.assertEqual((latest.car_id, latest.state, latest.ctime, latest.period), (1, 1, stamp, 90))
        self.assertEqual((other.car_id, other.state), (2, 1))

    def test_2011_cannot_equip_new_category(self):
        v = self.skill()
        version.configure({'version': '2011'})
        self.assertFalse(vshop.fits(v, self.a))
        self.assertFalse(driftuse.drive_skill(self.tables.visuals[20784]))
