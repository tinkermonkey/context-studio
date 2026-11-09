"""
Reference calls through the reference-api-buddy proxy (#1472).

Runs the real proxy in-process against a fake upstream on loopback: repeated
searches and grounding runs are served from the proxy's cache, a burst is held to
the configured hourly limit, errors are not cached, and with the proxy off or
failing to start the sources call their APIs directly.
"""

import asyncio
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx
import pytest

from adapters.reference import proxy as proxy_module
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding import GroundingAdapter
from adapters.reference.http_headers import USER_AGENT
from adapters.reference.proxy import ReferenceProxy
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from config import ReferenceProxyConfig

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_original_connect = socket.socket.connect

# One body answers all three APIs: each adapter reads only its own key.
UPSTREAM_BODY = {
    "edges": [{"start": {"@id": "/c/en/water", "label": "water"}}],
    # DBpedia Lookup: the current "docs" shape (#1500) and the older "results" shape.
    "docs": [{"resource": ["http://dbpedia.org/resource/Water"], "label": ["Water"]}],
    "results": [{"uri": "http://dbpedia.org/resource/Water", "label": "Water"}],
    "search": [{"id": "Q283", "label": "water", "description": "chemical compound"}],
}


def _loopback_only_connect(sock, address):
    """Refuse any connection that leaves this machine."""
    host = address[0] if isinstance(address, tuple) else address
    if sock.family in (socket.AF_INET, socket.AF_INET6) and host not in LOOPBACK_HOSTS:
        raise RuntimeError(f"Network access is blocked during test runs: {address}")
    return _original_connect(sock, address)


@pytest.fixture(autouse=True)
def block_network():
    """Overrides the integration conftest: these tests run servers on loopback only."""
    with patch.object(socket.socket, "connect", _loopback_only_connect):
        yield


