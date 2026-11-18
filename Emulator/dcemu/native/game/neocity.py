"""Neo City (2016): the player car's HP, the chapter dungeon's party entry, chapter / quest flow and its
rewards, and the enemies / turrets / part repair of stage 3 (docs/NEOCITY.md; every client address below is of
the 2016 exe, image base 0x400000, and comes from docs/neo_work/NEO_PROTOCOL_A.md and NEO_PROTOCOL_B.md).

Neo City is the chapter-dungeon region where the player's car has HP that only that mode uses (Korean sources:
namu.wiki 스키드러쉬/게임 모드 1.9). The client keeps that HP in its stat object (0x760d30) XOR-protected: getter
0x760900 = [+0x1da4] ^ [+0x1da0], setter 0x760910 stores [+0x1da0] ^ value. It **reports** it about once a second:

C>S 0xf4d (6 bytes; 0x4430d0 -> 0x54c740 -> sender 0x866270): u32 = the car's current HP (getter 0x760900; sent only
    while that HP > 0 and the app flag [0x442790()+0x198] is set: the MissionBattleAdv content flag, filled at
    0x946dbc). The 0x111a (4378) in every 2016 log is such an HP, not a key (lead, 2026-11-14: stage 1 had read it
    as a XOR base and answered base ^ hp = 24378, which the client refused as > 20000).
S>C 0xf4e (6 bytes; handler 0x53e630): u32 HP, stored as is through the setter 0x760910 when 0 < HP <= 20000
    (0x4e20, 0x53e663); 0 / -1 store -1; anything else prints "Receive HP : %d" (0x956c90). The stored HP is
    applied to the car when it is created (0x4b5320: -1 = the car's max HP, vtable +0x60), so the server is
    where it survives a map change.

Ours: the last reported HP (1..20000) is kept per character and echoed back as is; nothing is answered before
the first report. The server never changes it itself: enemy damage happens in the clients (an explosion of an
enemy a client drives hurts that client's own car locally, 0x4e5bf0-0x4e5cc8; one reaching another player's car
is forwarded as 0xf4f -> 0xf50, stage 3 below), and the next report carries the result. damage() / heal() are
here so server-side enemy AI has one place to call.

Chapters and quests. The client's own tables are copied to server_data_2016/NeoData: NC_chapter.xlt and
NC_quest.xlt (UTF-16-LE with BOM, tab separated, cells may be quoted and hold newlines). A **chapter key** is a
chapter's 0-based position among the NC_chapter data rows (c_0000 -> 0, c_0008 -> 1, c_0005 -> 2, ...): the
client's [mgr+0x148] map is chapter key -> chapter object, filled by the NC_chapter.xlt loader 0x7ae1a0 with
the key = the data-row order. The **quest index** is a quest's 0-based order among the NC_quest rows of that
chapter. Every message below that NEO_PROTOCOL_A.md calls a "player serial" (0xe89 +0xa, 0xed8 +2, 0xed9 +2,
0xedc +2, 0xedd +2, 0xedf +2, 0xee3 +2, 0xee5 +2, 0xeea +2, 0xeec +2, 0xeee +2, 0xeda +2, 0xedb +2, 0xee4 +2,
0xef0 +2, 0xef2 +2, 0xee6 record +0) carries the chapter key instead (lead-verified field map). The real player
serial is only in 0xe88 +2, 0xe8b +2, 0xe8c +2, 0xee4 +0xe, 0xef0 +0xe, S>C 0xee5 +0xa and S>C 0xef1 +6.
Offsets are from the 2-byte type; the sizes include it.

A quest's **mission list** is its NC_mission.xlt rows in file order, **without** the `mission_type` `start`
rows (they only set the quest's start position, 0x7ae8e1..0x7af004) and the `patrol_pass` / `escort_pass`
rows (they are appended to their parent mission, 0x7aebc4). The client's **mission index** (activity+0x2c,
the u32 at +0xa of 0xeeb / 0xeef / 0xeee) is the 0-based position in that list; the type numbers
(NC_mission loader 0x75b020) are start 1, move 2, escort 4, escort_pass 5, collect 6, investigate 7,
patrol 8, patrol_pass 9, end 10, destroy 11. mission_of() resolves chapter + quest index + mission index
to the row (docs/neo_work/NEO_PROTOCOL_E.md 1.1).

Entry, in a party or alone (like game/undercity.py: suggest / agree / reject / load):
 C>S 0xe88 (68; sender 0x867a00) NeoCitySuggest: u32 own serial @2, u32 time (ms) @6, u32 @0xa, u32 CHAPTER KEY
     @0xe, u32 @0x12, u32 @0x16 (the chapter's member_check column); alone (no party or one member) the run is
     made at once and 0xe89 sent. In a party every member must be online in the same city and channel.
   -> S>C 0xe88 (68; handler 0x53e440) to every member: the first 0x18 payload bytes of the request, then the
     suggester's name at +0x1a (42 bytes) *(guess: NEO_PROTOCOL_A 3.1 proves 42 bytes copied and formatted
     into GlobalText 12313/12314, not that they are UTF-16-LE wchar[21])*. The client ignores its own (it sets
     a 15 s notice instead, 0x53e45f) and auto-rejects from the wrong UI state or when the suggester is not in
     its Neo party list (0x53e483 / 0x53e4b7). 15 s to answer: on timeout S>C 0xe8b (three zero u32) to all and
     the run is dropped.
 C>S 0xe8b (14; sender 0x867be0) reject: u32 serial @2, u32 reason 0..4 @6, u32 @0xa.
   -> S>C 0xe8b (14; handler 0x53e6c0) with the same 12 payload bytes to the party (texts 12315..12319); the
     run is dropped.
 C>S 0xe8c (18; sender 0x867c80) agree: four u32, +2 = own serial.
   -> S>C 0xe8c (18; handler 0x53e3c0) with the same 16 payload bytes to the party; every member agreed ->
     0xe89 to each of them.
 C>S 0xe8a (6; sender 0x867ac0) leaves the Neo area (the client's leave routine 0x788ae0 sends it, value 2 after
     a chapter give-up): the player leaves its run; a run with no member left is dropped.
 S>C 0xe89 (30; handler 0x53e400, the teleport/map load 0x788860) NeoCityLoad: u32 0 @2, u32 map selector @6
     (0..9; 6 NeoOros, 7 NeoCras, 8 NeoKoinonia, 9 NeoMoonPalace, jump table 0x788a2c), u32 CHAPTER KEY @0xa,
     u32 run id @0xe, 12 zero bytes @0x12. Ours: the selector comes from the chapter's city_ID; on sending it
     session.state['neo_run'] is the run and the player's kept Neo HP is forgotten (the new car reports it).

Chapter start, quests, missions (the client's activity object is [mgr+0x174], 0x7b5420):
 C>S 0xed8 (10; sender 0x84eaf0, its only caller 0x53e42c is inside the 0xe89 handler) u32 CHAPTER KEY,
     u32 run id -> S>C 0xed9 (18; handler 0x526ce0) key, 0, 0, run id. 0xed9 only installs the activity, it does
     not load a map (0x526cf9 -> 0x7b5420).
 C>S 0xedc (10; sender 0x84f070, the quest list's selection) u32 CHAPTER KEY, u32 quest index -> S>C 0xedd
     (10; handler 0x526d30) the same two u32, to the requester only (0x7b47a0 starts that quest in the activity).
 C>S 0xeeb (26; sender 0x84f8f0; all six send sites in NEO_PROTOCOL_E 1.2) six u32: key, quest, mission,
     value, then two more. **S>C 0xeea is not sent any more**: its result 1 sets [activity+0x9c] = 3
     (0x53400f) and the client's per-frame mission tick only runs while that flag is 2 (0x7a5aea), so it
     stopped the patrol / collect / investigate / destroy progress (0x7a5a90..0x7a5b22). New rule: when
     +0x12 or +0x16 is non-zero the message is a destroy KILL report (0x5132ae, once per destroyed enemy, only in
     a type 11 mission) -> S>C 0xeec **echoing the request's 24 payload bytes unchanged** (the matcher 0x53cd90
     reads the HUV group / level in the last two u32, so they must survive), and the server's own count -> 0xeee at
     param_2 kills (destroy_kill);
     otherwise S>C 0xeec (26; handler 0x53cee0) key, quest, mission, u32 param1 = the request's +0xe,
     u32 param2, u32 @0x16, u32 @0x1a — also the request's own bytes: harmless for every type (patrol needs it to
     set the point bit, 0x538de0; collect / investigate only store it in activity+0x64 / +0x7c). Then, by the row's type from NC_mission.xlt: collect (6), when value >= param_2
     (a required count <= 0 means 1), and investigate (7), when value == 1, get S>C 0xeee (14; handler
     0x521940) once per (quest, mission) per run; patrol, move and unknown / out of range get nothing more.
 C>S 0xeef (14; sender 0x84fbd0) three u32 -> S>C 0xeee (14; handler 0x521940) the same 12 payload bytes (the
     mission is done, 0x79f640); the (quest, mission) is marked done so a later 0xeeb sends no second 0xeee.
 C>S 0xeed (14; sender 0x84fa70) mission-complete parameters: logged only. It is **not** answered with 0xeec
     (the client then clears its own per-mission counters, 0x5a47e6-0x5a4836); 0xeec is sent from 0xeeb
     instead. Its per-mission-type fields (types 6..11 write activity+0x64 / +0x7c / patrol bits / the 11
     picker) are still not decoded.
 C>S 0xede (14; sender 0x84f1d0) u32 key, u32 quest index, f32 seconds (the activity's elapsed time) -> the quest
     reward from NC_quest: exp, Mito and up to 3 items (reward_item_01..03, 'n/a' = none):
     progress.add_exp, items.add_money, rewards.give for the items known in context.data.item_index,
     play_mode(c, 'NEOCITY'), then S>C 0xedf (58; handler 0x533cb0):
       u32 key @2, u32 quest @6, u32 exp gained @0xa, u32 Mito gained @0xe,
       u64 exp @0x12, u64 exp_next @0x1a, u64 exp_base @0x22 (the 2016 widths: pack_exp, as mothers' 0x7d1),
       u16 level @0x2a, u16 item count @0x2c (<= 3), 3 x u32 item TableIdx @0x2e.. (0 = unused).
     After it login.stat_frames(p) and the inventory frames rewards.give gained (mod_list, as jobs.py does).
     A quest is rewarded at most once per run.
 C>S 0xeda (10; sender 0x84edb0, its only caller 0x533e61 is in the 0xedf handler when the chapter's last quest
     closed) u32 CHAPTER KEY, u32 run id -> chapter cleared: SKID_QUEST_TB gets QUESTID = 'neo_' + the chapter
     id ('neo_c_0000'), STATE 2, FAILNUM = the clear count (+1; insert when missing), the chapter's
     chapter_summary_reward EXP and Mito go through add_exp / add_money with 0x7d1 / 0x7d2 exactly as
     mothers.mother_complete, then S>C 0xedb (203 bytes; handler 0x52e960; its size is (n-1)*0x10 + 0xcb with
     n = 1): u32 key, u16 1, u16 0, u8 0, then zero bytes to the end *(guess: the client reads a name at +0xb
     and n x 0x10 records from +0xbb, neither is decoded yet)*. Once per run.
 C>S 0xee7 (18; sender 0x84f780) quest-list request -> S>C 0xee6 (6 + 28 n; handler 0x52ea00): u16 n, u16 0,
     then n records of 28 bytes: u32 CHAPTER KEY @0, u16 clear count @0x14 (> 0 = cleared), rest 0 — one per
     chapter the character has cleared (n may be 0; SKID_QUEST_TB 'neo_*'). The handler 0x52ea00 **destroys**
     the client's activity ([mgr+0x174] = 0, 0x7ad070), so it is never sent while the player has a run; it is
     not sent at login either (no login hook to add it to: login.py calls each module's on_login itself).
 C>S 0xee8 (10; sender 0x84ef10, the chapter-reward window) u32 -> S>C 0xee9 (262; handler 0x526d80): that u32
     and 256 zero bytes (16 empty 16-byte reward slots; the per-slot meaning is not decoded) *(guess: the
     empty-slot content)*.
 C>S 0xee2 (18; sender 0x84f330) quest failed -> S>C 0xee3 (10; handler 0x526db0) the request's u32 @0 and @4.
 C>S 0xee4 (18; sender 0x84f4a0, the give-up button 0x721ede) key, quest, mission, u32 serial @0xe -> S>C 0xee5
     (14; handler 0x526e10) key, quest, the serial that gave up (from the request's payload +0xc) to every run
     member (the client shows text 12311 to everyone but that serial).
 C>S 0xef0 (18; sender 0x84f610, the chapter give-up button 0x721f3d) the same four fields -> S>C 0xef1 (10;
     handler 0x533e70) u32 0, the serial (the request's payload +0xc) to every run member; that player leaves
     the run (its client runs the leave routine 0x788ae0 and then sends 0xe8a).
 C>S 0xef2 (14; sender 0x84e830; 0x788f5d sends 0 = died, 0x78907b 1 = alive again) key, u32 flag, u32.
     Flag 0 -> S>C 0xef3 (14; handler 0x526ec0) u32 0, u32 1, u32 0 to that player (the death text, GlobalText
     12301); flag 1 -> the kept Neo HP is forgotten (the revived car reports it).
 C>S 0xef5 (10; sender 0x84ec50, the chapter bonus window) -> S>C 0xef6 (14; handler 0x5218e0) u32 0, u32 0,
     u32 0 (the client shows "count / 10" from +0xa) *(guess: the three values; the sender's fields are not
     decoded)*.

Stage 3 — enemies, turrets, part repair (docs/neo_work/NEO_PROTOCOL_B.md; its addresses are the 2016 exe's).
The client's Neo tables (NC_objectDef.tsv, NC_HuvRand.tsv, NeoHuvParam.xlt) are never sent: what travels is the
numeric **Huv Param ID** (an NC_HuvRand row, 100001..), and the client resolves it locally (0x4eda00). The
0xc7 handler 0x53baf0 is gated by app state 0x13 or the area id in 84..99 (0x53bb05); 0xcd 0x525a10 and 0xce
0x525d60 by app state 0x14; 0xcf 0x526000, 0xd0 0x52e2f0, 0xf42 0x53edd0, 0xf3f 0x5259f0 and 0x4c5 0x52a870
have no state gate. One run = one party, so every relay goes to the run's members (r.cast / r.others).
 C>S 0xc6 (0xa + 0x40 n; maker 0x85dd50, writer 0x865e60) the client's "spawn these Neo enemies" request:
      u32 time @2, u32 n @6, n x 0x40 records @0xa. The record (its builder is 0x4eeaa0) has u16 kind @0
      (1/2/3 = the client's internal classes), u16 serial @8, u16 @0xa, u32 Huv Param ID @0xe, u32/u16 block
      @0x12..0x1a, xyz @0x20, u32 @0x30, u32 @0x34, u32 @0x38; the client itself leaves @0x08, @0x0a, @0x30
      and @0x34 zero.
   -> S>C 0xc7 (0xc + 0x40 n; handler 0x53baf0) to EVERY run member: the request's u32 time @2, u32 n @6,
      u16 0 @0xa, then the records from +0xc. Each record is copied as the client sent it, except u16 @0x08 =
      the sender's serial when 0, u16 @0x0a = the run's next enemy number (the handler skips a record whose +0xa is 0,
      0x53bd0c-0x53bd11 with the record at ebx-0x3c; it was forced to 0, so no enemy ever spawned; and
      (+0x0a << 16) | +0x08 is the client's actor key, so it must differ per enemy: ENEMY_FIRST), u32 @0x30 = the run's CHAPTER KEY when 0 (the handler compares it with
      [activity+0x24], which is the chapter key — not an owner serial; lead's correction to NEO_PROTOCOL_B
      1.1 / 5.2) and u32 @0x34 = the quest index (0 without a quest) when 0. The record fields @0x12..0x1a are
      left exactly as the client sent them *(guess: NEO_PROTOCOL_B 5.2 says they are HP/level copied into the
      actor by 0x4edaf0; the client's own 0xc6 leaves them 0, so which one is HP is not proven)*. n is
      clamped to the records the payload really holds. The records are kept on the run (run.enemies, at most
      512) so a member who reloads can be sent them later.
 C>S 0xc2 (18; maker 0x85dc40, writer 0x865d50) the car's position, 4 x f32 @2 -> no answer; kept on the
      session as session.state['neo_pos']. **The 0xc2 handler is undercity.py's (the 2011 HuvParam) and is
      registered on the same SVC, so neocity does not register it again**; store_position() is the call that
      lets it feed a Neo run (the one-line change in undercity.huv_param is left to the lead).
 C>S 0xcd (42; maker 0x85def0, writer 0x866020) a hit: u16 hitter serial @2, u16 @4, u16 victim key lo @6,
      u16 key hi @8, u16 @0xa, i32 HP left @0xc, i32 damage @0x10, u16 @0x14 (> 0 = the client's UI notice),
      u16 @0x16, u16 flag @0x18; @0x1a..@0x29 are not written by the client.
   -> S>C 0xcd (42; handler 0x525a10) to EVERY run member, the sender included (it compares +2 with its own
      serial): +2..+0x19 copied, then i32 Mito 0 @0x1a, i64 0 @0x1e, i32 exp 0 @0x26 — the rewards travel
      with the kill (0xce below). Logged only when the HP left is <= 0 (the relay can be very frequent).
 C>S 0xce (64; maker 0x848c90) a kill: u16 key lo @2, u16 key hi @4, u32 serial @6 (+0xa..+0x35 unread),
      u32 Huv Param ID @0x36, u32 the HUV record's +0xac @0x3a, u16 killer serial @0x3e.
   -> S>C 0xce (64; handler 0x525d60) the same 62 payload bytes to EVERY run member; then the sender (the
      killer) is paid: exp = the Huv Param's level x KILL_EXP_PER_LEVEL and Mito = level x
      KILL_MITO_PER_LEVEL (**10 and 10 are THE EMULATOR'S OWN amounts: no client table has kill amounts**;
      the level is NeoHuvParam.xlt column 2), add_exp / add_money and 0x7d1 / 0x7d2 exactly as
      chapter_complete, play_mode(c, 'NEOCITY'); then the reward group of column 18 ('n/a' = none, expanded by
      .driftuse.roll): the first NormalItem / SkidItem that context.data.item_index knows goes through
      rewards.give, followed by items.mod_list. A (lo, hi) enemy pair is paid once per run (run.killed), so
      duplicate reports are relayed but not paid twice. The Huv Param ID comes from the run's own spawn record for
      the report's actor key (record +0x0e); only when that record is unknown is the client's +0x34 used, which a
      HUV fills with its **model** (19040 / 19041 / 19104 = HUV-MRL / APS / HMG), not a Huv Param ID — those kills
      paid nothing before 2026-11-17. An unknown ID is relayed and logged only.
 C>S 0xcf (11; maker 0x85dff0) targeting / C>S 0xd0 (16; maker 0x85e070) aggro -> S>C 0xcf (11; handler
      0x526000) / S>C 0xd0 (16; handler 0x52e2f0) the same bytes to every OTHER run member (not the sender).
      Neither is logged: both can be very frequent.
 C>S 0xf41 (maker 0x848e30) turret request: u32 n @2, u16 kind @6, u16 objective id @8, n x 12 bytes @0xa.
      The declared size is 0xa + 12 n but the client reserves only 22 bytes for every n (0x848f25), so n is
      clamped to what the payload holds.
   -> S>C 0xf42 (0xa + 0x10 n; handler 0x53edd0) to EVERY run member: u32 n @2, the request's u16 @6 and
      u16 @8, then per turret 16 bytes: u16 the sender's serial, u16 a per-run id (from 1), then the request's
      12 bytes *(guess: the 12 bytes are the turret's position; only "3 dwords copied" is proven)*.
 C>S 0xf43 (4; maker 0x849090) a turret's u16 @2 (the client sends [turret+0x62], only while it operates the
      turret): logged only. *(guess: the fire/use notification; no answer is known. 0xf44, the switch, is not
      sent, so a turret never changes hands.)*
 C>S 0xf3e (2; maker 0x85dde0) -> S>C 0xf3f (2; handler 0x5259f0) to EVERY run member: the client deletes its
      scripted Neo HUVs.
 C>S 0x4c4 (6; maker 0x852c80) part repair: u32 item id @2 -> S>C 0x4c5 (10; handler 0x52a870): u32 item id,
      u32 1 (only result 1 acts, 0x52a874). Answered outside a run too. Nothing is charged or saved: the
      emulator keeps no Neo part durability, so the repair is free (logged).
 C>S 0xc8, 0xd1, 0xf40, 0xf49, 0xf4a, 0xf4c, 0xfbf: registered so they stop being "no handler"; each writes
      one log note with its payload (at most 64 bytes) and no answer (NEO_PROTOCOL_B / E pair none of them
      with a proven S>C message; 0xfbf would be answered with 0xf50, a guess, not sent).
 C>S 0xf4f (18; writer 0x8662b0, built at 0x4e5ccd-0x4e5cfe) an explosion a client drives reached ANOTHER
      player's car: u16 the victim's key low @2, u16 the shooter's key high @4, u32 effect id @6, f32 radius
      @0xa, f32 distance @0xe.
   -> S>C 0xf50 (18; handler 0x53ecb0, "create this explosion at this actor and damage the local player") to
      that run member ONLY: u16 its serial (the request's +2), u16 VICTIM_SORT, then the request's 12 bytes
      at +6..+0x11 unchanged (effect id, radius, distance — the client computes the damage itself,
      0x53ed7c-0x53edc4). VICTIM_SORT = 1 is the car sort a player's own car has in every move it sends
      (area.py) *(guess)*. Not found / the sender itself: dropped, one log note per run; forwards are not
      logged (they can be frequent), only counted on the run (run.hits). The server's HP value is not
      changed by a forwarded hit, so a later 0xf4d poll still answers full HP.
 Enemy attacks on players are S>C 0xfc0 (6; handler 0x53eb50, +2 f32 damage) and S>C 0xf50 (above).
 0xfc0 is **NOT sent: the server has no enemy AI yet, so no enemy damages a player.** The Neo HP follows the
 client's own reports (0xef2 / 0xef3, stage 2) and the forwarded 0xf50, which the client applies locally.

Areas (area.py enter_area): a car whose game session has state['neo_run'] (looked up by the entering car's
serial, because the area connection keeps its own state — as undercity.uc_area_key does) is keyed
('neo', area, run id) — one area instance per run — and gets no city traffic. Which area number the 2016
client enters after 0xe89 is not known yet.

Stages 1..3 are here; not done: the enemy AI (and with it 0xfc0, so no enemy damages a player), the bonus
missions (0xef6's count), the chapter-reward slots, the destroy mission's param1 / param2 pair (a guess:
the NC_object +0xac / +0xae ids, so 0xeec type 11 matches nothing for now), and sending run.enemies to a
member who reloads.
"""
import asyncio
import csv
import io
import itertools
import os
import random
import re
import struct
import time

