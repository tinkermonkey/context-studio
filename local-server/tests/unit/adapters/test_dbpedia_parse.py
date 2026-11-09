"""DBpedia Lookup responses parse into reference results.

The fixture is a real response from lookup.dbpedia.org/api/search?query=Bicycle,
recorded 2026-11-09.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.reference import dbpedia
from adapters.reference.dbpedia import DBpediaSource

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "reference" / "dbpedia_lookup_bicycle.json"


@pytest.fixture
def bicycle_response() -> dict:
    return json.loads(FIXTURE.read_text())


def test_recorded_response_parses_into_results(bicycle_response):
    results = DBpediaSource()._parse_search_response(bicycle_response, limit=10)

    assert len(results) == 10
    assert all(r.source == "DBpedia" for r in results)
    bicycle = next(r for r in results if r.uri == "http://dbpedia.org/resource/Bicycle")
    assert bicycle.label == "Bicycle"
    assert bicycle.description.startswith("A bicycle, also called a bike or cycle")


def test_highlight_tags_are_stripped(bicycle_response):
    results = DBpediaSource()._parse_search_response(bicycle_response, limit=10)

    assert results[0].label == "Road bicycle racing"
    for r in results:
        assert "<B>" not in r.label and "</B>" not in r.label
        assert "<B>" not in (r.description or "")


def test_limit_caps_the_results(bicycle_response):
    assert len(DBpediaSource()._parse_search_response(bicycle_response, limit=3)) == 3


def test_doc_without_a_resource_is_skipped():
    data = {"docs": [{"label": ["No resource"]}, {"resource": ["http://dbpedia.org/resource/X"]}]}

    results = DBpediaSource()._parse_search_response(data, limit=10)

    assert [r.uri for r in results] == ["http://dbpedia.org/resource/X"]
    assert results[0].label == ""
    assert results[0].description is None


def test_empty_docs_is_no_results():
    assert DBpediaSource()._parse_search_response({"docs": []}, limit=10) == []


def test_unknown_response_shape_is_logged(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(dbpedia, "logger", logger)

    assert DBpediaSource()._parse_search_response({"results": []}, limit=10) == []
    logger.warning.assert_called_once()
    assert "docs" in logger.warning.call_args.args[0]


def test_search_returns_parsed_results(monkeypatch, bicycle_response):
    def fake_get(url, **kwargs):
        return httpx.Response(200, json=bicycle_response, request=httpx.Request("GET", url))

    monkeypatch.setattr(dbpedia.httpx, "get", fake_get)

    results = DBpediaSource(timeout=1).search("Bicycle", limit=10)

    assert "http://dbpedia.org/resource/Bicycle" in [r.uri for r in results]


async def test_search_async_returns_parsed_results(bicycle_response):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bicycle_response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await DBpediaSource(timeout=1, async_client=client).search_async("Bicycle")

    assert "http://dbpedia.org/resource/Bicycle" in [r.uri for r in results]
