"""
The offline benchmark replay (scripts/benchmark_replay.py): what it runs is an
implementation and a configuration read from the pipeline registry, the
ontology it builds is the one the gold extractions were made against, and a
document runs through chunking, extraction, merging and planning into scored
predictions without any network access.
"""

import json
import os
import re
import sys
from dataclasses import replace

import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.ports import LLMResponse
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from scripts import benchmark_replay
from scripts.benchmark_replay import (
    DEV_DOCUMENTS,
    HOLDOUT_DOCUMENTS,
    PIPELINE_TYPE,
    RECORDED_WITH,
    DocumentResult,
    UnknownTargetError,
    benchmark_ontology,
    cassette_dir,
    cassette_path,
    default_configuration,
    default_implementation,
    extract_document,
    pipeline_registries,
    pipeline_resolver,
    recorded_targets,
    replay_document,
    resolve_target,
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
# The implementations with committed recordings, by their registry ids. The
# two-pass implementation's id is `default`, a name only: the type's default
# implementation is find_then_type.
TWO_PASS = "default"
FIND_THEN_TYPE = "find_then_type"
ALL_DOCUMENTS = sorted([*DEV_DOCUMENTS, *HOLDOUT_DOCUMENTS])
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
        # (system prompt, model, temperature) of every call
        self.calls: list[tuple[str, str, object]] = []
        self.limits: list[object] = []

    def complete(self, system_prompt, user_prompt, model, **kwargs: object) -> LLMResponse:
        self.calls.append((system_prompt, model, kwargs.get("temperature")))
        self.limits.append(kwargs.get("max_tokens"))
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
    individuals, relationships = await extract_document(
        ontology, provider, DOCUMENT, resolve_target(TWO_PASS)
    )

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
    result = await replay_document(DOCUMENT, resolve_target(TWO_PASS))
    assert (result.status, result.score) == ("not_recorded", None)


async def test_a_stale_cassette_is_reported_not_scored_as_zero(ontology, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.benchmark_replay.CASSETTE_DIR", tmp_path)
    (tmp_path / f"{DOCUMENT}.json").write_text("{}")
    result = await replay_document(DOCUMENT, resolve_target(TWO_PASS))
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
        ontology, provider, DOCUMENT, resolve_target(FIND_THEN_TYPE)
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
    result = await replay_document(DOCUMENT, resolve_target(FIND_THEN_TYPE))
    assert (result.status, result.score) == ("not_recorded", None)


# -- what runs: an implementation and a configuration, from the registry -----


def test_with_nothing_asked_for_the_target_is_the_registrys_default_implementation():
    implementations, configurations = pipeline_registries()
    target = resolve_target()

    assert target.implementation == default_implementation()
    assert target.implementation == implementations.default_implementation(PIPELINE_TYPE)
    assert target.implementation == FIND_THEN_TYPE, "find_then_type is the type's default"
    assert TWO_PASS != default_implementation(), "the two-pass id `default` is only a name"
    assert target.orchestrator is implementations.get(PIPELINE_TYPE, target.implementation)
    registered = configurations.get_latest(
        PIPELINE_TYPE, target.implementation, target.configuration
    )
    assert target.config == registered.config
    assert target.model == registered.config["model"], "the model is the configuration's"


def test_the_run_input_is_the_resolvers():
    """Model, temperature and output-token limit come from the pipeline resolver."""
    for implementation in (TWO_PASS, FIND_THEN_TYPE):
        target = resolve_target(implementation)
        selection = pipeline_resolver().resolve(PIPELINE_TYPE, implementation, target.configuration)
        assert target.run_input({"text": "t"}) == selection.run_input({"text": "t"})
        filled = target.run_input({"text": "t"})
        assert filled["model"] == target.model
        assert filled["max_tokens"] == target.config["max_tokens"]


def test_the_default_benchmark_runs_with_the_configuration_its_recordings_were_made_with():
    target = resolve_target(TWO_PASS)

    assert RECORDED_WITH[TWO_PASS] == "extraction-openrouter-default"
    assert target.configuration == "extraction-openrouter-default"
    assert target.configuration != default_configuration(TWO_PASS), "pinned by name, not by default"
    assert cassette_dir(target).name == "extraction_benchmark"


def test_a_new_default_configuration_does_not_move_the_default_benchmark(monkeypatch):
    """`extraction-default` changing model leaves the recorded target as it was."""
    before = resolve_target(TWO_PASS)
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    moved = {**configurations.get_latest(PIPELINE_TYPE, TWO_PASS, "extraction-default").config}
    moved["model"] = "another-model"
    configurations.register(PIPELINE_TYPE, TWO_PASS, "extraction-default", moved)
    monkeypatch.setattr(
        "scripts.benchmark_replay.pipeline_registries", lambda: (implementations, configurations)
    )

    after = resolve_target(TWO_PASS)
    assert (after.configuration, after.model) == (before.configuration, before.model)
    assert cassette_dir(after) == cassette_dir(before)
    # Asked for by name, the moved configuration is another target with its own folder
    asked = resolve_target(TWO_PASS, "extraction-default")
    assert asked.model == "another-model"
    assert cassette_dir(asked).name == "extraction_benchmark__extraction-default"


def test_every_recorded_implementation_is_pinned_to_the_configuration_it_was_recorded_with():
    _, configurations = pipeline_registries()
    target = resolve_target(FIND_THEN_TYPE)

    assert RECORDED_WITH[FIND_THEN_TYPE] == "extraction-find-then-type"
    assert target.configuration == "extraction-find-then-type"
    registered = configurations.get_latest(PIPELINE_TYPE, FIND_THEN_TYPE, target.configuration)
    assert target.model == registered.config["model"]
    assert cassette_dir(target).name == "extraction_benchmark_find_then_type"
    assert {t.implementation for t in recorded_targets()} == set(RECORDED_WITH)


def test_a_new_default_configuration_does_not_inherit_the_recordings(monkeypatch):
    """A new default configuration of find_then_type is another target, another folder."""
    before = resolve_target(FIND_THEN_TYPE)
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, None)
    newer = {**before.config, "model": "another-model"}
    configurations.register(
        PIPELINE_TYPE, FIND_THEN_TYPE, "extraction-find-then-type-2", newer, default=True
    )
    configurations.register(
        PIPELINE_TYPE, FIND_THEN_TYPE, "extraction-find-then-type", dict(before.config)
    )
    monkeypatch.setattr(
        "scripts.benchmark_replay.pipeline_registries", lambda: (implementations, configurations)
    )

    assert default_configuration(FIND_THEN_TYPE) == "extraction-find-then-type-2"
    after = resolve_target(FIND_THEN_TYPE)
    assert (after.configuration, after.model) == (before.configuration, before.model)
    assert cassette_dir(after) == cassette_dir(before)
    asked = resolve_target(FIND_THEN_TYPE, "extraction-find-then-type-2")
    assert asked.model == "another-model"
    assert cassette_dir(asked).name == (
        "extraction_benchmark_find_then_type__extraction-find-then-type-2"
    )


def test_an_implementation_with_no_recordings_runs_with_its_default_configuration(monkeypatch):
    monkeypatch.setattr("scripts.benchmark_replay.RECORDED_WITH", {})
    for implementation in (TWO_PASS, FIND_THEN_TYPE):
        target = resolve_target(implementation)
        assert target.configuration == default_configuration(implementation)


def test_a_configuration_asked_for_by_name_is_the_one_run():
    _, configurations = pipeline_registries()
    target = resolve_target(TWO_PASS, "extraction-default")

    registered = configurations.get_latest(PIPELINE_TYPE, TWO_PASS, "extraction-default")
    assert target.config == registered.config
    assert target.flags == "--implementation default --configuration extraction-default"
    assert cassette_dir(target).name == "extraction_benchmark__extraction-default"
    other = replace(resolve_target(FIND_THEN_TYPE), configuration="extraction-other")
    assert cassette_dir(other).name == "extraction_benchmark_find_then_type__extraction-other"


@pytest.mark.parametrize(
    "implementation, configuration, message",
    [
        ("no_such", None, "no implementation 'no_such'"),
        # A configuration of another implementation is not one of this one's
        (TWO_PASS, "extraction-find-then-type", "no configuration 'extraction-find-then-type'"),
        (FIND_THEN_TYPE, "extraction-default", "no configuration 'extraction-default'"),
        # Registered, but it does not extract a source chunk by chunk
        ("open_v1", None, "the benchmark cannot run it"),
    ],
)
def test_a_target_the_benchmark_cannot_run_is_refused(implementation, configuration, message):
    with pytest.raises(UnknownTargetError, match=message):
        resolve_target(implementation, configuration)


def test_each_committed_recording_belongs_to_a_registered_target():
    recorded = {(t.implementation, t.configuration) for t in recorded_targets()}
    assert recorded == {
        (TWO_PASS, "extraction-openrouter-default"),
        (FIND_THEN_TYPE, "extraction-find-then-type"),
    }
    two_pass, find_then_type = (
        cassette_path(DOCUMENT, resolve_target(TWO_PASS)),
        cassette_path(DOCUMENT),
    )
    assert two_pass.parent.name == "extraction_benchmark"
    assert find_then_type.parent.name == "extraction_benchmark_find_then_type"
    assert two_pass.parent.parent == find_then_type.parent.parent
    assert two_pass.exists() and find_then_type.exists()


async def test_the_run_uses_its_configurations_model_temperature_and_stage_prompts(
    ontology, monkeypatch
):
    """A prompt-only experiment is a configuration: its stage prompts are the ones sent."""
    base = resolve_target(TWO_PASS)
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    configurations.register(
        PIPELINE_TYPE,
        TWO_PASS,
        "test-configured",
        {
            **base.config,
            "model": "a-configured-model",
            "temperature": 0.3,
            "max_tokens": 1234,
            "stage_prompts": {"identify_individuals": {"system": "CONFIGURED IDENTIFY PROMPT"}},
        },
    )
    monkeypatch.setattr(
        "scripts.benchmark_replay.pipeline_registries", lambda: (implementations, configurations)
    )
    configured = resolve_target(TWO_PASS, "test-configured")
    provider = StubProvider("Wikimedia Foundation", ACTOR)
    await extract_document(ontology, provider, DOCUMENT, configured)

    assert provider.calls
    assert {model for _, model, _ in provider.calls} == {"a-configured-model"}
    assert {temperature for _, _, temperature in provider.calls} == {0.3}
    assert set(provider.limits) == {1234}, "the configuration's output-token limit reaches the call"
    assert "CONFIGURED IDENTIFY PROMPT" in {system for system, _, _ in provider.calls}

    plain = StubProvider("Wikimedia Foundation", ACTOR)
    await extract_document(ontology, plain, DOCUMENT, base)
    assert {model for _, model, _ in plain.calls} == {base.model}
    assert {temperature for _, _, temperature in plain.calls} == {base.temperature}
    assert "CONFIGURED IDENTIFY PROMPT" not in {system for system, _, _ in plain.calls}


def test_a_summary_says_what_was_run():
    target = resolve_target(FIND_THEN_TYPE)
    summary = summarize([DocumentResult("edit_check", "not_recorded")], target)
    assert summary["implementation"] == FIND_THEN_TYPE
    assert summary["configuration"] == target.configuration
    assert summary["model"] == target.model
    assert "implementation" not in summarize([])


# -- the committed recordings still answer today's prompts --------------------

# Split means of the committed recordings that the accept gate reads (dev
# typed F1 and found F1, holdout typed F1): what experiments/README.md and the
# ledger's 2026-11-14 baseline_reset entry state.
COMMITTED_SCORES = {
    TWO_PASS: {"dev": {"typed_f1": 0.1138, "f1": 0.4112}, "holdout": {"typed_f1": 0.156}},
    FIND_THEN_TYPE: {"dev": {"typed_f1": 0.4648, "f1": 0.5343}, "holdout": {"typed_f1": 0.4813}},
}
_REPLAYED: dict[tuple[str, str], DocumentResult] = {}


async def replayed(implementation: str, document: str) -> DocumentResult:
    """A committed recording's replay, made once for the tests below."""
    key = (implementation, document)
    if key not in _REPLAYED:
        _REPLAYED[key] = await replay_document(document, resolve_target(implementation))
    return _REPLAYED[key]


@pytest.mark.parametrize("document", ALL_DOCUMENTS)
async def test_default_recordings_replay(ontology, document):
    """
    The recorded runs of the two-pass implementation (id `default`) answer today's prompts
    with the model of the configuration they were recorded with. A change to
    the two-pass prompts, to what feeds them, or to that configuration's model
    fails here until they are recorded again
    (`python scripts/benchmark_replay.py --record --spend --implementation default`).
    """
    result = await replayed(TWO_PASS, document)

    assert result.status == "scored", result
    assert result.misses == 0
    assert result.calls > 0
    assert result.score.metrics["recall"] > 0


@pytest.mark.parametrize("document", ALL_DOCUMENTS)
async def test_find_then_type_recordings_replay_and_keep_their_gain(ontology, document):
    """
    The recorded find-then-type runs answer today's prompts, and score well
    above the two-pass baseline's typed F1 (0.07 to 0.16 on these documents).
    """
    result = await replayed(FIND_THEN_TYPE, document)

    assert result.status == "scored", result
    assert result.misses == 0
    assert result.score.metrics["typed_f1"] > 0.3
    assert result.score.metrics["type_accuracy"] > 0.6


@pytest.mark.parametrize("implementation", sorted(COMMITTED_SCORES))
async def test_committed_recordings_score_what_the_baselines_state(ontology, implementation):
    """
    A change that leaves every prompt as it was (merging, planning,
    recognition, scoring) replays without a stale cassette and can still move
    the scores. This pins them.
    """
    target = resolve_target(implementation)
    results = [await replayed(implementation, document) for document in ALL_DOCUMENTS]
    summary = summarize(results, target)

    assert summary["status"] == "scored", summary["documents"]
    assert summary["recorded_models"] == [target.model]
    for split, measures in COMMITTED_SCORES[implementation].items():
        for measure, committed in measures.items():
            assert summary[split][measure] == pytest.approx(committed, abs=0.0005), (
                f"{split} {measure} of {implementation} with {target.configuration} is "
                f"{summary[split][measure]}, and the committed baseline says {committed}. Nothing "
                "was recorded again, so a change to code after the LLM calls moved the score. If "
                "that is intended, update COMMITTED_SCORES here, the tables in "
                "experiments/README.md and documentation/karpathy_loop_design.md, and record the "
                "new baseline in the ledger (experiments/ledger.py baseline-reset)."
            )


# -- the command line -------------------------------------------------------


def _fake_replays(statuses: dict[str, str] | None = None):
    """A replay_all that scores every document, unless told otherwise per implementation."""
    seen: list[tuple[str, str, tuple[str, ...]]] = []

    async def replay_all(documents=None, target=None):
        seen.append((target.implementation, target.configuration, tuple(documents)))
        status = (statuses or {}).get(target.implementation, "scored")
        if status == "scored":
            return [
                DocumentResult(d, "scored", score(load_gold(d), []), calls=1) for d in documents
            ]
        return [DocumentResult(d, status, calls=3, misses=3) for d in documents]

    return replay_all, seen


def _run_main(monkeypatch, argv: list[str], statuses: dict[str, str] | None = None):
    replay_all, seen = _fake_replays(statuses)
    monkeypatch.setattr(benchmark_replay, "replay_all", replay_all)
    monkeypatch.setattr(sys, "argv", ["benchmark_replay.py", *argv])
    return benchmark_replay.main(), seen


def test_main_with_no_flags_replays_the_registrys_default_target(monkeypatch, capsys):
    exit_code, seen = _run_main(monkeypatch, [])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert seen == [(FIND_THEN_TYPE, "extraction-find-then-type", tuple(benchmark_documents()))]
    assert "target: implementation find_then_type, configuration extraction-find-then-type" in out
    assert "status: scored" in out
    assert "dev typed F1 0.000, found F1 0.000" in out


def test_main_runs_the_target_its_flags_name(monkeypatch, capsys):
    argv = ["--implementation", FIND_THEN_TYPE, "--configuration", "extraction-find-then-type"]
    exit_code, seen = _run_main(monkeypatch, argv)

    assert exit_code == 0
    assert [(i, c) for i, c, _ in seen] == [(FIND_THEN_TYPE, "extraction-find-then-type")]
    assert "cassettes: extraction_benchmark_find_then_type/" in capsys.readouterr().out

    _, seen = _run_main(monkeypatch, ["--implementation", TWO_PASS])
    assert [(i, c) for i, c, _ in seen] == [(TWO_PASS, "extraction-openrouter-default")]
    _, seen = _run_main(
        monkeypatch, ["--implementation", TWO_PASS, "--configuration", "extraction-default"]
    )
    assert [(i, c) for i, c, _ in seen] == [(TWO_PASS, "extraction-default")]


@pytest.mark.parametrize("status", ["stale", "not_recorded", "failed"])
def test_main_exits_non_zero_when_the_target_was_not_scored(monkeypatch, capsys, status):
    exit_code, _ = _run_main(monkeypatch, [], {FIND_THEN_TYPE: status})
    assert exit_code == 2
    assert f"status: {status}" in capsys.readouterr().out


def test_main_over_some_documents_is_partial_and_exits_zero(monkeypatch, capsys):
    exit_code, seen = _run_main(monkeypatch, ["--document", "edit_check"])
    assert exit_code == 0
    assert seen[0][2] == ("edit_check",)
    assert "status: partial" in capsys.readouterr().out


def test_main_json_puts_only_the_json_on_standard_output(monkeypatch, capsys):
    exit_code, _ = _run_main(monkeypatch, ["--json", "--implementation", FIND_THEN_TYPE])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert exit_code == 0
    assert summary["implementation"] == FIND_THEN_TYPE
    assert summary["configuration"] == "extraction-find-then-type"
    assert summary["status"] == "scored"
    assert "target: implementation find_then_type" in captured.err
    assert "edit_check" in captured.err


def test_main_all_replays_every_recorded_target(monkeypatch, capsys):
    exit_code, seen = _run_main(monkeypatch, ["--all", "--json"])
    captured = capsys.readouterr()
    targets = json.loads(captured.out)["targets"]

    assert exit_code == 0
    # In registration order: find_then_type, the type's default, first
    assert [(i, c) for i, c, _ in seen] == [
        (FIND_THEN_TYPE, "extraction-find-then-type"),
        (TWO_PASS, "extraction-openrouter-default"),
    ]
    assert [(t["implementation"], t["status"]) for t in targets] == [
        (FIND_THEN_TYPE, "scored"),
        (TWO_PASS, "scored"),
    ]
    assert captured.err.count("target: implementation") == 2


def test_main_all_exits_non_zero_when_any_target_is_not_scored(monkeypatch, capsys):
    exit_code, _ = _run_main(monkeypatch, ["--all"], {TWO_PASS: "stale"})
    out = capsys.readouterr().out

    assert exit_code == 2
    assert "status: stale" in out and "status: scored" in out


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--implementation", "no_such"], "no implementation 'no_such'"),
        (["--implementation", "open_v1"], "the benchmark cannot run it"),
        (["--implementation", FIND_THEN_TYPE, "--configuration", "extraction-default"], "no conf"),
        (["--all", "--implementation", TWO_PASS], "--all replays every recorded target"),
        (["--all", "--record", "--spend"], "--all replays every recorded target"),
        (["--record"], "pass --spend"),
        # On replay the flag did nothing; with --record it overwrote the committed cassette
        (["--model", "another-model"], "--model is not taken"),
        (["--record", "--spend", "--model", "another-model"], "--model is not taken"),
    ],
)
def test_main_refuses_what_it_cannot_do(monkeypatch, argv, message):
    recorded: list[str] = []

    async def record_document(document_id, target):
        recorded.append(document_id)

    monkeypatch.setattr(benchmark_replay, "record_document", record_document)
    with pytest.raises(SystemExit) as raised:
        _run_main(monkeypatch, argv)
    assert message in str(raised.value)
    assert recorded == [], "nothing may be recorded by a refused call"


def test_main_records_each_document_of_the_target_only_with_spend(monkeypatch, capsys):
    recorded: list[tuple[str, str]] = []

    async def record_document(document_id, target):
        recorded.append((document_id, target.configuration))
        return DocumentResult(document_id, "scored", score(load_gold(document_id), []), calls=1)

    monkeypatch.setattr(benchmark_replay, "record_document", record_document)
    argv = ["--record", "--spend", "--implementation", FIND_THEN_TYPE, "--document", "edit_check"]
    exit_code, replays = _run_main(monkeypatch, argv)

    assert exit_code == 0
    assert recorded == [("edit_check", "extraction-find-then-type")]
    assert replays == [], "a recording is not replayed"
