param([ValidateSet('train','dev','test')][string]$Split='test', [ValidateRange(1,50)][int]$Seeds=5,
      [ValidateSet('strict-v1','relaxed-v1')][string]$Profile='relaxed-v1')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.venv/Scripts/python.exe' -m stm_bench evaluate --split $Split --seeds $Seeds --policies rule random --profile $Profile
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark infrastructure failure; inspect output evidence.' }
} finally { Pop-Location }
