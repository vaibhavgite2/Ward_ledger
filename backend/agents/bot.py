"""Citizen Accountability Bot (SPEC §6.7). Facts in, plain-language answer out.

Resolve the question to a complaint / work order / road (or a few candidates the citizen picks from),
gather only promoted, public facts, then answer. Claude may phrase the answer; the template
answer is always available and is used if the model output fails the number / neutrality checks.
"""
from __future__ import annotations

import re

import config
import db
from agents import claude_client as cc
from agents import complaint_parser as cp
from agents import facts as Fx
from agents import geocoder, guard
from rules import text as T

RE_COMPLAINT = re.compile(r"BMC\d{2}-\d{6}", re.I)
RE_TICKET = re.compile(r"CMP-\d{6}", re.I)
RE_WO = re.compile(r"WO\d{2}-\d{5}", re.I)
RE_ROAD = re.compile(r"RD\d{4}", re.I)
DEV = re.compile(r"[ऀ-ॿ]")
HI_MARK = re.compile(r"(है|मेरी|मेरा|का |की |में |क्या |कब )")

_LANG_NAME = {"en": "English", "mr": "Marathi", "hi": "Hindi"}


def detect_lang(text: str, default: str = "mr") -> str:
    if DEV.search(text):
        mr_mark = re.search(r"(आहे|माझी|माझा|झाले|काय|का\b|तक्रार)", text)
        if HI_MARK.search(text) and not mr_mark:
            return "hi"
        return "mr"
    return default if default in T.LANGS else "en"


# ---- resolve ------------------------------------------------------------------------------------
def _norm(s):
    return geocoder.norm(s)


def resolve(conn, q: str) -> dict:
    q = (q or "").strip()
    m = RE_TICKET.search(q)
    if m:
        return {"type": "ticket", "id": m.group(0).upper()}
    m = RE_COMPLAINT.search(q)
    if m:
        return {"type": "complaint", "id": m.group(0).upper()}
    m = RE_WO.search(q)
    if m:
        return {"type": "work", "id": m.group(0).upper()}
    m = RE_ROAD.search(q)
    if m:
        return {"type": "road", "id": m.group(0).upper()}
    nq = " " + _norm(q) + " "
    # locality: longest leading-words prefix of any gazetteer name/alias that appears as whole words
    # in the question ("Andheri" matches "Andheri East"; "Vile" matches "Vile Parle West").
    loc, best = None, 0
    for r in db.rows(conn, "SELECT locality, aliases FROM localities"):
        for n in [r["locality"]] + [a for a in (r["aliases"] or "").split(";") if a.strip()]:
            toks = _norm(n).split()
            for k in range(len(toks), 0, -1):
                pref = " ".join(toks[:k])
                if len(pref) >= 4 and f" {pref} " in nq and len(pref) > best:
                    loc, best = pref, len(pref)
    # road name
    road_ids = []
    for r in db.rows(conn, "SELECT DISTINCT road_name FROM roads"):
        if _norm(r["road_name"]) and f" {_norm(r['road_name'])} " in nq:
            road_ids = [x["road_id"] for x in db.rows(conn, "SELECT road_id FROM roads WHERE road_name=? ORDER BY segment_no LIMIT 3", (r["road_name"],))]
            break
    cat = cp.classify_keyword(q)["category"]
    cat = cat if cat != "Other" else None
    cands = []
    if loc:
        sql = ("SELECT p.complaint_id, c.received_at, p.category, p.locality, p.link_status FROM parsed_complaint p "
               "JOIN complaints c USING(complaint_id) WHERE lower(p.locality) LIKE ?")
        params = [loc + "%"]
        if cat:
            sql += " AND p.category=?"
            params.append(cat)
        sql += " ORDER BY c.upvotes DESC, c.received_at DESC LIMIT 3"
        cands = db.rows(conn, sql, params)
    if cands:
        return {"type": "candidates", "locality": loc, "category": cat, "complaints": cands}
    if road_ids:
        return {"type": "road_candidates", "roads": road_ids}
    return {"type": "none", "locality": loc, "category": cat}


