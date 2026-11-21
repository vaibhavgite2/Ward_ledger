"""Loader, append-only facts, hash chain, linker, geocoder, budget, noting (SPEC §13.1)."""
import json
import sqlite3

import pytest

import db
from agents import budget, geocoder, linker, noting
from rules import promote as P


def test_loader_counts_match_data_dictionary(conn):
    expect = {"work_orders": 2499, "complaints": 6501, "roads": 291, "wards": 24, "contractors": 8, "rate_card": 10,
              "localities": 118, "flood_hotspots": 28, "traffic": 291, "accidents": 420, "facilities": 160, "social_posts": 650}
    for t, n in expect.items():
        assert db.one(conn, f"SELECT COUNT(*) n FROM {t}")["n"] == n, t
    assert db.one(conn, "SELECT COUNT(*) n FROM source_doc WHERE length(doc_id)=64")["n"] >= 14


def test_every_source_fact_cites_a_file_hash_and_row(conn):
    bad = db.one(conn, "SELECT COUNT(*) n FROM fact WHERE promoted_by LIKE 'rule:source-csv%' AND (source_doc IS NULL OR source_row IS NULL)")["n"]
    assert bad == 0


def test_rerun_is_a_noop(built_db):
    from pipeline import run
    c = db.connect(built_db)
    assert run.run(conn=c, quiet=True) == {"skipped": True}
    c.close()


def test_facts_are_append_only(conn):
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE fact SET value_json='1' WHERE seq=1")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM fact WHERE seq=1")


def test_hash_chain_verifies_and_detects_tampering(db_copy):
    assert P.verify_chain(db_copy)["ok"]
    db_copy.execute("DROP TRIGGER fact_no_update")
    db_copy.execute("UPDATE fact SET value_json='999999' WHERE seq=(SELECT seq FROM fact WHERE field_path='cost_inr' LIMIT 1 OFFSET 10)")
    db_copy.commit()
    v = P.verify_chain(db_copy)
    assert v["ok"] is False and v["first_broken_seq"] is not None


def test_human_promotion_appends_a_new_fact_with_named_officer(client, conn, tokens):
    item = client.get("/api/officer/review-queue?limit=1", headers=tokens["officer"]).json()["items"][0]
    before = db.one(conn, "SELECT COUNT(*) n FROM fact")["n"]
    r = client.post(f"/api/officer/review/{item['item_id']}", json={"action": "approve"}, headers=tokens["officer"])
    assert r.status_code == 200 and r.json()["decided_by"] == "user:ae-4471"
    c2 = db.connect()
    assert db.one(c2, "SELECT COUNT(*) n FROM fact")["n"] == before + 1
    assert db.one(c2, "SELECT promoted_by FROM fact ORDER BY seq DESC LIMIT 1")["promoted_by"] == "user:ae-4471"
    assert P.verify_chain(c2)["ok"]
    c2.close()


def test_claude_output_is_never_a_fact_without_a_rule(conn):
    # every category fact must come from a rule (or a named human), and cite its claim
    rows = db.rows(conn, "SELECT promoted_by, from_claim FROM fact WHERE field_path='category'")
    assert rows and all(r["from_claim"] and (r["promoted_by"].startswith("rule:") or r["promoted_by"].startswith("user:")) for r in rows)
    # unverified claims are queued, not promoted
    assert db.one(conn, "SELECT COUNT(*) n FROM review_queue")["n"] > 0


def test_blank_wards_are_filled(conn):
    assert db.one(conn, "SELECT COUNT(*) n FROM parsed_complaint WHERE ward_code IS NULL")["n"] == 0
    assert db.one(conn, "SELECT COUNT(*) n FROM complaints WHERE ward_code IS NULL")["n"] > 300


def test_geocoder_handles_truncated_names_and_devanagari(conn):
    gaz = geocoder.Gazetteer(db.rows(conn, "SELECT * FROM localities"))
    assert gaz.lookup("Grant")[0] is not None and gaz.lookup("Grant")[1] == "gazetteer-prefix"
    p, method, *_ = gaz.lookup("परळ")
    assert p.locality == "Parel" and method == "gazetteer"
    assert gaz.lookup("zzzzzz qqqq")[0] is None


def test_linker_never_merges_two_work_orders():
    base = dict(status="Resolved", upvotes=0, category="Pothole", ward_code="K/E", lat=19.1, lon=72.9, uncertainty_m=10,
                locality_resolved="Andheri", road_id=None)
    cs = [dict(base, complaint_id="C1", received_at="2025-06-01 08:00"), dict(base, complaint_id="C2", received_at="2025-06-01 09:00")]
    wos = [dict(work_order_id="W1", linked_complaint_ids="C1", reopened_within_30d="N", sla_hours=48, road_id="R", ward_code="K/E"),
           dict(work_order_id="W2", linked_complaint_ids="C2", reopened_within_30d="N", sla_hours=48, road_id="R", ward_code="K/E")]
    per, issues = linker.link(cs, wos)
    assert per["C1"]["issue_id"] != per["C2"]["issue_id"]
    # ... but unlinked near-duplicates do cluster
    per, issues = linker.link([dict(cs[0], status="Open"), dict(cs[1], status="Open")], [])
    assert per["C1"]["issue_id"] == per["C2"]["issue_id"] and issues[0]["complaint_count"] == 2


