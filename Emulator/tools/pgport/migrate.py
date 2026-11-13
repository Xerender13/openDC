"""One-time SQL Server (SKDBTW / SKDB2016TEST) -> PostgreSQL migration.

usage (from Emulator/):

    python -m tools.pgport.migrate --mssql HOST:PORT:USER:PASSWORD:DB \\
                                   --pg   HOST:PORT:USER:PASSWORD:DB \\
                                   [--schema-only] [--out DIR]

The password is the rest between the user and the database, so it may contain ':'.

What it does, in order:

1. Introspects the SQL Server database (schema dbo): every user table and its columns in order, the
   primary key, the unique constraints, the other indexes, the identity seed/increment and IDENT_CURRENT
   of each identity column. Every stored procedure, function, view and trigger definition (sys.sql_modules)
   is written verbatim to OUT/procedures/<name>.sql, to be ported to PL/pgSQL by hand.
2. Writes the generated DDL to OUT/schema.sql and applies it to the PostgreSQL database.
3. Copies the rows table by table (batches of 1000) and then sets each identity sequence to max(col)+1
   with setval(pg_get_serial_sequence(...), ..., false), so the next INSERT gets a fresh id.
4. Writes OUT/report.txt: row counts (source vs target), the sequences, and everything that needs a human
   (defaults copied verbatim, reserved-word column names, identifiers that had to be rewritten).

Design notes (evidence, not preference):

- Identifiers are unquoted and lower case: PostgreSQL folds unquoted names to lower case, so the
  emulator's existing unquoted SQL (``SELECT ... FROM SKID_ITEM_TB``) keeps working unchanged.
- Text is ``citext``: SQL Server's default collation compares strings case-insensitively and the emulator
  relies on it, so ``citext`` keeps that behaviour. Lengths (varchar(n), char(n)) are not enforced by
  citext; the report counts them. char(n) padding is copied as read, as decided.
- ``numeric(p,0)`` identity columns cannot use ``GENERATED ... AS IDENTITY``: PostgreSQL 16 rejects any
  identity column whose type is not smallint/integer/bigint
  ("identity column type must be smallint, integer, or bigint", src/backend/commands/sequence.c in
  REL_16_STABLE). The schema's id columns are ``numeric(18,0) IDENTITY``, so for those the tool creates an
  explicit sequence, ``DEFAULT nextval(...)`` and ``ALTER SEQUENCE ... OWNED BY``, which keeps the same
  "explicit values allowed" behaviour and keeps pg_get_serial_sequence working.
- The generated DDL has no DROP and no IF NOT EXISTS. Run it against an empty database: the tool refuses
  to start if one of the source tables already exists in the target.

Nothing is written to the SQL Server database; this tool only reads it.
"""
import argparse
import re
import sys
from pathlib import Path

# PostgreSQL reserved words (CREATE TABLE / keywords list, PG 16). Unquoted, these cannot be column names.
RESERVED = {
    'all', 'analyse', 'analyze', 'and', 'any', 'array', 'as', 'asc', 'asymmetric', 'authorization',
    'binary', 'both', 'case', 'cast', 'check', 'collate', 'collation', 'column', 'concurrently',
    'constraint', 'create', 'cross', 'current_catalog', 'current_date', 'current_role', 'current_schema',
    'current_time', 'current_timestamp', 'current_user', 'default', 'deferrable', 'desc', 'distinct', 'do',
    'else', 'end', 'except', 'false', 'fetch', 'for', 'foreign', 'freeze', 'from', 'full', 'grant', 'group',
    'having', 'ilike', 'in', 'initially', 'inner', 'intersect', 'into', 'is', 'isnull', 'join', 'lateral',
    'leading', 'left', 'like', 'limit', 'localtime', 'localtimestamp', 'natural', 'not', 'notnull', 'null',
    'offset', 'on', 'only', 'or', 'order', 'outer', 'overlaps', 'placing', 'primary', 'references',
    'returning', 'right', 'select', 'session_user', 'similar', 'some', 'symmetric', 'table', 'tablesample',
    'then', 'to', 'trailing', 'true', 'union', 'unique', 'user', 'using', 'variadic', 'verbose', 'when',
    'where', 'window', 'with',
}

