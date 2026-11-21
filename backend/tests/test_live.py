"""Three login panels and the complaint -> verification -> task -> repair -> review workflow (SPEC section 16)."""
import io
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

import db
from live import events, media, tickets
from live.seed import demo_bill_pdf

MARKER = "SECRET-METADATA-MARKER"


# ---- helpers ------------------------------------------------------------------------------------------
def jpeg_with_metadata(w=64, h=48, orientation=6) -> bytes:
    im = Image.new("RGB", (w, h), (120, 120, 120))
    ex = Image.Exif()
    ex[0x010E] = MARKER            # ImageDescription
    ex[0x010F] = "PhoneMaker"      # Make
    ex[0x0112] = orientation       # Orientation: 6 = rotate 90
    try:
        ex[0x8825] = {1: "N", 2: (19.0, 6.0, 0.0), 3: "E", 4: (72.0, 52.0, 0.0)}   # GPS IFD
    except Exception:
        pass
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=ex)
    return buf.getvalue()


FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 400


def road_point(conn, road_id):
    r = db.one(conn, "SELECT * FROM roads WHERE road_id=?", (road_id,))
    return (r["start_lat"] + r["end_lat"]) / 2, (r["start_lon"] + r["end_lon"]) / 2


def raise_ticket(client, headers, lat, lon, category="Pothole", desc="Large pothole near the bus stop, please repair soon.",
                 files=None, **extra):
    data = {"category": category, "description": desc,
            "locations": json.dumps([{"lat": lat, "lon": lon, "accuracy_m": 12, "source": "gps"}])}
    data.update(extra)
    return client.post("/api/tickets", data=data, files=files or [], headers=headers)


def new_citizen(client, mobile):
    r = client.post("/api/auth/citizen/register", json={"mobile": mobile, "password": "citizen-pass-1", "consent": True})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture(scope="module")
def ke_points(built_db):
    c = db.connect(built_db)
    rows = db.rows(c, "SELECT road_id FROM roads WHERE ward_code='K/E' AND under_dlp='N' ORDER BY road_id LIMIT 8")
    pts = [road_point(c, r["road_id"]) for r in rows]
    dlp = db.one(c, "SELECT road_id FROM roads WHERE ward_code='K/E' AND under_dlp='Y' ORDER BY road_id LIMIT 1")["road_id"]
    other = db.one(c, "SELECT road_id FROM roads WHERE ward_code='H/W' ORDER BY road_id LIMIT 1")["road_id"]
    out = {"ke": pts, "dlp": road_point(c, dlp), "dlp_road": dlp, "hw": road_point(c, other)}
    c.close()
    return out


# ---- three login panels ---------------------------------------------------------------------------------
def test_each_panel_only_authenticates_its_own_role(client):
    pw = {"password": "test-pass-123"}
    assert client.post("/api/auth/officer/login", json={"login": "ae-4471", **pw}).status_code == 200
    assert client.post("/api/auth/contractor/login", json={"login": "ae-4471", **pw}).status_code == 401
    assert client.post("/api/auth/citizen/login", json={"login": "ae-4471", **pw}).status_code == 401
    assert client.post("/api/auth/officer/login", json={"login": "ct05", **pw}).status_code == 401
    r = client.post("/api/auth/officer/login", json={"login": "ae-4471", "password": "wrong-password"})
    assert r.status_code == 401 and "incorrect" in r.json()["detail"]
    r2 = client.post("/api/auth/officer/login", json={"login": "nobody-here", "password": "wrong-password"})
    assert r2.json()["detail"] == r.json()["detail"]              # no hint whether the account exists


def test_citizen_registration_rules_and_masked_profile(client):
    bad = client.post("/api/auth/citizen/register", json={"mobile": "12345", "password": "long-enough-1", "consent": True})
    assert bad.status_code == 422
    assert client.post("/api/auth/citizen/register", json={"mobile": "9811111111", "password": "short", "consent": True}).status_code == 422
    assert client.post("/api/auth/citizen/register", json={"mobile": "9811111111", "password": "long-enough-1"}).status_code == 422
    r = client.post("/api/auth/citizen/register", json={"mobile": "+91 98111 11111", "password": "long-enough-1", "consent": True,
                                                        "display_name": "Asha"})
    assert r.status_code == 200
    h = {"Authorization": "Bearer " + r.json()["token"]}
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "citizen" and me["login"] == "98XXXXXX11"            # never echo the full number
    assert client.post("/api/auth/citizen/register", json={"mobile": "9811111111", "password": "long-enough-1", "consent": True}).status_code == 409
    assert client.post("/api/auth/citizen/login", json={"login": "09811111111", "password": "long-enough-1"}).status_code == 200


