"""In-memory tables."""

import threading
from datetime import datetime, timedelta, timezone

lock = threading.RLock()

_now = datetime.now(timezone.utc)
classes = {
    "yoga-mon": {"id": "yoga-mon", "name": "Morning Yoga", "capacity": 2,
                 "starts_at": (_now + timedelta(days=2, hours=1)).isoformat()},
    "spin-tue": {"id": "spin-tue", "name": "Spin", "capacity": "3",
                 "starts_at": (_now + timedelta(hours=5)).isoformat()},
}

credits = {"ann": 5, "bob": 5, "cat": 5, "dan": 5}   # class credits per member

bookings = {}      # booking_id -> {"id", "user", "class_id", "status"}
waitlists = {}     # class_id -> [user, ...]
history = []       # (user, delta, reason)
