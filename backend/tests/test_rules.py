"""Finding rules on hand-built fixtures: a positive and a negative case for each (SPEC §13.1)."""
import pandas as pd
import pytest

import db
from rules import findings as F


def _wo(id_, **kw):
    base = dict(work_order_id=id_, linked_complaint_ids="BMC25-000001", ward_code="K/E", road_id="RD1", work_type="Pothole",
                repair_method="Cold mix patch", contractor_id="CT01", contractor_name="X (synthetic)",
                assigned_at="2025-06-10 08:00", work_started_at="2025-06-10 12:00", completed_at="2025-06-11 08:00",
                area_sqm=10.0, cost_inr=18000, sla_hours=48, sla_met="Y", reopened_within_30d="N", engineer_remark="")
    base.update(kw)
    return base


def build(wos, *, dlp=False, low_lying=0.2, rain=None, complaints=None):
    c = db.connect(":memory:")
    db.init_schema(c)
    for i, w in enumerate(wos):
        w["_row"] = i + 2
    pd.DataFrame(wos).to_sql("work_orders", c, index=False)
    pd.DataFrame([dict(road_id="RD1", road_name="Test Rd", segment_no=1, ward_code="K/E", under_dlp="Y" if dlp else "N",
                       last_resurfaced="2024-01-01", _row=2)]).to_sql("roads", c, index=False)
    pd.DataFrame([dict(repair_method="Cold mix patch", unit="per sqm", standard_rate_inr=1800, _row=2),
                  dict(repair_method="Hot mix patch", unit="per sqm", standard_rate_inr=2600, _row=3)]).to_sql("rate_card", c, index=False)
    pd.DataFrame([dict(ward_code="K/E", low_lying_index=low_lying, monsoon_repair_budget_inr_2025=1)]).to_sql("wards", c, index=False)
    pd.DataFrame([dict(contractor_id="CT01", contractor_name="X (synthetic)")]).to_sql("contractors", c, index=False)
    comps = complaints or [dict(complaint_id="BMC25-000001", received_at="2025-06-10 06:00", _row=2)]
    pd.DataFrame(comps).to_sql("complaints", c, index=False)
    pd.DataFrame(rain or [dict(date="2025-06-01", station="Santacruz", imd_category="Light")]).to_sql("rainfall_daily", c, index=False)
    return c


def rules_for(c, wo_id):
    return {f["rule"]: f for f in F.compute(c) if f["subject_id"] == wo_id}


def test_overrun_positive_and_negative():
    c = build([_wo("A", cost_inr=int(18000 * 1.5)), _wo("B", cost_inr=int(18000 * 1.25)), _wo("C", cost_inr=18000)])
    assert "rate_card_overrun" in rules_for(c, "A")
    assert "rate_card_overrun" not in rules_for(c, "B")      # inside normal +/-30% variation
    assert "rate_card_overrun" not in rules_for(c, "C")


def test_overrun_threshold_relaxed_in_low_lying_ward_in_heavy_rain():
    rain = [dict(date=f"2025-06-{d:02d}", station="Santacruz", imd_category="Heavy") for d in range(4, 11)]
    w = _wo("A", cost_inr=int(18000 * 1.35))
    assert "rate_card_overrun" in rules_for(build([w], low_lying=0.2, rain=rain), "A")        # strict threshold
    f = rules_for(build([_wo("A", cost_inr=int(18000 * 1.35))], low_lying=0.8, rain=rain), "A")
    assert "rate_card_overrun" not in f                                                        # relaxed to 1.40


def test_overrun_metrics_and_evidence():
    c = build([_wo("A", cost_inr=int(18000 * 1.5))])
    f = rules_for(c, "A")["rate_card_overrun"]
    import json
    m = json.loads(f["metrics_json"])
    assert m["pct_above"] == 50 and m["expected_inr"] == 18000
    ev = json.loads(f["evidence_json"])
    assert {e["table"] for e in ev} == {"work_orders", "rate_card"} and all(e["row"] for e in ev)


