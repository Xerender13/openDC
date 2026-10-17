"""A character in the game service: loaded from the database the way the 2008 server does it
(the SQL is the 2008 server's own, from ZoneServer.exe; field mapping from BS_GameDB::LoadCharInfo),
with the values the 2008 server derives from its tables taken from the 2011 tables instead.

Derived values (2008 server -> here):
  ExpInfo          NEXP, and the exp at this and the next level (LevelServer.tdf sums)
  PType            'A' if the account is in adminlist.txt (AdminTable::IsAdmin), else PTYPE
  Flags            0x4000000 if the battle tutorial was won (PLAYMODE 'BATTLETUTORIAL' WINCNT)
  QuickCnt         PLAYMODE 'ARBEIT' WINCNT
  car Mitron capacity / efficiency, base stats: VehicleUpgrade.xlt (car type, grade)
  item TableIdx    the 2011 item tables (data.Tables); ExpireTick = CTIME, or the server tick
                   (SKID_SERVER_TB.SERVERPTICK) when 0
Stats (XiStrStatInfo): based = the car grade's stats, equip = the parts on the current car (part
value + its random bonus) and the drift shop items on it (VShopItem Bonus columns), char = level / 2 each (Contents.ini Main.HalfLevelPoint, else level; 0 for EU players: nation rule level_points).
"""
from .. import context, time_t
from .records import Car, Character, Item, Stats, VisualItem

PAINT_CATEGORIES = {1, 32}
TEMP_UPGRADE = 38            # VisualItem category of the timed car upgrades i_d_u_11..18 (V2..V9, 7 days)


def upgrade_grade(table_idx):
    """The grade a car upgrade item gives: VShopItem Sub 8001 (CARREMODELING_R1R2) = V2 .. 8008 = V9."""
    try:
        return int(context.data.vshop.get(table_idx, {}).get('Sub', '0')) - 8000 + 1
    except ValueError:
        return 0
TINT_CATEGORY = 3

CHAR_SQL = """SELECT a.CID, a.CNAME, a.LASTDATE, a.AVATAR, a.NLevel, a.NExp, a.Gold, a.KM, a.TeamId, a.TeamRank,
    d.TeamName, d.TMarkId, a.PTYPE, a.LASTAREA, a.LASTPOSX, a.LASTPOSY, a.LASTPOSZ, a.LASTPOSW, a.LASTCITYID,
    a.LASTPOSSTATE, b.TRYCNT, b.WINCNT, b.POINT, c.TRYCNT, c.WINCNT, c.POINT, a.QUICKSLOT1, a.QUICKSLOT2,
    a.TeamJoinDate, a.TeamCloseDate, a.TeamLeaveDate, a.CURCAR, a.MEMBERID, q.WINCNT, i.WINCNT,
    a.HANCOININVEN, a.HANCOINGARAGE, a.GUILDTYPE, a.MILEAGE, a.PARTINVENIDX
  FROM SKID_CHARACTER_TB a
    LEFT OUTER JOIN SKID_PLAYMODE_TB b ON a.serverid=b.serverid AND a.CID=b.CID AND b.modeid='PVP'
    LEFT OUTER JOIN SKID_PLAYMODE_TB c ON a.serverid=c.serverid AND a.CID=c.CID AND c.modeid='TPVP'
    LEFT OUTER JOIN SKID_PLAYMODE_TB q ON a.serverid=q.serverid AND a.CID=q.CID AND q.modeid='ARBEIT'
    LEFT OUTER JOIN SKID_PLAYMODE_TB i ON a.serverid=i.serverid AND a.CID=i.CID AND i.modeid='BATTLETUTORIAL'
    LEFT OUTER JOIN SKID_TEAM_TB d ON a.serverid=d.serverid AND a.TEAMID=d.TID
  WHERE a.serverid=%s AND a.UCNAME=UPPER(%s) AND a.state='P'"""

CARS_SQL = ("SELECT CARID, CARTYPE, COLOR, NUPGRADE, AUCTIONCNT, MITRON, KM, SLOT FROM SKID_CAR_TB"
            " WHERE serverid=%s AND cid=%s ORDER BY lastdate DESC")
