"""Borrowing, returning and renewing."""

import uuid
from datetime import timedelta

from lib import catalog, clock, counters, db, fines, holds, members, policy


class Refused(Exception):
    pass


def borrow(member_id, book_id):
    if len(members.active_loans(member_id)) >= members.limit(member_id):
        raise Refused("loan limit reached")
    if catalog.available(book_id) <= 0:
        holds.place(member_id, book_id)
        raise Refused("no copy free; you are on the hold list")
    waiting = holds.first(book_id)
    if waiting and waiting != member_id:
        raise Refused("this copy is held for another member")
    loan = {"id": "ln-" + uuid.uuid4().hex[:8], "member": member_id, "book": book_id,
            "due": clock.now() + timedelta(days=policy.LOAN_DAYS), "status": "active"}
    with db.lock:
        db.loans[loan["id"]] = loan
    counters.on_loan(catalog.get(book_id))
    return loan


def give_back(loan_id):
    with db.lock:
        loan = db.loans[loan_id]
        if loan["status"] != "active":
            raise Refused("not an active loan")
        loan["status"] = "returned"
    days_late = (clock.now() - loan["due"]).days
    fines.charge(loan["member"], days_late)
    counters.on_return(catalog.get(loan["book"]))
    holds.notify_next(loan["book"])
    return loan


def renew(loan_id):
    with db.lock:
        loan = db.loans[loan_id]
    if holds.first(loan["book"]):
        raise Refused("someone is waiting for this book")
    loan["due"] = clock.now() + timedelta(days=policy.LOAN_DAYS)
    return loan
