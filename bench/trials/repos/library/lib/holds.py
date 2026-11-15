"""Holds (reservations) for books with no free copy."""

from lib import db, notifications


def place(member_id, book_id):
    with db.lock:
        q = db.holds.setdefault(book_id, [])
        if member_id not in q:
            q.append(member_id)
        return q.index(member_id) + 1


def first(book_id):
    with db.lock:
        q = db.holds.get(book_id) or []
        return q[0] if q else None


def notify_next(book_id):
    nxt = first(book_id)
    if nxt:
        notifications.book_ready(nxt, book_id)
    return nxt
