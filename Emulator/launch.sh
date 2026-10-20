#!/usr/bin/env bash
# Drift City emulator launcher: start the components together or one by one. emulator.ini [client] version says
# which client build (2011 or 2016) this server is for; the ports, database and client follow from it.
#
#   ./launch.sh [all] [eu]   database + emulator (in the background) + the client (US, or the EU client with eu;
#                            version 2016: the 2016 client ../DriftCity Dev Ed)
#   ./launch.sh server       database + emulator (in the background), no client
#   ./launch.sh db           the database only (SQL Server container)
#   ./launch.sh emu [-q]     the emulator only, in the foreground (Ctrl+C stops it; -q: log to the file only)
#   ./launch.sh emu-bg       the emulator only, in the background (output: logs/emulator.out)
#   ./launch.sh client [eu]  the client: ../Client US/DriftCityLauncher, ../Client EU/ with eu, or for version 2016
#                            ../DriftCity Dev Ed/DriftCityLauncher2016
#   ./launch.sh stop [part]  stop everything, or one part: emu, db
#   ./launch.sh restart-emu  stop and start the background emulator (clients are disconnected)
#   ./launch.sh status       what is running
#   ./launch.sh logs [part]  follow a log: emu (default), db
#   ./launch.sh setup        first time: the Python environment (.venv with python-tds), which client (2011 or 2016:
#                            emulator.ini [client] version) and its tables; after a client patch: copy them again
#                            (the first server / emu start asks the same on its own: tools/client_setup.py)
#   ./launch.sh init-db      create the game database from db/*.sql (an existing one is DELETED: asks first)
#   ./launch.sh backup-db [F]    save the game database to a SQL Server backup (default db/<name>_<date>.bak)
#   ./launch.sh restore-db F     replace the game database with the backup F (e.g. db/SKDBTW_clean.bak; asks first)
# The game database is [database] name: SKDBTW for 2011, SKDB2016TEST for 2016 (emulator.ini [2016]).
#
# Needs: Python 3.10+, podman (or docker) with podman-compose / docker compose. The emulator's settings are in
# emulator.ini; the clients' in ../Client US/DriftCityLauncher.ini and ../Client EU/DriftCityLauncher.ini (the EU client:
# tools/eu_client.py).
set -euo pipefail
cd "$(dirname "$0")"
HERE=$(pwd)
PIDFILE=$HERE/.emulator.pid
OUT=$HERE/logs/emulator.out
CLIENT_DIR="$HERE/../Client US"          # the US client (its tables: tools/client_setup.py asks for the folder)
CLIENT_EU_DIR="$HERE/../Client EU"       # the EU client (DriftCityEU.exe, tools/eu_client.py)
CLIENT_2016_DIR="$HERE/../DriftCity Dev Ed"   # the 2016 client (its launcher: DriftCityLauncher2016)

die() { echo "launch.sh: $*" >&2; exit 1; }

engine() {
  if command -v podman >/dev/null 2>&1; then echo podman
  elif command -v docker >/dev/null 2>&1; then echo docker
  else die "podman or docker is needed for the database"; fi
}

compose() {
  if command -v podman-compose >/dev/null 2>&1; then podman-compose "$@"
  elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then docker compose "$@"
  elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then podman compose "$@"
  else die "no compose provider: install podman-compose (e.g. pipx install podman-compose) or Docker Compose"; fi
}

python() {
  if [ -x .venv/bin/python ]; then echo .venv/bin/python
  elif [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe
  else echo python3; fi
}

read_config() {  # the settings as the emulator resolves them (emulator.ini, with the [2016] section's when version = 2016)
  local cfg
  cfg=$("$(python)" -m dcemu --get client.version services.auth services.area database.name database.password) ||
    die "emulator.ini: the settings could not be read"
  { read -r VERSION; read -r AUTH_PORT; read -r AREA_PORT; read -r DB_NAME; read -r DB_PASSWORD; } <<< "$cfg"
  AUTH_PORT=${AUTH_PORT%% *}
  AREA_PORT=${AREA_PORT%% *}
}
read_config

sqlcmd() {      # SQL Server's sqlcmd inside the database container, as sa
  "$(engine)" exec dcemu2011_db /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$DB_PASSWORD" -b "$@"
}

listening() { ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; }

emu_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid; pid=$(cat "$PIDFILE")
  kill -0 "$pid" 2>/dev/null && [ "$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -c dcemu)" -gt 0 ] && echo "$pid"
}

