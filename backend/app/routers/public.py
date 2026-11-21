"""Public (citizen / corporator) endpoints. Facts and neutral findings only."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

import config
import db
from agents import bot, budget, rti
from agents import facts as Fx
from agents import scorecard as S
from app import schemas
from app.deps import get_conn, lang_q, planner_ref
from rules import text as T

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/meta")
def meta(conn=Depends(get_conn)):
    spend = db.one(conn, "SELECT SUM(cost_inr) s, COUNT(*) n, SUM(CASE WHEN reopened_within_30d='Y' THEN cost_inr ELSE 0 END) f, "
                         "SUM(CASE WHEN reopened_within_30d='Y' THEN 1 ELSE 0 END) fn FROM work_orders")
    budget_total = db.one(conn, "SELECT SUM(monsoon_repair_budget_inr_2025) b FROM wards")["b"]
    nf = db.one(conn, "SELECT COUNT(*) n FROM issue WHERE status='never_fixed'")["n"]
    return {
        "notice": config.SYNTHETIC_NOTICE, "as_of": config.AS_OF, "claude_enabled": config.CLAUDE_ENABLED,
        "city": {"budget_inr": budget_total, "spend_inr": spend["s"], "jobs": spend["n"], "failed_inr": spend["f"],
                 "failed_jobs": spend["fn"], "never_fixed_issues": nf,
                 "complaints": db.one(conn, "SELECT COUNT(*) n FROM complaints")["n"],
                 "unique_issues": db.one(conn, "SELECT COUNT(*) n FROM issue")["n"]},
    }


@router.get("/wards")
def wards(conn=Depends(get_conn)):
    return S.compare_wards(conn)


@router.get("/wards/compare")
def wards_compare(conn=Depends(get_conn)):
    return S.compare_wards(conn)


@router.get("/wards/geojson")
def wards_geojson():
    from pipeline.geo import load_geo
    return load_geo().ward_geojson


@router.get("/roads/geojson")
def roads_geojson(ward: str | None = None, conn=Depends(get_conn)):
    """Road segments with repair-history properties for the map."""
    import json as _j
    gj = _j.loads((config.DATA_DIR / "roads.geojson").read_text(encoding="utf-8"))
    stats = {r["road_id"]: r for r in db.rows(conn, "SELECT road_id, COUNT(*) repairs, SUM(reopened_within_30d='Y') failed, SUM(cost_inr) spent FROM work_orders GROUP BY road_id")}
    dlp = {r["road_id"]: r["under_dlp"] == "Y" for r in db.rows(conn, "SELECT road_id, under_dlp FROM roads")}
    open_i = {r["road_id"]: r["n"] for r in db.rows(conn, "SELECT road_id, COUNT(*) n FROM issue WHERE status IN ('never_fixed','pending','fixed_failed') AND road_id IS NOT NULL GROUP BY road_id")}
    feats = []
    for f in gj["features"]:
        p = f["properties"]
        if ward and p["ward_code"] != ward:
            continue
        s = stats.get(p["road_id"], {"repairs": 0, "failed": 0, "spent": 0})
        p.update(repairs=s["repairs"], failed=s["failed"] or 0, spent=s["spent"] or 0, under_dlp=dlp.get(p["road_id"], False),
                 open_issues=open_i.get(p["road_id"], 0))
        feats.append(f)
    return {"type": "FeatureCollection", "features": feats}


@router.get("/wards/{code:path}/money-trail")
def money_trail(code: str, lang: str = Depends(lang_q), conn=Depends(get_conn)):
    code = code.replace("-", "/").upper()
    t = S.ward_money_trail(conn, code)
    if not t:
        raise HTTPException(404, "Unknown ward")
    t["narrative"] = S.ward_narrative(conn, t, lang)
    rows = db.rows(conn, "SELECT * FROM finding WHERE ward_code=? AND polarity='concern' AND subject_type IN ('work_order','issue') "
                         "AND rule NOT IN ('sla_missed') ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, finding_id LIMIT 40", (code,))
    rp = Fx._replies(conn)
    t["findings"] = [schemas.PublicFinding(**Fx.serialize_finding(conn, r, lang, False, rp)).model_dump() for r in rows]
    t["clean_records"] = [schemas.PublicFinding(**Fx.serialize_finding(conn, r, lang, False, rp)).model_dump() for r in
                          db.rows(conn, "SELECT * FROM finding WHERE ward_code=? AND rule='clean_record'", (code,))]
    t.pop("payload", None)
    return t


@router.get("/wards/{code:path}/priorities")
def priorities(code: str, lang: str = Depends(lang_q), as_of: str | None = None, limit: int = Query(15, le=100),
               conn=Depends(get_conn), ref=Depends(planner_ref)):
    code = code.replace("-", "/").upper()
    plan = budget.plan_ward(conn, code, as_of=as_of, ref=ref)
    if not plan:
        raise HTTPException(404, "Unknown ward")
    items = []
    for it in plan["items"][:limit]:
        r = budget.render_item(it, lang)
        items.append({**{k: it[k] for k in ("rank", "issue_id", "category", "road_id", "road_name", "locality", "score", "factors", "weights",
                                            "under_dlp", "method", "est_cost_inr", "bmc_cost_inr", "complaint_count", "upvotes", "funded",
                                            "severity", "kind", "location_known", "lat", "lon")},
                      "category_label": T.category(it["category"], lang), "rationale": r["rationale"], "reasons": r["reasons_text"]})
    return {"ward_code": code, "ward_name": plan["ward_name"], "as_of": plan["as_of"], "budget_inr": plan["budget_inr"],
            "remaining_inr": plan["remaining_inr"], "allocatable_inr": plan["allocatable_inr"], "allocated_inr": plan["allocated_inr"],
            "allocation_cap_pct": plan["allocation_cap_pct"], "over_budget": plan["over_budget"], "candidates": plan["candidates"],
            "funded": plan["funded"], "items": items, "weights": plan["weights"], "note": plan["note"]}


@router.get("/works")
def works(ward: str | None = None, contractor: str | None = None, road: str | None = None, finding: str | None = None,
          sort: str = "recent", limit: int = Query(50, le=200), offset: int = 0, conn=Depends(get_conn)):
    where, params = ["1=1"], []
    if ward:
        where.append("w.ward_code=?"); params.append(ward.replace("-", "/").upper())
    if contractor:
        where.append("w.contractor_id=?"); params.append(contractor)
    if road:
        where.append("w.road_id=?"); params.append(road)
    if finding:
        where.append("EXISTS (SELECT 1 FROM finding f WHERE f.subject_type='work_order' AND f.subject_id=w.work_order_id AND f.rule=?)")
        params.append(finding)
    order = {"recent": "w.completed_at DESC", "cost": "w.cost_inr DESC", "oldest": "w.completed_at ASC"}.get(sort, "w.completed_at DESC")
    total = db.one(conn, f"SELECT COUNT(*) n FROM work_orders w WHERE {' AND '.join(where)}", params)["n"]
    rows = db.rows(conn, f"SELECT w.* FROM work_orders w WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?", params + [limit, offset])
    ids = [r["work_order_id"] for r in rows]
    chips = {}
    if ids:
        q = ",".join("?" * len(ids))
        for r in db.rows(conn, f"SELECT subject_id, rule, polarity FROM finding WHERE subject_type='work_order' AND subject_id IN ({q})", ids):
            chips.setdefault(r["subject_id"], []).append(r["rule"])
    return {"total": total, "items": [{**Fx.work_summary_row(r), "chips": chips.get(r["work_order_id"], [])} for r in rows]}


@router.get("/works/near")
def works_near(lat: float, lon: float, radius: float = Query(200, ge=10, le=2000), conn=Depends(get_conn)):
    return Fx.works_near(conn, lat, lon, radius)


@router.get("/works/{wo_id}")
def work(wo_id: str, lang: str = Depends(lang_q), conn=Depends(get_conn)):
    w = Fx.work_detail(conn, wo_id, lang)
    if not w:
        raise HTTPException(404, "Unknown work order")
    w["findings"] = [schemas.PublicFinding(**f).model_dump() for f in w["findings"]]
    return w


@router.get("/roads/{road_id}")
def road(road_id: str, lang: str = Depends(lang_q), conn=Depends(get_conn)):
    r = Fx.road_card(conn, road_id, lang)
    if not r:
        raise HTTPException(404, "Unknown road")
    return r


@router.get("/complaints/{cid}")
def complaint(cid: str, lang: str = Depends(lang_q), conn=Depends(get_conn)):
    t = Fx.complaint_timeline(conn, cid, lang)
    if not t:
        raise HTTPException(404, "Unknown complaint")
    t["findings"] = [schemas.PublicFinding(**f).model_dump() for f in t["findings"]]
    t["category_label"] = T.category(t["category"], lang)
    return t


@router.get("/contractors")
def contractors(conn=Depends(get_conn)):
    out = []
    for c in db.rows(conn, "SELECT * FROM contractors ORDER BY contractor_name"):    # alphabetical: no ranking
        n = db.one(conn, "SELECT COUNT(*) n, SUM(cost_inr) s FROM work_orders WHERE contractor_id=?", (c["contractor_id"],))
        clean = db.one(conn, "SELECT COUNT(*) n FROM finding WHERE contractor_id=? AND rule='clean_record'", (c["contractor_id"],))["n"]
        out.append({"contractor_id": c["contractor_id"], "name": c["contractor_name"], "empanelled_since": c["empanelled_since"],
                    "jobs": n["n"], "billed_inr": n["s"], "clean_record_wards": clean})
    return out


@router.get("/contractors/{cid}/scorecard")
def scorecard(cid: str, lang: str = Depends(lang_q), conn=Depends(get_conn)):
    card = S.contractor_scorecard(conn, cid)
    if not card:
        raise HTTPException(404, "Unknown contractor")
    card["narrative"] = S.contractor_narrative(conn, card, lang)
    card["context_note"] = card["context_note"][lang]
    card["clean_record"] = [{"ward_code": c["ward_code"], "text": c[f"public_text_{lang}"], "finding_id": c["finding_id"],
                             "metrics": json.loads(c["metrics_json"])} for c in card["clean_record"]]
    card["right_of_reply"] = {"label": {"en": "Contractor's reply", "mr": "कंत्राटदाराचे उत्तर", "hi": "ठेकेदार का उत्तर"}[lang],
                              "replies": db.rows(conn, "SELECT finding_id, reply_text, received_at FROM right_of_reply WHERE subject_type='contractor' AND subject_id=?", (cid,))}
    return card


@router.get("/findings", response_model=list[schemas.PublicFinding])
def findings(subject_type: str | None = None, subject_id: str | None = None, ward: str | None = None, rule: str | None = None,
             lang: str = Depends(lang_q), limit: int = Query(50, le=200), conn=Depends(get_conn)):
    where, params = ["1=1"], []
    for col, v in (("subject_type", subject_type), ("subject_id", subject_id), ("ward_code", ward), ("rule", rule)):
        if v:
            where.append(f"{col}=?"); params.append(v)
    rows = db.rows(conn, f"SELECT * FROM finding WHERE {' AND '.join(where)} ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
                         f"WHEN 'low' THEN 2 ELSE 3 END, finding_id LIMIT ?", params + [limit])
    rp = Fx._replies(conn)
    return [Fx.serialize_finding(conn, r, lang, False, rp) for r in rows]


@router.post("/ask")
def ask(body: schemas.AskIn, conn=Depends(get_conn)):
    if not body.question.strip():
        raise HTTPException(400, "Empty question")
    r = bot.ask(conn, body.question[:500], body.lang)
    r.pop("question", None)
    db.log(conn, "public", "ask", "bot", r.get("resolved", {}).get("id", ""), {"type": r.get("resolved", {}).get("type")})
    conn.commit()
    return r


@router.post("/rti-draft")
def rti_draft(body: schemas.RtiIn, conn=Depends(get_conn)):
    if body.work_order_id:
        kind, ident = "work", body.work_order_id
    elif body.complaint_id:
        kind, ident = "complaint", body.complaint_id
    elif body.road_id:
        kind, ident = "road", body.road_id
    else:
        raise HTTPException(400, "Provide work_order_id, complaint_id or road_id")
    d = rti.draft(conn, kind, ident.upper())
    if not d:
        raise HTTPException(404, "Nothing found for that reference")
    db.log(conn, "public", "rti_draft_generated", kind, ident.upper())     # no personal data is logged
    conn.commit()
    return d


_REDACT = {"complaints": {"complainant_id", "description", "photo_url", "photo_description"}}


@router.get("/source/{filename}/{row}")
def source_row(filename: str, row: int, conn=Depends(get_conn)):
    """Provenance chip target: the raw source row (PII columns removed) + the file's sha256."""
    table = filename.removesuffix(".csv")
    if table not in config.SOURCE_FILES and table != "complaints_sample_200":
        raise HTTPException(404, "Unknown source file")
    table = "complaints" if table == "complaints_sample_200" else table
    r = db.one(conn, f"SELECT * FROM {table} WHERE _row=?", (row,))
    if not r:
        raise HTTPException(404, "No such row")
    for k in _REDACT.get(table, ()):
        r.pop(k, None)
    for k in ("lat", "lon"):
        if table == "complaints" and r.get(k) is not None:
            r[k] = round(r[k], 3)
    return {"file": filename, "row": row, "sha256": Fx.doc_sha(conn, filename), "data": r,
            "note": "Line number in the source file (header = line 1)."}
