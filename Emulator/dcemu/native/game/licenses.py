"""Licenses (2011; no 2008 server code): License.xlt (69 licenses: up to 12 gain conditions "GC_x:target", up to two
mount effects "ME_x" + value), License_GC.xlt (195 condition kinds), License_ME.xlt (31 effects).

Messages (client handlers / senders; the request senders are vtable methods 0x805a40 .. 0x805c30):
0x32b GetLicenseInfo (u32 the client's list version) -> 0x32c GetLicenseInfoAck (u32 version, u32 n, n x (u16 license
    id, u16 0, u16 0); client 0x525e50: replaces its list at [char + 0x1b1c], the version at list + 0x10 comes back in
    the next request). Sent when the license window opens (0x5fd43b / 0x61e5d7), with 0x32d.
0x32d GetLicenseCond (u32 version) -> 0x32e GetLicenseCondAck (u32 version, u16 n, u16 0 = first part (the list is
    cleared), u32 total, n x (u16 condition id, u32 value); client 0x525f40, list at [char + 0x1b28]; the client
    reads GC_Reputation_01..03 from it too). The client also sends 0x32d by itself every ~2 minutes (answered here:
    the conditions are checked then as well).
0x32f SelectLicense (3 x u16: the mounted licenses, 0 = empty) -> 0x330 SelectLicenseAck (the same; client 0x51e920
    keeps them at [char + 0x1b20] and reads the client-side effects ME_AcroComboRepair / ME_ReverseComboRepair /
    ME_UseBoost50Recovery of the mounted ones), and 0x326 LicenseInfoRes (u16 serial, the 3 x u16) to the other players
    (client 0x50e770: kept with that player's car). Only held licenses can be mounted.
0x331 NewLicenseNoti (u16 license id, u16 1): a license gained (client 0x50e7e0: its notice; text by the id).
0x29a LicenseStatus (u32 0, u32 serial: another player's licenses, the car's menu "license", client 0x5eb6b7) ->
    0x29b LicenseStatusAck (u32 0, u32 serial, u32 n @0xa, wchar[21] name @0xe, 3 x u16 mounted @0x38, n x (u16 id,
    u16 0, u16 0) @0x3e; client 0x511260 opens the license window on them) and 0x32a ETCInfo (that player's
    conditions: u16 n @0xa, u16 0 = first part @0xc, u32 @0xe, n x (u16 condition id, u32 value) @0x12; client
    0x511510). The emulator sent an empty 0x32a at login before (login.py, still).
License Ownership Reward Money (client texts 11703 / 11712-11715, its dialog 3010000 only shows the amounts): once a
    month, on or after the reset day (RESET_DAY = content flag Etc.NewLicenseSystemnDay, the day the dialog names), the
    first time the player is in the Driver Dome (position state 3: login there, 0xa2 SaveCarPos with state 3, or the
    periodic 0x32d; user: only in the Driver Dome, not after the tutorial): the License.xlt "Grade" of every license held
    (Rookie 3000 .. Mittron Island Guardian 100000) added up, paid in Mito as a kind-500 message (0x84; the client adds
    its Mito to its money and shows the text; not stored). A month without a login is not paid (the dialog: uncollected
    money expires at the reset). Kept: SKID_PLAYMODE_TB 'LICPAY' (POINT = the YYYYMM paid last, NEXP = the amount).
Content flags (handlers/game.py NEW_FLAGS): Main.License (the license panel and its requests, 0x5fd40f) and
    Etc.NewLicenseSystem (the 2011 window, 0x61e558).

Kept in SKID_PLAYMODE_TB: MODEID = the condition's name (GC_BattleTeam, ...; POINT = the counter), 'GCM_<kind>_YYYYMM'
(monthly counters: parts modify / convert / production tries, read as This / Last Month), 'LIC_<id>' per license held
(CDATE = when), 'LICSLOTS' (TRYCNT / WINCNT / POINT = the 3 mounted ids).

Conditions. Counters (count()): battles (team / individual rooms) and battles per city track, HUV chases cleared (alone /
party, per city), rush time cleared and won (Lucky Driver), deliveries (played, gold / silver / bronze, per job: medal /
gold, GC_Quick<G><City>_<job number> = job a_000<number>), patrols (alone / party, per city: the posts' city), quests
(repeatable rq_*, per city), Undercity and field driving time (the increases of the client's coupon totals, seconds),
mission tokens, auctions of 20000 Mito or more (registered / sold), parts enhanced to +10 .. +19 and above, Mita 500
(drinks, the 500 % roll, the third step 250 %), the Mitro City reputations GC_Reputation_01..03 (mothers.py), camouflage kit time (cartrans items: 300 s, Adv. 900 s), monthly tries.
Computed (value()): GC_MQuestClear / GC_Mo|Co|Cr|OrQuestClear (a city's main quest chain finished: one of its last
quests rewarded; Oros has the ROO and the OMD ending), GC_OMD / GC_TEAMROO (the faction quest taken: QuestClient column
5), GC_LicenseGain_<ids> (held), GC_DCbadge_NN (badge i_n_dcbadge_NN held once: kept as a counter then), the ladder win rates (no ladder arena here: 0, so Rookie, "any one of them >= 0", is everyone's).
Not counted (no such game mode here): channel battle attack / defence (GC_Challenger / GC_Guardian), ghost battles,
the 3rd anniversary coins, GC_BattleTimePercent.
A license is gained when every condition reaches its target (License.xlt "Support" 1 only), checked after each count,
at login and on 0x32d.

Mount effects (the mounted licenses only; effects()): server side: Mito / exp bonuses by activity (items.play_bonus:
ME_AllExpMito, ME_MittronGuardian (also drops), ME_BattleTeamMito / PersonalMito, ME_<City>TrackExp, ME_QuickExpMito and
the per-city delivery ones, ME_ChasingExpMito, ME_AllPatrolExpMito, ME_UnderExpMito, ME_CarTransExp (Mito while a
camouflage kit runs)), fees (ME_AuctionFeeDis, ME_EnhanceFeeDis, ME_FeeDis), ME_PartDropRate; client side: the combo
repairs and the booster recovery.
"""
import datetime
import re
import struct
import time

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .login import SVC, send, sessions

