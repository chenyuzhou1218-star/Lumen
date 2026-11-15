"""Live counters shown on the timetable."""

booked = {}


def on_booked(cls):
    booked[cls["name"]] = booked.get(cls["name"], 0) + 1


def on_cancelled(cls):
    booked[cls["name"]] = max(0, booked.get(cls["name"], 0) - 1)


def booked_count(key):
    return booked.get(key, 0)
