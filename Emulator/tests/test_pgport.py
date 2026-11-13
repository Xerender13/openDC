"""tools/pgport/migrate.py: part of the SQL Server -> PostgreSQL port.

Type mapping, default translation, DDL generation from a fake column list and reserved-word detection.
No database is touched here; the connection helpers import pytds / pg8000 only when they connect.
"""
import sys
import unittest

from tools.pgport import migrate


def col(name, type_, nullable=False, length=None, precision=None, scale=None, default=None,
        identity=None):
    default_sql, ok = migrate.translate_default(default)
    return {'name': name, 'type': type_, 'length': length, 'precision': precision, 'scale': scale,
            'nullable': nullable, 'default': default, 'default_sql': default_sql, 'default_ok': ok,
            'identity': identity}


def table(name='SKID_TEST_TB', columns=(), pk=None, uniques=(), indexes=()):
    return {'name': name, 'columns': list(columns), 'primary_key': pk or [],
            'uniques': list(uniques), 'indexes': list(indexes), 'identity_current': None}


class TypeTest(unittest.TestCase):
    def test_text_types_are_citext(self):
        for kind in ('char', 'varchar', 'nchar', 'nvarchar', 'text', 'ntext', 'VARCHAR'):
            self.assertEqual(migrate.pg_type(col('C', kind, length=32)), 'citext', kind)

    def test_numbers(self):
        self.assertEqual(migrate.pg_type(col('C', 'bit')), 'smallint')
        self.assertEqual(migrate.pg_type(col('C', 'tinyint')), 'smallint')
        self.assertEqual(migrate.pg_type(col('C', 'smallint')), 'smallint')
        self.assertEqual(migrate.pg_type(col('C', 'int')), 'integer')
        self.assertEqual(migrate.pg_type(col('C', 'bigint')), 'bigint')
        self.assertEqual(migrate.pg_type(col('C', 'money')), 'numeric(19,4)')
        self.assertEqual(migrate.pg_type(col('C', 'float')), 'double precision')
        self.assertEqual(migrate.pg_type(col('C', 'real')), 'real')

    def test_numeric_keeps_precision_and_scale(self):
        self.assertEqual(migrate.pg_type(col('C', 'numeric', precision=18, scale=0)), 'numeric(18,0)')
        self.assertEqual(migrate.pg_type(col('C', 'decimal', precision=5, scale=2)), 'numeric(5,2)')
        self.assertEqual(migrate.pg_type(col('C', 'numeric')), 'numeric')

    def test_time(self):
        for kind in ('datetime', 'datetime2', 'smalldatetime'):
            self.assertEqual(migrate.pg_type(col('C', kind)), 'timestamp(3)', kind)
        self.assertEqual(migrate.pg_type(col('C', 'date')), 'date')

    def test_binary_and_guid(self):
        for kind in ('varbinary', 'binary', 'image'):
            self.assertEqual(migrate.pg_type(col('C', kind)), 'bytea', kind)
        self.assertEqual(migrate.pg_type(col('C', 'uniqueidentifier')), 'uuid')

    def test_unknown_type_names_the_column(self):
        with self.assertRaises(ValueError) as caught:
            migrate.pg_type(col('XMLDATA', 'xml'))
        self.assertIn('xml', str(caught.exception))
        self.assertIn('XMLDATA', str(caught.exception))


class DefaultTest(unittest.TestCase):
    def test_number_defaults(self):
        self.assertEqual(migrate.translate_default('((0))'), ('0', True))
        self.assertEqual(migrate.translate_default('(0)'), ('0', True))
        self.assertEqual(migrate.translate_default('(((-1)))'), ('-1', True))
        self.assertEqual(migrate.translate_default('((0.0))'), ('0.0', True))

    def test_getdate(self):
        self.assertEqual(migrate.translate_default('(getdate())'), ('getdate()', True))
        self.assertEqual(migrate.translate_default('(GETDATE())'), ('getdate()', True))

    def test_string_defaults(self):
        self.assertEqual(migrate.translate_default("('Y')"), ("'Y'", True))
        self.assertEqual(migrate.translate_default("(N'x')"), ("'x'", True))
        self.assertEqual(migrate.translate_default("('it''s')"), ("'it''s'", True))
        self.assertEqual(migrate.translate_default("(' ')"), ("' '", True))

    def test_null_and_none(self):
        self.assertEqual(migrate.translate_default('(NULL)'), ('NULL', True))
        self.assertEqual(migrate.translate_default(None), (None, True))

    def test_unknown_default_is_kept_and_flagged(self):
        sql, ok = migrate.translate_default('(newid())')
        self.assertEqual(sql, '(newid())')
        self.assertFalse(ok)
        sql, ok = migrate.translate_default("(CONVERT([datetime],'1900-01-01',0))")
        self.assertFalse(ok)
        self.assertIn('CONVERT', sql)


