"""Budget Planner: "where should the next rupee go" (SPEC §6.6).

Transparent weighted score (no black box): every factor is 0-1, shown to the user with its weight.
Advisory only; stored as `budget_recommendation`, never as a fact.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import config
import db
from agents import metrics
from pipeline.geo import dist_m
from rules import text as T

B = config.RULES["budget"]
W = B["weights"]
ACCIDENT_CAUSES = {"Pothole", "Waterlogged road", "Uneven road / open chamber"}
ACC_SEV = {"Minor": 1, "Grievous": 3, "Fatal": 5}
FAC_SCORE = lambda f: (1.0 if f["type"] == "Hospital" and f["emergency_services"] == "Y" else 0.85 if f["type"] == "Hospital" else 0.7)

REASON_T = {
    "severity": {"en": "{category} (severity {s} of 5)", "mr": "{category} (तीव्रता {s}/5)", "hi": "{category} (गंभीरता {s}/5)"},
    "facility": {"en": "a {kind} is within {m} m", "mr": "{kind} {m} मीटरच्या आत आहे", "hi": "{kind} {m} मीटर के भीतर है"},
    "ambulance": {"en": "this is the ambulance entry road for a {kind}", "mr": "हा {kind} चा रुग्णवाहिका प्रवेश रस्ता आहे", "hi": "यह {kind} का एम्बुलेंस प्रवेश मार्ग है"},
    "flood": {"en": "chronic flood spot nearby (flagged {y} of the last 5 years)", "mr": "जवळ नेहमी पाणी साचणारे ठिकाण (गेल्या 5 वर्षांपैकी {y} वर्षे नोंद)", "hi": "पास में बार-बार जलभराव का स्थान (पिछले 5 में से {y} वर्ष दर्ज)"},
    "accidents": {"en": "{n} road accidents on this road were linked to potholes or water", "mr": "या रस्त्यावर खड्डे/पाण्यामुळे {n} अपघातांची नोंद", "hi": "इस सड़क पर गड्ढों/पानी से जुड़ी {n} दुर्घटनाएँ दर्ज"},
    "reports": {"en": "{n} complaint(s) with {u} upvotes", "mr": "{n} तक्रारी आणि {u} अपव्होट", "hi": "{n} शिकायतें और {u} अपवोट"},
    "congestion": {"en": "heavy traffic (congestion {c} of 10)", "mr": "जास्त वाहतूक (गर्दी {c}/10)", "hi": "भारी यातायात (भीड़ {c}/10)"},
    "age": {"en": "last repaired {d} days ago", "mr": "शेवटची दुरुस्ती {d} दिवसांपूर्वी", "hi": "आख़िरी मरम्मत {d} दिन पहले"},
    "failed_before": {"en": "an earlier repair did not hold", "mr": "आधीची दुरुस्ती टिकली नाही", "hi": "पिछली मरम्मत टिकी नहीं"},
    "never_fixed": {"en": "no repair linked {d} days after the first complaint", "mr": "पहिल्या तक्रारीनंतर {d} दिवसांनीही दुरुस्ती जोडलेली नाही", "hi": "पहली शिकायत के {d} दिन बाद भी कोई मरम्मत नहीं जुड़ी"},
    "rain": {"en": "heavy recent rain", "mr": "अलीकडे जास्त पाऊस", "hi": "हाल की भारी बारिश"},
}
KIND = {"Hospital": {"en": "hospital", "mr": "रुग्णालय", "hi": "अस्पताल"}, "School": {"en": "school", "mr": "शाळा", "hi": "स्कूल"}}
RATIONALE_T = {
    "en": "{category} at {where}: {reasons}. Suggested method: {method} (about ₹{cost}).",
    "mr": "{where} येथे {category}: {reasons}. सुचवलेली पद्धत: {method} (सुमारे ₹{cost}).",
    "hi": "{where} पर {category}: {reasons}। सुझाई गई पद्धति: {method} (लगभग ₹{cost})।",
}
DLP_ACTION = {
    "en": "Ask the warranty contractor to repair at no cost to BMC.",
    "mr": "वॉरंटी कंत्राटदाराला BMC ला कोणताही खर्च न लावता दुरुस्ती करण्यास सांगा.",
    "hi": "वारंटी वाले ठेकेदार से BMC को बिना लागत मरम्मत कराने को कहें।",
}


class Ref:
    """Reference tables loaded once per planning run."""

    def __init__(self, conn):
        self.wards = {r["ward_code"]: r for r in db.rows(conn, "SELECT * FROM wards")}
        self.roads = {r["road_id"]: r for r in db.rows(conn, "SELECT * FROM roads")}
        self.traffic = {r["road_id"]: r for r in db.rows(conn, "SELECT * FROM traffic")}
        self.rate = {r["repair_method"]: r for r in db.rows(conn, "SELECT * FROM rate_card")}
        self.hotspots = db.rows(conn, "SELECT * FROM flood_hotspots")
        self.facilities = db.rows(conn, "SELECT * FROM facilities")
        self.rain = defaultdict(float)
        for r in db.rows(conn, "SELECT date, station, rainfall_mm FROM rainfall_daily"):
            self.rain[(r["station"], r["date"])] = r["rainfall_mm"] or 0.0
        self.big_tides = {r["date"] for r in db.rows(conn, "SELECT date FROM tides WHERE big_tide_flag='Y'")}
        self.acc = defaultdict(float)
        self.acc_n = defaultdict(int)
        for r in db.rows(conn, "SELECT road_id, severity, probable_cause FROM accidents"):
            if r["probable_cause"] in ACCIDENT_CAUSES:
                self.acc[r["road_id"]] += ACC_SEV.get(r["severity"], 1)
                self.acc_n[r["road_id"]] += 1
        ward_max = defaultdict(float)
        for rid, v in self.acc.items():
            wc = self.roads.get(rid, {}).get("ward_code")
            ward_max[wc] = max(ward_max[wc], v)
        self.acc_ward_max = ward_max
        df = metrics.wo_frame(conn)
        self.wo = df
        self.method_reopen = metrics.method_reopen_table(df)
        self.island = set(config.RULES["context"]["island_city_wards"])
        self.median_area = {}
        for (w, t), g in df.groupby(["ward_code", "work_type"]):
            if len(g) >= 3:
                self.median_area[(w, t)] = float(g["area_sqm"].median())
        for t, g in df.groupby("work_type"):
            self.median_area[("*", t)] = float(g["area_sqm"].median())

    def road_mid(self, rid):
        r = self.roads.get(rid)
        return ((r["start_lat"] + r["end_lat"]) / 2, (r["start_lon"] + r["end_lon"]) / 2) if r else None


def _rain_7d(ref: Ref, ward: str, as_of: datetime) -> float:
    stn = "Colaba" if ward in ref.island else "Santacruz"
    return sum(ref.rain.get((stn, (as_of - timedelta(days=k)).date().isoformat()), 0.0) for k in range(7))


def _method_for(ref: Ref, category: str, ward: str, high_traffic: bool, rain_risk: float):
    cands = config.RULES["methods_by_category"].get(category) or []
    if not cands:
        return None, []
    low = float(ref.wards[ward]["low_lying_index"] or 0) >= config.RULES["context"]["low_lying_index"]
    opts = []
    for m in cands:
        if m == "Cold mix patch" and (high_traffic or rain_risk >= 0.6):
            continue
        t = ref.method_reopen.get(m)
        rr = (t["low_lying"] if low and t and t["low_lying"] is not None else t["all"]) if t else 1.0
        opts.append({"method": m, "reopen_pct": round(rr * 100), "unit_rate_inr": ref.rate[m]["standard_rate_inr"],
                     "unit": ref.rate[m]["unit"]})
    if not opts:
        opts = [{"method": cands[-1], "reopen_pct": 0, "unit_rate_inr": ref.rate[cands[-1]]["standard_rate_inr"],
                 "unit": ref.rate[cands[-1]]["unit"]}]
    opts.sort(key=lambda o: (o["reopen_pct"], o["unit_rate_inr"]))
    return opts[0], opts


def plan_ward(conn, ward: str, as_of: str | None = None, ref: Ref | None = None, lang_pref: str = "en") -> dict | None:
    ref = ref or Ref(conn)
    if ward not in ref.wards:
        return None
    as_of_s = as_of or config.AS_OF
    asof = datetime.fromisoformat(as_of_s)
    asof_end = asof + timedelta(hours=23, minutes=59)
    w = ref.wards[ward]
    wo = ref.wo
    done = wo[(wo["ward_code"] == ward) & (wo["completed"] <= asof_end)]
    spend = float(done["cost_inr"].sum())
    budget = float(w["monsoon_repair_budget_inr_2025"])
    remaining = budget - spend
    cap_amt = max(0.0, remaining) * B["allocation_cap"]
    wo_by_id = wo.set_index("work_order_id")

    # Candidate issues open as of `as_of`
    issues = db.rows(conn, "SELECT * FROM issue WHERE ward_code=?", (ward,))
    cands = []
    for i in issues:
        if i["first_reported"] > asof_end.strftime("%Y-%m-%d %H:%M"):
            continue
        if i["work_order_id"]:
            row = wo_by_id.loc[i["work_order_id"]]
            if row["completed"] > asof_end:
                kind = "open"                       # repair not yet complete at that date
            elif row["failed"]:
                kind = "failed_before"
            else:
                continue
        elif i["status"] in ("never_fixed", "pending"):
            kind = "never_fixed"
        else:
            continue
        cands.append((i, kind))

    locality = {r["issue_id"]: r["locality"] for r in db.rows(
        conn, "SELECT issue_id, MIN(locality) locality FROM parsed_complaint WHERE ward_code=? GROUP BY issue_id", (ward,))}
    rain_mm = _rain_7d(ref, ward, asof)
    items = []
    for i, kind in cands:
        rid = i["road_id"]
        road = ref.roads.get(rid) if rid else None
        pt = ref.road_mid(rid) if rid else ((i["lat"], i["lon"]) if i["lat"] is not None else None)
        # S: severity
        S = i["severity"] / 5
        # F: flood hotspot
        F_v, flood_y, tide_sens = 0.0, None, False
        if pt:
            near = [(h, dist_m(pt[0], pt[1], h["lat"], h["lon"])) for h in ref.hotspots]
            near = [h for h, d in near if d <= B["hotspot_radius_m"]]
            if near:
                h = max(near, key=lambda h: h["years_flagged_last_5"])
                F_v, flood_y, tide_sens = h["years_flagged_last_5"] / 5, h["years_flagged_last_5"], h["tide_sensitive"] == "Y"
        # R: rainfall risk
        R_v = min(1.0, rain_mm / B["rain_norm_mm"])
        if tide_sens and any((asof + timedelta(days=k)).date().isoformat() in ref.big_tides for k in range(8)):
            R_v = min(1.0, R_v * 1.2)
        # A: accident severity
        A_v, acc_n = 0.0, 0
        if rid and ref.acc.get(rid):
            A_v = ref.acc[rid] / ref.acc_ward_max[ward] if ref.acc_ward_max.get(ward) else 0.0
            acc_n = ref.acc_n[rid]
        # P: hospital / school
        P_v, fac_kind, fac_m = 0.0, None, None
        for f in ref.facilities:
            d = dist_m(pt[0], pt[1], f["lat"], f["lon"]) if pt else 1e9
            if d <= B["facility_radius_m"] or (rid and f["ambulance_entry_road"] == rid):
                s = FAC_SCORE(f)
                if s > P_v:
                    P_v, fac_kind, fac_m = s, f["type"], int(min(d, B["facility_radius_m"])) if d <= B["facility_radius_m"] else None
        # C: congestion
        C_v, cong = 0.0, None
        tr = ref.traffic.get(rid) if rid else None
        if tr:
            cong = tr["congestion_index_0_10"]
            C_v = min(1.0, cong / 10 + (0.1 if road and road["bus_route"] == "Y" else 0))
        # D: days since last repair
        D_v, days = 0.0, None
        if rid:
            last = wo[(wo["road_id"] == rid) & (wo["completed"] <= asof_end)]["completed"]
            ref_date = last.max() if len(last) else datetime.fromisoformat(road["last_resurfaced"]) if road else None
            if ref_date is not None:
                days = max(0, (asof - ref_date).days)
                D_v = min(1.0, days / 365)
        factors = {"S": S, "F": F_v, "R": R_v, "A": A_v, "P": P_v, "C": C_v, "D": D_v}
        score = sum(W[k] * v for k, v in factors.items())
        dlp = bool(road and road["under_dlp"] == "Y")
        if dlp:
            score *= B["dlp_discount"]

        high_traffic = bool(tr and (tr["congestion_index_0_10"] >= B["hot_traffic_congestion"] or (road and road["bus_route"] == "Y")))
        best, opts = _method_for(ref, i["category"], ward, high_traffic, R_v)
        est = None
        if best:
            if best["unit"] == "per sqm":
                area = ref.median_area.get((ward, i["category"])) or ref.median_area.get(("*", i["category"])) or 5.0
                est = best["unit_rate_inr"] * area
            else:
                est = float(best["unit_rate_inr"])
        bmc = 0.0 if dlp else (est or 0.0)

        # reasons, ordered by weighted contribution
        reasons = []
        reasons.append(("severity", W["S"] * S, {"category": i["category"], "s": i["severity"]}))
        if fac_kind:
            if fac_m is not None:
                reasons.append(("facility", W["P"] * P_v, {"kind": fac_kind, "m": B["facility_radius_m"]}))   # "within 250 m" is true
            else:
                reasons.append(("ambulance", W["P"] * P_v, {"kind": fac_kind}))
        if flood_y:
            reasons.append(("flood", W["F"] * F_v, {"y": flood_y}))
        if acc_n:
            reasons.append(("accidents", W["A"] * A_v, {"n": acc_n}))
        if i["complaint_count"] > 1 or i["upvotes"]:
            reasons.append(("reports", 0.5 * W["S"], {"n": i["complaint_count"], "u": i["upvotes"]}))
        if cong is not None and cong >= B["hot_traffic_congestion"]:
            reasons.append(("congestion", W["C"] * C_v, {"c": cong}))
        if days is not None and days >= 180:
            reasons.append(("age", W["D"] * D_v, {"d": days}))
        if kind == "failed_before":
            reasons.append(("failed_before", 0.9 * W["S"], {}))
        if kind == "never_fixed":
            reasons.append(("never_fixed", 0.8 * W["S"], {"d": max(0, (asof - datetime.strptime(i["first_reported"], "%Y-%m-%d %H:%M")).days)}))
        if R_v >= 0.5:
            reasons.append(("rain", W["R"] * R_v, {}))
        reasons.sort(key=lambda r: -r[1])
        reasons = [{"code": c, **p} for c, _, p in reasons[:4]]

        items.append({
            "issue_id": i["issue_id"], "category": i["category"], "ward_code": ward, "road_id": rid,
            "road_name": road["road_name"] if road else None, "locality": locality.get(i["issue_id"]),
            "kind": kind, "score": round(score, 4), "factors": {k: round(v, 3) for k, v in factors.items()},
            "weights": W, "under_dlp": dlp, "method": best["method"] if best else None, "alternatives": opts,
            "est_cost_inr": round(est) if est is not None else None, "bmc_cost_inr": round(bmc),
            "complaint_count": i["complaint_count"], "upvotes": i["upvotes"], "severity": i["severity"],
            "reasons": reasons, "location_known": pt is not None, "lat": pt[0] if pt else None, "lon": pt[1] if pt else None,
        })
    items.sort(key=lambda x: (-x["score"], x["issue_id"]))
    cum = 0.0
    for rank, it in enumerate(items, 1):
        it["rank"] = rank
        if it["bmc_cost_inr"] + cum <= cap_amt:
            it["funded"] = True
            cum += it["bmc_cost_inr"]
        else:
            it["funded"] = False
        it["cumulative_inr"] = round(cum)
        it["action"] = "warranty" if it["under_dlp"] else "repair"
    return {
        "ward_code": ward, "ward_name": w["ward_name"], "as_of": as_of_s, "budget_inr": round(budget), "spend_inr": round(spend),
        "remaining_inr": round(remaining), "allocation_cap_pct": int(B["allocation_cap"] * 100),
        "allocatable_inr": round(cap_amt), "allocated_inr": round(cum), "over_budget": remaining < 0,
        "rain_7d_mm": round(rain_mm, 1), "candidates": len(items), "funded": sum(1 for x in items if x["funded"]),
        "items": items, "weights": W,
        "note": "Advisory ranking from a transparent weighted score. Officers decide and assign work orders outside this system.",
    }


# --- text rendering ---------------------------------------------------------------------------
def render_reason(r: dict, lang: str) -> str:
    p = {k: v for k, v in r.items() if k != "code"}
    if r["code"] in ("facility", "ambulance"):
        p["kind"] = KIND[p["kind"]][lang]
    if r["code"] == "severity":
        p["category"] = T.category(p["category"], lang)
    return REASON_T[r["code"]][lang].format(**p)


def render_item(item: dict, lang: str) -> dict:
    where = item["road_name"] or item["locality"] or item["ward_code"]
    reasons = "; ".join(render_reason(r, lang) for r in item["reasons"])
    cat = T.category(item["category"], lang)
    text = RATIONALE_T[lang].format(category=cat, where=where, reasons=reasons, method=item["method"] or "-",
                                    cost=T.inr(item["est_cost_inr"] or 0))
    if item["under_dlp"]:
        text += " " + DLP_ACTION[lang]
    return {"rationale": text, "reasons_text": [render_reason(r, lang) for r in item["reasons"]]}


def run_all(conn) -> int:
    ref = Ref(conn)
    run_id = "run_" + uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("DELETE FROM budget_recommendation")
    n = 0
    for ward in ref.wards:
        plan = plan_ward(conn, ward, ref=ref)
        for it in plan["items"]:
            conn.execute(
                "INSERT INTO budget_recommendation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, ward, it["rank"], it["issue_id"], it["road_id"], it["score"],
                 json.dumps({"factors": it["factors"], "reasons": it["reasons"], "alternatives": it["alternatives"]}, ensure_ascii=False),
                 it["method"], it["est_cost_inr"], it["bmc_cost_inr"], it["cumulative_inr"], int(it["funded"]), it["action"],
                 render_item(it, "en")["rationale"], render_item(it, "mr")["rationale"], now))
            n += 1
    conn.commit()
    return n


