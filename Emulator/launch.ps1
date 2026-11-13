# Drift City 2011 emulator launcher for Windows (Docker Desktop): the database and the emulator run in containers
# (docker-compose.yml), the client natively (..\Client US\ or ..\Client EU\DriftCityLauncher.exe). launch.bat runs this script.
#
#   launch.bat [all] [eu]     database + emulator + the client (US, or the EU client with eu)
#   launch.bat server         database + emulator, no client
#   launch.bat client [eu]    the client only (US, or the EU client with eu; version 2016: ..\DriftCity Dev Ed)
#   launch.bat setup          build the emulator image; which client (2011 / 2016) and its tables (again after a client patch)
#   launch.bat init-db        create the game database from db\postgres (an existing one is DELETED: asks first)
#   launch.bat restore-db F   replace the game database with the dump F (e.g. db\postgres\skdbtw_clean.dump; asks)
#   launch.bat backup-db [F]  save the game database (pg_dump; default db\<name>_<date>.dump)
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
$ClientUsDir = Join-Path $PSScriptRoot '..\Client US'    # the US client (its tables: tools\client_setup.py)
$ClientEuDir = Join-Path $PSScriptRoot '..\Client EU'    # the EU client (tools\eu_client.py)
$Client2016Dir = Join-Path $PSScriptRoot '..\DriftCity Dev Ed'   # the 2016 client (emulator.ini [client] version = 2016)
$DbContainer = 'dcemu_pg'   # PostgreSQL (docker-compose.yml service db)

function Die($msg) { Write-Host "launch: $msg" -ForegroundColor Red; exit 1 }

# A setting of emulator.ini as the emulator resolves it: with [client] version = 2016 the [2016] section's
# "section.key = value" lines replace the ones of the other sections (dcemu/__main__.py apply_2016).
function Setting($name, $default) {
    if ($Version -eq '2016' -and $Ini.ContainsKey("2016.$name")) { return $Ini["2016.$name"] }
    if ($Ini.ContainsKey($name)) { return $Ini[$name] }
    return $default
}
function Read-Config {   # again after the first-launch question changed [client] version
    $script:Ini = @{}
    $section = ''
    foreach ($line in Get-Content (Join-Path $PSScriptRoot 'emulator.ini')) {
        $line = ($line -replace '\s[;#].*$', '').Trim()
        if ($line -match '^\[(.+)\]') { $section = $Matches[1].Trim().ToLower(); continue }
        if ($line -match '^([^;#=][^=]*?)\s*=\s*(.*)$') { $script:Ini["$section.$($Matches[1].ToLower())"] = $Matches[2].Trim() }
    }
    $script:Version = if ($Ini['client.version']) { $Ini['client.version'] } else { '2011' }
    $script:AuthPort = [int]((Setting 'services.auth' '11005 0 56') -split '\s+')[0]
    $script:DbName = Setting 'database.name' 'skdbtw'
    $script:ClientDir = if ($Version -eq '2016') { $Client2016Dir } else { $ClientUsDir }
}
Read-Config

function Docker-Check {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die 'Docker Desktop is needed: https://www.docker.com/products/docker-desktop/' }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { Die 'Docker is not running: start Docker Desktop and try again' }
}

function Compose { docker compose @args; if ($LASTEXITCODE -ne 0) { Die "docker compose $args failed" } }

function Ask($text) { (Read-Host "$text Type YES") -eq 'YES' }

# psql in the database container on one database; extra arguments are psql's (-c ..., -tAc ...)
function Psql($db) { docker exec -i $DbContainer psql -U dcemu -d $db -v ON_ERROR_STOP=1 -q @args }

function Seed-Dump {
    $f = "db\postgres\$($DbName)_clean.dump"
    if (Test-Path $f) { return $f } else { return 'db\postgres\skdbtw_clean.dump' }
}