SLOTS = 3
AUCTION_MIN = 20000                      # GC_AuctionOn / GC_AuctionSuccess: "20k Mito or Higher"
CITY_SUFFIX = {1: ('Moon', 'Mo', 'MO'), 2: ('Koi', 'Ko', 'KO'), 3: ('Cras', 'Cr', 'CR'), 4: ('Oros', 'Or', 'OR')}
POST_CITY = {'post_1st': 1, 'post_2nd': 2, 'post_3rd': 3, 'post_4rd': 4}
TRACK_CITY = {'moonpalace': 1, 'koinonia': 2, 'kononia': 2, 'cras': 3, 'oros': 4}
LOAD_SQL = ("SELECT MODEID, POINT, TRYCNT, WINCNT FROM SKID_PLAYMODE_TB WHERE SERVERID=%s AND CID=%s AND"
            " (MODEID LIKE 'GC[_]%%' OR MODEID LIKE 'GCM[_]%%' OR MODEID LIKE 'LIC[_]%%' OR MODEID='LICSLOTS')")
ADD_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), POINT=POINT+%s WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME, NEXP,
    GAMEMONEY, BESTCNT, RETIRECNT) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),0,0,%s,0,0,0,0,0)"""
SLOTS_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), TRYCNT=%s, WINCNT=%s, POINT=%s WHERE SERVERID=%s AND CID=%s AND MODEID='LICSLOTS';
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME, NEXP,
    GAMEMONEY, BESTCNT, RETIRECNT) VALUES (%s,%s,%s,'LICSLOTS',GetDate(),GetDate(),%s,%s,%s,0,0,0,0,0)"""
