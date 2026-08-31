# Backward-compatible alias. Prefer .\scripts\goat.ps1
& (Join-Path $PSScriptRoot "goat.ps1") @args
exit $LASTEXITCODE
