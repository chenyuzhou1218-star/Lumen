"""Books."""

from lib import counters, db


def get(book_id):
    with db.lock:
        return dict(db.books[book_id])


def available(book_id):
    return get(book_id)["copies"] - counters.out(book_id)
