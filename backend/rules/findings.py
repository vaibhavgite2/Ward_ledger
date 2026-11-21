"""Rule engine: deterministic findings with evidence (SPEC §6.4). No LLM is involved here.

Each finding has: metrics, evidence rows (table/id/row/file), the context adjustments applied,
and neutral template-rendered public text in en/mr/hi.
"""
from __future__ import annotations

import hashlib
import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import config
import db
from rules import text as T

CFG = config.RULES
VERSION = CFG["version"]
FMT = "%Y-%m-%d %H:%M"
SURFACE_TYPES = {"Pothole", "Road cave-in", "Broken paver blocks"}


def _dt(s):
    return datetime.strptime(s, FMT) if s else None


def fid(rule, subject_type, subject_id) -> str:
    return "fd_" + hashlib.sha1(f"{rule}|{subject_type}|{subject_id}".encode()).hexdigest()[:16]


def expected_cost(rate_row: dict, area: float) -> float:
    return rate_row["standard_rate_inr"] * area if rate_row["unit"] == "per sqm" else rate_row["standard_rate_inr"]


class Context:
    """Lookups shared by rules: wards, rain, rate card, complaint links."""

    def __init__(self, conn):
        self.conn = conn
        self.wards = {r["ward_code"]: r for r in db.rows(conn, "SELECT * FROM wards")}
        self.roads = {r["road_id"]: r for r in db.rows(conn, "SELECT * FROM roads")}
        self.rate = {r["repair_method"]: r for r in db.rows(conn, "SELECT * FROM rate_card")}
        self.contractors = {r["contractor_id"]: r for r in db.rows(conn, "SELECT * FROM contractors")}
        self.complaints = {r["complaint_id"]: r for r in db.rows(conn, "SELECT * FROM complaints")}
        self.rain: dict[tuple[str, str], str] = {}
        for r in db.rows(conn, "SELECT date, station, imd_category FROM rainfall_daily"):
            self.rain[(r["station"], r["date"])] = r["imd_category"]
        self.heavy = set(CFG["context"]["heavy_rain_categories"])
        self.island = set(CFG["context"]["island_city_wards"])

    def station(self, ward: str) -> str:
        return "Colaba" if ward in self.island else "Santacruz"

    def low_lying(self, ward: str) -> bool:
        w = self.wards.get(ward)
        return bool(w and w["low_lying_index"] is not None and w["low_lying_index"] >= CFG["context"]["low_lying_index"])

    def heavy_days(self, ward: str, start: datetime, end: datetime) -> int:
        stn = self.station(ward)
        n, d = 0, start.date()
        while d <= end.date():
            if self.rain.get((stn, d.isoformat())) in self.heavy:
                n += 1
            d += timedelta(days=1)
        return n

    def heavy_week_before(self, ward, dt) -> bool:
        return self.heavy_days(ward, dt - timedelta(days=7), dt) >= CFG["context"]["heavy_rain_days_in_week"]

    def heavy_week_after(self, ward, dt) -> bool:
        return self.heavy_days(ward, dt, dt + timedelta(days=7)) >= CFG["failed_within_30d"]["heavy_rain_week_days"]


def wo_complaint_ids(wo: dict) -> list[str]:
    v = wo.get("linked_complaint_ids")
    return [x for x in v.split("|") if x] if isinstance(v, str) and v else []


def _ev(table, id_, row, file):
    return {"table": table, "id": id_, "row": row, "file": file}


