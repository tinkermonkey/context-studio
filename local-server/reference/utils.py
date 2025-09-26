"""Utility helpers for reference package"""

from datetime import datetime, UTC


def utcnow_iso():
    return datetime.now(UTC)
