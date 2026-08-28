# Run the coboose CLI through uv when possible. Safe from any cwd.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $env:COBOOSE_ROOT) {
    $env:COBOOSE_ROOT = $Root
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    if ((Test-Path (Join-Path $Root "uv.lock")) -or (Test-Path (Join-Path $Root "pyproject.toml"))) {
        & uv run --project $Root coboose @args
        exit $LASTEXITCODE
    }
}

$venvCoboose = Join-Path $Root ".venv\Scripts\coboose.exe"
if (Test-Path $venvCoboose) {
    & $venvCoboose @args
    exit $LASTEXITCODE
}

$venvCobooseUnix = Join-Path $Root ".venv\bin\coboose"
if (Test-Path $venvCobooseUnix) {
    & $venvCobooseUnix @args
    exit $LASTEXITCODE
}

if (Get-Command coboose -ErrorAction SilentlyContinue) {
    & coboose @args
    exit $LASTEXITCODE
}

Write-Error "uv is required. See docs/install-uv.md (Windows: .\scripts\setup.ps1, macOS/Linux: ./scripts/setup.sh)"
exit 127
