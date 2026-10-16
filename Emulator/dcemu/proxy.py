"""The proxy: one listener per service, each client connection paired with a connection to
the 2008 ZoneServer. Every frame is logged and passed through the handlers registered for its
(service, direction, type); unhandled frames go on byte for byte.

A service with upstream port 0 is local: the emulator itself is the server. It sends the
handshake, runs the handlers for what the client sends, and forwards nothing; handlers answer
with session.to_client()."""
import asyncio
import inspect
import itertools
import traceback

from . import commands, handlers
from .protocol import C2S, S2C
from .wire import Frame, FrameReader, Raw

_ids = itertools.count(1)
live = {}       # session id -> Session: every open connection of the local (native) services


class Session:
    """One client connection and its upstream connection."""

    def __init__(self, service, client_w, server_w, msglog):
        self.id = next(_ids)
        self.service = service
        self.client_w = client_w
        self.server_w = server_w
        self.msglog = msglog
        self.log = msglog.session(self.id, service)
        self.state = {}
        self.log_frames = True      # False: frames are not written to the message log

    def to_client(self, item):
        self.msglog.item(self.id, self.service, S2C, item, rewritten=True)
        self.client_w.write(item.encode())

    def close(self):
        """Drop the client (a kick): its pump ends and the connection's hooks are cancelled."""
        if not self.client_w.is_closing():
            self.client_w.close()

    def to_server(self, item):
        self.msglog.item(self.id, self.service, C2S, item, rewritten=True)
        self.server_w.write(item.encode())

    @property
    def key(self):
        """Handler namespace: 'native:<service>' for a local service, else the service name."""
        return self.service if self.server_w is not None else 'native:' + self.service

    async def handle(self, direction, frame):
        """Run the handlers -> (frames to forward, whether anything changed). A frame holding
        several commands is split (commands.split) and each command runs its own handlers."""
        parts = None if handlers.wants_whole(self.key) else commands.split(frame)
        if parts and len(parts) > 1:
            self.log.note('commands: ' + ' '.join(f'0x{f.type:x}({len(f.payload) + 2})' for f in parts))
            out, changed = [], False
            for f in parts:
                r, c = await self._run(direction, f)
                out += r; changed |= c
            return ([commands.join(out)] if changed and out else [frame] if not changed else []), changed
        return await self._run(direction, frame)

    async def _run(self, direction, frame):
        items = [frame]
        fns = handlers.handlers_for(self.key, direction, frame.type)
        if not fns and self.server_w is None:
            self.log.note(f'no handler for 0x{frame.type:04x} on this local service')
        for fn in fns:
            nxt = []
            for f in items:
                try:
                    r = fn(self, f)
                    if inspect.isawaitable(r):
                        r = await r
                except Exception:
                    self.log.note(f'handler {fn.__module__}.{fn.__name__} failed, message passed on:\n'
                                  + traceback.format_exc())
                    r = f
                nxt.extend([] if r is None else r if isinstance(r, list) else [r])
            items = nxt
        changed = len(items) != 1 or items[0] is not frame
        return items, changed


async def pump(session, direction, reader, writer, handshake):
    fr = FrameReader(handshake)
    try:
        while data := await reader.read(65536):
            for item in fr.feed(data):
                if session.log_frames:
                    session.msglog.item(session.id, session.service, direction, item)
                if not isinstance(item, Frame):
                    if writer:
                        writer.write(item.encode())
                    continue
                out, changed = await session.handle(direction, item)
                if not writer:              # local service: nothing to forward to
                    continue
                for f in out:
                    if changed:
                        session.msglog.item(session.id, session.service, direction, f, rewritten=True)
                    writer.write(f.encode())
            if writer:
                await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        if writer and not writer.is_closing():
            writer.close()


class Service:
    def __init__(self, name, listen, port, upstream, upstream_port, handshake, msglog):
        self.name, self.listen, self.port = name, listen, port
        self.upstream, self.upstream_port = upstream, upstream_port
        self.handshake, self.msglog = handshake, msglog

    async def start(self):
        return await asyncio.start_server(self.accept, self.listen, self.port)

    async def accept(self, cr, cw):
        peer = cw.get_extra_info('peername')
        if not self.upstream_port:
            s = Session(self.name, cw, None, self.msglog)
            self.msglog.event(s.id, self.name, f'open {peer[0]}:{peer[1]} (local)')
            if self.handshake:              # cipher type 0: plain traffic
                s.to_client(Raw(bytes(self.handshake), 'handshake'))
            live[s.id] = s
            tasks = [asyncio.ensure_future(fn(s)) for fn in handlers.open_hooks(s.key)]
            try:
                await pump(s, C2S, cr, None, self.handshake)
            finally:
                live.pop(s.id, None)
                for t in tasks:
                    t.cancel()
            cw.close()
            self.msglog.event(s.id, self.name, 'closed')
            return
        try:
            sr, sw = await asyncio.open_connection(self.upstream, self.upstream_port)
        except OSError as e:
            self.msglog.event(0, self.name, f'{peer} connected, but {self.upstream}:{self.upstream_port} is down ({e})')
            cw.close()
            return
        s = Session(self.name, cw, sw, self.msglog)
        self.msglog.event(s.id, self.name, f'open {peer[0]}:{peer[1]}')
        await asyncio.gather(pump(s, C2S, cr, sw, self.handshake), pump(s, S2C, sr, cw, self.handshake))
        self.msglog.event(s.id, self.name, 'closed')
