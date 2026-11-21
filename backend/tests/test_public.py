"""Public/officer separation, neutral language, privacy, number guard, scorecard fairness (SPEC §13.1)."""
import json

import pytest

import db
from agents import guard, scorecard
from rules import text as T

PUBLIC_PATHS = [
    "/api/meta", "/api/wards", "/api/wards/K-E/money-trail?lang=en", "/api/wards/K-E/priorities?lang=en",
    "/api/works?ward=K-E&limit=5", "/api/works/WO25-00017?lang=en", "/api/roads/RD0119", "/api/complaints/BMC25-000037?lang=en",
    "/api/contractors", "/api/contractors/CT03/scorecard?lang=en", "/api/findings?limit=100", "/api/works/near?lat=19.1&lon=72.87",
]
FORBIDDEN_KEYS = {"flag_label", "complainant_id", "officer_label", "noting", "photo_url", "description"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_routes_expose_no_officer_or_pii_fields(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert not (set(_keys(r.json())) & FORBIDDEN_KEYS), path
    assert "Risk flag" not in r.text


def test_officer_and_audit_routes_are_gated(client, tokens):
    for path in ("/api/officer/flags", "/api/officer/review-queue", "/api/audit", "/api/audit/verify", "/api/audit/export"):
        assert client.get(path).status_code == 401                                   # not logged in
        assert client.get(path, headers={"X-Role": "officer"}).status_code == 401    # a self-declared role is ignored
        assert client.get(path, headers=tokens["citizen"]).status_code == 403
        assert client.get(path, headers=tokens["ct05"]).status_code == 403
        assert client.get(path, headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401
    assert client.get("/api/officer/flags?limit=1", headers=tokens["officer"]).status_code == 200
    assert client.get("/api/audit?limit=1", headers=tokens["auditor"]).status_code == 200
    assert client.post("/api/officer/draft-noting/WO25-00017", headers=tokens["citizen"]).status_code == 403


def test_officer_findings_use_risk_flag_framing(client, tokens):
    items = client.get("/api/officer/flags?limit=5", headers=tokens["officer"]).json()["items"]
    assert items and all(i["flag_label"] for i in items)


def test_no_banned_words_in_any_public_text(conn):
    for lang in T.LANGS:
        for rule, tpl in T.TEMPLATES.items():
            assert not guard.banned_words(tpl[lang]), (rule, lang)
    for col in ("public_text_en", "public_text_mr", "public_text_hi"):
        for r in db.rows(conn, f"SELECT {col} t FROM finding"):
            assert not guard.banned_words(r["t"])
    assert "red flag" in guard.BANNED_PUBLIC and guard.banned_words("This looks like fraud")


def test_every_finding_has_evidence_and_all_three_languages(conn):
    for r in db.rows(conn, "SELECT * FROM finding"):
        assert json.loads(r["evidence_json"]), r["finding_id"]
        assert r["public_text_en"] and r["public_text_mr"] and r["public_text_hi"]
        assert r["rule_version"]


def test_number_guard():
    payload = {"billed_inr": 2450000, "sla_pct": 47, "name": "ABC", "ratio": 0.38}
    assert guard.numbers_ok("47% were on time and ₹24,50,000 was billed", payload)
    assert guard.numbers_ok("लक्ष्य वेळेत ४७% कामे", payload)
    assert guard.numbers_ok("about 38% reopened", payload)
    assert not guard.numbers_ok("52% were on time", payload)                       # fabricated
    assert not guard.numbers_ok("₹99,999 was billed", payload)
    assert guard.unsupported_numbers("47% and 61%", payload) == ["61"]


def test_scorecards_have_a_transparent_score_but_no_grade_or_rank(client):
    """The product shows ONE transparent 0-100 score per contractor (agents/score.py: fixed weights over three published
    measures, context-adjusted, always shown with its inputs). It still never ranks, grades or letter-rates contractors."""
    for cid in ("CT01", "CT03", "CT05"):
        j = client.get(f"/api/contractors/{cid}/scorecard?lang=en").json()
        assert not (set(_keys(j)) & {"grade", "rank", "rating", "stars"})
        assert j["score"]["score"] is not None and j["score"]["weights"] and j["score"]["context_adjusted"]
        assert j["narrative"]["text"] and not guard.banned_words(j["narrative"]["text"])
        assert guard.numbers_ok(j["narrative"]["text"], j["metrics"])
    rows = client.get("/api/contractors").json()
    names = [c["name"] for c in rows]
    assert names == sorted(names)                                                    # alphabetical, never ordered by score
    assert [c["score"]["score"] for c in rows] != sorted((c["score"]["score"] for c in rows), reverse=True)


def test_scorecard_does_not_praise_a_contractor_below_expectation(conn):
    """Derive the expectation independently from the published numbers, not from the code under test."""
    saw_no_strength = saw_strength = 0
    for cid in ("CT01", "CT02", "CT03", "CT04", "CT05", "CT06", "CT07", "CT08"):
        card = scorecard.contractor_scorecard(conn, cid)
        m = card["metrics"]
        text = scorecard.contractor_narrative(conn, card, "en")["text"]
        gaps = [m["sla_pct"] - m["expected_sla_pct"], m["expected_reopen_pct"] - m["reopen_pct"], m["within_rate_pct"] - 95]
        if max(gaps) < -1:                     # below expectation on every measure -> must not be called a strength
            assert "Strength:" not in text, cid
            saw_no_strength += 1
        if max(gaps) > 1:
            assert "Strength:" in text, cid
            saw_strength += 1
        if min(gaps) > 1:                      # at/above expectation everywhere -> nothing "to improve"
            assert "To improve:" not in text, cid
    assert saw_no_strength >= 1 and saw_strength >= 1, "fixture data must exercise both branches"


def test_context_adjustment_is_visible_in_scorecard(client):
    j = client.get("/api/contractors/CT03/scorecard?lang=en").json()
    assert "expected" in j["context_note"].lower()
    m = j["metrics"]
    assert "expected_sla_pct" in m and "expected_reopen_pct" in m


def test_complaint_timeline_is_pii_free_and_rounded(client, conn):
    cid = db.one(conn, "SELECT complaint_id FROM complaints WHERE lat IS NOT NULL LIMIT 1")["complaint_id"]
    j = client.get(f"/api/complaints/{cid}").json()
    lat = j["location"]["lat"]
    assert lat is None or round(lat, 3) == lat
    raw = db.one(conn, "SELECT complainant_id FROM complaints WHERE complaint_id=?", (cid,))["complainant_id"]
    assert raw not in json.dumps(j)


def test_source_endpoint_redacts_complaint_pii(client, conn):
    row = db.one(conn, "SELECT _row, complainant_id FROM complaints LIMIT 1")
    j = client.get(f"/api/source/complaints.csv/{row['_row']}").json()
    assert "complainant_id" not in j["data"] and "description" not in j["data"] and len(j["sha256"]) == 64


def test_ask_bot_and_rti(client, conn):
    never = db.one(conn, "SELECT complaint_id FROM parsed_complaint WHERE link_status='never_fixed' LIMIT 1")["complaint_id"]
    j = client.post("/api/ask", json={"question": f"what happened to {never}?", "lang": "en"}).json()
    assert "No repair has been linked" in j["answer"] and j["rti_suggested"] and not guard.banned_words(j["answer"])
    j = client.post("/api/ask", json={"question": "tell me about ZZZ nothing", "lang": "en"}).json()
    assert "don't have this information" in j["answer"]
    r = client.post("/api/rti-draft", json={"complaint_id": never}).json()
    assert "Section 6(1)" in r["text_en"] and "कलम 6(1)" in r["text_mr"] and r["fee_inr"] == 10 and r["reply_due_days"] == 30
    assert "verify" in r["disclaimer"]["en"].lower()
    assert not guard.banned_words(r["text_en"] + r["text_mr"])
    assert "fraud" not in r["text_en"].lower()


def test_audit_chain_and_export(client, tokens):
    h = tokens["auditor"]
    v = client.get("/api/audit/verify", headers=h).json()
    assert v["ok"] and v["checked"] > 20000
    ch = client.get("/api/audit/WO25-00017/chain", headers=h).json()
    assert ch["all_hashes_ok"] and ch["facts"]
    ex = client.get("/api/audit/export?format=csv&ward=K/E", headers=h)
    assert ex.headers["x-chain-ok"] == "true" and "row_hash" in ex.text.splitlines()[0] and "prompt_hash" in ex.text.splitlines()[0]
    a = client.get("/api/audit?ward=K/E&field=cost_inr&limit=3", headers=h).json()
    assert a["items"] and all(i["field_path"] == "cost_inr" and i["source_file"] == "work_orders.csv" for i in a["items"])


def test_right_of_reply_round_trip(client, tokens):
    f = client.get("/api/findings?rule=rate_card_overrun&limit=1").json()[0]
    assert f["reply"] is None
    assert client.post("/api/officer/reply", json={"finding_id": f["finding_id"], "reply_text": "Site conditions differed."},
                       headers=tokens["officer"]).status_code == 200
    again = client.get(f"/api/findings?rule=rate_card_overrun&limit=1").json()[0]
    assert again["reply"]["text"] == "Site conditions differed."


def test_timeline_is_chronological_and_flags_reports_filed_after_the_work(client, conn):
    late = db.one(conn, "SELECT p.complaint_id FROM parsed_complaint p JOIN complaints c USING(complaint_id) "
                        "JOIN work_orders w ON w.work_order_id=p.work_order_id "
                        "WHERE p.link_status IN ('fixed','fixed_failed') AND c.received_at > w.completed_at LIMIT 1")["complaint_id"]
    ontime = db.one(conn, "SELECT p.complaint_id FROM parsed_complaint p JOIN complaints c USING(complaint_id) "
                          "JOIN work_orders w ON w.work_order_id=p.work_order_id "
                          "WHERE p.link_status IN ('fixed','fixed_failed') AND c.received_at <= w.completed_at LIMIT 1")["complaint_id"]
    for cid, expect in ((late, True), (ontime, False)):
        j = client.get(f"/api/complaints/{cid}").json()
        ats = [e["at"] for e in j["events"]]
        assert ats == sorted(ats), "events must never contradict each other"
        assert j["filed_after_completion"] is expect
