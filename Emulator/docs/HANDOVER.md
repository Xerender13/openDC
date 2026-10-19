# Handover: continuing openDC on another device

Written 2026-10-16 (end of session 13) for moving the work from the Steam Deck to another machine, for a person or
a new Claude session. The detailed research log is `docs/EMULATOR_NOTES.md` (newest entries at the top); this file
says what to copy, how to set up, how the work is done, and what is open.

## Latest handoff: 2026-10-19 (session 26, end of day)

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
| The game database | `Emulator/db/SKDBTW_2026-10-18.bak` (6 MB, 22:52) | All accounts and characters as of the handover. Make a newer one before moving: `./launch.sh backup-db`. Not in git (`db/*.bak` is ignored). |
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
./launch.sh restore-db db/SKDBTW_2026-10-18.bak # your characters (or: ./launch.sh init-db for an empty database)
./launch.sh                                     # database + emulator + client
```

**Windows** (Docker Desktop running; the emulator runs in a container):

```bat
cd Emulator
launch.bat setup
launch.bat restore-db db\SKDBTW_2026-10-18.bak
launch.bat
```

In the container the emulator tells clients DCEMU_PUBLIC_HOST (default 127.0.0.1: a client on the same machine) as
the lobby / game address; for players on the network set it to the machine's address (environment or `.env`).
`launch.bat` / `launch.ps1` passed PowerShell's parser but have **not been run on real Windows yet**; expect to fix
small things the first time. `./launch.sh restore-db` is new (2026-10-16) and was not run against the live
database (`backup-db` was); it uses the same SQL as the Windows one, which was tested on a scratch database.

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
`server_data/` files, or database backups other than `db/SKDBTW_clean.bak` (`.gitignore` covers these). The tools
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