def test_logout_revokes_the_session(client):
    h = new_citizen(client, "9822222222")
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_failed_logins_are_throttled(client):
    new_citizen(client, "9833333333")
    codes = [client.post("/api/auth/citizen/login", json={"login": "9833333333", "password": "wrong-pass-x"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # even the right password is refused while throttled
    assert client.post("/api/auth/citizen/login", json={"login": "9833333333", "password": "citizen-pass-1"}).status_code == 429


def test_passwords_and_tokens_are_never_stored_in_clear(conn):
    u = db.one(conn, "SELECT pw_hash FROM app_user WHERE login='ae-4471'")
    assert u["pw_hash"].startswith("scrypt$") and "test-pass-123" not in u["pw_hash"]
    s = db.one(conn, "SELECT token_hash FROM auth_session LIMIT 1")
    assert len(s["token_hash"]) == 64


def test_browsing_never_needs_a_login(client):
    for path in ("/api/tickets", "/api/meta", "/api/wards", "/api/live/options"):
        assert client.get(path).status_code == 200
        assert client.get(path, headers={"Authorization": "Bearer expired-or-bogus"}).status_code == 200


# ---- raising a complaint (DFD 2.0) -------------------------------------------------------------------------
def test_only_logged_in_citizens_can_raise_complaints(client, tokens, ke_points):
    lat, lon = ke_points["ke"][0]
    assert raise_ticket(client, {}, lat, lon).status_code == 401
    assert raise_ticket(client, tokens["officer"], lat, lon).status_code == 403
    assert raise_ticket(client, tokens["ct05"], lat, lon).status_code == 403


def test_raise_complaint_with_photos_video_and_several_locations(client, tokens, ke_points, conn):
    (lat, lon), (lat2, lon2) = ke_points["ke"][1], ke_points["ke"][2]
    r = client.post("/api/tickets", headers=tokens["citizen"], data={
        "category": "Pothole", "description": "Deep pothole near the signal. Call me on 98765 43210 or mail asha@example.com. Car MH02AB1234 damaged.",
        "locations": json.dumps([{"lat": lat, "lon": lon, "accuracy_m": 8, "source": "gps"}, {"lat": lat2, "lon": lon2, "source": "map"}])},
        files=[("files", ("p.jpg", jpeg_with_metadata(), "image/jpeg")), ("files", ("v.mp4", FAKE_MP4, "video/mp4"))])
    assert r.status_code == 200, r.text
    t = r.json()
    tid = t["ticket_id"]
    assert tid.startswith("CMP-") and t["status"] == "submitted" and t["ward_code"] == "K/E" and t["road"]
    assert len(t["locations"]) == 2 and t["viewer"] == "owner"
    kinds = sorted(m["kind"] for m in t["media"])
    assert kinds == ["photo", "video"]                                   # the owner sees both

    # public view: identity-free, scrubbed text, rounded location, photo only (no video)
    pub = client.get(f"/api/tickets/{tid}").json()
    assert pub["viewer"] == "public" and "citizen" not in pub and "locations" not in pub
    assert "98765" not in pub["description"] and "asha@example.com" not in pub["description"] and "MH02AB1234" not in pub["description"]
    assert "[number removed]" in pub["description"]
    assert pub["location"]["lat"] == round(pub["location"]["lat"], 3)
    assert [m["kind"] for m in pub["media"]] == ["photo"]
    assert pub["media"][0]["url"].endswith("/public")

    # the public copy has no metadata and is upright; the original keeps its metadata internally
    m = db.one(conn, "SELECT * FROM media WHERE owner_id=? AND kind='photo'", (tid,))
    pub_bytes = media.file_path(m["public_name"]).read_bytes()
    assert MARKER.encode() not in pub_bytes and b"PhoneMaker" not in pub_bytes
    with Image.open(io.BytesIO(pub_bytes)) as im:
        assert len(im.getexif()) == 0 and im.size == (48, 64)           # orientation 6 applied before stripping
    assert MARKER.encode() in media.file_path(m["stored_name"]).read_bytes()
    r = client.get("/api" + pub["media"][0]["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and MARKER.encode() not in r.content

    # officer view: masked mobile, our reading of the category, actions
    off = client.get(f"/api/tickets/{tid}", headers=tokens["officer"]).json()
    assert off["citizen"]["mobile"] == "98XXXXXX01" and off["category_suggested"]["category"] and off["actions"]["verify"]
    assert "98765 43210" in off["description"]                           # officers see the original text


def test_signed_media_links(client, tokens, ke_points):
    lat, lon = ke_points["ke"][3]
    t = raise_ticket(client, tokens["citizen"], lat, lon, files=[("files", ("v.mp4", FAKE_MP4, "video/mp4"))]).json()
    url = next(m["url"] for m in t["media"] if m["kind"] == "video")
    assert "sig=" in url
    ok = client.get("/api" + url)
    assert ok.status_code == 200 and ok.headers["x-content-type-options"] == "nosniff" and ok.headers["content-security-policy"] == "sandbox"
    assert client.get("/api" + url.replace("sig=", "sig=0")).status_code == 403
    mid = url.split("/")[2]
    assert client.get(f"/api/media/{mid}/original").status_code == 403
    expired = media.signed_url(mid, "original", ttl=-10)
    assert client.get("/api" + expired).status_code == 403
    assert client.get(f"/api/media/{mid}/public").status_code == 404           # videos are never public


@pytest.mark.parametrize("files,code", [
    ([("files", ("x.jpg", b"<html><script>alert(1)</script></html>" * 3, "image/jpeg"))], 415),
    ([("files", ("x.jpg", b"\xff\xd8\xff" + b"0" * 200, "image/jpeg"))], 422),            # claims JPEG, is not one
    ([("files", (f"{i}.jpg", jpeg_with_metadata(), "image/jpeg")) for i in range(7)], 422),
])
def test_bad_uploads_are_rejected(client, ke_points, files, code):
    h = new_citizen(client, f"97{code}{len(files):05d}0"[:10])
    lat, lon = ke_points["ke"][4]
    assert raise_ticket(client, h, lat, lon, files=files).status_code == code


def test_location_rules(client, tokens, ke_points):
    h = tokens["citizen"]
    assert raise_ticket(client, h, 28.61, 77.21).status_code == 422                          # Delhi
    r = client.post("/api/tickets", headers=h, data={"category": "Pothole", "description": "Pothole near the market, please fix."})
    assert r.status_code == 422 and "location" in r.json()["detail"].lower()
    r = client.post("/api/tickets", headers=h, data={"category": "Pothole", "description": "Pothole near the market, please fix.",
                                                     "locality_text": "Byculla"})
    assert r.status_code == 200 and r.json()["ward_code"] == "E" and r.json()["road"] is None   # no road snapping from a name
    assert raise_ticket(client, h, *ke_points["ke"][0], desc="short").status_code == 422
    assert raise_ticket(client, h, *ke_points["ke"][0], category="Graffiti").status_code == 422


def test_complaint_rate_limit(client, ke_points):
    h = new_citizen(client, "9844444444")
    lat, lon = ke_points["ke"][5]
    codes = [raise_ticket(client, h, lat, lon).status_code for _ in range(tickets.PER_HOUR + 1)]
    assert codes[:-1] == [200] * tickets.PER_HOUR and codes[-1] == 429


def test_redaction():
    s = tickets.redact("Call +91 98765-43210 or 9876543210, mail a.b@x.co.in, car MH 02 AB 1234. Ref BMC25-000123 on 2025-06-05.")
    assert "98765" not in s and "9876543210" not in s and "a.b@x.co.in" not in s and "1234" not in s
    assert "BMC25-000123" in s and "2025-06-05" in s


# ---- complaints section (public list) ---------------------------------------------------------------------
def test_complaints_section_lists_everyone_s_complaints_without_identity(client, tokens):
    j = client.get("/api/tickets?limit=100").json()
    assert j["total"] >= 3 and j["items"]
    blob = json.dumps(j)
    assert "citizen_id" not in blob and "9800000001" not in blob and "u_" not in blob
    mine = client.get("/api/tickets?mine=1&limit=100", headers=tokens["citizen"]).json()
    assert mine["items"] and all(i["is_mine"] for i in mine["items"])
    assert client.get("/api/tickets?mine=1").status_code == 401
    assert client.get("/api/tickets?status=open").status_code == 200
    ke = client.get("/api/tickets?ward=K-E&limit=1").json()["counts"]
    allc = client.get("/api/tickets?limit=1").json()["counts"]
    assert ke["open"] == sum(ke.get(k, 0) for k in tickets.OPEN) and ke["open"] <= allc["open"]
    assert client.get("/api/tickets?ward=E&limit=1").json()["counts"].get("submitted", 0) < allc["submitted"]   # scoped to the ward


# ---- verification (DFD 3.0) ----------------------------------------------------------------------------
def test_verification_is_for_acting_officers_only(client, tokens, ke_points):
    tid = raise_ticket(client, tokens["citizen"], *ke_points["ke"][6]).json()["ticket_id"]
    assert client.post(f"/api/tickets/{tid}/verify", json={}, headers=tokens["citizen"]).status_code == 403
    assert client.post(f"/api/tickets/{tid}/verify", json={}, headers=tokens["ct05"]).status_code == 403
    r = client.post(f"/api/tickets/{tid}/verify", json={}, headers=tokens["auditor"])          # separation of duties
    assert r.status_code == 403 and "read-only" in r.json()["detail"]
    r = client.post(f"/api/tickets/{tid}/verify", json={"category": "Road cave-in", "note": "Checked on site"}, headers=tokens["officer"])
    assert r.status_code == 200 and r.json()["category"] == "Road cave-in"
    assert client.post(f"/api/tickets/{tid}/verify", json={}, headers=tokens["officer"]).status_code == 409
    owner = client.get(f"/api/tickets/{tid}", headers=tokens["citizen"]).json()
    assert [e["event"] for e in owner["events"]] == ["submitted", "verified"] and owner["events"][1]["note"] == "Checked on site"
    pub = client.get(f"/api/tickets/{tid}").json()
    assert "note" not in pub["events"][1] and "actor_id" not in pub["events"][1]


def test_reject_and_duplicate(client, tokens, ke_points):
    a = raise_ticket(client, tokens["citizen"], *ke_points["ke"][7]).json()["ticket_id"]
    b = raise_ticket(client, tokens["citizen"], *ke_points["ke"][7]).json()["ticket_id"]
    off = client.get(f"/api/tickets/{b}", headers=tokens["officer"]).json()
    assert a in [d["ticket_id"] for d in off["duplicate_candidates"]]
    assert client.post(f"/api/tickets/{b}/reject", json={"reason": "duplicate"}, headers=tokens["officer"]).status_code == 422
    assert client.post(f"/api/tickets/{b}/reject", json={"reason": "other"}, headers=tokens["officer"]).status_code == 422
    r = client.post(f"/api/tickets/{b}/reject", json={"reason": "duplicate", "duplicate_of": a}, headers=tokens["officer"])
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    c = raise_ticket(client, tokens["citizen"], *ke_points["ke"][0], category="Other", desc="Garbage not collected on this lane.",
                     files=[("files", ("p.jpg", jpeg_with_metadata(), "image/jpeg"))]).json()
    assert client.post(f"/api/tickets/{c['ticket_id']}/reject", json={"reason": "not_road_issue"}, headers=tokens["officer"]).status_code == 200
    pub = client.get(f"/api/tickets/{c['ticket_id']}").json()
    assert pub["status"] == "rejected" and pub["reject_reason"] == "not_road_issue"
    assert pub["media"] == []                                                       # photos of rejected complaints are not public
    assert client.get("/api" + c["media"][0]["public_url"]).status_code == 404


# ---- tasks: assign (4.0), repair (5.0), review (6.0) -----------------------------------------------------------
_n = iter(range(10, 99))


def fresh_citizen(client):
    """A new citizen per workflow test: the shared demo citizen would hit the 10-per-hour complaint limit."""
    return new_citizen(client, f"95000000{next(_n):02d}")


def _verified(client, tokens, pt, citizen=None, **kw):
    r = raise_ticket(client, citizen or fresh_citizen(client), *pt, **kw)
    assert r.status_code == 200, r.text
    tid = r.json()["ticket_id"]
    assert client.post(f"/api/tickets/{tid}/verify", json={}, headers=tokens["officer"]).status_code == 200
    return tid


def test_task_needs_verified_same_ward_complaints(client, tokens, ke_points):
    sub = raise_ticket(client, fresh_citizen(client), *ke_points["ke"][1]).json()["ticket_id"]
    r = client.post("/api/tasks/preview", json={"contractor_id": "CT05", "ticket_ids": [sub]}, headers=tokens["officer"])
    assert r.status_code == 409
    a = _verified(client, tokens, ke_points["ke"][1])
    b = _verified(client, tokens, ke_points["hw"])
    assert client.post("/api/tasks/preview", json={"contractor_id": "CT05", "ticket_ids": [a, b]}, headers=tokens["officer"]).status_code == 422
    assert client.post("/api/tasks/preview", json={"contractor_id": "CT99", "ticket_ids": [a]}, headers=tokens["officer"]).status_code == 404
    assert client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a]}, headers=tokens["ct05"]).status_code == 403


def test_full_workflow_task_completion_resolves_every_complaint(client, tokens, ke_points, conn):
    me = fresh_citizen(client)
    a = _verified(client, tokens, ke_points["ke"][2], citizen=me)
    b = _verified(client, tokens, ke_points["dlp"], citizen=me)           # this road is under another contractor's warranty
    dup = raise_ticket(client, fresh_citizen(client), *ke_points["ke"][2]).json()["ticket_id"]
    client.post(f"/api/tickets/{dup}/reject", json={"reason": "duplicate", "duplicate_of": a}, headers=tokens["officer"])

    pv = client.post("/api/tasks/preview?lang=en", json={"contractor_id": "CT05", "ticket_ids": [a, b]}, headers=tokens["officer"]).json()
    codes = {c["code"] for c in pv["checks"]}
    assert {"ct_sla", "ct_reopen", "ct_overrun", "dlp_road"} <= codes                    # pre-award risk checks
    assert pv["suggested"]["repair_method"] and pv["suggested"]["est_cost_inr"] > 0
    task = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a, b], "instructions": "Patch and roll."},
                       headers=tokens["officer"])
    assert task.status_code == 200, task.text
    k = task.json()
    tid = k["task_id"]
    assert tid.startswith("TSK-") and k["status"] == "assigned" and len(k["complaints"]) == 2
    assert client.post("/api/tasks", json={"contractor_id": "CT07", "ticket_ids": [a]}, headers=tokens["officer"]).status_code == 409

    # the other contractor cannot see or act on it
    assert client.get(f"/api/tasks/{tid}", headers=tokens["ct07"]).status_code == 403
    assert client.post(f"/api/tasks/{tid}/start", headers=tokens["ct07"]).status_code == 403
    assert tid in [x["task_id"] for x in client.get("/api/tasks", headers=tokens["ct05"]).json()["items"]]
    assert tid not in [x["task_id"] for x in client.get("/api/tasks", headers=tokens["ct07"]).json()["items"]]
    # the assigned contractor sees exact locations and the citizen's original photos
    ck = client.get(f"/api/tasks/{tid}", headers=tokens["ct05"]).json()
    assert all(c["viewer"] == "contractor" and c["locations"] for c in ck["complaints"])

    assert client.post(f"/api/tasks/{tid}/start", headers=tokens["ct05"]).json()["status"] == "in_progress"
    rep = client.post(f"/api/tasks/{tid}/report?lang=en", headers=tokens["ct05"], data={
        "summary": "Both potholes cut, cleaned and patched with hot mix; rolled and opened.", "repair_method": "Hot mix patch",
        "area_sqm": "4", "bill_amount_inr": "30000", "bill_ref": "DPS/77"},
        files=[("files", ("after.jpg", jpeg_with_metadata(), "image/jpeg")),
               ("bill_files", ("bill.pdf", demo_bill_pdf("bill").getvalue(), "application/pdf"))])
    assert rep.status_code == 200, rep.text
    r0 = rep.json()["reports"][0]
    checks = {c["code"]: c for c in r0["checks"]}
    assert "bill_over_rate" in checks and "188%" in checks["bill_over_rate"]["text"]     # 30000 vs 2600 x 4 sqm
    assert "dlp_road" in checks and r0["bills"] and r0["evidence"]
    assert client.get(f"/api/tickets/{a}").json()["status"] == "work_submitted"
    # evidence is not public before approval; bills never are
    assert client.get(f"/api/tickets/{a}").json()["repair_evidence"] == []

    assert client.post(f"/api/tasks/{tid}/approve", json={}, headers=tokens["auditor"]).status_code == 403
    assert client.post(f"/api/tasks/{tid}/approve", json={}, headers=tokens["ct05"]).status_code == 403
    done = client.post(f"/api/tasks/{tid}/approve", json={"note": "Verified on site"}, headers=tokens["officer"])
    assert done.status_code == 200 and set(done.json()["resolved"]) == {a, b, dup}
    for x in (a, b, dup):
        assert client.get(f"/api/tickets/{x}").json()["status"] == "resolved"
    pub = client.get(f"/api/tickets/{a}").json()
    assert pub["task"]["approved_cost_inr"] == 30000 and pub["task"]["contractor_name"]
    assert [m["kind"] for m in pub["repair_evidence"]] == ["photo"]                        # after-photo now public, bill is not
    # the citizen was told, in their language
    n = client.get("/api/me/notifications?lang=mr", headers=me).json()
    assert any(i["kind"] == "ticket_resolved" and i["entity_id"] == a and "निकाली" in i["text"] for i in n["items"])
    assert events.verify(conn)["ok"]


