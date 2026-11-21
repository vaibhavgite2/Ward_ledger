"""Ticket and task tracking log: append-only, hash-chained (row_hash = sha256(prev_hash || row)).

Every status change of a complaint ticket or task is one row. The current status on `ticket`/`task`
is only a convenience projection; this log is the record an auditor trusts.
"""
from __future__ import annotations

import hashlib
import json

import db
from live.common import GENESIS, now_iso
from rules.promote import _canon

KEYS = ["at", "entity_type", "entity_id", "event", "from_status", "to_status", "actor_role", "actor_id", "note", "data_json"]


def row_hash(prev: str, row: dict) -> str:
    return hashlib.sha256((prev + _canon({k: row.get(k) for k in KEYS})).encode("utf-8")).hexdigest()


def append(conn, entity_type: str, entity_id: str, event: str, actor_role: str, actor_id: str, *,
           from_status=None, to_status=None, note=None, data=None) -> int:
    """Must run inside db.write_tx: the write lock makes read-last-hash + insert atomic."""
    if not conn.in_transaction:
        raise RuntimeError("events.append must run inside db.write_tx")
    last = conn.execute("SELECT row_hash FROM ticket_event ORDER BY seq DESC LIMIT 1").fetchone()
    prev = last[0] if last else GENESIS
    row = {"at": now_iso(), "entity_type": entity_type, "entity_id": entity_id, "event": event,
           "from_status": from_status, "to_status": to_status, "actor_role": actor_role, "actor_id": actor_id,
           "note": note, "data_json": json.dumps(data, ensure_ascii=False, sort_keys=True) if data is not None else None}
    h = row_hash(prev, row)
    cur = conn.execute(
        f"INSERT INTO ticket_event({','.join(KEYS)}, prev_hash, row_hash) VALUES ({','.join('?' * (len(KEYS) + 2))})",
        [row[k] for k in KEYS] + [prev, h])
    return cur.lastrowid


def history(conn, entity_type: str, entity_id: str) -> list[dict]:
    return db.rows(conn, "SELECT * FROM ticket_event WHERE entity_type=? AND entity_id=? ORDER BY seq", (entity_type, entity_id))


def verify(conn) -> dict:
    prev, n = GENESIS, 0
    for r in conn.execute("SELECT * FROM ticket_event ORDER BY seq"):
        if r["prev_hash"] != prev or row_hash(prev, dict(r)) != r["row_hash"]:
            return {"ok": False, "checked": n, "first_broken_seq": r["seq"], "head_hash": None}
        prev = r["row_hash"]
        n += 1
    return {"ok": True, "checked": n, "first_broken_seq": None, "head_hash": prev if n else None}