# ---- templates ------------------------------------------------------------------------------------
A = {
    "head": {
        "en": "Complaint {id} ({category}, {locality}) was filed on {date}.",
        "mr": "तक्रार {id} ({category}, {locality}) {date} रोजी नोंदवली गेली.",
        "hi": "शिकायत {id} ({category}, {locality}) {date} को दर्ज हुई।",
    },
    "work": {
        "en": " It was linked to work order {wo}, given to {contractor}. Work was completed on {completed}. Cost billed: ₹{cost}. Target time met: {sla}. Reopened within 30 days: {reopened}.",
        "mr": " ती कामाच्या आदेश {wo} शी जोडली गेली, जो {contractor} यांना दिला होता. काम {completed} रोजी पूर्ण झाले. बिल केलेला खर्च: ₹{cost}. लक्ष्य वेळ पाळली: {sla}. 30 दिवसांत पुन्हा उघडले: {reopened}.",
        "hi": " यह कार्य आदेश {wo} से जुड़ी थी, जो {contractor} को दिया गया था। काम {completed} को पूरा हुआ। बिल की गई लागत: ₹{cost}। लक्ष्य समय पूरा हुआ: {sla}। 30 दिनों में दोबारा खुला: {reopened}।",
    },
    "via_issue": {
        "en": " It appears to be the same issue reported {n} times, and the repair was linked to the group.",
        "mr": " ही समस्या {n} वेळा नोंदवलेली दिसते आणि दुरुस्ती या गटाशी जोडली आहे.",
        "hi": " यह वही समस्या {n} बार दर्ज दिखती है और मरम्मत इस समूह से जुड़ी है।",
    },
    "dlp": {
        "en": " The road ({road}) is recorded as still under the contractor's Defect Liability Period.",
        "mr": " हा रस्ता ({road}) अजून कंत्राटदाराच्या दोष दायित्व कालावधीत (Defect Liability Period) असल्याची नोंद आहे.",
        "hi": " यह सड़क ({road}) अब भी ठेकेदार के दोष दायित्व काल (Defect Liability Period) में दर्ज है।",
    },
    "over": {
        "en": " The bill is {pct}% above the standard rate for this type of repair.",
        "mr": " या प्रकारच्या दुरुस्तीसाठी बिल प्रमाण दरापेक्षा {pct}% जास्त आहे.",
        "hi": " इस तरह की मरम्मत के लिए बिल मानक दर से {pct}% अधिक है।",
    },
    "never": {
        "en": " No repair has been linked to it {days} days after it was filed.",
        "mr": " नोंदवल्यानंतर {days} दिवसांनीही कोणतीही दुरुस्ती जोडलेली नाही.",
        "hi": " दर्ज होने के {days} दिन बाद भी कोई मरम्मत जुड़ी नहीं है।",
    },
    "pending": {
        "en": " It is still open ({days} days).",
        "mr": " ती अजून खुली आहे ({days} दिवस).",
        "hi": " यह अभी खुली है ({days} दिन)।",
    },
    "closed": {
        "en": " Its recorded status is: {status}.",
        "mr": " तिची नोंदवलेली स्थिती: {status}.",
        "hi": " इसकी दर्ज स्थिति: {status}।",
    },
    "unverified": {
        "en": " (The category is our reading of the text and has not been verified.)",
        "mr": " (वर्ग आमच्या वाचनावर आधारित आहे, पडताळलेला नाही.)",
        "hi": " (श्रेणी हमारी पढ़ाई पर आधारित है, सत्यापित नहीं।)",
    },
    "rti": {
        "en": " If you want the records, an RTI application draft is ready for you.",
        "mr": " कागदपत्रे हवी असल्यास, RTI अर्जाचा मसुदा तयार आहे.",
        "hi": " यदि आप रिकॉर्ड चाहते हैं, तो RTI आवेदन का मसौदा तैयार है।",
    },
    "missing": {
        "en": "We don't have this information yet. You can file an RTI to ask for the records.",
        "mr": "ही माहिती आमच्याकडे अजून नाही. कागदपत्रे मागण्यासाठी तुम्ही RTI अर्ज करू शकता.",
        "hi": "यह जानकारी अभी हमारे पास नहीं है। रिकॉर्ड माँगने के लिए आप RTI आवेदन कर सकते हैं।",
    },
    "pick": {
        "en": "I found a few matching complaints. Please pick yours.",
        "mr": "काही जुळणाऱ्या तक्रारी सापडल्या. कृपया तुमची निवडा.",
        "hi": "कुछ मिलती-जुलती शिकायतें मिलीं। कृपया अपनी चुनें।",
    },
    "road": {
        "en": "Road {name} (segment {seg}): {repairs} repairs this season costing ₹{spent}; {failed} did not hold for 30 days (₹{failed_inr}). {dlp}",
        "mr": "रस्ता {name} (भाग {seg}): या हंगामात {repairs} दुरुस्त्या, खर्च ₹{spent}; {failed} 30 दिवस टिकल्या नाहीत (₹{failed_inr}). {dlp}",
        "hi": "सड़क {name} (खंड {seg}): इस मौसम में {repairs} मरम्मतें, लागत ₹{spent}; {failed} 30 दिन नहीं टिकीं (₹{failed_inr})। {dlp}",
    },
    "road_dlp": {
        "en": "The road is recorded as still under the contractor's Defect Liability Period.",
        "mr": "हा रस्ता अजून कंत्राटदाराच्या दोष दायित्व कालावधीत असल्याची नोंद आहे.",
        "hi": "यह सड़क अब भी ठेकेदार के दोष दायित्व काल में दर्ज है।",
    },
    "work_only": {
        "en": "Work order {wo} ({method}) was given to {contractor} and completed on {completed}. Cost billed: ₹{cost}. Target time met: {sla}. Reopened within 30 days: {reopened}.",
        "mr": "कामाचा आदेश {wo} ({method}) {contractor} यांना दिला आणि {completed} रोजी पूर्ण झाला. बिल केलेला खर्च: ₹{cost}. लक्ष्य वेळ पाळली: {sla}. 30 दिवसांत पुन्हा उघडले: {reopened}.",
        "hi": "कार्य आदेश {wo} ({method}) {contractor} को दिया गया और {completed} को पूरा हुआ। बिल की गई लागत: ₹{cost}। लक्ष्य समय पूरा हुआ: {sla}। 30 दिनों में दोबारा खुला: {reopened}।",
    },
}