def test_issue_counts_reconcile(conn):
    linked = db.one(conn, "SELECT COUNT(*) n FROM work_orders WHERE linked_complaint_ids IS NOT NULL")["n"]
    assert db.one(conn, "SELECT COUNT(*) n FROM issue WHERE work_order_id IS NOT NULL")["n"] == linked
    assert db.one(conn, "SELECT COUNT(*) n FROM parsed_complaint WHERE issue_id IS NULL")["n"] == 0


def test_budget_allocation_cap_and_dlp(conn):
    ref = budget.Ref(conn)
    for ward in ref.wards:
        plan = budget.plan_ward(conn, ward, ref=ref)
        assert plan["allocated_inr"] <= plan["allocatable_inr"] + 1
        assert plan["allocatable_inr"] <= max(0, plan["remaining_inr"]) * 0.8 + 1
        for it in plan["items"]:
            if it["under_dlp"]:
                assert it["bmc_cost_inr"] == 0 and it["action"] == "warranty"
            assert 0 <= it["score"] <= 1
        scores = [it["score"] for it in plan["items"]]
        assert scores == sorted(scores, reverse=True)


def test_budget_ranking_is_stable(conn):
    ref = budget.Ref(conn)
    a = [i["issue_id"] for i in budget.plan_ward(conn, "K/E", ref=ref)["items"]]
    b = [i["issue_id"] for i in budget.plan_ward(conn, "K/E", ref=ref)["items"]]
    assert a == b


def test_budget_prefers_durable_method_and_excludes_cold_mix_on_busy_roads(conn):
    ref = budget.Ref(conn)
    best, opts = budget._method_for(ref, "Pothole", "K/E", high_traffic=True, rain_risk=0.0)
    assert "Cold mix patch" not in [o["method"] for o in opts]
    assert opts == sorted(opts, key=lambda o: (o["reopen_pct"], o["unit_rate_inr"]))


def test_rain_raises_rain_factor(conn):
    ref = budget.Ref(conn)
    dry = budget.plan_ward(conn, "K/E", ref=ref)["items"][0]["factors"]["R"]
    wet = budget.plan_ward(conn, "K/E", as_of="2025-07-08", ref=ref)["items"][0]["factors"]["R"]
    assert wet > dry


def test_noting_blocks_unsourced_paragraphs():
    kept, blocked = noting.enforce_citations(
        [{"kind": "flag", "text": "no cite", "citations": []},
         {"kind": "flag", "text": "bad cite", "citations": [{"id": "ZZ"}]},
         {"kind": "work", "text": "ok", "citations": [{"id": "A"}]},
         {"kind": "officer_input", "text": "decide", "citations": []}], {"A"})
    assert [p["text"] for p in kept] == ["ok", "decide"] and len(blocked) == 2


def test_real_noting_every_assertion_cited_and_balanced(conn):
    wo = db.one(conn, "SELECT subject_id FROM finding WHERE rule='dlp_breach' AND subject_id IN "
                      "(SELECT subject_id FROM finding WHERE rule='failed_within_30d') LIMIT 1")["subject_id"]
    for lang in ("en", "mr"):
        d = noting.draft(conn, wo, lang)
        assert d["submitted"] is False and not d["blocked"]
        for p in d["paras"]:
            assert p["kind"] == "officer_input" or (p["citations"] and all(c["sha256"] for c in p["citations"]))
        assert any(p["kind"] == "context" for p in d["paras"])
        assert d["paras"][-1]["kind"] == "officer_input"        # the recommendation is the officer's to make
    assert db.one(conn, "SELECT COUNT(*) n FROM fact WHERE field_path LIKE '%noting%'")["n"] == 0
    _ = json


def test_planner_ref_is_safe_under_concurrent_first_requests(built_db):
    """Regression: a half-published cache made concurrent first requests raise KeyError (HTTP 500)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from app import deps

    deps._REF.clear()
    barrier = threading.Barrier(8)

    def call(_):
        c = db.connect(built_db)
        try:
            barrier.wait()
            return deps.planner_ref(c)
        finally:
            c.close()

    with ThreadPoolExecutor(8) as ex:
        refs = list(ex.map(call, range(8)))          # any exception propagates here
    assert len({id(r) for r in refs}) == 1            # one shared reference object, built once


def test_priorities_endpoint_survives_parallel_requests(client):
    from concurrent.futures import ThreadPoolExecutor
    from app import deps
    deps._REF.clear()
    with ThreadPoolExecutor(6) as ex:
        codes = list(ex.map(lambda i: client.get("/api/wards/K-E/priorities?limit=3&lang=" + ("mr", "en")[i % 2]).status_code, range(6)))
    assert codes == [200] * 6