old_stack() {   # the 2008 server's containers use the same database volume and port
  local e; e=$(engine)
  local running; running=$($e ps --format '{{.Names}}' 2>/dev/null | grep -E '^driftcity2011_(db|zoneserver)_1$' || true)
  if [ -n "$running" ]; then
    echo "stopping the 2008 server stack (../Server2008), it uses the same database: $running"
    # shellcheck disable=SC2086
    $e stop $running >/dev/null
  fi
}

start_db() {
  old_stack
  echo "database: starting"
  local e; e=$(engine)
  # one database container for every copy of Emulator/ (a 2011 and a 2016 server share it): start it if it is there
  if $e container exists dcemu2011_db 2>/dev/null || $e inspect dcemu2011_db >/dev/null 2>&1; then
    $e start dcemu2011_db >/dev/null
  else
    compose up -d db
  fi
  for _ in $(seq 90); do
    [ "$($e inspect -f '{{.State.Health.Status}}' dcemu2011_db 2>/dev/null)" = healthy ] && { echo "database: ready (127.0.0.1:14330)"; return; }
    sleep 2
  done
  die "the database did not become ready (./launch.sh logs db)"
}

restart_agent() {   # only with the old TrafficAgent (../Server2008/traffic_agent, emulator.ini [traffic] city = agent):
  local e; e=$(engine)  # it does not reconnect, so after the emulator (re)started it must start again
  $e ps --format '{{.Names}}' 2>/dev/null | grep -q '^dc2011_trafficagent$' || return 0
  $e exec dc2011_trafficagent sh -c \
    'ps -eo pid=,stat=,comm= | awk "\$3 == \"TrafficAgent.ex\" && \$2 !~ /Z/ {print \$1}" | xargs -r kill' \
    >/dev/null 2>&1 || true
}

after_emu_up() {    # in the background: once the area port listens, the agent connects again
  ( for _ in $(seq 60); do listening $AREA_PORT && break; sleep 1; done; restart_agent ) &
}

client_tables() {  # the tables that come from the client (not in git): the first time asks which client version
  # (2011 / 2016, written to emulator.ini) and the client folder; the version may have changed: read the settings again
  "$(python)" -m tools.client_setup "$@" || die "the client tables are missing (tools/client_setup.py)"
  read_config
}

start_emu_bg() {
  if pid=$(emu_pid); then echo "emulator: already running (pid $pid)"; return; fi
  client_tables
  listening $AUTH_PORT && die "port $AUTH_PORT is in use by another program (another emulator?)"
  mkdir -p logs
  echo "emulator: starting in the background (output $OUT)"
  nohup "$(python)" -m dcemu -q >> "$OUT" 2>&1 &
  echo $! > "$PIDFILE"
  after_emu_up
  for _ in $(seq 30); do listening $AUTH_PORT && { echo "emulator: listening (pid $(cat "$PIDFILE"))"; return; }; sleep 1; done
  die "the emulator did not start: see $OUT"
}

stop_emu() {
  if pid=$(emu_pid); then
    echo "emulator: stopping (pid $pid)"
    kill "$pid"
    for _ in $(seq 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
  else
    echo "emulator: not running (from this launcher)"
  fi
  rm -f "$PIDFILE"
}

start_client() {   # $1: us (default) or eu; version 2016: the 2016 client
  local dir=$CLIENT_DIR name=DriftCityLauncher
  case "${1:-us}" in us|US) ;; eu|EU) dir=$CLIENT_EU_DIR ;; *) die "client: us or eu, not '$1'" ;; esac
  [ "$VERSION" = 2016 ] && { dir=$CLIENT_2016_DIR; name=DriftCityLauncher2016; }
  local exe=$dir/$name
  [ -x "$exe" ] || die "$exe not found"
  echo "client: starting (${dir##*/})"
  (cd "$dir" && nohup "./$name" >> "$dir/DriftCityLauncher.log" 2>&1 &)
}