class DdlTest(unittest.TestCase):
    def sample(self):
        return table(
            columns=[
                col('MEMBERID', 'char', length=12),
                col('CNO', 'int'),
                col('NICK', 'nvarchar', length=32),
                col('CDATE', 'datetime', nullable=True, default='(getdate())'),
                col('USE_YN', 'char', length=1, default="('Y')"),
                col('ITEM_SEQ', 'numeric', precision=18, scale=0, identity={'seed': 100000,
                                                                            'increment': 1}),
            ],
            pk=['MEMBERID'], uniques=[['NICK']],
            indexes=[{'name': 'IX_TEST_CNO', 'unique': False, 'columns': [('CNO', False)]}])

    def test_create_table(self):
        stmts = migrate.table_ddl(self.sample())
        create = [s for s in stmts if s.startswith('CREATE TABLE')][0]
        self.assertEqual(create,
                         'CREATE TABLE skid_test_tb (\n'
                         '    memberid citext NOT NULL,\n'
                         '    cno integer NOT NULL,\n'
                         '    nick citext NOT NULL,\n'
                         "    cdate timestamp(3) DEFAULT getdate(),\n"
                         "    use_yn citext DEFAULT 'Y' NOT NULL,\n"
                         "    item_seq numeric(18,0) DEFAULT nextval('skid_test_tb_item_seq_seq') "
                         'NOT NULL,\n'
                         '    PRIMARY KEY (memberid),\n'
                         '    UNIQUE (nick)\n'
                         ')')

    def test_numeric_identity_uses_an_owned_sequence(self):
        stmts = migrate.table_ddl(self.sample())
        self.assertEqual(stmts[0], 'CREATE SEQUENCE skid_test_tb_item_seq_seq START WITH 100000')
        self.assertIn('ALTER SEQUENCE skid_test_tb_item_seq_seq OWNED BY skid_test_tb.item_seq', stmts)
        self.assertEqual(stmts[-1],
                         'CREATE INDEX skid_test_tb_ix_test_cno ON skid_test_tb (cno)')

    def test_int_identity_is_native(self):
        one = table(columns=[col('EVENT_SEQ', 'int', identity={'seed': 100, 'increment': 1})])
        stmts = migrate.table_ddl(one)
        self.assertEqual(len(stmts), 1)                     # no CREATE SEQUENCE, no OWNED BY
        self.assertIn('event_seq integer GENERATED BY DEFAULT AS IDENTITY (START WITH 100)', stmts[0])
        self.assertNotIn('NOT NULL', stmts[0])              # identity implies it

    def test_identity_increment_and_negative_seed(self):
        one = table(columns=[col('SEQ', 'bigint', identity={'seed': 10, 'increment': 5})])
        self.assertIn('GENERATED BY DEFAULT AS IDENTITY (START WITH 10 INCREMENT BY 5)',
                      migrate.table_ddl(one)[0])
        two = table(columns=[col('SEQ', 'int', identity={'seed': -5, 'increment': 1})])
        self.assertIn('(START WITH -5 MINVALUE -5)', migrate.table_ddl(two)[0])

    def test_unique_and_descending_index(self):
        one = table(columns=[col('A', 'int'), col('B', 'datetime')],
                    indexes=[{'name': 'UX_A_B', 'unique': True, 'columns': [('A', False), ('B', True)]}])
        self.assertEqual(migrate.table_ddl(one)[-1],
                         'CREATE UNIQUE INDEX skid_test_tb_ux_a_b ON skid_test_tb (a, b DESC)')

    def test_schema_sql_creates_citext_first(self):
        stmts = migrate.ddl_statements([self.sample()])
        self.assertEqual(stmts[0], 'CREATE EXTENSION IF NOT EXISTS citext')
        self.assertEqual(len(stmts), 5)     # extension, sequence, table, owned by, index
        sql = migrate.schema_sql([self.sample()])
        self.assertIn('CREATE EXTENSION IF NOT EXISTS citext;\n', sql)
        self.assertTrue(sql.endswith(';\n'))
        self.assertIn('CREATE TABLE skid_test_tb (', sql)

    def test_defaults_are_inlined_only_when_translated(self):
        one = table(columns=[col('K', 'int'), col('X', 'int', nullable=True, default='((7))'),
                             col('Y', 'int', nullable=True, default='(newid())')])
        create = migrate.table_ddl(one)[0]
        self.assertIn('x integer DEFAULT 7', create)
        self.assertIn('y integer DEFAULT (newid())', create)  # kept verbatim, listed in the report

    def test_identifiers_are_lower_case_and_unquoted(self):
        one = table('SkidMixed_TB', columns=[col('MixedCase', 'int'), col('ITEM-ID', 'int'),
                                             col('1ST', 'int')])
        create = migrate.table_ddl(one)[0]
        self.assertIn('CREATE TABLE skidmixed_tb (', create)
        self.assertIn('mixedcase integer', create)
        self.assertIn('item_id integer', create)             # rewritten; reported
        self.assertIn('_1st integer', create)                # leading digit; reported