def test_send_back_and_cancel(client, tokens, ke_points):
    a = _verified(client, tokens, ke_points["ke"][3])
    tid = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a]}, headers=tokens["officer"]).json()["task_id"]
    client.post(f"/api/tasks/{tid}/report", headers=tokens["ct05"], data={"summary": "Patched the pothole with cold mix.",
                "repair_method": "Cold mix patch", "area_sqm": "2", "bill_amount_inr": "3600"})
    assert client.post(f"/api/tasks/{tid}/send-back", json={"reason": "x"}, headers=tokens["officer"]).status_code == 422
    r = client.post(f"/api/tasks/{tid}/send-back", json={"reason": "No photo of the finished work."}, headers=tokens["officer"])
    assert r.json()["status"] == "rework" and client.get(f"/api/tickets/{a}").json()["status"] == "in_progress"
    k = client.get(f"/api/tasks/{tid}", headers=tokens["ct05"]).json()
    assert k["reports"][0]["decision"] == "rejected" and k["actions"]["submit_report"]
    notes = client.get("/api/me/notifications?lang=en", headers=tokens["ct05"]).json()["items"]
    assert any(i["kind"] == "task_rework" and "No photo" in i["text"] for i in notes)
    assert client.post(f"/api/tasks/{tid}/cancel", json={"reason": "Road handed to MMRDA"}, headers=tokens["officer"]).status_code == 200
    t = client.get(f"/api/tickets/{a}").json()
    assert t["status"] == "verified" and t["task"] is None                        # back in the pool for a new task


