"""Class lookups."""

from datetime import datetime

from server import db, stats


def get(class_id):
    with db.lock:
        return dict(db.classes[class_id])


def remaining(class_id):
    cls = get(class_id)
    return cls["capacity"] - stats.booked_count(class_id)


def starts_at(class_id):
    return datetime.fromisoformat(get(class_id)["starts_at"])
