"""Reference adapters identify themselves and explain a refused availability check."""

import os
import sys
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.reference import conceptnet, dbpedia, wikidata
from adapters.reference.http_headers import USER_AGENT

SOURCES = [
    (wikidata, wikidata.WikidataSource),
    (dbpedia, dbpedia.DBpediaSource),
    (conceptnet, conceptnet.ConceptNetSource),
]


class FakeGet:
    """Stands in for httpx.get: records each call's headers and answers with one status."""

    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload if payload is not None else {}
        self.headers: list[dict] = []

    def __call__(self, url, **kwargs):
        self.headers.append(kwargs.get("headers") or {})
        return httpx.Response(self.status_code, json=self.payload, request=httpx.Request("GET", url))


@pytest.mark.parametrize("module,source_class", SOURCES)
def test_availability_check_sends_the_user_agent(monkeypatch, module, source_class):
    fake_get = FakeGet(200)
    monkeypatch.setattr(module.httpx, "get", fake_get)

    assert source_class(timeout=1).is_available() is True
    assert fake_get.headers[0].get("User-Agent") == USER_AGENT


@pytest.mark.parametrize("module,source_class", SOURCES)
def test_refused_availability_check_is_logged(monkeypatch, module, source_class):
    monkeypatch.setattr(module.httpx, "get", FakeGet(403))
    logger = MagicMock()
    monkeypatch.setattr(module, "logger", logger)

    assert source_class(timeout=1).is_available() is False
    logger.warning.assert_called_once()
    assert "HTTP 403" in logger.warning.call_args.args[0]


@pytest.mark.parametrize("module,source_class", SOURCES)
def test_search_sends_the_user_agent(monkeypatch, module, source_class):
    fake_get = FakeGet(200)
    monkeypatch.setattr(module.httpx, "get", fake_get)

    source_class(timeout=1).search("house", limit=1)

    assert fake_get.headers, "search made no request"
    assert all(h.get("User-Agent") == USER_AGENT for h in fake_get.headers)