def test_notifications_read_flow(client, tokens):
    n = client.get("/api/me/notifications", headers=tokens["citizen"]).json()
    assert n["items"] and n["unread"] >= 1
    first = n["items"][0]["id"]
    assert client.post("/api/me/notifications/read", json={"ids": [first]}, headers=tokens["citizen"]).json()["marked"] == 1
    assert client.post("/api/me/notifications/read", json={}, headers=tokens["citizen"]).status_code == 200
    assert client.get("/api/me/notifications", headers=tokens["citizen"]).json()["unread"] == 0
    assert client.get("/api/me/notifications").status_code == 401


def test_auditor_gets_no_operational_notifications(conn):
    aud = db.one(conn, "SELECT user_id FROM app_user WHERE login='audit-01'")["user_id"]
    assert db.one(conn, "SELECT COUNT(*) n FROM notification WHERE user_id=?", (aud,))["n"] == 0


def test_contractor_can_reply_only_to_findings_about_itself(client, tokens, conn):
    own = db.one(conn, "SELECT finding_id FROM finding WHERE contractor_id='CT05' AND polarity='concern' LIMIT 1")["finding_id"]
    other = db.one(conn, "SELECT finding_id FROM finding WHERE contractor_id='CT03' AND polarity='concern' LIMIT 1")["finding_id"]
    assert client.post("/api/contractor/reply", json={"finding_id": other, "reply_text": "Not ours."}, headers=tokens["ct05"]).status_code == 404
    assert client.post("/api/contractor/reply", json={"finding_id": own, "reply_text": "Site had a burst pipe."}, headers=tokens["ct05"]).status_code == 200
    f = db.one(conn, "SELECT subject_type, subject_id FROM finding WHERE finding_id=?", (own,))
    shown = client.get(f"/api/findings?subject_type={f['subject_type']}&subject_id={f['subject_id']}").json()
    assert next(x for x in shown if x["finding_id"] == own)["reply"]["text"] == "Site had a burst pipe."


