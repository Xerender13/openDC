"""Web workshop checks: version-aware tables, edits, token and path safety; no real writes.

Every test works on temporary copies of a few tables. The real server_data folders are only
read as the source of those copies; emulator.ini is not copied (it holds credentials), a
small synthetic one is written instead.
"""
import http.client
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from tools.webadmin.api import Admin
from tools.webadmin.server import WebServer

ROOT = Path(__file__).resolve().parents[1]
if Path('/tmp/opencode').is_dir():
    TEMP_ROOT = Path('/tmp/opencode')
else:
    TEMP_ROOT = None

TABLES = [
    'tables/ItemClient.tdf', 'tables/UseItemClient.tdf',
    'tables/ItemDropServer.tdf', 'tables/InstantDrop_Server.tdf',
    'Init/VisualItem.xlt', 'Init/VShopItem.xlt', 'Init/RewardGroup.xlt',
    'Init/VehicleList.xlt', 'Init/VehicleUpgrade.xlt',
    'patrol_rewards.txt', 'delivery_rewards.txt', 'mode_tuning.txt',
]
NEO = ['NeoData/NC_chapter.xlt', 'NeoData/NC_quest.xlt']


class FakeGM:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = dict(replies or {})

    def __call__(self, command):
        self.calls.append(command)
        for prefix, reply in self.replies.items():
            if command.startswith(prefix):
                return reply
        return 'OK done'


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, args, timeout):
        self.calls.append((tuple(args), timeout))
        return 0, 'fake launcher output'


class Fixture:
    """Temporary emulator root with copied tables and a synthetic emulator.ini."""

    def __init__(self, version):
        self.version = version
        self.temp = tempfile.TemporaryDirectory(prefix='webadmin-', dir=TEMP_ROOT)
        self.root = Path(self.temp.name)
        self.data = self.root / ('server_data_2016' if version == '2016' else 'server_data')
        self.config = self.root / 'emulator.ini'
        self.reset()

    def reset(self):
        for relative in TABLES + (NEO if self.version == '2016' else []):
            source = ROOT / self.data.name / relative
            target = self.data / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        self.config.write_text(
            '[emulator]\ncontrol_port = 11099\nlog_dir = logs\n'
            '[client]\nversion = ' + self.version + '\n' +
            ('data_2016 = server_data_2016\n' if self.version == '2016' else
             '[native]\ndata = server_data\nserver_data = server_data/tables\n') +
            '[database]\npassword = do-not-expose\n'
            '[services]\nauth = 11105 0 56\n'
            '[events]\nchristmas = auto\nnewyear = auto\nanniversary = off\n' +
            ('[2016]\nemulator.control_port = 11199\n' if self.version == '2016' else ''),
            encoding='utf-8')

    def table(self, relative):
        return self.data / relative

    def admin(self):
        admin = Admin.from_config(self.config, root=self.root)
        admin.gm = FakeGM()
        admin.runner = FakeRunner()
        admin.backup_root = self.root / 'editor_backups'
        admin.log_file = self.root / 'logs' / 'emulator.out'
        return admin

    def close(self):
        self.temp.cleanup()


class HttpMixin:
    """A live ThreadingHTTPServer on an ephemeral port with the API token."""
    token = 'test-token'

    def start(self, admin):
        self.server = WebServer(('127.0.0.1', 0), admin, self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method='GET', body=None, token='auto'):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        headers = {}
        if token == 'auto':
            headers['X-Token'] = self.token
        elif token is not None:
            headers['X-Token'] = token
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            data = response.read()
            return response.status, data
        finally:
            connection.close()

    def get_json(self, path, token='auto'):
        status, data = self.request(path, token=token)
        return status, json.loads(data)

    def post_json(self, path, body, token='auto'):
        status, data = self.request(path, 'POST', body, token=token)
        return status, json.loads(data)


class TokenTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')
        cls.admin = cls.fixture.admin()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.start(self.admin)

    def test_api_requires_the_token(self):
        self.assertEqual(self.request('/api/tables', token=None)[0], 403)
        self.assertEqual(self.request('/api/tables', token='wrong')[0], 403)
        status, data = self.get_json('/api/tables')
        self.assertEqual(status, 200)
        self.assertEqual(data['version'], '2016')

    def test_post_without_token_does_not_run_gm(self):
        status, _ = self.request('/api/gm', 'POST', {'command': 'who'}, token=None)
        self.assertEqual(status, 403)
        self.assertEqual(self.admin.gm.calls, [])
        status, _ = self.post_json('/api/gm', {'command': 'who'})
        self.assertEqual(status, 200)
        self.assertEqual(self.admin.gm.calls, ['who'])

    def test_static_page_needs_no_token(self):
        status, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'openDC', page)
        for name in ('app.js', 'style.css'):
            status, body = self.request('/static/' + name)
            self.assertEqual(status, 200, name)
            self.assertTrue(body)

    def test_unknown_api_route(self):
        self.assertEqual(self.get_json('/api/missing')[0], 404)

    def test_static_traversal_refused(self):
        self.assertEqual(self.request('/static/../api.py')[0], 404)


class VersionTests(unittest.TestCase):
    def test_2011_and_2016_lists_follow_the_config(self):
        old = Fixture('2011')
        new = Fixture('2016')
        self.addCleanup(old.close)
        self.addCleanup(new.close)
        first = old.admin()
        second = new.admin()
        self.assertEqual(first.version, '2011')
        self.assertEqual(second.version, '2016')
        first_paths = [table['path'] for group in first.tables()['groups']
                       for table in group['tables']]
        second_paths = [table['path'] for group in second.tables()['groups']
                        for table in group['tables']]
        self.assertIn('server_data/tables/ItemClient.tdf', first_paths)
        self.assertIn('server_data/Init/RewardGroup.xlt', first_paths)
        self.assertFalse(any(path.startswith('server_data_2016/') for path in first_paths))
        self.assertIn('server_data_2016/tables/ItemClient.tdf', second_paths)
        self.assertIn('server_data_2016/NeoData/NC_quest.xlt', second_paths)
        self.assertIn('server_data_2016/NeoData/NC_chapter.xlt', second_paths)
        self.assertFalse(any('NeoData' in path for path in first_paths))
        # Deployment files never become editable modes.
        self.assertFalse(any(path.endswith(('adminlist.txt', 'serverlist.txt'))
                             for path in first_paths + second_paths))
        # The settings entry is the configured emulator.ini itself.
        settings = [table['path'] for group in second.tables()['groups']
                    if group['name'] == 'Settings' for table in group['tables']]
        self.assertEqual(settings, ['emulator.ini'])

    def test_loopback_binding_is_required_by_default(self):
        import contextlib
        import io
        from tools.webadmin.__main__ import loopback, main
        self.assertTrue(loopback('127.0.0.1'))
        self.assertTrue(loopback('::1'))
        self.assertTrue(loopback('localhost'))
        self.assertFalse(loopback('0.0.0.0'))
        self.assertFalse(loopback('192.168.1.20'))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(['--host', '0.0.0.0', '--port', '0'])
        self.assertEqual(caught.exception.code, 2)


class ReadTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')
        cls.admin = cls.fixture.admin()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.start(self.admin)

    def test_item_table_page_has_labels_and_identifiers(self):
        status, data = self.get_json(
            '/api/table?path=server_data_2016/tables/ItemClient.tdf&offset=0&limit=5')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['rows']), 5)
        self.assertGreater(data['row_count'], 1000)
        self.assertEqual(data['offset'], 0)
        self.assertEqual(data['labels'][12], 'Buy price (Mito)')
        self.assertEqual(data['identifiers'], [2])
        self.assertEqual(len(data['rows']), 5)
        self.assertEqual(data['rows'][0]['cells'][2], 'i_s_000001')
        self.assertEqual(data['pending'], 0)

    def test_reward_group_probability_column_and_group_filter(self):
        groups = self.admin.reward_groups()
        self.assertGreater(groups['total'], 100)
        self.assertEqual(groups['probability_column'], 11)
        chosen = next(group for group in groups['groups'] if group['rows'] > 2)
        status, data = self.get_json(
            '/api/table?path=server_data_2016/Init/RewardGroup.xlt&group='
            + chosen['group'] + '&limit=50')
        self.assertEqual(status, 200)
        self.assertEqual(data['probability_column'], 11)
        self.assertEqual(data['labels'][11], 'Probability')
        self.assertEqual(data['row_count'], chosen['rows'])
        self.assertLessEqual(len(data['rows']), 50)
        self.assertAlmostEqual(data['probability_sum'], chosen['probability'], places=3)
        for row in data['rows']:
            self.assertEqual(row['cells'][1], chosen['group'])

    def test_row_detail_marks_identifiers_and_english(self):
        status, data = self.get_json(
            '/api/row?path=server_data_2016/tables/ItemClient.tdf&row=0')
        self.assertEqual(status, 200)
        self.assertTrue(data['fields'][2]['locked'])
        self.assertEqual(data['fields'][2]['value'], 'i_s_000001')
        self.assertIn('Car parts', data['description'])
        status, data = self.get_json(
            '/api/table?path=server_data_2016/patrol_rewards.txt&limit=3')
        self.assertEqual(status, 200)
        self.assertEqual(data['labels'][:3], ['Patrol', 'Item', 'Count'])

    def test_row_and_column_ranges_are_checked(self):
        self.assertEqual(self.get_json(
            '/api/row?path=server_data_2016/tables/ItemClient.tdf&row=999999')[0], 400)
        self.assertEqual(self.get_json(
            '/api/row?path=server_data_2016/tables/ItemClient.tdf&row=x')[0], 400)

    def test_cars_and_grades(self):
        status, data = self.get_json('/api/cars')
        self.assertEqual(status, 200)
        self.assertGreater(data['total'], 500)
        model = data['models'][0]
        self.assertEqual(data['table'], 'server_data_2016/Init/VehicleList.xlt')
        self.assertTrue(model['uid'])
        status, grades = self.get_json('/api/car/grades?uid=' + model['uid'])
        self.assertEqual(status, 200)
        self.assertGreater(len(grades['grades']), 0)
        numbers = [row['grade'] for row in grades['grades']]
        self.assertEqual(numbers, sorted(numbers))

    def test_item_index_and_icon_without_client(self):
        status, data = self.get_json('/api/items?limit=5')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['items']), 5)
        self.assertGreater(data['total'], 5000)
        self.assertTrue(data['kinds'])
        self.assertTrue(data['grades'])
        tables = {item['table'] for item in self.admin.item_index()}
        self.assertEqual(tables, {'server_data_2016/tables/ItemClient.tdf',
                                  'server_data_2016/tables/UseItemClient.tdf',
                                  'server_data_2016/Init/VisualItem.xlt'})
        filtered = self.get_json(
            '/api/items?table=server_data_2016/tables/ItemClient.tdf&limit=500')[1]
        self.assertTrue(all(item['table'].endswith('ItemClient.tdf')
                            for item in filtered['items']))
        status, icon = self.request('/api/icon?id=i_s_000001&key=ig_p_1q')
        self.assertEqual(status, 404)       # no client folder in the temporary root
        self.assertIn(b'error', icon)

    def test_drift_shop_row_lookup(self):
        status, data = self.get_json('/api/shop/row?id=i_d_c_00001')
        self.assertEqual(status, 200)
        self.assertEqual(data['path'], 'server_data_2016/Init/VShopItem.xlt')
        self.assertGreaterEqual(data['row'], 3)
        self.assertEqual(self.get_json('/api/shop/row?id=no-such-item')[0], 404)


class EditTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.fixture.reset()
        self.admin = self.fixture.admin()
        self.start(self.admin)
        self.item_table = 'server_data_2016/tables/ItemClient.tdf'
        self.ini = 'emulator.ini'

    def test_save_writes_a_backup_and_reloads(self):
        path = self.fixture.table('tables/ItemClient.tdf')
        original = path.read_bytes()
        status, data = self.post_json('/api/table/apply', {
            'path': self.item_table,
            'changes': [{'row': 0, 'col': 12, 'value': '12345'}],
            'save': True,
        })
        self.assertEqual(status, 200, data)
        self.assertTrue(data['saved'])
        self.assertEqual(data['pending'], 0)
        self.assertTrue(data['backup'])
        backup = self.fixture.root / data['backup']
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_bytes(), original)
        self.assertNotEqual(path.read_bytes(), original)
        status, row = self.get_json(
            '/api/row?path=' + self.item_table + '&row=0')
        self.assertEqual(row['fields'][12]['value'], '12345')

    def test_identifier_columns_are_refused(self):
        path = self.fixture.table('tables/ItemClient.tdf')
        original = path.read_bytes()
        status, data = self.post_json('/api/table/apply', {
            'path': self.item_table,
            'changes': [{'row': 0, 'col': 2, 'value': 'not_really'}],
            'save': True,
        })
        self.assertEqual(status, 400)
        self.assertIn('Item ID', data['error'])
        self.assertEqual(path.read_bytes(), original)
        status, row = self.get_json('/api/row?path=' + self.item_table + '&row=0')
        self.assertEqual(row['pending'], 0)

    def test_ini_names_and_mode_tuning_keys_are_fixed(self):
        status, data = self.post_json('/api/table/apply', {
            'path': self.ini,
            'changes': [{'row': 0, 'col': 1, 'value': 'renamed'}],
            'save': True,
        })
        self.assertEqual(status, 400)
        status, data = self.post_json('/api/table/apply', {
            'path': 'server_data_2016/mode_tuning.txt',
            'changes': [{'row': 0, 'col': 2, 'value': '2'}],
            'save': False,
        })
        self.assertEqual(status, 400)
        self.assertIn('value column', data['error'])

    def test_numeric_cells_reject_text(self):
        status, data = self.post_json('/api/table/apply', {
            'path': self.item_table,
            'changes': [{'row': 0, 'col': 12, 'value': 'a lot'}],
            'save': False,
        })
        self.assertEqual(status, 400)
        self.assertIn('number', data['error'])

    def test_stale_file_is_reported_not_overwritten(self):
        path = self.fixture.table('tables/ItemClient.tdf')
        self.assertEqual(self.get_json('/api/table?path=' + self.item_table)[0], 200)
        status, data = self.post_json('/api/table/apply', {
            'path': self.item_table,
            'changes': [{'row': 0, 'col': 12, 'value': '999'}],
            'save': False,
        })
        self.assertEqual(status, 200)
        self.assertEqual(data['pending'], 1)
        external = path.read_bytes() + b'\r\n'
        path.write_bytes(external)
        status, data = self.post_json('/api/table/apply', {
            'path': self.item_table, 'changes': [], 'save': True,
        })
        self.assertEqual(status, 409)
        self.assertIn('changed since', data['error'])
        self.assertEqual(path.read_bytes(), external)

    def test_bad_change_shapes_are_refused(self):
        for change in ({'row': '0', 'col': 12, 'value': '1'},
                       {'row': 0, 'col': 9999, 'value': '1'},
                       {'row': 0, 'col': 12, 'value': 5}):
            status, _ = self.post_json('/api/table/apply', {
                'path': self.item_table, 'changes': [change], 'save': False})
            self.assertEqual(status, 400, change)

    def test_settings_hide_credentials(self):
        status, data = self.get_json('/api/settings')
        self.assertEqual(status, 200)
        sections = [section['name'] for section in data['sections']]
        self.assertIn('events', sections)
        self.assertIn('client', sections)
        for hidden in ('database', 'services', 'emulator', 'native'):
            self.assertNotIn(hidden, sections)
        self.assertNotIn('do-not-expose', json.dumps(data))
        status, _ = self.post_json('/api/table/apply', {
            'path': 'emulator.ini',
            'changes': [{'row': data['sections'][0]['rows'][0]['row'], 'col': 2, 'value': '1'}],
            'save': True,
        })
        self.assertIn(status, (200, 400))       # a numeric/flag setting is accepted or checked
        backup = self.fixture.root / 'editor_backups'
        if status == 200:
            self.assertTrue(any(backup.rglob('emulator.ini')))


class PathTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')
        cls.admin = cls.fixture.admin()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.start(self.admin)

    def test_paths_outside_the_emulator_and_unknown_files_are_refused(self):
        for path in ('../emulator.ini', '/etc/passwd', 'server_data_2016/../../secret',
                     'server_data_2016/tables/../../emulator.ini',
                     'server_data_2016/tables/NotThere.tdf', 'logs/emulator.out',
                     'emulator.ini/../emulator.ini'):
            status, payload = self.get_json('/api/table?path=' + path)
            self.assertIn(status, (400, 403), path)
        status, payload = self.post_json('/api/table/duplicate',
                                         {'path': '/etc/passwd', 'row': 0})
        self.assertIn(status, (400, 403))


class DuplicateTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.fixture.reset()
        self.admin = self.fixture.admin()
        self.start(self.admin)

    def test_patrol_reward_row_is_appended(self):
        path = self.fixture.table('patrol_rewards.txt')
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        before = [line for line in lines if line.strip() and not line.lstrip().startswith('#')]
        status, data = self.post_json('/api/table/duplicate', {
            'path': 'server_data_2016/patrol_rewards.txt', 'row': 0})
        self.assertEqual(status, 200, data)
        after_lines = path.read_text(encoding='utf-8-sig').splitlines()
        after = [line for line in after_lines if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after[-1].split('\t'), before[0].split('\t'))
        self.assertTrue((self.fixture.root / data['backup']).is_file())

    def test_xlt_row_is_inserted_after_the_original(self):
        path = self.fixture.table('Init/RewardGroup.xlt')
        before = path.read_bytes().decode('utf-16-le').lstrip('\ufeff').split('\r\n')
        status, data = self.post_json('/api/table/duplicate', {
            'path': 'server_data_2016/Init/RewardGroup.xlt', 'row': 10})
        self.assertEqual(status, 200, data)
        after = path.read_bytes().decode('utf-16-le').lstrip('\ufeff').split('\r\n')
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after[11], before[10])
        self.assertEqual(data['row'], 11)

    def test_binary_drop_table_refuses_new_rows(self):
        status, data = self.post_json('/api/table/duplicate', {
            'path': 'server_data_2016/tables/ItemDropServer.tdf', 'row': 0})
        self.assertEqual(status, 400)
        self.assertIn('RewardGroup', data['error'])


class GmTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.fixture.reset()
        self.admin = self.fixture.admin()
        self.start(self.admin)

    def test_gm_passthrough(self):
        status, data = self.post_json('/api/gm', {'command': 'who'})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertEqual(self.admin.gm.calls, ['who'])

    def test_gm_input_is_validated(self):
        for command in ('', 'who\nitem x', '   '):
            status, _ = self.post_json('/api/gm', {'command': command})
            self.assertEqual(status, 400, repr(command))
        self.assertEqual(self.admin.gm.calls, [])

    def test_password_commands_are_blocked_from_the_console(self):
        status, data = self.post_json('/api/gm',
                                      {'command': 'account-password test secretpw'})
        self.assertEqual(status, 400)
        self.assertIn('Accounts', data['error'])
        self.assertEqual(self.admin.gm.calls, [])

    def test_online_players_are_parsed(self):
        self.admin.gm = FakeGM({'who': 'OK 2 online\n  Alpha (account acc1, level 12, 127.0.0.1)\n'
                                       '  Beta (account acc2, level 3, 127.0.0.2)'})
        status, data = self.get_json('/api/server/online')
        self.assertEqual(status, 200)
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['players'][0]['name'], 'Alpha')
        self.assertEqual(data['players'][0]['account'], 'acc1')
        self.assertEqual(data['players'][1]['level'], '3')

    def test_unreachable_emulator_is_reported(self):
        def down(command):
            raise ConnectionError('Emulator GM port is unavailable. Start the emulator first.')
        self.admin.gm = down
        status, data = self.post_json('/api/gm', {'command': 'who'})
        self.assertEqual(status, 502)
        self.assertIn('unavailable', data['error'])


class ServerTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.fixture.reset()
        self.admin = self.fixture.admin()
        self.start(self.admin)

    def test_status_runs_the_launcher_read_only(self):
        status, data = self.get_json('/api/server/status')
        self.assertEqual(status, 200)
        self.assertEqual(data['output'], 'fake launcher output')
        self.assertEqual(self.admin.runner.calls, [(('status',), 25)])

    def test_restart_requires_confirmation(self):
        status, _ = self.post_json('/api/server/restart', {})
        self.assertEqual(status, 400)
        self.assertEqual(self.admin.runner.calls, [])
        status, data = self.post_json('/api/server/restart', {'confirm': True})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertEqual(self.admin.runner.calls[0][0], ('restart-emu',))

    def test_log_tail_keeps_the_last_lines(self):
        log = self.fixture.root / 'logs' / 'emulator.out'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('\n'.join(f'line {number}' for number in range(1, 251)) + '\n',
                       encoding='utf-8')
        status, data = self.get_json('/api/server/log?lines=200')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['lines']), 200)
        self.assertEqual(data['lines'][-1], 'line 250')
        self.assertEqual(data['lines'][0], 'line 51')

    def test_accounts_and_credentials(self):
        self.admin.gm = FakeGM({
            'accounts': 'OK [{"account": "tester", "valid": "y", "joined": "2026-01-02"}]',
            'account ': 'OK {"account": "tester", "valid": "y", "joined": "2026-01-02", '
                        '"coins": 10, "characters": []}',
        })
        status, data = self.get_json('/api/server/accounts?q=test')
        self.assertEqual(status, 200)
        self.assertEqual(data['rows'][0]['account'], 'tester')
        status, data = self.get_json('/api/server/account?id=tester')
        self.assertEqual(data['account']['coins'], 10)

        status, data = self.post_json('/api/server/account/create',
                                      {'id': 'newbie', 'password': 'secretpw'})
        self.assertEqual(status, 200)
        self.assertIn('account-create newbie secretpw', self.admin.gm.calls)
        self.assertNotIn('secretpw', json.dumps(data))

        status, data = self.post_json('/api/server/account/password',
                                      {'id': 'tester', 'password': 'anotherpw'})
        self.assertEqual(status, 200)
        self.assertNotIn('anotherpw', json.dumps(data))

        for body in ({'id': 'bad/id', 'password': 'x'},
                     {'id': 'test', 'password': 'has space'},
                     {'id': 'test', 'password': ''},
                     {'id': 'test', 'password': 'x' * 64}):
            status, _ = self.post_json('/api/server/account/password', body)
            self.assertEqual(status, 400, body)
        status, _ = self.post_json('/api/server/account/role', {'id': 'tester', 'role': 'X'})
        self.assertEqual(status, 400)


class EventTests(HttpMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture('2016')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()

    def setUp(self):
        self.fixture.reset()
        self.admin = self.fixture.admin()
        self.start(self.admin)

    def test_events_list_modes_and_windows(self):
        status, data = self.get_json('/api/events')
        self.assertEqual(status, 200)
        names = [event['name'] for event in data['events']]
        self.assertIn('christmas', names)
        christmas = next(event for event in data['events'] if event['name'] == 'christmas')
        self.assertEqual(christmas['mode'], 'auto')
        self.assertIn('12-01', christmas['window'])

    def test_event_toggle_writes_ini_and_applies_live(self):
        path = self.fixture.config
        status, data = self.post_json('/api/events', {'name': 'christmas', 'mode': 'off'})
        self.assertEqual(status, 200, data)
        self.assertTrue(data['live'])
        self.assertIn('event christmas off', self.admin.gm.calls)
        self.assertIn('christmas = off', path.read_text(encoding='utf-8'))
        self.assertTrue((self.fixture.root / data['backup']).is_file())

    def test_invalid_events_are_refused(self):
        path = self.fixture.config
        before = path.read_bytes()
        self.assertEqual(self.post_json('/api/events',
                                        {'name': 'christmas', 'mode': 'sometimes'})[0], 400)
        self.assertEqual(self.post_json('/api/events',
                                        {'name': 'nope', 'mode': 'on'})[0], 400)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.admin.gm.calls, [])


if __name__ == '__main__':
    unittest.main()
