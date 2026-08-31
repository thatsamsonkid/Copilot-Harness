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

uv run goat workspace generate
Write-Host "Setup complete. First-run checklist:"
uv run goat init --format text
Write-Host "Next:"
Write-Host "  1. Create a Jira API token (docs/jira-api-token.md), set email/URL in .env,"
Write-Host "     then run: uv run goat jira login"
Write-Host "     (or: uv run goat init --interactive)"
Write-Host "  2. Edit repositories.yml, then ./scripts/clone-repos.sh"
Write-Host "  3. In Copilot Chat: /get-started"
Write-Host "Register goat on PATH (any cwd):"
try {
    uv run goat install --format text
} catch {
    Write-Host "goat install skipped: $_"
}
Write-Host "Run the CLI with: goat <command>  (or: uv run goat <command>)"
Write-Host "From a sibling clone: goat <command>"
Write-Host "  or: uv run --project `"$Root`" goat <command>"
Write-Host "  or: $Root\scripts\goat.ps1 <command>"
