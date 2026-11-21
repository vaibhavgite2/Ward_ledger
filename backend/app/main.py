"""FastAPI entrypoint. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from app.routers import audit, officer, public

@asynccontextmanager
async def lifespan(_app):
    conn = db.connect()
    try:
        if not db.one(conn, "SELECT name FROM sqlite_master WHERE name='finding'"):
            print("WARNING: database is empty. Run:  python -m pipeline.run")
    finally:
        conn.close()
    yield


app = FastAPI(title="The Ward Ledger API", version="1.0", lifespan=lifespan,
              description="Follow the rupee: Mumbai monsoon roads. " + config.SYNTHETIC_NOTICE)

origins = [o.strip() for o in os.environ.get("WL_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"], expose_headers=["X-Chain-OK", "X-Chain-Checked", "X-Rows"])

app.include_router(public.router)
app.include_router(officer.router)
app.include_router(audit.router)
