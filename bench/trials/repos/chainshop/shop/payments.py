"""Wallet payments."""

from shop import db


class Declined(Exception):
    pass


def charge(user, cents):
    if db.wallets.get(user, 0) < cents:
        raise Declined(user)
    db.wallets[user] -= cents
    db.payments.append((user, cents, "charge"))


def refund(order):
    amount = order["subtotal"]
    db.wallets[order["user"]] += amount
    db.payments.append((order["user"], amount, "refund"))
