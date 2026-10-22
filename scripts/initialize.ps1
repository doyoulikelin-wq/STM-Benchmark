$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
    }
    & '.venv/Scripts/python.exe' -m pip install -e '.[test]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & '.venv/Scripts/python.exe' -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Environment validation failed.' }
} finally { Pop-Location }
