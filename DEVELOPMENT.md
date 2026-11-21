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
5. Build `backend/ward_ledger.db` with `python -m pipeline.run --force` (about 6 s), then seed the demo login accounts and a few demo complaints (`python -m live.seed --demo --tickets`).
6. Create `frontend/.env.local` from `.env.example` and run `npm install`.

## Manual setup (macOS / Linux, or if you prefer)

```bash
bash scripts/fetch_data.sh
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[test]"          # Windows: .venv/Scripts/pip
.venv/bin/python -m pipeline.run --force
.venv/bin/python -m live.seed --demo --tickets   # demo logins + demo complaints (demo only)
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

## Logging in

Nobody has to log in to browse: complaints, wards, roads, contractors, the map, Ask and RTI are all public.
There are three separate login panels (header → **Log in**), one per role, all backed by the same user table:

| Panel | Who | Can do | Demo account |
|---|---|---|---|
| **Citizen** (`/login/citizen`) | Anyone; registers with a mobile number | Raise complaints (photos, videos, GPS or map pins), track them in **My complaints**, get notifications | `9800000001`, or create your own |
| **Government officer** (`/login/officer`) | Provisioned staff | Verify or reject complaints, bundle them into tasks for a contractor (with pre-award checks), review and approve repair reports, audit trail | `ae-4471` (K/E ward), `ae-3310` (H/W), `ee-1001` (all wards), `audit-01` (read-only) |
| **Contractor** (`/login/contractor`) | Provisioned, linked to an empanelled firm | See assigned tasks, start work, submit evidence, bills and the resolution report, reply to findings about the firm | `ct01` ... `ct08` |

Demo password for all seeded accounts: `wardledger-demo` (override with `WL_DEMO_PASSWORD` before seeding).
These accounts exist only if you run `python -m live.seed --demo`; never seed them in a real deployment.

The workflow follows the DFD: citizen raises a complaint → officer verifies → officer assigns one or more verified
complaints as a task → contractor submits the repair report → officer approves (every complaint in the task is resolved
and its citizen notified) or sends it back. Uploaded files live in `backend/instance/uploads/` (gitignored).

### Supporting a complaint, sections, e-mail and deadlines

- **"Me too" instead of a duplicate.** While raising a complaint, once a pin is dropped the form lists open complaints within 250 m (same category) with an
  **I have this problem too** button; the same button is on every complaint page. One vote per citizen, own complaints and closed ones cannot be voted on,
  the count is public and voters are not. Officers can sort their queue by most supported.
- **Sections.** Every complaint has a section (roads, hospitals, schools, bus stops and stations, markets, residential, other) next to its category;
  the officer can correct it when verifying. The recorded 2025 complaints get a section from their distance to hospitals / schools in `facilities.csv`.
- **Complaints page.** Two tabs: complaints raised in this app, and the 2025 BMC records (6,501), both filterable by ward, category, section and status.
- **E-mail.** Citizens add an optional address when registering or in **My complaints**; contractors in **My tasks**. When an officer approves work, every
  complaint in the task is resolved and the citizen who raised it (and everyone who supported it) is e-mailed the status, contractor and approved bill.
  When a task is still assigned / in progress / sent back after its deadline, the contractor is e-mailed once and the officers are notified in-app.
  The check runs every `WL_OVERDUE_CHECK_MIN` minutes (default 15) inside the API, from the officer button on **Tasks**, or with `python -m live.overdue` (cron).
  A due date typed without a time is due at the end of that day, Mumbai time.
  Without `WL_SMTP_HOST` nothing is sent: messages are stored in the `email_outbox` table with status `logged`
  (`select to_addr, subject, status from email_outbox`). Demo addresses end in `.example` and can never receive mail.
- **Contractor civic trust score.** On the Contractors page and each contractor's page (and in the contractor's own panel); see SPEC section 6.5.

## Tests and checks

```bash
cd backend  && .venv/Scripts/python -m pytest
cd frontend && node scripts/check-i18n.mjs && npx tsc --noEmit
```

End-to-end (optional, drives the whole complaint workflow in a real browser against running servers seeded with `--tickets`):

```bash
cd frontend && npm i -D playwright && npx playwright install chromium
npm run e2e        # BASE=http://localhost:3000 API=http://localhost:8000/api by default; screenshots in e2e-shots/
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
| `WL_INSTANCE_DIR` | Uploads and the media-link signing key (default `backend/instance`) |
| `WL_SECRET` | Signing key for private media links (generated in `WL_INSTANCE_DIR` if unset) |
| `WL_DEMO_PASSWORD` | Password used by `python -m live.seed --demo` |
| `WL_SMTP_HOST`, `WL_SMTP_PORT`, `WL_SMTP_USER`, `WL_SMTP_PASSWORD`, `WL_SMTP_SECURITY` | Send e-mail over SMTP (`starttls` default, `ssl` or `none`); unset = messages are only logged in `email_outbox` |
| `WL_MAIL_FROM` | Sender shown on e-mails |
| `WL_APP_URL` | Base URL of the web app, used for the links inside e-mails (default `http://localhost:3000`) |
| `WL_OVERDUE_CHECK_MIN` | Minutes between automatic deadline checks (default 15, `0` = off) |

PowerShell example: `$env:ANTHROPIC_API_KEY = "sk-..."; .venv\Scripts\python -m uvicorn app.main:app --port 8000`

Frontend: `frontend/.env.local` sets `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`).

## Troubleshooting

- **Port already in use**: stop the old process, or change the port in the uvicorn command and in `NEXT_PUBLIC_API_URL`.
- **Complaints page is empty or shows "Not Found"**: the API process is older than the code (uvicorn does not reload by itself). Stop it and start it again.
- **"Please log in" / login fails**: run `python -m live.seed --demo` from `backend/` to create the demo accounts.
- **New pages show errors after pulling**: restart the API (uvicorn does not reload by itself); it adds the new tables on start.
- **Empty or stale data**: re-run `backend\.venv\Scripts\python -m pipeline.run --force` from `backend/`.
- **`python` not found**: reinstall Python with "Add to PATH" ticked, then open a new terminal.
- **Dataset clone fails**: check network access to github.com, or copy the CSV/GeoJSON files into `data/` by hand.

See [SPEC.md](SPEC.md) section 15 for implementation status and [agents.md](agents.md) for the agent architecture.
