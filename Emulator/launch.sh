#!/usr/bin/env bash
# Drift City 2011 emulator launcher: start the components together or one by one.
#
#   ./launch.sh [all]        database + emulator (in the background) + the client
#   ./launch.sh server       database + emulator (in the background), no client
#   ./launch.sh db           the database only (SQL Server container)
#   ./launch.sh emu [-q]     the emulator only, in the foreground (Ctrl+C stops it; -q: log to the file only)
#   ./launch.sh emu-bg       the emulator only, in the background (output: logs/emulator.out)
#   ./launch.sh client       the 2011 client (../Client/DriftCityLauncher)
#   ./launch.sh stop [part]  stop everything, or one part: emu, db
#   ./launch.sh restart-emu  stop and start the background emulator (clients are disconnected)
#   ./launch.sh status       what is running
#   ./launch.sh logs [part]  follow a log: emu (default), db
#   ./launch.sh setup        first time: the Python environment (.venv with python-tds) and the client tables (server_data/Init, server_data/tables)
#   ./launch.sh init-db      create the game database from db/*.sql (an existing one is DELETED: asks first)
#
# Needs: Python 3.10+, podman (or docker) with podman-compose / docker compose. The emulator's settings are in
# emulator.ini; the client's in ../Client/DriftCityLauncher.ini.
set -euo pipefail
cd "$(dirname "$0")"
HERE=$(pwd)
PIDFILE=$HERE/.emulator.pid
OUT=$HERE/logs/emulator.out
CLIENT_DIR=$HERE/../Client
AREA_PORT=11031
AUTH_PORT=11005

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
  compose up -d db
  local e; e=$(engine)
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

start_emu_bg() {
  if pid=$(emu_pid); then echo "emulator: already running (pid $pid)"; return; fi
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

start_client() {
  local exe=$CLIENT_DIR/DriftCityLauncher
  [ -x "$exe" ] || die "$exe not found"
  echo "client: starting"
  (cd "$CLIENT_DIR" && nohup ./DriftCityLauncher >> "$CLIENT_DIR/DriftCityLauncher.log" 2>&1 &)
}

status() {
  local e; e=$(engine)
  if pid=$(emu_pid); then echo "emulator:      running (pid $pid)"; elif listening $AUTH_PORT; then
    echo "emulator:      port $AUTH_PORT in use (started some other way)"; else echo "emulator:      stopped"; fi
  for c in dcemu2011_db; do
    printf '%-14s %s\n' "${c#dcemu2011_}:" "$($e ps -a --filter "name=^$c\$" --format '{{.Status}}' 2>/dev/null | head -1 || true)"
  done
}

case "${1:-all}" in
  all)       start_db; start_emu_bg; start_client ;;
  server)    start_db; start_emu_bg ;;
  db)        start_db ;;
  emu)       shift; listening $AUTH_PORT && die "port $AUTH_PORT is in use (./launch.sh status)"
             after_emu_up; exec "$(python)" -m dcemu "$@" ;;
  emu-bg)    start_emu_bg ;;
  client)    start_client ;;
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
    .venv/bin/python -m tools.sync_data "$CLIENT_DIR" server_data
    echo "setup done" ;;
  init-db)
    read -r -p "This deletes the SKDBTW database (all accounts and characters) and creates it again. Type YES: " a
    [ "$a" = YES ] || die "cancelled"
    old_stack
    compose stop db || true
    compose --profile setup run --rm db-setup ;;
  -h|--help|help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command '$1' (./launch.sh help)" ;;
esac
