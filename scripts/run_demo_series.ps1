param([ValidateRange(1,5)][int]$Repeats=5, [ValidateSet('strict-v1','relaxed-v1')][string]$Profile='relaxed-v1')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.venv/Scripts/python.exe' -m stm_bench demo-series --repeats $Repeats --profile $Profile
    if ($LASTEXITCODE -ne 0) { throw 'Some Demo trials did not qualify; evidence has been retained.' }
} finally { Pop-Location }
