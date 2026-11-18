"""
Unit tests for SentenceTransformerEmbedding.warm_up and is_loading.

The real model is never loaded: _load_model is replaced by a fake that counts
its calls and can be held open to simulate a slow load.
"""

import sys
import threading
import types

import pytest

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding


class _FakeVector(list):
    def tolist(self) -> list:
        return list(self)


class _FakeModel:
    """Stands in for the SentenceTransformer: records what it encodes."""

    def __init__(self):
        self.encoded: list[str] = []

    def encode(self, text, convert_to_tensor=False):
        self.encoded.append(text)
        return _FakeVector([0.0, 1.0])


class _FakeLoad:
    """Stands in for _load_model: counts calls and blocks until released."""

    def __init__(self, embedding: SentenceTransformerEmbedding, fail: bool = False):
        self._embedding = embedding
        self._fail = fail
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self) -> None:
        self.calls += 1
        self.started.set()
        assert self.release.wait(timeout=5)
        if self._fail:
            raise RuntimeError("no model here")
        self._embedding._model = _FakeModel()  # type: ignore[assignment]


@pytest.fixture
def embedding():
    return SentenceTransformerEmbedding(model_name="test-model")


def test_warm_up_loads_the_model(embedding, monkeypatch):
    load = _FakeLoad(embedding)
    load.release.set()
    monkeypatch.setattr(embedding, "_load_model", load)

    embedding.warm_up()

    assert embedding.is_loaded()
    assert not embedding.is_loading()
    assert load.calls == 1


def test_is_loading_while_warming_and_a_request_waits_instead_of_loading_again(
    embedding, monkeypatch
):
    load = _FakeLoad(embedding)
    monkeypatch.setattr(embedding, "_load_model", load)
    warm = threading.Thread(target=embedding.warm_up)
    warm.start()
    assert load.started.wait(timeout=5)

    assert embedding.is_loading()
    assert not embedding.is_loaded()
    request = threading.Thread(target=embedding._ensure_model_loaded)
    request.start()
    request.join(timeout=0.2)
    assert request.is_alive(), "a request during warm-up waits for the load"

    load.release.set()
    warm.join(timeout=5)
    request.join(timeout=5)

    assert not request.is_alive()
    assert embedding.is_loaded()
    assert not embedding.is_loading()
    assert load.calls == 1


def test_warm_up_when_already_loaded_does_not_load_again(embedding, monkeypatch):
    load = _FakeLoad(embedding)
    load.release.set()
    monkeypatch.setattr(embedding, "_load_model", load)
    embedding._model = _FakeModel()

    embedding.warm_up()

    assert load.calls == 0


def test_a_failed_warm_up_is_not_raised_and_the_next_use_retries(embedding, monkeypatch):
    failing = _FakeLoad(embedding, fail=True)
    failing.release.set()
    monkeypatch.setattr(embedding, "_load_model", failing)

    embedding.warm_up()

    assert not embedding.is_loaded()
    assert not embedding.is_loading()
    working = _FakeLoad(embedding)
    working.release.set()
    monkeypatch.setattr(embedding, "_load_model", working)
    embedding._ensure_model_loaded()
    assert embedding.is_loaded()


def test_the_load_runs_the_first_encode_before_the_model_counts_as_loaded(embedding, monkeypatch):
    seen_loaded_during_encode = []

    class _FakeSentenceTransformer(_FakeModel):
        def __init__(self, model_name):
            super().__init__()

        def encode(self, text, convert_to_tensor=False):
            seen_loaded_during_encode.append(embedding.is_loaded())
            return super().encode(text, convert_to_tensor)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = _FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    embedding.warm_up()

    assert embedding.is_loaded()
    assert len(embedding._model.encoded) == 1
    assert seen_loaded_during_encode == [False]