from ...handlers import on, on_open
from ...protocol import C2S
from ...wire import Frame
from .. import context
from .items import add_money
from .login import SVC, send, serial_of, stat_frames
from .progress import add_exp, play_mode
from .records import pack_exp

MAX_HP = 20000                      # the client's own bound on the answer (0x53e663)
_hp = {}                            # (server id, cid) -> current HP; absent = full

AGREE_SECONDS = 15.0                # the client's own notice timer (0x41700000 = 15.0 s, 0x53e477)
MAPS = {'NeoOros': 6, 'NeoCras': 7, 'NeoKoinonia': 8, 'NeoMoonPalace': 9}       # 0x788a2c (0x788968..)
CHAPTERS_FILE, QUESTS_FILE = 'NC_chapter.xlt', 'NC_quest.xlt'
MISSION_FILE = 'NC_mission.xlt'     # columns: 1 quest_ID, 2 mission_ID, 9 mission_type, 10 param_1, 11 param_2
MISSION_TYPES = {'start': 1, 'move': 2, 'escort': 4, 'escort_pass': 5, 'collect': 6, 'investigate': 7,
                 'patrol': 8, 'patrol_pass': 9, 'end': 10, 'destroy': 11}        # 0x75b020 (NEO_PROTOCOL_E 1.1)
