"""Load the source CSVs into SQLite and register each file by sha256 (SPEC §4.2)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config
import db


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_files(sample: bool = False) -> dict[str, Path]:
    """table name -> file path."""
    files = {name: config.DATA_DIR / f"{name}.csv" for name in config.SOURCE_FILES}
    if sample:
        files["complaints"] = config.DATA_DIR / "complaints_sample_200.csv"
    for g in config.GEOJSON_FILES:
        files[g.replace(".geojson", "_geojson")] = config.DATA_DIR / g
    return files


def current_hashes(sample: bool = False) -> dict[str, str]:
    out = {}
    for name, p in source_files(sample).items():
        if not p.exists():
            raise FileNotFoundError(f"{p} missing. Run scripts/fetch_data.sh first.")
        out[p.name] = sha256_file(p)
    return out


def stored_hashes(conn) -> dict[str, str]:
    try:
        return {r["filename"]: r["doc_id"] for r in db.rows(conn, "SELECT doc_id, filename FROM source_doc")}
    except Exception:
        return {}


def sources_changed(conn, sample: bool = False) -> bool:
    return stored_hashes(conn) != current_hashes(sample)


def load_sources(conn, sample: bool = False) -> dict[str, str]:
    """Load every CSV as a table (with `_row` = line number in the file, header = 1)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("DELETE FROM source_doc")
    hashes = {}
    for name, path in source_files(sample).items():
        digest = sha256_file(path)
        hashes[path.name] = digest
        if path.suffix == ".csv":
            df = pd.read_csv(path, encoding="utf-8")
            df.insert(0, "_row", range(2, len(df) + 2))
            df.to_sql(name, conn, if_exists="replace", index=False)
            n = len(df)
        else:
            n = 0
        conn.execute("INSERT INTO source_doc VALUES (?,?,?,?)", (digest, path.name, n, now))
    conn.commit()
    return hashes


def doc_hash(conn, filename: str) -> str | None:
    r = db.one(conn, "SELECT doc_id FROM source_doc WHERE filename=?", (filename,))
    return r["doc_id"] if r else None
