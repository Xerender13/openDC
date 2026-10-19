"""Wire checks for both builds; no live database or client writes."""
import hashlib
import asyncio
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from dcemu.__main__ import load_config, native_setup
from dcemu.native import context, version
from dcemu.native.game import cars, items, login
from dcemu.native.game.records import Car, Character, Item, Stats, enchant_bonus, pack_exp
from dcemu.wire import Frame, read_wstr
from tools.client_tables import Client
from tools import agt
from tools.sync_data import sync_traffic


def character():
    return Character(cid=7, name='Driver', member='test', last_date=123, avatar=2, level=55,
                     exp=123456, exp_next=234567, exp_base=100000, mito=9876543210,
                     team_id=12, team_mark=23, team_name='Crew', team_rank=4, ptype='N',
                     pvp=(1, 2, 3), tpvp=(4, 5, 6), quick_cnt=7, km=1.5,
                     pos=(1., 2., 3., 4.), last_area=9, city=2, pos_state=2, cur_car=42,
                     quick_slots=(11, 12, 13, 14), team_dates=(100, 200, 300),
                     hancoin_inven=2, hancoin_garage=3, flags=0x4000000, guild=1, mileage=99)


def car():
    return Car(42, 50, 0x83123456, 9, 2, 30., 123.5, 1, 40., 5.)


def item():
    return Item(1, 123, 'i_test', 42, 3, 7, 1, 0, 1, '', '', 0, 0, table_idx=456)


class VersionTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({})

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def test_default_and_invalid_switch(self):
        self.assertEqual(load_config('/does/not/exist')['client']['version'], '2011')
        self.assertEqual(version.layout().year, 2011)
        for value in ('auto', '2012', '', '2016x'):
            with self.assertRaises(ValueError):
                version.configure({'version': value})
        version.configure({'version': '2016'})
        self.assertTrue(version.is_2016())
        version.configure({})
        self.assertFalse(version.is_2016())

    def test_character_offsets_and_uint64_experience(self):
        c = character()
        old, new = c.encode(2011), c.encode(2016)
        self.assertEqual((len(old), len(new)), (0x11b, 0x141))
        self.assertEqual(read_wstr(new, 8, 64), c.name)
        self.assertEqual(struct.unpack_from('<HH3Qq', new, 0x4c),
                         (2, 55, c.exp, c.exp_next, c.exp_base, c.mito))
        for old_off, new_off in ((0x46, 0x68), (0xc1, 0xe3), (0xed, 0x10f), (0xf1, 0x113)):
            self.assertEqual(old[old_off:old_off+4], new[new_off:new_off+4])
        c.exp, c.exp_next, c.exp_base = 2**40+1, 2**41+2, 2**39+3
        self.assertEqual(struct.unpack_from('<3Q', c.encode(2016), 0x50),
                         (c.exp, c.exp_next, c.exp_base))
        with self.assertRaises(struct.error):
            c.encode(2011)

    def test_load_ack_cars_and_following_command(self):
        c = character()
        c.cars = [car(), car()]
        c.cars[1].car_id = 43
        for year, count_at, cars_at, stride in ((2011, 0x125, 0x129, 0x31),
                                               (2016, 0x14b, 0x14f, 0x32)):
            version.configure({'version': str(year)})
            payload = struct.pack('<II', 100, 1234) + c.encode() + struct.pack('<I', 2)
            payload += b''.join(v.encode() for v in c.cars)
            packet = struct.pack('<H', 0x7c) + payload
            self.assertEqual(struct.unpack_from('<I', packet, count_at)[0], 2)
            self.assertEqual(struct.unpack_from('<I', packet, cars_at+stride)[0], 43)
            self.assertEqual(len(packet), cars_at + 2*stride)
            bundled = login.bundle(Frame(0x7c, payload), Frame(0x1e, bytes(8)))
            self.assertEqual(struct.unpack_from('<H', bundled.payload, len(payload))[0], 0x1e)

    def test_inventory_indices_and_mod_stride(self):
        it = item()
        old, new = it.encode(2011), it.encode(2016)
        self.assertEqual((len(old), len(new)), (0x5c, 0x60))
        self.assertEqual(new[:0x50], old[:0x50])
        self.assertEqual(new[0x50:0x54], bytes(4))
        self.assertEqual(struct.unpack_from('<II', new, 0x54), (456, 123))
        for year, stride in ((2011, 0x60), (2016, 0x64)):
            version.configure({'version': str(year)})
            result = items.mod_list((it, 1), (it, 2))
            self.assertEqual(len(result.payload)+2, 6+2*stride)
            self.assertEqual(struct.unpack_from('<I', result.payload, stride)[0], 1)
            self.assertEqual(struct.unpack_from('<I', result.payload, 2*stride)[0], 2)

    def test_stats_and_bonus_packet_offsets(self):
        stats = Stats((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12))
        for year, stat_size, bonus_size, command_size in ((2011, 104, 40, 0x92),
                                                        (2016, 112, 44, 0x9e)):
            data = stats.encode(year) + enchant_bonus(6., year)
            self.assertEqual(len(data)+2, command_size)
            self.assertEqual(struct.unpack_from('<4i', data, 0x40), stats.total())
            self.assertEqual(struct.unpack_from('<f', data, stat_size+0x10)[0], 6.)
            self.assertEqual(len(enchant_bonus(version=year)), bonus_size)

    def test_2011_record_golden(self):
        # Digest from these fixtures encoded by records.py at HEAD before the port.
        data = character().encode(2011) + car().encode(2011) + item().encode(2011)
        data += Stats((1, 2, 3, 4)).encode(2011) + enchant_bonus(6., 2011)
        self.assertEqual(hashlib.sha256(data).hexdigest(), 'a945e1afb554357c898ef2757661b9309414ba6fb3bb89dbd4c47e0de7dddf07')

    def test_flag_groups_and_no_overlaps(self):
        for year in (2011, 2016):
            version.configure({'version': str(year)})
            used = set()
            for name, (off, shift, width) in version.flag_table().items():
                bits = set(range(off*8+shift, off*8+shift+width))
                self.assertFalse(bits & used, name)
                self.assertLessEqual(off+4, version.layout().flags)
                used |= bits
        self.assertEqual(version.flag_table()['BattleZone.ChannelPro'], (0x38, 31, 1))
        self.assertEqual(version.flag_table()['BattleZone.GhostBattle'], (0x34, 3, 1))
        self.assertEqual(version.flag_table()['BattleZone.PreMatchTime'], (0x34, 11, 7))
        data = version.pack_flags({'BattleZone.ChannelPro': 1, 'BattleZone.FinalMatchTime': 10,
                                   'BattleZone.GhostBattle': 1, 'BattleZone.DCGP': 2})
        self.assertEqual(struct.unpack_from('<I', data, 0x38)[0], 0x8000000a)
        self.assertEqual(struct.unpack_from('<I', data, 0x34)[0], 8)
        self.assertEqual(struct.unpack_from('<I', data, 0x3c)[0], 16)

    def test_default_flag_bytes_equal_2011_encoder(self):
        from dcemu.handlers.game import pack_flags_2011, NEW_FLAGS
        self.assertEqual(version.pack_flags(NEW_FLAGS), pack_flags_2011(NEW_FLAGS))
        version.configure({'version': '2016'})
        self.assertEqual(len(version.pack_flags(NEW_FLAGS)), 96)

    def test_both_clients_show_the_native_hud_selector(self):
        from dcemu.handlers.game import NEW_FLAGS
        for year in (2011, 2016):
            version.configure({'version': str(year)})
            data = version.pack_flags(NEW_FLAGS)
            self.assertEqual((struct.unpack_from('<I', data, 8)[0] >> 19) & 3, 2)

    def test_2016_advertises_level_100_without_changing_2011(self):
        context.data = SimpleNamespace(contents={})
        for year, off, shift, expected in ((2011, 0x4c, 15, 0), (2016, 0x50, 16, 100)):
            version.configure({'version': str(year)})
            flags = login.game_setting().payload[8:]
            self.assertEqual((struct.unpack_from('<I', flags, off)[0] >> shift) & 1023, expected)
        for value in ('0', '-1', '1024', 'wrong'):
            with self.assertRaises(ValueError):
                version.configure({'version': '2016', 'max_level_2016': value})

    def test_reward_exp_counters_widen_and_tail_stays_aligned(self):
        for year, fmt, size in ((2011, '<III3IHH3I', 42), (2016, '<III3QHH3I', 54)):
            version.configure({'version': str(year)})
            counters = (123, 456, 100) if year == 2011 else (2**40+123, 2**41+456, 2**39+100)
            values = (7, 50, 300, *counters, 55, 2, 101, 102, 0)
            payload = pack_exp('<III3IHH3I', *values)
            self.assertEqual(len(payload)+2, size)  # Cmd_QuestRewardAck handler size
            self.assertEqual(struct.unpack(fmt, payload), values)
            exp_update = pack_exp('<3IHi', *counters, 55, 50)
            self.assertEqual(len(exp_update)+2, 20 if year == 2011 else 32)
        with self.assertRaises(ValueError):
            pack_exp('<III', 1, 2, 3)

    def test_2016_progression_stops_at_100_and_2011_keeps_its_cap(self):
        from dcemu.native.game.progress import add_exp
        context.data = SimpleNamespace(exp_bounds=lambda n: ((n-1)*10, n*10))
        context.db = SimpleNamespace(server_id=2016, execute=AsyncMock())
        for year, expected in ((2016, 100), (2011, 102)):
            version.configure({'version': str(year)})
            c = character()
            c.level, c.exp = 99, 980
            asyncio.run(add_exp(c, 30))
            self.assertEqual(c.level, expected)

    def test_visual_update_has_2016_byte_before_car(self):
        for year, size, car_at in ((2011, 59, 8), (2016, 61, 9)):
            version.configure({'version': str(year)})
            session = SimpleNamespace(state={'serial': 12})
            with patch.dict(login.sessions, {}, clear=True):
                frame = cars.visual_update(session, car())
            self.assertEqual(len(frame.payload)+2, size)
            self.assertEqual(struct.unpack_from('<I', frame.payload, car_at)[0], 42)

    def test_native_setup_selects_data_without_database_queries(self):
        cp = load_config('/does/not/exist')
        for year, root in ((2011, 'server_data'), (2016, 'server_data_2016')):
            cp['client']['version'] = str(year)
            with patch('dcemu.native.data.Tables') as tables, patch('dcemu.native.db.Database'), \
                 patch('dcemu.native.auth.load_server_list', return_value=[]), patch('os.path.isfile', return_value=True):
                native_setup(cp)
            args = tables.call_args.args
            self.assertEqual(Path(args[0]).name, root)
            self.assertEqual(Path(args[1]).parent.name, root)
            self.assertEqual(Path(args[2]).parent.name, 'server_data')


