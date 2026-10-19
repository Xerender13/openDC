# Drift City 2011 emulator launcher for Windows (Docker Desktop): the database and the emulator run in containers
# (docker-compose.yml), the client natively (..\Client US\ or ..\Client EU\DriftCityLauncher.exe). launch.bat runs this script.
#
#   launch.bat [all] [eu]     database + emulator + the client (US, or the EU client with eu)
#   launch.bat server         database + emulator, no client
#   launch.bat client [eu]    the 2011 client only (US, or the EU client with eu)
#   launch.bat setup          first time (and after a client patch): build the emulator image, copy the client's tables
#   launch.bat init-db        create the game database from db\*.sql (an existing one is DELETED: asks first)
#   launch.bat restore-db F   replace the game database with the SQL Server backup F (e.g. db\SKDBTW_clean.bak; asks)
#   launch.bat backup-db [F]  save the game database to a SQL Server backup (default db\SKDBTW_<date>.bak)
#   launch.bat stop           stop the emulator and the database
#   launch.bat restart-emu    restart the emulator (clients are disconnected)
#   launch.bat status         what is running
#   launch.bat logs [db]      follow the emulator's (or the database's) output; Ctrl+C stops following
#   launch.bat gm ARGS        GM commands (tools\gmctl.py): who | kick NAME | block NAME days | ban ACCOUNT ...
#
# Needs Docker Desktop (running). Settings: emulator.ini; the clients': ..\Client US\ and ..\Client EU\DriftCityLauncher.ini.
param([string]$Command = 'all', [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$ErrorActionPreference = 'Continue'   # docker writes progress to stderr: exit codes are checked instead
# no extra arguments: $Rest is $null and $Rest[0] threw "Cannot index into a null array" after the server had started
# (a Windows user, 2026-10-19: launch.bat closed right away); an empty array gives $null for $Rest[0]
if (-not $Rest) { $Rest = @() }
# any other script error: exit 1, so launch.bat keeps the window open (it pauses on errorlevel 1)
trap { Write-Host "launch: $_" -ForegroundColor Red; exit 1 }
Set-Location $PSScriptRoot
$ClientDir = Join-Path $PSScriptRoot '..\Client US'      # the US client: setup copies its tables
$ClientEuDir = Join-Path $PSScriptRoot '..\Client EU'    # the EU client (tools\eu_client.py)
$Sql = @('exec', 'dcemu2011_db', '/opt/mssql-tools18/bin/sqlcmd', '-C', '-S', 'localhost', '-U', 'sa', '-P', 'z0ne!server', '-b')

function Die($msg) { Write-Host "launch: $msg" -ForegroundColor Red; exit 1 }

function Docker-Check {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die 'Docker Desktop is needed: https://www.docker.com/products/docker-desktop/' }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { Die 'Docker is not running: start Docker Desktop and try again' }
}

function Compose { docker compose @args; if ($LASTEXITCODE -ne 0) { Die "docker compose $args failed" } }

function Ask($text) { (Read-Host "$text Type YES") -eq 'YES' }

function Wait-Db {
    Write-Host 'database: starting'
    Compose up -d db
    for ($i = 0; $i -lt 90; $i++) {
        if ((docker inspect -f '{{.State.Health.Status}}' dcemu2011_db 2>$null) -eq 'healthy') { Write-Host 'database: ready'; return }
        Start-Sleep 2
    }
    Die 'the database did not become ready (launch.bat logs db)'
}

function Need-Setup {
    if (-not (Test-Path 'server_data\Init')) { Die 'run "launch.bat setup" first (it copies the client''s tables)' }
}

function Start-Server {
    Need-Setup
    Wait-Db
    Write-Host 'emulator: starting'
    Compose up -d emulator
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-NetConnection 127.0.0.1 -Port 11005 -InformationLevel Quiet -WarningAction SilentlyContinue) {
            Write-Host 'emulator: listening on 11005-11051'; return
        }
        Start-Sleep 1
    }
    Die 'the emulator did not start (launch.bat logs)'
}

