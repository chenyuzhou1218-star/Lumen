"""Reminder e-mails one hour before class."""

from datetime import datetime, timedelta

from server import classes, db

REMIND_BEFORE = timedelta(minutes=1)


def due(now=None):
    now = now or datetime.now()
    out = []
    with db.lock:
        active = [b for b in db.bookings.values() if b["status"] == "booked"]
    for b in active:
        start = classes.starts_at(b["class_id"]).replace(tzinfo=None)
        if start - REMIND_BEFORE <= now < start:
            out.append((b["user"], b["class_id"]))
    return out
