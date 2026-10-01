param([switch]$Install, [switch]$Full, [switch]$CreateVenv)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$Python = 'python'
if ($CreateVenv) {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    $Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
}
$Arguments = @('-m', 'scripts.doctor')
if ($Install) { $Arguments += '--install' }
if ($Full) { $Arguments += '--full' }
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Write-Host "Start the app with: $Python -m app"
