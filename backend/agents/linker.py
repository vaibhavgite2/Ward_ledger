"""Dedup + Complaint -> Work Order linker (SPEC §6.3). Deterministic.

* Complaints sharing a work order are one issue.
* Candidate duplicates (same parsed category, same place, within 48h) are clustered into the same
  issue. A cluster never merges two different work orders.
* "never_fixed" is decided at issue level: no work order anywhere in the cluster, still open, and older
  than the SLA for its severity.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

import config
from pipeline.geo import dist_m

D = config.RULES["dedup"]
B = config.RULES["budget"]
FMT = "%Y-%m-%d %H:%M"
SLA_BY_SEVERITY = {5: 24, 4: 48, 3: 72, 2: 120, 1: 168}
SEVERITY_BY_SLA = {v: k for k, v in SLA_BY_SEVERITY.items()}


def _dt(s):
    return datetime.strptime(s, FMT)


class _UF:
    def __init__(self, n, wo_of):
        self.p = list(range(n))
        self.wos = [({w} if w else set()) for w in wo_of]

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if len(self.wos[ra] | self.wos[rb]) > 1:     # never merge two different work orders
            return
        self.p[rb] = ra
        self.wos[ra] |= self.wos[rb]


def _same_place(a: dict, b: dict) -> bool:
    if a.get("road_id") and a.get("road_id") == b.get("road_id"):
        return True
    ga = a.get("lat") is not None and (a.get("uncertainty_m") or 9999) <= 500
    gb = b.get("lat") is not None and (b.get("uncertainty_m") or 9999) <= 500
    if ga and gb:
        return dist_m(a["lat"], a["lon"], b["lat"], b["lon"]) <= D["radius_m"]
    la, lb = a.get("locality_resolved"), b.get("locality_resolved")
    return bool(la and la == lb)


def link(complaints: list[dict], wos: list[dict], as_of: str = config.AS_OF) -> tuple[dict, list[dict]]:
    """complaints: dicts with complaint_id, received_at, status, upvotes, category (parsed), ward_code,
    lat, lon, uncertainty_m, locality_resolved, road_id. wos: work_orders rows.
    -> (per_complaint {cid: {issue_id, link_status, work_order_id}}, issues [..])"""
    wo_of: dict[str, dict] = {}
    for w in wos:
        for cid in (w.get("linked_complaint_ids") or "").split("|"):
            if cid:
                wo_of[cid] = w
    cs = sorted(complaints, key=lambda c: (c["received_at"], c["complaint_id"]))
    idx = {c["complaint_id"]: i for i, c in enumerate(cs)}
    uf = _UF(len(cs), [wo_of[c["complaint_id"]]["work_order_id"] if c["complaint_id"] in wo_of else None for c in cs])

    # 1) shared work order
    by_wo = defaultdict(list)
    for c in cs:
        w = wo_of.get(c["complaint_id"])
        if w:
            by_wo[w["work_order_id"]].append(idx[c["complaint_id"]])
    for members in by_wo.values():
        for m in members[1:]:
            uf.union(members[0], m)

    # 2) candidate duplicates
    buckets = defaultdict(list)
    for i, c in enumerate(cs):
        buckets[(c["category"], c.get("ward_code"))].append(i)
    window = D["window_hours"] * 3600
    for members in buckets.values():
        for a_pos, ia in enumerate(members):
            ta = _dt(cs[ia]["received_at"])
            for ib in members[a_pos + 1:]:
                if (_dt(cs[ib]["received_at"]) - ta).total_seconds() > window:
                    break
                if _same_place(cs[ia], cs[ib]):
                    uf.union(ia, ib)

    clusters = defaultdict(list)
    for i in range(len(cs)):
        clusters[uf.find(i)].append(i)
    ordered = sorted(clusters.values(), key=lambda m: (cs[m[0]]["received_at"], cs[m[0]]["complaint_id"]))

    asof = datetime.fromisoformat(as_of)
    per: dict[str, dict] = {}
    issues: list[dict] = []
    for n, members in enumerate(ordered, 1):
        iid = f"ISS-{n:05d}"
        group = [cs[i] for i in members]
        wo = next((wo_of[c["complaint_id"]] for c in group if c["complaint_id"] in wo_of), None)
        cat = Counter(c["category"] for c in group).most_common(1)[0][0]
        upvotes = sum(int(c.get("upvotes") or 0) for c in group)
        sev = B["category_severity"].get(cat, 1)
        if upvotes + len(group) >= 10:
            sev = min(5, sev + 1)
        if wo:
            sev = max(sev, SEVERITY_BY_SLA.get(int(wo["sla_hours"]), 1))
        first = min(c["received_at"] for c in group)
        has_gps = [c for c in group if c.get("lat") is not None and (c.get("uncertainty_m") or 9999) <= 500]
        loc = has_gps or [c for c in group if c.get("lat") is not None]
        lat = sum(c["lat"] for c in loc) / len(loc) if loc else None
        lon = sum(c["lon"] for c in loc) / len(loc) if loc else None
        road = wo["road_id"] if wo else (Counter(c["road_id"] for c in group if c.get("road_id")).most_common(1) or [(None, 0)])[0][0]
        ward = wo["ward_code"] if wo else (Counter(c["ward_code"] for c in group if c.get("ward_code")).most_common(1) or [(None, 0)])[0][0]

        member_status = {}
        for c in group:
            cid = c["complaint_id"]
            if cid in wo_of:
                w = wo_of[cid]
                st = "fixed_failed" if w["reopened_within_30d"] == "Y" else "fixed"
            elif wo:
                st = "linked_via_issue"
            else:
                s = c["status"]
                age_h = (asof - _dt(c["received_at"])).total_seconds() / 3600
                if s in config.RULES["never_fixed"]["open_statuses"]:
                    sev_c = B["category_severity"].get(c["category"], 1)
                    st = "never_fixed" if age_h > SLA_BY_SEVERITY[sev_c] else "pending"
                elif s.startswith("Forwarded") or s.startswith("Rejected"):
                    st = "closed_other"
                elif s == "Closed - Duplicate":
                    st = "duplicate"
                else:
                    st = "resolved_no_record"
            member_status[cid] = st
            per[cid] = {"issue_id": iid, "link_status": st, "work_order_id": wo["work_order_id"] if wo else None}

        if wo:
            status = "fixed_failed" if wo["reopened_within_30d"] == "Y" else "fixed"
        elif "never_fixed" in member_status.values():
            status = "never_fixed"
        elif "pending" in member_status.values():
            status = "pending"
        else:
            status = "closed"
        issues.append({
            "issue_id": iid, "category": cat, "road_id": road, "ward_code": ward, "lat": lat, "lon": lon,
            "first_reported": first, "complaint_count": len(group), "upvotes": upvotes, "severity": sev,
            "work_order_id": wo["work_order_id"] if wo else None, "status": status,
        })
    return per, issues
