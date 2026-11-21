"""Request dependencies: per-request DB connection, role gate, language, cached planner reference."""
from __future__ import annotations

import threading

from fastapi import Depends, Header, HTTPException, Query

import db
from agents import budget

LANGS = ("mr", "en", "hi")


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def lang_q(lang: str = Query("mr", description="mr | en | hi")) -> str:
    return lang if lang in LANGS else "en"


def require_role(*allowed: str):
    """Demo-only role gate (SPEC §7): X-Role: public | officer | auditor. Replace with SSO in Phase 2."""
    def dep(x_role: str = Header("public")) -> str:
        if x_role not in allowed:
            raise HTTPException(status_code=403, detail=f"This endpoint requires role: {' or '.join(allowed)}")
        return x_role
    return dep


def actor(x_user: str = Header("ae-demo")) -> str:
    return "user:" + "".join(ch for ch in x_user if ch.isalnum() or ch in "-_")[:24]


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
