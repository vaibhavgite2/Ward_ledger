"""Live-operations schema (SPEC section 16): accounts, complaint tickets, tasks, repair reports, media,
notifications and the append-only ticket event log.

These tables are created if missing and are NEVER dropped by the analytics pipeline (`db.DERIVED_TABLES`
does not list them), so live complaints survive `python -m pipeline.run --force`.
"""

LIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
  user_id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('citizen','officer','contractor')),
  login TEXT NOT NULL,
  display_name TEXT,
  pw_hash TEXT NOT NULL,
  contractor_id TEXT,
  ward_code TEXT,
  designation TEXT,
  created_at TEXT NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0,
  can_act INTEGER NOT NULL DEFAULT 1,   -- 0 = read-only officer (e.g. audit): sees everything, changes nothing
  email TEXT,                           -- optional: used only for resolution / overdue-task e-mails
  lang TEXT NOT NULL DEFAULT 'en',      -- language of e-mails to this person
  UNIQUE (role, login)
);

CREATE TABLE IF NOT EXISTS auth_session (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, role TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS login_attempt (role TEXT, login TEXT, at TEXT, ok INTEGER);
CREATE INDEX IF NOT EXISTS login_attempt_idx ON login_attempt(role, login, at);

CREATE TABLE IF NOT EXISTS id_counter (name TEXT PRIMARY KEY, value INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS ticket (
  ticket_id TEXT PRIMARY KEY,
  citizen_id TEXT NOT NULL,
  category TEXT NOT NULL,
  category_reported TEXT NOT NULL,
  category_suggested TEXT, suggest_confidence REAL, suggest_extractor TEXT,
  section TEXT NOT NULL DEFAULT 'roads',        -- roads | hospitals | schools | ... (what the complaint is about / near)
  description TEXT NOT NULL,
  locality_text TEXT,
  ward_code TEXT, road_id TEXT, road_distance_m REAL,
  lat REAL, lon REAL, accuracy_m REAL, geo_method TEXT,
  status TEXT NOT NULL,
  duplicate_of TEXT, reject_reason TEXT, task_id TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, verified_at TEXT, resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS ticket_status ON ticket(status);
CREATE INDEX IF NOT EXISTS ticket_ward ON ticket(ward_code);
CREATE INDEX IF NOT EXISTS ticket_citizen ON ticket(citizen_id);

CREATE TABLE IF NOT EXISTS ticket_location (
  ticket_id TEXT NOT NULL, seq INTEGER NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
  accuracy_m REAL, source TEXT NOT NULL, PRIMARY KEY (ticket_id, seq)
);

CREATE TABLE IF NOT EXISTS media (
  media_id TEXT PRIMARY KEY,
  owner_type TEXT NOT NULL,          -- ticket | report
  owner_id TEXT NOT NULL,
  kind TEXT NOT NULL,                -- photo | video | bill
  mime TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
  stored_name TEXT NOT NULL,         -- original, metadata retained (internal only)
  public_name TEXT,                  -- photos: re-encoded copy with EXIF/GPS removed (the only thing ever public)
  uploaded_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS media_owner ON media(owner_type, owner_id);

CREATE TABLE IF NOT EXISTS task (
  task_id TEXT PRIMARY KEY,
  contractor_id TEXT NOT NULL, ward_code TEXT,
  title TEXT, instructions TEXT, repair_method TEXT,
  est_area_sqm REAL, est_cost_inr REAL, due_at TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  started_at TEXT, submitted_at TEXT, completed_at TEXT, approved_cost_inr REAL,
  overdue_notified_at TEXT                      -- set once when the contractor was told the deadline passed
);
CREATE INDEX IF NOT EXISTS task_contractor ON task(contractor_id);
CREATE INDEX IF NOT EXISTS task_status ON task(status);

CREATE TABLE IF NOT EXISTS task_ticket (task_id TEXT NOT NULL, ticket_id TEXT NOT NULL, PRIMARY KEY (task_id, ticket_id));

CREATE TABLE IF NOT EXISTS repair_report (
  report_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, submitted_by TEXT NOT NULL,
  summary TEXT NOT NULL, repair_method TEXT, area_sqm REAL, bill_amount_inr REAL, bill_ref TEXT,
  submitted_at TEXT NOT NULL, decision TEXT NOT NULL DEFAULT 'pending',
  decided_by TEXT, decided_at TEXT, decision_note TEXT, checks_json TEXT
);
CREATE INDEX IF NOT EXISTS report_task ON repair_report(task_id);

-- Ticket and task tracking log: append-only and hash-chained, like `fact`.
CREATE TABLE IF NOT EXISTS ticket_event (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  event TEXT NOT NULL, from_status TEXT, to_status TEXT,
  actor_role TEXT NOT NULL, actor_id TEXT NOT NULL,
  note TEXT, data_json TEXT,
  prev_hash TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ticket_event_entity ON ticket_event(entity_type, entity_id);
CREATE TRIGGER IF NOT EXISTS ticket_event_no_update BEFORE UPDATE ON ticket_event
  BEGIN SELECT RAISE(ABORT, 'ticket_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ticket_event_no_delete BEFORE DELETE ON ticket_event
  BEGIN SELECT RAISE(ABORT, 'ticket_event is append-only'); END;

CREATE TABLE IF NOT EXISTS notification (
  notif_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
  kind TEXT NOT NULL, params_json TEXT, created_at TEXT NOT NULL, read_at TEXT
);
CREATE INDEX IF NOT EXISTS notification_user ON notification(user_id, read_at);

-- "Me too": one supporter vote per citizen per open complaint, instead of raising a duplicate.
CREATE TABLE IF NOT EXISTS ticket_upvote (
  ticket_id TEXT NOT NULL, user_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (ticket_id, user_id)
);
CREATE INDEX IF NOT EXISTS ticket_upvote_user ON ticket_upvote(user_id, created_at);

-- Transactional outbox: a message is queued in the same transaction as the state change that caused it, then sent
-- (SMTP) or logged (no SMTP configured). dedupe_key makes "once per task / per complaint" messages idempotent.
CREATE TABLE IF NOT EXISTS email_outbox (
  email_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT, to_addr TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
  kind TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending',        -- pending | sent | logged | failed
  attempts INTEGER NOT NULL DEFAULT 0, error TEXT,
  created_at TEXT NOT NULL, sent_at TEXT,
  dedupe_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS email_outbox_status ON email_outbox(status);
"""

# Columns added after the first release: applied to databases created earlier (CREATE TABLE IF NOT EXISTS skips them).
MIGRATIONS = [
    ("app_user", "email", "TEXT"),
    ("app_user", "lang", "TEXT NOT NULL DEFAULT 'en'"),
    ("ticket", "section", "TEXT NOT NULL DEFAULT 'roads'"),
    ("task", "overdue_notified_at", "TEXT"),
]