MISSION_ROW_ONLY = ('start', 'patrol_pass', 'escort_pass')  # rows that are not entries of a mission list
VICTIM_SORT = 1                     # *(guess)*: the car sort of a player's own car (area.py)
CHAPTER_DONE = 2                    # SKID_QUEST_TB STATE, as mothers.DONE
LOAD_SQL = ("SELECT QUESTID, FAILNUM FROM SKID_QUEST_TB"
            " WHERE SERVERID=%s AND CID=%s AND QUESTID LIKE 'neo\\_%%'")
SAVE_SQL = ("UPDATE SKID_QUEST_TB SET STATE=%s, FAILNUM=%s, LASTDATE=GetDate()"
            " WHERE SERVERID=%s AND CID=%s AND QUESTID=%s",
            "INSERT INTO SKID_QUEST_TB(SERVERID, CID, CNAME, QUESTID, STATE, FAILNUM, PLACEIDX)"
            " VALUES (%s,%s,%s,%s,%s,%s,0)")
REWARD_TEXT = re.compile(r'reward\s+(exp|mito)\s*:\s*([\d,]+)', re.I)
HUV_FILE = 'NeoHuvParam.xlt'        # Init/: column 1 Huv Param ID, 2 level, 4 HUV Name, 18 reward group ('n/a')
ENEMY_CAP = 512                     # 0xc6 records kept per run, for a member who reloads
ENEMY_FIRST = 0x100                 # record +0x0a of a run's first enemy: (+0x0a << 16) | +0x08 is the client's actor
                                    # key (0x523483 -> 0x558e65); +0x08 = the owner's serial (0x5237d1: the owner's
                                    # client runs the AI). One +0x0a for all made 25 enemies one actor (client log:
                                    # "Already huv have control" x24, 0x45e7c2; NEO_VISIBLE.md)
KILL_EXP_PER_LEVEL = 10             # THE EMULATOR'S OWN kill amounts: no client table has them (NEO_PROTOCOL_B 5)
KILL_MITO_PER_LEVEL = 10

runs = {}                           # run id -> Run
START_ENTRY = 1                     # 0xe89 / 0xed9 +0xe: activity +0x34 (send_load)
_run_ids = itertools.count(1)
_chapters = _quests = _missions = _huvs = _objects = _huv_rand = None
OBJECT_FILE, HUV_RAND_FILE = 'NC_object.xlt', 'NC_HuvRand.xlt'
ENEMY_KINDS = {'NEO_HUB': 1, 'NEO_HUV': 0}   # NC_object object_type -> record u16 @0 (NEO_SPAWN.md 2.1)
POSITION = re.compile(r'(\d+)\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\)')


def is_on():
    from ..version import is_2016
    return is_2016()


# ---- Neo HP (0xf4d / 0xf4e) ------------------------------------------------------------------------------

def _key(session):
    p = session.state.get('player')
    return (context.db.server_id, p.char.cid) if p else None


def hp_of(session):
    """The last HP this character reported (0xf4d), or None before the first report."""
    key = _key(session)
    return _hp.get(key) if key else None


def set_hp(session, hp):
    key = _key(session)
    if key:
        _hp[key] = max(0, min(MAX_HP, int(hp)))


def forget_hp(session):
    """A new car (a Neo load, a revival): its next report sets the HP again."""
    key = _key(session)
    if key:
        _hp.pop(key, None)


def damage(session, amount):
    """The car takes `amount`; -> the HP left (None when no HP was reported yet)."""
    hp = hp_of(session)
    if hp is None:
        return None
    set_hp(session, hp - max(0, int(amount)))
    return hp_of(session)


def heal(session, amount):
    hp = hp_of(session)
    if hp is None:
        return None
    set_hp(session, hp + max(0, int(amount)))
    return hp_of(session)


@on(SVC, C2S, 0xf4d)
async def hp_sync(session, frame):
    """C>S 0xf4d: the car's HP report (its max HP after each 0x2f8: 0x4b3d20 -> 0x788750 = 0x2f8 dword 20 + the parts'
    own Neo option sum at record +0x9e4, which the server cannot change; docs/neo_work/NEO_HP.md) -> kept, and S>C 0xf4e.
    The client's handler stores 1..20000 as is (0x53e663) and 0 / -1 as -1 (0x53e69f), and -1 means "the car's own
    HP" (0x4b5328). A strong car reports more than 20000 (Xerender's 45936, user 2026-11-14): no answer left its HP
    unset (entered Neo City destroyed), a capped 20000 left it below its max, so the damage state never reset
    (0x4b3d5f: only when HP >= max); it gets 0 = its own HP."""
    if not is_on() or len(frame.payload) < 4:
        return
    hp, = struct.unpack_from('<i', frame.payload)
    if hp <= 0:
        return
    set_hp(session, min(hp, MAX_HP))
    send(session, Frame(0xf4e, struct.pack('<i', hp if hp <= MAX_HP else 0)))
    r = run_of(session)
    if r is not None and not getattr(r, 'hud_drawn', False) and session.state.get('player'):
        # the first report inside the run comes after the Neo area loaded: the stat frames once more, so the client
        # draws the HP HUD from the car (0x2f8 -> 0x4b3d20 -> 0x596d40); sent after 0xedd it came before the area
        # and the bar stayed empty at the start (user, 2026-11-14)
        r.hud_drawn = True
        for f in stat_frames(session.state['player']):
            send(session, f)


# ---- the client's tables (NC_chapter.xlt / NC_quest.xlt) ------------------------------------------------

def _cell(row, i):
    return row[i].strip() if i < len(row) else ''


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _summary(text):
    """chapter_summary_reward ("Reward EXP : 5000 ... Reward MITO : 5000") -> (exp, Mito), 0 when absent."""
    found = {k.lower(): int(n.replace(',', '')) for k, n in REWARD_TEXT.findall(text or '')}
    return found.get('exp', 0), found.get('mito', 0)


def _rows(path):
    """A table's data rows: UTF-16-LE with BOM, tab separated, a quoted cell may hold newlines; the header is
    the first row whose first cell is 'index' (NeoHuvParam.xlt has two rows above it)."""
    with open(path, 'rb') as f:
        text = f.read().decode('utf-16-le').lstrip('\ufeff')
    rows = list(csv.reader(io.StringIO(text), delimiter='\t'))
    start = next((i for i, r in enumerate(rows) if r and r[0].strip().lower() == 'index'), None)
    if start is None:
        raise ValueError(f'{path}: no header row (a first cell "index")')
    return [r for r in rows[start + 1:] if r and r[0].strip()]


def _read(name):
    """A NeoData table's data rows."""
    return _rows(os.path.join(context.data.root, 'NeoData', name))


def chapters():
    """NC_chapter.xlt's data rows, keyed by the client's chapter key = the 0-based data-row order."""
    global _chapters
    if _chapters is None:
        out = []
        for key, r in enumerate(_read(CHAPTERS_FILE)):
            exp, mito = _summary(_cell(r, 9))
            out.append(dict(key=key, id=_cell(r, 4), title=_cell(r, 5), city=_cell(r, 2),
                            member_check=_int(_cell(r, 11)), level_low=_int(_cell(r, 16)),
                            level_high=_int(_cell(r, 17), 999), exp=exp, mito=mito,
                            reward_group=_cell(r, 18)))           # result_rewardGroup (NEO_CLEAR_PROTOCOL 8.3)
        _chapters = out
    return _chapters


def quests():
    """NC_quest.xlt's data rows; a quest's index is its 0-based order among its chapter's rows."""
    global _quests
    if _quests is None:
        _quests = [dict(chapter=_cell(r, 1), id=_cell(r, 2), title=_cell(r, 3), exp=_int(_cell(r, 6)),
                        mito=_int(_cell(r, 7)), objects=_cell(r, 5),
                        items=[c for c in (_cell(r, 8), _cell(r, 9), _cell(r, 10))
                               if c not in ('', 'n/a', '0')])
                   for r in _read(QUESTS_FILE)]
    return _quests


def chapter_by_key(key):
    table = chapters()
    return table[key] if 0 <= key < len(table) else None


def quests_of(chapter):
    return [q for q in quests() if q['chapter'] == chapter['id']]


def missions():
    """NC_mission.xlt's data rows keyed by quest_ID, in file order."""
    global _missions
    if _missions is None:
        out = {}
        for r in _read(MISSION_FILE):
            kind = _cell(r, 9)
            out.setdefault(_cell(r, 1), []).append(
                dict(id=_cell(r, 2), type=kind, number=MISSION_TYPES.get(kind, 0),
                     param_1=_cell(r, 10).split(), param_2=_int(_cell(r, 11))))
        _missions = out
    return _missions


def mission_of(chapter, quest_index, mission_index):
    """The mission the client's mission index names (activity+0x2c, the +0xa of 0xeeb / 0xeef / 0xeee) ->
    dict(type, number, param_1, param_2) or None. A quest's mission list is its NC_mission rows in file
    order without the `start` rows (they only set the quest's start position, 0x7ae8e1..0x7af004) and the
    `patrol_pass` / `escort_pass` rows (they are appended to their parent mission, 0x7aebc4)."""
    if chapter is None:
        return None
    table = quests_of(chapter)
    if not 0 <= quest_index < len(table):
        return None
    rows = [m for m in missions().get(table[quest_index]['id'], ()) if m['type'] not in MISSION_ROW_ONLY]
    return rows[mission_index] if 0 <= mission_index < len(rows) else None


def huv_params():
    """Init/NeoHuvParam.xlt: Huv Param ID -> level, name and reward group (the 2016 client resolves the ID in
    its own NC_HuvRand table, 0x4eda00; this is the server's copy of the same rows)."""
    global _huvs
    if _huvs is None:
        out = {}
        for r in _rows(os.path.join(context.data.root, 'Init', HUV_FILE)):
            i = _int(_cell(r, 1))
            if i:
                out[i] = dict(level=_int(_cell(r, 2)), model=_int(_cell(r, 3)), hp=_int(_cell(r, 13)),
                              name=_cell(r, 4), reward=_cell(r, 18),
                              kind=kill_class(_int(_cell(r, 5)), _cell(r, 4)))
        _huvs = out
    return _huvs


def objects():
    """NC_object.xlt's enemy rows (NEO_HUB / NEO_HUV) by Group ID: dict(index, kind, create, regen_num, regen_time,
    positions=[(pos group, x, y, z, heading)]). BUILDING / TURRET rows have another position format and travel by
    other messages; they are left out."""
    global _objects
    if _objects is None:
        out = {}
        for r in _read(OBJECT_FILE):
            kind = ENEMY_KINDS.get(_cell(r, 3))
            if kind is None:
                continue
            pos = []
            for i in range(10, 10 + min(_int(_cell(r, 9)), 10)):
                m = POSITION.fullmatch(_cell(r, i).strip('"'))
                if m:
                    pos.append((int(m[1]),) + tuple(float(v) for v in m.groups()[1:]))
            out.setdefault(_cell(r, 1), []).append(dict(
                index=_int(_cell(r, 0)), kind=kind, create=_cell(r, 4), regen_num=_int(_cell(r, 6)),
                regen_time=float(_cell(r, 7) or 0), positions=pos))
        _objects = out
    return _objects


def huv_rand():
    """NC_HuvRand.xlt: position group -> [(Huv Param ID, probability)]."""
    global _huv_rand
    if _huv_rand is None:
        out = {}
        for r in _read(HUV_RAND_FILE):
            out.setdefault(_int(_cell(r, 1)), []).append((_int(_cell(r, 3)), max(_int(_cell(r, 5)), 0)))
        _huv_rand = out
    return _huv_rand


def pick_huv(group, rng=random):
    """One Huv Param ID of a position group, weighted by Probability (the client accepts any id of the group)."""
    rows = [(i, w) for i, w in huv_rand().get(group, ()) if i in huv_params()]
    if not rows:
        return None
    return rng.choices([i for i, _ in rows], weights=[w or 1 for _, w in rows])[0]


