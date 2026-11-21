"""Tasks: DFD 4.0 Assign Contractor, 5.0 Submit Repair Report, 6.0 Review & Update Status.

An officer bundles one or more VERIFIED complaints into a task for one contractor. The contractor starts
the work and submits a repair report (evidence, bill, resolution summary). The officer approves it, which
resolves EVERY complaint in the task (and complaints marked as duplicates of them), or sends it back.

Task status: assigned -> in_progress -> submitted -> completed
                                   ^------ rework <--/ (officer sends back)
             assigned | in_progress | rework -> cancelled (complaints return to 'verified')

Before assignment the officer sees pre-award checks from the existing evidence base (the Risk Flagger):
the contractor's on-time and durability record against what is expected, past bills against the rate card,
findings in this ward, and roads still under another contractor's warranty. On submission, the bill is
checked against the standard rate and the task estimate. All checks are neutral statements, not verdicts.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
import db
from agents import budget as B
from agents import scorecard as SC
from agents.linker import SLA_BY_SEVERITY
from live import events, mailer, media, notify
from live import text as LT
from live.common import LiveError, Viewer, next_id, now_iso
from live import tickets as TK
from rules import text as T

IST = timezone(timedelta(hours=5, minutes=30))     # a due date typed without a time zone is Mumbai time

STATUSES = ("assigned", "in_progress", "submitted", "rework", "completed", "cancelled")
ACTIVE = ("assigned", "in_progress", "submitted", "rework")
OWED = ("assigned", "in_progress", "rework")          # the contractor still owes the work (not waiting on the officer)
MAX_TICKETS = 50
MAX_EVIDENCE, MAX_BILLS = 8, 3
OVER = config.RULES["rate_card_overrun"]["ratio"]


def _officer(v):
    if v is None or v.role != "officer":
        raise LiveError(403, "officers_only", "Only ward officers can do this.")
    if not v.can_act:
        raise LiveError(403, "read_only", "This officer account is read-only (audit) and cannot change records.")


def _contractor(v):
    if v is None or v.role != "contractor":
        raise LiveError(403, "contractors_only", "Only contractors can do this.")


def _get(conn, task_id):
    k = db.one(conn, "SELECT * FROM task WHERE task_id=?", (task_id,))
    if not k:
        raise LiveError(404, "not_found", "No task with that ID.")
    return k


def _own(k, v):
    if v.role != "contractor" or k["contractor_id"] != v.contractor_id:
        raise LiveError(403, "not_your_task", "This task is assigned to another contractor.")


def _ticket_ids(conn, task_id):
    return [r["ticket_id"] for r in db.rows(conn, "SELECT ticket_id FROM task_ticket WHERE task_id=? ORDER BY ticket_id", (task_id,))]


def _check(code, tone, lang, **params):
    return {"code": code, "tone": tone, "params": params, "text": LT.render(LT.CHECK, code, params, lang)}


def _render_checks(stored: list, lang: str) -> list:
    return [{**c, "text": LT.render(LT.CHECK, c["code"], c.get("params", {}), lang)} for c in stored or []]


def _expected_cost(rate_row, method, area, n_jobs):
    if not rate_row:
        return None, None
    if rate_row["unit"] == "per sqm":
        if not area:
            return None, None
        return rate_row["standard_rate_inr"] * area, f"{area:g} sqm"
    return rate_row["standard_rate_inr"] * n_jobs, f"{n_jobs} job(s)"


# ---- pre-award (DFD 4.0, Risk Flagger) --------------------------------------------------------------
def _load_tickets_for_task(conn, ticket_ids) -> list[dict]:
    ids = list(dict.fromkeys(i.strip().upper() for i in ticket_ids or [] if i and i.strip()))
    if not ids:
        raise LiveError(422, "no_tickets", "Select at least one verified complaint.")
    if len(ids) > MAX_TICKETS:
        raise LiveError(422, "too_many_tickets", f"A task can hold at most {MAX_TICKETS} complaints.")
    q = ",".join("?" * len(ids))
    rows = db.rows(conn, f"SELECT * FROM ticket WHERE ticket_id IN ({q})", ids)
    found = {r["ticket_id"] for r in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise LiveError(404, "not_found", f"Unknown complaint(s): {', '.join(missing)}")
    bad = [r["ticket_id"] for r in rows if r["status"] != "verified"]
    if bad:
        raise LiveError(409, "not_verified", f"Only verified complaints that are not already in a task can be assigned: {', '.join(bad)}")
    if len({r["ward_code"] for r in rows}) > 1:
        raise LiveError(422, "mixed_wards", "All complaints in a task must be in the same ward.")
    return rows


def preview(conn, ref: B.Ref, contractor_id: str, ticket_ids, lang: str = "en") -> dict:
    c = db.one(conn, "SELECT * FROM contractors WHERE contractor_id=?", (contractor_id,))
    if not c:
        raise LiveError(404, "not_found", "Unknown contractor.")
    tickets = _load_tickets_for_task(conn, ticket_ids)
    ward = tickets[0]["ward_code"]
    checks = []
    card = SC.contractor_scorecard(conn, contractor_id)
    if card:
        m = card["metrics"]
        d = m["sla_pct"] - m["expected_sla_pct"]
        checks.append(_check("ct_sla", "concern" if d < -5 else "positive" if d > 5 else "info", lang,
                             sla=m["sla_pct"], exp=m["expected_sla_pct"]))
        d = m["reopen_pct"] - m["expected_reopen_pct"]
        checks.append(_check("ct_reopen", "concern" if d > 5 else "positive" if d < -5 else "info", lang,
                             reopen=m["reopen_pct"], exp=m["expected_reopen_pct"]))
        share = m["overrun_jobs"] / m["completed"] if m["completed"] else 0
        checks.append(_check("ct_overrun", "concern" if share > 0.05 else "info", lang, n=m["overrun_jobs"], total=m["completed"]))
        if ward in m["clean_record_wards"]:
            checks.append(_check("ct_clean", "positive", lang, ward=ward))
    fr = db.rows(conn, "SELECT rule, COUNT(*) n FROM finding WHERE contractor_id=? AND ward_code=? AND polarity='concern' "
                       "AND rule IN ('rate_card_overrun','possible_double_billing','estimate_drift') GROUP BY rule", (contractor_id, ward))
    if fr:
        lst = ", ".join(f"{T.RULE_TITLES[r['rule']][lang if lang in T.LANGS else 'en']} ({r['n']})" for r in fr)
        checks.append(_check("ct_findings", "concern", lang, ward=ward, list=lst))
    dlp_roads = []
    for t in tickets:
        road = TK._road(conn, t["road_id"])
        if road and road["under_dlp"] and road["road_name"] not in dlp_roads:
            dlp_roads.append(road["road_name"])
            checks.append(_check("dlp_road", "concern", lang, road=f"{road['road_name']} ({road['road_id']})"))

    cat = Counter(t["category"] for t in tickets).most_common(1)[0][0]
    high_traffic = False
    for t in tickets:
        tr = ref.traffic.get(t["road_id"]) if t["road_id"] else None
        rd = ref.roads.get(t["road_id"]) if t["road_id"] else None
        if (tr and tr["congestion_index_0_10"] >= config.RULES["budget"]["hot_traffic_congestion"]) or (rd and rd["bus_route"] == "Y"):
            high_traffic = True
    best, opts = B._method_for(ref, cat, ward, high_traffic, 0.0) if cat in config.RULES["methods_by_category"] else (None, [])
    n = len(tickets)
    area = cost = None
    if best:
        if best["unit"] == "per sqm":
            per = ref.median_area.get((ward, cat)) or ref.median_area.get(("*", cat)) or 5.0
            area = round(per * n, 1)
            cost = round(best["unit_rate_inr"] * area)
        else:
            cost = round(best["unit_rate_inr"] * n)
    sev = max(config.RULES["budget"]["category_severity"].get(t["category"], 1) for t in tickets)
    due = (datetime.now(timezone.utc) + timedelta(hours=SLA_BY_SEVERITY[sev])).isoformat(timespec="minutes")
    return {"ward_code": ward, "contractor": {"contractor_id": contractor_id, "name": c["contractor_name"]},
            "tickets": [TK.summary(conn, t, None) for t in tickets], "checks": checks,
            "suggested": {"category": cat, "repair_method": best["method"] if best else None, "alternatives": opts,
                          "est_area_sqm": area, "est_cost_inr": cost, "due_at": due, "sla_hours": SLA_BY_SEVERITY[sev],
                          "high_traffic": high_traffic}}


def create(conn, viewer: Viewer, ref: B.Ref, *, contractor_id: str, ticket_ids, repair_method=None, est_area_sqm=None,
           est_cost_inr=None, due_at=None, instructions=None, title=None) -> str:
    _officer(viewer)
    pv = preview(conn, ref, contractor_id, ticket_ids, "en")            # validates contractor + tickets
    sug = pv["suggested"]
    method = repair_method or sug["repair_method"]
    if method and not db.one(conn, "SELECT 1 FROM rate_card WHERE repair_method=?", (method,)):
        raise LiveError(422, "bad_method", "Choose a repair method from the rate card.")
    try:
        area = sug["est_area_sqm"] if est_area_sqm in (None, "") else max(0.0, min(100000.0, float(est_area_sqm)))
        cost = sug["est_cost_inr"] if est_cost_inr in (None, "") else max(0.0, min(1e9, float(est_cost_inr)))
    except (TypeError, ValueError):
        raise LiveError(422, "bad_number", "Area and cost must be numbers.")
    due = due_at or sug["due_at"]
    try:
        datetime.fromisoformat(due)
    except (TypeError, ValueError):
        raise LiveError(422, "bad_due", "Due date is not a valid date.")
    ids = [t["ticket_id"] for t in pv["tickets"]]
    ward = pv["ward_code"]
    with db.write_tx(conn):
        # re-check inside the write lock: no two officers can put the same complaint in two tasks
        _load_tickets_for_task(conn, ids)
        task_id = next_id(conn, "task", "TSK")
        ts = now_iso()
        ttl = (title or "").strip()[:120] or f"{T.category(sug['category'], 'en')} repair, ward {ward} ({len(ids)} complaint(s))"
        conn.execute("INSERT INTO task(task_id, contractor_id, ward_code, title, instructions, repair_method, est_area_sqm, est_cost_inr, "
                     "due_at, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (task_id, contractor_id, ward, ttl, (instructions or "").strip()[:2000] or None, method, area, cost, due,
                      "assigned", viewer.actor_ref, ts, ts))
        for tid in ids:
            conn.execute("INSERT INTO task_ticket VALUES (?,?)", (task_id, tid))
            conn.execute("UPDATE ticket SET status='assigned', task_id=?, updated_at=? WHERE ticket_id=?", (task_id, ts, tid))
            events.append(conn, "ticket", tid, "assigned", "officer", viewer.actor_ref, from_status="verified", to_status="assigned",
                          data={"task_id": task_id, "contractor_id": contractor_id})
        events.append(conn, "task", task_id, "created", "officer", viewer.actor_ref, to_status="assigned",
                      data={"contractor_id": contractor_id, "tickets": ids, "repair_method": method, "est_cost_inr": cost,
                            "due_at": due, "pre_award_checks": [{"code": c["code"], "tone": c["tone"]} for c in pv["checks"]]})
        notify.notify(conn, notify.contractor_users(conn, contractor_id), "task_assigned", "task", task_id,
                      task_id=task_id, n=len(ids), ward=ward, due=due[:10])
        cname = pv["contractor"]["name"]
        for t in db.rows(conn, f"SELECT ticket_id, citizen_id FROM ticket WHERE ticket_id IN ({','.join('?' * len(ids))})", ids):
            notify.notify(conn, [t["citizen_id"]], "ticket_assigned", "ticket", t["ticket_id"], ticket_id=t["ticket_id"],
                          task_id=task_id, contractor=cname)
    return task_id


# ---- contractor (DFD 5.0) ------------------------------------------------------------------------------
def start(conn, viewer: Viewer, task_id: str) -> dict:
    _contractor(viewer)
    with db.write_tx(conn):
        k = _get(conn, task_id)
        _own(k, viewer)
        if k["status"] not in ("assigned", "rework"):
            raise LiveError(409, "bad_state", f"This task is {k['status']}.")
        ts = now_iso()
        conn.execute("UPDATE task SET status='in_progress', started_at=COALESCE(started_at, ?), updated_at=? WHERE task_id=?", (ts, ts, task_id))
        events.append(conn, "task", task_id, "started", "contractor", viewer.actor_ref, from_status=k["status"], to_status="in_progress")
        first = k["status"] == "assigned"
        for tid in _ticket_ids(conn, task_id):
            t = db.one(conn, "SELECT status, citizen_id FROM ticket WHERE ticket_id=?", (tid,))
            if t["status"] == "assigned":
                conn.execute("UPDATE ticket SET status='in_progress', updated_at=? WHERE ticket_id=?", (ts, tid))
                events.append(conn, "ticket", tid, "work_started", "contractor", viewer.actor_ref, from_status="assigned", to_status="in_progress",
                              data={"task_id": task_id})
                if first:
                    notify.notify(conn, [t["citizen_id"]], "work_started", "ticket", tid, ticket_id=tid)
    return {"task_id": task_id, "status": "in_progress"}


def submit_report(conn, viewer: Viewer, task_id: str, *, summary: str, repair_method: str | None, area_sqm, bill_amount_inr,
                  bill_ref: str | None, evidence_files, bill_files) -> str:
    _contractor(viewer)
    summary = (summary or "").strip()
    if not (10 <= len(summary) <= 2000):
        raise LiveError(422, "bad_summary", "Write a resolution report of 10 to 2000 characters.")
    try:
        bill = float(bill_amount_inr)
        assert 0 < bill <= 1e9
    except Exception:
        raise LiveError(422, "bad_bill", "Enter the bill amount in rupees.")
    try:
        area = None if area_sqm in (None, "") else float(area_sqm)
        assert area is None or 0 <= area <= 100000
    except Exception:
        raise LiveError(422, "bad_area", "Area must be a number of square metres.")
    k0 = _get(conn, task_id)
    _own(k0, viewer)
    method = repair_method or k0["repair_method"]
    rate = db.one(conn, "SELECT * FROM rate_card WHERE repair_method=?", (method,)) if method else None
    if method and not rate:
        raise LiveError(422, "bad_method", "Choose a repair method from the rate card.")
    if rate and rate["unit"] == "per sqm" and not area:
        raise LiveError(422, "area_required", "Enter the repaired area in square metres for this method.")
    ev = media.stage_many(evidence_files or [], "evidence")
    bills = []
    try:
        bills = media.stage_many(bill_files or [], "bill")
        if len(ev) > MAX_EVIDENCE or len(bills) > MAX_BILLS:
            raise LiveError(422, "too_many_files", f"Attach at most {MAX_EVIDENCE} photos/videos and {MAX_BILLS} bill files.")
        with db.write_tx(conn):
            k = _get(conn, task_id)
            _own(k, viewer)
            if k["status"] not in ("assigned", "in_progress", "rework"):
                raise LiveError(409, "bad_state", f"This task is {k['status']}.")
            ids = _ticket_ids(conn, task_id)
            checks = []
            expected, qty = _expected_cost(rate, method, area, len(ids))
            if expected:
                ratio = bill / expected
                if ratio > OVER:
                    checks.append({"code": "bill_over_rate", "tone": "concern", "params": {
                        "bill": bill, "pct": round((ratio - 1) * 100), "expected": round(expected), "qty": qty, "method": method}})
                else:
                    checks.append({"code": "bill_within_rate", "tone": "info", "params": {
                        "bill": bill, "expected": round(expected), "qty": qty, "method": method}})
            if k["est_cost_inr"] and bill > k["est_cost_inr"] * OVER:
                checks.append({"code": "bill_over_estimate", "tone": "concern", "params": {
                    "bill": bill, "pct": round((bill / k["est_cost_inr"] - 1) * 100), "est": round(k["est_cost_inr"])}})
            for tid in ids:
                road = TK._road(conn, db.one(conn, "SELECT road_id FROM ticket WHERE ticket_id=?", (tid,))["road_id"])
                if road and road["under_dlp"] and not any(c["code"] == "dlp_road" and road["road_id"] in c["params"]["road"] for c in checks):
                    checks.append({"code": "dlp_road", "tone": "concern", "params": {"road": f"{road['road_name']} ({road['road_id']})"}})
            if not ev:
                checks.append({"code": "no_photos", "tone": "concern", "params": {}})
            if not bills:
                checks.append({"code": "no_bill_file", "tone": "concern", "params": {}})
            rid = next_id(conn, "report", "RPT")
            ts = now_iso()
            conn.execute("INSERT INTO repair_report(report_id, task_id, submitted_by, summary, repair_method, area_sqm, bill_amount_inr, "
                         "bill_ref, submitted_at, checks_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (rid, task_id, viewer.actor_ref, summary, method, area, bill, (bill_ref or "").strip()[:60] or None, ts,
                          json.dumps(checks, ensure_ascii=False)))
            for s in ev + bills:
                media.insert(conn, s, "report", rid, viewer.user_id)
            conn.execute("UPDATE task SET status='submitted', submitted_at=?, updated_at=? WHERE task_id=?", (ts, ts, task_id))
            events.append(conn, "task", task_id, "report_submitted", "contractor", viewer.actor_ref, from_status=k["status"],
                          to_status="submitted", data={"report_id": rid, "bill_amount_inr": bill, "repair_method": method, "area_sqm": area,
                                                       "evidence_sha256": [s.sha256 for s in ev], "bill_sha256": [s.sha256 for s in bills]})
            for tid in ids:
                cur = db.one(conn, "SELECT status FROM ticket WHERE ticket_id=?", (tid,))["status"]
                if cur in ("assigned", "in_progress"):
                    conn.execute("UPDATE ticket SET status='work_submitted', updated_at=? WHERE ticket_id=?", (ts, tid))
                    events.append(conn, "ticket", tid, "work_submitted", "contractor", viewer.actor_ref, from_status=cur,
                                  to_status="work_submitted", data={"task_id": task_id, "report_id": rid})
            notify.notify(conn, notify.officers_for_ward(conn, k["ward_code"]), "report_submitted", "task", task_id,
                          task_id=task_id, contractor=TK._contractor_name(conn, k["contractor_id"]))
    except Exception:
        for s in ev + bills:
            s.cleanup()
        raise
    return rid


# ---- officer review (DFD 6.0) -----------------------------------------------------------------------
def _latest_report(conn, task_id):
    return db.one(conn, "SELECT * FROM repair_report WHERE task_id=? ORDER BY submitted_at DESC, report_id DESC LIMIT 1", (task_id,))


def approve(conn, viewer: Viewer, task_id: str, note: str | None = None) -> dict:
    """Approve the resolution: the task completes and EVERY complaint in it (and its duplicates) is resolved."""
    _officer(viewer)
    with db.write_tx(conn):
        k = _get(conn, task_id)
        if k["status"] != "submitted":
            raise LiveError(409, "bad_state", f"This task is {k['status']}; only submitted work can be approved.")
        r = _latest_report(conn, task_id)
        ts = now_iso()
        note = (note or "").strip()[:1000] or None
        conn.execute("UPDATE repair_report SET decision='approved', decided_by=?, decided_at=?, decision_note=? WHERE report_id=?",
                     (viewer.actor_ref, ts, note, r["report_id"]))
        conn.execute("UPDATE task SET status='completed', completed_at=?, updated_at=?, approved_cost_inr=? WHERE task_id=?",
                     (ts, ts, r["bill_amount_inr"], task_id))
        events.append(conn, "task", task_id, "approved", "officer", viewer.actor_ref, from_status="submitted", to_status="completed",
                      note=note, data={"report_id": r["report_id"], "approved_cost_inr": r["bill_amount_inr"]})
        resolved = []
        done_task = {**k, "status": "completed", "approved_cost_inr": r["bill_amount_inr"]}
        for tid in _ticket_ids(conn, task_id):
            t = db.one(conn, "SELECT * FROM ticket WHERE ticket_id=?", (tid,))
            if t["status"] in ("assigned", "in_progress", "work_submitted"):
                conn.execute("UPDATE ticket SET status='resolved', resolved_at=?, updated_at=? WHERE ticket_id=?", (ts, ts, tid))
                events.append(conn, "ticket", tid, "resolved", "officer", viewer.actor_ref, from_status=t["status"], to_status="resolved",
                              data={"task_id": task_id, "report_id": r["report_id"]})
                resolved.append(tid)
                notify.notify(conn, [t["citizen_id"]], "ticket_resolved", "ticket", tid, ticket_id=tid)
                TK.queue_resolved_mail(conn, t, task=done_task)        # e-mail: the citizen and everyone who supported it
        # complaints that were closed as duplicates of these are resolved with them
        if resolved:
            q = ",".join("?" * len(resolved))
            for d in db.rows(conn, f"SELECT * FROM ticket WHERE status='duplicate' AND duplicate_of IN ({q})", resolved):
                conn.execute("UPDATE ticket SET status='resolved', resolved_at=?, updated_at=? WHERE ticket_id=?", (ts, ts, d["ticket_id"]))
                events.append(conn, "ticket", d["ticket_id"], "resolved", "officer", viewer.actor_ref, from_status="duplicate",
                              to_status="resolved", data={"task_id": task_id, "via_duplicate_of": True})
                notify.notify(conn, [d["citizen_id"]], "ticket_resolved", "ticket", d["ticket_id"], ticket_id=d["ticket_id"])
                TK.queue_resolved_mail(conn, d, task=done_task, parent_id=d["duplicate_of"])
                resolved.append(d["ticket_id"])
        notify.notify(conn, notify.contractor_users(conn, k["contractor_id"]), "task_approved", "task", task_id, task_id=task_id)
    return {"task_id": task_id, "status": "completed", "resolved": resolved}


def send_back(conn, viewer: Viewer, task_id: str, reason: str) -> dict:
    _officer(viewer)
    reason = (reason or "").strip()
    if not (5 <= len(reason) <= 1000):
        raise LiveError(422, "reason_required", "Explain what still needs to be done (5 to 1000 characters).")
    with db.write_tx(conn):
        k = _get(conn, task_id)
        if k["status"] != "submitted":
            raise LiveError(409, "bad_state", f"This task is {k['status']}; only submitted work can be sent back.")
        r = _latest_report(conn, task_id)
        ts = now_iso()
        conn.execute("UPDATE repair_report SET decision='rejected', decided_by=?, decided_at=?, decision_note=? WHERE report_id=?",
                     (viewer.actor_ref, ts, reason, r["report_id"]))
        conn.execute("UPDATE task SET status='rework', updated_at=? WHERE task_id=?", (ts, task_id))
        events.append(conn, "task", task_id, "sent_back", "officer", viewer.actor_ref, from_status="submitted", to_status="rework",
                      note=reason, data={"report_id": r["report_id"]})
        for tid in _ticket_ids(conn, task_id):
            if db.one(conn, "SELECT status FROM ticket WHERE ticket_id=?", (tid,))["status"] == "work_submitted":
                conn.execute("UPDATE ticket SET status='in_progress', updated_at=? WHERE ticket_id=?", (ts, tid))
                events.append(conn, "ticket", tid, "sent_back", "officer", viewer.actor_ref, from_status="work_submitted",
                              to_status="in_progress", data={"task_id": task_id})
        notify.notify(conn, notify.contractor_users(conn, k["contractor_id"]), "task_rework", "task", task_id, task_id=task_id, reason=reason)
    return {"task_id": task_id, "status": "rework"}


def cancel(conn, viewer: Viewer, task_id: str, reason: str) -> dict:
    _officer(viewer)
    reason = (reason or "").strip()
    if not (5 <= len(reason) <= 1000):
        raise LiveError(422, "reason_required", "Give a reason for cancelling (5 to 1000 characters).")
    with db.write_tx(conn):
        k = _get(conn, task_id)
        if k["status"] not in ("assigned", "in_progress", "rework"):
            raise LiveError(409, "bad_state", f"This task is {k['status']} and cannot be cancelled.")
        ts = now_iso()
        conn.execute("UPDATE task SET status='cancelled', updated_at=? WHERE task_id=?", (ts, task_id))
        events.append(conn, "task", task_id, "cancelled", "officer", viewer.actor_ref, from_status=k["status"], to_status="cancelled", note=reason)
        for tid in _ticket_ids(conn, task_id):
            t = db.one(conn, "SELECT status, task_id FROM ticket WHERE ticket_id=?", (tid,))
            if t["task_id"] == task_id and t["status"] in ("assigned", "in_progress", "work_submitted"):
                conn.execute("UPDATE ticket SET status='verified', task_id=NULL, updated_at=? WHERE ticket_id=?", (ts, tid))
                events.append(conn, "ticket", tid, "unassigned", "officer", viewer.actor_ref, from_status=t["status"], to_status="verified",
                              note=reason, data={"task_id": task_id})
        notify.notify(conn, notify.contractor_users(conn, k["contractor_id"]), "task_cancelled", "task", task_id, task_id=task_id)
    return {"task_id": task_id, "status": "cancelled"}


# ---- read ------------------------------------------------------------------------------------------
def due_datetime(due_at) -> datetime | None:
    """The moment a task is due. A bare date (from the form) is due at the END of that day, Mumbai time."""
    try:
        due = datetime.fromisoformat(due_at)
    except (TypeError, ValueError):
        return None
    if len(str(due_at).strip()) <= 10:
        due = due.replace(hour=23, minute=59, second=59)
    if due.tzinfo is None:
        due = due.replace(tzinfo=IST)
    return due


def _overdue(k) -> bool:
    if k["status"] not in ("assigned", "in_progress", "rework"):
        return False
    due = due_datetime(k["due_at"])
    return bool(due and due < datetime.now(timezone.utc))


def check_overdue(conn, now: datetime | None = None) -> list[str]:
    """Tell the contractor (e-mail + in-app) when a task is still not completed after its deadline. Once per task.

    "Not completed" means the contractor still owes the work: assigned, in progress or sent back for rework. Work that
    was submitted and is waiting for the officer's review is not the contractor's delay. The ward officers are told
    in-app, and the complaints in the task get a neutral "deadline passed" line in their tracking history.
    """
    now = now or datetime.now(timezone.utc)
    notified = []
    cand = db.rows(conn, f"SELECT task_id FROM task WHERE status IN ({','.join('?' * len(OWED))}) "
                         "AND overdue_notified_at IS NULL", OWED)
    for c in cand:
        with db.write_tx(conn):
            k = _get(conn, c["task_id"])                  # re-read inside the write lock
            if k["status"] not in OWED or k["overdue_notified_at"]:
                continue
            due = due_datetime(k["due_at"])
            if due is None or due >= now:
                continue
            days = max(1, (now - due).days)
            cname = TK._contractor_name(conn, k["contractor_id"])
            ts = now_iso()
            conn.execute("UPDATE task SET overdue_notified_at=? WHERE task_id=?", (ts, k["task_id"]))
            emailed = 0
            for uid in notify.contractor_users(conn, k["contractor_id"]):
                emailed += mailer.enqueue(conn, uid, "task_overdue", "task", k["task_id"], dedupe_key=f"overdue:{k['task_id']}:{uid}",
                                          contractor=cname, task_id=k["task_id"], title=k["title"] or k["task_id"], ward=k["ward_code"],
                                          due=k["due_at"][:10], status=k["status"], days=days,
                                          url=f"{config.APP_URL}/tasks/{k['task_id']}")
            events.append(conn, "task", k["task_id"], "overdue_notified", "system", "system:overdue", from_status=k["status"],
                          to_status=k["status"], data={"due_at": k["due_at"], "days_overdue": days, "emailed": emailed})
            for tid in _ticket_ids(conn, k["task_id"]):
                events.append(conn, "ticket", tid, "deadline_passed", "system", "system:overdue", data={"task_id": k["task_id"]})
            notify.notify(conn, notify.contractor_users(conn, k["contractor_id"]), "task_overdue", "task", k["task_id"],
                          task_id=k["task_id"], ward=k["ward_code"], due=k["due_at"][:10])
            notify.notify(conn, notify.officers_for_ward(conn, k["ward_code"]), "task_overdue_officer", "task", k["task_id"],
                          task_id=k["task_id"], contractor=cname, ward=k["ward_code"], due=k["due_at"][:10])
            notified.append(k["task_id"])
    return notified


def _brief(conn, k) -> dict:
    return {"task_id": k["task_id"], "title": k["title"], "status": k["status"], "ward_code": k["ward_code"],
            "contractor_id": k["contractor_id"], "contractor_name": TK._contractor_name(conn, k["contractor_id"]),
            "repair_method": k["repair_method"], "est_cost_inr": k["est_cost_inr"], "approved_cost_inr": k["approved_cost_inr"],
            "due_at": k["due_at"], "created_at": k["created_at"], "updated_at": k["updated_at"], "overdue": _overdue(k),
            "overdue_notified_at": k["overdue_notified_at"],
            "tickets": len(_ticket_ids(conn, k["task_id"]))}


def list_tasks(conn, viewer: Viewer, *, status=None, ward=None, limit=50, offset=0) -> dict:
    if viewer is None or viewer.role not in ("officer", "contractor"):
        raise LiveError(403, "forbidden", "Tasks are visible to officers and contractors.")
    where, params = ["1=1"], []
    if viewer.role == "contractor":
        where.append("contractor_id=?"); params.append(viewer.contractor_id)
    if status == "active":
        where.append("status IN ('assigned','in_progress','submitted','rework')")
    elif status in STATUSES:
        where.append("status=?"); params.append(status)
    if ward:
        where.append("ward_code=?"); params.append(ward)
    w = " AND ".join(where)
    total = db.one(conn, f"SELECT COUNT(*) n FROM task WHERE {w}", params)["n"]
    rows = db.rows(conn, f"SELECT * FROM task WHERE {w} ORDER BY CASE status WHEN 'submitted' THEN 0 WHEN 'rework' THEN 1 "
                         f"WHEN 'assigned' THEN 2 WHEN 'in_progress' THEN 3 ELSE 4 END, due_at, task_id DESC LIMIT ? OFFSET ?",
                   params + [max(1, min(200, limit)), max(0, offset)])
    counts = {r["status"]: r["n"] for r in db.rows(conn, f"SELECT status, COUNT(*) n FROM task WHERE {w} GROUP BY status", params)}
    return {"total": total, "counts": counts, "items": [_brief(conn, k) for k in rows]}


def detail(conn, viewer: Viewer, task_id: str, lang: str = "en") -> dict:
    k = _get(conn, task_id)
    if viewer is None or viewer.role not in ("officer", "contractor"):
        raise LiveError(403, "forbidden", "Tasks are visible to the assigned contractor and officers.")
    if viewer.role == "contractor":
        _own(k, viewer)
    out = _brief(conn, k)
    out.update({"instructions": k["instructions"], "est_area_sqm": k["est_area_sqm"], "started_at": k["started_at"],
                "submitted_at": k["submitted_at"], "completed_at": k["completed_at"], "created_by": k["created_by"]})
    out["complaints"] = [TK.detail(conn, tid, viewer) for tid in _ticket_ids(conn, task_id)]
    reports = []
    for r in db.rows(conn, "SELECT * FROM repair_report WHERE task_id=? ORDER BY submitted_at DESC, report_id DESC", (task_id,)):
        files = media.for_owner(conn, "report", r["report_id"], viewer)
        reports.append({**{x: r[x] for x in ("report_id", "summary", "repair_method", "area_sqm", "bill_amount_inr", "bill_ref",
                                              "submitted_at", "decision", "decided_at", "decision_note")},
                        "evidence": [f for f in files if f["kind"] != "bill"], "bills": [f for f in files if f["kind"] == "bill"],
                        "checks": _render_checks(json.loads(r["checks_json"] or "[]"), lang)})
    out["reports"] = reports
    out["events"] = [{"at": e["at"], "event": e["event"], "to_status": e["to_status"], "actor_role": e["actor_role"],
                      "actor_id": e["actor_id"] if viewer.role == "officer" else None, "note": e["note"]}
                     for e in events.history(conn, "task", task_id)]
    created = next((e for e in events.history(conn, "task", task_id) if e["event"] == "created"), None)
    if created and viewer.role == "officer":
        out["pre_award_checks"] = [c for c in json.loads(created["data_json"] or "{}").get("pre_award_checks", [])]
    out["actions"] = {
        "start": viewer.role == "contractor" and k["status"] in ("assigned", "rework"),
        "submit_report": viewer.role == "contractor" and k["status"] in ("assigned", "in_progress", "rework"),
        "approve": viewer.role == "officer" and viewer.can_act and k["status"] == "submitted",
        "send_back": viewer.role == "officer" and viewer.can_act and k["status"] == "submitted",
        "cancel": viewer.role == "officer" and viewer.can_act and k["status"] in ("assigned", "in_progress", "rework"),
    }
    return out
