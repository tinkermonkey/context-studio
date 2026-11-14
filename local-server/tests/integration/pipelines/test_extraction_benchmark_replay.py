"""
The offline benchmark replay (scripts/benchmark_replay.py): the ontology it
builds is the one the gold extractions were made against, and a document runs
through chunking, extraction, merging and planning into scored predictions
without any network access.
"""

import json
import os
import re
import sys

import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from domain.pipelines.ports import LLMResponse
from scripts.benchmark_replay import (
    DEV_DOCUMENTS,
    FIND_THEN_TYPE,
    HOLDOUT_DOCUMENTS,
    DocumentResult,
    benchmark_ontology,
    cassette_path,
    extract_document,
    replay_document,
    summarize,
)
from tests.integration.pipelines._harness.benchmark import (
    SchemaSnapshot,
    benchmark_documents,
    class_reference,
    load_gold,
    load_schema_bundle,
    score,
)

DOCUMENT = "wikimedia_enterprise"
ACTOR = "business.businessactor"
_OFFERED = re.compile(r"^- ([a-z\-]+\.[a-z]+) \(", re.MULTILINE)


class StubProvider:
    """
    Answers the identify stage with one individual whenever its name is in the
    chunk, typed with a class the prompt offers, and every other call with nothing.
    """

    def __init__(self, name: str, preferred_class: str) -> None:
        self._name = name
        self._preferred = preferred_class
        self.offered: list[set[str]] = []

    def complete(self, system_prompt, user_prompt, model, **_: object) -> LLMResponse:
        triples = []
        if "Identify the individuals" in user_prompt:
            offered = set(_OFFERED.findall(user_prompt))
            self.offered.append(offered)
            start = user_prompt.find(self._name)
            if start >= 0 and offered:
                label = self._preferred if self._preferred in offered else sorted(offered)[0]
                triples.append(
                    {
                        "subject": {"kind": "individual", "label": self._name},
                        "predicate": {"label": "is_a"},
                        "object": {"kind": "class", "label": label},
                        "confidence": 0.9,
                        "provenance": {
                            "text_offset_start": 0,
                            "text_offset_end": len(self._name),
                            "raw": self._name,
                        },
                    }
                )
        return LLMResponse(
            content=json.dumps({"triples": triples}),
            tokens_in=1,
            tokens_out=1,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(self, **kwargs) -> LLMResponse:
        return self.complete(**kwargs)

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return []


@pytest.fixture(scope="module")
def ontology():
    return benchmark_ontology()


def test_split_names_real_documents():
    assert set(DEV_DOCUMENTS) | set(HOLDOUT_DOCUMENTS) == set(benchmark_documents())
    assert not set(DEV_DOCUMENTS) & set(HOLDOUT_DOCUMENTS)


def test_pinned_spec_builds_the_schema_the_gold_files_were_made_against(ontology):
    """The pinned DR spec and the schema bundle are two snapshots of one schema."""
    snapshot = SchemaSnapshot.load()
    assert set(ontology.class_refs.values()) == set(snapshot.attributes)
    built_types = {
        (
            ontology.class_refs[p.domain_class_id],
            ontology.predicates.get(p.predicate_id) or p.canonical_predicate,
            ontology.class_refs[p.range_class_id],
        )
        for p in ontology.repo.list_property_definitions(limit=None)
        if p.domain_class_id in ontology.class_refs and p.range_class_id in ontology.class_refs
    }
    assert built_types == set(snapshot.relationship_types)
    bundle_definitions = {
        class_reference(c): c["description"] for c in load_schema_bundle()["classes"]
    }
    built_definitions = {
        ontology.class_refs[c.id]: c.description for c in ontology.repo.list_classes(limit=None)
    }
    assert built_definitions == bundle_definitions


async def test_document_runs_as_a_source_into_scored_predictions(ontology):
    provider = StubProvider("Wikimedia Foundation", ACTOR)
    individuals, relationships = await extract_document(ontology, provider, DOCUMENT)

    assert len(provider.offered) > 1, "the document should be extracted chunk by chunk"
    assert [i.title for i in individuals] == ["Wikimedia Foundation"], "chunks merge into one"
    assert relationships == []
    assert individuals[0].evidence, "the planned create keeps its passages"

    result = score(load_gold(DOCUMENT), individuals, relationships)
    assert result.counts["matched"] == 1
    assert result.metrics["precision"] == 1.0
    assert individuals[0].class_refs, "the planned create is typed with a DR class reference"


async def test_a_document_without_a_cassette_is_not_scored(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.benchmark_replay.CASSETTE_DIR", tmp_path)
    result = await replay_document(DOCUMENT)
    assert (result.status, result.score) == ("not_recorded", None)


async def test_a_stale_cassette_is_reported_not_scored_as_zero(ontology, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.benchmark_replay.CASSETTE_DIR", tmp_path)
    (tmp_path / f"{DOCUMENT}.json").write_text("{}")
    result = await replay_document(DOCUMENT)
    assert result.status == "stale"
    assert result.score is None
    assert result.misses == result.calls > 0


def test_summary_is_trusted_only_when_every_document_scored():
    results = [
        DocumentResult("edit_check", "stale", calls=4, misses=4),
        DocumentResult("gitlab_architecture", "not_recorded"),
    ]
    summary = summarize(results)
    assert summary["status"] == "stale"
    assert summary["dev"] == {} and summary["holdout"] == {}
    assert summarize([DocumentResult("edit_check", "not_recorded")])["status"] == "not_recorded"


def test_a_run_over_some_documents_is_partial_and_gives_no_split_mean():
    one = score(load_gold("edit_check"), [])
    summary = summarize([DocumentResult("edit_check", "scored", one, calls=1)])
    assert summary["status"] == "partial"
    assert summary["dev"] == {} and summary["holdout"] == {} and summary["failure_counts"] == {}
    assert summarize([])["status"] == "partial"


def test_every_document_scored_gives_both_split_means():
    results = [
        DocumentResult(d, "scored", score(load_gold(d), []), calls=1)
        for d in ("edit_check", "gitlab_architecture", "wikimedia_enterprise")
    ]
    summary = summarize(results)
    assert summary["status"] == "scored"
    assert summary["dev"]["typed_f1"] == 0.0 and summary["holdout"]["typed_f1"] == 0.0
    assert summary["failure_counts"]["missed_core"] > 0


def test_a_document_whose_extraction_failed_is_not_scored():
    failed = DocumentResult("edit_check", "failed", calls=4, detail="extraction failed")
    summary = summarize([failed])
    assert summary["status"] == "failed"
    assert summary["dev"] == {}


class FindThenTypeStub:
    """
    Answers the find stage with one named thing whenever its name is in the
    chunk, the type stage with a class of the catalog, and relate with nothing.
    """

    def __init__(self, name: str, class_ref: str) -> None:
        self._name = name
        self._class_ref = class_ref
        self.finds = 0
        self.catalogs: set[str] = set()
        self.typed: list[str] = []

    def complete(self, system_prompt, user_prompt, model, **_: object) -> LLMResponse:
        content = json.dumps({"triples": []})
        if user_prompt.startswith("List the elements"):
            self.finds += 1
            mentions = []
            if self._name in user_prompt:
                mentions = [{"name": self._name, "kind": "thing", "quote": self._name}]
            content = json.dumps({"mentions": mentions})
        elif "Candidate: " in user_prompt:
            self.catalogs.add(system_prompt)
            self.typed.append(user_prompt.split("Candidate: ")[1].splitlines()[0])
            assert f"- {self._class_ref}: " in system_prompt, "the catalog lists the class"
            content = json.dumps({"class": self._class_ref, "confidence": 0.9})
        return LLMResponse(
            content=content,
            tokens_in=1,
            tokens_out=1,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    def forget(self, **_: object) -> None:
        pass


async def test_find_then_type_types_a_mention_once_against_the_whole_catalog(ontology):
    provider = FindThenTypeStub("Wikimedia Foundation", ACTOR)
    individuals, relationships = await extract_document(
        ontology, provider, DOCUMENT, implementation=FIND_THEN_TYPE
    )

    assert provider.finds > 1, "the document should be read chunk by chunk"
    assert provider.typed == ["Wikimedia Foundation"], "one typing call for the whole source"
    (catalog,) = provider.catalogs
    offered = set(re.findall(r"^- ([a-z\-]+\.[a-z]+): ", catalog, re.MULTILINE))
    assert offered == set(ontology.class_refs.values()), "every class of the taxonomy is offered"
    assert [(i.title, i.class_refs) for i in individuals] == [("Wikimedia Foundation", (ACTOR,))]
    assert len(individuals[0].evidence) > 1, "a passage from each chunk that mentions it"
    assert relationships == []


async def test_a_document_without_a_find_then_type_cassette_is_not_scored(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.benchmark_replay.CASSETTE_DIR", tmp_path / "extraction_benchmark")
    result = await replay_document(DOCUMENT, implementation=FIND_THEN_TYPE)
    assert (result.status, result.score) == ("not_recorded", None)


def test_the_two_implementations_keep_their_cassettes_apart():
    default, find_then_type = cassette_path(DOCUMENT), cassette_path(DOCUMENT, FIND_THEN_TYPE)
    assert default.parent.name == "extraction_benchmark"
    assert find_then_type.parent.name == "extraction_benchmark_find_then_type"
    assert default.parent.parent == find_then_type.parent.parent


@pytest.mark.parametrize("document", sorted([*DEV_DOCUMENTS, *HOLDOUT_DOCUMENTS]))
async def test_find_then_type_recordings_replay_and_keep_their_gain(ontology, document):
    """
    The recorded find-then-type runs answer today's prompts, and score well
    above the two-pass baseline's typed F1 (0.07 to 0.16 on these documents).
    """
    result = await replay_document(document, implementation=FIND_THEN_TYPE)

    assert result.status == "scored", result
    assert result.misses == 0
    assert result.score.metrics["typed_f1"] > 0.3
    assert result.score.metrics["type_accuracy"] > 0.6
