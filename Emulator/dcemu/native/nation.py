"""The client's nation (publisher version), and the rules that depend on it.

The 2011 client is one program for every publisher; a nation number picks its rules, texts and data (client
0x4e9360 GetNation): 0 KR, 1 US, 2 JP, 3 TW, 4 INI, 5 TH thai, 6 TH eng, 7 EU de, 8 EU eng, 9 EU fr, 10 EU es.
The US client (DriftCity.exe) says nothing about it. The EU client (DriftCityEU.exe set to 7-10 by
tools/eu_client.py) sends 0x7cf Nation (u32) on every connection right after it opens: after the login on auth
(client 0x538aa9 -> 0x7feaf0), before the check-in on lobby / game / area. No answer is read.

So each session knows its client's nation: `of(session)` (or of a Player: `of(player)`, set at the game login).
A connection that sent no 0x7cf is a US client (1). emulator.ini [nation] client = N forces one nation for every
client (auto = what the client says).

Allowed nations: emulator.ini [nation] allow = all, or a list of nations / groups ("eu", "us", "8", "eu_eng" ...).
A client of another nation cannot log in: the auth service holds the login answer until the client's 0x7cf arrives
(the EU client sends it right behind the login; the US client never does: 1 s without it = US; with allow = all and
an ASCII password nothing waits, the nation is noted when it comes), then answers
WRONG_NATION instead of checking the password (no account is made). The nation of an accepted login is kept per
account (`remember`). The lobby and game check-ins test it again (a client can reach them with a ticket from an
earlier login): the session's own 0x7cf, else the account's login nation. On game the 0x7cf may come after the
check-in (both orders seen, 2026-10-17: a refusal there left the character loading), so game refuses only a
nation it knows. `detected(session)` is what the client said, whatever
[nation] client forces.

Rules that differ by nation go through this module (`rule(x, name)`), so the handlers ask one place:
    part_level   a part needs the player's level >= ItemClient column 7 ("Req Level")
    part_grade   a part needs the car's V grade >= ItemClient column 8 (the client's tooltip "Required Grade: %d",
                 GlobalText 11275, shown when column 7 is 0; client item record +0x120 level, +0x124 grade,
                 tooltip 0x657442). Which grade it means is not in the client (it only shows the number); the EU
                 texts call it the car's rank ("Your car's rank ...", 12140): read here as the car's V grade.
On for EU only (EU changes never touch US clients: user, 2026-10-17). The US tables fill only column 7; the EU
rules (parts by V grade) need column 8 filled: the EU client's tables.
emulator.ini [nation] us.<rule> / eu.<rule> = 0 / 1 overrides a rule for that group.
    level_points the player's level adds points to the four stats (the "User" column of F2 / the garage: level / 2
                 each with Contents.ini Main.HalfLevelPoint, else the level; player.stats). Off for EU: the EU
                 version gives no stat bonus for the player's level (user, 2026-10-17).
Client behaviour found so far that differs for the EU nations, for reference (tools/eu_client.py has the rest):
login password UTF-8, the start token, data folder Data_EU_<lang>, no GameGuard, the drift item swap special case
for i_d_u_11..18 is US only (client 0x602441).
"""
import asyncio

from ..handlers import on
from ..protocol import C2S
from . import context

NATION = 0x7cf
US, EU_DE, EU_ENG, EU_FR, EU_ES = 1, 7, 8, 9, 10
EU = frozenset((EU_DE, EU_ENG, EU_FR, EU_ES))
NAMES = {0: 'KR', 1: 'US', 2: 'JP', 3: 'TW', 4: 'INI', 5: 'TH thai', 6: 'TH eng',
         7: 'EU de', 8: 'EU eng', 9: 'EU fr', 10: 'EU es'}

# rules per nation group (group(): 'us' or 'eu'); emulator.ini [nation] us.<rule> / eu.<rule> overrides
RULES = {
    'us': dict(part_level=True, part_grade=False, level_points=True),
    'eu': dict(part_level=True, part_grade=True, level_points=False),
}


WRONG_NATION = 99      # the login result for a refused nation: the client shows "Authentication system abnormal.(99)"
WAIT_SECONDS = 1.0     # how long the login waits for the client's 0x7cf
GROUPS = {'us': {US}, 'eu': set(EU), 'eu_de': {EU_DE}, 'eu_eng': {EU_ENG}, 'eu_fr': {EU_FR}, 'eu_es': {EU_ES}}


def parse_allow(v):
    """'all' -> None (every nation), else the set of nations named ('eu, 1', 'eu_eng', '8 9')."""
    v = (v or 'all').strip().lower()
    if v in ('all', '*', ''):
        return None
    out = set()
    for w in v.replace(',', ' ').split():
        if w in GROUPS:
            out |= GROUPS[w]
        elif w.isdigit():
            out.add(int(w))
        else:
            raise ValueError(f'emulator.ini [nation] allow: unknown nation {w!r} (all, us, eu, eu_de / eu_eng / '
                             'eu_fr / eu_es or numbers)')
    return out


