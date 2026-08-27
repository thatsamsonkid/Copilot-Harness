# Run the harness CLI through uv when possible. Safe from any cwd.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $env:HARNESS_ROOT) {
    $env:HARNESS_ROOT = $Root
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    if ((Test-Path (Join-Path $Root "uv.lock")) -or (Test-Path (Join-Path $Root "pyproject.toml"))) {
        & uv run --project $Root harness @args
        exit $LASTEXITCODE
    }
}

$venvHarness = Join-Path $Root ".venv\Scripts\harness.exe"
if (Test-Path $venvHarness) {
    & $venvHarness @args
    exit $LASTEXITCODE
}

$venvHarnessUnix = Join-Path $Root ".venv\bin\harness"
if (Test-Path $venvHarnessUnix) {
    & $venvHarnessUnix @args
    exit $LASTEXITCODE
}

if (Get-Command harness -ErrorAction SilentlyContinue) {
    & harness @args
    exit $LASTEXITCODE
}

Write-Error "uv is required. See docs/install-uv.md (Windows: .\scripts\setup.ps1, macOS/Linux: ./scripts/setup.sh)"
exit 127
