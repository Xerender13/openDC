"""Message log: every frame in both directions, one line each, in logs/<start time>.msgs.txt.

    12:00:01.234 #3 auth  C>S  0x0014 Login        156 <payload hex>
    12:00:01.234 #3 auth  C>S* 0x0014 Login        152 <payload hex>     (* = as rewritten)
    12:00:01.240 #3 auth  --   login 'admin' ...                         (handler notes)
Lengths include the 4-byte header; the hex is the payload after it. Raw (unframed) chunks have
'raw' in place of the type.
"""
import os
import time

from .protocol import name
from .wire import Frame


class MsgLog:
    def __init__(self, log_dir, echo=True, echo_hex=48):
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, time.strftime('%Y%m%d-%H%M%S') + '.msgs.txt')
        self.f = open(self.path, 'a', buffering=1, encoding='utf-8')
        self.echo = echo
        self.echo_hex = echo_hex

    @staticmethod
    def stamp():
        t = time.time()
        return time.strftime('%H:%M:%S', time.localtime(t)) + f'.{int(t % 1 * 1000):03d}'

    def _line(self, head, body):
        self.f.write(f'{head} {body}\n')
        if self.echo:
            print(head, body if len(body) < 160 else body[:160] + '...', flush=True)

    def item(self, sid, service, direction, item, rewritten=False):
        d = direction + ('*' if rewritten else ' ')
        head = f'{self.stamp()} #{sid} {service:5} {d}'
        if isinstance(item, Frame):
            n = 4 + len(item.payload)
            self.f.write(f'{head} 0x{item.type:04x} {name(item.type):16} {n:5} {item.payload.hex()}\n')
            if self.echo:
                print(f'{head} 0x{item.type:04x} {name(item.type):16} {n:5} {item.payload[:self.echo_hex].hex()}'
                      + ('...' if len(item.payload) > self.echo_hex else ''), flush=True)
        else:
            self.f.write(f'{head} raw    {item.reason:16} {len(item.data):5} {item.data.hex()}\n')
            if self.echo:
                print(f'{head} raw    {item.reason:16} {len(item.data):5}', flush=True)

    def event(self, sid, service, text):
        self._line(f'{self.stamp()} #{sid} {service:5} -- ', text)

    def session(self, sid, service):
        """A logger bound to one connection, for handlers: session.log.note(...)."""
        log = self

        class Bound:
            def note(self, text):
                log.event(sid, service, text)
        return Bound()

