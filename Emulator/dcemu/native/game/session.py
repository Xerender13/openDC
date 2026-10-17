"""Game service requests of an ordinary session (batch 1 of the native game, see EMULATOR_NOTES.md).

0x3f2 UpdateCouponForVar (XiStrCouponForVar, the coupon progress counters: PvP battle, quick service,
    chasing, combo, drive time, drift, art drive, jump, reverse drive, undercity; 10 floats in 2008. In
    2011 combo and drift are u32, the rest floats, the two times in seconds (client 0x709e50: fild for
    them, x 1/60 for the times); read as floats the counts were lost and later updates "went down":
    user, 2026-10-13, combos / drifts stayed 0. COUPON_VARS).
    XiCsCharInfo::UpdateCouponForVar 0x5ccfd0: if any of the first nine went down, the update is
    refused and the stored values are sent back (0x3f4); else they are kept and saved
    (SKID_COUPONVALUE_TB), no answer. (The 2008 server saved at most every few minutes.)
0x104 TutorialClear (u32 type) -> 0x105 (u32 type). Type 0, the battle tutorial: PLAYMODE
    'BATTLETUTORIAL' try + 1, win + 1 (DefQuerySKIDIncPlayMode), character flag 0x4000000.
0x578 GetMyHancoin -> 0x579 (u32 G Coin: SKID_UNALISCOIN_TB.COIN of the account, a row with 0 made
    if there is none; i64 mileage).
No answer (as the 2008 server in this setup): 0x7a CheckOutGame, 0x86 GetMail (a friend invitation
    web call), 0x87 CheckEvent (VIP event check), 0x12e LeaveArea (the game side forgets the area),
    and the 2011-only 0x466 (u32), which the 2008 server did not know either (0xc28: partypatrol.py) (0x32d: licenses.py)
    (0x327 SetMyDeliveryItem: jobs.py).
"""
import math
import struct

from ...handlers import on
from ...protocol import C2S
from ...wire import Frame
from .. import admin, context, now
from .login import SVC, error, send
from .records import wstr
from .player import BATTLE_TUTORIAL_DONE

COUPON_SAVE_SQL = """IF EXISTS (SELECT 1 FROM SKID_COUPONVALUE_TB WHERE SERVERID=%s AND CID=%s)
  UPDATE SKID_COUPONVALUE_TB SET PVPBATTLE=%s, QUICKSERVICE=%s, CHASING=%s, COMBO=%s, DRIVETIME=%s, DRIFT=%s,
    ARTDRIVE=%s, JUMP=%s, REVDRIVE=%s, UNDERCITY=%s WHERE SERVERID=%s AND CID=%s
ELSE
  INSERT INTO SKID_COUPONVALUE_TB(SERVERID, CID, CNAME, PVPBATTLE, QUICKSERVICE, CHASING, COMBO, DRIVETIME, DRIFT,
    ARTDRIVE, JUMP, REVDRIVE, UNDERCITY) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
# the SQL Server form of the 2008 server's IncPlayMode (UPDATE ... OUTPUT, else INSERT)
PLAY_MODE_SQL = """SET NOCOUNT ON;
UPDATE SKID_PLAYMODE_TB SET LASTDATE=GetDate(), TRYCNT=TRYCNT+%s, WINCNT=WINCNT+%s
  WHERE SERVERID=%s AND CID=%s AND MODEID=%s;
