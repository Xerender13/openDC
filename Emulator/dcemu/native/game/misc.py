"""Player profiles, team / channel battle answers without teams, GM commands
(batch 3 of the native game).

0x294 GameCharInfo (character name) -> 0x295 GameCharInfoAck (2011: 844 bytes; client 0x515be0 reads
    XiStrCharInfo @0, XiStrCarInfo @0x11b, XiStrStatInfo @0x14c, XiStrTeamInfo @0x1b4 (384), u32
    serial @0x334, then the location: 2008 one u32 (1 recorded), here u32 city @0x338 and zeros).
    Cmd_GameCharInfo: any character by name (online or not here), else 20019.
0x348 MyTeamInfo and the other crew messages: crews.py.
0x35e GetCBattleTime (act) -> 0x35f (act, u32 battle time: channels.battle_time).
0x387 CBattleInstance (act, ..) -> 0x388 (act, u32 0 battles; 2011 10 bytes).
0xf4 PartyLeave: social.py.
0x82 GameStream (u16 byte length, chat text; PacketParser::Cmd_GameStream): GM commands of accounts
    with PType 'A' or in the admin list, answered with 0x0001 "cmd(arg1,arg2,arg3)=[1 or 0]" (recorded
    "gmlevel(Xerender,50,0)=[1]"): gmlevel [name] level, gmexp [name] exp, gmmoney [name] Mito,
    gmitem [name] item id [count]. The character changed gets 0x169 CharUpdate (XiStrCharInfo) and its
    stats. Without a name the command is for the sender. (2008 also had gmcar, gmmove, gmeventitem.)
    Kick / block / ban (native/admin.py; the 2008 server had them on its GM console only): gmkick name
    [days], gmblock name days, gmunblock name, gmchatblock name minutes, gmban account-or-name, gmunban
    account-or-name, gmwho; answered with a line of text. gmgate N (0-7) makes every gate of every
    race give reward N, gmgate off ends it (to match the reward numbers to the power-ups). Rush time (rush.py, the
    2008 names): rushtimenow / rushtime [HUV type] [course], getrushtime, rushend.
"""
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame, read_wstr
from .. import admin, context, now
from . import player
from .channels import battle_time
from .login import SVC, error, send, sessions, stat_frames
from .progress import CHAR_EXP_SQL, add_exp

CHAR_INFO_ACK = 844
ADMIN_COMMANDS = ('kick', 'block', 'unblock', 'chatblock', 'ban', 'unban', 'who', 'realmatch')   # native/admin.py
TEAM_2011 = 384
NO_TEAM = struct.pack('<qq', -1, -1) + bytes(TEAM_2011 - 16)


def online(name):
    """-> the session of the character with this name, or None."""
    name = name.lower()
    return next((s for s in list(sessions.values())
                 if s.state.get('player') and s.state['player'].char.name.lower() == name), None)


@on(SVC, C2S, 0x294)
async def game_char_info(session, frame):
    name = read_wstr(frame.payload, 0, 0x2a)
    s = online(name)
    p = s.state['player'] if s else await player.load(name)
    if not p:
        return error(session, '20019')
    c = p.char
    car = p.car
    from .crews import info_bytes, team                 # the character's crew (XiStrTeamInfo, crews.py)
    crew = await team(c.team_id) if c.team_id > 0 else None
    out = bytearray(c.encode() + (car.encode() if car else bytes(49)) + p.stats().encode() + info_bytes(crew))
    out += struct.pack('<II', s.state.get('serial', 0) if s else 0, c.city)
    send(session, Frame(0x295, bytes(out.ljust(CHAR_INFO_ACK, b'\0'))))


@on(SVC, C2S, 0x35e)
async def cbattle_time(session, frame):
    act, = struct.unpack_from('<i', frame.payload) if len(frame.payload) >= 4 else (0,)
    send(session, Frame(0x35f, struct.pack('<iI', act, battle_time())))


@on(SVC, C2S, 0x387)
async def cbattle_instance(session, frame):
    act, = struct.unpack_from('<i', frame.payload) if len(frame.payload) >= 4 else (0,)
    send(session, Frame(0x388, struct.pack('<iI', act, 0)))


