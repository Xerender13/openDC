import inspect
import unittest

from dcemu import handlers
import dcemu.native.game  # noqa: F401  (registers the handlers)


class HooksTest(unittest.TestCase):
    def test_open_hooks_are_coroutines(self):
        """A plain function as an on_open hook breaks every connection of its service (2026-10-15: a helper put
        under city_offers' decorator left the client stuck on loading data)."""
        for service, fns in handlers._open.items():
            for fn in fns:
                self.assertTrue(inspect.iscoroutinefunction(fn), f'{service}: {fn.__module__}.{fn.__name__}')
