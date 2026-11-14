# Neo City (네오시티): what it is, and the messages the 2016 client uses

Research 2026-11-13. Nothing of it is implemented in the emulator. This file is the starting point: the game's
design from the Korean sources, and the client's message set measured from `DriftCity Dev Ed/DriftCity.exe`.

## The design (Korean sources)

Sources: namu.wiki `스키드러쉬/게임 모드` §1.9 (the fullest), ko.wikipedia `스키드러쉬` §3.9, the official
`sr.masanggames.co.kr` news (Neo City reward buff, 2022-06-29).

- **Story / access.** Set 30 years after the base game. Unlocked at level 40 (namu; the official site said 80 before a
  change) **plus** the main quests of cities 1-4; an entry quest at Oros sends the player to the ROAD secret base
  through a time tunnel.
- **Structure.** Chapter-based **instanced dungeons** for 1-4 players, one chapter set per city (Neo Oros, Neo Kras,
  Neo Koinonia, Neo Moon Palace). A chapter is 3-5 quests of types move / patrol / collect / destroy / escort /
  investigate. Chapters are taken at the **Neo Gate** in the ROAD base and teleport the party straight in.
- **Enemies.** Spider **HUS** (summoned by other AI, blocks the path), scout **HUB** (calls an OMD satellite laser and
  flees), armed **HUV** (HMG 1-20 dmg, APS 10-40, RPG 40-100, MRL 100-300), elite **HUV-AV02** (two weapons, heavy
  armour, summons adds), and fixed **defence turrets** (fixed 20 damage).
- **Vehicle combat (Neo only).** The player's car gains **durability/HP that only Neo City uses**. Gear: plasma
  weapon (cannon / railgun / wave, fired with Space, costs booster gauge), plasma amplifier and fusion unit (weapon
  options), light / heavy **armour** (less damage, more weight = slower). The exclusive combat skill is a **180°
  turning rush** (double-tap reverse while drifting).
- **Items.** Repair capsule, personal repair kit, party repair kit, revival item, and **item repair** (restores the
  durability of the Neo gear itself), slot expansions, attack/defence buffs, HUV-disruption items.
- **Rewards.** EXP and Mito per chapter (5 000-10 000 originally, raised to 30 000-50 000) and per operation
  (150 000 / 200 000 / 250 000). Chapters also feed the crew research / contribution systems.

## The client's messages (2016 exe; names from its own handler registrations, `tools/re2016/handlers_2016.json`)

Full layouts with addresses: the module docstring of `dcemu/native/game/neocity.py` (sessions 46). The research notes
the workers wrote (`docs/neo_work/NEO_PROTOCOL_A.md`, `_B.md`) are kept out of git (`.git/info/exclude`) and call
the chapter key a "player serial" in many places: **that is wrong** (see "Chapter keys" below).

