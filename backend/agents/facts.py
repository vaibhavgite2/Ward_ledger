"""Public fact assembly: complaint timeline, work order detail, road card (SPEC §3.1, §7).

Everything here is PII-free (no complainant_id, no free text, coordinates rounded to 3 decimals) and
only exposes neutral findings. Officer framing is added by `serialize_finding(..., officer=True)`.
"""
from __future__ import annotations

import json
from datetime import datetime

import config
import db
from pipeline.geo import load_geo
from rules import findings as F
from rules import text as T

_DOC: dict = {"_db": None, "map": {}}


def doc_sha(conn, filename: str) -> str | None:
    cur = _DOC
    if cur["_db"] != str(config.DB_PATH) or filename not in cur["map"]:
        fresh = {"_db": str(config.DB_PATH), "map": {r["filename"]: r["doc_id"] for r in db.rows(conn, "SELECT filename, doc_id FROM source_doc")}}
        globals()["_DOC"] = cur = fresh        # atomic swap
    return cur["map"].get(filename)


def with_sha(conn, ev: dict) -> dict:
    return {**ev, "sha256": doc_sha(conn, ev["file"])}


def _replies(conn, finding_ids=None, contractor_id=None):
    out = {}
    for r in db.rows(conn, "SELECT finding_id, reply_text, received_at FROM right_of_reply WHERE finding_id IS NOT NULL"):
        out[r["finding_id"]] = {"text": r["reply_text"], "received_at": r["received_at"]}
    return out


def serialize_finding(conn, row: dict, lang: str = "en", officer: bool = False, replies: dict | None = None) -> dict:
    lang = lang if lang in T.LANGS else "en"
    replies = replies if replies is not None else _replies(conn)
    out = {
        "finding_id": row["finding_id"], "rule": row["rule"], "title": T.RULE_TITLES[row["rule"]][lang],
        "polarity": row["polarity"], "severity": row["severity"],
        "subject": {"type": row["subject_type"], "id": row["subject_id"]},
        "ward_code": row["ward_code"], "contractor_id": row["contractor_id"],
        "text": row[f"public_text_{lang}"], "metrics": json.loads(row["metrics_json"]),
        "context": json.loads(row["context_json"]),
        "evidence": [with_sha(conn, e) for e in json.loads(row["evidence_json"])],
        "reply": replies.get(row["finding_id"]), "reply_label": None,
        "actions": ["rti"] if row["polarity"] == "concern" else [],
        "rule_version": row["rule_version"],
    }
    if officer:
        out["flag_label"] = T.OFFICER_LABEL[row["rule"]]
    return out


def findings_for(conn, subject_type: str, subject_id: str, lang="en", officer=False) -> list[dict]:
    rows = db.rows(conn, "SELECT * FROM finding WHERE subject_type=? AND subject_id=? ORDER BY "
                         "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END, rule",
                   (subject_type, subject_id))
    rp = _replies(conn)
    return [serialize_finding(conn, r, lang, officer, rp) for r in rows]


def _round3(x):
    return None if x is None else round(float(x), 3)


def _yes(b, lang):
    return {"en": ("Yes", "No"), "mr": ("होय", "नाही"), "hi": ("हाँ", "नहीं")}[lang][0 if b else 1]


# --------------------------------------------------------------------------------------------
def work_summary_row(w: dict) -> dict:
    return {"work_order_id": w["work_order_id"], "ward_code": w["ward_code"], "road_id": w["road_id"], "work_type": w["work_type"],
            "repair_method": w["repair_method"], "contractor_id": w["contractor_id"], "contractor_name": w["contractor_name"],
            "assigned_at": w["assigned_at"], "completed_at": w["completed_at"], "area_sqm": w["area_sqm"], "cost_inr": w["cost_inr"],
            "sla_hours": w["sla_hours"], "sla_met": w["sla_met"] == "Y", "reopened_within_30d": w["reopened_within_30d"] == "Y"}


