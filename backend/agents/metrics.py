"""Shared work-order frame with context flags, plus the context-adjusted expectations used for
fair scorecards (SPEC §6.5)."""
from __future__ import annotations

import pandas as pd

import config
import db
from rules import findings as F

_CACHE: dict = {}


def _stamp(conn):
    r = db.one(conn, "SELECT COALESCE(MAX(seq),0) s FROM audit_log")
    return r["s"]


def wo_frame(conn) -> pd.DataFrame:
    key = ("wo", _stamp(conn), str(config.DB_PATH))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    ctx = F.Context(conn)
    rows = db.rows(conn, "SELECT * FROM work_orders")
    out = []
    for w in rows:
        a, c = F._dt(w["assigned_at"]), F._dt(w["completed_at"])
        rr = ctx.rate.get(w["repair_method"])
        exp = F.expected_cost(rr, w["area_sqm"]) if rr else None
        road = ctx.roads.get(w["road_id"], {})
        w.update(
            assigned=a, completed=c, expected=exp, ratio=(w["cost_inr"] / exp if exp else None),
            low_lying=ctx.low_lying(w["ward_code"]), heavy_before=ctx.heavy_week_before(w["ward_code"], a),
            heavy_after=ctx.heavy_week_after(w["ward_code"], c), dlp=(road.get("under_dlp") == "Y"),
            sla_ok=(w["sla_met"] == "Y"), failed=(w["reopened_within_30d"] == "Y"),
            month=w["completed_at"][:7], unit=(rr["unit"] if rr else None),
        )
        out.append(w)
    df = pd.DataFrame(out)
    _CACHE.clear()          # keep only the newest pipeline run's frame
    _CACHE[key] = df
    return df


def expected_rates(df: pd.DataFrame) -> dict:
    """City-wide reference rates used as 'what we would expect' for a given mix of jobs.

    * sla by sla_hours bucket (urgency mix)
    * reopen by (method, low_lying, heavy_after) cell; falls back to (method) when a cell has < 20 jobs
    """
    sla = df.groupby("sla_hours")["sla_ok"].mean().to_dict()
    m = df.groupby("repair_method")["failed"].mean().to_dict()
    cell = df.groupby(["repair_method", "low_lying", "heavy_after"])["failed"].agg(["mean", "size"])
    cells = {k: (v["mean"], int(v["size"])) for k, v in cell.iterrows()}
    return {"sla": sla, "reopen_method": m, "reopen_cell": cells, "city_sla": float(df["sla_ok"].mean()),
            "city_reopen": float(df["failed"].mean())}


def expected_reopen(row, ref) -> float:
    k = (row["repair_method"], bool(row["low_lying"]), bool(row["heavy_after"]))
    mean, n = ref["reopen_cell"].get(k, (None, 0))
    if n >= 20:
        return float(mean)
    return float(ref["reopen_method"].get(row["repair_method"], ref["city_reopen"]))


def method_reopen_table(df: pd.DataFrame) -> dict:
    """reopen rate per method overall and for low-lying wards (used by the budget planner)."""
    out = {}
    for m, g in df.groupby("repair_method"):
        low = g[g["low_lying"]]
        out[m] = {"all": float(g["failed"].mean()), "n": int(len(g)),
                  "low_lying": float(low["failed"].mean()) if len(low) >= 20 else None}
    return out
