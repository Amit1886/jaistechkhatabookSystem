$ErrorActionPreference = "Stop"

$repoDb = Join-Path $PSScriptRoot "db.sqlite3"
if (-not (Test-Path $repoDb)) {
    throw "db.sqlite3 not found at: $repoDb"
}

$env:SQLITE_PATH = (Resolve-Path $repoDb).Path
Write-Host "SQLITE_PATH set to: $env:SQLITE_PATH"