def work_detail(conn, wo_id: str, lang="en", officer=False) -> dict | None:
    w = db.one(conn, "SELECT * FROM work_orders WHERE work_order_id=?", (wo_id,))
    if not w:
        return None
    road = db.one(conn, "SELECT * FROM roads WHERE road_id=?", (w["road_id"],))
    rate = db.one(conn, "SELECT * FROM rate_card WHERE repair_method=?", (w["repair_method"],))
    cids = F.wo_complaint_ids(w)
    comps = []
    if cids:
        q = ",".join("?" * len(cids))
        comps = db.rows(conn, f"SELECT complaint_id, received_at, channel, status FROM complaints WHERE complaint_id IN ({q}) ORDER BY received_at", cids)
    expected = F.expected_cost(rate, w["area_sqm"]) if rate else None
    return {
        **work_summary_row(w),
        "expected_cost_inr": round(expected) if expected else None,
        "cost_vs_rate_pct": round((w["cost_inr"] / expected - 1) * 100) if expected else None,
        "rate_card": {"unit": rate["unit"], "standard_rate_inr": rate["standard_rate_inr"]} if rate else None,
        "work_started_at": w["work_started_at"], "engineer_remark": w["engineer_remark"],
        "road": {"road_id": road["road_id"], "road_name": road["road_name"], "segment_no": road["segment_no"],
                 "road_type": road["road_type"], "surface": road["surface"], "under_dlp": road["under_dlp"] == "Y",
                 "last_resurfaced": road["last_resurfaced"]} if road else None,
        "linked_complaints": comps,
        "findings": findings_for(conn, "work_order", wo_id, lang, officer),
        "provenance": [with_sha(conn, {"table": "work_orders", "id": wo_id, "row": w["_row"], "file": "work_orders.csv"})],
    }


def complaint_timeline(conn, cid: str, lang="en") -> dict | None:
    c = db.one(conn, "SELECT * FROM complaints WHERE complaint_id=?", (cid,))
    p = db.one(conn, "SELECT * FROM parsed_complaint WHERE complaint_id=?", (cid,))
    if not c or not p:
        return None
    wo = work_detail(conn, p["work_order_id"], lang) if p["work_order_id"] else None
    # a complaint is "directly linked" only if the work order lists it; otherwise it's linked via a duplicate issue
    direct = bool(wo and cid in [x["complaint_id"] for x in wo["linked_complaints"]])
    issue = db.one(conn, "SELECT * FROM issue WHERE issue_id=?", (p["issue_id"],))
    asof = datetime.fromisoformat(config.AS_OF)
    events = [{"kind": "received", "at": c["received_at"], "channel": c["channel"]}]
    if wo:
        events += [{"kind": "assigned", "at": wo["assigned_at"], "contractor_id": wo["contractor_id"],
                    "contractor_name": wo["contractor_name"]},
                   {"kind": "started", "at": wo["work_started_at"]},
                   {"kind": "completed", "at": wo["completed_at"]}]
    events.sort(key=lambda e: e["at"] or "")          # always chronological, whatever the data order
    filed_after = bool(wo and wo["completed_at"] and c["received_at"] > wo["completed_at"])
    findings = []
    if wo:
        findings = wo["findings"]
    elif issue and issue["status"] == "never_fixed":
        findings = findings_for(conn, "issue", issue["issue_id"], lang)
    rti = p["link_status"] in ("never_fixed", "fixed_failed") or any(
        f["polarity"] == "concern" and f["rule"] in ("dlp_breach", "rate_card_overrun", "possible_double_billing") for f in findings)
    unverified = p["category_status"] != "verified"
    return {
        "complaint_id": cid, "received_at": c["received_at"], "channel": c["channel"], "status": c["status"],
        "category_reported": c["category_reported"], "category": p["category"], "category_verified": not unverified,
        "category_changed": bool(p["category_changed"]), "language": c["language"],
        "location": {"locality": p["locality"], "ward_code": p["ward_code"], "lat": _round3(p["lat"]), "lon": _round3(p["lon"]),
                     "uncertainty_m": p["uncertainty_m"], "method": p["geocode_method"], "road_id": p["road_id"]},
        "upvotes": c["upvotes"], "link_status": p["link_status"], "directly_linked": direct,
        "issue": {"issue_id": issue["issue_id"], "reported_times": issue["complaint_count"], "status": issue["status"]} if issue else None,
        "work": ({k: wo[k] for k in ("work_order_id", "contractor_id", "contractor_name", "repair_method", "cost_inr", "expected_cost_inr",
                                     "cost_vs_rate_pct", "assigned_at", "completed_at", "sla_hours", "sla_met", "reopened_within_30d", "road", "provenance")}
                 if wo else None),
        "days_open": max(0, (asof - datetime.strptime(c["received_at"], F.FMT)).days) if not wo else None,
        "events": events, "filed_after_completion": filed_after, "findings": findings, "rti_suggested": rti,
        "provenance": [with_sha(conn, {"table": "complaints", "id": cid, "row": c["_row"], "file": "complaints.csv"})],
    }


