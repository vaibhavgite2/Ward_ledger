"""Request dependencies: per-request DB connection, role gate, language, cached planner reference."""
from __future__ import annotations

import threading

from fastapi import Depends, Header, HTTPException, Query

import db
from agents import budget
from live import users
from live.common import Viewer

LANGS = ("en", "mr", "hi")


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def lang_q(lang: str = Query("en", description="en | mr | hi")) -> str:
    return lang if lang in LANGS else "en"


def bearer_token(authorization: str | None = Header(None)) -> str | None:
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip() or None
    return None


def viewer_opt(token: str | None = Depends(bearer_token), conn=Depends(get_conn)) -> Viewer | None:
    """The logged-in person, or None. Browsing never requires a login."""
    return users.viewer_for_token(conn, token)


def require(*roles: str):
    """Role-based access from the session (DFD 1.1-1.3). The client cannot claim a role: it comes from the
    account that logged in on that role's panel."""
    def dep(v: Viewer | None = Depends(viewer_opt)) -> Viewer:
        if v is None:
            raise HTTPException(status_code=401, detail="Please log in.", headers={"WWW-Authenticate": "Bearer"})
        if roles and v.role not in roles:
            raise HTTPException(status_code=403, detail=f"This needs a {' or '.join(roles)} login.")
        return v
    return dep


_REF: dict = {}
_LOCK = threading.Lock()


def planner_ref(conn=Depends(get_conn)):
    """Reference tables for the planner, cached per pipeline run. Built fully before it is published, and
    under a lock, so concurrent first requests can never observe a half-initialised cache."""
    stamp = db.one(conn, "SELECT COALESCE(MAX(seq),0) s FROM audit_log WHERE action='pipeline_run'")["s"]
    cached = _REF.get("v")
    if cached and cached[0] == stamp:
        return cached[1]
    with _LOCK:
        cached = _REF.get("v")
        if not (cached and cached[0] == stamp):
            _REF["v"] = (stamp, budget.Ref(conn))
        return _REF["v"][1]
