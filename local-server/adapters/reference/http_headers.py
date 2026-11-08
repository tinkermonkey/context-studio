"""Shared HTTP settings for the reference source adapters."""

# Wikimedia rejects generic client user agents (such as httpx's default) with a 403
# and asks every client to identify itself: https://w.wiki/4wJS
USER_AGENT = "ContextStudio (https://github.com/tinkermonkey/context-studio) python-httpx"

REFERENCE_HEADERS = {"User-Agent": USER_AGENT}