def configure(section):
    """emulator.ini [nation] (a configparser section or a dict)."""
    v = (section.get('client', 'auto') or 'auto').strip().lower()
    context.nation_forced = None if v == 'auto' else int(v)
    context.nation_allow = parse_allow(section.get('allow', 'all'))
    for key, value in section.items():
        g, _, r = key.partition('.')
        if g in RULES and r in RULES[g]:
            RULES[g][r] = value.strip() not in ('0', 'no', 'off')


def of(x):
    """The nation of a session (what its client said, else US) or of a Player; emulator.ini [nation] client wins."""
    forced = getattr(context, 'nation_forced', None)
    if forced is not None:
        return forced
    if x is None:
        return US
    if hasattr(x, 'state'):                          # a session: its own 0x7cf, else its player's / account's
        n = x.state.get('nation')
        if n is None and x.state.get('player') is not None:
            n = getattr(x.state['player'], 'nation', None)
        if n is None:
            n = _login_nation.get((x.state.get('member') or '').lower())
        return US if n is None else n
    return getattr(x, 'nation', US)                  # a Player


def detected(session):
    """What the session's client said (1 = said nothing: a US client)."""
    n = session.state.get('nation')
    return US if n is None else n


async def wait_detected(session, timeout=WAIT_SECONDS):
    """The client's nation once its 0x7cf has come, or US after timeout seconds without it."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while session.state.get('nation') is None and loop.time() < end:
        await asyncio.sleep(0.02)
    return detected(session)


_login_nation = {}     # account (lower case) -> the nation of its last accepted login


def remember(member, n):
    _login_nation[member.lower()] = n


def known(session, member):
    """The session's own nation (its 0x7cf), else the account's login nation, else None (not known yet)."""
    n = session.state.get('nation')
    return n if n is not None else _login_nation.get((member or '').lower())


def of_member(member):
    """The nation of a character not in the game (loaded for someone else): its account's last accepted login,
    else the lowest allowed nation when this server lets only EU nations in (an EU nation), else US."""
    n = _login_nation.get((member or '').lower())
    if n is not None:
        return n
    allow = getattr(context, 'nation_allow', None)
    return min(allow) if allow and allow <= EU else US


def allowed(n):
    allow = getattr(context, 'nation_allow', None)
    return allow is None or n in allow


def allowed_all():
    return getattr(context, 'nation_allow', None) is None


def allowed_names():
    allow = getattr(context, 'nation_allow', None)
    return 'all' if allow is None else ', '.join(f'{n} {name(n)}' for n in sorted(allow))


def is_eu(x):
    return of(x) in EU


def group(x):
    return 'eu' if is_eu(x) else 'us'


def name(n):
    return NAMES.get(n, str(n))


def rule(x, key):
    return RULES[group(x)][key]


# Login results (auth 0x16 @4) whose text means something else in the EU texts. The client maps a code to a text key
# (client 0x50cb10; nations other than 1: table 0x50ce80, the same keys for 1-5, 7, 10, 12-14) and the EU column
# of those keys was written for the EU server's codes: 10049 (code 4) is "An ID or Password has not been entered."
# in US English but "This is an ID with an age restriction" in EU English (user, 2026-10-17). EU English has
# "You did not enter your ID or password." (10081), but no code reaches it, so an empty password is sent as 1
# ("Your password is incorrect") and an empty ID as 2 ("This ID does not exist").
NO_ID = 4


def login_result(n, result, member):
    """The login result to send to a client of nation n."""
    if n in EU and result == NO_ID:
        return 2 if not member else 1
    return result


def part_allowed(x, player, info, car):
    """-> None if the part may go on the car, else why not (for the log). x: the session or the player."""
    if rule(x, 'part_level') and info.req_level and player.char.level < info.req_level:
        return f'level {player.char.level} < {info.req_level}'
    if rule(x, 'part_grade') and info.req_grade and car is not None and car.grade < info.req_grade:
        return f'car V{car.grade} < V{info.req_grade}'
    return None


@on('native:game', C2S, 0x0005)
async def eu_report(session, frame):
    """0x0005 (104 bytes): a report only the EU client sends, from a periodic sender (client 0x6506d0 -> 0x7e3ef0,
    when its +0x22c flag is set; also from the 0x0004 handler 0x52fdc0). Seen once per session, mostly an
    uninitialised buffer. The 2008 server's ping answer (Cmd_Ping -> 2) is not it; nothing is answered."""
    session.log.note(f'client report 0x0005 ({len(frame.payload)} bytes, nation {of(session)}): not answered')


@on('native:auth', C2S, NATION)
@on('native:lobby', C2S, NATION)
@on('native:game', C2S, NATION)
@on('native:area', C2S, NATION)
@on('native:barea', C2S, NATION)
async def nation(session, frame):
    """0x7cf Nation (u32): the EU client's nation, sent on each connection."""
    n = int.from_bytes(frame.payload[:4], 'little')
    first = session.state.get('nation') is None
    session.state['nation'] = n
    if session.state.get('login_member') and allowed(n):     # auth: a login answered without waiting for this
        remember(session.state['login_member'], n)
    p = session.state.get('player')
    if p is not None:
        p.nation = n
    if first:
        session.log.note(f'client nation {n} ({name(n)})')
    if session.state.get('member') and not allowed(n):     # it came after a check-in that let it through
        session.log.note(f'client nation {n} ({name(n)}) is not allowed here: closed')
        session.close()