def spawn_records(chapter, quest, serial, create='Q_START', rng=random, numbers=None):
    """The 0xc7 messages the client itself asked for with 0xc6 when +0xe of 0xe89 / 0xed9 was 0 (NEO_SPAWN.md 1.3,
    3.2; one rebuilt record was byte-identical to a logged one): per NC_object row of the quest's object_group_ID with
    this create_type, one message of object_num records. Record (0x40): u16 kind (1 HUB / 0 HUV), u16 position index,
    u16 level, u16 HUV model, u16 owner serial, u16 enemy number (@0xa, from `numbers`, never 0: the handler skips
    0, 0x53bd0c; with @0x08 the client's actor key), u16 HP, u32 Huv Param ID,
    u32 position group, u16 NC_object index, u16 regen_num, f32 regen_time, u16 1, f32 x, y, z, heading, u32 chapter
    key, u32 quest, u32 0, u16 0 (@0x3c: non-zero parks the actor, 0x53bec7), 2 bytes 0. -> [bytes records]."""
    table = quests_of(chapter)
    if not 0 <= quest < len(table):
        return []
    numbers = numbers if numbers is not None else itertools.count(ENEMY_FIRST)
    out = []
    for row in objects().get(table[quest]['objects'], ()):
        if row['create'] != create:
            continue
        recs = b''
        for i, (group, x, y, z, h) in enumerate(row['positions']):
            pid = pick_huv(group, rng)
            if pid is None:
                continue
            huv = huv_params()[pid]
            recs += struct.pack('<6HHIIHHfH4fIII2x2x', row['kind'], i, huv['level'], huv['model'], serial & 0xffff,
                                next(numbers) & 0xffff or 1,
                                min(huv['hp'], 0xffff), pid, group, row['index'], row['regen_num'],
                                row['regen_time'], 1, x, y, z, h, chapter['key'], quest, 0)
        if recs:
            out.append(recs)
    return out


def enemy_numbers(r):
    """The run's enemy numbers (record +0x0a), unique within the run, 0 skipped."""
    while True:
        n = r.enemy_no
        r.enemy_no = n % 0xffff + 1
        yield n


def clear_enemies(r):
    """Remove the enemies the run spawned so far: S>C 0xce (handler 0x525d60: actor by key (+2, +4) -> state 2,
    dying) per kept record, no killer. The client has no other way to drop a server-spawned group (its own
    delete_type machinery only runs in the +0xe = 0 flow; 0xf3f flushes only what the client staged:
    NEO_HUBCRASH.md 3). Without it Q1-Q3 stacked three HUBs at 1084(1719.6,5623.5). The keys go into r.killed, so a
    kill report that comes back for them pays nothing."""
    n = 0
    for rec in r.enemies:
        lo, hi = struct.unpack_from('<HH', rec, 8)
        huv_id, = struct.unpack_from('<I', rec, 0xe)
        r.killed.add((lo, hi))
        body = bytearray(0x3e)
        struct.pack_into('<HH', body, 0, lo, hi)
        struct.pack_into('<I', body, 0x34, huv_id)
        r.cast(Frame(0xce, bytes(body)))
        n += 1
    r.enemies = []
    return n


def spawn(session, r, quest):
    """Send the quest's enemies to every run member (0xc7), kept on the run for a member who reloads; the previous
    quest's enemies are removed first (clear_enemies)."""
    gone = clear_enemies(r)
    if gone:
        session.log.note(f'neocity: {gone} enemies of the previous quest removed (0xce) in run {r.id}')
    msgs = spawn_records(r.chapter, quest, serial_of(session), numbers=enemy_numbers(r))
    for recs in msgs:
        n = len(recs) // 0x40
        r.enemies.extend(recs[i * 0x40:(i + 1) * 0x40] for i in range(n) if len(r.enemies) < ENEMY_CAP)
        r.cast(Frame(0xc7, struct.pack('<IIH', int(time.monotonic() * 1000) & 0xffffffff, n, 0) + recs))
    if msgs:
        session.log.note(f'neocity: quest {quest} enemies: {sum(len(m) // 0x40 for m in msgs)} in {len(msgs)} '
                         f'message(s) (run {r.id})')


def kill_class(huv_type, name):
    """The CHAPTER CLEARED window's kill column of an enemy: NeoHuvParam "Huv Type" 0 = HUB, else HUV, with the HUS
    (type 1 like the HUV) told apart by its name (NEO_CLEAR_PROTOCOL 8.1)."""
    n = (name or '').strip().upper()
    if n.startswith('HUS'):
        return 'HUS'
    if huv_type == 0 or n.startswith('HUB') or 'HUB' in n.split():
        return 'HUB'
    return 'HUV'


# ---- the chapter clears kept in SKID_QUEST_TB ------------------------------------------------------------

async def cleared(p):
    """-> p.neo_cleared {chapter key: clear count} from the rows QUESTID 'neo_<chapter_ID>' (FAILNUM)."""
    if getattr(p, 'neo_cleared', None) is None:
        db = context.db
        found = await db.rows(LOAD_SQL, (db.server_id, p.char.cid))
        by_id = {c['id']: c['key'] for c in chapters()}
        p.neo_cleared = {}
        for qid, failnum in found or []:
            key = by_id.get(qid[len('neo_'):]) if qid and qid.startswith('neo_') else None
            if key is not None and _int(failnum) > 0:
                p.neo_cleared[key] = _int(failnum)
    return p.neo_cleared


async def _save(p, chapter, count):
    db, c = context.db, p.char
    qid = 'neo_' + chapter['id']
    await db.update_or_insert(SAVE_SQL[0], (CHAPTER_DONE, count, db.server_id, c.cid, qid),
                              SAVE_SQL[1], (db.server_id, c.cid, c.name, qid, CHAPTER_DONE, count))
    (await cleared(p))[chapter['key']] = count


# ---- runs ------------------------------------------------------------------------------------------------

class Run:
    """One Neo City run: its members, chapter, the quest they are on and what it already gave."""
    def __init__(self, members, chapter, solo):
        self.id = next(_run_ids)
        self.chapter = chapter
        self.solo = solo
        self.members = list(members)
        self.agreed = set() if not solo else {id(m) for m in self.members}
        self.agree_mode = 2 if solo else 1
        self.task = None                            # the agree timeout
        self.quest = None
        self.rewarded = set()                       # quest indexes rewarded in this run
        self.missions_done = set()                  # (quest, mission) already answered with 0xeee
        self.mission_notes = set()                  # (quest, mission) already logged as 0xeec only
        self.kills = {}                             # (quest, mission) -> destroy-mission kills counted
        self.enemies = []                           # the 0xc7 records (the client's, filled); at most ENEMY_CAP
        self.enemy_no = ENEMY_FIRST                 # the next record +0x0a (the actor key's high word)
        self.killed = set()                         # (lo, hi) enemy pairs already paid in this run
        self.turrets = 0                            # the next 0xf42 turret id
        self.hits = 0                               # 0xf4f explosions forwarded (0xf50) in this run
        self.effects_dropped = False                # an 0xf4f without a victim was already logged
        self.cleared = False                        # 0xeda taken
        self.over = False
        # the CHAPTER CLEARED window (0xedb, NEO_CLEAR_PROTOCOL 2): what the run did, per member serial
        self.t0 = time.monotonic()
        self.failed = 0                             # 0xee2
        self.deaths = 0                             # 0xef2 flag 0
        self.kills = {}                             # serial -> {'HUV': n, 'HUB': n, 'HUS': n}
        self.gained = {}                            # serial -> [exp, Mito] this run paid
        self.clear_item = {}                        # serial -> item TableIdx of the Reward column
        self.cards = None                           # the 16 Chapter Bonus Item cards: [kind, TableIdx, count, picker]
        self.card_items = []                        # the cards' item ids
        self.pick_task = None
        for s in self.members:
            s.state['neo_run'] = self

    def cast(self, *frames):
        for s in self.members:
            send(s, *frames)

    def others(self, session, *frames):
        """Every run member but `session` (the 0xcf / 0xd0 relays)."""
        for s in self.members:
            if s is not session:
                send(s, *frames)

    def note(self, text):
        for s in self.members[:1]:
            s.log.note(f'neocity: {text}')


def gained(r, session, exp=0, money=0):
    g = r.gained.setdefault(serial_of(session), [0, 0])
    g[0] += exp
    g[1] += money


def run_of(session):
    r = session.state.get('neo_run')
    return r if r and not r.over and runs.get(r.id) is r else None


def drop_run(r):
    """The run is over: its members leave it (their session.state['neo_run'] goes)."""
    r.over = True
    if r.pick_task:
        r.pick_task.cancel()
        r.pick_task = None
    if r.task:
        r.task.cancel()
        r.task = None
    if runs.get(r.id) is r:
        del runs[r.id]
    for s in r.members:
        if s.state.get('neo_run') is r:
            s.state.pop('neo_run', None)


def leave(session):
    """A player leaves its run (0xe8a, a chapter give-up, the connection closing); an empty run is dropped."""
    r = run_of(session)
    if not r:
        session.state.pop('neo_run', None)
        return
    if session in r.members:
        r.members.remove(session)
    if r.solo or not r.members:
        drop_run(r)
    elif session.state.get('neo_run') is r:
        session.state.pop('neo_run', None)


def send_load(r, session):
    """S>C 0xe89 NeoCityLoad to one member; the Neo HP starts full."""
    p = session.state['player']
    map_id = MAPS.get(r.chapter['city'], MAPS['NeoOros'])
    session.state['neo_run'] = r
    forget_hp(session)
    # +0xe: the client echoes it in 0xed8 and 0xed9 puts it in activity +0x34, an index into the quest's 0x38-byte
    # entries (0x7b47c6). 1 (it was the run id, 1 for the first run) showed "1) A mysterious voice"; 0 skipped that
    # first objective (user, 2026-11-14): 1, also for later runs
    send(session, Frame(0xe89, struct.pack('<IIII', 0, map_id, r.chapter['key'], START_ENTRY) + bytes(12)))
    session.log.note(f'neocity: load {r.chapter["id"]} ({r.chapter["city"]}, map {map_id}) as run {r.id}')


def neo_area_key(session_or_serial, area):
    """area.py: the area key of a car in a Neo City area (one instance per run)."""
    r = in_neocity(session_or_serial)
    if r:
        return ('neo', area, r.id)
    serial = session_or_serial.state.get('serial', 0) if hasattr(session_or_serial, 'state') \
        else session_or_serial
    return ('neo', area, serial)


def _session_of(session_or_serial):
    if hasattr(session_or_serial, 'state'):
        return session_or_serial
    from .social import by_serial
    return by_serial(session_or_serial)


def in_neocity(session_or_serial):
    """The run of this session or car serial, or None. The area connection has its own state, so area.py
    hands over the entering car's serial and the game session (which keeps 'neo_run') is looked up, as
    undercity.uc_area_key does."""
    s = _session_of(session_or_serial)
    return run_of(s) if s else None


async def _agree_timeout(r):
    try:
        await asyncio.sleep(AGREE_SECONDS)
    except asyncio.CancelledError:
        return
    if runs.get(r.id) is r and r.agree_mode == 1:
        r.task = None
        r.cast(Frame(0xe8b, bytes(12)))
        r.note(f'the {AGREE_SECONDS:g} s to agree ran out: {r.chapter["id"]} dropped')
        drop_run(r)


# ---- handlers --------------------------------------------------------------------------------------------

def _player(session, frame, size):
    """The player, when the 2016 layout runs and the payload is long enough; else None (drop the message)."""
    if not is_on() or len(frame.payload) < size:
        return None
    return session.state.get('player')


@on(SVC, C2S, 0xe88)
async def suggest(session, frame):
    """Cmd_NeoCitySuggest: alone -> the run at once; in a party -> 0xe88 to each (15 s to agree)."""
    p = _player(session, frame, 0x18)
    if not p:
        return
    own, ms_, _, key, _, member_check = struct.unpack_from('<6I', frame.payload)
    chapter = chapter_by_key(key)
    if chapter is None:
        session.log.note(f'neocity: suggest for an unknown chapter key {key}')
        return
    level = p.char.level
    if not chapter['level_low'] <= level <= chapter['level_high']:
        session.log.note(f'neocity: {chapter["id"]} needs level {chapter["level_low"]}..{chapter["level_high"]}, '
                         f'{p.char.name} is {level}: not suggested')
        return
    from .social import party_of
    party = party_of(session)
    if not party or len(party.members) < 2:
        old = run_of(session)
        if old:
            drop_run(old)
        r = Run([session], chapter, solo=True)
        runs[r.id] = r
        session.log.note(f'neocity: suggest chapter key {key} ({chapter["id"]}, member_check {member_check}, '
                         f'ms {ms_}) by serial {own}: alone, entering')
        send_load(r, session)
        return
    members = list(party.members)
    if not all(s.state.get('player') and s.state['player'].char.city == p.char.city
               and s.state.get('channel') == session.state.get('channel') for s in members):
        session.log.note(f'neocity: suggest chapter key {key}: the party is not all in {p.char.city} / '
                         f'channel {session.state.get("channel")}, not suggested')
        return
    old = list({id(r): r for r in (run_of(s) for s in members) if r}.values())
    if any(r.agree_mode == 1 for r in old):         # a suggestion is still waiting for answers
        return
    for r in old:
        drop_run(r)
    r = Run(members, chapter, solo=False)
    runs[r.id] = r
    r.agreed = {id(session)}
    r.task = asyncio.ensure_future(_agree_timeout(r))
    out = frame.payload[:0x18] + p.char.name.encode('utf-16-le')[:40].ljust(42, b'\0')
    r.cast(Frame(0xe88, out))
    session.log.note(f'neocity: suggested chapter key {key} ({chapter["id"]}, member_check {member_check}, '
                     f'ms {ms_}) by serial {own} to {len(members)} members, {AGREE_SECONDS:g} s to agree')


