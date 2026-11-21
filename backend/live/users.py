"""Accounts and sessions for the three login panels (DFD 1.1 Citizen, 1.2 Officer, 1.3 Contractor).

* One `app_user` table, but each panel authenticates only its own role: officer credentials do not
  work on the contractor panel and vice versa.
* Passwords: scrypt with a per-user salt. Sessions: random bearer tokens, stored only as SHA-256.
* Failed logins are throttled per (role, login); error messages never say whether the account exists.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import config
import db
from live import mailer
from live.common import LiveError, Viewer, now_iso

_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)
MAX_FAILED = 5
FAILED_WINDOW_MIN = 15
PW_MIN, PW_MAX = 8, 128
RE_LOGIN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


# ---- passwords ---------------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return "scrypt${n}${r}${p}${s}${h}".format(n=_SCRYPT["n"], r=_SCRYPT["r"], p=_SCRYPT["p"],
                                               s=base64.b64encode(salt).decode(), h=base64.b64encode(h).decode())


def check_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, h = stored.split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(base64.b64decode(h)))
        return hmac.compare_digest(got, base64.b64decode(h))
    except Exception:
        return False


_DUMMY_HASH = hash_password(secrets.token_urlsafe(12))   # equalises timing for unknown accounts


def _validate_password(pw: str):
    if not isinstance(pw, str) or not (PW_MIN <= len(pw) <= PW_MAX):
        raise LiveError(422, "weak_password", f"Password must be {PW_MIN} to {PW_MAX} characters.")


# ---- login identifiers ---------------------------------------------------------------------------
def normalise_mobile(raw: str) -> str:
    """Indian mobile numbers: accepts +91 / 0 prefixes, spaces and dashes; returns 10 digits."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise LiveError(422, "bad_mobile", "Enter a valid 10-digit Indian mobile number.")
    return digits


def normalise_login(role: str, raw: str) -> str:
    if role == "citizen":
        return normalise_mobile(raw)
    s = (raw or "").strip().lower()
    if not RE_LOGIN.match(s):
        raise LiveError(422, "bad_login", "Enter a valid login ID.")
    return s


def mask_mobile(m: str) -> str:
    return m[:2] + "XXXXXX" + m[-2:] if m and len(m) == 10 else "XXXXXXXXXX"


# ---- accounts -------------------------------------------------------------------------------------
def clean_email(raw: str | None, required: bool = False) -> str | None:
    e = (raw or "").strip().lower()
    if not e:
        if required:
            raise LiveError(422, "bad_email", "Enter a valid e-mail address.")
        return None
    if not mailer.valid_address(e):
        raise LiveError(422, "bad_email", "Enter a valid e-mail address.")
    return e


def create_user(conn, role: str, login: str, password: str, *, display_name=None, contractor_id=None,
                ward_code=None, designation=None, can_act=True, email=None, lang="en") -> str:
    if role not in ("citizen", "officer", "contractor"):
        raise LiveError(422, "bad_role", "Unknown role.")
    login = normalise_login(role, login)
    _validate_password(password)
    if role == "contractor":
        if not contractor_id or not db.one(conn, "SELECT 1 FROM contractors WHERE contractor_id=?", (contractor_id,)):
            raise LiveError(422, "bad_contractor", "Contractor accounts must be linked to an empanelled contractor.")
    if db.one(conn, "SELECT 1 FROM app_user WHERE role=? AND login=?", (role, login)):
        raise LiveError(409, "exists", "An account with this login already exists.")
    email = clean_email(email)
    uid = "u_" + secrets.token_hex(8)
    conn.execute(
        "INSERT INTO app_user(user_id, role, login, display_name, pw_hash, contractor_id, ward_code, designation, created_at, can_act, "
        "email, lang) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, role, login, (display_name or "").strip()[:60] or None, hash_password(password), contractor_id, ward_code,
         designation, now_iso(), int(bool(can_act)), email, lang if lang in ("en", "mr", "hi") else "en"))
    return uid


def register_citizen(conn, mobile: str, password: str, display_name: str | None, consent: bool,
                     email: str | None = None, lang: str = "en") -> str:
    if not consent:
        raise LiveError(422, "consent_required", "Please agree to how we use your mobile number.")
    with db.write_tx(conn):
        uid = create_user(conn, "citizen", mobile, password, display_name=display_name, email=email, lang=lang)
        db.log(conn, "citizen", "citizen_registered", "app_user", uid)   # no mobile number in the log
    return uid


