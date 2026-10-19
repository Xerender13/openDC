"""Native services: the emulator is the server (no 2008 ZoneServer behind them).

Same architecture as the original server (separate auth / lobby / game / area / barea services
on their own ports, the same SQL Server database and tables, serverlist.txt), but the messages
are the 2011 client's and the tables are read in the 2011 client's own formats (.xlt / .tdf as
the client has them, see data.py), not converted to the 2008 server's columns.

A service is native when its ZoneServer port in emulator.ini is 0; its handlers are the modules
here, registered like the proxy handlers (dcemu.handlers.on). Shared state (the database,
the server list) lives in `context`, set up by __main__.

Times: the 2008 server's clock runs an hour behind UTC (its time_t values, e.g. the lobby's
character dates and GetDateTime, are UTC - 3600, while its broken-down dates are UTC; the
database stores UTC). While game/area still run on the 2008 server the native services use the
same clock: CLOCK_SHIFT.
"""
import calendar
import hashlib
import hmac
import os
import secrets
import time

CLOCK_SHIFT = -3600


def now():
    """The server clock as a time_t."""
    return int(time.time()) + CLOCK_SHIFT


_tick0 = time.monotonic()


def tick():
    """The server tick (GetSystemTick): milliseconds since the emulator started, as a u32."""
    return int((time.monotonic() - _tick0) * 1000) & 0xffffffff


def time_t(dt):
    """A database datetime (UTC) -> time_t on the server clock; None -> 0."""
    return calendar.timegm(dt.timetuple()) + CLOCK_SHIFT if dt else 0


SECRET_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.ticket_secret')


def _secret():
    try:
        return open(SECRET_FILE, 'rb').read()
    except OSError:
        s = secrets.token_bytes(32)
        with open(SECRET_FILE, 'wb') as f:
            f.write(s)
        return s


def ticket_for(member):
    """The login ticket (auth -> lobby) of an account: derived from the account and a secret kept in
    Emulator/.ticket_secret, so it stays valid when the emulator restarts (the client keeps its
    ticket and checks in to the lobby again without logging in)."""
    d = hmac.new(context.secret, member.lower().encode('utf-8'), hashlib.sha256).digest()
    return (int.from_bytes(d[:4], 'little') & 0x7fffffff) | 1