function Start-Client([string]$Which = 'us') {
    $dir = if ($Which -eq 'eu') { $ClientEuDir } else { $ClientDir }
    $exe = Join-Path $dir 'DriftCityLauncher.exe'
    if (-not (Test-Path $exe)) { Die "$exe not found" }
    Write-Host "client: starting ($(Split-Path $dir -Leaf))"
    Start-Process -FilePath $exe -WorkingDirectory $dir
}

Docker-Check
switch ($Command) {
    'all'         { Start-Server; Start-Client $Rest[0] }
    'server'      { Start-Server }
    'client'      { Start-Client $Rest[0] }
    'setup' {
        Compose build emulator
        Compose run --rm --no-deps emulator python -m tools.sync_data /client server_data
        Write-Host 'setup done. A new machine also needs a database: launch.bat init-db (or restore-db db\SKDBTW_clean.bak)'
    }
    'init-db' {
        if (-not (Ask 'This deletes the SKDBTW database (all accounts and characters) and creates it again.')) { Die 'cancelled' }
        docker compose stop emulator db 2>$null
        Compose --profile setup run --rm db-setup
    }
    'restore-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file -or -not (Test-Path $file)) { Die 'usage: launch.bat restore-db FILE.bak' }
        if (-not (Ask "This replaces the SKDBTW database (all accounts and characters) with $file.")) { Die 'cancelled' }
        docker compose stop emulator 2>$null
        Wait-Db
        docker cp $file dcemu2011_db:/var/opt/mssql/data/restore.bak
        if ($LASTEXITCODE -ne 0) { Die 'copying the backup into the container failed' }
        docker @Sql -Q "IF DB_ID(N'SKDBTW') IS NOT NULL ALTER DATABASE SKDBTW SET SINGLE_USER WITH ROLLBACK IMMEDIATE; RESTORE DATABASE SKDBTW FROM DISK='/var/opt/mssql/data/restore.bak' WITH REPLACE, MOVE 'SKDBTW' TO '/var/opt/mssql/data/SKDBTW.mdf', MOVE 'SKDBTW_log' TO '/var/opt/mssql/data/SKDBTW_log.ldf'; ALTER DATABASE SKDBTW SET MULTI_USER"
        if ($LASTEXITCODE -ne 0) { Die 'the restore failed' }
        docker exec dcemu2011_db rm -f /var/opt/mssql/data/restore.bak
        Write-Host 'database restored'
    }
    'backup-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file) { $file = "db\SKDBTW_$(Get-Date -Format yyyy-MM-dd).bak" }
        Wait-Db
        docker @Sql -Q "BACKUP DATABASE SKDBTW TO DISK='/var/opt/mssql/data/backup.bak' WITH INIT, COPY_ONLY" | Out-Null
        if ($LASTEXITCODE -ne 0) { Die 'the backup failed' }
        docker cp dcemu2011_db:/var/opt/mssql/data/backup.bak $file
        if ($LASTEXITCODE -ne 0) { Die 'copying the backup out of the container failed' }
        docker exec dcemu2011_db rm -f /var/opt/mssql/data/backup.bak
        Write-Host "database saved to $file"
    }
    'stop'        { docker compose stop emulator db }
    'restart-emu' { Need-Setup; Compose restart emulator }
    'status'      { docker compose ps -a }
    'logs' {
        $part = if ($Rest -and $Rest[0] -eq 'db') { 'db' } else { 'emulator' }
        docker compose logs -f --tail 100 $part
    }
    'gm'          { docker compose exec emulator python -m tools.gmctl @Rest }
    { $_ -in 'help', '-h', '--help' } { Get-Content $PSCommandPath | Select-Object -Skip 1 -First 16 | ForEach-Object { $_ -replace '^# ?', '' } }
    default       { Die "unknown command '$Command' (launch.bat help)" }
}