def _date(s):
    return s[:10] if s else "-"


def answer_complaint(conn, cid: str, lang: str) -> dict | None:
    t = Fx.complaint_timeline(conn, cid, lang)
    if not t:
        return None
    cat = T.category(t["category"], lang)
    loc = t["location"]["locality"] or t["location"]["ward_code"] or "-"
    s = A["head"][lang].format(id=cid, category=cat, locality=loc, date=_date(t["received_at"]))
    if not t["category_verified"]:
        s += A["unverified"][lang]
    cites = [{"label": f"Complaint {cid}", **t["provenance"][0]}]
    w = t["work"]
    facts = {"complaint_id": cid, "received": _date(t["received_at"]), "link_status": t["link_status"]}
    if w:
        s += A["work"][lang].format(wo=w["work_order_id"], contractor=w["contractor_name"], completed=_date(w["completed_at"]),
                                    cost=T.inr(w["cost_inr"]), sla=Fx._yes(w["sla_met"], lang), reopened=Fx._yes(w["reopened_within_30d"], lang))
        if not t["directly_linked"] and t["issue"]:
            s += A["via_issue"][lang].format(n=t["issue"]["reported_times"])
        if w["road"] and w["road"]["under_dlp"]:
            s += A["dlp"][lang].format(road=w["road"]["road_name"])
        if w["cost_vs_rate_pct"] is not None and w["cost_vs_rate_pct"] > 30:
            s += A["over"][lang].format(pct=w["cost_vs_rate_pct"])
        cites.append({"label": f"Work order {w['work_order_id']}", **w["provenance"][0]})
        facts.update(work_order=w["work_order_id"], cost_inr=w["cost_inr"], completed=_date(w["completed_at"]),
                     sla_met=w["sla_met"], reopened=w["reopened_within_30d"], pct_over_rate=w["cost_vs_rate_pct"])
    elif t["link_status"] == "never_fixed":
        s += A["never"][lang].format(days=t["days_open"])
    elif t["link_status"] == "pending":
        s += A["pending"][lang].format(days=t["days_open"])
    elif t["link_status"] in ("closed_other", "duplicate", "resolved_no_record"):
        s += A["closed"][lang].format(status=t["status"])
    else:
        s = A["missing"][lang]
    if t["rti_suggested"]:
        s += A["rti"][lang]
    return {"answer": s, "citations": cites, "rti_suggested": t["rti_suggested"],
            "resolved": {"type": "complaint", "id": cid}, "facts": facts, "timeline": t}


def answer_work(conn, wo_id: str, lang: str) -> dict | None:
    w = Fx.work_detail(conn, wo_id, lang)
    if not w:
        return None
    s = A["work_only"][lang].format(wo=wo_id, method=w["repair_method"], contractor=w["contractor_name"], completed=_date(w["completed_at"]),
                                    cost=T.inr(w["cost_inr"]), sla=Fx._yes(w["sla_met"], lang), reopened=Fx._yes(w["reopened_within_30d"], lang))
    if w["road"] and w["road"]["under_dlp"]:
        s += A["dlp"][lang].format(road=w["road"]["road_name"])
    if w["cost_vs_rate_pct"] is not None and w["cost_vs_rate_pct"] > 30:
        s += A["over"][lang].format(pct=w["cost_vs_rate_pct"])
    rti = any(f["polarity"] == "concern" and f["rule"] in ("dlp_breach", "rate_card_overrun", "possible_double_billing") for f in w["findings"])
    if rti or w["reopened_within_30d"]:
        s += A["rti"][lang]
    return {"answer": s, "citations": [{"label": f"Work order {wo_id}", **w["provenance"][0]}], "rti_suggested": rti or w["reopened_within_30d"],
            "resolved": {"type": "work", "id": wo_id}, "facts": {"work_order": wo_id, "cost_inr": w["cost_inr"]}}


