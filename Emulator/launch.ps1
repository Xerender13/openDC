# Drift City 2011 emulator launcher for Windows (Docker Desktop): the database and the emulator run in containers
# (docker-compose.yml), the client natively (..\Client US\ or ..\Client EU\DriftCityLauncher.exe). launch.bat runs this script.
#
#   launch.bat [all] [eu]     database + emulator + the client (US, or the EU client with eu)
#   launch.bat server         database + emulator, no client
#   launch.bat client [eu]    the client only (US, or the EU client with eu; version 2016: ..\DriftCity Dev Ed)
#   launch.bat setup          build the emulator image; copy the client's tables again (after a client patch)
#   launch.bat init-db        create the game database from db\*.sql (an existing one is DELETED: asks first)
#   launch.bat restore-db F   replace the game database with the SQL Server backup F (e.g. db\SKDBTW_clean.bak; asks)
#   launch.bat backup-db [F]  save the game database to a SQL Server backup (default db\SKDBTW_<date>.bak)
#   launch.bat stop           stop the emulator and the database
#   launch.bat restart-emu    restart the emulator (clients are disconnected)
#   launch.bat status         what is running
#   launch.bat logs [db]      follow the emulator's (or the database's) output; Ctrl+C stops following
#   launch.bat gm ARGS        GM commands (tools\gmctl.py): who | kick NAME | block NAME days | ban ACCOUNT ...
#
# emulator.ini [client] version (2011 or 2016) picks the client build; with 2016 its [2016] section's ports and database.
# Needs Docker Desktop (running). Settings: emulator.ini; the clients': ..\Client US\ and ..\Client EU\DriftCityLauncher.ini.
param([string]$Command = 'all', [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$ErrorActionPreference = 'Continue'   # docker writes progress to stderr: exit codes are checked instead
# no extra arguments: $Rest is $null and $Rest[0] threw "Cannot index into a null array" after the server had started
# (a Windows user, 2026-10-19: launch.bat closed right away); an empty array gives $null for $Rest[0]
if (-not $Rest) { $Rest = @() }
# any other script error: exit 1, so launch.bat keeps the window open (it pauses on errorlevel 1)
trap { Write-Host "launch: $_" -ForegroundColor Red; exit 1 }
Set-Location $PSScriptRoot
$ClientDir = Join-Path $PSScriptRoot '..\Client US'      # the US client (its tables: tools\client_setup.py)
$ClientEuDir = Join-Path $PSScriptRoot '..\Client EU'    # the EU client (tools\eu_client.py)
$Client2016Dir = Join-Path $PSScriptRoot '..\DriftCity Dev Ed'   # the 2016 client (emulator.ini [client] version = 2016)
$Sql = @('exec', 'dcemu2011_db', '/opt/mssql-tools18/bin/sqlcmd', '-C', '-S', 'localhost', '-U', 'sa', '-P', 'z0ne!server', '-b')

function Die($msg) { Write-Host "launch: $msg" -ForegroundColor Red; exit 1 }

# A setting of emulator.ini as the emulator resolves it: with [client] version = 2016 the [2016] section's
# "section.key = value" lines replace the ones of the other sections (dcemu/__main__.py apply_2016).
$Ini = @{}
$section = ''
foreach ($line in Get-Content (Join-Path $PSScriptRoot 'emulator.ini')) {
    $line = ($line -replace '\s[;#].*$', '').Trim()
    if ($line -match '^\[(.+)\]') { $section = $Matches[1].Trim().ToLower(); continue }
    if ($line -match '^([^;#=][^=]*?)\s*=\s*(.*)$') { $Ini["$section.$($Matches[1].ToLower())"] = $Matches[2].Trim() }
}
$Version = if ($Ini['client.version']) { $Ini['client.version'] } else { '2011' }
function Setting($name, $default) {
    if ($Version -eq '2016' -and $Ini.ContainsKey("2016.$name")) { return $Ini["2016.$name"] }
    if ($Ini.ContainsKey($name)) { return $Ini[$name] }
    return $default
}
$AuthPort = [int]((Setting 'services.auth' '11005 0 56') -split '\s+')[0]
$DbName = Setting 'database.name' 'SKDBTW'
if ($Version -eq '2016') { $ClientDir = $Client2016Dir }

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

# The tables that come from the client are not in git: the first time, ask for the client folder and copy them
# (tools\client_setup.py in the emulator's container, the folder mounted at /client: DCEMU_CLIENT_DIR).
function Client-Tables([switch]$Refresh) {
    if (-not $Refresh) {
        docker compose run --rm --no-deps emulator python -m tools.client_setup --check
        if ($LASTEXITCODE -eq 0) { return }
    }
    $default = if (Test-Path $ClientDir) { (Resolve-Path $ClientDir).Path } else { '' }
    while ($true) {
        $dir = (Read-Host "Drift City client folder [$default]").Trim('"', ' ')
        if (-not $dir) { $dir = $default }
        if (-not $dir -or -not (Test-Path $dir -PathType Container)) { Write-Host "not a folder: $dir"; continue }
        $env:DCEMU_CLIENT_DIR = (Resolve-Path $dir).Path
        $extra = if ($Refresh) { @('--refresh') } else { @() }
        docker compose run --rm --no-deps emulator python -m tools.client_setup --client /client @extra
        if ($LASTEXITCODE -eq 0) { return }
    }
}

function Need-Setup { Client-Tables }

function Start-Server {
    Need-Setup
    Wait-Db
    Write-Host 'emulator: starting'
    Compose up -d emulator
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-NetConnection 127.0.0.1 -Port $AuthPort -InformationLevel Quiet -WarningAction SilentlyContinue) {
            Write-Host "emulator: listening (version $Version, auth port $AuthPort)"; return
        }
        Start-Sleep 1
    }
    Die 'the emulator did not start (launch.bat logs)'
}