class Context:
    client_version = 2011   # server-wide wire build, independent of nation
    max_level_2016 = 100    # 2016 advertised cap and progression cap; 2011 keeps its existing rules
    db = None            # native.db.Database
    data = None          # native.data.Tables
    server_list = []     # native.auth.ServerEntry
    secret = _secret()   # for ticket_for
    ranking_port = 0
    public_host = ''         # emulator.ini [native] public_host / DCEMU_PUBLIC_HOST: sent for serverlist.txt's 127.x
                             # addresses instead of the address the client reached (a container's own address)
    start_time = now()   # sent in LoadCharAck (m_ServerStartTime)
    delete_wait_days = None  # emulator.ini [native] delete_wait_days; None = what the client asks
    race_traffic = None      # native.race.RaceTraffic, when barea is native
    city_traffic = None      # native.city_traffic.CityTraffic: the city's traffic cars ([traffic] city = native)
    sections = {}            # battle zone: PvP channel id -> (name, lowest car grade, highest, exp multiplier)
    sections_eu = {}         # the same for EU players (emulator.ini eu.section.<channel>), where set
    practice_alone = True    # battle zone: a room with one member starts a practice run, not a race
    realmatch = 'always'     # Real Match open hours: always, schedule (realmatchtable.txt) or off
    realmatch_minutes = 60   # schedule: how long each opening lasts
    realmatch_car = (50, 9)  # the car everyone drives in a Real Match: car type, grade; None = own cars
    realmatch_effect = 1     # Etc.RealMatchEffect while a player is in a Real Match room (0 = never)
    laptime_level_limit = False  # Lap Time: laptimeinfo.txt's level limit per arena
    sticker_upload = 'all'   # who may upload stickers: all or gm
    sticker_daily_limit = 0  # stickers a character may upload per day (0 = no limit)
    drink_exp = 30           # EXP drink: % more exp from play (2008 CalcExperience: x 0.3; item text: 30%)
    drink_mito = 50          # MITO drink: % more Mito from play (item text: 50%)
    option_parts = False     # option parts can be equipped (Main.OptionItem; the official 2011 server: off)
    docking_parts = True     # docking parts: combining and docking (Main.DockingItem)
    mita500 = dict(enabled=False, bottles=10, regen_sec=300, buff_sec=1800, fee=500, lucky_rate=10)   # [mita500]
    enhancer_plus = 1.5      # [items] enhancer_plus: x success % with a Mittron Enhancer PLUS (gauge fill 2)
    enhancer_deluxe = 2.0    # [items] enhancer_deluxe: x success % with a DELUXE (gauge fill 4)
    vshop_hidden = frozenset()   # [vshop] hidden: drift shop rows (VShopItem UniqueId) not sold (tools/shop_hide.py)
    rename_days = 60         # [items] rename_days: days before a renamed character can be renamed again (kit text: 60)
    auto_register = True     # [auth] auto_register: logging in with an unknown ID creates that account
    mail_min_level = 1       # emulator.ini [mail] min_level: the lowest level that can send messages
    mail_fee = 0             # [mail] fee: Mito per message sent
    auction_days = 7         # emulator.ini [auction] days: how long a listing runs before it expires
    auction_min_level = 1    # [auction] min_level (client GlobalContent AuctionMinLevel: 1 in the US client)
    auction_item_fee = 7     # [auction] item_fee: % of the price taken at registration (Main.AuctionCommission)
    auction_cars = True      # [auction] cars: the car auction open (0x708, Main.AuctionCar)
    auction_car_fee = 10     # [auction] car_fee: % (2008 CarTaxReg 0.1)
    auction_drift = False    # [auction] drift_items: the drift item auction
    auction_drift_fee = 10   # [auction] drift_fee: % (Main.AuctionVSCommission)
    daymission_reset_hour = 0  # emulator.ini [daymission] reset_hour: the hour (local) a new mission day starts
    instant_city_minutes = 5    # emulator.ini [instant] city_offer_minutes: a City instant mission offered this often (0: off)
    # emulator.ini [partypatrol] (game/partypatrol.py): the party patrol's time rules (guesses: the wiki gives only the
    # 60 s start) and its solo test mode
    partypatrol = dict(start_seconds=60, bonus_posts=5, bonus_seconds=4, quick_max_seconds=20, quick_min_seconds=5,
                       quick_decay_seconds=3, quick_exp=10, grace_seconds=2, test=False, test_start_seconds=600)
    # emulator.ini [vchase] (game/vchase.py): Virtual HUV match rules (the wiki's; amounts are guesses) and the test mode
    vchase = dict(seconds_4=300, seconds_8=600, hits=3, catch_points=20, drain=5, traffic_points=3, traffic_heal=5,
                  win_rate=30, lose_rate=10, test=False)
    # emulator.ini [undercity] (game/undercity.py): the test mode (one player alone, with the /ucm .. chat commands)
    undercity = dict(test=False, phase=1, beta_class=4, enhancer='i_n_00003', enhancers=(1, 1, 2, 3, 3))
    # emulator.ini [cbattle] (game/channels.py): the channels and their crews' battles. main / semi: (max level, min car
    # grade, max car grade), 0 = no limit; semi by Semi-channel number (from 1); eu_*: the EU clients' rules
    cbattle = dict(channels=13, day=-1, hour=-1, open_minutes=10, battle_minutes=60, coupon=True, defence_reward=5000,
                   test=False, tax_hour=6, tax_major=10.0, tax_minor=(3.0, 4.0, 5.0), tax_semi=(1.0, 1.0, 1.5),
                   main=(0, 0, 0), semi={1: (40, 0, 0), 2: (60, 0, 0), 3: (70, 0, 0)},
                   eu_main=(0, 6, 0), eu_semi={1: (0, 1, 3), 2: (0, 1, 6)}, major_stakes=False, replays=200)
    # emulator.ini [championship] (game/championship.py): the GT Championship. Minutes as the client's content flags
    # (PreMatchTime, MatchWaitTime, MainMatchTime, FinalMatchTime); touring_a / touring_b: the Touring classes' speed
    # caps in km/h as the client's GlobalContent PvpGT_TouringA / B (shown in mph to US clients); schedule: (weekday
    # 0-6 or None for every day, hour, minute), local time; maps: the stages' tracks (PVPTrackInfo Id), prelim first;
    # rewards: (class, rank) -> (Mito, item id, count)
    championship = dict(enabled=True, schedule=[], pre=30, wait=3, main=8, final=10, min_players=8, min_players_ini=8,
                        touring_a=361, touring_b=341, maps=[0, 1, 2, 3, 4], map_flag=0x04,
                        rewards={(7, 1): (100000, '', 1), (7, 2): (50000, '', 1), (7, 3): (30000, '', 1),
                                 (8, 1): (200000, '', 1), (8, 2): (100000, '', 1), (8, 3): (50000, '', 1),
                                 (9, 1): (300000, '', 1), (9, 2): (150000, '', 1), (9, 3): (80000, '', 1),
                                 (10, 1): (500000, '', 1), (10, 2): (250000, '', 1), (10, 3): (100000, '', 1)})
    gotcha_enabled = True    # emulator.ini [gotcha] enabled: the Gotcha machine (main menu button)
    gotcha_season = 13       # [gotcha] season: the newest season offered (Etc.GotchaSeason; client GotchaViewSeason 13)
    gotcha_mito_price = 0    # [gotcha] mito_price / coin_price: 0 = the client's prices (gotcha.py)
    gotcha_coin_price = 0
    extra_flags = {}         # emulator.ini [flags]: content flags by 2011 name, sent at login
    rush_schedule = True     # [rush] schedule: the 2008 rushtimetable.txt starts rushes at its hours
    rush_always = False      # [rush] always: a zone with start_members players starts a rush (City.AlwaysRushTime)
    rush_start_members = 2   # [rush] start_members (City.RushTimeStartMember)
    rush_countdown = 60      # [rush] countdown: seconds from reaching start_members to the start (client text: 1 min)
    rush_test_health = 0     # [rush] test_health: every rush HUV's health (for testing; 0 = the client's table)


context = Context()
