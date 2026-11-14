# Handover: continuing openDC on another device

Written 2026-10-16 (end of session 13) for moving the work from the Steam Deck to another machine, for a person or
a new Claude session. The detailed research log is `docs/EMULATOR_NOTES.md` (newest entries at the top); this file
says what to copy, how to set up, how the work is done, and what is open.

## Session 47 (2026-11-14): EU = V-grade rules on the US client — resume here

- EU rules differ from US in: parts by V grade, battle zone and channel battle by V grade, no stat points for the
  level, drops by V grade (`emulator.ini [nation]`, `nation.RULES`); the rest is US (complete bonus, new physics).
- **The EU client is retired** (files kept). The US client plays either rule set: its launcher's `[client] rules =
  us | eu` (or `--us` / `--eu`; `./launch.sh client eu`), 2011 and 2016. For EU it makes the client send nation 8 at
  login (memory only) and swaps in EU copies of the client tables. **After any change to the client tables or the
  EU lines of emulator.ini, run `.venv/bin/python -m tools.eu_rules build` (2016) and
  `.venv/bin/python -m tools.eu_rules build "../Client US"` (2011)**, else the launcher keeps the US tables.
- **New, off by default (2016):** PvP collision damage (`[battlezone] attack_player = 1`), welcome-back popup
  (`[promotion] enabled = 1`, reward groups optional); on: GM `gmrushevent [name] [hp]` (GM accounts only see it),
  0x1d3 car change in Real Match rooms, 0x240 ReplaceCar answer, 0x6c return rental car.
- **Open (user, 2026-11-14):** Oros city traffic was missing on the first entry on the 2016 client and came back after
  re-entering the city. The server had sent normal traffic all along (checked: right lanes, models, record size), so it
  looks like a first-entry timing issue in the client (traffic sent before the city finished loading?). Watch for it.
- **Fixed, confirmed in game:** the 2016 Drift Booster (`i_d_passive_02`): the 2016 visual item record has its assist
  slots at +0x50, not +0x4c (client 0x783457 / 0x69ff30); see EMULATOR_NOTES session 47.
- To try: start each client with `--eu`: part tooltips "Required Grade", Newbie / Pro buttons by V grade, channel
  battle minimum grades; the emulator log shows `client nation 8 (EU eng)` at the login; then `--us` (tables back:
  the launcher log says "US tables put back"). Details: EMULATOR_NOTES session 47.

## Session 46 (2026-11-13/14, overnight): Neo City stages 2-3, rankings, World Match, DCGP — resume here

**Worked while the user slept; nothing tried in game, nothing committed.** Delegated to OpenCode DeepSeek
(`opencode-go/deepseek-v4.1-flash`); the lead extracted the evidence, wrote the specs, re-checked the key client addresses
and reviewed every edit. 278 tests pass (`.venv/bin/python -m unittest discover -s tests -t .`: **pytest is not
installed in the venv**). The emulator was restarted with the new code (2016, 111xx). Details: EMULATOR_NOTES session 46,
`docs/NEOCITY.md`, the module docstring of `dcemu/native/game/neocity.py`.

### Done, not yet confirmed in game

- **Neo City entry / chapters / quests** (`neocity.py`): suggest / agree / reject / load (`0xe88`-`0xe8c`, `0xe89`),
  chapter start, quests, missions (patrol / collect / investigate / destroy rules from the client), quest and chapter
  rewards from the client's own `NC_quest` / `NC_chapter` (copied to `server_data_2016/NeoData/`), chapter clears in
  SKID_QUEST_TB (`neo_c_0000` ...), give-ups, death. One area instance per run (area.py; Neo Oros is area 84).
- **Neo enemies**: the client asks (`0xc6`), the server places them for the run (`0xc7`), hits / kills / aggro relayed,
  kill rewards (level x 10 exp and Mito: **our amounts**, plus the enemy's reward group), turrets, free part repair,
  explosion damage to another player forwarded (`0xf4f` -> `0xf50`).
- **HP pair corrected**: `0xf4d` reports the car's HP; `0xf4e` takes a plain HP. Stage 1's `base ^ hp` was refused by
  the client (> 20000), so it never did anything.

- **Rankings window** (`game/rankings.py`, flag `Main.New2011RankSystem` = 1 for 2016): the client now connects to the
  ranking service (11151) and gets character / crew / honor pages. The data is ours (EXP order; crews by points).

- **World Match Lap Time** (`game/worldmatch.py`), **off**: set `emulator.ini [worldmatch] enabled = 1` and restart to
  try it (battle zone > World Match button). Off means nothing changed for the normal Lap Time.

- **DCGP** (`game/dcgp.py`), **off**: `[dcgp] enabled = 1` shows the DCGP tab; team choice, season window, points
  from ordinary battle-zone races (ours), reward claim. No DCGP Stadium channels yet.
- **Crew contribution rank tab**: retry it now that the ranking connection exists (`Main.New2011RankSystem`).

### To try in game (in this order)

0. Open the Ranking window (each tab, a page, a name search). Expect a `ranking` connection in the newest log.

1. Log in a level 40+ character on 2016 and look for the Neo City entry: the main menu (`Main.NeoCityMainUI`), the
   minimap / city menu, or an NPC in Oros. Nothing tells yet how the Neo window opens; `grep -n neocity` in the newest
   `logs/2016/*.msgs.txt` shows every Neo message the client sent.
2. Start chapter 1 alone ("The Future Mitron Island", solo, level 40). Expect `0xe89` then the client loading Neo Oros.
3. Drive the first quest: patrol posts should tick off, enemies should appear (`0xc6` / `0xc7` in the log).

### Open

- How the Neo window opens; `0xeed` -> `0xeec`, the `0xedb` body, `0xee9` reward slots and `0xef6` are guesses; Neo gear
  items / weapon slots (`0xe80`/`0xe82` -> `0xe81`); whether Neo enemies fire weapons at all.
- Everything in the session 45 "Open" list below except the Neo City items.

## Session 45 (2026-11-13): 2016 in-game test round — crew, cars, aero, Neo City start

**User tested in game all session.** 250 tests pass. Everything below is committed and pushed (`99865f8` at the end).
The emulator was left **running** (pid 1658250, 2016 ports 111xx, database `skdb2016test`) and the **client closed**.

### What was fixed and CONFIRMED in game

- **Porting aero sets (`portorigin` / VisualItem).** The 2016 client draws an aero body by its number, and in the
  original table every non-generic `Aero Parts Set` row has **index == its position in the category**. The port
  appended the new cars' rows with their Origin index numbers, so 220 rows broke that (`pc_0449s_02`, the Hurricane's
  B body, sat at position 656 with index 674), and a ported car stayed on its default body. Renumbered to the row
  position in `server_data_2016` **and** the client's `Data/Init.agt`; `portorigin.renumber_aero()` keeps it. **User
  confirmed the fix.** The Kicker test that found it: its style-1 aero is a category **4 bumper**, not a category 6
  body, which is why original cars were unaffected.
- **Crew creation (2016).** My `RANK_ORDER_SQL` had reused the name `RANK_SQL` (the member-rank UPDATE, 4 params), so
  the UPDATE won and every `team()` call raised after a create: the crew was made in the database but the client got
  no `0x34b`. Renamed; `test_ranking_statements_are_distinct` guards it. **Crew creation and the crew window work.**
- **Crew grade / ranking.** `rankings()` numbered every open crew 1..N, so the only crew (0 points) took rank 1 ->
  grade 3 (S) with the red S nameplate. Now only a crew with `CHANNELWINCNT` or `TEAMPOINT` > 0 is ranked; everything
  else is written back to `TEAMRANKING = 0` (the client's "no grade"). The grade also no longer rides in the top byte
  of the u32 at `+0xeb` — `0x536674` does `lea eax,[eax+eax*1+0xef]`, i.e. the client uses that u32 as an index — so
  the rank is written plain at `+0xeb` and the grade at `+0xef`.
- **Team Research Lab works** (user). Its gate is crew EXP: Team Level 1 = 50 000 crew EXP (1 % of members' EXP), and
  the 26 research rows need level 1-9.
- **Donations (`0xceb`).** The sender forces the u32 at `+2` to 0 (`0x8690db`), so kind is `@6` and the amount `@0xa`;
  the old code read that fixed zero as the kind and dropped every donation. kind 0 = OMD Gold Mark (the account's
  G Coin, 1 research point each), kind 1 = Mito (1 point per 100).
- **`gmcrewexp`** — `tools.gmctl crewexp NAME AMOUNT` and the in-game chat command `gmcrewexp [name] amount` (GM
  only): crew EXP + research points, so Team Level 1 is reachable without grinding.

### Done, not yet confirmed in game

- **Neo City stage 1**: the region gate is content flags, not a message. `login.content_flags()` now sets
  `City.NeoCity` + `City.NeoOros/Cras/Koinonia/MoonPalace` (flags_2016.tsv `0x14` bits 21-25) for 2016. **Check Oros
  for the entry quest.**
- **Neo City HP sync** (`neocity.py`): `0xf4d` -> `0xf4e`, `base ^ hp`, full 20 000 until enemies exist.
- **Decals**: `portorigin` never copied `data\decal\pc_XXXXs_decalNN.dds` (it only collected `data\vehicle\`); 143
  decals for the ported cars are in `Data/vehicles.agt` again.

### Open

- **Crew "contribution rank" tab** shows `"is feature is currently unavailable"`. `Team Research Point = +0x290` is
  ours and correct (screenshot), `Team Contribution 50 000 000` is derived by the client. The message is in no client
  file (GlobalText, GlobalContent, the exe; `game.nui` has no plain strings), the tab sends no request, the ranking
  service is an empty stub, and `TeamSystemRenewalStep` is already 3. **Next cheap test: add a second member to the
  crew** — a ranking of one may be what the client calls unavailable.
- **Neo City stages 2-5** (`docs/NEOCITY.md`): chapter entry (`Cmd_NeoCitySuggest/Agree/Load`), enemies, gear /
  `0x4c4` repair, rewards. The client's own `Cmd_Neo*` symbol names are listed there as the map.
- **Still unimplemented features** (`docs/OPEN_FEATURES.md`, measured): DCGP `0x776-0x778`, World Laptime
  `0x3c0`/`0xf51-0xf5e`, honor ranking `0xfae-0xfb2`, Neo HUS combat, Neo repair `0x4c4`/`0x4c5`, PvpCollisionDamage
  `0xfbd`/`0xfbe`, GMEventRush `0xfc3`, rank pages `0xfa2-0xfa5`, plus size-changed messages never built.
- **The only requests the client sends that we ignore** are `0x0f4d` (Neo HP poll, answered now), `0x0e8d` and
  `0x02d5` (no reply expected), `0x0fc1`/`0x0fb4` (GM event) and `0x0777` (DCGP).

## Session 44 (2026-11-13): 2016 cars re-ported from the newer Skid Rush build

Details: EMULATOR_NOTES session 44. 240 tests pass.
- The newer Skid Rush build's packs use the **standard** NayaPack key (byte 16 = 0x31); the 2025 Origin client keeps
  0x6c. `tools/portorigin.py` gained `--key auto|origin|standard`.
- `portorigin reset` restored the pre-port 2016 packs; then `apply --origin ../SkidRush/client` added **243 player
  cars** (Unique Ids 89-683, 234 above 449) with 2112 vehicle files. First test: start the 2016 client, check the
  dealership list, buy one, garage picture, drive it, its aero sets.
- server_data_2016's tables were rewritten (they are in git); the client packs are not.

### Open from the 2026-11-13 2016 test session (user reports)

- **Crew donations** (0xceb) were dropped: the sender forces the u32 at +2 to 0 (`0x8690db`), so kind is `@6` and the
  amount `@0xa`; the handler read that fixed zero as the kind. Now kind 0 = OMD Gold Mark (the account's G Coin, 1
  research point each) and kind 1 = Mito (1 point per 100). Not yet tried in game after the fix.
- **Crew EXP for testing**: `tools.gmctl crewexp NAME AMOUNT` and the chat command `gmcrewexp [name] amount` (GM only)
  give crew EXP + research points, so Team Level 1 (50 000) is reachable without grinding.

- **SOLVED** (user, 2026-11-14; the aero index renumbering of session 45, confirmed in game there). The record below
  is kept for reference.
  **Hurricane's second aero kit does not change the car's look** (user, 2026-11-13). Investigation (2026-11-13): the
  server-side data is **correct and complete** — VisualItem rows 673/674/675 (ids 21934/21935/21936, models
  `pc_0449s_01/02/03`) are flagged for cars 449/450/451, the client's own Init.agt has the same rows, VShopItem
  1941/1942/1943 exist, and all three `.nif` plus `pc_0449s_map/mask/light` are in `Data/vehicles.agt`; the index
  numbers match the Skid Rush source exactly. Two concrete findings:
  1. **The A-type set (673) is the car's default part** — VShopItem 21934 has `Default Part = 1`, `SellStage = 0`,
     price 0 — so equipping it is *supposed* to change nothing. The B-type (674) is the first paid set
     (`SellStage = 1000`, 1 200 000 Mito), the C-type is Hancoin only.
  2. **`pc_0449s_02.nif` and `pc_0449s_03.nif` are byte-identical in the source client** (md5 `cd3bb5f7f505`,
     809 189 bytes, from patch.010 and patch.006), and the port copied that faithfully. So B and C must render the
     same; only A (593 991 bytes) differs.
  Next step: the client's own application of the aero slot — car model 0x471170 reads the category-6 value at +0x12
  and validates with 0x769460; it is not established how it turns 674 into `pc_0449s_02`. Nothing was changed.
  **Follow-up (user: "equipped the B aero and it looks exactly same as A; default car look is A"):** the item is the
  *generic* set, not the car's own: SKID_VSITEM_TB has `pc_Aero` GID 100212 on car 8 (SKID_CAR_TB car 8 = type 449,
  the Hurricane) with `ITEM_DATA = '          449121935'` = 10 reserved chars + car 449 + style 1 + VisualItem uid
  21935 = `pc_0449s_02` (B). `misc.aero_model` decodes exactly that (`tail[-5:]` = 21935 -> `visuals[21935].index` =
  674). So the server's value and the stored item both name B; the client still renders A. Also note the older rows
  for cars 2 and 5 carry a **different ITEM_DATA format** (`'4020000011079220216'`, no 10-space prefix), so those may
  decode to 0. The defect is therefore inside the client's own aero application (or in the generic-set decode), not in
  the ported tables; the next step is that code, not the data.
  **Answer (user equipped Aero2):** both purchases carry the **same** text. `SKID_VSITEM_TB` and the 0x4b3 log lines:
  `buy visual item pc_Aero (Aero) text '          449121935'` (22:07:55) and `pc_Aero2 (Aero2) text
  '          449121935'` (22:11:52). The client itself sends the item text (`vshop.item_text` stores it verbatim), so
  Aero and Aero2 both name car 449, style 1, uid 21935 = the *same* B model — they are the same item, which is why
  the look does not change. The generic rows (20293-20470) are byte-identical between the original 2016 table and the
  ported one, so the port did not flatten them. The style digit is chosen in the shop window: the text sits at
  `[window+0x4e8]`, is copied at 0x6d56a3 and sent through the 0x4b3 builder (ctor 0x858d90, its only caller
  0x6d5788). **Next:** find what fills `[window+0x4e8]` — i.e. how the client picks the style digit — or test the
  car's *own* set (VShopItem 1942, "Hurricane 에어로셋 01(B타입)") instead of the generic "Aero2".
  **Checked after the user's "it is the car model, not the item" note:** the aero model itself IS ported —
  `vehicle\player\pc_0449s_02.nif` is in the pack, 809 189 bytes, md5 `cd3bb5f7f505`, byte-identical to what BOTH
  source builds ship (Origin patch.006 and Skid Rush patch.010), and different from the default `pc_0449s_01.nif`
  (593 991, `bbf3bcc878d9`). So the modified body exists; the client still renders the default one. The client's own
  `GameLog_*.txt` shows per-car lookups failing for other cars (`GetVehicleDisplayInfo - wrong id: N` for 169 player
  cars that have no VehicleDisplay row — the Hurricane 449 does have one) and `GetPartData - wrong id: 0` 34 times,
  plus `GetDecalInfo fail 683,12` / `662,12` (the missing decal textures). Nothing in the log names 449 or the aero.
  **Key next test:** equip an aero set on an ORIGINAL car (e.g. the Kicker/Drifter). If its body does not change
  either, the fault is the emulator's aero slot value in general; if it does, it is specific to the ported cars.
  **Root cause found (user's Kicker test):** the Kicker's style-1 aero resolves to a **category 4 bumper** part
  (`pc_0000c_b02`, index 2), while the Hurricane's resolves to a **category 6 whole-body set** (`pc_0449s_02`).
  In the original 2016 table every non-generic "Aero Parts Set" row has **index == its position in the category**
  (653 rows, the only exceptions the six index-0 generic sets at the end). `portorigin` appended the new cars' rows
  with their Origin index numbers, so 220 rows broke that: `pc_0449s_02` (the Hurricane's B body) sat at position 656
  with index **674**, and the client draws the aero body by that number — an out-of-place number leaves the car on its
  default body, which is exactly "B looks like A". **Fixed:** the aero index column is renumbered to the row position
  (220 rows; the six generic 0 rows untouched), in `server_data_2016/Init/VisualItem.xlt` and in the client's
  `Data/Init.agt`; `portorigin.renumber_aero()` now keeps the invariant on future ports. Not yet confirmed in game.
- **The cars' decals were never copied**: `portorigin` only collected `data\vehicle\`, so `data\decal\pc_XXXXs_decalNN.dds`
  was always skipped (the client logs `GetDecalInfo fail <car>,12`). Added to the tool's collection and applied now:
  **143 decal textures** for the ported cars are in `Data/vehicles.agt` again (the Hurricane's
  `pc_0449s_decal01/02.dds` are there). The other ~79 source decals belong to cars the 2016 build already had.
- **VehicleDisplay**: 6 ported ids (446/447/448/569/570/644) have no row, but the Skid Rush source has none either,
  so that is upstream, not the port. Left alone; the client only logs it.
- **Missing decal textures for the ported cars**: `decal\pc_XXXXs_decal01.dds` / `_decal02.dds` were not copied by
  `portorigin` (it copies the `.dds` the *models* name, and the aero/body NIFs do not name the decals). Two are known
  missing for the Hurricane (patch.006 / patch.007). A car's own decals would show blank.
- **Crew "contribution rank" not implemented.** 0xcee (10 bytes, i64 @2, sender wrapper 0x86a3c0, its only caller
  0x719333) is answered by 0xcef (handler 0x52cd60: u32 @0xa -> window[conn+0x40c] +0x8, u32 @6 -> +0xc, byte @0xe);
  0xcf0 (6 bytes, u32 @2, wrapper 0x86a450, callers 0x796f43 / 0x816516 / 0x816967 / 0x819923 / 0x81a26b) by 0xcf2
  (handler 0x52cdd0: u32 @2 -> a bool + window[conn+0x3e8] 0x656630). Neither is implemented: **what they carry was not
  determined** — the handler reads only 3 fields and calls window setters, so they look like state notifications
  rather than a list. Do not guess the payload; find the window 0x40c / 0x3e8 owners first.
  **Searched the client's own text table (Data/Localize.agt -> Localize\GlobalText.xlt, 3163 rows): there is NO
  "contribution ranking" string.** The crew-contribution UI is a single label `12816 팀공헌도` and `12832 팀 연구
  포인트`; the only ranking texts are the team ladder (12027 / 12721 / 11333) and the race rankings. So there is no
  per-member contribution ranking list to fill — the feature is one number plus the shop's cost (12845 "<$contribpoint>
  팀 공헌도"). The i64 at XiStrTeamInfo +0x290 is what the contribution panel shows with `%I64d` (0x676475 reads the
  player's copy at +0x1d5c, i.e. record +0x290, base +0x1acc) and crews.fill() currently puts the **crew's research
  points** there — a guess. Which label owns it (12816 or 12832) is not yet established.
  **Menu opened in game (2026-11-13 22:34):** no new request — only `0x348` act 0x407 -> `0x349` and `0xce6` board
  0x408 -> `0xce7` (the news board, now 4 entries). So the contribution view is fed entirely by the crew record, and
  there is no separate message to implement. The record as it stands: crew EXP 500 000 000, level 17,
  **+0x290 = 499 900 011** (our research points). The client reads +0x290 with `%I64d` at 0x676475 (contribution
  panel) and 0x678cd5; nothing reads +0x298 (player +0x1d64). **Question to settle it:** which label does that big
  number sit next to in the crew window — 12816 팀공헌도 or 12832 팀 연구 포인트?
  **Screenshot (2026-11-13, user):** the crew window's **Team Research Point = 499 900 011**, so `+0x290` is the
  research points and our fill is correct — no change needed there. The header shows **Team Contribution 50 000 000**,
  which no record field equals (crew EXP 500 000 000 / 10; the client derives it). The **Contribution Rank** tab
  (columns Ranking / Nickname / Point Distribution / Team Contributor / User Info) renders **"is feature is currently
  unavailable"** and sends nothing to the game service. That string is in **no** client file: not
  `Localize\GlobalText.xlt` (3163 rows), not `Localize\GlobalContent.xlt`, not `DriftCity.exe`, and `game.nui` holds
  no plain strings at all (it has no "Contribution", "Ranking" or "Nickname" either), so its text table is packed.
  `TeamSystemRenewalStep` is already 3 in GlobalContent and the ranking service (`native/ranking.py`) is an empty
  stub that answers nothing. **Next hypothesis to test (cheap): the crew has 1 member** — a ranking of one may be
  what the client calls unavailable; try with a second member before disassembling the tab.
- **Team Research Lab is implemented but gated.** 0xce8 / 0xce9 (list), 0xcea (start), 0xcec (buy), 0xceb (donate) are
  in crewlevel.py and the client's own TeamResearchTable is sent. The 26 research rows need Team Level 1-9, and
  TeamLevelExpBuffTable makes **level 1 = 50,000 crew EXP**; crew EXP is 1% of members' EXP (progress.add_exp ->
  crewlevel.gain), so a new crew is level 0 and every research is locked. Racing with a crew member is the way in.


## Session 43 (2026-11-13): crew Acceptance page (2016), crew grade / ranking

Details: EMULATOR_NOTES session 43. **Nothing was tried in game.** 240 tests pass.
- The Acceptance page **is** pinned down: it asks with **0x357 act 0x3f4** and is answered by 0x358 act 0x3f4 (the same
  member entry); the Accept / Reject buttons send **0x36f** (i64 applicant @2 + u8 result @0xa). Client addresses in
  the notes.
- `SKID_TEAMREQ_TB` keeps the requests for 7 days, so a request to an **offline master** is no longer refused (2016
  only; 2011 keeps 20199). `0x368` and `0x36f` share `approve`, which now also accepts an offline applicant.
- Crew ranking (`TEAMRANKING`) is computed from TEAMPOINT (ours) and the grade letter is packed into the top byte of
  XiStrTeamInfo's u32 at +0xeb. **The S/A/B = 3/2/1 encoding is a guess;** the letter in the crew window is the test.
- Open: ranking windows (0xfa2 / 0xfa4 entry layout), honor ranking, World Laptime, DCGP, Neo City messages.

## Session 42 (2026-11-13): PostgreSQL, request audit, trade, crew level / research / window

Details: EMULATOR_NOTES session 42. **Nothing was tried in game.** 232 tests pass. Nothing committed.
- **The database is PostgreSQL now** (`./launch.sh db` starts container dcemu_pg on 127.0.0.1:15432; databases skdbtw /
  skdb2016test, already migrated from SQL Server with all rows). SQL Server code is removed; the old container
  dcemu2011_db and its volume are untouched (the local `../Emulator 2011` copy still uses them).
- 2016: chase-end result offset fixed; password joins 0x1d8 / 0x1dd; player trade (both clients); Valentine
  chocolate event; crew level / research / boards / donations; 2016 crew creation (0xce4); crew rank refresh.
- Open: the crew Acceptance page (request unknown, no queue), crew grade byte, ranking windows (0xfa2 / 0xfa4 entry
  layout), honor ranking, World Laptime, DCGP, Neo City messages.

## Session 41 (2026-11-13): car limit 2000, Origin cars in 2016, Gotcha car slots — resume here

Details: EMULATOR_NOTES session 41. **Nothing was tried in game** (emulator, database and clients were stopped all
session). 183 tests pass. Nothing committed.
- Delegation to OpenCode DeepSeek: `../CLAUDE.md` + `../AGENTS.md`.
- 2016 client: car Unique Ids up to 1999 (`tools/carlimit2016.py`, section .p20 in DriftCity.exe) and 197 Origin
  player cars (`tools/portorigin.py`; the dealership sells them). **First test:** start the 2016 client; if it fails
  while loading, `python -m tools.portorigin reset` + `python -m tools.carlimit2016 remove`. Then: dealership list,
  buy one (e.g. Survivor, Id 635), garage picture, drive it, its aero sets in the shop.
- `[gotcha] car_slot_1..7` (2016 only) + `python -m tools.gotcha_slots apply`.
- 2016 messages: WhisperDeny 0xfb3, crew apply answer 0x36e, offline character info 0x29e -> 0x29f. Still open
  (layouts in EMULATOR_NOTES session 41): honor ranking, Neo repair, NeoChapter bonus, Valentine, PvP collision.
- The 2016 zip in ../Releases is older than these client changes.

## Session 40 (2026-10-29): timeline check

The client build timeline (https://timeline.slide.town/) lists every handler size change between our 2011 (0.29c,
2011-10-27) and 2016 (0.77a, 2016-02-16) clients. `tools/re2016/timeline_audit.py` checks it against the code and the
2016 logs: all sent messages agree; one fix (crew-battle stake entries 0x8c in 2016, `channels.Stake`), not yet
confirmed in game. The list of 2016 messages the emulator never builds (Mission Battle 0x3b7-0x3bd, DCGP, World
Laptime, crew research, Neo HUS, honor ranking, ...) is in EMULATOR_NOTES session 40: use it as the 2016 to-do list.

**Mission Battle on 2016 (same session, `game/missionarena.py`), not yet tried in game:** the item missions now pay on
2016 (the client ends them with 0x3b8, not 0x3e2: GlobalContent MissionBattleAdv), and the Mission Battle Arena
(battle zone section 13: mode / difficulty in the room window, 0x3bb / 0x3b6 / 0x3b7 / 0x3bc / 0x3bd) is implemented.
First test: 2016 client, Battle Zone > Mission Battle Arena > a room > Line Ball, Sec rank > Start. Unknowns and our
rules: EMULATOR_NOTES session 40 "Mission Battle for 2016".

## Current state: 2026-10-20 (session 39) — resume here

**One `emulator.ini` for both builds** (EMULATOR_NOTES session 39): `[client] version = 2016` in `Emulator/`, its
`[2016]` section gives 2016 its ports (111xx), database (SKDB2016TEST) and logs (logs/2016). `server_data_2016/emulator.ini`
and `tools/test2016.ini` are gone; scripted tests use 112xx now. **2011 is played from `../Emulator 2011/`**, a local
copy (not in git) with `version = 2011` (110xx, SKDBTW). Running at the end of the session: 2011 copy pid 10710,
2016 pid 10826 (both started with `./launch.sh server`; verify before stopping). Client zips: `Drift City Project/Releases/`.
The loose 2016 files (`DriftCity Dev Ed (loose)`) were deleted. Session 38's open list below still applies.

## Session closed: 2026-10-20 (session 38)

User requested handoff and end of session. **Current scope is the new 2016 client only.** Preserve all existing
tracked/untracked work; nothing committed. The entries below are historical snapshots; use this block for current state.

Completed this session: time-limited rental redemption and cleanup; rental countdown epoch correction; HOME
category enablement; drift-item auction enablement/UI and lifecycle race fixes; category 58 Turbo/Drift Booster
binding/equipping in native skill slot 20. Battle quick-slot flag is already on and was verified in client memory.
Inventory has a complete native Drift Auction tab and registration panel; no additional inventory UI patch needed.
See EMULATOR_NOTES sessions 35–37 for packet layouts, native addresses, files and limitations.

**Running server (then):** PID 255258 (session 38), command `.venv/bin/python -m dcemu -c server_data_2016/emulator.ini -q`
(that file is merged into emulator.ini since session 39) from Emulator/. Database SKDB2016TEST, server id 2016; ports 11105/11111/11121/11131/11141/11151, control 11199.
Log: logs/2016/20261020-153632.msgs.txt. Server left running. Verify PID identity before any later stop/restart.
Last full suite: **128 tests pass** (session 38). 136 tests. 2016 room layouts + race moves (XiCarMove 0x3a / XiCarState 0x32) and apprentice -> Driver Dome + licenses fixed, untested in game. Next (user): 2016 level-down items. Rental SQL redemption/expiry/replay also
validated with a temporary rolled-back fixture. Auction lifecycle tests use stub sessions, not live character logins.

**Next actions, in order:**

1. Fully restart the 2016 client to load local shop settings and UI. Last inspected client PID 73494 predates those
   asset changes. Reapply if needed from Emulator/: `.venv/bin/python -m tools.shop2016`.
   Backups: client_backup/shop2016; pack header bytes 20–31 and unrelated entries preserved.
2. Confirm one-day rental countdown, HOME page, public drift auction layout and inventory Drift Auction tab in game.
   Test registration/cancellation/purchase/collection with the unused Inventory Expansion item (10407 / i_d_ivn_01),
   eligible while unbound and state 0. Do not consume it just to test auction eligibility.
3. Confirm Turbo/Drift Booster purchase, equip/unequip, replacement and car binding in game. Replacement intentionally
   deletes the previous skill on that car, matching its table description. Earlier unbound purchases repair at login.
4. Clarify the Battle Zone slot report if still failing: boxes missing, grey, or refusing a specific item? The actual
   BattleQuickSlot switch was already 1; do not claim a new enablement fix. Use battle_quick inventory items such as
   Crash Capsule / Boost Recharger; regular EXP/item/Mito drinks are a different kind.
5. Resume remaining 2016 work: meter-rated rental kind 2 and explicit 0x6c early return; Part Option Extractor
   (0xfc1/0xfc2), NEO repair (0x4c4/0x4c5), combining above level 70 for Ultra, NeoCity R parts, Battle Zone OB Gacha,
   and earlier open items. No further implementation was authorized by this session-close request.

User screenshots confirm the rental car exists, but the new countdown/shop/auction/skill effects still need user
confirmation. No player rows manually edited. Keep 2011 client/config behavior separate. REA/Ghidra timed out;
reuse `/tmp/dc-rental/client.dis` and the session notes rather than repeating heavy imports. Runtime memory reads
were read-only, with ptrace enabled. No client process was stopped by the agent.

## Follow-up: 2026-10-20 (session 37: 2016 slots / inventory drift auction)

Battle quick-slot switch already enabled and verified in running 2016 client memory (net+0x29a bit 0).
Asked user whether boxes are missing/grey or refusing an item; answer pending. No additional toggle needed.
Inventory sixth tab 4980020 and registration pane 5150000 are complete. Session 36 AuctionVSItem enablement
reveals them after **full client restart**; PID 73494 still uses old local settings. Control 4980021 is an
intentional keyboard-cycle target to Parts, not a missing click overlay. Inventory Expansion 10407 / i_d_ivn_01
is eligible unused, unbound, state 0. No new implementation changes/restart; server remains PID 100911.
See session 37 native evidence. In-game confirmation pending.

## Latest handoff: 2026-10-20 (session 36: 2016 shop, auction, countdown, driving skills)

**2016 only.** Rental countdown now uses the 2012 UTC epoch (fixes 15340 days for a one-day rental); DB terms unchanged.
HOME enabled; drift auction enabled in 2016 config/local table, with native tab/headers restored by
`python -m tools.shop2016`. Backups: client_backup/shop2016. Full client restart required. Auction lifecycle sizes
verified; race guards and time-column sorts added. Driving skills (category 58 Turbo/Drift Booster) now bind,
equip/replace on current car using native slot 20. DRIVE_PASSIVE shop row enabled; login repairs old unbound purchases.
These new effects are **not yet confirmed in game**. 126 tests pass. Details: EMULATOR_NOTES session 36.

2016 emulator restarted: PID **100911** (verify identity before stopping), tools/test2016.ini, SKDB2016TEST, 111xx,
log logs/2016/20261020-102056.msgs.txt. All seven listeners verified. No 2011 assets/config changed for these fixes;
no manual player edits or commits. Preserve earlier dirty work. Meter-rated rentals and early return remain open.

## Latest handoff: 2026-10-20 (session 35: 2016 rental capsule use)

**Scope explicitly clarified by user: this session is the new 2016 client only.** Time-limited rental use now
implemented in game/rentals.py (0xfb4 -> 0xfb6 + 0xfb5), allocated base stats, chosen special assist and two
rental sets, persistent terms/metadata, atomic capsule redemption, expiry cleanup. Purchase confirmed by user;
**rental loaded in the live client after reconnect**, allocated base stats and rental-set bonuses verified in memory.
User visual/driving confirmation pending. Details/evidence/limitations in
EMULATOR_NOTES session 35. Meter-rated kind 2 and explicit 0x6c early return remain open. No client changes.

2016 test server now PID **93645** (verify before stopping), tools/test2016.ini, 111xx/SKDB2016TEST,
logs/2016/20261020-100336.msgs.txt. **102 tests pass**, plus real SQL redemption/expiry/replay check on a temporary
fixture within a rolled-back transaction. The new empty dbo.SKID_RENTCAR_TB table persists; no player edits.
No commits. Preserve all earlier dirty work. 2011 does not receive the rental protocol.

## Latest handoff: 2026-10-20 (session 34: 2016 items, Ultra, car assists, Gotcha 2015, pieces, rentals)

Details: EMULATOR_NOTES session 34 (top). **2011 stays the default (110xx, SKDBTW); the 2016 test instance runs with
`tools/test2016.ini` (111xx, SKDB2016TEST), last pid 81552 (verify before stopping).** The Dev Ed client is packed and
pack-only (session 33); it is started with `DriftCity Dev Ed/DriftCityLauncher2016` (the user's name). Nothing
committed this session or the last; 93 tests pass.

User-confirmed this session: 100 Capsule Points -> ST Vehicle Ticket (2008 rule: a full piece stack becomes its item,
items.complete_piece), login works again after the merge_stacks name clash. Not yet confirmed: the 2016 drift packs
(categories 23 / 56 / 59, Parts box counts), the inventory Mittron Enhancer Booster in 0x1ae, the Chance Fluid, the
Manufacturing Booster (which 0xe78 field: logged), Ultra rules (odds = Hyper x [items] ultra_odds, options, heat kits,
OU dockings, docking letters: guesses marked), car-own assists counted on the server (Exp / Mito +100 %, speedup:
**also changes 2011**), Gotcha 2016 (season 0, 2015 capsules, prices, prize count), RewardGroup Probability by header
(2016 gift boxes were all empty before), 0x19f stack merge, rental pack purchase (gives the capsule).

**Next (user's order: 2016 features)**: rental car step 2 (0xfb4 / 0xfb5 / 0xfb6: trace the client when the capsule is
used), then round 2: Part Option Extractor (0xfc1 -> 0xfc2), NEO parts repair (0x4c4 -> 0x4c5), Drive skill boosters
(category 58, Skill Item Slot), combining above level 70 for Ultra, NeoCity R parts, Battle Zone OB Gacha (0x834 ..
0x83a), Capsule Points shop?, Etc.ShowGotchaOldStyle. Open from session 33: packed loading is slower (Quest 1 -> 11 s).

## Previous handoff: 2026-10-20 (session 33: client tables tool, 2016 tutorial window)

The client's tables stay out of git (user, 2026-10-20). `python -m tools.client_setup [-c config]` adds the missing
ones on first start (launch.sh / launch.bat / the container ask for the client folder); details EMULATOR_NOTES
session 33. 2016 guided tutorial: the Dev Ed table and test exe must agree (`tools.tutorial_flow --only 2016`).
Not yet confirmed in game. No commits.
Dev Ed is now packed and pack-only (tools/pack_client.py; loose copies in `../DriftCity Dev Ed (loose)`); the user played
on it. Licenses fixed for the apprentice tutorial (licenses.start). Open: packed loading is slower (session 33).

## Previous handoff: 2026-10-19 (session 32: guided apprentice race works)

**User confirms: “Works correctly now” after the tutorial race fix.** Expected route supplied by user:
drive from Driver Dome to Battle Zone -> guided race with prompts -> normal race -> old field tutorial.
Keep that two-stage race sequence; do not skip directly to apprentice stage3.

Final fix: `dcemu/native/game/rooms.py::practice` no longer sends ordinary practice PvpLoad0x1e7/type100
for Main.Apprentice + the marked training car + map11/flag0. Native client start already initializes a
local race with time=-1; the practice answer overwrote it and bypassed lesson initialization. Ordinary
practice behavior is unchanged. Regression checks cover both client versions. **73 tests pass.**

The prior button bypass is also applied: `python -m tools.tutorial_flow` sets guided GlobalContent mode1
and changes one comparison byte in Client US/EU exes and DriftCity2016Test.exe. It enters the existing
native tutorial start branch upon reaching Battle Zone, skipping only the inaccessible Tutorial button.
`tools.client2016` preserves/rebuilds this patch. Original Dev Ed exe untouched; backups under
`client_backup/tutorial_flow/`. `--mode 4` restores the direct flow/comparison. Restart the client fully
when changing its table. Bypass alone had started a race without prompts; the server correction fixed that.

Both servers restarted and listeners verified after source change:
- 2011 default: PID83577, emulator.ini,110xx, SKDBTW; log `logs/20261019-230542.msgs.txt`.
- Optional2016: PID83578, server_data_2016/emulator.ini,111xx, SKDB2016TEST;
  log `logs/2016/20261019-230542.msgs.txt`.
Verify process identity before stopping anything. No character rows manually changed, no commits.

**Next session:** preserve all existing dirty/untracked work. Finish2011, then full2016; Origin stays parked.
Confirm the full starter selection/0x5d2 completion -> old field intro if not covered by the user's test.
Investigate an additional observed issue: Driver Dome position saving calls licenses.pay_monthly even for
training cars; old log22:56:26 shows a Rookie reward during training despite login's tutorial guard.
Do not reset the user's character to hide it. Then continue2016 movement0x21d (112/118 vs old100),
periodic0xf4d/0xe8d and remaining gameplay layouts. Level/EXP cap100 is already user-confirmed fixed.
Pedestrian flag is on in2016 test config; visible pedestrians remain unconfirmed.
See notes session32 for native addresses and debugging pointers.

## Latest handoff: 2026-10-19 (session 31: guided tutorial correction)

User found instant Battle Zone teleport and no tutorial tips. Cause: client table ApprenticeFlowType4
(US2011/2016),3(EU2011) selects direct entry. Local clients now use **mode1** in their US/EU language columns.
Reproduce: `python -m tools.tutorial_flow`; `--mode 4` selects direct entry. Backups under client_backup/tutorial_flow.
Pack entries/header20..31 validated unchanged except tutorial row. **Restart client fully**; visual result pending.
No server restart required. If tips still fail, inspect rooms.practice type100 vs client-local tutorial setup.

**Priority set by user: finish2011 support, then full2016 support. Origin is for much later.**
Origin feasibility is parked in `docs/ORIGIN_CLIENT_RESEARCH.md`; research only, no third profile.
2011/2016 remain as before; Origin original files untouched. Preserve existing workspace changes.

## Latest handoff: 2026-10-19 (session 30: apprentice tutorial implementation)

Shared new-character tutorial enabled with Main.Apprentice=1; legacy creation selectable through
`[flags] Main.Apprentice = 0`. New characters get the temporary Birdie RTI in Driver Dome; client runs
its tutorial race; 0x5d2 completion swaps it atomically for the chosen starter and saves the old field intro
state. Both 2011/2016 reply layouts implemented. **70 tests pass**, real isolated SQL lifecycle/replay
check passed. **Full sequence not yet confirmed in game**; use a freshly created character for the next test.
2011 remains default on110xx/SKDBTW (PID72786); optional2016 on111xx/SKDB2016TEST (PID73850).
Both restarted after code changes. Verify PIDs. Details/addresses/layouts in notes session30.

Pedestrians: user requested enabling the flag. Main.PasserBy=1 is now set in the local 2016 test config;
ShowPassenger=true locally. Verified the outgoing flag bit and restarted the 2016 server (PID73850).
Visible pedestrians still await in-game confirmation.
No exe patches this session, no commits. Preserve earlier workspace modifications.

## Latest handoff: 2026-10-19 (session 29: real 2016 login works)

**2011 remains default and runs on 110xx / SKDBTW.** A separate 2016 instance runs on 111xx /
SKDB2016TEST with server_data_2016/emulator.ini (tracked; tools/test2016.ini was merged into it on 2026-10-20).
Latest PIDs: 2011 68820, 2016 68796 (verify, do not assume). All 65 tests pass.

2016 client launched and logged in successfully, created a character, entered the world and played Director
Green's introduction. User confirms the old tutorial works too. **2016 level/EXP fixed and user-confirmed**:
Etc.LevelLimit now follows `[client] max_level_2016 = 100`; 15 reward encoders widen EXP counters only for 2016.
Main.MainButtonAdvanced=2 exposes the native classic/ADV HUD selector in both versions; user confirmation pending.

Launch/rebuild the test client: `python -m tools.client2016 launch` / `patch` from Emulator.
Separate DriftCity2016Test.exe; original exe unchanged and backed up. Test sockets verified on 111xx.
Fresh DB snapshot **db/SKDB2016TEST_clean.bak**, only admin/admin and no characters. Active test DB now has the
user's character. Never restore this backup over live SKDBTW. More details and exact patch offsets: notes session 29.

Open: 2016 movement sizes/field offsets, periodic 0xf4d and login 0xe8d, other changed gameplay records.
No commits/pushes. Preserve existing workspace changes.

## Latest handoff: 2026-10-19 (session 28, optional 2016 foundation)

2011 US/EU remains the default: `[client] version = 2011`. Version 2016 is opt-in and experimental.
Restarted and verified listening on 110xx after the changes (PID 63643; DB healthy).
See the newest EMULATOR_NOTES session for exact layouts, tests, uncertainties and next steps.

Implemented: version switch, shared char/car/item/stats/bonus encoders, selected content-flag table,
0x425 new byte, loose-file table/traffic extraction, and isolated `tools.prepare2016` data preparation.
Local `server_data_2016/` is ready (gitignored). `python -m tools.prepare2016` reconstructs it on another machine;
it refuses to overwrite an existing directory. 59 tests pass; both table configurations load; 2016 listener
smoke checks on 111xx pass. Not yet confirmed in game. Changes have not been committed.

**Next priority: the new 2016 tutorial (user correction), then changed area/room/crew/EXP packets.**
Do not assume legacy tutorial files in Dev Ed describe its new entry sequence. A question about what the newer
introduction starts with is pending; use the reply. The current port has shared records, not complete gameplay.
Do not modify 2011 tutorial behavior while implementing the 2016 path.

## Latest handoff: 2026-10-19 (session 27, end of day)

Details: "Session 27" at the top of [EMULATOR_NOTES.md](EMULATOR_NOTES.md). **Everything below is committed and pushed**
except the client files (never in git: see the archives below).

**Running state:** emulator restarted after the last code change (pid 33531; `./launch.sh status`), DB healthy.
**This machine had stale `server_data/Init/`** (the 2011 vanilla tables of 10-15 while the client had the port2016 ones):
re-synced from Client US, and `server_data/Init/` + `server_data/tables/UseItemClient.tdf` are now in git (user).

**Client changes this session** (tools in git, so they can be made again; files in the user's archives
`../openDC_client_changes_2026-10-19.zip` and the full clean clients `../openDC_Client_US_2026-10-19.zip` /
`../openDC_Client_EU_2026-10-19.zip`, outside the repo; logs, dumps and the decomp `version.dll` left out):
- Both clients: the 34 icons of the 20 ported 2016 tires (`port2016.py tires` / `eu tires`; game.nui 2650000 + uitex).
- US: Championship_Tooltip2 "Speed Limit: %d mph" (`global_text.py`, Patch.006).
- `client_backup/game.nui.before_tires` = the US game.nui before the tire icons (no vanilla game.nui.orig on this machine).

**Done, not yet confirmed in game:**
- MPH converts (Speed Up / speedup assists): the client takes them only as AddSpeed (float @0x10 of the 0x2f8 enchant
  bonus); now sent (assists.own_bonus). Works the same on the EU client (km/h: Speed Up 6 = +6 km/h).
- Over Turbo counts as boost points in the server's totals (as the client's own stat sum).
- Buying a ported 2016 wheel crashed the client: icons added (cause a guess: test Allied, a vanilla tire without item
  rows, to confirm).
- **GT Championship** (the client's tournament, new `game/championship.py`, emulator.ini `[championship]`): classes =
  battle zone sections 7-10, preliminaries (time attack) -> quarter-finals 1 / 2 -> semi-finals -> finals, all the
  client's windows answered (0xd48-0xd57), stage times from content flags. Test: `gmtour test on`, `gmtour start 1`,
  `gmtour next` / `status` / `end`. Script-tested only.
- Touring class speed texts in mph for US clients (km/h for EU).

**Open (next session):**
1. **The 2016 client port (user asked: "make a switch for the 2016 client in the emulator config and start
   implementing")**: research done, no emulator code yet. Plan and findings in §"2016 client port" below; start there.
2. Try the GT Championship in game (user), the tire purchase, the MPH convert.
3. Older items from session 26 below (ghost-battle items on Xerander, 0x214, crew ranking, TEAMPOINT test setup).

### 2016 client port (DriftCity Dev Ed): what is known, what to do

The 2016 exe (2016-02-16, `DriftCity Dev Ed/DriftCity.exe`) is a community build already patched to connect to
127.0.0.1 on our ports; same network code, handshake and login messages as 2011. Tools: `tools/re2016/` (README).
Measured layouts (2011 -> 2016):
- XiStrCharInfo 0x11b -> 0x141: name field 0x2a -> 0x40 (or 0x16 new bytes after the name: send the name as wstr 0x40,
  identical either way); avatar 0x36 -> 0x4c, level 0x38 -> 0x4e; exp / exp next / exp base become u64 (12 -> 24
  bytes); everything from Mito on +0x22 (Mito 0x46 -> 0x68 ... cur car 0xc1 -> 0xe3, flags 0xed -> 0x10f, guild
  0xf1 -> 0x113); 0x7c LoadCharAck: car count @0x14b, cars 0x32 each, total (n-1)*0x32 + 0x181.
- XiStrCarInfo 0x31 -> 0x32 (one byte more at the end; fields up to 0x2c unchanged).
- XiStrMyItem 0x5c -> 0x60: same up to @0x48 (expiry), then 2011's @0x4c and a new u32 (@0x4c / @0x50, order not
  known), TableIdx @0x54, InvenIdx @0x58 (2011 @0x50 / @0x54), 2011's last u32 @0x5c. 0x191 entries 0x60, 0x192
  entries 0x64 (record + u32 state).
- XiStrStatInfo 0x68 -> 0x70 (two longs more at the end; totals still @0x40); XiStrEnChantBonus 0x28 -> 0x2c
  (AddSpeed still @0x10, a new u32 after it); 0x2f8 = stats @2 + bonus @0x72 (0x9e).
- Content flags: 0x1e is 8 bytes longer (0x62 -> 0x6a); 176 of 196 flags keep their bits, 20 moved (mostly
  BattleZone.*: PreMatchTime 10 -> 11, GhostBattle 2 -> 3 ...), 8 new (DCGP, AttackPlayer, ...):
  `dcemu/data/flags_2016_raw.tsv` (raw, to be turned into the flags_2011.tsv format).
- Message size changes: S>C 61 of 428 shared types, C>S 34 of 407 (EMULATOR_NOTES session 27 lists the main ones:
  rooms +8, area moves +10 / +12, crew info +0x118, char info window, exp info +12, ...).
Steps:
1. `emulator.ini [client] version = 2011 | 2016` (context.client_version) and a `dcemu/native/version.py` (like
   nation.py); records.py encoders per version (char, car, item, stats, bonus, flags table, VisualItem +2 in 0x425).
2. `server_data_2016/` from the Dev Ed client (sync_data; check client_tables.Client reads its loose files + packs).
3. Run the 2016 client against the test emulator (ports 111xx) when the user is not playing: login -> lobby ->
   character -> city; fix by layout (C>S offsets: rooms, area moves).
4. Then the other changed messages, then 2016-only features.

## Previous handoff: 2026-10-19 (session 26, end of day)

Details: "Session 26" at the top of [EMULATOR_NOTES.md](EMULATOR_NOTES.md). **Everything below is committed and pushed.**

**Running state:** emulator restarted at the end (pid 287721 then; check `./launch.sh status`), DB healthy. Both client
exes are as at the start of the session (a sticker size experiment was reverted, see below).

**Done and user-confirmed:** selling cars (0x57 -> 0x58), bought cars at their dealership class grade (Shark V7);
channel battles with two crews: no defence -> the attacker takes the channel without a race, crew room seats by role
(even = owner window, odd = challenger window: the client picks the window by seat), 0x386 channel / area order,
attack name for queued challengers and the defence, Team Comparison (0xe24 -> 0xe25, match log SKID_CBATTLELOG_TB),
replay list (0x395's u32 is a list version) and replay headers (0x1bf in the recording), ownership lost when the
defence room empties, no extra 15 s after a round's result, "Win the channel!" once.

**Done, not yet confirmed in game:**
- The defence's round-start VS splash: 0x386 now goes out before the round's 0x390 / 0x1e7.
- Replays stream 4 pieces per 0x227 (~128 KB/s; 16 KB a request lagged an 8 MB round after a minute).
- Ghost Battle in replays: content flags BattleZone.GhostBattle + GhostBattleOnOff (the replay's ghost button); during a
  ghost battle traffic hits / combos give nothing (state['ghost'] from 0x213 to 0x216 / 0x1e0).
- Windows / Docker: DCEMU_PUBLIC_HOST (default 127.0.0.1 in docker-compose.yml) is sent as the lobby / game address
  instead of the container's own address (a Windows user's client never reached the lobby). Ask them to run
  launch.bat again.

**Reverted at the user's request:** 512 px stickers (client editor size, upload check, preview, sticker atlas). The
uploads worked, but stickers stayed low-resolution on the car (cause not found: probably a fixed-size car texture);
all client bytes, tools and server limits are back as before, the test sticker deleted from the database.

**Open (next session):**
1. Xerander holds 37 items from the ghost-battle drop bug (log 20261019-152042, 15:21:36 on): the user did not say
   whether to remove them (edit only while offline).
2. C>S 0x214 (36 bytes, sender 0x7eb7ac; 0x215 handler 0x52b260 -> 0x7a6960) during replays: not known, unanswered.
3. Crew ranking (SKID_TEAM_TB.TEAMRANKING) is never computed: Team Comparison shows "Rank 0".
4. Test setup left in the database: TEAMPOINT 500000 for RecompsRule and NewbieCrew (rank S); set to 0 to undo.
5. Older items: see the previous handoffs below (gift boxes, small ST cars, Windows launch, 2016 quests).

## Previous handoff: 2026-10-19 (sessions 25-25b, end of day)

Details: "Session 25" and "Session 25b" at the top of [EMULATOR_NOTES.md](EMULATOR_NOTES.md). **Everything up to the
editor / gift box / port work was committed and pushed (f450cc4 on main).** This handoff note itself is not committed.

**Running state:** emulator restarted mid-session (pid 140719 then; check `./launch.sh status`), DB healthy. Client
files changed this session need a client restart (the user's clients may still run the old copies).
`git config core.fileMode false` is set in this working copy (files are mode 755 after a copy; ~240 fake changes).

**Done, none confirmed in game yet:**
- Race traffic on every track with client paths: `tools/race_paths.py` (chunked .chpath reader) wrote 18 missing
  server_data/race/*.index + trafficCarSettingForTrack_5.txt (Taipei). 101 tracks; taipei_track2 has no paths.
- Bought cars start at their first real VehicleUpgrade grade (cars.start_grade): 2011 class cars (Utopia V9, Rotary
  V5 ...) were sold as empty V1 rows; 2016 cars V1 (as the 2016 client). The dealership's V tab = VehicleList column 23.
- Small ST cars' hit box (user-confirmed cause): 2016 "GOTCHA_SMALL" rows labelled "SMALL" (47 cars; size is a % of
  the base car, the 2011 client only scales for "SMALL"): `port2016.py [us|eu] small`, both clients + server_data.
- Every track in every battle zone section, US exe (`eu_client.py "Client US" tracks on|off`; `eu_client.py us`
  applies it). EU already lists all tracks (nation 7-10 rule in 0x5bc2d0).
- EU Performance Graph Total = US stat sum (`eu_client.py chart us|eu`, GlobalContent CarChartAdv 0; part of setup).
- Hidden Semi-channel tooltips transparent (semi_tooltips.py, both clients).
- Gift boxes (tools/giftbox.py + editor Items/Cars > New gift box): car / item / drift / Mito / EXP lines, each with
  its own chance (sub-groups with an n/a row). Writes server_data and both clients at the same row. Tested on copies
  only; no real box made yet.
- gmcar reports the grade given; editor translation 셋 = Set; tests/test_editor.py GiftBoxes (16 + 1 tests pass).
- Windows launch.ps1: `$Rest` null without arguments ("Cannot index into a null array", the client never started);
  fixed + trap exit 1. **Untested (no PowerShell here): ask the Windows user to retry.**
- GM reference: new Claude Doc "openDC GM Commands" on this account
  (https://claude.ai/code/artifact/d53089bd-4fd4-479e-80cd-a8eb956c26c3); exported as "openDC GM Commands.pdf"
  (repo root, in git). The old doc is on the user's other account.
- Clean client zips for sharing (no decomp version.dll, logs, dumps, pc_spec, save): `../openDC Client US
  2026-10-19.zip`, `../openDC Client EU 2026-10-19.zip` (outside the repo).

**Not a bug / left as is:** "[A] Collision damage ..." race text is the client's debug print for GM accounts (PType < 'N';
user: no patch). The 2016 V9 tab + V1 car matches the 2016 client.

**Open (next session):**
1. Confirm in game: small ST cars hit objects, all tracks in Newbie / 4X rooms, race traffic on the new tracks, bought
   2011 class cars (Utopia V9 at its price), EU graph totals, gift boxes (make one, `gmitem giftbox_<id>`).
2. Windows user: retry launch.bat with the new launch.ps1 (and the server setup there, never tried yet).
3. Older open items: channel battles untested (session 22 list in §5), 2016-only quests not ported, EU client with the
   new cars / tracks in game.
4. "Drift City Item Catalog.zip" (editor icons) is untracked on purpose; the user decides whether it goes to git.

## Previous handoff: 2026-10-19 (sessions 24-24d)

Details: "Session 24" .. "Session 24d" at the top of [EMULATOR_NOTES.md](EMULATOR_NOTES.md). No commit or push was asked
for; the working tree still holds the uncommitted session 23 editor work too (new untracked files: tools/editor/,
tools/semi_tooltips.py, tools/port2016.py, tools/p16_cars.s).

**Done (client files changed with the user's approval; originals in client_backup/):**
- Semi-channel tooltips (`tools/semi_tooltips.py`): the vanilla pack had kill-counter digits under the tooltip names;
  now the 2016 bubble with the server's own rules. US and EU.
- **2016 content ported** (`tools/port2016.py [us|eu] tracks|cars|exe|reset`, docstring = everything):
  9 battle zone tracks (ids 93-102) and 218 player cars (Unique Ids 94-442; 300-303 renumbered 102-105), in both
  clients. Car pictures the 2016 Dev Ed files lack come from `~/Drift City World/.../uitex.agt` (WORLD_UITEX).
  **User-confirmed:** the new cars work in the US client. Not yet confirmed: the EU client in game, the track
  picture fix (dialog 1060000 order), driving every new track.
- **Client code patch** (both exes, section `.p16`, code in `tools/p16_cars.s`): VisualItem records hold car Unique
  Ids up to 511 (was 299). `tools/eu_client.py us` / `setup` re-apply it when the tables hold the 2016 cars. Any
  crash in the shop / garage / car code: suspect this first (`port2016.py exe` checks the original bytes).
- Fixes found on the way: names over 31 bytes overflow the VehicleDisplay reader's stack buffer (port clips them);
  the first fitting aero row is a car's body (new rows go before the generic pc_Aero* rows); battle zone track
  pictures must stay before dialog 1060000's other controls.
- GM: `gmcar [name] car name [V1-V9]` (gmctl `car`), `gmcbattle start [minutes]` / `gmcbstart` (gmctl
  `cbattle start`). Script-tested only.
- Not a bug: Cras / Oros tracks are only offered in 6X / 8X+ Pro rooms (client 0x5bc2d0; Taipei always).

**Debugging method that worked this session** (for crashes at start): run the client under Proton without the
launcher (token = md5 of the 5-minute CLOCK_MONOTONIC window; EU: "eu_%d_plz_do_not_hack") and attach gdb with a
breakpoint on the stack cookie failure jump 0x895c6c; `x/24wx $sp` gives the failing function's return address.
Screenshots of the live client: `spectacle -b -n -f -o FILE`; xdotool can click into the XWayland window.

**Open:**
1. EU channel list report from session 24 (needs an EU screenshot); test the EU client with the new cars / tracks.
2. Confirm the track picture fix in game; gmcar / gmcbattle start in game.
3. Optional (user to decide): all cities in every Pro room (client patch of 0x5bc2d0); race traffic on the new
   tracks (no .index files); the 2016-only quests (neo_q, Christmas rq) not ported; GM Commands doc lacks the new
   commands.
4. Running state: emulator restarted at the end of the session (all server tables current).

## Previous handoff: 2026-10-19 (sessions 23–23b)

The latest work is the **desktop Server Workshop editor**, requested by the user for items, cars,
mode parameters/rewards, GM console access and account management. The follow-up request was to translate
Korean table text into English in the editor. See the session 23b / 23 entries in
[EMULATOR_NOTES.md](EMULATOR_NOTES.md) and the desktop editor section of [../README.md](../README.md).
No commits or pushes were requested or made for this work. The working tree already had extensive
pre-existing changes; preserve them. The new editor files are still untracked and must be included
explicitly when the user eventually asks to publish.

**Last verified server state:** after the user started the server on 2026-10-19, `launch.sh status`
reported emulator PID 17118 and a healthy database container. `tools.gmctl who` returned `OK 0 online`;
an account search for a deliberately nonexistent ID returned `OK []`, confirming the new account command
and live SQL connection. These were read-only checks. Do not treat the earlier session-23 startup failure
as the current blocker, and do not assume the recorded PID remains current: check the launcher status.
Live account mutations, editor-driven reward changes and in-game behavior have not been verified.

**Start the editor:** from `Emulator/`, run `./editor.sh` (or `.venv/bin/python -m tools.editor`).
The emulator/database need to run for GM and account panels; table browsing/editing works independently.
Python Tk and Pillow are required. Pillow 13.0.0 is installed in this machine's emulator `.venv`;
reinstall elsewhere with `.venv/bin/python -m pip install -r tools/editor/requirements.txt`.
On Windows use `editor.bat`; its Docker Compose GM transport is implemented but untested on Windows.
Reopen the editor to load editor-only code/translation changes; those do not require a server restart.
Changes to cached server tables or `mode_tuning.txt` require an emulator restart and disconnect players.

**Implementation map:**

| File | Responsibility |
|---|---|
| `tools/editor/__main__.py` | Tk interface: Items, Cars, Modes & rewards, GM Console, Accounts; asynchronous server calls |
| `tools/editor/data.py` | XLT/TDF/text/INI documents, validation, exact backups, atomic saves, conflict detection, game artwork, local GM transport |
| `tools/editor/translations.py` | Offline English display translations; original text option; English/Korean search support |
| `editor.sh`, `editor.bat`, `tools/editor/requirements.txt` | Desktop launchers and Pillow dependency |
| `dcemu/native/editor_admin.py` | Account search/detail/create/password/role commands, through the loopback GM port |
| `dcemu/native/admin.py` | GM dispatch additions and credential log redaction |
| `dcemu/native/mode_tuning.py`, `server_data/mode_tuning.txt` | 107 allowlisted gameplay values, validated and applied once at startup by `dcemu/__main__.py` |
| `tests/test_editor.py` | 16 editor data, translation and account tests |

**Capabilities and boundaries:**

- Items cover `ItemClient.tdf`, `UseItemClient.tdf`, `VisualItem.xlt`, `VShopItem.xlt`; cars cover model and
  V-grade tables. Original artwork comes from `Client US/Data_US/gameui/game.nui` and `uitex.agt`.
  The optional root-level `Drift City Item Catalog.zip` supplies additional descriptions/icon atlases;
  keep it when moving the workspace. The editor does not rewrite any client archive.
- Modes & rewards exposes the available game tables, gameplay INI settings, schedules, drops and reward
  files. The added tuning file exposes Undercity fees/stage payouts/timers, Rush winner prizes,
  Virtual HUV item prizes, chase time tables and the daily token. Defaults preserve existing behavior.
  Unimplemented modes and other handler rules are not automatically configurable. Unknown columns are
  explicitly labeled as raw parameters.
- All Korean values in the four item tables and Korean column headings in the loaded tables have English
  display translations. Assist effects, upgrade requirements and recurring reward terminology are also
  translated. Some historical prose/proper names elsewhere remain original when no translation exists.
  `Original table text` shows source values. Display translations must **never** become implicit writes:
  `Document.set_display` skips unchanged display text, while deliberate user field edits change data.
- Saves keep exact originals in ignored `editor_backups/<timestamp>/`, reject stale edits and preserve
  row indices, linked IDs, encodings (including CP949 Lap Time), BOMs and untouched cells. Delivery/patrol
  item reward files allow duplicate rows for extra prizes. Restore by copying the appropriate backup
  over the original while its editor is closed. `sync_data` can overwrite edited client-derived tables.
  Client-visible prices/names/requirements may also need a deliberate client pack update with existing tools.
- GM additions include online level/EXP/Mito, channel battle controls, party/VHUV/Undercity/CB test modes,
  Rush and forced gate rewards. GM/account mutations execute through the emulator, rather than arbitrary
  SQL from the editor. Credential commands redact passwords from logs; list/detail payloads are omitted
  from general server logs. Keep the unauthenticated GM control port loopback-only.
- Account password resets and role changes require full logout from both game and lobby. Passwords keep
  the existing game-compatible MD5 format. GM roles update `SKID_CHARACTER_TB.PTYPE` on existing characters;
  future characters retain their default. `adminlist.txt` independently grants GM access, and revocation
  reports that override instead of claiming success.

**Podman Compose restored on this Steam Deck:** Podman 6.0.2 was already installed; the Compose provider
was missing. SteamOS 3.9.3 has its system partition read-only, and sudo required a password. Installed
`podman-compose` 1.6.0 in a dedicated user venv at `/home/deck/.local/share/podman-compose`, with the command
symlink `/home/deck/.local/bin/podman-compose`. Both `podman-compose --version` and `podman compose version`
were verified outside the sandbox. The user installation lives outside the read-only system image;
verify it after future OS/Python upgrades and recreate the venv if the interpreter changes. This is
machine setup, not part of the repository or an installation on a new machine.

**Validation and next steps:**

```sh
cd Emulator
.venv/bin/python -m unittest tests.test_editor -q
.venv/bin/python -m tools.editor --smoke-test
```

All 16 editor tests passed after translation changes. The desktop smoke test passed on the Deck display:
item/car/mode forms, original artwork, English/original view switching and no implicit edits; no table
writes. The full suite was run before the four translation tests were added: 39/41 passed, with the two
previously documented `test_position.py` failures (stale tutorial state expectation; DB stub missing
`rows`). Do not report a new full-suite total without rerunning it. Windows and in-game editor changes
remain unconfirmed. Next, let the user try the editor, then test deliberate edits on scratch copies/test
accounts before changing their main character or live economy. Do not create accounts or alter balances
just to prove the connection; live read-only GM/database connectivity already passed.
The gameplay open list in section 5 below still applies, especially channel battle/replay testing.

## 1. What to copy

The GitHub repository (https://github.com/Xerender13/openDC) holds `Emulator/` and `Launcher/` only. Copy the rest
from the old device:

| What | Where it is on the Deck | Notes |
|---|---|---|
| The code | GitHub, or `Drift City US 2011/Emulator` + `Launcher` | `git clone https://github.com/Xerender13/openDC` |
| The 2011 clients | `Drift City US 2011/Client US/` and `Client EU/` | Not on GitHub (shared on Google Drive). **Copy the Deck's folders**: `Client US/` has the text patches in `Patch/Patch.006` (12215 license name, 12216 coupon, 11413 / 12214 crew logon), `DriftCityUS.exe` and `DriftCityLauncher.ini`; `Client EU/` is the EU client (`DriftCityEU.exe` set by `Emulator/tools/eu_client.py`, `Data_EU_eng/`, the Km/h dial). Put them next to `Emulator/`. |
| The game database | `Emulator/db/<name>_<date>.dump` (`pg_dump -Fc`) | All accounts and characters as of the handover. Make a newer one before moving: `./launch.sh backup-db`; load it with `./launch.sh restore-db F`. Not in git (`db/*.dump` is ignored; `db/postgres/` holds the clean seeds). An old SQL Server `.bak` is migrated once with `tools/pgport/migrate.py` (see `README.md`). |
| `emulator.ini` | `Emulator/emulator.ini` | Is in git. Change `[database]` if your PostgreSQL differs; the ports and `[flags]` are set for this client. |
| `.ticket_secret` | `Emulator/.ticket_secret` | Not needed: the server's key for login tickets, made again when missing (a client that is logged in at that moment logs in again). Not in git. |
| `client_backup/` | `Emulator/client_backup/` | The client's original packs before the text patches. Not in git; keep a copy. |
| Old stacks / research | `Server2008/`, `Handoff/`, `DriftCity Dev Ed/` | Not needed to run anything. `Server2008/client_image/DriftCity_2011_unpacked.bin` (the unpacked client, for disassembly) and `Server2008/server/ZoneServer.exe` (the 2008 server, the reference for server rules) are worth keeping for research. |

## 2. Setting up

Layout (folder names matter: launch.sh / launch.bat look for `../Client US` and `../Client EU`):

```
<anything>/Emulator/   <anything>/Launcher/   <anything>/Client US/   <anything>/Client EU/
```

**Linux** (Python 3.10+, podman + podman-compose, or docker + compose):

```sh
cd Emulator
./launch.sh setup                               # .venv with pg8000, copies the client's tables to server_data/
./launch.sh restore-db db/<name>_<date>.dump    # your characters (or: ./launch.sh init-db for an empty database)
./launch.sh                                     # database + emulator + client
```

**Windows** (Docker Desktop running; the emulator runs in a container):

```bat
cd Emulator
launch.bat setup
launch.bat restore-db db\<name>_<date>.dump
launch.bat
```

In the container the emulator tells clients DCEMU_PUBLIC_HOST (default 127.0.0.1: a client on the same machine) as
the lobby / game address; for players on the network set it to the machine's address (environment or `.env`).
`launch.bat` / `launch.ps1` passed PowerShell's parser but have **not been run on real Windows yet**; expect to fix
small things the first time. `./launch.sh restore-db` was rewritten for PostgreSQL in session 42 (pg_restore from a
`pg_dump -Fc` file, asks first); its SQL Server version was tested on a scratch database, the PostgreSQL one has not
been run against the live database.

The client: `Client US/DriftCityLauncher` (Linux, runs DriftCityUS.exe with Proton: `DriftCityLauncher.ini [client] exe`,
`[linux]`; the EU client the same from `Client EU/`) or
`Client US/DriftCityLauncher.exe` (Windows; run it once as administrator for windowed mode). Its server address is
`DriftCityLauncher.ini [server] address` (127.0.0.1 for the same machine). Other players: their launcher ini gets
your address, and `Emulator/server_data/serverlist.txt` too; open TCP 11005-11051.

Accounts are made on the first login with a new ID. GM rights: the account in `server_data/adminlist.txt` or
SKID_CHARACTER_TB.PTYPE 'A'; GM commands with
`./launch.sh` running: `.venv/bin/python -m tools.gmctl who | kick NAME | block NAME days | ban ACCOUNT ...`.

## 3. How the work is done (rules the user set)

- **Fix protocol problems in the emulator**, not by editing the database, and **keep the client vanilla** unless the
  user asks (the text patches above were asked for). Client pack changes: rewrite the pack keeping header bytes 20-31,
  originals in `client_backup/`; when something breaks after a client change, suspect the change first.
- **Restart the emulator after every change** without asking (`./launch.sh restart-emu`) and say so: the user plays
  while the work goes on, and a restart disconnects them (they log in again).
- Edit a character's database rows **only while that character is offline**.
- Stop only processes you started, by their pid (the emulator's is in `Emulator/.emulator.pid`); no pkill patterns.
- Tell the user what was tested and what was not ("not yet confirmed in game" in the notes until they confirm).
- Research method: the client is `Server2008/client_image/DriftCity_2011_unpacked.bin` (image base 0x400000; file
  offset = VA - 0x400000). Disassemble with capstone (`pip install capstone`); a full sweep of the client gives the
  addresses quoted in the notes (e.g. handler tables: `push handler; push type; call 0x806590`). The 2008
  `ZoneServer.exe` (not packed) shows the original server rules. The emulator logs every message:
  `Emulator/logs/<date>-<time>.msgs.txt` (one file per emulator start) and `logs/emulator.out`.
- Notes: add each change at the top of `docs/EMULATOR_NOTES.md` (what the user reported, the cause with client
  addresses, the fix, confirmed or not).

## 4. Publishing to GitHub

Since 2026-10-17 (session 14) the project folder (the one with `Emulator/` and `Launcher/`) **is the git working
copy** of github.com/Xerender13/openDC (branch `main`). Commit and push only when the user asks ("commit to github").

```sh
cd "<project>"
git fetch origin && git log --oneline HEAD..origin/main   # the user sometimes edits README.md on GitHub
git status --short                                        # only Emulator/ and Launcher/ files belong here
git diff | grep -n -i -E '^\+.*(passw|secret|ticket|@gmail)'   # nothing sensitive in the changes
git add -A Emulator Launcher
git -c user.name=Xerender13 -c user.email=sasuke8453@gmail.com commit    # end with the Co-Authored-By line
git rebase origin/main   # if GitHub had newer commits
git push origin main
```

The local EMULATOR_NOTES.md is the redacted version (the second test account's password is not in it). Never add
`Client US/`, `Client EU/`, `Server2008/`, `Handoff/`, `.ticket_secret`, `logs/`, `client_backup/`, client-derived
`server_data/` files (except `server_data/Init/` and `server_data/tables/UseItemClient.tdf`: kept in git since
2026-10-19 at the user's request, they hold the tables `tools/port2016.py` wrote), or database backups other than
`db/SKDBTW_clean.bak` (`.gitignore` covers these). `server_data_2016/` (the experimental 2016 tables) is in git since
2026-10-19 under the same rules as `server_data/`: its client-copied `tables/`, `teammark/`, `NeoData/` (the Neo City tables) and pid files stay out
(the user confirmed on 2026-10-20: never push client files; `tools/client_setup.py` copies them on first start). The tools
that change client files are in git, so those changes can be made again on another machine (see §5).

## 5. State at the handover

Gameplay status below last updated 2026-10-18 ~23:00 (sessions 21–22b). For the 2026-10-19 editor,
translations, Compose installation and last verified server status, read the latest handoff above.
The older gameplay work was committed before this editor session. Details: the "Session 22b", "Session 22", "Session 21" entries, then the "Session 19
hand-off" at the top of `docs/EMULATOR_NOTES.md`, then "Session 19b" (Undercity), "Session 19" (size check), "Session 18".

**Running state:** emulator and DB running (`./launch.sh restart-emu` after code changes), emulator.ini
`[nation] allow = all` (US and EU clients both log in; the user tests a decompilation project of the EU exe in
`../DriftCityEU-decomp`, not part of this repo: its proxy `version.dll` is in `Client US/` and loads when the client is
started through Steam, whose launch options set `WINEDLLOVERRIDES="version=n,b"`; it replaces ~585 client functions,
the VHUV handlers too). `[partypatrol] test = 0`, `[vchase] test = 0`, `[undercity] test = 0`, `[mita500] enabled = 0` (Mita bottles off for
now, user).

**Confirmed in game on 2026-10-18:**
- Virtual HUV (game/vchase.py) in the 2-player test mode: registration, the Tatiana dialog / waiting list, start,
  hits, catches, HUV changes, HP drain, the end at the time limit (after the early-end fix) with the result.
- A HUV cannot boost while being the HUV (as the client does it; the user: "it's all good"). One HUV model per city
  (the wiki's) is fine (user).

**Confirmed in game on 2026-10-17:**
- Party Patrol (partypatrol.py, flag InstantMission.PartyPatrol): countdown, posts, emergency posts, result window
  (tested alone with the test mode, `gmpartytest on`).
- Mitro City mother quests retaken after a failure; Agent Riggs.
- License gained text with the license name; repeatable missions (rq_*); Mito V-upgrade items.
- Mission Battles (Line Ball / Mecha Watch / Exodus Quake): offer, room, practice-type race, Rechallenge, EXP.
- EU client HUD speed number is km/h (the KPH labels match it).

**Done in session 17, not yet confirmed in game:**
- Solo patrol end: 0x3e3 after the last post (it stayed at 40/40); patrol reward items go to the inventory only.
- US stat points 1 per level (nation rule `half_level_points` = 0).
- Content flag `Main.AutoCarAssist` on for all clients: garage Function 1 / 2 list the car grade's assists
  (VehicleUpgrade OptionID -> Assist_Client.tdf). Unknown: whether the client applies them in races by itself.
- `tools/item_names.py`: English name for random_skb_bust ("Useless Skill Book") in both clients + server_data.
- **EU rules** (`dcemu/native/nation.py`, EU clients only; US unchanged):
  - `part_grade` on, `part_level` off: parts need the car's V grade (data.part_grade_rule: N V1-3 / S V4-6 / H V7-9
    by tier 2-2-1, set / shop / rental parts by their level's tier; options and docking N V1 / S V4 / H V7).
  - `drop_by_grade`: traffic / combo / rush drops by the car's V grade (V<n> = the n-th ItemDropServer level row).
  - `battle_levels` off + EU tiers: Newbie V1-3, Pro V4-9 with 4X V4-5 / 6X V6 / 8X V7-8 / 16X V9
    (emulator.ini `eu.section.11/12`, rooms.PRO_TIERS_EU), no level limits; invites checked per invitee's nation.
  - `level_points` off (no stat points from level), UTF-8 passwords, EU login texts (earlier sessions).
- **Client EU changes** (not in git; remade by the tools; originals in client_backup/):
  - `Data_US` deleted (identical to Client US's); `eu_client.py setup` builds from `../Client US/Data_US`.
  - `eu_client.py grades`: ItemClient.tdf in Data_EU_eng/World.agt with level 0 and the V grade (the tooltip then
    shows "Required Grade"); `eu_client.py kph`: game.nui speed labels KPH. Both run by `setup`.
  - GlobalText (Patch.006, `global_text.py "../Client EU" --column EU_eng`): 11275 "Grade %d required"
    (must stay %d), 11276 "Your car grade is not high enough for this part" (the client's own refusal), 11874 kph.
  - GlobalContent (Patch.000, `global_content.py "../Client EU" --column Value_EU_eng`): battle zone levels removed,
    the EU V tiers above.
- Earlier, still unconfirmed: Auto Fill-Up, battle quick slots and their items, Battle EXP up items, solo Start for
  non-GM accounts, Mitro City traffic / signals, crew nameplate colour, parts rules (Heat Treatment Kit), docking.

**Reference data the user brought (scratchpad only, not kept in the project):** an older EU Init.agt (7-Zip, 24
xlt from 2009-12; other car stats and prices: **the user wants the US stats and costs kept**) and an older EU
ItemClient.tdf (column 8 = 0 everywhere, same levels): no real EU grade data exists, the rule above is the user's.

**Session 20 (2026-10-18; details: "Session 20" at the top of EMULATOR_NOTES.md):**
- Confirmed in game: the Undercity (solo test mode), the new Undercity rewards (a random Alpha / Beta set part of
  the city by class + Mittron Enhancers) with their result icons.
- Not yet confirmed: DriftBooster bought from the drift shop acts at once (vshop.grant), gmitem parts / docking
  items (`gmitem [name] item [count] [+level] [A|B|C [tier]]`, docking `[+purple] [white]`) and the GM replies,
  option part fixes (types 6-10, stats, own assists; [items] option_parts still 0), the Undercity start phase
  (`gmuctest on 1-4`), 1-3 enhancers by class, the EU assist texts in km/h (`eu_client.py assists`, applied).
- Found, not changed: the EU client uses the old vehicle stat curves (GlobalContent NEWVEHICLESTAT 0 ->
  Vehicle/oldLevelModifier.dat); option assist effects the server would have to apply (drop chance, exp, fuel,
  party bonuses, HUV damage) are not done for any item.

**Done in session 19, not yet confirmed in game:**
- **The Undercity** (`dcemu/native/game/undercity.py`, new): the 2008 server's rules in the 2011 layouts (entry at
  Tatiana or `/ucm` `/uck` `/ucc` `/uco`, the four missions, HUV waves + BossHUV, rating, rewards); areas 100-103 one
  instance per party (`area.py`). Test mode alone: GM `gmuctest on` or `[undercity] test = 1`. Only script-tested.
- Message fixes from checking logged frames against the client's own handlers (decomp harness): 0x3f6 empty coupon
  stamp list (was "Wrong Command: 0" in the client's PacketAnalyzeLog at every login), 0xf3 party join (an extra empty
  unit), 0x331 license gained (2 bytes short), another player's license window (conditions now 0x29c, were 0x32a).
- Tools for this live only in the session scratchpad (they need the private decomp): `size_check.py` (walks every
  logged S>C frame through the original handlers), `uc_test.py` (the Undercity script test). Rerun the size check
  after protocol work: it found what the client logs only as "Wrong Command" / "Wrong Packet Size".

**Done in session 18, not yet confirmed in game:**
- Manufacturing Enhancer (i_n_createup): +20 % per try while held, one used up (alchemy.enhancer).
- Drift shop rows from emulator.ini `[vshop]`: `hidden` (harvest event rows 20204-20210: the server refuses them),
  `sell.10820` (PassiveAssist DriftBooster passive_a_00118 for 100 / 250 / 500 G Coin, 7 / 30 / 90 days);
  `tools/shop_rows.py apply` writes them into Client US Data_US/Init_us.agt and Client EU Init_eueng.agt.
- Tatiana Call Unit (i_n_00062) in the parts shop (`tools/item_names.py` CELLS, column 13).
- Lucky bag prize icons (Big 4 Shopping Bag): 0x192 now before 0x5b5 (the window finds prizes in the inventory).
- Fuel Booster: checked, it already worked (half price, the client shows the server's sale price).
- City instant offers skipped while registered for / in a VHUV.
- **Client US/DriftCityUS.exe without the dname.chk check** (`eu_client.py us` now writes it so; the check refused
  the rewritten Init_us.agt: "Invalid Files Detected."). Launcher: a second client starts without the Steam game ids
  when one runs (Proton's steam.exe hung). Both: the user started both clients afterwards.

**Session 22b (2026-10-18), none confirmed in game:** main channels (flag Main.NormalCh), EU Semi buttons 1-2 only
(game.nui), Major channel part stakes ([cbattle] major_stakes, `gmcbattle stakes`), CB spectators across rounds, round
replays (Emulator/replays/, Replay Pass free), Ghost Battle start with the Ghost Pass / tickets.

**Session 22 (2026-10-18; details: "Session 22" at the top of EMULATOR_NOTES.md), none confirmed in game:** channel
battles (`game/channels.py`, [cbattle], test mode `gmcbtest on` + `gmcbattle now`), EU Semi-channels by V grade (EU
client pack rewritten by `eu_client.py cbattle`), EU physics toggle (`[nation] eu.new_physics` + `eu_client.py physics`,
not switched), `gmcoin` / gmctl `coin`. Two old unit tests in tests/test_position.py fail (stale since session 12).

**Open (next session):**
00. **Channel battles (sessions 22 / 22b) are untested in game.** Try first: `gmcbtest on`, `gmcbattle owner 4 test`,
    `gmcbattle now 2 20`, Crew window > Channel Battle > Minor tab > channel 4 > Enter (one player attacks alone: finish
    2 rounds). Then: the main channel tab (flag Main.NormalCh, new), EU Semi buttons 1-2 only (EU client restart),
    spectating (Channel Battle view > Spectate), a replay of a recorded round (Replay button; Emulator/replays/; the
    client may need more than the recorded frames: see 22b), Ghost Battle in a replay (Ghost Pass / tickets; which
    connection 0x212 comes on is unknown), the Major channel stakes with two crews (`gmcbattle stakes on`), the tax
    payout (daily, [cbattle] tax_hour) and the owner refuel discount. Open questions for the user: EU Semi-channel 2 as
    V1-V6 (now) or V4-V6; whether to switch the EU physics (`[nation] eu.new_physics` + `tools/eu_client.py physics`).
    The client's own Ready button for challengers seems to want 4 crew members (test mode queues without it).
    `gmcoin` (G Coin) is new; the GM command reference is a Claude Doc ("openDC GM Commands", the user's artifacts).
    tests/test_position.py has 2 stale failures (since session 12), not from these sessions.
0. Session 20 leftovers: confirm in game the DriftBooster bought from the shop, `gmitem` parts / docking items and
   the GM replies, the EU km/h assist texts (restart the EU client), 1-3 enhancers by class; the Undercity with a
   real party at Tatiana (only solo test runs so far, `gmuctest on [1-4]`). Option parts: the server-side assist
   effects are done (session 21, `game/assists.py`: drops, exp, fuel capacity / mileage, party bonus 0x2f9);
   confirm them in game, then `[items] option_parts` (user's call). Decide whether the EU client keeps the old vehicle stat curves (NEWVEHICLESTAT, GlobalContent).
1. Confirm the session 18 items above in game (the drift shop rows need a client restart).
2. Virtual HUV: a real 4:4 / 8:8 needs 8 / 16 players (only the 2-player test was played); a party registering
   together (0x11c / 0x11d) is untested; rewards are our amounts (`[vchase] win_rate / lose_rate`); guessed fields
   are listed in the notes (0x124 @0xa / @0x16, 0x127 @2, 0x128 @2). Newbie's "status window" question was left open.
3. Confirm the session 17 items in game, EU client first (restart it: it reads the packs at start): grade
   tooltips, refusal text, KPH, garage functions, drops by grade, battle zone tiers; US: patrol end, stat points.
4. AutoCarAssist: check that a car with assists (e.g. Metro V2, Turbo Start cars) shows them and races normally;
   find whether the client applies them itself (as part options) or the server must (0x2f9 assist info).
5. 75 more Korean-named usable items (old events) could get English names in tools/item_names.py (user's call).
6. The Item Exchange Attendant (Mittron Crystal Powder -> TokenBook rows 5-9).
7. The rest of the Taipei main chain (mq_5th_*), the _m / _c branches and their reputations.
8. Battle rooms: the Complete Bonus Reward panel ("Recommended by Duffy EXP +25%", probably 0x1e4).
9. Other Taipei channels: which areas the client joins from channels other than 0 (logs: `enters area`).
10. The Windows launcher on real Windows (and the second-client fix is Linux only).
11. Drop tables: the server uses the 2008 **TW** ItemDropServer.tdf (combo chances 3-5x the 2008 US one);
    DropLimit_Server.tdf is not read. The user has not decided whether to switch.
12. Mita 500 bottles are off ([mita500] enabled = 0) until the user wants them back.
13. Older items under "Open, first things next time" in `docs/EMULATOR_NOTES.md` (session 12).

**Characters:** Xerander (cid 100000) is the user's main (level 81 now, Taipei chain in progress, faction OMD; holds a
"Useless Skill Book"). Test characters: NewChar, Newbie, DCLoverN. Make a fresh DB backup before moving
(`./launch.sh backup-db`).
