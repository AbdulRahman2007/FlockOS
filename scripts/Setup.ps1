[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from local placeholder values. Do not use it for production.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.12 is required. Install Python and reopen PowerShell.'
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Node.js 22 and npm are required.'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop with Compose is required.'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& '.venv\Scripts\python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& '.venv\Scripts\python.exe' -m pip install -e 'backend[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Could not install backend dependencies.' }
npm.cmd ci --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Could not install frontend dependencies.' }
& '.venv\Scripts\python.exe' -m pre_commit install
if ($LASTEXITCODE -ne 0) { throw 'Could not install pre-commit hooks.' }

Write-Host 'Setup complete. Start PostgreSQL and apply the baseline with scripts\Start-Dev.ps1.'