CNAME_SQL = "SELECT CNAME FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND CID=%s"


class Tables:
    def __init__(self):
        import os
        from ..data import read_xlt
        root = os.path.join(context.data.root, 'Init')
        self.gc_id, self.gc_name, self.instant = {}, {}, set()
        for r in read_xlt(os.path.join(root, 'License_GC.xlt'))[3:]:
            if len(r) > 3 and r[1].strip().isdigit() and r[2].strip():
                i, n = int(r[1]), r[2].strip()
                self.gc_id[n], self.gc_name[i] = i, n
                if r[3].strip() == '1':
                    self.instant.add(n)
        rows = read_xlt(os.path.join(root, 'License.xlt'))
        h = rows[2]
        col = {n: h.index(n) for n in ('Support', 'LicenseID', 'LicenseName', 'Grade', 'MountEffectID', 'MountEffectValue',
                                       'MountEffectID_second', 'MountEffectValue_second', 'Condition_1')}
        self.licenses = {}
        for r in rows[3:]:
            if len(r) <= col['Condition_1'] or not r[col['LicenseID']].strip().isdigit():
                continue
            conds = []
            for c in r[col['Condition_1']:col['Condition_1'] + 12]:
                name, _, target = c.strip().partition(':')
                if name and name != 'n/a':
                    conds.append((name, int(target or 0)))
            effects = [(r[col[k]].strip(), int(float(r[col[v]] or 0))) for k, v in
                       (('MountEffectID', 'MountEffectValue'), ('MountEffectID_second', 'MountEffectValue_second'))
                       if r[col[k]].strip() not in ('', 'n/a')]
            self.licenses[int(r[col['LicenseID']])] = dict(
                name=r[col['LicenseName']].strip(), support=r[col['Support']].strip() == '1', conds=conds,
                reward=int(float(r[col['Grade']] or 0)),
                effects=effects, any=all(n.startswith('GC_LadderPoint_') for n, _ in conds))
        # main quest chains: a city's exits = its main q_ quests whose next quest is in another city or none
        q = context.data.quests
        nxt = {}
        for i, r in enumerate(q):
            if r and r[4] != '0':
                nxt.setdefault(r[4], []).append(i)
        self.city_exits = {}
        self.faction_quest = {}
        for i, r in enumerate(q):
            if not r or r[2] != 'main' or not r[0].startswith('q_'):
                continue
            city = POST_CITY.get(r[9][:8])
            later = [POST_CITY.get(q[k][9][:8]) for k in nxt.get(r[1], [])]
            if city and (not later or any(c != city for c in later)):
                self.city_exits.setdefault(city, set()).add(i)
            if r[5] in ('OMD', 'ROO'):
                self.faction_quest[i] = r[5]


_tables = None


def tables():
    global _tables
    if _tables is None:
        _tables = Tables()
    return _tables


def month_key(kind, when=None):
    d = when or datetime.date.today()
    return f'GCM_{kind}_{d.year:04d}{d.month:02d}'


def last_month():
    first = datetime.date.today().replace(day=1)
    return first - datetime.timedelta(days=1)


async def load(p):
    db = context.db
    st = dict(gc={}, held={}, slots=[0] * SLOTS, version=1, conds_version=1, camo_until=0)
    for mode, point, tries, wins in await db.rows(LOAD_SQL, (db.server_id, p.char.cid)):
        mode = mode.strip()
        if mode == 'LICSLOTS':
            st['slots'] = [int(tries or 0), int(wins or 0), int(point or 0)]
        elif mode.startswith('LIC_') and mode[4:].isdigit():
            st['held'][int(mode[4:])] = True
        else:
            st['gc'][mode] = int(point or 0)
    p.lic = st
    return st


def state(p):
    return getattr(p, 'lic', None)


ROOKIE = 7000


