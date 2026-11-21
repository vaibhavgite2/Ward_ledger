"""Uploads: complaint photos/videos, repair evidence, bills.

* File type is decided by the file's bytes (magic numbers), never by its name or the browser's claim.
* Originals are kept internally with their metadata (SPEC: "EXIF retained internally").
* Photos also get a re-encoded public copy: orientation applied, then EXIF/GPS and other metadata dropped.
  Only that copy is ever public. Videos and bills are never public.
* Private files are served through short-lived HMAC-signed URLs, so <img>/<video> tags work without
  exposing the session token.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
import secrets
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import config
import db
from live.common import LiveError, now_iso

MB = 1024 * 1024
LIMIT = {"photo": 10 * MB, "video": 50 * MB, "bill": 10 * MB}
URL_TTL_S = 3600
PUBLIC_MAX_PX = 1600


def sniff(head: bytes):
    """-> (family, mime, ext) or None."""
    if head[:3] == b"\xff\xd8\xff":
        return "image", "image/jpeg", "jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image", "image/png", "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image", "image/webp", "webp"
    if head[:5] == b"%PDF-":
        return "pdf", "application/pdf", "pdf"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"avif"):
            return None                      # still-image containers we cannot re-encode
        if brand == b"qt  ":
            return "video", "video/quicktime", "mov"
        return "video", "video/mp4", "mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video", "video/webm", "webm"
    return None


@dataclass
class Staged:
    media_id: str
    kind: str
    mime: str
    size: int
    sha256: str
    stored_name: str
    public_name: str | None
    paths: list = field(default_factory=list)

    def cleanup(self):
        for p in self.paths:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass


def _upload_dir() -> Path:
    d = Path(config.UPLOAD_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _public_copy(data: bytes) -> bytes:
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 40_000_000
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            im = ImageOps.exif_transpose(im)          # keep the photo upright before dropping EXIF
            if im.mode in ("RGBA", "LA", "P"):
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel("A"))
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((PUBLIC_MAX_PX, PUBLIC_MAX_PX))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=82, optimize=True)   # no exif= / icc_profile= -> none written
            return out.getvalue()


def stage(fileobj, purpose: str) -> Staged:
    """Validate and write one upload to disk. purpose: 'evidence' (photo/video) or 'bill' (pdf/photo)."""
    head = fileobj.read(16)
    s = sniff(head)
    if not s:
        raise LiveError(415, "bad_file_type", "Only JPEG, PNG or WEBP photos, MP4/MOV/WEBM videos and PDF bills are accepted.")
    family, mime, ext = s
    if purpose == "evidence":
        kind = {"image": "photo", "video": "video"}.get(family)
    else:
        kind = "bill" if family in ("pdf", "image") else None
    if kind is None:
        raise LiveError(415, "bad_file_type", "This file type is not accepted here.")
    limit = LIMIT[kind]
    rest = fileobj.read(limit - len(head) + 1)
    data = head + rest
    if len(data) > limit:
        raise LiveError(413, "file_too_large", f"Each {kind} must be under {limit // MB} MB.")
    if len(data) < 32:
        raise LiveError(422, "empty_file", "The file is empty.")
    media_id = "m_" + secrets.token_hex(10)
    d = _upload_dir()
    stored = f"{media_id}.{ext}"
    staged = Staged(media_id, kind, mime, len(data), hashlib.sha256(data).hexdigest(), stored, None)
    if kind == "photo" or (kind == "bill" and family == "image"):
        try:
            pub = _public_copy(data)
        except Exception:
            raise LiveError(422, "bad_image", "That image could not be read. Please try another photo.")
        if kind == "photo":
            staged.public_name = f"{media_id}.pub.jpg"
            (d / staged.public_name).write_bytes(pub)
            staged.paths.append(d / staged.public_name)
    (d / stored).write_bytes(data)
    staged.paths.append(d / stored)
    return staged


def stage_many(files, purpose: str) -> list[Staged]:
    out: list[Staged] = []
    try:
        for f in files:
            out.append(stage(f, purpose))
    except Exception:
        for s in out:
            s.cleanup()
        raise
    return out


def insert(conn, s: Staged, owner_type: str, owner_id: str, uploaded_by: str) -> None:
    conn.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (s.media_id, owner_type, owner_id, s.kind, s.mime, s.size, s.sha256, s.stored_name, s.public_name,
                  uploaded_by, now_iso()))


# ---- signed URLs ---------------------------------------------------------------------------------
_SECRET_CACHE: dict = {}


def _secret() -> bytes:
    env = os.environ.get("WL_SECRET")
    if env:
        return env.encode("utf-8")
    p = Path(config.INSTANCE_DIR) / "secret.key"
    if str(p) not in _SECRET_CACHE:
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(secrets.token_hex(32), encoding="utf-8")
        _SECRET_CACHE[str(p)] = p.read_text(encoding="utf-8").strip().encode("utf-8")
    return _SECRET_CACHE[str(p)]


def _sig(media_id: str, variant: str, exp: int) -> str:
    return hmac.new(_secret(), f"{media_id}|{variant}|{exp}".encode(), hashlib.sha256).hexdigest()


def signed_url(media_id: str, variant: str = "original", ttl: int = URL_TTL_S) -> str:
    exp = int(time.time()) + ttl
    return f"/media/{media_id}/{variant}?exp={exp}&sig={_sig(media_id, variant, exp)}"


def check_sig(media_id: str, variant: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    return hmac.compare_digest(_sig(media_id, variant, exp), sig or "")


# ---- visibility ----------------------------------------------------------------------------------
def public_ok(conn, m: dict) -> bool:
    """Only photos, only the stripped copy, and only once the owner record may be public."""
    if m["kind"] != "photo" or not m["public_name"]:
        return False
    if m["owner_type"] == "ticket":
        t = db.one(conn, "SELECT status FROM ticket WHERE ticket_id=?", (m["owner_id"],))
        return bool(t) and t["status"] != "rejected"
    if m["owner_type"] == "report":
        r = db.one(conn, "SELECT t.status FROM repair_report r JOIN task t USING(task_id) WHERE r.report_id=?", (m["owner_id"],))
        return bool(r) and r["status"] == "completed"
    return False


def can_view_original(conn, viewer, m: dict) -> bool:
    if viewer is None:
        return False
    if viewer.role == "officer":
        return True
    if m["owner_type"] == "ticket":
        t = db.one(conn, "SELECT citizen_id, task_id FROM ticket WHERE ticket_id=?", (m["owner_id"],))
        if not t:
            return False
        if viewer.role == "citizen" and t["citizen_id"] == viewer.user_id and m["kind"] != "bill":
            return True
        if viewer.role == "contractor" and t["task_id"]:
            task = db.one(conn, "SELECT contractor_id FROM task WHERE task_id=?", (t["task_id"],))
            return bool(task) and task["contractor_id"] == viewer.contractor_id
        return False
    if m["owner_type"] == "report" and viewer.role == "contractor":
        r = db.one(conn, "SELECT t.contractor_id FROM repair_report r JOIN task t USING(task_id) WHERE r.report_id=?", (m["owner_id"],))
        return bool(r) and r["contractor_id"] == viewer.contractor_id
    return False


def serialize(conn, m: dict, viewer) -> dict | None:
    """What this viewer may see of one file. None if nothing."""
    pub = public_ok(conn, m)
    orig = can_view_original(conn, viewer, m)
    if not pub and not orig:
        return None
    out = {"media_id": m["media_id"], "kind": m["kind"], "mime": m["mime"], "size_bytes": m["size_bytes"],
           "public_url": f"/media/{m['media_id']}/public" if pub else None}
    if orig:
        out["url"] = signed_url(m["media_id"], "original")
        out["sha256"] = m["sha256"]
    else:
        out["url"] = out["public_url"]
    return out


def for_owner(conn, owner_type: str, owner_id: str, viewer) -> list[dict]:
    rows = db.rows(conn, "SELECT * FROM media WHERE owner_type=? AND owner_id=? ORDER BY created_at, media_id", (owner_type, owner_id))
    return [x for x in (serialize(conn, r, viewer) for r in rows) if x]


def file_path(name: str) -> Path:
    return Path(config.UPLOAD_DIR) / name
