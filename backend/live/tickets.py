"""Complaint tickets: DFD 2.0 Raise Complaint and 3.0 Verify Complaint.

Status flow:
  submitted -> verified | rejected | duplicate        (officer, 3.0)
  verified  -> assigned                               (officer creates a task, 4.0; see tasks.py)
  assigned  -> in_progress -> work_submitted          (contractor, 5.0)
  work_submitted -> resolved | in_progress            (officer approves / sends back, 6.0)

Every transition appends to the hash-chained `ticket_event` log and notifies the people concerned.
Public views never include the citizen's identity, free text is scrubbed of phone numbers, e-mails and
vehicle numbers, and locations are rounded to about 100 m.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
import db
from agents import complaint_parser as cp
from agents import geocoder
from live import events, mailer, media, notify
from live import text as LT
from live.common import LiveError, Viewer, next_id, now_iso
from live.users import mask_mobile
from pipeline.geo import dist_m, load_geo

STATUSES = ("submitted", "verified", "rejected", "duplicate", "assigned", "in_progress", "work_submitted", "resolved")
OPEN = ("submitted", "verified", "assigned", "in_progress", "work_submitted")
CLOSED_NEG = ("rejected", "duplicate")
REJECT_REASONS = tuple(LT.REJECT_REASON)
# What the complaint is about / next to. `category` says what is wrong (pothole, manhole ...); `section` says where it matters.
SECTIONS = ("roads", "hospitals", "schools", "transport", "markets", "residential", "other")
DEFAULT_SECTION = "roads"
UPVOTES_PER_HOUR = 30
BBOX = (18.85, 19.35, 72.74, 73.05)          # lat min, lat max, lon min, lon max (Greater Mumbai)
MAX_LOCATIONS, MAX_PHOTOS, MAX_VIDEOS = 5, 6, 2
DESC_MIN, DESC_MAX = 10, 2000
PER_HOUR = 10
DUP_RADIUS_M, DUP_DAYS = 250, 30

_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_PHONE = re.compile(r"(?<![\w])(?:\+?91[\s-]?)?(?:\d[\s-]?){9,11}\d(?![\w])")
_RE_VEHICLE = re.compile(r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{4}\b", re.I)


def redact(text: str | None) -> str | None:
    """Scrub personal identifiers from text before it is shown publicly."""
    if not text:
        return text
    text = _RE_EMAIL.sub("[email removed]", text)
    text = _RE_VEHICLE.sub("[vehicle number removed]", text)
    return _RE_PHONE.sub("[number removed]", text)


# ---- create (DFD 2.0) ------------------------------------------------------------------------------
def _parse_locations(raw) -> list[dict]:
    if raw in (None, "", "[]"):
        return []
    try:
        pts = json.loads(raw) if isinstance(raw, str) else raw
        assert isinstance(pts, list)
    except Exception:
        raise LiveError(422, "bad_locations", "Locations could not be read.")
    if len(pts) > MAX_LOCATIONS:
        raise LiveError(422, "too_many_locations", f"Add at most {MAX_LOCATIONS} locations.")
    out = []
    for p in pts:
        try:
            lat, lon = float(p["lat"]), float(p["lon"])
        except Exception:
            raise LiveError(422, "bad_locations", "Locations could not be read.")
        if not (BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]):
            raise LiveError(422, "outside_area", "That location is outside the BMC area.")
        acc = p.get("accuracy_m")
        try:
            acc = None if acc in (None, "") else max(0.0, min(100000.0, float(acc)))
        except (TypeError, ValueError):
            acc = None
        src = p.get("source") if p.get("source") in ("gps", "map") else "map"
        out.append({"lat": lat, "lon": lon, "accuracy_m": acc, "source": src})
    return out


def create(conn, viewer: Viewer, *, category: str, description: str, locality_text: str | None,
           locations, files, section: str | None = None) -> str:
    if viewer is None or viewer.role != "citizen":
        raise LiveError(403, "citizens_only", "Please log in with the Citizen panel to raise a complaint.")
    if category not in cp.CATEGORIES:
        raise LiveError(422, "bad_category", "Choose a category from the list.")
    section = (section or DEFAULT_SECTION).strip().lower()
    if section not in SECTIONS:
        raise LiveError(422, "bad_section", "Choose a section from the list.")
    desc = (description or "").strip()
    if not (DESC_MIN <= len(desc) <= DESC_MAX):
        raise LiveError(422, "bad_description", f"Describe the problem in {DESC_MIN} to {DESC_MAX} characters.")
    loc_text = (locality_text or "").strip()[:120] or None
    pts = _parse_locations(locations)

    geo = load_geo()
    lat = lon = acc = road = rdist = None
    if pts:
        p0 = pts[0]
        lat, lon, acc, method = p0["lat"], p0["lon"], p0["accuracy_m"], p0["source"]
        ward = geo.ward_at(lat, lon)
        if not ward:
            raise LiveError(422, "outside_area", "That location is outside the BMC wards.")
        if acc is None or acc <= 500:          # never snap to a road from an imprecise fix
            road, rdist = geo.nearest_road(lat, lon, max(200.0, acc or 0.0), ward=ward)
    elif loc_text:
        gaz = geocoder.Gazetteer(db.rows(conn, "SELECT * FROM localities"))
        place, _, ambiguous, _ = gaz.lookup(loc_text)
        if not place:
            raise LiveError(422, "no_location", "We could not find that place. Use your location or drop a pin on the map.")
        lat, lon, ward, method, acc = place.lat, place.lon, place.ward_code, "locality", 2000.0 if ambiguous else 1000.0
    else:
        raise LiveError(422, "no_location", "Add your current location, drop a pin on the map, or type the locality.")

    staged = media.stage_many(files or [], "evidence")
    try:
        kinds = Counter(s.kind for s in staged)
        if kinds["photo"] > MAX_PHOTOS or kinds["video"] > MAX_VIDEOS:
            raise LiveError(422, "too_many_files", f"Attach at most {MAX_PHOTOS} photos and {MAX_VIDEOS} videos.")
        # Our reading of the text (Claude when configured, keyword classifier otherwise): a claim for the officer.
        sug = cp.parse_all([{"complaint_id": "new", "description": desc, "category_reported": category,
                             "photo_description": None}])["new"]
        with db.write_tx(conn):
            since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
            n = db.one(conn, "SELECT COUNT(*) n FROM ticket WHERE citizen_id=? AND created_at>=?", (viewer.user_id, since))["n"]
            if n >= PER_HOUR:
                raise LiveError(429, "too_many_complaints", "You have raised many complaints in the last hour. Please try again later.")
            tid = next_id(conn, "ticket", "CMP")
            ts = now_iso()
            conn.execute(
                "INSERT INTO ticket(ticket_id, citizen_id, category, category_reported, category_suggested, suggest_confidence, "
                "suggest_extractor, description, locality_text, ward_code, road_id, road_distance_m, lat, lon, accuracy_m, geo_method, "
                "status, created_at, updated_at, section) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, viewer.user_id, category, category, sug["category"], sug["confidence"], sug["extractor"], desc, loc_text,
                 ward, road, rdist, lat, lon, acc, method, "submitted", ts, ts, section))
            for i, p in enumerate(pts):
                conn.execute("INSERT INTO ticket_location VALUES (?,?,?,?,?,?)", (tid, i, p["lat"], p["lon"], p["accuracy_m"], p["source"]))
            for s in staged:
                media.insert(conn, s, "ticket", tid, viewer.user_id)
            events.append(conn, "ticket", tid, "submitted", "citizen", viewer.actor_ref, to_status="submitted",
                          data={"category": category, "section": section, "ward": ward, "road_id": road, "locations": len(pts),
                                "media_sha256": [s.sha256 for s in staged]})
            notify.notify(conn, [viewer.user_id], "ticket_submitted", "ticket", tid, ticket_id=tid)
            notify.notify(conn, notify.officers_for_ward(conn, ward), "new_ticket", "ticket", tid, ticket_id=tid,
                          category=category, ward=ward)
    except Exception:
        for s in staged:
            s.cleanup()
        raise
    return tid


# ---- read ----------------------------------------------------------------------------------------
def _get(conn, tid: str) -> dict:
    t = db.one(conn, "SELECT * FROM ticket WHERE ticket_id=?", (tid,))
    if not t:
        raise LiveError(404, "not_found", "No complaint with that ID.")
    return t


def _road(conn, road_id):
    if not road_id:
        return None
    r = db.one(conn, "SELECT road_id, road_name, segment_no, under_dlp FROM roads WHERE road_id=?", (road_id,))
    return {"road_id": r["road_id"], "road_name": r["road_name"], "segment_no": r["segment_no"],
            "under_dlp": r["under_dlp"] == "Y"} if r else None


def _contractor_name(conn, cid):
    r = db.one(conn, "SELECT contractor_name FROM contractors WHERE contractor_id=?", (cid,)) if cid else None
    return r["contractor_name"] if r else None


def relation(conn, t: dict, viewer: Viewer | None) -> str:
    """'officer' | 'owner' | 'contractor' (assigned) | 'public'."""
    if viewer is None:
        return "public"
    if viewer.role == "officer":
        return "officer"
    if viewer.role == "citizen" and viewer.user_id == t["citizen_id"]:
        return "owner"
    if viewer.role == "contractor" and t["task_id"]:
        task = db.one(conn, "SELECT contractor_id FROM task WHERE task_id=?", (t["task_id"],))
        if task and task["contractor_id"] == viewer.contractor_id:
            return "contractor"
    return "public"


def _task_brief(conn, task_id, rel):
    if not task_id:
        return None
    k = db.one(conn, "SELECT * FROM task WHERE task_id=?", (task_id,))
    if not k:
        return None
    out = {"task_id": k["task_id"], "status": k["status"], "contractor_id": k["contractor_id"],
           "contractor_name": _contractor_name(conn, k["contractor_id"]), "due_at": k["due_at"]}
    if k["status"] == "completed":
        out["approved_cost_inr"] = k["approved_cost_inr"]          # award/bill values are public once approved
        out["completed_at"] = k["completed_at"]
    elif rel in ("officer", "contractor"):
        out["est_cost_inr"] = k["est_cost_inr"]
    return out


def _events_view(conn, rows, rel):
    out = []
    for e in rows:
        item = {"at": e["at"], "event": e["event"], "to_status": e["to_status"], "actor_role": e["actor_role"]}
        if e["actor_role"] == "contractor":
            item["actor_label"] = _contractor_name(conn, e["actor_id"].split(":", 1)[1])
        if rel in ("officer", "owner", "contractor") and e["note"]:
            item["note"] = e["note"]
        if e["event"] == "rejected" and e["data_json"]:
            item["reason"] = json.loads(e["data_json"]).get("reason")
        if e["event"] in ("assigned", "unassigned") and e["data_json"]:
            cid = json.loads(e["data_json"]).get("contractor_id")
            if cid:
                item["contractor"] = {"contractor_id": cid, "name": _contractor_name(conn, cid)}
        if rel == "officer":
            item["actor_id"] = e["actor_id"]
        out.append(item)
    return out


def summary(conn, t: dict, viewer: Viewer | None) -> dict:
    rel = relation(conn, t, viewer)
    thumb = db.one(conn, "SELECT * FROM media WHERE owner_type='ticket' AND owner_id=? AND kind='photo' ORDER BY created_at LIMIT 1",
                   (t["ticket_id"],))
    thumb_url = None
    if thumb:
        s = media.serialize(conn, thumb, viewer)
        thumb_url = s["url"] if s else None
    road = _road(conn, t["road_id"])
    brief = _task_brief(conn, t["task_id"], rel) or {}
    return {"ticket_id": t["ticket_id"], "category": t["category"], "section": t["section"], "ward_code": t["ward_code"],
            "road_name": road["road_name"] if road else None, "locality_text": redact(t["locality_text"]),
            "status": t["status"], "created_at": t["created_at"], "updated_at": t["updated_at"],
            "task_id": t["task_id"], "contractor_id": brief.get("contractor_id"), "contractor_name": brief.get("contractor_name"),
            "upvotes": upvote_count(conn, t["ticket_id"]), "upvoted_by_me": has_upvoted(conn, t["ticket_id"], viewer),
            "thumb_url": thumb_url, "is_mine": rel == "owner",
            "media_count": db.one(conn, "SELECT COUNT(*) n FROM media WHERE owner_type='ticket' AND owner_id=?", (t["ticket_id"],))["n"]}


def detail(conn, tid: str, viewer: Viewer | None) -> dict:
    t = _get(conn, tid)
    rel = relation(conn, t, viewer)
    privileged = rel in ("officer", "owner", "contractor")
    road = _road(conn, t["road_id"])
    task = _task_brief(conn, t["task_id"], rel)
    out = {
        "ticket_id": tid, "category": t["category"], "section": t["section"], "status": t["status"], "ward_code": t["ward_code"],
        "road": road,
        "contractor": {"contractor_id": task["contractor_id"], "name": task["contractor_name"]} if task else None,
        "upvotes": upvote_count(conn, tid), "upvoted_by_me": has_upvoted(conn, tid, viewer),
        "can_upvote": bool(viewer and viewer.role == "citizen" and rel != "owner" and t["status"] in OPEN),
        "description": t["description"] if privileged else redact(t["description"]),
        "locality_text": t["locality_text"] if privileged else redact(t["locality_text"]),
        "location": {"lat": round(t["lat"], 3) if t["lat"] is not None else None,
                     "lon": round(t["lon"], 3) if t["lon"] is not None else None, "approximate": True},
        "created_at": t["created_at"], "updated_at": t["updated_at"], "verified_at": t["verified_at"],
        "resolved_at": t["resolved_at"], "reject_reason": t["reject_reason"], "duplicate_of": t["duplicate_of"],
        "task": task, "media": media.for_owner(conn, "ticket", tid, viewer),
        "events": _events_view(conn, events.history(conn, "ticket", tid), rel),
        "viewer": rel, "repair_evidence": [],
    }
    # Repair evidence (after-photos) becomes public once the officer approves the work.
    if t["task_id"]:
        for r in db.rows(conn, "SELECT report_id FROM repair_report WHERE task_id=? ORDER BY submitted_at", (t["task_id"],)):
            out["repair_evidence"] += [m for m in media.for_owner(conn, "report", r["report_id"], viewer) if m["kind"] != "bill"]
    if privileged:
        out["locations"] = db.rows(conn, "SELECT lat, lon, accuracy_m, source FROM ticket_location WHERE ticket_id=? ORDER BY seq", (tid,))
        out["location"] = {"lat": t["lat"], "lon": t["lon"], "accuracy_m": t["accuracy_m"], "method": t["geo_method"], "approximate": False}
    if rel == "officer":
        u = db.one(conn, "SELECT display_name, login FROM app_user WHERE user_id=?", (t["citizen_id"],))
        out["citizen"] = {"display_name": u["display_name"] if u else None, "mobile": mask_mobile(u["login"]) if u else None}
        out["category_reported"] = t["category_reported"]
        out["category_suggested"] = {"category": t["category_suggested"], "confidence": t["suggest_confidence"],
                                     "extractor": t["suggest_extractor"]}
        out["duplicate_candidates"] = duplicate_candidates(conn, t)
        out["actions"] = {"verify": viewer.can_act and t["status"] == "submitted", "reject": viewer.can_act and t["status"] == "submitted"}
    return out


def duplicate_candidates(conn, t: dict) -> list[dict]:
    """Open complaints of the same category nearby (or on the same road) in the last 30 days."""
    if t["lat"] is None:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=DUP_DAYS)).isoformat(timespec="seconds")
    out = []
    for o in db.rows(conn, "SELECT * FROM ticket WHERE ticket_id<>? AND category=? AND created_at>=? AND status NOT IN ('rejected','duplicate')",
                     (t["ticket_id"], t["category"], since)):
        d = dist_m(t["lat"], t["lon"], o["lat"], o["lon"]) if o["lat"] is not None else None
        same_road = bool(t["road_id"]) and o["road_id"] == t["road_id"]
        if (d is not None and d <= DUP_RADIUS_M) or same_road:
            out.append({"ticket_id": o["ticket_id"], "status": o["status"], "distance_m": round(d) if d is not None else None,
                        "same_road": same_road, "created_at": o["created_at"]})
    return sorted(out, key=lambda x: (x["distance_m"] is None, x["distance_m"] or 0))[:5]


def list_tickets(conn, viewer: Viewer | None, *, status=None, ward=None, category=None, q=None, mine=False,
                 limit=30, offset=0, section=None, sort="recent") -> dict:
    where, params = ["1=1"], []
    if mine:
        if viewer is None or viewer.role != "citizen":
            raise LiveError(401, "login_required", "Log in as a citizen to see your complaints.")
        where.append("citizen_id=?"); params.append(viewer.user_id)
    if ward:
        where.append("ward_code=?"); params.append(ward)
    scope_w, scope_p = " AND ".join(where), list(params)        # counts use the same ward/mine scope, any status
    if status == "open":
        where.append(f"status IN ({','.join('?' * len(OPEN))})"); params += list(OPEN)
    elif status == "closed":
        where.append("status IN ('rejected','duplicate')")
    elif status in STATUSES:
        where.append("status=?"); params.append(status)
    if category in cp.CATEGORIES:
        where.append("category=?"); params.append(category)
    if section in SECTIONS:
        where.append("section=?"); params.append(section)
    if q:
        where.append("(ticket_id LIKE ? OR locality_text LIKE ?)"); params += [f"%{q.strip()[:40]}%"] * 2
    w = " AND ".join(where)
    total = db.one(conn, f"SELECT COUNT(*) n FROM ticket WHERE {w}", params)["n"]
    order = ("(SELECT COUNT(*) FROM ticket_upvote u WHERE u.ticket_id=ticket.ticket_id) DESC, created_at DESC, ticket_id DESC"
             if sort == "upvotes" else "created_at DESC, ticket_id DESC")
    rows = db.rows(conn, f"SELECT * FROM ticket WHERE {w} ORDER BY {order} LIMIT ? OFFSET ?",
                   params + [max(1, min(100, limit)), max(0, offset)])
    counts = {r["status"]: r["n"] for r in db.rows(conn, f"SELECT status, COUNT(*) n FROM ticket WHERE {scope_w} GROUP BY status", scope_p)}
    counts["open"] = sum(counts.get(k, 0) for k in OPEN)
    counts["closed"] = sum(counts.get(k, 0) for k in CLOSED_NEG)
    return {"total": total, "items": [summary(conn, r, viewer) for r in rows], "counts": counts}


# ---- verify / reject (DFD 3.0) ----------------------------------------------------------------------
def _officer(viewer):
    if viewer is None or viewer.role != "officer":
        raise LiveError(403, "officers_only", "Only ward officers can do this.")
    if not viewer.can_act:
        raise LiveError(403, "read_only", "This officer account is read-only (audit) and cannot change records.")


def verify(conn, viewer: Viewer, tid: str, category: str | None = None, note: str | None = None,
           section: str | None = None) -> dict:
    _officer(viewer)
    with db.write_tx(conn):
        t = _get(conn, tid)
        if t["status"] != "submitted":
            raise LiveError(409, "bad_state", f"This complaint is already {t['status']}.")
        new_cat = category or t["category"]
        if new_cat not in cp.CATEGORIES:
            raise LiveError(422, "bad_category", "Choose a category from the list.")
        new_sec = (section or t["section"]).strip().lower()
        if new_sec not in SECTIONS:
            raise LiveError(422, "bad_section", "Choose a section from the list.")
        ts = now_iso()
        conn.execute("UPDATE ticket SET status='verified', category=?, section=?, verified_at=?, updated_at=? WHERE ticket_id=?",
                     (new_cat, new_sec, ts, ts, tid))
        changed = {}
        if new_cat != t["category"]:
            changed.update(category_from=t["category"], category_to=new_cat)
        if new_sec != t["section"]:
            changed.update(section_from=t["section"], section_to=new_sec)
        events.append(conn, "ticket", tid, "verified", "officer", viewer.actor_ref, from_status="submitted", to_status="verified",
                      note=(note or "").strip()[:500] or None, data=changed or None)
        notify.notify(conn, [t["citizen_id"]], "ticket_verified", "ticket", tid, ticket_id=tid)
    return {"ticket_id": tid, "status": "verified", "category": new_cat, "section": new_sec}


def _root(conn, tid: str) -> dict:
    seen = set()
    t = _get(conn, tid)
    while t["status"] == "duplicate" and t["duplicate_of"] and t["ticket_id"] not in seen:
        seen.add(t["ticket_id"])
        t = _get(conn, t["duplicate_of"])
    return t


def reject(conn, viewer: Viewer, tid: str, reason: str, note: str | None = None, duplicate_of: str | None = None) -> dict:
    _officer(viewer)
    if reason not in REJECT_REASONS:
        raise LiveError(422, "bad_reason", "Choose a reason.")
    note = (note or "").strip()[:500] or None
    if reason == "other" and not note:
        raise LiveError(422, "note_required", "Add a note explaining the reason.")
    with db.write_tx(conn):
        t = _get(conn, tid)
        if t["status"] != "submitted":
            raise LiveError(409, "bad_state", f"This complaint is already {t['status']}.")
        ts = now_iso()
        if reason == "duplicate":
            if not duplicate_of:
                raise LiveError(422, "duplicate_of_required", "Give the ID of the complaint this repeats.")
            parent = _root(conn, duplicate_of.strip().upper())
            if parent["ticket_id"] == tid or parent["status"] == "rejected":
                raise LiveError(422, "bad_duplicate", "That complaint cannot be used as the original.")
            status = "resolved" if parent["status"] == "resolved" else "duplicate"
            conn.execute("UPDATE ticket SET status=?, duplicate_of=?, reject_reason=?, updated_at=?, resolved_at=? WHERE ticket_id=?",
                         (status, parent["ticket_id"], reason, ts, ts if status == "resolved" else None, tid))
            events.append(conn, "ticket", tid, "duplicate", "officer", viewer.actor_ref, from_status="submitted", to_status=status,
                          note=note, data={"duplicate_of": parent["ticket_id"], "reason": reason})
            notify.notify(conn, [t["citizen_id"]], "ticket_duplicate", "ticket", tid, ticket_id=tid, parent_id=parent["ticket_id"])
            if status == "resolved":
                ptask = db.one(conn, "SELECT * FROM task WHERE task_id=?", (parent["task_id"],)) if parent["task_id"] else None
                queue_resolved_mail(conn, t, task=ptask, parent_id=parent["ticket_id"])
            return {"ticket_id": tid, "status": status, "duplicate_of": parent["ticket_id"]}
        conn.execute("UPDATE ticket SET status='rejected', reject_reason=?, updated_at=? WHERE ticket_id=?", (reason, ts, tid))
        events.append(conn, "ticket", tid, "rejected", "officer", viewer.actor_ref, from_status="submitted", to_status="rejected",
                      note=note, data={"reason": reason})
        notify.notify(conn, [t["citizen_id"]], "ticket_rejected", "ticket", tid, ticket_id=tid, reason=reason)
    return {"ticket_id": tid, "status": "rejected", "reason": reason}



# ---- "me too": support an existing complaint instead of raising a new one ----------------------------------------
def upvote_count(conn, tid: str) -> int:
    return db.one(conn, "SELECT COUNT(*) n FROM ticket_upvote WHERE ticket_id=?", (tid,))["n"]


def has_upvoted(conn, tid: str, viewer: Viewer | None) -> bool:
    if viewer is None or viewer.role != "citizen":
        return False
    return bool(db.one(conn, "SELECT 1 FROM ticket_upvote WHERE ticket_id=? AND user_id=?", (tid, viewer.user_id)))


def _citizen(viewer):
    if viewer is None or viewer.role != "citizen":
        raise LiveError(403, "citizens_only", "Please log in with the Citizen panel to support a complaint.")


def upvote(conn, viewer: Viewer, tid: str) -> dict:
    """Add the citizen's support to someone else's open complaint. Idempotent: voting twice counts once."""
    _citizen(viewer)
    with db.write_tx(conn):
        t = _get(conn, tid)
        if t["citizen_id"] == viewer.user_id:
            raise LiveError(409, "own_complaint", "This is your own complaint; it already counts.")
        if t["status"] not in OPEN:
            raise LiveError(409, "not_open", "This complaint is already closed, so it can no longer be supported.")
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        n = db.one(conn, "SELECT COUNT(*) n FROM ticket_upvote WHERE user_id=? AND created_at>=?", (viewer.user_id, since))["n"]
        if n >= UPVOTES_PER_HOUR:
            raise LiveError(429, "too_many_votes", "You have supported many complaints in the last hour. Please try again later.")
        conn.execute("INSERT OR IGNORE INTO ticket_upvote(ticket_id, user_id, created_at) VALUES (?,?,?)", (tid, viewer.user_id, now_iso()))
    return {"ticket_id": tid, "upvotes": upvote_count(conn, tid), "upvoted_by_me": True}


def unvote(conn, viewer: Viewer, tid: str) -> dict:
    _citizen(viewer)
    with db.write_tx(conn):
        _get(conn, tid)
        conn.execute("DELETE FROM ticket_upvote WHERE ticket_id=? AND user_id=?", (tid, viewer.user_id))
    return {"ticket_id": tid, "upvotes": upvote_count(conn, tid), "upvoted_by_me": False}


def nearby(conn, viewer: Viewer | None, lat: float, lon: float, category: str | None = None,
           radius_m: float = DUP_RADIUS_M, limit: int = 5) -> list[dict]:
    """Open complaints close to a point (optionally of the same category): shown while someone raises a complaint,
    so they can support an existing one instead of filing a duplicate."""
    if not (BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]):
        raise LiveError(422, "outside_area", "That location is outside the BMC area.")
    radius_m = max(20.0, min(1000.0, radius_m))
    deg = radius_m / 111_000 * 1.3
    where = ["lat BETWEEN ? AND ?", "lon BETWEEN ? AND ?", f"status IN ({','.join('?' * len(OPEN))})"]
    params: list = [lat - deg, lat + deg, lon - deg, lon + deg, *OPEN]
    if category in cp.CATEGORIES:
        where.append("category=?")
        params.append(category)
    out = []
    for o in db.rows(conn, f"SELECT * FROM ticket WHERE {' AND '.join(where)}", params):
        d = dist_m(lat, lon, o["lat"], o["lon"])
        if d <= radius_m:
            out.append((d, o))
    out.sort(key=lambda x: x[1]["created_at"], reverse=True)         # same spot: newest first
    out.sort(key=lambda x: round(x[0] / 10))                         # then nearest first, in 10 m steps
    return [{**summary(conn, o, viewer), "distance_m": round(d)} for d, o in out[:limit]]


# ---- e-mail: complaint resolved ---------------------------------------------------------------------------------
def queue_resolved_mail(conn, t: dict, *, task: dict | None, parent_id: str | None = None) -> None:
    """Queue the "your complaint was resolved" e-mail (and in-app note) for the citizen who raised the complaint
    and for everyone who supported it. Runs inside the caller's transaction; one message per person per complaint."""
    people = [t["citizen_id"]] + [r["user_id"] for r in db.rows(
        conn, "SELECT user_id FROM ticket_upvote WHERE ticket_id=? ORDER BY created_at", (t["ticket_id"],))]
    cname = _contractor_name(conn, task["contractor_id"]) if task else None
    cost = task.get("approved_cost_inr") if task else None
    for uid in dict.fromkeys(people):
        if uid != t["citizen_id"]:
            notify.notify(conn, [uid], "ticket_resolved", "ticket", t["ticket_id"], ticket_id=t["ticket_id"])
        mailer.enqueue(conn, uid, "ticket_resolved", "ticket", t["ticket_id"],
                       dedupe_key=f"resolved:{t['ticket_id']}:{uid}", ticket_id=t["ticket_id"], category=t["category"],
                       ward=t["ward_code"], date=now_iso()[:10], contractor=cname,
                       task_id=task["task_id"] if task else None, cost=cost, parent_id=parent_id,
                       url=f"{config.APP_URL}/ticket/{t['ticket_id']}")
