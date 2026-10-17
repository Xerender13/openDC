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

The working folder is not a git repository: push from a separate clone.

```sh
git clone https://github.com/Xerender13/openDC openDC
cd "<project>"                                   # the folder with Emulator/ and Launcher/
find Emulator Launcher -type f -not -path '*/__pycache__/*' | sort > /tmp/cand.txt
git -C openDC check-ignore --stdin < /tmp/cand.txt | sort > /tmp/ign.txt
comm -23 /tmp/cand.txt /tmp/ign.txt | grep -v '/.venv/' > /tmp/publish.txt
rsync -a --files-from=/tmp/publish.txt ./ openDC/
```

Then, in the clone, **replace the second test account's password in `Emulator/docs/EMULATOR_NOTES.md`** (the
local notes keep it; three places) before committing. Never add `Client US/`, `Client EU/`, `Server2008/`, `Handoff/`,
`.ticket_secret`, `logs/`, `client_backup/`, client-derived `server_data/` files, or database backups other than
`db/SKDBTW_clean.bak` (`.gitignore` covers most of these). Commit as `Xerender13 <sasuke8453@gmail.com>`; push with
`gh` (logged in as Xerender13) or a personal access token.

## 5. State at the handover

Updated 2026-10-17 (end of session 17). Details of every item: the "Session 17" / "Session 16" / "Session 15"
entries at the top of `docs/EMULATOR_NOTES.md`.

**Confirmed in game on 2026-10-17:**
- Mitro City mother quests: retaking after a failure (children reset, quest list 0x111 resent; Agent Riggs ran fine).
- License gained text shows the license name.
- Repeatable missions (rq_*) at Moon Palace.
- Mito V-upgrade items (i_d_mu_v*_*per).
- Mission Battles (Line Ball / Mecha Watch / Exodus Quake items): offer, mission room, practice-type race (no gates),
  Rechallenge after a failure, EXP at the end (bonuses from the client's 0x3eb).

- Party Patrol (partypatrol.py, flag InstantMission.PartyPatrol): countdown, posts, emergency posts, result window
  (tested alone with the test mode, gmpartytest on; [partypatrol] test = 0 again).

**Done on 2026-10-17 (session 17), not yet confirmed in game:**
- Solo patrol end (0x3e3 after the last post; it stuck at 40/40), patrol rewards without the item notice box.
- US stat points 1 per level (nation rule half_level_points).
- EU rules (nation.py, EU clients only): drop groups by the car's V grade (drop_by_grade), part / option / docking
  requirements by V grade (part_grade, data.Tables.part_req_grade), battle zone without level limits
  (battle_levels) and EU V tiers (Newbie V1-3, Pro 4X V4-5 / 6X V6 / 8X V7-8 / 16X V9: eu.section lines,
  rooms.PRO_TIERS_EU; the same in Client EU's GlobalContent.xlt Value_EU_eng, tools/global_content.py --column).
- [nation] allow = all (both clients; the user tests a decompilation project).
- Client EU: no Data_US of its own (eu_client.py setup builds from Client US/Data_US); part tooltips "Grade %d
  required" with the grades written into its ItemClient.tdf (eu_client.py grades; eu.part_level = 0); refusal text
  11276; KPH texts (11874, game.nui labels: eu_client.py kph; global_text.py --column EU_eng).
- Main.AutoCarAssist on for all (garage Function 1 / 2 = the car grade's assists; the EU placeholder gone).
- tools/item_names.py: English names for Korean-named usable items (random_skb_bust so far; 75 more could follow).

**Done on 2026-10-17 (sessions 15-16), not yet confirmed in game:**
- Auto Fill-Up (i_automitron): automatic refuel at 80 % of the price (0x2d3 with u32 1).
- Battle quick slots (flag BattleZone.BattleQuickSlot) and the six battle_quick items (effects in the client).
- Battle EXP 25% / 50% up items: their % added to a battle's EXP, one used per battle (consumption is a guess).
- Solo Start for non-GM accounts (flag BattleZone.PracticeMode).
- From 2026-10-16: Mitro City traffic and signals (areas 62-75), crew nameplate colour, parts rules (Heat Treatment
  Kit only for normal H parts, docking letters).

**Open:**
1. Confirm the items above in game.
2. The Item Exchange Attendant (Mittron Crystal Powder -> TokenBook rows 5-9).
3. The rest of the Taipei main chain (mq_5th_*), the _m / _c branches and their reputations.
4. Battle rooms: the Complete Bonus Reward panel ("Recommended by Duffy EXP +25%", probably 0x1e4).
5. Other Taipei channels: check which areas the client joins from channels other than 0 (logs: `enters area`).
6. The Windows launcher on real Windows.
7. EU version: the real EU parts tables, then the V-grade rules (see the "EU client" entry in the notes).
8. Older items listed under "Open, first things next time" in `docs/EMULATOR_NOTES.md` (session 12).
9. EU parts: the real EU World.agt (ItemClient column 8) would replace the part grade rule's tiers if it differs.

**Characters:** Xerander (cid 100000) is the user's main (Taipei chain in progress, faction OMD). Test characters:
NewChar, Newbie, DCLoverN. The database backup above has them all.
