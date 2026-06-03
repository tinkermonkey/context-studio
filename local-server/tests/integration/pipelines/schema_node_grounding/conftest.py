"""Fixtures for schema node grounding tests.

Provides HTTP cassette recording/replay for deterministic testing of reference
source adapters (DBpedia, ConceptNet, Wikidata, schema.org) without requiring
live network access.
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest

from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding.adapter import GroundingAdapter
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from tests.integration.pipelines._harness.cassettes import (
    RecordingHTTPTransport,
    ReplayHTTPTransport,
)


@pytest.fixture
def http_cassette_path(request) -> Path:
    """Compute HTTP cassette path based on test module and function."""
    test_file = Path(request.node.fspath)
    test_name = request.node.name

    cassette_dir = test_file.parent / "_cassettes" / test_file.stem
    cassette_dir.mkdir(parents=True, exist_ok=True)

    return cassette_dir / f"{test_name}.json"


@pytest.fixture
def http_cassette_mode(request) -> str:
    """Determine HTTP cassette execution mode: 'record', 'replay', or 'live'."""
    if request.node.get_closest_marker("real_http"):
        return "live"
    if request.config.getoption("--refresh-cassettes", default=False):
        return "record"
    return "replay"


@pytest.fixture
async def http_client(
    http_cassette_mode, http_cassette_path
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an httpx.AsyncClient with optional cassette recording/replay.

    Returns:
    - Client with RecordingHTTPTransport if record mode
    - Client with ReplayHTTPTransport if replay mode and cassette exists
    - Client with default transport if live mode

    Properly closes the client on teardown, ensuring cassettes are flushed to disk.
    """
    transport: httpx.AsyncBaseTransport
    if http_cassette_mode == "record":
        transport = RecordingHTTPTransport(
            delegate=httpx.AsyncHTTPTransport(),
            cassette_path=http_cassette_path,
        )
        client = httpx.AsyncClient(transport=transport)
    elif http_cassette_mode == "replay":
        if not http_cassette_path.exists():
            raise FileNotFoundError(
                f"HTTP cassette not found at {http_cassette_path}. "
                f"Run with --refresh-cassettes to record, or mark test with @pytest.mark.real_http"
            )
        transport = ReplayHTTPTransport(cassette_path=http_cassette_path)
        client = httpx.AsyncClient(transport=transport)
    else:
        client = httpx.AsyncClient()

    yield client
    await client.aclose()


@pytest.fixture
def reference_sources_client(http_client) -> httpx.AsyncClient:
    """Alias for http_client used by reference source adapters."""
    return http_client


@pytest.fixture
def grounding_adapter(http_client) -> GroundingAdapter:
    """Create a GroundingAdapter with cassette-enabled HTTP client.

    All HTTP calls from source adapters will be recorded/replayed via cassettes.
    """
    return GroundingAdapter(
        dbpedia=DBpediaSource(async_client=http_client),
        conceptnet=ConceptNetSource(async_client=http_client),
        wikidata=WikidataSource(async_client=http_client),
        schema_org=SchemaOrgSource(async_client=http_client),
    )