TEXT_TYPES = ('char', 'varchar', 'nchar', 'nvarchar', 'text', 'ntext')

PLAIN_TYPES = {
    'bit': 'smallint',              # the client sends 0/1 flags; smallint keeps them as numbers
    'tinyint': 'smallint',          # PostgreSQL has no unsigned 8-bit type
    'smallint': 'smallint',
    'int': 'integer',
    'bigint': 'bigint',
    'money': 'numeric(19,4)',
    'float': 'double precision',
    'real': 'real',
    'datetime': 'timestamp(3)',
    'datetime2': 'timestamp(3)',
    'smalldatetime': 'timestamp(3)',
    'date': 'date',
    'varbinary': 'bytea',
    'binary': 'bytea',
    'image': 'bytea',
    'uniqueidentifier': 'uuid',
}

INT_TYPES = ('smallint', 'integer', 'bigint')
BATCH = 1000                        # rows read per batch (and at most per INSERT)
MAX_PARAMS = 30000                  # PostgreSQL protocol limit is 65535 bind parameters per statement


# --- pure helpers: identifiers, types, defaults, DDL ------------------------------------------------

def ident(name):
    """An unquoted, lower case PostgreSQL identifier (folded the way PostgreSQL folds it)."""
    s = re.sub(r'[^a-z0-9_]', '_', str(name).lower())
    if not s or s[0].isdigit():
        s = '_' + s
    return s[:63]


def sequence_name(table, col):
    return ident('%s_%s_seq' % (table['name'], col['name']))


def index_name(table, name):
    return ident('%s_%s' % (table['name'], name))


def pg_type(col):
    """The PostgreSQL type of an introspected column: {'type', 'length', 'precision', 'scale'}."""
    t = str(col['type']).lower()
    if t in TEXT_TYPES:
        return 'citext'                     # case-insensitive like the SQL Server default collation
    if t in ('numeric', 'decimal'):
        if col.get('precision') is None:
            return 'numeric'
        return 'numeric(%d,%d)' % (int(col['precision']), int(col.get('scale') or 0))
    if t in PLAIN_TYPES:
        return PLAIN_TYPES[t]
    raise ValueError('no PostgreSQL mapping for SQL Server type %r (column %r); add it to PLAIN_TYPES'
                     % (col['type'], col.get('name')))


def _unparen(s):
    """Strip balanced outer parentheses: '((0))' -> '0', but '(1)+(2)' is left alone."""
    s = s.strip()
    while len(s) >= 2 and s[0] == '(' and s[-1] == ')':
        depth, wrapped = 0, True
        for i, ch in enumerate(s):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    wrapped = False
                    break
        if not wrapped or depth:
            break
        s = s[1:-1].strip()
    return s


def translate_default(text):
    """SQL Server COLUMN_DEFAULT -> (PostgreSQL default expression or None, translated?).

    The second value is False when the text was kept verbatim because it is not one of the forms the
    emulator's schema uses; the caller lists those in the report. getdate() is assumed to be provided by
    a compatibility function of the target database.
    """
    if text is None:
        return None, True
    s = _unparen(text)
    low = s.lower()
    if low == 'null':
        return 'NULL', True
    if low == 'getdate()':
        return 'getdate()', True
    if re.fullmatch(r'-?\d+(?:\.\d+)?', s):
        return s, True
    quoted = re.fullmatch(r"N?'((?:[^']|'')*)'", s, re.I)
    if quoted:
        return "'" + quoted.group(1) + "'", True
    return text.strip(), False


def sequence_options(seed, increment):
    """START WITH / INCREMENT BY / MINVALUE options for a sequence starting at a SQL Server identity seed."""
    seed, increment = int(seed), int(increment)
    opts = ['START WITH %d' % seed]
    if increment != 1:
        opts.append('INCREMENT BY %d' % increment)
    if seed < 1 and increment > 0:
        opts.append('MINVALUE %d' % seed)
    return ' '.join(opts)


def _identity_is_native(col):
    """PostgreSQL only allows AS IDENTITY on smallint/integer/bigint."""
    return pg_type(col) in INT_TYPES