def answer_road(conn, rid: str, lang: str) -> dict | None:
    r = Fx.road_card(conn, rid, lang)
    if not r:
        return None
    s = A["road"][lang].format(name=r["road_name"], seg=r["segment_no"], repairs=r["repairs"], spent=T.inr(r["spent_inr"]),
                               failed=r["failed_repairs"], failed_inr=T.inr(r["failed_inr"]), dlp=A["road_dlp"][lang] if r["under_dlp"] else "")
    rti = r["failed_repairs"] > 0 or r["under_dlp"]
    if rti:
        s += A["rti"][lang]
    return {"answer": s.strip(), "citations": [{"label": f"Road {rid}", **r["provenance"][0]}], "rti_suggested": rti,
            "resolved": {"type": "road", "id": rid}, "facts": {"road": rid}}


def answer_ticket(conn, tid: str, lang: str) -> dict | None:
    """A complaint raised in the app (CMP-...): public facts only."""
    from live import text as LT
    from live import tickets as TK
    from live.common import LiveError
    try:
        x = TK.detail(conn, tid, None)
    except LiveError:
        return None
    s = LT.TICKET_ANSWER["head"][lang].format(id=tid, category=T.category(x["category"], lang), ward=x["ward_code"],
                                              date=_date(x["created_at"]), status=LT.STATUS[x["status"]][lang])
    if x["task"]:
        s += LT.TICKET_ANSWER["task"][lang].format(contractor=x["task"]["contractor_name"], task=x["task"]["task_id"])
        if x["task"].get("approved_cost_inr") is not None:
            s += LT.TICKET_ANSWER["cost"][lang].format(cost=T.inr(x["task"]["approved_cost_inr"]))
    return {"answer": s, "citations": [], "rti_suggested": False, "resolved": {"type": "ticket", "id": tid},
            "facts": {"ticket_id": tid, "status": x["status"]}}


_SYSTEM = (
    "You answer a Mumbai citizen's question about a road complaint, using ONLY the facts in the JSON. "
    "Never invent or compute new numbers. If something is not in the facts, say: 'We don't have this information yet' "
    "and mention an RTI can be filed. Describe facts only; never suggest wrongdoing; never use the words fraud, scam, "
    "suspicious, corrupt. Max 120 words. Plain text."
)


def _polish(question: str, base: dict, lang: str) -> str | None:
    payload = {"question": question, "facts": base["facts"], "draft_answer": base["answer"]}
    prompt = f"Reply in {_LANG_NAME[lang]}. Rewrite the draft answer so it directly addresses the question.\n{guard.payload_json(payload)}"
    res = cc.complete(config.MODEL_WRITER, _SYSTEM, prompt, agent="citizen-bot", version="v1", max_tokens=500, temperature=0.2)
    if not res:
        return None
    t = res.text.strip()
    if guard.numbers_ok(t, payload) and not guard.banned_words(t) and len(t.split()) <= 200:
        return t
    return None


def ask(conn, question: str, lang: str = "mr") -> dict:
    lang = detect_lang(question, lang) if DEV.search(question or "") else (lang if lang in T.LANGS else "en")
    r = resolve(conn, question)
    out = {"lang": lang, "question": question, "candidates": [], "citations": [], "rti_suggested": False, "source": "template"}
    base = None
    if r["type"] == "complaint":
        base = answer_complaint(conn, r["id"], lang)
    elif r["type"] == "work":
        base = answer_work(conn, r["id"], lang)
    elif r["type"] == "road":
        base = answer_road(conn, r["id"], lang)
    elif r["type"] == "ticket":
        base = answer_ticket(conn, r["id"], lang)
    elif r["type"] == "candidates":
        out.update(answer=A["pick"][lang], candidates=r["complaints"], resolved=r)
        return out
    elif r["type"] == "road_candidates":
        out.update(answer=A["pick"][lang], candidates=[{"road_id": x} for x in r["roads"]], resolved=r)
        return out
    if base is None:
        out.update(answer=A["missing"][lang], rti_suggested=True, resolved=r)
        return out
    text = base["answer"]
    if config.CLAUDE_ENABLED:
        p = _polish(question, base, lang)
        if p:
            text, out["source"] = p, "claude"
    out.update(answer=text, citations=base["citations"], rti_suggested=base["rti_suggested"], resolved=base["resolved"])
    return out

