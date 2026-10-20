#!/usr/bin/env bash
set -euo pipefail

/opt/mssql/bin/sqlservr &
sqlserver_pid=$!
trap 'kill "$sqlserver_pid" 2>/dev/null || true; wait "$sqlserver_pid" 2>/dev/null || true' EXIT

if [[ -x /opt/mssql-tools18/bin/sqlcmd ]]; then
  sqlcmd=(/opt/mssql-tools18/bin/sqlcmd -C)
else
  sqlcmd=(/opt/mssql-tools/bin/sqlcmd)
fi

echo "Waiting for SQL Server to accept connections..."
until "${sqlcmd[@]}" -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -Q 'SELECT 1' >/dev/null 2>&1; do
  if ! kill -0 "$sqlserver_pid" 2>/dev/null; then
    echo "SQL Server exited before becoming ready." >&2
    exit 1
  fi
  sleep 5
done

# This setup command intentionally rebuilds the game database from the checked-in schema.
# DB_NAME: emulator.ini [database] name (launch.sh passes it: SKDBTW for 2011, SKDB2016TEST for 2016)
db=${DB_NAME:-SKDBTW}
"${sqlcmd[@]}" -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -Q "IF DB_ID(N'$db') IS NOT NULL BEGIN ALTER DATABASE [$db] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$db]; END; CREATE DATABASE [$db];"
for script in /scripts/*.sql; do
  [[ "$script" == */setup-db.sh ]] && continue
  echo "Applying $(basename "$script")..."
  "${sqlcmd[@]}" -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d "$db" -b -i "$script"
done
echo "$db is ready."