# ---- integrity ------------------------------------------------------------------------------------------------
def test_ticket_event_log_is_append_only_and_tamper_evident(db_copy):
    assert events.verify(db_copy)["ok"]
    with pytest.raises(sqlite3.DatabaseError):
        db_copy.execute("UPDATE ticket_event SET note='edited' WHERE seq=1")
    with pytest.raises(sqlite3.DatabaseError):
        db_copy.execute("DELETE FROM ticket_event WHERE seq=1")
    db_copy.execute("DROP TRIGGER ticket_event_no_update")
    db_copy.execute("UPDATE ticket_event SET to_status='resolved' WHERE seq=2")
    db_copy.commit()
    v = events.verify(db_copy)
    assert v["ok"] is False and v["first_broken_seq"] == 2


def test_live_data_survives_a_pipeline_rebuild(db_copy):
    from pipeline import run
    before = db.one(db_copy, "SELECT COUNT(*) n FROM ticket")["n"]
    users = db.one(db_copy, "SELECT COUNT(*) n FROM app_user")["n"]
    assert before > 0
    run.run(force=True, conn=db_copy, quiet=True)
    assert db.one(db_copy, "SELECT COUNT(*) n FROM ticket")["n"] == before
    assert db.one(db_copy, "SELECT COUNT(*) n FROM app_user")["n"] == users
    assert events.verify(db_copy)["ok"]


def test_concurrent_complaints_never_fork_the_log_or_reuse_ids(client, ke_points, conn):
    heads = [new_citizen(client, f"96000000{i:02d}") for i in range(8)]
    lat, lon = ke_points["ke"][4]
    barrier = threading.Barrier(8)

    def go(h):
        barrier.wait()
        return raise_ticket(client, h, lat, lon)

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(go, heads))
    assert [r.status_code for r in res] == [200] * 8
    ids = [r.json()["ticket_id"] for r in res]
    assert len(set(ids)) == 8
    assert events.verify(conn)["ok"]


