"""Deadline watcher: tells contractors (e-mail + in-app) when a task is still open after its due date.

    python -m live.overdue            # one pass (use from cron / Task Scheduler)

The API also runs this in a background thread every WL_OVERDUE_CHECK_MIN minutes (default 15; 0 turns it off).
Each task is reported once (`task.overdue_notified_at`), so running it often is harmless.
"""
from __future__ import annotations

import threading

import config
import db
from live import mailer, tasks


def run_once(conn=None) -> dict:
    own = conn is None
    conn = conn or db.connect()
    try:
        notified = tasks.check_overdue(conn)
        return {"notified": notified, "mail": mailer.flush(conn)}     # flush also retries earlier failures
    finally:
        if own:
            conn.close()


def start_background(stop: threading.Event) -> threading.Thread | None:
    minutes = config.OVERDUE_CHECK_MINUTES
    if minutes <= 0:
        return None

    def loop():
        while not stop.is_set():
            try:
                r = run_once()
                if r["notified"]:
                    print(f"overdue check: reminded contractors about {', '.join(r['notified'])}")
            except Exception as e:                       # never let the watcher die
                print(f"overdue check failed: {type(e).__name__}: {e}")
            stop.wait(minutes * 60)

    th = threading.Thread(target=loop, name="overdue-watcher", daemon=True)
    th.start()
    return th


if __name__ == "__main__":
    print(run_once())
