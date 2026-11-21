"""Audit trail endpoints (role: auditor). A log, not a dashboard: raw rows, no interpretation."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

import db
from app.deps import get_conn, require
from live import events as LE
from rules import promote as P

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require("officer"))])

FACT_SQL = """
SELECT f.seq, f.promoted_at ts, f.subject_type, f.subject_id, f.field_path, f.value_json value, f.promoted_by actor,
       f.fact_id, f.from_claim, f.supersedes, f.prev_hash, f.row_hash, f.source_doc, f.source_row,
       s.filename source_file, c.extractor, c.prompt_hash, c.confidence,
       COALESCE(w.ward_code, p.ward_code, r.ward_code) ward, w.contractor_id contractor,
       (SELECT fact_id FROM fact n WHERE n.supersedes=f.fact_id LIMIT 1) superseded_by
FROM fact f
LEFT JOIN source_doc s ON s.doc_id=f.source_doc
LEFT JOIN claim c ON c.claim_id=f.from_claim
LEFT JOIN work_orders w ON f.subject_type='work_order' AND w.work_order_id=f.subject_id
LEFT JOIN parsed_complaint p ON f.subject_type='complaint' AND p.complaint_id=f.subject_id
LEFT JOIN roads r ON f.subject_type='road' AND r.road_id=f.subject_id
"""


def _filters(ward, contractor, frm, to, field, subject):
    where, params = ["1=1"], []
    if ward:
        where.append("COALESCE(w.ward_code, p.ward_code, r.ward_code)=?"); params.append(ward)
    if contractor:
        where.append("w.contractor_id=?"); params.append(contractor)
    if frm:
        where.append("f.promoted_at>=?"); params.append(frm)
    if to:
        where.append("f.promoted_at<=?"); params.append(to + "T23:59:59" if len(to) == 10 else to)
    if field:
        where.append("f.field_path=?"); params.append(field)
    if subject:
        where.append("f.subject_id=?"); params.append(subject)
    return " AND ".join(where), params


def _row(r: dict) -> dict:
    out = dict(r)
    out["value"] = json.loads(out["value"]) if out.get("value") else None
    out["superseded_note"] = (f"[SUPERSEDED by fact_id:{out['superseded_by']}]" if out.get("superseded_by") else None)
    return out


@router.get("")
def audit(ward: str | None = None, contractor: str | None = None, frm: str | None = Query(None, alias="from"), to: str | None = None,
          field: str | None = None, subject: str | None = None, limit: int = Query(100, le=1000), offset: int = 0, conn=Depends(get_conn)):
    where, params = _filters(ward, contractor, frm, to, field, subject)
    total = db.one(conn, f"SELECT COUNT(*) n FROM fact f LEFT JOIN work_orders w ON f.subject_type='work_order' AND w.work_order_id=f.subject_id "
                         f"LEFT JOIN parsed_complaint p ON f.subject_type='complaint' AND p.complaint_id=f.subject_id "
                         f"LEFT JOIN roads r ON f.subject_type='road' AND r.road_id=f.subject_id WHERE {where}", params)["n"]
    rows = db.rows(conn, f"{FACT_SQL} WHERE {where} ORDER BY f.seq LIMIT ? OFFSET ?", params + [limit, offset])
    return {"total": total, "offset": offset, "items": [_row(r) for r in rows]}


@router.get("/verify")
def verify(conn=Depends(get_conn)):
    v = P.verify_chain(conn)
    head = db.one(conn, "SELECT row_hash FROM fact ORDER BY seq DESC LIMIT 1")
    return {**v, "head_hash": head["row_hash"] if head else None}


@router.get("/export")
def export(format: str = "csv", ward: str | None = None, contractor: str | None = None, frm: str | None = Query(None, alias="from"),
           to: str | None = None, field: str | None = None, conn=Depends(get_conn)):
    if format != "csv":
        raise HTTPException(400, "Only csv export is supported")
    where, params = _filters(ward, contractor, frm, to, field, None)
    rows = db.rows(conn, f"{FACT_SQL} WHERE {where} ORDER BY f.seq LIMIT 200000", params)
    cols = ["seq", "ts", "subject_type", "subject_id", "field_path", "value", "actor", "fact_id", "from_claim", "supersedes",
            "source_file", "source_doc", "source_row", "extractor", "prompt_hash", "confidence", "prev_hash", "row_hash"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c) for c in cols])
    v = P.verify_chain(conn)
    db.log(conn, "auditor", "audit_export", "fact", "", {"rows": len(rows), "chain_ok": v["ok"]})
    conn.commit()
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=ward-ledger-audit.csv",
                             "X-Chain-OK": str(v["ok"]).lower(), "X-Chain-Checked": str(v["checked"]),
                             "X-Rows": str(len(rows))})


@router.get("/live")
def live_log(entity: str | None = None, limit: int = Query(200, le=2000), offset: int = 0, conn=Depends(get_conn)):
    """The complaint/task tracking log (ticket_event): append-only and hash-chained, raw rows."""
    where, params = ("WHERE entity_id=?", [entity.strip().upper()]) if entity else ("", [])
    total = db.one(conn, f"SELECT COUNT(*) n FROM ticket_event {where}", params)["n"]
    rows = db.rows(conn, f"SELECT * FROM ticket_event {where} ORDER BY seq LIMIT ? OFFSET ?", params + [limit, offset])
    return {"total": total, "items": rows}


@router.get("/live/verify")
def live_verify(conn=Depends(get_conn)):
    return LE.verify(conn)


@router.get("/{work_id}/chain")
def chain(work_id: str, conn=Depends(get_conn)):
    """Everything known about a work record, oldest first: facts, the claims behind them, findings."""
    facts = db.rows(conn, f"{FACT_SQL} WHERE f.subject_id=? OR f.subject_id IN (SELECT complaint_id FROM parsed_complaint WHERE work_order_id=?) "
                          f"OR f.subject_id=(SELECT road_id FROM work_orders WHERE work_order_id=?) ORDER BY f.seq", (work_id, work_id, work_id))
    if not facts:
        raise HTTPException(404, "No facts for that work order")
    out = []
    for f in facts:
        full = db.one(conn, "SELECT * FROM fact WHERE fact_id=?", (f["fact_id"],))
        ok = P.compute_row_hash(full["prev_hash"], {k: full[k] for k in P._FACT_KEYS}) == full["row_hash"]
        out.append({**_row(f), "row_hash_ok": ok})
    claims = db.rows(conn, "SELECT * FROM claim WHERE subject_id=? OR subject_id IN (SELECT complaint_id FROM parsed_complaint WHERE work_order_id=?)", (work_id, work_id))
    findings = db.rows(conn, "SELECT finding_id, rule, rule_version, severity, polarity, metrics_json, evidence_json FROM finding WHERE subject_id=?", (work_id,))
    return {"work_id": work_id, "facts": out, "claims": claims, "findings": findings, "all_hashes_ok": all(x["row_hash_ok"] for x in out)}


@router.get("/log/actions")
def action_log(limit: int = Query(100, le=500), conn=Depends(get_conn)):
    return {"items": db.rows(conn, "SELECT * FROM audit_log ORDER BY seq DESC LIMIT ?", (limit,))}
