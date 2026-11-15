"""In-memory state."""

wallets = {"u1": 20000, "u2": 1000}   # cents
points = {"u1": 300, "u2": 500}
orders = {}
payments = []        # (user, cents, kind)
shipments = {}       # order_id -> {"weight_g", "cost"}
