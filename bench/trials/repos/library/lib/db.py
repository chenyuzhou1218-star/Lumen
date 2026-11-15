"""In-memory tables."""

import threading

lock = threading.RLock()

books = {
    "b1": {"id": "b1", "title": "Dune", "copies": 1},
    "b2": {"id": "b2", "title": "Emma", "copies": 2},
    "b3": {"id": "b3", "title": "Ulysses", "copies": 1},
}
members = {
    "m1": {"id": "m1", "name": "Ann", "tier": "basic"},
    "m2": {"id": "m2", "name": "Bob", "tier": "Gold"},
    "m3": {"id": "m3", "name": "Cat", "tier": "basic"},
}
loans = {}       # loan_id -> {"id", "member", "book", "due", "status"}
holds = {}       # book_id -> [member_id, ...]
fines = {}       # member_id -> cents owed
ledger = []      # (member_id, cents, reason)  positive = money in
outbox = []      # (member_id, text)