| C>S | S>C (handler) | What |
|---|---|---|
| `0xe88` (68) | `0xe88` Cmd_NeoCitySuggest (`0x53e440`) | party suggestion of a chapter; the S>C copy carries the leader's name @0x1a |
| `0xe8c` (18) / `0xe8b` (14) | `0xe8c` Cmd_NeoCityAgree (`0x53e3c0`) / `0xe8b` Cmd_NeoCityReject (`0x53e6c0`) | answers, broadcast to the party; reject reasons 0-4 -> texts 12315-12319 |
| — | `0xe89` Cmd_NeoCityLoad (`0x53e400`) | **loads the map**: @6 map 6-9 (NeoOros/Cras/Koinonia/MoonPalace, `0x788a2c`), @0xa chapter key, @0xe run id |
| `0xed8` (10) | `0xed9` Cmd_NeoChapterStartAck (`0x526ce0`) | sent by the client from the `0xe89` handler itself; creates the chapter activity |
| `0xedc` (10) | `0xedd` Cmd_NeoQuestStartAck (`0x526d30`) | quest start (chapter key, quest index) |
| `0xeeb` (26) | `0xeea` Cmd_NeoQuestGoalPlaceAck (`0x533fb0`) | goal placed, result 1 |
| `0xeef` (14) | `0xeee` Cmd_NeoMissionCompleteAck (`0x521940`) | mission done |
| `0xeed` (14) | `0xeec` Cmd_NeoMissionCompleteParamAck (`0x53cee0`) | per mission type counters (not decoded: not answered) |
| `0xede` (14) | `0xedf` Cmd_NeoQuestCompleteAck (`0x533cb0`) | quest reward: exp, Mito, 3 x u64 exp counters, level, 3 items |
| `0xeda` (10) | `0xedb` Cmd_NeoChapterCompleteAck (`0x52e960`) | sent by the client itself after the last quest; 0xcb bytes for one record |
| `0xee8` (10) | `0xee9` Cmd_NeoChapterRewardAck (`0x526d80`) | 16 reward slots of 16 bytes |
| `0xee7` (18) | `0xee6` Cmd_MyNeoQuestListAck (`0x52ea00`) | cleared chapters (key @0, u16 count @0x14); **drops the client's activity** |
| `0xee2` / `0xee4` / `0xef0` | `0xee3` QuestFail / `0xee5` QuestGiveUp / `0xef1` ChapterGiveUp | `0xef1` @6 = the giver's serial; its own client leaves the area and sends `0xe8a` |
| `0xef2` (14) | `0xef3` Cmd_NeoDyingMsgReq (`0x526ec0`) | death (flag 0) / alive again (flag 1) |
| `0xef5` (10) | `0xef6` Cmd_NeoChapterBonusMissionAck (`0x5218e0`) | "n / 10" bonus count @0xa |
| `0xe8a` (6) | — | the client left the Neo area |
| `0xc6` (0xa+0x40n) | `0xc7` Cmd_NeoHuvRes (`0x53baf0`) | the client asks for its enemies; the server places them (gate: app state 0x13 or area 84-99) |
| `0xcd` (42) | `0xcd` Cmd_NeoHuvHit (`0x525a10`) | hit; the S>C copy adds Mito @0x1a, i64 @0x1e, exp @0x26 |
| `0xce` (64) | `0xce` Cmd_NeoHuvEnd (`0x525d60`) | kill (Huv Param ID @0x36, killer @0x3e) |
| `0xcf` (11) / `0xd0` (16) | `0xcf` Cmd_NeoHubTargeting / `0xd0` Cmd_NeoAggro | targeting / hate, relayed |
| `0xf41` (22) | `0xf42` Cmd_NeoTurretRes (`0x53edd0`) | turrets; `0xf44` Cmd_NeoTurretSwitch changes their controller |
| `0xf3e` (2) | `0xf3f` Cmd_ScriptNeoHuvDelRes (`0x5259f0`) | delete the scripted HUVs |
| `0x4c4` (6) | `0x4c5` Cmd_RepairNeoPartsAck (`0x52a870`) | Neo part repair, code 1 = done |
| `0xf4d` (6) | `0xf4e` Cmd_NeoPlayerHPReceiveAck (`0x53e630`) | player HP sync (below) |
| — | `0xfc0` Cmd_NeoPvpDamage (`0x53eb50`), `0xf50` Cmd_NeoHusExplosionAck (`0x53ecb0`) | **the only ways an enemy damages a player**: server-driven, needs server enemy AI |
| — | `0xe81` Cmd_NeoWSlotExtended (`0x52d0f0`) | weapon slot extension (u8, u32 expiry ms) |

**Not Neo** (corrected 2026-11-14): `0xf4b` is Cmd_PartyPing, `0xfc2` is Cmd_AssistTransferUseAck, `0xfc3`
Cmd_GMEventRush, `0xfbe` Cmd_PvpCollisionDamage.

### Chapter keys

The client loads `World/NeoData/NC_chapter.xlt` itself (`0x7ae1a0`) and keys each chapter by its **0-based data-row
order** (`[chapter+4] = row counter`), in the map `[0x9e5b70+0x148]`. Every Neo message field that the research notes
call "player serial" in `0xe89`, `0xed8`/`0xed9`, `0xedc`/`0xedd`, `0xedf`, `0xeea`, `0xeee`, `0xeda`/`0xedb`,
`0xee3`, `0xee4`/`0xee5` @2, `0xef0` @2, `0xef2` @2, the `0xee6` records and the `0xc7` record @0x30 is this key.
Quests: 0-based order of a chapter's rows in `NC_quest.xlt` (`0x7aa9b0` with a counter reset per chapter, `quest+0xc0` =
chapter key). Unlocking is client side (`0x7abee0`): level within need-level_low..high and the previous chapter cleared
(from `0xee6`). Only Neo Oros has a map in the 2016 client (`Data/World/neooros.agt`); all 8 chapters are Neo Oros.

## The player HP pair: `0xf4d` -> `0xf4e` (corrected 2026-11-14)

- `0xf4d`: one u32 = **the car's current HP** (`0x4430d0` reads it with the getter `0x760900` and sends it through
  `0x54c740` -> `0x866270`, about once a second, only while it is > 0 and the app flag `[0x442790()+0x198]`,
  the MissionBattleAdv content flag, is set). The `0x111a` (4378) in every 2016 log is an HP, not a XOR base.
- `0xf4e`: one u32 HP, stored **as is** by the setter `0x760910` (which XORs it with the object's own key at
  `+0x1da0`) when 0 < HP <= 20000 (`0x53e663`); 0 / -1 store -1; else `"Receive HP : %d"` (`0x956c90`). The stored
  HP is given to the car when it is created (`0x4b5320`; -1 = max HP, vtable `+0x60`).