def test_bot_answers_about_app_complaints(client, ke_points):
    tid = raise_ticket(client, fresh_citizen(client), *ke_points["ke"][0]).json()["ticket_id"]
    j = client.post("/api/ask", json={"question": f"what is the status of {tid.lower()}?", "lang": "en"}).json()
    assert tid in j["answer"] and "waiting for verification" in j["answer"] and "citizen" not in j["answer"].lower()


# ---- "me too": support an existing complaint instead of raising a new one ------------------------------------
def citizen_with_email(client, mobile, email):
    r = client.post("/api/auth/citizen/register", json={"mobile": mobile, "password": "citizen-pass-1", "consent": True, "email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_upvote_instead_of_raising_a_duplicate(client, tokens, ke_points):
    owner, fan = fresh_citizen(client), fresh_citizen(client)
    pt = ke_points["ke"][4]
    tid = raise_ticket(client, owner, *pt).json()["ticket_id"]
    # while raising a new complaint at the same spot the citizen is offered the existing one
    near = client.get(f"/api/tickets/nearby?lat={pt[0]}&lon={pt[1]}&category=Pothole", headers=fan).json()["items"]
    assert tid in [x["ticket_id"] for x in near] and all("distance_m" in x for x in near)
    other_cat = client.get(f"/api/tickets/nearby?lat={pt[0]}&lon={pt[1]}&category=Waterlogging").json()["items"]
    assert tid not in [x["ticket_id"] for x in other_cat]                                  # only the same kind of problem
    assert client.get("/api/tickets/nearby?lat=10&lon=10").status_code == 422             # outside Mumbai

    assert client.post(f"/api/tickets/{tid}/upvote").status_code == 401                   # a login is needed
    assert client.post(f"/api/tickets/{tid}/upvote", headers=tokens["officer"]).status_code == 403
    r = client.post(f"/api/tickets/{tid}/upvote", headers=owner)
    assert r.status_code == 409 and r.json()["code"] == "own_complaint"
    assert client.post(f"/api/tickets/{tid}/upvote", headers=fan).json() == {"ticket_id": tid, "upvotes": 1, "upvoted_by_me": True}
    assert client.post(f"/api/tickets/{tid}/upvote", headers=fan).json()["upvotes"] == 1  # idempotent: one vote each
    other = fresh_citizen(client)
    assert client.post(f"/api/tickets/{tid}/upvote", headers=other).json()["upvotes"] == 2
    d = client.get(f"/api/tickets/{tid}", headers=fan).json()
    assert d["upvotes"] == 2 and d["upvoted_by_me"] is True and d["can_upvote"] is True
    pub = client.get(f"/api/tickets/{tid}").json()
    assert pub["upvotes"] == 2 and pub["upvoted_by_me"] is False and pub["can_upvote"] is False
    assert "u_" not in json.dumps(pub)                                                    # the count is public, the voters are not
    assert client.get(f"/api/tickets/{tid}", headers=owner).json()["can_upvote"] is False
    assert client.get("/api/tickets?sort=upvotes&limit=1").json()["items"][0]["upvotes"] >= 2

    assert client.post(f"/api/tickets/{tid}/unvote", headers=other).json()["upvotes"] == 1
    # closed complaints cannot be supported any more
    rej = raise_ticket(client, owner, *ke_points["ke"][5], category="Other", desc="Garbage lying on the lane for days.").json()["ticket_id"]
    client.post(f"/api/tickets/{rej}/reject", json={"reason": "not_road_issue"}, headers=tokens["officer"])
    r = client.post(f"/api/tickets/{rej}/upvote", headers=fan)
    assert r.status_code == 409 and r.json()["code"] == "not_open"


# ---- sections: roads, hospitals, schools ... -----------------------------------------------------------------
def test_complaint_sections(client, tokens, ke_points):
    assert "hospitals" in client.get("/api/live/options").json()["sections"]
    me = fresh_citizen(client)
    a = raise_ticket(client, me, *ke_points["ke"][1]).json()
    assert a["section"] == "roads"                                                       # default
    h = raise_ticket(client, me, *ke_points["ke"][2], section="hospitals").json()
    assert h["section"] == "hospitals"
    assert raise_ticket(client, me, *ke_points["ke"][3], section="spaceport").status_code == 422
    hs = client.get("/api/tickets?section=hospitals&limit=100").json()
    assert h["ticket_id"] in [x["ticket_id"] for x in hs["items"]] and all(x["section"] == "hospitals" for x in hs["items"])
    # the officer can correct the section when verifying
    r = client.post(f"/api/tickets/{a['ticket_id']}/verify", json={"section": "schools"}, headers=tokens["officer"])
    assert r.status_code == 200 and r.json()["section"] == "schools"
    assert client.post(f"/api/tickets/{h['ticket_id']}/verify", json={"section": "nope"}, headers=tokens["officer"]).status_code == 422


def test_recorded_complaints_are_listed_with_sections_and_contractor(client):
    j = client.get("/api/complaints?limit=5").json()
    assert j["total"] > 6000 and len(j["items"]) == 5
    it = j["items"][0]
    assert {"complaint_id", "received_at", "category_label", "ward_code", "link_status", "section", "upvotes"} <= set(it)
    assert "description" not in json.dumps(j) and "complainant" not in json.dumps(j)
    ke = client.get("/api/complaints?ward=K-E&limit=100").json()
    assert 0 < ke["total"] < j["total"] and all(x["ward_code"] == "K/E" for x in ke["items"])
    fixed = client.get("/api/complaints?status=fixed&limit=100").json()["items"]
    assert fixed and all(x["contractor_name"] for x in fixed)                           # the track shows who did the work
    never = client.get("/api/complaints?status=never_fixed&limit=3").json()["items"]
    assert never and all(x["contractor_name"] is None for x in never)
    for sec in ("hospitals", "schools", "roads"):
        got = client.get(f"/api/complaints?section={sec}&limit=20").json()
        assert all(x["section"] == sec for x in got["items"])
    assert client.get("/api/complaints?section=hospitals").json()["total"] > 0
    top = client.get("/api/complaints?sort=upvotes&limit=2").json()["items"]
    assert top[0]["upvotes"] >= top[1]["upvotes"]
    # the track of one recorded complaint names the contractor on the assignment step
    c = client.get(f"/api/complaints/{fixed[0]['complaint_id']}?lang=en").json()
    assert c["section"] in ("roads", "hospitals", "schools")
    assert [e["contractor_name"] for e in c["events"] if e["kind"] == "assigned"] == [fixed[0]["contractor_name"]]


def test_app_complaint_track_names_the_contractor(client, tokens, ke_points):
    me = fresh_citizen(client)
    a = _verified(client, tokens, ke_points["ke"][6], citizen=me)
    assert client.get(f"/api/tickets/{a}").json()["contractor"] is None                 # not assigned yet
    client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a]}, headers=tokens["officer"])
    d = client.get(f"/api/tickets/{a}").json()
    assert d["contractor"]["contractor_id"] == "CT05" and d["contractor"]["name"]
    ev = [e for e in d["events"] if e["event"] == "assigned"][0]
    assert ev["contractor"]["name"] == d["contractor"]["name"]                           # the history says who it went to
    row = [x for x in client.get("/api/tickets?limit=100").json()["items"] if x["ticket_id"] == a][0]
    assert row["contractor_name"] == d["contractor"]["name"]


