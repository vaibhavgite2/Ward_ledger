# How to Start The Ward Ledger

Quick guide to getting the API and UI running. For deeper detail see [DEVELOPMENT.md](DEVELOPMENT.md).

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Git

## 1. One-time setup

Run the setup script from the repo root. It is safe to re-run; finished steps are skipped.

| OS | Command |
|---|---|
| Windows | `setup.bat` |
| macOS / Linux | `./setup.sh` |

Options (both scripts):

- `--test` — set up, then run backend (pytest) and frontend (i18n check, `tsc`) checks
- `--start` — set up, then launch both servers

What the script does:

1. Checks prerequisites
2. Fetches the dataset into `data/` (skipped if `data/complaints.csv` exists)
3. Creates the backend virtualenv at `backend/.venv`
4. Installs backend dependencies
5. Builds `backend/ward_ledger.db` (`python -m pipeline.run --force`)
6. Installs frontend dependencies (creates `frontend/.env.local` from `.env.example`)

> **Demo logins:** `setup.bat` also seeds demo accounts and complaints. `setup.sh` does not, so on macOS/Linux run this once from `backend/`:
> ```bash
> .venv/bin/python -m live.seed --demo --tickets
> ```

## 2. Start the servers

Use two terminals.

**Terminal 1 — API (port 8000)**

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --port 8000      # macOS / Linux
.venv\Scripts\python -m uvicorn app.main:app --port 8000  # Windows
```

**Terminal 2 — UI (port 3000)**

```bash
cd frontend
npm run dev
```

Or let the script do it: `setup.bat --start` (opens two windows) / `./setup.sh --start`.

## 3. Open the app

| What | URL |
|---|---|
| UI | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |

## Demo logins

Password for all seeded accounts: `wardledger-demo`

| Role | Login page | Account |
|---|---|---|
| Officer | `/login/officer` | `ae-4471` |
| Contractor | `/login/contractor` | `ct05` |
| Citizen | `/login/citizen` | `9800000001` |

Demo accounts are for local use only. Never seed them in a real deployment.

## Optional configuration

Everything works without any of these. Set them in the shell that runs `uvicorn`:

- `ANTHROPIC_API_KEY` — enable Claude features (every Claude path has a deterministic fallback)
- `WL_CORS_ORIGINS` — restrict allowed origins (default is `*`)
- `WL_DEMO_PASSWORD` — change the demo password before seeding

The full list is in [.env.example](.env.example). The frontend reads `NEXT_PUBLIC_API_URL` from `frontend/.env.local` (default `http://localhost:8000/api`).

## Troubleshooting

- **"Please log in" / login fails** — seed the demo accounts: `cd backend && .venv/bin/python -m live.seed --demo --tickets`
- **Port already in use** — stop the other process or pass a different `--port` to uvicorn (and update `NEXT_PUBLIC_API_URL`)
- **UI cannot reach the API** — confirm the API is running on port 8000 and that `frontend/.env.local` points to it
- **Empty data** — rebuild the database: `cd backend && .venv/bin/python -m pipeline.run --force`
