param([switch]$ReadOnly, [ValidateSet(6501,6502,6503)][int]$Port=6501)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if ($ReadOnly) {
        $probeOutput = Join-Path $projectRoot ('runs/probe_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
        & '.venv/Scripts/python.exe' -m stm_bench.demo --probe --out $probeOutput --port $Port
    } else {
        & '.venv/Scripts/python.exe' -m stm_bench demo --port $Port
    }
    if ($LASTEXITCODE -ne 0) { throw 'Demo did not qualify; inspect the retained evidence.' }
} finally { Pop-Location }
