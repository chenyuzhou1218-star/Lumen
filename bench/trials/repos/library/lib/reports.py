"""Staff reports."""

from datetime import datetime

from lib import db


def overdue():
    now = datetime.now()
    with db.lock:
        return [l["id"] for l in db.loans.values() if l["status"] == "active" and l["due"] < now]


def fine_revenue():
    with db.lock:
        return sum(cents for _, cents, _ in db.ledger)
