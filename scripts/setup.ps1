$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $localBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path $localBin) {
        $env:Path = "$localBin;$env:Path"
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is still not on PATH. Open a new PowerShell window and see docs/install-uv.md"
    exit 1
}

uv sync

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — fill in Jira values."
}

uv run harness workspace generate
Write-Host "Setup complete. First-run checklist:"
uv run harness init --format text
