"""Revenue."""

from shop import db


def revenue():
    """Money kept: charges minus refunds."""
    return sum(cents for _, cents, _ in db.payments)
