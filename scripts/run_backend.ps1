$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = Join-Path $root "backend"
$port = 8010
if ($env:APP_PORT) { $port = $env:APP_PORT }
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir backend --app-dir backend --host 127.0.0.1 --port $port