ITEMS_SQL = ("SELECT GID, INVENIDX, ITEMID, CARID, STACKNUM, NRANDOM, STATE, NUPGRADE, BELONGING, ASSIST_A, ASSIST_B,"
             " BOX, CTIME, CDATE FROM SKID_ITEM_TB WHERE SERVERID=%s AND CID=%s ORDER BY INVENIDX")
VSITEMS_SQL = ("SELECT GID, ITEMID, INVENIDX, CARID, STATE, ITEM_DATA, PERIOD, CTIME, UTIME FROM SKID_VSITEM_TB"
               " WHERE SERVERID=%s AND CID=%s ORDER BY INVENIDX")
QUESTS_SQL = "SELECT QUESTID, STATE, PLACEIDX, FAILNUM FROM SKID_QUEST_TB WHERE SERVERID=%s AND CID=%s"
COUPON_VARS_SQL = ("SELECT PVPBATTLE, QUICKSERVICE, CHASING, COMBO, DRIVETIME, DRIFT, ARTDRIVE, JUMP, REVDRIVE,"
                   " UNDERCITY FROM SKID_COUPONVALUE_TB WHERE SERVERID=%s AND CID=%s")
TICK_SQL = "SELECT SERVERPTICK FROM SKID_SERVER_TB WHERE SERVERID=%s"
BATTLE_TUTORIAL_DONE = 0x4000000


def _i(v):
    return int(v) if v is not None else 0


def _f(v):
    return float(v) if v is not None else 0.0


