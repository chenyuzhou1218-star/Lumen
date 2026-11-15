"""Booking and cancelling."""

import uuid

from server import classes, credits, db, policy, stats, waitlist


class ClassFull(Exception):
    pass


def create(user, class_id):
    booking_id = "bk-" + uuid.uuid4().hex[:8]
    with db.lock:
        db.bookings[booking_id] = {"id": booking_id, "user": user, "class_id": class_id, "status": "booked"}
    stats.on_booked(classes.get(class_id))
    return db.bookings[booking_id]


def book(user, class_id):
    if classes.remaining(class_id) <= 0:
        position = waitlist.join(class_id, user)
        raise ClassFull(f"class is full; you are number {position} on the waiting list")
    credits.charge(user, f"booking {class_id}")
    return create(user, class_id)


def cancel(booking_id):
    with db.lock:
        b = db.bookings[booking_id]
        if b["status"] != "booked":
            raise ValueError("not an active booking")
        b["status"] = "cancelled"
    stats.on_cancelled(classes.get(b["class_id"]))
    if not policy.is_late(classes.starts_at(b["class_id"])):
        credits.refund(b["user"], f"cancel {booking_id}")
    waitlist.promote(b["class_id"], b["user"])
    return b