def test_double_billing():
    a = _wo("A", linked_complaint_ids="BMC25-000001", assigned_at="2025-06-10 08:00", completed_at="2025-06-11 08:00")
    b = _wo("B", linked_complaint_ids=None, assigned_at="2025-06-13 08:00", completed_at="2025-06-14 08:00")
    assert "possible_double_billing" in rules_for(build([a, b]), "B")
    # negative: the second one has a linked complaint
    b2 = _wo("B", linked_complaint_ids="BMC25-000002", assigned_at="2025-06-13 08:00", completed_at="2025-06-14 08:00")
    comps = [dict(complaint_id="BMC25-000001", received_at="2025-06-10 06:00", _row=2), dict(complaint_id="BMC25-000002", received_at="2025-06-13 06:00", _row=3)]
    assert "possible_double_billing" not in rules_for(build([a, b2], complaints=comps), "B")
    # negative: far apart in time
    b3 = _wo("B", linked_complaint_ids=None, assigned_at="2025-07-13 08:00", completed_at="2025-07-14 08:00")
    assert "possible_double_billing" not in rules_for(build([a, b3]), "B")
    # negative: different work type
    b4 = _wo("B", linked_complaint_ids=None, work_type="Waterlogging", assigned_at="2025-06-13 08:00", completed_at="2025-06-14 08:00")
    assert "possible_double_billing" not in rules_for(build([a, b4]), "B")


def test_dlp_breach_and_severity():
    assert "dlp_breach" in rules_for(build([_wo("A")], dlp=True), "A")
    assert "dlp_breach" not in rules_for(build([_wo("A")], dlp=False), "A")
    assert rules_for(build([_wo("A")], dlp=True), "A")["dlp_breach"]["severity"] == "medium"          # surface repair
    assert rules_for(build([_wo("A", work_type="Waterlogging")], dlp=True), "A")["dlp_breach"]["severity"] == "low"


def test_sla_and_failed():
    f = rules_for(build([_wo("A", sla_met="N", completed_at="2025-06-20 08:00", reopened_within_30d="Y")]), "A")
    assert "sla_missed" in f and "failed_within_30d" in f
    f = rules_for(build([_wo("A")]), "A")
    assert "sla_missed" not in f and "failed_within_30d" not in f


def test_failed_lower_severity_after_heavy_rain():
    rain = [dict(date=f"2025-06-{d:02d}", station="Santacruz", imd_category="Very heavy") for d in range(11, 15)]
    f = rules_for(build([_wo("A", reopened_within_30d="Y")], rain=rain), "A")["failed_within_30d"]
    assert f["severity"] == "low"


def test_estimate_drift():
    base = [_wo(f"W{i}", cost_inr=18000) for i in range(6)]
    odd = _wo("ODD", cost_inr=int(18000 * 1.28))      # +28%: drift (>20%) but not an overrun (<30%)
    f = rules_for(build(base + [odd]), "ODD")
    assert "estimate_drift" in f and "rate_card_overrun" not in f
    assert "estimate_drift" not in rules_for(build(base + [odd]), "W1")


def _clean_set(n=4, **kw):
    return [_wo(f"W{i}", linked_complaint_ids=f"BMC25-00000{i}", **kw) for i in range(1, n + 1)]


def _comps(n=4):
    return [dict(complaint_id=f"BMC25-00000{i}", received_at="2025-06-10 06:00", _row=i + 1) for i in range(1, n + 1)]


def test_clean_record_positive_and_negative():
    c = build(_clean_set(), complaints=_comps())
    cr = [f for f in F.compute(c) if f["rule"] == "clean_record"]
    assert len(cr) == 1 and cr[0]["polarity"] == "positive" and cr[0]["subject_id"] == "CT01@K/E"
    # fewer than 3 completed works -> no certificate
    assert not [f for f in F.compute(build(_clean_set(2), complaints=_comps(2))) if f["rule"] == "clean_record"]
    # one overrun spoils it
    ws = _clean_set()
    ws[0]["cost_inr"] = int(18000 * 1.8)
    assert not [f for f in F.compute(build(ws, complaints=_comps())) if f["rule"] == "clean_record"]
    # too slow
    ws = _clean_set()
    for w in ws[:2]:
        w["sla_met"] = "N"
    assert not [f for f in F.compute(build(ws, complaints=_comps())) if f["rule"] == "clean_record"]


@pytest.mark.parametrize("rule,low,high", [("rate_card_overrun", 90, 140), ("possible_double_billing", 40, 60), ("dlp_breach", 400, 600)])
def test_real_data_counts_in_expected_range(conn, rule, low, high):
    n = db.one(conn, "SELECT COUNT(*) n FROM finding WHERE rule=?", (rule,))["n"]
    assert low <= n <= high