function Start-Client([string]$Which = 'us') {
    $dir = if ($Which -eq 'eu' -and $Version -ne '2016') { $ClientEuDir } else { $ClientDir }
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
        Client-Tables -Refresh
        Write-Host 'setup done. A new machine also needs a database: launch.bat init-db (or restore-db db\SKDBTW_clean.bak)'
    }
    'init-db' {
        if (-not (Ask "This deletes the $DbName database (all accounts and characters) and creates it again.")) { Die 'cancelled' }
        docker compose stop emulator db 2>$null
        Compose --profile setup run --rm -e "DB_NAME=$DbName" db-setup
    }
    'restore-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file -or -not (Test-Path $file)) { Die 'usage: launch.bat restore-db FILE.bak' }
        if (-not (Ask "This replaces the $DbName database (all accounts and characters) with $file.")) { Die 'cancelled' }
        docker compose stop emulator 2>$null
        Wait-Db
        docker cp $file dcemu2011_db:/var/opt/mssql/data/restore.bak
        if ($LASTEXITCODE -ne 0) { Die 'copying the backup into the container failed' }
        # the backup's logical file names (SKDBTW / SKDBTW_log in db\SKDBTW_clean.bak) go to files named after the database
        $move = ''
        foreach ($row in (docker @Sql -h -1 -W -s '|' -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK='/var/opt/mssql/data/restore.bak'")) {
            $f = "$row" -split '\|'
            if ($f.Count -lt 3 -or -not $f[0]) { continue }
            $ext = if ($f[2] -eq 'L') { '_log.ldf' } else { '.mdf' }
            $move += ", MOVE '$($f[0])' TO '/var/opt/mssql/data/$DbName$ext'"
        }
        docker @Sql -Q "IF DB_ID(N'$DbName') IS NOT NULL ALTER DATABASE [$DbName] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; RESTORE DATABASE [$DbName] FROM DISK='/var/opt/mssql/data/restore.bak' WITH REPLACE$move; ALTER DATABASE [$DbName] SET MULTI_USER"
        if ($LASTEXITCODE -ne 0) { Die 'the restore failed' }
        docker exec dcemu2011_db rm -f /var/opt/mssql/data/restore.bak
        Write-Host 'database restored'
    }
    'backup-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file) { $file = "db\$($DbName)_$(Get-Date -Format yyyy-MM-dd).bak" }
        Wait-Db
        docker @Sql -Q "BACKUP DATABASE [$DbName] TO DISK='/var/opt/mssql/data/backup.bak' WITH INIT, COPY_ONLY" | Out-Null
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
    { $_ -in 'help', '-h', '--help' } { Get-Content $PSCommandPath | Select-Object -Skip 1 -First 17 | ForEach-Object { $_ -replace '^# ?', '' } }
    default       { Die "unknown command '$Command' (launch.bat help)" }
}
