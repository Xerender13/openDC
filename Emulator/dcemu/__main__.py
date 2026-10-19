"""Drift City 2011 US emulator (stage 1: a logging, rewriting proxy in front of the 2008 server).

usage: python3 -m dcemu [-c emulator.ini] [-q]
"""
import argparse
import asyncio
import configparser
import os

from . import handlers
from .msglog import MsgLog
from .protocol import SERVICES
from .proxy import Service

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    cp.read_dict({'emulator': {'listen': '0.0.0.0', 'upstream': '127.0.0.1', 'log_dir': 'logs', 'control_port': '11099'},
                  'database': {'host': '127.0.0.1', 'port': '14330', 'user': 'sa', 'password': 'z0ne!server',
                               'name': 'SKDBTW', 'server_id': '100'},
                  'native': {'server_list': 'server_data/serverlist.txt', 'data': 'server_data',
                             'server_data': 'server_data/tables', 'admin_list': 'server_data/adminlist.txt',
                             'race_traffic_engine': 'dcemu/native/tw_traffic.py',
                             'race_traffic_data': 'server_data/race'},
                  'services': {k: ' '.join(map(str, v)) for k, v in SERVICES.items()}})
    if os.path.exists(path):
        cp.read(path, encoding='utf-8-sig')     # -sig: Windows Notepad may save a BOM
    # the database address from the environment wins (docker-compose.yml: the emulator container reaches the
    # database as db:1433, not 127.0.0.1:14330)
    for key in ('host', 'port', 'user', 'password', 'name'):
        value = os.environ.get('DCEMU_DB_' + key.upper())
        if value:
            cp['database'][key] = value
    return cp