PLAYER_INFO, MAX_KEYS = 0xd8, 0x28
VISUAL_2011 = 0x36                             # XiVisualItem (2011)
# VisualItem.xlt category -> offset of its i16 in the 2011 XiVisualItem: the 2008 struct (ZoneServer.pdb:
# Neon, Plate, Decal, DecalColor, AeroBumper, AeroIntercooler, AeroSet, MufflerFlame, Wheel, Spoiler,
# Reserve) 6 bytes further on, with two 2011 slots in the old reserve: roof items and air ducts. The client
# reads @0xe/0x10/0x12/0x18/0x1a/0x1c in the car model 0x468100 with categories 4, 5, 6, 7, 47, 52 and
# the wheels @0x16 (0x4baf70). The first version put category c @6 + 2c: right for 4-6 and 8 only; the
# booster flame (10) went into the roof slot and showed an X-cat Doll on the car (user, 2026-10-13).
VISUAL_OFFSETS = {2: 0x06, 9: 0x08, 11: 0x0a, 4: 0x0e, 5: 0x10, 6: 0x12, 10: 0x14, 8: 0x16, 48: 0x16, 7: 0x18,
                  47: 0x1a, 52: 0x1c}


def aero_model(vis, v, car):
    """The look of a generic aero set (category 6 with no index: pc_Aero, pc_Aero2, pc_AeroMK2, ...): the shop writes
    10 reserved characters + car type (3 digits) + style (1) + the VisualItem UniqueId of the car's own aero model (5),
    e.g. "          081220082" = car 81, style 2, pc_0073s_03 "Drifter aerokit Mk.2" (index 312). -> its index, or 0.
    Until 2026-10-14 these sent 0: other players saw the car without its aero kit (user)."""
    tail = (v.data or '')[10:].strip()
    if vis.category != 6 or len(tail) < 5 or not tail[-5:].isdigit():
        return 0
    model = context.data.visuals.get(int(tail[-5:]))
    if not model or model.category != 6 or (model.cars and car.car_type not in model.cars):
        return 0
    return model.index


def visual_item(p):
    """XiVisualItem, 2011 (0x36 bytes): an i16 per look (VISUAL_OFFSETS) holding the item's number inside
    its category (the table's "index" column, from 1; 0 = none, the client then takes the car's default);
    the rest 0 (the first 6 bytes, the decal colour @0xc and the bytes after 0x1e are not known). A remote
    car's info is applied by 0x4bc9c0 -> car model 0x468100, which checks each value with 0x769460 (car
    type, category - 1, number: 1 .. the category's item count, and the item must fit the car type).
    Sending VisualItem ids in the 2008 slots showed no wheels (user, 2026-10-13).
    The 2011 stat items (index 0 in the table: "Tire S5", "AeroWing S5", ...) get their look chosen at
    the purchase; the client sends it as the item text and it is the number for the slot: a TireList.xlt
    "Tire ID" ("54") or a SpoilerList.xlt "Spoiler ID" ("26"), the same numbering as the classic items'
    index (tires 1-18, glossy tires 31.., spoilers 1-23, SpoilerList from 24). Glossy tires are their
    own category (48) but go on the wheels. Items of other categories (drinks, Sticker Glue, ...) have no
    slot."""
    out = bytearray(VISUAL_2011)
    car = p.car
    for v in p.vsitems:
        vis = context.data.visuals.get(v.table_idx)
        if not (car and vis and v.state == 1 and v.car_id == car.car_id):
            continue
        offset = VISUAL_OFFSETS.get(vis.category)
        text = (v.data or '').strip()
        number = vis.index or (int(text) if text.isdigit() and len(text) <= 4 else 0) or aero_model(vis, v, car)
        if offset is not None and number:
            struct.pack_into('<h', out, offset, number)
    return bytes(out)


