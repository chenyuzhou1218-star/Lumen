"""Class credits."""

from server import db


class NoCredits(Exception):
    pass


def charge(user, reason):
    with db.lock:
        if db.credits.get(user, 0) < 1:
            raise NoCredits(user)
        db.credits[user] -= 1
        db.history.append((user, 1, reason))


def refund(user, reason):
    with db.lock:
        db.credits[user] = db.credits.get(user, 0) + 1
        db.history.append((user, +1, reason))