IF @@ROWCOUNT = 0
  INSERT INTO SKID_PLAYMODE_TB(SERVERID, CID, CNAME, MODEID, CDATE, LASTDATE, TRYCNT, WINCNT, POINT, PLAYTIME,
    NEXP, GAMEMONEY, BESTCNT, RETIRECNT, MEMBERID) VALUES (%s,%s,%s,%s,GetDate(),GetDate(),%s,%s,0,0,0,0,0,0,%s)"""
COIN_SQL = "SELECT COIN FROM SKID_UNALISCOIN_TB WHERE MEMBERID=%s"
COIN_NEW_SQL = "INSERT INTO SKID_UNALISCOIN_TB (MEMBERID, COIN, LASTDATE) VALUES (%s, 0, GETDATE())"
COUNTERS_CHECKED = 9
COUPON_VARS = '<3fIfI4f'         # 2011 XiStrCouponForVar


def pack_coupon_vars(v):
    return struct.pack(COUPON_VARS, v[0], v[1], v[2], int(v[3]), v[4], int(v[5]), *v[6:10])


async def inc_play_mode(c, mode, tries, wins):
    db = context.db
    await db.execute(PLAY_MODE_SQL, (tries, wins, db.server_id, c.cid, mode,
                                     db.server_id, c.cid, c.name, mode, tries, wins, c.member))


@on(SVC, C2S, 0x3f2)
async def update_coupon_vars(session, frame):
    p = session.state.get('player')
    if not p or len(frame.payload) < 40:
        return
    new = struct.unpack_from(COUPON_VARS, frame.payload)
    old = p.coupon_vars
    if any(n < o for n, o in zip(new[:COUNTERS_CHECKED], old[:COUNTERS_CHECKED])):
        session.log.note('coupon counters went down: refused, stored values sent back')
        send(session, Frame(0x3f4, pack_coupon_vars(old)))
        return
    p.coupon_vars = new
    from .licenses import CITY_SUFFIX, count, count_many
    drive, under = int(new[4] - old[4]), int(new[9] - old[9])
    if drive > 0:                               # licenses: GC_FieldTime (seconds; the client's drive time total)
        await count(session, 'FieldTime', drive)
    if under > 0:                               # GC_UndercityClear (and per city): the client's Undercity total
        sfx = CITY_SUFFIX.get(p.char.city, ('', '', ''))[2]
        for _ in range(under):
            await count_many(session, ['UndercityClear'] + ([f'UndercityClear_{sfx}'] if sfx and sfx != 'OR' else []))
    db, c = context.db, p.char
    await db.execute(COUPON_SAVE_SQL, (db.server_id, c.cid, *new, db.server_id, c.cid,
                                       db.server_id, c.cid, c.name, *new))


@on(SVC, C2S, 0x104)
async def tutorial_clear(session, frame):
    p = session.state.get('player')
    kind, = struct.unpack_from('<I', frame.payload) if len(frame.payload) >= 4 else (0,)
    if p and kind == 0:
        await inc_play_mode(p.char, 'BATTLETUTORIAL', 1, 1)
        p.char.flags |= BATTLE_TUTORIAL_DONE
        session.log.note('battle tutorial cleared')
    send(session, Frame(0x105, struct.pack('<I', kind)))


@on(SVC, C2S, 0x578)
async def my_hancoin(session, frame):
    p = session.state.get('player')
    if not p:
        return
    db, c = context.db, p.char
    r = await db.row(COIN_SQL, (c.member,))
    if r is None:
        await db.execute(COIN_NEW_SQL, (c.member,))
    send(session, Frame(0x579, struct.pack('<Iq', int(r[0]) if r else 0, c.mileage)))


async def no_answer(session, frame):
    pass


for _t in (0x7a, 0x87, 0x12e, 0x466):
    on(SVC, C2S, _t)(no_answer)


CHAT_ROOM = 20                      # wchar[10] room name: "channel", "team", "party", ...


@on(SVC, C2S, 0x92)
async def chat(session, frame):
    """0x92 ChatMsg (wchar[10] room, u32 colour, u16 length, the text: length characters + 0) ->
    0x93 ChatMsgAck (room, wchar[16] sender, colour, length, text) to everyone in the same game
    channel (Cmd_ChatMsg 0x5ff9a0: "channel"); "party" to the party (social.py), "team" to the crew's members in the
    game (crews.py; without a crew 20074)."""
    from .login import sessions
    p = session.state.get('player')
    if not p or len(frame.payload) < CHAT_ROOM + 6:
        return
    until = session.state.get('chat_block', 0)
    if until > now():                               # the client blocks its own chat on 0x9c4; told again
        return send(session, admin.chat_block_frame(until))
    room = frame.payload[:CHAT_ROOM].decode('utf-16-le', 'replace').split('\0')[0]
    from .rooms import room_of
    from .social import party_of
    if room.lower() == 'party':                     # the session's party (social.py)
        party = party_of(session)
        if party:
            out = Frame(0x93, frame.payload[:CHAT_ROOM] + wstr(p.char.name, 32) + frame.payload[CHAT_ROOM:])
            return party.cast(out)
    if room.lower() == 'team':                      # crew chat: the crew's members in the game (crews.py)
        from .crews import chat as crew_chat
        out = Frame(0x93, frame.payload[:CHAT_ROOM] + wstr(p.char.name, 32) + frame.payload[CHAT_ROOM:])
        if not crew_chat(session, p, out):
            error(session, '20074')
        return
    pvp_room = room_of(session)
    if room.lower() != 'channel' and not (pvp_room and room.lower() not in ('team', 'party')):
        session.log.note(f'chat to {room!r}: not available natively yet')
        return
    color, length = struct.unpack_from('<IH', frame.payload, CHAT_ROOM)
    text = frame.payload[CHAT_ROOM + 6:]
    out = Frame(0x93, frame.payload[:CHAT_ROOM] + wstr(p.char.name, 32) + struct.pack('<IH', color, length) + text)
    if room.lower() != 'channel':                   # in a race room: its members (the room's BS_ChatRoom)
        return pvp_room.cast(out)
    channel = session.state.get('channel')
    for s in list(sessions.values()):
        if s.state.get('player') and s.state.get('channel') == channel:
            s.to_client(out)


WHISPER_NAME = 40                   # wchar[20]


@on(SVC, C2S, 0x94)
async def whisper(session, frame):
    """0x94 Whisper (wchar[20] name, u32, u16 text byte length, the text; 2008 BS_PktWhisper 48 + text) ->
    the same message to the other player with the sender's name and the u32 0, and back to the sender with
    the other player's name and the u32 1 (PacketParser::Cmd_Whisper 0x5f03d0; the 2011 client 0x50ed40 prints
    either with the "whisper" format). Not in the game: 20213 "%s does not exist."."""
    from .misc import online
    p = session.state.get('player')
    if not p or len(frame.payload) < WHISPER_NAME + 6:
        return
    until = session.state.get('chat_block', 0)
    if until > now():
        return send(session, admin.chat_block_frame(until))
    name = frame.payload[:WHISPER_NAME].decode('utf-16-le', 'replace').split('\0')[0]
    length, = struct.unpack_from('<H', frame.payload, WHISPER_NAME + 4)
    text = frame.payload[WHISPER_NAME + 6:WHISPER_NAME + 6 + min(length, 0x400)]
    target = online(name)
    if not target or target is session:
        return admin.message(session, context.data.server_text.get('20213', '%s does not exist.').replace('%s', name))
    tail = struct.pack('<H', len(text)) + text
    send(target, Frame(0x94, wstr(p.char.name, WHISPER_NAME) + struct.pack('<I', 1) + tail))
    send(session, Frame(0x94, wstr(target.state['player'].char.name, WHISPER_NAME) + struct.pack('<I', 0) + tail))
    session.log.note(f'whisper to {name!r}')


CAR_SAVE_SQL = ("UPDATE SKID_CAR_TB SET LASTDATE=GetDate(), MITRON=%s, KM=%s, FUELCONSUME=FUELCONSUME+%s"
                " WHERE SERVERID=%s AND CID=%s AND CARID=%s")


@on(SVC, C2S, 0x2d1)
async def drive_info(session, frame):
    """0x2d1 DriveInfoUpdate: XiStrDriveInfo (u32 car, time, f32 total distance, total fuel, step
    distance, step fuel; 2011 adds 44 bytes after it, not read). Cmd_DriveInfoUpdate 0x5eb1b0 keeps the
    car's Mitron and distance; saved here at once with the 2008 server's car update."""
    p = session.state.get('player')
    if not p or len(frame.payload) < 24:
        return
    car_id, _, distance, fuel, _, step_fuel = struct.unpack_from('<Ii4f', frame.payload)
    if session.state.get('real_match_car'):
        return          # the Real Match car's fuel, under the player's car id (rooms.real_match_car)
    car = next((c for c in p.char.cars if c.car_id == car_id), None)
    if not car:
        return
    car.mitron, car.km = max(0.0, min(fuel, car.capacity or fuel)), distance
    db = context.db
    await db.execute(CAR_SAVE_SQL, (car.mitron, car.km, max(step_fuel, 0.0), db.server_id, p.char.cid, car_id))


PREMIUM_FUEL, PREMIUM_FUEL_DISCOUNT = 1, 0.5     # sale flag 1: char byte +0x363 set (not kept here)
AUTO_FILL_UP, AUTO_FILL_UP_FACTOR = 34, 0.8      # drift category of i_automitron, its 20 % discount
PAY_SQL = """SET NOCOUNT ON;
UPDATE SKID_CHARACTER_TB SET GOLD=GOLD-%s WHERE SERVERID=%s AND CID=%s AND GOLD>=%s;
IF @@ROWCOUNT = 1 UPDATE SKID_CAR_TB SET MITRON=%s WHERE SERVERID=%s AND CID=%s AND CARID=%s;
SELECT GOLD FROM SKID_CHARACTER_TB WHERE SERVERID=%s AND CID=%s"""


@on(SVC, C2S, 0x2d3)
async def fuel_charge(session, frame):
    """0x2d3 FuelChargeReq (u32 car, i64 pay, f32 fuel; 2011 + 4 bytes) -> 0x2d4 FuelChargeRes (u32 car,
    i64 pay, f32 fuel added, i64 money, f32 Mitron, f32 unit price, f32 sale unit price, f32 capacity,
    f32 efficiency, i32 sale flag; 2011 + u32 @0x32: 1 = leave the fuel dialog alone -> 0).
    Cmd_FuelChargeReq 0x5f5210: unit price = Contents.ini Main.MitronUnitPrice, factor 1 (- 0.5 with the
    Mittron Fuel Booster held: char flag 0x363, HalfMitronCharge, which also sets the sale flag; - 0.2 / 0.1
    for owners of team channels: none here). Pay 0 asks the price. A
    purchase needs fuel <= pay / (price x factor) + 0.1, pay <= money (else error 20121), Mitron + fuel
    <= capacity + 1; then the money is taken and the fuel added (car and money saved at once; the 2008
    server also paid a tax to the channel owners).
    **Auto Fill-Up** (drift item i_automitron, category 34, 2011): the client (0x5361b0, every 2 s) sends (car, 0, 0.0,
    u32 1) when the tank is below 20 %, it holds i_automitron (opts +0x1b12, set by 0x5dd) and has Mito; again after
    10 s, after 30 s with no Mito. Its item text: refuels with 20 % discounted Mittron, only as much as the Mito
    pays for. The answer carries 1 @0x32 so the client's handler (0x520290) leaves the fuel window closed. The
    discount does not add to the Fuel Booster's: the lower price counts (a guess)."""
    p = session.state.get('player')
    if not p or len(frame.payload) < 16:
        return
    c = p.char
    car_id, pay, fuel = struct.unpack_from('<Iqf', frame.payload)
    car = next((x for x in c.cars if x.car_id == car_id), None)
    if not car:
        return
    price = float(context.data.contents.get('Main.MitronUnitPrice', 15))
    from .items import FUEL_BOOSTER, holds
    factor, sale_flag = (0.5, 1) if holds(p, FUEL_BOOSTER) else (1.0, 0)
    auto = len(frame.payload) >= 20 and struct.unpack_from('<I', frame.payload, 16)[0] == 1
    if auto:
        if not holds(p, AUTO_FILL_UP):
            return
        factor = min(factor, AUTO_FILL_UP_FACTOR)
        fuel = max(0.0, (car.capacity or 0) - car.mitron)
        pay = math.ceil(fuel * price * factor)
        if pay > c.mito:                    # not enough Mito: what it pays for
            pay = max(c.mito, 0)
            fuel = pay / (price * factor)
    paid, added = 0, 0.0
    if pay > 0 and fuel <= pay / (price * factor) + 0.1 and car.mitron + fuel <= (car.capacity or 0) + 1.0:
        if pay > c.mito:
            return error(session, '20121')
        db = context.db
        r = await db.row(PAY_SQL, (pay, db.server_id, c.cid, pay, car.mitron + fuel, db.server_id, c.cid, car_id,
                                   db.server_id, c.cid))
        gold = int(r[0]) if r else c.mito
        if gold == c.mito - pay:
            car.mitron += fuel
            paid, added = pay, fuel
        c.mito = gold
    send(session, Frame(0x2d4, struct.pack('<Iqfqfffffi', car_id, paid, added, c.mito, car.mitron, price,
                                           price * factor, car.capacity, car.efficiency, sale_flag)
                  + struct.pack('<I', int(auto))))
    if auto:
        session.log.note(f'auto fill-up car {car_id}: {added:.1f} Mitron for {paid} Mito')
