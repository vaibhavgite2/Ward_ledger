"""File Noting Drafter (SPEC §6.9): the note-sheet paragraph an officer reviews, edits and signs.

Every paragraph carries citations (document + row + source hash). `enforce_citations` blocks any
paragraph with no citation or a citation outside the evidence bundle. Drafts are returned to the
editor only: never stored as facts, never auto-filed.
"""
from __future__ import annotations

import config
import db
from agents import facts as Fx
from rules import text as T

LABELS = {
    "en": {
        "p1": "Work order {wo} ({wtype}; {method}) on {road} ({rid}), ward {ward}, was assigned to {contractor} and completed on {completed}. Amount billed: Rs. {cost}.",
        "p_rate": "The billed amount is Rs. {cost} against Rs. {expected} at the standard rate for {method} ({pct}% above).",
        "p_double": "A repair of the same type on the same road is recorded within {days} days (work order {first}); this work order has no linked complaint.",
        "p_dlp": "Road {rid} is recorded as under the original contractor's Defect Liability Period; this work was billed at Rs. {cost}.",
        "p_failed": "This repair is recorded as reopened within 30 days.",
        "p_sla": "Completed {hours} hours after the complaint against a target of {sla} hours.",
        "p_drift": "Unit cost of Rs. {unit} compared with Rs. {median} typical for {method} ({basis}).",
        "p_hist": "Contractor {contractor}: {n} works recorded this season, {ov} above the standard-rate range, {fl} reopened within 30 days.",
        "p_clean": "Contractor {contractor} has a clean record in ward {ward} ({n} completed works, on time, within the standard rate).",
        "p_ctx": "Context: ward {ward} {lowlying}; {heavy}.",
        "lowlying_yes": "is low-lying", "lowlying_no": "is not recorded as low-lying",
        "heavy_yes": "a heavy-rain week preceded this work", "heavy_no": "no heavy-rain week is recorded around this work",
        "p_rec": "Recommendation: (accept / conditional / refer to committee) - to be decided and recorded by the officer.",
        "title": "Draft note-sheet - for the officer's review, edit and signature. Not submitted.",
    },
    "mr": {
        "p1": "कामाचा आदेश {wo} ({wtype}; {method}) - {road} ({rid}), प्रभाग {ward} - {contractor} यांना देण्यात आला आणि {completed} रोजी पूर्ण झाला. बिल केलेली रक्कम: रु. {cost}.",
        "p_rate": "बिल केलेली रक्कम रु. {cost} आहे; {method} साठी प्रमाण दराने रु. {expected} ({pct}% जास्त).",
        "p_double": "त्याच रस्त्यावर {days} दिवसांच्या आत त्याच प्रकारची दुरुस्ती नोंदलेली आहे (कार्यादेश {first}); या कार्यादेशाशी कोणतीही तक्रार जोडलेली नाही.",
        "p_dlp": "रस्ता {rid} मूळ कंत्राटदाराच्या दोष दायित्व कालावधीत असल्याची नोंद आहे; हे काम रु. {cost} ला बिल केले गेले.",
        "p_failed": "ही दुरुस्ती 30 दिवसांत पुन्हा उघडल्याची नोंद आहे.",
        "p_sla": "तक्रारीनंतर {hours} तासांत पूर्ण; लक्ष्य {sla} तास.",
        "p_drift": "{method} साठी नेहमीच्या रु. {median} च्या तुलनेत एकक खर्च रु. {unit} ({basis}).",
        "p_hist": "कंत्राटदार {contractor}: या हंगामात {n} कामे नोंदलेली, {ov} प्रमाण दराच्या मर्यादेबाहेर, {fl} 30 दिवसांत पुन्हा उघडली.",
        "p_clean": "कंत्राटदार {contractor} यांची प्रभाग {ward} मध्ये स्वच्छ नोंद आहे ({n} पूर्ण कामे, वेळेत, प्रमाण दरात).",
        "p_ctx": "संदर्भ: प्रभाग {ward} {lowlying}; {heavy}.",
        "lowlying_yes": "सखल आहे", "lowlying_no": "सखल म्हणून नोंदलेला नाही",
        "heavy_yes": "या कामापूर्वी अतिवृष्टीचा आठवडा होता", "heavy_no": "या कामाच्या आसपास अतिवृष्टीचा आठवडा नोंदलेला नाही",
        "p_rec": "शिफारस: (मंजूर / सशर्त / समितीकडे पाठवणे) - अधिकाऱ्याने ठरवून नोंदवावे.",
        "title": "नोंदवही मसुदा - अधिकाऱ्याने तपासून, संपादित करून सही करावी. सादर केलेला नाही.",
    },
}


def cite(ev: dict) -> str:
    sha = (ev.get("sha256") or "")[:8]
    where = f"row {ev['row']}" if ev.get("row") else ev.get("note", "all rows")
    return f"[Ref: {ev['id']} · {ev['file']} {where} · sha256:{sha}…]"


