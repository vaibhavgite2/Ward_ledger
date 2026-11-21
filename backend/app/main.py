"""FastAPI entrypoint. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from app.routers import audit, auth, live, officer, public
from live import overdue
from live.common import LiveError

@asynccontextmanager
async def lifespan(_app):
    conn = db.connect()
    try:
        db.init_schema(conn)      # idempotent: adds the live tables (accounts, tickets, tasks) to an older database
        if not db.one(conn, "SELECT name FROM sqlite_master WHERE name='work_orders'"):
            print("WARNING: database is empty. Run:  python -m pipeline.run")
        elif not db.one(conn, "SELECT 1 FROM app_user LIMIT 1"):
            print("NOTE: no accounts yet. For demo logins run:  python -m live.seed --demo --tickets")
    finally:
        conn.close()
    stop = threading.Event()
    overdue.start_background(stop)      # reminds contractors when a task passes its deadline (WL_OVERDUE_CHECK_MIN=0: off)
    try:
        yield
    finally:
        stop.set()


app = FastAPI(title="The Ward Ledger API", version="1.0", lifespan=lifespan,
              description="Follow the rupee: Mumbai monsoon roads. " + config.SYNTHETIC_NOTICE)

origins = [o.strip() for o in os.environ.get("WL_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Chain-OK", "X-Chain-Checked", "X-Rows"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(live.router)
app.include_router(officer.router)
app.include_router(audit.router)


@app.exception_handler(LiveError)
def _live_error(_req: Request, exc: LiveError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})
