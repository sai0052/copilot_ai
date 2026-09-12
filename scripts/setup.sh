#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -f .env ]; then
  cp .env.example .env
fi
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
