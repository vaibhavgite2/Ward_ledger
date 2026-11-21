"""SQLite helpers + the derived-table schema (SPEC §5)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_doc (doc_id TEXT PRIMARY KEY, filename TEXT, rows INT, loaded_at TEXT);

CREATE TABLE IF NOT EXISTS claim (
  claim_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, field_path TEXT, value_json TEXT,
  source_doc TEXT, source_row INT, extractor TEXT, prompt_hash TEXT, confidence REAL, created_at TEXT
);

CREATE TABLE IF NOT EXISTS fact (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  fact_id TEXT UNIQUE, subject_type TEXT, subject_id TEXT, field_path TEXT, value_json TEXT,
  from_claim TEXT, source_doc TEXT, source_row INT, promoted_by TEXT, promoted_at TEXT,
  supersedes TEXT, prev_hash TEXT, row_hash TEXT
);
CREATE TRIGGER IF NOT EXISTS fact_no_update BEFORE UPDATE ON fact BEGIN SELECT RAISE(ABORT,'fact is append-only'); END;
CREATE TRIGGER IF NOT EXISTS fact_no_delete BEFORE DELETE ON fact BEGIN SELECT RAISE(ABORT,'fact is append-only'); END;
CREATE INDEX IF NOT EXISTS fact_subject ON fact(subject_type, subject_id);

CREATE TABLE IF NOT EXISTS parsed_complaint (
  complaint_id TEXT PRIMARY KEY, category TEXT, category_confidence REAL, category_changed INT,
  category_status TEXT, language TEXT, locality TEXT, ward_code TEXT, ward_source TEXT,
  lat REAL, lon REAL, uncertainty_m REAL, geocode_method TEXT, road_id TEXT, road_distance_m REAL,
  issue_id TEXT, link_status TEXT, work_order_id TEXT, extractor TEXT
);

CREATE TABLE IF NOT EXISTS issue (
  issue_id TEXT PRIMARY KEY, category TEXT, road_id TEXT, ward_code TEXT, lat REAL, lon REAL,
  first_reported TEXT, complaint_count INT, upvotes INT, severity INT, work_order_id TEXT, status TEXT
);

CREATE TABLE IF NOT EXISTS finding (
  finding_id TEXT PRIMARY KEY, rule TEXT, rule_version TEXT, subject_type TEXT, subject_id TEXT,
  ward_code TEXT, contractor_id TEXT, polarity TEXT, severity TEXT, metrics_json TEXT, evidence_json TEXT,
  context_json TEXT, public_text_en TEXT, public_text_mr TEXT, public_text_hi TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS finding_subject ON finding(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS finding_ward ON finding(ward_code);

CREATE TABLE IF NOT EXISTS right_of_reply (subject_type TEXT, subject_id TEXT, finding_id TEXT, reply_text TEXT, received_at TEXT);
CREATE TABLE IF NOT EXISTS review_queue (item_id TEXT PRIMARY KEY, claim_id TEXT, subject_id TEXT, reason TEXT, status TEXT, decided_by TEXT, decided_at TEXT);

CREATE TABLE IF NOT EXISTS budget_recommendation (
  run_id TEXT, ward_code TEXT, rank INT, issue_id TEXT, road_id TEXT, score REAL, factors_json TEXT,
  method TEXT, est_cost_inr REAL, bmc_cost_inr REAL, cumulative_inr REAL, funded INT, action TEXT,
  rationale_en TEXT, rationale_mr TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, object_type TEXT, object_id TEXT, detail_json TEXT);

CREATE TABLE IF NOT EXISTS narrative (key TEXT PRIMARY KEY, lang TEXT, text TEXT, extractor TEXT, prompt_hash TEXT, created_at TEXT);
"""

DERIVED_TABLES = [
    "claim", "fact", "parsed_complaint", "issue", "finding", "review_queue",
    "budget_recommendation", "narrative",
]


def connect(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def write_tx(conn):
    """BEGIN IMMEDIATE ... COMMIT. Takes SQLite's write lock *before* reading, so read-then-append
    sequences (hash chains, ID counters, status transitions) cannot interleave between requests."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def tx(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_schema(conn: sqlite3.Connection) -> None:
    from live.schema import LIVE_SCHEMA, MIGRATIONS      # live tables: created if missing, never dropped
    conn.executescript(SCHEMA)
    conn.executescript(LIVE_SCHEMA)
    for table, col, decl in MIGRATIONS:                  # older databases: add the columns introduced later
        if col not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.commit()


def reset_derived(conn: sqlite3.Connection) -> None:
    """Rebuild derived tables. `fact` is append-only via triggers, so drop the whole table
    (a full re-derivation from unchanged sources; never done by the API)."""
    conn.execute("DROP TRIGGER IF EXISTS fact_no_update")
    conn.execute("DROP TRIGGER IF EXISTS fact_no_delete")
    for t in DERIVED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    init_schema(conn)


def rows(conn, sql, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def log(conn, actor, action, object_type="", object_id="", detail=None):
    import json
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO audit_log(ts,actor,action,object_type,object_id,detail_json) VALUES (?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), actor, action, object_type, object_id,
         json.dumps(detail or {}, ensure_ascii=False)),
    )
