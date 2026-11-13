"""The game database: PostgreSQL (since session 42; before it the 2008 server's SQL Server database SKDBTW, whose tables
and columns were moved over unchanged by tools/pgport/migrate.py: names in lower case, text columns citext so that
names compare case-insensitively as they did, db/postgres/00_compat.sql for getdate() and the stored procedures).

Queries run in a worker thread (pg8000 is blocking and pure Python, so it runs on any CPU), one connection per thread,
autocommit. Parameters use the %s style: db.rows('SELECT ... WHERE memberid=%s', (member,)).
  rows(sql, params)          -> list of rows        row(sql, params) -> the first row or None
  execute(sql, params)       -> the number of rows the statement changed
  update_or_insert(update, params, insert, params)   the UPDATE, or the INSERT when it changed no row
  transaction(fn)            -> fn(cursor)'s result; fn runs in one thread on one connection inside BEGIN / COMMIT
                                (ROLLBACK when it raises): for what the SQL Server batches did with BEGIN TRAN.
                                cursor.execute(sql, params), cursor.fetchall(), cursor.fetchone(), cursor.rowcount.
One statement per call: PostgreSQL's extended protocol takes one statement with parameters.
"""
import asyncio
import threading


class Database:
    def __init__(self, host, port, user, password, name, server_id):
        self.args = dict(host=host, port=int(port), user=user, password=password, database=name)
        self.server_id = server_id
        self.local = threading.local()

    def _conn(self):
        c = getattr(self.local, 'conn', None)
        if c is None:
            import pg8000.dbapi
            c = pg8000.dbapi.connect(**self.args)
            c.autocommit = True
            self.local.conn = c
        return c

    def _drop(self):
        c = getattr(self.local, 'conn', None)
        self.local.conn = None
        try:
            if c is not None:
                c.close()
        except Exception:
            pass

    def _run(self, sql, params, fetch):
        import pg8000.dbapi
        try:
            cur = self._conn().cursor()
            cur.execute(sql, tuple(params) if params else ())
            if fetch:
                return [tuple(r) for r in cur.fetchall()] if cur.description else []   # tuples, as python-tds gave
            return cur.rowcount
        except (pg8000.dbapi.InterfaceError, OSError):
            self._drop()                    # reconnect next time
            raise

    def _transaction(self, fn):
        import pg8000.dbapi
        conn = self._conn()
        try:
            conn.autocommit = False
            cur = conn.cursor()
            try:
                result = fn(cur)
                conn.commit()
                return result
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True
        except (pg8000.dbapi.InterfaceError, OSError):
            self._drop()
            raise

    async def rows(self, sql, params=()):
        return await asyncio.to_thread(self._run, sql, params, True)

    async def row(self, sql, params=()):
        r = await self.rows(sql, params)
        return r[0] if r else None

    async def execute(self, sql, params=()):
        return await asyncio.to_thread(self._run, sql, params, False)

    async def update_or_insert(self, update_sql, update_params, insert_sql, insert_params):
        """The SQL Server "UPDATE ...; IF @@ROWCOUNT = 0 INSERT ..." pattern (no unique key to ON CONFLICT on)."""
        if not await self.execute(update_sql, update_params):
            await self.execute(insert_sql, insert_params)

    async def transaction(self, fn):
        return await asyncio.to_thread(self._transaction, fn)
