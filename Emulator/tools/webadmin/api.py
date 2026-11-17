"""Version-aware tables, items, rewards and server control for the web UI.

Everything here is plain data in and out; server.py adds HTTP and the token.
Only server copies are edited, through tools/editor/data.py Document: backups,
identifier protection and the stale-file check therefore stay in one place.
Client archives are read solely for item pictures.
"""
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading

from dcemu.__main__ import load_config
from dcemu.native import events as season_events
from tools.editor.data import (Artwork, DESCRIPTIONS, Document, IDENTIFIERS, atomic_save,
                               gm as editor_gm)
from tools.editor.translations import english

ROOT = Path(__file__).resolve().parents[2]
GROUPS = ('Items', 'Cars', 'Rewards & drops', 'Settings')
DEFAULT_DESCRIPTION = ('Original game table. Columns marked "raw parameter" have no verified '
                       'description yet.')
ACCOUNT_ID = re.compile(r'[A-Za-z0-9_.-]{1,32}')
# editor_admin.SECRET_COMMANDS: never carried through the generic console.
SECRET_COMMANDS = {'account-create', 'account-password'}
EVENT_MODES = tuple(season_events.MODES)

# Which game mode a reward source belongs to. The descriptions next to them come from
# tools/editor/data.py DESCRIPTIONS; these short labels are for the source picker.
MODE_LABELS = {
    'ItemClient.tdf': 'Car parts, option parts, docking parts',
    'UseItemClient.tdf': 'Consumables, gift boxes, keys',
    'VisualItem.xlt': 'Drift shop items (visual)',
    'VShopItem.xlt': 'Drift shop prices and tooltips',
    'VehicleList.xlt': 'Car models',
    'VehicleUpgrade.xlt': 'Cars by V grade',
    'RewardGroup.xlt': 'Reward pools: patrol, gift boxes, events, shop boxes',
    'ItemDropServer.tdf': 'Traffic items, combos, Rush Time HUV hits',
    'InstantDrop_Server.tdf': 'Patrol drops at 50 / 100 / 150 / 160 places',
    'patrol_rewards.txt': 'Patrol completion prizes',
    'delivery_rewards.txt': 'Delivery job prizes',
    'gate_rewards.txt': 'Solo race gate rewards',
    'team_gate_rewards.txt': 'Team race gate rewards',
    'comboexp.txt': 'Combo driving EXP',
    'pvpexpbase.txt': 'Battle race EXP base',
    'pvpexprate.txt': 'Battle race EXP rate',
    'pvpmoneybase.txt': 'Battle race Mito base',
    'pvpmoneyrate.txt': 'Battle race Mito rate',
    'mode_tuning.txt': 'Undercity, Rush Time, HUV, daily missions, timers',
    'laptimeinfo.txt': 'Lap Time',
    'realmatchtable.txt': 'Real Match schedule',
    'docking_chances.txt': 'Docking part crafting',
    'NC_chapter.xlt': 'Neo City chapter rewards',
    'NC_quest.xlt': 'Neo City quest rewards',
    'emulator.ini': 'Server settings',
}

# Columns of tables without a header row. Sources: dcemu/native/data.py _drops (ItemDropServer:
# level, group, then three play-time blocks of six drop-mode rates) and instant.py DROP_AT
# (InstantDrop_Server: level, then the group at 50 / 100 / 150 / 160 places). The two item
# reward lists document their columns in their own comment lines.
LABEL_OVERRIDES = {
    'ItemDropServer.tdf': {0: 'Level', 1: 'Item group'},
    'InstantDrop_Server.tdf': {0: 'Level', 1: 'Drop group at 50 places',
                               2: 'Drop group at 100 places', 3: 'Drop group at 150 places',
                               4: 'Drop group at 160 places'},
    'delivery_rewards.txt': {0: 'Job', 1: 'Medal', 2: 'Item', 3: 'Count'},
    'patrol_rewards.txt': {0: 'Patrol', 1: 'Item', 2: 'Count'},
}
for _block, _name in enumerate(('0 h block', '4 h block', '12 h block')):
    for _mode in range(6):
        LABEL_OVERRIDES['ItemDropServer.tdf'][2 + _block * 6 + _mode] = \
            f'Drop mode {_mode} rate (%), {_name}'

PROBABILITY_DEFAULT = 11