def _throttled(conn, role, login) -> bool:
    since = (datetime.now(timezone.utc) - timedelta(minutes=FAILED_WINDOW_MIN)).isoformat(timespec="seconds")
    n = db.one(conn, "SELECT COUNT(*) n FROM login_attempt WHERE role=? AND login=? AND ok=0 AND at>=?", (role, login, since))["n"]
    return n >= MAX_FAILED


def login(conn, role: str, raw_login: str, password: str) -> tuple[str, Viewer]:
    """Authenticate on ONE panel. Returns (bearer token, viewer)."""
    try:
        lg = normalise_login(role, raw_login)
    except LiveError:
        raise LiveError(401, "bad_credentials", "Login ID or password is incorrect.")
    throttled, ok, token, u = False, False, None, None
    with db.write_tx(conn):
        if _throttled(conn, role, lg):
            throttled = True
        else:
            u = db.one(conn, "SELECT * FROM app_user WHERE role=? AND login=? AND disabled=0", (role, lg))
            ok = check_password(password or "", u["pw_hash"] if u else _DUMMY_HASH) and u is not None
            conn.execute("INSERT INTO login_attempt VALUES (?,?,?,?)", (role, lg, now_iso(), int(ok)))   # kept on failure too
            if ok:
                token = secrets.token_urlsafe(32)
                exp = (datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS[role])).isoformat(timespec="seconds")
                conn.execute("INSERT INTO auth_session VALUES (?,?,?,?,?,0)", (_token_hash(token), u["user_id"], role, now_iso(), exp))
                db.log(conn, f"citizen:{u['user_id']}" if role == "citizen" else f"{role}:{lg}", "login", "app_user", u["user_id"])
    if throttled:
        raise LiveError(429, "too_many_attempts", f"Too many failed attempts. Try again in {FAILED_WINDOW_MIN} minutes.")
    if not ok:
        raise LiveError(401, "bad_credentials", "Login ID or password is incorrect.")
    return token, _viewer(u)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _viewer(u) -> Viewer:
    return Viewer(user_id=u["user_id"], role=u["role"], login=u["login"], display_name=u["display_name"],
                  contractor_id=u["contractor_id"], ward_code=u["ward_code"], designation=u["designation"],
                  can_act=bool(u["can_act"]))


def viewer_for_token(conn, token: str | None) -> Viewer | None:
    if not token or len(token) > 200:
        return None
    s = db.one(conn, "SELECT * FROM auth_session WHERE token_hash=?", (_token_hash(token),))
    if not s or s["revoked"] or s["expires_at"] < now_iso():
        return None
    u = db.one(conn, "SELECT * FROM app_user WHERE user_id=? AND disabled=0", (s["user_id"],))
    if not u or u["role"] != s["role"]:
        return None
    return _viewer(u)


def logout(conn, token: str) -> None:
    with db.write_tx(conn):
        conn.execute("UPDATE auth_session SET revoked=1 WHERE token_hash=?", (_token_hash(token),))


def set_contact(conn, v: Viewer, email: str | None, lang: str | None) -> dict:
    """The signed-in person sets (or clears) their own e-mail address and the language of the e-mails they receive."""
    e = clean_email(email)
    with db.write_tx(conn):
        if lang in ("en", "mr", "hi"):
            conn.execute("UPDATE app_user SET email=?, lang=? WHERE user_id=?", (e, lang, v.user_id))
        else:
            conn.execute("UPDATE app_user SET email=? WHERE user_id=?", (e, v.user_id))
        db.log(conn, v.actor_ref, "contact_updated", "app_user", v.user_id)        # the address itself is never logged
    return {"email": e}


def public_profile(v: Viewer, conn) -> dict:
    me = db.one(conn, "SELECT email, lang FROM app_user WHERE user_id=?", (v.user_id,)) or {}
    out = {"user_id": v.user_id, "role": v.role, "display_name": v.display_name, "ward_code": v.ward_code,
           "designation": v.designation, "contractor_id": v.contractor_id, "can_act": v.can_act,
           "email": me.get("email"), "mail_lang": me.get("lang") or "en"}
    if v.role == "citizen":
        out["login"] = mask_mobile(v.login)
    else:
        out["login"] = v.login
    if v.role == "contractor" and v.contractor_id:
        c = db.one(conn, "SELECT contractor_name FROM contractors WHERE contractor_id=?", (v.contractor_id,))
        out["contractor_name"] = c["contractor_name"] if c else None
    return out