def test_default_language_is_english(client):
    j = client.get("/api/live/options").json()
    assert {r["code"]: r["label"] for r in j["reject_reasons"]}["not_bmc_road"] == "the road is not maintained by BMC"


# ---- e-mail: complaint resolved -> citizen (and supporters) -------------------------------------------------------
def test_resolution_email_goes_to_the_citizen_and_supporters_only_if_they_have_an_address(client, tokens, ke_points, conn):
    owner = citizen_with_email(client, "9511000001", "owner.one@wardledger.example")
    fan = citizen_with_email(client, "9511000002", "fan.two@wardledger.example")
    silent = fresh_citizen(client)                                                       # no e-mail address on file
    a = _verified(client, tokens, ke_points["ke"][7], citizen=owner)
    for h in (fan, silent):
        assert client.post(f"/api/tickets/{a}/upvote", headers=h).status_code == 200
    tid = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a]}, headers=tokens["officer"]).json()["task_id"]
    client.post(f"/api/tasks/{tid}/start", headers=tokens["ct05"])
    client.post(f"/api/tasks/{tid}/report", headers=tokens["ct05"], data={
        "summary": "Pothole cut, cleaned and patched with hot mix; rolled and opened.", "repair_method": "Hot mix patch",
        "area_sqm": "3", "bill_amount_inr": "7800", "bill_ref": "DPS/9"},
        files=[("files", ("after.jpg", jpeg_with_metadata(), "image/jpeg"))])
    assert db.rows(conn, "SELECT 1 FROM email_outbox WHERE entity_id=?", (a,)) == []              # nothing before approval
    assert client.post(f"/api/tasks/{tid}/approve", json={}, headers=tokens["officer"]).status_code == 200

    mails = db.rows(conn, "SELECT * FROM email_outbox WHERE entity_id=? AND kind='ticket_resolved' ORDER BY email_id", (a,))
    assert [m["to_addr"] for m in mails] == ["owner.one@wardledger.example", "fan.two@wardledger.example"]
    assert all(m["status"] == "logged" for m in mails)                                   # no SMTP configured: logged, not sent
    body = mails[0]["body"]
    assert a in body and "resolved" in body and "Hello" in body
    assert "Work carried out by:" in body and "7,800" in body and f"/ticket/{a}" in body
    assert a in mails[0]["subject"]
    # supporters are told in-app as well
    assert any(i["kind"] == "ticket_resolved" for i in client.get("/api/me/notifications", headers=fan).json()["items"])
    # e-mail addresses never leak into the audit log or the public API
    assert "owner.one@" not in json.dumps(db.rows(conn, "SELECT detail_json, actor FROM audit_log"))
    assert "owner.one@" not in json.dumps(client.get(f"/api/tickets/{a}").json())
    # re-flushing never sends the same mail twice
    from live import mailer
    assert mailer.flush(conn)["logged"] == 0


def test_contact_settings(client):
    h = fresh_citizen(client)
    assert client.post("/api/me/contact", json={"email": "not-an-address"}, headers=h).status_code == 422
    r = client.post("/api/me/contact", json={"email": "Me.Citizen@WardLedger.example", "lang": "mr"}, headers=h)
    assert r.json() == {"email": "me.citizen@wardledger.example"}
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "me.citizen@wardledger.example" and me["mail_lang"] == "mr"
    assert client.post("/api/me/contact", json={"email": ""}, headers=h).json() == {"email": None}   # clearing is allowed
    assert client.post("/api/me/contact", json={"email": "a@b.example"}).status_code == 401


