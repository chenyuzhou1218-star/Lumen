"""Shop policy."""

POINT_VALUE_CENTS = 10     # one loyalty point is worth 10 cents when spent
POINTS_PER_YUAN = 1        # one point per full yuan (100 cents) actually paid
COUPONS = {"TEN": 10, "HALF": 50}           # percent off the subtotal
SHIPPING_TIERS_KG = [(1, 500), (3, 900), (None, 1500)]   # (up to this many kg, cost in cents)