def native_setup(cp):
    """Shared state of the native services (database, tables, server list), if any is native."""
    if not any(spec.split()[1] == '0' for _, spec in cp['services'].items()):
        return
    from .native import context
    from .native.auth import load_server_list
    from .native.data import Tables
    from .native.db import Database
    d, n = cp['database'], cp['native']
    context.db = Database(d['host'], int(d['port']), d['user'], d['password'], d['name'], int(d['server_id']))
    context.data = Tables(os.path.join(HERE, n['data']), os.path.join(HERE, n['server_data']),
                          os.path.join(HERE, n['admin_list']))
    context.server_list = load_server_list(os.path.join(HERE, n['server_list']))
    from .handlers.game import FLAGS_2011_TABLE
    context.extra_flags = {}
    if cp.has_section('flags'):
        for key, value in cp['flags'].items():
            name = next((n for n in FLAGS_2011_TABLE if n.lower() == key.lower()), None)
            if name:
                context.extra_flags[name] = int(value)
            else:
                print(f'emulator.ini [flags]: unknown content flag {key}', flush=True)
    if cp.has_section('items'):
        context.drink_exp = int(cp['items'].get('drink_exp', context.drink_exp))
        context.drink_mito = int(cp['items'].get('drink_mito', context.drink_mito))
        context.option_parts = cp['items'].get('option_parts', '0').strip() == '1'
        context.docking_parts = cp['items'].get('docking_parts', '1').strip() == '1'
        context.rename_days = int(cp['items'].get('rename_days', context.rename_days) or 0)
        context.enhancer_plus = float(cp['items'].get('enhancer_plus', context.enhancer_plus) or 1)
        context.enhancer_deluxe = float(cp['items'].get('enhancer_deluxe', context.enhancer_deluxe) or 1)
    if cp.has_section('vshop'):
        from .native.game.vshop import row_changes
        context.vshop_hidden, changes = row_changes(cp['vshop'])
        for uid, cols in changes.items():
            if uid in context.data.vshop:
                context.data.vshop[uid].update(cols)
    if cp.has_section('auth'):
        context.auto_register = cp['auth'].get('auto_register', '1').strip() not in ('0', 'no', 'off')
    from .native import nation
    nation.configure(cp['nation'] if cp.has_section('nation') else {})
    if cp.has_section('mail'):
        context.mail_min_level = int(cp['mail'].get('min_level', context.mail_min_level))
        context.mail_fee = int(cp['mail'].get('fee', context.mail_fee))
    if cp.has_section('auction'):
        a = cp['auction']
        context.auction_days = int(a.get('days', context.auction_days))
        context.auction_min_level = int(a.get('min_level', context.auction_min_level))
        context.auction_item_fee = int(a.get('item_fee', context.auction_item_fee))
        context.auction_cars = a.get('cars', '1').strip() == '1'
        context.auction_car_fee = int(a.get('car_fee', context.auction_car_fee))
        context.auction_drift = a.get('drift_items', '0').strip() == '1'
        context.auction_drift_fee = int(a.get('drift_fee', context.auction_drift_fee))
    if cp.has_section('daymission'):
        context.daymission_reset_hour = int(cp['daymission'].get('reset_hour', '0') or 0) % 24
    if cp.has_section('instant'):
        context.instant_city_minutes = int(cp['instant'].get('city_offer_minutes', '5') or 0)
    if cp.has_section('partypatrol'):
        pp = cp['partypatrol']
        for k, v in list(context.partypatrol.items()):
            raw = pp.get(k, '').strip()
            if raw:
                context.partypatrol[k] = raw not in ('0', 'no', 'off') if isinstance(v, bool) else int(float(raw))
    if cp.has_section('vchase'):
        vc = cp['vchase']
        for k, v in list(context.vchase.items()):
            raw = vc.get(k, '').strip()
            if raw:
                context.vchase[k] = raw not in ('0', 'no', 'off') if isinstance(v, bool) else float(raw)
    if cp.has_section('undercity'):
        uc = cp['undercity']
        context.undercity['test'] = uc.get('test', '0').strip() not in ('0', 'no', 'off', '')
        phase = uc.get('test_phase', '1').strip()
        context.undercity['phase'] = int(phase) if phase in ('1', '2', '3', '4') else 1
        context.undercity['beta_class'] = int(uc.get('beta_class', '4').strip() or 4)
        context.undercity['enhancer'] = uc.get('enhancer', 'i_n_00003').strip() or 'i_n_00003'
        counts = [int(x) for x in uc.get('enhancers', '1, 1, 2, 3, 3').replace(',', ' ').split() if x.isdigit()]
        context.undercity['enhancers'] = tuple(counts) or (1, 1, 2, 3, 3)
    if cp.has_section('cbattle'):
        cb = cp['cbattle']
        c = context.cbattle
        nums = lambda v: [float(x) for x in v.replace(',', ' ').split()]
        for k in ('channels', 'day', 'hour', 'open_minutes', 'battle_minutes', 'defence_reward', 'tax_hour', 'replays'):
            if cb.get(k, '').strip():
                c[k] = int(cb[k])
        for k in ('coupon', 'test', 'major_stakes'):
            if cb.get(k, '').strip():
                c[k] = cb[k].strip() not in ('0', 'no', 'off')
        if cb.get('tax_major', '').strip():
            c['tax_major'] = float(cb['tax_major'])
        for k in ('tax_minor', 'tax_semi'):
            if cb.get(k, '').strip():
                c[k] = tuple(nums(cb[k]))
        for g in ('', 'eu.'):
            key = g.replace('.', '_')
            if cb.get(g + 'main', '').strip():
                c[key + 'main'] = tuple(int(x) for x in nums(cb[g + 'main'])[:3])
            semis = {int(k[len(g) + 5:]): tuple(int(x) for x in nums(v)[:3]) for k, v in cb.items()
                     if k.startswith(g + 'semi.') and k[len(g) + 5:].isdigit()}
            if semis:
                c[key + 'semi'] = semis
        c['channels'] = max(10, min(24, c['channels']))
    if cp.has_section('gotcha'):
        g = cp['gotcha']
        context.gotcha_enabled = g.get('enabled', '1').strip() == '1'
        context.gotcha_season = int(g.get('season', context.gotcha_season))
        context.gotcha_mito_price = int(g.get('mito_price', '0') or 0)
        context.gotcha_coin_price = int(g.get('coin_price', '0') or 0)
    if cp.has_section('rush'):
        rs = cp['rush']
        on = lambda k, d: rs.get(k, d).strip() not in ('0', 'no', 'off')
        context.rush_schedule = on('schedule', '1')
        context.rush_always = on('always', '0')
        context.rush_start_members = max(1, min(255, int(rs.get('start_members', '2') or 2)))
        context.rush_countdown = max(0, int(rs.get('countdown', '60') or 0))
        context.rush_test_health = max(0.0, float(rs.get('test_health', '0') or 0))
    if cp.has_section('mita500'):
        mt = cp['mita500']
        context.mita500 = dict(
            enabled=mt.get('enabled', '0').strip() not in ('0', 'no', 'off'),
            bottles=max(1, min(16, int(mt.get('bottles', '10') or 10))), regen_sec=int(mt.get('regen_sec', '300') or 300),
            buff_sec=int(mt.get('buff_sec', '1800') or 1800), fee=int(mt.get('fee', '500') or 0),
            lucky_rate=int(mt.get('lucky_rate', '10') or 0))
    if context.mita500['enabled']:               # the client's bottles and salesperson (2008 XiMita500)
        m = context.mita500
        for flag, v in (('InstantMission.Mita500', 1), ('InstantMission.Mita500RegenCnt', m['bottles']),
                        ('InstantMission.Mita500RegenSec', m['regen_sec']), ('InstantMission.Mita500BuffSec', m['buff_sec'])):
            context.extra_flags.setdefault(flag, v)
    from .native.game.items import BACCHUS_SECONDS     # Bacchus F / D: the client's boost protection lasts this long
    context.extra_flags.setdefault('InstantMission.BacchusBuffSec', BACCHUS_SECONDS)
    if context.rush_always:                     # the client shows "N or more users ..." (texts 11138 / 11139)
        context.extra_flags.setdefault('City.AlwaysRushTime', 1)
        context.extra_flags.setdefault('City.RushTimeStartMember', context.rush_start_members)
    if cp.has_section('stickers'):
        context.sticker_upload = cp['stickers'].get('upload', 'all').strip().lower()
        context.sticker_daily_limit = int(cp['stickers'].get('daily_limit', '0') or 0)
    context.sections = {}
    if cp.has_section('battlezone'):
        context.practice_alone = cp['battlezone'].get('practice_alone', '1').strip() not in ('0', 'no', 'off')
        context.realmatch = cp['battlezone'].get('realmatch', 'always').strip().lower()
        context.laptime_level_limit = cp['battlezone'].get('laptime_level_limit', '0').strip() == '1'
        context.realmatch_minutes = int(cp['battlezone'].get('realmatch_minutes', '60'))
        rm_car = [v.strip() for v in cp['battlezone'].get('realmatch_car', '50, 9').split(',') if v.strip()]
        context.realmatch_car = ((int(rm_car[0]), int(rm_car[1]) if len(rm_car) > 1 else 9)
                                 if rm_car and int(rm_car[0]) else None)
        context.realmatch_effect = int(cp['battlezone'].get('realmatch_effect', '1'))
        for key, value in cp['battlezone'].items():
            f = [v.strip() for v in value.split(',')]
            if key.startswith(('section.', 'eu.section.')) and len(f) >= 4:
                levels = (int(f[4]), int(f[5])) if len(f) >= 6 else (0, 9999)
                to = context.sections_eu if key.startswith('eu.') else context.sections
                to[int(key.rsplit('.', 1)[1])] = (f[0], int(f[1]), int(f[2]), float(f[3]), *levels)
    w = n.get('delete_wait_days', '').strip()
    context.delete_wait_days = int(w) if w else None
    context.ranking_port = int(cp['services']['ranking'].split()[0]) if 'ranking' in cp['services'] else 0
    if cp['services'].get('barea', '').split()[1:2] == ['0']:
        from .native.race import RaceTraffic
        context.race_traffic = RaceTraffic(os.path.join(HERE, n['race_traffic_engine']), os.path.join(HERE, n['race_traffic_data']),
                                           os.path.join(context.data.root, 'Init', 'PVPTrackInfo.xlt'))
    t = cp['traffic'] if cp.has_section('traffic') else {}
    mode = t.get('city', 'native').strip().lower()
    if cp['services'].get('area', '').split()[1:2] == ['0'] and mode == 'native':
        from .native.city_traffic import CITIES, CityTraffic
        counts = {cid: int(t[f'cars.{name.lower()}']) for cid, (name, _) in CITIES.items() if f'cars.{name.lower()}' in t}
        context.city_traffic = CityTraffic(context.data.root, counts)
    print(f'city traffic: {"native" if context.city_traffic else mode}', flush=True)
    print(f'native: {len(context.server_list)} server(s), database {d["host"]}:{d["port"]}/{d["name"]}', flush=True)


