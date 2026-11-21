"""Demo accounts for the three login panels, and optionally demo complaints walked through the real workflow.

    python -m live.seed --demo              # accounts only (idempotent)
    python -m live.seed --demo --tickets    # plus demo complaints at every stage (only if there are none yet)

Password: $WL_DEMO_PASSWORD, or "wardledger-demo". DEMO ONLY: never seed these accounts in a real deployment.
Officer and contractor accounts are provisioned (no self-registration); citizens register themselves in the app.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import db
from live import mailer, tasks, tickets
from live.common import Viewer
from live.users import _viewer, create_user

DEFAULT_PASSWORD = "wardledger-demo"
OFFICERS = [
    ("ae-4471", "A. Kulkarni (demo)", "K/E", "Assistant Engineer (Maintenance), K/E ward"),
    ("ae-3310", "S. Shaikh (demo)", "H/W", "Assistant Engineer (Maintenance), H/W ward"),
    ("ee-1001", "R. Deshmukh (demo)", None, "Executive Engineer (Roads), all wards"),
    ("audit-01", "Chief Auditor's office (demo)", None, "Municipal Chief Auditor's office"),
]
READ_ONLY = {"audit-01"}      # separation of duties: the auditor sees everything and changes nothing
CITIZENS = [("9800000001", "Demo citizen"), ("9800000002", "Demo neighbour")]
# E-mail addresses on the reserved .example domain: nothing is ever delivered to them, so the e-mail flow can be
# demonstrated safely (messages are logged in `email_outbox` unless WL_SMTP_HOST is configured).
CITIZEN_EMAILS = {"9800000001": "demo.citizen@wardledger.example", "9800000002": "demo.neighbour@wardledger.example"}


def contractor_email(login: str) -> str:
    return f"{login}@contractors.wardledger.example"


def seed_accounts(conn, password: str) -> list[tuple]:
    made = []
    with db.write_tx(conn):
        for login, name, ward, desig in OFFICERS:
            if not db.one(conn, "SELECT 1 FROM app_user WHERE role='officer' AND login=?", (login,)):
                create_user(conn, "officer", login, password, display_name=name, ward_code=ward, designation=desig,
                            can_act=login not in READ_ONLY)
            made.append(("officer", login, name))
        for c in db.rows(conn, "SELECT contractor_id, contractor_name FROM contractors ORDER BY contractor_id"):
            login = c["contractor_id"].lower()
            if not db.one(conn, "SELECT 1 FROM app_user WHERE role='contractor' AND login=?", (login,)):
                create_user(conn, "contractor", login, password, display_name=c["contractor_name"], contractor_id=c["contractor_id"],
                            email=contractor_email(login))
            else:                                    # accounts created before e-mail existed get a demo address
                conn.execute("UPDATE app_user SET email=? WHERE role='contractor' AND login=? AND email IS NULL",
                             (contractor_email(login), login))
            made.append(("contractor", login, c["contractor_name"]))
        for mobile, name in CITIZENS:
            if not db.one(conn, "SELECT 1 FROM app_user WHERE role='citizen' AND login=?", (mobile,)):
                create_user(conn, "citizen", mobile, password, display_name=name, email=CITIZEN_EMAILS.get(mobile))
            else:
                conn.execute("UPDATE app_user SET email=? WHERE role='citizen' AND login=? AND email IS NULL",
                             (CITIZEN_EMAILS.get(mobile), mobile))
            made.append(("citizen", mobile, name))
    return made


def _viewer_for(conn, role, login) -> Viewer:
    return _viewer(db.one(conn, "SELECT * FROM app_user WHERE role=? AND login=?", (role, login)))


def demo_photo(label: str) -> io.BytesIO:
    """An obviously synthetic placeholder image (never a fake 'real' photo)."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (640, 420), (96, 96, 96))
    d = ImageDraw.Draw(im)
    for y in range(0, 420, 28):
        d.line([(0, y), (640, y + 60)], fill=(110, 110, 110), width=3)
    d.ellipse([220, 150, 420, 270], fill=(58, 52, 46), outline=(40, 36, 30), width=6)
    d.rectangle([0, 0, 640, 44], fill=(245, 230, 180))
    d.text((12, 14), f"DEMO PHOTO (synthetic) - {label}", fill=(60, 40, 10))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    buf.seek(0)
    return buf


def demo_bill_pdf(text: str) -> io.BytesIO:
    body = f"BT /F1 14 Tf 40 760 Td ({text}) Tj ET".encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    out.seek(0)
    return out


DEMO = [  # (category, description, road index, section)
    ("Pothole", "Big pothole near the bus stop. Two-wheelers are falling every evening.", 0, "transport"),
    ("Pothole", "Several potholes between the signal and the petrol pump, traffic is slowing down.", 1, "roads"),
    ("Waterlogging", "Knee-deep water near the station after every heavy rain, vehicles are stuck.", 2, "transport"),
    ("Open or broken manhole", "Open manhole without a cover near the school gate. Very dangerous for children.", 3, "schools"),
    ("Broken paver blocks", "Paver blocks uprooted on the footpath; senior citizens are tripping.", 4, "residential"),
    ("Road cave-in", "Part of the road has sunk near the pipeline work. A barricade is needed.", 5, "roads"),
    ("Other", "Garbage has not been collected for three days on this lane.", 4, "residential"),
    ("Pothole", "Deep pothole outside the hospital emergency entrance; ambulances have to slow down.", 1, "hospitals"),
]