def _mk(rule, subject_type, subject_id, *, ward=None, contractor=None, polarity="concern", severity,
        metrics, evidence, context, text_kw) -> dict:
    texts = T.render_all(rule, **text_kw)
    return {
        "finding_id": fid(rule, subject_type, subject_id), "rule": rule, "rule_version": VERSION,
        "subject_type": subject_type, "subject_id": subject_id, "ward_code": ward, "contractor_id": contractor,
        "polarity": polarity, "severity": severity, "metrics_json": json.dumps(metrics, ensure_ascii=False),
        "evidence_json": json.dumps(evidence, ensure_ascii=False), "context_json": json.dumps(context),
        "public_text_en": texts["en"], "public_text_mr": texts["mr"], "public_text_hi": texts["hi"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def compute(conn) -> list[dict]:
    ctx = Context(conn)
    wos = db.rows(conn, "SELECT * FROM work_orders ORDER BY work_order_id")
    out: list[dict] = []

    # Per-WO pre-computation
    for w in wos:
        w["_assigned"] = _dt(w["assigned_at"])
        w["_completed"] = _dt(w["completed_at"])
        cids = [c for c in wo_complaint_ids(w) if c in ctx.complaints]
        w["_cids"] = cids
        firsts = [_dt(ctx.complaints[c]["received_at"]) for c in cids]
        w["_first_complaint"] = min(firsts) if firsts else None
        rr = ctx.rate.get(w["repair_method"])
        w["_expected"] = expected_cost(rr, w["area_sqm"]) if rr else None
        w["_ratio"] = w["cost_inr"] / w["_expected"] if w["_expected"] else None
        w["_low_lying"] = ctx.low_lying(w["ward_code"])
        w["_heavy_before"] = ctx.heavy_week_before(w["ward_code"], w["_assigned"]) if w["_assigned"] else False
        w["_heavy_after"] = ctx.heavy_week_after(w["ward_code"], w["_completed"]) if w["_completed"] else False

    def wo_ev(w):
        return _ev("work_orders", w["work_order_id"], w["_row"], "work_orders.csv")

    # ---- rate_card_overrun --------------------------------------------------------------
    R = CFG["rate_card_overrun"]
    for w in wos:
        if w["_ratio"] is None:
            continue
        relaxed = w["_low_lying"] and w["_heavy_before"]
        thr = R["ratio_relaxed"] if relaxed else R["ratio"]
        if w["_ratio"] > thr:
            rr = ctx.rate[w["repair_method"]]
            out.append(_mk(
                "rate_card_overrun", "work_order", w["work_order_id"], ward=w["ward_code"], contractor=w["contractor_id"],
                severity="high" if w["_ratio"] > R["high_ratio"] else "medium",
                metrics={"cost_inr": w["cost_inr"], "expected_inr": round(w["_expected"]), "ratio": round(w["_ratio"], 2),
                         "pct_above": round((w["_ratio"] - 1) * 100), "method": w["repair_method"],
                         "unit": rr["unit"], "rate_inr": rr["standard_rate_inr"], "area_sqm": w["area_sqm"],
                         "threshold": thr},
                evidence=[wo_ev(w), _ev("rate_card", w["repair_method"], rr["_row"], "rate_card.csv")],
                context={"low_lying_ward": w["_low_lying"], "heavy_rain_week": w["_heavy_before"], "threshold_relaxed": relaxed},
                text_kw=dict(cost=T.inr(w["cost_inr"]), expected=T.inr(w["_expected"]),
                             pct=round((w["_ratio"] - 1) * 100), method=w["repair_method"])))

    # ---- possible_double_billing ---------------------------------------------------------
    D = CFG["possible_double_billing"]
    groups = defaultdict(list)
    for w in wos:
        groups[(w["road_id"], w["work_type"])].append(w)
    for (road, wtype), g in groups.items():
        g.sort(key=lambda x: x["_assigned"])
        for a, b in zip(g, g[1:]):
            if b["_cids"]:
                continue
            gap = (b["_assigned"] - a["_completed"]).total_seconds() / 86400
            if gap <= D["window_days"]:
                out.append(_mk(
                    "possible_double_billing", "work_order", b["work_order_id"], ward=b["ward_code"], contractor=b["contractor_id"],
                    severity="high",
                    metrics={"road_id": road, "work_type": wtype, "first_wo": a["work_order_id"], "gap_days": round(gap, 1),
                             "first_cost_inr": a["cost_inr"], "second_cost_inr": b["cost_inr"],
                             "first_contractor": a["contractor_id"], "second_contractor": b["contractor_id"]},
                    evidence=[wo_ev(a), wo_ev(b)],
                    context={"second_has_linked_complaint": False},
                    text_kw=dict(days=max(0, round(gap)))))

    # ---- dlp_breach -----------------------------------------------------------------------
    for w in wos:
        rd = ctx.roads.get(w["road_id"])
        if rd and rd["under_dlp"] == "Y":
            surface = w["work_type"] in SURFACE_TYPES
            out.append(_mk(
                "dlp_breach", "work_order", w["work_order_id"], ward=w["ward_code"], contractor=w["contractor_id"],
                severity="medium" if surface else "low",
                metrics={"road_id": w["road_id"], "cost_inr": w["cost_inr"], "work_type": w["work_type"],
                         "last_resurfaced": rd["last_resurfaced"], "surface_repair": surface},
                evidence=[wo_ev(w), _ev("roads", w["road_id"], rd["_row"], "roads.csv")],
                context={"surface_repair": surface},
                text_kw=dict(cost=T.inr(w["cost_inr"]))))

    # ---- sla_missed -----------------------------------------------------------------------
    S = CFG["sla"]
    for w in wos:
        if w["sla_met"] != "N":
            continue
        start = w["_first_complaint"] or w["_assigned"]
        hours = (w["_completed"] - start).total_seconds() / 3600
        ev = [wo_ev(w)]
        if w["_cids"]:
            c0 = min(w["_cids"], key=lambda c: ctx.complaints[c]["received_at"])
            ev.append(_ev("complaints", c0, ctx.complaints[c0]["_row"], "complaints.csv"))
        out.append(_mk(
            "sla_missed", "work_order", w["work_order_id"], ward=w["ward_code"], contractor=w["contractor_id"],
            severity="medium" if hours >= S["medium_multiple"] * w["sla_hours"] else "low",
            metrics={"hours": round(hours), "sla_hours": w["sla_hours"], "measured_from": "first_complaint" if w["_cids"] else "assignment"},
            evidence=ev, context={}, text_kw=dict(hours=round(hours), sla=w["sla_hours"])))

    # ---- failed_within_30d ------------------------------------------------------------------
    for w in wos:
        if w["reopened_within_30d"] != "Y":
            continue
        out.append(_mk(
            "failed_within_30d", "work_order", w["work_order_id"], ward=w["ward_code"], contractor=w["contractor_id"],
            severity="low" if w["_heavy_after"] else "medium",
            metrics={"cost_inr": w["cost_inr"], "repair_method": w["repair_method"], "completed_at": w["completed_at"]},
            evidence=[wo_ev(w)],
            context={"low_lying_ward": w["_low_lying"], "heavy_rain_week_after": w["_heavy_after"]},
            text_kw={}))

    # ---- estimate_drift -----------------------------------------------------------------------
    E = CFG["estimate_drift"]

    def unit_cost(w):
        rr = ctx.rate.get(w["repair_method"])
        if not rr:
            return None
        if rr["unit"] == "per sqm":
            return w["cost_inr"] / w["area_sqm"] if w["area_sqm"] else None
        return float(w["cost_inr"])

    by_ward_method = defaultdict(list)
    by_method = defaultdict(list)
    for w in wos:
        u = unit_cost(w)
        if u is not None:
            by_ward_method[(w["ward_code"], w["repair_method"])].append(u)
            by_method[w["repair_method"]].append(u)
    for w in wos:
        u = unit_cost(w)
        if u is None:
            continue
        grp = by_ward_method[(w["ward_code"], w["repair_method"])]
        basis = "ward"
        if len(grp) < E["min_group"]:
            grp, basis = by_method[w["repair_method"]], "city"
        med = st.median(grp)
        relaxed = w["_low_lying"] or w["_heavy_before"]
        thr = E["ratio_relaxed"] if relaxed else E["ratio"]
        if u > med * thr:
            per = "sqm" if ctx.rate[w["repair_method"]]["unit"] == "per sqm" else "job"
            out.append(_mk(
                "estimate_drift", "work_order", w["work_order_id"], ward=w["ward_code"], contractor=w["contractor_id"],
                severity="medium",
                metrics={"unit_cost_inr": round(u), "median_inr": round(med), "ratio_to_median": round(u / med, 2),
                         "per": per, "comparison": basis, "group_size": len(grp), "threshold": thr,
                         "method": w["repair_method"]},
                evidence=[wo_ev(w)],
                context={"low_lying_ward": w["_low_lying"], "heavy_rain_week": w["_heavy_before"], "threshold_relaxed": relaxed},
                text_kw=dict(unit=T.inr(u), median=T.inr(med), method=w["repair_method"], per=T.PER[per][0],
                             per_mr=T.PER[per][1], per_hi=T.PER[per][2])))

    # ---- never_fixed (per issue) ------------------------------------------------------------------
    for iss in db.rows(conn, "SELECT * FROM issue WHERE status='never_fixed'"):
        asof = datetime.fromisoformat(config.AS_OF)
        first = datetime.fromisoformat(iss["first_reported"].replace(" ", "T"))
        days = max(0, (asof - first).days)
        cids = db.rows(conn, "SELECT complaint_id FROM parsed_complaint WHERE issue_id=? ORDER BY complaint_id", (iss["issue_id"],))
        ev = [_ev("complaints", c["complaint_id"], ctx.complaints[c["complaint_id"]]["_row"], "complaints.csv")
              for c in cids[:5] if c["complaint_id"] in ctx.complaints]
        out.append(_mk(
            "never_fixed", "issue", iss["issue_id"], ward=iss["ward_code"], severity="medium",
            metrics={"days_open": days, "complaint_count": iss["complaint_count"], "upvotes": iss["upvotes"],
                     "category": iss["category"], "first_reported": iss["first_reported"]},
            evidence=ev, context={}, text_kw=dict(days=days)))

    out.extend(_clean_records(wos, out, ctx))
    return out


def _clean_records(wos, findings, ctx) -> list[dict]:
    """Positive finding per (contractor, ward) with no cost/repeat-billing findings, on-time and durable."""
    C = CFG["clean_record"]
    bad = defaultdict(set)
    for f in findings:
        if f["rule"] in ("rate_card_overrun", "possible_double_billing", "estimate_drift") and f["subject_type"] == "work_order":
            bad[f["subject_id"]].add(f["rule"])
    city_reopen = defaultdict(list)
    for w in wos:
        city_reopen[w["repair_method"]].append(1 if w["reopened_within_30d"] == "Y" else 0)
    city_rate = {m: sum(v) / len(v) for m, v in city_reopen.items()}
    groups = defaultdict(list)
    for w in wos:
        groups[(w["contractor_id"], w["ward_code"])].append(w)
    out = []
    for (ct, ward), g in sorted(groups.items()):
        if len(g) < C["min_completed"]:
            continue
        if any(w["work_order_id"] in bad for w in g):
            continue
        sla = sum(w["sla_met"] == "Y" for w in g) / len(g)
        reopen = sum(w["reopened_within_30d"] == "Y" for w in g) / len(g)
        expected_reopen = sum(city_rate[w["repair_method"]] for w in g) / len(g)
        if sla < C["min_sla_rate"] or reopen > expected_reopen:
            continue
        out.append(_mk(
            "clean_record", "contractor_ward", f"{ct}@{ward}", ward=ward, contractor=ct, polarity="positive", severity="info",
            metrics={"completed": len(g), "sla_rate": round(sla, 2), "reopen_rate": round(reopen, 2),
                     "expected_reopen_rate": round(expected_reopen, 2),
                     "median_cost_ratio": round(st.median(w["_ratio"] for w in g if w["_ratio"]), 2)},
            evidence=[_ev("work_orders", w["work_order_id"], w["_row"], "work_orders.csv") for w in g],
            context={}, text_kw=dict(ward=ward, n=len(g))))
    return out


def store(conn, findings: list[dict]) -> None:
    conn.execute("DELETE FROM finding")
    cols = ["finding_id", "rule", "rule_version", "subject_type", "subject_id", "ward_code", "contractor_id",
            "polarity", "severity", "metrics_json", "evidence_json", "context_json", "public_text_en",
            "public_text_mr", "public_text_hi", "created_at"]
    conn.executemany(f"INSERT OR REPLACE INTO finding({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [[f[c] for c in cols] for f in findings])
    conn.commit()
