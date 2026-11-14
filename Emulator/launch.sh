#!/usr/bin/env bash
# Drift City emulator launcher: start the components together or one by one. emulator.ini [client] version says
# which client build (2011 or 2016) this server is for; the ports, database and client follow from it.
#
#   ./launch.sh [all] [eu]   database + emulator (in the background) + the client (US rules, or EU rules with eu;
#                            version 2016: the 2016 client ../DriftCity Dev Ed)
#   ./launch.sh server       database + emulator (in the background), no client
#   ./launch.sh db           the database only (PostgreSQL container dcemu_pg)
#   ./launch.sh emu [-q]     the emulator only, in the foreground (Ctrl+C stops it; -q: log to the file only)
#   ./launch.sh emu-bg       the emulator only, in the background (output: logs/emulator.out)
#   ./launch.sh client [eu]  the client: ../Client US/DriftCityLauncher, or for version 2016
#                            ../DriftCity Dev Ed/DriftCityLauncher2016; eu = with the EU rules (the launcher's --eu:
#                            Launcher/eurules.go, tools/eu_rules.py; the EU client is retired since 2026-11-14)
#   ./launch.sh stop [part]  stop everything, or one part: emu, db
#   ./launch.sh restart-emu  stop and start the background emulator (clients are disconnected)
#   ./launch.sh status       what is running
#   ./launch.sh logs [part]  follow a log: emu (default), db
#   ./launch.sh setup        first time: the Python environment (.venv with pg8000), which client (2011 or 2016:
#                            emulator.ini [client] version) and its tables; after a client patch: copy them again
#                            (the first server / emu start asks the same on its own: tools/client_setup.py)
#   ./launch.sh init-db      create the game database from db/postgres (an existing one is DELETED: asks first)
#   ./launch.sh backup-db [F]    save the game database (pg_dump; default db/<name>_<date>.dump)
#   ./launch.sh restore-db F     replace the game database with the dump F (e.g. db/postgres/skdbtw_clean.dump; asks first)
# The game database is [database] name: skdbtw for 2011, skdb2016test for 2016 (emulator.ini [2016]); the first start
# makes it from db/postgres when it is not there.
#
# Needs: Python 3.10+, podman (or docker) with podman-compose / docker compose. The emulator's settings are in
# emulator.ini; the clients' in their DriftCityLauncher.ini ([client] rules = us / eu).
set -euo pipefail
cd "$(dirname "$0")"
HERE=$(pwd)
PIDFILE=$HERE/.emulator.pid
OUT=$HERE/logs/emulator.out
CLIENT_DIR="$HERE/../Client US"          # the US client (its tables: tools/client_setup.py asks for the folder)
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

DB_CONTAINER=dcemu_pg

psql_db() {     # psql inside the database container: psql_db DATABASE [psql arguments]
  local d=$1; shift
  "$(engine)" exec -i "$DB_CONTAINER" psql -U dcemu -d "$d" -v ON_ERROR_STOP=1 -q "$@"
}

db_exists() { [ "$(psql_db dcemu -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")" = 1 ]; }

seed_dump() {   # the clean database a new one starts from
  local f=db/postgres/${DB_NAME}_clean.dump
  [ -f "$f" ] || f=db/postgres/skdbtw_clean.dump
  echo "$f"
}

create_db() {   # create_db DUMP: a new $DB_NAME from the dump (pg_dump -Fc), then the helpers and procedures
  local f=$1
  [ -f "$f" ] || die "$f not found"
  psql_db dcemu -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE)" -c "CREATE DATABASE \"$DB_NAME\""
  # the dump has the citext extension, the helpers and the tables; the helper scripts after it bring them up to date
  "$(engine)" exec -i "$DB_CONTAINER" pg_restore -U dcemu -d "$DB_NAME" --no-owner --exit-on-error < "$f"
  psql_db "$DB_NAME" < db/postgres/00_compat.sql
  psql_db "$DB_NAME" < db/postgres/02_procedures.sql
  echo "database $DB_NAME created from $f"
}

