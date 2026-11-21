"""Contractor score: one transparent 0-100 number built only from the contractor's own recorded work.

    score = 40% x durability  +  35% x on-time  +  25% x billing

* durability  - share of repairs that were NOT reopened within 30 days ("fixes held beyond 30 days")
* on-time     - share of jobs finished inside their target time (SLA)
* billing     - share of bills within the normal range of the standard rate-card amount ("billing match")

Context adjustment (the "Flood index" line on the card): a contractor who is given harder work than average (more urgent
jobs, repair methods that fail more often, low-lying wards, heavy-rain weeks) is not penalised for it. For durability and
on-time we compare the contractor's actual rate with what is *expected* for the same mix of jobs (metrics.expected_rates) and
shift it by the gap between the city-wide rate and that expectation. The flood index shown is the job-weighted low-lying
index (0-1) of the wards the contractor worked in.

Work done through the app counts too: tasks the officer approved (on time or late) and tasks that are past their deadline and
still not completed count towards on-time; approved bills checked against the rate card count towards billing.

Deterministic arithmetic only: no model writes or changes a score. The inputs are always shown next to the number, and
contractors can reply to any finding from their own panel (right of reply).
"""
from __future__ import annotations

from datetime import datetime, timezone

import config
import db
from agents import metrics

R = config.RULES
WEIGHTS = {"durability": 0.40, "sla": 0.35, "billing": 0.25}
# (minimum score, band). Wording stays descriptive: it says how the record compares, not what anyone intended.
BANDS = [(80, "reliable"), (65, "mixed"), (0, "below")]


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def band_for(score: int) -> str:
    return next(b for lo, b in BANDS if score >= lo)


def _live_stats(conn, contractor_id: str) -> dict:
    """Outcome of tasks created in the app for this contractor."""
    from live import tasks as TS            # late import: live.tasks imports agents.scorecard
    on_time = late = bills = bills_ok = 0
    for k in db.rows(conn, "SELECT * FROM task WHERE contractor_id=? AND status IN ('completed','assigned','in_progress','rework')",
                     (contractor_id,)):
        due = TS.due_datetime(k["due_at"])
        if k["status"] == "completed":
            done = TS.due_datetime(k["completed_at"]) if k["completed_at"] else None
            if due and done:
                if done <= due:
                    on_time += 1
                else:
                    late += 1
            r = db.one(conn, "SELECT checks_json FROM repair_report WHERE task_id=? AND decision='approved' "
                             "ORDER BY submitted_at DESC LIMIT 1", (k["task_id"],))
            if r:
                bills += 1
                bills_ok += "bill_over_rate" not in (r["checks_json"] or "")
        elif due and due < datetime.now(timezone.utc):
            late += 1                        # still owed after the deadline
    return {"on_time": on_time, "late": late, "bills": bills, "bills_ok": bills_ok}


def _score_from_frame(conn, df, ref, wards: dict, contractor_id: str) -> dict | None:
    g = df[df["contractor_id"] == contractor_id]
    if g.empty:
        return None
    n = int(len(g))
    sla_actual = float(g["sla_ok"].mean()) * 100
    sla_expected = float(g["sla_hours"].map(ref["sla"]).mean()) * 100
    held_actual = (1 - float(g["failed"].mean())) * 100
    held_expected = (1 - float(g.apply(lambda r: metrics.expected_reopen(r, ref), axis=1).mean())) * 100
    sla_adj = _clamp(sla_actual + (ref["city_sla"] * 100 - sla_expected))
    dur_adj = _clamp(held_actual + ((1 - ref["city_reopen"]) * 100 - held_expected))
    over = float((g["ratio"] > R["rate_card_overrun"]["ratio"]).mean())
    bill = (1 - over) * 100

    live = _live_stats(conn, contractor_id)
    jobs_sla = live["on_time"] + live["late"]
    if jobs_sla:
        sla_adj = (n * sla_adj + live["on_time"] * 100) / (n + jobs_sla)
    if live["bills"]:
        bill = (n * bill + live["bills_ok"] * 100) / (n + live["bills"])

    flood = float(g["ward_code"].map(wards).mean())
    dur, sla, billing = round(dur_adj), round(sla_adj), round(bill)
    score = round(WEIGHTS["durability"] * dur_adj + WEIGHTS["sla"] * sla_adj + WEIGHTS["billing"] * bill)
    return {
        "score": int(score), "band": band_for(int(score)),
        "durability_pct": dur, "sla_pct": sla, "billing_pct": billing,
        "flood_index": round(flood, 2), "context_adjusted": True,
        "basis": {"repairs": n, "app_tasks": jobs_sla},
        "weights": {k: int(v * 100) for k, v in WEIGHTS.items()},
    }


