"""E-mail through a transactional outbox.

A message is queued (`enqueue`) inside the same transaction as the state change that caused it, so a rolled-back
approval never sends a "your complaint is resolved" mail. `flush` then delivers whatever is pending:

* WL_SMTP_HOST set  -> sent over SMTP (STARTTLS by default); failures are kept and retried (max MAX_ATTEMPTS).
* WL_SMTP_HOST unset -> status 'logged': the message is stored but nothing leaves the machine (demo / development).

Addresses are optional personal data: they are never written to the audit log or to notifications, and a person
with no address on file simply gets the in-app notification.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import config
import db
from live import text as LT
from live.common import now_iso

MAX_ATTEMPTS = 5
_RE_ADDR = re.compile(r"^[^@\s<>,;]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def valid_address(addr: str | None) -> bool:
    return bool(addr) and len(addr) <= 120 and bool(_RE_ADDR.match(addr))


def mode() -> str:
    return "smtp" if config.SMTP_HOST else "outbox"


def user_target(conn, user_id: str) -> tuple[str | None, str]:
    """(email or None, language) for a user."""
    u = db.one(conn, "SELECT email, lang FROM app_user WHERE user_id=? AND disabled=0", (user_id,))
    if not u:
        return None, "en"
    return (u["email"] if valid_address(u["email"]) else None), (u["lang"] if u["lang"] in LT.LANGS else "en")


def enqueue(conn, user_id: str, kind: str, entity_type: str, entity_id: str, *, dedupe_key: str | None = None, **params) -> bool:
    """Queue one templated message for a user. Returns False if they have no address on file or it was already queued.
    Must run inside the caller's transaction."""
    addr, lang = user_target(conn, user_id)
    if not addr:
        return False
    subject, body = LT.render_mail(kind, params, lang)
    cur = conn.execute(
        "INSERT OR IGNORE INTO email_outbox(user_id, to_addr, subject, body, kind, entity_type, entity_id, created_at, dedupe_key) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, addr, subject, body, kind, entity_type, entity_id, now_iso(), dedupe_key))
    return cur.rowcount == 1


def _build(row: dict) -> EmailMessage:
    name, from_addr = parseaddr(config.MAIL_FROM)
    msg = EmailMessage()
    msg["From"] = formataddr((name, from_addr)) if from_addr else config.MAIL_FROM
    msg["To"] = row["to_addr"]
    msg["Subject"] = row["subject"]
    msg.set_content(row["body"])
    return msg


def _send(msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if config.SMTP_SECURITY == "ssl":
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15, context=ctx) as s:
            _login_and_send(s, msg)
        return
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
        if config.SMTP_SECURITY == "starttls":
            s.starttls(context=ctx)
        _login_and_send(s, msg)


def _login_and_send(s: smtplib.SMTP, msg: EmailMessage) -> None:
    if config.SMTP_USER:
        s.login(config.SMTP_USER, config.SMTP_PASSWORD)
    s.send_message(msg)


def flush(conn, limit: int = 50) -> dict:
    """Deliver pending (and previously failed, under the retry limit) messages. Never raises: a mail problem must
    not break the workflow that queued the message."""
    sent = logged = failed = 0
    try:
        rows = db.rows(conn, "SELECT * FROM email_outbox WHERE status IN ('pending','failed') AND attempts<? "
                             "ORDER BY email_id LIMIT ?", (MAX_ATTEMPTS, limit))
        for r in rows:
            if mode() == "outbox":
                status, err = "logged", None
            else:
                try:
                    _send(_build(r))
                    status, err = "sent", None
                except Exception as e:          # network, auth, rejected recipient ...
                    status, err = "failed", f"{type(e).__name__}: {e}"[:300]
            with db.write_tx(conn):
                conn.execute("UPDATE email_outbox SET status=?, error=?, attempts=attempts+1, sent_at=? WHERE email_id=?",
                             (status, err, now_iso() if status != "failed" else None, r["email_id"]))
            sent += status == "sent"
            logged += status == "logged"
            failed += status == "failed"
    except Exception as e:                       # database busy etc.: the next flush retries
        print(f"mailer: flush interrupted: {type(e).__name__}: {e}")
    return {"mode": mode(), "sent": sent, "logged": logged, "failed": failed}


def flush_in_background() -> None:
    """For FastAPI BackgroundTasks: own connection, runs after the response has been sent."""
    conn = db.connect()
    try:
        flush(conn)
    finally:
        conn.close()