def road_card(conn, road_id: str, lang="en") -> dict | None:
    r = db.one(conn, "SELECT * FROM roads WHERE road_id=?", (road_id,))
    if not r:
        return None
    tr = db.one(conn, "SELECT * FROM traffic WHERE road_id=?", (road_id,))
    wos = db.rows(conn, "SELECT * FROM work_orders WHERE road_id=? ORDER BY completed_at", (road_id,))
    open_issues = db.rows(conn, "SELECT issue_id, category, status, complaint_count, first_reported FROM issue "
                                "WHERE road_id=? AND status IN ('never_fixed','pending','fixed_failed')", (road_id,))
    fnd = db.rows(conn, "SELECT rule, COUNT(*) n FROM finding WHERE subject_type='work_order' AND polarity='concern' AND subject_id IN "
                        "(SELECT work_order_id FROM work_orders WHERE road_id=?) GROUP BY rule", (road_id,))
    return {
        "road_id": road_id, "road_name": r["road_name"], "segment_no": r["segment_no"], "ward_code": r["ward_code"],
        "road_type": r["road_type"], "surface": r["surface"], "length_m": r["length_m"], "bus_route": r["bus_route"] == "Y",
        "last_resurfaced": r["last_resurfaced"], "under_dlp": r["under_dlp"] == "Y",
        "geometry": {"start": [r["start_lat"], r["start_lon"]], "end": [r["end_lat"], r["end_lon"]]},
        "congestion_index": tr["congestion_index_0_10"] if tr else None,
        "repairs": len(wos), "spent_inr": int(sum(w["cost_inr"] for w in wos)),
        "failed_repairs": sum(1 for w in wos if w["reopened_within_30d"] == "Y"),
        "failed_inr": int(sum(w["cost_inr"] for w in wos if w["reopened_within_30d"] == "Y")),
        "works": [work_summary_row(w) for w in wos],
        "open_issues": open_issues, "finding_counts": {x["rule"]: x["n"] for x in fnd},
        "provenance": [with_sha(conn, {"table": "roads", "id": road_id, "row": r["_row"], "file": "roads.csv"})],
    }


def works_near(conn, lat: float, lon: float, radius_m: float = 200, limit_roads: int = 8) -> dict:
    geo = load_geo()
    near = geo.roads_within(lat, lon, max(radius_m, 1))[:limit_roads]
    ward = geo.ward_at(lat, lon)
    roads = []
    for rid, d in near:
        card = road_card(conn, rid)
        if card:
            roads.append({"distance_m": round(d), **{k: card[k] for k in ("road_id", "road_name", "segment_no", "under_dlp", "repairs",
                          "spent_inr", "failed_repairs", "failed_inr", "last_resurfaced", "finding_counts")},
                          "open_issues": len(card["open_issues"])})
    return {"query": {"lat": round(lat, 4), "lon": round(lon, 4), "radius_m": radius_m}, "ward_code": ward, "roads": roads,
            "note": "Please confirm which road is yours. Locations are approximate (map data is synthetic)."}
