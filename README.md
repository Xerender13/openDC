# openDC

![Open Drift City](https://github.com/Xerender13/openDC/blob/d05ced31e936e77c70660c8ca0f6aef5ba121735/openDC_logo_white.png)

Drift City (Skid Rush) Stage 2 Emulation Project: a server emulator for the **2011 Drift City client**: the US version and the European (EU) version.

**DISCLAIMER: This project is all entirely made with Claude Code (vibecoded)**

**It's still early stage work in progress!**

The emulator is a native server written in Python. It keeps the original server's architecture from the leaked 2008 files (separate auth /
lobby / game / area / battle-area services, the original SQL Server database tables), reads the server tables in the
2011 client's own formats, and drives the city traffic, battle zone races, quests, crews, parts shop, auctions and
the rest itself.

[Link to the US client download](https://drive.google.com/file/d/1ryBK-ZSFAEZfazAx7Ks4rUPvOWRyIt7J/view?usp=sharing)

[Link to the EU client download](https://drive.google.com/file/d/1xqOmNVxj8UySWotUqleW5vHej6kofY3a/view?usp=sharing)

| Folder | What |
|---|---|
| `Emulator/` | the server: `launch.sh` (Linux) / `launch.bat` (Windows), `docker-compose.yml`, the code in `dcemu/`. Start with [`Emulator/README.md`](Emulator/README.md); the detailed research notes are [`Emulator/docs/EMULATOR_NOTES.md`](Emulator/docs/EMULATOR_NOTES.md) |
| `Launcher/` | source of `DriftCityLauncher` (Go): starts the client against your server; `build.sh` builds the Linux and Windows launchers into each client folder |
| `Client US/` | **not in this repository**: the 2011 US client (with `DriftCityLauncher`) is shared separately. Put it here, next to `Emulator/` |
| `Client EU/` | **not in this repository**, optional: the EU client (below) |

## Quick start

1. Get the client and unpack it as `Client US/` in this folder.
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS) or podman / docker
   with compose (Linux; also Python 3.10+).
3. Start it:

   **Windows** (in `Emulator\`):
   ```bat
   launch.bat setup       :: once: builds the emulator image, copies the client's tables
   launch.bat init-db     :: once: an empty database with the account admin / admin
   launch.bat             :: database + emulator + the client
   ```

   **Linux** (in `Emulator/`):
   ```sh
   ./launch.sh setup && ./launch.sh init-db && ./launch.sh
   ```

4. Log in with `admin` / `admin`, or any new ID and password (accounts are created on first login).

Settings: `Emulator/emulator.ini` (server) and `Client US/DriftCityLauncher.ini` (server address, window mode, HUD).
Moving an existing setup (database, client) to another machine: [`Emulator/docs/HANDOVER.md`](Emulator/docs/HANDOVER.md).
To let other players join, put your address in their `DriftCityLauncher.ini` and in
`Emulator/server_data/serverlist.txt`, and open TCP ports 11005-11051.

## EU version

The same 2011 program serves every publisher; a nation number inside it picks the version. The EU client is the
2011 exe unpacked and set to an EU nation (`DriftCityEU.exe`, English by default). Its main difference is that parts
and some restrictions go by the car's V grade instead of the player's level, and the player's level adds no stat
points. Setup:

1. Copy the US client to `Client EU/` and put `DriftCityEU.exe` (the unpacked 2011 exe) in it.
2. `python3 Emulator/tools/eu_client.py setup eng` (or `de`, `fr`, `es`): sets the nation in the exe (original kept in
   `Emulator/client_backup/`) and makes the EU data folder `Data_EU_eng/` from `Data_US/`.
3. Start it with `Client EU/DriftCityLauncher` (`./launch.sh client eu`, `launch.bat client eu`).

The emulator recognises each client's nation and applies the EU rules only to EU clients (`emulator.ini` `[nation]`;
`allow = eu` or `us` makes a server for one version only). The EU parts tables are not available, so the parts
keep the US level requirements for now. `eu_client.py us` writes `Client US/DriftCityUS.exe`, the same exe as
a US client without GameGuard (choose it with `exe =` in `DriftCityLauncher.ini`).

**Current emulator progress (17.10.2026):** 

**Game features that haven't been done yet:**
- Channels and Channel Battle
- Virtual HUV
- Undercity
- GT Tournament
- Seasonal Events
- Some drift shop items and specific consumable items

**Features that still require testing and might work with issues:**
- Crew management

If you find a bug, something not working not listed above or something working wrongly (not like it was on official servers), creating an issue describing the issue will help the project to improve.