def mounted(st):
    """The mounted licenses as shown and applied: with none mounted, Rookie (everyone's first license) in slot 1, so the
    nameplate's license spot is never empty (user, 2026-10-15). The stored slots stay as chosen."""
    slots = list(st['slots']) if st else [0] * SLOTS
    if not any(slots) and st and ROOKIE in st['held']:
        slots[0] = ROOKIE
    return slots


def quest_state(p, idx):
    return next((q[1] for q in p.quests if q[0] == idx), None)


def faction(p):
    """'ROO' for guild type 1 (0x76c SelectGuild, quests.py: sent by "First Task from ROO" and by the choice), else the
    side of the faction quest taken after "Choice" (#127 ROO / #145 OMD)."""
    from .quests import ROO_GUILD
    if p.char.guild == ROO_GUILD:
        return 'ROO'
    t = tables()
    for idx, side in t.faction_quest.items():
        if quest_state(p, idx) is not None:
            return side if side != 'ROO' or not p.char.guild else None
    return None


def city_cleared(p, city):
    return any(quest_state(p, i) == 2 for i in tables().city_exits.get(city, ()))


def value(p, name):
    """The condition's value for the player (a counter, or computed)."""
    st = state(p)
    if st is None:
        return 0
    if name.startswith('GC_LadderPoint_') or name in ('GC_BattleTimePercent',):
        return 0
    if name == 'GC_MQuestClear':
        return int(city_cleared(p, 4))
    m = re.fullmatch(r'GC_(Mo|Co|Cr|Or)QuestClear', name)
    if m:
        return int(city_cleared(p, ('Mo', 'Co', 'Cr', 'Or').index(m[1]) + 1))
    if name == 'GC_OMD':
        return int(faction(p) == 'OMD')
    if name == 'GC_TEAMROO':
        return int(faction(p) == 'ROO')
    if name.startswith('GC_LicenseGain_'):
        return int(any(int(x) in st['held'] for x in name[15:].split('_') if x.isdigit()))
    m = re.fullmatch(r'GC_(Upgrade|Enchant|Create)(This|Last)Month', name)
    if m:
        return st['gc'].get(month_key(m[1], None if m[2] == 'This' else last_month()), 0)
    return st['gc'].get(name, 0)


async def _add(cid, cname, mode, n):
    db = context.db
    await db.execute(ADD_SQL, (n, db.server_id, cid, mode, db.server_id, cid, cname, mode, n))


async def count(session, name, n=1, p=None):
    """Count a condition (names without "GC_" are taken as given) for the session's player, then check the licenses."""
    p = p or (session.state.get('player') if session else None)
    if not p or n <= 0:
        return
    st = state(p) or await load(p)
    if not name.startswith(('GC_', 'GCM_')):
        name = 'GC_' + name
    st['gc'][name] = st['gc'].get(name, 0) + n
    st['conds_version'] += 1
    await _add(p.char.cid, p.char.name, name, n)
    if session:
        await check(session, p)


async def count_many(session, names, p=None):
    for name in names:
        await count(session, name, p=p)


async def count_monthly(session, kind, n=1):
    await count(session, month_key(kind), n)


async def count_cid(cid, name, n=1):
    """A count for a character who may be offline (an auction sold): online through its session."""
    from .social import online
    s = online(cid)
    if s:
        return await count(s, name, n)
    r = await context.db.row(CNAME_SQL, (context.db.server_id, cid))
    if r:
        await _add(cid, r[0].strip(), name if name.startswith('GC_') else 'GC_' + name, n)


def city_of_post(post):
    return POST_CITY.get((post or '')[:8])