class Player:
    def __init__(self, char, items, vsitems, quests, coupon_vars, tick):
        self.char = char
        self._tick = tick           # SKID_SERVER_TB.SERVERPTICK at login (tick: the live value)
        self.items = items
        self.vsitems = vsitems
        self.quests = quests
        self.coupon_vars = coupon_vars
        self.buffs = {}             # stat index -> (points, monotonic end): timed point-up items
        self.nation = 1             # the client's nation (native/nation.py), set at the game login

    @property
    def tick(self):
        from .setparts import tick_now
        return tick_now() or self._tick

    def apply_paints(self):
        """Each car's drawn colour from the paint on it (VisualItem category 1 colours, 32 glossy colours
        and the RGB paints "Paint S15" etc.). 2011 client, car model
        SetColor 0x4690b0 / 0x467570 (with Etc.ColorSetReform): 0x8X RRGGBB is an RGB colour - X = 2 a
        second layer, else the base colour (the client turns palette colours into 0x83RRGGBB itself);
        any other value is a palette index (dealership colours, e.g. 0x08000002). Window tints (category 3)
        go to the car record's 2011 field @0x24 as 0x82RRGGBB (the second layer = the glass). The paint item's text
        is the colour as a decimal 0xRRGGBB (the colour window), or RRRGGGBBB after 10 spaces (older)."""
        visuals = context.data.visuals
        for v in self.vsitems:                  # equippable PassiveAssist items act only on the car being driven
            v.on_current_car = v.state == 1 and v.car_id == self.char.cur_car
        for car in self.char.cars:
            car.paint = car.tint = car.boost_grade = 0
        from .items import active
        for v in self.vsitems:                  # timed car upgrades (category 38, "V4 car upgrade (7days)") on a car
            vis = visuals.get(v.table_idx)
            car = next((c for c in self.char.cars if c.car_id == v.car_id), None)
            if car and v.state == 1 and vis and vis.category == TEMP_UPGRADE and active(v):
                car.boost_grade = max(car.boost_grade, upgrade_grade(v.table_idx))
        for v in self.vsitems:
            vis = visuals.get(v.table_idx)
            car = next((c for c in self.char.cars if c.car_id == v.car_id), None)
            text = (v.data or '').strip()
            if not car or v.state != 1 or not vis or not text.isdigit() or \
                    vis.category not in PAINT_CATEGORIES and vis.category != TINT_CATEGORY:
                continue
            rgb = int(text)
            if len(text) == 9 and rgb > 0xffffff:          # RRRGGGBBB
                rgb = (int(text[:3]) & 0xff) << 16 | (int(text[3:6]) & 0xff) << 8 | (int(text[6:]) & 0xff)
            if vis.category == TINT_CATEGORY:
                car.tint = 0x82000000 | (rgb & 0xffffff)
            else:
                car.paint = 0x83000000 | (rgb & 0xffffff)

    @property
    def car(self):
        return next((c for c in self.char.cars if c.car_id == self.char.cur_car), None)

    def stats(self):
        t = context.data
        s = Stats()
        car = self.car
        if car:
            s.based = t.car_stats(car.car_type, car.shown_grade())     # a timed upgrade item counts
            equip = [0, 0, 0, 0]
            for it in self.items:
                p = t.part_stat(it.item_id) if it.car_id == car.car_id else None
                if p:
                    from .setparts import expired, expired_value
                    if expired(self, it):           # a run-out set part: its expired form, no enhancement
                        equip[p[0]] += expired_value(it) + it.random
                        continue
                    equip[p[0]] += p[1] + it.random
                    from .convert import assist_bonus
                    for k, points in assist_bonus(it):      # converted options (convert.py)
                        equip[k] += points
                    if it.upgrade > 0:              # Mittron Enhancer level (upgrade.py; < 0 = broken)
                        from .upgrade import bonus
                        equip[p[0]] += bonus(t.item_info(it.table_idx).grade, it.upgrade)
            from .setparts import set_bonus
            for k, v in enumerate(set_bonus(self, car.car_id)):
                equip[k] += v
            from .docking import dock_bonus
            for k, v in enumerate(dock_bonus(self, car.car_id)):
                equip[k] += v
            from .items import active
            from .aero import mk2_points
            for v in self.vsitems:              # drift shop items on the car (not run out): VShopItem Bonus columns
                row = t.vshop.get(v.table_idx) if v.car_id == car.car_id and v.state == 1 and active(v) else None
                for k, name in enumerate(('Bonus Speed', 'Bonus Crash', 'Bonus Accel', 'Bonus Boost')):
                    if row and (row.get(name) or '0').lstrip('-').isdigit():
                        equip[k] += int(row[name])
                if row:                         # Aero kit Mk.2: the points the player distributed (aero.py)
                    for k, n in enumerate(mk2_points(v)):
                        equip[k] += n
            s.equip = tuple(equip)
        from .. import nation
        points = self.char.level // 2 if t.contents.get('Main.HalfLevelPoint') else self.char.level
        s.char = (points if nation.rule(self, 'level_points') else 0,) * 4
        import time
        s.item_use = tuple(v if end > time.monotonic() else 0
                           for v, end in (self.buffs.get(k, (0, 0)) for k in range(4)))
        return s


