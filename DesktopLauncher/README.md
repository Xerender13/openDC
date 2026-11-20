# openDC Launcher (desktop)

A desktop launcher for openDC that installs and runs everything **without Docker**: the game client, the
emulator, a portable Python and a portable PostgreSQL. One window for Windows 10/11 (`openDC Launcher.exe`) and
Linux (an AppImage that runs on any x86_64 distro). Electron 45, no npm packages; the database work goes through
a small Python helper run by the portable Python.

This is a separate program from `Launcher/` (the Go `DriftCityLauncher` that starts the client). The desktop
launcher calls `DriftCityLauncher` to start the game, exactly as `launch.sh` / `launch.bat` do.

Texts: Portuguese, English and Russian. The first start picks the system's language (English when it is none of
those); Settings > Language changes it.

## What it does

- **Install** (DOWNLOAD button): the client from the Google Drive links in the root `README.md` (2016 or 2011), the
  openDC server from this repository (the `main` zip), Python 3.12 (python-build-standalone) with `pg8000`, and
  PostgreSQL 17 (theseus-rs/postgresql-binaries). It creates the database from `Emulator/db/postgres` and copies the
  client's tables (`python -m tools.client_setup`). "I already have openDC in a folder" adopts an existing install.
- **Database and server** start with the launcher (`python -m dcemu -q`, hidden, ports and passwords from
  `emulator.ini`) and stop when it closes. Closing the launcher also closes the game. While the game is open the
  launcher goes to the system tray (or minimizes; Settings > Server) and comes back when the game closes.
- **Updates**, checked every time it opens:
  - emulator: new commits on `main` (the commit list is shown; Update downloads the zip and copies `Emulator/` and
    `Launcher/`, keeping a copy of the old `emulator.ini` as `emulator.ini.before-update`);
  - client: the README's Drive link for the installed client changed (the new client replaces the old one; the
    player's `goption.ini` and `DriftCityLauncher.ini` are kept);
  - the launcher itself: a GitHub release on this repository tagged `launcher-vX.Y.Z` with the assets
    `openDC-Launcher-X.Y.Z-x86_64.AppImage` and `openDC-Launcher-X.Y.Z-Windows.zip` (the files `build.sh` makes).
    The AppImage replaces itself; on Windows a small script copies the new folder over after the launcher exits.
- **Accounts**: list, create, delete, password, GM (`adminlist.txt`), ban, G Coin; per character: rename, level
  (control port, server on), Mito, cars and inventory, give a car / item (control port), delete. Export an
  account (with all its characters) or one character to a `.json` file and import it on another install (Windows
  and Linux alike, same client only). Friends, crews, auctions and stickers are not exported.
- **Video** (Settings > Video): written straight into the client's `Data/Init/goption.ini` (resolution from 800x600
  up to the user's screen, window / fullscreen, HUD, anti-aliasing, preset and details, motion blur none / normal,
  view distance, fog, car outline). `DriftCityLauncher.ini` gets the matching `display` and `main_ui_type`.
- **Linux / Proton**: the launcher writes `[linux] runner / proton / steam` in `DriftCityLauncher.ini`. It picks the
  system's Proton first (`/usr/share/steam/compatibilitytools.d`, e.g. CachyOS's `proton-cachyos-slr`), otherwise
  the newest one found in Steam, Heroic or Lutris (native and Flatpak). With none, PLAY stays disabled and the
  Proton menu (Settings > Video > Proton…) can download a GE-Proton release or import a folder / archive. A prefix
  made by plain Wine (no `tracked_files`) is moved aside so Proton can make its own.
- **Windows**: before starting the game it marks `DriftCity.exe` and `DriftCityLauncher.exe` as high-DPI aware for
  the current user (`HKCU\...\AppCompatFlags\Layers`, `~ HIGHDPIAWARE`, other flags kept). Without it, display
  scaling of 125% / 150% blows the game window up and cuts it off at high resolutions. Settings > Advanced has
  buttons for `Emulator/tools/laa.py` (check / apply / remove) and "Restore backup"
  (`client_backup/DriftCity.exe.before_laa`).
- Settings also has: local server or another IP (with a test), database backup (manual and one a day, the last 7
  kept), repair the client tables, folders, and the launcher / server / database / game logs.

## Install folder

```
<openDC folder>              default: ~/Games/openDC (Settings > Folders)
  DriftCity Dev Ed/          the 2016 client (Client US/ for 2011)
  Emulator/  Launcher/       from this repository
  runtime/
    python/  pgsql/  pgdata/ portable Python, PostgreSQL and its data
    logs/                    launcher.log, server.out, postgres.log (the 5 newest of each are kept)
    backups/  proton/  downloads/  tmp/
```

The launcher's own settings are in `%APPDATA%\openDC Launcher\config.json` (Windows) or
`~/.config/openDC Launcher/config.json` (Linux).

## Building

```sh
pip install pefile pillow      # for seticon.py (the Windows exe icon)
./build.sh                     # Linux; downloads Electron, 7-Zip and appimagetool once into .cache/
```

Out come `out/openDC-Launcher-<version>-x86_64.AppImage` and `out/openDC-Launcher-<version>-Windows.zip`. The version
is in `app/package.json`. The Windows build is made on Linux: Electron's `electron.exe` renamed, with the icon
written by `seticon.py` (no rcedit needed).

To run from source while working on it: unpack Electron 45 anywhere and run `electron app/` (the Python helper is
then taken from `app/helper/`).

## Code

| File | What |
|---|---|
| `app/main.js` | window, tray, IPC API (`window.odc`), start / stop on open / close, updates |
| `app/preload.js` | the API the page sees |
| `app/backend/core.js` | config, paths, logging, downloads (incl. Google Drive's large-file confirm), extraction, ini read / write |
| `app/backend/install.js` | install steps, GitHub commits / zip, README client links |
| `app/backend/server.js` | portable Python and PostgreSQL, database create / start / stop / backup, emulator start / stop, control port |
| `app/backend/game.js` | starting the client and watching it, Proton search / download / import, DPI flag, `laa.py` |
| `app/backend/accounts.js` | accounts and characters (helper + control port) |
| `app/backend/settings.js` | `goption.ini` |
| `app/backend/updates.js` | emulator / client / launcher update checks and installs |
| `app/helper/odc_helper.py` | database work (pg8000), JSON in / out on stdin / stdout |
| `app/ui/` | the page: `index.html`, `app.css`, `app.js`, `i18n.js` (pt / en / ru), `assets/` |

## Known limits

- Windows 7 and 8.1 can't run Electron 45; the server part of the launcher needs Windows 10 or newer.
- The exe is not code-signed: SmartScreen asks once ("More info" > "Run anyway").
- The client update check sees a new client only when the README link changes, not when the file behind the same
  link is replaced.
- Tested by script on Linux (install steps, database, server, accounts, export / import, video, Proton search,
  `laa.py`); played on Windows 10 and CachyOS. Not tested yet: the self-update with a real release, and the
  launcher's DPI flag on a real high-DPI Windows screen.