# A new $DbName from a dump (pg_dump -Fc), then the helpers (db\postgres\00_compat.sql, 02_procedures.sql)
function Create-Db($file) {
    if (-not (Test-Path $file)) { Die "$file not found" }
    Psql dcemu -c "DROP DATABASE IF EXISTS `"$DbName`" WITH (FORCE)" -c "CREATE DATABASE `"$DbName`""
    if ($LASTEXITCODE -ne 0) { Die 'creating the database failed' }
    # through a file in the container: PowerShell's pipes would change the binary dump
    docker cp $file "$($DbContainer):/tmp/restore.dump"
    if ($LASTEXITCODE -ne 0) { Die 'copying the dump into the container failed' }
    docker exec $DbContainer pg_restore -U dcemu -d $DbName --no-owner --exit-on-error /tmp/restore.dump
    if ($LASTEXITCODE -ne 0) { Die "restoring $file failed" }
    docker exec $DbContainer rm -f /tmp/restore.dump
    Get-Content db\postgres\00_compat.sql -Raw | Psql $DbName
    Get-Content db\postgres\02_procedures.sql -Raw | Psql $DbName
    if ($LASTEXITCODE -ne 0) { Die 'the database helpers failed' }
    Write-Host "database $DbName created from $file"
}

function Wait-Db {
    Write-Host 'database: starting'
    Compose up -d db
    for ($i = 0; $i -lt 90; $i++) {
        if ((docker inspect -f '{{.State.Health.Status}}' $DbContainer 2>$null) -eq 'healthy') {
            $have = (Psql dcemu -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" | Out-String).Trim()
            if ($have -ne '1') { Create-Db (Seed-Dump) }
            Write-Host "database: ready ($DbName)"; return
        }
        Start-Sleep 2
    }
    Die 'the database did not become ready (launch.bat logs db)'
}

# The tables that come from the client are not in git: the first time, ask for the client folder and copy them
# (tools\client_setup.py in the emulator's container, the folder mounted at /client: DCEMU_CLIENT_DIR).
# The first launch (tables missing) and setup also ask which client the server is for, 2011 or 2016, and write it to
# emulator.ini [client] version (tools\client_setup.py --version).
function Choose-Version {
    Write-Host "Which Drift City client is this server for?`n  1) 2011 (the US and EU clients)`n  2) 2016 (the 2016 US client, experimental)"
    $default = if ($Version -eq '2011') { '1' } else { '2' }
    while ($true) {
        $a = (Read-Host "Client [$default]").Trim()
        if (-not $a) { $a = $default }
        $v = @{ '1' = '2011'; '2' = '2016'; '2011' = '2011'; '2016' = '2016' }[$a]
        if ($v) { break }
        Write-Host '1 or 2'
    }
    if ($v -ne $Version) {
        docker compose run --rm --no-deps emulator python -m tools.client_setup --version $v --check | Out-Null
        Read-Config
        if ($Version -ne $v) { Die 'writing [client] version to emulator.ini failed' }
        Write-Host "emulator.ini: [client] version = $v"
    }
}

function Client-Tables([switch]$Refresh) {
    if (-not $Refresh) {
        docker compose run --rm --no-deps emulator python -m tools.client_setup --check
        if ($LASTEXITCODE -eq 0) { return }
    }
    Choose-Version
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
        Write-Host "setup done (version $Version). The first server start creates the database (db\postgres)."
    }
    'init-db' {
        if (-not (Ask "This deletes the $DbName database (all accounts and characters) and creates it again.")) { Die 'cancelled' }
        docker compose stop emulator 2>$null
        Wait-Db
        Create-Db (Seed-Dump)
    }
    'restore-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file -or -not (Test-Path $file)) { Die 'usage: launch.bat restore-db FILE.dump' }
        if (-not (Ask "This replaces the $DbName database (all accounts and characters) with $file.")) { Die 'cancelled' }
        docker compose stop emulator 2>$null
        Wait-Db
        Create-Db $file
        Write-Host 'database restored'
    }
    'backup-db' {
        $file = $Rest | Select-Object -First 1
        if (-not $file) { $file = "db\$($DbName)_$(Get-Date -Format yyyy-MM-dd).dump" }
        Wait-Db
        # through a file in the container: PowerShell's pipes would change the binary dump
        docker exec $DbContainer pg_dump -U dcemu -Fc --no-owner -f /tmp/backup.dump $DbName
        if ($LASTEXITCODE -ne 0) { Die 'the backup failed' }
        docker cp "$($DbContainer):/tmp/backup.dump" $file
        if ($LASTEXITCODE -ne 0) { Die 'copying the backup out of the container failed' }
        docker exec $DbContainer rm -f /tmp/backup.dump
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
