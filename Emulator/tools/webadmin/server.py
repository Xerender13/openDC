"""HTTP server for the web workshop: token-protected JSON API plus the static page.

The page is served without a token (it is only markup and scripts); every /api request
needs the X-Token header. The GM control port behind this tool has no password, so a
loopback bind and the random token are the access control.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import secrets
import traceback
from urllib.parse import parse_qs, unquote, urlparse

from .api import Admin, ApiError

STATIC = Path(__file__).resolve().parent / 'static'
MAX_BODY = 1 << 20


def _first(params, name, default=''):
    values = params.get(name)
    return values[0] if values else default


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, admin, token):
        super().__init__(address, Handler)
        self.admin = admin
        self.token = token


class Handler(BaseHTTPRequestHandler):
    server_version = 'openDC-webadmin'
    protocol_version = 'HTTP/1.1'

    # ----- plumbing ------------------------------------------------------

    def log_message(self, fmt, *args):
        pass                                    # the tool prints its own start/stop lines

    def _send(self, status, payload, content_type='application/json; charset=utf-8'):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
        elif isinstance(payload, str):
            payload = payload.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if status >= 400:
            # A rejected request may still have an unread body; do not reuse the connection.
            self.send_header('Connection', 'close')
            self.close_connection = True
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json_error(self, status, message):
        self._send(status, {'error': message})

    def _authorised(self):
        supplied = self.headers.get('X-Token', '')
        if not supplied:
            return False
        try:
            return secrets.compare_digest(supplied, self.server.token)
        except TypeError:                       # non-ASCII header values are never the token
            return False

    def _body(self):
        try:
            length = int(self.headers.get('Content-Length', '0') or 0)
        except ValueError:
            raise ApiError('Invalid Content-Length') from None
        if length < 0 or length > MAX_BODY:
            raise ApiError('Request body is too large', 413)
        raw = self.rfile.read(length) if length else b''
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError('The request body must be JSON') from None
        if not isinstance(value, dict):
            raise ApiError('The request body must be a JSON object')
        return value

    # ----- HTTP verbs ----------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            if not self._authorised():
                return self._json_error(403, 'Missing or stale token. Open the URL printed by '
                                             'python -m tools.webadmin.')
            params = parse_qs(parsed.query)
            try:
                status, payload, content_type = self._get(parsed.path, params)
            except ApiError as error:
                return self._json_error(error.status, str(error))
            except Exception as error:
                traceback.print_exc()
                return self._json_error(500, f'{type(error).__name__}: {error}')
            return self._send(status, payload, content_type)
        self._static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._body()
        except ApiError as error:
            return self._json_error(error.status, str(error))
        if not parsed.path.startswith('/api/'):
            return self._json_error(404, 'Not found')
        if not self._authorised():
            return self._json_error(403, 'Missing or stale token. Open the URL printed by '
                                         'python -m tools.webadmin.')
        try:
            status, payload, content_type = self._post(parsed.path, body)
        except ApiError as error:
            return self._json_error(error.status, str(error))
        except Exception as error:
            traceback.print_exc()
            return self._json_error(500, f'{type(error).__name__}: {error}')
        self._send(status, payload, content_type)

    # ----- API routes ----------------------------------------------------

    def _get(self, path, params):
        admin = self.server.admin
        if path == '/api/tables':
            return 200, admin.tables(), 'application/json; charset=utf-8'
        if path == '/api/items':
            return 200, admin.items(query=_first(params, 'q'),
                                    table=_first(params, 'table'),
                                    kind=_first(params, 'kind'),
                                    grade=_first(params, 'grade'),
                                    offset=_first(params, 'offset', '0'),
                                    limit=_first(params, 'limit', '100')), \
                'application/json; charset=utf-8'
        if path == '/api/icon':
            return 200, admin.icon(_first(params, 'id'), _first(params, 'key')), 'image/png'
        if path == '/api/table':
            return 200, admin.table_page(_first(params, 'path'),
                                         offset=_first(params, 'offset', '0'),
                                         limit=_first(params, 'limit', '100'),
                                         query=_first(params, 'q'),
                                         group=_first(params, 'group')), \
                'application/json; charset=utf-8'
        if path == '/api/row':
            return 200, admin.row_detail(_first(params, 'path'),
                                         _first(params, 'row')), \
                'application/json; charset=utf-8'
        if path == '/api/rewards/groups':
            return 200, admin.reward_groups(), 'application/json; charset=utf-8'
        if path == '/api/shop/row':
            return 200, admin.shop_row(_first(params, 'id')), \
                'application/json; charset=utf-8'
        if path == '/api/cars':
            return 200, admin.cars(_first(params, 'q')), 'application/json; charset=utf-8'
        if path == '/api/car/grades':
            return 200, admin.car_grades(_first(params, 'uid')), \
                'application/json; charset=utf-8'
        if path == '/api/settings':
            return 200, admin.settings(), 'application/json; charset=utf-8'
        if path == '/api/events':
            return 200, admin.events(), 'application/json; charset=utf-8'
        if path == '/api/server/status':
            return 200, admin.status(), 'application/json; charset=utf-8'
        if path == '/api/server/online':
            return 200, admin.online(), 'application/json; charset=utf-8'
        if path == '/api/server/accounts':
            return 200, admin.accounts(_first(params, 'q')), \
                'application/json; charset=utf-8'
        if path == '/api/server/account':
            return 200, admin.account(_first(params, 'id')), \
                'application/json; charset=utf-8'
        if path == '/api/server/log':
            return 200, admin.tail(_first(params, 'lines', '200')), \
                'application/json; charset=utf-8'
        raise ApiError('Unknown API route', 404)

    def _post(self, path, body):
        admin = self.server.admin
        if path == '/api/table/apply':
            return 200, admin.apply(body.get('path'), body.get('changes', []),
                                    body.get('save') is True), \
                'application/json; charset=utf-8'
        if path == '/api/table/reload':
            return 200, admin.reload(body.get('path')), \
                'application/json; charset=utf-8'
        if path == '/api/table/duplicate':
            return 200, admin.duplicate(body.get('path'), body.get('row')), \
                'application/json; charset=utf-8'
        if path == '/api/gm':
            return 200, admin.gm_passthrough(body.get('command')), \
                'application/json; charset=utf-8'
        if path == '/api/server/account/create':
            return 200, admin.account_create(body.get('id'), body.get('password')), \
                'application/json; charset=utf-8'
        if path == '/api/server/account/password':
            return 200, admin.account_password(body.get('id'), body.get('password')), \
                'application/json; charset=utf-8'
        if path == '/api/server/account/role':
            return 200, admin.account_role(body.get('id'), body.get('role')), \
                'application/json; charset=utf-8'
        if path == '/api/events':
            return 200, admin.set_event(body.get('name'), body.get('mode')), \
                'application/json; charset=utf-8'
        if path == '/api/server/restart':
            return 200, admin.restart(body.get('confirm')), \
                'application/json; charset=utf-8'
        raise ApiError('Unknown API route', 404)

    # ----- static files --------------------------------------------------

    def _static(self, path):
        if path in ('/', '/index.html'):
            target = STATIC / 'index.html'
        elif path.startswith('/static/'):
            name = unquote(path[len('/static/'):])
            if not name or name.startswith('/') or '..' in Path(name).parts:
                return self._json_error(404, 'Not found')
            target = (STATIC / name).resolve()
            if STATIC.resolve() not in target.parents and target != STATIC.resolve():
                return self._json_error(404, 'Not found')
        else:
            return self._json_error(404, 'Not found')
        if not target.is_file():
            return self._json_error(404, 'Not found')
        content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        if content_type.startswith('text/') or content_type in ('application/javascript',
                                                                'application/json'):
            content_type += '; charset=utf-8'
        self._send(200, target.read_bytes(), content_type)
