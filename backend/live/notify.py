"""In-app notifications (the DFD's acknowledgement / verification status / resolution notification flows).
Stored as kind + params; rendered in the reader's language when listed."""
from __future__ import annotations

import json

import db
from live import text as LT
from live.common import now_iso


def notify(conn, user_ids, kind: str, entity_type: str, entity_id: str, **params) -> None:
    for uid in dict.fromkeys(u for u in user_ids if u):          # de-duplicate, keep order
        conn.execute("INSERT INTO notification(user_id, entity_type, entity_id, kind, params_json, created_at) VALUES (?,?,?,?,?,?)",
                     (uid, entity_type, entity_id, kind, json.dumps(params, ensure_ascii=False), now_iso()))


def officers_for_ward(conn, ward: str | None) -> list[str]:
    """Officers posted to the ward, plus officers with no ward (city-wide roles)."""
    return [r["user_id"] for r in db.rows(conn, "SELECT user_id FROM app_user WHERE role='officer' AND disabled=0 "
                                                "AND can_act=1 AND (ward_code IS NULL OR ward_code=?)", (ward,))]


def contractor_users(conn, contractor_id: str) -> list[str]:
    return [r["user_id"] for r in db.rows(conn, "SELECT user_id FROM app_user WHERE role='contractor' AND disabled=0 "
                                                "AND contractor_id=?", (contractor_id,))]


def list_for(conn, user_id: str, lang: str, limit: int = 50) -> dict:
    rows = db.rows(conn, "SELECT * FROM notification WHERE user_id=? ORDER BY notif_id DESC LIMIT ?", (user_id, limit))
    unread = db.one(conn, "SELECT COUNT(*) n FROM notification WHERE user_id=? AND read_at IS NULL", (user_id,))["n"]
    return {"unread": unread, "items": [{
        "id": r["notif_id"], "kind": r["kind"], "entity_type": r["entity_type"], "entity_id": r["entity_id"],
        "text": LT.render(LT.NOTIFY, r["kind"], json.loads(r["params_json"] or "{}"), lang),
        "created_at": r["created_at"], "read": r["read_at"] is not None} for r in rows]}


def mark_read(conn, user_id: str, ids: list[int] | None = None) -> int:
    with db.write_tx(conn):
        if ids:
            q = ",".join("?" * len(ids))
            cur = conn.execute(f"UPDATE notification SET read_at=? WHERE user_id=? AND read_at IS NULL AND notif_id IN ({q})",
                               [now_iso(), user_id, *ids])
        else:
            cur = conn.execute("UPDATE notification SET read_at=? WHERE user_id=? AND read_at IS NULL", (now_iso(), user_id))
    return cur.rowcount
