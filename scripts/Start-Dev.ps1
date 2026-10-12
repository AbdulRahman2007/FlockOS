[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path '.env')) {
    throw 'Missing .env. Run scripts\Setup.ps1 first.'
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    throw 'Missing Python environment. Run scripts\Setup.ps1 first.'
}

docker compose up -d --wait postgres
if ($LASTEXITCODE -ne 0) { throw 'Could not start PostgreSQL. Check Docker Desktop.' }
& '.venv\Scripts\python.exe' -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Could not apply the database baseline migration.' }
Write-Host 'PostgreSQL is running and the baseline migration is applied.'
Write-Host 'API:      .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload'
Write-Host 'Frontend: npm.cmd run dev --prefix frontend'
Write-Host 'Run the API and frontend commands in separate PowerShell terminals.'