class ApiError(Exception):
    """A refused request: the message is shown in the browser."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _as_int(value, name, default=None, minimum=0, maximum=None):
    if value is None or value == '':
        if default is None:
            raise ApiError(f'{name} is required')
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ApiError(f'{name} must be a whole number') from None
    if number < minimum or (maximum is not None and number > maximum):
        raise ApiError(f'{name} must be between {minimum} and {maximum}')
    return number


def _text(value, name, maximum=300):
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f'{name} is required')
    if len(value) > maximum or any(c in value for c in '\0\r\n'):
        raise ApiError(f'{name} is not a single line of at most {maximum} characters')
    return value.strip()


def _json_reply(reply):
    """'OK <json>' -> the decoded value, else None."""
    if not reply.startswith('OK '):
        return None
    try:
        return json.loads(reply[3:])
    except json.JSONDecodeError:
        return None


class Admin:
    """Data operations of one emulator copy (one emulator.ini version)."""

    def __init__(self, root, config=None, version='2011', data_root=None, table_root=None,
                 neo_root=None, client=None, catalog=None, gm_command=None, runner=None,
                 log_file=None, backup_root=None):
        self.root = Path(root).resolve()
        self.config = Path(config).resolve() if config else None
        self.version = str(version)
        self.data_root = Path(data_root).resolve() if data_root else self.root / 'server_data'
        self.table_root = (Path(table_root).resolve() if table_root
                           else self.data_root / 'tables')
        self.neo_root = Path(neo_root).resolve() if neo_root else None
        self.client = Path(client) if client else None
        self.catalog = Path(catalog) if catalog else None
        self.log_file = Path(log_file) if log_file else None
        self.backup_root = Path(backup_root) if backup_root else self.root / 'editor_backups'
        self.gm = gm_command or self._default_gm
        self.runner = runner or self._default_runner
        self.lock = threading.RLock()
        self.docs = {}
        self.doc_mtimes = {}
        self._items = None
        self._item_stamp = None
        self._names = None
        self._groups = None
        self._group_stamp = None
        self._cars = None
        self._car_stamp = None
        self._art = None
        self._art_ready = False
        self._art_error = None
        self._icons = {}
        self.warning = None
        self.entries = {group: [] for group in GROUPS}
        self.by_path = {}
        self._build_sources()
        if not self._source_by_file('ItemClient.tdf'):
            self.warning = (f'The client tables are missing in {self.table_root}; '
                            'run python -m tools.client_setup (or tools.prepare2016).')

    # ----- configuration -------------------------------------------------

    @classmethod
    def from_config(cls, config, client=None, catalog=None, root=None):
        root = Path(root or ROOT).resolve()
        config = Path(config)
        if not config.is_absolute():
            config = root / config
        settings = load_config(config)
        version = settings['client'].get('version', '2011').strip()
        if version not in ('2011', '2016'):
            raise ValueError(f'[client] version must be 2011 or 2016, not {version!r}')
        if version == '2016':
            data = Path(settings['client'].get('data_2016', 'server_data_2016'))
            if not data.is_absolute():
                data = root / data
            table = data / 'tables'
            neo = data / 'NeoData'
        else:
            data = Path(settings['native'].get('data', 'server_data'))
            table = Path(settings['native'].get('server_data', 'server_data/tables'))
            if not data.is_absolute():
                data = root / data
            if not table.is_absolute():
                table = root / table
            neo = None
        # the console: launch.sh writes it to logs/emulator.out for both versions (its OUT=); [emulator] log_dir holds
        # only the message logs (a logs/2016/emulator.out there is a stale file from before)
        log_file = root / 'logs' / 'emulator.out'
        return cls(root=root, config=config, version=version, data_root=data, table_root=table,
                   neo_root=neo, client=client or root.parent / 'Client US',
                   catalog=catalog or root.parent / 'Drift City Item Catalog.zip',
                   log_file=log_file)

    def _default_gm(self, command):
        return editor_gm(command, config=self.config or self.root / 'emulator.ini')

    def _default_runner(self, args, timeout):
        """-> (returncode, output) of ./launch.sh plus args."""
        script = self.root / ('launch.ps1' if os.name == 'nt' else 'launch.sh')
        if os.name == 'nt':
            command = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(script)]
        else:
            command = ['bash', str(script)]
        try:
            result = subprocess.run(command + list(args), cwd=str(self.root), timeout=timeout,
                                    capture_output=True, text=True, errors='replace')
        except FileNotFoundError:
            return 127, f'{script.name} not found'
        except subprocess.TimeoutExpired:
            return 124, f'./launch.sh {args[0]} timed out after {timeout} seconds'
        return result.returncode, (result.stdout + result.stderr).strip()

    # ----- sources -------------------------------------------------------

    def _build_sources(self):
        def add(path, group, description=None, mode=None):
            path = Path(path)
            if not path.is_file():
                return
            try:
                relative = path.resolve().relative_to(self.root)
            except ValueError:
                return                          # outside Emulator/: never exposed
            entry = {
                'path': relative.as_posix(),
                'file': path.name,
                'group': group,
                'mode': mode or MODE_LABELS.get(path.name, ''),
                'description': description or DESCRIPTIONS.get(path.name, DEFAULT_DESCRIPTION),
                'abspath': path.resolve(),
            }
            self.entries[group].append(entry)
            self.by_path[entry['abspath']] = entry

        init = self.data_root / 'Init'
        for name in ('ItemClient.tdf', 'UseItemClient.tdf'):
            add(self.table_root / name, 'Items')
        for name in ('VisualItem.xlt', 'VShopItem.xlt'):
            add(init / name, 'Items')
        add(init / 'VehicleList.xlt', 'Cars')
        add(init / 'VehicleUpgrade.xlt', 'Cars')
        add(init / 'RewardGroup.xlt', 'Rewards & drops')
        for name in ('ItemDropServer.tdf', 'InstantDrop_Server.tdf'):
            add(self.table_root / name, 'Rewards & drops')
        for path in sorted(self.data_root.glob('*.txt')):
            if path.name in ('adminlist.txt', 'serverlist.txt'):
                continue                        # deployment settings, not game modes
            add(path, 'Rewards & drops')
        if self.neo_root:
            add(self.neo_root / 'NC_chapter.xlt', 'Rewards & drops')
            add(self.neo_root / 'NC_quest.xlt', 'Rewards & drops')
        if self.config:
            add(self.config, 'Settings')

    def _source_by_file(self, name):
        for entries in self.entries.values():
            for entry in entries:
                if entry['file'] == name:
                    return entry
        return None

    def _config_entry(self):
        if not self.config:
            return None
        return self.by_path.get(self.config.resolve())

    def _resolve(self, path):
        """A request path -> (absolute table path, source entry); refuse anything else."""
        if not isinstance(path, str) or not path.strip():
            raise ApiError('path is required')
        if len(path) > 300 or path.startswith(('/', '\\')) or '..' in Path(path).parts:
            raise ApiError('Invalid table path', 403)
        target = (self.root / path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ApiError('Path outside Emulator/', 403)
        entry = self.by_path.get(target)
        if not entry:
            raise ApiError('Not a table of this emulator version', 403)
        if not target.is_file():
            raise ApiError(f'{entry["path"]} does not exist', 404)
        return target, entry

    def tables(self):
        groups = []
        for name in GROUPS:
            groups.append({
                'name': name,
                'tables': [{key: entry[key] for key in ('path', 'file', 'mode', 'description')}
                           for entry in self.entries[name]],
            })
        return {'version': self.version,
                'data_root': self._relative(self.data_root),
                'table_root': self._relative(self.table_root),
                'groups': groups,
                'warning': self.warning}

    def _relative(self, path):
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    # ----- documents -----------------------------------------------------

    def document(self, path):
        """The cached Document of a table, reloaded when the file changed on disk."""
        path = Path(path)
        with self.lock:
            doc = self.docs.get(path)
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                mtime = None
            if doc is not None and mtime is not None and self.doc_mtimes.get(path) != mtime:
                if doc.changes:
                    # Pending browser edits win until they are saved or reloaded; Document.save
                    # then reports the stale file instead of overwriting it.
                    return doc
                doc = None
            if doc is None:
                doc = Document(path)
                self.docs[path] = doc
                self.doc_mtimes[path] = mtime
            return doc

    def reload(self, path):
        target, entry = self._resolve(path)
        with self.lock:
            self.docs.pop(target, None)
            try:
                mtime = target.stat().st_mtime_ns
            except OSError:
                mtime = None
            doc = Document(target)
            self.docs[target] = doc
            self.doc_mtimes[target] = mtime
        self._invalidate()
        return {'ok': True, 'path': entry['path'], 'pending': 0}

    def _ncols(self, doc):
        ncols = getattr(doc, '_web_ncols', None)
        if ncols is None:
            ncols = max((len(row) for row in doc.rows), default=1) or 1
            doc._web_ncols = ncols
        return ncols

    def _labels(self, doc):
        overrides = LABEL_OVERRIDES.get(doc.path.name, {})
        ncols = self._ncols(doc)
        labels = []
        for col in range(ncols):
            label = overrides.get(col)
            labels.append(english(label) if label else doc.label(col))
        return labels

    def _locked(self, doc):
        locked = set(IDENTIFIERS.get(doc.path.name, set()))
        if doc.is_text and doc.path.suffix.lower() == '.ini':
            locked.update((0, 1))
        if doc.path.name == 'mode_tuning.txt':
            for col in range(self._ncols(doc)):
                if col != 3:
                    locked.add(col)
        return locked

    def _probability_columns(self, doc):
        """(group, type, item, count, probability) columns from the header names."""
        header = list(getattr(doc, 'headers', []) or [])

        def find(name, default):
            for index, cell in enumerate(header):
                if cell.strip().lower() == name.lower():
                    return index
            return default

        return (find('GroupId', 1), find('Reward_Type', 3), find('ItemId', 5),
                find('Reward_Count', 7), find('Probability', PROBABILITY_DEFAULT))

    def _row_title(self, doc, row):
        cells = doc.rows[row]
        if doc.path.name == 'RewardGroup.xlt':
            group, _, item, count, probability = self._probability_columns(doc)

            def cell(col):
                return cells[col].strip() if col < len(cells) else ''

            name = self.item_names().get(cell(item), '')
            text = f'{cell(group)} · {english(cell(2))} · {cell(item)}'
            if name:
                text += f' ({name})'
            text += f' ×{cell(count)} · {cell(probability)} %'
            return text[:220]
        if doc.path.name in ('ItemDropServer.tdf', 'InstantDrop_Server.tdf'):
            return ' · '.join(cell.strip() for cell in cells[:2] if cell.strip())
        return doc.title(row)

    def _row_note(self, doc, row):
        if doc.path.name != 'RewardGroup.xlt':
            return ''
        cells = doc.rows[row]
        _, kind, item, count, _ = self._probability_columns(doc)
        parts = []
        if kind < len(cells) and cells[kind].strip():
            parts.append(cells[kind].strip())
        if count < len(cells) and cells[count].strip():
            parts.append(f'count {cells[count].strip()}')
        return ' · '.join(parts)

    # ----- generic table API ---------------------------------------------

    def table_page(self, path, offset=0, limit=100, query='', group=''):
        offset = _as_int(offset, 'offset', 0)
        limit = _as_int(limit, 'limit', 100, 1, 500)
        query = (query or '').strip().lower()
        group = (group or '').strip()
        target, entry = self._resolve(path)
        with self.lock:
            doc = self.document(target)
            start = doc.start
            selected = []
            group_col = self._probability_columns(doc)[0]
            for index in range(start, len(doc.rows)):
                cells = doc.rows[index]
                if not any(cell.strip() for cell in cells):
                    continue
                if group and doc.path.name == 'RewardGroup.xlt':
                    if group_col >= len(cells) or cells[group_col].strip() != group:
                        continue
                if query and not doc.matches(index, query):
                    continue
                selected.append(index)
            total = len(selected)
            if offset > total:
                offset = max(0, (total - 1) // limit * limit)
            page = selected[offset:offset + limit]
            rows = [{'row': index,
                     'title': self._row_title(doc, index),
                     'note': self._row_note(doc, index),
                     'cells': list(doc.rows[index])} for index in page]
            probability_sum = None
            probability_col = None
            if doc.path.name == 'RewardGroup.xlt':
                probability_col = self._probability_columns(doc)[4]
                probability_sum = 0.0
                for index in selected:
                    cells = doc.rows[index]
                    if probability_col < len(cells):
                        try:
                            probability_sum += float(cells[probability_col].strip() or 0)
                        except ValueError:
                            pass
                probability_sum = round(probability_sum, 4)
            result = {
                'path': entry['path'],
                'file': entry['file'],
                'mode': entry['mode'],
                'description': entry['description'],
                'start': start,
                'row_count': total,
                'all_rows': len(doc.rows) - start,
                'offset': offset,
                'limit': limit,
                'labels': self._labels(doc),
                'headers': list(getattr(doc, 'headers', []) or []),
                'identifiers': sorted(self._locked(doc)),
                'pending': len(doc.changes),
                'rows': rows,
                'group': group,
                'probability_column': probability_col,
                'probability_sum': probability_sum,
            }
            return result

    def row_detail(self, path, row):
        row = _as_int(row, 'row', minimum=0)
        target, entry = self._resolve(path)
        with self.lock:
            doc = self.document(target)
            if row < doc.start or row >= len(doc.rows):
                raise ApiError(f'row {row} is outside this table '
                               f'({doc.start}..{len(doc.rows) - 1})')
            cells = list(doc.rows[row])
            labels = self._labels(doc)
            locked = self._locked(doc)
            fields = []
            for col, value in enumerate(cells):
                label = labels[col] if col < len(labels) else f'Column {col} (raw parameter)'
                display = english(value)
                shown = display if display != value else ''
                fields.append({'col': col, 'label': label, 'value': value,
                               'display': shown if len(shown) <= 300 else '',
                               'locked': col in locked,
                               'note': 'Fixed: the client and server reference this value.'
                                       if col in locked else ''})
            description = DESCRIPTIONS.get(doc.path.name, DEFAULT_DESCRIPTION)
            description += '\n\n' + self._row_title(doc, row)
            for col, value in enumerate(cells):
                label = labels[col].lower() if col < len(labels) else ''
                if label in ('description', 'desc (tooltip)', 'objective') and value not in ('n/a', ''):
                    text = english(value)
                    if text not in description:
                        description += '\n' + text
            hint = doc.hints.get(row, '') if doc.is_text else ''
            if hint:
                description += '\n' + english(hint)
            return {'path': entry['path'],
                    'file': entry['file'],
                    'mode': entry['mode'],
                    'description': description,
                    'hint': english(hint),
                    'title': self._row_title(doc, row),
                    'row': row,
                    'start': doc.start,
                    'row_count': len(doc.rows) - doc.start,
                    'labels': labels,
                    'identifiers': sorted(locked),
                    'fields': fields,
                    'note': self._row_note(doc, row),
                    'pending': len(doc.changes)}

    def apply(self, path, changes, save=False):
        if not isinstance(changes, list) or len(changes) > 1000:
            raise ApiError('changes must be a list of at most 1000 cells')
        target, entry = self._resolve(path)
        with self.lock:
            doc = self.document(target)
            ncols = self._ncols(doc)
            before = dict(doc.changes)
            applied = 0
            for change in changes:
                if not isinstance(change, dict):
                    doc.changes = before
                    raise ApiError('each change must be {row, col, value}')
                row = change.get('row')
                col = change.get('col')
                value = change.get('value')
                if isinstance(row, bool) or not isinstance(row, int):
                    doc.changes = before
                    raise ApiError('row must be a whole number')
                if isinstance(col, bool) or not isinstance(col, int):
                    doc.changes = before
                    raise ApiError('col must be a whole number')
                if row < doc.start or row >= len(doc.rows):
                    doc.changes = before
                    raise ApiError(f'row {row} is outside this table '
                                   f'({doc.start}..{len(doc.rows) - 1})')
                if col < 0 or col >= ncols:
                    doc.changes = before
                    raise ApiError(f'column {col} is outside this table (0..{ncols - 1})')
                if not isinstance(value, str):
                    doc.changes = before
                    raise ApiError('value must be text')
                try:
                    doc.set(row, col, value)
                except ValueError as error:
                    doc.changes = before
                    raise ApiError(f'{doc.label(col)} (row {row}): {error}') from None
                except IndexError:
                    doc.changes = before
                    raise ApiError(f'row {row} has no column {col}') from None
                applied += 1
            if not save:
                return {'saved': False, 'applied': applied, 'pending': len(doc.changes),
                        'path': entry['path']}
            try:
                backup = doc.save(self.backup_root)
            except ValueError as error:
                status = 409 if 'changed since' in str(error) else 400
                raise ApiError(str(error), status) from None
            self.doc_mtimes[target] = target.stat().st_mtime_ns
            self._invalidate()
            return {'saved': True, 'applied': applied, 'pending': 0, 'path': entry['path'],
                    'backup': self._relative(backup) if backup else None,
                    'message': 'Saved. Restart the emulator to load table changes.'}

    def duplicate(self, path, row):
        row = _as_int(row, 'row', minimum=0)
        target, entry = self._resolve(path)
        with self.lock:
            doc = self.document(target)
            if doc.changes:
                raise ApiError('Save or reload the pending changes before adding a row.')
            if row < doc.start or row >= len(doc.rows):
                raise ApiError(f'row {row} is outside this table '
                               f'({doc.start}..{len(doc.rows) - 1})')
            name = doc.path.name
            if name in ('delivery_rewards.txt', 'patrol_rewards.txt'):
                # The row keeps its job / patrol id and medal, so it lands in the same group.
                doc.duplicate(row)
                new_row = len(doc.rows) - 1
                try:
                    backup = doc.save(self.backup_root)
                except ValueError as error:
                    raise ApiError(str(error), 409) from None
            elif doc.path.name == 'RewardGroup.xlt':
                # Document.duplicate only supports the two text lists. An XLT row is one CRLF
                # line, so insert a copy of it after the original and save the same way.
                try:
                    backup = self._xlt_duplicate(doc, row)
                except ValueError as error:
                    raise ApiError(str(error), 409) from None
                new_row = row + 1
                self.docs.pop(target, None)
                doc = Document(target)
                self.docs[target] = doc
            else:
                raise ApiError('Adding rows is supported in delivery_rewards.txt, '
                               'patrol_rewards.txt and RewardGroup.xlt, not in this table.')
            self.doc_mtimes[target] = target.stat().st_mtime_ns
            self._invalidate()
            return {'ok': True, 'path': entry['path'], 'row': new_row,
                    'backup': self._relative(backup) if backup else None,
                    'message': 'Row added. Edit it, then save.'}

    def _xlt_duplicate(self, doc, row):
        text = doc.path.read_bytes().decode('utf-16-le')
        bom = '\ufeff' if text.startswith('\ufeff') else ''
        lines = text[len(bom):].split('\r\n')
        if row >= len(lines):
            raise ApiError('This row is not a line of the file')
        # copy the raw line: cells may be quoted and hold bare \n (14 rows of the 2016 table); rebuilding the line from
        # the parsed cells would drop the quotes. Lines split on \r\n match the parsed rows one to one.
        if len(lines) != len(doc.rows) or lines[row].split('\t', 1)[0] != doc.rows[row][0]:
            raise ApiError('The file\'s lines do not match its rows: add the row by hand')
        lines.insert(row + 1, lines[row])
        data = (bom + '\r\n'.join(lines)).encode('utf-16-le')
        return atomic_save(doc.path, doc.original, data, self.backup_root)

    # ----- item index ----------------------------------------------------

    def item_index(self):
        paths = []
        for name in ('ItemClient.tdf', 'UseItemClient.tdf', 'VisualItem.xlt', 'VShopItem.xlt'):
            entry = self._source_by_file(name)
            if entry:
                paths.append(entry['abspath'])
        stamp = self._stamp(paths)
        with self.lock:
            if self._items is None or self._item_stamp != stamp:
                self._items = self._build_items()
                self._item_stamp = stamp
                self._names = None
            return self._items

    def _build_items(self):
        items = []

        def add(table, row, ident, name, kind, grade, level, price, icon_key):
            ident = ident.strip()
            if not ident:
                return
            name = name.strip()
            items.append({'id': ident, 'name': english(name) or ident, 'raw_name': name,
                          'kind': english(kind.replace('"', ' ').replace('\n', ' ').strip()),
                          'grade': grade.strip(), 'level': level.strip(),
                          'price': price.strip(), 'table': table, 'row': row,
                          'icon_key': icon_key.strip()})

        entry = self._source_by_file('ItemClient.tdf')
        if entry:
            doc = self.document(entry['abspath'])
            for index in range(doc.start, len(doc.rows)):
                cells = doc.rows[index]
                if len(cells) < 13:
                    continue
                add(entry['path'], index, cells[2], cells[4], cells[0], cells[6], cells[7],
                    cells[12], cells[3])
        entry = self._source_by_file('UseItemClient.tdf')
        if entry:
            doc = self.document(entry['abspath'])
            for index in range(doc.start, len(doc.rows)):
                cells = doc.rows[index]
                if len(cells) < 8:
                    continue
                add(entry['path'], index, cells[0], cells[2], cells[1], '', '', cells[7],
                    cells[3] if len(cells) > 3 else '')
        entry = self._source_by_file('VisualItem.xlt')
        if entry:
            prices = self._vshop_prices()
            doc = self.document(entry['abspath'])
            category = ''
            for index in range(doc.start, len(doc.rows)):
                cells = doc.rows[index]
                if len(cells) < 6:
                    continue
                if cells[0].strip():
                    category = cells[0]
                if not cells[3].strip():
                    continue
                price = prices.get(cells[3].strip(), '')
                add(entry['path'], index, cells[3], cells[5], category, '', '', price,
                    cells[3] if cells[3].startswith('ig_') else '')
        return items

    def _vshop_prices(self):
        entry = self._source_by_file('VShopItem.xlt')
        if not entry:
            return {}
        doc = self.document(entry['abspath'])
        header = [cell.strip().lower() for cell in (doc.headers or [])]
        column = header.index('mito price') if 'mito price' in header else 27
        result = {}
        for index in range(doc.start, len(doc.rows)):
            cells = doc.rows[index]
            if len(cells) > column and cells[3].strip():
                result.setdefault(cells[3].strip(), cells[column].strip())
        return result

    def item_names(self):
        self.item_index()
        with self.lock:
            if self._names is None:
                self._names = {}
                for item in self._items:
                    self._names.setdefault(item['id'], item['name'])
            return self._names

    def items(self, query='', table='', kind='', grade='', offset=0, limit=100):
        offset = _as_int(offset, 'offset', 0)
        limit = _as_int(limit, 'limit', 100, 1, 500)
        query = (query or '').strip().lower()
        table = (table or '').strip()
        kind = (kind or '').strip()
        grade = (grade or '').strip()
        with self.lock:
            entries = self.item_index()
        filtered = []
        for item in entries:
            if table and item['table'] != table:
                continue
            if kind and item['kind'] != kind:
                continue
            if grade and item['grade'] != grade:
                continue
            if query:
                haystack = ' '.join((item['id'], item['name'], item['raw_name'],
                                     item['kind'], item['grade'])).lower()
                if query not in haystack:
                    continue
            filtered.append(item)
        tables = []
        for entry in self.entries['Items']:
            tables.append({'path': entry['path'], 'file': entry['file']})
        kinds = sorted({item['kind'] for item in entries if item['kind']}, key=str.lower)
        grades = sorted({item['grade'] for item in entries if item['grade']})
        return {'total': len(filtered), 'offset': offset, 'limit': limit,
                'items': filtered[offset:offset + limit],
                'tables': tables, 'kinds': kinds, 'grades': grades}

    def icon(self, item_id, key=''):
        item_id = (item_id or '').strip()
        key = (key or '').strip()
        for value in (item_id, key):
            if len(value) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ApiError('Invalid picture key')
        with self.lock:
            if (item_id, key) in self._icons:
                return self._icons[(item_id, key)]
        art = self._artwork()
        if art is None:
            raise ApiError(self._art_error or 'Game artwork is not available', 404)
        try:
            image = art.get(key, item_id)
        except Exception as error:               # a broken picture must not stop the page
            raise ApiError(f'Game picture could not be read: {error}', 404) from None
        if image is None:
            raise ApiError('No game picture for this entry', 404)
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        data = buffer.getvalue()
        with self.lock:
            self._icons[(item_id, key)] = data
        return data

    def _artwork(self):
        with self.lock:
            if self._art_ready:
                return self._art
            self._art_ready = True
            if not self.client or not self.client.is_dir():
                self._art_error = 'No client folder: pass --client with the game client directory'
                return None
            try:
                self._art = Artwork(self.client, self.catalog)
            except Exception as error:              # artwork must never stop the editor
                self._art_error = f'Game pictures could not be loaded: {type(error).__name__}: {error}'
                self._art = None
            return self._art

    def warm_artwork(self):
        threading.Thread(target=self._artwork, name='webadmin-art', daemon=True).start()

    # ----- cars ----------------------------------------------------------

    def cars(self, query=''):
        query = (query or '').strip().lower()
        model_entry = self._source_by_file('VehicleList.xlt')
        upgrade_entry = self._source_by_file('VehicleUpgrade.xlt')
        if not model_entry:
            raise ApiError('VehicleList.xlt is not in this version\'s data', 404)
        with self.lock:
            stamp = self._stamp([model_entry['abspath']] +
                                ([upgrade_entry['abspath']] if upgrade_entry else []))
            if self._cars is None or self._car_stamp != stamp:
                self._cars = self._build_cars(model_entry, upgrade_entry)
                self._car_stamp = stamp
            models = self._cars['models']
        if query:
            models = [model for model in models
                      if query in ' '.join((model['name'], model['car_name'], model['uid'],
                                            model['file'])).lower()]
        return {'models': models, 'total': len(models), 'query': query,
                'table': model_entry['path'],
                'upgrade_table': upgrade_entry['path'] if upgrade_entry else None}

    def _build_cars(self, model_entry, upgrade_entry):
        upgrade = self.document(upgrade_entry['abspath']) if upgrade_entry else None
        grades = {}
        if upgrade is not None:
            for index in range(upgrade.start, len(upgrade.rows)):
                cells = upgrade.rows[index]
                if len(cells) > 19 and cells[1].strip():
                    grades.setdefault(cells[1].strip(), []).append(index)
        doc = self.document(model_entry['abspath'])
        models = []
        for index in range(doc.start, len(doc.rows)):
            cells = doc.rows[index]
            if len(cells) < 10 or not cells[9].strip():
                continue
            uid = cells[9].strip()
            models.append({'row': index, 'uid': uid,
                           'name': english(cells[6].strip()) or english(cells[5].strip()),
                           'car_name': english(cells[5].strip()),
                           'maker': english(cells[4].strip()),
                           'file': cells[7].strip(),
                           'vehicle': cells[2].strip(),
                           'grades': len(grades.get(uid, []))})
        return {'models': models, 'grades': grades}

    def car_grades(self, uid):
        uid = _text(uid, 'car id', 32)
        upgrade_entry = self._source_by_file('VehicleUpgrade.xlt')
        if not upgrade_entry:
            raise ApiError('VehicleUpgrade.xlt is not in this version\'s data', 404)
        self.cars()
        with self.lock:
            doc = self.document(upgrade_entry['abspath'])
            rows = []
            for index in range(doc.start, len(doc.rows)):
                cells = doc.rows[index]
                if len(cells) < 20 or cells[1].strip() != uid:
                    continue

                def cell(col):
                    return cells[col].strip() if col < len(cells) else ''

                try:
                    grade = int(float(cells[19].strip() or 0))
                except ValueError:
                    grade = 0
                rows.append({'row': index, 'grade': grade,
                             'name': english(cell(4)),
                             'price': cell(10), 'sell': cell(11), 'req_level': cell(16)})
            rows.sort(key=lambda item: (item['grade'], item['row']))
            return {'uid': uid, 'table': upgrade_entry['path'], 'grades': rows}

    # ----- rewards -------------------------------------------------------

    def shop_row(self, item_id):
        """The VShopItem.xlt row of a drift item (its price, duration and bonuses)."""
        item_id = _text(item_id, 'item id', 128)
        entry = self._source_by_file('VShopItem.xlt')
        if not entry:
            raise ApiError('VShopItem.xlt is not in this version\'s data', 404)
        with self.lock:
            doc = self.document(entry['abspath'])
            for index in range(doc.start, len(doc.rows)):
                cells = doc.rows[index]
                if len(cells) > 3 and cells[3].strip() == item_id:
                    return {'path': entry['path'], 'row': index}
        raise ApiError('No drift shop entry for this item', 404)

    def reward_groups(self):
        entry = self._source_by_file('RewardGroup.xlt')
        if not entry:
            raise ApiError('RewardGroup.xlt is not in this version\'s data', 404)
        stamp = self._stamp([entry['abspath']])
        with self.lock:
            if self._groups is None or self._group_stamp != stamp:
                self._groups = self._build_groups(entry)
                self._group_stamp = stamp
            return self._groups

    def _build_groups(self, entry):
        doc = self.document(entry['abspath'])
        group_col, _, _, _, probability_col = self._probability_columns(doc)
        groups = {}
        for index in range(doc.start, len(doc.rows)):
            cells = doc.rows[index]
            if group_col >= len(cells):
                continue
            group = cells[group_col].strip()
            if not group:
                continue
            item = groups.get(group)
            if item is None:
                description = cells[2].strip() if len(cells) > 2 else ''
                item = groups[group] = {'group': group,
                                        'description': english(description),
                                        'rows': 0, 'probability': 0.0}
            item['rows'] += 1
            if probability_col < len(cells):
                try:
                    item['probability'] += float(cells[probability_col].strip() or 0)
                except ValueError:
                    pass
        result = sorted(groups.values(), key=lambda item: item['group'].lower())
        for item in result:
            item['probability'] = round(item['probability'], 4)
        return {'path': entry['path'], 'groups': result, 'total': len(result),
                'probability_column': probability_col}

    # ----- settings and season events ------------------------------------

    def settings(self):
        entry = self._config_entry()
        if not entry:
            raise ApiError('emulator.ini is outside Emulator/: settings are not editable here',
                           403)
        target = Path(entry['abspath'])
        with self.lock:
            doc = self.document(target)
            sections = []
            index = {}
            for row, cells in enumerate(doc.rows):
                if len(cells) < 3:
                    continue
                section, key, value = cells[0], cells[1], cells[2]
                item = index.get(section)
                if item is None:
                    item = index[section] = {'name': section, 'rows': []}
                    sections.append(item)
                item['rows'].append({'row': row, 'key': key, 'value': value,
                                     'hint': english(doc.hints.get(row, ''))})
            return {'path': entry['path'], 'file': entry['file'], 'sections': sections,
                    'note': 'Database, services, emulator and native sections stay out of the '
                            'browser: they hold credentials and deployment ports.'}

    def events(self):
        settings = load_config(self.config) if self.config else None
        section = settings['events'] if settings and settings.has_section('events') else {}
        entry = self._config_entry()
        events = []
        for name, (shown, window, _flags) in season_events.EVENTS.items():
            mode = str(section.get(name, 'auto')).strip().lower()
            if mode not in EVENT_MODES:
                mode = 'auto'
            custom = section.get(name + '.dates')
            if custom:
                window_text = str(custom).strip().replace('..', ' … ')
            elif window == 'easter':
                window_text = 'Easter Sunday −21 … +7 days'
            elif window:
                window_text = f'{window[0]} … {window[1]}'
            else:
                window_text = 'no auto window (on / off only)'
            events.append({'name': name, 'shown': shown, 'mode': mode,
                           'window': window_text})
        return {'events': events, 'modes': list(EVENT_MODES),
                'path': entry['path'] if entry else None}

    def set_event(self, name, mode):
        name = _text(name, 'event name', 40).lower()
        mode = _text(mode, 'event mode', 10).lower()
        if name not in season_events.EVENTS:
            raise ApiError(f'Unknown season event {name!r}')
        if mode not in EVENT_MODES:
            raise ApiError(f'Event mode must be one of {", ".join(EVENT_MODES)}')
        entry = self._config_entry()
        if not entry:
            raise ApiError('emulator.ini is outside Emulator/: the ini cannot be written', 403)
        target = Path(entry['abspath'])
        with self.lock:
            doc = self.document(target)
            row = None
            for index, cells in enumerate(doc.rows):
                if len(cells) >= 3 and cells[0] == 'events' and cells[1] == name:
                    row = index
                    break
            if row is None:
                raise ApiError(f'emulator.ini has no [events] {name} row; add it by hand first.')
            doc.set(row, 2, mode)
            try:
                backup = doc.save(self.backup_root)
            except ValueError as error:
                raise ApiError(str(error), 409) from None
            self.doc_mtimes[target] = target.stat().st_mtime_ns
        reply = ''
        try:
            reply = self._gm(f'event {name} {mode}')
        except ApiError as error:
            reply = f'ini saved, but the live change failed: {error}'
        return {'ok': True, 'event': name, 'mode': mode,
                'backup': self._relative(backup) if backup else None,
                'reply': reply, 'live': reply.startswith('OK')}

    # ----- server control ------------------------------------------------

    def _gm(self, command):
        try:
            return self.gm(command)
        except (ConnectionError, OSError) as error:
            raise ApiError(str(error) or 'The emulator GM port is not reachable', 502) from None
        except ValueError as error:
            raise ApiError(str(error)) from None

    def gm_passthrough(self, command):
        command = _text(command, 'command', 1000)
        words = command.split()
        if words and words[0].lower() in SECRET_COMMANDS:
            raise ApiError('Use the Accounts panel for passwords: they must not pass through '
                           'the command line or its history.')
        reply = self._gm(command)
        return {'ok': reply.startswith('OK'), 'command': command, 'reply': reply}

    def online(self):
        reply = self._gm('who')
        ok = reply.startswith('OK ')
        text = reply[3:] if ok else reply
        lines = text.splitlines()
        players = []
        pattern = re.compile(r'^(.*) \(account (.*), level (\d+), (.*)\)$')
        for line in lines[1:]:
            match = pattern.match(line.strip())
            if match:
                players.append({'name': match[1], 'account': match[2],
                                'level': match[3], 'address': match[4]})
        count = len(players)
        if lines and lines[0].strip().endswith('online'):
            try:
                count = int(lines[0].split()[0])
            except (ValueError, IndexError):
                pass
        return {'ok': ok, 'reply': reply, 'count': count, 'players': players}

    def accounts(self, query=''):
        query = (query or '').strip()
        if len(query) > 64 or '\n' in query or '\r' in query:
            raise ApiError('account search must be one short line')
        reply = self._gm('accounts ' + query)
        rows = _json_reply(reply)
        return {'ok': rows is not None, 'rows': rows or [],
                'reply': '' if rows is not None else reply}

    def account(self, member):
        member = self._account_name(member)
        reply = self._gm('account ' + member)
        data = _json_reply(reply)
        return {'ok': data is not None, 'account': data,
                'reply': '' if data is not None else reply}

    def _account_name(self, member):
        if not isinstance(member, str) or not ACCOUNT_ID.fullmatch(member.strip()):
            raise ApiError('Account ID: 1-32 letters, digits, _, . or -')
        return member.strip()

    def _password(self, password):
        if (not isinstance(password, str) or not password
                or len(password.encode('utf-8')) > 63
                or any(character.isspace() for character in password)
                or '\0' in password):
            raise ApiError('Password: 1-63 UTF-8 bytes without whitespace')
        return password

    def account_create(self, member, password):
        member = self._account_name(member)
        password = self._password(password)
        reply = self._gm(f'account-create {member} {password}')
        return {'ok': reply.startswith('OK'), 'reply': reply}

    def account_password(self, member, password):
        member = self._account_name(member)
        password = self._password(password)
        reply = self._gm(f'account-password {member} {password}')
        return {'ok': reply.startswith('OK'), 'reply': reply}

    def account_role(self, member, role):
        member = self._account_name(member)
        if role not in ('A', 'N'):
            raise ApiError('Role must be A (GM) or N (normal)')
        reply = self._gm(f'account-role {member} {role}')
        return {'ok': reply.startswith('OK'), 'reply': reply}

    def status(self):
        code, output = self.runner(['status'], 25)
        return {'ok': code == 0, 'output': output, 'command': './launch.sh status'}

    def restart(self, confirm=False):
        if confirm is not True:
            raise ApiError('Restarting the emulator must be confirmed: it disconnects players.')
        code, output = self.runner(['restart-emu'], 120)
        return {'ok': code == 0, 'output': output, 'command': './launch.sh restart-emu'}

    def tail(self, lines=200):
        lines = _as_int(lines, 'lines', 200, 1, 1000)
        if not self.log_file or not self.log_file.is_file():
            return {'path': self._relative(self.log_file) if self.log_file else '',
                    'lines': []}
        size = self.log_file.stat().st_size
        with open(self.log_file, 'rb') as handle:
            handle.seek(max(0, size - 262144))
            text = handle.read().decode('utf-8', 'replace')
        return {'path': self._relative(self.log_file), 'lines': text.splitlines()[-lines:]}

    # ----- caches --------------------------------------------------------

    def _stamp(self, paths):
        stamp = []
        for path in paths:
            try:
                stamp.append((str(path), Path(path).stat().st_mtime_ns))
            except OSError:
                stamp.append((str(path), 0))
        return tuple(stamp)

    def _invalidate(self):
        self._items = None
        self._item_stamp = None
        self._names = None
        self._cars = None
        self._car_stamp = None
        self._groups = None
        self._group_stamp = None
        self._icons = {}