# ---- e-mail: task past its deadline -> contractor ---------------------------------------------------------------
def test_overdue_task_reminds_the_contractor_once(client, tokens, ke_points, conn):
    before = {x["contractor_id"]: x for x in client.get("/api/contractors").json()}["CT05"]["score"]
    me = fresh_citizen(client)
    a = _verified(client, tokens, ke_points["ke"][0], citizen=me)
    late = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [a], "due_at": "2024-01-02T10:00"},
                       headers=tokens["officer"]).json()["task_id"]
    b = _verified(client, tokens, ke_points["ke"][1])
    fine = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [b]}, headers=tokens["officer"]).json()["task_id"]
    c = _verified(client, tokens, ke_points["ke"][2])
    waiting = client.post("/api/tasks", json={"contractor_id": "CT05", "ticket_ids": [c], "due_at": "2024-01-02T10:00"},
                          headers=tokens["officer"]).json()["task_id"]
    client.post(f"/api/tasks/{waiting}/start", headers=tokens["ct05"])
    client.post(f"/api/tasks/{waiting}/report", headers=tokens["ct05"], data={
        "summary": "Patched with hot mix, rolled and opened to traffic.", "repair_method": "Hot mix patch", "area_sqm": "2",
        "bill_amount_inr": "5000"}, files=[("files", ("after.jpg", jpeg_with_metadata(), "image/jpeg"))])

    assert client.post("/api/tasks/check-overdue", headers=tokens["ct05"]).status_code == 403    # officers only
    assert client.post("/api/tasks/check-overdue", headers=tokens["auditor"]).status_code == 403
    r = client.post("/api/tasks/check-overdue", headers=tokens["officer"]).json()
    assert late in r["notified"]
    assert fine not in r["notified"]                                  # deadline not reached
    assert waiting not in r["notified"]                               # submitted: it is the officer's turn, not the contractor's
    mails = db.rows(conn, "SELECT * FROM email_outbox WHERE kind='task_overdue' AND entity_id=?", (late,))
    assert [m["to_addr"] for m in mails] == ["ct05@contractors.wardledger.example"]
    assert late in mails[0]["subject"] and "2024-01-02" in mails[0]["body"] and f"/tasks/{late}" in mails[0]["body"]
    assert "assigned, not started" in mails[0]["body"]
    ct = client.get("/api/me/notifications", headers=tokens["ct05"]).json()["items"]
    assert any(i["kind"] == "task_overdue" and i["entity_id"] == late for i in ct)
    off = client.get("/api/me/notifications", headers=tokens["officer"]).json()["items"]
    assert any(i["kind"] == "task_overdue_officer" and i["entity_id"] == late for i in off)
    # the complaint's track shows the deadline passed, neutrally
    assert "deadline_passed" in [e["event"] for e in client.get(f"/api/tickets/{a}").json()["events"]]
    assert client.get(f"/api/tasks/{late}", headers=tokens["officer"]).json()["overdue_notified_at"]
    # once only
    assert late not in client.post("/api/tasks/check-overdue", headers=tokens["officer"]).json()["notified"]
    assert len(db.rows(conn, "SELECT 1 FROM email_outbox WHERE kind='task_overdue' AND entity_id=?", (late,))) == 1
    assert events.verify(conn)["ok"]
    # a missed deadline is part of the contractor's record
    after = {x["contractor_id"]: x for x in client.get("/api/contractors").json()}["CT05"]["score"]
    assert after["basis"]["app_tasks"] > before["basis"]["app_tasks"] and after["sla_pct"] <= before["sla_pct"]


def test_a_bare_due_date_is_due_at_the_end_of_that_day():
    from datetime import datetime, timedelta, timezone
    from live import tasks as TS
    today_ist = datetime.now(TS.IST).date().isoformat()
    assert TS.due_datetime(today_ist) > datetime.now(timezone.utc)                       # not overdue on its own due date
    assert TS.due_datetime("2024-01-02") < datetime.now(timezone.utc)
    assert TS.due_datetime("garbage") is None and TS.due_datetime(None) is None
    assert TS.due_datetime("2024-01-02T10:00").utcoffset() == timedelta(hours=5, minutes=30)


# ---- contractor scores ----------------------------------------------------------------------------------------------
def test_every_contractor_has_a_transparent_score(client):
    rows = client.get("/api/contractors?lang=en").json()
    assert len(rows) == 8
    for c in rows:
        s = c["score"]
        assert 0 <= s["score"] <= 100 and s["band"] in ("reliable", "mixed", "below")
        assert all(0 <= s[k] <= 100 for k in ("durability_pct", "sla_pct", "billing_pct"))
        assert 0 <= s["flood_index"] <= 1 and s["context_adjusted"] and sum(s["weights"].values()) == 100
        w = s["weights"]
        want = round(w["durability"] / 100 * s["durability_pct"] + w["sla"] / 100 * s["sla_pct"] + w["billing"] / 100 * s["billing_pct"])
        assert abs(s["score"] - want) <= 1                                               # the shown parts add up to the shown score
        assert str(s["score"]) in s["verdict"] and s["band_label"] in s["verdict"]
        assert not any(x in s["verdict"].lower() for x in ("fraud", "corrupt", "scam", "theft"))
    assert len({c["score"]["score"] for c in rows}) > 3                                  # not one number for everybody
    one = client.get("/api/contractors/CT01/scorecard?lang=mr").json()
    assert one["score"]["score"] == {c["contractor_id"]: c for c in rows}["CT01"]["score"]["score"]
    assert one["score"]["band_label"] in ("विश्वासार्ह", "संमिश्र नोंद", "अपेक्षेपेक्षा कमी")
