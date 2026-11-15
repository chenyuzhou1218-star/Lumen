"""Library policy."""

LOAN_DAYS = 14          # a loan lasts two weeks; a renewal adds another two weeks to the due date
GRACE_DAYS = 2          # returning up to this many days late costs nothing
FINE_CENTS_PER_DAY = 50 # after the grace days
LIMITS = {"basic": 3, "gold": 5}   # books a member may have out at once
