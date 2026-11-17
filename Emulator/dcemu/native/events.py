"""Season events: one switch per event (emulator.ini [events]), on / off / auto (auto = inside the event's date window).

An event that is on (for the day of a player's login) turns on its content flags in the login's flag block
(login.content_flags; emulator.ini [flags] still overrides any single flag) and its server parts (is_on(name) in the
modules). The flags reach the client only at login: a change (gmevent, a new day) shows after a relog.

emulator.ini [events]:
    <event> = on | off | auto           (default auto)
    <event>.dates = MM-DD..MM-DD        the auto window (may wrap the year end); Easter's default follows Easter Sunday
GM: chat `gmevent` (list), `gmevent <event> on|off|auto` (until the restart); control port `event ...` the same.

What each event is in the clients: docs/neo_work/SEASON_EVENTS.md (research) and EMULATOR_NOTES (session 48).
"""
import datetime

from . import context

# name -> (shown name, default window or 'easter', content flags (2011 names; flags missing from a build are skipped))
EVENTS = {
    'christmas': ('Christmas', ('12-01', '01-07'),
                  ('Etc.EventChristmas', 'Etc.EventChristmasTree', 'Etc.EventChristmasChase')),
    'newyear': ('Lunar New Year (lucky bag, Hongbao)', ('01-20', '02-20'),
                ('Etc.EventLuckyBag', 'Etc.HongbaoEvent', 'Etc.HongbaoEventRush')),
    'valentine': ('Valentine', ('02-01', '02-28'), ('Etc.EventValentine', 'Etc.EventValentainChocolate')),
    'easter': ('Easter', 'easter', ()),
    'independence': ('Independence Day', ('06-27', '07-10'), ('Etc.EventIndependenceDay',)),
    'summer': ('Summer (Watermelon HUV)', ('07-01', '08-31'), ('Etc.EventWaterMelon',)),
    'harvest': ('Harvest', ('09-15', '10-20'), ('Etc.EventGoodHarvest',)),
    'halloween': ('Halloween', ('10-20', '11-07'), ('Etc.EventHalloween',)),
    'anniversary': ('Anniversary', None, ('Etc.Event3Year',)),     # no fixed date: on / off only
}
MODES = ('on', 'off', 'auto')


def easter_sunday(year):
    """Gregorian Easter Sunday (the anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return datetime.date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def _md(text):
    month, day = (int(x) for x in text.strip().split('-'))
    return month, day


def window(name, year):
    """-> the (first, last) dates of the event's auto window that can contain a day of `year` (or None)."""
    dates = context.events.get(name + '.dates') or EVENTS[name][1]
    if dates == 'easter':
        sunday = easter_sunday(year)
        return sunday - datetime.timedelta(days=21), sunday + datetime.timedelta(days=7)
    if not dates:
        return None
    if isinstance(dates, str):
        dates = dates.split('..')
    return _md(dates[0]), _md(dates[1])


def in_window(name, day):
    w = window(name, day.year)
    if w is None:
        return False
    first, last = w
    if isinstance(first, datetime.date):
        return first <= day <= last
    md = (day.month, day.day)
    return first <= md <= last if first <= last else md >= first or md <= last     # a window over the year end


def mode(name):
    return context.events.get(name, 'auto')


def is_on(name, day=None):
    """The event runs (on, or auto and inside its window today)."""
    m = mode(name)
    if m == 'on':
        return True
    return m == 'auto' and in_window(name, day or datetime.date.today())


def flags(day=None):
    """Content flags of the events that run: {flag: 1}."""
    from .version import flag_table
    table = flag_table()
    return {f: 1 for n, (_, _, fl) in EVENTS.items() if is_on(n, day) for f in fl if f in table}


def load(section):
    """emulator.ini [events] -> context.events (unknown keys are reported, bad values fall back to auto)."""
    context.events = {}
    for key, value in (section or {}).items():
        key, value = key.strip().lower(), value.strip().lower()
        name = key.split('.', 1)[0]
        if name not in EVENTS:
            print(f'emulator.ini [events]: unknown event {key}', flush=True)
        elif key.endswith(('.drops', '.tree')):        # seasonal.py: event drops, the Christmas tree stage
            context.events[key] = value
        elif key.endswith('.dates'):
            try:
                a, b = value.split('..')
                _md(a), _md(b)
                context.events[key] = value
            except ValueError:
                print(f'emulator.ini [events]: {key} = {value}: use MM-DD..MM-DD', flush=True)
        elif value in MODES:
            context.events[key] = value
        else:
            print(f'emulator.ini [events]: {key} = {value}: use on, off or auto', flush=True)


def status(day=None):
    day = day or datetime.date.today()
    out = []
    for n, (shown, _, _) in EVENTS.items():
        w = window(n, day.year)
        span = '' if w is None else (f' {w[0]:%m-%d}..{w[1]:%m-%d}' if isinstance(w[0], datetime.date)
                                     else ' %02d-%02d..%02d-%02d' % (*w[0], *w[1]))
        out.append(f'{n} ({shown}): {mode(n)}{span} -> {"ON" if is_on(n, day) else "off"}')
    return out


def gm_command(args):
    """gmevent | gmevent <event> on|off|auto -> the reply text."""
    if not args:
        return 'season events (flags reach the client at login):\n  ' + '\n  '.join(status())
    name = args[0].lower()
    if name not in EVENTS or len(args) < 2 or args[1].lower() not in MODES:
        return f'usage: gmevent [{"|".join(EVENTS)} on|off|auto]'
    context.events[name] = args[1].lower()
    from .game.seasonal import push_event_switch
    told = push_event_switch(name)
    return (f'{name}: {args[1].lower()} -> {"ON" if is_on(name) else "off"} (until the emulator restarts; '
            f'players see the client side after a relog' + (f'; {told} online told now' if told else '') + ')')