async def load(name, member=None):
    """-> Player, or None if there is no such character (of this account, if member is given)."""
    db, t = context.db, context.data
    r = await db.row(CHAR_SQL, (db.server_id, name))
    if not r or (member and (r[32] or '').lower() != member.lower()):
        return None
    (cid, cname, last, avatar, level, exp, gold, km, team, team_rank, team_name, mark, ptype, area, x, y, z, w, city,
     pos_state, pvp_n, pvp_w, pvp_p, tpvp_n, tpvp_w, tpvp_p, qs1, qs2, tjoin, tclose, tleave, cur_car, member_id,
     arbeit_wins, tutorial_wins, hc_inven, hc_garage, guild, mileage, part_inven) = r
    level = _i(level) or 1
    base, nxt = t.exp_bounds(level)
    from .quickslot import quick_slots_of
    char = Character(
        cid=int(cid), name=cname, member=member_id, last_date=time_t(last), avatar=_i(avatar), level=level,
        exp=_i(exp), exp_next=nxt, exp_base=base, mito=_i(gold), team_id=_i(team) if team is not None else -1,
        team_mark=_i(mark), team_name=team_name or '', team_rank=_i(team_rank) if team_rank is not None else -1,
        ptype='A' if (member_id or '').lower() in t.admins else (ptype or 'N'),
        pvp=(_i(pvp_n), _i(pvp_w), _i(pvp_p)), tpvp=(_i(tpvp_n), _i(tpvp_w), _i(tpvp_p)),
        quick_cnt=_i(arbeit_wins), km=_f(km), pos=(_f(x), _f(y), _f(z), _f(w)), last_area=_i(area), city=_i(city),
        pos_state=_i(pos_state), cur_car=_i(cur_car), quick_slots=quick_slots_of(qs1, qs2), team_dates=(time_t(tjoin), time_t(tclose), time_t(tleave)),
        hancoin_inven=_i(hc_inven), hancoin_garage=_i(hc_garage),
        flags=BATTLE_TUTORIAL_DONE if _i(tutorial_wins) else 0, guild=_i(guild), mileage=_i(mileage),
        part_inven_idx=_i(part_inven))
    for c in await db.rows(CARS_SQL, (db.server_id, cid)):
        car = Car(*(_i(v) for v in c[:5]), mitron=_f(c[5]), km=_f(c[6]), slot=_i(c[7]))
        if not car.color:                       # gift box cars of the first version had no colour: the client then kept
            from .cars import DEFAULT_COLOR     # another car's paint on the shared model (user, 2026-10-14)
            car.color = DEFAULT_COLOR
            await db.execute("UPDATE SKID_CAR_TB SET COLOR=%s WHERE SERVERID=%s AND CID=%s AND CARID=%s",
                             (car.color, db.server_id, cid, car.car_id))
        u = t.upgrade.get((car.car_type, car.grade))
        if u:
            car.capacity, car.efficiency = float(u['capacity']), float(u['efficiency'])
        char.cars.append(car)
    from .setparts import current_tick, start_expiry
    tick = await current_tick()                 # SERVERPTICK in hours, advanced (setparts.py)
    items = []
    for gid, inven, item_id, car_id, stack, rnd, state, upg, bel, aa, ab, box, ctime, cdate in await db.rows(ITEMS_SQL, (db.server_id, cid)):
        it = Item(int(gid), _i(inven), item_id, _i(car_id), _i(stack), _i(rnd), _i(state), _i(upg), _i(bel),
                  aa or '', ab or '', _i(box), _i(ctime))
        it.cdate = cdate
        it.table_idx = t.item_index.get(item_id, -1)
        it.expire_tick = it.ctime or tick
        items.append(it)
    vsitems = []
    for gid, item_id, inven, car_id, state, data, period, ctime, utime in await db.rows(VSITEMS_SQL, (db.server_id, cid)):
        v = VisualItem(int(gid), item_id, _i(inven), _i(car_id), _i(state), data or '', _i(period), _i(ctime), _i(utime))
        v.table_idx = t.visual_index.get(item_id, 0)
        vsitems.append(v)
    # only QuestClient quests: the Mother quests (mq_* / sq_*, mothers.py) share the table; as row -1 they came first
    # in the quest list and the client showed the Rookie missions again (user, 2026-10-16)
    quests = sorted((t.quest_index[q], _i(st), _i(place), _i(fail))
                    for q, st, place, fail in await db.rows(QUESTS_SQL, (db.server_id, cid)) if q in t.quest_index)
    cv = await db.row(COUPON_VARS_SQL, (db.server_id, cid))
    coupon_vars = tuple(_f(v) for v in cv) if cv else (0.0,) * 10
    p = Player(char, items, vsitems, quests, coupon_vars, tick)
    from .. import nation
    p.nation = nation.of_member(char.member)    # the game login sets the client's own (login.load_char)
    for it in items:                            # set parts without an expiry yet
        await start_expiry(p, it)
    from .items import fix_shared_slots
    for it in await fix_shared_slots(p):
        print(f'{char.name}: {it.item_id} moved out of a shared slot -> car {it.car_id} slot {it.state >> 16}', flush=True)
    p.apply_paints()
    return p