def player_info(session):
    """XiPlayerInfo of the session's character, 2011 size (0xd8). The 2011 client reads the 2008 fields
    at the 2008 offsets (its uses of a car's info pointer [car+0x41e0]: name @0, u16 serial @0x1a, age
    @0x1c, i64 cid @0x1e, u16 level @0x26, u32 exp @0x28, i64 team @0x2c, team mark @0x34, team name
    @0x3c, u16 team level @0x58, XiVisualItem @0x5a) and takes the first 0x96 bytes from the server
    (handler 0x519f00); the bytes after XiVisualItem (@0x90: u16 @0x92, u8 @0x95 are read): u8 @0x95 = the
    delivery cargo the player carries (a_i_%04u model number, 0 none; jobs.set_delivery_item), drawn above
    their car by the other clients (0x6eac50); the rest is not known: 0."""
    from .records import wstr
    from .crews import crew_level
    p = session.state['player']
    c = p.char
    out = (wstr(c.name, 26) + struct.pack('<HHqHI', session.state.get('serial', 0),
                                           session.state.get('visual_age', 1) & 0xffff, c.cid, c.level, c.exp)
           + struct.pack('<qq', c.team_id, c.team_mark if c.team_id >= 0 else -1) + wstr(c.team_name, 28)
           + struct.pack('<H', crew_level(session.state.get('crew')) if c.team_id > 0 else 0) + visual_item(p))
    assert len(out) == 0x5a + VISUAL_2011
    out = bytearray(out.ljust(PLAYER_INFO, b'\0'))
    out[0x95] = session.state.get('cargo', 0) & 0xff
    # the client's own block (0x537ed0) also has u16 avatar @0x96 (char +0x36) and u16 guild type @0x98 (char +0xf1,
    # 1 = ROO: car 0x4ba640 tests it); 0x322 drops everything after 0x96, 0x329 keeps it (user, 2026-10-16: another
    # player still saw a ROO driver as OMD)
    struct.pack_into('<HH', out, 0x96, c.avatar & 0xffff, c.guild & 0xffff)
    return bytes(out)


