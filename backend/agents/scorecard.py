"""Contractor scorecards and ward money trail (SPEC §6.5).

Numbers are computed here, deterministically. Claude only phrases them (and the narrative is
number-checked against the payload; on any mismatch we fall back to the template text).
This module produces no score, grade or rank; the contractor's single transparent score lives in agents/score.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import config
import db
from agents import claude_client as cc
from agents import guard, metrics
from rules import text as T

R = config.RULES
NARRATIVE_VERSION = "v1"


def _pct(x) -> int:
    return int(round(float(x) * 100))


def _inr_clean(x) -> int:
    return int(round(float(x)))


# --------------------------------------------------------------------------------------------
def contractor_scorecard(conn, contractor_id: str) -> dict | None:
    c = db.one(conn, "SELECT * FROM contractors WHERE contractor_id=?", (contractor_id,))
    if not c:
        return None
    df = metrics.wo_frame(conn)
    ref = metrics.expected_rates(df)
    g = df[df["contractor_id"] == contractor_id].copy()
    if g.empty:
        return None
    g["exp_sla"] = g["sla_hours"].map(ref["sla"])
    g["exp_reopen"] = g.apply(lambda r: metrics.expected_reopen(r, ref), axis=1)

    sla, exp_sla = float(g["sla_ok"].mean()), float(g["exp_sla"].mean())
    reopen, exp_reopen = float(g["failed"].mean()), float(g["exp_reopen"].mean())
    over = float((g["ratio"] > R["rate_card_overrun"]["ratio"]).mean())
    within = 1 - over
    fr = db.rows(conn, "SELECT rule, polarity, COUNT(*) n FROM finding WHERE contractor_id=? GROUP BY rule, polarity", (contractor_id,))
    clean = db.rows(conn, "SELECT subject_id, ward_code, public_text_en, public_text_mr, public_text_hi, metrics_json, finding_id "
                          "FROM finding WHERE contractor_id=? AND rule='clean_record' ORDER BY ward_code", (contractor_id,))
    by_ward = []
    for w, gg in g.groupby("ward_code"):
        by_ward.append({"ward_code": w, "completed": int(len(gg)), "billed_inr": _inr_clean(gg["cost_inr"].sum()),
                        "sla_pct": _pct(gg["sla_ok"].mean()), "reopen_pct": _pct(gg["failed"].mean())})
    metrics_payload = {
        "contractor_id": contractor_id, "name": c["contractor_name"], "empanelled_since": int(c["empanelled_since"]),
        "completed": int(len(g)), "billed_inr": _inr_clean(g["cost_inr"].sum()), "wards": int(g["ward_code"].nunique()),
        "sla_pct": _pct(sla), "expected_sla_pct": _pct(exp_sla),
        "reopen_pct": _pct(reopen), "expected_reopen_pct": _pct(exp_reopen),
        "within_rate_pct": _pct(within), "overrun_jobs": int((g["ratio"] > R["rate_card_overrun"]["ratio"]).sum()),
        "median_cost_ratio": round(float(g["ratio"].median()), 2),
        "dlp_jobs": int(g["dlp"].sum()),
        "failed_cost_inr": _inr_clean(g.loc[g["failed"], "cost_inr"].sum()),
        "clean_record_wards": [x["ward_code"] for x in clean],
    }
    s_gap, r_gap, c_gap = sla - exp_sla, exp_reopen - reopen, within - 0.95
    gaps = [("speed", s_gap), ("durability", r_gap), ("cost", c_gap)]
    best = max(gaps, key=lambda t: t[1])
    metrics_payload["strength"] = best[0]
    # Only call it a strength if the contractor actually meets or beats the expected level.
    metrics_payload["strength_kind"] = "strength" if best[1] >= 0 else "closest"
    worst = min(gaps, key=lambda t: t[1])
    metrics_payload["improve"] = worst[0]
    # Only call it "to improve" if it is actually below the expected level.
    metrics_payload["improve_kind"] = "improve" if worst[1] < 0 else "smallest_margin"
    return {
        "contractor_id": contractor_id, "name": c["contractor_name"], "empanelled_since": int(c["empanelled_since"]),
        "active_wards": c["active_wards"], "metrics": metrics_payload, "by_ward": by_ward,
        "findings": {r["rule"]: r["n"] for r in fr},
        "clean_record": clean,
        "evidence": {"table": "work_orders", "filter": f"contractor_id={contractor_id}", "file": "work_orders.csv",
                     "count": int(len(g))},
        "context_note": {
            "en": "Speed and durability are compared with what is expected for the same mix of urgent jobs, repair methods, low-lying wards and heavy-rain weeks.",
            "mr": "वेग आणि टिकाऊपणा यांची तुलना त्याच प्रकारच्या तातडीच्या कामांसाठी, दुरुस्ती पद्धती, सखल प्रभाग आणि अतिवृष्टीच्या आठवड्यांसाठी अपेक्षित पातळीशी केली आहे.",
            "hi": "गति और टिकाऊपन की तुलना उसी तरह के तत्काल कामों, मरम्मत पद्धतियों, निचले वार्डों और भारी बारिश वाले सप्ताहों के अपेक्षित स्तर से की गई है।",
        },
    }


_STRENGTH = {
    "speed": {"en": "finishing jobs on time", "mr": "कामे वेळेत पूर्ण करणे", "hi": "काम समय पर पूरा करना"},
    "durability": {"en": "repairs that hold up", "mr": "टिकाऊ दुरुस्ती", "hi": "टिकाऊ मरम्मत"},
    "cost": {"en": "billing close to the standard rate", "mr": "प्रमाण दराच्या जवळ बिल", "hi": "मानक दर के करीब बिल"},
}
_IMPROVE = {
    "speed": {"en": "meeting the target time for urgent jobs", "mr": "तातडीच्या कामांसाठी लक्ष्य वेळ पाळणे", "hi": "तत्काल कामों के लिए लक्ष्य समय का पालन"},
    "durability": {"en": "making repairs last beyond 30 days", "mr": "दुरुस्ती 30 दिवसांपेक्षा जास्त टिकवणे", "hi": "मरम्मत को 30 दिनों से अधिक टिकाऊ बनाना"},
    "cost": {"en": "keeping bills within the standard rate", "mr": "बिल प्रमाण दराच्या आत ठेवणे", "hi": "बिल मानक दर के भीतर रखना"},
}
_CONTRACTOR_TPL = {
    "en": ("{name} completed {completed} repairs worth ₹{billed} across {wards} wards. {sla_pct}% were finished within the "
           "target time (about {expected_sla_pct}% is expected for this mix of urgent jobs). {reopen_pct}% had to be reopened "
           "within 30 days (about {expected_reopen_pct}% is expected for these methods and conditions). {within_rate_pct}% of bills "
           "were within the normal range of the standard rate. {strength_label}: {strength}. {improve_label}: {improve}."),
    "mr": ("{name} यांनी {wards} प्रभागांत ₹{billed} च्या {completed} दुरुस्त्या पूर्ण केल्या. {sla_pct}% कामे लक्ष्य वेळेत झाली "
           "(या प्रकारच्या तातडीच्या कामांसाठी साधारण {expected_sla_pct}% अपेक्षित). {reopen_pct}% कामे 30 दिवसांत पुन्हा उघडावी लागली "
           "(अपेक्षित साधारण {expected_reopen_pct}%). {within_rate_pct}% बिले प्रमाण दराच्या सामान्य मर्यादेत होती. "
           "{strength_label}: {strength}. {improve_label}: {improve}."),
    "hi": ("{name} ने {wards} वार्डों में ₹{billed} की {completed} मरम्मतें पूरी कीं। {sla_pct}% काम लक्ष्य समय में हुए "
           "(इस तरह के तत्काल कामों के लिए लगभग {expected_sla_pct}% अपेक्षित)। {reopen_pct}% काम 30 दिनों में दोबारा खोलने पड़े "
           "(अपेक्षित लगभग {expected_reopen_pct}%)। {within_rate_pct}% बिल मानक दर की सामान्य सीमा में थे। "
           "{strength_label}: {strength}। {improve_label}: {improve}।"),
}


_STRENGTH_LABEL = {
    "strength": {"en": "Strength", "mr": "बलस्थान", "hi": "ताकत"},
    "closest": {"en": "Closest to the expected level", "mr": "अपेक्षित पातळीच्या सर्वात जवळ", "hi": "अपेक्षित स्तर के सबसे करीब"},
}


_IMPROVE_LABEL = {
    "improve": {"en": "To improve", "mr": "सुधारणा", "hi": "सुधार"},
    "smallest_margin": {"en": "Smallest margin above the expected level", "mr": "अपेक्षित पातळीपेक्षा सर्वात कमी फरक", "hi": "अपेक्षित स्तर से सबसे कम अंतर"},
}


def _contractor_template(m: dict, lang: str) -> str:
    return _CONTRACTOR_TPL[lang].format(
        improve_label=_IMPROVE_LABEL[m["improve_kind"]][lang],
        strength_label=_STRENGTH_LABEL[m["strength_kind"]][lang],
        name=m["name"], completed=m["completed"], billed=T.inr(m["billed_inr"]), wards=m["wards"], sla_pct=m["sla_pct"],
        expected_sla_pct=m["expected_sla_pct"], reopen_pct=m["reopen_pct"], expected_reopen_pct=m["expected_reopen_pct"],
        within_rate_pct=m["within_rate_pct"], strength=_STRENGTH[m["strength"]][lang], improve=_IMPROVE[m["improve"]][lang])


_LANG_NAME = {"en": "English", "mr": "Marathi", "hi": "Hindi"}

_NARRATIVE_SYSTEM = (
    "You write short, fair, plain-language summaries of public road-repair records for Mumbai citizens. "
    "Use ONLY the numbers in the JSON you are given; never compute or invent new numbers. "
    "Mention the context comparison (expected values). Name one thing that is going well ONLY if strength_kind is 'strength'; "
    "if it is 'closest', say it is the area closest to the expected level, not a strength. Name the weakest area as 'to improve' only if improve_kind is 'improve'; otherwise call it the smallest margin above the expected level. "
    "Neutral tone: describe what the records show. Never use the words fraud, scam, suspicious, corrupt, theft. "
    "Do not rank or grade. Plain text only, no markdown."
)


def narrative(conn, key: str, lang: str, payload: dict, template_text: str, max_words: int) -> dict:
    """Return {text, source: 'claude'|'template', extractor}. Cached in the narrative table."""
    ck = f"{key}:{lang}"
    row = db.one(conn, "SELECT * FROM narrative WHERE key=?", (ck,))
    if row:
        return {"text": row["text"], "source": "claude" if (row["extractor"] or "").startswith("claude") else "template",
                "extractor": row["extractor"]}
    text, extractor, ph = template_text, "template@v1", None
    prompt = (f"Write at most {max_words} words in {_LANG_NAME[lang]}.\nData (JSON):\n{guard.payload_json(payload)}")
    res = cc.complete(config.MODEL_WRITER, _NARRATIVE_SYSTEM, prompt, agent="narrative", version=NARRATIVE_VERSION,
                      max_tokens=700, temperature=0.3)
    if res:
        t = res.text.strip()
        if guard.numbers_ok(t, payload) and not guard.banned_words(t) and len(t.split()) <= max_words * 1.6:
            text, extractor, ph = t, res.extractor, res.prompt_hash
    conn.execute("INSERT OR REPLACE INTO narrative VALUES (?,?,?,?,?,?)",
                 (ck, lang, text, extractor, ph, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    return {"text": text, "source": "claude" if extractor.startswith("claude") else "template", "extractor": extractor}


def contractor_narrative(conn, card: dict, lang: str) -> dict:
    m = card["metrics"]
    return narrative(conn, f"contractor:{m['contractor_id']}", lang, m, _contractor_template(m, lang), 120)


# --------------------------------------------------------------------------------------------
def _ward_rows(conn):
    return db.rows(conn, "SELECT * FROM wards ORDER BY ward_code")


def ward_money_trail(conn, ward_code: str) -> dict | None:
    w = db.one(conn, "SELECT * FROM wards WHERE ward_code=?", (ward_code,))
    if not w:
        return None
    df = metrics.wo_frame(conn)
    g = df[df["ward_code"] == ward_code]
    budget = float(w["monsoon_repair_budget_inr_2025"])
    spend = float(g["cost_inr"].sum())
    by_contractor = [{"contractor_id": cid, "name": gg["contractor_name"].iloc[0], "jobs": int(len(gg)),
                      "billed_inr": _inr_clean(gg["cost_inr"].sum()), "failed_inr": _inr_clean(gg.loc[gg["failed"], "cost_inr"].sum())}
                     for cid, gg in g.groupby("contractor_id")]
    by_method = [{"method": m, "jobs": int(len(gg)), "billed_inr": _inr_clean(gg["cost_inr"].sum()),
                  "failed_pct": _pct(gg["failed"].mean())} for m, gg in g.groupby("repair_method")]
    by_month = [{"month": m, "billed_inr": _inr_clean(gg["cost_inr"].sum()), "jobs": int(len(gg))} for m, gg in g.groupby("month")]
    funnel = db.one(conn, """
        SELECT COUNT(*) received,
               SUM(link_status='fixed') fixed, SUM(link_status='fixed_failed') fixed_failed,
               SUM(link_status='linked_via_issue') via_issue, SUM(link_status='never_fixed') never_fixed,
               SUM(link_status='pending') pending, SUM(link_status='closed_other') closed_other,
               SUM(link_status='duplicate') duplicate
        FROM parsed_complaint WHERE ward_code=?""", (ward_code,))
    unique_issues = db.one(conn, "SELECT COUNT(*) n FROM issue WHERE ward_code=?", (ward_code,))["n"]
    ctx_stn = "Colaba" if ward_code in R["context"]["island_city_wards"] else "Santacruz"
    heavy_days = db.one(conn, "SELECT COUNT(*) n FROM rainfall_daily WHERE station=? AND imd_category IN ('Heavy','Very heavy','Extremely heavy')", (ctx_stn,))["n"]
    fr = db.rows(conn, "SELECT rule, COUNT(*) n FROM finding WHERE ward_code=? AND polarity='concern' GROUP BY rule", (ward_code,))
    payload = {
        "ward_code": ward_code, "ward_name": w["ward_name"], "budget_inr": _inr_clean(budget), "spend_inr": _inr_clean(spend),
        "utilisation_pct": _pct(spend / budget) if budget else None, "jobs": int(len(g)),
        "failed_jobs": int(g["failed"].sum()), "failed_inr": _inr_clean(g.loc[g["failed"], "cost_inr"].sum()),
        "failed_pct_of_spend": _pct(g.loc[g["failed"], "cost_inr"].sum() / spend) if spend else 0,
        "dlp_jobs": int(g["dlp"].sum()), "dlp_inr": _inr_clean(g.loc[g["dlp"], "cost_inr"].sum()),
        "sla_pct": _pct(g["sla_ok"].mean()) if len(g) else None,
        "complaints_received": int(funnel["received"] or 0), "unique_issues": unique_issues,
        "never_fixed_complaints": int(funnel["never_fixed"] or 0),
        "low_lying_index": w["low_lying_index"], "heavy_rain_days": heavy_days, "crews": int(w["engineering_crews"]),
    }
    return {
        "ward_code": ward_code, "ward_name": w["ward_name"], "zone": w["zone"], "office": w["assistant_commissioner_office"],
        "localities": w["localities"], "population": int(w["population_est"]),
        "budget_inr": payload["budget_inr"], "spend_inr": payload["spend_inr"], "remaining_inr": payload["budget_inr"] - payload["spend_inr"],
        "utilisation_pct": payload["utilisation_pct"], "overspent": spend > budget,
        "failed_inr": payload["failed_inr"], "failed_jobs": payload["failed_jobs"], "failed_pct_of_spend": payload["failed_pct_of_spend"],
        "dlp_inr": payload["dlp_inr"], "dlp_jobs": payload["dlp_jobs"], "sla_pct": payload["sla_pct"], "jobs": payload["jobs"],
        "by_contractor": sorted(by_contractor, key=lambda x: -x["billed_inr"]),
        "by_method": sorted(by_method, key=lambda x: -x["billed_inr"]), "by_month": by_month,
        "funnel": {"received": payload["complaints_received"], "unique_issues": unique_issues,
                   "fixed_and_held": int(funnel["fixed"] or 0), "fixed_but_failed": int(funnel["fixed_failed"] or 0),
                   "linked_via_duplicate_issue": int(funnel["via_issue"] or 0),
                   "never_fixed": int(funnel["never_fixed"] or 0), "pending": int(funnel["pending"] or 0),
                   "closed_other": int(funnel["closed_other"] or 0), "duplicate": int(funnel["duplicate"] or 0)},
        "context": {"low_lying_index": w["low_lying_index"], "heavy_rain_days_season": heavy_days, "crews": payload["crews"],
                    "rain_station": ctx_stn},
        "finding_counts": {r["rule"]: r["n"] for r in fr},
        "payload": payload,
    }


_WARD_TPL = {
    "en": ("In ward {ward_code} ({ward_name}), ₹{spend} of the ₹{budget} monsoon road-repair budget was billed ({utilisation_pct}%) "
           "across {jobs} repairs. {failed_jobs} repairs, costing ₹{failed}, failed within 30 days and had to be reopened. "
           "{dlp_jobs} repairs (₹{dlp}) were on roads recorded as still under warranty. {complaints_received} complaints were received, "
           "which were grouped into {unique_issues} separate issues; {never_fixed_complaints} complaints have no repair linked."),
    "mr": ("प्रभाग {ward_code} ({ward_name}) मध्ये ₹{budget} च्या पावसाळी रस्ते दुरुस्ती अर्थसंकल्पापैकी ₹{spend} ({utilisation_pct}%) "
           "{jobs} दुरुस्त्यांसाठी बिल केले गेले. {failed_jobs} दुरुस्त्या (₹{failed}) 30 दिवसांत अपयशी ठरल्या आणि पुन्हा उघडाव्या लागल्या. "
           "{dlp_jobs} दुरुस्त्या (₹{dlp}) वॉरंटी कालावधीत असल्याची नोंद असलेल्या रस्त्यांवर होत्या. {complaints_received} तक्रारी आल्या, "
           "त्या {unique_issues} वेगळ्या समस्यांमध्ये गटबद्ध झाल्या; {never_fixed_complaints} तक्रारींशी कोणतीही दुरुस्ती जोडलेली नाही."),
    "hi": ("वार्ड {ward_code} ({ward_name}) में ₹{budget} के मानसून सड़क मरम्मत बजट में से ₹{spend} ({utilisation_pct}%) "
           "{jobs} मरम्मतों के लिए बिल किए गए। {failed_jobs} मरम्मतें (₹{failed}) 30 दिनों में विफल हुईं और दोबारा खोलनी पड़ीं। "
           "{dlp_jobs} मरम्मतें (₹{dlp}) ऐसी सड़कों पर थीं जो वारंटी में दर्ज हैं। {complaints_received} शिकायतें मिलीं, "
           "जो {unique_issues} अलग समस्याओं में समूहित हुईं; {never_fixed_complaints} शिकायतों से कोई मरम्मत जुड़ी नहीं है।"),
}


def ward_narrative(conn, trail: dict, lang: str) -> dict:
    p = trail["payload"]
    tpl = _WARD_TPL[lang].format(
        ward_code=p["ward_code"], ward_name=p["ward_name"], spend=T.inr(p["spend_inr"]), budget=T.inr(p["budget_inr"]),
        utilisation_pct=p["utilisation_pct"], jobs=p["jobs"], failed_jobs=p["failed_jobs"], failed=T.inr(p["failed_inr"]),
        dlp_jobs=p["dlp_jobs"], dlp=T.inr(p["dlp_inr"]), complaints_received=p["complaints_received"],
        unique_issues=p["unique_issues"], never_fixed_complaints=p["never_fixed_complaints"])
    return narrative(conn, f"ward:{p['ward_code']}", lang, p, tpl, 200)


def compare_wards(conn) -> list[dict]:
    df = metrics.wo_frame(conn)
    funnel = {r["ward_code"]: r for r in db.rows(
        conn, "SELECT ward_code, COUNT(*) received, SUM(link_status='never_fixed') never_fixed FROM parsed_complaint GROUP BY ward_code")}
    open_issues = {r["ward_code"]: r["n"] for r in db.rows(
        conn, "SELECT ward_code, COUNT(*) n FROM issue WHERE status IN ('never_fixed','pending','fixed_failed') GROUP BY ward_code")}
    out = []
    for w in _ward_rows(conn):
        g = df[df["ward_code"] == w["ward_code"]]
        spend = float(g["cost_inr"].sum())
        budget = float(w["monsoon_repair_budget_inr_2025"])
        f = funnel.get(w["ward_code"], {})
        out.append({
            "ward_code": w["ward_code"], "ward_name": w["ward_name"], "zone": w["zone"],
            "budget_inr": _inr_clean(budget), "spend_inr": _inr_clean(spend), "utilisation_pct": _pct(spend / budget) if budget else None,
            "failed_inr": _inr_clean(g.loc[g["failed"], "cost_inr"].sum()), "failed_pct": _pct(g["failed"].mean()) if len(g) else None,
            "sla_pct": _pct(g["sla_ok"].mean()) if len(g) else None, "jobs": int(len(g)),
            "complaints": int(f.get("received", 0) or 0), "never_fixed": int(f.get("never_fixed", 0) or 0),
            "open_issues": int(open_issues.get(w["ward_code"], 0)), "low_lying_index": w["low_lying_index"],
        })
    return out

