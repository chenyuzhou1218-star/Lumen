"""Members and their limits."""

from lib import db, policy


def get(member_id):
    with db.lock:
        return dict(db.members[member_id])


def limit(member_id):
    return policy.LIMITS[get(member_id)["tier"]]


def active_loans(member_id):
    with db.lock:
        return [l for l in db.loans.values() if l["member"] == member_id]
