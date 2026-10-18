# Handover: continuing openDC on another device

Written 2026-10-16 (end of session 13) for moving the work from the Steam Deck to another machine, for a person or
a new Claude session. The detailed research log is `docs/EMULATOR_NOTES.md` (newest entries at the top); this file
says what to copy, how to set up, how the work is done, and what is open.

## 1. What to copy

The GitHub repository (https://github.com/Xerender13/openDC) holds `Emulator/` and `Launcher/` only. Copy the rest
from the old device:

| What | Where it is on the Deck | Notes |
|---|---|---|
| The code | GitHub, or `Drift City US 2011/Emulator` + `Launcher` | `git clone https://github.com/Xerender13/openDC` |
| The 2011 clients | `Drift City US 2011/Client US/` and `Client EU/` | Not on GitHub (shared on Google Drive). **Copy the Deck's folders**: `Client US/` has the text patches in `Patch/Patch.006` (12215 license name, 12216 coupon, 11413 / 12214 crew logon), `DriftCityUS.exe` and `DriftCityLauncher.ini`; `Client EU/` is the EU client (`DriftCityEU.exe` set by `Emulator/tools/eu_client.py`, `Data_EU_eng/`, the Km/h dial). Put them next to `Emulator/`. |
| The game database | `Emulator/db/SKDBTW_2026-10-16.bak` (6 MB, 15:39) | All accounts and characters as of the handover. Make a newer one before moving: `./launch.sh backup-db`. Not in git (`db/*.bak` is ignored). |
| `emulator.ini` | `Emulator/emulator.ini` | Is in git. Change `[database]` if your SQL Server differs; the ports and `[flags]` are set for this client. |
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
./launch.sh setup                               # .venv with python-tds, copies the client's tables to server_data/
./launch.sh restore-db db/SKDBTW_2026-10-16.bak # your characters (or: ./launch.sh init-db for an empty database)
./launch.sh                                     # database + emulator + client
```

**Windows** (Docker Desktop running; the emulator runs in a container):

```bat
cd Emulator
launch.bat setup
launch.bat restore-db db\SKDBTW_2026-10-16.bak
launch.bat
```

`launch.bat` / `launch.ps1` passed PowerShell's parser but have **not been run on real Windows yet**; expect to fix
small things the first time. `./launch.sh restore-db` is new (2026-10-16) and was not run against the live
database (`backup-db` was); it uses the same SQL as the Windows one, which was tested on a scratch database.

The client: `Client US/DriftCityLauncher` (Linux, runs DriftCityUS.exe with Proton: `DriftCityLauncher.ini [client] exe`,
`[linux]`; the EU client the same from `Client EU/`) or
`Client US/DriftCityLauncher.exe` (Windows; run it once as administrator for windowed mode). Its server address is
`DriftCityLauncher.ini [server] address` (127.0.0.1 for the same machine). Other players: their launcher ini gets
your address, and `Emulator/server_data/serverlist.txt` too; open TCP 11005-11051.

Accounts are made on the first login with a new ID. GM rights: the account in `server_data/adminlist.txt` or
SKID_ACCOUNT_TB.PTYPE 'A'; GM commands with
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
`server_data/` files, or database backups other than `db/SKDBTW_clean.bak` (`.gitignore` covers these). The tools
that change client files are in git, so those changes can be made again on another machine (see §5).

## 5. State at the handover

Updated 2026-10-18 ~13:30 (end of session 19; committed and pushed, 3293ef0 + this note). Details: the "Session 19
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

**Open (next session):**
0. The Undercity (session 19b, `game/undercity.py`): play it in game, alone with `gmuctest on` (or `[undercity] test =
   1`) and `/ucm` in a Moon Palace channel, then with a real party at Tatiana. Not confirmed in game at all yet.
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
