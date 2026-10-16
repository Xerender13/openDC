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
| The 2011 client | `Drift City US 2011/Client/` | Not on GitHub (shared on Google Drive). **Copy the Deck's folder**: it has the text patches in `Client/Patch/Patch.006` (12215 license name, 12216 coupon, 11413 / 12214 crew logon) and `DriftCityLauncher.ini`. Put it next to `Emulator/` as `Client/`. |
| The game database | `Emulator/db/SKDBTW_2026-10-16.bak` (6 MB, 15:39) | All accounts and characters as of the handover. Make a newer one before moving: `./launch.sh backup-db`. Not in git (`db/*.bak` is ignored). |
| `emulator.ini` | `Emulator/emulator.ini` | Is in git. Change `[database]` if your SQL Server differs; the ports and `[flags]` are set for this client. |
| `.ticket_secret` | `Emulator/.ticket_secret` | Not needed: the server's key for login tickets, made again when missing (a client that is logged in at that moment logs in again). Not in git. |
| `client_backup/` | `Emulator/client_backup/` | The client's original packs before the text patches. Not in git; keep a copy. |
| Old stacks / research | `Server2008/`, `Handoff/`, `DriftCity Dev Ed/` | Not needed to run anything. `Server2008/client_image/DriftCity_2011_unpacked.bin` (the unpacked client, for disassembly) and `Server2008/server/ZoneServer.exe` (the 2008 server, the reference for server rules) are worth keeping for research. |

## 2. Setting up

Layout (folder names matter: the launcher looks for `../Client`):

```
<anything>/Emulator/   <anything>/Launcher/   <anything>/Client/
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

The client: `Client/DriftCityLauncher` (Linux, runs DriftCity.exe with Proton; `DriftCityLauncher.ini [linux]`) or
`Client/DriftCityLauncher.exe` (Windows; run it once as administrator for windowed mode). Its server address is
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
local notes keep it; three places) before committing. Never add `Client/`, `Server2008/`, `Handoff/`,
`.ticket_secret`, `logs/`, `client_backup/`, client-derived `server_data/` files, or database backups other than
`db/SKDBTW_clean.bak` (`.gitignore` covers most of these). Commit as `Xerender13 <sasuke8453@gmail.com>`; push with
`gh` (logged in as Xerender13) or a personal access token.

## 5. State at the handover

**Done on 2026-10-16 afternoon, not yet confirmed in game:**
- Mitro City (Taipei) traffic: areas 62-75 are Taipei (area 68 seen); path traffic (0x21e) on
  `path_taipei.chpath`, 400 cars (`emulator.ini cars.taipei`), stopping at the path signals on ZoneServer's 60 s
  cycle. The client's lamps in Taipei cannot change colour (no .tcs there); only the cars follow the lights.
- Mitro City missions can be taken again after failing (0x17c resent after 0x181).
- Crew nameplate colour from the crew grade (`crews.crew_level`).
- Parts: a part dropped on a filled slot goes to the free line first; Heat Treatment Kit only for normal H parts;
  docking letters ranked A lowest. (The free-line change was confirmed.)

**Open:**
1. Confirm the items above in game.
2. Repeatable missions (rq_*) and the Item Exchange Attendant (Mittron Crystal Powder -> TokenBook rows 5-9).
3. The rest of the Taipei main chain (mq_5th_*), the _m / _c branches and their reputations.
4. Battle rooms: the Complete Bonus Reward panel ("Recommended by Duffy EXP +25%", probably 0x1e4).
5. Other Taipei channels: check which areas the client joins from channels other than 0 (logs: `enters area`).
6. The Windows launcher on real Windows.
7. Older items listed under "Open, first things next time" in `docs/EMULATOR_NOTES.md` (session 12).

**Characters:** Xerander (cid 100000) is the user's main (Taipei chain in progress, faction OMD). Test characters:
NewChar, Newbie, DCLoverN. The database backup above has them all.
