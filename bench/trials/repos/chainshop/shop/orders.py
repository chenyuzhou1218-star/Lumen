"""Placing, cancelling and refunding orders."""

import uuid

from shop import db, events, inventory, loyalty, payments, pricing


def _lines(items):
    return [{"sku": i["sku"].strip().upper(), "qty": int(i["qty"])} for i in items]


def create(user, items, coupon=None, use_points=0):
    lines = _lines(items)
    subtotal = pricing.subtotal(lines)
    discount = pricing.coupon_discount(subtotal, coupon)
    points_discount = loyalty.redeem(user, use_points) if use_points else 0
    total = subtotal - discount - points_discount
    inventory.reserve(lines)
    payments.charge(user, total)
    order = {"id": "o-" + uuid.uuid4().hex[:8], "user": user, "lines": lines, "subtotal": subtotal,
             "discount": discount, "points_used": use_points, "total": total, "status": "paid"}
    db.orders[order["id"]] = order
    events.emit("order_paid", order=order)
    return order


def cancel(order_id):
    order = db.orders[order_id]
    if order["status"] != "paid":
        raise ValueError("only paid orders can be cancelled")
    order["status"] = "cancelled"
    payments.refund(order)
    events.emit("order_cancelled", order=order)
    return order


def refund(order_id):
    order = db.orders[order_id]
    if order["status"] != "paid":
        raise ValueError("only paid orders can be refunded")
    order["status"] = "refunded"
    payments.refund(order)
    events.emit("order_refunded", order=order)
    return order
