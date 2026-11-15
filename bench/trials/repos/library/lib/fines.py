"""Late fines."""

from lib import db, policy


def charge(member_id, days_late):
    if days_late <= 0:
        return 0
    cents = days_late * policy.FINE_CENTS_PER_DAY
    with db.lock:
        db.fines[member_id] = db.fines.get(member_id, 0) + cents
    return cents


def pay(member_id, cents):
    with db.lock:
        owed = db.fines.get(member_id, 0)
        if cents > owed:
            raise ValueError("paying more than is owed")
        db.fines[member_id] = owed - cents
        db.ledger.append((member_id, cents, "fine paid"))


def waive(member_id, cents):
    """Staff cancel part of a fine (money that will never come in)."""
    with db.lock:
        db.fines[member_id] = max(0, db.fines.get(member_id, 0) - cents)
        db.ledger.append((member_id, cents, "fine waived"))
