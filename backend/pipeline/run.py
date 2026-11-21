"""Pipeline CLI: python -m pipeline.run [--sample] [--force]   (run from backend/)

load -> parse (Claude/keyword) -> geocode -> claims & promotion -> link/dedup -> findings -> budget
Idempotent: unchanged source hashes and an existing database make this a no-op (unless --force).
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import config
import db
from agents import complaint_parser as cp
from agents import geocoder, linker
from pipeline import geo as geomod
from pipeline import load
from rules import findings as F
from rules import promote as P

VAGUE = {"Road related", "Other", None}


def _step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(sample: bool = False, force: bool = False, conn=None, quiet: bool = False) -> dict:
    own = conn is None
    conn = conn or db.connect()
    db.init_schema(conn)
    say = (lambda m: None) if quiet else _step

    derived_exists = db.one(conn, "SELECT COUNT(*) n FROM finding")["n"] > 0 if _has(conn, "finding") else False
    if not force and derived_exists and not load.sources_changed(conn, sample):
        say("Sources unchanged and database populated: nothing to do (use --force to rebuild).")
        return {"skipped": True}

    say("Loading source files")
    db.reset_derived(conn)
    load.load_sources(conn, sample)
    geo = geomod.load_geo(force=True)
    stats: dict = {}

    complaints = db.rows(conn, "SELECT * FROM complaints ORDER BY complaint_id")
    wos = db.rows(conn, "SELECT * FROM work_orders ORDER BY work_order_id")
    wo_by_complaint = {}
    for w in wos:
        for cid in F.wo_complaint_ids(w):
            wo_by_complaint[cid] = w
    complaints_doc = load.doc_hash(conn, "complaints_sample_200.csv" if sample else "complaints.csv")
    wo_doc = load.doc_hash(conn, "work_orders.csv")

    say(f"Parsing {len(complaints)} complaints ({'Claude + keyword fallback' if config.CLAUDE_ENABLED else 'keyword classifier; no API key'})")
    parsed = cp.parse_all(complaints)

    say("Geocoding")
    gaz = geocoder.Gazetteer(db.rows(conn, "SELECT * FROM localities"))
    centroids = {w["ward_code"]: (w["centroid_lat"], w["centroid_lon"]) for w in db.rows(conn, "SELECT * FROM wards")}
    geocoded = {c["complaint_id"]: geocoder.geocode(c, gaz, geo, centroids) for c in complaints}

    say("Writing claims and promoting facts")
    ledger = P.Ledger(conn)
    stats["source_facts"] = P.promote_source_facts(ledger, conn)
    # complaint -> work order links, straight from the work_orders file
    present = {c["complaint_id"] for c in complaints}
    for cid, w in wo_by_complaint.items():
        if cid in present:
            ledger.fact("complaint", cid, "linked_work_order", w["work_order_id"], P.RULE_SOURCE_CSV,
                        source_doc=wo_doc, source_row=w["_row"])
    ledger.flush()

    cat_status, ward_status, cat_promoter = {}, {}, Counter()
    for c in complaints:
        cid = c["complaint_id"]
        pr, g = parsed[cid], geocoded[cid]
        claim_id = ledger.claim("complaint", cid, "category",
                                {"category": pr["category"], "reason": pr.get("reason")},
                                complaints_doc, c["_row"], pr["extractor"], pr.get("prompt_hash"), pr["confidence"])
        wo = wo_by_complaint.get(cid)
        status, by = P.promote_category(ledger, claim_id, c, pr, wo["work_type"] if wo else None,
                                        complaints_doc, VAGUE, cp.CATEGORIES)
        cat_status[cid] = status
        cat_promoter[by or "review_queue"] += 1

        if g["lat"] is not None:
            ledger.claim("complaint", cid, "geocode",
                         {"lat": g["lat"], "lon": g["lon"], "uncertainty_m": g["uncertainty_m"], "method": g["method"]},
                         complaints_doc, c["_row"], "geocoder@v1", None, None)
        # ward: only a *claim* when the source left it blank
        ward_status[cid] = g["ward_source"]
        if g["ward_source"] in ("polygon", "gazetteer"):
            wclaim = ledger.claim("complaint", cid, "ward_code", g["ward_code"], complaints_doc, c["_row"],
                                  f"geocoder@v1:{g['ward_source']}", None, None)
            other = g.get("gazetteer_ward") if g["ward_source"] == "polygon" else g.get("polygon_ward")
            if other == g["ward_code"]:
                ledger.fact("complaint", cid, "ward_code", g["ward_code"], P.RULE_TWO_SOURCE, from_claim=wclaim,
                            source_doc=complaints_doc, source_row=c["_row"])
                ward_status[cid] = g["ward_source"] + "-verified"
            else:
                ledger.queue(wclaim, cid, f"ward '{g['ward_code']}' from {g['ward_source']} only; no second source agrees")
                ward_status[cid] = g["ward_source"] + "-unverified"
        if g.get("review"):
            ledger.queue(ledger.claim("complaint", cid, "locality_candidates", g["review"], complaints_doc, c["_row"], "geocoder@v1"),
                         cid, f"locality '{c['locality_text']}' fuzzy-matches {g['review'][:2]} below auto-accept threshold")
    ledger.flush()
    stats["category_promotion"] = dict(cat_promoter)

    say("Snapping to roads, clustering duplicates, linking to work orders")
    merged = []
    for c in complaints:
        cid = c["complaint_id"]
        g = geocoded[cid]
        pr = parsed[cid]
        wo = wo_by_complaint.get(cid)
        road, rdist = None, None
        if wo:
            road = wo["road_id"]
        elif g["method"] == "gps":
            road, rdist = geo.nearest_road(g["lat"], g["lon"], max(config.RULES["geocode"]["road_snap_min_m"], g["uncertainty_m"]),
                                           ward=g["ward_code"])
        merged.append({
            "complaint_id": cid, "received_at": c["received_at"], "status": c["status"], "upvotes": c["upvotes"],
            "category": pr["category"], "ward_code": g["ward_code"], "lat": g["lat"], "lon": g["lon"],
            "uncertainty_m": g["uncertainty_m"], "locality_resolved": g.get("locality_resolved"),
            "road_id": road, "road_distance_m": rdist, "geocode_method": g["method"],
            "ward_source": ward_status[cid], "_c": c,
        })
    per, issues = linker.link(merged, wos)
    rows = []
    for m in merged:
        c, pr = m["_c"], parsed[m["complaint_id"]]
        l = per[m["complaint_id"]]
        rows.append((
            m["complaint_id"], pr["category"], pr["confidence"],
            int(pr["category"] != cp.normalise_reported(c["category_reported"])), cat_status[m["complaint_id"]],
            c["language"], c["locality_text"], m["ward_code"], m["ward_source"], m["lat"], m["lon"], m["uncertainty_m"],
            m["geocode_method"], m["road_id"], m["road_distance_m"], l["issue_id"], l["link_status"],
            l["work_order_id"], pr["extractor"]))
    conn.executemany("INSERT INTO parsed_complaint VALUES (" + ",".join("?" * 19) + ")", rows)
    icols = ["issue_id", "category", "road_id", "ward_code", "lat", "lon", "first_reported", "complaint_count",
             "upvotes", "severity", "work_order_id", "status"]
    conn.executemany(f"INSERT INTO issue VALUES ({','.join('?' * len(icols))})", [[i[c] for c in icols] for i in issues])
    conn.commit()
    stats["issues"] = len(issues)
    stats["issue_status"] = dict(Counter(i["status"] for i in issues))

    say("Evaluating finding rules")
    fs = F.compute(conn)
    F.store(conn, fs)
    stats["findings"] = dict(Counter(f["rule"] for f in fs))

    try:
        from agents import budget
        say("Running next-rupee planner for all wards")
        stats["budget_rows"] = budget.run_all(conn)
    except ImportError:
        pass

    db.log(conn, "system", "pipeline_run", "database", str(config.DB_PATH.name),
           {"sample": sample, "claude": config.CLAUDE_ENABLED, **{k: v for k, v in stats.items() if k != 'budget_rows'}})
    conn.commit()
    say("Done")
    if own:
        conn.close()
    return stats


def _has(conn, table) -> bool:
    return db.one(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)) is not None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ward Ledger data pipeline")
    ap.add_argument("--sample", action="store_true", help="use complaints_sample_200.csv")
    ap.add_argument("--force", action="store_true", help="rebuild even if sources are unchanged")
    a = ap.parse_args(argv)
    stats = run(sample=a.sample, force=a.force)
    if not stats.get("skipped"):
        import json
        print(json.dumps(stats, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
