$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$portablePython = Join-Path $projectRoot '.tools\python\python.exe'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} elseif (Test-Path -LiteralPath $portablePython) {
    & $portablePython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} else {
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
}