listening() { ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; }

emu_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid; pid=$(cat "$PIDFILE")
  kill -0 "$pid" 2>/dev/null && [ "$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -c dcemu)" -gt 0 ] && echo "$pid"
}

start_db() {
  echo "database: starting"
  local e; e=$(engine)
  # one database container for every copy of Emulator/ (a 2011 and a 2016 server share it): start it if it is there
  if $e container exists $DB_CONTAINER 2>/dev/null || $e inspect $DB_CONTAINER >/dev/null 2>&1; then
    $e start $DB_CONTAINER >/dev/null
  else
    compose up -d db
  fi
  for _ in $(seq 90); do
    if [ "$($e inspect -f '{{.State.Health.Status}}' $DB_CONTAINER 2>/dev/null)" = healthy ]; then
      db_exists || create_db "$(seed_dump)"
      echo "database: ready (127.0.0.1:15432, $DB_NAME)"; return
    fi
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

start_client() {   # $1: us or eu, the rules (default: the launcher's ini, [client] rules); version 2016: the 2016 client
  local dir=$CLIENT_DIR name=DriftCityLauncher rules=
  case "${1:-}" in '') ;; us|US) rules=--us ;; eu|EU) rules=--eu ;; *) die "client: us or eu, not '$1'" ;; esac
  [ "$VERSION" = 2016 ] && { dir=$CLIENT_2016_DIR; name=DriftCityLauncher2016; }
  local exe=$dir/$name
  [ -x "$exe" ] || die "$exe not found"
  echo "client: starting (${dir##*/}${rules:+, ${rules#--} rules})"
  (cd "$dir" && nohup "./$name" $rules >> "$dir/DriftCityLauncher.log" 2>&1 &)
}

status() {
  local e; e=$(engine)
  echo "version:       $VERSION (auth port $AUTH_PORT, database $DB_NAME)"
  if pid=$(emu_pid); then echo "emulator:      running (pid $pid)"; elif listening $AUTH_PORT; then
    echo "emulator:      port $AUTH_PORT in use (started some other way)"; else echo "emulator:      stopped"; fi
  printf '%-14s %s\n' "db:" "$($e ps -a --filter "name=^$DB_CONTAINER\$" --format '{{.Status}}' 2>/dev/null | head -1 || true)"
}

case "${1:-all}" in
  all)       start_db; start_emu_bg; start_client "${2:-}" ;;
  server)    start_db; start_emu_bg ;;
  db)        start_db ;;
  emu)       shift; client_tables; listening $AUTH_PORT && die "port $AUTH_PORT is in use (./launch.sh status)"
             after_emu_up; exec "$(python)" -m dcemu "$@" ;;
  emu-bg)    start_emu_bg ;;
  client)    start_client "${2:-}" ;;
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
    .venv/bin/pip install -q pg8000
    client_tables --choose --refresh
    echo "setup done (version $VERSION)" ;;
  init-db)
    read -r -p "This deletes the $DB_NAME database (all accounts and characters) and creates it again. Type YES: " a
    [ "$a" = YES ] || die "cancelled"
    stop_emu
    start_db
    create_db "$(seed_dump)" ;;
  backup-db)
    f=${2:-db/${DB_NAME}_$(date +%F).dump}
    start_db
    "$(engine)" exec "$DB_CONTAINER" pg_dump -U dcemu -Fc --no-owner "$DB_NAME" > "$f"
    echo "database saved to $f" ;;
  restore-db)
    f=${2:-}
    [ -n "$f" ] && [ -f "$f" ] || die "usage: ./launch.sh restore-db FILE.dump"
    read -r -p "This replaces the $DB_NAME database (all accounts and characters) with $f. Type YES: " a
    [ "$a" = YES ] || die "cancelled"
    stop_emu
    start_db
    create_db "$f"
    echo "database restored (start the emulator: ./launch.sh server)" ;;
  -h|--help|help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command '$1' (./launch.sh help)" ;;
esac
