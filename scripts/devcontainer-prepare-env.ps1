# Host-side prepare before Dev Container Compose build (Windows initializeCommand).
# Copies versions.env → .devcontainer/.env so Compose can substitute build-args.
# Must Remove-Item before Copy-Item: if .devcontainer/.env is a symlink, overwrite
# would write through into versions.env (#410 / #415).

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repoRoot

$versionsEnv = Join-Path $repoRoot 'versions.env'
$devcontainerDir = Join-Path $repoRoot '.devcontainer'
$envFile = Join-Path $devcontainerDir '.env'

if (-not (Test-Path -LiteralPath $versionsEnv -PathType Leaf)) {
    Write-Error "ERROR: versions.env missing at repo root ($repoRoot)"
    exit 1
}

New-Item -ItemType Directory -Force -Path $devcontainerDir | Out-Null
if (Test-Path -LiteralPath $envFile) {
    Remove-Item -LiteralPath $envFile -Force
}
Copy-Item -LiteralPath $versionsEnv -Destination $envFile -Force
Write-Host 'Prepared .devcontainer/.env from versions.env'