def column_ddl(table, col):
    """One column line of CREATE TABLE (no trailing comma)."""
    out = [ident(col['name']), pg_type(col)]
    ident_col = col.get('identity')
    if ident_col:
        opts = sequence_options(ident_col['seed'], ident_col['increment'])
        if _identity_is_native(col):
            out.append('GENERATED BY DEFAULT AS IDENTITY (%s)' % opts)     # implies NOT NULL
            return ' '.join(out)
        # numeric identity: PostgreSQL refuses AS IDENTITY here, use an owned sequence instead
        out.append("DEFAULT nextval('%s')" % sequence_name(table, col))
    elif col.get('default_sql') is not None:
        out.append('DEFAULT ' + col['default_sql'])
    if not col['nullable']:
        out.append('NOT NULL')
    return ' '.join(out)


def table_ddl(table):
    """The statements for one table: CREATE TABLE plus its indexes (and any identity sequence)."""
    tname = ident(table['name'])
    pre, post, lines = [], [], []
    for col in table['columns']:
        ident_col = col.get('identity')
        if ident_col and not _identity_is_native(col):
            seq = sequence_name(table, col)
            pre.append('CREATE SEQUENCE %s %s'
                       % (seq, sequence_options(ident_col['seed'], ident_col['increment'])))
            post.append('ALTER SEQUENCE %s OWNED BY %s.%s' % (seq, tname, ident(col['name'])))
        lines.append('    ' + column_ddl(table, col))
    if table.get('primary_key'):
        lines.append('    PRIMARY KEY (%s)' % ', '.join(ident(c) for c in table['primary_key']))
    for cols in table.get('uniques') or []:
        lines.append('    UNIQUE (%s)' % ', '.join(ident(c) for c in cols))
    used = set()
    for ix in table.get('indexes') or []:
        base = name = index_name(table, ix['name'])
        n = 2
        while name in used:                 # index names are schema-wide in PostgreSQL
            name = ident('%s_%d' % (base, n))
            n += 1
        used.add(name)
        cols = ', '.join(ident(c) + (' DESC' if d else '') for c, d in ix['columns'])
        post.append('CREATE %sINDEX %s ON %s (%s)'
                    % ('UNIQUE ' if ix.get('unique') else '', name, tname, cols))
    return pre + ['CREATE TABLE %s (\n%s\n)' % (tname, ',\n'.join(lines))] + post


def ddl_statements(tables):
    """The whole schema, as individual statements (pg8000 runs one statement per execute)."""
    stmts = ['CREATE EXTENSION IF NOT EXISTS citext']
    for table in tables:
        stmts.extend(table_ddl(table))
    return stmts


def schema_sql(tables):
    """OUT/schema.sql: the same statements as text."""
    head = ('-- Generated by tools/pgport/migrate.py from SQL Server (schema dbo).\n'
            '-- Identifiers are unquoted and lower case, text is citext (case-insensitive, as the\n'
            '-- SQL Server default collation was), and the emulator\'s existing SQL keeps working.\n\n')
    return head + ';\n\n'.join(ddl_statements(tables)) + ';\n'


def reserved_columns(table):
    """Columns whose name is a PostgreSQL reserved word: reported, never quoted silently."""
    return [c['name'] for c in table['columns'] if str(c['name']).lower() in RESERVED]


