# Run the goat CLI through uv when possible. Safe from any cwd.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $env:GOAT_ROOT) {
    $env:GOAT_ROOT = if ($env:COBOOSE_ROOT) { $env:COBOOSE_ROOT } else { $Root }
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    if ((Test-Path (Join-Path $Root "uv.lock")) -or (Test-Path (Join-Path $Root "pyproject.toml"))) {
        & uv run --project $Root goat @args
        exit $LASTEXITCODE
    }
}

$venvGoat = Join-Path $Root ".venv\Scripts\goat.exe"
if (Test-Path $venvGoat) {
    & $venvGoat @args
    exit $LASTEXITCODE
}

$venvGoatUnix = Join-Path $Root ".venv\bin\goat"
if (Test-Path $venvGoatUnix) {
    & $venvGoatUnix @args
    exit $LASTEXITCODE
}

if (Get-Command goat -ErrorAction SilentlyContinue) {
    & goat @args
    exit $LASTEXITCODE
}

Write-Error "uv is required. See docs/install-uv.md (Windows: .\scripts\setup.ps1, macOS/Linux: ./scripts/setup.sh)"
exit 127
