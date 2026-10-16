"""The game database (SQL Server, the same SKDBTW database and tables the 2008 server uses).

Queries run in a worker thread (python-tds is blocking), one connection per thread. Parameters use
the %s style: db.rows('SELECT ... WHERE MEMBERID=%s', (member,)).
"""
import asyncio
import threading

import pytds


class Database:
    def __init__(self, host, port, user, password, name, server_id):
        self.args = dict(server=host, port=port, user=user, password=password, database=name, autocommit=True)
        self.server_id = server_id
        self.local = threading.local()

    def _conn(self):
        c = getattr(self.local, 'conn', None)
        if c is None:
            c = self.local.conn = pytds.connect(**self.args)
        return c

    def _run(self, sql, params, fetch):
        try:
            cur = self._conn().cursor()
            cur.execute(sql, params)
            return cur.fetchall() if fetch else None
        except (pytds.Error, OSError):
            self.local.conn = None          # reconnect next time
            raise

    async def rows(self, sql, params=()):
        return await asyncio.to_thread(self._run, sql, params, True)

    async def row(self, sql, params=()):
        r = await self.rows(sql, params)
        return r[0] if r else None

    async def execute(self, sql, params=()):
        await asyncio.to_thread(self._run, sql, params, False)