@on(SVC, C2S, 0xe8c)
async def agree(session, frame):
    """Cmd_NeoCityAgree: the same frame to the party; everyone agreed -> 0xe89 to each."""
    if not _player(session, frame, 0x10):
        return
    r = run_of(session)
    if not r:
        return
    r.cast(Frame(0xe8c, frame.payload[:0x10]))
    r.agreed.add(id(session))
    session.log.note(f'neocity: agree in run {r.id} ({len(r.agreed)} of {len(r.members)})')
    if r.agree_mode == 1 and len(r.agreed) >= len(r.members):
        r.agree_mode = 2
        if r.task:
            r.task.cancel()
            r.task = None
        for s in r.members:
            send_load(r, s)


@on(SVC, C2S, 0xe8b)
async def reject(session, frame):
    """Cmd_NeoCityReject: the same frame to the party, the run dropped (the client shows 12315..12319)."""
    if not _player(session, frame, 0xc):
        return
    r = run_of(session)
    if not r:
        return
    r.cast(Frame(0xe8b, frame.payload[:0xc]))
    serial_, reason = struct.unpack_from('<II', frame.payload)
    session.log.note(f'neocity: serial {serial_} rejected run {r.id} (reason {reason}): dropped')
    drop_run(r)


@on(SVC, C2S, 0xe8a)
async def leave_area(session, frame):
    """Cmd_NeoCityLeave: the player leaves the Neo area -> it leaves its run."""
    p = _player(session, frame, 4)
    if not p:
        return
    value, = struct.unpack_from('<I', frame.payload)
    session.log.note(f'neocity: leaves the Neo area (value {value})')
    leave(session)


@on(SVC, C2S, 0xee7)
async def quest_list(session, frame):
    """0xee7 -> 0xee6: the chapters this character has cleared (records: u32 chapter key looked up in the client's
    chapter map [mgr+0x148], u16 @+0x14 the clear count, added when > 0; 0x7ad040, then 0x7abee0 recomputes the
    unlocks). Never during a run: 0x7ad040 also sets [mgr+0x174] = 0, and answering in a run removed the quest marker
    (user screenshot, 2026-11-14), so the client's repeated 0xee7 during a run stays unanswered."""
    p = _player(session, frame, 0)
    if not p:
        return
    r = run_of(session)
    if r:
        await goal_zone(session, r, frame)
        return
    counts = await cleared(p)
    done = sorted((k, n) for k, n in counts.items() if n > 0)
    body = b''.join(struct.pack('<I', k).ljust(0x14, b'\0') + struct.pack('<H', min(n, 0xffff)) + bytes(6)
                    for k, n in done)
    send(session, Frame(0xee6, struct.pack('<HH', len(done), 0) + body))
    session.log.note(f'neocity: quest list: {len(done)} chapters cleared {done}')


async def goal_zone(session, r, frame):
    """0xee7 during a run is not a list request: the client's activity sends it from its ticks with u32 key, quest,
    mission, flag (NEO_READY_QUEST.md 1.2): flag 3 / 2 from the phase-0 tick before the quest runs (left unanswered:
    0xee6 would drop the activity), 1 once when the car enters the mission's goal zone in the running quest (0x7a5883,
    after 0x79d4e0 / 0x7a54e0, latch +0x12c), 0 when it leaves (0x7a58c2). The zone answer is S>C 0xeea
    Cmd_NeoQuestGoalPlaceAck (18: key, quest, mission, result; handler 0x533fb0): result 1 -> activity phase 3 (0x53400f),
    the checkpoint's scene (the NPC dialogue of the video); the client then reports the mission itself with 0xeef, which
    mission_complete answers with 0xeee. Once per mission. (A first try answered 0xeee at once: the dialogue was skipped
    and the start zone's mission 0 completed on arrival; user, 2026-11-14.)"""
    if len(frame.payload) < 16:
        return
    key, quest, mission, flag = struct.unpack_from('<4I', frame.payload)
    if flag == 3:
        # phase 0 ("Ready Quest"): the car entered the pending quest's start zone (0x7a2f40: 0x79d4e0, latch +0x12c,
        # flag 3; 2 when it leaves). The quest starts here: 0xedd (0x526d30 -> phase 2, the intro). Sending 0xedd at
        # the chapter load skipped the start-zone intro (user screenshots, 2026-11-14)
        # Tried: 0xeea result 1 here to play an intro scene first -> the client crashed (no quest running yet in phase
        # 0; user, 2026-11-14). The car spawns inside the zone, so the quest starts about a second after the load; the
        # video's start-zone intro is still open.
        # The video's start dialogue (Korean server screenshot, user 2026-11-14: "Quest Ready" + the start row's
        # Call Sign Radio talk) is 0xeea result 3: 0x5340a2 -> 0x532d60 (phase 0/1: the chapter's first quest, phase
        # 5: the next one) -> 0x79ee90 -> 0x532c70, the script runner, on the quest's start script (activity +0x18).
        # It leaves the phase and activity +0x10 alone (result 1 read the NULL +0x10 and crashed). The quest then
        # starts with the client's 0xedc (quest_start) or, failing that, when the car enters the zone again.
        nxt = getattr(r, 'next_quest', None)
        if r.quest is None and nxt is not None and nxt < len(quests_of(r.chapter)):
            intros = r.__dict__.setdefault('intros', set())
            if nxt not in intros:
                intros.add(nxt)
                send(session, Frame(0xeea, struct.pack('<4I', key, quest, mission, 3)))
                session.log.note(f'neocity: start zone of quest {nxt} entered: 0xeea result 3, the start dialogue '
                                 f'(activity quest {quest}, mission {mission}; run {r.id})')
                return
            start_quest(session, r, key, nxt)
        return
    if flag != 1:
        return
    goals = r.__dict__.setdefault('goals', set())
    if (quest, mission) in goals or (quest, mission) in r.missions_done:
        return
    m = mission_of(r.chapter, quest, mission)
    if m and m['number'] == 11:                    # destroy: the mark only counts once the kills are done
        need = max(m['param_2'], 1)
        if r.kills.get((quest, mission), 0) < need:
            return
    goals.add((quest, mission))
    send(session, Frame(0xeea, struct.pack('<4I', key, quest, mission, 1)))
    session.log.note(f'neocity: goal zone of mission {mission} ({m["type"] if m else "?"}) of quest {quest} reached in '
                     f'run {r.id}: 0xeea')


@on(SVC, C2S, 0xed8)
async def chapter_start(session, frame):
    """0xed8 -> 0xed9 (the activity, "Ready Quest", phase 0) and 0xedd (key, quest 0): the only message that moves the
    activity to the running quest (0x526d30 -> 0x7b47a0 -> 0x7aab50: phase 2, the quest's missions, the intro notice
    GlobalText 10122 = the NPC briefing). The client asks for it with 0xedc only from its quest list row (0x5a0260);
    without it the run stayed at "Ready Quest" with an empty HP frame (user, 2026-11-14; NEO_READY_QUEST.md). 0xed9's
    last u32 goes to activity +0x34 (an index, see send_load): START_ENTRY."""
    r = run_of(session)
    if not _player(session, frame, 8) or not r:
        return
    key, _ = struct.unpack_from('<II', frame.payload)
    send(session, Frame(0xed9, struct.pack('<IIII', key, 0, 0, START_ENTRY)))
    r.quest, r.next_quest = None, 0         # "Ready Quest": 0xedd comes when the car enters the start zone (goal_zone)
    session.log.note(f'neocity: chapter start key {key}, run {r.id}: ready, quest 0 waits for its start zone')


@on(SVC, C2S, 0xedc)
async def quest_start(session, frame):
    """0xedc -> 0xedd: the quest the member picked in the Neo quest list."""
    if not _player(session, frame, 8):
        return
    r = run_of(session)
    if not r:
        return
    key, quest = struct.unpack_from('<II', frame.payload)
    start_quest(session, r, key, quest)


def start_quest(session, r, key, quest):
    """0xedd (the only way to phase 2, 0x526d30) and the quest's enemies, once per quest start."""
    if r.quest == quest:
        session.log.note(f'neocity: quest {quest} already running (run {r.id})')
        return
    r.quest, r.next_quest = quest, None
    send(session, Frame(0xedd, struct.pack('<II', key, quest)))
    spawn(session, r, quest)
    session.log.note(f'neocity: quest {quest} of chapter key {key} starts: 0xedd (run {r.id})')


@on(SVC, C2S, 0xeeb)
async def mission_progress(session, frame):
    """0xeeb -> 0xeec (26) plus 0xeee when the mission's type rule is met; 0xeea is not sent any more (its
    result 1 stops the client's mission tick, 0x53400f / 0x7a5aea). A destroy kill report (+0x12 / +0x16
    non-zero, 0x5132ae): destroy_kill."""
    if not _player(session, frame, 0x18):
        return
    r = run_of(session)
    if not r:
        return
    key, quest, mission, value, report, huv = struct.unpack_from('<6I', frame.payload)
    if report or huv:
        return destroy_kill(session, r, key, quest, mission, value, report, frame.payload[:0x18])
    # Every type gets the request's own 24 bytes back, not a rebuilt body with the tail zeroed: the matcher and the
    # per-type stores read the last two u32 (see the module docstring), so zeroing them loses what the client sent
    # (user, 2026-11-17: a destroy kill's +0x16 was dropped this way).
    send(session, Frame(0xeec, frame.payload[:0x18]))
    if (quest, mission) in r.missions_done:     # 0xeee went already: no second one, no more notes
        return
    m = mission_of(r.chapter, quest, mission)
    if m:
        if m['number'] == 6:                # collect: param_2 is the required count
            done = value >= (m['param_2'] if m['param_2'] > 0 else 1)
        elif m['number'] == 7:              # investigate: 1 then 0 (re-arm)
            done = value == 1
        else:                               # patrol, move, destroy, escort, ...: 0xeec only
            done = False
        if done:
            r.missions_done.add((quest, mission))
            send(session, Frame(0xeee, struct.pack('<3I', key, quest, mission)))
            session.log.note(f'neocity: mission {mission} ({m["type"]}) of quest {quest} complete at value '
                             f'{value} in run {r.id}')
            return
    if (quest, mission) in r.mission_notes:
        return
    r.mission_notes.add((quest, mission))
    session.log.note(f'neocity: mission {mission} of quest {quest} ({m["type"] if m else "unknown"}, value '
                     f'{value}): 0xeec only, no 0xeee, in run {r.id}')


def destroy_target_hit(m, reported):
    """A destroy kill report's +0xe against the mission's targets (NC_mission param_1, Huv Param IDs): the ID itself, or
    an NC_HuvRand group that holds a target (the client reports the group of a randomly picked HUV, e.g. 1088 with
    level 45 / 50 at +0x12; *(guess)*: the group can also have rolled another HUV). No targets = any kill (as the
    client's matcher 0x53cd90 with [mission+0xdc] == 0)."""
    targets = {_int(t) for t in m['param_1'] if _int(t)}
    if not targets or reported in targets:
        return True
    return any(i in targets for i, _ in huv_rand().get(reported, ()))


