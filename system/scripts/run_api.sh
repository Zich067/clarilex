#!/usr/bin/env bash
# 啟動 FastAPI dev server，給 web/ 前端用。
#
# 用法:
#   cd thesis-system
#   ./scripts/run_api.sh
#
# 預設 port 8000；可設 API_PORT=8001 ./scripts/run_api.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${API_PORT:-8000}"
HOST="${API_HOST:-127.0.0.1}"

# 確保 PYTHONPATH 含專案 root
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONIOENCODING=utf-8

exec uvicorn api.main:app --host "$HOST" --port "$PORT" --reload