class ReservedTest(unittest.TestCase):
    def test_reserved_words_are_found(self):
        one = table(columns=[col('USER', 'int'), col('ORDER', 'int'), col('GROUP', 'char'),
                             col('DESC', 'int'), col('LIMIT', 'int'), col('OFFSET', 'int'),
                             col('CHECK', 'int'), col('END', 'int'), col('BOTH', 'int'),
                             col('MEMBERID', 'char'), col('CDATE', 'datetime')])
        self.assertEqual(migrate.reserved_columns(one),
                         ['USER', 'ORDER', 'GROUP', 'DESC', 'LIMIT', 'OFFSET', 'CHECK', 'END', 'BOTH'])

    def test_detection_ignores_case(self):
        self.assertEqual(migrate.reserved_columns(table(columns=[col('User', 'int')])), ['User'])

    def test_illegal_identifiers(self):
        one = table(columns=[col('MY COL', 'int'), col('ITEM-ID', 'int'), col('1ST', 'int'),
                             col('NORMAL_1', 'int'), col('_OK', 'int')])
        self.assertEqual(migrate.illegal_columns(one), ['MY COL', 'ITEM-ID', '1ST'])


class TargetTest(unittest.TestCase):
    def test_target_splits_host_port_user_password_db(self):
        got = migrate.parse_target('localhost:1433:sa:secret:SKDBTW')
        self.assertEqual(got, {'host': 'localhost', 'port': 1433, 'user': 'sa',
                               'password': 'secret', 'db': 'SKDBTW'})

    def test_password_may_contain_a_colon(self):
        got = migrate.parse_target('db:5432:opendc:pa:ss:word:SKDB2016TEST')
        self.assertEqual(got['password'], 'pa:ss:word')
        self.assertEqual(got['db'], 'SKDB2016TEST')

    def test_bad_target(self):
        with self.assertRaises(ValueError):
            migrate.parse_target('localhost:1433:sa')

    def test_value_conversion(self):
        from decimal import Decimal
        self.assertEqual(migrate.convert_value(True), 1)
        self.assertEqual(migrate.convert_value(False), 0)
        self.assertEqual(migrate.convert_value(bytearray(b'\x01')), b'\x01')
        self.assertEqual(migrate.convert_value(Decimal('1.50')), Decimal('1.50'))
        self.assertEqual(migrate.convert_value('ab '), 'ab ')   # char(n) padding kept
        self.assertIsNone(migrate.convert_value(None))


class ImportTest(unittest.TestCase):
    def test_drivers_are_imported_only_when_connecting(self):
        self.assertNotIn('pytds', sys.modules)
        self.assertNotIn('pg8000', sys.modules)


if __name__ == '__main__':
    unittest.main()
