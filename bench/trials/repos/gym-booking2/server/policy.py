"""Cancellation policy."""

from datetime import datetime, timezone

LATE_HOURS = 12      # cancelling less than this many hours before class costs the credit


def hours_until(starts_at):
    return (starts_at - datetime.now(timezone.utc)).seconds // 3600


def is_late(starts_at):
    return hours_until(starts_at) < LATE_HOURS
