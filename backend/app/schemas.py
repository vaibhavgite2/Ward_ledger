"""Pydantic models. `PublicFinding` is the ONLY shape public endpoints use for findings: it has no
officer framing field, so officer-only data cannot leak through it (SPEC §7)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Subject(BaseModel):
    type: str
    id: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    table: str
    id: str
    row: int | None = None
    file: str
    sha256: str | None = None
    note: str | None = None


class PublicFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")      # drops flag_label etc. if ever passed in
    finding_id: str
    rule: str
    title: str
    polarity: str
    severity: str
    subject: Subject
    ward_code: str | None = None
    contractor_id: str | None = None
    text: str
    metrics: dict
    context: dict
    evidence: list[Evidence]
    reply: dict | None = None
    actions: list[str]
    rule_version: str


class AskIn(BaseModel):
    question: str
    lang: str = "mr"


class RtiIn(BaseModel):
    work_order_id: str | None = None
    complaint_id: str | None = None
    road_id: str | None = None
    lang: str = "mr"


class ReplyIn(BaseModel):
    finding_id: str
    reply_text: str


class DecisionIn(BaseModel):
    action: str          # approve | reject
    note: str | None = None