def contractor_scores(conn) -> dict[str, dict]:
    """Score for every contractor that has recorded work (one pass over the shared work-order frame)."""
    df = metrics.wo_frame(conn)
    ref = metrics.expected_rates(df)
    wards = {w["ward_code"]: float(w["low_lying_index"]) for w in db.rows(conn, "SELECT ward_code, low_lying_index FROM wards")}
    out = {}
    for cid in sorted(df["contractor_id"].unique()):
        s = _score_from_frame(conn, df, ref, wards, cid)
        if s:
            out[cid] = s
    return out


def contractor_score(conn, contractor_id: str) -> dict | None:
    return contractor_scores(conn).get(contractor_id)


# ---- plain-language verdict (deterministic template; the numbers are the ones on the card) ------------------------
BAND_LABEL = {
    "reliable": {"en": "Reliable", "mr": "विश्वासार्ह", "hi": "भरोसेमंद"},
    "mixed": {"en": "Mixed record", "mr": "संमिश्र नोंद", "hi": "मिली-जुली रिकॉर्ड"},
    "below": {"en": "Below expected", "mr": "अपेक्षेपेक्षा कमी", "hi": "अपेक्षा से कम"},
}
_VERDICT = {
    "en": ("{name}: {score}/100, {band}. {durability}% of repairs held beyond 30 days, {sla}% were finished on time and "
           "{billing}% of bills matched the standard rate. Scores are adjusted for the mix of jobs and the weather "
           "(flood index {flood}). Based on {repairs} recorded repairs{app}."),
    "mr": ("{name}: {score}/100, {band}. {durability}% दुरुस्त्या 30 दिवसांपेक्षा जास्त टिकल्या, {sla}% कामे वेळेत झाली आणि "
           "{billing}% बिले प्रमाण दराशी जुळली. गुण कामाच्या प्रकारानुसार आणि हवामानानुसार समायोजित केले आहेत "
           "(पूर निर्देशांक {flood}). {repairs} नोंदवलेल्या दुरुस्त्यांवर आधारित{app}."),
    "hi": ("{name}: {score}/100, {band}। {durability}% मरम्मतें 30 दिनों से अधिक टिकीं, {sla}% काम समय पर हुए और "
           "{billing}% बिल मानक दर से मेल खाए। स्कोर काम के मिश्रण और मौसम के अनुसार समायोजित है "
           "(बाढ़ सूचकांक {flood})। {repairs} दर्ज मरम्मतों पर आधारित{app}।"),
}
_APP = {"en": " plus {n} task(s) handled through this app", "mr": " आणि या ॲपमधून दिलेली {n} कामे",
        "hi": " और इस ऐप से दिए गए {n} कार्य"}


def verdict(name: str, s: dict, lang: str) -> str:
    lang = lang if lang in _VERDICT else "en"
    n = s["basis"]["app_tasks"]
    return _VERDICT[lang].format(
        name=name.replace(" (synthetic)", ""), score=s["score"], band=BAND_LABEL[s["band"]][lang], durability=s["durability_pct"],
        sla=s["sla_pct"], billing=s["billing_pct"], flood=f"{s['flood_index']:.2f}", repairs=s["basis"]["repairs"],
        app=_APP[lang].format(n=n) if n else "")