status() {
  local e; e=$(engine)
  echo "version:       $VERSION (auth port $AUTH_PORT, database $DB_NAME)"
  if pid=$(emu_pid); then echo "emulator:      running (pid $pid)"; elif listening $AUTH_PORT; then
    echo "emulator:      port $AUTH_PORT in use (started some other way)"; else echo "emulator:      stopped"; fi
  for c in dcemu2011_db; do
    printf '%-14s %s\n' "${c#dcemu2011_}:" "$($e ps -a --filter "name=^$c\$" --format '{{.Status}}' 2>/dev/null | head -1 || true)"
  done
}

case "${1:-all}" in
  all)       start_db; start_emu_bg; start_client "${2:-us}" ;;
  server)    start_db; start_emu_bg ;;
  db)        start_db ;;
  emu)       shift; client_tables; listening $AUTH_PORT && die "port $AUTH_PORT is in use (./launch.sh status)"
             after_emu_up; exec "$(python)" -m dcemu "$@" ;;
  emu-bg)    start_emu_bg ;;
  client)    start_client "${2:-us}" ;;
  restart-emu) stop_emu; start_emu_bg ;;
  stop)
    case "${2:-all}" in
      emu) stop_emu ;;
      db) compose stop db ;;
      all) stop_emu; compose stop db ;;
      *) die "stop what? emu, db" ;;
    esac ;;
  status)    status ;;
  logs)
    case "${2:-emu}" in
      emu) tail -f "$OUT" ;;
      db) compose logs -f db ;;
      *) die "logs of what? emu, db" ;;
    esac ;;
  setup)
    [ -x .venv/bin/python ] || python3 -m venv .venv
    .venv/bin/pip install -q python-tds
    client_tables --choose --refresh
    echo "setup done (version $VERSION)" ;;
  init-db)
    read -r -p "This deletes the $DB_NAME database (all accounts and characters) and creates it again. Type YES: " a
    [ "$a" = YES ] || die "cancelled"
    old_stack
    compose stop db || true
    compose --profile setup run --rm -e "DB_NAME=$DB_NAME" db-setup ;;
  backup-db)
    f=${2:-db/${DB_NAME}_$(date +%F).bak}
    start_db
    sqlcmd -Q "BACKUP DATABASE [$DB_NAME] TO DISK='/var/opt/mssql/data/backup.bak' WITH INIT, COPY_ONLY" >/dev/null
    "$(engine)" cp dcemu2011_db:/var/opt/mssql/data/backup.bak "$f"
    "$(engine)" exec dcemu2011_db rm -f /var/opt/mssql/data/backup.bak
    echo "database saved to $f" ;;
  restore-db)
    f=${2:-}
    [ -n "$f" ] && [ -f "$f" ] || die "usage: ./launch.sh restore-db FILE.bak"
    read -r -p "This replaces the $DB_NAME database (all accounts and characters) with $f. Type YES: " a
    [ "$a" = YES ] || die "cancelled"
    stop_emu
    start_db
    "$(engine)" cp "$f" dcemu2011_db:/var/opt/mssql/data/restore.bak
    # the backup's logical file names (SKDBTW / SKDBTW_log in db/SKDBTW_clean.bak) go to files named after DB_NAME
    mapfile -t logical < <(sqlcmd -h -1 -W -s '|' -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK='/var/opt/mssql/data/restore.bak'" | cut -d'|' -f1,3)
    move=""
    for row in "${logical[@]}"; do
      [ -n "$row" ] || continue
      ext=.mdf; [ "${row#*|}" = L ] && ext=_log.ldf
      move="$move, MOVE '${row%%|*}' TO '/var/opt/mssql/data/$DB_NAME$ext'"
    done
    sqlcmd -Q "IF DB_ID(N'$DB_NAME') IS NOT NULL ALTER DATABASE [$DB_NAME] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; RESTORE DATABASE [$DB_NAME] FROM DISK='/var/opt/mssql/data/restore.bak' WITH REPLACE$move; ALTER DATABASE [$DB_NAME] SET MULTI_USER" >/dev/null
    "$(engine)" exec dcemu2011_db rm -f /var/opt/mssql/data/restore.bak
    echo "database restored (start the emulator: ./launch.sh server)" ;;
  -h|--help|help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command '$1' (./launch.sh help)" ;;
esac
