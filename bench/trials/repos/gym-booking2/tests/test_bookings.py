from server import bookings, db


def test_booking_charges_one_credit():
    before = db.credits["ann"]
    bookings.book("ann", "spin-tue")
    assert db.credits["ann"] == before - 1


def test_cancel_marks_booking_cancelled():
    b = bookings.book("bob", "spin-tue")
    assert bookings.cancel(b["id"])["status"] == "cancelled"
