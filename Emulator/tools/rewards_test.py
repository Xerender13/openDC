"""Scripted test (database, test character NewChar; everything made is removed again): a car gift box gives the car,
the Premium Package stays a drift item and acts as the three drinks (once, with a drink held too), a drink won while one is held adds its days."""
import asyncio, configparser, struct, sys
sys.path.insert(0, '.')
from dcemu.native import context
from dcemu.native.db import Database
from dcemu.native.data import Tables
from dcemu.wire import Frame

cp = configparser.ConfigParser(inline_comment_prefixes=(';',)); cp.read('emulator.ini'); d = cp['database']
context.db = Database(d['host'], int(d['port']), d['user'], d['password'], d['name'], int(d['server_id']))
context.data = Tables('server_data', 'server_data/tables', 'server_data/adminlist.txt')
from dcemu.native.game import cars, driftuse, gotcha, items, login, player, vshop  # noqa


class Log:
    def note(self, t): print('    note:', t)


class S:
    def __init__(self, p): self.state = {'player': p, 'serial': 1}; self.log = Log(); self.out = []; self.id = 9

    def to_client(self, f): self.out.append(f)


def fake_send(s, *fs): s.out.extend(fs)


for m in (driftuse, items, login, vshop, cars, gotcha):
    if hasattr(m, 'send'): m.send = fake_send


async def main():
    db = context.db
    cid = 100005
    gold, pinv, ncar = (await db.row("SELECT GOLD, PARTINVENIDX, NEXTCAR FROM SKID_CHARACTER_TB WHERE CID=%s", (cid,)))
    await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD=5000000 WHERE CID=%s", (cid,))
    coin = await db.row("SELECT COIN FROM SKID_UNALISCOIN_TB WHERE MEMBERID=(SELECT MEMBERID FROM SKID_CHARACTER_TB WHERE CID=%s)", (cid,))
    try:
        p = await player.load('NewChar'); s = S(p); t = context.data
        print('1. Serpens gift box V3')
        box = await items.new_item(p, t.item_info(t.item_index['giftbox_Serpens_v3']), 1)
        await items.use_item(s, Frame(0x1a1, struct.pack('<II', box.inven_idx, 1)))
        print('   frames', [hex(f.type) for f in s.out]); s.out.clear()
        print('   cars', [(c.car_id, c.car_type, c.grade) for c in p.char.cars], 'cur', p.char.cur_car)
        assert any(c.car_type == 96 and c.grade == 3 for c in p.char.cars)
        print('2. drink won while held: days added')
        g = driftuse.Gains()
        await driftuse.give_drift_item(p, 'i_d_drk_01', 7, g, s)
        await driftuse.give_drift_item(p, 'i_d_drk_01', 7, g, s)
        drinks = [v for v in p.vsitems if v.item_id == 'i_d_drk_01']
        print('   ', [(v.inven_idx, v.period) for v in drinks]); assert len(drinks) == 1 and drinks[0].period == 14
        print('3. Premium Package bought')
        await db.execute("UPDATE SKID_UNALISCOIN_TB SET COIN=100000 WHERE MEMBERID=%s", (p.char.member,))
        pl = struct.pack('<II', 20315, 0) + bytes(40) + struct.pack('<IB', 2, 0) + bytes(13)
        await vshop.buy_visual_item(s, Frame(0x4b3, pl))
        print('   frames', [hex(f.type) for f in s.out]); s.out.clear()
        print('   ', sorted((v.item_id, v.period, v.state) for v in p.vsitems))
        assert [v.item_id for v in p.vsitems].count('i_package_01') == 1
        assert not any(v.item_id in ('i_d_drk_02', 'i_d_drk_03') for v in p.vsitems)
        assert all(items.holds(p, k) for k in (items.EXP_DRINK, items.MITO_DRINK, items.ITEM_DRINK))
        print('   play bonus 1000 exp / 1000 Mito with package + EXP drink:', items.play_bonus(p, 1000, 1000))
        assert items.play_bonus(p, 1000, 1000) == (1300, 1500)
        f = items.bonus_update(p); print('   0x5dd', struct.unpack('<9I', f.payload))
        await vshop.buy_visual_item(s, Frame(0x4b3, pl)); s.out.clear()
        pk = [v for v in p.vsitems if v.item_id == 'i_package_01']
        print('   bought again:', [(v.inven_idx, v.period) for v in pk]); assert len(pk) == 1 and pk[0].period == 60
        print('4. Gotcha: Mito car capsule season 9, G Coin capsule season 13')
        m0 = p.char.mito
        await gotcha.gotcha(s, Frame(0xdac, struct.pack('<6I', 0, 10000, 0, 0, 0, 9)))
        print('   frames', [hex(f.type) for f in s.out], 'mito', m0, '->', p.char.mito); s.out.clear()
        assert p.char.mito == m0 - 10000
        await gotcha.gotcha(s, Frame(0xdac, struct.pack('<6I', 1, 300, 0, 98510, 0, 13)))
        print('   frames', [hex(f.type) for f in s.out], 'coin', struct.unpack_from('<I', s.out[-1].payload)[0]); s.out.clear()
        print('5. Gotcha key parts + vehicle parts A-D -> car box -> car')
        key = await items.new_item(p, t.item_info(t.item_index['i_n_winner_k_v1_09']), 1)
        for x in 'ABC':
            await items.new_item(p, t.item_info(t.item_index['i_n_gacha_' + x]), 1)
        await items.use_item(s, Frame(0x1a1, struct.pack('<II', key.inven_idx, 1)))
        print('   without D:', [hex(f.type) for f in s.out]); s.out.clear()
        await items.new_item(p, t.item_info(t.item_index['i_n_gacha_D']), 2)
        await items.use_item(s, Frame(0x1a1, struct.pack('<II', key.inven_idx, 1)))
        print('   with A-D:', [hex(f.type) for f in s.out]); s.out.clear()
        left = sorted((i.item_id, i.stack) for i in p.items if i.item_id.startswith(('i_n_gacha', 'i_n_winner')))
        print('   left', left)
        box = next(i for i in p.items if i.item_id == 'i_n_winner_box_v1')
        await items.use_item(s, Frame(0x1a1, struct.pack('<II', box.inven_idx, 1)))
        print('   box:', [hex(f.type) for f in s.out], [(c.car_type, c.grade) for c in p.char.cars]); s.out.clear()
        print('ALL DONE')
    finally:
        await db.execute("DELETE FROM SKID_ITEM_TB WHERE CID=%s AND INVENIDX>%s", (cid, pinv))
        await db.execute("DELETE FROM SKID_CAR_TB WHERE CID=%s AND CARID>%s", (cid, ncar))
        await db.execute("DELETE FROM SKID_VSITEM_TB WHERE CID=%s AND INVENIDX>64", (cid,))
        await db.execute("UPDATE SKID_CHARACTER_TB SET GOLD=%s, PARTINVENIDX=%s, NEXTCAR=%s, NUMCAR=%s, CURCAR=1 WHERE CID=%s",
                         (gold, pinv, ncar, ncar, cid))
        if coin:
            await db.execute("UPDATE SKID_UNALISCOIN_TB SET COIN=%s WHERE MEMBERID=(SELECT MEMBERID FROM SKID_CHARACTER_TB WHERE CID=%s)", (coin[0], cid))

asyncio.run(main())
