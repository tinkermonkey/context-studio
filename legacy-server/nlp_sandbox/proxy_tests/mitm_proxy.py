# mypy: ignore-errors
from mitmproxy import http
import hashlib
from collections import OrderedDict


class SimpleCache:
    def __init__(self, max_size=100):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            # Move to end (most recently used)
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        return None

    def put(self, key, value):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            # Remove least recently used (first item)
            self.cache.popitem(last=False)
        self.cache[key] = value


cache = SimpleCache(max_size=100)


def request(flow: http.HTTPFlow) -> None:
    # Create cache key from method, URL, and body
    cache_key = hashlib.md5(
        f"{flow.request.method}:{flow.request.pretty_url}:{flow.request.content}".encode()
    ).hexdigest()

    cached_response = cache.get(cache_key)
    if cached_response:
        print(f"🟢 CACHE HIT: {flow.request.method} {flow.request.pretty_url}")

        # Create response from cache
        flow.response = http.Response.make(
            cached_response["status_code"],
            cached_response["content"],
            cached_response["headers"],
        )
    else:
        print(f"🔴 CACHE MISS: {flow.request.method} {flow.request.pretty_url}")
        print(f"  headers: {flow.request.headers}")
        print(f"  body: {flow.request.content}")
        # Store cache key for later use in response
        flow.cache_key = cache_key


def response(flow: http.HTTPFlow) -> None:
    # Only cache if this was a cache miss
    if hasattr(flow, "cache_key"):
        cached_data = {
            "status_code": flow.response.status_code,
            "content": flow.response.content,
            "headers": dict(flow.response.headers),
        }
        cache.put(flow.cache_key, cached_data)
        print(f"💾 CACHED: {flow.request.method} {flow.request.pretty_url}")
        print(f"  headers: {flow.response.headers}")
        # print(f"  body: {flow.response.content}")