class FakeUpstream:
    """A reference API stand-in that records each request it receives."""

    def __init__(self):
        self.requests: list[tuple[str, dict]] = []
        self.statuses: list[int] = []  # answered in order, then 200
        self.delay_seconds = 0.0
        self._lock = threading.Lock()
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with upstream._lock:
                    upstream.requests.append((self.path, dict(self.headers)))
                    status = upstream.statuses.pop(0) if upstream.statuses else 200
                time.sleep(upstream.delay_seconds)
                body = json.dumps(UPSTREAM_BODY if status == 200 else {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def upstream():
    fake = FakeUpstream()
    yield fake
    fake.close()


def _proxy_config(tmp_path, upstream_url, requests_per_hour=3600, enabled=True):
    source = {"upstream": upstream_url, "requests_per_hour": requests_per_hour}
    return ReferenceProxyConfig(
        enabled=enabled,
        cache_db_path=str(tmp_path / "cache" / "reference_api_cache.db"),
        sources={"conceptnet": source, "dbpedia": source, "wikidata": source},
    )


@pytest.fixture
def make_proxy(tmp_path, upstream):
    proxies: list[ReferenceProxy] = []

    def make(**kwargs) -> ReferenceProxy:
        reference_proxy = ReferenceProxy(_proxy_config(tmp_path, upstream.url, **kwargs))
        reference_proxy.start()
        proxies.append(reference_proxy)
        return reference_proxy

    yield make
    for reference_proxy in proxies:
        reference_proxy.stop()


def _sources(reference_proxy: ReferenceProxy):
    return (
        ConceptNetSource(
            base_url=reference_proxy.base_url("conceptnet"),
            upstream_url=reference_proxy.upstream_url("conceptnet"),
            timeout=5,
        ),
        DBpediaSource(
            base_url=reference_proxy.base_url("dbpedia"),
            upstream_url=reference_proxy.upstream_url("dbpedia"),
            timeout=5,
        ),
        WikidataSource(
            base_url=reference_proxy.base_url("wikidata"),
            upstream_url=reference_proxy.upstream_url("wikidata"),
            timeout=5,
        ),
    )


def test_proxy_listens_on_a_free_loopback_port(make_proxy):
    reference_proxy = make_proxy()

    assert reference_proxy.running
    assert reference_proxy.port not in (None, 0, 8000, 3100)
    assert reference_proxy.base_url("wikidata") == (
        f"http://127.0.0.1:{reference_proxy.port}/wikidata"
    )


def test_repeated_search_is_served_from_the_cache(make_proxy, upstream):
    conceptnet, dbpedia, wikidata = _sources(make_proxy())

    for source in (conceptnet, dbpedia, wikidata):
        first = source.search("water", limit=5)
        second = source.search("water", limit=5)
        assert first and first == second

    assert len(upstream.requests) == 3


def test_repeated_grounding_run_is_served_from_the_cache(make_proxy, upstream):
    conceptnet, dbpedia, wikidata = _sources(make_proxy())
    grounding = GroundingAdapter(
        dbpedia=dbpedia, conceptnet=conceptnet, wikidata=wikidata, schema_org=SchemaOrgSource()
    )

    async def run_twice():
        return (
            await grounding.query_sources("water"),
            await grounding.query_sources("water"),
        )

    first, second = asyncio.run(run_twice())

    assert {c.source for c in first} >= {"ConceptNet", "DBpedia", "Wikidata"}
    assert [c.uri for c in first] == [c.uri for c in second]
    # One upstream request per network source; the second run is all cache hits.
    assert len(upstream.requests) == 3


def test_proxy_forwards_the_user_agent(make_proxy, upstream):
    _, _, wikidata = _sources(make_proxy())

    wikidata.search("water", limit=1)

    _, headers = upstream.requests[0]
    assert headers.get("User-Agent") == USER_AGENT


def test_burst_is_held_to_requests_per_hour(make_proxy, upstream):
    reference_proxy = make_proxy(requests_per_hour=3)
    base_url = reference_proxy.base_url("conceptnet")

    statuses = [
        httpx.get(f"{base_url}/query", params={"text": f"term{i}"}, timeout=10).status_code
        for i in range(5)
    ]

    assert statuses == [200, 200, 200, 429, 429]
    assert len(upstream.requests) == 3


def test_throttled_term_asked_again_is_answered_at_once(make_proxy, upstream):
    """A 429 must not leave the term stuck in-flight (reference-api-buddy 0.5.0 bug)."""
    base_url = make_proxy(requests_per_hour=1).base_url("conceptnet")
    httpx.get(f"{base_url}/query", params={"text": "first"}, timeout=5)

    for _ in range(2):
        started = time.monotonic()
        response = httpx.get(f"{base_url}/query", params={"text": "second"}, timeout=5)
        assert response.status_code == 429
        assert time.monotonic() - started < 2

    assert len(upstream.requests) == 1


def test_a_source_can_set_only_its_rate_limit():
    config = ReferenceProxyConfig.model_validate(
        {"sources": {"dbpedia": {"requests_per_hour": 600}}}
    )

    assert config.sources.dbpedia.upstream == "https://lookup.dbpedia.org"
    assert config.sources.dbpedia.requests_per_hour == 600
    assert config.sources.wikidata.upstream == "https://www.wikidata.org"


def test_throttled_search_returns_no_results(make_proxy, upstream):
    conceptnet, _, _ = _sources(make_proxy(requests_per_hour=1))

    assert conceptnet.search("first", limit=5)
    assert conceptnet.search("second", limit=5) == []
    assert len(upstream.requests) == 1


def test_identical_concurrent_requests_reach_upstream_once(make_proxy, upstream):
    upstream.delay_seconds = 0.3
    conceptnet, _, _ = _sources(make_proxy())
    results: list = []

    threads = [
        threading.Thread(target=lambda: results.append(conceptnet.search("water", limit=5)))
        for _ in range(5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 5 and all(results)
    assert len(upstream.requests) == 1


def test_upstream_errors_are_not_cached(make_proxy, upstream):
    upstream.statuses = [500]
    conceptnet, _, _ = _sources(make_proxy())

    assert conceptnet.search("water", limit=5) == []
    assert conceptnet.search("water", limit=5)
    assert len(upstream.requests) == 2


def test_availability_is_checked_against_the_upstream(make_proxy, upstream):
    other_upstream = FakeUpstream()
    try:
        reference_proxy = make_proxy()
        conceptnet = ConceptNetSource(
            base_url=reference_proxy.base_url("conceptnet"),
            upstream_url=other_upstream.url,
            timeout=5,
        )

        assert conceptnet.is_available()
        assert conceptnet.is_available()

        assert [path for path, _ in other_upstream.requests] == ["/c/en/test", "/c/en/test"]
        assert upstream.requests == []
    finally:
        other_upstream.close()


def test_disabled_proxy_calls_the_upstream_directly(make_proxy, upstream):
    reference_proxy = make_proxy(enabled=False)
    conceptnet, _, _ = _sources(reference_proxy)

    assert not reference_proxy.running
    assert reference_proxy.base_url("conceptnet") == upstream.url
    assert conceptnet.search("water", limit=5)
    assert conceptnet.search("water", limit=5)
    assert len(upstream.requests) == 2


def test_proxy_that_fails_to_start_falls_back_to_the_upstream(make_proxy, upstream, monkeypatch):
    def refuse_to_start(config):
        raise OSError("address already in use")

    monkeypatch.setattr(proxy_module, "CachingProxy", refuse_to_start)
    reference_proxy = make_proxy()
    conceptnet, _, _ = _sources(reference_proxy)

    assert not reference_proxy.running
    assert reference_proxy.base_url("conceptnet") == upstream.url
    assert conceptnet.search("water", limit=5)


def test_stop_hands_out_the_upstream_again(make_proxy, upstream):
    reference_proxy = make_proxy()
    reference_proxy.stop()
    reference_proxy.stop()

    assert not reference_proxy.running
    assert reference_proxy.base_url("dbpedia") == upstream.url
