"""Message handlers: functions that see a frame on its way through the proxy.

    @on('auth', C2S, 0x14)
    def login(session, frame):
        ...
        return frame              # forward (the same or a new Frame)

A handler returns a Frame to forward, a list of Frames, or None to drop the message. It can
also inject messages with session.to_client(frame) / session.to_server(frame), and keep
per-connection state in session.state. Handlers for one message run in registration order,
each on the previous one's output. A handler that raises is logged and the message goes on
unchanged, so a bug never cuts the connection.

Modules listed in MODULES are imported by the proxy; add new ones there. Native services (a
local service, ZoneServer port 0) use the namespace 'native:<service>' (dcemu/native/); their
handlers may be coroutines.
"""
import collections

_handlers = collections.defaultdict(list)

MODULES = ['auth', 'lobby', 'game', 'area', 'vshop', 'room', '..native.auth', '..native.lobby', '..native.stickers', '..native.ranking', '..native.game', '..native.area']


def on(service, direction, msg_type):
    def deco(fn):
        _handlers[(service, direction, msg_type)].append(fn)
        return fn
    return deco


_whole = set()


def whole_frames(service):
    """Frames of this (native) service reach its handlers whole, not split into commands with the
    2008 sizes: the handler walks them itself (native/area.py, 2011 sizes)."""
    _whole.add(service)


def wants_whole(service):
    return service in _whole


def handlers_for(service, direction, msg_type):
    return _handlers.get((service, direction, msg_type), ())


_open = collections.defaultdict(list)


def on_open(service):
    """Coroutine run for each new connection of a native service (e.g. a keepalive loop);
    cancelled when the connection closes."""
    def deco(fn):
        _open[service].append(fn)
        return fn
    return deco


def open_hooks(service):
    return _open.get(service, ())


def load():
    import importlib
    for m in MODULES:
        importlib.import_module(m, __name__) if m.startswith('.') else importlib.import_module(f'{__name__}.{m}')
