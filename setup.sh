#!/usr/bin/env bash
# ============================================================
#  The Ward Ledger - one-shot developer environment setup (macOS / Linux)
#  Usage:  ./setup.sh            set everything up
#          ./setup.sh --test     set up, then run backend + frontend checks
#          ./setup.sh --start    set up, then launch both servers
#  Safe to re-run: every step skips work that is already done.
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV_PY="$BACKEND/.venv/bin/python"

DO_TEST=0
DO_START=0
for arg in "$@"; do
  case "$arg" in
    --test)  DO_TEST=1 ;;
    --start) DO_START=1 ;;
  esac
done

echo ""
echo "=== [1/7] Checking prerequisites ==="
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Python 3.11+ not found on PATH."; exit 1; }
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" || { echo "[ERROR] Python 3.11 or newer is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[ERROR] Node.js 18+ not found on PATH."; exit 1; }
command -v npm  >/dev/null 2>&1 || { echo "[ERROR] npm not found on PATH."; exit 1; }
command -v git  >/dev/null 2>&1 || { echo "[ERROR] Git not found on PATH."; exit 1; }
echo "  $(python3 --version)"
echo "  node $(node --version)"

echo ""
echo "=== [2/7] Checking dataset in data/ ==="
if [ -f "$ROOT/data/complaints.csv" ]; then
  echo "  data/ already populated, skipping."
else
  "$ROOT/scripts/fetch_data.sh"
fi

echo ""
echo "=== [3/7] Creating backend virtualenv ==="
if [ -x "$VENV_PY" ]; then
  echo "  backend/.venv already exists, skipping."
else
  python3 -m venv "$BACKEND/.venv"
fi

echo ""
echo "=== [4/7] Installing backend dependencies ==="
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -e "$BACKEND[test]"

echo ""
echo "=== [5/7] Building the database (pipeline) ==="
(cd "$BACKEND" && "$VENV_PY" -m pipeline.run --force)

echo ""
echo "=== [6/7] Installing frontend dependencies ==="
if [ ! -f "$FRONTEND/.env.local" ] && [ -f "$FRONTEND/.env.example" ]; then
  cp "$FRONTEND/.env.example" "$FRONTEND/.env.local"
  echo "  created frontend/.env.local from .env.example"
fi
(cd "$FRONTEND" && npm install)

echo ""
echo "=== [7/7] Done ==="
echo "  Backend  : backend/.venv ready, backend/ward_ledger.db built"
echo "  Frontend : frontend/node_modules installed"
echo ""
echo "  Run the API : cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000"
echo "  Run the UI  : cd frontend && npm run dev     (http://localhost:3000)"
echo "  Optional    : set ANTHROPIC_API_KEY in the shell that runs uvicorn (see .env.example)"
echo ""

if [ "$DO_TEST" -eq 1 ]; then
  echo "=== Running checks ==="
  (cd "$BACKEND" && "$VENV_PY" -m pytest)
  (cd "$FRONTEND" && node scripts/check-i18n.mjs && npx tsc --noEmit)
fi

if [ "$DO_START" -eq 1 ]; then
  echo "=== Starting servers ==="
  echo "  API: http://localhost:8000/docs"
  echo "  UI : http://localhost:3000"
  (cd "$BACKEND" && "$VENV_PY" -m uvicorn app.main:app --port 8000) &
  BACKEND_PID=$!
  (cd "$FRONTEND" && npm run dev) &
  FRONTEND_PID=$!
  trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' EXIT INT TERM
  wait
fi
