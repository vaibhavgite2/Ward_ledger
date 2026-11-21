"""Shared helpers for live operations: time, IDs, errors, the authenticated viewer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

GENESIS = "0" * 64


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LiveError(Exception):
    """A user-facing workflow error. Routers turn it into an HTTP response."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Viewer:
    user_id: str
    role: str                 # citizen | officer | contractor
    login: str
    display_name: str | None = None
    contractor_id: str | None = None
    ward_code: str | None = None
    designation: str | None = None
    can_act: bool = True              # officers: may verify, assign, approve (auditors: False)

    @property
    def actor_ref(self) -> str:
        """How this person is recorded in logs. Officers by employee ID (as in `fact.promoted_by`),
        contractors by firm, citizens by an opaque account ID (never their mobile number)."""
        if self.role == "officer":
            return f"user:{self.login}"
        if self.role == "contractor":
            return f"contractor:{self.contractor_id}"
        return f"citizen:{self.user_id}"


def next_id(conn, name: str, prefix: str, width: int = 6) -> str:
    """Sequential human-readable IDs (CMP-000001). Must run inside db.write_tx."""
    if not conn.in_transaction:
        raise RuntimeError("next_id must run inside db.write_tx")
    row = conn.execute("UPDATE id_counter SET value = value + 1 WHERE name=? RETURNING value", (name,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO id_counter(name, value) VALUES (?, 1)", (name,))
        value = 1
    else:
        value = row[0]
    return f"{prefix}-{value:0{width}d}"
