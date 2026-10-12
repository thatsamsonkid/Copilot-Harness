# Run the goat CLI. Do not `uv run goat`: a PATH shim of that name calls
# `uv run` again, and uv follows it until UV_RUN_RECURSION_DEPTH trips.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$env:GOAT_ROOT = $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -c "import goat" 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $venvPython -m goat @args
        exit $LASTEXITCODE
    }
}

$venvPythonUnix = Join-Path $Root ".venv\bin\python"
if (Test-Path $venvPythonUnix) {
    & $venvPythonUnix -c "import goat" 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $venvPythonUnix -m goat @args
        exit $LASTEXITCODE
    }
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $Root "pyproject.toml")) {
        & uv run --project $Root python -m goat @args
        exit $LASTEXITCODE
    }
}

Write-Error "uv is required. See docs/install-uv.md (Windows: .\scripts\setup.ps1, macOS/Linux: ./scripts/setup.sh)"
exit 127
