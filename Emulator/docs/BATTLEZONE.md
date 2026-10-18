# Battle zone (race rooms and races) with the 2011 US client

Reference for the battle zone work of 2026-10-12 (session 2). Everything here was measured with
the real 2011 client unless marked *(guess)*. Offsets count from the message type (as the 2008
`BS_Pkt*` structs and the 2011 client handlers do); payload offsets are 2 less.

Status (session 3, 2026-10-13): **native** in `Emulator/dcemu/native/game/rooms.py` (+ the native BArea
of `native/area.py` / `race.py`), see "Native rooms and races" below; tested with two scripted clients,
not yet with the real client. "What works" and the layout table were measured through the proxy in
front of the 2008 server (`Emulator/dcemu/handlers/room.py`, `game.py`), which is what the native
service reproduces.

## What works (user-tested)

| Step | Result |
|---|---|
| Battle zone lobby (0x1b8 -> 0x1b9) | opens |
| Create a room (0x1cc -> 0x26e, 0x1be, 0x1cd) | the room opens with its name, map and options |
| Choose the track, room options, lock / unlock seats (0x26d) | works; a 16-player room shows 16 seats |
| Practice room (one player, PracticeMode=1) | drives the track; no start signal, no result (by design, see below) |
| Normal solo race (PracticeMode=0) | load, go, all gates, finish, result screen |
| Race traffic on the tracks | yes (ZoneServer's own race traffic, room options passed on correctly) |
| City traffic, area | native area (`Emulator/dcemu/native/area.py`), separate from this |

Not tested: a second player (joining, leaving, the room list with rooms in it, results with
several entries, team races), Real Match, observers, channel battles.

## The race flow (2008 server, as the 2011 client runs it)

```
lobby   C 0x1b8 RegisterRoomObserver          S 0x1b9 ack (+12 in 2011), 0x1d0 room list
create  C 0x1cc RoomCreate (2011 layout)      S 0x26e RoomMaster, 0x1be RoomState (2008: 0x1ce),
                                                0x1cd RoomCreateAck
setup   C 0x26d RoomModify (2008: 0x26c)      S 0x26d to the room (2008: 0x26c)
start   C 0x1e6 PvpStartReq                   S 0x1e7 PvpLoad (type 100 = practice)
load    C 0x1e8 loading status ..., game 0x12c JoinArea (room area), barea 0x232 join
        C 0x1e9 PvpLoadComplete               S 0x1ea PvpGo (when everyone loaded)
race    barea 0x238 SetAreaMap (owner: map, max traffic, mode, city), 0x21d moves, 0x21e traffic
        C 0x1ed PvpGate (each gate)           S 0x1ee
finish  C 0x1eb PvpEnd                        S 0x1eb (to the room), 0x1ef PvpFinish, 0x26e,
                                                0x1ec PvpResult
leave   C 0x1e5 PvpReadyState, 0x12e LeaveArea, barea 0x23a / 0x234
```

2008 code (ZoneServer.exe, `tools/dev/sdis.py`): Cmd_RoomCreate 0x685720, Cmd_RoomModify
0x6818b0 (BS_Room::ApplySlot, then 0x26c to the room), Cmd_PvpStartReq 0x682430 (errors 20180 no
members, 20181 not the owner, 20182 not all ready), BS_Room::StartLoad 0x5aaec0,
Cmd_PvpLoadComplete 0x685dd0 -> BS_Room::LoadComplete 0x5b2a20 -> RemoveFromWaitSet 0x5b1ef0
(all loaded and room state 1 -> BS_Room::Start + 0x1ea PvpGo; at the end 0x1ef and
BS_Room::PvpRaceResult).

**Practice:** BS_Room::StartLoad takes the practice path when the room has exactly one member,
Contents.ini `BattleZone.PracticeMode=1` ([0x70590c] bit 12) and the room type lacks 0x200: 0x1e7
type 100, the room never enters state 1, so no 0x1ea, no gates, no 0x1eb / 0x1ec, no reward. The
2011 client's practice room and a normal room differ only in capacity (1 vs 16, both type 0x80),
so with PracticeMode=1 every solo race is practice. **Now PracticeMode=0** in
`Server/server/Data_TW/Contents.ini` (the user's choice; original in `Server/backup/data_tw_2008/`):
solo races in any room run the real flow. The 2008 server gave 0 mito / 0 exp for a one-player race.

## Message layouts and what the proxy does

Shared types:
- **XiPvpUserInfo** 2008 (8): u16 Level, u16 Port, u32 Ip. 2011 (12): u32 ? @0 (0x0001a132,
  0x00010c5a, 0x0001005a seen), u16 ? @4, u16 port @6, u32 IP @8 (the UDP address the client got in
  0x323). Converted: port and IP across, 2008 Level from 2011 @2 *(guess)*; the client's own 12 bytes
  are kept and returned in its 0x1cd.
- **Room type** 2008 i16 (0x80 normal; 0x100 without 0x200 = Real Match), 2011 u32 (0x80, 0x580 seen;
  new bits 0x400 / 0x800 tested by the 0x1cd handler with 0x10000). The server gets `& 0x3ff`, the
  client gets its own value back.
- **Seats (XiPvpRoomSlot)** 2008 u16[32], **2011 u32[32]**: a player's serial, 0 open, 0xffff /
  0xffffffff locked. Unconverted, a 16-player room showed 8 seats (u16 pairs read as u32).
- **Map flag** (room options; traffic bits 0x04 / 0x08 / 0x10, 0x40, 0x80, 0x1000 seen): u16 in 2008,
  u32 in the 2011 0x26d.

| Type | Dir | 2008 (from the type) | 2011 | Proxy |
|---|---|---|---|---|
| 0x1b9 RegisterRoomObserverAck | S>C | 0x1a: Result, PvpChannelId, RoomFilter, Page, RealMatchEnable, RealMatchTime | 0x26: + u32 @0x1a (bool), @0x1e, @0x22 (lobby dialog settings) | 12 zero bytes added |
| 0x1cc RoomCreate | C>S | 0x8a: UserInfo @2, i16 RoomType @0xa, MapId @0xc, PlayerCapacity @0xe, MapFlag @0x10, wchar[30] name @0x12, password @0x4e | 0xa4 (builder 0x7e87f0): UserInfo(12) @2, u32 RoomType @0xe, MapId @0x12, Capacity @0x14, MapFlag @0x16, u32 @0x18, u32 @0x1c, name @0x20, password @0x5c, 12 bytes @0x98 | -> 2008 |
| 0x1cd RoomCreateAck | S>C | 0x1c: UserInfo, Result @0xa, RoomId, RoomLifeId, i16 RoomType @0x16, MapId, MapFlag | 0x22 (handler 0x52a740): UserInfo(12), Result @0xe, RoomId, RoomLifeId, u32 RoomType @0x1a, MapId @0x1e, MapFlag @0x20 | -> 2011 |
| 0x1ce RoomState | S>C | 0xb2 + n x 53: Result, RoomId, RoomLifeId, MapId @0xe, MapFlag, i16 RoomType @0x12, State, AreaId, Capacity, Viewers, RoomReady, wchar[40] name @0x1e, seats @0x6e, u32 n @0xae, members @0xb2 (u16 Serial, u16 Age, UserInfo, bool Ready, XiCarAttr, wchar[16] Name) | **no handler** ("Wrong Command: 462"); 2011 uses **0x1be** (handler 0x52d000): same to @0x12, u32 RoomType @0x12, the rest +2 (name @0x20), seats u32[32] @0x70, u32 n @0xf0, members @0xf4 x 63 (u32 Serial, u16 Age, UserInfo(12), bool Ready, XiCarAttr + 4, wchar[16] Name) | 0x1ce -> 0x1be |
| 0x26c / 0x26d RoomModify | both | 0x26c 0x4c: RoomId, MapId @6, u16 MapFlag @8, Capacity @0xa, seats @0xc | **0x26d** 0x8e (builder 0x7e8b4e, handler 0x52a7c0): RoomId, MapId @6, u32 MapFlag @8, Capacity @0xc, seats u32[32] @0xe | 0x26d <-> 0x26c (the 2008 server said "Wrong Command: 621" to 0x26d) |
| 0x1ec PvpResult | S>C | 0x1a + n x 52 (XiPvpResult: EndType, Serial, DeltaMoney, u64 Money, DeltaExp, Record, u16 Rank, u16 Level @0x1e, XiStrExpInfo @0x20, Point, Flag) | same header, n x 60 (handler 0x52ced0 -> room dialog vfunc 0x12c = 0x778980): the 2008 fields + 8 bytes (u32 @0x38 read) | 8 zero bytes per entry |
| 0x5a SelectCarAck, 0x56 BuyCarAck | S>C | XiStrCarInfo (45) [+ u32 Gold] | car record 49 (4 new bytes @0x24, as in 0x7c) | converted (game.py) |
| 0x1e7 PvpLoad, 0x1ea PvpGo, 0x1eb PvpEnd, 0x1ee, 0x1ef, 0x1e5, 0x26e | | | same sizes | passed on |
| 0x1e9 PvpLoadComplete | C>S | u32 Time, u32 CompletePercent | the same (percent 0 in practice, 100 in a race; the 2008 server does not read it) | passed on |

0x1d0 RoomListAck (2008 0x12 + n x 104 XiPvpRoomInfo; the 2011 handler reads 128 for one entry:
probably 110-byte entries, u32 room type and 4 more bytes *(not checked)*) is passed on unchanged:
only empty lists have been seen. `Emulator/dcemu/commands.py` knows the variable 2008 sizes of
0x1ce and 0x1d0 (frames holding several commands).

**"Level up to level 0" at the end of a race:** the result parser 0x778980 copies each entry's
Level and exp info into the character and plays the level-up (0x6d6510) when the level differs.
With the 8-byte-short 2008 result the client rejected / misread it; fixed by the 0x1ec conversion.
After a practice race (no 0x1ec at all) the same screen appeared once; not looked into further.

## Native rooms and races (session 3, 2026-10-13)

`native/game/rooms.py`; its docstring lists every message with offsets. Found for it:
- **Room list 0x1d0**: 2011 XiPvpRoomInfo is 0x72 bytes (client 0x52be30 steps by 0x72 and returns
  0x12 + n x 0x72): the 2008 fields with a u32 room type @0x12 (the rest 2 later: players @0x16,
  capacity @0x18, name @0x1e, team @0x5a, team mark @0x62) and 8 more bytes. The client has no
  0x1cf RoomList request: lists come with 0x1b8 and are pushed when rooms change.
- **Joining**: the client builds 0x1d4 (0x7e9450, 0x184 bytes), 0x1bc secure (0x7e9700), 0x1bb direct
  (0x7e9900), 0x1bd by id (0x7e9ae0), 0x1d7 channel room (0x7e9160); each carries the joiner's UserInfo
  (12), XiCarAttr (12) and XiPlayerInfo (0xd8 = 216 bytes; 2008 144; name @0, u16 serial @0x1a, age @0x1c
  as before, checked in handler 0x52c330). The 2008 server filled PlayerInfo itself (BS_Game::
  FillPlayerInfo); the rest of the 2011 layout is unknown, so the client's own bytes are passed on.
  S>C 0x1d4 is the same struct: u32 serial @2 (> 0xffff is tested), age @6, UserInfo @8, CarAttr @0x14,
  room @0x20, life id @0x24, PlayerInfo @0x28, seats @0x100, u32 room type @0x180.
- **Leave / banish** 0x1d5 / 0x1d6: 0x8a bytes (u32 serial, seats u32[32], u32 room type); a client that
  gets 0x1d6 with its own serial closes its room (0x52a970).
- **0x1da RoomClose**: the 2011 handler (0x52c4a0) reads its text @0xa (2008 @6); size not known, not sent.
- **Race flow** as recorded: 0x1e7 (type 0, map, flag, area, 0, the request's start time, -1), 0x1ea (the
  last loader's time, countdown 19500 = the constant in BS_Room::RemoveFromWaitSet), 0x1eb back with the
  server's rank, 0x1ef = first end time + 20000, then 0x26e + 0x1ec.
- **Rewards** (BS_Room::PvpRaceResult 0x5ae820, PvpTrackTable::LoadPvpExp 0x668670): files next to
  ZoneServer.exe. `pvpexpbase.txt` / `pvpmoneyrate.txt`: 16 rows = rank, 15 columns = racers 16 down to 2
  (no column for 1: a race alone gives 0, as recorded); `pvpexprate.txt` by PvP channel (the id in 0x1b8:
  5 and 6 seen; 1-6: 2, 3, 4, 6, 8, 2); `pvpmoneybase.txt` by a 1-9 value taken from the racer's car
  *(read as the car's grade)*. A racer who did not finish ranks last. Exp = base x rate, Mito = base x
  rate; then CalcBonus (GM / premium bonuses, the result's Flag: not done, Point and Flag sent as 0;
  the recorded solo result had Point 8, Flag 0x80). PLAYMODE 'PVP' try / win.
- The area of a race is 900 + room id (the 2008 server took a free one from a pool: 907-909 recorded).
- Choices of ours: the joiner gets 0x26e + 0x1be and not its own 0x1d4 (the 0x1be handler is what
  creates the room dialog); a member who has not ended 23 s after the first finish is ranked last; a
  loading that takes over 120 s starts without the stragglers.
- With the real client (user, 2026-10-13, two clients): the list shows the room, joining from the list
  sends 0x1d4 and the room opens on 0x26e + 0x1be, ready works. **The host had no "Start"**: the master's
  member record must say ready = 1 (as in the 2008 recording); fixed, to be confirmed. The lobby's
  spectate button sends 0x1de JoinOBS (u32 room): refused with 20188 for now. A 0x1e6 without a room
  (map 74, from the lobby; the client loads the track whatever the answer) is answered as a practice run
  (0x1e7 type 100, area 20000 + serial) *(guess)*.
- User, 2026-10-13: **a race with two real clients works from start to end** (after the master-ready
  fix). Gates gave nothing (0x1ee was always 0) -> **gate rewards**: `Emulator/gate_rewards.txt` (racers,
  position at the gate, clean, chance of reward 0-7), exported from the 2008 server's tables in
  ZoneServer.exe (BS_Room::Gate 0x5a8ca0; rooms.gate_reward does the same draw) and editable; reward 0 =
  nothing, 1 Boost 50%, 2 Boost 100%, 3 Skid Rush, 4 Repairs Complete, 5 Untouchable, 6 Hyper Boost,
  7 Team Boost 50% (user, in game, with the GM command `gmgate N`; `gmgate off` ends it).
- **Power-up durations are the client's** (user asked for them per position, 2026-10-13): 0x1ee carries
  only serial + reward. Client 0x52ad90 -> room dialog vfunc 0x114 (0x777d00) -> 0x777d30 computes a float
  from the racer's place in the dialog's ranking list ([dlg+0x3bc]; 0 for the first entry, else from a
  client object at 0x96fb00, not read further) -> vfunc 0x118 (0x775c30, reward < 8): that float, if not 0,
  is the duration; if 0: with content flag BattleZone.NewGateEffect ([mgr+0x294] & 0x40000) off (what we
  send) Untouchable 5 s, Skid Rush / Hyper Boost 15 s; with it on, arg4 / NewGateEffectFactor (bits 19-28)
  + 10 s (Hyper, Untouchable, max 20 / 30) or + 5 s (Skid Rush), where arg4 is the 0 the 0x1ee handler
  passes. So the server can only switch NewGateEffect; no per-position duration can be sent.
- **Seat change** (user): a member clicking a free seat sends 0x270 (2011 only: u32 room, serial, seat),
  unanswered until now; the member is moved and the room gets 0x26d with the new seats *(our answer; 0x271,
  handler 0x52c420: u32 n + n x 24 bytes, is something else: per-member records with a name lookup)*.
  **Host auto-kick** (user): BS_Room::OnTick banishes the host when the room waits, has more than one
  member, everyone is ready and 15 s (0x3a98) pass without a start; rooms.Room.watch_start. Both
  script-tested with two clients, to be confirmed in game. (The same tick banishes members still loading
  after 80 s; here a loading over 120 s starts without them.)
- **Section rules** (user, 2026-10-13: Amateur V1-V3, Rookie V3-V5, Pro V4-V6, Star V6-V8, SuperStar
  V8-V9, no level limits): `Emulator/emulator.ini [battlezone]` `section.<PvP channel id> = name, lowest
  grade, highest grade, exp multiplier`; checked when a room is created or joined (rooms.car_allowed, the
  grade of the current car), refused with a text of ours. The 2008 server checks neither level nor car at
  0x1b8 (only channel <= 10). **Ids** (user + logs): 0 Amateur (2X), 1 Rookie (3X), 2 Pro (4X), 3 Star
  (6X), 4 SuperStar (8X), 5 Free, the order of pvpexprate.txt (2, 3, 4, 6, 8, 2); 6 was seen once (rooms
  of type 0x180, not identified). The exp multiplier comes from this table. All sections are opened for
  the client (NEW_FLAGS Channel4X / 6X / 8X = 1).
  **The client enables the section buttons itself** (0x59d0a0..0x59d26c): for each section Min<S>Grade
  <= the car's grade <= Max<S>Grade and the level <= Max<S>Level, S = Battle2X / 3X / 4X / 6X / 8X /
  BattleFree, read with 0x83aa50 from the client table **Localize\GlobalContent.xlt** (effective copy:
  Client/Patch/Patch.000, column Value_US). US values: grades 1-3 / 3-5 / 4-6 / 6-8 / 8-9 / Free 1-10 (what
  the user asked for), level caps 20 / 40 / 70 / 1000 / 1000 / 1000: a level 90 character only gets Free.
  Removing the caps means changing that client table (not done: a client file, the user decides).
- **Level caps in the client table**: rewriting Client/Patch/Patch.000 with agt.write zeroed header
  bytes 20-31 and other players' car thumbnails in ordinary rooms disappeared; the same rewrite with the
  original bytes 20-31 copied back works (user, caps lifted, thumbnails fine). PatchMod.000 is ignored by
  the client. The user then asked for the vanilla client: Patch.000 is original again; the working
  version is Server/backup/client_2011/Patch.000.levelcaps_1000 (copy it over Patch.000 to lift the caps).
  global_content.py still targets PatchMod.000 (does not work; to be changed to the Patch.000 method).
  Server side: optional level limits per section in emulator.ini (none set).
  Seat thumbnails, for the record: the room's add-member (0x778180) takes another member's car from the
  vehicles the client knows (0x53f880 by serial).
- **Battle tutorial prompt at every visit** (user): the decline (dialog button 0xea604) sends 0x104, which
  we record, but XiStrCharInfo.Flags was sent 12 bytes early (client reads it @0xed: 0x5a39e3). Fixed in
  records.Character.encode (12 more new bytes before the team dates; HancoinInven / Garage @0xe5 / 0xe9 and
  Guild @0xf1 move with it).
- **Spectators** (user): 0x1de JoinOBS answered with 0x26e + **0x1bf** (the 2011 OBSState, handler
  0x52e160; layout in rooms.Room.obs_state_frame), 0x1cb spectator count to the room, every room cast
  also went to the spectators; 0x1e0 leave, 0x1db / 0x1dc switch. In game (user): the spectator's client
  **raced** (it loads the track as a racer on 0x1e7). Now spectators get only 0x1bf refreshes (state,
  area; the handler passes room type, state, map and area on to the dialog, and treats state 4 apart)
  and the result 0x1ec. To be tested again.
- **Real Match, scoped only**: its lobby is PvP channel 6 and its rooms have type bit 0x100 (0x180 seen).
  The 2008 server sends 0x1c7 RealMatchInfo on entering such a room: the same stats, option bonuses,
  visual items and 8 parts for everyone (XiRealMatchStat, constants in ZoneServer.exe; the TW project's
  tools/patch_server_realmatch.py describes the 2008 message), on the schedule of realmatchtable.txt
  (weekday, hour) with 0x1c8 notices. 2011 0x1c7 (handler 0x52b480): 0x142 + (n - 1) x 0x4c with n @0xf2,
  so stats 104 @2, two bonuses 40 @0x6a / 0x92, XiVisualItem **56** @0xba, parts of 76 bytes @0xf6.
  The 2008 Real Match car (XiRealMatch::XiRealMatch, table at 0x700f20: item id, option A, option B):
  si_s02_001 a_00075 a_00054; si_s02_002 a_00060 a_00068; si_s02_003 a_00056 a_00035; si_s02_004 a_00080 -;
  si_a02_001 a_00075 a_00054; si_a02_002 a_00060 a_00068; si_a02_003 a_00056 a_00035; si_a02_004 a_00080
  a_00002; stats = XiVehicleTable::GetVehicleAbility of a car type / grade passed in + these parts
  (XiRealMatchStat::StatUpdate 0x5a0170). Open questions before writing it: the 76-byte part record of the
  2011 message, whether a Real Match room works without 0x1c7 (rooms of type 0x180 are created as
  ordinary rooms now), what the client's F1 does there (the user asked to check the "F1 car switch").
  **The "F1 event" car** (user: with the event on, everyone in a Real Match drives a Formula 1 car, not
  the Tamer / McLaren F1): the 2011 client has no such car. Its VehicleList has no formula car (146 player
  cars, models up to pc_0226; one special row 30001 "RacingBattleCar" = the Advance model) and no model
  file for one. The 2016 Dev Ed client has it: "Ferrari 60F1" = NSR05 / NSR05 ST / NSR05 BT, car types
  273-275, pc_0273s-pc_0275s.nif. What the 2011 client does have for Real Match: Data/effects.agt
  effects\realmatch\visual.xlt (16 rows of Color, Decal, DecalColor, Neon: a livery per seat) and number
  textures real_90000..90060.dds, switched by the content flag Etc.RealMatchEffect (group Etc 0x48, bit 29
  as far as flags_2011.tsv tells); 0x1c7 carries no car type.
  **Implemented (option 1, the user's choice): rooms.real_match_info / real_match_times.** 0x1c7 goes out
  before the room state on create and join for rooms of type & 0x100: based = car 50 ("Duel") grade 9 =
  (211, 229, 223, 137), equip = the eight parts' values (114, 94, 79, 84), no options yet (AssistA / B of
  the unit are sent 0), visual block 0; size checked against the client's formula (854 for 8 parts).
  emulator.ini [battlezone] realmatch = always | schedule | off, realmatch_minutes, realmatch_effect
  (Etc.RealMatchEffect, 3 bits @0x48 bit 29: client 0x6f85fb tests 0xe0000000; added to flags_2011.tsv).
  0x1b9 carries open / next opening; closed: no create, no start (a text of ours; error 20272 has no US
  text). 0x1c8 notices not sent. Not seen in game yet.
  User: the effect (liveries) works; a one-hour opening and weekday 0 = Sunday are right. **One car for
  everyone** (user): emulator.ini realmatch_car = car type, grade (default 50, 9). On entering the room the
  client gets 0x5a SelectCarAck with its current car record turned into that car (client 0x510ea0 copies
  the record into its current car and rebuilds it) + 0x425 to the others, the member's XiCarAttr in the
  room is set to it, and the real car comes back the same way on leaving (rooms.enter_real_match /
  exit_real_match). XiCarAttr 2011 = u16 0, u16 car type, u32 colour, u32 second colour (from the client's
  own requests). Script-tested; in game not yet.
  **Etc.RealMatchEffect sent at login emptied the car models in ordinary rooms** (user, right after it
  was switched on for everyone; the room messages were byte-for-byte as in the working session): now the
  flag is 0 at login and a second 0x1e GameSetting switches it on when the player enters a Real Match room
  and off when it leaves (rooms.enter_real_match / exit_real_match). *The cause is inferred from the
  timing, and a second 0x1e mid-session is untried: to be confirmed in game.* Also since then: spectate
  refusals with a message again, 0x1d0 "pages" = number of the last page.
  Lap Time (BS_Room::LapTime*, laptimeinfo.txt) not started.
- **Practice alone** (user, 2026-10-13, reversing the earlier PracticeMode=0 choice): a room with one
  member answers the start with 0x1e7 type 100 and stays waiting, so no go, gates, end or result
  (emulator.ini [battlezone] practice_alone = 1).
- **AI racers (first version, 2026-10-13)**: content flag BattleZone.FrontAi (emulator.ini [flags], now 1)
  makes the client show "AI Vehicles Activated"; with it, clicking a seat sends 0x26d with that seat =
  0xffff. The server then adds an AI member (serial = n << 16; the client treats serial > 0xffff as AI):
  0x1d4 like a player join + 0x271 (u32 n, n x 6 u32: key, AICarParam Idx, 0, level, 0, 0 - fields after
  the key guessed), a driver from the client's AICarParam.xlt near the host's level and one of its car
  types; joiners get 0x271 with the room's AIs. AIs are always ready, not waited for, not in results; a
  room with a player and an AI races (no practice). 0x21f (AI car moves, sent by 0x53a13d) is relayed on
  game and barea *(who drives AI cars is not confirmed)*. Script-tested up to the start; in game not yet.
- **AI racers parked** (user, 2026-10-13: AI drove on every screen in the original, so the server drove
  them; too much for now): seats and the room side work (after fixing the 0x271 fields: key, serial low
  word, AICarParam idx, car type, colour, colour 2; AI tracks = PVPTrackInfo "AI" = 1; player cars only),
  but the AI cars never move: the client sent no 0x21f at all. FrontAi = 0 again (emulator.ini [flags]);
  the code stays. Driving them means a server-side driver along the tracks' paths (race.py has the
  traffic paths) sending their moves to the room.
- **Lap Time (first version, 2026-10-13)**: `native/game/laptime.py` (docstring = the flow). The Lap Time
  button sends 0x1bb with filter 4 @0xf8 (was answered "no room": 20159). Arenas per car grade (room type
  0x40, 32 seats), 0x528 load (tracks 70-73 = PVPTrackInfo CityType 4, cities from laptimeinfo.txt),
  0x529 -> 0x52a / 0x52f, 0x52c lap records with exp / Mito per lap from laptimeinfo.txt, round end on the
  first finished last lap: 0x52d, 20 s, 0x52e result, 8 s, next track. Level limit per arena off by default
  (emulator.ini laptime_level_limit). **User-confirmed in game (2026-10-13)** after two fixes: start lap 0
  in 0x52a / 0x52f (1 made the client start at lap 2), and arenas skip the section car rules (they had
  channel 4 = SuperStar and refused V1 cars). AI is off (no seats added while FrontAi = 0), and the client
  setting BattleRoomAI = 0 (global_content.py; Patch.000 rewritten with its header bytes 20-31 kept)
  removes the AI seat option from Amateur..SuperStar rooms.
- **Lap Time traffic** (user: none): the client sends no 0x238 in a lap arena; race.py now attaches the
  arena's BArea to the track by map id (RaceTraffic.attach_map, lap_map_of) and re-attaches on a new
  round. In-process: cars around the lap (not at the start line, kept clear as in races).
- Not native: 0x1c7 RealMatchInfo (the 2008 server sent it on creating a room of type 0x180; not sent
  now), teams (0x26f, team rewards), observers, invitations, 0x1c9, 0x1d3 (car changed in the room),
  the traffic level from the room's map flag.
- Tests: `Handoff/scratchpad_session3/tests/rooms.py` (two clients: list, create, join, modify, ready,
  start, load, go, a move relayed in the BArea, gate, end, result and its rewards, leave, direct joins,
  banish, new master, a dropped connection).

## Client facts (2011 memory image, `Server/client_image/DriftCity_2011_unpacked.bin`)

- UI objects: game object `[0x948844]` (function 0x43aef0). Room dialog `[game+0x170]` (set by the
  0x1be handler from `[game+0x168]`, or `[game+0x16c]` for room type 0x40); its vtable (read from the
  running client) 0x8ecb90: +0x12c = 0x778980 (result parser), +0x34 = 0x7719d0. Battle zone lobby
  dialog `[ui+0x288]`, or `[ui+0x28c]` with BattleZone.BattleZoneReform = 1.
- Outgoing room messages are built at 0x7e8600-0x7eadb9 (`mov word ptr [..], 0x1b8 / 0x1cc / 0x1d4
  / 0x1d7 / 0x1bb / 0x1e6 / 0x26d`).
- `BattleZone.BattleZoneReform` (2 bits, 2011 only) is sent as 0 (the 2008 Contents.ini has no such
  flag). 1 switches the lobby dialog in the 0x1b9 and 0x1be handlers; not tried.
- Tools (dev venv): `Server/tools/dev/cimm.py IMAGE 0x1cc ...` (instructions using a value),
  `Server/tools/dev/ccalls.py IMAGE 0xADDR` (call sites), `mdis.py dis IMAGE ADDR N`. Reading the
  running client (`/proc/<pid>/mem`, needs `kernel.yama.ptrace_scope=0`) was how the dialog vtable
  was found; only read, never write (ASProtect checks the code: Error 45).

## Race traffic

- Today: BArea proxied; ZoneServer's own race traffic (`Server/server/TrafficServer.ini`
  Mode=native, `.index` / `.signal` files from the TW project's `make_traffic_paths.py`), driven by
  the room's max traffic / options from 0x238 SetAreaMap. Works on the tracks (user).
- Native BArea (written, not switched on): `Emulator/dcemu/native/area.py` (World(pvp=True): the area
  is the room id, moves go to the whole room) + `native/race.py`, which loads the TW project's
  engine (`Server/tools/traffic_server.py`, the Race class of its emulate mode; see "Traffic" in
  `../../Drift City 0.02/Server/README.md`) with the tracks from the 2011 PVPTrackInfo.xlt by column
  name (83 tracks with path files). Script-tested on test ports (room 909, map 1 -> track 0, 161
  cars). Switch: `barea = 11041 0 0`. Its traffic level is the engine's default (Medium); the room's
  map flag (0x26d) holds the level and is not passed to it yet.

## Open (in order of likely need)

1. A second player: native now (join, leave, banish, list entries, results with n > 1), to be tested
   with two real clients. Still open: 0x1d3 RoomNotifyChange (158 -> 236), 0x1da RoomClose.
2. Rewards: what the 2008 server gives for races with several players (0 for one).
3. 0x316 ChannelOwnershipListAck (1776 -> 1787 in the client's log; not room-related).
4. Real Match (room type 0x100, 0x1c7 RealMatchInfo 248 -> 14), observers (0x1df OBSState 405),
   channel battles (0x35c..0x393: done in session 22, game/channels.py), BattleZoneReform = 1.
5. Done in session 3: rooms and races in the native game service, native BArea (see above).
