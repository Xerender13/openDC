# Drift City 2011 client (US and EU): notes for building a server emulator

Hand-off for a new Claude session. Goal: make the **2011 client** playable against a server we control: the US
version (`../../Client US`) and, since session 14, the European version (`../../Client EU`). Everything below was measured, unless marked *(guess)*.

**The emulator project is `Emulator/`** (this file is `Emulator/docs/EMULATOR_NOTES.md`; started 2026-10-12, see
`Emulator/README.md`). **Start with the newest session right below**, then "Current state and where to continue"
(session 12) and the session entries.
Paths in older entries say `Server/...`: that folder is now `Server2008/`. Moving to another device: `docs/HANDOVER.md`.

## Session 25b (2026-10-19): small ST cars' hit box, all tracks in every section, GM damage text, EU chart

- **Cars drove through lamps / trees, in races and the city; invisible hits elsewhere** (user; "the issue is the car hit
  box", fine with an original car, fine before the port): the 2016 VehicleList marks its small ST cars (Murago ST,
  Wave ST ... 47 cars) "GOTCHA_SMALL" with size 80 x 80 x 80 = a percentage of the base car (column 12). The 2011 client
  scales size, model and engine sound from the base car only for an exact "SMALL" (strcmpi at 0x4c6xxx, 0x4d2xxx,
  0x4a9800; loader 0x84a4f5 keeps column 12 at +0x218); the 2016 client tests "GOTCHA_SMALL" next to "SMALL"
  (0x4b3f16 / 0x4b3f25, 0x4cc76b / 0x4cc77a ...). So the 2011 client took 80 as the size: an 8 cm collision box.
  `port2016.py [us|eu] small` (small_cars; also in port_vehicle_list for later runs) writes "SMALL" for those rows
  whose size is < 1000 (PRANA ST has a real 4310 size and keeps its label): Client US Init_us.agt, Client EU
  Init_eueng.agt, server_data (the server does not read the label). Needs a client restart. **Not yet confirmed in
  game.** Side effect: those cars are drawn at their scale (80 %) as the 2016 client draws them.
- **Every battle zone track in every section** (user: "make a client patch to allow the usage of all tracks in the lower
  level racing lobbies"): MakeTrackList_GetCanGoCity 0x5bc2d0 allows a track when the nation is 7-10 (EU: the EU
  client already listed every track) or the track is in Taipei, else by section. `eu_client.py "Client US" tracks
  on|off` NOPs the two branches that skip "allowed = 1" (0x5bc320 jl, 0x5bc325 jg); `eu_client.py us` applies it
  when it rebuilds the exe. Applied to Client US/DriftCityUS.exe (rebuilt from the original by `us`: dname.chk off,
  GameGuard off, car limit re-applied; checked). The server never checked a room's track against its section. **Not
  yet confirmed in game.**
- **"[A] Collision damage / [B] Penalty - Wall / [A-B] Dmg, Cur HP" during races**: the client's own debug print
  (UTF-16 strings 0x8ecf1c / 0x8ecea0 / 0x8ece10, code 0x776920 ..) shown only when the character's PType byte
  (char +0x7c) is below 'N', i.e. GM accounts. User: no patch for GMs. Left as is.
- **Performance graph Total column (dealership car detail, game.nui dialog 2940000, Total cells 2940038-2940046,
  filled by FUN_005cfba0)**: US fine (user). In the EU client V1-V8 show "-" and V9 odd text for Murago ST, while EU
  Hunter ST shows a number at V9. With GlobalContent CarChartAdv on (EU) the column shows assists (row +0x17c / +0x180
  pointers, "%.1f" / "%.1f%s", "-" when none) instead of the stat sum. The EU VehicleUpgrade and Assist_Client tables
  are identical to the US ones, and Murago ST's car assists (VehicleList column 76: a_00118 a_00500) exist in both.
  Loader note: LoadVehicleUpgradeList 0x4cd710 zeroes its row buffer once, not per car, and fills an option pointer
  only for a non-empty name. Cause of the V9 text not found; the user chose the US layout instead: `eu_client.py
  chart us` (part of `setup`) sets CarChartAdv 0 in the four EU columns of Client EU Patch.000 (was 1; US 0), so the
  Total column shows the stat sum as in the US client. Needs an EU client restart. **Not yet confirmed in game.**
- **Windows: launch.bat closed right after "emulator: listening"** (a Windows user's screenshot, Portuguese Windows:
  "Não é possível indexar em uma matriz nula", launch.ps1:75 `'all' { Start-Server; Start-Client $Rest[0] }`): with no
  extra arguments PowerShell leaves `$Rest` (ValueFromRemainingArguments) at $null, and `$Rest[0]` throws "Cannot index
  into a null array"; the server was already up, only the client did not start, and the script ended with exit 0, so
  launch.bat (pauses on errorlevel 1 only) closed. Fix: `if (-not $Rest) { $Rest = @() }` after param, plus a trap that
  exits 1 on terminating errors (the window then stays open). **Not tested: no PowerShell here; needs the Windows user.**

## Session 25 (2026-10-19): race traffic on every track, bought car grades, gift boxes, Semi tooltip, GM doc

- **Race traffic on the new tracks** (user: "traffic during races on the new tracks added last time"): 18 battle zone
  tracks had no server path file (server_data/race/PVP_map*.index): the 10 tracks of session 24b and 2011 ones the 2008
  server never had (oros_track9 / 10, koinonia_track11 / 12, cras_track11 / 12, moonpalace_track12_r, the Taipei
  tracks). Server2008/tools/make_traffic_paths.py's fixed-offset chpath reader breaks on their chunked layout. New
  `tools/race_paths.py`: reads the client's own Data/World/<city>.agt PVP_map*.chpath in the chunked layout (as
  city_traffic.read_chpath, keeping each point's progress), resamples to one point per progress unit, writes only
  missing .index files; Taipei also gets trafficCarSettingForTrack_5.txt (TrafficFlowControl's Taipei models).
  101 tracks with traffic (was 83). taipei_track2 (PVP_map5_03.chpath) has no paths in the client: no traffic there.
  Script-tested (engine Race on tracks 97 / 99 / 101: 28-53 cars, 6-9 near a car, like an old track). **Not yet
  confirmed in game.**
- **Bought cars' grade** (user: a new car listed as V9 in the dealership came as V1; then "The 2016 client has all
  cars start at V1"): the dealership's V tabs are VehicleList column 23, the car's class (record +0x138, tab buttons
  at window +0x140 + class * 4, 0x5db6xx; also the CarShopSellMaxGrade filter, 0x5d3c00). 2016 has V9 there for
  Murago ST too, so V9 tab + V1 car is the 2016 behaviour. Found on the way: 77 sold 2011 cars (Utopia, Gigas, Rotary
  ...) have empty VehicleUpgrade rows (stats and capacity 0) below their class, and buy_car made every car grade 1
  for the V1 price (Utopia: V1 for 1000 instead of V9 for 100000). Now cars.start_grade: the first grade with a real
  row (capacity > 0) and its price, for buying and for create_car (gift boxes, gmcar; gmcar's reply names the grade
  given). 2016 cars stay V1. Script-checked (Utopia 9, Drifter 1, Murago ST 1, Rotary 5, TRIO 7). **Not yet confirmed
  in game.**
- **Blank tooltip under EU Semi Channel 2** (user screenshot): the spot is the hidden Semi-channel 3 button; the
  window still shows the tooltip under the mouse, and semi_tooltips drew a blank bubble for Semi-channels without a
  rule. Now those pieces are fully transparent (US 4-5, EU 3-5). Applied to both clients; needs a client restart.
  **Not yet confirmed in game.**
- **Gift boxes in the editor** (user: "add the ability to make Car gift Boxes", then "gift boxes with items from a list
  of items and with % chance for each item"): new `tools/giftbox.py` (docstring = the layout) and the Server Workshop
  dialog Items / Cars > New gift box. A box = a UseItemClient row (kind giftbox, appended at the same row in
  server_data, US Patch.004 and EU Data_EU_eng/World.agt; refused unless the three tables match row for row) + its
  RewardGroup group (server_data and both Init packs) + an icon control in game.nui dialog 270000 (the Serpens box
  picture with a label, both clients). Lines: car (key + Etc_Value grade), item, drift, mito, exp. Each line's own
  chance uses the existing roll rules: a sub-group [item c, n/a 100 - c] linked by a RewardGroup row of 100 (no server
  change). Tested end to end on copies of the packs in the scratchpad (rows, groups, icons, refusals) and with
  tests/test_editor.py (new GiftBoxes test; also a missing translation, 셋 = Set, made an old test fail). No box was
  created in the real files. **Not yet used in game.**
- **GM Commands doc**: the old Claude Doc was on the user's other account; a new one, "openDC GM Commands"
  (https://claude.ai/code/artifact/d53089bd-4fd4-479e-80cd-a8eb956c26c3), adds gmcar, gmcbattle (status / now / start
  / end / owner / stakes / replays), gmcbstart, the gmctl car / cbattle / level / exp / money / test / account commands
  and gift boxes.
- **"disable debug information during races in battle zone"**: found in session 25b (GM-only client text; left as is).
  Earlier search notes: The server sends no chat notes
  during races. Client facts: debug text printer 0x4e3410 / 0x4e34c0 draws only when the dev mode *(0x94d16c)
  (getter 0x4e1f80) is not 0 / is 0x29 (AI racer "MIND: / ACTION: / WaitTime:" text at 0x47c0c0); the mode is
  set only by code that sets it to 1 for one print and restores it (0x7737d0, 0x78ce70: replay texts) and 0x4ff5be
  (0x4b). Waiting for a screenshot from the user.

## Session 24d (2026-10-19): gmcbattle start, track pictures, cars and tracks for the EU client

- **gmcbattle start [battle minutes]** (alias `gmcbstart`; control port `cbattle start`; user: "start channel battle
  right away"): with registration open (PREPARE) the battle time becomes now (the lobbies try a round on the next
  tick); with nothing open, registration and battle open together (schedule(now, 1 s, length)); refused while a
  battle is on. Script-tested (Board with the real config: none -> prepare -> wait at once). Not yet used in game.
- **Track list showed the same picture for every track** (user screenshot, battle zone room; seen live with the
  client: with Recommend off the slider moves through the tracks but the picture never changes). The battle zone
  room's track pictures are game.nui dialog 1060000's first controls (1060001-1060106, all at one place); the client
  shows the selected one among the controls before the dialog's other controls (1060107 frame ...). port2016.py had
  removed the two 2011 controls it replaced (koinonia_track12, taipei_track4) and appended its controls after the
  dialog's other ones, so they stayed drawn on top. Now: replaced controls keep their place and id, added ones go
  after the last original track picture (Interface.place_tracks; the original order kept, checked against
  client_backup/game.nui.orig). Applied to both clients. **Not yet confirmed in game.** (Recommend ticked shows the
  Recommend column's tracks only; that is the client's filter.)
- **Cras / Oros tabs empty ("No maps available"; user): not a bug.** MakeTrackList_GetCanGoCity (0x5bc2d0, called per
  track by the list builder 0x5bd660): track +0x98 = city (5 Taipei always allowed); in the Pro section (channel
  12, lobby section value 0xc) the room type's tier bit decides: 0x20000 4X -> cities <= 2 (Moon Palace, Koinonia),
  0x40000 6X -> <= 3 (Cras), 0x80000 8X -> <= 4 (Oros), 0x100000 16X -> all. The user's room was type 0x20080 (4X);
  log: Koinonia (flags 0x108) and Mitro (0x800) tabs gave tracks, Cras (0x200) / Oros (0x400) map 0. Explained to
  the user; no change.
- **Cars and tracks for the EU client** (user: "The new cars work without issues, port them to EU client as well"):
  `port2016.py eu tracks|cars` with the EU paths (Client EU's own Data/vehicles.agt, Data/World/*.agt,
  Data_EU_eng/Init_eueng.agt, Data_EU_eng/World.agt for the keys, Data_EU_eng/gameui, Data_EU_eng/audio/engine,
  DriftCityEU.exe patched the same way: same program); backups <name>_ClientEU...orig (DriftCityEU.exe.orig, the
  vanilla exe other tools build from, untouched). The tracks were ported too: the EU client shares the server and
  would otherwise list tracks it has no files for. Checked: the EU client runs past loading (45 s, no failure).
  Not yet confirmed in game.

## Session 24c (2026-10-19): gmcar

User: "add a gm command to be able to give player a car based on its name". Chat `gmcar [name] car name [V1-V9]`,
control port / `tools.gmctl car NAME CAR-NAME [V1-V9]` (misc.gm_car, find_cars): the car is found by its shown name
(VehicleList UI Name, e.g. AXIS ST), model name (Car Name, e.g. Kubelwagen), model file (pc_0199s) or Unique Id;
an exact shown name wins, else every car containing the words (several -> listed, nothing given). Given as a gift box
gives a car (cars.create_car: full Mittron, needs garage space; its key with the CarID; 0x62 RewardCar), grade V1
unless given. Script-tested with stubs (AXIS ST V5, pc_0442s V9, ambiguity, unknown name); not yet used in game.

## Session 24b (2026-10-19): 2016 tracks ported; the 2016 player cars hit a client limit

User: "Port the tracks and all the new cars that are absent in 2011 (player cars only)".
- **Tracks (done, `tools/port2016.py tracks`; docstring = the details; not yet confirmed in game):** the 9 tracks of
  the 2016 PVPTrackInfo the 2011 one lacks (ids 93-102): Oros Track19, Koinonia Track24 / 25, Cras Track24 / 25 with
  their folders, PVP_map*.chpath and 44 new Obj files appended to Data/World/oros|koinonia|cras.agt (originals in
  client_backup/<pack>.orig; the other entries' compressed data copied as is, checked byte-identical on a copy);
  Taipei Track3 / 5 / 7 and Koinonia Track23, whose files were already in the 2011 packs, only needed rows. 134 rows
  appended to Init_us.agt PVPTrackInfo.xlt (Count 1265, TrackCnt 103) and server_data. Track pictures are found by
  name (PVPTrackInfo "name"): controls copied from 2016 game.nui dialogs 1170000/1180000/1190000 to 2011
  1060000/1070000/1080000, 15 picture pieces added to uitex.agt; 2016 pieces whose 2011 namesake holds another
  picture are renamed "..._p16<atlas>". Found: **uitex.agt container = byte sum of the lower-case atlas name % 16**
  (8526 / 8533 pieces). The client reads PVPTrackInfo into a growing array (0x83f970, 0x308-byte rows), no track
  count limit seen. The 2016 models are the same Gamebryo 20.0.0.4 with no block type 2011 lacks. Not done: race
  traffic on the new tracks (no 2008 .index files), the EU client (its packs are separate files).
- **Cars: 218 player cars of the 2016 VehicleList are not in 2011** (Unique Ids 94, 127, 198-442 ...; 2350 files,
  890 MB uncompressed: player/, texture/, neon/; 20 new tire models / TireList rows; 156 engine sounds; per car:
  VehicleList row (2016 adds column 77 "Color Group Name"), 9 VehicleUpgrade rows, VehicleDisplay row (2016 adds
  "Category"), UseItemClient key row, aero sets pc_XXXXs_01-03 (VisualItem + VShopItem rows; _01 = the basic body),
  4 interface pictures found by name (game.nui 1800000 key icon, 2610000 / 2620000 / 2630000 name images; 2016 1990000
  / 2840000-2860000). **Limit: the 2011 VisualItem keeps one byte per car type per item at +0x7c of a 0x1ac-byte
  record, car index < 300 (0x7694f6, cache 300 x 56 at +0x710, 0x769ee7).** 2011 uses 148 car types, so 152 more
  fit; all 218 need a client code change (record size / limits). User chose: patch the client limit.
- **Cars ported with the limit raised (`tools/port2016.py cars`; not yet confirmed in game).** Read with the EU decomp's
  Ghidra output (../DriftCityEU-decomp/raw/src, same program): LoadVisualItemList 0x84ad00 maps each car column to
  `local_670[col]` = VisualItem **row 2 ("Engine sound") = the car's Unique Id**, and stores the item's Exist byte at
  record +0x7c + Unique Id (`auStack_144[300]`); the record ends with a float at +0x1a8 (0x84c5e0: the size of "T"
  items). So the limit is on the Unique Id (< 300), not on the number of cars. Patch (`port2016.py exe`, code
  tools/p16_cars.s, new section .p16 at 0xa1e000, SizeOfImage 0x620000): record 0x1ac -> 0x27c (all stride / copy
  sites in 0x7690c0-0x769ea5), loader replaced (column map 1024, record in .p16), default-part cache getter 0x769080
  falls back to FindDefaultPart 0x7694e0 for Ids 300-511, Id checks 300 -> 512 at 0x7694a8 / 0x7694f6 / 0x769bd9 /
  0x679b7d / 0x602202 / 0x67dbf9 / 0x68ed76 (the others comparing with 300 are unrelated: 0x4a42f8 frame time,
  0x57b83c text, 0x6e73eb mesh, 0x7bd12e, 0x778dea world objects). None of these functions is replaced by the decomp
  version.dll. Unique Ids 300-303 (RACHEL BT, ACROBAT, Impact MINI, TITAN MINI) would share bytes with the float:
  renumbered 102-105 (free in 2011 and 2016). Engine sounds are idle%u / mid%u.wav by Unique Id (0x547290).
  Applied: 218 VehicleList rows (364 player cars), 1962 VehicleUpgrade rows, 227 VehicleDisplay rows, 20 tires,
  363 VisualItem car columns (2011 cells unchanged: 182420 checked), 282 aero items + VShopItem rows, 218 keys in
  Patch.004 UseItemClient.tdf, 1776 files (577 MB) into Data/vehicles.agt (now 388 MB), 154 engine sounds, 991 picture
  pieces (the 2016 Dev Ed tex lacks most car name images: taken from ~/Drift City World's uitex.agt). Checked: the
  server's Tables load them (364 player cars, keys, aero fits only its car, paints fit new cars); the exe patch
  disassembled from the patched file. **Not tested: the client loading the tables / drawing the cars.**
  tools/shop_rows.py now keeps rows other tools added; eu_client.py `us` / `setup` re-apply the exe patch.
  EU client not updated: an EU client near a US player driving a new car lacks its model and table rows.
- **Crash at start after the port (user: "The game crashes on loading"; fixed):** the client exited with code 3 after
  `__security_error_handler` (no server connection). Found by running the client under Proton without the launcher
  (token = md5 of the 5-minute CLOCK_MONOTONIC window) with gdb on the stack cookie check's failure jump 0x895c6c:
  the return address 0x84a284 = the VehicleDisplay row reader 0x84a240 (format "%s%s%d%d%d%d" into two 32-byte stack
  buffers, called from 0x4cd630 `Init/VehicleDisplay`); the 2016 name "MITSUBISHI LANCER Evolution III 1995" (36
  bytes) overwrote the cookie. port2016.py now clips new names to 31 bytes (VehicleList / VehicleUpgrade /
  VehicleDisplay) and 34 (VisualItem / VShopItem: the 2011 maximum), and chooses the cars against the original
  VehicleList so a second run rebuilds all of them. Checked: the client then ran past loading (45 s, no cookie
  failure, under gdb). Not yet checked: logging in, garage, dealership, driving a new car.
- **New cars showed only their wheels (user, dealership screenshot of AXIS ST; fixed):** an "s" car's body is its
  basic aero set (pc_XXXXs_01, VisualItem category 6; ST / BT variants use the base car's set, e.g. AXIS ST 199 ->
  pc_0198s_01). The client takes the car's default part with FindDefaultPart 0x7694e0 = the first row of the category
  whose byte for the car is 1, in table order. The generic rows pc_Aeroset1 / pc_Aeroset2 / pc_AeroMK2 / pc_Aero /
  pc_Aero2 / pc_AeroMK2+ (Index 0) fit every car and stand after the car rows; port2016.py had appended the new rows
  after them, so the generic set became the body. Now inserted after the category's last pc_NNNN row (the 2016
  order). Checked: every new car's first fitting category-6 row is its own set; the 2011 cars' defaults unchanged
  (vanilla compared; 201-203 were columns without a 2011 car). Not yet confirmed in game.

## Session 24 (2026-10-19): Semi-channel tooltips in the channel battle window

User (screenshot, US client, Crew Center > Semi Channel tab): "fix the client UI bugs in Crew center Enter Channel
battle screen on semi channels. They appear on both US and EU client." The screenshot showed red digits "05 / 16"
with a line to the Semi Channel 1 button, next to the list.
- **Cause: a vanilla client art bug.** While the Semi-channel list is open the window (UI+0x2ac, 0x6a3330) shows game.nui
  dialog 2030000 for every nation but JP (2) and, under the mouse, the Semi-channel button's tooltip: controls
  2030001-2030005 (ID_TC_SEMICHANNEL_TOOLTIP_1..5; window +0x20b8 / +0x20bc.., read at 0x6ab9a5), pictures
  "3,625~179,697_ui_contents56.dds" .. "3,917~179,989_ui_contents56.dds". In the 2011 US uitex.agt (unchanged: same md5
  as client_backup/uitex.agt.orig) those pieces hold the kill counter's digits ("0 5 / 1 6", "2 7", "3 8", "4 9",
  "KILL"); the EU folder is built from it. The 2016 client (DriftCity Dev Ed, Data_US/gameui/tex/F.ntx) has the real
  pieces: a speech bubble "Crew Member / with V3 ~ V6 Vehicle / level 40 or less" (V3-V8 / 60, V3-V9 / 70, then two
  more), i.e. the 2016 rules, not the 2011 ones (US: levels only; EU: V1-V3 / V1-V6).
- **Fix (client packs, asked for by the user):** new `tools/semi_tooltips.py`: the 2016 bubble (cached as
  client_backup/semi_tooltip_N.dds; a drawn bubble when the 2016 client is absent), text cleared, the server's rules
  written in its colours: US "Crew Member / level 40|60|70 or less", EU "Crew Member / with V1 ~ V3|V6 Vehicle / no
  level limit"; Semi-channels without a rule get a blank bubble. Only those 5 pieces change (checked against the
  backup: 8533 pieces, 5 differ); header bytes 20-31 kept; `reset` puts the original pieces back.
  `eu_client.py cbattle` runs it for the EU folder. Applied to Client US and Client EU. Needs a client restart.
  **Not yet confirmed in game.**
- Not bugs (the client's own design, left as is): the panel title says "Channel 1" for Semi-channel 1 (text 10324
  "Channel %u" with index - 9, 0x6a6fb5; the Regular tab uses the same text with index + 1); the crew rows stay empty
  while the channel has no owner (0x6a6a4e: owner crew id <= 0 skips them). Switching to the Semi tab selects
  Semi-channel 1 (0x6a3b49) without sending 0x372; clicking a Semi button sends 0x372 with 10 + N - 1.
- EU ("doesn't have channels listed there properly"): no EU session since session 22b (Main.NormalCh, EU Semi
  buttons 1-2); the last EU log (20261018-225013) predates them and shows the Semi tab only. Waiting for an EU
  screenshot / description.

**2016 client vs 2011: Mitro City (Taipei) and missions** (user: "see if we can port the remaining mitro city (Taipei)
and missions from 2016 client"). Compared every file of Client US (packs + patches, md5 per entry) with DriftCity Dev
Ed (loose files; 2016-02 exe), vehicles and audio left out (scratchpad manifest.py / mdev.py):
- **Taipei is the same city in both**: terrain, paths (path_taipei.chpath / .signal), tracks 3 / 5 / 7, modeltable;
  only 10 textures added / 13 changed and taipei.xlt +2 objects (New_START / New_PVP gate models, battle zone prop
  occupancy 0 -> 10). MotherQuest.xlt identical (38 rows), Icon_Taipei_Client.tdf the same 80 posts (2016 adds a 6th
  column, 0 everywhere). Nothing of Taipei is missing in the 2011 client; the emulator already serves its traffic,
  signals and Mother quests (session 13; the chain is still not confirmed in game).
- **2016-only missions** (QuestClient 273 -> 286 rows; all rows also differ in reward columns 75 / 76, doubled):
  - neo_q_0001-0006 (IDn 163-168): "A Girl from the Future" / "Death of President Jacob" / "To the OMD Communications
    Headquarters", a ROO line (after quest 143) and an OMD line (after 161), level 40, Oros posts (one new:
    post_4rd_10009), portraits ch_neo_0001_0x (present in the 2011 uitex), 2000 exp / 4000 Mito.
  - rq_00069-0075 (IDn 10052-10058): Christmas 2012 chain of Yuki in Moon Palace ("Senior Yuki's Request" ..
    "Runaway Ghost Car", "Chasing Santa": chases of HUV rows 19173 / 10079), 20 new Moon Palace posts
    post_1st_2012_crist_01-19 + post_1st_dummy (Icon_Moonpalace_Client), reward item 2012_yuki_giftbox.
  - Instant_Client 147 -> 207 rows: ROO patrol variants (move_ROO "Minyoung's Scouting") per level band.
  - Other 2016 content: battle tracks Oros 19, Koinonia 24 / 25, Cras 24 / 25 (folders + pvp_mapN_M.chpath);
    Init tables for 2016-exe features (compound, teamresearchtable, valentainreward, worldmatchseasonlaptime, ...:
    no 2011 client code reads them).
- Porting the quests means rewriting the 2011 client's QuestClient.tdf / Icon_* tables (rows appended: the client
  indexes quests by row) and the server_data copies; the chases / gift box also need HuvTable / item rows. Not
  started: waiting for the user's choice.

## Session 23c (2026-10-19): Compose restored, live connection checked, handoff updated

User requested reinstalling Podman Compose, then reported starting the server and requested handoff notes.
Podman 6.0.2 was already present. Installed podman-compose 1.6.0 in the user venv
`/home/deck/.local/share/podman-compose`, linked from `/home/deck/.local/bin/podman-compose`.
SteamOS system partition remains read-only; no sudo/system package changes. Both Compose command forms
reported the installed version outside the sandbox. Recheck/recreate the environment after Python upgrades.

After the user's server start, read-only checks returned: emulator running (PID 17118 at that check),
database healthy; `gmctl who` -> `OK 0 online`; a deliberately unmatched `accounts` search -> `OK []`.
This supersedes the earlier session-23 startup failure as an open blocker. Account creation, credential
changes, role changes and balance mutations were not exercised against live data. No client packs,
account rows or character rows were changed to test the editor.

Updated `docs/HANDOVER.md` with the editor file map, dependencies/launch commands, translated display
semantics, backups/restore, mode tuning scope, GM/account behavior, Compose location, test results and
remaining verification. Corrected the handoff's GM role table reference to `SKID_CHARACTER_TB.PTYPE`.
Latest tests remain 16/16 editor tests and the desktop English/original-view smoke test; earlier full
suite was 39/41 with the two known position-test failures. No commit/push requested or performed.

## Session 23b (2026-10-19): English text in the desktop editor

User: "Translate Korean parts to English in the editor from the tables."
Added offline display translations (`tools/editor/translations.py`) for every Korean value in the four
item tables (ItemClient, UseItemClient, VisualItem, VShopItem), Korean column headings throughout the
loaded tables, rental/set effects, consumables, AI/car parameters, assist effects and upgrade requirements.
Additional recurring reward/event terminology is translated; unmapped historical prose/names remain
in their original wording rather than inventing translations. Values/effects are translations of source
text, not claims that the corresponding old event or item is implemented.

Lists, editable fields and previews use English; English and Korean search both work. "Original table
text" switches values back to their source wording. Translation is a display layer: opening/focusing a
translated cell or saving an unrelated edit never writes the English display value over the Korean source.
Only explicit changes become edits. Client/server tables and game behavior are unchanged; reopen the
editor to load the update, without restarting the game server.

Validation: all 16 editor tests pass, including complete four-item-table translation coverage, Korean
heading coverage, byte-identical round trips with every translated item cell visited, English/Korean
search, explicit edits and numeric/unknown-text preservation. Desktop smoke test checks English/original
view switching and absence of implicit edits. Not yet confirmed by the user.

## Session 23 (2026-10-19): desktop server editor

User requested an editor for items, cars, every game mode's parameters/rewards, GM console and accounts.
Added `tools/editor/` (Tk desktop; Pillow for original DDS/WebP pictures), `editor.sh` / `editor.bat`.
Reads server copies of XLT/TDF/text/INI files; named fields for verified columns, original XLT headers,
configuration comments and explicit raw-column labels elsewhere. Game artwork comes from the US game's
`game.nui` + `uitex.agt`, with the user's catalog ZIP as an optional icon/description fallback. No client
packs changed. Cached client-side values still require deliberate synchronization through existing tools.

`server_data/mode_tuning.txt` + `native/mode_tuning.py` expose 107 previously hardcoded gameplay values:
Undercity fees/stage payouts/timers, Rush prizes, Virtual HUV prize items, chase time tables, daily token.
Startup validates the complete file against an explicit allowlist before applying it. Default tuning is
identical to the previous gameplay. Protocol constants cannot be changed. Modes not implemented by the
emulator and other rules still embedded in handler code remain outside the editor's supported fields.

Local GM control adds account search/detail/create/password/role, online level/EXP/Mito, channel battles,
party/VHUV/UC/CB test modes, Rush and forced gate rewards. Password changes/role edits reject accounts
connected to the lobby or game; existing MD5 authentication retained. Credential commands redact passwords
from logs; account list/detail responses aren't copied to general logs. GM roles use existing character
PTYPE (new characters keep their normal default); adminlist.txt overrides are reported on revocation.
The editor uses Docker Compose stdin for Windows GM access, keeping the control port private.

Saves preserve exact backups in ignored `editor_backups`, reject externally modified files, preserve
TDF row indices/identifiers, BOM/encoding/line endings and untouched cells. Delivery/patrol reward lists
can duplicate rows for additional prizes. The legacy CP949 Lap Time file is preserved. No live account
or character data edited while developing. **Not yet confirmed in game**. Validation: editor tests for
all-table byte round trips, TDF/XLT edits and exact backups, stale writes, legacy encoding, INI secret/comment
preservation, reward rows, tuning defaults/validation and account password/offline/log behavior. Desktop
smoke test passed on the Deck display (item/car/mode selection and forms, original artwork, no writes).
Full suite: 39/41 pass; the two pre-existing `test_position.py` failures documented in HANDOVER remain
(one stale tutorial-state expectation, one DB stub missing `rows`). Real Windows desktop/Docker path untested.
`launch.sh restart-emu` briefly reported listeners (pid 14551); subsequent GM connection was refused and
host status showed emulator stopped, DB container exited since 16 hours earlier. Live database/account
integration was therefore not verified; start `./launch.sh server` for the GM and Accounts panels.

## Session 22b (2026-10-18): main channels shown, EU semi buttons, part stakes, CB spectators, replays, Ghost Battle

User: "Make a document with all the GM commands" (a Claude Doc, "openDC GM Commands"), "implement losing an equipped part
when failing to take a major channel and make it toggleable", "implement spectator mode in CB and the use of CB replay
items", "check why the client only shows 3 semi-channels", "check same for US client", "There are no main channels shown
in the client". **None of it confirmed in game**; script-tested with stubs (scratchpad cb_test.py / cb_test2.py).

- **No main channels** (user): the channel battle window (0x6a5de0) greys the Major / Minor tab buttons (UI+0x2ac +0x20e8
  / +0x20f0) and forces the Semi-channel tab unless content flag **Main.NormalCh** ([net+0x270] bit 7) is set; the 2008
  Contents.ini has no such flag. NEW_FLAGS: Main.NormalCh, Main.SemiCh (bit 8), TeamCenter.ChannelBattleReplay (the
  "Replay" buttons of the channel battle view, 0x58d730: [net+0x2a4] bit 3).
- **3 Semi-channel buttons in the EU client** (user): read from the running client (window UI+0x2ac, buttons +0x2078..:
  flags 0x27 / 0x27 / 0x23, the others 0x26): the server's state bit only enables or greys a button (bits 2 / 4); bit 1
  (shown) comes from the layout, game.nui dialog 2020000: Semi-channel N = control 2020001 + N, shown when it has a
  `<NATION>` entry (the US layout: 1-3). `eu_client.py cbattle` now also drops that entry for Semi-channels the EU rules
  do not open (built from client_backup/game_Data_EU_eng.nui.orig): EU shows Semi-channels 1-2. US client: 3 buttons =
  the US rules (Semi 1-3), left vanilla.
- **Major channel part stakes** ([cbattle] major_stakes, default 0; GM `gmcbattle stakes on|off`): 2008
  BS_CBattleRoom::RegisterBattleItem (0x5bebf0: at the match's first round, one item of each racer, locked) and
  BS_CBattleLobby::GatherBattleItem (0x5c0400: when the match is decided, the losers' items are deleted ("LoseItem", 0x392
  CBattleMissedItems to the owner) and go to the winning crew's master ("CBattle", by message when offline; 0x391
  CBattleRewardItems to the winners)). Here: a random part on the car raced with; locked (no unequip / sell while at
  stake); the prize goes as a message with the part attached (mail.py item text: enhancement, converts, box kept) to
  the winning master, online or not. 0x38d CBattleItems lists the parts at stake (0x88 each: wchar[32] id + item unit
  0x48 = XiStrMyItem's first 0x48 bytes, *guess*). Not done: the 2008 "reserve" rule (items with assists worth > 4 kept
  out).
- **CB spectators**: 0x38b JoinOBS now keeps the spectator for the whole battle (lobby.spectators): each round's race
  room gets them (0x26e + 0x1bf; rooms.watch's spectator-option and one-racer checks skipped), between rounds they get
  0x386; 0x1bf carries the crews and round states (Room.obs_teams: i32 state[4], i64 crew[2], mark[2], wchar[31]
  name[2]). 0x1e0 LeaveOBS ends it.
- **Replays** (TeamCenter.ChannelBattleReplay; the Ch. Battle Replay Pass, ch_replaypass, drift item category 44): the
  client's replay = a recording of the race as received (its own recorder 0x78d9e0 "play_record.r0": 0x26d RoomModify
  0x8e, 0x1be RoomState, 0x329 + XiPlayerInfo per racer, then the race commands the NetMsg handlers pass to App+0x174
  vfunc 0x34: 0x221, 0x224, 0x225, 0x22b, 0x21e, 0x2bd, 0x223, 0x220, 0x2c2, 0x2d0, 0x21b, 0x2d5, 0x23e, 0x21f, 0x1ec),
  played back in scene 0xd. The server records every round so (area.recorders fed by the barea relays; race traffic of
  the first racer) into Emulator/replays/<key>.r0 + index.json (git-ignored; [cbattle] replays = how many kept).
  Protocol (client 0x52dbf0 / 0x52b130 / 0x7921a0 / 0x78d120 / 0x78cfb0 / 0x58ee60): 0x395 -> 0x396 list (0xec
  entries), 0x397 step 0 open -> 0x398 result 0, step 1 (with the first data) pays -> 0x398 result 2 + price + Mito;
  0x227 on the race connection (net+0x168) -> 0x228 chunks of 16000. Prices = the client's: Major 1000, Minor 500, Semi
  free; free with the Replay Pass. *Unverified*: whether playback needs more than these frames (the recording client
  also writes its own car as a 0x220-type frame, 0x538180; here every racer's 0x221 is in the stream).
- **Ghost Battle** (Ch. Replay Ghost Pass ch_ghostpass category 45, Ch. Battle Ghost Tickets ch_ghost_NN): 0x212
  GhostStart -> 0x213 with the client's own stat blocks (client 0x52cda0 reads @0x16 / @0x7e / @0xa6), when the player
  holds the Ghost Pass or uses up a ticket of the replay's channel (*our rule*); 0x216 -> 0x217 (ignored by the
  client). Registered on game and barea (which connection the client uses is not known yet).
- The GM command document: a Claude Doc "openDC GM Commands" (all chat GM commands, test modes, channel battle, sticker
  and control port commands).

## Session 22 (2026-10-18): channels and channel battles, EU physics toggle, G Coin GM command

User: "Implement channel battle and channels. For EU client version implement the driving physics new model toggle (the
EU version drives on old physics). For EU version channel battle semi-channels don't have level limitation, but V grade
limitation. Need 1 semi channel with max V3 allowed, 1 channel with max V6 allowed." Then: "for 2011 the attacker needs
just 2 straight wins", "add a testing function where just 1 player is enough to attack a channel", "add a gm command to
add g coins (han coins) to account". **Nothing of it confirmed in game yet**; script-tested with stub sessions only.

- **Channel battles** (`game/channels.py`, rewritten; docstring = every layout and rule). Source: the 2008 server
  (ZoneServer.pdb: PacketParser::Cmd_CBattle* 0x662900-0x664c30, BS_CBattleLobby 0x4c4440-0x4c9c00 / 0x5be6b0-0x5c1580,
  BS_CBattleBoard; decompiled with the decomp's zone Ghidra session) and the 2011 client (channel battle window class
  UI+0x2ac: 0x6a5de0 the 0x35d list, 0x6a2340 the Enter checks, 0x6a3b90 the buttons, 0x6a6120 / 0x6a8900 the state,
  0x6a61b0 the battle records, 0x6a5230 the settings, 0x6a7590 the crew room window; 0x5308f0 0x376).
  - Found: the 2011 channel record splits the 2008 i32 channel into i16 channel + u8 max level + u8 max car grade
    (0x6a5de0 -> +0x18f4 / +0x1954; 0x6a2340 greys Enter above them): per-nation limits go there. Channels 0-9 normal
    (0-1 Major), 10+ Semi-channels (MinSemi<index-9>ChBattleGrade). u16 @0x130 bit 0 = channel shown / open.
  - Found: 0x1e7 PvpLoad with type 1-99 is a channel battle race (PvP manager App+0x168 vfunc 0xd4 -> 0x7726d0: changes
    to scene 0x12, opens window 0x29); the 2008 server sent the round number there (TryBattle -> StartRace(round + 1)).
  - Rules (2008 + user): crew master / first class makes the crew room (0x370), members join (0x371); the owner crew's
    room defends (its client readies on 0x376), challengers queue on Ready (0x384; the client's button wants 4 members);
    Challenge Coupon i_n_00037 used up at the first round; crew rank B for normal channels; one try per channel per
    battle; no defence room -> the first challenger defends and owns the channel at once. Rounds: both crews' members
    move into a race room (team 0 defence, 1 attack; rooms.py race, type 0x28 team points; tie -> defence). **2 straight
    attack wins take the channel** (user; 2008 EndBattle agrees: AtkWinCnt >= 2). Defence win: the challenger is out,
    the defending master gets 5000 Mito x attacking racers (0x393). End: channel win + successive weeks
    (SKID_TEAM_TB.CHANNELWINCNT, SKID_CBATTLE_TB), rooms closed (0x1d6). Owners kept in SKID_CHANNEL_TB / OWNCHANNEL.
  - Tax: every refuel payment adds Major 10 % / Minor 3-5 % / Semi 1-1.5 % to each owned channel; paid daily
    ([cbattle] tax_hour) to the crew master (*our choice*: the 2008 payout was a stored procedure we lack). Owner refuel
    discount 10 % / 20 % for 2 / 3+ weeks (session.fuel_charge, 0x2d4 sale flag bits 4 / 2).
  - Per nation ([cbattle] main / semi.N, eu.main / eu.semi.N = max level, min grade, max grade): US Semi 1-3 below level
    40 / 60 / 70 (2008 BS_CBattleBoard); **EU Semi 1 V1-V3, Semi 2 V1-V6, no level limits** (Semi 3 closed for EU),
    normal channels V6+ (EU client design). *Our reading*: "max V3 / max V6" as V1 upwards (Semi 2 could be V4-V6: one
    ini line + `tools/eu_client.py cbattle`).
  - EU client changed (user-requested; `tools/eu_client.py cbattle`, part of setup; originals in client_backup/
    Patch.000_ClientEU.orig / Patch.006_ClientEU.orig): GlobalContent EU columns MinSemi1/2ChBattleGrade 3/4 -> 1/1,
    MinSemi3-5 -> 0 (MinChBattleGrade stays 6); GlobalText EU_eng 11409 / 11411 rewritten for the two Semi-channels.
  - **Test mode** (user: 1 player attacks alone): `gmcbtest on` (or [cbattle] test = 1): no coupon / crew rank, the room
    queues at once, a lone test crew against an owner without a room attacks alone (finish = round win, 2 wins = the
    channel). `gmcbattle now [min] [length]` opens a battle now, `gmcbattle owner N test|crew|none`, `end`, `status`.
    Try: `gmcbtest on`, `gmcbattle owner 4 test`, `gmcbattle now 2 20`, then Crew > Channel Battle > channel 4 > Enter.
  - rooms.py: `room.no_start` (no Start in channel battle rooms), `room.on_result` (after the result), leave() tells
    channels.room_changed.
  - Not done: the Major channels' part stakes (2008 GatherBattleItem; 0x38d answers empty), 0x1bf spectator state for
    crew rooms (2008 AddOBS/SendOBSState; left out: 0x1bf opens the spectator view), battle logs (SKID_CBATTLELOG_TB...).
  - Script test (scratchpad cb_test.py, stub sessions / DB): 0x35d 0x12 + 13 x 0x134 with US (40/60/70 levels) and EU
    (V3 / V6, Semi 3 closed) limits; EU V5 refused on Semi 1; the solo flow: test owner -> 0x370 -> queue -> round 1
    (0x26e, 0x1be, 0x1e7 type 1) -> finish -> 0x1ec -> back to the crew room -> round 2 -> owner Widiastari -> end
    (0x1d6, successive 1); tax 3 % of 1000; frame sizes 0x386 0x76, 0x316 1787, 0x390 0xa + n x 0x6a.
- **EU driving physics toggle**: the client reads GlobalContent NEWVEHICLESTAT whenever it loads a car (0x484840
  LevelModifier.dat vs oldLevelModifier.dat, 0x47d7d0 0x641 / 0x3e9 rows, caps 2500 / 1200 / 1600 vs 999), so only the
  client pack can switch it. emulator.ini [nation] eu.new_physics (nation.RULES new_physics) + `tools/eu_client.py
  physics [new|old]` (part of setup): the four EU columns; with new also EU_eng 21769-21772 (the stat window labels,
  Korean in the EU column) in English. **Not applied** (still old, the EU design) until the user switches it.
- **G Coin GM command**: chat `gmcoin [name or account] amount`, `tools.gmctl coin NAME-or-ACCOUNT amount`
  (admin.add_coin: SKID_UNALISCOIN_TB of the account, never below 0; online characters get 0x579). Tested on the live
  DB with 0 (no change).

## Session 21 (2026-10-18): server-side assist effects

User: "Implement the server-side option part assist effects". New `dcemu/native/game/assists.py` (docstring = the
whole finding). The client's assist kinds (UTF-16 list at 0x93da44, 0x74 bytes each; 1 stop .. 22 driftbooster)
and what it does with each: 0x70f970 applies the driving ones to the car (stop, qstart, criticalcrash, untouchable,
crashsaving, overturbo, bonusreal, bonusdamage, driftbooster, battle / field kinds), 0x720650 the stat ones and
partycrashup 8 / partyspeedup 16; saving 4, gage 5, chance 13, exp 17 it ignores. The 2008 server did those
(ZoneServer.pdb, Ghidra zone session: XiRealMatchStat::CalcAssist 0x59f0e0 / EnChantUpdate 0x59fe00, over assist A
/ B of each item on the car and an option's own SetAssist; XiCsCharInfo::GetMitronCapacity 0x5c2060 / Efficiency
0x5c2030; BS_Party::EnChantUpdate 0x5d9860 + PacketSend::Send_PartyEnChantUpdate = 0x2f9, XiStrEnChantBonus Speed,
Crash, Accel, Boost, AddSpeed, Drop, Exp, MitronCapacity, MitronEfficiency; 2011: 40 bytes). Now, for the car being
driven (items on it: converts, option assists; drift items on it and PassiveAssist ones: their slots):
- chance -> licenses.drop_bonus (+ % on parts drop groups: combo / traffic / chase), exp -> items.play_bonus (+ %);
- gage -> Car.max_mitron() (capacity x (100 + gage) / 100), saving -> Car.mileage() (efficiency x (100 + saving) /
  100; efficiency is distance per Mitron, VehicleUpgrade V1 4.0 .. V9 0.2): sent in XiStrCarInfo / 0x425 / 0x2d4
  and kept to for fuel bought, Mitron items and 0x2d1 drive info (Player.apply_paints sets them);
- party: 0x2f9 to each member with the *other* members' partyspeedup (field 0) / partycrashup (field 1), at every
  stat_frames and when a member joins or leaves (social.join / leave_party). *Guess:* 2008 sent one total with the
  player in it; the 2011 client already counts its own (0x728700 -> 0x720650), so it is left out; the 2011 field
  order of 0x2f9 beyond the first two is not checked.
- stat_frames(p) now also sends a 0x425 when the car's capacity / mileage changed (Player.session, set at login).
Note: option parts are still off ([items] option_parts = 0); the same effects work now for converts and drift items
(e.g. Exclusive Shadow Decal+ row 20008, Bonus Assist a_00244 chance 20 %, now +20 % parts drops while on the car).
Script-tested (stub players: Lucky A + Shadow Decal+ -> +23 % drops, Experient A 1000 -> 1010 exp, Extron A 96 ->
97.92 Mitron, Duty A 4.0 -> 4.04 mileage, 0x425 with them; party: A gets B's (1, 5), B gets A's (1, 0)). **Not yet
confirmed in game.**

## Session 20 hand-off (2026-10-18 ~18:40)

**In short:** DriftBooster bought from the drift shop acts at once; converts match the 2011 client's table;
`gmitem` gives enhanced / converted parts and docking items, and the 2008 GM commands answer with real text; option
parts fixed (type numbers, stats, own assists; still off); EU assist texts in km/h (client pack rewritten); EU
physics difference found (NEWVEHICLESTAT); Undercity start phase for tests, new Undercity rewards (set part by class
+ 1-3 Mittron Enhancers), **confirmed in game**. State and the open list: `docs/HANDOVER.md` §5 (item 0).

**Rules / choices the user made this session:** EU assist texts in km/h (client change approved); Undercity rewards
= a random part of the city's Alpha / Beta set + Mittron Enhancers. Our choices, to confirm: Beta from class A,
enhancers 1 / 1 / 2 / 3 / 3 for D-S (`emulator.ini [undercity]`), "rank" read as the class.

**Reading the running client:** with `ptrace_scope` 0 (the user set it) `/proc/<pid>/mem` of DriftCityUS.exe can be
read; App = [0x948844], UI = [App+0x158], the Undercity manager App+0x164 (see the UC icons entry below). The watcher
script (`ucwatch.py`) lives in the session scratchpad only.

## Session 20 (2026-10-18): DriftBooster bought from the shop, converts checked, gmitem parts, GM replies

- **PassiveAssist(DriftBooster) did nothing when bought** (user: "not working when bought from the drift shop";
  log 20261018-163134 16:34:37: bought for 90 days, on car 1). Cause: vshop.grant put it on the car, but the 0x4b2
  that adds it was built before Player.apply_paints set VisualItem.on_current_car, so records.assist_slots sent no
  assist (the frame's 48-byte tail was all 0) and nothing sent it again until the next login. grant now calls
  apply_paints first (buying and taking a gift). Script-tested (stub: assist slot 0 = 146, a_00118). **Not yet
  confirmed in game.**
- **Converts against the 2011 client** (user: check that the part converts match the client's): the server reads
  `server_data/tables/PartModify_Client.tdf`, which is byte-identical to Client US Data_US/World/Data's (Client EU's
  copy differs in one trailer byte; all 34 rows are the same). The client loads it in XiItemTable::LoadFile
  (0x725cc7, 0x725d42 loop): per row 3 pairs of assist ids, stored as 0x7c-byte rows at item table +0x4c (+0 a
  number from 34 down to 1, pairs @4 / @0x2c / @0x54), so the client also has the A / B / C pairs. The columns'
  assist kinds match convert.py: A (cols 0-1) speed (bonusspeed / speedup), B (2-3) bonusaccel, C (4-5) overturbo
  + bonuscrash; row 34 is the best (A Speed Up 6 x 2; B +40 / +30 accel; C 1.2 s booster + 150 durability).
  Assist indices come from the same Assist_Client.tdf (identical to the client's). The 0x1ab handler (0x515420)
  shows only the two assist names. Not found: where the client reads the +0x4c rows back (no tier list shown in
  the convert tab was found); the odds remain the 2008 server's (the client has none).
- **gmitem gives enhanced and converted parts** (user): `gmitem [name] item [count] [+level] [A|B|C [tier]]`,
  level up to +20 (ItemUpgradeClient.tdf's 20 steps; players still enhance to MAX_LEVEL 15), tier 1-34 (no tier =
  34); also `gmctl item NAME ...` (misc.gm_part_args / gm_part). Script-tested (stub: +20 Enigma record @0x40 = 20,
  @0x44 = 58 bonus, slots 196 / 196).
- **GM command replies** (user: the 2008 commands only echoed "cmd(args)=[1]"): gmitem / gmlevel / gmexp / gmmoney
  now answer with a line saying what was done or why not (no such item, with close ids / names; not online;
  usage; not enough Mito; unknown command with the list). Script-tested with stubs; **not yet seen in game.**
- **gmitem for docking items** (user: give the best docking parts): `gmitem [name] dock_X_Hnnn [count] [+purple]
  [white]` (purple 0-25 = the docking_b assist, white = BOX, as docking.combine stores them; a lone number after
  the id is the count). Script-tested (stub: record @0x10 = 117, @0x44 = 35). Given to Xerender: 2 x
  dock_S / A / B / C_H012 (Hyper letter L, the best a seed can make here; the client also has M-O, H013-H015)
  with purple 25 and white 35 (the white_hyper top for 3 x base-45 H parts).
- **Option parts checked** (user: "check if the emulator has all of the game's option parts working in general",
  not to switch them on; `emulator.ini [items] option_parts` stays 0). 316 options: op_S 93, op_C 84, op_A 54,
  op_B 67, op_F 18; points in ItemClient column 9 (Speed Plus A 3) and/or an assist in column 20 (Engine Speeder A
  a_00031 Speed Up 1, Lucky A a_00026 Chance 1, ...). Fixed (script-tested with stubs, **not yet in game**):
  - type numbers: the client's ItemTypeStrToVar (0x7012d0) is speed 1, crash 2, accel 3, boost 4, op_S 6, op_C 7,
    op_A 8, op_B 9, op_F 10, dock_S/C/A/B/D 11-15. data.PART_TYPES had op_S 4 (in the emulator's part range 0-3 +
    4, outside items.OPTION_TYPES 6-10): a speed option would have gone on as a part. Now op_S..op_F = 6..10;
    unknown kinds 12 (was 10, an option type).
  - stats: the client's stat sum (0x722320) counts types 6 / 7 / 8 / 9 as speed / crash / accel / boost with the
    item value (0x72c9c0: table value + record @0x44 + random); Player.stats counted parts only. Now options on
    the car add column 9 + random and their stat assists (data.OPTION_STAT, Tables.option_value).
  - assists: the client takes an equipped item's assists only from the record's ten slots (0x72c8a0 builds them,
    0x729330 / 0x722320 apply them), never from column 20; the record had none. convert.option_assist sends the
    option's own assist in slot 0 until it is converted (2008: ItemServer.tdf column 21, the same ids).
  - Then not done, since session 21 done (assists.py): chance, exp, saving, gage, partyspeedup / partycrashup;
    bonusdamage / criticalcrash turned out to be client-side (0x70f970), like speedup, overturbo, qstart, stop,
    crashsaving, bonusreal.
    Equip rules (a part in the slot, ItemGrade::CheckGrade, one option per slot), unequip with the part, and the
    Change Solution N / S / H converts were already there.
- **EU speed converts** (user: are they in km/h?): the EU client reads Data_EU_eng/World.agt first, whose
  Assist_Client.tdf is byte-identical to the US one (the Korean table in Client EU Patch.010 is only the fallback;
  it has 3 more rows, a_00264-266 booster charge, from row 72 on, which would have shifted every assist index:
  not used). The values are km/h in both (column 6 unit "km/h": Speed Up 6 = 6 km/h); the English texts say mph
  ("Increase speed by 3.6 mph"): 454 rows (speedup 29, partyspeedup 5, booster_max_speed 11, BA_BM / BA_MS /
  BA_NS / CH_BM 409). User: rewrite them. New `eu_client.py assists` (part of setup): Data_EU_<lang>/World.agt's
  Assist_Client.tdf column 4 with the row's own value in km/h ("Increase speed by 6 km/h", "Max Battle Speed +0.1
  km/h"; 451 rows; a_11111-11113 "Test Option Speed Up", value 0, left), header bytes 20-31 kept, the original is
  client_backup/World_Data_EU_eng.agt.orig (from `grades`). Applied to Client EU; a second run changes nothing.
  **Restart the EU client; not yet seen in game.**
- **Undercity start phase** (user: a testing option to choose the phase to start at): `gmuctest on N` (or
  `gmuctest phase N`, emulator.ini [undercity] test_phase = N), N = 1 Mission 1 .. 4 BossHUV. The client drives
  its stages (0x7677b0) and moves on when the server reports a mission done, so: 2 answers 0xbb8 with 0xbb9 and
  0xbbe result 1 at once (0x517bc0 -> 0x7651a0 -> state 7); 3 also answers stage (1, 7) with 0xbc8 result 1
  instead of 0xfb 7 (which starts Mission 2, client state 8; 0x5181f0 -> 0x766c90 -> state 0xb -> HuvReq); 4 also
  cuts the HuvReq list to its BossHUVs, out at once. Skipped missions give nothing. Script-tested (stub session:
  phase 4 -> 0xbb9 + 0xbbe, 0xbc3, 0xbc8 for stage 7, HUV list stage 5 only, boss out on the first tick; phase 1
  unchanged). **Not yet tried in game.**
- **Drift booster physics in EU** (user): the exes differ in 27 bytes only, all our own patches (eu_client.py:
  0x4e4106 the nation, 0x4e1211 the US exe's protection class, 0x570013 the F2 panel table), so the code is the
  same (it still branches on the nation in ~460 places, 0x4e9360; none traced to the booster); vehicles_eueng.agt = vehicles_us.agt, a_00118 the same in both tables. The
  difference is GlobalContent **NEWVEHICLESTAT** (Value_US 1, Value_EU_eng 0): the client then loads
  Vehicle/oldLevelModifier.dat instead of Vehicle/LevelModifier.dat (0x484840), reads 0x3e9 instead of 0x641
  rows per stat curve (0x47d7d0, the dynamic data file layout 0x483eb0) and caps at 999 instead of 2500 / 1200
  / 1600 (0x48xxxx init): the EU client turns stats into speed / acceleration / boost with the old curves. EU
  design: not changed. Whether the drift booster's own strength reads these curves: not traced.
- **The Undercity works** (user, 2026-10-18: "Undecity works correctly"; played alone with the test mode).
- **Undercity rewards** (user: "the undercity rewards should be alpha or beta ready part instead of ore (random part
  out of 4 from the set) depending on the performance grade and 3 mittron enhancers"): a cleared run now gives each
  member one random part (_001-_004: B / C / S / A) of the set the city's ore makes (UseItemClient text "Combine 3 of
  these ores to get <name>'s Set Parts": Moon Palace Kayla si_s01 / Yuki si_s02, Koinonia Hyeyoung si_a01 / Erina
  si_a02, Cras Duffy si_c01 / Mr. H si_c02, Oros Yahn si_b01 / Branton si_b02), Beta (H) from class
  [undercity] beta_class = 4 (A; S too), else Alpha (S) (*the threshold is our choice*), and enhancers = 3 x
  enhancer = i_n_00003 Mittron Enhancer (*which enhancer: our choice*), instead of the ore and RANK_ITEMS' one
  enhancer. Result window: the part @0x4e+4, the enhancer @0x4e+8. Failed runs unchanged (an Alpha ore by level
  chance). Script-tested (stub: 5 runs, cities 1-4, classes 1-5). **Confirmed in game** (user, 2026-10-18 18:27, a
  phase-4 run: Kayla's Alpha C + 3 Mittron Enhancers, icons shown: "All good now, it works properly").
  Then (user: "make the mittron enhancers being from 1-3 depending on rank"): 1-3 by the class, [undercity]
  enhancers = 1, 1, 2, 3, 3 for D, C, B, A, S (*read "rank" as the class, as the Alpha / Beta rule; a solo run is
  always place 1*). Script-tested; **not yet confirmed in game.**
- **UC result window icons** (user: "the UC result menu didn't properly show the icons of the items recieved"; log
  20261018-171425 18:12:49, a solo run started at phase 4: items sent (-1, 969 gi ore, -1)). Open; checked so far:
  0x100 (0x531870 -> 0x7688d0) keeps only the packet pointer (manager +0x90) and draws 6 s later (state 0xe -> 0xf
  -> 0x764b50); the three i32 @unit+0x4e go through 0x7172f0 (the same TableIdx lookup as 0x2e5 / 0x5ad, whose
  icons work) to 0x6b1f30 (window +0x384 + row x 0xc), drawn by 0x6b1980 -> 0x5c2ed0 (a table row); 0x6b1ee0's two
  bytes @0x5a / @0x5b only show two per-row pictures (window +0x17c / +0x18c). The frames after the 0x100 were
  8-12 bytes (they cannot reach the items @0x60 of the reused buffer). The decomp's port of 0x531870 matches.
  Read from the running client (ptrace_scope 0 set by the user; /proc/<pid>/mem: App [0x948844], manager App+0x164
  (state +0xc, packet +0x90), window [App+0x158]+0x384, item slots window +0x384 + row x 0xc, rows: type @0, ASCII
  name @0xe4, TableIdx @0x2fc): with the new rewards row 0 held Kayla's Alpha C (101) and the Mittron Enhancer
  (1001), and the user saw the icons. The earlier run's only item was a Mittron Ore (969), found as well (the
  window still held it at the next run's state 0xe): its icon did not show, so the ores' icon is what is missing
  *(not checked further: the ores are no longer a reward)*. Solved by the reward change; script
  ucwatch.py (session scratchpad) does the reading.
- For the Undercity tests: Xerender gets 2 x each of Enigma / Goldwing / Mittren / Plasma (i_?_000015) at +20 with
  convert row 34 (speed A, accel B, crash and boost C), given with gmctl item after the restart.

## Session 19 hand-off (2026-10-18 ~13:30)

**In short:** (1) the decompilation (`../DriftCityEU-decomp`, private, the user's) now has every S>C handler; running
the client's *original* handlers on every frame in our logs found four wrong message layouts, all fixed (session 19).
(2) The Undercity, ported from the 2008 server (whose PDB has the whole mode) with a one-player test mode (session 19b).
Neither is confirmed in game. State and the open list: `docs/HANDOVER.md` §5 (item 0 = play the Undercity).

**How to test the Undercity alone:** a Moon Palace channel, GM chat `gmuctest on`, then chat `/ucm` (the client's own
command, open to every account; Tatiana's dialog refuses a party of one in the client). If it breaks: the newest
`logs/*.msgs.txt` (`grep -n "undercity" `) and the client's `DriftCityUS_Log/PacketAnalyzeLog*.txt`.

**Where things are for the next Undercity work:** the 2008 server functions are listed in the 19b entry; decompile them
with the decomp's read-only zone Ghidra session (`tools/gq-zone.sh &`, then `GQ_PORT=18492 tools/gq decomp
BS_Party::OnTick`; `tools/gq quit` stops it, ~3 GB of memory). The client side is in the decomp's `raw/src/seg_0076.c`
(the manager, 0x764xxx-0x769xxx) and `src/re/msg_auto*.c` (the handlers).

## Session 19b (2026-10-18): the Undercity, with a test mode for one player

User: "Now start implementing Undercity gamemode" (the JP wiki page ゲームモード/アンダーシティ), "Make a test mode that
will make the mode doable by 1 person". Nothing of it was in the emulator (no 0xfa / 0xfc / 0xbe ever logged).
- **Source of the rules: the 2008 server.** ZoneServer.pdb has the whole mode (PacketParser::Cmd_UnderCity* /
  Cmd_UCPatrol* / Cmd_UCBossPatrol* / Cmd_Huv*, BS_Party::OnTick 0x5dded0, UnderChaseEnd 0x5dd3f0,
  Pre/PostUnderCityResult, the reward tables s_UCItemTable / s_UCNewItemTable at 0x6fef28 / 0x6ff068), decompiled with the
  decomp's Ghidra zone session (`GQ_PORT=18492 tools/gq`). The 2011 client speaks the same protocol: every message has
  the 2008 size (checked against the decomp's senders and handlers) except 0x100 UnderCityResult (2011: 0x5c-byte units
  with two new bytes @0x5a / @0x5b, client 0x764b50) and 0xbcc (2011 handler 0x518310: flag @2 = text 11114 "Undercity
  120% item has been applied.", exp @6, Mito @0xa). The 2008 numbers match the wiki: fees 600 / 1200 / 2100 (4200
  Oros), Mission 2 times 2:20 / 2:30 / 2:40 and barrier HUBs 5 / 4 / 3 for 2 players up to 15 / 12 / 9 for 4, 4 HUV
  waves + the boss, the class shown at most A (client 0x6b1e20 clamps 1-4, so S shows as A, as the wiki says), the S
  pattern near 2150 s (one of the six marks). All layouts and rules: `dcemu/native/game/undercity.py` docstring.
- **The client's side** (EU exe): the Undercity manager at [App + 0x164] (0x764xxx-0x769xxx) drives the stages itself
  (0x7677b0) and sends 0xfa with them; after 0xff UnderCityLoad it loads scene 0x13 with area 100 + city - 1
  (0x765950). The HUBs are client objects (the server counts places 0-99); the HUV waves come from the client's own list
  (0xbe HuvReq, 0x767530); each member's client drives the HUVs given to it in 0xbf (0x512630 spawns them).
- **Entering:** Tatiana's dialog refuses a party of fewer than 2 in the client (0x6b4xxx, UC_Err_PlayTogether). The
  client's chat command `/uc` + city letter (`/ucm` Moon Palace, `/uck` Koinonia, `/ucc` Cras, `/uco` Oros; parser
  0x5e43e0) sends the same 0xfc without that check, and it is on the client's list of commands every account may use.
- **Test mode** (`emulator.ini [undercity] test = 1`, or the GM chat command `gmuctest on`): `/ucm` alone enters (free,
  as the 2008 solo party), and Mission 2 has a 2-player party's barrier HUBs. Without the test mode a lone 0xfc gets
  UC_Err_PlayTogether (the wiki's rule; the 2008 server let a party of one in).
- Emulator changes: `game/undercity.py` (new); `area.py` takes areas 100-103 (UC_AREAS), one instance per party
  (`uc_area_key`), no city traffic there (area_city(100) would have started Taipei's); `commands.py` knows the
  Undercity C>S sizes (the client buffers them, several per frame) and HuvReq's length; no city instant offers while
  in the Undercity; `[undercity]` in emulator.ini; GM `gmuctest`.
- Guesses / not done: the Undercity 120% item (i_n_00064) adds 20 % to Undercity exp / Mito and one is used up at the
  result (when the real server used it up is not known); the two new result bytes are sent 0; a member leaving
  mid-run just loses his HUVs (2008 handed them to another member); Undercity Direct (Korea only) not done.
- Script-tested (stub session and DB, `uc_test.py` in the session scratchpad): a whole solo run in the test mode:
  0xfc -> party + 0xff, stages 1 / 4, Mission 1 (100 HUBs, 10 red: 200 exp, 250 Mito), Mission 2 with one timeout
  (0xbc9, try 2: 4 HUBs, 150 s) and the main HUB, five HUV releases, the middle reward, the boss, 0xc1 and a 386-byte
  0x100. Every frame of that run was walked through the original client handlers (decomp harness): all consumed
  exactly. **Not yet confirmed in game** (nothing of the Undercity has been played).

## Session 19 (2026-10-18): message sizes checked against the decompilation

User: "Check the decompilation project and see if there are any parts of the emulator that can be improved". The
decomp (`../DriftCityEU-decomp`, private) now has every S>C handler and 402 of the 423 C>S senders ported and checked
against the original. Its unicorn harness (`tools/autotest.py` World) can run any **original** handler on a packet,
so every distinct S>C frame in all 317 `logs/*.msgs.txt` (3 samples per type and length) was walked the way the client's
PacketAnalyze (0x813870) does: each handler returns the bytes it consumed, and the next message starts there. For the
handlers the harness cannot finish (C++ / large UI paths), the return expressions of the ports were used. Result: 1807
frames correct; the rest below. The client agrees: `Client US/DriftCityUS_Log/PacketAnalyzeLogC022/C024.txt` (today
08:37 / 08:48) hold "Wrong Command: 0" exactly when the emulator sent an empty 0x3f6. Note: the client compares a
handler's size with the whole frame length, so a lone message 2 bytes short goes unnoticed (it reads 2 bytes past).
- **0x3f6 GetCouponStampListAck**, empty list: the handler takes `(n - 1) x 12 + 0x12` as a u16 = 6 bytes for n = 0;
  the 12 padding bytes ("the client reads one entry even for n = 0", wrong) were read as type 0. Fixed (coupons.py).
- **0xf3 PartyJoinResult**: `(n - 1) x 0x3e + 0x88` = exactly n units; the empty unit after them was read as type 0
  (the old note had read the formula as 0x88 + n x 0x3e). Fixed (social.party_state).
- **0x331 NewLicenseNoti**: the handler (0x50e7e0) takes 8 bytes; we sent 6. Now u16 id, u16 1, u16 0 (licenses.py).
- **0x29a another player's licenses**: the conditions went out as 0x32a, but 0x32a's handler (0x511620) is ETCInfo,
  a fixed 0x8a bytes (it keeps u32 @6, here the serial, at net +0x3e828); the handler named in the docstring, 0x511510,
  is **0x29c LCondStatusAck**, whose layout is exactly what we built ((n + 3) x 6 bytes). Now sent as 0x29c. The
  license window of another player never had its conditions before.
- Virtual HUV guesses settled (see session 18 below): 0x124 @0xa, 0x127 @2, 0x128 @2, 0x122 @6 are never read;
  0x124 @0x16 == 1 is the attacker's catch effect. The 0x128 handler also counts the daily-mission events 0x1a-0x1f
  on the client by itself (nothing for the server).
- The area walker's command sizes (area.SIZES) match the decomp's senders for every type that has one.
- Checked and fine: 0x17 server list (state 1 falls through to the load texts 10762..; 100 / 200 / 300 are the
  states with their own texts 10759 / 10758 / 10760), 0x1a2 (fixed in session 15), 0x1a7 / 0xe1b (shared handler
  0x50f060, 10 bytes).
- Lead, not done: **C>S 0x1b5** (5 x u32; sender 0x7f0c90, no Dev Ed name) is sent in pairs after a 0x89 NotifyEvent
  and has no handler here ("no handler for 0x01b5"). Its callers (e.g. 0x728xxx) swap two items' slots: u32 item A
  InvenIdx, u32 A's slot (100+ / 0x6a+), u32 item B InvenIdx, u32 B's slot, u32 kind.
- The two checking scripts are in the session scratchpad (they need the private decomp, so they are not in this repo).
Frames script-tested through the original handlers (harness): 0x3f6 n = 0 / 2, 0xf3 n = 1 / 3, 0x331, 0x29c n = 0 /
40 all consumed exactly. **Not yet confirmed in game** (party join, license gained, another player's license window,
login without coupon stamps: the client's PacketAnalyzeLog should stay empty).

## Session 18 hand-off (2026-10-18 ~09:10)

**In short:** drift shop items (Manufacturing Enhancer, Fuel Booster checked, DriftBooster sold, harvest rows hidden:
emulator.ini [vshop] + tools/shop_rows.py), lucky bag prize icons, **Virtual HUV** (game/vchase.py from the JP wiki and
the 2011 client's ChasingBattle messages, with a 2-player test mode; user-confirmed with two clients), the Tatiana Call
Unit in the parts shop, the US exe without the dname.chk check, the launcher's second-client fix. At the end: VHUV test
mode off, Mita 500 bottles off. State and the open list: `docs/HANDOVER.md` §5.

**Rules the user set this session:** test modes with two players, not solo ("solo is impossible" for VHUV); disabling
the dname.chk check is fine; one HUV model per city is fine.

## Session 18 (2026-10-18): drift shop items, shop rows from emulator.ini, Virtual HUV

Client addresses in this entry are of the EU exe (../DriftCityEU-decomp, the same 2011-10-27 build).
- **Mittron Fuel Booster** (drift item i_d_half, category 24 HalfMitronCharge; user: implement it): already done
  (session.fuel_charge: price x 0.5 and sale flag 1 while held, 0x5dd bit 7). Checked the client side: the 0x2d4
  handler (0x520290 -> 0x5759d0) puts the answer's unit price @0x1c and sale price @0x20 into the fuel window (+0x40 /
  +0x44), and the window works out fuel = pay / sale price (0x575450), so the window shows the half price. No change;
  **not yet confirmed in game.**
- **Manufacturing Enhancer** (drift shop 20427 / 20428 = 50 / 10 x inventory item i_n_createup, UseItemClient kind
  user_create_source (client kind 0x48), value 20; text "When you have this in your inventory, the ratio of
  manufacturing will increase"): it did nothing. The client sends only the skill book id in 0x0e78
  (Send_AlchemyCreate 0x8060a0, char[56]); a right-click on kind 0x48 only opens the manufacturing window
  (0x61d190). alchemy.manufacture now adds the held enhancer's value to the chance (SuccessChance + license
  ME_DoubleUserCreate + 20) and uses one up per try (alchemy.enhancer; Space Warp Engine, the same kind with no
  value, is not one). Script-tested (stub: 45 % recipe -> 65 %, 50 -> 49 enhancers). **Not yet confirmed in game.**
- **Harvest event items hidden from the drift shop** (user: "for now"): the client lists a VShopItem row only when
  SellStage (% 1000, < 1 -> 100; row reader 0x846e10, field +0xf0) <= Etc.VShopOpenStage (1) and
  Etc.VShopCloseStage < CloseStage (0x5c7196 and two more), so a content flag cannot pick out single rows (309 rows
  have SellStage 1). New emulator.ini [vshop]: `hidden` = 20204-20210 (Delivery Box Recipe, Normal / Ice Box, Fresh
  Vegetable / Fish / Fruit / Meat); the server refuses to sell or gift them (vshop.buy_visual_item, gifts); new
  tools/shop_rows.py apply writes SellStage 99 into Client US Data_US/Init_us.agt and Client EU
  Data_EU_eng/Init_eueng.agt (only VShopItem.xlt changed, header bytes 20-31 kept, originals in
  client_backup/Init_us.agt.orig / Init_eueng_ClientEU.agt.orig; `reset` puts them back). Applied. **Restart the
  clients; not yet confirmed in game.**
- **PassiveAssist(DriftBooster) sold** (user: buyable in the drift shop; picked passive_a_00118 "Post-Drift Booster",
  row 10820, and G Coin like the Fuel Booster): the row had SellStage 99 and no price. [vshop] `sell.10820` sets
  SellStage 1, UseHancoin 1, 100 / 250 / 500 G Coin for 7 / 30 / 90 days; the server applies the sell.<id> lines to
  its own rows at start (__main__, vshop.row_changes), shop_rows.py writes them into both clients. It goes on the car
  as before (driftuse.EQUIP_PASSIVE). Script-tested (30 days for 250 G Coin, 0x4b4). **Not yet confirmed in game.**
- **Mittron Big 4 Shopping Bag** (i_n_package_mitronbig4, luckybag; user: check and fix): the user's purchase and
  opening (log 20261017-222331 07:38-07:41) worked on the server: rw_summerpackage_mitronbig4 rolled one row of each
  of its four slots (10 Enhancer DELUXE, 99 Enhancement Formula, 3 Gold-Bar Boxes, PRIME V4 box), 0x5b5 with 4
  cells of 10 bytes (the client's 0x61a270 reads them so), and the PRIME box gave the car. The client gives this
  bag its own window layout (0x61a3f0, by the name prefix). The shop's own name for it is "mitron big4 Lucky Bag"
  (VShopItem MarketName).
  - User: the window showed no icons except the Enhancement Formula's. Cause: for an inventory prize (kind 1) the
    window (0x61a270) does not use the item table; it searches the player's inventory list for an item of that
    TableIdx (0x717d40: [+0x60] list, entry +0x2fc, state 0/2/3/5/6). The server sent 0x5b5 before the 0x192 that
    adds the prizes, so only the Formula (a stack already held) was found. driftuse.use_lucky_bag now sends the
    0x192 first. Every lucky bag had this. Scratch cards (0x5ad) look prizes up by table (0x7172f0): not affected.
    Script-tested (order 0x192, 0x5b5). **Not yet confirmed in game.**
- Emulator restarted 07:49 (log 20261018-074949), again after the lucky bag fix.
- **Virtual HUV (Virtual Chasing)** (user: implement it from the JP wiki page ゲームモード/バーチャルチェイシング, and sell its
  call unit in the parts shop; then "a testing mode with 2 players only, instead of solo"): new game/vchase.py, its
  docstring has every message. Not in the 2008 server; the 2011 client still has it all: handlers 0x119 / 0x11b /
  0x11c / 0x11f / 0x122 / 0x124 / 0x127-0x129 / 0x12b (0x512fe0 ... 0x5262b0), senders 0x118 / 0x11a / 0x11d / 0x11e /
  0x120 / 0x123 / 0x12a (0x7e6100 ...); Dev Ed names ChasingBattle*. Found:
  - The Tatiana Call Unit (i_n_00062, kind vc_T_callunit = 0x1e; not used up) sends 0x118 in a city other than Mitro
    City (0x601cf0); 4:4 / 8:8 from Tatiana's dialog; a party's members get 0x11c and answer 0x11d.
  - Start records (0x84 bytes at [net+0x3d584]): +0x20 max HP, +0x28 damage (gauge = (max - damage) / max, red under
    30 %: 0x5ab770), +0x24 HP shown, +0x18 the HUV id for the model (0x73be70 -> 0x5e2130; per city O-Raid 10005,
    V-Boxer 10011, B-Terror 10013, R-Trouble 10019). The per-city machine points of the wiki are in the client
    (chaser 0x741350, HUV 0x73be70). The client counts down 7.5 s, runs the clock and warnings, lets only a non-HUV
    hit an opposing HUV (0x488xxx -> 0x486690, damage roll 0x485440), sends 0x12a for the HUV's traffic hits (once
    a car) and 0x120 every 10 s while the team's next HUV is >= 1500 m away (0x7469b1). Role timers 3 -> 1 (1.5 s)
    and 4 -> 0 (3 s) are the client's. Content flag Main.VirtualChasing: never tested by the client.
  - Server rules (wiki; emulator.ini [vchase]): 3 hits catch (33 %), 1-3 points a hit (3 critical), +20 a catch,
    HUV HP -5 % every 10 s and per 0x120, traffic hit +3 points / +5 % HP, 300 / 600 s, more points win (draw:
    both lose); a player leaving stops the match (result -1, VC_Cancel_Msg). Rewards: exp / Mito = HuvTable exp /
    Mito at the player's level x win_rate 30 / lose_rate 10 (x 2 in 8:8; the wiki gives no amounts, ours);
    winners: Undercity 120% x1, N / S Mittron Enhancers by city (10 / 30 / 1 / 3), Team ROO 10 HUV Call Units.
  - Guesses: 0x124 @0xa (sent: the target's team) and @0x16 (sent: 1 when caught), 0x127 @2 (the team), 0x122 @6 and
    the entry's +0x14 / +0x1c / +0x20 (0), 0x128 @2 (0), which team score field is which (team 0 first).
    *Settled from the decomp (session 19):* 0x124 @0xa, 0x127 @2, 0x128 @2 and 0x122 @6 are never read by the
    client; 0x124 @0x16 == 1 is the attacker's catch effect (0x6b4fc0), so "1 when caught" is right. Still open:
    0x122 entry +0x14 (kept at the chaser's +0x1c, like 0x127 @0x1a) and +0x1c / +0x20 (chaser +0x40 / +0x44),
    and which score setter (0x56b650 @0x1a / 0x56b680 @0x1e) is which team on screen.
  - **Test mode, two players** ([vchase] test = 1, or GM chat `gmvchasetest on` by one of them): a match starts with
    two waiting in the same city and channel, one a team, one HUV at a time (with one HUV per team both would be
    HUVs and nobody could ram); when it is out the other player becomes the HUV of his team.
  - Script-tested with two stub players (test mode): registration, 0x122 (190 bytes for 2), traffic heal, three
    hits -> caught (+20) -> 0x127 to the other team, HP drain, 0x128 for both (winner's items), cancel, a stopped
    match. **User-confirmed 2026-10-18** in the 2-player test (two US clients): see the entries below.
- **Tatiana Call Unit in the parts shop** (user): UseItemClient column 13 (shop) True for i_n_00062 (1000 Mito)
  through tools/item_names.py (new CELLS table; written into Client US Patch.004, Client EU World.agt, header bytes
  kept, and server_data/tables/UseItemClient.tdf; the HUV Call Unit i_n_00063 was already sold). Restart the clients.
- Emulator restarted again after these (08:3x).
- **"Invalid Files Detected." at the US client's start** (user, after the shop rows): the US exe's data file check
  0x4ed620 compares Data_US with Client\dname.chk; tools/shop_rows.py had rewritten Data_US/Init_us.agt (the EU
  client skips the check since its setup; packs in Patch/ are not listed). User: "Can we just disable dname.chk
  checking?" -> `eu_client.py us` now also skips it (55 8b ec -> 31 c0 c3 at 0x4ed620, as the EU setup does);
  Client US/DriftCityUS.exe rebuilt from client_backup/DriftCityEU.exe.orig: 4 bytes differ (the GameGuard class
  0xe0611, the check 0xeca20-22). The shop_rows.py changes to Init_us.agt stay. **Not yet confirmed in game.**
- **A second client did not start** (user: "before I was able to launch 2 clients at the same time"): the second
  launcher (through Steam: SteamAppId 2857987919, overlay) hung in its first Wine command, Proton's steam.exe running
  `reg add ... EnableWindowMode`, while the running client's session had been started outside Steam (launcher
  parent systemd, no Steam ids). Reproduced: `proton run reg query ...` returns at once without SteamAppId and hangs
  with it (25 s timeout) while that session runs. Launcher (launch_linux.go): when any Drift City client runs
  (anyClientPids: DriftCityUS / EU / DriftCity.exe), the Wine commands run without SteamAppId / SteamGameId /
  SteamOverlayGameId / STEAM_COMPAT_APP_ID (that client has no Steam overlay). Rebuilt (build.sh) into both client
  folders. **Not yet confirmed.**
- **VHUV: "wrong message window" for the 2nd player** (user, screenshot: Tatiana's VC_Enter and the waiting list
  right, plus a yellow Accept / Abandon window with Korean placeholder text "테스트...내용입니다"; fine on the next
  try): log 20261018-081805 08:32:31.324 a city instant mission offer (0x3df, mission 29) reached Newbie (#9) 90 ms
  before his 0x118; the 0x119 handler's window reset (0x5846b0) cleared the offer window's texts while it stayed
  open. Not a VHUV window. instant.city_offers now skips players registered for or in a VHUV (busy 'vchase'); an
  offer arriving just before the unit is used can still collide. Not restarted yet (the user was testing).
- **VHUV did not start with 2 players** (user: "with the test on"): log 20261018-081805: Xerander (#3) and Newbie (#9,
  US client) both registered 4:4 (0x11b 1, 0x12b "2 waiting", 08:33:41 and 08:35:11), but emulator.ini [vchase] test
  was 0 and no gmvchasetest in the log, so 8 were needed. Set test = 1; emulator restarted. Newbie's missing "status
  window": he got the same 0x11b / 0x12b as Xerander; which window is meant is asked.
- **VHUV: both clients crashed when the time ran out** (user): log 20261018-083652: the match ran (Start 08:37:47.6,
  hits, catches, HUV changes, drain), 0x128 went out at 08:42:55.2 (7.5 + 300 s), but both clients' last messages
  were at 08:42:53.5 (connections closed by timeout at 08:43:57): they died when their own clock reached 0, 1.6 s
  earlier (the client counts frame times from its countdown, 0x745b00). That clock, [net+0x154]+0x3c, is also the
  race clock: the battle race state machine (0x49d3d0) runs the race finish (0x500270, 0x44b800) when it is below 0;
  the 0x128 handler resets that state ([net+0x154]+0x14 = 0). No message sets it for a VHUV. vchase.Match now ends 1 %
  of the seconds, at least 3 s, early (END_MARGIN / END_MIN: 3 s in 4:4, 6 s in 8:8). The crash point is inferred
  (no crash dump: the launcher log was overwritten by the next start). Script-tested; emulator restarted.
  **User-confirmed 2026-10-18**: "the match now ended properly".
- **End of the session** (user): [vchase] test = 0, [mita500] enabled = 0 (Mita bottles off for now); emulator
  restarted. Committed and pushed.
- **VHUV test run 2** (log 20261018-084657, 08:49): the 2-player test match started, hits and the catch worked
  (HUV 2 -> 7). Newbie as the HUV had a full boost gauge but could not boost; the user then found that expected
  ("Oh, I see ... it's all good"): no change. The HUV model id (entry +0x18, HuvTable id 10005) went to
  GetVehicleInfo (0x4c9f30) without its "wrong id" message in the client logs.

## Session 17 hand-off (2026-10-17 ~22:30)

**In short:** solo patrol end fixed (0x3e3), party patrol finished and user-confirmed, US stat points 1 per level,
then the EU version's rules: parts by car V grade (and the EU client's tooltips / refusal text showing the grade),
drops by car V grade, battle zone without levels and with EU V tiers, KPH texts, Client EU without Data_US; content
flag Main.AutoCarAssist on (garage functions); English name for the "Useless Skill Book". Commits b3b5506, aaf6da1
(pushed). State and the open list: `docs/HANDOVER.md` §5. Everything below this point of session 17 is not yet
confirmed in game unless marked.

**Rules the user set this session:** keep the US car stats and costs (do not take the 2009 EU tables' values); the EU
part tooltip must show "Required Grade" (written into Client EU's ItemClient.tdf), with the user's own wording for
texts ("Grade %d required" - %d because the client passes a number - and "Your car grade is not high enough for this
part"); client changes for EU go to Client EU only, through the tools (eu_client.py grades / kph, global_text.py /
global_content.py --column), so `eu_client.py setup` can remake them.

## Session 17 (2026-10-17 evening): solo patrol end, party patrol, US stat points, EU rules

- **Solo patrol stuck at 40/40** (user, Xerander, Officer Heather's patrol TableIdx 5; log 20261017-163318 18:26:07):
  the server ended it (0x3ea, 0x3e5 with the final exp, mission dropped), but the client kept it on the HUD. In the
  2011 client only the 0x3e3 handler (0x513ed0 -> 0x70d7c0) frees a mission object; the 0x3e5 handler (0x514120)
  only adds the exp, lists the items and opens the result window (0x73ca10). The 2008 server sent no 0x3e3 for a
  patrol (Cmd_InstantGoalPlace 0x6065dd). instant.instant_goal_place now sends 0x3e3 after the 0x3e5 (the order
  INSTANT_ORDER keeps for other missions). The 10-14 patrol had the same flow; the user probably did not notice.
- **Patrol reward without a message box** (user): patrol_rewards.txt items now go into the inventory only (0x192);
  0x3e5's item list (each item = chat line, pick-up icon and a notice, 0x739f70 / 0x69f200) is sent empty. The
  "Instant Mission Complete" result window with the exp stays (it is the 0x3e5 itself). Every patrol row in
  patrol_rewards.txt is still `-` (no item): fill it in to give one.
- **US stat points 1 per level** (user; was level / 2 from the 2008 Contents.ini Main.HalfLevelPoint): new nation
  rule half_level_points (emulator.ini [nation] us. / eu.half_level_points = 0); player.stats no longer reads the
  Contents.ini flag. EU unchanged (level_points off).
- **Party patrol test mode on for everyone** (user): emulator.ini [partypatrol] test = 1 (a solo patrol accepted
  alone at a pillar starts that city's party patrol). Turn it back to 0 to get normal solo patrols again.
- Script-tested with a stub session (patrol to the last post: 0x3ea, 0x3e5 with 0 items, 0x3e3; the US rule gives
  30 points at level 30). **Not yet confirmed in game.**
- **Test party patrol: no posts and no timer** (user, log 20261017-183125 18:32:02, row 91): the client's HUD
  (0x652440) keeps a party patrol in state 1 (starting: no timer, posts not reported, 0x742a41) until the time left
  (start tick + limit - now) is 60 s or less (0x6524ac), then sets state 2. The test mode's first limit of 600 s
  kept it in state 1 for 9 minutes. partypatrol.start now sends the first 0xc27 with at most 60 s (RUN_AT) and a
  longer limit 1.5 s later (raise_limit; 0xc27 sets the limit at any time, 0x523560). Normal party patrols (60 s)
  are unchanged. Script-tested (frames and timing); **not yet confirmed in game.**
- **Party patrol, second test run** (user, log 20261017-183357 19:21-19:30, screenshot of the result):
  - *Yellow "1 Mittron Enhancer(s) have been issued" box over the Party Patrol Result*: 0x3e5's item list (client
    0x514120 -> 0x69f200 notice per item). partypatrol.complete now sends 0x3e5 with no items; the items go to the
    inventory (0x192) and the result window 0xc1e still shows the prize.
  - *Checkpoints before the start countdown ended*: posts are drawn only in state 2 (0x62f6ec / 0x6336b8), which
    comes at 60 s left (0x6524ac); with a 60 s first limit that was at once. The 0x3e1 handler plays a 7.5 s start
    effect (0x51fce0: effect 0x12, 7.5f), so the first limit is now start_seconds + COUNTDOWN (8): the posts and
    the timer (60 s) come when the countdown ends. The test mode's limit is raised 9.5 s after the start.
  - *One emergency post only*: the client clears its slot to -1 before it reads the post it sends (0x742b0a /
    0x742b11), so 0xc25 always carries post -1; the server compared the post, refused ("not set"), kept its slot
    and refused every later 0xc28 ("still has one", every minute). 0xc25 now goes by the slot alone; 0xc28 always
    takes the new post (the client asks only with its own slot empty).
  - Script-tested (start frames and timing, emergency post ask / replace / take -> 0xc26). **User-confirmed
    2026-10-17**: party patrols work correctly (countdown, posts, emergency posts, result window).
- After that (user): [partypatrol] test = 0 again, and the server set to EU: [nation] allow = eu (US clients get
  "Authentication system abnormal.(99)"; allow = all lets both in again).
- **EU reference tables** (user, ~/Downloads/Init.agt, two identical copies): a 7-Zip archive (not a NayaPack) of 24
  Init/*.xlt from 2009-12-28 of an older EU client. No ItemClient (the parts' Required Grade, column 8, is in
  World.agt), no part / grade rule columns in any table. EU VehicleUpgrade has 87 cars with other stats, prices and
  required levels; **not used: the user wants the US stats and costs kept**. Kept in the scratchpad only.
- **Drop chances** (user question): only the server has them: server_data/tables/ItemDropServer.tdf = the 2008
  **TW** table (Server2008/server/Data_TW). The 2008 US table has the same 83 rows, but 62 rows have other combo
  chances (TW 3-5x higher, e.g. level 1 ig_n_A 93.85 % vs 19.7 %); crash (traffic, mode 1, rolled in 0-10) chances
  are the same. DropLimit_Server.tdf (per-item caps) is not read. Nothing changed there.
- **EU drop groups by the car's V grade** (user: "EU groups item depending on the car V grade level"): nation rule
  drop_by_grade (eu 1, us 0): combo.drop_rates takes data.Tables.drop_rates_of_grade(current car's grade) for EU
  players: the table has nine levels (1, 5, 11, 21, 31, 41, 51, 61, 71), V<n> = the n-th (the mapping is ours).
  Traffic, combo and rush-hit drops; patrol drops stay by level. Script-tested (V1 / V3 / V5 / V9 rows; US level 30
  -> row 21, EU V5 -> row 41). **Not yet confirmed in game.**
- **EU part requirements by the car's V grade** (user: "the better the part, the more grade it requires; best N parts
  V3, best S V6, best H V9"; then "options and docking parts: N V1, S V4, H V7"): data.Tables.part_req_grade, used by
  nation.part_allowed (rule part_grade, EU only) when ItemClient column 8 is empty (always, in our tables). Parts
  (speed / accel / crash / boost): the grade's first V grade (N 1, S 4, H 7) + 0 0 1 1 2 over the five normal tiers
  (N 1/7/13/19/25 -> V1 V1 V2 V2 V3, S 31-55 -> V4 V4 V5 V5 V6, H 60-80 -> V7 V7 V8 V8 V9); set / shop / rental
  parts take the tier of the highest normal level not above their own (e.g. H set level 71 -> V8, level 1 rentals
  the grade's first). Options FN / FS / FH and docking parts ON / OS / OH: V1 / V4 / V7. The tier split (2-2-1) is
  ours. Refused in items.equip_item (0x199, which also carries options and docking): 0x0001 "Your car must be V<n>
  or higher to equip this item." in place of 20027 ItemEquipFail. Parts already on a car stay. The client's own
  tooltip ("Required Grade", column 8 of its copy) shows nothing. Script-tested over the whole ItemClient table and
  part_allowed (EU V5 car refused an H level-60 part, US allowed). **Not yet confirmed in game.**
- **EU battle zone: no level limits, V grades only** (user; "make sure everything works in the reworked battle
  zone UI too"). The 2011 lobby (BattleZoneReform = 1: Newbie 11, Pro 12 with the room EXP tiers, Real Match 6)
  takes its limits from GlobalContent.xlt in the 0x1b9 handler (switch 0x52a19c on the channel, table 0x52a490:
  6 -> 0x52a2c7 Real Match keys, 11 -> 0x52a31e Newbie, 12 -> 0x52a38a Pro) and for the tiers 0x5a6950 (the
  *11New keys); the EU client reads the Value_EU_eng column. Its level limits there were the US ones (Newbie max 30,
  Pro min 11, tiers 11 / 11 / 31 / 51 / 71, Real Match min 30 (US 1)); the old sections' caps were 1000 already.
  - Client EU only (user's request; the US pack unchanged): tools/global_content.py got `--column NAME` and a
    backup per client folder (client_backup/Patch.000_ClientEU.orig, the EU pack as it was, header bytes 20-31
    kept); set in Value_EU_eng: MaxBattleNEWBIELevel 1000, MinBattlePROLevel 1, MinBattle2X/4X/6X/8X/16XLevel11New 1,
    MinBattleRealMatchLevel 1. The grade limits stay (Newbie V1-5, Pro tiers V1-5 / 1-7 / 1-9 / 1-9, the same in
    both columns). Channel 7's fixed "level >= 71" (0x52a30e) is not a button in the reformed lobby: left.
    The EU client reads the pack at start: restart it.
  - Server: nation rule battle_levels (us 1, eu 0): rooms.car_allowed (create / join, the Pro tiers), the invite
    list and Lap Time (with laptime_level_limit) skip the level check for EU players; the V grade checks stay.
  - The EU column also has other V limits for the old 2X-8X sections (2X V2-4 ...), which the reformed lobby does
    not show: the server keeps the [battlezone] section lines there.
  - Script-tested: car_allowed for US / EU (Newbie level 50, Pro 4X level 5 V5 / V6, 6X level 20, 16X level 30);
    the pack rewrite read back. **Not yet confirmed in game.**
- [nation] allow = all again (user: for testing the decompilation project, both nations for now).
- **EU battle zone V tiers** (user): Newbie V1-3; Pro V4-9 with the room tiers 4X V4-5, 6X V6, 8X V7-8, 16X V9.
  Client EU Value_EU_eng: MaxBattleNEWBIEGrade 3, MinBattlePROGrade 4, Min/MaxBattle4XGrade11New 4/5, 6X 6/6,
  8X 7/8, 16X 9/9 (global_content.py; header bytes kept; the US pack unchanged). Server: rooms.section_rule takes the
  player (EU: emulator.ini eu.section.11 / .12, rooms.PRO_TIERS_EU), in car_allowed and per invitee in the invite
  list. Script-tested (every grade x section / tier, EU and US). **Not yet confirmed in game**; the EU client must
  be restarted to read the pack.
- **Client EU without Data_US** (user: move what is needed to Data_EU_eng, delete the US data): Data_EU_eng already
  held all 635 files (World.agt with the five patch tables folded in, checked equal to Patch.000 / 003 / 004 / 006;
  uitex.agt with the Km/h dial); nation 8 loads only Data_EU_eng (the exe's per-nation path tables 0x8d4f07..), so
  Client EU/Data_US (234 MB, identical to Client US/Data_US) was deleted. tools/eu_client.py setup now builds from
  ../Client US/Data_US when the folder has none (us_data). Not yet started in game after the deletion.
- **EU part tooltips show the required grade** (user: the EU client still showed levels; "Required grade is the one
  that should be showing"). The tooltip (0x657442, all nations) shows "Required Level" when ItemClient column 7
  (+0x120) is not 0, else "Required Grade" column 8 (+0x124); the user's ItemClient.tdf from an EU client
  (~/Downloads, 737 rows / 23 columns, older) also has column 8 = 0 everywhere and the same levels, so the grades are
  the emulator's rule. tools/eu_client.py **grades** (also in setup) writes it into Client EU's
  Data_EU_eng/World.agt ItemClient.tdf: column 7 = 0, column 8 = data.part_grade_rule (now a function shared with
  Tables.part_req_grade); levels for the tiers from the first original (client_backup/World_Data_EU_eng.agt.orig),
  so a second run changes nothing; checked: all 749 items equal to the server's grade. The .tdf header's u32 @4
  (520619991) is the same in every table (not a checksum); @12 = the table size. Server: **eu.part_level = 0**
  (the EU client shows no level, so only the V grade counts for EU).
- **KPH instead of MPH on the EU client** (user: "in localization ... any MPH changed to KPH"): GlobalText 11874 "mph"
  -> "kph" in the EU English column (the only speed unit there; the "mile" hits are Mileage points; the EU texts
  use km / km/h elsewhere): tools/global_text.py got `--column EU_de|EU_eng|EU_fr|EU_es` (the EU columns are all
  headed "Value", columns 11-14) and a per-folder backup (client_backup/Patch.006_ClientEU.orig). The HUD's six speed
  labels in Data_EU_eng/gameui/game.nui (T1="MPH" / "mph", controls named ..._km/h) -> KPH / kph: eu_client.py
  **kph** (also in setup; client_backup/game_Data_EU_eng.nui.orig). The Newbie tooltip picture is the same in all
  packs (not the 161MPH edit). The HUD's speed number is km/h on the EU client (user-confirmed 2026-10-17), so the KPH labels match it. The EU client was
  running during the change: the new texts and tooltips show after its restart. **Not yet confirmed in game.**
- **Grade tooltip text** (user: "Grade %s required" instead of the word ranking): GlobalText 11275 (EU English
  "Ranking %d required"; US "Required Grade: %d") -> "Grade %d required" in Client EU's Patch.006 (global_text.py
  --column EU_eng). %d, not %s: the client passes the number (push [item+0x124], 0x657469), and %s would read it
  as a text address. Not yet seen in game.
- **Grade refusal text** (user: "Your car grade is not high enough for this part", screenshot of "Your level isn't high
  enough for this class of car."): the client refuses the part itself, no 0x199 sent: with column 7 = 0 it compares
  the car's grade (0x5fa290) with +0x124 (0x5fe251 part drop, 0x60b5da the other equip path) and shows GlobalText
  11276 (column 7 > 0: the level, 0x5fe22e, text 0x8e1420). 11276 EU English -> the user's text (Client EU
  Patch.006); the server's own refusal (items.equip_item, EU part_grade) now sends the same words. Not yet seen in game.
- **Garage Function 2 showed "(º¸³Ê½º ¾î½Ã½ºÆ® ¿É¼Ç)" on the EU client** (user; the session 14 open item): the CP949
  placeholder "(보너스 어시스트 옵션)" of game.nui control 1650007 ID_GARAGE_GETON_PANEL_ASSIST2. The garage (0x79c2d0)
  fills Function 1 / 2 ([garage+0xa8] / +0xac) with the car grade's assists only with **Main.AutoCarAssist**
  ([net+0x274] & 0x180000, 2011 only -> sent 0); without it it hides only Function 1 (0x79c34c). GlobalContent
  MyGarageAdv: US 0 (Function 2 hidden at 0x79ab7c), EU 1 -> the placeholder showed. The assists are VehicleUpgrade
  "OptionID" (112 car grades, e.g. Metro V2 "BA_CS_060 CH_AD_015", Turbo Start AL_QS_001) -> Assist_Client.tdf rows.
  The flag also feeds the car tooltips (0x657b7e, 0x65bde8), 0x70f4a0, and makes 0x71ac10 skip the old fixed
  per-car assist list (its cases test nations 2 / 3). User's choice: on for **all** clients -> handlers/game.py
  NEW_FLAGS 'Main.AutoCarAssist': 1 (dword @0xc = 0x8803e8 checked). Whether the client applies the assists in races
  by itself (as part options) or needs the server is not known yet. **Not yet confirmed in game.**
- **"?? ?? ???" item in Xerander's inventory** (user screenshot): random_skb_bust "쓸모 없는 스킬북" (event_item; not in
  rw_random_skb, origin unknown): its name / description are Korean in both clients' tables (the fonts have no
  Korean). New tools/item_names.py (NAMES: "Useless Skill Book" / "A skill book too old to be of any use.") writes
  Client US Patch.004 (client_backup/Patch.004.orig), Client EU Data_EU_eng/World.agt and
  server_data/tables/UseItemClient.tdf; read back, 2 cells changed each, header bytes kept, the EU grades intact.
  75 other UseItemClient rows still have Korean names (old event items: Seoul Motor Show tickets, Pizza Hut coupons,
  Indiana Jones items, event ticket pieces). **Not yet confirmed in game** (both clients must restart).

## Session 16 (2026-10-17): Party Patrol and its solo test mode

- **Party Patrol** (user request, with the Japanese wiki page ゲームモード/パトロール for the rules): new module
  `dcemu/native/game/partypatrol.py`; its docstring has every message layout. The 2008 server had no party patrol, so
  everything comes from the 2011 client:
  - Instant_Client rows 91-123, types party_move / party_move_ROO = client mission types 0x20 / 0x21 (type names at
    0x7027xx, UTF-16). The pillar shows them only with the content flag **InstantMission.PartyPatrol** (bit 5 of
    [net+0x280], tested at 0x62f95d) and a party of 2+: the flag was missing from the 2008 Contents.ini -> NEW_FLAGS.
  - 0x3e1 to every member starts it (0x51fb40: party patrol object 0x72d4d0, slots @0, limit ms @0x10, start @0x14,
    asked @0x18, state @0x1c). Shared posts: 0x3ea to all (0x70b750 marks the place). New 2011 messages:
    0xc27 (cid, posts, time limit) S>C, 0xc28 (post) C>S = the client's emergency post every minute (0x7475b0;
    session.py had swallowed it), 0xc24 (4 slots) S>C, 0xc25 (slot, post) C>S, 0xc26 (slot, post, exp, exp info,
    level, limit) S>C, 0xc1e result window (0x514560 / 0x569ae0). End: 0x3e5 + 0x3e3 + 0xc1e; fail 0x3e6
    (time up, member leaves the party or the game); give-up 0x3e8 to all ("Party Leader has quit", 11159).
  - **0x3e6 InstantFail from the client** is now answered (0x3e6 back, the mission dropped) also for solo missions;
    it was ignored before.
  - Rewards: the client's RewardGroup rw_patrol_moon / koi / cras / oros_omd / oros_roo (Mittron Enhancers via
    rw_patrol_trans, Mysterious Gift Box i_n_00085); Etc_Value 15/30/45/60 read as the seconds left at the end
    *(guess)*. patrol_rewards.txt still applies.
  - Time rules in emulator.ini **[partypatrol]**: 60 s start (wiki), +4 s per 5 party posts, emergency post 20 s
    down to 5 s by waiting, exp 10x per post *(guesses: the wiki gives no numbers)*. No parts every 50 posts in a
    party patrol *(guess)*. All members get the starter's row (the wiki says factions run their own routes).
  - Which result-window number is which (posts / emergency posts / exp, total = exp) is a *guess*.
- **Party patrol test mode** (user: "check the party patrol by myself and be able to complete it within the time
  limits"): GM chat command **gmpartytest on | off** (per character until logout) or [partypatrol] test = 1 (all).
  Alone, accepting a solo patrol at a pillar starts that city's party row (same faction / level band / giver post
  when there is one) with test_start_seconds (600) to start. The client builds the mission from the 0x3e1 TableIdx,
  so it runs as a party patrol (timer, emergency posts, result window).
- Script-tested with stub sessions (start, shared posts, bonuses, emergency post, completion and 0xc1e size, time
  out, member leaving, give-up, refusal, test mode on / off). **Not yet confirmed in game.**

## Session 15 (2026-10-17 morning; repo CLAUDE.md added, HANDOVER.md §5 updated)

- **Mitro City mother quest retaken: "You cannot do missions while you're doing Chase missions."** (user, Agent
  Riggs mq_5th_005): taking a mother quest makes the client send 0x106 for every child; nq_00006 "Converse with Agent
  Riggs" was still REWARDED from the 2026-10-16 try, so quests.quest_start refused it with 20241 (that text) and the
  client went straight to the patrol child. The children's progress was never reset after a failure (user: objectives
  not reset). mothers._reset_children now drops the children's SKID_QUEST_TB rows at 0x181 (failed / given up) and at
  0x17d (start; also clears rows left from before). Children belong to one mother quest only (MotherQuest.xlt).
  Emulator restarted 09:55.
- **Then: two quest markers, no timer, failed at 0** (user): on the retry the client sent 0x106 for both children at
  once, because its own list still had nq_00006 rewarded and nq_00007 needs it (QuestClient col 4 = 50006); the
  first try (2026-10-16) started only nq_00006 and nq_00007 after its 0x10b. Xerander is not stopped by the server's
  previous-quest check (it lets PType 'A' through). Now 0x111 (login.quest_list_frame; client 0x51adb0 -> 0x750c50
  frees its two quest lists and rebuilds them) is resent whenever children were dropped: at 0x181 before 0x17c, at
  0x17d before 0x17e. Restarted ~10:10. **User-confirmed 2026-10-17**: Agent Riggs ran fine (one marker, the patrol after
  the talk).
- **Auto Fill-Up** (drift item i_automitron, category 34; user asked whether it works): it never did. The client
  (0x5361b0, every 2 s) sends 0x2d3 (car, pay 0, fuel 0, u32 1) when the tank is below 20 %, i_automitron is held
  (opts +0x1b12 from 0x5dd) and it has Mito; again 10 s later, 30 s with no Mito. The server read it as a price
  question. session.fuel_charge now fills the tank at 80 % of the price (item text; with the Fuel Booster the lower
  price, a guess), only as much as the Mito pays for, and answers with 1 @0x32 (0x2d4 handler 0x520290: the fuel
  window stays closed). Script-tested (stub session); not yet in game.
- **Battle quick slots** (user: no battle zone quick item slots): flag BattleZone.BattleQuickSlot ([net+0x296] bit 0;
  0x5aca0a, 0x5f7ce9, 0x6047da quick-slot drop, 0x60555d, 0x606a42, 0x60fbf3) was 0 (not in the 2008 Contents.ini):
  handlers/game.py NEW_FLAGS. The battle_quick items (i_n_00055 Crash Capsule, 00056 Boost Recharger, 00058 Invincible
  Rush Capsule, 00059 Drift City Capsule, 00060 Emergency Boost Kit, 00099 Mk.II Battle Quick Repair Kit) act in the
  client on 0x1a2 kind 0x1b (0x72a480 -> 0x72a9c2, by item id; Mk.II: energy + 30 % of the maximum, capped); the
  server only uses them up (items.use_item, already so). **Battle EXP 25% / 50% up** (i_n_battleEXP_*, kind
  battle_exp, "carry it in the inventory"; no client code for them): rooms.battle_exp_item adds the best one's % to
  a battle's EXP and uses one up per battle that pays EXP (a guess). Not yet in game.
- **Start alone greyed out for Newbie** (user; Xerander could): the room window (client 0x5a3435) enables Start for one
  player only with BattleZone.PracticeMode, else only for GM accounts (PType < 'N', char +0x7c; Xerander is on the
  admin account). The 2008 Contents.ini has PracticeMode=0 -> NEW_FLAGS 'BattleZone.PracticeMode': 1. Not the section.
- **Mission Battles** (Line Ball i_n_00122 / Mecha Watch 00123 / Exodus Quake 00124, kind instant, value 0-2; user: the
  item, used in the battle zone, makes a mission room and starts the solo mission, EXP at the end): the item use is
  answered with an offer 0x3df of the Instant_Client row of type Mission_Battle1..3 (124-126, Battle_Lobby); accepted ->
  0x3e0 -> 0x3e1; the client's battle lobby object (0x782bd0) switches Mission Battle on, sends 0x1b8 channel 5 and
  0x1cc type 0x10000 (rooms.MISSION_ROOM), capacity 1, map flag 0x2048 / 0x204a. That room races for real (not the
  one-member practice run); its battle result pays nothing; 0x3e2 (TableIdx only) pays instant.mission_battle_exp
  (column 14 base; Line Ball points / collisions unknown to the server; Exodus Quake +30 % for 3:30 or less from the
  race time). Layout and flow in instant.py's comment. Rechallenge Mission Battle (i_n_00125, instant_r): client
  side (0x775408 shows its button while one is held), only used up here. **First run in game (user, 2026-10-17)**:
  works end to end (offer, room, the client's own 0x1e6, race, 0x3e2, EXP). Then: the client sends **0x3eb** before
  0x3e2 (u32 TableIdx, u32 kind 1-3, u32 value = Line Ball points (144) / Mecha Watch count, f32 time, u32 tries;
  sender 0x7ef150): instant.mission_battle_result keeps it for the bonuses. The client sent 0x1e6 twice (the second
  got 20186 "Already loading."). **Second run** (user): gates still there, Rechallenge did nothing after a failed
  mission (the item was used, then nothing). The Rechallenge button (0x7824f0: free retries in mission +0x50, else the
  i_n_00125 is used with 0x1a1) restarts the race with race vfunc 0xcc (0x77bd20, race manager vtable 0x8ecb90), which
  restarts only a practice race (+0x126, set by the 0x1e7 handler vfunc 0xd4 0x7726d0 for type 100). So a Mission
  Battle room's start is now answered as a **practice run** (0x1e7 type 100, the room's map flag; no gates either),
  the duplicate start within 2 s ignored; the mission still ends and pays through 0x3eb / 0x3e2. **User-confirmed
  2026-10-17**: no gates, failing and Rechallenge work, EXP at the end.
- **License gained text** (12215 "%s", Patch.006): **user-confirmed 2026-10-17**, the license name shows, no number.

## Session 14 hand-off (2026-10-17, ~09:50; the EU client session)

Transcript `Handoff/claude_sessions/3160bd11-74ec-4c7a-982f-d8d0aecd4e8f.jsonl` (run from the side folder, so its
path key is `-home-deck-Drift-City-Project-Drift-City-EU-2011`); working files `Handoff/scratchpad_session14/`
(`tools/eu.py` = disassembler / xref / caller helpers for the unpacked exe; `nat2.py` lists every GetNation call
site with its compares; `nation_probe.py` / `empty_probe.py` = login probes for a test emulator, `test_main.ini`;
`speedo/` the dial pictures). The detail is in the "EU client" entry right below.

**What happened:**
- The user brought `DriftCityEU.exe` from the 2011 European client. It turned out to be **the US build itself**
  (2011-10-27, same addresses), ASProtect-free; one program serves every publisher through a nation number (1 US,
  7-10 EU de/eng/fr/es). Worked out in a side folder `Drift City EU 2011`, then **merged here**. The user deleted
  the side folder; its DB container `dcemueu2011_db` is stopped. Its volume `drifteu2011_mssql-data` is exported to
  `Handoff/db/drifteu2011_mssql-data.tar` and holds only a level-3 EU test character.
- **Layout now:** `Client US/` (runs `DriftCityUS.exe` = the unpacked exe without GameGuard; `DriftCity.exe` kept)
  and `Client EU/` (runs `DriftCityEU.exe`, nation 8). `./launch.sh [all|client] eu` for the EU client. One DB for
  both, emulator.ini `[nation] allow = all`.
- **`tools/eu_client.py`**: `setup eng` (nation, dname.chk check off, F2 car panel on, Data_EU_eng from Data_US,
  re-applies the dial), `us`, `f2 on|off`, `speedo [TW dir|mph]`, `status`, `reset`. The exe differs from the
  original in 29 bytes; the original is in `client_backup/DriftCityEU.exe.orig`.
- **`dcemu/native/nation.py`**: nation per session / player (0x7cf from the EU client; none = US), nation lock
  (`allow`), and EU-only rules. Active for EU: no stat points from the player's level, part V-grade check (but
  ItemClient column 8 is empty in our US data, so it does nothing yet), UTF-8 passwords, login result codes
  remapped to the EU texts (empty password -> 1, empty ID -> 2), 0x0005 logged.
- **EU client changes made at the user's request:** the F2 car-name / V-grade panel shown (the EU client skips it by
  design; `f2 on`), and the classic speedometer dial from the 2008 TW client ("Km/h", `speedo`).
- **GitHub:** this folder is now a git working copy of github.com/Xerender13/openDC. Merge commit `e878145` is
  pushed. The local EMULATOR_NOTES is now GitHub's redacted version (the test password is in memory).

**User's standing direction (session 14):**
- Keep the EU client's own design; patch it only for an exact request.
- Every EU difference in the emulator goes through nation.py, and US behaviour must not change.
- The user pushes to GitHub only when asking ("commit to github too").

**State at hand-off:** the emulator (this folder, `allow = all`) and DB `dcemu2011_db` are running. The US client
is running for the user ("switch the project to US client for now"). **Not pushed yet** (local changes):
`dcemu/native/auth.py` + `nation.py` (EU login result texts, `allowed_all` fast path), `tools/eu_client.py`
(`speedo`), these notes.

**Open, first things next time:**
1. **EU reference data:** the user is getting files from a real EU client. Wanted: `Data_EU_eng/Init_eueng.agt`,
   `Data_EU_eng/World.agt` (ItemClient.tdf column 8 = required V grade; VShopItem / VehicleList EU rules), and EU
   patches. Then sync them into server_data for EU players (data.py reads only the US tables today: per-nation tables
   are the next design step), and fill `Client EU/Data_EU_eng` with them in place of the Data_US copies.
2. Ask the user whether to keep this folder as a git working copy or go back to pushing from a separate clone
   (memory drift-city-github), and whether to push the pending changes.
3. The garage "Function 2" Korean placeholder "(보너스 아이템 옵션)" on the EU client with parts on the car: not yet
   compared with a US car that has parts.
4. The ADV HUD's speed unit is a text control (game.nui 220057, T1="MPH"); change it in Client EU's game.nui only if
   the user asks.
5. Two old test failures (tests/test_position.py: tutorial gate, `DB` stub without `rows`) predate session 14.
6. The Session 13 entries (2026-10-16 afternoon) and session 12's open list below still stand.

## EU client (2026-10-17; worked out in a side folder `Drift City EU 2011`, merged into this project the same day)

**Merged layout:** `Client US/` (the US client; `DriftCityLauncher.ini exe = DriftCityUS.exe`, the unpacked US exe from
`tools/eu_client.py us`; `DriftCity.exe` still there) and `Client EU/` (`DriftCityEU.exe` set to nation 8, `Data_EU_eng/`).
`./launch.sh [all|client] eu` / `launch.bat [all|client] eu` start the EU client; `setup` copies the tables from
`Client US/`; `Launcher/build.sh` builds into both. One database for both versions (`dcemu2011_db`); emulator.ini
`[nation] allow = all` (with all nations allowed and an ASCII password the login does not wait for the client's 0x7cf;
its nation is noted when it comes). The side folder kept its own database (container `dcemueu2011_db`, volume
`drifteu2011_mssql-data`, port 14331: its EU test character), not used here.


**The "EU client" `Client EU/DriftCityEU.exe` is the US build (2011-10-27, same timestamp, same addresses) dumped without
ASProtect** (stolen import calls restored); unchanged it is nation 1 (US) with the US server address. The program
serves every publisher; the nation (client 0x4e9360, global 0x94d880; 1 US, 7 EU de, 8 EU eng, 9 EU fr, 10 EU es) is
set only by the options constructor (0x4e4106). `Emulator/tools/eu_client.py setup [eng|de|fr|es]` (docstring has
the bytes): sets the nation (original kept in `client_backup/DriftCityEU.exe.orig`, `reset` restores), skips the
dname.chk data file check 0x4ed620 ("Invalid Files Detected": the list is the US folder's), builds
`Client EU/Data_EU_<lang>/` from Data_US (hard links; World.agt with the five Data_US tables of the patch packs folded
in, since patches name them Data_US\...). EU nation differences found so far: data packs ../Data_EU_eng/*_eueng.agt;
login server slots 0x8daa14/24 (62.146.191.136/.135); start token md5("eu_%d_plz_do_not_hack") (0x5095a0) instead
of md5("%d"); no GameGuard (class table 0x4e1210 = 0); login 0x14 with a UTF-8 password, then 0x7cf (u32 nation) on
auth (0x7feaf0); GlobalText EU ENG column has ~2,200 texts vs ~5,600 US (expect blanks). The launcher: `[client]
exe` (default DriftCityEU.exe when present), EU token when the exe holds an EU nation, address over all 13 slots.
**Own database**: compose project dcemueu2011, container dcemueu2011_db, volume drifteu2011_mssql-data, port 14331
(the US characters stay in driftcity2011_mssql-data). Status: client starts, reaches the login screen (2026-10-17).
**Nation-aware emulator** (2026-10-17): `dcemu/native/nation.py` - every session knows its client's nation (0x7cf from the EU client on each connection; none = US 1; Player.nation set at the game login); `nation.of(x)`, `is_eu(x)`, `rule(x, name)`; emulator.ini [nation] client = auto | N and us.<rule> / eu.<rule>. First rule: part requirements (items.equip_item -> nation.part_allowed): ItemClient column 7 = player level, column 8 = the client's "Required Grade" (tooltip 0x657442, item record +0x124; read as the car's V grade; 0 in all US rows). **Nation lock**: emulator.ini [nation] allow (here eu): the auth answer waits for the client's 0x7cf (<= 1 s; none = US) and refuses other nations with result 99 before the password check (no account made); accepted logins remember the account's nation (nation.remember) for the lobby / game check-ins, because on game the 0x7cf can come after the check-in (a refusal by order once left the character loading). **US exe**: `eu_client.py us` writes Client/DriftCityUS.exe = the unpacked exe, nation 1, GameGuard class byte 0x4e1211 2 -> 0 (runs to the login screen; launcher [client] exe = DriftCityUS.exe). **F2 user information car panel = EU client design**: 0x294 GameCharInfo is answered the same for both (0x295); the handler 0x515be0 fills the window with 0x56ff80 -> 0x56f910 (shared; only the distance unit differs: miles for US, km for others, 0x56fbb1), then draws the car panel with 0x551ce0 (car-name image 0x564820 by car type, V grade 0x563f30) only for nations 1-3 and 6: table 0x570010 (nation - 4) = 0 0 1 0 0 0 0 skips it for 4, 5 and 7-10. Then shown on the user's request (2026-10-17, the one exception): `eu_client.py f2 on` (part of setup) sets the table bytes of nations 7-10 (0x570013-16) to 1; `f2 off` = EU design. Before that it was kept as the EU design (user: "Keep the EU design, that's the key point of the version"; the F2 box under the portrait is the crew, empty without one). **EU changes in the emulator are gated on the client's nation** (user): part_grade only eu (us.part_grade = 0), the password decoded as UTF-8 only for EU (decoded after the nation is known), 0x0005 logged (nation.eu_report). **No stat points from the player's level in the EU version** (user): nation rule level_points (us 1, eu 0) -> Player.stats char points 0 for EU players (0x2f8, F2 0x295, other players' info); characters loaded for someone else get nation.of_member (the account's last login nation, else an EU nation on an EU-only server). **Login error texts**: the EU client maps result codes to the same GlobalText keys, but the EU column means other things for some (10049 = code 4: US "An ID or Password has not been entered", EU "This is an ID with an age restriction": user saw it for an empty password); nation.login_result sends EU clients 1 for an empty password and 2 for an empty ID; a failed login waits for the client's 0x7cf first (with allow = all a successful one does not). **Km/h speedometer** (user): the classic HUD dial (game.nui 210001, piece 272,267~512,512_ui_play01.dds, "MPH" painted in) replaced in `Client EU/Data_EU_eng/gameui/uitex.agt` only by the 2008 TW client's dial (Data_TW.agt picture 406, "Km/h" + RPM numbers 0-10; uncompressed 256x256): `eu_client.py speedo` (`speedo mph` back; original pack client_backup/uitex_Data_EU_eng.agt.orig; setup re-applies it from client_backup/tw_speedometer_406.dds). The ADV HUD's unit is a text control (220057, T1="MPH" in game.nui), not changed. The EU client also sends a one-off 0x0005 (104 bytes, client report, sender 0x7e3ef0) that US clients never sent. Login to the city in EU mode works. Next: the V-grade rules (EU-only branches, e.g. 0x5fa8ed in the item code; the
'7..10' nation checks: Handoff/scratchpad_session14/tools `nat2.py` pattern = list GetNation call sites and their compares).

## Session 13 (2026-10-16 afternoon; not yet confirmed in game)

- **Mitro City (Taipei) traffic** (user: no traffic cars): the client joined **area 68** there (from Moon Palace
  channel 0, area 4); the emulator took 68 for an Oros area and sent Oros's .tcs cars (0x2bd), which Taipei cannot
  place. Now areas 62-75 = Taipei (city_traffic.TAIPEI_AREAS; other Taipei channels not seen yet) and Taipei gets
  **path traffic (0x21e)** on Taipei/Path/path_taipei.chpath (136 lanes, 336 km; chunked chpath layout in the
  city_traffic module text — make_traffic_paths.read_chpath's fixed offsets break on it), driven by tw_traffic.Race
  (crossings found once in a thread, ~2 s; stepped every 0.5 s, ~7% of a core for 400 cars), 40-70 km/h,
  TrafficFlowControl block 5 models, emulator.ini cars.taipei = 400; 0x220 / 0x223 wreck the car. **Signals**
  (user request): path_taipei.signal (248 stop points on 63 paths) on ZoneServer's rule (0x5983ad loads
  trafficSignal_%d.txt / PVP_map*.signal; 0x5976d0: one 60 s cycle of the server clock, type 0 red 0-30 / green
  30-58 / amber 58-60 s, type 2 green 0-28 / amber 28-30 / red 30-60 s); city_traffic.CityRace adds them to the
  engine's stops. The client's Taipei lamps cannot follow (it reads .signal only for trainPath; its lamp table comes
  from a .tcs). Not yet confirmed in game.

- **Mitro City missions not offered again after failing** (user): a failed child quest makes the client send 0x10c,
  then 0x181 (row, 1) (client 0x5138b0; give-up 0x513a70 sends (row, 0)); its 0x182 handler 0x50ed80 only redraws the
  window and the mother quest stayed in its held list (+0x12c) until the next login. mothers.mother_give_up now
  resends 0x17c (0x754fb0 clears and rebuilds the list). Not yet confirmed.

- **Part on an occupied slot** (user: docking refused on Double Beta parts, fine on High GR Beta; H set parts came off
  without a Heat Treatment Kit): the client sends only 0x199 for a part dropped on a filled slot and expects the old
  part to come off. items.equip_item kept both parts in one slot and skipped the kit. Now the old part comes off first
  (take_off: option + docking with it); a hyper part there is refused. **Hyper parts / H docking slots come off only by
  a Heat Treatment Kit used on the part (0x1a3)**, as the client does for normal (scorched) hyper parts; 0x19b no
  longer takes a kit from the bag (user: set parts came off by dragging). Client kit path 0x5fe110: use kind 0xf / 0x35
  on a slot whose part is grade H / E (set parts too) -> 0x1a3. The client draws a second
  part of a shared slot in the next free slot of its type (slots: speed 100-102, accel 103-105, crash 106-108, boost
  109-111, items.SLOT_BASE), so docking there found no part: items.fix_shared_slots at login moves it there
  (Xerender car 4: si_B_D01 -> 109, si_B_D04 -> 103).
- **A part dropped on an occupied slot goes to the type's free line first** (user: equipping the second set took the
  first one off): the client sends the slot it was dropped on (Double Beta Dura -> 107 with 106 free); the part there
  is replaced only when the type's Main.PartsInvenLine lines are full (0x19a echoes the slot used). Client slot pick:
  0x5fe32c.. (the target if free, else the first free index below the per-type limit 0x5fdde0, default 2).
  The client draws the new part over the dropped-on one at once (user: the first set's parts went invisible, the
  DB was right): the 0x192 now also carries the dropped-on part after the new one. Not yet confirmed.
- **Set parts need no Heat Treatment Kit** (user, confirmed with other players: the kit is only for normal H parts):
  items.needs_heat returns False for set parts (setparts.is_set) and for an H docking on one; they drag off / swap
  freely. Normal H parts still only by a kit used on the part (0x1a3).
- **Crew nameplate colour** (user: pink on the own client, green for others): the client colours it by the crew grade
  in XiPlayerInfo @0x58 (0x62ac31: 0 C green, 1 B blue, 2 A pink, 3 S orange); for its own crew it computes the grade
  itself (0x537e70: total exp / 10 + points >= 500000 or a channel win -> S, >= 100000 A, >= 20000 B); the emulator
  sent 0 for others. Now crews.crew_level in misc.player_info. Not yet confirmed.
- **Docking letters** (user: a later letter must have better stats): the white range is cut into one band per letter,
  A lowest (docking.roll_docking); the hidden % already rose with the letter. Docking items made before keep their points.

## Current state and where to continue (end of session 12, 2026-10-16 ~12:05)

**Session 12 in short** (2026-10-16 morning; transcript `Handoff/claude_sessions/b3aee7eb-d07e-49f5-92fb-634cf477d4e7`;
the detailed log is the "Session 12 log" paragraph right below this list; module docstrings have the layouts):
- **Confirmed by the user in game:** battle room Start after an unready player leaves (0x1e5 ready = 1 before 0x1d5),
  race traffic None, spectator view, room invitations across sections (invitee moved to the room's section with
  0x1b9), battle tracks from the start request (0x1e6 map; Recommend / Random were always track 0), Taipei tracks
  (emulator.ini [flags] City.Taipei = 1), Real Match notices + GM command `realmatch open|close|in N|auto|status`
  (Real Match left on emulator.ini `always`), rush notices, Mita 500, quest failure assist, licenses + counters,
  license gained text (12215 %s), the "loading data" login hang (bundles cut at 8 KB, login.BUNDLE_MAX), factions
  (0x76c SelectGuild -> GUILDTYPE, "First Task from ROO" sets 1, "Choice" -> OMD sets 0; others see it through 0x329
  PlayerInfoRes with guild @0x98; ROO needs a HUV Call Unit for HUV calls), the Santa parts on the own driver (0x1e
  content flags now sent before 0x7c), main quests broken by mq_ rows (player.load skips non-QuestClient rows).
- **Done, not yet confirmed in game:** Pro EXP tiers read from the room type (0x20000 4X .. 0x100000 16X; 6X / 8X
  bits by pattern), host-leave Start fix (leaver / host announced ready), Mitro City (Taipei) Mother quests +
  reputations (mothers.py; chain start "Suspicious Man" at post_4rd_00004 Oros; list flag in 0x17c a guess), quest
  HUV chases (0xb4 type = quest row, nearest HuvTable level), City instant offers OMD-only, ST Lottery gift (gift
  colour = leading number of the item text; Newbie's waiting gift message fixed by hand), repeatable missions +
  Small Gift Box level bands, the Item Exchange Attendant (TokenBook rows 5-9, Mittron Crystal Powder; daymission.py).
- **Open, first things next time:**
  1. **Test the repeatable missions and the Item Exchange Attendant** (the user's current request): a Koinonia / Cras
     rq_ twice, a Small Gift Box, a powder exchange; if the attendant's menu sends something other than 0x48a, look at
     its dialog (text "Itemtradeshop", ch_1st_0004_01).
  2. **Taipei chain in game** (Xerander, ROO -> now OMD): mq_5th_002's B-Hex S chase, mq_5th_003 "To Mitro City"
     (client sends 0xc80 for the city), reputation messages 0x7d4, the _m / _c branches need Airport Base reputation
     >= 1000 (repeat sq_5th_*).
  3. Complete Bonus Reward panel in battle rooms ("Recommended by Duffy EXP +25%", bonus stage stars; probably 0x1e4
     PvpBattleBonusResult) - the user asked to look at it later.
  4. Older open items: crews beyond marks, Mito car upgrade items, Pro tiers, Mita 500 bottles in Moon Palace, 0x465,
     0x0e7f / 0x0e81, Taipei traffic, channel battles, crew board, DCLoverN's car 1 fuel (103 -> 88.6).
- **Client files changed this session (user-requested; originals in `Emulator/client_backup/`):**
  `Client/Patch/Patch.006`: text 12215 "%d license" -> "%s"; Patch.006 had been found vanilla again (cause unknown), so
  12216 (coupon) and 11413 / 12214 (crew logon without "[Team]") were re-applied (`tools/global_text.py`).
- **Characters / DB changed by hand:** Xerander main quests rewarded up to #125 (next: "Choice" done by the user ->
  OMD); Xerander GUILDTYPE set 1 / 0 by hand while debugging (now 0 = OMD, set by the client); NewChar restored after
  the Mother quest test; Newbie's ST Lottery gift message ITEM colour fixed (20408). DB backup in
  `Handoff/db/SKDBTW.bak` (2026-10-16 12:05).
- **Debugging lessons** (tools in `Handoff/scratchpad_session12/tools/`): diff a good and a bad login's server
  frames (type, size, payload hash) first - it found the 24 KB item bundle at once; gdb breakpoints with logging
  (`gdbtrace.py`, `gdbxmas.py`, attached by `watchnew.sh` / `watchxmas.sh` to a newly started client) work in the Wine
  client; never stop such a gdb with `timeout` (left int3s: the client crashed); 2008 server functions with
  `zdis.py` (needs the dc-dev-venv for capstone). Client facts found: 0x7e handler 0x511640 -> 0x537ed0 (own
  XiPlayerInfo at ctx+0x3d41c: avatar @0x96, guild @0x98, 0xd0, 0xd4) -> 0x801030 (0x30e); content flags block =
  [0x973e40]+0x268; driver model 0x474d20 (Santa parts if Etc.EventChristmas and hero type 4); car.isROO 0x4ba640.

**Session 12 log (detail, in order):** Xerander's main quests #1-#81 marked rewarded (no rewards given; #82 "Patrolling the
Mining Complex" is next; script `Handoff/scratchpad_session12/set_main_quest.py NAME TABLEIDX`, character offline);
battle room Start fix after an unready player leaves (user-confirmed; open item 1 below is done). Also user-confirmed: race traffic None, spectator view, quest failure
assist (longer timer, more hits allowed). Mita 500 pick-up / drink and rush notices user-confirmed. GM command **realmatch open | close | in MINUTES | auto | status** (chat gmrealmatch, control port; rooms.gm_realmatch: an override of emulator.ini realmatch until auto; 'in' sends the 10/5/2/1-minute 0x1c8 notices and the 'started' one, opens for realmatch_minutes, then back to the ini; Real Match notices user-confirmed; left on auto = emulator.ini realmatch = always, open permanently: user). **License gained text** 12215 "%d license" -> "%s" (Client/Patch/Patch.006, global_text.py; user: number instead of the name). Patch.006 was found vanilla again (cause unknown): 12216 coupon and 11413 / 12214 crew texts re-applied. **Battle tracks**: the 2011 client keeps the room's map at 0 and sends the chosen track (pick, Recommend, Random) in 0x1e6 @2; start_request now races that map (2008 Cmd_PvpStartReq -> BS_Room::StartLoad does the same); before, every race was track 0 (user: Recommend / Random always one track). Recommend = PVPTrackInfo "Recommend" column; "Recommended by Duffy EXP +25%" panel and **Complete Bonus Reward** panel (stars, EXP / MITO; probably 0x1e4 PvpBattleBonusResult) not implemented: user asked to look at it later. **Mitro City (Taipei) Mother quests + reputations** (`dcemu/native/game/mothers.py`, docstring has the layouts; user request): MotherQuest.xlt 38 rows (level and V9 car needed; mq_5th_001..020 main with _m Mafia / _c City Hall branches, sq_5th_001..018 repeatable), 0x17d/0x17e start, 0x17f/0x180 complete (rewards 0x7d1 exp, 0x7d2 Mito, 0x7d4 reputation), 0x181/0x182 give up, 0x17c list at login (flag = done: guess), 0x7d4 x3 at login; children nq_* are ordinary quests the client starts itself (0x106); reputations = license counters GC_Reputation_01..03 (the old computed reading in licenses.py removed); levels from client 0x50e3e0 (<1000 neutral, <3000 somewhat friendly, <9000 friendly). Chain start: "Suspicious Man" (Agent Matt) at post_4rd_00004, Oros (5554, 10448); #3 "To Mitro City" from post_1st_00941 Moon Palace. Taipei icons added (data.CITY_ICONS 5: Icon_Taipei_Client.tdf, map 4) for the quest GPS 0x312. Script-tested on NewChar (restored); not yet in game. **Quest HUV chases** (user: nq_00001 had no HUV): 0xb4 type = the quest's TableIdx (0 for a HUV call) and its HUV count; the quest's HUV level may be missing from HuvTable.tdf (B-Hex S 10015 at 75: only 71 / 73 / 78) -> chase.huv takes the nearest level; quest chases spawn exactly the asked count of that HUV. **Factions** (2011 only; no server field, the client and server read the quests): Oros "Choice" (#126) -> "Team ROO Headquarters" (#127, QuestClient col 5 ROO) or "Patrol Oros City" (#145, OMD); licenses.faction = the one taken. **The faction is the character's guild type**: 0x76c SelectGuild (u32) -> 0x76d (same u32; client 0x517b20 -> char +0xf1), SKID_CHARACTER_TB.GUILDTYPE (2008 Cmd_SelectGuild); "First Task from ROO" (#108) sends 1 = ROO (user: faction did not change, 0x76c had no handler); licenses.faction: guild 1 = ROO, else the Choice quest taken (Choice -> OMD sends 0 = OMD: user-confirmed 2026-10-16). **Gift of an ST / Normal Lottery bundle froze the receiver** (user): its item text is "<card UniqueId> <count>" ("20408 11"); gifts.colour gave 0 for it -> now the leading number (0x51c and the kind-300 message ITEM); Newbie's waiting gift message fixed by hand. Not yet confirmed. **Repeatable missions** (user request): rq_* rows (QuestClient column 5 = 1; column 7 the highest level) can be started again once rewarded (quests.is_repeatable; no wait / daily limit in the table); "The Fifth City Tour" (column 5 city) stays one-time. Their Small Gift Box (i_n_00100, giftbox_lv, rw_rq_koi) now opens: only the player's level band (Etc_Value = the band's top level) is rolled (driftuse.open_gift_box). The repeatable missions' shop = the Item Exchange Attendant ("Itemtradeshop" text): Mittron Crystal Powder (i_n_00096) -> TokenBook.xlt rows 5-9, already served by daymission.py's token exchange (0x48a); not yet used in game. **Santa parts on the own driver** (user: "christmas outfit" only on the own client, after the bundle split): the 0x7c handler builds the own driver model at once and checks Etc.EventChristmas (0x4750e1: flags +0x50 bit 13, hero model type 4) with the flags the client holds then (0x60ffc01, leftover); the 0x1e came in the next frame. Login now sends 0x1e before 0x32a / 0x7c. **User-confirmed 2026-10-16** (also the ROO HUV call / faction at login and for others). **Other players' faction**: 0x329 PlayerInfoRes (2011, keeps all 0xd8 bytes) instead of 0x322 (keeps 0x96), with avatar @0x96 and guild type @0x98 (user-confirmed: Newbie sees Xerander as ROO). **"Loading data" hang at login (fixed, 2026-10-16; not the faction):** the item list (all 0x191 parts + 0x1a5) went out as one bundle of 24360 bytes for Xerander's 189 items (14828 bytes still worked); the client stopped reading the game socket (Recv-Q grew), dropped its area / barea connections, never sent 0x30e. login.send now cuts bundles at BUNDLE_MAX 8192 bytes. Found by diffing a good and a stuck login's server frames (type, size, payload hash). The faction (guild type 1 = ROO) is fine at login (user: on the official server ROO changed only the HUV calls). ROO drivers get HUV calls (0xbd -> 0xba) only holding a HUV Call Unit (i_n_00063, vc_C_callunit), one used up at the call's 0xb4 (chase.use_call_unit; quest chases do not use one); City instant offers (OMD rows) go to non-ROO players only (ROO: the request-house band). Not yet in game. player.load skips SKID_QUEST_TB rows that are not QuestClient quests (an mq_ row became TableIdx -1 at the head of 0x111 and the stations showed the Rookie missions again: user). Next (user): repeatable quests + their Moon Palace shop. **Taipei tracks**: emulator.ini [flags] City.Taipei = 1 (Contents.ini lacks it: the fifth city button was blank); not yet confirmed; may open the city too. Invite list fixed (all sections; user-confirmed). A player joining a room of another section (invitation) kept its own section's rules (user): join() now sends 0x1b9 with the room's channel first (client 0x52a040 stores it at +0x3d520 and redraws that section); user-confirmed 2026-10-16. Pro EXP tiers fixed (read from the room type; see "Battle zone rooms (2011)").

## State at the end of session 11 (2026-10-16 morning; session 10 summary below)

**Session 11 in short** (2026-10-15 evening to 2026-10-16 morning; details in the entries right below and in the
module docstrings; transcript `Handoff/claude_sessions/1127d900-...` continued as `0c5bd430-...`):
- **Confirmed by the user in game:** drift shop gifts and the gift queue, V upgrade gifts, Director Green's start
  message, crew marks, Mita 500 stacking (1-3 bottles next to the nameplate, below level 71), the Mita / Bacchus
  timers (seconds, not ms), the battle zone no longer freezing (BattleZone.BattleZoneReform = 1), spectators sent
  off when the host starts alone, the seamless Real Match car swap (0x425 only, no car-change light column).
- **Done, not yet confirmed in game:** licenses + monthly reward (Driver Dome only), crews beyond marks (approval,
  Manage Crew with 2 members), Mito car upgrade items, quest give-up at login, Mita 500 on exp (not on quest exp; on
  quest Mito), city instant offers by level band, battle zone sections Newbie (11) / Pro (12) with flags
  ChannelNewbie / ChannelPro / Channel16X and emulator.ini rules, Pro EXP tiers (rooms.PRO_TIERS; the tier bits in
  the room-create message are a guess, logged), race traffic level from the room (0x04 None, 0x08 Light, 0x10
  Normal, 0x20 Heavy, none Random) and halved densities, spectator view (BArea 0x336), spectator counts (list entry
  + 0x1cb to spectators), room invitations (0x1c2 / 0x1d1 / 0x1d2), Real Match fuel (own tank, 0x2d1 ignored),
  realmatch_effect = 0 (roof figure; christ_girl / christ_gift effects, cause unconfirmed), 0x1a2 size, the Newbie
  tooltip picture (161MPH) and the crew logon texts without "[Team]".
- **Open, first things next time:**
  1. **Host's Start greyed out after the other player left by itself** - session 12: only when that player had not
     been ready (user); the resent 0x1be did not help. Now rooms.leave casts 0x1e5 ready = 1 for a not-ready member
     just before its 0x1d5 (the client's 0x1d5 handler keeps its not-ready state). **User-confirmed 2026-10-16.**
     Session 12 also: the new host's Start greyed after the host left (after a race the clients hold everyone
     not ready): every leaver (host too) is announced ready before 0x1d5, and the host is announced ready after a
     result; Start = 0x5a2a60 (+0x14a6: more than one member and all seated ready, else room type & 0x200 at
     0x942b40 = room info +0x10; ready flag = member entry +0x6c, list 0x96fb60, stride 0xcc). Not yet confirmed.
  2. The not-yet-confirmed list above, especially Pro tiers (invitations, traffic None and spectator view user-confirmed 2026-10-16).
  3. DCLoverN's car 1 fuel went 103 -> 88.6 in a Real Match race before the fuel fix: set it back while offline if
     the user wants.
  4. Older: Mita 500 bottles in Moon Palace, 0x465, 0x0e7f / 0x0e81, Taipei traffic, channel
     battles, crew board.
- **Client files changed this session (user-requested; originals in `Emulator/client_backup/`):**
  `Client/Patch/Patch.006` (texts 11413 / 12214, besides 12216 from session 10; `tools/global_text.py`),
  `Client/Data_US/gameui/uitex.agt` (Newbie tooltip picture; `tools/ui_texture.py`). Patch.000 unchanged
  (BattleRoomAI = 0 from session 4).
- **Debugging a hung client** (used this session): `Handoff/scratchpad_session11/tools/` - gdb attach (`gdbthr*.py`:
  the Windows esp / eip of a waiting thread are in the syscall frame on its unix stack, segment words 0x2b0023
  0x2b002b 0x6b0063), `gdbcatch.py` + `watch.sh` (faults; C++ exceptions do not raise signals), `mdis2.py` / `calls.py`
  on the client image, `q.py` (SQL query).


**Running it:** `cd Emulator && ./launch.sh` (database + emulator in the background + client; the city traffic is
native since session 9, the old TrafficAgent container is now `Server2008/traffic_agent/`) or
`./launch.sh server` / `db` / `emu` / `emu-bg` / `client` / `stop [part]` / `restart-emu` / `status` /
`logs [part]` (`./launch.sh help`). The client: `Client/DriftCityLauncher` (Linux; Windows `DriftCityLauncher.exe`),
settings `Client/DriftCityLauncher.ini` (address, `display = windowed|fullscreen`, HUD, `item_icons`). Source
`Launcher/` (Go), `Launcher/build.sh` builds both in the golang container (build to a temp name and `mv`: running
launchers keep the old file open). Accounts admin/admin (Xerender, level 90) and a second test account (DCLoverN). Test
characters for scripted tests: NewChar (cid 100005); DCLoverN (100032, the user's 2nd character: only while offline).
At hand-off the stack was running (container `dcemu2011_db`, emulator pid in `Emulator/.emulator.pid`).

**Session 10 in short** (2026-10-15 day; details in "Session 10" below; all user-confirmed unless listed under
"not yet tried"): account registration at login, rename kit 60-day wait, the 2011 item use-type table (Auto-Driver,
Damage Boosters, fuel, enhancers), quick slots saved, party HUV chases, rush time 2011 (always-on zones with 2+
players, scheduled rushes win over player-triggered ones, boss / escort moves, Lil' Grimer, parts on every hit,
win reward per text 10893), Real Match notices, city instant missions only in the field, manufacturing (skill
books, crafting, shop in the Driver Dome, K key, parts grinder), scorched hyper parts, PLUS / DELUXE enhancer odds,
Bacchus F / D (0x483), Mita 500 (on), coupon marking fix, drops respect the inventory limit; Doom Dozer's baby
dozers and Optimum Grime's escorts / Lil' Grimer confirmed by the user, `[rush] test_health` back to 0; the US
client's coupon text 12216 fixed in `Patch.006` (the only client change besides Patch.000). **Data layout changed
at the end:** `Emulator/data/` is gone; the client's tables are in `server_data/Init/` and `server_data/tables/`
(next to the 2008 server tables), the reward / chance txt files in `server_data/`.

**Session 11 (2026-10-15 evening): drift shop gifts** (`dcemu/native/game/gifts.py`, docstring has the layouts;
user request): 0x51a name search -> 0x51b, 0x516 SendVisualItem (2011: 490 bytes, message wchar[200]) -> 0x517 to the
sender + 0x51c to the receiver when online, 0x518 GetVisualItem (i64 GID, u32 car, u8) -> 0x4b2 .. 0x519. As the
2008 server: SKID_VISUALITEM_HISTORY rows (receiver STATE 2 waiting -> 0 taken) + a SKID_MSG_TB message of **kind
300** (ITEM "TableIdx,days,GID,time,colour"), which the 2011 client's 0x84 handler puts in its gift list (so the list
comes back at every login); the message is deleted when the gift is taken. Price as a purchase (vshop.charge, split
out of 0x4b3 with grant / finish). The 2008 refusal of car upgrades (20137) is not applied: the 2011 client offers
the V upgrades as gifts (the user's first try was the V3 upgrade). Script-tested (NewChar -> DCLoverN, claim, second
claim refused, cleaned up; test in `Handoff/scratchpad_session11/gift_test.py`). **User-confirmed in game** (V3 / V2
upgrades Xerender -> DCLoverN).
**Permanent V upgrades (VShop category 14, i_d_u_01..08) cannot be used from the drift inventory** (user: "don't work
when used"): the client never buys them as items (0x680ea0 sends 0x5b UpgradeCar for the selected car instead), so a
gifted one is now applied when taken, to the car chosen then (a car one grade below; else refused and the gift
stays); ones taken earlier go back to the gift list at login (gifts.return_upgrades; DCLoverN had V2 and V3).
**Mito car upgrade items** (UseItemClient kind MitoCarUpgrade, i_d_mu_v2_2per .. v9_10per, value = chance %; user
request): 0x1a1 on the current car (the client's checks 0x5f9990 repeated: real grade + 1 = the item's, level, not on
auction); success -> 0x5c (text 10501), failure -> a message; used up either way, no Mito (cars.py "upgrade items").
Script-tested (`Handoff/scratchpad_session11/upgrade_items_test.py`). Not in game yet.
**V upgrades cost CC** (user: Mito was a bug): 0x5b (upgrade window and the drift shop's V upgrade "purchase") is paid
like a purchase of the grade's CARREMODELING row (i_d_u_01..08, "$Price 0D" CC, or mileage), 0x5c carries the CC /
mileage the client takes off (@0xa / @0xe); VehicleUpgrade.xlt only gives the level, capacity, efficiency.
**Trade history window** (user: "implement the trade history tab"): 0x514 BuyHistoryList (offset = page x 14, 14,
type 1 bought / 2 sent / 3 received) -> 0x515 (0x216-byte units; gifts.py docstring) from SKID_VISUALITEM_HISTORY;
purchases (0x4b3) and V upgrades (0x5b) are recorded now (GetType 0). A waiting gift can be taken from the received
tab. **The gift pop-up is a queue, not a list** (user: the V3 gift vanished when the V2 one was opened): the client
shows one gift at a time (0x68f140, dedup by GID) and marks its message read; it comes back at the next login and
stays in the trade history's received tab. Script-tested (`Handoff/scratchpad_session11/history_test.py`; it once
deleted NewChar's 3 old purchase rows, restored).

**Licenses** (`dcemu/native/game/licenses.py`, docstring has the layouts and every rule; user: "license system", "all
license conditions and their counters"): License.xlt (69), License_GC.xlt (195 conditions), License_ME.xlt (31 effects).
0x32b / 0x32d (the client also sends 0x32d by itself every ~2 min; was ignored) -> 0x32c held licenses / 0x32e all
condition values; 0x32f -> 0x330 mounted (3 slots, held only); 0x326 (serial + mounted) = the car's nameplate licenses: to everyone incl. the player on a change, to the player at 0x12c JoinArea, with 0x322 player info (user: the nameplate showed none when it went to the others only); 0x331 a license gained; 0x29a ->
0x29b + 0x32a another player's licenses (car menu). Content flags Main.License + Etc.NewLicenseSystem now on (the panel
was hidden), Main.LadderDisplay (the nameplate's license icon, 0x536790). Counters in SKID_PLAYMODE_TB (MODEID = the GC name, 'GCM_<kind>_YYYYMM' monthly, 'LIC_<id>', 'LICSLOTS'),
hooked into battles (team / individual, track city), chases (per city, party), rush (clear, Lucky Driver = winner),
deliveries (medals, per job a_000NN <-> GC_Quick*_NNN), patrols (per city from the posts, party = party_move*), quests
(rq_* repeatable, per city), coupon totals (field drive time s, Undercity), Mita 500 (drinks, 500 %, 250 %), mission
tokens, auctions >= 20k Mito (registered / sold, seller offline too), enhancement (+10 .. +19, monthly tries), convert /
production monthly tries, camouflage kits (cartrans 300 / 900 s); computed: main quest chain per city (exits: Moon #34,
Koinonia #71, Cras #107, Oros #144 ROO / #162 OMD), faction (QuestClient column 5 'ROO' / 'OMD' quest taken), licenses
held, DC badges held, Neo Oros reputations (rewarded quests at Airport Base / City Hall / Mafia posts: our reading).
License Ownership Reward Money (user: monthly Mito): once a month from day 1 (flag Etc.NewLicenseSystemnDay = 1), the License.xlt "Grade" of the licenses held, paid in the Driver Dome only (position state 3: login there, 0xa2 with state 3, the periodic 0x32d; user), shown once the client is in the game (0x86 GetMail): 0x8a MoneyMessage + a kind-500 text message without Mito (licenses.pay_monthly / tell_payment; a 0x84 sent during the login was lost: user; **user-confirmed working**) (`licpay_test.py`). **Room invitations** (rooms.py): 0x1c2 -> 0x1c3 invitee list (players in any section's lobby, own section first, not in a room, passing the room's level / grade rules; session 12: the 2008 same-channel list missed Newbie in the Newbie section for a Real Match room, user), 0x1d1 / 0x1d2 forwarded to the invitee with the inviter's serial, cid and name (2011 layout +4 bytes @0xa). Car-change light column after a Real Match room (user: should be seamless): the 0x5a handler 0x510ea0 starts it outside the garage (0x6d1960 resets the effect timer of effects/levelup.nif, sound 0x4ea1); rooms.drive() now swaps with 0x425 only (0x708820 sets car id / type / colour of the current car); **user-confirmed 2026-10-16**: no effect, Duel in room and race, own car back. effects/ui/christ_girl.nif + christ_gift.nif = the roof figure with gift boxes (0x6f8581 / 0x6f8612; what switches them on not looked at yet). **Real Match fuel**: the Real Match car (rooms.real_match_car) gets a full tank of its own; 0x2d1 drive info is ignored while real_match_car is set (it reported the Real Match car's fuel under the player's car id and was saved onto the player's own car, user). **Spectators**: BArea 0x336 ObserveMode (0xe bytes, was sized 0x10 and dropped): World.observers get the race's moves; race traffic is not sent to spectators yet. **0x1a2 ItemUseAck** is 4 bytes longer in 2011 (a u32 time after the use info). realmatch_effect set to 0 (roof figure in Real Match, user; cause unconfirmed). **Spectators sent off** (rooms.send_off_spectators): 0x1bf result 3 ("This room no longer exists.", the client also clears the room) when the host starts alone (practice run; user: 2 players + spectator, one left; result 2 only showed its message, the client stayed in the room), and result 3 when the room closes. After a leave / kick the waiting room's full state 0x1be is cast again (the host's Start stayed greyed out after a voluntary leave, with or without spectators; test pending) (they were not told before). **Crew logon notice without "[Team]"** (user): client text GlobalText 11413 / 12214 changed to "%s has logged on/off." with tools/global_text.py (Client/Patch/Patch.006; original client_backup/Patch.006.orig, `global_text.py reset`). **Race traffic halved** (user, 2026-10-16): server_data/race/TrafficServer.ini CarsPerKm 0.85 / 1.8 / 2.4 (Light / Normal / Heavy; was 1.7 / 3.6 / 4.8). **Battle zone rooms (2011)**: map flag bits: traffic 0x04 None / 0x08 Light / 0x10 Normal / 0x20 Heavy / no bit Random (client 0x5bb2c0 button order; the Taiwan mapping 4 = Light was wrong, user) -> race.room_traffic_level -> the race traffic engine ('None' = no cars); 0x4000 = speed limit on (the client caps the car itself, 0x489165, at the section's MaxBattle*SpeedLimit km/h); Pro EXP tier 0x20000 4X (lv 11+, V1-5, 290) / 0x40000 6X (31+, V1-7, 320) / 0x80000 8X (51+, V1-9, 350) / 0x100000 16X (71+, V1-9, 380): rooms.PRO_TIERS (exp multiplier and join limits); Newbie section x3 (lv 1-30, V1-5, 260). **The tier bits are room type bits, not map flags** (session 12: 0x1cc type 0x20080 = 4X, 0x100080 = 16X in the logs; the two u32 after the flags were always 0, so every Pro room paid the section's x4): section_rule / car_allowed take the room type; 6X / 8X bits by the same pattern, not recorded yet. **Newbie tooltip picture** ("260KM" -> "161MPH", user asked): tools/ui_texture.py replaced 636,540~806,607_ui_contents30.dds in Client/Data_US/gameui/uitex.agt (original: client_backup/uitex.agt.orig, `ui_texture.py reset`). **2011 battle zone sections**: buttons Newbie = PvP channel 11, Pro = 12, Real Match = 6 (client 0x5aa075); flags ChannelNewbie (0x34 bit 30) and ChannelPro (0x34 bit 31, added to flags_2011.tsv) unlock them, Channel16X sent too; emulator.ini section.11 / .12 with the GlobalContent.xlt limits. Open: the reform's per-room EXP tiers (2X-16X with speed limits, GlobalContent *11New / MaxBattle*SpeedLimit) are not implemented. **Battle zone freeze -> BattleZone.BattleZoneReform = 1** (handlers/game.py NEW_FLAGS): a new character (DCLover2, Amateur section) froze on opening the battle zone; found with gdb on the hung client: the main thread sat in the game's crash handler, exception in 0x5baff0 (control 0xe30d7 of the old battle lobby layout, looked up by 0x8191e0 and used unchecked; that code runs only with the flag 0). The battle tutorial flag 0x4000000 was not it (tried and reverted). Windows stack of a hung Wine thread: the syscall frame on its unix stack (segment words 0x2b0023 0x2b002b 0x6b0063; windows eip / esp just before). **Mita 500 also raises exp** (user; 2008 was Mito only, the client shows MITO/EXP); on quest rewards only the Mito (user). **City instant offers by level** (user: a level 2 character got "Accumulate 500 Combos"): below level 56 the player's request-house band (classic rows), from 56 the three City rows (instant.city_offer_kind), below 4 none. **Mita 500 stacking** (150 / 200 / 250 %, below level 71 only) is shown as 1-3 bottles next to the nameplate, the count taken from the rate (client 0x61f020); user-confirmed. **Buff times are seconds**: 0x481 Mita 500 and 0x483 Bacchus carry the time left in seconds (the client adds it to its clock; ms showed 998 minutes, user). **A quest left started** (the emulator stopped / crashed, so the close hook quests.give_up_on_leave never ran) is given up at the next login (quests.give_up_at_login; user: the main mission stayed active after a disconnect). **Director Green's start message** (StartMent_Client.tdf, gate 0) needs 0x30f MyPositionAck state 0 for a new character (2008 sends the stored LASTPOSSTATE); the emulator had sent 1 since going native (user: no tutorial messages) - position.first_position; **user-confirmed working**. Instructor Duffy's battle tutorial (Tutorial.tdf): left out on purpose (user, 2026-10-15: probably not finished in this client version). **In the tutorial gate (position state < IN_CITY) the login is this morning's** (login.TUTORIAL_FLAGS: the 4 license / nameplate flags off, no license frames, no 0x0e75, no 0x326; user: Director Green's tutorial messages stopped); licenses.on_login when the character reaches the city (position.my_city_position). No license is gained in the tutorial gate (a new character holding Rookie at login skipped Director Green's intro: user; licenses.check). Rookie (ladder >= 0) goes to everyone, and stands in slot 1 whenever nothing is mounted (licenses.mounted; user: the nameplate spot must not be empty). Not counted (no such mode): channel battle attack / defence, ghost battles, 3rd
anniversary coins. Effects of the mounted ones: items.play_bonus(activity) Mito / exp %, auction / enhance fee %, parts
drop %, chance gauge x, production chance %; booster / combo repair ones are the client's. Script-tested
(`Handoff/scratchpad_session11/license_test.py`). **Not yet seen in game** (the window needs the flags above).
**Crews** (`dcemu/native/game/crews.py`, docstring has the 2011 layouts; user: "crews with crew center functionality (crew
chat too)"): 2008 PacketParser::Cmd_*Team* rules with the 2011 sizes (XiStrTeamInfo 384 = 2008 + u8 @0xef + 12 bytes at
the end; member entry 76): create (level 20, 10000 Mito), name / URL check, my crew (0x348 was "no crew" in misc.py), member
list, join request -> master's approval (0x367 / 0x368 / 0x36c), leave (0x350), kick (0x36b, 24 h wait), ranks (1 master,
2 first class, 3 member), master handover, close / cancel / deletion after 7 days, crew marks (built-in 01-10 from
server_data/teammark (sync_data copies them), uploads saved as teammark/<id>.bmp), notices 0x36d (incl. logged on / off,
deletion countdown), crew chat (room "team"), profiles show the crew. Script-tested (`crew_test.py`). In game (user): the mark upload is a JPEG; marks are images of the lobby's image
service (0x40 GetImage act 0x3f5 (crew, mark) -> 0x41, stickers.get_image) kept in SKID_IMAGE_TB (TMARKID = IMGID; the
built-in 1-10 from server_data/teammark); 0x368 comes for OK only with its i32 0 (Cancel = 0x36c): approvals were read as
refusals; Manage Crew only adds kick / rank buttons to the member slots (none for a crew of one); the Bulletin Board
opens Hangame's web board (guild.hangame.com ... guildbbs, 0x63a5f0) in the client's browser: dead, not a server
message. A crew mark not found is answered with result 0 (not -1 as for stickers): -1 left the client's mark cache busy
(one request at a time) and it never asked for another mark until restarted. Not done: channel battles (crew vs crew, owned channels), the crew board tab, 0xe24 / 0xe25 (a win / loss record
view, not crews), 0xcee ContributeItem.

**Open after session 10 (in this order):**
- **Coupon banner fix to check in game** (client restart needed): `Client/Patch/Patch.006` now has text 12216 with
  %s (see the Session 10 entry); the banner should name the coupon.
- **Mita 500 bottles not seen in Moon Palace** (user): they are in the client's list (0x95c830 + 4, 16-byte
  entries; positions at +0x10 .. +0x50), the nearest was 380 m away. Next: with the user in Moon Palace, read the
  client's list live (/proc/PID/mem, read-only) and tell them the nearest bottle's coordinates; if one is not drawn
  up close, trace the client's draw code.
- **Not yet tried in game:** Mita 500 pick-up / drink, rush scheduled-vs-triggered and
  leaving-the-zone notices, Real Match notices, the rush splash for every player (Doom Dozer and Grime themselves: confirmed).
- **Quest failure assist** (client-side, server already sends the fail count; **user-confirmed 2026-10-16**: the timer and the hits allowed grow after a fail): test later - fail a timed main
  quest, start it again, the timer should be longer.
- Not done: 0x465 (a member complains about a HUV / controller switch), 0x0e7f / 0x0e81 (quick slot extension,
  Neo weapon slot), Taipei traffic (from session 9).

**Session 9 in short** (2026-10-15; details in "Session 9" below): the city traffic is native
(`dcemu/native/city_traffic.py` + `tcs.py`, `emulator.ini [traffic]`), replacing TrafficAgent.exe, which had Oros's
and Cras's lanes swapped (Oros got Cras's traffic). Traffic lights now show **amber** (0x2c2 carries the time of
the light's last change; the client draws amber 4 s after stop / 1 s after go). **Confirmed by the user: amber
lights work.** The agent kit moved to `Server2008/traffic_agent/` (own docker-compose.yml, for comparing only).
Next traffic goal (user): **Taipei**, which has no .tcs (path traffic from Taipei/Path/path_taipei.chpath +
.signal, like the races' 0x21e; its area numbers are unknown: log what the client sends there first). Session 8
(late 2026-10-14: parts boxes, H parts / heat treatment kits, daily mission clear, delivery / patrol reward
tables, rookie missions for DCLoverN, Metro key) is written up inside the "Session 7" entry.

**Layout:** `Emulator/` is self-contained (own `server_data/` = the 2008 server's files + the client's tables:
`server_data/Init/*.xlt`, `server_data/tables/*.tdf` and the cities' traffic files in `server_data/tables/<City>/`
(from `tools/sync_data.py`, gitignored); `db/`, `docker-compose.yml` project dcemu2011 on the volume driftcity2011_mssql-data); `Server2008/` = 2008 stack + research
tools + `traffic_agent/` (the standalone TrafficAgent container) (client image, sdis.py, pdbtypes.py, handlers/dispatch tables), not needed to play; `Launcher/` = client launcher
source. Client files: `Client/Patch/Patch.000` = original + BattleRoomAI = 0; `Client/Patch/Patch.006` = original + US
text 12216 "%d" -> "%s" (coupon banner; original in `Emulator/client_backup/Patch.006.orig`); cursor files original (backup also in
`Emulator/client_backup/cursor/`); other originals in `Emulator/client_backup/`.

**Session 7 in short** (details in "Session 7" right below):
- **Launcher** keeps data patches in the running client (`keepPatches`, once a second; ASProtect forbids code
  patches): the item-icon flag ([[0x973e40]+0x2b4] bit 4: received items as HUD icons; user-confirmed) and, with the
  ADV HUD, the delivery cargo camera's viewport (into the Delivery Service box). **Linux: 32-bit libXcursor /
  libXrender from the Steam Linux Runtime (sniper) on LD_LIBRARY_PATH** (`cursorLibs`): SteamOS has none, so Wine drew
  the two-colour pale hand instead of the blue glove (user-confirmed working).
- **Items:** timed usable items (UseItemClient column 12; Mittron Enhancers 72 h) get ExpireTick @0x48 (they showed
  expired at once); the server tick runs live in a session; CDATE is UTC. Premium Package = a drift item acting as the
  three drinks (no double effect). Restoration Lubes: kept in the drift inventory, used on ONE set part from the
  inventory's lube panel (0x1b0 ReplenishItem, +720 h). Drift items can be deleted (0x4bb, also items on a car;
  paid items with time left: the client refuses, text 10455). PassiveAssist DriftBooster equippable, effect only on
  the car being driven.
- **Patrols:** parts per 50 posts follow the client's InstantDrop_Client.tdf (none at 4-7, Lvl 65 from 67);
  completion prize `[patrol] prize / prize_count` (placeholder Mittron Enhancer); 0x3e5 lists items by **TableIdx**.
- **Instant missions (NewInstant):** 0x3de request-house "Instant Quest" -> 0x3df offer -> TAB notice; City
  missions offered by the server every `[instant] city_offer_minutes`; formula rewards.
- **Daily mission + Mission Tokens** (`daymission.py`): today's mission, token at Suyeon, 0x489, TokenBook exchange
  0x48a; counters in SKID_PLAYMODE_TB 'DAYMISSION'.
- **Delivery jobs:** 0x144 sends the place count (5; was 0: no markers, user-confirmed fixed); leaderboard kept in
  SKID_ARBEITREC_TB, job list ranks, 0x153 -> 0x154 rank list, best / current in 0x146.
- Tests: `tools/rewards_test.py`, `tools/auction_test.py [seller]` (DCLoverN default; snapshot cleanup). Scripted
  tests of this session (patrol, lube, day mission, drop, jobs) are in `Handoff/scratchpad_session7/`.

**Confirmed by the user this session:** item icons on pick-up, patrol prize, delivery points on the map, the cargo in
its box (by hand; launcher version built after), the blue glove cursor (with the cursor libraries).

**Not yet confirmed in game:** timed item expiry display (Mittron Enhancer time left), lube panel use on one part,
deleting drift items, the daily mission (token at Suyeon, exchange), instant mission offers (request house and City
notices: needs the client option "Show instant messages"), the delivery leaderboard, equipping the DriftBooster
(the client offers Equip; the old code refused), the launcher's automatic cargo move.

**Open / next:**
- Instant missions: the other 2011 contexts (Battle_Room, Battle_Lobby, Chasing, QuestFail5; their reward formulas
  use battle / chase values); ROO faction rows; how the request house post number maps (logged at 0x3de).
- Daily mission: attendance / day mileage (0x48b, 0x494, texts 10913 / 10917), 0x488 to players online at the day
  change (2008 XiDayMission::OnTick), the token event season value in 0x489.
- Delivery: date type mapping of the rank list (0-5) is ours; check the Week / Month / All buttons in game.
- Patrol completion prize is a placeholder (the client has none); the user may want another item / count.
- Older items: friend "play together", car colour fix, Bonus Assists, Windows launcher on real Windows, Gotcha parts
  machines (client-closed), auction @0x18 guess, Driver Dome drift bonus, crews (0x357), rest of the Misc tab, AI racers.

**Method that worked:** the client image `Server2008/client_image/DriftCity_2011_unpacked.bin`, linear disassembly with
`Handoff/scratchpad_session5/sweep.py` (needs capstone: a scratch venv `python3 -m venv V && V/bin/pip install capstone
pefile pillow`), a single function with `sweep.py <image> <start> <end> out.txt` when the linear sweep is misaligned;
2008 functions by name with `Server2008/tools/dev/sdis.py server/ZoneServer.exe.orig tools/dev/ZoneServer.syms NAME`,
2008 struct layouts with `tools/dev/pdbtypes.py server/ZoneServer.pdb NAME`; callers of a 2008 function with
`Handoff/scratchpad_session7/xref.py`, operand search with `scan.py`. C>S senders (`mov word ptr [eax], TYPE` after
`call 0x807450`), S>C handlers in `Server2008/tools/dev/handlers_2011.txt`. UI from `Client/Data_US/gameui/game.nui`
(euc-kr). The 2016 Dev Ed exe is unencrypted (pefile import names). **Live client memory** via /proc/PID/mem (the user
set kernel.yama.ptrace_scope = 0): read freely, write only with the user's OK; scripts in
`Handoff/scratchpad_session7/` (job.py, cam.py, mgr.py, qread.py ...).

**Working rules (user):** native server in the 2011 formats; protocol fixes in the emulator, not the DB; client vanilla
unless asked (and check that a GlobalContent switch has UI support before turning it on); **restart the emulator after
every change without asking** (`./launch.sh restart-emu`) and say so; edit a character's DB rows only while it is
offline (`tools.gmctl who` / `kick`); kill only processes I started, by exact pid (never pkill / pgrep -f patterns);
commit only when asked.

## Session 10 (2026-10-15): account registration at login, rename kit wait

- **Registration at login** (`native/auth.py` `register`, `emulator.ini [auth] auto_register = 1`): an ID with no
  MEUSERMT row is created with the password typed (MD5, VALID 'y') and the login continues as normal. Empty
  password -> result 4 (10049); IDs other than 1-32 of `A-Za-z0-9_.-` -> 2 (unknown ID, as with the switch off).
  Tested against the DB (throwaway account, deleted); confirmed by the user from the client (Testaccount1).
- **Driver's Name Change Kit wait** (`game/driftuse.py`): the kit's texts 10954 / 10955 say 60 days before the
  next change. The last rename is kept in SKID_PLAYMODE_TB MODEID 'RENAME' (LASTDATE UTC, TRYCNT = renames);
  `[items] rename_days = 60` (0 = no wait). The client's 0x6b (0x51ce70) has only ok / failed (mode 1: 10605 free /
  10604 taken; mode 0: 10954 renamed / 10960 failed), so an early try gets a Send_Error text with the time left
  (and a failed 0x6b for mode 0); the kit is not used up. Renames made before this have no record. Confirmed by
  the user in game (2026-10-15).

- **Auto-Drive:** the drift shop Auto Drive System (VisualItem category 39) is all client-side and works (user,
  2026-10-15). The Auto-Driver / Turbo Auto-Drive (UseItemClient kind `auto_drive`, i_n_00097 / 98) did nothing:
  0x1a2 ItemUseAck carried the **2008** use-type codes, but the 2011 client's codes are the 2008 ones + 1 plus new
  kinds (string -> code 0x7014e8; ack handler 0x51fdc0 -> 0x72a480 switches on our code). `items.USE_KINDS` is
  now the 2011 table: auto_drive 0x29 opens the destination window. This also moves fuel (3) and the point-up
  enhancers (8-10) onto their real client cases; before, accelpointup ran the client's "damage" case. Test in
  game: a Mittron can. **Damage Boosters N / S / H (each in its level range), the other consumables and the Auto
  Quick-Slot confirmed by the user (2026-10-15).** **Auto-Driver confirmed by the user (no crash; the old 0x1a reply had crashed
  the client).**

- **Consumables after the use-type fix:** the client acts on 0x1a2's type (cases listed in items.py). Damage
  (7): value bit 1 = one critical hit on a HUV (Damage Booster N/S/H, value 1, 1 s), bit 2 = damage boost (Power
  Up, value 2, 30 s); HUV damage is client-side, so nothing more on the server. The Boosters' level ranges are the
  **player's** level, checked by the client (0x717eb0: i_n_00093 N 1-30, 00094 S 31-60, 00095 H 61+; refused
  silently, no 0x1a1; Damage Booster H on Xerender (Lv 90) confirmed working by the user). Quick slots (client rules, 0x573360 / drop 0x604080): an item with a cooldown used from
  the inventory goes into a quick slot; a slot item of the same kind (0x240) blocks another (Damage Power Up
  cannot be placed while Damage Booster N is in a slot), no free slot = silently nothing. The client sends its
  slots as **0x7d0** (u32 mode 0, 4 x u32 TableIdx; mode 1: one TableIdx @20, a fifth slot not restored by the
  client): now saved (`game/quickslot.py`, SKID_CHARACTER_TB.QUICKSLOT1 = "a,b,c,d") and sent back in
  XiStrCharInfo @0xc5 / 0xc9 / 0xcd / 0xd1 (the last two are the first 8 of the formerly unknown 12 bytes; the 0x7c
  handler restores the slots from them via 0x71fc90). Fuel items and quick-slot saving confirmed by the user. Before the fix: damage went out as 6 = turbosave,
  fuelsave as 4 = money (nothing), turbosave as 5 = fuelsave.
- **Auto Quick-Slot / Auto Fill-Up / Auto Drive drift items:** the client sets its flags ([opts+0x1b11 / 0x1b12
  ..]) by looking up i_autoquick / i_automitron / i_autodrive in its drift inventory **in the 0x5dd BonusUpdate
  handler** (0x517390, also 0x535fc0), so 0x5dd must follow any change (it does: login, purchase, gmdrift).
  The quick-slot window then shows the "A" buttons; when a slot's cooldown (the client item table's +0x248 /
  +0x24c, not our ack) ends, the client sends 0x1a1 again. No server message of its own.
- Control port (`tools.gmctl`): `item NAME ITEM-ID [count]`, `drift NAME DRIFT-ITEM-ID [days]` (as gmitem /
  gmdrift, for a character online).

- **Quest failure assist (2011, not in 2008):** client-side, from the fail count in 0x107 QuestStartAck (u32
  TableIdx, u32 fails). Handler 0x513500: for F fails it passes 3F, 5F, max(F-1, 0) and min(5F, 15) to the
  mission object (0x7582e0 -> 0x7581b0 -> ctor 0x74bc70); none for quest kinds [quest+0x914] 1 / 2 / 4 / 5. Each
  goal's time limit = the quest table's goal time + one of them (0x74bd65: [obj+0x30] = goal time + [obj+0x14]);
  the others are most likely the hit limits (not traced). The server side was already there: 0x10c QuestFail
  (sent by the client, 0x7ec816) -> FAILNUM + 1 in SKID_QUEST_TB, sent back in the next 0x107. No recorded
  session has a failed quest yet (every 0x107 so far had 0 fails). **TO TEST LATER (user, 2026-10-15): fail a timed
  main quest, start it again, the timer should be longer.**

- **Party HUV chases** (`game/chase.py`; user: only the caller got the chase). 2008 Cmd_ChaseBegin 0x5f6a40:
  the party members in the same city / channel, not busy, chase together; HUV k belongs to member k mod n
  (unit serial) at that member's level (GetChasePartyHuvLevel; user: "2+2", each player's HUVs at his level),
  the same 0xb5 to all; 0xb9 progress to all with the sender's serial (Cmd_ChaseProgress), 0xbb hits to the
  others (Cmd_ChaseHit); a caught HUV rewards the player who sent its 0xb7; serial 0 = that player stops (his
  HUVs end, own 0xb8); 0xb8 to all when no HUV is left, a unit per member. Leaving the game leaves the chase.
  The 0xba offer still goes only to the caller (as 2008). Confirmed by the user in game (2026-10-15): both got
  HUVs, the result screen for everyone.

- **Rush time 2011** (`game/rush.py` docstring, `emulator.ini [rush]`): the 2008 timetable (`schedule`, was already
  there) plus the 2011 always-on mode (`always = 1` -> content flags City.AlwaysRushTime + RushTimeStartMember):
  a city gate's zone (key city + channel *name*, e.g. "speeding") with `start_members` (2) players starts a rush
  `countdown` (60) s later, sent as 0x467 RushUpdate (start, HUV, course, members); fewer players cancel it.
  0x464 member count also on entering. **No server announcements** (user): only the client's own from 0x45c
  (scheduled rushes: chat line + green top notice, handler 0x52eed0). In always mode the zone window shows 11138
  / 11139 ("participants n/m") unless 0 < start - now < 660 s: then the countdown (mm:ss) and the boss name /
  description (client 0x58ac80, flag 0x1000 of [char + 0x278]). Only 0x457 redraws the window (0x467 just stores),
  so a zone reaching start_members gets its countdown at once (on entering, not at the next tick) and every
  member gets 0x457 + 0x467 (user: the window stayed on "?" / 11138 with 2 players).
- **Rush boss stuck / hits not counted (fixed):** the boss got car sort 1 = every player's car sort (0x7e), so it
  was the controller's own car (serial, 1): the other client sent area 0x23d RequestCar ~14,000 times (unknown
  here: the frames' rest dropped) and the area service took boss moves as the controller's car. Now boss sorts
  are 1001+ (rush.SORT_BASE), area.py keeps client-driven objects apart (car.objects, own sort = first move) and
  answers 0x23d with 0x23e ResponseCar (XiCarMove). tests/test_area.py ObjectTest. Then (user: still stuck): the
  controller's client drives the boss with a car sort of its own (1357 recorded, not 0x45e's 1001), so the others
  got moves of an unknown car: rush.object_sort maps each new sort of the controller to the next unmapped HUV and
  area.py relays / answers under that. **Rush times on the client clock:** 0x45c / 0x457 / 0x467 now carry
  rush.client_time (UTC - 1 h, native.CLOCK_SHIFT as in 0x311): with real times the client saw every rush an hour
  late (no countdown window, no "under N minutes" notices). **User 2026-10-15: countdown shows, the boss moves and
  takes hits (HP goes down).** Then: a player-triggered rush picks its boss (HUV_TYPES) and course at random (all
  zones used the timetable hour's type: always Doom Dozer); boss hits drop from the part groups only (combo.drop
  parts_only: a part on every hit (user), the group weighted by the table's mode-3 part rates) and
  roll twice with the Item Drink (combo.drops; rush called drop directly). User: parts on every hit, confirmed.
- **Rush: scheduled vs player-triggered (user):** the scheduled rush's period (10 min before its start to 10 min
  after: RushTime.scheduled) blocks player-triggered countdowns; a waiting zone goes idle and shows the scheduled
  start; at the start every zone with members starts with the table's boss. Leaving the zone: 0x459 then 0x45c
  again (rush.schedule_notice: the running scheduled rush's start, in the past = HUD back without texts, or the
  coming one within an hour), since the client's 0x459 handler drops its rush HUD (user: the scheduled rush
  information was gone outside the circle). Offline-tested; not yet in game.
- **TEMPORARY (user, 2026-10-15, for testing): `emulator.ini [rush] test_health` (5, then 10)**: every rush HUV dies
  in that many hits (each hit's damage x full health / test_health; first version overrode the health in 0x45e). Set it to 0 (or remove it) when testing is done.
- **Rush HUV moves (Optimum Grime escorts):** a HUV move's XiCarMove has its 0x45e number at +4 and its type at +6
  (11001 Grime, 10001-10004 escorts); +2 is a local id of the driving client (1357, 15876, 0, 50264..). The
  first-come sort mapping (rush.object_sort) scrambled Grime and the 4 escorts (user: escorts not with Grime, not
  following): removed; area.move relays with +2 = +4. Lil' Grimer: client-side on the controller (0x4aee10 state
  machine: a threshold, then events 1 / 2 (+3 s) / spawn 11002 + event 4 (+3 s +2.4 s) via 0x8027c0 -> 0x462 and
  0x802620 -> 0x45e); in the user's test (test_health 5) the controller never reached the threshold (no 0x462 at
  all) - the trigger value is not the server health (+0x88 compare, not traced; BossHuvInfo "event" column = 40
  for Grime). 0x465 (u16 serial, u16 HUV number: a member complains about a HUV) still has no handler.
  Doom Dozer's baby dozers (11005 / 11006, pre-loaded at 0x4ac6d5) have the same problem (no 0x462 in the user's
  test). Found so far: 0x45b sets a HUV's health [+0x43c0] and [+0x43cc] = max [+0x43bc] - health - [+0x43c4];
  [+0x43c4] (damage) is written by 0x00c5 BS_PktHuvHealth (u16 HuvId, CarSerial, CarSort, HealthType, i32 HP,
  Delta; client 0x512d60, only in game mode 0x13), and the trigger (0x4aee10) compares [obj + 0x88] with the
  boss's [+0x43c4]. The 2008 server sent only 0x45b on a rush hit (RushEvent::HitHuv -> MakeRushStatus). Death
  Dumper's timed events (0x462 every 5 s) work. **Traced live (2026-10-15, read-only /proc/PID/mem, both
  clients):** the boss vehicle (vehicle array [[0x948844]+0x124]+0xe4, type @0xe4) has max @0x43bc, health
  @0x43c0, damage taken @0x43c4 (= max - health, updated from 0x45b in every client); its AI object (first dword
  = the vehicle, state @0x90) holds the threshold @0x88 = 480.0 for Grime (40% of the client table's 1200
  durability, the "event" column): Lil' Grimer comes out when the damage reaches 480 - absolute, so the old
  test_health (health 5 / 10) could never get there. test_health now scales each hit's damage (health stays the
  client's; every HUV dies in test_health hits). Monitor script: Handoff/scratchpad_session10/rushmon.py.
- **Lil' Grimer traced live and confirmed (2026-10-15):** with test_health scaling the damage passed 480 at the 4th
  hit, both clients ran the sequence to state 4, the controller sent events 1 / 2 / 4 and 0x45e 11002 (health 400),
  both clients got a live Lil' Grimer. The rush ends only when the escorts are down too (user: correct). Splash
  only for the controller (Newbie): the others' own 0x45e for a part that comes out mid-rush (rush.EMERGING 11002
  / 11005 / 11006) is now answered with that part's 0x45e (r.frames). Not yet tried.
- **Notices (user):** rush 0x45c only at 10 / 5 / 2 / 1 minutes; leaving the zone re-sends it only for a running
  scheduled rush. Real Match (schedule mode only): 0x1c8 RealMatchNotice (u32 time, u32 type; client 0x52bac0)
  type 0 "will begin in %d minutes" at 10 / 5 / 2 / 1, type 1 "Real Match Started!" at the opening
  (rooms.real_match_tick, run by rush's ticker). emulator.ini has realmatch = always: no notices then.
- **City instant mission offers only in the field** (user: they came in the Driver Dome): instant.in_field - the
  player's area car (area connection, by serial) must be in a city area (city_traffic.area_city; areas 0-3 =
  Driver Dome / tutorial, area 0 after login, area 4+ after the gate dialog).
- **Manufacturing (skill books, crafting, the manufacturing shop)** - `game/alchemy.py` (docstring = protocol):
  0x0e75 at login (EXP u64 + learned skill book ids), learning = 0x1a1 on a user_create item -> 0x0e7c, crafting
  0x0e78 (skill book id) -> 0x0e79 (id, u8 success, u64 EXP) + 0x192; recipes Alchemy_SkillBook.xlt, levels
  Alchemy_LevelModify.xlt; kept in SKID_PLAYMODE_TB ('ALCHEMY', 'SKB_<id>'). The manufacturing shop (NPC Sid,
  texts only for city 0 = Driver Dome) sells RewardGroup rs_manufashop_* through 0x195 (items.buy_item). Choices
  of ours: materials and kit are used up on a failed attempt too. Offline-tested (learn, craft, refusals) + SQL
  against the DB; not yet in game. Unidentified Skill Book (random_skb, rw_random_skb: 97% Mittron Enhancer,
  ~3% a skill book) already worked.
  **Content flag Main.ManufacturingSystem (block 0xc, bits 17-18) must be >= 1** (emulator.ini [flags]; was 0):
  the client checks it 7 times (skill book use 0x6015b0, the shop / its marker 0x7b4d6f next to manufashop_icon.nif,
  UI 0x5748fd / 0x6087a9 / 0x610dd6 / 0x61b87b / 0x73bcfa) - user: the shop did not show (map marker only), K did
  nothing. (Etc.AlchemySystem, block 0x54 bits 24-25, left at 0.) The shop's 3D entrance + icon (cylinder_liteblue.nif,
  manufashop_icon.nif, 0x7b4d6f) are made once when the Dome scene is built: the client must be restarted after the
  flag changes (user: shows up after a restart). **Parts Grinder:** 0x0e1a (u32 part InvenIdx, u32 grinder
  InvenIdx) -> 0x0e1b echo + 0x192, RewardGroup rw_partsgrinder_<n|s|h>[_dock] (1 dust + 1 / 3 Modified Parts
  Piece), alchemy.grind_part; grinding always succeeds (user: fine). **0x0e75's entries are UTF-16** (wchar[60];
  the client's recipe names are wide, read live at [0x95a134+4..+8]); sent as char[0x78] the learned skills were
  lost after logging in again (user). 0x0e7c's char[56] is converted by its handler, so learning live worked.
- **Scorched hyper parts** (user: no scorched icon): ItemClient column 14 links 20 hyper parts with their scorched
  twin (i_a_000009 Gargoyle <-> i_a_000009_b Scorched Gargoyle, same stats). items.scorch: equipping turns the part
  into the twin (ITEMID updated), a Heat Treatment Kit (take_off) turns it back; at login hyper parts already on a
  car are scorched. Confirmed by the user (2026-10-15).
- **Mittron Enhancer PLUS / DELUXE better odds** (user): the success % of an enhancing try x emulator.ini [items]
  enhancer_plus (1.5) / enhancer_deluxe (2.0), by the enhancer's UseItemClient "time" (2 PLUS, 4 DELUXE; also the
  gauge fill), capped at 100 %; break % unchanged (upgrade.tier_factor). Converting Solution PLUS: two draws, the
  better kept (convert.draw, unchanged).
- **Bacchus F / D** (manufactured; user: using it did nothing): the client has no timed effect for use types 0x4c /
  0x4d (its case only adds the value, 0 in the table, to the boost). Server: p.bacchus_until (10 min per use, adding
  up) -> +50 % EXP and Mito in items.play_bonus (with the drinks). **The client's side is 0x483 BacchusBuffInfo**
  (u8 1, u32 uses, u32 kind 1 F / 2 D, u32 ms left, u8 new; client 0x5188c0 -> 0x705af0: "Acquired [Bacchus F
  Effect]" 11936 / 11937, then its own use type 6 (boost kept on collisions) for content flag
  InstantMission.BacchusBuffSec seconds (block 0x20 bits 0-11; set to 600 by __main__), D also 0x4d (booster
  charging)). (First try: the ack sent as turbosave - no effect shown, user.) Mita 500 buff = 0x481 (same idea). 0x0e7f = the Field QuickSlot extension (count @+0x1925, expiry), 0x0e81 =
  the Neo weapon slot (+0x192d): not sent yet. Manufacturing confirmed by the user.
- **Mita 500** (user: turn on, configurable; 2008 had it, off) - `game/mita500.py` (docstring = protocol), emulator.ini
  [mita500] (enabled 1, bottles 10, regen_sec 300, buff_sec 1800, fee 500, lucky_rate 10) -> content flags
  InstantMission.Mita500*. Bottles per city area at mitaquest.qpos indexes (500 per city), sent on 0x12c JoinArea
  (0x47e); 0x47f pick-up -> 0x480 to the area/channel; 0x482 drink -> 0x481 (2011: + i64 Mito paid); 2008 rate
  rules (150/200/250, lucky 500, lv 71+ 150), 3 a day, exclusive with Bacchus; Mito bonus in items.play_bonus.
  Offline-tested (sizes, broadcast, rates, limit); not yet in game.
- **Coupon marking** (user: "failed to mark" for ERIC at 14000 combos): the client sends 0x3f7 MarkCoupon before
  the 0x3f2 with the counter that reached the target, so the stored counter was one short; coupons.reached now
  trusts the client for its own counters (only DUEL_RM / RUSH_TRY, the server's, are checked). Test values for
  Xerander set 2026-10-15 (one short of each first coupon; PANDA drifts 999).
- **Rush win reward (2011):** client text 10893 "Received 3 Unidentified Skill Books, %d Mito, 5 Enhancement
  Formula." -> rush.WIN_ITEMS: 3 random_skb + 5 i_n_00061 + the Mito (was the TW Mittron Enhancer).
- **Rush bosses confirmed, test values off (user, 2026-10-15 end of session):** Doom Dozer (baby dozers) and
  Optimum Grime (escorts, Lil' Grimer) work; `emulator.ini [rush] test_health = 0` again (normal client health).
- **Coupon banner text (client fix, user-requested):** "Congratulations! You have acquired %d Coupon." is the US
  column (Value_US) of `Data\Localize\GlobalText.xlt` row Key 12216; the client passes the coupon's name (the KR /
  JP / TW texts have %s), so the US text printed the string pointer as a number. **`Client/Patch/Patch.006`** (the
  pack that holds the effective GlobalText.xlt) rewritten with that one `%d` -> `%s` (agt.write, original header
  bytes 20-31 copied back, every other entry byte-identical); original kept as
  `Emulator/client_backup/Patch.006.orig` (restore: copy it back over `Client/Patch/Patch.006`). The client reads
  packs when it starts. Not yet seen in game.
- **Data folders merged (user, end of session 10):** `Emulator/data/` removed. The client's tables:
  `data/Init` -> `server_data/Init`, `data/World/*` (the .tdf tables and the `<City>/` traffic folders) ->
  `server_data/tables/` beside the 2008 server tables (no name clashes). `emulator.ini [native] data = server_data`
  (Init is read from `<data>/Init`), the former World reads use `Tables.server_data` (`[native] server_data =
  server_data/tables`), city_traffic reads `<data>/tables/<City>/`. `delivery_rewards.txt`, `patrol_rewards.txt`,
  `gate_rewards.txt`, `team_gate_rewards.txt`, `docking_chances.txt` moved from `Emulator/` to `server_data/`.
  `tools/sync_data.py` (and `./launch.sh setup`) write `<out>/Init` and `<out>/tables`, default out = server_data.
  `.gitignore`: `server_data/Init/` and the client's files in `server_data/tables/` are ignored (the 2008 files
  stay tracked). Tests pass, the emulator restarted fine (city traffic loads). Older entries below still say
  `data/World` / `data/Init`: read them as `server_data/tables` / `server_data/Init`.
- **Drops respect the inventory limit** (user: the Item Drink's second item went past it): combo.take_if_room
  (free = (HancoinInven + 2) x 20 - items not on a car; a stack needs no slot) in combo.drop (traffic, combo, rush
  hits) and chase.catch; full -> 0x2e5 (0, -1), also for the drink's second roll.

## Session 9 (2026-10-15): native city traffic (TrafficAgent.exe replaced)

User request: move the traffic agent into the emulator (a mismatch with the agent; Taipei, absent in 2008, will
need traffic later). **`dcemu/native/city_traffic.py`** (+ `tcs.py`, the .tcs reader) now drives the city
cars and signals; `emulator.ini [traffic] city = native` (default) / `agent` (the old program) / `off`,
`cars.<city>` per area. The agent kit (Dockerfile, start.sh, agent/ data; was `Emulator/traffic/`) moved to
**`Server2008/traffic_agent/`** with its own docker-compose.yml (container `dc2011_trafficagent`) for `city = agent`;
launch.sh has no traffic part any more (it only re-kicks that container after an emulator restart, if it runs).
Tests: `tests/test_city_traffic.py`; a scripted client in area 52 got Oros lanes and cars.
Amber: confirmed by the user in game (2026-10-15).
- **The mismatch found:** TrafficAgent drove **Cras's lanes in areas 52-61 and Oros's in 76-85**, but the
  2011 client drives Oros in area 52 (a logged session of the user's, 2026-10-14 23:26: the car's positions
  are 2-10 m from Oros.tcs lanes and off every Cras lane). So Oros had Cras's traffic (cars on invisible
  roads, mostly out of range) and Cras Oros's. Native: area block 1 Moon Palace, 2 Koinonia, 3 Oros, 4 Cras
  (city_traffic.AREA_CITY), the files by the client's world numbering (0x44e840: 1 MOONPALACE, 2 KOINONIA,
  3 CRAS, 4 OROS, 5 TAIPEI, 6 NEOOROS; TrafficFlowControl's city blocks in the same order).
- **The agent's output, measured** (a capture server on 11031 with the real agent, 1 min all areas + 5.5 min
  area 4; scripts in Handoff/scratchpad_session9: capture.py, capture2.py, an*.py, e2e.py): 0x2be/0x2c3 per area for every car and lamp each
  second, 0x2c0 flush. XiTCSCarMove: time = the server tick (from its 0x21c), pos in lane units (travel time
  at 100 km/h: 1 = 27.78 m; a lane's points are `delta` = 1 apart), speed m/s (lanes' max 19.44), accel
  +max/10 (also at top speed), braking so that speed + accel >= 0, -100 stopped; model = Unique Id - 20001;
  next lane ~200 m before the end, third lane always -1. XiTCSSignal: time 0, **the lamp id** (.tcs 0xA6030,
  490 in Moon Palace; not the signal id), state 1 green / 0 red. Intersections (0xA5030 controllers): road i
  green 15 s at i x 30 s of a roads x 30 s cycle; crosswalk signals (0xA0040) red 30 s / green 28 s. Cars:
  Moon 300, Koinonia 400, Cras 438, Oros 380 per area, all areas from the start; it placed car k on lane
  first + k (all in one part of the city); native spreads them over all forward lanes.
- Native engine: per area, started when a player enters (0x232), stopped 120 s after the last one left;
  1 s steps (each car moves with the acceleration it was sent, then plans the next: the client's
  extrapolation is what the server does), ~1 ms per area step. Cars within 320 m + lamps within 320 m
  go to each player once a second. Car models: the client's TrafficFlowControl.xlt (5 city blocks; weights
  6/3/1). Data: tools/sync_data.py now also copies the city packs' .tcs / .chpath / .signal to
  data/World/<City>/ (TCS files identical to the agent's).
- Also fixed: area.flush_cast (agent mode) cut its output every 4096 bytes, splitting 24/14-byte commands
  over two frames; now cut between commands (city_traffic.frames).
- **Taipei** (for later): no .tcs in the client; it has Taipei/Path/path_taipei.chpath + .signal (and
  trainPath), path traffic like the races' 0x21e (the client loads path_<city>.chpath for the city at
  0x4a8e60 mode 0; one traffic object, vtable 0x8cdd70: slot 1 = 0x2bd, slot 2 = 0x21e). Its cars are
  TrafficFlowControl block 5 (c_t_5_*). Its area numbers are not known (block 5 would be 100+: area.AREAS = 100
  and 0x2ab has 100 counts); check what the client sends in Taipei first.
- **Amber** (user question): the client draws it itself (0x41f840, per lamp: nodes T_light_R01 / Y01 / G01, +
  A01 arrow on 4-lamp signals, crosswalks T_light_stop01 / walk01). The 0x2c2 handler (0x5375e0) keeps state
  != 0 as 2 (go), else 0, and the message's time as the lamp's last change ([lamp+0x24], server tick ->
  client seconds); the lamp shows amber for 4 s after a change to stop and 1 s after a change to go. The
  agent sent time 0, so amber never showed. Now 0x2c2 carries the tick of the last change (City.state);
  cars stop for amber if they can comfortably, wait out the 1 s amber before green; red passes ~0.2%, amber
  ~4%. (In replay modes, [game+0xc4] 0xf / 0x11 / 0x12, the client runs its own 60 s cycle instead.)
- Open:
  merges at joints are not arbitrated (two cars can enter one lane together); collisions (0x220/0x223) are
  relayed between players but do not stop the server's car (the agent did not see them either).

## Session 7 (2026-10-14 evening): items, patrols, instant / daily missions, deliveries, launcher patches

- **Premium Package / 3 Drink Set** (category 49; user correction): not split into drinks any more. It stays in the
  drift item tab and acts as the EXP, MITO and Item Drink while held (items.PACKAGE / held_categories: holds(), play
  bonus, 0x5dd BonusUpdate flags). With a drink held too the effect counts once (item text: "will not duplicate the
  effects"). Bought again while held: the days are added (vshop.EXTENDS). tools/rewards_test.py step 3 tests it.
  (No package in the DB had been split by the old code.)
- **Patrol rewards** (user question: is there an item for completing a patrol?): **no**. The client's
  Instant_Client.tdf patrol rows have no mission item (column 12 n/a) and no reward group; World/InstantDrop_Client.tdf
  is only the dialog text per level: "There are no item rewards." (levels 4-7) / "Acquire a Lvl N part for every 50
  locations patrolled." (N = 7 at 8, 13, 19, ... 55, 60 at 56-66, **65 at 67-200**). The completion message 0x3e5 could
  carry items (client 0x514120: u16 count @0x1a, u32 InvenIdx x count @0x1c, each shown by name, 3 fit in the 42 bytes),
  but nothing gives any. RewardGroup.xlt has rw_patrol_moon / koi / cras / oros_omd / oros_roo / trans / giftbox
  ("Partypatrol_JP": Etc_Value 15 / 30 / 45 / 60 / 3 looks like a post count), but the US client and its tables do not
  name them: a JP event, not used. Now the 50 / 100 / 150 place drops follow the client's text
  (data.Tables._client_patrol_drops): nothing at 4-7 (2008 gave Lvl 7 parts), Lvl 65 parts (Lotus / T-bolt / Terra,
  i_c/a/b_000006) from 67 (the 2008 table stopped at Lvl 60). The 160th place keeps 2008's ig_n_F (V2-V5 car upgrade
  coupons). **Completing a patrol** now gives a placeholder prize (user): instant.PATROL_PRIZE = i_n_00003 Mittron
  Enhancer, listed in 0x3e5 (count 1, its InvenIdx; script-tested on NewChar). Emulator restarted 19:48 with all of this;
  not yet seen in game.
- **Item icons on pick-up** (user question, screenshot of the HUD): the client has an "items received" icon strip.
  0x2e5 TrafficItemEventAck (client 0x515e60): count 0 -> texts 10039 / 10040 (inventory full); else the item
  (TableIdx @4) -> sound, 0x6dae70 (HUD effect), 0x739f70(item, count) = chat line with the name (format 0x8ea66c,
  colour 0xfff29177) + [ui+0x3c0] 0x6669a0 (class ctor 0x6668c0, vtable 0x8e32dc, made at 0x55aa3a): queues the item
  ID (item info +0x74; name is +0xe4) in a list of 6; its draw method (0x6661b0) fades them out and draws each as a
  32x32 icon through [ui+0x388] (0x5c26f0: ID -> icon, 0x5c2800: by texture name; 0x5c11e0 draws). 0x3e5
  InstantRewardAck uses the same 0x739f70. **The queue only fills when bit 4 of [[0x973e40]+0x2b4] is set**
  ([0x973e40] = the network object, vtable 0x8cddd0, ctor 0x45d8b0, holds the server name @+0x218 and the character
  name @+0x2c4). Read live: +0x2b4 = 0 on both clients, so no icons are shown. The same word gates other things (bit 2:
  0x500700 / 0x7b7b56 / 0x799397; 0x1000 / 0x2000 / 0x4000 elsewhere). Who sets it was not found (only clears at
  0x49f403 / 0x49ffd0 / 0x6744ee; no indexed / byte writes); maybe never set in the US build. The 2011 "get item"
  notice dialog 3990000 (ID_GETITEM_NOTIFY_TEXT, text only) is another window (loaded at 0x61fbf0).
  **Tested (user, 2026-10-14): with the bit set by hand (/proc/PID/mem) the icons show on pick-up.** Now the launcher
  sets it (Launcher/common.go keepItemIcons: every second while the client runs, once the object has vtable
  0x8cddd0; Linux /proc/PID/mem, Windows WriteProcessMemory; `[client] item_icons = 0` turns it off). Data write
  only (ASProtect checks the code). Built, not yet run from the launcher.
- **Patrol prize, fixed** (user: wrong icon and name on completion): 0x3e5's item list is **TableIdx** (client
  0x514120 looks each up with 0x7172f0, as 0x2e5), not InvenIdx: the InvenIdx 1065 sent showed "Ch 03. Battle Ghost
  Ticket". The reward window itself (0x73ca10, [ui+0x164]) shows only exp and Mito; each listed item gets a chat line,
  a pick-up icon and a notice with count 1 (hard-coded), so the prize is listed once. emulator.ini **[patrol] prize /
  prize_count** (default i_n_00003 x1). Script-tested (x3 -> one stack of 3, listed as TableIdx 1001).
- **Usable items with a period** (user: the Mittron Enhancer was "already expired"): UseItemClient column 12 = period
  in server-tick hours (36 items: Mittron Enhancer / PLUS / DELUXE 24, Battle Ghost Tickets 167, crude parts 240,
  Halloween Drink 24, Summer Festival boxes 168, ...), column 4 = the expired form. The client shows expiry from
  XiStrMyItem @0x48 ExpireTick; only set parts had one, so these showed expired at once. Now setparts.period covers
  them (value-99 enhancers: 72 h, the user's guide, instead of the table's 24), ExpireTick = tick + period in CTIME
  (items made before: counted from CDATE), sent @0x48; timed items stack only with the same ExpireTick (stack_for,
  merge_stacks); the enhancing / auction checks use it (upgrade.expired(p, it)). new_item set the expiry before the
  INSERT (the UPDATE hit no row; set parts too): now after. **CDATE is UTC** (GetDate() in the container; the emulator
  runs on local time, MSK): ages use utcnow (the old 72 h check was 3 h early).
- **Server tick during a session** (user: do timed items run down?): SERVERPTICK only advanced at a login and a player
  kept their login's tick for the session (the client counts on by itself from 0x311). Now Player.tick is live
  (setparts.tick_now: last read SERVERPTICK + hours since its LASTDATE). Drift items (days from CTIME, real time) were
  already right.
- **Restoration Lubes, redone** (user: they go in the drift inventory and work on one part at a time, from the lube
  screen): the drift inventory window has a lube panel, dialog 3260000 (ID_INVEN_SETACTIVATE_*: name, held count, slots
  i_d_set_ch01 / 02 / _mito, title 10939 "Restore or Extend expiration time for Set Parts.", Buy / Use; window +0x870,
  made at 0x5fc064). Use (3260010; 0x5fb5bd) on the selected set part ([win+0x898], family = item info +0x4cc 1 Alpha /
  2 Beta) finds a held lube (uid 10439 / 10440; nation 7-10 also the _mito ones), confirms (0x2c8e47) -> 0x5f91e0 -> the
  held drift item of category 25 / 26 (0x7137a0) -> **0x1b0 ReplenishItem** (u32 part InvenIdx, u32 lube InvenIdx;
  0x803f20) -> 0x1b1 ReplenishItemAck (18; client 0x50f140). 2008 Cmd_ReplenishItem / XiCsCharInfo::ReplenishItem /
  XiCsItem::ChangeCTime(720): family check, run out -> tick + 720, else + 720; lube used. Now setparts.replenish; the
  lubes are no longer "Instant" (driftuse.instant returns False for them, so they stay after purchase). Script-tested
  (two lubes bought and held, an expired part -> +720 from now, a running one +720, the other part untouched, no lube
  -> 20024). The earlier version (at purchase, all parts of the family) renewed the user's 21 Alpha / 24 Beta parts
  until tick 400 at 20:04 (left as is).
- **tools/auction_test.py** now takes the seller as an argument (default DCLoverN, the second character on this machine;
  Newbie is gone; the character must be offline) and cleans up from a snapshot: only rows made by the test go, item
  states / stacks, car counters, money, mileage and earlier auction listings are put back (the old cleanup deleted
  all the seller's drift items, cars but car 1, and every auction row of both characters). Run 2026-10-14: ALL DONE,
  both characters' rows identical before and after.
- **Instant missions, 2011 offers** (user: "TAB to accept"; instant.py docstring): GlobalContent NewInstant = 1. The
  request house menu (dialog 280000) "Instant Quest" (280005) sends **0x3de InstantRequest** (u32 post, u32 flag 1;
  no handler until now) -> **0x3df** (u32 TableIdx, u32 a, u32 b; client 0x513c50) -> the call-sign notice (dialog
  760000, TAB button 760007, only with the player's "Show instant messages" option on, global 0x94d354) -> TAB ->
  mission dialog -> 0x3e0 (TableIdx, b, a). Pick: 2008 XiInstantTable::InstantRequest (roll 0-99 vs the running
  percent sum, column 8), classic rows (columns 3 / 4 = 0), the level band of the highest start not above the level
  (the 2011 table ends every band at 1000). 2011 context rows 124-146 (column 3 OMD / ROO, column 4 City /
  Battle_Room / Battle_Lobby / Chasing / QuestFail5, formula rewards): **City rows offered by the server every
  [instant] city_offer_minutes** (5) while driving in the city with no mission (instant.city_offers); the other
  contexts not yet. Formula rewards (INT(({Level}^1.7)/5+10) ...) evaluated (reward_exp); formulas with other values
  give 0. 0x8b InstantEvent is a 2008 PR event ("HAPPYBEAN"), unrelated. Script-tested; not yet seen in game.
- **Daily mission and Mission Tokens** (`native/game/daymission.py`, docstring = everything): today's mission (one
  day_mission row 80-90 per day for everyone, [daymission] reset_hour), 0x488 at login (TableIdx + today / total /
  run + attendance 0s), 0x3e2 at Suyeon -> mission item taken (mission_item rows), token i_n_00049, 0x489 (1, 0, run,
  total / 7), the row's exp / Mito (0x3e3, 0x3e5); counters in SKID_PLAYMODE_TB 'DAYMISSION' (TRYCNT today, WINCNT
  total, POINT run; 2008 GetPlayModeList -> SetDayEvent). Day missions are kept apart from instant missions
  (session 'day_mission'). Token exchange 0x48a (TokenBook.xlt row) -> price taken, gifts given (+ 0x2e5 each), 0x48c.
  Not done: attendance / day mileage (0x48b, 0x494, 10913 / 10917), 0x488 at the day change for players online
  (2008 XiDayMission::OnTick). Script-tested on NewChar (mission 80, token, refusal, exchange row 0 / 1).
- **Deleting drift items** (user: equipped items that cannot be taken off could not be deleted): 0x4bb
  DropVisualItem (u32 TableIdx, u32 InvenIdx) had no handler at all. Now vshop.drop_visual_item (2008
  Cmd_DropVisualItem: off the car first, then deleted) -> 0x4bc (same), 0x4b2, 0x5dd, stats, 0x63 / 0x425 for the
  car; any slot (paint / neon / tint too); auction items refused (20026). Script-tested (a tint on NewChar's car).
- **Delivery (part-time job) markers** (user: no points on the map, the arrow pointed back to the station): 0x144
  ArbeitStartAck's third u32 is the **number of delivery places** (client job object +0x2c, set by 0x74ac10 from
  0x74f2e0; the map loops 0x62eb60 / 0x632af9 draw posts k < +0x2c not yet done, row + 0x21f8 = the resolved posts),
  not the completed count: the emulator sent 0. 2008 XiCsArbeit::XiCsArbeit 0x5c2bc0 sets 5 (recorded 2008 traffic:
  5). Now jobs.PLACES = 5, completion after 5 distinct places in any order. Live check (/proc) of the running job:
  Navigation option 0x94d370 = 1, hud+0xec4 = 1, job state 2, +0x2c = 0 (the cause).
- **Delivery cargo model in the wrong place** (user screenshot: the pamphlet drawn top left, the box is on the
  right): the cargo is a 3D model drawn every frame by hud 0x6d26b0 -> 0x6eab30 (model by the job ID's number, also
  sent with 0x801740) through the camera [hud+0x114], created once with a fixed viewport x 4..176, y 27..149
  (0x6d221a: 0x7c0670(cam, 4, 27, 176, 149, 1, 0.5, 1)): the classic HUD's box. The 2011 ADV HUD (main_ui_type 1)
  has the box (dialog 700000, control 700004 "delivery item base") right-anchored at x 849..1009, y 105..225 (1024 x
  768). The camera's viewport (NiRect left, right, top, bottom as screen fractions) is at cam + 0x114 (camera vtable
  0x8c9c48; screen size 0x94d444 / 0x94d448). Moved to ((W-175)/W, (W-15)/W, 1-105/H, 1-225/H): the model sits in
  the box. **The launcher does it** (Launcher/common.go keepPatches / fixCargo, with main_ui_type = 1, every second
  while the viewport still has the classic values; the item-icon flag is in the same loop). User confirmed the delivery
  points on the minimap after the 0x144 fix (screenshot).
- **Mouse cursor** (user: the 2011 client showed a pale hand; Drift City Remastered on the same machine the coloured
  blue glove): every client (2011, 2016 Dev Ed, Remastered) has the same Data/GameUI/cursor files and loads them with
  LoadCursorFromFileA (2011 0x4406d0, handles at 0x9487d0..0x948810: all loaded, read live). The cause is the host:
  Wine draws colour cursors with libXcursor, the client is 32-bit and SteamOS has no 32-bit libXcursor / libXrender
  (/usr/lib32), so Wine fell back to two-colour cursors; Remastered runs from a Steam shortcut (default proton_11)
  inside the Steam Linux Runtime, which has them. **The launcher now links the sniper runtime's i386 libXcursor.so.1 /
  libXrender.so.1 into <prefix>/lib32 and puts it on LD_LIBRARY_PATH** when the host lacks them
  (Launcher/launch_linux.go cursorLibs). A first try re-saved the .cur files as 32-bit: the transparency broke (user),
  reverted (originals, byte-identical, also in Emulator/client_backup/cursor/). **User-confirmed: the glove shows.**
- **Delivery leaderboard** (user: no names / times): the job list's Rank[3] / MyRankUnit[6] were zeros and 0x153
  ArbeitRankList (u32 job, u32 page, u32 date type) had no handler. Now jobs.py keeps SKID_ARBEITREC_TB (the 2008
  table and its SQL Server queries: one row per character and job, AID = TableIdx, the best TIME in ms), fills the
  list entries (XiStrArbeitInfo, PDB layouts), answers 0x153 -> 0x154 (10 per page, 2008 Cmd_ArbeitRankList) and
  sends Best / Cur rank units in 0x146. Date types 0 all, 1 month, 2 week, 3 last month, 4 last week, 5 today (our
  mapping). Script-tested on NewChar (61.5 s, a slower 70 s kept the record, 55.25 s replaced it).
- **Paint that cannot be discarded** (user: Xerender's Cross): paint 127 on car 1 is a 7-day paid paint (until
  2026-10-19); the client itself refuses to discard paid items with time left (text 10455), nothing reaches the
  server. Not changed.
- **PassiveAssist DriftBooster on the car** (user: equippable, effect only while on the car, can come off):
  driftuse.EQUIP_PASSIVE (passive_a_00118 / 00247); vshop.fits lets them on; passive_follow / convert_bundles leave
  them; records.VisualItem.assist_slots sends their assist only while on_current_car (Player.apply_paints: state 1
  on the current car; select_car resends them when it changes). The client offers Equip for them (user's attempt,
  refused by the old code). Script-tested (equip: slot 146, unequip: none).
- **PassiveAssist icon in the Visual Item tab** (user, 2026-10-14 night: equipped, but no icon in the list): the
  inventory's Visual Item tab (dialog 4770000, 8 visible rows of a 19-slot array at window +0xb4) is filled by
  0x7139d0 (the car's state-1 drift items by slot), slot = 0x70edd0(category) via byte table 0x70eedc: slots exist
  only for categories 1-13, 30, 31, 32, 38, 47, 48, 52; category 41 -> case 20 = -1, so the client never lists it.
  Not fixable from the server. The launcher (user's choice) writes byte 0x70ef04 (category 41) 20 -> 13 = the
  rental slot of category 30, once logged in (code section: after ASProtect's start check; `[client]
  passive_slot`). Other users of the slots: the car look builder 0x536840 ignores 30 / 31 / 41, the stat sums
  (0x61355f, 0x728ff4) add the item's Mk.2 points (0 here); assists are applied by their own loop (no double).
  **Not yet tested in game** (if "Error: 45" appears, set passive_slot = 0).
- **Paint S15 cannot come off** (user, 2026-10-14 night): glossy paint 32, FIXED_SLOTS rule kept (user's choice);
  drift items cannot be auctioned in the US client anyway (no tab).
- **Delivery medal** (user: no medal shown after a gold run): 0x146's result is 1 gold, 2 silver, 3 bronze, 0 none
  (client 0x73d050, texts 10134-10136); the MEDALS index (0 = gold) was sent. jobs.MEDAL_RESULT.
- **Delivery / patrol item rewards** (user, 2026-10-14 night: tables, every job x medal and every patrol, with a
  count; no rewards filled in yet): `Emulator/delivery_rewards.txt`, `Emulator/patrol_rewards.txt` (rewards.py, read
  again when changed; `python3 -m tools.reward_tables` rewrites them keeping filled lines). 0x146 shows the first
  item (count @0xc, TableIdx @0x10), 0x3e5 lists up to 3. emulator.ini [patrol] prize removed (the placeholder
  Mittron Enhancer is gone). Script-tested on NewChar.
- **Car auction with drift items on the car** (user: the client asks text 11147 "Equipped items ... removed
  permanently", the server refused): client check 0x71ab80 (parts -> refuse; drift item with 0x72c770 true, VShop
  row +0xfc > 0 = "CC items" -> refuse; others -> the question, then 0x6a6). Now the car's state-1 drift items are
  deleted at registration (auction.auction_car_on). In game: Paint S15 + passive_a_00247 were deleted that way.
- **Car keys: NRANDOM = the CarID** of the key's car (the 2008 server's keys have it; the client finds the car for
  the key tooltip by it). Emulator keys (dealership, auction, gift cars) had 0: no tooltip (user). new_item(random=),
  items.link_keys at login fixes old ones (a car of the key's type no other key names).
  Cars without a key get one at login (2008 XiCsCharInfo::CheckCarKey -> CreateCarKey; the key item = VehicleList
  "File Name"): characters created by the emulator had no key for their first car (user: DCLoverN's Metro; made,
  InvenIdx 113). DCLoverN: Rookie Missions 1-5 completed with tools.complete_quests (user, 2026-10-14).
- **Stickers private** (user: a "My Sticker" upload was seen by DCLoverN, who also got a remove button): category
  13 uploads -> STICKERTYPE 1, lists / search show them only to the creator and GMs (adminlist). The client's remove
  button follows the category (the server refused the delete anyway).
- **0x327 SetMyDeliveryItem -> 0x328** (u16 serial, u16 age, u8 cargo; client 0x516b50): the cargo number goes into
  XiPlayerInfo @0x95 with a new age; other clients draw a_i_%04u above that car (0x6eac50). Was ignored.
- **City ids: 1 Moon Palace, 2 Koinonia, 3 Oros, 4 Cras** (client: 0xc80 names city 3 for the Oros post
  post_4rd_00506, then joins area 52 = (city - 1) x 24 + 4 + channel); the world / table numbering (post_3rd, PVP_map3,
  Laptime3 = Cras; post_4rd, PVP_map4 = Oros) is different. The traffic agent's city paths had 3 and 4 swapped (Oros
  ran on Cras's 3 paths: almost no cars; user): traffic/agent/pathIndex_3 = Oros (6 paths), _4 = Cras (3);
  Server2008/tools/make_traffic_paths.py CITY_OF_WORLD. The lap-time types 6-9 keep the world numbering.
- **Rush GM commands** (user: rushtime / rushtimenow did nothing): the 2008 names (ProcessGameStream) work for admins,
  also with "gm" in front: rushtimenow / rushtime [HUV type] [course] (in 5 s / 305 s, notice at once), getrushtime,
  rushend (rush.gm_command).
- **Entering another city** (user, 2026-10-14: did not work): the 2011 client asks 0xc80 CityLeaveCheck (u32 city,
  char[255] arrival post, char[255] post to face) and waits for 0xc81 (u32 result 1 + the same bytes; client
  0x519310) - no handler until then (position.city_leave_check). What the client sends after it is not seen yet.
- **Team races** (user, 2026-10-14: zero points for both teams; the team button did nothing): a team is the seat's
  parity (2008 BS_Room::TeamCount / ChangeTeam). 0x26f RoomChangeTeam (u32 room, u32 serial, u32 team) -> the
  member moves to a free seat of that team, 0x26d to the room (rooms.change_team). Team points in 0x1ec (@4 / @8)
  and each entry's point field for type 0x28 or room type bit 0 (2008 PvpRaceResult): finishers only,
  GetTeamPoint = T[rank] - T[racers + 1], T = 40 37 34 32 30 28 26 25 .. 1 0 (.data 0x700c0c). Not yet seen in
  game. Team gate rewards: `Emulator/team_gate_rewards.txt` (s_fTeamReward[clean][8][32] from the 2008 exe, rows
  for 5-16 racers via FixedRank, the normal file's format) for team rooms (type & 1 or & 8) with more than 4 racers
  (rooms.team_gates); up to 4 racers the normal table, as the 2008 Gate (SmallGate). What Team Boost (7) does for
  the teammates is the client's (not checked).
- **Aero kit not shown to other players** (user): the generic aero sets (pc_Aero / pc_Aero2 / pc_AeroMK2..,
  category 6, index 0) carry the car's own model in the item text after the 10 reserved characters: car type (3),
  style (1), VisualItem UniqueId (5); misc.aero_model puts that model's index in XiVisualItem's aero slot (was 0).
- **Race repair message** (user, 2026-10-14: missing once, then showed properly; nothing changed). Seen while
  looking: barea C>S **0x2d5** (u32 gate number, u32 tick, u32 n, n x a RaceState record; sent after a gate's 0x1ee)
  has no handler; the client also handles an S>C 0x2d5 (12 bytes, 0x50b760, queued only during a race). Unknown use.
- **City instant mission offers never came** (user: only HUV calls, which the client makes itself): instant.city_offers
  skipped players unless position state == 2, but the client saves 3 in the city (0xa2): now >= 2, and a skipped
  offer is logged ("city instant offer skipped: ...").
- **Parts box from the drift shop** (user: an unusable drift item; should be 10 inventory boxes): i_d_partsbox
  (category 19) gives 10 x i_n_00027 Parts Box at purchase, as the 2008 Cmd_BuyVisualItem (PartsBoxID); old drift
  rows are converted at login (driftuse.AT_PURCHASE / convert_bundles). Script-tested on NewChar.
  Using one: the 2011 client sends **0x1a6 PackItem** (u32 part InvenIdx, u32 box InvenIdx) -> 0x1a7 (the same 8
  bytes; client handler 0x50f060 reads nothing) + 0x192; no handler until then (user: boxes did not work). Any
  hyper part (grade H), tradeable ones too (the client offered si_B_I02, tradeable). items.pack / pack_item.
  **All H parts need a Parts Box** to change hands (user): items.needs_box (grade H or untradeable) / boxed, used by
  auction.item_refusal (20062) and mail.sendable (mail refused boxed parts before and checked no tradeability).
  Equipping a boxed part (0x199) takes it out of the box (BOX 0; user: the box stayed).
  **H parts come off only with a Heat Treatment Kit** (user), one used (items.needs_heat: the part's grade H, or an H
  docking on the slot); without one 0x19b answers a text error. Script-tested on NewChar.
- **Delivery markers + "return to the agency?"** (user: Remastered draws a light pillar with the cargo; no window to
  go back after a job): both need the 2011 flag **InstantMission.ImproveQuickService** (byte [net+0x287] bit 0; the
  client's content flags are at [net+0x268], InstantMission @0x280), sent 0 until 2026-10-14: 0x6e5a77 draws the
  delivery point with 0x6dd820 (quick_post_fx_01.nif: q_cylinder_yellow + twinkles) + 0x6dd670 instead of 0x6dc8e0
  (cylinder.nif, the red beam), and 0x5855a0 / 0x57f7bc ask text 11562 "Would you like to return to the agency?"
  (Yes -> 0x312 QuestPosition, quests.py -> 0x313). Now in handlers/game.NEW_FLAGS. Not yet seen in game.
  ([net+0x280] & 0x180 = InstantMission.DayMission, sent 1: the loader 0x6ece50 picks i_post_00008 / 00007 by it.)
- **Daily mission clear notice** (user: no "complete" sign): the client shows "*** Daily Mission Clear! ***" (10912,
  0x70b6e0) and "(Clear)" (10938) in the list itself: type 0xb (bring an item) on each 0x192 (0x70c970, inventory
  count >= goal), quick_grade (0x19) from 0x146's result through 0x70ba30 (was broken by the medal value bug). Our
  0x489 opens Suyeon's "DayMission_Complete" dialog (GlobalText 1126 "Collect Tokens and exchange them with items
  listed above.", NPC talk window [ui+0x37c], 0x6b60e0). 2008 order: 0x489, 0x192, then 0x3e3 / 0x3e5 (ours: 0x192
  first). DCLoverN (22:25, 3 coins held from login, so the goal was met at the mission's start) saw no completion
  message; user screenshot: the "Instant Mission Complete" banner and the result were missing). Cause: 0x3e3 was
  sent before 0x3e5; 0x3e3 frees the client's mission object (0x70d7c0) and the 0x3e5 handler (0x514120) finds no
  mission (0x70b820) and skips exp, banner and result window. 2008 order (Cmd_InstantComplete): 0x489, 0x192, 0x3e5,
  0x3e3; now so for day missions and all instant missions (instant.py). Not yet confirmed in game.

## Session 6 (2026-10-14): new folder layout, client launcher, Auction House

**Layout (user request, 2026-10-14):** `Server/` is now `Server2008/` (the 2008 stack + research tools; not needed
to play). These notes moved to `Emulator/docs/`; older entries below still say `Server/...` (read `Server2008/...`).
The emulator is self-contained: `Emulator/server_data/` (copies of the 2008 files it reads; `[native] server_data =
server_data/tables`, the code reads `server_data/..` for the .txt files), `Emulator/traffic/` (since session 9 `Server2008/traffic_agent/`; TrafficAgent.exe +
data under Wine, container `dcemu2011_traffic`, `start.sh` writes TrafficAgent.ini's Host), `Emulator/db/` (schema),
`Emulator/docker-compose.yml` (project dcemu2011: db, traffic, db-setup; same volume driftcity2011_mssql-data),
`Emulator/launch.sh` (all / server / db / traffic / emu / emu-bg / client / stop / restart-emu / status / logs /
setup / init-db). The race traffic engine is `dcemu/native/tw_traffic.py` (copy of the TW traffic_server.py).
The 2008 ZoneServer is gone from the running setup: UDP 11400/11401 has no listener now (the native area answers
time sync itself; nothing seen depending on UDP so far).

**Client launcher** (`Launcher/`, Go, `build.sh` builds in the golang container -> `Client/DriftCityLauncher` +
`DriftCityLauncher.exe`; settings `Client/DriftCityLauncher.ini`: address, `display = windowed|fullscreen` (also
`--windowed` / `--fullscreen`), main_ui_type, Proton or Wine). Linux = the Python launcher's method (ptrace hardware
breakpoint, only on its own descendants). Note: Go's syscall.PtraceGetRegs returned zeros here: raw PTRACE_GETREGS is
used. Windows: a Win32 debugger made ASProtect hang (tested under Proton: the client never unpacked), so the Windows
build uses no debugger: Read/WriteProcessMemory, the address, then the GameGuard object's vtable swapped for the
no-check one (also tested with the Python launcher with the breakpoint skipped: client runs). Tested under Proton
only, not on real Windows. Windowed on Windows needs admin once (HKLM).

**Client change tried and reverted:** GlobalContent.xlt `AuctionVSItem = 1` (user asked for the drift item auction
tab): the client then hides its column-title buttons (1220010..16) and shows a second set (1220030..38) that the US
game.nui has as empty placeholders, so the titles went blank (user screenshot), and there is no drift item tab in the
US (or Dev Ed) layout anyway (only ID_AUCTION_CHK_ITEM / CHK_VEHICLE). Restored `Patch.000.battleroomai0`
(AuctionVSItem = 0). Client 0x5c8050 (tab change): with AuctionVSItem = 1 (or the drift tab) it clears bit 2 (shown) of
the title buttons [win+0xc8..0xd8] (window = [[[0x948844]+0x158]+0x338]); read live: 0x25 hidden, 0x27 shown. A client
started before the revert keeps them hidden until restarted. Drift item auction given up for now (user). Column titles are images in ui_contents54.dds (Data_US/gameui/uitex.agt tex\D.ntx; 2011 ntx
entries: 64-byte name "x,y~x2,y2_file.dds", then a DDS).

### Gotcha machine, rewards (2026-10-14)

- **Gotcha** (`native/game/gotcha.py`, docstring = everything found): Etc.ShowMainButtonGotcha / Etc.GotchaSeason sent
  from `emulator.ini [gotcha]`; request 0xdac (24 bytes: currency, client price, machine car/parts, client G Coin, 0,
  season), sent from the dialog [ui+0x320] (0x66dcd2) through [net+0x158] (= the game connection: it also sends 0x6a,
  0x1b2, 0xfa0). **The client has no handler for an answer** (no 0xdad in the image, not in the handler table, not in
  data): answered with the rewards' item / car / money messages + 0x579. Rewards rw_gacha_{car|parts}_{mito|cash}_NN
  (RewardGroup). Script-tested; **not yet seen in game** (does the dialog wait for something?). Car parts / key parts /
  boxes it gives: **prize window** = 0x89 NotifyEvent type 23 (item TableIdx @6) / 24 (drift item @6, days @0xe)
  (client 0x51c40f / 0x51c447 -> [ui+0x324] 0x670b70; without it the window opened empty: user screenshot).
  **Combining** (gotcha.combine): 0x1a1 ItemUse on a key parts item (kind gacha_key): one of each part of its column-4
  group (rw_*_compound_NN: i_n_gacha_A..D; old keys name missing groups: that car's i_n_<car>_A..D) + the key are used
  up -> its column-3 car box (giftbox_car, opened by 0x1a1 like gift boxes -> the car via 0x62). Script-tested.
- **Car gift boxes** (user: the Serpens box gave only the key): a reward row whose item is a car key (UseItemClient kind
  car) gives the car (type = the key's value column 9, grade = Etc_Value) + the key; the car becomes the current one
  (sent as 0x56 BuyCarAck, as a purchase). RewardGroup rows keep Etc_Value now (driftuse.groups / roll: 5-tuples).
- **Timed car upgrades** (category 38, i_d_u_11..18 "V2..V9 car upgrade (7days)"; user: could not be equipped on the
  V3 Serpens): equippable now (vshop.EQUIPPABLE); while on a car and not run out the car counts as that grade
  (VShopItem Sub 8001 = V2 .. 8008 = V9; Car.boost_grade / shown_grade: car record, base stats, battle zone section
  check). Recomputed in Player.apply_paints (login, every drift item change); expiry mid-session shows at the next one.
  Only on a car one grade below the item (V4 item on a V3 car; user rule; vshop.fits). The client shows the grade
  from **0x63 ChangeCarGrade** (u32 car, u32 grade; client 0x510df0: sets the car's grade and Mitron values), sent
  after a drift item change (vshop.after_change) and at login for boosted cars; 0x425 alone did not change it (user).
- **Aero kit Mk.2** (`native/game/aero.py`, user: did not work): 0x4bd SetAeroStats (4 x u16 points = 60, 2 x u16
  options 1-4) had no handler -> 0x4be (InvenIdx, result 1) + the item with its text's 10 reserved leading characters
  set to "PPPPPPPPOO" (the client offers the window only while the text is empty / starts with a space, 0x5fff8d).
  Points -> equip stats in the window's order speed / accel / durability / boost (user-confirmed). Options = the
  window's tick boxes (layout C="3470000" in game.nui; its picture labels them): option 1 "For Battle Zone Only" box
  1-4 = a_00179..a_00182, option 2 "Field or Undercity Only" box 1-4 = a_00183..a_00186 (0 = group disabled: bumper /
  intercooler kits); sent as assist slots (aero.mk2_assists). (game.nui must be decoded with errors='replace': iconv
  stops early and loses the second half.) The **tooltip** reads XiStrMyVSItem @0x44 4 x i16
  speed / accel / durability / boost (client 0x658bb2, struct + 0x4c..0x52) added to the table bonus: the kit's points
  are sent there (records.VisualItem.assist_slots); with zeros there the tooltip showed another kit's values (user).
  A bought Mk.2 kit is not put on the car (vshop.buy_visual_item): set its points from the drift inventory first.
- **Drift item bonuses:** VShopItem "Bonus Assist" (60 items: booster max speed, parts drop chance, ...) now in the
  item record's assist slots (the client applies them for items on the current car; the 2008 server's drops did not
  read assists); Bonus Speed/Crash/Accel/Boost only while the item has not run out.
- **Car colour 0** (user: paint on one Shadow showed on all): gift box cars had colour 0 and the client kept the
  shared model's last paint; now the dealership default 0x01010102 (cars.DEFAULT_COLOR), old ones fixed at login.
- **Timed V upgrade destroyed** when a real upgrade (0x5b) reaches its grade (cars.drop_spent_upgrades; user rule).
- **Lap Time traffic** (user: none): the client drove a different lap track than the map named in 0x528 (map 70 Moon
  Palace sent, the client raced Cras' 72, probably the player's current city), and the traffic engine ran on the named
  track far away. Now the traffic follows the lap track whose start is nearest the car (race.RaceTraffic.lap_track_at).
  Near the start the engine keeps cars 350 m away for 30 s (as in races).
- **Friend "play together"** (user: "You cannot do this with a friend." 10202): the 8-byte place in XiStrFriend
  @0x60 and 0x297 @0x1ba was always kind 1 / the city number. Now social.place_of: kind 1 city, 2 room waiting
  (client joins with 0x1d7), 3 room racing (client opens the lobby on it), 6 Lap Time (0x1bd -> laptime.enter);
  u8 section / class-1, u16 room id, u32 room flags (0x7000 bet rooms: Mito check). Client 0x5c04cb / 0x5bfc20 /
  texts 0x63a9b0. Not yet confirmed in game.
- **Drinks won** (scratch cards, boxes) while one is held add their days (driftuse.give_drift_item, vshop.EXTENDS).
- **Premium Package / 3 Drink Set** (category 49, user): gave i_d_drk_01/02/03 and were used up. **Replaced in session 7**
  (user correction: the package stays a drift item and acts as the three drinks).

### Auction House

- **`Emulator/dcemu/native/game/auction.py`** (docstring = every rule and layout): items, cars (`emulator.ini [auction]
  cars`), drift items (`drift_items`); 2008 rules (Cmd_Auction*, XiAuctionMgr / XiAuctionCarMgr, XiCsCharInfo::Auction*),
  2011 layouts from the client handlers (0x51b390.., senders 0x7f3b00..0x7f5800, auction window 0x5c8000..0x5cb000).
  Tables SKID_AUCTION_TB / SKID_AUCTIONCAR_TB / SKID_AUCTIONMILEAGE_TB (2008) + SKID_AUCTIONVS_TB (made on first use).
  Listing expiry: `[auction] days` (7; 2008 CalcPeriod), then state 3: out of the public lists, the seller takes it back
  with Cancel. Fees at registration ([auction] item_fee / car_fee / drift_fee; item and drift fees also sent as
  Main.AuctionCommission / Main.AuctionVSCommission, the client shows them). 0x708 at login = car auction open.
- The registered item / key / drift item stays with the seller in **state 4** (the client looks listings up in its own
  inventory). Guards added: sell / drop / use / equip / drift use refuse state 4; select / upgrade / equip on a car on
  auction refused (Car.on_auction -> XiStrCarInfo AuctionOn).
- **Hyper parts** (user): tradeable column False (ItemClient col 17 / UseItemClient col 15 = ItemInfo.tradeable) ->
  only with a Parts Box: 0x1a3 with an Open Part Box (i_n_00026) on an H part sets BOX = 1 (items.item_use_ex); the
  buyer's copy comes out of the box (2008 AuctionBuy clears it).
- Guesses: the 2011 XiStrAuctionUnit's new u32 @0x18 (the client prints it in list rows; sent: days left), the drift
  item entry layout (66 bytes; the client reads the text @8, period @0x32, start time @0x36).
- **List filter** (user: a registered item did not show): the client's filter tables are {label[32], value}: 0 = All
  Items; items 1-4 parts, 6-10 option parts, 11-14 docking parts, 5 General Items; cars the grade; drift items
  VShopItem Main. First version read them shifted and filtered Type 0 as speed parts. Fixed (auction.type_fits);
  user: works.
- **Stacks** (user: a bought OMD Gold Coin did not join the 3 held): auction_buy now puts usable items on a stack
  with room (items.stack_for, which also skips state-4 items now: a shop purchase could have joined a listed stack);
  login merges split usable stacks (items.merge_stacks).
- The earlier "UI stuck" report went away with the filter fix (user: the auction house works properly now).
- Script-tested against the DB (scratchpad auction_test.py: register, box, split, lists, search, buy, own-buy refusal,
  complete, cancel, expiry, cars incl. resale refusal, drift items); **not yet seen in game**.

## Session 5 (2026-10-13 evening to 2026-10-14 00:20)

**Session 5 in short** (2026-10-13 evening to midnight; every item has its own entry further down). Hand-off
kit and the list of what the user confirmed / what is still unseen in game: `../Handoff/README.md` section 4.
- New modules in `Emulator/dcemu/native/game/`: `docking.py` (combine 0x1ac, docking items, white / purple /
  letter bonus; odds in `Emulator/docking_chances.txt`), `upgrade.py` (enhance 0x19d / 0x1ae, repair 0x1b3, the
  bonus gauge = 0x89 type 37, enhancer expiry), `setparts.py` (set parts, expiry by server tick, set bonus,
  Restoration Lubes), `convert.py` (0x1aa, Enhancement Formula), `mail.py` (messages; emulator.ini `[mail]`).
- `records.Item.encode` is the 2011 XiStrMyItem (0x5c bytes: ten assist slots @0x10, Box @0x38, level @0x40,
  bonus @0x44, ExpireTick @0x48); `VisualItem` carries assist slots @0x4c (PassiveAssist drift booster).
- Communication Zone: Main.Letter = 1 opens it; XiStrFriend's place is 8 bytes @0x60 (kind 1 = online), serial
  @0x6c; whisper 0x94; party member info ends with the car's V grade.
- Reply order matters in the parts shop (ack before 0x192; 0x1af before the Booster's 0x4b2), else the client
  leaves Exit / Modify disabled.
- Method that worked: grep a linear disassembly of the client image (`Handoff/scratchpad_session5/sweep.py`)
  for message types and struct offsets; read the running client's memory when a field's place is unclear.

## State at the end of session 4 (2026-10-13 afternoon)


**Session 4 in short** (the long 2026-10-13 session; every item has its own entry further down, most under
"Native game, batch 2" after "Drift shop", and in `BATTLEZONE.md`). Every service is native; the user plays
with two clients (admin/admin: Xerender, level 90; a second test account: Newbie).
- User-confirmed in game: battle zone rooms and races with two clients, gate rewards (`Emulator/
  gate_rewards.txt`), spectators, Real Match (server-chosen car, schedule), Lap Time, friends, parties
  (invite / join / kick), chat, stickers (upload, attach, images, Sticker Glue limit), other players'
  looks (XiVisualItem slot table).
- Done and script-tested, **not yet seen in game**: Misc tab drift items (`native/game/driftuse.py`:
  bundles, Mito prizes, extensions, gift boxes, scratch cards, lucky bags, Name Change Kit), drink / Fuel
  Booster effects, the coupon book (`coupons.py`; the 2011 counter layout), dealership purchase
  conditions (Etc.NoviceAdvUI2nd = 1), community window (BattleZone.Friend = 1), party combos
  (`native/area.py` group messages), the "kicked" party message.
- **Misc tab items were put on the car** (user, 2026-10-13 evening: a bought Expand inventory did not show up as a usable drift
  item): vshop.buy equipped every bought item that "fits" (no car list = fits all), so drift items got STATE 1 + CARID.
  The 2008 VisualItemCategory::IsEnableEquip (0x5eb170) equips only categories 1-13; now `vshop.EQUIPPABLE` = 1-13 + the
  2011 looks 32 / 47 / 48 / 52, drift items get no car; old rows are fixed at login (driftuse.convert_bundles). Also as
  2008 GetVisualItem: buying a drink / booster / glue (vshop.EXTENDS) while one is held adds its days to it. Not yet seen in game.
- **Paint is one slot and cannot come off** (user, 2026-10-13; client texts 11325 / 10957 / 11607: a new paint makes the
  old one disappear, also glossy over normal and the other way): paint (1) and glossy paint (32) share one slot
  (`vshop.FIXED_SLOTS`; neon (2) and window tint (3) the same, each its own slot, user 2026-10-13); a new one on the car deletes the old row (0x4b2 state 2), 0x4b7 unequip of a paint -> ItemUnEquipFail.
  At login `driftuse.one_paint_per_car` keeps the item of each such slot on each car (or puts the newest back on) and deletes the rest.
  The Expand inventory fix above was seen working in game (19:07: bought, used, HANCOININVEN 1).
- **Lottery bundles** (user, 2026-10-13: scratch cards must become inventory items used through the scratch UI):
  "Lottery (1/5/11)" / "ST Lottery" (VisualItem value "Normal 11" / "ST 5") name no item; the shop lets the player pick
  a car's card and sends "<card's VisualItem UniqueId> <count>" as the item text ("10829 11" = Serpens).
  `driftuse.parse_value` resolves it to the card's inventory item (kind lotto) x the bundle's count; buy refuses a
  bundle with nothing to give before paying (a lottery without a pick). Seed Parts bundles: VisualItem says
  "i_n_seed_S", ItemClient "i_n_Seed_S" (kind craft_up, for the parts shop's combine section): item ids in bundle
  values are matched ignoring case (`driftuse.item_named`). **Combine / upgrade (0x19d UpgradeItem, 0x1aa ModifyItem,
  0x1ae, 0x20b, Alchemy 0xe74..) has no native handler yet.** Earlier purchases convert at
  login (ITEM_DATA keeps the pick). The scratch UI (0x5aa / 0x5ac) is not yet seen in game.
- **Docking points, from the user's guide** (`/home/deck/Documents/Parts shop`, a player guide to the parts shop):
  docking needs a seed; without one, 3 parts make the next higher part above their average level, also into the
  next grade (N 25 -> S 31; up to level 70; user report: 1 + 7 + 25 was refused when the highest level was used). A docking item has its own
  white (base) + purple (bonus) points, added flat when docked: the client's item value 0x72c9c0 = table value
  (0 for docking) + record @0x44 + NRANDOM @0xc. White from the parts' base (table + random; avg 34 -> best 21,
  steps of 5), scaled by the random grade letter; purple = the parts' enhancement .. +5. White is stored in
  SKID_ITEM_TB.BOX (records.Item.encode sends it @0x44). The table's docking_p % is not applied (the % text
  and the tooltip's "acceleration +10" are client table quirks). Docking items made before have 0 points.
  **Corrected with StrategyWiki "Drift City/Docking Parts"** (cloudflare-blocked; read via web.archive.org id_ URL):
  docked = white + purple + hidden, hidden = the docked part's base x the letter's docking_p %, rounded down (fits the
  wiki's measured tables); white ranges N 0-19 / S 12-27 / H 18-31, independent of the letter; letters A-K, A most
  common. Letter odds and N / S white rates guessed.
  **Purple and Hyper white, from the user's video** (`~/Downloads/Drift City Remastered Dockings Guide.mp4`; frames via
  ffmpeg): the tooltip shows white as "Speed + 25" and purple as its own line "Docked Parts Points +12p" = the docking_b
  assist (a_00154.. = +1..+25): stored in ASSIST_A, sent as XiStrItemUnit.AssistA @0x10 = Assist_Client row + 1 (2008
  XiAssistTable key). Hyper white = measured ranges (docking.white_range: sum(base // 5) - 21 = t, 21 + t ..
  27 + ceil(4t/3)); letters N A-H, S A-J, H A-L, odds A ~25 % decaying x0.75. The video's "Dock Letter stats" table
  (Hyper A 1 .. L 23) is from Drift City Remastered (modified server); the client's docking_p % is kept.
  **XiStrMyItem @0x28 is an assist slot in 2011**, not the 2008 ExpireTick (user screenshot: every part showed a
  random purple assist = the tick sent there, e.g. 4 -> a_00182 battle option, 17 -> a_00077 +14 accel). Now 0.
  **Heat Treatment Kit** (user: it removes the part as well): a slot with an H docking (OH) comes off only with a
  kit (i_n_00025, kind heattreatment), the part and its docking together, one kit used (items.take_off), by 0x19b
  (until session 13 also with a kit held; now only) 0x1a3 ItemUseEx (dest part / docking, src kit, car -> 0x1a4; 2008 used it for the Parts Box on
  hyper parts, not native). Swapping H dockings needs no kit. Not done: scorched hyper parts (i_*_b) in general.
  Assist kinds (client table @0x93ee..): docking_b = 31 (flat), docking_p = 32 (formula 0x720711).
- **XiStrMyItem 2011 layout** (client tooltip 0x5c9370, record at struct + 0x52; user screenshot: level / gauge sent
  @0x20 / @0x24 showed as purple assist lines): @8 stack, @0xc random, @0x10..@0x34 ten assist slots (row + 1),
  @0x38 Box (parts box icon + untradeable), @0x3c ?, @0x4c Belonging
  (guess), @0x40 enhancement level (< 0 broken), @0x44 stat
  bonus (enhancement / docking white), @0x48 ExpireTick, @0x50 TableIdx, @0x54 InvenIdx. records.Item.encode.
- **Communication Zone / F1** (user: F1 only said "You are not registered in a crew."): the open function 0x61da50..
  goes to tab 2 (Messages) with new mail, else tab 1 (Walkie-Talkie = friends) with Main.Letter ([mgr + 0x270] bit
  15), else tab 0 (My Crew), which refuses without a crew (0x6472b0, text 10425). Main.Letter = 1 now (2011 flag).
  Mail (0x84, 0x5c8..0x5d1) is not native: the Messages tab stays empty.
- **Drift booster** (user asked where it comes from): assist kind driftbooster (a_00118 Post-Drift Booster, a_00247 /
  a_00248 Drift Booster 01 / 02) only on cars (VehicleList "Car Assist": Veyron 50, RUF CTR3 97 in the dealership,
  29 premium / event entries) and drift items (PassiveAssist(DriftBooster) passive_a_00118 / passive_a_00247,
  category 41, not sold; the old tint i_d_w_00005); no part, option, set or convert has it. The client applies the ten
  assist slots of XiStrMyVSItem @0x4c (Assist_Client row + 1; records.VisualItem.assist_slots): for a category
  40 / 41 item in any state but 4 while it has time left (period @0x38 x 24 h - elapsed since ctime @0x40;
  client 0x72961f), and for any drift item on the current car (state 1; 0x7295a2). So PassiveAssist items stay
  in the drift inventory (state 0); on the car they vanish from the inventory (user, 2026-10-13: booster worked,
  items gone). GM `gmdrift <id> [days]`.
- **Messages** (`native/game/mail.py`, user request 2026-10-13): SKID_MSG_TB as the 2008 server. 0x86 GetMail ->
  0x84 MailContent per message (2011 layout in mail.py: send time @0x44, kind @0x4c 0 = a player's message, state
  'N' / 'R' / 'K' -> inbox or kept list; empty text = ignored by the client); 0x5c8 / 0x5ca / 0x5cc read / delete /
  keep -> 0x5c9 / 0x5cb / 0x5cd; 0x5ce SendMail (receiver, text, item count + InvenIdx) -> 0x5cf (result 1 = sent,
  0 = unknown receiver; its Mito field is taken off the client's money: fee, 0 here); 0x5d0 GetMailItem -> 0x192 /
  0x8a + 0x5d1. The client has no compose box in the Communication Zone: SendMail comes from the gift dialog, the
  gift box and the chat command "/쪽지보내기 name text inven". Item text format and what may be sent: guesses.
  Tested against the database without an item (send, list, read, keep, delete); the item path is untested in game.
  emulator.ini `[mail]` (user request 2026-10-14): `min_level` (lowest level that can send), `fee` (Mito per
  message; told in 0x5cf; the client's window shows 50). Ack results: 0 unknown name, -2 bad attachment. The compose
  window's item slots 2 / 3 (crossed out) cannot be unlocked: the dialog holds one item (0x69e790 refuses a second)
  and sends 0 for the rest; an `item_slots` option was added and removed again (user).
- **Whisper** (user: "whisper chat doesn't work"): 0x94 had no handler. Now as Cmd_Whisper 0x5f03d0: to the other
  player with the sender's name and u32 0, back to the sender with the other's name and u32 1 (session.py).
- Whisper u32: 0 = text 10474 "Whispering to [%s]" (the sender's echo), 1 = 10475 "Whispering from [%s]" (client
  0x5ea972); party member info's last u32 = the car's V grade (shown as V%d in the party window; the car type showed V81 / V79).
- **Friend record** XiStrFriend 2011: the place @0x60 is 8 bytes (u8 kind: 1 online in the city, 0 offline; u16 area @0x62), level @0x68, grade
  @0x6a, serial @0x6c (client rows 0x63c888, Party button 0x640907 sent serial 0 -> "does not exist"; user: "Party
  button in communications menu also doesn't work properly").
- **`Emulator/docking_chances.txt`** (user request): docking crafting letter chances per grade and seed (seed / plus),
  white ranges (N / S: lowest, highest, rate; Hyper: the measured step formula), purple spread, the no-seed upgrade's
  max level; read once at start (docking.chances), defaults in docking.py when a line is missing.
  GM chat command `gmsets [set]`: one of every set part (72 in 18 sets) or of one set (misc.py).
- **Converting (Convert tab)** (`native/game/convert.py`, docstring = rules; script-tested): tab shown with Main.Modify
  = 1 (2011 flag, was 0); 0x1aa ModifyItem (part, solution, count) -> 0x1ab (2011: part, ten assist slots, mode 0)
  + 0x192; a tier of PartModify_Client.tdf (34 rows, 2008 odds spread over them) gives two assists by solution
  type A / B / C (stored in ASSIST_A / ASSIST_B, sent @0x10 / @0x14, stat ones counted); tiers 1-4 bind the part.
  Parts and option parts only (user). **Reply order matters**: the ack before 0x192 for 0x19d / 0x1ae / 0x1b3 /
  0x1aa (2008 order; the other way round the parts shop's Esc stayed disabled: user); 0x1ac is list-first.
  0x1ab mode: 0 = kept by the Enhancement Formula ("Converting Warranty", text 11415), else normal; the Formula
  (trans_up) keeps a part's better tier and is used up then (user). **Esc lock**: the Booster path (client
  0x64d6d9) disables the Modify + Exit buttons ([dlg + 0x1d0], [dlg + 0x14]) until the 0x1af animation ends; the
  0x1af handler returns early when the Booster drift item is already gone, so 0x1af must come before 0x4b2. A
  client locked that way stays locked until restarted (seen live: flags 0x23 / 0x63, scratchpad shop.py).
- **The enhancement gauge is not in the item record**: "Modify Chance Time", one value per character, the parts
  shop window ([UI root + 0x334]) +0x238 (boxes +0x208.., client 0x64c701), set only by 0x89 NotifyEvent type 37
  (u32 37, u32 ?, u32 value, u32 ?; client 0x51ca37, no null check: sent with the first 0x311, not at login).
  Found by reading the running client (parts shop setup 0x64e0xx: control ids 0x10c8e0.., 0x3d0900..).
  upgrade.py: +1 / PLUS +2 / DELUXE +4 per failed or breaking try, 10 = sure success, success resets; stored in
  SKID_COUPONPARAMVALUE_TB CTYPE 1000 (not sent as a coupon param). Scratch tools: scratchpad live.py / sweep.py.
- **Set parts, expiry, Restoration Lubes** (`native/game/setparts.py`, docstring = rules; script-tested): XiStrMyItem
  @0x44 = a part's enhancement bonus (client 0x72c9c0 adds it), @0x48 = ExpireTick (2011) in server-tick hours
  (client advances 0x311's tick by s/3600); expired -> the client uses ItemClient column 14 (the *_to form: icon,
  value) without @0x44. ExpireTick in CTIME (tick + column-21 period); SERVERPTICK advanced by hours since LASTDATE
  at login. Set bonus = the set's parts' stat assists while all are on the car and unexpired. Lubes (drift 25 / 26,
  Instant) renew all Alpha / Beta set parts. No gemstone crafting in 2011 (user).
- **Part enhancing (Modify tab) and the Mittron Enhancer Booster** (`native/game/upgrade.py`, docstring = rules;
  script-tested, not yet in game): 0x19d UpgradeItem -> 0x19e (fee, result 0x30000 / 0x30001 / 0x30002 destroyed);
  0x1ae UpgradeItemDouble (2011: + Booster drift InvenIdx + an unused item idx) -> 0x1af (two success rolls, no
  destroy, Booster used up). Odds from 2008 ItemUpgradeServer.tdf (per grade), fee and bonus from the 2011
  ItemUpgradeClient.tdf; level in NUPGRADE, bonus counted in stats; max +15. **Corrected (user):** @0x24
  UpgradePoint is a fail gauge (+1 / PLUS +2 / DELUXE +4 per failed or breaking try, full = sure success, reset on
  success; size = ItemUpgradeClient column 1, a guess; stored in ASSIST_B). Breaking = NUPGRADE negated (2008
  ItemDestroy), not deleted; restoring 0x1b3 -> 0x1b4 (repair -> +0, full_repair -> old level up to +12,
  new_repair -> up to its level). Value-99 Mittron Enhancers expire 72 h after CDATE.
- Main.NewRepair = 1 (2011 flag, sent): the new Restoration Kits (client 0x64db10 checks the kit's level).
- **Option parts switch, docking parts, delete mode** (user, 2026-10-13; script-tested with a fake DB, not yet in game):
  `emulator.ini [items] option_parts` (0 = as the official 2011 server: options cannot be equipped) and `docking_parts`,
  also sent as Main.OptionItem / Main.DockingItem. `native/game/docking.py` (docstring = everything found): 2011
  0x1ac CombiItem is 22 bytes (Type, 3 parts, the 4th slot = seed InvenIdx; client 0x7f1bd0), -> 0x192 + 0x1ad;
  three parts of one stat type and grade (+ a seed of that class) -> a docking item of that type and grade, rank
  from the parts' level tier + a roll (`STEP_CHANCE`: our guess). Docking = 0x18e EnchantItem (part InvenIdx,
  docking InvenIdx; client 0x5f7110) -> 0x18f, or 0x199 with the part's slot: the docking item goes into the
  part's slot on the car; bonus = the part's value x the docking %, rounded up (the starter part i_s_000001 is worth
  1: 20% rounded down gave nothing; user report). The client docks with 0x199. Client: slot UI
  0x5fabe0 (12 slots, types 11-14 = A B C S, grades 0x20008-b = N S H U, icon dock_D*). Not known: whether the
  official server let a part in the inventory (not on a car) be docked; here it must be on a car.
  Delete mode: 0x193 DropItem (TableIdx 0, InvenIdx, count) had no handler -> items.drop_item, 0x194 + 0x192.
- **Open:** drift bonus missing in the Driver Dome outside the field (entry 1 under "Open": what was
  found, and the recording method to continue with); left in the Misc tab: passive assists, discount
  coupons, Pick'em (ObsGacha 0x834-0x83a), Gotcha coins, auto drive / quick slot / fill-up, replay /
  ghost passes, car transfer; drift item expiry (items stay in the inventory); crews (0x357 TeamMembers
  is not answered: the community window would hang for a character in a crew); AI racers parked
  (`BATTLEZONE.md`); the F1 event car needs Dev Ed car types (separate client project).
- New tools: `Server/tools/dev/packets_deved.txt` (516 message names from the Dev Ed client),
  `Server/tools/global_content.py` (client GlobalContent.xlt; the client's Patch.000 is the original +
  BattleRoomAI = 0). Live-memory reads of a running client are plain `/proc/PID/mem` reads (examples in
  `Handoff/scratchpad_session4/`: boost.py, memscan.py, record.py); they need ptrace_scope 0.
- The emulator must be restarted after every code change, and that disconnects the clients: see the
  memory note "Emulator restarts". Nothing is committed; everything is staged.

### State at the end of session 3 (2026-10-13 morning)

**The user's direction** (in their words): "Let's start with native server earlier", then "Keep
the same server architecture, but make sure it uses the same file formats as the new client".
So the native server mirrors the original server: separate auth / lobby / game / area / barea
services on their own ports, the same SQL Server database `SKDBTW` and its tables (and the
2008 server's SQL, taken from ZoneServer.exe strings), `serverlist.txt`, ini config. Tables are
read in the 2011 client's own formats (`.xlt` / `.tdf` as the client has them, copied by
`Emulator/tools/sync_data.py` to `Emulator/data/`), never converted to 2008 columns. Data the
client does not carry (exp per level, Contents.ini, adminlist.txt) comes from the 2008 server's
folder (`emulator.ini [native] server_data / admin_list`). Other standing rules: protocol fixes
go in the emulator, not the DB (the user rejected a getAccInfo change); the TW project in
`../../Drift City 0.02 TW/` must not break (same host ports: stop one stack before the other).

**What runs now** (`Server/driftcity.sh up`, then `./driftcity.sh emu`, which uses
`Emulator/.venv` with python-tds; the client: `python3 Server/tools/dev/run_us2011.py`; the login server address is in
`Server/tools/dev/run_us2011.ini` (since 2026-10-13 no sudo: the launcher is a child subreaper, so the
self-restarting client stays its descendant and the default ptrace_scope 1 allows the patches - not yet tested with scope 1, the user keeps 0 for dev work; the
dev tools that attach to an already running client (cmem*.py, bptrace.py, crashcatch.py) still need
ptrace_scope 0); log in as admin/admin):

| Service | Port | Mode | State |
|---|---|---|---|
| auth | 11005 | native (`native/auth.py`) | login (MEUSERMT, MD5), server list; tested with the client |
| lobby | 11011 | native (`native/lobby.py`) | check-in, character list, name check, create, 2011 two-step delete; tested with the client |
| game | 11021 | native (`native/game/`, batches 1-3 + chase, see below) | switched on 2026-10-12 late (user: "batch 3, then switch to native"); back to the proxy: `game = 11021 12021 56` (with barea) |
| area | 11031 | native (`native/area.py`, see "Native area service") | switched on 2026-10-12 with the game still proxied; back: `area = 11031 12031 0` |
| barea | 11041 | native (`native/area.py`, `native/race.py`, see `BATTLEZONE.md`) | switched on with the game; rooms and races are in the native game since session 3 (`native/game/rooms.py`): script-tested with two clients, **not yet with the real client**; back: `barea = 11041 12041 0` |
| ranking | 11051 | native stub | the client connects and sends nothing |

Restart the emulator: find the pid with `ss -ltnpH 'sport = :11005'`, kill it, start
`./driftcity.sh emu` again (never `pkill -f` a pattern that is in your own command line). Login
tickets survive restarts (`Emulator/.ticket_secret`). `emulator.ini` currently has
`delete_wait_days = 0` (the user's test setting; empty = the client's 3 days).

**Since 2026-10-12 late every service is native** (the table above); the 2008 ZoneServer still runs
in the stack but nothing talks to it (back to the proxy: `game = 11021 12021 56`, `barea = 11041
12041 0` in `Emulator/emulator.ini`). The native game covers batches 1-3 (session basics, items and
cars, drift shop, quests, part-time jobs, combos, instant missions, rush time, HUV chases, GM
commands; sections "Native game, batch 1/2/3" below). The user then tests and reports what is
missing ("will start fixing missing stuff later").

**Fixed after the switch, by user reports (2026-10-12/13; each has a numbered entry 1b-1i under
"Open" below, or a note in "2008 layouts ... / Etc.")** - user-confirmed in game: RGB colour window
(Etc.ColorSetReform = 3), paint / tint / neon / decal colours (car record colours 0x83 / 0x82RRGGBB),
story missions given up on logout, HUV ram damage (Main.StatApply = 1000), HUV hits, gate selection
(0x30f select byte). Done and tested by script, **not yet seen in game**: login error codes (2011
codes), "inventory full" on HUV hits, killing one HUV no longer ends the chase, HUV count per call,
patrol exp per node / patrol ends at the last post / no HUV call during a patrol, day mission start
accepted at login, launcher without sudo (child subreaper; run_us2011.ini holds the server address).
**The last fixes (patrol, chase-in-patrol) were made after the last emulator restart: they are
live only from the next `./driftcity.sh emu`.**

**Session 3 (2026-10-13), all tested by script on test ports, none of it yet with the real client**
(details: "Kick, block, ban" and "Network play" below, `BATTLEZONE.md` "Native rooms and races"):
- **Kick / block / ban** (`native/admin.py`): kick, game block (BLOCKGAMEDATE, error 20089), chat block
  (BLOCKCHATDATE, 0x9c4), account ban (MEUSERMT.VALID -> login 12, lobby / game refuse it, online
  connections dropped), duplicate login (old connection closed, new one error 20088). GM chat commands
  gmkick / gmblock / gmunblock / gmchatblock / gmban / gmunban / gmwho, and from a shell
  `cd Emulator && .venv/bin/python -m tools.gmctl kick NAME` (control port 127.0.0.1:11099).
- **Second account** for network tests: a local test account (MEUSERMT, not an admin; no
  character yet. The character "Xerender" belongs to account admin: IDs and character names are separate).
- **Network play**: the server list's 127.0.0.1 addresses are sent as the address the client connected
  to, so a client on another machine only needs the host's address in its `run_us2011.ini`.
- **Native battle zone** (`native/game/rooms.py`): lobby list, create / modify, the join requests, leave,
  banish, ready, start, loading, go, gates, end, result with the 2008 reward tables, room chat.
- `tools/client.py`: a scripted 2011 client (login, lobby, game, area) for tests; the session's tests are
  in `Handoff/scratchpad_session3/tests/` (kickban.py, rooms.py; they need an emulator on the test ports
  with every service native: `test_all.ini` there).
- The stack was down at the start of the session; `./driftcity.sh up` was run, the emulator itself was
  only run on the test ports (111xx) and stopped again.

- **Other players' info** (user, 2026-10-13, two clients in the city: no name, no profile, wheels not
  shown; the paint colour did show): the client asks 0x321 PlayerInfoReq (u32 n, n x u16 serial + u16
  age) for every car it sees, every 10 s until answered; native had no handler. Now 0x322 PlayerInfoRes
  (u32 n, n x XiPlayerInfo 0xd8; `game/misc.py player_info`: the 2008 fields at the 2008 offsets, checked
  against the client's reads of [car+0x41e0]), and 0x425 VisualUpdate now also goes to the others in
  the game channel. User: names and profiles show. **XiVisualItem is not the 2008 struct in 2011**
  (first try, VisualItem ids in the 2008 slots: no wheels): 0x36 bytes, one i16 per VisualItem.xlt
  category c @6 + 2c holding the item's number inside the category ("index" column), or for the 2011 stat
  items (index 0: Tire S5, AeroWing S5) the look chosen at the purchase = the item text (TireList.xlt
  Tire ID "54", SpoilerList.xlt Spoiler ID "26"); client 0x531e60 -> 0x4bc9c0 -> 0x468100 / 0x4baf70,
  see `game/misc.py visual_item`. *Second try, not yet confirmed by the user.* The plate text's place
  in the 2011 struct is not known (not sent).
- Reported, not looked into yet: a grey arrow in the tutorial on the second client; one
  "Wrong Command: 0" in the client's PacketAnalyzeLogC035.txt (some message of ours is too long).

- **Later in session 3** (all in `BATTLEZONE.md` "Native rooms and races"): two real clients raced start
  to end (user); master-ready fix, gate rewards (`Emulator/gate_rewards.txt`, `gmgate N`), seat change
  0x270, host auto-kick, section rules (`emulator.ini [battlezone]`, ids 0-5), client level caps removed
  (`Server/tools/global_content.py`, Patch.000 changed, original in Server/backup/client_2011/), the
  XiStrCharInfo tail offsets (Flags @0xed), spectators (0x1bf), `tools/complete_quests.py`. Since then done
  and user-confirmed: Real Match (forced car, liveries, schedule), Lap Time; AI racers parked (the
  original server drove them); open: "lobby wages" (unclear), the Formula 1 event car (client mod); spectators and the tutorial prompt still need
  the user's confirmation in game. The emulator currently runs as a background task of the Claude session.

- **Friends, parties, city chat, profile search** (user: could not add friends / invite / chat / find):
  `native/game/social.py` (docstring = layouts and flow) and area chat 0x23b in `native/area.py`.
  Script-tested with two clients; in game not yet. **Stickers**: `native/stickers.py` (lobby: name check, image push,
  upload, small image, catalog list / search, image download, delete) and `native/game/stickers.py`
  (my list, attach with price + creator royalty, detach, 0x324 to others); layouts as 2008 (2011 sizes
  match). Upload, attach, detach, report, daily limit, GM-only upload work in game. Client facts found
  from the running client: sticker image ids **below 100000** are loaded from local files
  (`effects\realmatch\real_%05d.dds`, cache 0x447a10), only ids >= 100000 are requested with lobby 0x40
  (99999 = none), so uploads are numbered from 100000 (the first ones from 1000 showed the error image);
  id % 4 picks the size (0 = 32, 1 = 64, 2 = 128 px). The client puts the player's stickers on its car
  only when 0x5dd BonusUpdate's sticker field (Sticker Glue held) is 1 (flag player+0x1b0c, 0x5403d0);
  Glue L1/L3/L6 = stickers per car (user), plain Glue = 6.
**Open, where to continue:**
0. **Test session 3's work with the real client** (two clients for the rooms): what a real client sends
   to join a room from the list (0x1d4, 0x1bb, 0x1bd or 0x1d7: all answered), whether the joiner's room
   opens on 0x26e + 0x1be alone, the room list entries (0x72 bytes), races with two cars (moves relayed
   by the native BArea as 0x221), the result screen with two entries. Read
   `Client/DriftCity_Log/PacketAnalyzeLogC*.txt` after each try.
1. **Booster gauge does not fill when drifting: only in the Driver Dome** (user, 2026-10-13: "the
   city works fine"; later: the gauge's own rise over time is normal, the drift bonus is missing "in the
   dome outside the field"). **Open, parked by the user.** Found in the client (all read-only):
   - the gauge is the car record's f32 +0x2734 (min +0x150, max +0x15c); the record is
     [[0x948844] + 0x124]: vector +0x9c, index [+0xac] ^ [+0xa8], 0x2970 bytes each (it moves between
     slots, read the index each time). Live in the dome: max 100, +1.6 / s by itself.
   - every gain goes through add-boost 0x484ba0 (record, f32 amount, flag); its gates: Chasing Battle
     state [mgr + 0x3d590] == 3, +0x28c4 / +0x2768 both 0, and with City.NeoCity (off here) a cut by +0x9f8
     in areas 84-99.
   - the direct stunt bonuses (reverse driving 0x48fd7d, and the others using +0xec .. +0x10c) are
     skipped when Main.NewCombo is 1 (we send 1: [mgr + 0x270] bit 10), unless the global 0x94c500 (set
     only by a developer chat command, to 11 / 12) is 12. With NewCombo the drift gain comes from the
     drift-end code 0x4b4698 -> 0x4929d0 (needs byte +0x43d0 of the drift object, not +0x4364).
   - "ParkingLotBoost" is a client GlobalContent key (0x7b67f5): a full gauge once.
   Not found: what differs in the dome. Next step: `scratchpad record.py`-style recording of the car
   record while the user drifts in the dome and in the city, then compare (the recorder was started once,
   the user moved on before drifting). Trying Main.NewCombo = 0 for the dome is a possible test, but it
   changes the city's combo system too.
1b. **HUV chase hits did 0 damage, no turbo from HUVs** (user, 2026-10-13, native chase): the
   chase messages are fine (layouts as 2008). Cause, found with live memory reads and one breakpoint
   (Server/tools/dev/cmem*.py read /proc/PID/mem; bptrace.py sets int3 breakpoints but **crashed the
   client** after the first hit under Wine - use it only with the user's OK): a ram goes 0x4860f0 ->
   0x485440, damage = random in a per-direction range (char data +0x21c..+0x230, hardcoded 91-100 /
   76-90 / 61-75) x the char's +0x260 x a speed factor x 0.01; +0x260 = (TotalCrash + 2 bonuses) x
   (**Main.StatApply** & 0x3ff) x 0.001 (0x488e00; the same for speed +0x258, accel/boost +0x25c /
   +0x268). Main.StatApply is a 2011-only content flag (Main @0xc, 10 bits) that we sent as 0, so
   every ram did 0. Now sent as 1000 (= 100%, NEW_FLAGS). **User-confirmed 2026-10-13: hits work.** The 6 longs the
   2011 client added to XiStrStatInfo (only the server fills them; Dev Ed: HP, Defense, Crash Damage)
   are not used by rams; still 0 (records.Stats.combat). Live-memory map: game object [0x948844];
   char data [[game+0x124]+0x9c] + idx*0x2970 (idx = u32[+0xa8]^u32[+0xac], changes; find it by its
   stat block at +0xb18), vehicles [[game+0x124]+0xe4] (count +0xe8, +0x41a0 serial, +0x41a2 sort).
1c. HUV count per call (user, 2026-10-13): 1 player 1-4, 2: 2-6, 3: 3-8, 4: 4-12 (chase.HUV_COUNT;
   the 2008 server: 1-4 / 3-6 / 5-8 / 7-10, then up to the HUV row's Ea, at most 8). Alone for now.
1d. "Inventory full" on HUV hits (user, 2026-10-13): our 0x2e5 for "nothing dropped" was (0, -1);
   the 2008 PickUpItem returns success with item -1 -> (1, -1, mode); (0, -1) = could not take the
   item = "inventory full" in the client. Fixed in combo.drop (combos, traffic items, rush and chase
   hits all use it).
1e. "Killing one HUV kills all of them" (user, 2026-10-13): we sent 0xb8 ChaseResult for every
   0xb7, and the client ends the whole chase on 0xb8. The 2008 server (Cmd_ChaseEnd alone, 0x60c481):
   EndHuv for that HUV, reward only if m_Result = 1 (caught), 0xb8 only when the HUV count reaches 0
   (serial 0 = given up / time out ends all). Fixed in chase.chase_end (totals in one 0xb8); tested
   with a fake session (scratchpad tests/chase_unit.py), not yet in game.
1f. **Gate selection skipped** (user, 2026-10-13: going to the city, the gate screen opened and went
   straight to loading Gate 1). Found with a read-only memory watch: the dialog was shown, the client
   sent 0x314 (channel 0, byte 1) in the same millisecond as our 0x315/0x316, our 0x30f came back and
   the city loaded. Client 0x516050 (Cmd_MyPositionAck): with the client switch Select_Gate_MainEX
   (looked up with 0x83aa50; a missing switch gives -1 = on) and 0x30f's 2011 byte @0x1c = 1 it stays
   on the gate dialog instead of loading; the dialog's own join (0x6b7800) sends 0x314 with byte 0.
   We always sent 0 -> now position.my_city_position echoes the request's byte. The gate list 0x315
   is not used by the 2011 client (its handler only marks 0x30c answered and shows the dialog); the
   number of gates is Main.OpenGate (2). Not yet tested in game.
1g. Wrong password showed "Authentication system abnormal" (user, 2026-10-13): the 2011 US client
   (nation 1, LoginAck handler 0x50cb10) maps result 1 = wrong password, 2 = unknown ID, 4 = no ID /
   password, 12 = blocked, others -> "abnormal (%d)"; native auth sent the 2008 server's -1 / -2 / -3.
   Fixed in native/auth.py (tested on the test ports: 1 / 2 / 0).
1h. Patrol nodes showed "{} exp" (user, 2026-10-13): instant reward columns were swapped. XiInstantTable
   ::LoadFile 0x64f3bb reads Mito, exp, final exp (2011 columns 13, 14, 15); patrol rows are (0, 1-3,
   30.., posts), so every node gave 0 exp. Fixed in instant.py (tested: 1 exp per node). Also no HUV
   call during a patrol (user): chase_request refuses with a message (the 2008 server had no such
   check; its texts have none, so the message is ours).
1h2. Patrol completion did not end the mission (user, 2026-10-13): the client sends no 0x3e2 for a
   patrol; the 2008 server ended it at the last post (Cmd_InstantGoalPlace 0x606528: 0x3ea, then 0x3e5
   InstantRewardAck with the final exp, mission removed). Now the same in instant.py (tested: 40
   posts -> 0x3e5 with 30 final exp, 70 exp in all, HUV calls allowed again).
1i. Item catalog with icons (user request): Server/tools/dev/item_catalog.py builds it (icons from
   game.nui + uitex.agt), published as an artifact (https://claude.ai/artifact/9y6hVMesYg7VfuTJRcGqwd).
2. Neon (category 2) and decal (11) RGB colours: user-confirmed working (2026-10-13), nothing to do.
3. HUV calls: native chase (chase.py) works with the real client (calls, HUVs, hits; user 2026-10-13);
   chase end: see 1e.
4. Battle zone: native since session 3 (see 0). Not native: teams (0x26f), Real Match (0x1c7),
   observers, invitations, 0x1d3 (a car change inside a room), item races (gate rewards), 0x1da.
5. Not native: teams, parties, auctions (0x246 -> error), docking parts, day mission completion,
   rush controller switch, chase bonus formulas; older open issues: dealership coupon text, new cars'
   keys (native buy gives the key now), tutorial messages, 3D model placement in the UI.

**How to work on a native service** (the method used so far):
1. Find the 2008 handler: `Server/tools/dev/dispatch_2008.txt` (type -> service -> handler),
   disassemble it: `/home/deck/.local/share/dc-dev-venv/bin/python Server/tools/dev/sdis.py
   Server/server/ZoneServer.exe Server/tools/dev/ZoneServer.syms PacketParser::Cmd_X`; structs:
   `Server/tools/dev/pdbtypes.py Server/server/ZoneServer.pdb BS_PktX` (sizes in bytes); SQL:
   `strings -a Server/server/ZoneServer.exe | grep ...`.
2. The 2011 side: `Server/tools/dev/handlers_2011.txt` (type -> client handler, size it reads),
   `sizes_2008_2011.txt`. Client code: the exe on disk is ASProtect-encrypted; an unpacked
   memory image of the running client is `Server/client_image/DriftCity_2011_unpacked.bin`
   (7 MB, gitignored; file offset = address - 0x400000), disassembled with
   `Server/tools/dev/mdis.py` (`mdis.py dis IMG ADDR [N]`, `mdis.py refs IMG HEXVALUE`, dev venv).
   A new image: `client_dump.py OUTDIR`, then start the client. The unencrypted 2016 Dev Ed exe
   helps with meanings. Client facts used so far: char list entry +0x3e state / +0x42 deletion
   time (0x7b9be0), 0x32 sender 0x7ff0a0, 0x02 sets the lobby clock.
3. Record a real client session (any `Emulator/logs/*.msgs.txt`), run a second emulator on other
   ports (`cd Emulator && .venv/bin/python -m dcemu -c tools/test_ports.ini -q`: every service on
   111xx; game 11121 native there, set `game = 11121 12021 56` for the proxy side), replay the session against the proxy
   and against the native service and compare: `cd Emulator && .venv/bin/python -m
   tools.replay LOG CONN PORT out.json`, then `-m tools.replay --compare a.json b.json`.
   For game, the native replies match the 2008 server's except times, weather, session serial
   and the stats (now from the 2011 VehicleUpgrade.xlt).
4. Test DB-writing handlers with scripted clients (`tools/probe_login.py` has the 2011 login)
   on throwaway characters, and delete those rows afterwards.

Nothing is committed: the repo (initialised 2026-10-12, branch master) has everything staged;
commit only when the user asks.

**Moving devices:** the project has moved machines before and is prepared for another move after
session 4 (2026-10-13). On this machine the project is `/home/deck/Drift City Project/Drift City US 2011/`
(the TW project `/home/deck/Drift City Project/Drift City 0.02 TW/`); older text here may still say
`/home/deck/Games/Drift City 2011/`. The "DriftCity Dev Ed" 0.77 client is in `DriftCity Dev Ed/`.
`../Handoff/README.md` lists what lives outside the project (DB backup, Claude memory and session
transcripts, session scratchpads) and how to set up the next machine.

The TW 0.02 project (a working server + translated 2008 client, separate build) lives in
`/home/deck/Games/Drift City 0.02/` (on the old machine `Drift City Project/Drift City 0.02 TW/`). Its `Server/README.md` and `Server/HANDOFF.md` explain the
2008 server, the database and many protocol details; read them, they apply here too. This folder
is a copy of that stack, separated so 2011 experiments cannot break the TW build.

## Folder layout (`/home/deck/Games/Drift City 2011/`; first machine: `/home/deck/Drift City Project/Drift City US 2011/`)

| Path | What |
|---|---|
| `Emulator/` | the emulator (Python; the native services need python-tds in `Emulator/.venv`): per service either a logging, rewriting proxy in front of the 2008 server, or native (`dcemu/native/`). `Server/driftcity.sh emu` runs it. |
| `Client/` | 2011 US client, unpacked from `DriftCity_Setup_20111116.exe` with 7-Zip (not installed). Patches 000-010 included. |
| `Server/docker-compose.yml` | the 2008 ZoneServer (Wine, Ubuntu 22.04 i386) + SQL Server 2019 Express. Its TCP ports are on 127.0.0.1:12005/12011/12021/12031/12041 (the emulator owns 110xx). Compose project **driftcity2011**, containers `driftcity2011_zoneserver_1` / `driftcity2011_db_1`, DB volume `driftcity2011_mssql-data` (separate from TW's). |
| `Server/server/` | ZoneServer.exe and its data, copied from the TW build (TW tables, `LocaleIndex=4`). `ZoneServer.exe` has the TW fixes (patch_server_*.py: English strings, rush message sizes, assist kind, patrol item, Real Match layout, Undercity table); `ZoneServer.exe.orig` is the untouched 2008 build. `ZoneServer.pdb` (16.7 MB) has full debug info. |
| `Server/db/` | schema (`01_initialize_database.sql`, stored procedures incl. `getAccInfo`), `02_create_user.sql` (login admin/admin), `03_seed_sequences.sql` (id counters; without them new ids are 0/-2). |
| `Server/tools/` | `agt.py` (NayaPack .agt archives: read/extract/write), `ntx.py`/`dds.py` (UI atlases), `traffic_server.py` (an asyncio TCP relay that parses and injects messages: the pattern to grow the emulator from), `gm.py` (GM console on 21158), `table_edits.py` (config: `table_editor_config.json` names the 2011 containers), `patch_server_*.py` (how we patch the 2008 exe safely). |
| `Server/tools/dev/` | `run_us2011.py` (starts the 2011 client under Proton, see below), `sdis.py` (disassemble whole functions of ZoneServer.exe with symbol names: `sdis.py server/ZoneServer.exe tools/dev/ZoneServer.syms PacketParser::Cmd_BuyCar`), `pe_dis.py`, `immscan.py` (find instructions using an immediate, e.g. a message type), `sniff.py` (log TCP payloads in the server container's namespace), `msgs.py` (split a sniff log into messages), `ZoneServer.syms` (25,670 symbols), `handlers_2008.txt` (the 2008 Cmd_* handlers). Needs the dev venv: `/home/deck/.local/share/dc-dev-venv/bin/python` (pefile, capstone, Pillow, numpy, pyffi). |
| `Server/data_2011/` | the 2011 client's tables, extracted: `base/` + `us/` (Init: VehicleList, VShopItem, VisualItem, ... `.xlt` UTF-16 tab separated), `base_world/` + `us_world/` (`.tdf`: ItemClient, UseItemClient, Assist_Client, Quest...). The US files override the base ones. |
| `DriftCity Dev Ed/` | a later client ("Dev Ed 0.77a", exe built 2016-02-16, folder dated 2018), for reference. Its `DriftCity.exe` is **not encrypted**: code and strings can be read straight from the file (pefile/capstone, image base 0x400000), unlike the 2011 exe. Newer than 2011, so layouts may differ; use it for meanings (flag names, handlers), check offsets against the 2011 client. Has its own Data/, Data_US/ (gameui), Patch/. |
| `DriftCity_Setup_20120404.exe` | 2012 installer, incomplete download (7-Zip: unexpected end of archive). |
| `Server/captures_reference/` | captures of the community "Drift City Remastered" server (a later client; its folder `~/Games/Drift City Remastered/` is on the current machine: `Drift City Remastered Alpha/DriftCity.exe` built 2010-10-29, a different build from the 2011 client, readable imports) in races: raw `.log` from sniff.py, `.msgs.txt` split by msgs.py. Race message ids were the same as 0.02, some field offsets moved. |

Running: `./driftcity.sh init-db` once (creates the DB; done 2026-10-12), then `./driftcity.sh up` /
`down` / `logs`, and `./driftcity.sh emu` for the emulator.
**The TW stack uses the same host ports** (11005, 11011, 11021, 11031, 11041, UDP 11400/11401,
21000-21014, 21157/21158): stop one stack before starting the other
(`cd "/home/deck/Games/Drift City 0.02/Server" && ./driftcity.sh down`; its
containers are `driftcitytw_*`). podman-compose is `/usr/bin/podman-compose`.
The dev venv was recreated on 2026-10-12 (`python3 -m venv ~/.local/share/dc-dev-venv`, then
`pip install pefile capstone Pillow numpy pyffi`). The Proton prefix `~/.local/share/drift2011-pfx`
does not exist on this machine yet: run_us2011.py creates it on its first run.

## The 2008 server (what the emulator must replace)

- 32-bit VC 7.1 / Gamebryo program run by Wine (`/usr/lib/wine/wine ZoneServer.exe`), ODBC to SQL
  Server (`odbc.ini`, sa / `z0ne!server`, database SKDBTW). `ZoneServerConfig.ini`: `AuthType=1`
  (login by stored procedure `getAccInfo`, which compares the MD5 hex of the password),
  `LocaleIndex=4` (Taiwan: reads `Data_TW/`; 1 = US reads `Data_US/`, whose init failed at 0x63ff60
  in an earlier attempt with 2007 tables).
- Ports: 11005 auth/login, 11011 lobby, 11021 game, 11031 area (city; TrafficAgent.exe drives city
  traffic through it), 11041 BArea (race area), UDP 11400/11401 and 21000-21014, 21157 RPC, 21158 GM
  console (EUC-KR text commands, see `tools/gm.py`). `server/serverlist.txt` advertises server id 100
  and the lobby/game/area/barea addresses (127.0.0.1).
- Wire format (TCP, plain, little endian): `[u16 length incl. header][u16 type][payload]`; one
  frame can hold several commands: the server splits them by the byte count each `Cmd_*` handler
  returns (Cmd_UserAuth returns 0x96 = type + 148 payload bytes), so a command longer than the
  2008 one leaves its tail to be read as the next command ("Wrong Command: N").
- Auth, lobby and game (and the emulator's ranking port) start each direction with an unframed
  56-byte key exchange, the server first; **area and barea do not** (a proxy that cuts 56 bytes
  there misreads the next length and stalls the city traffic: the 2011 client then hangs on
  the loading screen). The exchange: two 28-byte units of u64 + 4 x u32 + u32 cipher type (`BS_Cipher::RecvKey`,
  `MergeKey`, `CStreamCipher`). The keys are XORed; the cipher type comes from the unit the server
  receives, and type 0 leaves the traffic plain. The server sends type 0; a client that sends 56
  zero bytes gets plain traffic. A client that skips it loses its first 56 bytes. Details of many messages: `tools/traffic_server.py` docstring and `HANDOFF.md` of the
  TW build (race traffic 0x21e, collisions 0x220/0x223, race start 0x238, city cars 0x2bd, room
  options 0x26c/0x1ce, rush time, Real Match 0x1c7 ...).
- 324 packet handlers (`PacketParser::Cmd_*`, list in `handlers_2008.txt`), 316 packet types. The
  symbols make every rule readable: e.g. buying a car (`PacketParser::Cmd_BuyCar` 0x605d10) checks
  the car tables, money (error "20092"), garage space, coupons, then creates the car in the DB and
  its key item (UseItem row named after the model).
- Tables are read with `DA_SScanf` format strings (find them with sdis.py in the `Load*` functions);
  the header line holds the row count, rows past it are ignored.

## The 2011 US client

- `DriftCity.exe` built 2011-10-27, launcher 2011-10-26. Fully encrypted (ASProtect, every section
  entropy 8.0): analyse it from memory while it runs (`/proc/<pid>/mem`; tools started separately need
  `sudo sysctl kernel.yama.ptrace_scope=0`, a reboot resets it; the launcher itself does not). No memory dump is kept; make one
  with the running client.
- **Packs vs ASProtect (session 11):** ASProtect guards only the exe's code; it does not check the packs. The pack
  loaders (0x834570 for PatchMod.000, 0x834e70 for Patch.000-010, read through the XOR reader 0x8338c0, key 0x8f77d0,
  90 bytes) check only "NayaPack\0", the words at +12 / +14 (= 1) and the entry count at +16. Header bytes 20-31 are
  never read and are no checksum of anything (24-31 are the same in every pack); the pack size is free (rewritten
  packs are 1-2 bytes longer and load). Why the zeroed header seemed to break car thumbnails is unexplained (A/B
  test still to do). Of the dump's ~500 IAT entries, 18 point into ASProtect stubs (0x15xxxxx), the rest straight into DLLs.
- One program for several publishers, chosen by a nation number; US = 1.
- **Start:** only via the launcher: `DriftCity.exe /runsw <token>`, token =
  `md5(str(t - t % 300000))` with t = the millisecond tick count (the previous 5-minute window is
  accepted too). `tools/dev/run_us2011.py [server ip]` does this under Proton 11
  (prefix `~/.local/share/drift2011-pfx`).
- **Server address:** hard-coded for nation 1 at 0x8daaa4 (`208.80.248.47`, live) and 0x8daab4
  (`208.80.248.215`, alpha), 16-byte slots, port 11005. `init/network.txt` is for other nations.
  run_us2011.py overwrites both in memory once the exe has unpacked itself.
- **GameGuard:** started for the US (protection class table byte 0x4e1211 = 2; object pointer
  0x94d168 with vtable 0x8d0d34). GameGuard cannot run under Proton ("GameGuard initialization
  error"). The exe has a class whose checks all succeed (vtable 0x8d0d7c, used by other nations);
  run_us2011.py writes 0 to the table byte and swaps the object's vtable. The client restarts
  itself once, so every DriftCity.exe instance is patched.
- **Windowed mode:** fullscreen takes no input under Proton. The client forces fullscreen unless
  `HKLM\SOFTWARE\DriftCity\EnableWindowMode` (DWORD, 32-bit view) is non-zero; then goption.ini's
  `Fullscreen` applies (the client writes goption.ini back on exit). run_us2011.py sets both.
- Data: `Data/` (base, Korean texts) + `Data_US/` (US overrides: `Init_us.agt`, `World.agt`,
  `game_us.agt`, `gameui/uitex.agt`, `vehicles_us.agt`). Settings in the encrypted `DriftCityUS.ini`.

## Protocol findings so far

1. **Login (auth port 11005, type 0x14)**: same framing and layout as 2008: version dword (10135),
   UTF-16 ID at +8, password at +0x58, no encryption. Differences:
   - the password is **plain text**; 2008 clients send its MD5 hex and the DB stores MD5. The
     server answers -2 (wrong password). A `getAccInfo` change accepting both worked but was
     reverted at the user's request: **the emulator/proxy must MD5 the password** before passing
     the login on. Done in `Emulator/dcemu/handlers/auth.py`.
   - the 2008 server reads the password field as a **narrow (ASCII) string**: 32 lowercase hex
     chars, zero-padded to 64 bytes (`strncpy` 0x21 in the query object at 0x421e40). UTF-16 hex
     fails (-2). Whether the 2011 client's plain password is ASCII or UTF-16 is not yet seen; the
     emulator accepts both and logs it.
   - the message is 4 bytes longer (156 vs 152); the 2008 server reads the tail as another command
     and logs `Wrong Command: 32327` (the tail starts 47 7e). The emulator drops it.
   - the ack 0x16 (S>C, 206-byte payload from the 2008 server) is u32 ticket @0, i32 getAccInfo
     result @4 (0 OK, -1 unknown ID, -2 wrong password), ..., and the **server list 0x17 is packed
     into the same frame** (ServerTable::SendServerList), sent whatever the result.
   Tested 2026-10-12 with `Emulator/tools/probe_login.py` through the emulator: 0 / -2 / -1 as
   expected. Not yet tested with the real 2011 client.
   - on the first connection the server also logged `Wrong Command: 437` 12 times (unknown
     2011 command, not yet identified).
2. With the password accepted, the server sent the login ack (0x16) and the server list (0x17); the
   client then **hung on the loading screen and never connected to the lobby (11011)**.
   **Next step:** run the real client through the emulator and read its log. Lead: the 0x17 list
   rides in the 0x16 frame, so if the 2011 client's 0x16 body is longer or shorter than 2008's,
   it reads the list from the wrong offset. Then compare the 2011 client's 0x16/0x17 parsers
   (from its memory image) with the 2008 server's layout and fix them in an auth handler.
3. Remastered captures: race messages keep the 0.02 ids with shifted offsets *(the Remastered
   client is later than 2011; check against the 2011 client before relying on it)*.

## Data delta, 2008 TW server vs 2011 client

- 21 new tables: alchemy, license, apprentice, weapons, Neo Oros (+ neoai, neohuvparam), mother
  quest, reward groups, upgrade condition list, emoticons ...
- ItemClient 195 → 749 rows, UseItem 174 → 1,112, Assist (part options) 113 → 5,125.
- VisualItem 86 → 169 columns (162 car types; the 2008/0.02 client caps car types at 100: its
  per-car fit flags are 100 bytes in a 180-byte record), VehicleList 69 → 78 columns,
  VehicleUpgrade 20 → 31, VShopItem 67 → 75; most shared tables gained columns.
- New city Neo Oros (`Data/World/NeoOros`), patches mostly Neo Oros map files.
- Car models are "Stage 2" (one mesh, two UV sets, newer shader extras); the TW port tools
  (`0.02/Server/tools/port_cars.py`, `nif_stage1.py`) convert them for the old engine; the 2011
  client draws them natively.

## Recommended plan (agreed earlier; since 2026-10-12 the services go native one by one, see the top)

Do not decompile and rebuild the 2008 server, and do not binary-patch it into a 2011 server (too
many new systems). Build an **emulator incrementally behind a proxy** in front of the 2008 server:

1. Proxy every port (asyncio, like `traffic_server.py`): log both directions, pass messages through.
   **Done** (`Emulator/`).
2. Adapt what differs: login (MD5 the password, drop the 4 extra bytes: **done**), the server list (0x17),
   then each next blocker on the way to lobby → character select → city → race.
3. Move handlers from the 2008 server into the emulator one by one (the 2008 handler code and
   symbols are the specification), until the 2008 server is no longer needed. Reuse the SQL
   Server schema in `db/`.
4. Serve the 2011 tables (`data_2011/`) to the emulator's own logic; the 2008 server keeps reading
   the TW tables until its handlers are replaced.

## Working rules learned on this machine

- Never write `ZoneServer.exe` in place while the server runs (write `.tmp`, then `os.replace`).
- Never `pkill -f <pattern>` when the pattern is also in your own command line: it kills your shell.
- Restart the server only when nobody is logged in; a stuck stop: `podman stop -t 15`, then
  `podman unshare kill -9` the PID.
- Compose derives volume names from `name:`: keep `name: driftcity2011` or the stack gets an empty DB.
- Patching the client in memory (address, GameGuard) runs only in this local setup and touches no
  file on disk. An earlier attempt to put the GameGuard bypass into one of the client's DLLs on
  disk was blocked by the permission check and dropped; ask the user before trying anything like it.

## Emulator (`../Emulator`, started 2026-10-12)

Python 3, standard library only. `dcemu/proxy.py` listens on the client ports (11005 auth, 11011
lobby, 11021 game, 11031 area, 11041 barea) and pairs each connection with one to the 2008 server
on 127.0.0.1:120xx; the handshake (56 bytes, both directions) is passed through and logged as
`raw`. Frames go through the handlers registered with `@on(service, direction, type)` in
`dcemu/handlers/` (new modules go into `MODULES` there). Every message is logged in full to
`Emulator/logs/<time>.msgs.txt`. Next handlers to write go by the plan above; to replace a 2008
handler, read it with `tools/dev/sdis.py` and answer from the emulator (`session.to_client`)
instead of forwarding.

### Findings with the real client (2026-10-12)

- **The client checks every message's size and says which one is wrong**:
  `Client/DriftCity_Log/PacketAnalyzeLogC*.txt` (plain text; CmdLen = what the 2011 handler
  takes counted from the type, AnalysisSize = the whole frame received), e.g.
  `Wrong Packet Size. CMD(61) CmdLen: 74, AnalysisSize: 12` = it wanted 74 bytes of 0x3d, got 12.
  Read it after every test run: it points straight at the next layout to fix.
- The client sends the plain password as ASCII.
- Its handlers are registered as `push handler; push type; mov ecx, esi; call 0x806590`
  (e.g. 0x53d208: 0x16 -> 0x50cb10, 0x17 -> 0x50e230); the dispatcher is at 0x8138a0 (handler
  table at [dispatcher+8], "Wrong Command" at 0x813938). A memory image of the unpacked client
  (0x400000-0xb00000, taken once 0x8daaa4 holds the address) is enough to read them with capstone.
- Server list 0x17: 2011 entries are 136 bytes (2008: 124): one more u32 after the user counts,
  a 5th IP and a 7th port. The connect on server select (0x536a70) reads IPs @0x64-0x74 and
  ports @0x78-0x84. The new IP/port are the **ranking server** (the client has a `RankingTCP`
  connection; without it: "Server not on ranking"). The emulator converts the list
  (`handlers/auth.py`) and serves ranking itself on 11051 (a local service: handshake + log, no
  answers yet).
- Lobby 0x3d (user info, the account's characters): 2011 inserts a 64-byte UTF-16 string
  after the count, before the 0x78-byte character entries (client handler 0x528e40). If it equals
  the string the client keeps (empty at first) and there are characters, the client says
  "Please log-in again" (text 10988). The emulator inserts a random token (`handlers/lobby.py`).
  The real server's value is unknown.
- After that the client reached character creation (0x50/0x51 name check, 0x52/0x53 create)
  and the game port (0x78/0x79, 0x7b, 0x32a character info, ...).
- **"Error: 45" is ASProtect's "Protection Error"** (WINEDEBUG=+relay: MessageBoxA(title
  "Protection Error") called from ASProtect's runtime, then ExitProcess). ASProtect checks the
  unpacked code roughly 0.4-0.5 s after start; the launcher used to write the GameGuard class
  byte 0x4e1211 (code) and won or lost that race (random failures, then every launch once the
  write moved earlier). It is not the /runsw token check (that one hashes timeGetTime(); the
  launcher's token matched) and not the Wine prefix, logs, crash report or options (all tested).
  Fix in run_us2011.py: no code writes at all. The launcher ptrace-attaches as soon as the
  process exists, sets a hardware execute breakpoint (DR0/DR7 via PTRACE_POKEUSER) on the class
  switch 0x4e114b in every thread, and when it is hit moves EIP to the no-GameGuard branch
  0x4e1191; then it clears the breakpoints and detaches. The server address is still written in
  memory (data, not checked). Any code patch (e.g. skipping the token check) triggers Error 45.
  The launcher also ignores DriftCity.exe processes that were running before the launch.
  Diagnosis switches: RUN_US2011_SKIP=address,gameguard, RUN_US2011_WINEDEBUG, RUN_US2011_TOKEN.

### 2008 layouts from the PDB; loading the character (2026-10-12)

- `tools/dev/pdbtypes.py server/ZoneServer.pdb <struct regex>` prints struct members and offsets
  from the 2008 PDB (pdbparse does not build on Python 3.14; this is a small MSF/TPI reader).
- `tools/dev/pkt_table.py` -> `tools/dev/packets_2008.txt`: message type -> BS_Pkt struct ->
  sizeof (144 types, from the GetMessageBuffer/AllocMessage<T> functions). The emulator uses a
  copy (`Emulator/dcemu/data/packets_2008.tsv`) to split frames into commands
  (`dcemu/commands.py`); the log shows `commands: 0x32a(138) 0x7c(292) 0x1e(66)` for packed frames.
- After entering the game the server sends one frame: 0x32a ETCInfo (138, same in 2011),
  0x7c LoadCharAck, 0x1e GameSetting. The 2011 client stopped on it ("Wrong Command: 0").
  - 0x7c: character record XiStrCharInfo 233 -> 283 bytes (8 new bytes @0x95, everything after
    moves by 8, 42 new bytes at the end), car count u32 @0x125, cars XiStrCarInfo 45 -> 49
    bytes (4 new bytes @0x24, after Color). Evidence and offsets: `handlers/game.py`.
  - 0x1e: XiContentsFlag 7 -> 11 groups of 8 bytes (new groups sent as 0).
- Entering the city, next mismatches (fixed in `handlers/game.py`): 0x2f8 StatUpdate
  (XiStrStatInfo 80 -> 104, 6 client-computed longs appended; XiStrEnChantBonus 36 -> 40),
  0x2f9 PartyEnChantUpdate (bonus 36 -> 40), 0x191 ItemListAck (XiStrMyItem 52 -> 92:
  TableIdx/InvenIdx moved to 0x50/0x54; where the 36 new XiStrItemUnit bytes go is a guess).
  `pkt_table.py` now also reads `BS_MessagePacket<...,T>` builders (308 types).
- The 2008 server logs commands it does not know in `server/ZoneServer_Log/PacketAnalyzeLogC*.txt`
  ("Wrong Command: N"): the counterpart of the client's log, for C>S. New 2011 client commands
  seen while loading: 0x484 (no reply registered; dropped), 0x640 -> 0x641 (second item list,
  0x5e-byte entries; answered empty), 0xfa0 -> 0xfa1 (2226 bytes, probably mentor/apprentice
  data; answered empty, the loading waits for it). The emulator answers these itself
  (`handlers/game.py`). 0x29 (lobby check-in) and 0x78 (game check-in) are longer in 2011 and
  are cut to the 2008 sizes (0x9e, 0x23).
- The "stuck loading" after joining the city (0x232/0x233) was a **crash**: the client writes
  `Client/DriftCity.exe.npd` (faulting address only). `tools/dev/crashcatch.py <out dir>`
  attaches with ptrace once the client has unpacked and logs registers + a stack walk for faults
  inside DriftCity.exe (passes the signals on). Caught: 0x8198b4 (show control) with a null
  control from 0x5f9bc0: the city dialog's sub-dialog 4470000 at +0x644 was never found. The
  city dialog is picked by content flags (0x1e GameSetting, [game+0x2bc] = flags +0x54, in the
  groups that are new in 2011): &0x180 == 0x80 / 0x100 / 0 -> three HUD variants; 0 crashed.
  That flag is `Etc.InventoryReform` (see below); 1 got into the city.
- **Content flags (0x1e GameSetting, XiContentsFlag) changed layout in 2011**, not just size:
  2008 = 7 groups x 8 bytes; 2011 = Main @0 (16), City @0x10, InstantMission @0x18 (12),
  OMDBase @0x24, BattleZone @0x2c (16), TeamCenter @0x3c, NetSync @0x40 (new), Etc @0x44 (20),
  and the bits moved inside the groups. The client has every flag's name ("Main.NeoCityMainUI",
  "Etc.InventoryReform", 194 names) in its Reflect<Group> functions (0x45a030.., called from
  0x45be30 with the group offsets). `tools/dev/flagtable.py img <image>` reads them (from the
  write-back after each lookup); the 2008 layout comes from the PDB bitfields
  (`pdbtypes.py` prints LF_BITFIELD as `uint:width@bitN`). The emulator converts by name
  (`dcemu/data/flags_2008.tsv` -> `flags_2011.tsv`, `handlers/game.py`); 2011-only flags are 0
  except NEW_FLAGS (Etc.InventoryReform=2). The old pad-with-zeros conversion put City and every
  later group in the wrong place (glitched UI, inventory crash on F3).
- Inspecting the running client's UI: `tools/dev/uiwalk.py` lists the created dialogs (UI root =
  [[0x948844]+0x158], dialog list [root+0x11c], count [root+0x120], id [dialog+0x3c]: all 513
  of game.nui exist at the login screen); `tools/dev/invwalk.py` shows the three city inventory
  dialogs (root+0x16c/0x170/0x174, picked by Etc.InventoryReform 0/1/2). Only the third one
  (2) has all its controls; 0 crashed on entering the city, 1 on F3. The emulator sends 2.
- 0x192 ItemModList (item changes; XiStrMyItemMod = XiStrMyItem + State, 56 -> 96 bytes in 2011)
  crashed the drift shop (F4); converted like 0x191. Main.NeoCityMainUI (2011 city main UI:
  1 = new UI, 2 = also weapon slots, dialog 4620000) is sent as 1 (with 0 the main UI was glitched).
- F4 (item shop) still crashed after the 0x192 fix, at 0x698fe9: the shop's tab mapping 0x671be0
  uses the old layout when Etc.VShopSeason ([game+0x2bc] & 0xf00000) is 0, and those controls do
  not exist in the 2011 UI. VShopSeason is now sent as 1 (compared with 1/2/3 elsewhere).
  Pattern so far: each "0 = old design" 2011 switch (InventoryReform, NeoCityMainUI, VShopSeason)
  makes the client use controls the 2011 game.nui no longer has. Candidates still at 0 if more of
  this shows up: the other *Reform flags (ColorSetReform, BattleZoneReform), AlchemySystem, ...
- HUD (speedometer, minimap, speed combo, item slots) has a classic and an "ADV" dialog each
  (210000/220000, 80000+90000/100000, 180000/190000, 230000/240000). Which one shows is the
  **client option** `MainUIType` in `Client/Data/Init/goption.ini` (0 = classic, default), not a
  server flag. run_us2011.py now sets MainUIType=1 (MAIN_UI_TYPE) together with windowed mode.
- crashcatch.py also saves 4 KB at each pointer register (`<tid>_<eip>_<reg>_<addr>.bin`).
- F4 still crashed with VShopSeason=1 (same 0x698fe9, null control from [shop + 0x220 + i*4],
  shop = [ui+0x2e8], vtable 0x8e4300). Solved with the register dumps: the entry was a type-3
  tab (id 6000; the tab list holds 6000/6100), which 0x671be0 maps only for VShopSeason >= 3;
  below that it returns 1 and slot [shop+0xe4+4] is empty. VShopSeason is now 3.
- **Etc.ColorSetReform** ([game+0x2bc] & 0xe00, bits 9-11) switches the drift shop to the 2011 RGB
  colour window (paint / tint / decal): about 30 places test `> 0x200 && <= 0x600` (2 or 3), the
  window of shop entry 0xce4 needs `> 0x400` (3); entry 0x44c needs > 0x200. With 0 the colour
  window never appeared (user, 2026-10-12). Now sent as 3 (NEW_FLAGS).
  With the window the client sends the colour as a decimal 0xRRGGBB ("16715002"), no padding; the
  native drift shop now stores and returns the text exactly as sent (it had re-added 10 spaces, and the
  bought paint did not change the car's colour). The proxy's handlers/vshop.py still has the old
  10-space handling (only matters if the game goes back to the proxy).
  **The paint still did not show**: the client draws the car from the car record's colour, not from
  the paint item. Car model SetColor (client 0x4690b0 / 0x467570, only with ColorSetReform): a colour
  0x8X RRGGBB is RGB (X = 2: a second layer; else the base colour; the client itself turns palette
  colours into 0x83RRGGBB), anything else a palette index (dealership colours like 0x08000002). So the
  native game sends a car with a paint on it (category 1 colours or 32 glossy colours / RGB paints;
  the 2011 RGB "Paint S15/C15" items are 32) with colour 0x83RRGGBB in XiStrCarUnit.BaseColor and
  XiStrCarInfo.Color (records.Car.paint, Player.apply_paints; SKID_CAR_TB keeps the dealership
  colour). Tested by script: 0x425 after the purchase carries 0x83C36CFF for "12807423".
- **Window tint** (category 3) RGB did not show either: the 2011 car record's new 4 bytes @0x24 are a
  colour the client applies after building the car with Color and a default glass colour 0x82CCCCCC
  (client 0x708054..0x708086, through the vehicle colour setter 0x4c0a60 -> 0x4690b0, ColorSetReform
  only); 0x82RRGGBB is the second layer = the glass. Native now sends the tint there (records.Car.tint).
  Neon (2) and decals (11) colours are not in the car record; not checked yet (decal texts can be
  negative numbers: "-3180032").
- **Booster gauge does not fill when drifting** (user, 2026-10-13, native game): open. Since the switch
  the client sends no 0x2e4 combo at all (every proxy session with driving had some), so it does not
  count drifts. Differences found: (1) 0x3e0 at login (the client starts today's day mission, idx 90
  from our 0x488) was refused natively (the 2008 server accepted it): now accepted; (2) stats: the
  2008 server sent base stats from the TW tables ((2, 3, 3, 2) for car 81), native from the 2011
  VehicleUpgrade.xlt ((38, 24, 53, 45) at the upgraded grade) - unverified which scale the client wants;
  content flags are identical.
- **Story missions** (quests) stayed in progress after logging out (user, 2026-10-13): the 2008 server
  gave up the quest in progress when the character left (XiCsCharInfo::SetEnable -> QuestGiveUp: state
  4, saved, "QUEST" play mode). Native now does the same on disconnect, and answers 0x10c QuestFail
  (state 3, fail + 1) and 0x10e QuestGiveUp (state 4), which it did not before.
- Status 2026-10-12: login, character, city, HUD (MainUIType=1), inventory (F3) and the item shop (F4) work; the launcher starts the client reliably.

### Server tables from the 2011 client (2026-10-12)

- Items are numbered by row, parts then usable items, one index (XiStrMyItem.TableIdx); the
  2008 server had 196 + 175 rows, the 2011 client 749 + 1112: every item showed as another one
  (drops, keys, Mitron, sell prices). The database stores items by code (SKID_ITEM_TB.ITEMID).
- `tools/client_tables.py`: the client's effective tables (Data_US over Data, patch packs over
  archives; e.g. ItemClient comes from Patch.003, UseItemClient from Patch.004).
- `tools/convert_2011.py`: ItemServer.tdf and UseItemServer.tdf rebuilt from the 2011 client
  (rows and order as the client; column map in the docstring; ItemServer's server-only columns
  12-14 from the 2008 row or the most common values for the part type and grade). 2008
  originals: backup/data_tw_2008/. Car keys are found by code (CreateCarKey: code from the
  VehicleList row -> XiItemTable::GetItemByID), so VehicleList must carry the 2011 codes.
- Not converted yet: VehicleList / VehicleUpgrade / VShopItem / VisualItem (init, by column name;
  VisualItem has one column per car type, 76 -> 148: check the server's limit first), Assist
  (options), quests, part-time jobs, instant missions, drops.
- 0x21d MoveVehicle (C>S, area/barea) is 4 bytes longer in 2011 (filler after XiCarAttr; the
  position moves from payload 0x10 to 0x14). The 2008 server read the extra bytes as further
  commands (0x582 NotifyDelCharacter: "Delete Character:hack detected(N)" in chat, plus a delete
  notice by UDP) and the race traffic relay read the position from the wrong place.
  `handlers/area.py` removes the 4 bytes. Server debug output in chat: ZoneServerConfig.ini
  DebugLog=1 -> 0 (original in backup/data_tw_2008/).
- VShopItem/VisualItem conversion (convert_2011.py --shop): the first version crashed the server
  at load (page fault 0x4addfe in the visual item map iterator, seen in XiQuestTable::LoadFile):
  2011 strings longer than the server's fixed buffers (pdbtypes sizes are bytes: ushort[64b] =
  31 characters; XiVShop::ITEM_INFO tszMarketName is followed by a std::vector) and car type ids
  >= 100 (XIVISUALITEM_INFO.Compatability is char[100]). The converter now truncates the string
  columns and keeps car type ids < 100 (87 of 148); the server loads them.
  LoadVisualItemList (0x66f950) limits: car type ids in a 100-entry array, fit flags in a byte
  array indexed by car type id (112).
- admin's G Coin: SKID_UNALISCOIN_TB.COIN (set to 100000 on 2026-10-12).
- Driver dome: in the 2011 client players only use the upper dome (Floor1); the lower one (B1)
  is for the later Neo City update. Contents.ini OMDBase.FloorB1=1 -> 0 (original in
  backup/data_tw_2008/); the content flag conversion passes it on to the client by name.
- Visual items / drift shop messages (`handlers/vshop.py`): XiStrMyVSItem 48 -> 116 bytes
  (PlateName 20 -> 40, 48 new bytes at the end) in 0x4b1 (list) and 0x4b2 (changes, + State);
  0x4b3 buy request: PlateName 40 -> 20 and 5 new bytes dropped. 2011 paints send their colour
  in PlateName as 10 spaces + a 9-digit code ("Unreliable data." from the 2008 server): the
  server gets the code, the client gets the spaces back. 0x425 VisualUpdate: XiStrCarInfo +4
  (bought wings did not show). 0x3e1 InstantStartAck: 5 more bytes in 2011 (u32 @6, u8 @0xa);
  without them the client read the stream and started a party patrol.

### Native auth and lobby (2026-10-12)

Direction from the user: start the native server now; keep the original server's
architecture (auth/lobby/game/area/barea as separate services and ports, the same SQL Server
database `SKDBTW` and tables, `serverlist.txt`, ini config) but use the 2011 client's file
formats for the tables (`.xlt`/`.tdf` as the client has them, not converted to 2008 columns).

- `emulator.ini`: a service with ZoneServer port 0 is native (`dcemu/native/`). Now auth 11005,
  lobby 11011 and ranking 11051 are native; game/area/barea are still proxied to the 2008
  server. `[database]`: SQL Server published on 127.0.0.1:14330 (docker-compose.yml), sa,
  server id 100. `[native]`: `server_list` (the 2008 serverlist.txt), `data`.
- Needs `Emulator/.venv` with python-tds; `./driftcity.sh emu` uses it. Tables:
  `Emulator/.venv/bin/python -m tools.sync_data` copies the client's effective tables (57,
  patches applied, US over base) to `Emulator/data/{Init,World}` unchanged.
- Verified with scripted clients against the real DB: native login reply (0x16 + 0x17) is
  byte-identical to the proxied 2008 one; wrong password -> -2, unknown ID -> -1; check-in and
  the character list (0x3d) give entries byte-identical to the 2008 lobby (XiStrCharKey.dTime
  = CDATE read as UTC minus 3600); name check (taken/free) works.
- Character creation (0x52) as the 2008 server does it: INSERT into SKID_CHARACTER_TB with
  `OUTPUT INSERTED.CID` (identity column), `PC_SKID_CREATECAR` (grade 1, Mitron = the car's V1
  capacity from the 2011 VehicleUpgrade.xlt), then CURCAR, in one transaction (lobby.CREATE_SQL).
  First try with the real client failed: without SET NOCOUNT ON the row counts come back
  before the SELECT (pytds "Previous statement didn't produce any results"), the client got no
  0x53, but the rows were written (CharacterS, cid 100002). Fixed; tested by script (and the
  taken name -> cid -1).
- The 2008 game server's check-in does not need the login state (Cmd_CheckInGame only runs
  CheckGameGuard; LoadChar reads the DB), so native auth/lobby + proxied game works together.
- To go back to the 2008 auth/lobby: `auth = 11005 12005 56`, `lobby = 11011 12011 56`.
- Next: the ranking service's messages, then the native game server (reading the 2011 tables
  from `Emulator/data/`).

### Native game service, first part (2026-10-12)

`Emulator/dcemu/native/game/` (`records.py` 2011 layouts, `player.py` loading from the DB,
`login.py` handlers). Answers everything a real client sends while entering the city (see the
login.py docstring); not switched on yet (emulator.ini still proxies game): area/barea must
go native at the same time (the 2008 area server only knows characters its own game service
loaded), and the gameplay handlers the proxy already covers come first.
- Verified by replaying a recorded client session (scratchpad replay.py: the client's messages of
  one connection, as received) against the proxy and against the native service and comparing
  the replies: identical except times, weather, the session serial, and the stats (now the
  2011 VehicleUpgrade values: Drifter V1 is accel 53 / speed 38, the 2008 table had 3 / 2).
- How the 2008 server fills the character (BS_GameDB::LoadCharInfo, Cmd_LoadChar): PType 'A'
  for accounts in adminlist.txt (AdminTable::IsAdmin; also when Cheatable); Flags 0x4000000
  when PLAYMODE 'BATTLETUTORIAL' has wins; QuickCnt = PLAYMODE 'ARBEIT' WINCNT; ExpInfo =
  NEXP plus the LevelServer.tdf sums at this and the next level; times = DB time - 3600 (the
  2008 server's clock is an hour behind UTC; native.CLOCK_SHIFT keeps the native services on it).
- Items: TableIdx = ItemClient.tdf row, or 749 + UseItemClient.tdf row (the 2011 tables give the
  same indices as the 2008 server); ExpireTick = CTIME, or SKID_SERVER_TB.SERVERPTICK when 0;
  the list goes out in messages of 12 items (ListUpdate 0x40000, then 0x40001) plus 0x1a5
  (InvenIdx + ASSIST_A text). Quests: TableIdx = QuestClient.tdf row, sorted. Visual items:
  TableIdx = VisualItem.xlt unique id (column 4).
- Equip stats = for each part on the current car: ItemClient value (column 9) + NRANDOM; char
  stats = level / 2 each (Contents.ini Main.HalfLevelPoint; the flag is gone in 2011).
- Proxy fixes found on the way: the item list frame [0x191, 0x191, 0x1a5] was not split (0x1a5
  had a fixed size in commands.py), so the item list went to the client unconverted; replies the
  2011 client reads longer are now padded (handlers/game.py PAD_TO_2011: 0x488 +8, 0x30f +1,
  0x3f6 to one coupon entry).
- `Server/tools/dev/dispatch.py` -> `dispatch_2008.txt`: the 2008 server's type -> handler map
  per service (from BS_ZoneServer::InitializeNet; 316 entries). `handlers_2011.txt`: the 2011
  client's type -> handler and the size it reads. `sizes_2008_2011.txt`: the S>C messages whose
  size changed (117), e.g. room create/join 0x1cd/0x1d4 (battle zone rooms), buy/select/upgrade
  car 0x56/0x5a/0x5c (+4, the car record), fuel charge 0x2d4 (+4), char update 0x169 (+50),
  game char info 0x295 (739 -> 846), party 0xf0-0xf8 (+4), friends (+4), vehicle moves
  0x221-0x226 (+4). Not all are converted by the proxy yet.

### Character deletion, 2011 (2026-10-12)

The 2011 client deletes in two steps (character select page, client setting
DeleteCharExpireDays = 3): 0x32 (name, cid, state 'R', days) reserves the character, 0x32 with
'P' cancels; the server answers 0x32 with the state and the deletion time (time_t on the client's clock, UTC - 3600 like the 2008 server's: with UTC the client showed 59 minutes left for a wait of 0). A
reserved character cannot enter the game. When the time has passed, selecting it asks "Are you
sure you want to delete this ID?" and Yes sends 0x54 DeleteChar (name, as 2008), answered with
0x54 (name). The character list record changed for this: XiStrCharKey @0x3e = state ('P'/'R'),
@0x42 = deletion time (2008: car type, colour; the 2011 client never read those). Native lobby:
STATE 'R' + DELDATE while reserved, then the 2008 server's delete (STATE 'D', MEMBERID '$'+id).
emulator.ini [native] delete_wait_days overrides the wait (0 = at once).
- Login tickets (auth -> lobby) are derived from the account and a secret in
  `Emulator/.ticket_secret` (gitignored), not kept in memory: the client checks in to the lobby
  again with its old ticket after the emulator restarts (it does not log in again), and an
  in-memory ticket made the lobby show no characters and refuse creation after a restart.
- The client's clock on the character select page comes from the lobby keepalive 0x02 (u32 server
  time): deletion time left = entry @0x42 - that time. The native lobby sends it at once on
  connect and on the 2008 server's clock (native.now); sent only after 3 s, the page was drawn
  with time 0 ("20738 days" left), and with real UTC the countdown was an hour off.

### Kick, block, ban (session 3, 2026-10-13)

The 2008 server has them on its GM console only (ZoneServer_GMParser.lua "kick" / "block", GM port
21158; GM_Kick_Player 0x688620, GM_Block_Player 0x688450) plus the checks in Cmd_LoadChar:
- kick: "Kicked by a GM." to the player, BS_Session::Disconnect, and with a time BS_GameDB::BlockGame
  (`update SKID_CHARACTER_TB set BLOCKGAMEDATE=GetDate()+? where cid=?`, days).
- block = chat block: `BLOCKCHATDATE=GetDate()+?`, 0x9c4 ChatBlock (bool, long until) to the player;
  the 2011 client keeps both in its game object (handler 0x5184b0).
- Cmd_LoadChar: the character already in the game -> "Disconnecting by another login!" to the old
  connection, which is closed, and error 20088 to the new one; BLOCKGAMEDATE in the future -> 20089;
  BLOCKCHATDATE in the future -> 0x9c4.
- account: getAccInfo's MEUSERMT.VALID; the 2011 client shows login result 12 as "blocked".
The native server had only the VALID check at login. Now `native/admin.py` has all of the above (its
docstring is the reference), the lobby and LoadChar also check VALID (login tickets outlive a ban), and
`proxy.live` lists every open native connection (Session.close drops one). A kick closes the account's
game, lobby, area and barea connections. Commands: GM chat (game/misc.py) and `tools/gmctl.py` through
the control port (`emulator.ini [emulator] control_port`, 127.0.0.1 only; 0 = off).
Known gap, as in the 2008 server: the game check-in (0x78) takes the account name from the client
without a ticket, so the game port trusts whoever connects (fine for a LAN, not for the internet).

### Network play (session 3)

`serverlist.txt` holds 127.0.0.1 for every service. Native auth now sends loopback addresses as the
address the client connected to (ServerEntry.encode), so the list works for the local client and for
one on the network; a real address in serverlist.txt is sent as it is. The emulator listens on 0.0.0.0.
The other machine: its own copy of the client and launcher, `Server/tools/dev/run_us2011.ini` `address`
= this machine's address. UDP (11400 / 11401) still goes to the container and the native area sends
0x323 with port 0, so cars are relayed by the server (area / barea 0x21d -> 0x221), not peer to peer;
*two real clients seeing each other in the city or a race has not been tested yet*.

### Native area service (2026-10-12, session 2)

`Emulator/dcemu/native/area.py` (docstring: every message and size). The 2008 handlers
(`Cmd_EnterArea`, `Cmd_TimeSync`, `Cmd_AreaStatus`, `Cmd_ExitArea`, `Cmd_MoveVehicle`, the `Cmd_Cast*`
of the agent) read with sdis.py; layouts from the PDB (`BS_PktEnterArea(Ack)`, `XiCarMove`,
`XiTCSCarMove`, `XiTCSSignal`, `BS_PktCastTCS` ...).
- EnterArea 0x232 -> 0x233 (area, 1, the client's local time, server tick); TimeSync 0x21c echoes
  the local time with the server tick; AreaStatus 0x2aa -> 0x2ab (cars in each of 100 areas). The
  area connection names its car by the serial from JoinChannel (game) and the name; the native area
  needs nothing else from the game service, so it can run with the game still proxied.
- Moves (0x21d) go to the other cars within 300 m as 0x221 MoveVehicleExt (2011: 106 bytes) and a
  leaving car as 0x226 RemoveVehicle *(the 2008 server's choice between 0x221 and 0x224 per observer
  was not read; not yet tested with two clients)*. ObjectUpdate 0x2d0 goes to the whole area.
- *(Session 9: the city traffic is native now, see "Session 9"; this was the agent setup.)*
- **City traffic comes from TrafficAgent.exe** (in the container, started by `start.sh`), which
  connects to the area port like a client: 0x2c1 RegisterAgent (40 areas: 4-13, 28-37, 52-61,
  76-85, ten per city), 0x21c TimeSync once a second, then ~30,000 commands a second (measured:
  1.83 M a minute): 0x2be CastTCS (area, x, y, XiTCSCarMove) and 0x2c3 CastTCSSignal (area, x, y,
  XiTCSSignal), and 0x2c0 FlushCast once a second. The server sends each car within 320 m of the
  cast position 0x2bd / 0x2c2 (0x2bc CastTraffic -> 0x21e), queued until the flush, so a player
  gets one frame a second such as `0x2bd 0x2bd 0x2c2 0x2c2` (as recorded from the 2008 server).
  The native area does the same; the CPU cost is small (about 1.3 s of CPU for 1.8 M commands).
- `Server/server/TrafficAgent.ini` now has `Host=169.254.1.2` (the host as seen from the container,
  podman's host.containers.internal; the emulator must listen on 0.0.0.0): the agent always
  connects to the emulator, which passes it on to ZoneServer when the area is proxied (tested: the
  2008 server still sends the city cars) or serves it when native. Its frames are not written to
  the message log (`session.log_frames`; a count every minute in native mode). The agent does
  not reconnect when its connection drops (it keeps running, without traffic): `driftcity.sh emu`
  kills it in the container once the emulator listens, and `start.sh`'s loop starts it again.
- Tested: `tests/test_area.py`; a scripted client and the real TrafficAgent against a second
  emulator (area native on 11131, a second agent in the container in `/tmp/agent2` with symlinks to
  /srv/zoneserver and its own ini): the client near a traffic road got 2 cars and 4 signals a second.
  Not yet tested with the real client.
- Native services can take whole frames (`handlers.whole_frames`): the area walks commands by
  their 2011 sizes itself; the proxy's 2008-size split would cut 0x21d (0x64 in 2011) wrongly.
- Server tick: `native.tick()` = ms since the emulator started. With the game proxied, the client
  gets the 2008 server's tick from the game port (e.g. 0x311) and the emulator's from the area;
  if traffic cars appear at wrong places in that setup, look here first.
- **Tested with the real client (2026-10-12): area and city traffic work** (area 4, 0x2bd from the
  agent). A first "no traffic" report was the tutorial gate: area 3 (city 1, channel -1; areas 0-3
  have no agent traffic, under the 2008 server too; area = 4 + 24 x (city - 1) + channel, judging
  by the agent's areas).
- 0x323 TimeSyncByUDP: the 2008 server sends it on the area connection when the client's UDP time
  sync (UDP 11400) arrives, right before the 0x21c reply with the same local time. UDP still goes
  to the container, which no longer knows the area connection, so the native area sends it itself
  (IP = the client's address, port 0). The client counts them (handler 0x509ff0, [+0x3d30c]), and its
  update 0x5408fc returns early after more than 3 time syncs without one. *Whether anything visible
  depends on that is not known: it was added while chasing the tutorial-gate report.*
- Traffic collisions 0x220 (0x52) / 0x223 (0x36) are relayed to the cars within 300 m.
- Not done: a native UDP service (11400/11401; P2P addresses in 0x323), groups
  (BS_GroupMgr, 0x236/0x237/0x23c/0x242: parties), SilentMove/ObserveMode, speed-hack checks.

### Battle zone, race rooms, native BArea (2026-10-12, session 2)

Moved to **`BATTLEZONE.md`** (next to this file): what works, the race flow, every message layout
the proxy converts (0x1b9, 0x1cc, 0x1cd, 0x1ce -> 0x1be, 0x26d <-> 0x26c, 0x1ec, 0x5a / 0x56),
practice mode (Contents.ini BattleZone.PracticeMode is now 0), race traffic (native BArea +
`native/race.py`, written, not switched on), client facts and the open list. Parked: the native
server comes first.

### Native game, batch 1: session basics (2026-10-12, session 2)

The user's direction: the native game service before the battle zone. Survey of every game-port
request in the recorded sessions: 84 types, 21 answered natively before (login/loading). Porting
order: 1 session basics, 2 items and cars, 3 quests / part-time jobs / instant missions / rush /
party / auction, 4 battle zone with native barea; switch game (+ barea) when it covers what the
user uses. Method per request: the recorded 2008 reply (logs), the 2008 handler (sdis.py) for the
rules and SQL, the 2011 client handler for the layout; scripted test on test ports with throwaway
characters (scratchpad tests/game_batch1.py: native lobby create, game check-in, requests; then
the rows are deleted).

Done (`native/game/position.py`, `channels.py`, `session.py`; all tested by script against the DB):
- **Position** (0x30e, 0x314, 0xa2): the 2008 position states (0 new, 1 tutorial gate, 2 city, 3
  driver dome) and its 10 tutorial-gate start points (ZoneServer.exe, Cmd_FirstPosition). **At the end
  of the tutorial the character goes to Station 1** (user, 2026-10-12): the client sends 0x314 (2011:
  + u8 1) and then its own 0xa2 with the Station 1 position, but the 2008 server answered 0x314 first
  with the stored tutorial position, so the car went back there. Native: a character in the tutorial
  gate gets Station 1 of Moon Palace (Icon_Moonpalace_Client.tdf "Station 1" -3379.0, 1213.2, 85.5;
  data.Tables.stations, all four cities), state 2, saved. The proxy does the same for the 2008 server's
  answer (handlers/game.py position_ack). SaveCarPos is written at once (2008: at logout).
- **Channel lists** (0x35c -> 0x35d, 0x30c -> 0x315 + 0x316): 13 unowned channels, the next channel
  battle time from Contents.ini CBattleDay/CBattleHour (matches the recorded value). 2011
  XiSmpTeamInfo has one more byte before the team name (0x316 handler 0x51b4b0): 0x316 records 136 ->
  137, 0x35d 306 -> 308; converted in the proxy too (the client's log had asked for 1787 / 4022).
- **Coupon counters** 0x3f2 (refused and sent back if any went down; SKID_COUPONVALUE_TB),
  **tutorial clear** 0x104 -> 0x105 (PLAYMODE BATTLETUTORIAL), **G Coin** 0x578 -> 0x579
  (SKID_UNALISCOIN_TB), **chat** 0x92 -> 0x93 to the game channel (team / party chat not yet),
  **drive info** 0x2d1 (2011 + 44 bytes; Mitron and km saved), **refuel** 0x2d3 -> 0x2d4 (the 2008
  rules: Main.MitronUnitPrice, capacity + 1, money; 2011: request + 4 bytes, reply + u32 @0x32 =
  "leave the fuel dialog alone"; converted in the proxy too: the open issue "Mitron cannot be
  refilled" may be this), no answer for 0x7a, 0x86, 0x87, 0x12e and the 2011-only 0x327, 0x32d,
  0x466, 0xc28 (the 2008 server did not answer them either).
- Car type 23 has an all-zero row in the 2011 VehicleUpgrade.xlt (capacity 0): not a car to test with.
Left in batch 1: 0x294 GameCharInfo (-> 0x295, 741 -> 846 in 2011), 0x2e4 TrafficItemEvent (combo
exp, item drops: 0x2e5, 0x410, 0x192), 0x82 GameStream (GM commands typed in chat).

### Native game, batch 2: items and cars (2026-10-12, session 2)

`native/game/items.py`, `cars.py`; item rows from the 2011 tables (`data.Tables.item_info`: ItemClient.tdf
id 2 / kind 0 / grade 6 / level 7 / cost 12 / sell 13 / shop 15; UseItemClient.tdf id 0 / kind 1 / cost 7 /
sell 8 / shop 13 / stack 5, 99 when empty), vehicles from VehicleList.xlt / VehicleUpgrade.xlt by column
name, coupon cars from Coupon.xlt. Errors as the 2008 server: 0x0001 (u16 byte length + UTF-16) with the
GlobalText_Server.xlt text (`login.error`; the 2008 named keys are numbers: NotInitializedChar 20017,
NotFoundItem 20024, NotFoundCar 20025, ItemEquipFail 20027, ItemUnEquipFail 20028, ItemBuyFail 20029,
ItemSellFail 20030, BuyCarFail 20042). All tested by script against the DB (throwaway characters).
- **2008 item types** (ItemTypeStrToVar): speed 0, crash 1, accel 2, boost 3, op_S 4, op_C 6, op_A 7, op_B 8,
  op_F 9, unknown 10; usable items 5. **2011 docking parts** (dock_A/B/C/S/D, 144 rows, O grades) are
  unknown to the 2008 server; the user: unlike option parts (own slot), they "are put right on top of
  the parts themselves and give more bonus points". Their client request is not known yet (none
  recorded): refused by EquipItem for now; native type 11.
- **Buy / sell** 0x195 / 0x197 (2011 buy + u32 -1): shop flag, parts one at a time, cost x count, usable
  items stack (FindStackableItem), new items: GID from SKID_SEQUENCE_TB.item_sq1, inventory index =
  PARTINVENIDX + 1 (PC_SKID_INSERTITEM); 0x192 states 1 new / 2 removed / 3 changed.
- **Equip / unequip** 0x199 / 0x19b: SKID_ITEM_TB.STATE = slot << 16 | 1 (Xerender: speed in 100 and
  101, boost in 109); at most Main.PartsInvenLine (2) parts of a type per car; options need a part in the
  slot and a fitting grade (CheckGrade: N <- FN ON; S <- FN FS OS; H <- FN FS FH OH; E <- FN FS FH FE OE);
  a part comes off with its option. Stats count the parts' values; options' bonuses (Assist) not yet.
- **Cars** 0x59 select (CURCAR, 0x5a, 0x425 with an "age" counter), 0x55 buy (stage rule Etc.CarOpenStage
  vs Sellable / closestage, default grade Price, garage floors x 8, coupon item used up, PC_SKID_CREATECAR,
  key item = File Name without .nif).
- **2011 VehicleList "Sellable" is a category, not a stage**: 0 not sold (191 cars), 1 dealership (83), 50
  premium / event series (ST, BT, MINI: 34), 101 (4), 10001 / 20001 / 30001 / 40001 the four starter cars
  (Laputa, Drifter, Metro, Birdie). The user: the Drifter must be buyable -> native: any Sellable other
  than 0 can be bought (the 2008 Etc.CarOpenStage comparison is not used). Garage floors = HANCOINGARAGE +
  the "i_d_garage" drift shop items + 1 (the 2008 server's SQL), 8 cars each.
- **Drift shop** (`native/game/vshop.py`, docstring has every rule): VShopItem.xlt (1053 rows, by column
  name: UniqueId = the client's TableIdx, categories, Mito / G Coin ($Price) / mileage prices per period,
  Bonus Speed / Accel / Boost / Crash) and VisualItem.xlt (`Tables.visuals`: category index, the car
  types an item fits; categories 1 Paint, 2 Neon, 3 Window Color, 4/5/6 Aero, 7 Spoiler, 8 Tire, 9 Number
  Plate, 10 Muffler Flame, 11 Decal, 12 Horn, 13 Engine sound, 32 GrossPaint, 33 UseItem, ...).
  **2011 colours** (the user): paint, neon, window colour (tint), decals and gloss paint take any RGB colour:
  the client sends it in the item text as 10 spaces + RRRGGGBBB ("          023110162"); stored as the
  code in ITEM_DATA (the proxy already passed the code; the 2008 server refused it before that:
  "Unreliable data."). Periods: index 1 7 days, 2 30, 3 90 (else 365), 4 for good (forced when the item
  has a price for good); SKID_VSITEM_TB.PERIOD in days. Bought items go on the car when they fit, replacing
  the item of the same category; visual items stay with their car (unequipped: STATE 0, CARID kept).
  Equip 0x4b5 sends slot -1 in 2011: the 2008 server refused every 2011 equip ("Failed to equip the
  item."), native goes by category. G Coin purchases take SKID_UNALISCOIN_TB.COIN (2008: an external
  billing service). Bonus stats count in the equip group. Tested by script (colours, replacement, equip,
  unequip, money). Not native yet: category 0x13 items (parts boxes, given as inventory items), expiry,
  selling (DropVisualItem).
- **Misc tab (TOP_ETC) items** (`native/game/driftuse.py`, docstring has the rules; user asked for all,
  2026-10-13). Found in the client: it sends 0x4b9 VisualItemUse only for categories 16, 22, 27, 37, 43,
  51, 54 (0x5f6fa0); UseItem (33) / package set (50) bundles cannot be used from the drift inventory, so
  they become inventory items when bought (VisualItem.xlt value column "item count"; also converted at
  login if bought earlier). Done and script-tested: inventory / garage extension (0x2fa), Mito prizes,
  bundles, VShopItem "Instant", inventory gift boxes / packages (0x1a1, RewardGroup.xlt via
  UseItemClient column 3), scratch cards (0x5aa / 0x5ab, 0x5ac / 0x5ad), lucky bags (0x5b4 / 0x5b5),
  Name Change Kit (0x6a / 0x6b RenameChar, found via the Dev Ed name table). Message names:
  `Server/tools/dev/packets_deved.txt` (the Dev Ed client's handler table, 516 types).
  Drinks and boosters (items.py: holds / play_bonus, script-tested): EXP drink +30% exp from play
  (races, combos (on the fraction), missions, jobs, chases, rush, lap time; not quests), MITO drink +50%
  Mito (emulator.ini [items] drink_exp / drink_mito), Item Drink = two pick-up rolls (PickupTrafficItem),
  Mittron Fuel Booster = refuel at half price + sale flag (Cmd_FuelChargeReq, char flag 0x363); only
  unexpired items count (also for 0x5dd). Gio, Turbo Man, Mittron Enhancer Booster: client-side (the 2008
  server never reads their flags). 2008 char flags 0x35d.. 0x365 = the 0x5dd order.
- **Dealership purchase conditions** (user, 2026-10-13: a locked panel with Korean text on every car): the
  client writes the condition texts (GlobalText 11979-11996: Mito, level, coupon car, garage / inventory
  full, quest cars; 0x5d7160, mask from 0x5d2250) into the label ID_AUTOSHOPADVMENU_MSG_TXT1_2ND only with
  the content flag Etc.NoviceAdvUI2nd ([game + 0x2bc] & 0x8000000); without it the label keeps its
  game.nui text (CP949 "coupon needed"). Now sent as 1 (NEW_FLAGS). Free space as the client counts it:
  garage (HancoinGarage + 1) x 8 - cars, inventory (HancoinInven + 2) x 20 - items.
- **Community window (friends / crew) did not open** (user, 2026-10-13): its open function 0x59c6f0 needs
  the content flag BattleZone.Friend ([mgr + 0x294] & 2), else text 10745 "This feature is currently
  unavailable."; now 1 (NEW_FLAGS). It then sends 0xe6 and, only with a team (char +0x4e != -1), 0x357
  TeamMembers, and shows itself when 0xe7 (and 0x358) arrived (0x51b7e0, 0x530e30): 0x357 is not
  answered, so a character in a team would wait forever (no teams yet).
- **Party requests were never accepted** (user, 2026-10-13; `native/game/social.py`), four causes: (1) 0xe4
  PartyPreCheck from a car's menu carries only the serial (name empty): looked up by name -> "does not
  exist"; (2) its reply's party id must be -1 for "no party" (client 0x51a890 invites only then), it was 0
  and the asker's party instead of the target's; (3) no handler for 0xf0 PartyInvite (invite -> 0xf2
  PartyJoin; the other way is 0xf6 PartyApply -> 0xf7 PartyAccept, which was handled like 0xf2 with the
  roles swapped); (4) an old empty 0xf4 handler in misc.py ran instead of the real PartyLeave.
  Script-tested with two clients (sizes 120 / 328 / 168 / 260 as the client's handlers).
- **Party combos** (user, 2026-10-13; `native/area.py`): area messages 0x236 EnterGroup (group = party id)
  -> 0x242 (group, count), 0x237 ExitGroup, 0x23c GroupCombo (34 bytes, relayed to the group's cars with
  the group's count @0x1e), 0x23f GroupComboReset (2008 BS_GroupMgr). The client sends 0x23c in one frame
  with a 0x21d move; without its size the whole frame, move included, was dropped. Script-tested.
  A kicked member now gets 0xf5 PartyBanish instead of 0xf4 PartyLeave (the client's "kicked" message).
- **Coupon book** (`native/game/coupons.py`): stamp list 0x3f5 / 0x3f6, MarkCoupon 0x3f7, OpenCoupon 0x3f9,
  GetCoupon 0x3fb (coupon item), server-side counters 0x3fd (Real Match wins DUEL_RM, rush tries
  RUSHTRY; SKID_COUPONPARAMVALUE_TB). **2011 XiStrCouponForVar is not 10 floats**: combo and drift are
  u32 (client 0x709e50), the times are seconds; read as floats the combo / drift counts were lost and
  updates were refused as "went down". Script-tested.
  Left: passive assists (41), discount coupons (51, own dialog), Pick'em
  (gacha_observe, 0x834-0x83a ObsGacha), Gotcha coins (53), auto drive / quick slot / fill-up (34, 35,
  39), replay / ghost passes (44, 45), car transfer (43), Premium Packages (49, no contents in the
  tables), Seed Parts and the "ST" / "Normal" cards (no inventory item in the 2011 tables).
- **Car upgrade** 0x5b -> 0x5c (2011: request + 4 bytes; reply + i32 @0x12 that the client adds to the
  money). The 2008 server sold grades as drift shop items (CARREMODELING_R1R2..) for G Coin through
  external billing and **never answered the 2011 request** (recorded): upgrading cannot work through the
  proxy. 2011 VehicleUpgrade.xlt: "UpgradeMito" (Drifter V2 28000 .. V9 850000), "Req Level", "UpgradeCon"
  (UpgradeCondList.xlt: medal counts etc.; empty for the cars seen), "OptionID" (part options per grade).
  Native: Mito + level, NUPGRADE + UPn_DATE (conditions and options not applied yet). Tested.
- **Item use** 0x1a1 -> 0x1a2 (same size in 2011) + 0x192: XiCsCharInfo::UseItem 0x5ce920 by use kind (the
  2008 UseItemTypeStrToVar codes; fuel fills the car, accel / crash / speedpointup give a timed stat bonus
  = the item-use stat group, stats are sent again when it ends; the rest is used up and acts on the
  client; 2011 kinds unknown to 2008 (battle_quick, gacha_parts, mobile_shop, ...) are used up, kind 0x1a).
  UseItemClient.tdf value col 9, time col 10. Tested (Accel. Enhancer: +30 accel for 50 s).
- **Bonus update** 0x5dd (9 u32: exp, Mito, Repair Girl, Turbo Man, sticker, double upgrade, half Mitron
  charge, 2x drop, inventory upgrade), sent at login, after a drift shop purchase and for 0x5dc
  ItemExpireCmd: 1 per held drift shop item of those categories (guess: the 2008 values and expiry are
  not read yet).
Left in batch 2: docking (needs a recorded docking request), 0x1a3 ItemUseEx, the drift shop leftovers above.

### Native game, batch 3: quests, jobs, combos, instant missions, rush time, leftovers (2026-10-12, session 2)

Modules `native/game/progress.py` (exp / level: CalcExperience on LevelServer.tdf; play-mode rows),
`quests.py`, `jobs.py`, `combo.py`, `instant.py`, `rush.py`, `misc.py`; each module's docstring has the
layouts and the 2008 rules it follows. All tested by script on the test ports (scratchpad
tests/game_quest.py, game_jobs.py, game_combo.py, game_instant.py, game_misc.py; rush with fake
sessions in tests/rush_unit.py since the schedule cannot be forced from a client).
- **Quests** 0x106 / 0x112 / 0x108 / 0x10a / 0x312: QuestClient.tdf rows (its columns hold the 2008
  QuestServer.tdf's), SKID_QUEST_TB; replies match the recordings.
- **Part-time jobs** 0x141 / 0x143 / 0x14f / 0x151 / 0x14b / 0x145 / 0x149: ArbeitClient.tdf (the list
  follows the 2011 rows, so it differs from the recorded 2008 list); no item rewards (the a_I_ groups
  are not defined client-side).
- **Combos / traffic items** 0x2e4 -> 0x2e5 (+ 0x410 ComboExp, 0x192): drop tables from the 2008 server
  folder (ItemDropServer.tdf rates per level and group, 3 play-time blocks x 6 drop modes: 1 traffic,
  2 combo, 3 rush hit; groups from ItemServer.tdf / UseItemServer.tdf column 3, matched to 2011 TableIdx
  by item id), comboexp.txt (exp per level, fraction kept); same frames as recorded (1, 212, 2).
  Not done: the bot checks ("autoSuspect", test question, _Bad table), premium +30%, double drop.
- **Instant missions** 0x3e0 / 0x3e9 / 0x3e2 / 0x3e7: Instant_Client.tdf (147 rows; the 2008 server
  had 99, so 2011 indices past the first new row were unknown to it: the recorded "Cannot find a
  Courier service request" on a party patrol). 2011 columns = 2008 + two after the level range + a
  description, no reward group. Patrols give items at 50 / 100 / 150 / 160 places
  (InstantDrop_Server.tdf) and the final exp on completion. Day missions (token events) refused.
- **Rush time** 0x456 / 0x458 / 0x45e / 0x45a / 0x462 / 0x463, server 0x45c notices, 0x45d control,
  0x45b status, 0x460 result, 0x464 member count: rushtimetable.txt schedule (every hour in Data_TW),
  per city channel, controller = first HUV notifier, HUV hits drop mode 3, winner gets i_n_00003 and
  Mito by city. 0x460 was never recorded (2008 layout sent). Not done: controller switch (0x465/0x461).
- **Leftovers** (`misc.py`): 0x294 GameCharInfo -> 0x295 at the 2011 size (844; offsets from client
  handler 0x515be0: car @0x11b, stats @0x14c, team 384 @0x1b4, serial @0x334), 0x348 -> 0x349 no team,
  0x35e -> 0x35f, 0x387 -> 0x388, 0x24c -> 0x24d empty, 0xf4 no answer, **GM commands** in chat (0x82;
  PType 'A' or adminlist): gmlevel / gmexp / gmmoney / gmitem [name] value, answered
  "cmd(a,b,c)=[1]" as recorded, 0x169 CharUpdate + stats.
- Still proxied-only or missing in native game: HUV chases (0xbd ... see below), teams, parties,
  auctions (0x246), the battle zone rooms (BATTLEZONE.md), docking, 0x1a3.

**HUV calls (user, 2026-10-12: "just tried one and it didn't work")**: using the HUV Call Unit sends
0xbd ChaseRequest (u8 now, XiVec4 position; same as 2008); the 2008 server answered 0xba ChasePropose
(serial, start / end position 0 (the client picks a spawn itself), type 1, course, HUV level 70,
HUV id 10035, "test") and the client sent nothing more. The 2008 HUV comes from the TW HuvTable.tdf
(10035 = B-Monster S at level 70); the 2011 client's HuvTable.tdf has other ids per level (B-Monster S
= 10017 at 70; levels up to 80) plus NeoHuvParam.xlt / ChaseSpawn.xlt / BossHuvInfo.xlt, so the
client most likely found no such HUV. **Native chase** (`native/game/chase.py`, tested by script
tests/game_chase.py): HUVs from the 2011 HuvTable.tdf, which carries the server columns (decoded from
ChaseTable::ReloadChaseTable: level, id, name, rate, Ea, speed, max speed, boost x3, durability,
avoidance x3 @13-15, exp @16, Mito @17, item group @18, drop rate @19); 0xbd -> 0xba, 0xb4 -> 0xb5
(48-byte HUV units as 2008: the "44" in sizes_2008_2011.txt is the client's fixed part, the units are
variable), 0xb9 echoed, 0xbb drop mode 0, 0xb7 -> 0xb8 (2011 header 0x2a bytes of payload: 32 more than
2008, from client handler 0x51a230; units 124 as 2008, 2 reward items). Simplified against 2008: no
"HUV option" bonus formulas, no chase party. Needs a test with the real client (only possible with the
game native).
