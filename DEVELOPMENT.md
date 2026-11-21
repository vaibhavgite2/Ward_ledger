# Developer Setup

Everything here is synthetic data. No API key is required: every Claude code path has a deterministic fallback.

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js / npm | 18+ |
| Git | any recent |

## Quick start (Windows)

```bat
setup.bat            :: set everything up
setup.bat --test     :: set up, then run pytest + i18n check + tsc
setup.bat --start    :: set up, then open the API and UI in two new windows
```

`setup.bat` is safe to re-run. It will:

1. Check that Python, Node, npm and Git are installed.
2. Clone the dataset into `data/` (skipped if `data/complaints.csv` exists).
3. Create `backend/.venv`.
4. Install backend dependencies (`pip install -e ".[test]"`).
5. Build `backend/ward_ledger.db` with `python -m pipeline.run --force` (about 6 s).
6. Create `frontend/.env.local` from `.env.example` and run `npm install`.

## Manual setup (macOS / Linux, or if you prefer)

```bash
bash scripts/fetch_data.sh
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[test]"          # Windows: .venv/Scripts/pip
.venv/bin/python -m pipeline.run --force
cd ../frontend
cp .env.example .env.local
npm install
```

## Running

```bash
# terminal 1: API on http://localhost:8000 (docs at /docs)
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000

# terminal 2: UI on http://localhost:3000
cd frontend && npm run dev
```

Use the **View as** menu in the header to switch between Citizen, Officer and Auditor.

## Tests and checks

```bash
cd backend  && .venv/Scripts/python -m pytest
cd frontend && node scripts/check-i18n.mjs && npx tsc --noEmit
```

## Configuration

All optional. The backend reads real environment variables only; it does **not** load a `.env` file, so export them in the shell that runs uvicorn.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enable live Claude output |
| `WL_DISABLE_CLAUDE=1` | Force deterministic fallbacks even when a key is set |
| `WL_AS_OF` | "Today" for the dataset (default `2025-10-05`) |
| `WL_MODEL_FAST`, `WL_MODEL_WRITER` | Override model IDs |
| `WL_CORS_ORIGINS` | Allowed frontend origins |
| `WL_DATA_DIR`, `WL_DB_PATH` | Override dataset and database locations |

PowerShell example: `$env:ANTHROPIC_API_KEY = "sk-..."; .venv\Scripts\python -m uvicorn app.main:app --port 8000`

Frontend: `frontend/.env.local` sets `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`).

## Troubleshooting

- **Port already in use**: stop the old process, or change the port in the uvicorn command and in `NEXT_PUBLIC_API_URL`.
- **Empty or stale data**: re-run `backend\.venv\Scripts\python -m pipeline.run --force` from `backend/`.
- **`python` not found**: reinstall Python with "Add to PATH" ticked, then open a new terminal.
- **Dataset clone fails**: check network access to github.com, or copy the CSV/GeoJSON files into `data/` by hand.

See [SPEC.md](SPEC.md) section 15 for implementation status and [agents.md](agents.md) for the agent architecture.
