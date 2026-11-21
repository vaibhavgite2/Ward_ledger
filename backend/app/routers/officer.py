"""Officer console endpoints (role: officer). Risk-flag framing, planner detail, file noting, review queue."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

import db
from agents import budget, noting
from agents import facts as Fx
from app import schemas
from app.deps import actor, get_conn, lang_q, planner_ref, require_role
from rules import promote as P
from rules import text as T

router = APIRouter(prefix="/api/officer", tags=["officer"], dependencies=[Depends(require_role("officer"))])

_SEV = "CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END"


@router.get("/flags")
def flags(ward: str | None = None, rule: str | None = None, severity: str | None = None, limit: int = Query(100, le=500),
          offset: int = 0, conn=Depends(get_conn)):
    where, params = ["f.polarity='concern'"], []
    if ward:
        where.append("f.ward_code=?"); params.append(ward.replace("-", "/").upper())
    if rule:
        where.append("f.rule=?"); params.append(rule)
    if severity:
        where.append("f.severity=?"); params.append(severity)
    total = db.one(conn, f"SELECT COUNT(*) n FROM finding f WHERE {' AND '.join(where)}", params)["n"]
    rows = db.rows(conn, f"SELECT f.* FROM finding f WHERE {' AND '.join(where)} ORDER BY {_SEV}, f.finding_id LIMIT ? OFFSET ?", params + [limit, offset])
    rp = Fx._replies(conn)
    counts = db.rows(conn, f"SELECT rule, COUNT(*) n FROM finding f WHERE {' AND '.join(where)} GROUP BY rule", params)
    queue = db.one(conn, "SELECT COUNT(*) n FROM review_queue WHERE status='pending'")["n"]
    return {"total": total, "counts": {c["rule"]: c["n"] for c in counts}, "review_queue_pending": queue,
            "items": [Fx.serialize_finding(conn, r, "en", True, rp) for r in rows]}


@router.get("/works")
def works(ward: str, sort: str = "dlp", limit: int = Query(100, le=500), offset: int = 0, conn=Depends(get_conn)):
    """Dense work-order table. Sorted by what needs attention first (DLP, SLA, findings)."""
    ward = ward.replace("-", "/").upper()
    order = {
        "dlp": "r.under_dlp DESC, nf DESC, w.completed_at DESC",
        "sla": "(w.sla_met='N') DESC, nf DESC, w.completed_at DESC",
        "findings": "nf DESC, w.cost_inr DESC",
        "recent": "w.completed_at DESC",
        "cost": "w.cost_inr DESC",
    }.get(sort, "r.under_dlp DESC")
    q = (f"SELECT w.*, r.road_name, r.under_dlp, r.last_resurfaced, "
         f"(SELECT COUNT(*) FROM finding f WHERE f.subject_type='work_order' AND f.subject_id=w.work_order_id AND f.polarity='concern' AND f.rule<>'sla_missed') nf "
         f"FROM work_orders w JOIN roads r USING(road_id) WHERE w.ward_code=? ORDER BY {order} LIMIT ? OFFSET ?")
    rows = db.rows(conn, q, (ward, limit, offset))
    total = db.one(conn, "SELECT COUNT(*) n FROM work_orders WHERE ward_code=?", (ward,))["n"]
    ids = [r["work_order_id"] for r in rows]
    fl = {}
    if ids:
        qq = ",".join("?" * len(ids))
        for f in db.rows(conn, f"SELECT subject_id, rule, severity, polarity FROM finding WHERE subject_type='work_order' AND subject_id IN ({qq})", ids):
            fl.setdefault(f["subject_id"], []).append({"rule": f["rule"], "severity": f["severity"], "label": T.OFFICER_LABEL[f["rule"]]})
    return {"total": total, "items": [{**Fx.work_summary_row(r), "road_name": r["road_name"], "under_dlp": r["under_dlp"] == "Y",
                                       "last_resurfaced": r["last_resurfaced"], "flags": fl.get(r["work_order_id"], [])} for r in rows]}


@router.get("/works/{wo_id}")
def work(wo_id: str, conn=Depends(get_conn)):
    w = Fx.work_detail(conn, wo_id, "en", officer=True)
    if not w:
        raise HTTPException(404, "Unknown work order")
    return w


@router.get("/budget/{ward}")
def planner(ward: str, as_of: str | None = None, lang: str = Depends(lang_q), conn=Depends(get_conn), ref=Depends(planner_ref)):
    plan = budget.plan_ward(conn, ward.replace("-", "/").upper(), as_of=as_of, ref=ref)
    if not plan:
        raise HTTPException(404, "Unknown ward")
    for it in plan["items"]:
        r = budget.render_item(it, lang)
        it["rationale"], it["reasons_text"] = r["rationale"], r["reasons_text"]
        it["category_label"] = T.category(it["category"], lang)
    return plan


@router.post("/draft-noting/{work_id}")
def draft_noting(work_id: str, lang: str = "mr", conn=Depends(get_conn), who: str = Depends(actor)):
    d = noting.draft(conn, work_id, lang)
    if not d:
        raise HTTPException(404, "Unknown work order")
    db.log(conn, who, "draft_noting_generated", "work_order", work_id, {"lang": lang, "paras": len(d["paras"]), "blocked": len(d["blocked"])})
    conn.commit()
    return d              # returned to the editor only; never stored as a fact


@router.post("/reply")
def add_reply(body: schemas.ReplyIn, conn=Depends(get_conn), who: str = Depends(actor)):
    f = db.one(conn, "SELECT * FROM finding WHERE finding_id=?", (body.finding_id,))
    if not f:
        raise HTTPException(404, "Unknown finding")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("INSERT INTO right_of_reply VALUES (?,?,?,?,?)", (f["subject_type"], f["subject_id"], f["finding_id"], body.reply_text[:2000], now))
    db.log(conn, who, "right_of_reply_recorded", "finding", body.finding_id)
    conn.commit()
    return {"ok": True, "received_at": now}


@router.get("/review-queue")
def review_queue(status: str = "pending", limit: int = Query(50, le=200), offset: int = 0, conn=Depends(get_conn)):
    total = db.one(conn, "SELECT COUNT(*) n FROM review_queue WHERE status=?", (status,))["n"]
    rows = db.rows(conn, "SELECT q.item_id, q.reason, q.subject_id, q.status, c.field_path, c.value_json, c.extractor, c.confidence, c.claim_id "
                         "FROM review_queue q JOIN claim c USING(claim_id) WHERE q.status=? ORDER BY q.item_id LIMIT ? OFFSET ?", (status, limit, offset))
    return {"total": total, "items": rows}


@router.post("/review/{item_id}")
def decide(item_id: str, body: schemas.DecisionIn, conn=Depends(get_conn), who: str = Depends(actor)):
    """A named human promotes (or rejects) a queued claim. Append-only: promotion adds a new fact row."""
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    q = db.one(conn, "SELECT * FROM review_queue WHERE item_id=?", (item_id,))
    if not q or q["status"] != "pending":
        raise HTTPException(404, "No such pending item")
    claim = db.one(conn, "SELECT * FROM claim WHERE claim_id=?", (q["claim_id"],))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if body.action == "approve":
        led = P.Ledger(conn, run_ts=now)
        led.fact(claim["subject_type"], claim["subject_id"], claim["field_path"], json.loads(claim["value_json"]), who,
                 from_claim=claim["claim_id"], source_doc=claim["source_doc"], source_row=claim["source_row"])
        led.flush()
        if claim["field_path"] == "category":
            conn.execute("UPDATE parsed_complaint SET category_status='verified' WHERE complaint_id=?", (claim["subject_id"],))
    conn.execute("UPDATE review_queue SET status=?, decided_by=?, decided_at=? WHERE item_id=?",
                 ("approved" if body.action == "approve" else "rejected", who, now, item_id))
    db.log(conn, who, f"review_{body.action}", "review_queue", item_id, {"note": body.note})
    conn.commit()
    return {"ok": True, "status": "approved" if body.action == "approve" else "rejected", "decided_by": who}

