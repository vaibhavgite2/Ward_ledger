"""Three separate login panels (DFD 1.1 Citizen, 1.2 Officer, 1.3 Contractor) over one user database."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import config
from app.deps import bearer_token, get_conn, lang_q, require
from live import notify, users
from live.common import LiveError, Viewer

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str = Field(max_length=64)
    password: str = Field(max_length=128)


class RegisterIn(BaseModel):
    mobile: str = Field(max_length=20)
    password: str = Field(max_length=128)
    display_name: str | None = Field(default=None, max_length=60)
    consent: bool = False
    email: str | None = Field(default=None, max_length=120)
    lang: str = Field(default="en", max_length=2)


def _session(conn, role, login, password):
    token, v = users.login(conn, role, login, password)
    return {"token": token, "user": users.public_profile(v, conn), "expires_in_hours": config.SESSION_HOURS[role]}


@router.post("/citizen/register")
def citizen_register(body: RegisterIn, conn=Depends(get_conn)):
    users.register_citizen(conn, body.mobile, body.password, body.display_name, body.consent, body.email, body.lang)
    return _session(conn, "citizen", body.mobile, body.password)


@router.post("/citizen/login")
def citizen_login(body: LoginIn, conn=Depends(get_conn)):
    return _session(conn, "citizen", body.login, body.password)


@router.post("/officer/login")
def officer_login(body: LoginIn, conn=Depends(get_conn)):
    return _session(conn, "officer", body.login, body.password)


@router.post("/contractor/login")
def contractor_login(body: LoginIn, conn=Depends(get_conn)):
    return _session(conn, "contractor", body.login, body.password)


@router.post("/logout")
def logout(token: str | None = Depends(bearer_token), conn=Depends(get_conn)):
    if not token:
        raise LiveError(401, "not_logged_in", "Not logged in.")
    users.logout(conn, token)
    return {"ok": True}


@router.get("/me")
def me(v: Viewer = Depends(require()), lang: str = Depends(lang_q), conn=Depends(get_conn)):
    n = notify.list_for(conn, v.user_id, lang, limit=1)["unread"]
    return {**users.public_profile(v, conn), "unread_notifications": n}

