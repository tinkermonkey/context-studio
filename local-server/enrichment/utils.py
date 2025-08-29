"""Utility helpers for enrichment package"""

from datetime import datetime, UTC


def utcnow_iso():
    return datetime.now(UTC)