def city_of_track(map_id):
    """The city of a battle zone map (PVPTrackInfo.xlt "city" of the row with that Id)."""
    global _track_city
    if _track_city is None:
        import os
        from ..data import read_xlt
        _track_city = {}
        try:
            rows = read_xlt(os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
            c_id = rows[2].index('Id')
            for r in rows[3:]:
                if len(r) > c_id and r[c_id].strip().isdigit() and r[2].strip():
                    city = TRACK_CITY.get(r[2].strip().lower())
                    if city:
                        _track_city.setdefault(int(r[c_id]), city)
        except (OSError, ValueError):
            pass
    return _track_city.get(map_id)


_track_city = None


def sticky_state(p):
    """Conditions kept once seen: the DC badges held."""
    st = state(p)
    out = []
    for it in p.items:
        m = re.fullmatch(r'i_n_dcbadge_(\d\d)', it.item_id or '')
        if m and not st['gc'].get(f'GC_DCbadge_{m[1]}'):
            out.append(f'GC_DCbadge_{m[1]}')
    return out


async def check(session, p, notify=True):
    """Gain every supported license whose conditions are all met -> the ids gained. Not in the tutorial gate: a new
    character holding Rookie at login skipped Director Green's tutorial (user, 2026-10-15); it gets it in the city."""
    st = state(p) or await load(p)
    from .position import IN_CITY
    if p.char.pos_state < IN_CITY:
        return []
    for name in sticky_state(p):
        st['gc'][name] = 1
        await _add(p.char.cid, p.char.name, name, 1)
    t, gained = tables(), []
    changed = True
    while changed:                           # a license gained can complete another (GC_LicenseGain_*)
        changed = False
        for lid, lic in t.licenses.items():
            if not lic['support'] or lid in st['held'] or not lic['conds']:
                continue
            met = [value(p, n) >= target for n, target in lic['conds']]
            if (any(met) if lic['any'] else all(met)):
                st['held'][lid] = True
                await _add(p.char.cid, p.char.name, f'LIC_{lid}', 1)
                gained.append(lid)
                changed = True
    if gained:
        st['version'] += 1
        st['conds_version'] += 1
        session.log.note(f'licenses gained: {[(i, t.licenses[i]["name"]) for i in gained]}')
        if notify:
            for lid in gained:
                send(session, Frame(0x331, struct.pack('<HH', lid, 1)))
            send(session, info_frame(p))
    return gained


def info_frame(p, version=None):
    st = state(p)
    held = sorted(st['held'])
    return Frame(0x32c, struct.pack('<II', st['version'], len(held)) + b''.join(struct.pack('<HHH', i, 0, 0) for i in held))


def cond_frame(p):
    st, t = state(p), tables()
    entries = [(i, value(p, n)) for i, n in sorted(t.gc_name.items())]
    return Frame(0x32e, struct.pack('<IHHI', st['conds_version'], len(entries), 0, len(entries))
                 + b''.join(struct.pack('<HI', i, max(0, min(v, 0xffffffff))) for i, v in entries))


def slots_frame(p, kind=0x330):
    return Frame(kind, struct.pack(f'<{SLOTS}H', *mounted(state(p))))


async def on_login(session, p):
    """At login: the state, the licenses gained meanwhile (no notice), the lists and the mounted ones."""
    await load(p)
    await check(session, p, notify=False)
    send(session, info_frame(p), cond_frame(p), slots_frame(p))
    await pay_monthly(session, p)


@on(SVC, C2S, 0x32b)
async def get_license_info(session, frame):
    p = session.state.get('player')
    if not p:
        return
    if state(p) is None:
        await load(p)
    await check(session, p)
    send(session, info_frame(p))


@on(SVC, C2S, 0x32d)
async def get_license_cond(session, frame):
    p = session.state.get('player')
    if not p:
        return
    if state(p) is None:
        await load(p)
    await check(session, p)
    send(session, cond_frame(p))
    await pay_monthly(session, p)               # (0x32d comes every ~2 minutes: a reset day passing while online)


@on(SVC, C2S, 0x32f)
async def select_license(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 2 * SLOTS:
        return
    st = state(p) or await load(p)
    want = list(struct.unpack_from(f'<{SLOTS}H', frame.payload))
    slots = [i if i in st['held'] and i not in want[:k] else 0 for k, i in enumerate(want)]
    st['slots'] = slots
    db = context.db
    await db.execute(SLOTS_SQL, (*slots, db.server_id, p.char.cid, db.server_id, p.char.cid, p.char.name, *slots))
    session.log.note(f'licenses mounted: {slots}' + (f' (asked {want})' if slots != want else ''))
    send(session, slots_frame(p))
    out = nameplate_frame(session)
    for s in list(sessions.values()):           # everyone, the player too: the nameplate above each car
        if s.state.get('player'):
            send(s, out)


def nameplate_frame(session):
    """0x326 LicenseInfoRes (u16 serial, the 3 mounted ids): the licenses shown on that car's nameplate (client
    0x50e770: kept per serial, linked to the car [car + 0x41e8]). Sent to everyone on a change, to the player itself
    when it enters an area (login.join_area), and with the player info others ask for (misc.player_info_req)."""
    st = state(session.state['player'])
    slots = mounted(st)
    return Frame(0x326, struct.pack('<H', session.state.get('serial', 0) & 0xffff) + struct.pack(f'<{SLOTS}H', *slots))


def effects(p):
    """{ME name: summed value} of the mounted licenses."""
    st = state(p)
    out = {}
    if not st:
        return out
    t = tables()
    for lid in mounted(st):
        for name, v in (t.licenses.get(lid) or {}).get('effects', ()):
            out[name] = out.get(name, 0) + v
    return out


def bonus(p, activity=None, city=None):
    """(exp %, Mito %) of the mounted licenses for an activity: 'battle_team', 'battle_personal', 'delivery', 'chase',
    'patrol', 'undercity' or None (anything else); city for the track / delivery ones."""
    e = effects(p)
    if not e:
        return 0, 0
    both = e.get('ME_AllExpMito', 0) + e.get('ME_MittronGuardian', 0)
    exp = money = both
    if activity in ('battle_team', 'battle_personal'):
        money += e.get('ME_BattleTeamMito' if activity == 'battle_team' else 'ME_BattlePersonalMito', 0)
        if city in CITY_SUFFIX:
            exp += e.get(f'ME_{CITY_SUFFIX[city][0]}TrackExp', 0)
    elif activity == 'delivery':
        exp += e.get('ME_QuickExpMito', 0)
        money += e.get('ME_QuickExpMito', 0)
        if city in CITY_SUFFIX:
            exp += e.get(f'ME_Quick{CITY_SUFFIX[city][0]}Exp', 0)
            money += e.get(f'ME_Quick{CITY_SUFFIX[city][0]}Mito', 0)
    elif activity in ('chase', 'patrol', 'undercity'):
        key = {'chase': 'ME_ChasingExpMito', 'patrol': 'ME_AllPatrolExpMito', 'undercity': 'ME_UnderExpMito'}[activity]
        exp += e.get(key, 0)
        money += e.get(key, 0)
    st = state(p)
    if st and st.get('camo_until', 0) > time.time():
        money += e.get('ME_CarTransExp', 0)
    return exp, money


def fee_discount(p, kind):
    """% off a fee: 'auction' or 'enhance'."""
    e = effects(p)
    return min(100, e.get('ME_FeeDis', 0) + e.get('ME_AuctionFeeDis' if kind == 'auction' else 'ME_EnhanceFeeDis', 0))


def drop_bonus(p):
    """% more parts drop chance."""
    e = effects(p)
    return e.get('ME_PartDropRate', 0) + e.get('ME_MittronGuardian', 0)


@on(SVC, C2S, 0x29a)
async def license_status(session, frame):
    """Another player's licenses (by serial) for the license window."""
    if len(frame.payload) < 8:
        return
    act, serial = struct.unpack_from('<II', frame.payload)
    target = next((s for s in list(sessions.values()) if s.state.get('player') and s.state.get('serial') == serial), None)
    if not target:
        return
    p = target.state['player']
    st = state(p) or await load(p)
    from .records import wstr
    held = sorted(st['held'])
    send(session, Frame(0x29b, struct.pack('<III', act, serial, len(held)) + wstr(p.char.name, 42)
                        + struct.pack(f'<{SLOTS}H', *mounted(st)) + b''.join(struct.pack('<HHH', i, 0, 0) for i in held)))
    t = tables()
    entries = [(i, value(p, n)) for i, n in sorted(t.gc_name.items())]
    send(session, Frame(0x32a, struct.pack('<IIHHI', act, serial, len(entries), 0, len(entries))
                        + b''.join(struct.pack('<HI', i, max(0, min(v, 0xffffffff))) for i, v in entries)))


RESET_DAY = 1                            # = handlers/game.py NEW_FLAGS 'Etc.NewLicenseSystemnDay'
PAY_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), POINT=%s, NEXP=%s WHERE SERVERID=%s AND CID=%s AND MODEID='LICPAY';
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME, NEXP,
    GAMEMONEY, BESTCNT, RETIRECNT) VALUES (%s,%s,%s,'LICPAY',GetDate(),GetDate(),0,0,%s,0,%s,0,0,0)"""


def pay_period(today=None):
    """The reward month now: YYYYMM of the last reset day reached."""
    d = today or datetime.date.today()
    if d.day < RESET_DAY:
        d = d.replace(day=1) - datetime.timedelta(days=1)
    return d.year * 100 + d.month


def monthly_amount(p):
    st, t = state(p), tables()
    return sum(t.licenses[i]['reward'] for i in (st['held'] if st else ()) if i in t.licenses and t.licenses[i]['support'])


async def pay_monthly(session, p):
    """The License Ownership Reward Money of this month, once."""
    from .items import add_money
    st = state(p)
    if st is None:
        return
    db, c = context.db, p.char
    from .position import DRIVER_DOME
    if c.pos_state != DRIVER_DOME:              # paid in the Driver Dome only (user, 2026-10-15): not in the tutorial
        return                                  # gate, not in the city; the client reports the Dome with 0xa2 state 3
    period = pay_period()
    if 'paid' not in st:
        r = await db.row("SELECT POINT FROM SKID_PLAYMODE_TB WHERE SERVERID=%s AND CID=%s AND MODEID='LICPAY'",
                         (db.server_id, c.cid))
        st['paid'] = int(r[0] or 0) if r else 0
    if st['paid'] >= period:
        return
    amount = monthly_amount(p)
    st['paid'] = period
    await db.execute(PAY_SQL, (period, amount, db.server_id, c.cid, db.server_id, c.cid, c.name, period, amount))
    if amount <= 0 or not await add_money(c, amount):
        return
    t = tables()
    names = ', '.join(t.licenses[i]['name'] for i in sorted(st['held']) if i in t.licenses and t.licenses[i]['support'])
    session.log.note(f'license reward {period}: {amount} Mito ({names})')
    session.state['license_pay'] = (amount, names)
    if session.state.get('in_game'):            # else when the client asks for its messages (mail.get_mail, 0x86)
        tell_payment(session)


def tell_payment(session):
    """The paid reward to the client, once it is in the game (a notice sent during the login was lost: user): 0x8a
    MoneyMessage (kind 1, the amount, the new total; the money shown) and a kind-500 message with no Mito in it (only
    its text pop-up; with the Mito the client would add it a second time)."""
    from .mail import content
    pay = session.state.pop('license_pay', None)
    p = session.state.get('player')
    if not pay or not p:
        return
    amount, names = pay
    c = p.char
    send(session, Frame(0x8a, struct.pack('<iiqq', 1, 1, amount, c.mito) + b'\0\0'))
    send(session, content(0, 0, c.cid, 'License', 500, 'R', 'License Ownership Reward Money',
                          f'License Ownership Reward Money: {amount:,} Mito ({names}).', 0, '', datetime.datetime.utcnow()))
