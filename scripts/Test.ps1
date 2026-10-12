[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'

& $pythonExe -m ruff check backend
if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed.' }
& $pythonExe -m ruff format --check backend
if ($LASTEXITCODE -ne 0) { throw 'Ruff format check failed.' }
Push-Location 'backend'
try {
    & '..\.venv\Scripts\python.exe' -m mypy app
    if ($LASTEXITCODE -ne 0) { throw 'Mypy failed.' }
    & '..\.venv\Scripts\python.exe' -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Pytest failed.' }
} finally {
    Pop-Location
}
npm.cmd run lint --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'ESLint failed.' }
npm.cmd run format:check --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Prettier check failed.' }
npm.cmd run typecheck --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'TypeScript check failed.' }
npm.cmd test --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Vitest failed.' }
npm.cmd run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