async def run(cp, echo):
    e = cp['emulator']
    log_dir = os.path.join(HERE, e['log_dir'])
    msglog = MsgLog(log_dir, echo=echo)
    handlers.load()
    native_setup(cp)
    from .native import context
    if context.data:
        from .native.mode_tuning import apply
        apply(context.data.root)
    servers = []
    for name, spec in cp['services'].items():
        port, up_port, handshake = map(int, spec.split())
        svc = Service(name, e['listen'], port, e['upstream'], up_port, handshake, msglog)
        servers.append(await svc.start())
        to = f'{e["upstream"]}:{up_port}' if up_port else 'local'
        print(f'{name:7} {e["listen"]}:{port} -> {to}', flush=True)
    from .native import context
    if context.db and int(e['control_port']):     # GM commands (native/admin.py, tools/gmctl.py), local only
        from .native.admin import control
        servers.append(await asyncio.start_server(control, '127.0.0.1', int(e['control_port'])))
        print(f'control 127.0.0.1:{e["control_port"]}', flush=True)
    print(f'log: {msglog.path}', flush=True)
    await asyncio.gather(*(s.serve_forever() for s in servers))


def main():
    ap = argparse.ArgumentParser(prog='dcemu', description=__doc__.splitlines()[0])
    ap.add_argument('-c', '--config', default=os.path.join(HERE, 'emulator.ini'))
    ap.add_argument('-q', '--quiet', action='store_true', help='log to the file only')
    a = ap.parse_args()
    try:
        asyncio.run(run(load_config(a.config), not a.quiet))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
