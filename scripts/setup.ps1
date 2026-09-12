# CodePilot AI local setup for Windows PowerShell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = Get-Location }

Set-Location $root

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example. Add your LLM_API_KEY before running the agent."
}

py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

Set-Location .\frontend
npm install
Set-Location $root
npm install
Write-Host "Setup complete. From the project root run: npm run dev"
