"""Waiting lists for full classes."""

from server import credits, db


def join(class_id, user):
    with db.lock:
        q = db.waitlists.setdefault(class_id, [])
        if user not in q:
            q.append(user)
        return q.index(user)


def promote(class_id, payer=None):
    """Give the freed seat to the first person waiting. Returns the new booking or None."""
    from server import bookings

    with db.lock:
        q = db.waitlists.get(class_id) or []
        if not q:
            return None
        user = q.pop(0)
    credits.charge(payer or user, f"waitlist seat {class_id}")
    return bookings.create(user, class_id)
