# Drift City 2011 US emulator

A server for the 2011 US client, grown incrementally in front of the 2008 ZoneServer
(`../Server2008`, no longer needed). Background, findings and the plan: `docs/EMULATOR_NOTES.md`.

Each service in `emulator.ini` is either **proxied** (a port of the 2008 ZoneServer: every
message is logged and the handlers in `dcemu/handlers/` rewrite what the 2011 client and the
2008 server disagree on; the rest goes through byte for byte) or **native** (ZoneServer port 0:
the emulator is the server, `dcemu/native/`). The native services keep the original server's
architecture (separate auth/lobby/game/area/barea services and ports, the same SQL Server
database and tables, `serverlist.txt`) but read the server tables in the 2011 client's own
formats (.xlt/.tdf, not converted to the 2008 columns).

Now every service is native (`emulator.ini`); the 2008 ZoneServer is not used at all.
GM commands for the running emulator (kick, block, ban; `dcemu/native/admin.py`):
`.venv/bin/python -m tools.gmctl who | kick NAME [days] | block NAME days | unblock NAME | chatblock NAME
minutes | ban ACCOUNT | unban ACCOUNT`. `tools/client.py` is a scripted client for tests.

The emulator is self-contained: everything it needs is in this folder. From the 2008 server it keeps only
copies of what it reads (`server_data/`: a few server-side tables, exp tables, server messages, race track
paths). The city traffic is native too (`dcemu/native/city_traffic.py`, on the client's own lanes); the 2008
traffic program (TrafficAgent.exe under Wine in a container) moved to `../Server2008/traffic_agent/`, for
comparing only (`emulator.ini [traffic] city = agent`). `../Server2008/` (the 2008 ZoneServer stack and the research tools) is not needed
to run it. The client is started with `../Client US/DriftCityLauncher` (Linux) or `DriftCityLauncher.exe`
(Windows), source in `../Launcher/`; the EU client the same way from `../Client EU/` (`tools/eu_client.py`, below).

```
2011 client --11005..11051--> emulator (python3 -m dcemu) --14330--> SQL Server  (container dcemu2011_db)
```

UDP 11400/11401 (the client's time sync / P2P) has no listener: the native area answers the time sync on the
TCP connection and relays cars itself.

## Running

`./launch.sh` (Linux) starts the parts together or one by one (`./launch.sh help`); Windows: `launch.bat`, below.

```sh
./launch.sh setup        # once: .venv with python-tds, the client's tables -> server_data/Init, server_data/tables (again after a client patch)
./launch.sh init-db      # once, on a new machine: creates the database (deletes an existing one; asks)
./launch.sh              # database + emulator (background) + the client
./launch.sh server       # the same without the client
./launch.sh db | emu | emu-bg | client          # one part (emu: foreground, Ctrl+C stops it)
./launch.sh stop [emu|db]    ./launch.sh restart-emu    ./launch.sh status    ./launch.sh logs [part]
```

Needs Python 3.10+ and podman (or docker) with podman-compose / docker compose (`docker-compose.yml`: the
database; its volume is `driftcity2011_mssql-data`, the one the 2008 stack made). Restarting the emulator
disconnects the clients.

### Windows (Docker Desktop)

The database and the emulator run in containers (`docker-compose.yml` services `db` and `emulator`, the image
from `Dockerfile`), the client natively. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/),
put the 2011 client in `..\Client US` (next to this folder), then in this folder:

```bat
launch.bat setup        :: once: builds the emulator image, copies the client's tables to server_data\
launch.bat init-db      :: once: an empty database with the account admin / admin (asks; deletes an existing one)
launch.bat              :: database + emulator + the client (..\Client US\DriftCityLauncher.exe; "launch.bat all eu": ..\Client EU)
launch.bat server | client [eu] | stop | restart-emu | status | logs [db] | gm who | help
```

`emulator.ini`, `server_data\` and `logs\` are the files in this folder (mounted into the container): edit them
and `launch.bat restart-emu`. The same works on Linux / macOS with `docker compose up -d` (after
`docker compose run --rm --no-deps emulator python -m tools.sync_data /client server_data`).
Other players connect to this PC's address: set it in their `DriftCityLauncher.ini` and in
`server_data\serverlist.txt` (the four addresses), and open TCP 11005-11051 in the firewall.

### A fresh database

`db/SKDBTW_clean.bak` is an empty game database (the schema of `db/*.sql`, the account `admin` / `admin`, no
characters), the same thing `init-db` creates. To use it instead: `launch.bat restore-db db\SKDBTW_clean.bak`
on Windows, or on Linux:

```sh
podman cp db/SKDBTW_clean.bak dcemu2011_db:/var/opt/mssql/data/clean.bak
podman exec dcemu2011_db /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P 'z0ne!server' -Q \
  "RESTORE DATABASE SKDBTW FROM DISK='/var/opt/mssql/data/clean.bak' WITH REPLACE, MOVE 'SKDBTW' TO '/var/opt/mssql/data/SKDBTW.mdf', MOVE 'SKDBTW_log' TO '/var/opt/mssql/data/SKDBTW_log.ldf'"
```

(stop the emulator first: `./launch.sh stop emu`)

New accounts are made by logging in with a new ID (`emulator.ini [auth] auto_register = 1`).
Settings: `emulator.ini`; the clients': `../Client US/DriftCityLauncher.ini`, `../Client EU/DriftCityLauncher.ini` (server address, windowed /
fullscreen, HUD type, Proton or Wine). `-q` logs to the file only.

| Folder / file | What |
|---|---|
| `dcemu/` | the emulator (`native/` the services, `handlers/` the proxy mode, unused now) |
| `server_data/` | `Init/` and most of `tables/` (the client's .xlt / .tdf tables and `<City>/` traffic files) come from the client (`./launch.sh setup` / `python -m tools.sync_data`, not in git); from the 2008 server: `tables/` (LevelServer, Contents.ini, ItemServer, drops, upgrade odds, rush hours), exp / money tables, Lap Time and Real Match settings, `Localize/` server messages, `race/` battle zone track paths, `serverlist.txt`, `adminlist.txt`; the editable reward / chance files `delivery_rewards.txt`, `patrol_rewards.txt`, `gate_rewards.txt`, `team_gate_rewards.txt`, `docking_chances.txt` |
| `db/` | the database schema (`./launch.sh init-db`) and `SKDBTW_clean.bak` (the same, as a backup) |
| `tools/` | gmctl (GM commands), sync_data, client.py (scripted client), global_content.py / agt.py (client packs), auction_test.py |
| `client_backup/` | original client packs (Patch.000) for global_content.py `reset` |
| `docs/` | `EMULATOR_NOTES.md` (the hand-off: start there), `BATTLEZONE.md` |

Log: `logs/<start time>.msgs.txt`, one line per message, the full payload in hex:

```
07:38:34.522 #1 auth  C>S  0x0014 Login     156 9727...    as received
07:38:34.522 #1 auth  C>S* 0x0014 Login     152 9727...    * = as sent after a handler changed it
07:38:34.524 #1 auth  --  login result 0 (OK)             handler notes, open/close
```

`#n` is the connection. Lengths include the 4-byte header.

## The EU client and nations

One 2011 program serves every publisher; a nation number picks the version (1 US, 7-10 EU de / eng / fr / es).
`tools/eu_client.py setup eng` turns `../Client EU/DriftCityEU.exe` (the unpacked exe) into the EU English client
and builds its `Data_EU_eng/` from `Data_US/`; `tools/eu_client.py us` writes `../Client US/DriftCityUS.exe`, the
unpacked US client (no GameGuard). The EU client sends its nation (0x7cf) on every connection; the US client sends
nothing. `dcemu/native/nation.py` keeps it per session and player, and every EU-only rule goes through it, so US
clients behave as before: `emulator.ini [nation]` `allow` (which nations may log in), `us.*` / `eu.*` rules (EU: no
stat points from the player's level; parts may need a V grade, ItemClient column 8). Details: the "EU side project"
entry in `docs/EMULATOR_NOTES.md`.

## Code

| File | What |
|---|---|
| `dcemu/wire.py` | framing (`[u16 len][u16 type][payload]`), the 56-byte handshake, UTF-16 fields |
| `dcemu/proxy.py` | listeners, connection pairs, the handler chain |
| `dcemu/protocol.py` | services and ports, the handshake, message names for the log |
| `dcemu/msglog.py` | the message log |
| `dcemu/handlers/` | `@on(service, direction, type)` handlers; list new modules in `MODULES` |
| `dcemu/handlers/auth.py` | login: plain password -> MD5 hex, 2011 message cut to the 2008 size |
| `dcemu/native/__init__.py` | the native services' shared context: DB, tables, login tickets, server list |
| `dcemu/native/db.py` | SQL Server (python-tds) on a worker thread, awaitable `row`/`rows`/`execute` |
| `dcemu/native/data.py` | the server tables in the 2011 formats (`server_data/Init/*.xlt`, `server_data/tables/*.tdf`) |
| `dcemu/native/auth.py` | login (MEUSERMT, MD5) and the server list from `serverlist.txt` |
| `dcemu/native/lobby.py` | check-in, character list, name check, character creation, keepalive |
| `dcemu/native/ranking.py` | the 2011 ranking service (a stub so far) |
| `dcemu/commands.py` | splits frames carrying several commands (2008 sizes, `data/packets_2008.tsv`) |
| `tools/sync_data.py` | copies the client's effective tables (patches applied, US over base) to `server_data/Init` and `server_data/tables` |
| `dcemu/native/race.py` | race traffic for the native barea: the TW engine (`../Server/tools/traffic_server.py`), tracks from the 2011 PVPTrackInfo.xlt |
| `dcemu/native/area.py` | the area/barea services: enter/exit, time sync, area status, move relay |
| `dcemu/native/city_traffic.py`, `tcs.py` | the city traffic: cars and signals on the client's `.tcs` lanes (`server_data/tables/<City>/`), sent to players near them |
| `dcemu/native/game/` | the game service: `player.py` (character from the DB), `records.py` (2011 layouts), `login.py` (entering the game) |
| `tools/replay.py` | replays a recorded client connection against a port and compares the replies (proxy vs native) |
| `tools/probe_login.py` | logs in like the 2011 client: `python3 -m tools.probe_login admin admin` |
| `tests/` | `python3 -m unittest discover -s tests -t .` |

A handler gets the session and the frame and returns the frame to forward (changed or not), a
list of frames, or None to drop it; `session.to_client()` / `to_server()` inject messages and
`session.state` keeps per-connection data. A handler that raises is logged and the message is
forwarded unchanged. Native handlers register as `native:<service>` (`@on('native:lobby', C2S,
0x29)`), may be `async`, and answer with `session.to_client()`; `@on_open('native:<service>')`
runs when a client connects (the lobby's keepalive).
