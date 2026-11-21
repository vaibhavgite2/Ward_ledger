"""Live complaint tickets, contractor tasks, repair reports, media and notifications (DFD 2.0 - 6.0).

Reading the complaints section never needs a login. Raising a complaint needs a citizen login;
verification, assignment and approval need an officer login; tasks and reports need a contractor login.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db
from agents import complaint_parser as cp
from app.deps import get_conn, lang_q, planner_ref, require, viewer_opt
from live import mailer, media, notify, overdue, tasks, tickets, users
from live import text as LT
from live.common import LiveError, Viewer

router = APIRouter(prefix="/api", tags=["live"])


# ---- options for forms --------------------------------------------------------------------------------
@router.get("/live/options")
def options(lang: str = Depends(lang_q), conn=Depends(get_conn)):
    return {
        "categories": cp.CATEGORIES,
        "sections": list(tickets.SECTIONS),
        "reject_reasons": [{"code": k, "label": v[lang]} for k, v in LT.REJECT_REASON.items()],
        "methods": db.rows(conn, "SELECT repair_method, unit, standard_rate_inr FROM rate_card ORDER BY repair_method"),
        "contractors": db.rows(conn, "SELECT contractor_id, contractor_name FROM contractors ORDER BY contractor_name"),
        "limits": {"locations": tickets.MAX_LOCATIONS, "photos": tickets.MAX_PHOTOS, "videos": tickets.MAX_VIDEOS,
                   "photo_mb": media.LIMIT["photo"] // media.MB, "video_mb": media.LIMIT["video"] // media.MB,
                   "bill_mb": media.LIMIT["bill"] // media.MB, "description": [tickets.DESC_MIN, tickets.DESC_MAX],
                   "evidence": tasks.MAX_EVIDENCE, "bills": tasks.MAX_BILLS},
    }


# ---- complaint tickets --------------------------------------------------------------------------------
@router.get("/tickets")
def list_tickets(status: str | None = None, ward: str | None = None, category: str | None = None, q: str | None = None,
                 section: str | None = None, sort: str = "recent",
                 mine: bool = False, limit: int = Query(30, le=100), offset: int = 0,
                 v: Viewer | None = Depends(viewer_opt), conn=Depends(get_conn)):
    ward = ward.replace("-", "/").upper() if ward else None
    return tickets.list_tickets(conn, v, status=status, ward=ward, category=category, q=q, mine=mine, limit=limit,
                                offset=offset, section=section, sort=sort)


@router.get("/tickets/nearby")
def nearby_tickets(lat: float, lon: float, category: str | None = None, radius: float = Query(250, ge=20, le=1000),
                   v: Viewer | None = Depends(viewer_opt), conn=Depends(get_conn)):
    """Open complaints around a point, so a citizen can support one ("me too") instead of raising a duplicate."""
    return {"items": tickets.nearby(conn, v, lat, lon, category, radius)}


@router.post("/tickets")
def raise_ticket(category: str = Form(...), description: str = Form(...), locality_text: str | None = Form(None),
                 locations: str | None = Form(None), section: str | None = Form(None),
                 files: list[UploadFile] | None = File(None),
                 v: Viewer = Depends(require("citizen")), conn=Depends(get_conn)):
    tid = tickets.create(conn, v, category=category, description=description, locality_text=locality_text,
                         locations=locations, files=[f.file for f in (files or []) if f.filename], section=section)
    return tickets.detail(conn, tid, v)


@router.post("/tickets/{tid}/upvote")
def upvote_ticket(tid: str, v: Viewer = Depends(require("citizen")), conn=Depends(get_conn)):
    return tickets.upvote(conn, v, tid.upper())


@router.post("/tickets/{tid}/unvote")
def unvote_ticket(tid: str, v: Viewer = Depends(require("citizen")), conn=Depends(get_conn)):
    return tickets.unvote(conn, v, tid.upper())


@router.get("/tickets/{tid}")
def get_ticket(tid: str, v: Viewer | None = Depends(viewer_opt), conn=Depends(get_conn)):
    return tickets.detail(conn, tid.upper(), v)


class VerifyIn(BaseModel):
    category: str | None = None
    section: str | None = None
    note: str | None = Field(default=None, max_length=500)


class RejectIn(BaseModel):
    reason: str
    note: str | None = Field(default=None, max_length=500)
    duplicate_of: str | None = Field(default=None, max_length=20)


@router.post("/tickets/{tid}/verify")
def verify_ticket(tid: str, body: VerifyIn, v: Viewer = Depends(require("officer")), conn=Depends(get_conn)):
    return tickets.verify(conn, v, tid.upper(), body.category, body.note, body.section)


@router.post("/tickets/{tid}/reject")
def reject_ticket(tid: str, body: RejectIn, background: BackgroundTasks, v: Viewer = Depends(require("officer")),
                  conn=Depends(get_conn)):
    out = tickets.reject(conn, v, tid.upper(), body.reason, body.note, body.duplicate_of)
    background.add_task(mailer.flush_in_background)          # e-mail goes out after the response
    return out


# ---- tasks ---------------------------------------------------------------------------------------------
class PreviewIn(BaseModel):
    contractor_id: str
    ticket_ids: list[str] = Field(max_length=tasks.MAX_TICKETS)


class TaskIn(PreviewIn):
    repair_method: str | None = None
    est_area_sqm: float | None = None
    est_cost_inr: float | None = None
    due_at: str | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=120)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ReasonIn(BaseModel):
    reason: str = Field(max_length=1000)


@router.get("/tasks")
def list_tasks(status: str | None = None, ward: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
               v: Viewer = Depends(require("officer", "contractor")), conn=Depends(get_conn)):
    ward = ward.replace("-", "/").upper() if ward else None
    return tasks.list_tasks(conn, v, status=status, ward=ward, limit=limit, offset=offset)


@router.post("/tasks/preview")
def preview_task(body: PreviewIn, lang: str = Depends(lang_q), v: Viewer = Depends(require("officer")),
                 conn=Depends(get_conn), ref=Depends(planner_ref)):
    return tasks.preview(conn, ref, body.contractor_id, body.ticket_ids, lang)


@router.post("/tasks")
def create_task(body: TaskIn, lang: str = Depends(lang_q), v: Viewer = Depends(require("officer")),
                conn=Depends(get_conn), ref=Depends(planner_ref)):
    tid = tasks.create(conn, v, ref, **body.model_dump())
    return tasks.detail(conn, v, tid, lang)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, lang: str = Depends(lang_q), v: Viewer = Depends(require("officer", "contractor")), conn=Depends(get_conn)):
    return tasks.detail(conn, v, task_id.upper(), lang)


@router.post("/tasks/check-overdue")
def check_overdue(v: Viewer = Depends(require("officer")), conn=Depends(get_conn)):
    """Run the deadline check now (it also runs by itself every few minutes): reminds contractors of overdue tasks."""
    tasks._officer(v)
    return overdue.run_once(conn)


@router.post("/tasks/{task_id}/start")
def start_task(task_id: str, v: Viewer = Depends(require("contractor")), conn=Depends(get_conn)):
    return tasks.start(conn, v, task_id.upper())


@router.post("/tasks/{task_id}/report")
def submit_report(task_id: str, summary: str = Form(...), bill_amount_inr: str = Form(...), repair_method: str | None = Form(None),
                  area_sqm: str | None = Form(None), bill_ref: str | None = Form(None),
                  files: list[UploadFile] | None = File(None), bill_files: list[UploadFile] | None = File(None),
                  lang: str = Depends(lang_q), v: Viewer = Depends(require("contractor")), conn=Depends(get_conn)):
    tasks.submit_report(conn, v, task_id.upper(), summary=summary, repair_method=repair_method, area_sqm=area_sqm,
                        bill_amount_inr=bill_amount_inr, bill_ref=bill_ref,
                        evidence_files=[f.file for f in (files or []) if f.filename],
                        bill_files=[f.file for f in (bill_files or []) if f.filename])
    return tasks.detail(conn, v, task_id.upper(), lang)


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, body: NoteIn, background: BackgroundTasks, v: Viewer = Depends(require("officer")),
                 conn=Depends(get_conn)):
    out = tasks.approve(conn, v, task_id.upper(), body.note)
    background.add_task(mailer.flush_in_background)          # "your complaint was resolved" e-mails, after the response
    return out


@router.post("/tasks/{task_id}/send-back")
def send_back_task(task_id: str, body: ReasonIn, v: Viewer = Depends(require("officer")), conn=Depends(get_conn)):
    return tasks.send_back(conn, v, task_id.upper(), body.reason)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, body: ReasonIn, v: Viewer = Depends(require("officer")), conn=Depends(get_conn)):
    return tasks.cancel(conn, v, task_id.upper(), body.reason)


# ---- notifications ---------------------------------------------------------------------------------------
class ReadIn(BaseModel):
    ids: list[int] | None = None


@router.get("/me/notifications")
def my_notifications(lang: str = Depends(lang_q), v: Viewer = Depends(require()), conn=Depends(get_conn)):
    return notify.list_for(conn, v.user_id, lang)


class ContactIn(BaseModel):
    email: str | None = Field(default=None, max_length=120)
    lang: str | None = Field(default=None, max_length=2)


@router.post("/me/contact")
def update_contact(body: ContactIn, v: Viewer = Depends(require()), conn=Depends(get_conn)):
    """Set or clear the e-mail address used for resolution / overdue-task e-mails."""
    return users.set_contact(conn, v, body.email, body.lang)


@router.post("/me/notifications/read")
def read_notifications(body: ReadIn, v: Viewer = Depends(require()), conn=Depends(get_conn)):
    return {"marked": notify.mark_read(conn, v.user_id, body.ids)}


# ---- contractor right of reply ---------------------------------------------------------------------------
class ContractorReplyIn(BaseModel):
    finding_id: str
    reply_text: str = Field(min_length=5, max_length=2000)


@router.post("/contractor/reply")
def contractor_reply(body: ContractorReplyIn, v: Viewer = Depends(require("contractor")), conn=Depends(get_conn)):
    """A contractor answers a finding about its own work; the reply is shown next to the finding."""
    f = db.one(conn, "SELECT * FROM finding WHERE finding_id=?", (body.finding_id,))
    if not f or f["contractor_id"] != v.contractor_id:
        raise HTTPException(404, "No such finding about your firm.")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db.write_tx(conn):
        conn.execute("INSERT INTO right_of_reply VALUES (?,?,?,?,?)", (f["subject_type"], f["subject_id"], f["finding_id"],
                                                                        body.reply_text.strip(), now))
        db.log(conn, v.actor_ref, "right_of_reply_recorded", "finding", body.finding_id)
    return {"ok": True, "received_at": now}


# ---- media -------------------------------------------------------------------------------------------------
_SAFE = {"X-Content-Type-Options": "nosniff"}


@router.get("/media/{media_id}/{variant}")
def get_media(media_id: str, variant: str, exp: int | None = None, sig: str | None = None, conn=Depends(get_conn)):
    m = db.one(conn, "SELECT * FROM media WHERE media_id=?", (media_id,))
    if not m:
        raise HTTPException(404, "Not found")
    if variant == "public":
        if not media.public_ok(conn, m):
            raise HTTPException(404, "Not found")
        return FileResponse(media.file_path(m["public_name"]), media_type="image/jpeg",
                            headers={**_SAFE, "Cache-Control": "public, max-age=3600"})
    if variant == "original":
        if exp is None or not sig or not media.check_sig(media_id, "original", exp, sig):
            raise HTTPException(403, "This link has expired or is not valid.")
        path = media.file_path(m["stored_name"])
        if not path.exists():
            raise HTTPException(404, "Not found")
        ext = m["stored_name"].rsplit(".", 1)[-1]
        disp = "attachment" if m["mime"] == "application/pdf" else "inline"
        return FileResponse(path, media_type=m["mime"], headers={
            **_SAFE, "Cache-Control": "private, max-age=600", "Content-Security-Policy": "sandbox",
            "Content-Disposition": f'{disp}; filename="{media_id}.{ext}"'})
    raise HTTPException(404, "Not found")
