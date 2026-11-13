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

## The client's messages (measured; `pair` = the C>S request it answers)

| C>S | S>C handler | Subsystem |
|---|---|---|
| `0xee2` | `0xee3` (`0x526db0`) | Neo combat state |
| `0xee4` | `0xee5` (`0x526e10`) | Neo combat state |
| `0xee7` | `0xee6` (`0x52ea00`) | Neo combat state |
| `0xee8` | `0xee9` (`0x526d80`) | Neo combat state |
| `0xeeb` | `0xeea` (`0x533fb0`) | Neo combat state |
| `0xeed` | `0xeec` (`0x53cee0`) | Neo combat state |
| `0xeef` | `0xeee` (`0x521940`) | Neo combat state |
| `0xef0` | `0xef1` (`0x533e70`) | Neo combat state |
| `0xef2` | `0xef3` (`0x526ec0`) | Neo combat state |
| `0xef5` | `0xef6` (`0x5218e0`) | **NeoChapterBonusMission**: sends u32, u32; the answer shows "n / 10" (text 12699) |
| `0x4c4` | `0x4c5` (`0x52a870`) | **Neo item repair**: u32 id @2 -> u32 id, u32 result (1 = done) |
| `0xf4d` | `0xf4e` (`0x53e630`) | **Player HP/durability sync** (see below) |
| `0xf4f` | `0xf50` (`0x53ecb0`) | Neo combat state |
| `0xf3e` | `0xf3f` (`0x5259f0`) | Neo combat state |
| `0xf40` / `0xf41` | `0xf42` (`0x53edd0`) / `0xf44` (`0x53ee40`) | Neo combat state |
| `0xf43` | `0xf44` | Neo combat state |
| `0xf49` (454 bytes) | `0xf4b` (`0x537e30`) | Neo combat state |
| `0xf4a` | `0xf4b` | Neo combat state |
| `0xf4c` | — | Neo combat state |
| `0xfbf` | `0xfc0` (`0x53eb50`) | Neo combat state |
| `0xfc1` (13 bytes: `0x88, 0x6b, 1`) | `0xfc2` (`0x52d5f0`) / `0xfc3` (`0x545330`) | GM event |

Neighbouring messages that are **not** Neo City, for the record: `0xf51`-`0xf5e` are World Laptime rankings,
`0xfb0`/`0xfb1`/`0xfb2` honor ranking, `0xfb3` WhisperDeny, `0xfb9`/`0xfba` Valentine, `0xfbd`/`0xfbe`
PvpCollisionDamage.

## The one message whose layout is known: `0xf4d` -> `0xf4e` (player HP)

- `0xf4d`: one u32, the client's **XOR base** for this player (observed constant `0x111a`), sent about once a second
  while the HP mode is active.
- `0xf4e`: one u32 = `base ^ hp`. The handler (`0x53e630`) first tests `[player+0x198]` (the Neo mode flag) and does
  nothing when it is 0; it accepts `0 < hp <= 0x4e20` (**0-20000**), stores `[player+0x1da4] = [player+0x1da0] ^ value`
  (`0x760910`) and otherwise prints `"Receive HP : %d"` (format string `0x956c90`).

So the server must answer with the base XORed by the current durability. 20000 is the client's own upper bound.

## Staged plan

1. **Entry and chapter state.** Find what marks the player as "in Neo City" (`[player+0x198]`) and which message starts a
   chapter; without it none of the combat messages are accepted.
   **Done (2026-11-13): the region gate is content flags, not a message.** The client's own symbols name the whole
   feature (`City.NeoCity`, `City.NeoOros/Cras/Koinonia/MoonPalace`, `Main.NeoCityMainUI`, and the `Cmd_Neo*` handlers
   below). The flags are in `dcemu/data/flags_2016.tsv` (0x14 bits 21-25) and the emulator never sent them — the 2008
   `Contents.ini` has no Neo entry — so `login.content_flags()` now sets all five for 2016. `[session+0x198]` is
   **not** the Neo flag: the session constructor fills it from the `MissionBattleAdv` content flag (`0x946dbc`) and
   `+0x199` from `UseHeadLight`, so the HP handler's guard is that flag, not Neo City.
2. **Durability.** Keep a per-character Neo HP, answer `0xf4d`, and apply the damage the client reports.
3. **Enemies.** Spider HUS / HUB / HUV / turrets: spawn lists and AI are server-side in the original (the client only
   draws and reports hits).
4. **Gear and repair.** Plasma weapon use, armour, and `0x4c4`/`0x4c5` item repair (needs item durability, which the
   emulator does not keep yet).
5. **Rewards.** Chapter / operation EXP and Mito, and the `0xef5`/`0xef6` chapter bonus.

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