def destroy_kill(session, r, key, quest, mission, value, report, payload):
    """A kill in a destroy mission (C>S 0xeeb from 0x5132ae, sent once per destroyed enemy and only while the
    current mission is type 11 (0x51327d): +0xe = the enemy's ID (0x4f0650), +0x12 = [enemy+0x43e8], +0x16 =
    [enemy+0x41c0]). -> S>C 0xeec **with the request's 24 payload bytes unchanged**: the handler 0x53cee0 hands
    them to the matcher 0x53cd90, which counts the kill when they fit a target, so the last two u32 must survive
    (they are the HUV group and the level the client sent). Echoing only param1/param2 with the tail zeroed left
    Q3's destroy objective at 0/1 (user, 2026-11-17). The server counts the kills too and sends 0xeee (mission
    complete) at NC_mission param_2 kills, as for collect."""
    m = mission_of(r.chapter, quest, mission)
    if not m or m['number'] != 11:
        return
    send(session, Frame(0xeec, payload))
    if (quest, mission) in r.missions_done or not destroy_target_hit(m, value):
        return
    n = r.kills[(quest, mission)] = r.kills.get((quest, mission), 0) + 1
    need = max(m['param_2'], 1)
    session.log.note(f'neocity: destroy kill {n}/{need} (enemy {value}, {report}) for mission {mission} of quest '
                     f'{quest} in run {r.id}')
    if n >= need:
        # The objective is met, NOT the mission: the client then shows the mission's goal mark (NC_mission column 5,
        # e.g. m_000248's "Return to Base ROAD" at the base) and the player drives there, which is the same
        # goal-zone step as a move / patrol mission (0xee7 flag 1 -> 0xeea result 1 -> the NPC scene -> the client's
        # 0xeef -> 0xeee). Sending 0xeee here skipped the mark and the closing dialogue and, on the chapter's last
        # quest, jumped straight to CHAPTER CLEAR (user, 2026-11-18, with the official-server video).
        session.log.note(f'neocity: destroy objective of mission {mission} of quest {quest} complete: waiting for its '
                         f'goal mark in run {r.id}')


@on(SVC, C2S, 0xeef)
async def mission_complete(session, frame):
    """0xeef -> 0xeee: the same three u32 back; the (quest, mission) is marked done for 0xeeb."""
    if not _player(session, frame, 0xc):
        return
    r = run_of(session)
    if not r:
        return
    send(session, Frame(0xeee, frame.payload[:0xc]))
    key, quest, mission = struct.unpack_from('<III', frame.payload)
    r.missions_done.add((quest, mission))
    session.log.note(f'neocity: mission {mission} of quest {quest} done (chapter key {key})')


@on(SVC, C2S, 0xeed)
async def mission_params(session, frame):
    """0xeed (key, quest, mission): the client after a mission's checkpoint scene (0xeea result 1 -> phase 3) ended
    (user, 2026-11-14: the scene stayed at its end without an answer). -> 0xeee (complete) for that mission, once. The
    0xeec counters (handler 0x53cee0) only exist for mission types 6..11, so they are not sent here."""
    if not _player(session, frame, 0xc):
        return
    r = run_of(session)
    if not r:
        return
    key, quest, mission = struct.unpack_from('<III', frame.payload)
    if (quest, mission) in r.missions_done:
        return
    r.missions_done.add((quest, mission))
    send(session, Frame(0xeee, struct.pack('<3I', key, quest, mission)))
    session.log.note(f'neocity: mission {mission} of quest {quest} finished after its scene (0xeed): 0xeee, run {r.id}')


@on(SVC, C2S, 0xede)
async def quest_reward(session, frame):
    """0xede -> 0xedf: the quest's exp / Mito / items from NC_quest, then the stat and inventory frames."""
    p = _player(session, frame, 0xc)
    if not p:
        return
    r = run_of(session)
    if not r:
        return
    key, quest, seconds = struct.unpack_from('<IIf', frame.payload)
    table = quests_of(r.chapter)
    if quest >= len(table):
        session.log.note(f'neocity: quest {quest} is not in {r.chapter["id"]} ({len(table)} quests): no reward')
        return
    q, c = table[quest], p.char
    gains, items, exp, money = None, [], 0, 0
    if quest in r.rewarded:
        session.log.note(f'neocity: quest {quest} ({q["id"]}) was rewarded already in run {r.id}: nothing given')
    else:
        r.rewarded.add(quest)
        exp, money = q['exp'], q['mito']
        if exp:
            await add_exp(c, exp)
        if money:
            await add_money(c, money)
        for item in q['items']:
            info = context.data.item_info(context.data.item_index[item]) if item in context.data.item_index else None
            if info:
                items.append(info)
            if len(items) == 3:
                break
        from .rewards import give
        gains, given = await give(p, [(info.item_id, 1) for info in items])
        await play_mode(c, 'NEOCITY', exp=exp, money=money)
        gained(r, session, exp, money)
        session.log.note(f'neocity: quest {quest} ({q["id"]}) done in {seconds:.1f} s: {exp} exp, {money} Mito, '
                         f'items {[(i.item_id, n) for i, n in given]}')
    table_idx = [info.table_idx for info in items][:3]
    send(session, Frame(0xedf, pack_exp('<4I3IHH3I', key, quest, exp, money, c.exp, c.exp_next, c.exp_base,
                                       c.level, len(table_idx), *(table_idx + [0] * (3 - len(table_idx))))))
    for f in stat_frames(p):
        send(session, f)
    if gains and gains.items:
        from .items import mod_list
        send(session, mod_list(*gains.items))
    if quest + 1 < len(table) and r.quest == quest:
        # the next quest waits for its start zone (the minimap's Q) like the first: goal_zone sends its 0xedd
        r.quest, r.next_quest = None, quest + 1
        session.log.note(f'neocity: quest {quest + 1} ({table[quest + 1]["id"]}) waits for its start zone (run {r.id})')


@on(SVC, C2S, 0xeda)
async def chapter_complete(session, frame):
    """0xeda -> 0xedb CHAPTER CLEARED (the run's summary) + 0xee9 the Chapter Bonus Item cards. The chapter's exp /
    Mito and one item of its result_rewardGroup (the Reward column) are given; SKID_QUEST_TB 'neo_<chapter>' + 1."""
    p = _player(session, frame, 8)
    if not p:
        return
    r = run_of(session)
    if not r:
        return
    key, run_id = struct.unpack_from('<II', frame.payload)
    c = p.char
    me = serial_of(session)
    if me in r.clear_item:
        session.log.note(f'neocity: chapter key {key} was completed already in run {r.id}: nothing given')
    else:
        r.cleared = True
        counts = await cleared(p)
        count = counts.get(r.chapter['key'], 0) + 1
        await _save(p, r.chapter, count)
        exp, money = r.chapter['exp'], r.chapter['mito']
        if exp:
            await add_exp(c, exp)
            send(session, Frame(0x7d1, pack_exp('<3IHi', c.exp, c.exp_next, c.exp_base, c.level, exp)))
        if money:
            await add_money(c, money)
            send(session, Frame(0x7d2, struct.pack('<qq', c.mito, money)))
        await play_mode(c, 'NEOCITY', exp=exp, money=money)
        gained(r, session, exp, money)
        item = await give_rolled(session, p, r.chapter.get('reward_group'))
        r.clear_item[me] = item.table_idx if item else 0
        session.log.note(f'neocity: chapter {r.chapter["id"]} (key {key}, run {run_id}) cleared {count} time(s): '
                         f'{exp} exp, {money} Mito, item {item.item_id if item else None}')
        for f in stat_frames(p):
            send(session, f)
    send(session, clear_frame(r, key))
    if r.cards is None:
        roll_cards(r)
        r.pick_task = asyncio.ensure_future(auto_pick(r))
    send(session, cards_frame(r))


GRADES = 5                          # 0xedb grade index 0..4 -> one of five letters (0 = S: a guess, section 2.1)
PICK_SECONDS = 18                   # the client closes the window after 20 s (0x788ae0 from 0x71ef60)
CARDS = 16
CHAPTER_CARDS = 4                   # ours: cards from the chapter's own result_rewardGroup, the rest elite HUV items