def illegal_columns(table):
    """Columns that cannot be used unquoted at all (spaces, dashes, leading digit...)."""
    return [c['name'] for c in table['columns']
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', str(c['name']))]


# --- introspection (SQL Server, read only) ---------------------------------------------------------

TABLES_SQL = """SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo' ORDER BY TABLE_NAME"""

COLUMNS_SQL = """SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
                        NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT
                 FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION"""

IDENTITY_SQL = """SELECT c.name, CAST(ic.seed_value AS bigint), CAST(ic.increment_value AS bigint)
                  FROM sys.identity_columns ic
                  JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                  WHERE ic.object_id = OBJECT_ID(%s)"""

INDEXES_SQL = """SELECT i.name, i.is_primary_key, i.is_unique, i.is_unique_constraint,
                        ic.key_ordinal, ic.is_descending_key, c.name
                 FROM sys.indexes i
                 JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                 JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                 WHERE i.object_id = OBJECT_ID(%s) AND i.type IN (1, 2)
                   AND i.is_hypothetical = 0 AND ic.is_included_column = 0 AND ic.key_ordinal > 0
                 ORDER BY i.index_id, ic.key_ordinal"""

OBJECTS_SQL = """SELECT o.name, o.type, m.definition
                 FROM sys.sql_modules m JOIN sys.objects o ON o.object_id = m.object_id
                 WHERE o.schema_id = SCHEMA_ID('dbo') ORDER BY o.type, o.name"""


def query(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, tuple(params))
    return cur.fetchall() if cur.description else []


def load_indexes(conn, full_name):
    groups, order = {}, []
    for iname, is_pk, is_unique, is_constraint, _ordinal, descending, col in query(conn, INDEXES_SQL,
                                                                                   (full_name,)):
        g = groups.get(iname)
        if g is None:
            g = groups[iname] = {'name': iname, 'pk': is_pk, 'unique': is_unique,
                                 'constraint': is_constraint, 'columns': []}
            order.append(iname)
        g['columns'].append((col, bool(descending)))
    pk, uniques, indexes = [], [], []
    for iname in order:
        g = groups[iname]
        names = [c for c, _d in g['columns']]
        if g['pk']:
            pk = names
        elif g['constraint']:
            uniques.append(names)
        else:
            indexes.append({'name': iname, 'unique': bool(g['unique']), 'columns': g['columns']})
    return pk, uniques, indexes


def load_table(conn, name):
    full = 'dbo.' + name
    identity = {r[0]: (int(r[1]), int(r[2])) for r in query(conn, IDENTITY_SQL, (full,))}
    columns = []
    for cname, dtype, length, precision, scale, nullable, default in query(conn, COLUMNS_SQL, (name,)):
        default_sql, default_ok = translate_default(default)
        seed = identity.get(cname)
        columns.append({
            'name': cname, 'type': dtype, 'length': length, 'precision': precision, 'scale': scale,
            'nullable': nullable == 'YES', 'default': default,
            'default_sql': default_sql, 'default_ok': default_ok,
            'identity': None if seed is None else {'seed': seed[0], 'increment': seed[1]},
        })
    pk, uniques, indexes = load_indexes(conn, full)
    current = None
    if identity:
        try:
            current = query(conn, 'SELECT IDENT_CURRENT(%s)', (name,))[0][0]
        except Exception:                   # IDENT_CURRENT needs a permission some logins lack
            current = None
    return {'name': name, 'columns': columns, 'primary_key': pk, 'uniques': uniques,
            'indexes': indexes, 'identity_current': current}


def introspect(conn):
    tables = [load_table(conn, name) for (name,) in query(conn, TABLES_SQL)]
    # sys.objects.type is char(2): 'P ' comes back padded, so strip it before matching
    objects = [(name, kind.strip(), definition) for name, kind, definition in query(conn, OBJECTS_SQL)]
    return {'tables': tables, 'objects': objects}


# --- PostgreSQL side: schema and data ---------------------------------------------------------------

def connect_mssql(target):
    import pytds
    return pytds.connect(server=target['host'], port=target['port'], user=target['user'],
                         password=target['password'], database=target['db'], autocommit=True)


def connect_pg(target):
    import pg8000
    return pg8000.connect(host=target['host'], port=target['port'], user=target['user'],
                          password=target['password'], database=target['db'])


def parse_target(spec):
    """'host:port:user:password:DB' -> dict. The password is the rest before the database, so it may
    contain ':'."""
    parts = spec.split(':', 3)
    if len(parts) != 4:
        raise ValueError('expected HOST:PORT:USER:PASSWORD:DB, got %r' % spec)
    host, port, user, rest = parts
    password, sep, db = rest.rpartition(':')
    if not sep or not db:
        raise ValueError('expected HOST:PORT:USER:PASSWORD:DB, got %r' % spec)
    return {'host': host, 'port': int(port), 'user': user, 'password': password, 'db': db}


def convert_value(value):
    """SQL Server value -> what pg8000 accepts for the mapped type."""
    if isinstance(value, bool):                     # bit
        return int(value)
    if isinstance(value, (bytearray, memoryview)):  # varbinary/image
        return bytes(value)
    return value                                    # Decimal, datetime, date, bytes, str(uuid) kept


def copy_table(src, dst, table, log=print):
    """Copy one table in batches; returns the number of rows written."""
    cols = [c['name'] for c in table['columns']]
    tname = ident(table['name'])
    select = 'SELECT %s FROM [dbo].[%s]' % (', '.join('[%s]' % c for c in cols), table['name'])
    insert = 'INSERT INTO %s (%s) VALUES ' % (tname, ', '.join(ident(c) for c in cols))
    placeholders = '(%s)' % ', '.join(['%s'] * len(cols))
    per = max(1, min(BATCH, MAX_PARAMS // len(cols)))    # wide tables: fewer rows per INSERT
    read, write = src.cursor(), dst.cursor()
    read.execute(select)
    total = 0
    while True:
        batch = read.fetchmany(per)
        if not batch:
            break
        values = [convert_value(v) for row in batch for v in row]
        write.execute(insert + ', '.join([placeholders] * len(batch)), values)
        total += len(batch)
        if total % 20000 == 0:
            log('    %s: %d rows' % (table['name'], total))
    dst.commit()
    return total


def reset_identity(dst, table, log=print):
    """setval(sequence, max(col)+1, false) for every identity column; returns the report lines."""
    lines = []
    for col in table['columns']:
        if not col.get('identity'):
            continue
        tname, cname = ident(table['name']), ident(col['name'])
        found = query(dst, 'SELECT pg_get_serial_sequence(%s, %s)', (tname, cname))[0][0]
        if not found:
            lines.append('%s.%s: no sequence found, set it by hand' % (tname, cname))
            continue
        top = query(dst, 'SELECT max(%s) FROM %s' % (cname, tname))[0][0]
        if top is None:                          # empty table: the sequence still starts at the seed
            lines.append('%s.%s: empty, sequence %s left at START WITH %d'
                         % (tname, cname, found, int(col['identity']['seed'])))
            continue
        query(dst, 'SELECT setval(%s, %s, false)', (found, int(top) + 1))
        lines.append('%s.%s: sequence %s -> %d (IDENT_CURRENT was %s)'
                     % (tname, cname, found, int(top) + 1, table.get('identity_current')))
        log('    %s.%s sequence -> %d' % (tname, cname, int(top) + 1))
    dst.commit()
    return lines


# --- report ----------------------------------------------------------------------------------------

def report_text(meta, source, rows=None, seqs=None, schema_only=False):
    tables = meta['tables']
    ncols = sum(len(t['columns']) for t in tables)
    nidx = sum(len(t['indexes']) for t in tables)
    out = ['# pgport: SQL Server -> PostgreSQL report', '',
           'source database: %s (schema dbo)' % source,
           'tables: %d, columns: %d, other indexes: %d' % (len(tables), ncols, nidx),
           'sql modules (procedures / views / functions): %d' % len(meta['objects']), '']

    out.append('## sql modules (T-SQL, not translated: port by hand)')
    kinds = {'P': 'procedure', 'V': 'view', 'FN': 'function', 'IF': 'function', 'TF': 'function',
             'TR': 'trigger', 'AF': 'function', 'C': 'check', 'D': 'default'}
    for name, kind, _definition in meta['objects']:
        out.append('%-40s %-10s procedures/%s.sql' % (name, kinds.get(kind, kind), procs_file(name)))
    if not meta['objects']:
        out.append('(none readable: the login needs VIEW DEFINITION)')
    out.append('')

    reserved = [(t['name'], c) for t in tables for c in reserved_columns(t)]
    out.append('## column names that are PostgreSQL reserved words (created unquoted, so SQL using them '
               'must quote or be rewritten)')
    if reserved:
        out.extend('%-30s %s' % x for x in reserved)
    else:
        out.append('(none)')
    out.append('')

    illegal = [(t['name'], c) for t in tables for c in illegal_columns(t)]
    out.append('## column names that are not plain [A-Za-z0-9_] identifiers (rewritten in the DDL)')
    if illegal:
        out.extend('%-30s %s' % x for x in illegal)
    else:
        out.append('(none)')
    out.append('')

    unknown = [(t['name'], c['name'], c['default']) for t in tables for c in t['columns']
               if c.get('default') is not None and not c.get('default_ok')]
    out.append('## defaults kept verbatim (not translated; check or replace them)')
    if unknown:
        out.extend('%-30s %-28s %s' % x for x in unknown)
    else:
        out.append('(none)')
    out.append('')

    out.append('## text')
    text_total = sum(1 for t in tables for c in t['columns'] if str(c['type']).lower() in TEXT_TYPES)
    out.append('%d text column(s) are citext: case-insensitive like the SQL Server collation, but the '
               'varchar(n)/char(n)/text lengths are not enforced' % text_total)
    out.append('')

    if schema_only:
        out.append('## data')
        out.append('--schema-only: no rows were copied')
        out.append('')
        return '\n'.join(out)

    out.append('## row counts')
    out.append('%-34s %10s %10s %s' % ('table', 'source', 'target', 'state'))
    for tname, src_n, dst_n in rows or []:
        out.append('%-34s %10d %10d %s' % (tname, src_n, dst_n, 'ok' if src_n == dst_n else 'DIFFERENT'))
    out.append('')
    out.append('## identity sequences')
    out.extend(seqs or ['(none)'])
    out.append('')
    return '\n'.join(out)


def procs_file(name):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


# --- main ------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.pgport.migrate', description=__doc__.split('\n')[0])
    ap.add_argument('--mssql', required=True, metavar='HOST:PORT:USER:PASSWORD:DB')
    ap.add_argument('--pg', required=True, metavar='HOST:PORT:USER:PASSWORD:DB')
    ap.add_argument('--schema-only', action='store_true', help='write the DDL and the report, copy no rows')
    ap.add_argument('--out', default='pgport-out', metavar='DIR', help='output directory (default pgport-out)')
    args = ap.parse_args(argv)

    try:
        mssql, pg = parse_target(args.mssql), parse_target(args.pg)
    except ValueError as exc:
        sys.exit('migrate: %s' % exc)
    out = Path(args.out)
    (out / 'procedures').mkdir(parents=True, exist_ok=True)

    print('reading the SQL Server schema ...')
    src = connect_mssql(mssql)
    meta = introspect(src)
    print('  %d tables, %d sql modules' % (len(meta['tables']), len(meta['objects'])))

    for name, _kind, definition in meta['objects']:
        (out / 'procedures' / (procs_file(name) + '.sql')).write_text(definition or '',
                                                                      encoding='utf-8', errors='backslashreplace')
    (out / 'schema.sql').write_text(schema_sql(meta['tables']), encoding='utf-8')
    # write the findings now, so they survive a failure during the copy
    (out / 'report.txt').write_text(report_text(meta, mssql['db'], schema_only=True), encoding='utf-8')
    print('  wrote %s/schema.sql, %s/procedures/<name>.sql, %s/report.txt' % (out, out, out))
    src.close()

    if args.schema_only:
        print('--schema-only: nothing was created in PostgreSQL')
        return 0

    stmts = ddl_statements(meta['tables'])
    dst = connect_pg(pg)
    existing = {r[0] for r in query(dst, "SELECT table_name FROM information_schema.tables "
                                       "WHERE table_schema = 'public'")}
    clash = sorted(existing & {ident(t['name']) for t in meta['tables']})
    if clash:
        sys.exit('target already has %s; run against an empty database (nothing is dropped here)'
                 % ', '.join(clash))

    print('creating the PostgreSQL schema ...')
    # db/postgres/00_compat.sql first: citext and getdate(), which the column defaults call
    compat = Path(__file__).resolve().parents[2] / 'db' / 'postgres' / '00_compat.sql'
    if compat.exists():
        dst.cursor().execute(compat.read_text())
    for stmt in stmts:
        query(dst, stmt)
    dst.commit()

    print('copying data ...')
    rows = []
    for table in meta['tables']:
        if not table['columns']:
            continue
        msrc = connect_mssql(mssql)            # fresh connection per table: no half-read result left
        src_n = query(msrc, 'SELECT COUNT_BIG(*) FROM [dbo].[%s]' % table['name'])[0][0]
        dst_n = copy_table(msrc, dst, table)
        msrc.close()
        rows.append((table['name'], int(src_n), dst_n))
        print('  %-30s %8d rows' % (table['name'], dst_n))

    print('setting the identity sequences ...')
    seqs = []
    for table in meta['tables']:
        seqs.extend(reset_identity(dst, table))
    dst.close()

    (out / 'report.txt').write_text(report_text(meta, mssql['db'], rows, seqs), encoding='utf-8')
    print('done: %s/report.txt' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