def seed_tickets(conn, ref) -> list[str]:
    if db.one(conn, "SELECT COUNT(*) n FROM ticket")["n"]:
        return []
    citizen = _viewer_for(conn, "citizen", CITIZENS[0][0])
    officer = _viewer_for(conn, "officer", "ae-4471")
    roads = db.rows(conn, "SELECT * FROM roads WHERE ward_code='K/E' AND under_dlp='N' ORDER BY road_id LIMIT 6")
    ids = []
    for i, (cat, desc, ri, section) in enumerate(DEMO):
        r = roads[ri % len(roads)]
        lat, lon = (r["start_lat"] + r["end_lat"]) / 2, (r["start_lon"] + r["end_lon"]) / 2
        files = [demo_photo(f"{cat}, {r['road_name']}")] if cat != "Other" else []
        ids.append(tickets.create(conn, citizen, category=cat, description=desc, locality_text=None, section=section,
                                  locations=[{"lat": lat, "lon": lon, "accuracy_m": 15, "source": "gps"}], files=files))
    # 0,1 -> verified -> one task for CT05 -> started -> report -> approved (resolved)
    for t in ids[:4]:
        tickets.verify(conn, officer, t)
    t1 = tasks.create(conn, officer, ref, contractor_id="CT05", ticket_ids=ids[:2],
                      instructions="Patch both stretches with hot mix; barricade while curing.")
    ct05 = _viewer_for(conn, "contractor", "ct05")
    tasks.start(conn, ct05, t1)
    tasks.submit_report(conn, ct05, t1, summary="Both stretches cleaned, tack coat applied and patched with hot mix. Surface rolled and opened to traffic.",
                        repair_method="Hot mix patch", area_sqm=9.5, bill_amount_inr=25900, bill_ref="DPS/2026/118",
                        evidence_files=[demo_photo("after repair")], bill_files=[demo_bill_pdf("DEMO BILL (synthetic) DPS/2026/118 Rs 25,900")])
    tasks.approve(conn, officer, t1, note="Site checked on visit; both stretches patched.")
    # 2 -> verified -> task for CT07 -> started (in progress)
    t2 = tasks.create(conn, officer, ref, contractor_id="CT07", ticket_ids=[ids[2]])
    tasks.start(conn, _viewer_for(conn, "contractor", "ct07"), t2)
    # 3 stays verified (waiting for a task); 4, 5 stay submitted (waiting for verification); 6 is rejected
    tickets.reject(conn, officer, ids[6], "not_road_issue", note="Forwarded to the Solid Waste Management department.")
    # a neighbour supports the open waterlogging complaint instead of raising a new one
    tickets.upvote(conn, _viewer_for(conn, "citizen", CITIZENS[1][0]), ids[2])
    # 7 -> verified -> a task whose deadline has already passed (shows the overdue reminder to the contractor)
    tickets.verify(conn, officer, ids[7])
    t3 = tasks.create(conn, officer, ref, contractor_id="CT02", ticket_ids=[ids[7]], title="Hospital entrance pothole (demo, overdue)",
                      due_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="minutes"))
    tasks.start(conn, _viewer_for(conn, "contractor", "ct02"), t3)
    mailer.flush(conn)          # the resolution e-mails queued above: logged in email_outbox (or sent, if SMTP is configured)
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seed demo accounts / complaints (DEMO ONLY)")
    ap.add_argument("--demo", action="store_true", help="required: confirms you want demo accounts")
    ap.add_argument("--tickets", action="store_true", help="also create demo complaints at each workflow stage")
    a = ap.parse_args(argv)
    if not a.demo:
        ap.error("pass --demo to create demo accounts")
    conn = db.connect()
    db.init_schema(conn)
    if not db.one(conn, "SELECT name FROM sqlite_master WHERE name='contractors'"):
        sys.exit("Database is empty: run  python -m pipeline.run  first.")
    pw = os.environ.get("WL_DEMO_PASSWORD", DEFAULT_PASSWORD)
    made = seed_accounts(conn, pw)
    print("Demo accounts (password: %s):" % ("$WL_DEMO_PASSWORD" if "WL_DEMO_PASSWORD" in os.environ else DEFAULT_PASSWORD))
    for role, login, name in made:
        print(f"  {role:<10} {login:<12} {name}")
    if a.tickets:
        from agents import budget
        ids = seed_tickets(conn, budget.Ref(conn))
        print(f"Demo complaints: {', '.join(ids) if ids else 'skipped (complaints already exist)'}")
    conn.close()


if __name__ == "__main__":
    main()
