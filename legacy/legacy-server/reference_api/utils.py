"""Utility helpers for reference package"""

from datetime import UTC, datetime


def utcnow_iso():
    return datetime.now(UTC)
