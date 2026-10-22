param([ValidateRange(1,50)][int]$Seeds=20, [ValidateRange(0,950)][int]$SeedOffset=100)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.venv/Scripts/python.exe' -m stm_bench compare --seeds $Seeds --seed-offset $SeedOffset
    if ($LASTEXITCODE -ne 0) { throw 'Comparison infrastructure failed; inspect retained output.' }
} finally { Pop-Location }