Stage 1 had answered `0x111a ^ 20000` = 24378, which the client refused. Now the server keeps the last report and
echoes it.

## Staged plan

1. **Entry and chapter state.** Find what marks the player as "in Neo City" (`[player+0x198]`) and which message starts a
   chapter; without it none of the combat messages are accepted.
   **Done (2026-11-13): the region gate is content flags, not a message.** The client's own symbols name the whole
   feature (`City.NeoCity`, `City.NeoOros/Cras/Koinonia/MoonPalace`, `Main.NeoCityMainUI`, and the `Cmd_Neo*` handlers
   below). The flags are in `dcemu/data/flags_2016.tsv` (0x14 bits 21-25) and the emulator never sent them — the 2008
   `Contents.ini` has no Neo entry — so `login.content_flags()` now sets all five for 2016. `[session+0x198]` is
   **not** the Neo flag: the session constructor fills it from the `MissionBattleAdv` content flag (`0x946dbc`) and
   `+0x199` from `UseHeadLight`, so the HP handler's guard is that flag, not Neo City.
2. **Entry, chapters, quests, rewards** (session 46, 2026-11-14, **not yet tried in game**): `0xe88`-`0xe8c` party
   suggest / agree / reject, `0xe89` load, `0xed8` -> `0xed9`, quests `0xedc`-`0xedf`, goals / missions `0xeeb`, `0xeef`,
   chapter clear `0xeda` -> `0xedb` (kept in SKID_QUEST_TB as QUESTID `neo_<chapter_ID>`, FAILNUM = clear count),
   `0xee7` -> `0xee6`, give-ups, death `0xef2` -> `0xef3`. Rewards: quest exp / Mito / items from NC_quest, chapter exp /
   Mito parsed from NC_chapter's summary text. One area instance per run (`area.py`, `neocity.neo_area_key`).
3. **Enemies** (session 46, not yet tried in game): the client asks for its own enemies (`0xc6`), the server places
   them (`0xc7`) for the run, relays hits / kills / aggro, rewards kills; turrets `0xf41` -> `0xf42`; repair `0x4c4`
   -> `0x4c5` (free: no part durability is kept).
4. **Open.** Enemies never damage players (the server has no Neo enemy AI; `0xfc0` / `0xf50` are never sent).
   `0xeed` -> `0xeec` counters, the `0xedb` body, `0xee9` reward slots, `0xef6` count, `0xe80`/`0xe82` -> `0xe81`
   weapon slots. Neo gear (plasma weapons, armour) items and their durability.

## The client's own names for the feature (strings in the exe)

Reading the exe's symbol strings names everything, which is the map for the remaining work:

- Flags: `City.NeoCity`, `City.NeoOros`, `City.NeoCras`, `City.NeoKoinonia`, `City.NeoMoonPalace`,
  `Main.NeoCityMainUI`, `NeoItemDurableUI`.
- Entry / chapter: `Cmd_NeoCitySuggest`, `Cmd_NeoCityAgree`, `Cmd_NeoCityReject`, `Cmd_NeoCityLoad`,
  `Cmd_NeoChapterStartAck`, `Cmd_NeoChapterCompleteAck`, `Cmd_NeoChapterGiveUpAck`, `Cmd_NeoChapterRewardAck`,
  `Cmd_NeoChapterBonusMissionAck`, `Cmd_MyNeoQuestListAck`, `Cmd_NeoQuestStartAck`, `Cmd_NeoQuestCompleteAck`,
  `Cmd_NeoQuestFailAck`, `Cmd_NeoQuestGiveUpAck`, `Cmd_NeoQuestGoalPlaceAck`.
- Combat: `Cmd_NeoPlayerHPReceiveAck` (the `0xf4e`), `Cmd_NeoHuvHit`, `Cmd_NeoHuvRes`, `Cmd_NeoHuvEnd`,
  `Cmd_NeoHusExplosionAck`, `Cmd_NeoTurretRes`, `Cmd_NeoTurretSwitch`, `Cmd_NeoTurretFire`, `Cmd_NeoAggro`,
  `Cmd_NeoHubTargeting`, `Cmd_NeoDyingMsgReq`, `Cmd_NeoPvpDamage`, `Cmd_NeoMissionCompleteAck`,
  `Cmd_NeoMissionCompleteParamAck`, `Cmd_NeoWSlotExtended`, `Cmd_RepairNeoPartsAck`, `Cmd_ScriptNeoHuvDelRes`.
- Data tables the client loads: `NeoAI.xlt`, `NeoHuvParam.xlt`, `NeoOros_PatrolPos.xlt`, `NeoCras_PatrolPos.xlt`,
  `NeoKoinonia_PatrolPos.xlt`, `NeoMoonplace_PatrolPos.xlt`, `Neo_Prologue.nif`.


Each step needs the corresponding handler read (`tools/re2016`), like the crew work in sessions 42-44.