@on(SVC, C2S, 0x321)
async def player_info_req(session, frame):
    """0x321 PlayerInfoReq (u32 n, n x XiPlayerKey: u16 serial, u16 age), sent for every car the client
    sees and does not know (again every 10 s until answered, and when a car's age changes) -> 0x329 (2011;
    2008: 0x322) PlayerInfoRes (u32 n, n x XiPlayerInfo) for the serials that are in the game (Cmd_PlayerInfoReq
    0x5eba80, at most 40 keys). Without it the other players have no name, no profile (the client's
    0x294 goes out with an empty name) and no visual items on their cars."""
    p = frame.payload
    if len(p) < 4:
        return
    n = min(struct.unpack_from('<I', p)[0], MAX_KEYS, (len(p) - 4) // 4)
    by_serial = {s.state.get('serial'): s for s in list(sessions.values()) if s.state.get('player')}
    found = [by_serial[k] for k in (struct.unpack_from('<H', p, 4 + 4 * i)[0] for i in range(n)) if k in by_serial]
    if found:
        # 0x329 PlayerInfoRes (2011: handler 0x519e90 stores the whole 0xd8 bytes; 0x322 "PlayerInfoOld" 0x519f00
        # keeps only the first 0x96 and zeroes the avatar / guild / 0xd0 / 0xd4 fields)
        send(session, Frame(0x329, struct.pack('<I', len(found)) + b''.join(player_info(s) for s in found)))
        from .stickers import info_frame
        from .licenses import nameplate_frame
        for s in found:                             # their stickers (Cmd_PlayerInfoReq: StickerInfoRes)
            f = await info_frame(s)
            if f:
                send(session, f)
            send(session, nameplate_frame(s))       # their mounted licenses (nameplate)


def is_admin(session):
    p = session.state.get('player')
    member = (session.state.get('member') or '').lower()
    return bool(p) and (p.char.ptype == 'A' or member in context.data.admins)


def char_update(session):
    p = session.state['player']
    send(session, Frame(0x169, p.char.encode()))
    for f in stat_frames(p):
        send(session, f)


@on(SVC, C2S, 0x82)
async def game_stream(session, frame):
    if len(frame.payload) < 2:
        return
    n, = struct.unpack_from('<H', frame.payload)
    text = read_wstr(frame.payload, 2, n).strip()
    words = text.split()
    if words and words[0].lower().lstrip('/') == 'report':     # /report <sticker name> [reason]: anyone
        from .stickers import report
        return await report(session, words[1:])
    from .rush import RUSH_COMMANDS, gm_command as rush_command
    name = words[0].lower().lstrip('/') if words else ''
    if name.startswith('gm') and name[2:] in RUSH_COMMANDS:
        name = name[2:]
    if name in RUSH_COMMANDS and is_admin(session):    # the 2008 server's rush commands, by their own names
        reply = await rush_command(name, words[1:])
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if not words or not words[0].lower().startswith('gm') or not is_admin(session):
        return
    cmd, args = words[0].lower(), words[1:]
    if cmd in ('gmbadsticker', 'gmgoodsticker', 'gmreports'):
        from .stickers import gm_command
        return await gm_command(session, cmd, args)
    if cmd == 'gmdrift':                        # gmdrift <drift item id> [days]: a drift shop item (0 days = for good)
        from .driftuse import Gains, give_drift_item
        p, t = session.state.get('player'), context.data
        name = args[0] if args else ''
        days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        if name not in t.visual_index:
            close = [k for k in t.visual_index if name.lower() in k.lower()][:5] if name else []
            reply = f'no drift item {name!r}' + (f'; like: {", ".join(close)}' if close else '')
        else:
            gains = Gains()
            await give_drift_item(p, name, days, gains, session)
            gains.send(session, p)
            from .items import bonus_update
            send(session, bonus_update(p))
            reply = f'drift item {name} given ({days or "no"} days limit)'
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd == 'gmsets':                         # gmsets [set]: one of every set part (or of one set: gmsets kayla)
        from .combo import take
        from .items import mod_list
        p, t = session.state.get('player'), context.data
        want = args[0].lower() if args else ''
        rows = [r for r in t._part_rows if r[2].startswith('si_') and not r[2].endswith('_to')
                and (not want or r[1].lower() == want)]
        room = (p.char.hancoin_inven + 2) * 20 - sum(1 for i in p.items if not i.car_id)
        if not rows or len(rows) > room:
            reply = (f'no such set: {want}' if not rows else f'{len(rows)} parts need {len(rows)} free slots, {room} free')
        else:
            got = [await take(p, t.item_info(t.item_index[r[2]])) for r in rows]
            send(session, mod_list(*got))
            reply = f'{len(got)} set parts given ({len({r[1] for r in rows})} sets)'
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd == 'gmpartytest':                    # gmpartytest on | off: party patrol test mode alone (partypatrol.py)
        from .partypatrol import gm_test
        reply = gm_test(session, args)
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd == 'gmvchasetest':                   # gmvchasetest on | off: Virtual HUV with two players (vchase.py)
        from .vchase import gm_test
        reply = gm_test(session, args)
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd == 'gmuctest':                       # gmuctest on | off: the Undercity alone (undercity.py)
        from .undercity import gm_test
        reply = gm_test(session, args)
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd == 'gmgate':                         # gmgate 0-7: every gate gives that reward; gmgate off
        from . import rooms
        rooms.forced_reward = int(args[0]) if args and args[0].isdigit() and int(args[0]) < rooms.REWARDS else None
        reply = (f'every gate now gives reward {rooms.forced_reward}' if rooms.forced_reward is not None
                 else 'gate rewards follow gate_rewards.txt again')
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    if cmd[2:] in ADMIN_COMMANDS:
        ok, reply = await admin.command(cmd[2:], args)
        session.log.note(f'GM {text!r}: {reply}')
        return admin.message(session, reply)
    ok = await gm(session, cmd, args)
    session.log.note(f'GM {text!r}: {ok}')
    shown = (args * 2 if len(args) == 1 else args) + ['0'] * 3
    msg = f'{cmd}({",".join(shown[:3])})=[{int(ok)}]'.encode('utf-16-le') + b'\0\0'
    send(session, Frame(0x0001, struct.pack('<H', len(msg)) + msg))


async def gm(session, cmd, args):
    from .combo import take
    from .items import add_money, mod_list
    target = session
    if args and not args[0].lstrip('-').isdigit() and args[0] not in context.data.item_index:
        target = online(args[0])
        args = args[1:]
    if not target or not args:
        return False
    p, t, db = target.state['player'], context.data, context.db
    c = p.char
    if cmd == 'gmitem':
        info = t.item_info(t.item_index.get(args[0], -1))
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        if not info or count < 1:
            return False
        send(target, mod_list(*[await take(p, info) for _ in range(min(count, 99))]))
        return True
    try:
        value = int(args[0])
    except ValueError:
        return False
    if cmd == 'gmlevel':
        if not 1 <= value <= 200:
            return False
        c.level = value
        c.exp_base, c.exp_next = t.exp_bounds(value)
        c.exp = c.exp_base
        await db.execute(CHAR_EXP_SQL, (c.level, c.exp, db.server_id, c.cid))
    elif cmd == 'gmexp':
        if value < 0:
            return False
        await add_exp(c, value)
    elif cmd == 'gmmoney':
        if not await add_money(c, value):
            return False
    else:
        return False
    char_update(target)
    return True
