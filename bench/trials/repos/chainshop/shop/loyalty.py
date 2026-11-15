"""Loyalty points: earned on what the customer paid, spent as a discount."""

from shop import db, events, policy


def balance(user):
    return db.points.get(user, 0)


def redeem(user, points):
    """Spend points; returns the discount they are worth."""
    if points > balance(user):
        raise ValueError("not enough points")
    db.points[user] -= points
    return points


def on_paid(order):
    db.points[order["user"]] = balance(order["user"]) + order["subtotal"] // 100 * policy.POINTS_PER_YUAN


def on_refunded(order):
    earned = order["subtotal"] // 100 * policy.POINTS_PER_YUAN
    db.points[order["user"]] = max(0, balance(order["user"]) - earned)


events.subscribe("order_paid", on_paid)
events.subscribe("order_refunded", on_refunded)