def enforce_citations(paras: list[dict], allowed_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Block unsourced paragraphs. A para is kept iff it is officer_input or all its citations are in the bundle
    and there is at least one. -> (kept, blocked)"""
    kept, blocked = [], []
    for p in paras:
        if p.get("kind") == "officer_input":
            kept.append(p)
            continue
        cites = p.get("citations") or []
        if not cites or any(c["id"] not in allowed_ids for c in cites):
            blocked.append({**p, "reason": "no citation" if not cites else "citation outside evidence bundle"})
        else:
            kept.append(p)
    for n, p in enumerate(kept, 1):
        p["n"] = n
    return kept, blocked


def draft(conn, work_id: str, lang: str = "mr") -> dict | None:
    lang = lang if lang in ("mr", "en") else "mr"
    w = Fx.work_detail(conn, work_id, "en", officer=True)
    if not w:
        return None
    L = LABELS[lang]
    road = w["road"] or {}
    wo_ev = w["provenance"][0]
    ev_bundle: dict[str, dict] = {wo_ev["id"]: wo_ev}
    paras: list[dict] = []

    def add(kind, text, evs):
        for e in evs:
            ev_bundle[e["id"]] = e
        paras.append({"kind": kind, "text": text, "citations": [{"id": e["id"], "file": e["file"], "row": e["row"],
                                                                 "sha256": e.get("sha256"), "ref": cite(e)} for e in evs]})

    add("work", L["p1"].format(wo=work_id, wtype=T.category(w["work_type"], lang), method=w["repair_method"], road=road.get("road_name", "-"),
                               rid=w["road_id"], ward=w["ward_code"], contractor=w["contractor_name"], completed=w["completed_at"][:10],
                               cost=T.inr(w["cost_inr"])), [wo_ev])
    by_rule = {f["rule"]: f for f in w["findings"]}
    if "rate_card_overrun" in by_rule:
        m = by_rule["rate_card_overrun"]["metrics"]
        add("flag", L["p_rate"].format(cost=T.inr(m["cost_inr"]), expected=T.inr(m["expected_inr"]), method=m["method"], pct=m["pct_above"]),
            by_rule["rate_card_overrun"]["evidence"])
    if "possible_double_billing" in by_rule:
        m = by_rule["possible_double_billing"]["metrics"]
        add("flag", L["p_double"].format(days=max(0, round(m["gap_days"])), first=m["first_wo"]), by_rule["possible_double_billing"]["evidence"])
    if "dlp_breach" in by_rule:
        add("flag", L["p_dlp"].format(rid=w["road_id"], cost=T.inr(w["cost_inr"])), by_rule["dlp_breach"]["evidence"])
    if "failed_within_30d" in by_rule:
        add("flag", L["p_failed"], by_rule["failed_within_30d"]["evidence"])
    if "sla_missed" in by_rule:
        m = by_rule["sla_missed"]["metrics"]
        add("flag", L["p_sla"].format(hours=m["hours"], sla=m["sla_hours"]), by_rule["sla_missed"]["evidence"])
    if "estimate_drift" in by_rule:
        m = by_rule["estimate_drift"]["metrics"]
        add("flag", L["p_drift"].format(unit=T.inr(m["unit_cost_inr"]), median=T.inr(m["median_inr"]), method=m["method"], basis=m["comparison"]),
            by_rule["estimate_drift"]["evidence"])

    # contractor history (balance: also report positives)
    ct = w["contractor_id"]
    hist = db.rows(conn, "SELECT work_order_id, _row FROM work_orders WHERE contractor_id=?", (ct,))
    ov = db.one(conn, "SELECT COUNT(*) n FROM finding WHERE contractor_id=? AND rule='rate_card_overrun'", (ct,))["n"]
    fl = db.one(conn, "SELECT COUNT(*) n FROM work_orders WHERE contractor_id=? AND reopened_within_30d='Y'", (ct,))["n"]
    # a summary over many rows cites the filter it was computed from, not a made-up row number
    hist_ev = Fx.with_sha(conn, {"table": "work_orders", "id": f"work_orders[contractor_id={ct}]", "row": None,
                                 "file": "work_orders.csv", "note": f"filter contractor_id={ct} ({len(hist)} rows)"})
    add("history", L["p_hist"].format(contractor=w["contractor_name"], n=len(hist), ov=ov, fl=fl), [hist_ev])
    clean = db.one(conn, "SELECT finding_id, metrics_json, evidence_json FROM finding WHERE rule='clean_record' AND contractor_id=? AND ward_code=?",
                   (ct, w["ward_code"]))
    if clean:
        import json
        m = json.loads(clean["metrics_json"])
        evs = [Fx.with_sha(conn, e) for e in json.loads(clean["evidence_json"])[:3]]
        add("positive", L["p_clean"].format(contractor=w["contractor_name"], ward=w["ward_code"], n=m["completed"]), evs)

    # context (so that officers see the fairness adjustments applied)
    ctxs = [f["context"] for f in w["findings"] if f["context"]]
    low = any(c.get("low_lying_ward") for c in ctxs)
    heavy = any(c.get("heavy_rain_week") or c.get("heavy_rain_week_after") for c in ctxs)
    add("context", L["p_ctx"].format(ward=w["ward_code"], lowlying=L["lowlying_yes" if low else "lowlying_no"],
                                     heavy=L["heavy_yes" if heavy else "heavy_no"]), [wo_ev])
    paras.append({"kind": "officer_input", "text": L["p_rec"], "citations": []})

    kept, blocked = enforce_citations(paras, set(ev_bundle))
    return {"work_id": work_id, "lang": lang, "title": L["title"], "paras": kept, "blocked": blocked, "submitted": False,
            "demo_notice": config.SYNTHETIC_NOTICE}
