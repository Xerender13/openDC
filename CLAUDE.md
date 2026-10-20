# openDC: Drift City 2011 emulator

A native server for the 2011 Drift City client (US build, also run as the EU version), written in Python. It keeps
the original server's layout: separate services and ports, the same SQL Server database and tables,
`serverlist.txt`, an ini. It reads the game tables in the 2011 client's own formats.

## Read first

1. `Emulator/docs/HANDOVER.md`: setup, the working rules, how to publish, the current state and the open list.
2. `Emulator/docs/EMULATOR_NOTES.md`: the research log, newest session at the top. Every message layout, client
   address and user report is recorded there. Read the top sections before you change anything.
3. `Emulator/docs/BATTLEZONE.md`: battle zone rooms and races.

## Layout

| Path | What | In git |
|---|---|---|
| `Emulator/` | the emulator (`dcemu/`), `launch.sh` / `launch.bat`, `emulator.ini`, `server_data/`, `tools/`, `docs/` | yes |
| `Emulator/dcemu/native/` | native services: `auth.py`, `lobby.py`, `area.py`, `nation.py` (US / EU rules), `game/*.py` (one module per feature: rooms, quests, mothers, instant, items, licenses, ...) | yes |
| `Emulator/dcemu/handlers/game.py` | content flags sent to the client (`NEW_FLAGS`: flags new in 2011 or missing from the 2008 `Contents.ini`) | yes |
| `Launcher/` | Go source of the client launcher (`build.sh`) | yes |
| `Client US/`, `Client EU/`, `DriftCity Dev Ed/` | the game clients: 2011 US / EU, 2016 US (shared separately; zips in `../Releases/`) | **no** |
| `Emulator 2011/` | local copy of `Emulator/` set to 2011, for playing | **no** |
| `Server2008/`, `Handoff/` | 2008 server, research tools, hand-over copies | **no** |

## Running

`Emulator/emulator.ini` serves both builds: `[client] version` (2016 in this folder and on GitHub) and a `[2016]`
section whose `section.key = value` lines replace settings for 2016 (ports 111xx, database SKDB2016TEST, logs/2016).
`Emulator 2011/` is a local copy for playing 2011 (version = 2011, 110xx, SKDBTW; not in git: `.git/info/exclude`,
created 2026-10-20). It does not follow `Emulator/` by itself: copy fixes over when the user asks.

```sh
cd Emulator                 # or "Emulator 2011" for the 2011 server
./launch.sh                 # database + emulator + the client of the configured version
./launch.sh restart-emu     # after a code change (disconnects connected clients)
.venv/bin/python -m tools.gmctl who | item NAME ITEM-ID [count] | drift NAME ID [days] | kick NAME ...
```

Logs: `logs/<date>-<time>.msgs.txt` (2016: `logs/2016/`) has every message both ways, one file per emulator start.
`logs/emulator.out` has the console. Start every bug hunt by finding the user's report in the newest log
(`grep -n "#N game  --"` gives the server's own notes).

## Working rules (set by the user)

- **Fix protocol problems in the emulator.** Don't make the database accept plain passwords, and don't edit rows to
  work around a bug. Edit a character's rows only while that character is offline.
- **Keep the client vanilla** unless the user asks for a change. When the client itself refuses something, explain
  its rule instead of patching it. Change a client pack only by rewriting it with header bytes 20-31 kept, with the
  original in `Emulator/client_backup/`. If something breaks after a client change, suspect that change first.
- **Missing 2011 features are often only a content flag.** If a feature is absent or a button stays greyed out,
  check whether the client tests a content flag that the 2008 `Contents.ini` lacks: battle quick slots were
  `BattleZone.BattleQuickSlot`, solo Start was `BattleZone.PracticeMode`. Find the flag's bit in
  `dcemu/data/flags_2011.tsv`, find where the client tests it, then add it to `NEW_FLAGS`.
- **The user plays while you work.** Restart the emulator after a change (`./launch.sh restart-emu`) and say so in
  the reply: the restart disconnects them. Stop only processes you started, by exact pid. Never use `pkill -f` or a
  pattern kill.
- **EU behaviour goes through `dcemu/native/nation.py`** (`is_eu`, `rule`, `emulator.ini [nation] eu.*`). US
  behaviour must not change, and the EU client keeps its own design.
- **Report honestly.** Mark changes "not yet confirmed in game" in the notes until the user confirms them, and say
  what was script-tested and what wasn't.
- **Write the notes.** Add each change to the top session of `docs/EMULATOR_NOTES.md`: the user's report, the
  cause with client addresses, the fix, and whether it's confirmed. Keep the module docstrings up to date; they hold
  the message layouts.
- **Commit only when asked.** Commit as `Xerender13 <sasuke8453@gmail.com>`. Publishing rules and what must stay
  out of git are in `docs/HANDOVER.md` §4. This repository is public: never put passwords, tickets or personal data
  in it.
- Scripted-client tests run on a second emulator on ports 112xx (`tools/test_ports.ini`), never on the live one.
  Otherwise call the handlers directly with stub sessions (see `tests/`).

## Reverse-engineering the client

- **The client:** `Client US/DriftCityUS.exe` is the unpacked 2011 exe. Image base 0x400000. `.text` is at file
  offset 0x400 → VA 0x401000. `.data` is at file 0x4c6000 → VA 0x8c7000.
- **Disassemble** with `objdump -D -b binary -m i386 -M intel --adjust-vma=0x401000` on the `.text` bytes. Extract
  them with `dd bs=1 skip=$((0x400)) count=$((0x4c5c00))` into the scratchpad.
- **Message handlers** are registered as `push handler; push type; mov ecx, esi; call 0x806590`. Search the exe for
  `68 <type u32> 8b ce e8`; the dword before it is the handler.
- **Senders** write the type with `mov word [eax], TYPE` (`66 c7 00 <type>`), then call `0x80ca40`. Find the
  callers of a sender function by scanning for `e8` rel32 calls to it.
- **Content flags** live at `[0x536360() + 0x268 + offset]`. Example: `BattleQuickSlot` is offset 0x2c bit 16 →
  `test byte [eax+0x296], 1`.
- **Item use kinds:** after the item use answer (0x1a2), the client's switch at 0x72a480 applies the item's effect.
  Item kind codes are listed in `items.USE_KINDS`.
- **The 2008 server** (`Server2008/`, `ZoneServer.exe`, not packed) shows the original rules for anything that
  existed in 2008.

## Next session

Start with the "Open" list in `Emulator/docs/HANDOVER.md` §5 and the top of `EMULATOR_NOTES.md`.