def grade_of(r):
    """Ours: S with no failed quest and no death, then one letter down per two mishaps (the video: 0 / 0 -> S)."""
    return min(GRADES - 1, (r.failed + r.deaths + 1) // 2)


def clear_frame(r, key):
    """S>C 0xedb (handler 0x52e960 -> window 0x71f2b0; NEO_CLEAR_PROTOCOL 2): u32 chapter key, u32 n rows, u8 0, u32
    seconds (0x71f43a), u32 quests failed, u32 deaths, u32 grade 0..4, four rows of 0x2c (u32 serial, level, HUV / HUB
    / HUS kills, exp, Mito, the Reward item TableIdx twice, 0, 0; 0x71f5de, stride 0x71f959), then 0x10 per extra
    row (the handler's size: n * 0x10 + 0xbb)."""
    members = [m for m in r.members if m.state.get('player')][:4]
    n = max(1, len(members))
    rows = []
    for m in members:
        serial, c = serial_of(m), m.state['player'].char
        k = r.kills.get(serial, {})
        exp, money = r.gained.get(serial, (0, 0))
        item = r.clear_item.get(serial, 0)
        rows.append(struct.pack('<7I4I', serial, c.level, k.get('HUV', 0), k.get('HUB', 0), k.get('HUS', 0),
                                exp, money, item, item, 0, 0))
    rows += [bytes(0x2c)] * (4 - len(rows))
    seconds = int(time.monotonic() - r.t0)
    return Frame(0xedb, struct.pack('<IIBIIII', key, n, 0, seconds, r.failed, r.deaths, grade_of(r))
                 + b''.join(rows) + bytes(0x10 * (n - 1)))


def elite_group(chapter):
    """The elite HUV reward items of the chapter's level tier (RewardGroup rw_neo_elite_huv_45/60/80/100_item: the
    recovery capsules, booster recharges, enhancers and drift items the video's cards show)."""
    level = chapter.get('level_low', 40)
    tier = 45 if level < 60 else 60 if level < 80 else 80 if level < 100 else 100
    return f'rw_neo_elite_huv_{tier}_item'


def roll_item(group):
    """One rolled NormalItem / SkidItem of a group that this server's tables know -> (item id, count) or None."""
    from .driftuse import roll
    if not group or group in ('n/a', '0'):
        return None
    for _ in range(8):
        won = [w for w in roll(group) if w[0] in ('NormalItem', 'SkidItem') and w[1] in context.data.item_index]
        if won:
            return won[0][1], max(_int(won[0][3]), 1)
    return None


async def give_rolled(session, p, group):
    """One item of the group to the player (rewards.give + items.mod_list) -> its ItemInfo, or None."""
    got = roll_item(group)
    if not got:
        return None
    from .rewards import give
    gains, given = await give(p, [got])
    if gains and gains.items:
        from .items import mod_list
        send(session, mod_list(*gains.items))
    return given[0][0] if given else None


def roll_cards(r):
    """The 16 Chapter Bonus Item cards of the run (the same grid for every member): CHAPTER_CARDS from the chapter's
    result_rewardGroup, the rest from its elite HUV tier group (ours: the real mix is not known; duplicates happen,
    as in the video)."""
    r.cards, r.card_items = [], []
    for i in range(CARDS):
        got = roll_item(r.chapter.get('reward_group') if i < CHAPTER_CARDS else None) or roll_item(elite_group(r.chapter))
        item, count = got or ('', 0)
        info = context.data.item_info(context.data.item_index[item]) if item else None
        r.cards.append([1 if info else 0, info.table_idx if info else 0, count if info else 0, 0])
        r.card_items.append(item if info else '')


def cards_frame(r):
    """S>C 0xee9 (handler 0x526d80; NEO_CLEAR_PROTOCOL 3.1): u32 0 (the client ignores it), then 16 x {u32 kind,
    u32 item TableIdx, u32 count, u32 picker serial}.

    A slot that nobody has picked goes out as **all zeros**: kind 0 is the client's "?" face, and only that card face
    is clickable (`+0x08` control, bit 0x40 = clickable; every non-zero kind re-shows the caption of `+0xc8`). While
    the server sent the items in every slot, all 16 cards were drawn face-up, clicking one did nothing and the client
    never sent 0xee8, so the pick fell to the server's 18 s auto-pick (user, 2026-11-18, chapter 1 clear). Picked
    slots carry their item and the picker's serial, which is how the client shows the caption and the picker's name."""
    out = bytearray(struct.pack('<I', 0))
    for kind, item, count, picker in r.cards:
        out += struct.pack('<4I', kind, item, count, picker) if picker else bytes(16)
    return Frame(0xee9, bytes(out))


async def pick(r, session, slot):
    """A member takes card `slot` (one card each): the item is given and every member sees the new grid."""
    me = serial_of(session)
    if r.cards is None or not 0 <= slot < CARDS or r.cards[slot][3] or any(c[3] == me for c in r.cards):
        return False
    r.cards[slot][3] = me
    item = r.card_items[slot]
    p = session.state.get('player')
    if item and p:
        from .rewards import give
        gains, given = await give(p, [(item, max(r.cards[slot][2], 1))])
        if gains and gains.items:
            from .items import mod_list
            send(session, mod_list(*gains.items))
    r.cast(cards_frame(r))
    session.log.note(f'neocity: bonus card {slot} picked: {item} x{r.cards[slot][2]}')
    return True


async def auto_pick(r):
    """"If you don't choose a reward item within a given time, it will be automatically selected." (GlobalText 11799)"""
    await asyncio.sleep(PICK_SECONDS)
    r.pick_task = None
    for m in list(r.members):
        if r.cards and not any(c[3] == serial_of(m) for c in r.cards):
            free = [i for i, c in enumerate(r.cards) if not c[3]]
            if free:
                await pick(r, m, random.choice(free))


@on(SVC, C2S, 0xee8)
async def chapter_reward(session, frame):
    """0xee8 (sender 0x84ef10): u32 0, u32 the card slot the player clicked -> the card's item, 0xee9 to the run."""
    if not _player(session, frame, 8):
        return
    r = session.state.get('neo_run')
    _, slot = struct.unpack_from('<II', frame.payload)
    if not r or r.cards is None:
        session.log.note(f'neocity: bonus card {slot} picked outside a cleared run: ignored')
        return
    if not await pick(r, session, slot):
        session.log.note(f'neocity: bonus card {slot}: not available')
        send(session, cards_frame(r))


@on(SVC, C2S, 0xee2)
async def quest_fail(session, frame):
    """0xee2 -> 0xee3: the request's first two u32 back (the quest failed, the client counts it)."""
    if not _player(session, frame, 8) or not run_of(session):
        return
    key, quest = struct.unpack_from('<II', frame.payload)
    run_of(session).failed += 1
    send(session, Frame(0xee3, struct.pack('<II', key, quest)))
    session.log.note(f'neocity: quest {quest} (chapter key {key}) failed')


@on(SVC, C2S, 0xee4)
async def quest_give_up(session, frame):
    """0xee4 -> 0xee5 to every run member: who gave the quest up is the client's 12311 line."""
    if not _player(session, frame, 0x10):
        return
    r = run_of(session)
    if not r:
        return
    key, quest, mission, whose = struct.unpack_from('<IIII', frame.payload)
    r.cast(Frame(0xee5, struct.pack('<III', key, quest, whose)))
    session.log.note(f'neocity: quest {quest} (mission {mission}) given up by serial {whose} in run {r.id}')


@on(SVC, C2S, 0xef0)
async def chapter_give_up(session, frame):
    """0xef0 -> 0xef1 to every run member: the serial, its client leaves the Neo area; it leaves the run."""
    if not _player(session, frame, 0x10):
        return
    r = run_of(session)
    if not r:
        return
    key, quest, mission, whose = struct.unpack_from('<IIII', frame.payload)
    r.cast(Frame(0xef1, struct.pack('<II', 0, whose)))
    session.log.note(f'neocity: chapter key {key} given up by serial {whose} (mission {mission}), run {r.id}')
    leave(session)


@on(SVC, C2S, 0xef2)
async def dying(session, frame):
    """0xef2 (14; builder 0x84e90b): u32 chapter key @+2, u32 @+0xa a running count (1, 2, 3, ... 3750: the client
    sends it again and again while its car is destroyed); +6 is never written (leftover memory). -> 0xef3 (14, handler
    0x526ec0): u32 key, u32 revive @+6, u32 0 - always 0 here: a non-zero +6 runs the revive routine 0x787f10, and
    answering every 0xef2 with it made a destroyed car revive and die again in a loop (5516 messages in 34 s, user
    2026-11-14: "Resurrected!!" / "YOU ARE DESTROYED"). The NEO Retry is the client's own dialog (12 items, 5 minutes).
    A death is counted once per burst.
    The two senders (0xef2 builder 0x84e830, which never writes its 2nd argument, hence the leftover +6): 0x788f5d
    (argument 0) while the car is destroyed, then it opens the Retry dialog (UI 0x3c, 0x788f80) and sets [+0x60];
    0x78907b (argument 1) once the car has HP again (0x788e10) and the flag is set, clearing it. So an 0xef2 right
    after a revive is the "alive again" notice, not a death. The revive itself comes only from the server: the
    revival item (neo_i_00005, use kind 0x5a) answers its 0x1a2 and then 0xef3 +6 = 1 (revive below)."""
    if not _player(session, frame, 0xc):
        return
    r = run_of(session)
    if not r:
        return
    key, _, count = struct.unpack_from('<III', frame.payload)
    now = time.monotonic()
    if now - session.state.get('neo_revived', -99.0) < REVIVE_NOTICE:
        session.log.note(f'neocity: alive again after the revival (0xef2 from 0x78907b) in run {r.id}')
        session.state.pop('neo_revived', None)
        send(session, Frame(0xef3, struct.pack('<III', key, 0, 0)))
        return
    session.state['neo_dead'] = True
    if now - getattr(r, 'last_death', 0.0) > 5.0:
        r.deaths += 1
        session.log.note(f'neocity: destroyed in run {r.id} (chapter key {key}, count {count})')
    r.last_death = now
    send(session, Frame(0xef3, struct.pack('<III', key, 0, 0)))


REVIVE_NOTICE = 3.0      # s after a revive in which an 0xef2 is the client's "alive again" notice (0x78907b)


def revive(session):
    """The revival item (use kind 0x5a) in a run while the car is destroyed: S>C 0xef3 (key, 1, 0), the only server
    path to the client's revive routine 0x787f10 (0x526ed6; the other caller is a chapter script command, 0x61d24d).
    The client does not revive by itself after the item (log 20261114-190203 19:57:28: 0x1a1 / 0x1a2 and nothing
    else; user: "The NEO retry item doesn't work properly"). -> True when sent."""
    r = run_of(session)
    if not r:
        return False
    if not session.state.pop('neo_dead', False):
        session.log.note(f'neocity: revival item used while not destroyed in run {r.id}: no revive')
        return False
    session.state['neo_revived'] = time.monotonic()
    forget_hp(session)
    send(session, Frame(0xef3, struct.pack('<III', r.chapter['key'], 1, 0)))
    session.log.note(f'neocity: revived with the revival item in run {r.id}: 0xef3 +6 = 1')
    return True


@on(SVC, C2S, 0xef5)
async def bonus_mission(session, frame):
    """0xef5 (the Chapter List window; u32 chapter key) -> 0xef6 u32 key, u32 0, u32 n: the "n / 10" of "By completing
    10 rounds of each mission, you'll receive the same rewards again!" (only +0xa is read, the 10 is the client's;
    NEO_CLEAR_PROTOCOL 5). n = the chapter's clears modulo 10 (ours)."""
    p = _player(session, frame, 4)
    if not p:
        return
    key, = struct.unpack_from('<I', frame.payload)
    n = (await cleared(p)).get(key, 0) % 10
    send(session, Frame(0xef6, struct.pack('<III', key, 0, n)))
    session.log.note(f'neocity: bonus mission count of chapter key {key}: {n} / 10')


# ---- stage 3: enemies, turrets, part repair --------------------------------------------------------------

@on(SVC, C2S, 0xc6)
async def enemy_request(session, frame):
    """0xc6 -> 0xc7 to every run member: the client's enemy records, serial / chapter key / quest filled in."""
    if not _player(session, frame, 8):
        return
    r = run_of(session)
    if not r:
        return
    time_, n = struct.unpack_from('<II', frame.payload)
    n = min(n, (len(frame.payload) - 8) // 0x40)
    serial = session.state.get('serial', 0) & 0xffff
    body = bytearray()
    dropped = 0
    for i in range(n):
        rec = bytearray(frame.payload[8 + i * 0x40:8 + (i + 1) * 0x40])
        if struct.unpack_from('<H', rec)[0] == 3:
            # kind 3 = a HUB's summons (its AI 0x4e2980 -> 0x4ef2d0): relayed, they took the local HUV control
            # (+0x08 = the member's serial, 0x5237d1 -> 0x45e7b0) and the client crashed in 0x4a9990 at 0x4a99a1
            # reading the control's unset +0x78 (dump DriftCity.exe.npd, user 2026-11-14). Not relayed: the HUB
            # spends its summon count anyway (0x4e2a04) and has no children (NEO_HUBCRASH.md 4.1).
            dropped += 1
            continue
        if not struct.unpack_from('<H', rec, 8)[0]:
            struct.pack_into('<H', rec, 8, serial)
        struct.pack_into('<H', rec, 0xa, next(enemy_numbers(r)))   # unique actor key; 0 is skipped (0x53bd0c)
        if not struct.unpack_from('<I', rec, 0x30)[0]:
            struct.pack_into('<I', rec, 0x30, r.chapter['key'])
        if not struct.unpack_from('<I', rec, 0x34)[0]:
            struct.pack_into('<I', rec, 0x34, r.quest or 0)
        if len(r.enemies) < ENEMY_CAP:
            r.enemies.append(bytes(rec))
        body += rec
    if dropped:
        session.log.note(f'neocity: {dropped} HUB summon record(s) (kind 3) not relayed in run {r.id}')
    n -= dropped
    if not n:
        return
    r.cast(Frame(0xc7, struct.pack('<IIH', time_, n, 0) + bytes(body)))
    session.log.note(f'neocity: {n} enemy record(s) (request time {time_}, chapter key {r.chapter["key"]}, '
                     f'quest {r.quest}) for run {r.id}')


@on(SVC, C2S, 0xcd)
async def enemy_hit(session, frame):
    """0xcd -> 0xcd to every run member with the reward fields zeroed (the rewards go with the kill, 0xce)."""
    if not _player(session, frame, 0x28):
        return
    r = run_of(session)
    if not r:
        return
    hitter, = struct.unpack_from('<H', frame.payload)
    hp_left, damage = struct.unpack_from('<ii', frame.payload, 0xa)
    out = frame.payload[:0x18] + struct.pack('<iqi', 0, 0, 0)     # Mito @0x1a, i64 @0x1e, exp @0x26
    r.cast(Frame(0xcd, out))
    if hp_left <= 0:
        session.log.note(f'neocity: serial {hitter} brought an enemy to {hp_left} HP ({damage} damage) in run '
                         f'{r.id}')


async def collect_drop(session, p, r, huv_id):
    """A kill during a collect mission can drop its item. NC_mission collect rows carry param_1 = "0 <item> <Huv
    Param ID> <chance %> n/a" and param_2 = the count needed (e.g. q_00024 "Build a defense system": 5 neo_q_00001
    from HUV 100482 at 100). *(guess, lead session 46: the item / enemy / chance reading of param_1 is ours; the
    100482 is the same enemy the destroy rows name.)* The client counts the item in its inventory and reports the
    count with 0xeeb (0x796cc0), which mission_progress() turns into 0xeee once it reaches param_2."""
    if r.quest is None:
        return
    table = quests_of(r.chapter)
    if not 0 <= r.quest < len(table):
        return
    for m in missions().get(table[r.quest]['id'], ()):
        p1 = m['param_1']
        if m['type'] != 'collect' or len(p1) < 4 or _int(p1[2]) != huv_id:
            continue
        item = p1[1]
        if item not in context.data.item_index or random.random() * 100 >= _int(p1[3], 100):
            continue
        held = sum(i.stack for i in getattr(p, 'items', ()) if i.item_id == item)
        if held >= max(1, m['param_2']):
            continue
        from .rewards import give
        gains, _given = await give(p, [(item, 1)])
        if gains and gains.items:
            from .items import mod_list
            send(session, mod_list(*gains.items))
        session.log.note(f'neocity: collect drop {item} from Huv Param {huv_id} ({held + 1}/{m["param_2"]}) '
                         f'in run {r.id}')


def enemy_param(r, lo, hi):
    """The Huv Param ID of the enemy a kill report names, from the run's own spawn record for that actor key (record
    +0x08 owner serial, +0x0a enemy number, +0x0e Huv Param ID), or 0. The client's +0x34 is a Huv Param ID for most
    enemies but a HUV reports its **model** there — 19040 / 19041 / 19104 are the "등장 HUV ID" of HUV-MRL / HUV-APS /
    HUV-HMG, not IDs of the table — so those kills found no row and paid nothing (user, 2026-11-17)."""
    for rec in r.enemies:
        if struct.unpack_from('<HH', rec, 8) == (lo, hi):
            return struct.unpack_from('<I', rec, 0xE)[0]
    return 0


@on(SVC, C2S, 0xce)
async def enemy_kill(session, frame):
    """0xce -> 0xce to every run member, then the sender (the killer) is paid once per enemy pair."""
    p = _player(session, frame, 0x3e)
    if not p:
        return
    r = run_of(session)
    if not r:
        return
    lo, hi = struct.unpack_from('<HH', frame.payload)
    reported, = struct.unpack_from('<I', frame.payload, 0x34)
    r.cast(Frame(0xce, frame.payload[:0x3e]))
    if (lo, hi) in r.killed:
        session.log.note(f'neocity: kill of enemy {hi}:{lo} (Huv Param {reported}) reported again: relayed, '
                         f'paid once')
        return
    r.killed.add((lo, hi))
    huv_id = enemy_param(r, lo, hi) or reported
    if huv_id != reported:
        session.log.note(f'neocity: enemy {hi}:{lo}: the client sent {reported} (a model), the spawn record says '
                         f'Huv Param {huv_id}')
    await collect_drop(session, p, r, huv_id)
    info = huv_params().get(huv_id)
    if not info:
        session.log.note(f'neocity: kill of enemy {hi}:{lo}: unknown Huv Param ID {huv_id}, relayed only')
        return
    k = r.kills.setdefault(serial_of(session), {})
    kind = info.get('kind', 'HUV')
    k[kind] = k.get(kind, 0) + 1
    c = p.char
    exp, money = info['level'] * KILL_EXP_PER_LEVEL, info['level'] * KILL_MITO_PER_LEVEL
    if exp:
        await add_exp(c, exp)
        send(session, Frame(0x7d1, pack_exp('<3IHi', c.exp, c.exp_next, c.exp_base, c.level, exp)))
    if money:
        await add_money(c, money)
        send(session, Frame(0x7d2, struct.pack('<qq', c.mito, money)))
    gains, given = None, []
    group = info['reward']
    if group and group not in ('n/a', '0'):
        from .driftuse import roll
        won = [w for w in roll(group) if w[0] in ('NormalItem', 'SkidItem')]
        item = next((w[1] for w in won if w[1] in context.data.item_index), None)
        if item:
            from .rewards import give
            gains, given = await give(p, [(item, 1)])
    await play_mode(c, 'NEOCITY', exp=exp, money=money)
    gained(r, session, exp, money)
    session.log.note(f'neocity: killed {info["name"] or huv_id} (Huv Param {huv_id}, level {info["level"]}) in '
                     f'run {r.id}: {exp} exp, {money} Mito, items {[i.item_id for i, _ in given]}')
    for f in stat_frames(p):
        send(session, f)
    if gains and gains.items:
        from .items import mod_list
        send(session, mod_list(*gains.items))


@on(SVC, C2S, 0xcf)
async def hub_targeting(session, frame):
    """0xcf -> 0xcf to every OTHER run member (the sender's client already knows); not logged."""
    if not _player(session, frame, 9):
        return
    r = run_of(session)
    if r:
        r.others(session, Frame(0xcf, frame.payload[:9]))


@on(SVC, C2S, 0xd0)
async def enemy_aggro(session, frame):
    """0xd0 -> 0xd0 to every OTHER run member; not logged."""
    if not _player(session, frame, 0xe):
        return
    r = run_of(session)
    if r:
        r.others(session, Frame(0xd0, frame.payload[:0xe]))


@on(SVC, C2S, 0xf41)
async def turret_request(session, frame):
    """0xf41 -> 0xf42 to every run member: the sender's serial and a per-run turret id per record."""
    if not _player(session, frame, 8):
        return
    r = run_of(session)
    if not r:
        return
    n, = struct.unpack_from('<I', frame.payload)
    n = min(n, (len(frame.payload) - 8) // 12)              # the client reserves 22 bytes for every n (0x848f25)
    kind, objective = struct.unpack_from('<HH', frame.payload, 4)
    serial = session.state.get('serial', 0) & 0xffff
    body = b''
    for i in range(n):
        r.turrets = r.turrets % 0xffff + 1
        body += struct.pack('<HH', serial, r.turrets) + frame.payload[8 + 12 * i:20 + 12 * i]
    r.cast(Frame(0xf42, struct.pack('<IHH', n, kind, objective) + body))
    session.log.note(f'neocity: {n} turret(s) (kind {kind}, objective {objective}) in run {r.id}')


@on(SVC, C2S, 0xf43)
async def turret_use(session, frame):
    """0xf43: a turret's u16, logged only (guess: the fire/use notice; no answer is known)."""
    if not _player(session, frame, 2):
        return
    value, = struct.unpack_from('<H', frame.payload)
    session.log.note(f'neocity: turret message, u16 {value} (no answer known)')


@on(SVC, C2S, 0xf3e)
async def script_huv_delete(session, frame):
    """0xf3e -> 0xf3f to every run member: the client deletes its scripted Neo HUVs."""
    if not _player(session, frame, 0):
        return
    r = run_of(session)
    if not r:
        return
    r.cast(Frame(0xf3f, b''))
    session.log.note(f'neocity: scripted HUVs deleted in run {r.id}')


@on(SVC, C2S, 0x4c4)
async def repair_parts(session, frame):
    """0x4c4 -> 0x4c5: u32 item id and u32 1; free, no Neo part durability is kept."""
    if not _player(session, frame, 4):
        return
    item, = struct.unpack_from('<I', frame.payload)
    send(session, Frame(0x4c5, struct.pack('<II', item, 1)))
    session.log.note(f'neocity: Neo part {item} repaired (free: no durability is kept)')


def _log_only(session, frame, what):
    """One log note for a message with no known answer (at most 64 bytes of its payload on the line)."""
    data = frame.payload[:64].hex() + ('...' if len(frame.payload) > 64 else '')
    session.log.note(f'neocity: {what}, {len(frame.payload)} payload byte(s) {data} (no answer)')


@on(SVC, C2S, 0xc8)
async def object_state(session, frame):
    """0xc8: the client fills nothing; logged only (no answer known)."""
    if not _player(session, frame, 0x10):
        return
    _log_only(session, frame, '0xc8 (a Neo object state request)')


@on(SVC, C2S, 0xd1)
async def aggro_value(session, frame):
    """0xd1: a u16; logged only (no answer known)."""
    if not _player(session, frame, 2):
        return
    _log_only(session, frame, '0xd1')


@on(SVC, C2S, 0xf40)
async def enemy_list(session, frame):
    """0xf40: u16 n then n u16; logged only (no answer known)."""
    if not _player(session, frame, 4):
        return
    _log_only(session, frame, '0xf40')


@on(SVC, C2S, 0xf49)
async def text_block(session, frame):
    """0xf49: 448 copied bytes; logged only (guess: a name / score text block)."""
    if not _player(session, frame, 0x1c4):
        return
    _log_only(session, frame, '0xf49')


@on(SVC, C2S, 0xf4a)
async def text_block_id(session, frame):
    """0xf4a: one u32; logged only (no answer known)."""
    if not _player(session, frame, 4):
        return
    _log_only(session, frame, '0xf4a')


@on(SVC, C2S, 0xf4c)
async def damage_ratio(session, frame):
    """0xf4c: one f32; logged only (guess: a damage ratio)."""
    if not _player(session, frame, 4):
        return
    _log_only(session, frame, '0xf4c')


@on(SVC, C2S, 0xf4f)
async def explosion_hit(session, frame):
    """0xf4f -> 0xf50 to the victim only: an explosion this client drives reached another player's car
    (0x4e5ccd-0x4e5cfe). The victim is the run member whose serial low 16 bits is +2; +0xf50 carries it and
    VICTIM_SORT *(guess: the car sort of a player's own car, area.py)*, then the request's +6..+0x11."""
    if not _player(session, frame, 0x10):
        return
    r = run_of(session)
    if not r:
        return
    victim_key, shooter_hi = struct.unpack_from('<HH', frame.payload)
    victim = next((s for s in r.members if (s.state.get('serial', 0) & 0xffff) == victim_key), None)
    if victim is None or victim is session:
        if not r.effects_dropped:
            r.effects_dropped = True
            session.log.note(f'neocity: 0xf4f for car {victim_key} (shooter key high {shooter_hi}) from serial '
                             f'{session.state.get("serial")}: '
                             f'{"the sender itself" if victim else "no run member"}, dropped; further drops in '
                             f'run {r.id} are not logged, {r.hits} hit(s) forwarded so far')
        return
    r.hits += 1
    send(victim, Frame(0xf50, struct.pack('<HH', victim_key, VICTIM_SORT) + frame.payload[4:0x10]))


@on(SVC, C2S, 0xfbf)
async def car_exploded(session, frame):
    """0xfbf: the car id; logged only (the guess is that it wants 0xf50, not sent: no enemy AI)."""
    if not _player(session, frame, 4):
        return
    _log_only(session, frame, '0xfbf')


@on_open(SVC)
async def neocity_on_close(session):
    """The connection closes: the player leaves its run."""
    try:
        await asyncio.Event().wait()
    finally:
        leave(session)


# GM test gear (gmneo / control port "neo"; 2016 ItemClient.tdf + Init/WeaponList.xlt). The Rare 90 weapons point at
# the WeaponList "120" rows (ItemClient column 9: 21141 / 22141 / 23141 / 24141; e.g. Cannon damage 17940 against
# 11623 for U Cannon 108) and the Rare 90 armours have the highest defence (column 9: light 1500, heavy 2400; U 108:
# 871 / 1742), so 'rare' is the strongest set; 'u' is the U-Type 108 line (required level 108).
NEO_GEAR = {
    'rare': ('neo_wp_c_21141', 'neo_wp_a_22141', 'neo_wp_w_23141', 'neo_wp_m_24141',     # R Cannon / Railgun / Wave / Mine 90
             'neo_cop_10008', 'neo_fup_10008',                                           # R Amplifier 90, R Fuse 90
             'neo_arp_l_10036', 'neo_arp_h_10036'),                                      # R Light / Heavy Armor 90
    'u': ('neo_wp_c_21135', 'neo_wp_a_22135', 'neo_wp_w_23135', 'neo_wp_m_24135',        # U Cannon / Railgun / Wave / Mine 108
          'neo_cop_10007', 'neo_fup_10007',                                              # U Amplifier 90, U Fuse 90
          'neo_arp_l_10035', 'neo_arp_h_10035'),                                         # U Light / Heavy Armor 108
}
NEO_GEAR_USAGE = 'gmneo [name] [rare|u]: the strongest Neo City weapons, amplifier, fuse and armours (rare: Rare 90, the default)'


async def gm_gear(target, args):
    """One of each item of a NEO_GEAR set to the target's inventory -> (done, reply)."""
    from .combo import free_slots, take
    from .items import mod_list
    which = args[0].lower() if args else 'rare'
    if which not in NEO_GEAR:
        return False, f'usage: {NEO_GEAR_USAGE}'
    t, p = context.data, target.state['player']
    infos = [t.item_info(t.item_index[i]) if i in t.item_index else None for i in NEO_GEAR[which]]
    if not all(infos):
        return False, 'no Neo City items in this server\'s tables (2016 only: emulator.ini [client] version)'
    if free_slots(p) < len(infos):
        return False, f'{p.char.name}: {len(infos)} Neo items need {len(infos)} free slots, {free_slots(p)} free'
    send(target, mod_list(*[await take(p, info) for info in infos]))
    level = max(info.req_level for info in infos)
    note = f' (required level {level}; {p.char.name} is {p.char.level})' if level > p.char.level else ''
    return True, f'{p.char.name} got the {which} Neo set: ' + ', '.join(i.name or i.item_id for i in infos) + note
