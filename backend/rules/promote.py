"""Claims -> facts promotion (SPEC §5). The model never writes facts; rules or named humans do.

`Ledger` buffers claims/facts/review items and writes them in order. Facts are append-only and
hash-chained: row_hash = sha256(prev_hash || canonical row).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import config
import db

RULE_SOURCE_CSV = "rule:source-csv@v1"
RULE_TWO_SOURCE = "rule:two-source-agree@v1"
RULE_HIGH_CONF = "rule:high-confidence@v1"

# WO columns promoted straight from the source rows (SPEC §5)
WO_FIELDS = ["cost_inr", "contractor_id", "road_id", "repair_method", "area_sqm", "assigned_at",
             "completed_at", "sla_hours", "sla_met", "reopened_within_30d"]
ROAD_FIELDS = ["under_dlp", "last_resurfaced"]


def _canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def compute_row_hash(prev_hash: str, row: dict) -> str:
    return hashlib.sha256((prev_hash + _canon(row)).encode("utf-8")).hexdigest()


_FACT_KEYS = ["subject_type", "subject_id", "field_path", "value_json", "from_claim", "source_doc",
              "source_row", "promoted_by", "promoted_at", "supersedes"]
GENESIS = "0" * 64


class Ledger:
    def __init__(self, conn, run_ts: str | None = None):
        self.conn = conn
        self.ts = run_ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.claims: list[tuple] = []
        self.facts: list[dict] = []
        self.queue_rows: list[tuple] = []
        last = db.one(conn, "SELECT row_hash FROM fact ORDER BY seq DESC LIMIT 1")
        self.prev_hash = last["row_hash"] if last else GENESIS
        self._claim_ids: set[str] = set()

    def claim(self, subject_type, subject_id, field_path, value, source_doc, source_row,
              extractor, prompt_hash=None, confidence=None) -> str:
        vj = json.dumps(value, ensure_ascii=False, default=str)
        cid = "c_" + hashlib.sha256(f"{subject_type}|{subject_id}|{field_path}|{vj}|{extractor}".encode()).hexdigest()[:20]
        if cid not in self._claim_ids:
            self._claim_ids.add(cid)
            self.claims.append((cid, subject_type, subject_id, field_path, vj, source_doc, source_row,
                                extractor, prompt_hash, confidence, self.ts))
        return cid

    def fact(self, subject_type, subject_id, field_path, value, promoted_by, *, from_claim=None,
             source_doc=None, source_row=None, supersedes=None) -> str:
        row = {"subject_type": subject_type, "subject_id": subject_id, "field_path": field_path,
               "value_json": json.dumps(value, ensure_ascii=False, default=str), "from_claim": from_claim,
               "source_doc": source_doc, "source_row": source_row, "promoted_by": promoted_by,
               "promoted_at": self.ts, "supersedes": supersedes}
        row["prev_hash"] = self.prev_hash
        row["row_hash"] = compute_row_hash(self.prev_hash, {k: row[k] for k in _FACT_KEYS})
        row["fact_id"] = "f_" + row["row_hash"][:20]
        self.prev_hash = row["row_hash"]
        self.facts.append(row)
        return row["fact_id"]

    def queue(self, claim_id, subject_id, reason):
        item = "q_" + hashlib.sha256(f"{claim_id}|{reason}".encode()).hexdigest()[:20]
        self.queue_rows.append((item, claim_id, subject_id, reason, "pending", None, None))

    def flush(self):
        c = self.conn
        c.executemany("INSERT OR IGNORE INTO claim VALUES (?,?,?,?,?,?,?,?,?,?,?)", self.claims)
        c.executemany(
            "INSERT INTO fact(fact_id,subject_type,subject_id,field_path,value_json,from_claim,source_doc,"
            "source_row,promoted_by,promoted_at,supersedes,prev_hash,row_hash) VALUES "
            "(:fact_id,:subject_type,:subject_id,:field_path,:value_json,:from_claim,:source_doc,"
            ":source_row,:promoted_by,:promoted_at,:supersedes,:prev_hash,:row_hash)", self.facts)
        c.executemany("INSERT OR IGNORE INTO review_queue VALUES (?,?,?,?,?,?,?)", self.queue_rows)
        c.commit()
        self.claims, self.facts, self.queue_rows = [], [], []


def promote_source_facts(ledger: Ledger, conn) -> int:
    """rule:source-csv: facts read directly from CSV rows, citing (file sha256, row)."""
    n = 0
    wo_doc = _doc(conn, "work_orders.csv")
    for r in db.rows(conn, "SELECT * FROM work_orders ORDER BY work_order_id"):
        for f in WO_FIELDS:
            v = r[f]
            if v is None:
                continue
            ledger.fact("work_order", r["work_order_id"], f, v, RULE_SOURCE_CSV, source_doc=wo_doc, source_row=r["_row"])
            n += 1
    rd_doc = _doc(conn, "roads.csv")
    for r in db.rows(conn, "SELECT * FROM roads ORDER BY road_id"):
        for f in ROAD_FIELDS:
            if r[f] is not None:
                ledger.fact("road", r["road_id"], f, r[f], RULE_SOURCE_CSV, source_doc=rd_doc, source_row=r["_row"])
                n += 1
    return n


def _doc(conn, filename):
    r = db.one(conn, "SELECT doc_id FROM source_doc WHERE filename=?", (filename,))
    return r["doc_id"] if r else None


def promote_category(ledger: Ledger, claim_id: str, complaint: dict, parsed: dict, wo_type: str | None,
                     complaints_doc: str, vague_labels: set[str], valid: list[str]) -> tuple[str, str | None]:
    """Apply the promotion rules to a parsed category claim. -> (status, promoted_by|None)."""
    cid = complaint["complaint_id"]
    cat = parsed["category"]
    reported = complaint.get("category_reported")
    value = {"category": cat, "extractor": parsed["extractor"], "confidence": parsed["confidence"]}
    src = dict(source_doc=complaints_doc, source_row=complaint["_row"], from_claim=claim_id)
    if reported in valid and cat == reported:
        ledger.fact("complaint", cid, "category", value | {"agrees_with": "reported_category"}, RULE_TWO_SOURCE, **src)
        return "verified", RULE_TWO_SOURCE
    if wo_type and cat == wo_type:
        ledger.fact("complaint", cid, "category", value | {"agrees_with": "linked_work_order.work_type"},
                    RULE_TWO_SOURCE, **src)
        return "verified", RULE_TWO_SOURCE
    vague = reported is None or reported in vague_labels or reported not in valid
    if vague and parsed["confidence"] >= config.RULES["promotion"]["high_confidence"]:
        ledger.fact("complaint", cid, "category", value | {"agrees_with": None}, RULE_HIGH_CONF, **src)
        return "verified", RULE_HIGH_CONF
    reason = f"parsed '{cat}' differs from reported '{reported}'" + (f" and linked work order '{wo_type}'" if wo_type else "")
    ledger.queue(claim_id, cid, reason)
    return "unverified", None


def verify_chain(conn) -> dict:
    """Recompute the fact hash chain. -> {ok, checked, first_broken_seq}"""
    prev = GENESIS
    n = 0
    for r in conn.execute("SELECT * FROM fact ORDER BY seq"):
        row = {k: r[k] for k in _FACT_KEYS}
        if r["prev_hash"] != prev or compute_row_hash(prev, row) != r["row_hash"]:
            return {"ok": False, "checked": n, "first_broken_seq": r["seq"]}
        prev = r["row_hash"]
        n += 1
    return {"ok": True, "checked": n, "first_broken_seq": None}