class ClientTablesTest(unittest.TestCase):
    def test_loose_tables_and_overlay_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'Data').mkdir()
            agt.write(str(root/'Data/Init.agt'), b'', [('Init\\VehicleList.xlt', b'archive')])
            (root/'Data/Init').mkdir()
            (root/'Data/Init/VehicleList.xlt').write_bytes(b'base loose')
            self.assertEqual(Client(tmp).read('VehicleList.xlt'), b'base loose')
            (root/'Data_US/Init').mkdir(parents=True)
            (root/'Data_US/Init/VehicleList.xlt').write_bytes(b'US loose')
            self.assertEqual(Client(tmp).read('vehiclelist.XLT'), b'US loose')
            (root/'Patch').mkdir()
            agt.write(str(root/'Patch/Patch.000'), b'', [('Data_US\\Init\\VehicleList.xlt', b'patched')])
            self.assertEqual(Client(tmp).read('VehicleList.xlt'), b'patched')

    def test_loose_city_traffic_preserves_client_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'client'
            folder = root/'Data/World/MoonPalace/Path'
            folder.mkdir(parents=True)
            (folder/'moon.chpath').write_bytes(b'path bytes')
            (folder.parent/'moonpalace.tcs').write_bytes(b'lane bytes')
            out = Path(tmp)/'out'
            self.assertEqual(sync_traffic(str(root), Client(str(root)), str(out)), 2)
            self.assertEqual((out/'tables/MoonPalace/moonpalace.tcs').read_bytes(), b'lane bytes')
            self.assertEqual((out/'tables/MoonPalace/Path/moon.chpath').read_bytes(), b'path bytes')

    def test_prepare_refuses_existing_data(self):
        from tools.prepare2016 import prepare
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                prepare(tmp, tmp, tmp)
