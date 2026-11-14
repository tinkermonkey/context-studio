"""
Unit tests for FindThenTypeOrchestrator.

The shape finds each chunk's mentions, types each distinct mention of the
source once (calls side by side), relates the typed individuals of each chunk,
and hands the two-pass shape's triples to the same merge and proposer. Nothing
that failed reads as "found nothing": a failed part makes its chunk a failed
chunk, and the run fails when every find or every typing call failed, or at
once when the provider refuses the model's requests while finding or typing.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import asyncio
import re
import threading
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from domain.extraction.entities import Mention
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import ExtractionFailedError, PipelineExecutionError
from domain.pipelines.individual_extraction.find_then_type import (
    _TYPING_CONCURRENCY,
    FindThenTypeOrchestrator,
    _candidates,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState

INCOMPLETE = (
    "The LLM response for find_mentions was still incomplete after 3 attempts:"
    " it holds no complete JSON object (finish_reason=error)"
)
REFUSED = "The anthropic provider rejected its API key"
SQL = "(sqlite3.OperationalError) database is locked [SQL: SELECT * FROM ontology_entities]"

_NAME = re.compile(r"\b(?:Part\d{3}|Gateway|Skipme|Acme LLC|Acme)\b")


@dataclass
class _Result:
    """A stage's result as the service reports it."""

    mentions: list = field(default_factory=list)
    triples: list = field(default_factory=list)
    class_ref: str | None = None
    confidence: float = 0.9
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    failure_reason: str | None = None
    incomplete_response: bool = False
    provider_failed: bool = False
    provider_refused: bool = False


def _failed(how, tokens):
    spent = {"model": "m", "tokens_used": tokens, "duration_ms": 1}
    if how == "incomplete":
        return _Result(metadata=spent, failure_reason=INCOMPLETE, incomplete_response=True)
    if how == "refused":
        return _Result(
            metadata=spent, failure_reason=REFUSED, provider_failed=True, provider_refused=True
        )
    return _Result(metadata=spent, failure_reason=SQL)


class _FakeExtraction:
    """
    The five calls of the find-then-type shape over a text of 'Name xxx.'
    sentences.

    Find lists each distinct name of the text it is given, with the name as
    its passage. Type gives every name the class "app.component" (or its class
    in ``classes``), except "Skipme", which is not something to record. Relate
    states one relationship between the first two individuals it is given.
    Recognize stamps each individual with the id "known-<label>".

    ``find``, ``relate``: call number (from 1) -> "incomplete", "refused" or
    "broken", for calls that fail. ``type``: name -> the same, or "raises" for
    a call that raises.
    """

    def __init__(
        self,
        find=None,
        type=None,
        relate=None,
        recognize_error=None,
        type_delay=0.0,
        classes=None,
    ):
        self._find = find or {}
        self._type = type or {}
        self._relate = relate or {}
        self._recognize_error = recognize_error
        self._type_delay = type_delay
        self._classes = classes or {}
        self.recognized_in: list = []
        # How many typing calls had started when one was refused or raised
        self.typed_at_stop = None
        self.found: list[str] = []
        self.typed: list[str] = []
        self.related: list[str] = []
        self.prompts_built = 0
        # The output-token limit each find, type and relate call was given
        self.limits: set = set()
        self.stage_prompts: list = []
        self.type_threads: set[int] = set()
        self.in_flight = 0
        self.most_in_flight = 0
        self.first_done_before_others_start = None
        self._lock = threading.Lock()

    def find_mentions(
        self, text, ontology_id, model, temperature, stage_prompts=None, max_tokens=None
    ):
        self.found.append(text)
        self.limits.add(("find", max_tokens))
        self.stage_prompts.append(stage_prompts)
        how = self._find.get(len(self.found))
        if how:
            return _failed(how, 40)
        mentions, seen = [], set()
        for match in _NAME.finditer(text):
            if match.group() not in seen:
                seen.add(match.group())
                mentions.append(
                    Mention(match.group(), "thing", match.group(), match.start(), match.end())
                )
        return _Result(
            mentions=mentions,
            warnings=["a find warning"],
            metadata={"model": model, "tokens_used": 100, "duration_ms": 5},
        )

    def typing_prompt(self, ontology_id, stage_prompts=None):
        self.prompts_built += 1
        self.stage_prompts.append(stage_prompts)
        return SimpleNamespace(system="the catalog")

    def type_mention(self, prompt, context, mention, model, temperature, max_tokens=None):
        with self._lock:
            if self.first_done_before_others_start is None and self.typed:
                self.first_done_before_others_start = self.in_flight == 0
            self.typed.append(mention.name)
            self.limits.add(("type", max_tokens))
            self.type_threads.add(threading.get_ident())
            self.in_flight += 1
            self.most_in_flight = max(self.most_in_flight, self.in_flight)
        try:
            if self._type_delay:
                time.sleep(self._type_delay)
            assert prompt.system == "the catalog"
            assert mention.name in context
            how = self._type.get(mention.name)
            if how in ("refused", "raises"):
                self.typed_at_stop = len(self.typed)
            if how == "raises":
                raise RuntimeError("the typing call raised")
            if how:
                return _failed(how, 7)
            spent = {"model": model, "tokens_used": 10, "duration_ms": 2}
            if mention.name == "Skipme":
                return _Result(class_ref=None, metadata=spent)
            class_ref = self._classes.get(mention.name, "app.component")
            return _Result(class_ref=class_ref, confidence=0.9, metadata=spent)
        finally:
            with self._lock:
                self.in_flight -= 1

    def relate(
        self,
        text,
        typing_triples,
        ontology_id,
        model,
        temperature,
        stage_prompts=None,
        max_tokens=None,
    ):
        self.related.append(text)
        self.limits.add(("relate", max_tokens))
        self.stage_prompts.append(stage_prompts)
        how = self._relate.get(len(self.related))
        if how:
            return _failed(how, 30)
        names = list(dict.fromkeys(t["subject"]["label"] for t in typing_triples))
        triples = []
        if len(names) >= 2:
            triples.append(
                {
                    "subject": {"kind": "individual", "id": "", "label": names[0]},
                    "predicate": {"property_definition_id": "", "label": "uses"},
                    "object": {"kind": "individual", "id": "", "label": names[1]},
                    "confidence": 0.7,
                    "provenance": {"quote": names[0], "start": 0, "end": len(names[0])},
                }
            )
        return _Result(
            triples=triples, metadata={"model": model, "tokens_used": 50, "duration_ms": 3}
        )

    def recognize(self, triples, ontology_id, dataset_id=None):
        if self._recognize_error:
            raise self._recognize_error
        self.recognized_in.append(dataset_id)
        return [
            {**t, "subject": {**t["subject"], "id": f"known-{t['subject']['label']}"}}
            for t in triples
        ]


class _StatusWriter:
    def __init__(self):
        self.progress: list = []

    def update_running_status(self, run_id, started_at):
        pass

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))


class _Proposer:
    def __init__(self):
        self.triples: list = []
        self.unread: list = []

    def propose_individuals(self, run_id, input_data, triples, unread=None):
        self.triples = list(triples)
        self.unread.append(unread)
        return SimpleNamespace(warnings=[], to_json=lambda: {"proposal_id": "prop-1"})


def _text(sentences: int, every: str | None = "Gateway") -> str:
    """
    Sentences of 60 characters, each starting with a distinct name; ``every``
    is named in each tenth sentence too, so it is in every chunk.
    """
    out = []
    for i in range(sentences):
        name = f"Part{i:03d}"
        extra = f" {every}" if every and i % 10 == 0 else ""
        out.append(name + extra + " " + "x" * (60 - len(name) - len(extra) - 2) + ".")
    return " ".join(out)


SOURCE = _text(300)  # 18299 characters -> 3 chunks


def _state(**input_data):
    return IndividualExtractionState(
        run_id="run-1",
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={"ontology_id": "onto-1", "model": "m", **input_data},
    )


def _orchestrator(extraction, writer=None, proposer=None, config=None):
    return FindThenTypeOrchestrator(
        llm_provider=None,
        extraction_service=extraction,
        run_id="run-1",
        status_writer=writer,
        proposer=proposer,
        config=config,
    )


async def _run(extraction, writer=None, proposer=None, text=SOURCE, **input_data):
    input_data = input_data or {"source_id": "src-1"}
    return await _orchestrator(extraction, writer, proposer).execute(
        _state(text=text, **input_data)
    )


def _typing_triples(triples):
    return {t["subject"]["label"]: t for t in triples if t["predicate"]["label"] == "is_a"}


class TestFindThenTypeFlow:
    async def test_the_runs_output_limit_is_every_calls(self):
        # The run's configuration sets it (PipelineSelection.run_input)
        extraction = _FakeExtraction()

        await _run(extraction, source_id="src-1", max_tokens=16000)

        assert extraction.limits == {("find", 16000), ("type", 16000), ("relate", 16000)}

    async def test_a_run_that_names_no_limit_leaves_each_stage_its_own(self):
        extraction = _FakeExtraction()

        await _run(extraction)

        assert extraction.limits == {("find", None), ("type", None), ("relate", None)}

    async def test_a_source_is_found_typed_and_related_and_merged(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()

        state = await _run(extraction, writer)

        assert state.current_status == PipelineRunStatus.COMPLETED
        assert len(extraction.found) == 3
        assert len(extraction.related) == 3
        assert extraction.prompts_built == 1
        typed = _typing_triples(state.result["triples"])
        assert len(typed) == 301  # 300 parts and the gateway
        assert {t["object"]["label"] for t in typed.values()} == {"app.component"}
        for label, triple in typed.items():
            passage = triple["passages"][0]
            assert SOURCE[passage["start"] : passage["end"]] == label  # offsets of the whole text
        relations = [t for t in state.result["triples"] if t["predicate"]["label"] == "uses"]
        assert len(relations) == 3

    async def test_a_mention_of_several_chunks_is_typed_once_and_has_one_class(self):
        extraction = _FakeExtraction()

        state = await _run(extraction)

        assert extraction.typed.count("Gateway") == 1
        assert sorted(extraction.typed) == sorted(set(extraction.typed))
        gateway = _typing_triples(state.result["triples"])["Gateway"]
        assert len(gateway["passages"]) == 3  # one passage per chunk it is mentioned in
        typings = [
            t
            for t in state.result["triples"]
            if t["predicate"]["label"] == "is_a" and t["subject"]["label"] == "Gateway"
        ]
        assert len(typings) == 1

    async def test_a_mention_that_is_not_something_to_record_is_left_out(self):
        extraction = _FakeExtraction()

        state = await _run(extraction, text=_text(300, every="Skipme"))

        assert "Skipme" in extraction.typed
        assert "Skipme" not in _typing_triples(state.result["triples"])
        assert state.result["metadata"]["mentions"] == {
            "found": 303,  # 300 parts, and Skipme once in each of the 3 chunks
            "distinct": 301,
            "typed": 300,
            "not_recorded": 1,
            "untyped": 0,
        }
        assert "failed_chunks" not in state.result

    async def test_progress_is_counted_in_chunks(self):
        writer = _StatusWriter()

        await _run(_FakeExtraction(), writer)

        assert writer.progress == [(0, 3), (1, 3), (2, 3), (3, 3)]

    async def test_the_run_s_cost_is_every_call_s(self):
        state = await _run(_FakeExtraction())

        metadata = state.result["metadata"]
        assert metadata["tokens_used"] == 3 * 100 + 301 * 10 + 3 * 50
        assert metadata["model"] == "m"
        assert metadata["source_id"] == "src-1"
        assert [c["index"] for c in metadata["chunks"]] == [0, 1, 2]
        assert all(c["failure_reason"] is None for c in metadata["chunks"])
        # A typing triple per chunk the individual is in, and the chunk's relationship
        assert sum(c["triples"] for c in metadata["chunks"]) == 300 + 3 + 3

    async def test_warnings_name_their_chunk(self):
        state = await _run(_FakeExtraction())

        assert state.result["warnings"][:3] == [
            "Chunk 1 of 3: a find warning",
            "Chunk 2 of 3: a find warning",
            "Chunk 3 of 3: a find warning",
        ]

    async def test_the_merged_triples_are_proposed_whole(self):
        proposer = _Proposer()

        state = await _run(_FakeExtraction(), proposer=proposer)

        assert proposer.unread == [None]
        assert len(proposer.triples) == len(state.result["triples"])
        assert state.result["proposal_id"] == "prop-1"

    async def test_a_configuration_s_prompts_reach_every_stage(self):
        extraction = _FakeExtraction()
        prompts = {"find_mentions": {"system": "List the parts."}}
        orchestrator = _orchestrator(extraction, config={"stage_prompts": prompts})

        await orchestrator.execute(_state(text=SOURCE, source_id="src-1"))

        # Three finds, the typing prompt and three relates
        assert extraction.stage_prompts == [prompts] * 7

    def test_its_stages_are_find_type_and_relate(self):
        assert [stage.key for stage in FindThenTypeOrchestrator.STAGE_PROMPTS] == [
            "find_mentions",
            "type_mention",
            "derive_relationships",
        ]

    def test_names_that_share_a_label_key_are_one_candidate(self):
        found = [
            [Mention("screws (D)", "thing"), Mention("Moen Inc.", "thing")],
            [Mention("Screw", "thing", "Screw", 4, 9), Mention("Moen", "statement")],
        ]

        candidates = _candidates(found)

        # A corporate suffix keeps a name apart: the classes decide, at the merge
        assert [[m.name for _, m in c.found] for c in candidates] == [
            ["screws (D)", "Screw"],
            ["Moen Inc."],
            ["Moen"],
        ]
        # Typed where its passage was placed, else where it was first found
        assert candidates[0].typed_in[1].name == "Screw"
        assert candidates[1].typed_in == (0, found[0][1])


class TestTypingRunsSideBySide:
    async def test_typing_calls_run_on_worker_threads_within_the_limit(self):
        extraction = _FakeExtraction(type_delay=0.002)

        await _run(extraction)

        assert 1 < extraction.most_in_flight <= _TYPING_CONCURRENCY
        assert threading.get_ident() not in extraction.type_threads

    async def test_the_first_typing_call_ends_before_the_others_start(self):
        """It writes the catalog to a provider's cache; the others read it."""
        extraction = _FakeExtraction(type_delay=0.002)

        await _run(extraction)

        assert extraction.first_done_before_others_start is True


class TestFailedParts:
    async def test_a_chunk_whose_find_failed_is_a_failed_chunk(self):
        extraction = _FakeExtraction(find={2: "incomplete"})
        proposer = _Proposer()

        state = await _run(extraction, proposer=proposer)

        assert state.current_status == PipelineRunStatus.COMPLETED
        note = (
            "Extraction failed for 1 of 3 chunks (chunk 2), so what they hold, or part of it,"
            f" is missing. First failure: {INCOMPLETE}"
        )
        assert state.result["warnings"][0] == note
        assert proposer.unread == [note]
        assert [c["index"] for c in state.result["failed_chunks"]] == [1]
        assert state.result["failed_chunks"][0]["failure_reason"] == INCOMPLETE
        assert state.result["metadata"]["chunks"][1]["triples"] == 0
        assert len(extraction.related) == 2  # nothing to relate in the chunk that was not read

    async def test_the_run_fails_when_every_find_failed(self):
        extraction = _FakeExtraction(find={1: "incomplete", 2: "incomplete", 3: "incomplete"})

        with pytest.raises(ExtractionFailedError) as raised:
            await _run(extraction)

        assert str(raised.value) == f"Extraction failed for every chunk (3): {INCOMPLETE}"
        assert raised.value.llm_metadata == {"model": "m", "tokens_used": 120, "duration_ms": 3}
        assert extraction.typed == []

    async def test_a_reason_not_written_for_the_caller_is_not_shown(self):
        extraction = _FakeExtraction(find={1: "broken"})
        proposer = _Proposer()

        state = await _run(extraction, proposer=proposer)

        assert proposer.unread[0].endswith(
            "First failure: an internal error, recorded in failed_chunks of run run-1"
        )
        assert state.result["failed_chunks"][0]["failure_reason"] == SQL

    async def test_every_find_failing_for_another_reason_hides_the_reason(self):
        extraction = _FakeExtraction(find={1: "broken", 2: "incomplete", 3: "incomplete"})

        with pytest.raises(PipelineExecutionError) as raised:
            await _run(extraction)

        assert not isinstance(raised.value, ExtractionFailedError)

    async def test_a_mention_that_could_not_be_typed_fails_the_chunk_it_was_typed_in(self):
        extraction = _FakeExtraction(type={"Part150": "incomplete"})
        proposer = _Proposer()

        state = await _run(extraction, proposer=proposer)

        assert "Part150" not in _typing_triples(state.result["triples"])
        assert state.result["metadata"]["mentions"]["untyped"] == 1
        failed = state.result["failed_chunks"]
        assert len(failed) == 1
        reason = failed[0]["failure_reason"]
        assert re.fullmatch(
            rf"1 of its \d+ mentions could not be typed \(Part150\): {re.escape(INCOMPLETE)}",
            reason,
        )
        assert proposer.unread[0].endswith(f"First failure: {reason}")
        assert len(_typing_triples(state.result["triples"])) == 300

    async def test_the_run_fails_when_every_typing_call_failed(self):
        text = _text(3, every=None)
        extraction = _FakeExtraction(
            type={"Part000": "incomplete", "Part001": "incomplete", "Part002": "incomplete"}
        )

        with pytest.raises(ExtractionFailedError) as raised:
            await _run(extraction, text=text)

        assert str(raised.value) == f"Typing failed for every one of the 3 mentions: {INCOMPLETE}"
        assert raised.value.llm_metadata["tokens_used"] == 100 + 3 * 7

    async def test_relationships_that_could_not_be_read_keep_the_chunk_s_individuals(self):
        extraction = _FakeExtraction(relate={2: "incomplete"})
        proposer = _Proposer()

        state = await _run(extraction, proposer=proposer)

        assert len(_typing_triples(state.result["triples"])) == 301
        assert [t["predicate"]["label"] for t in state.result["triples"]].count("uses") == 2
        failed = state.result["failed_chunks"]
        assert [c["index"] for c in failed] == [1]
        assert failed[0]["failure_reason"] == (f"Its relationships could not be read: {INCOMPLETE}")
        assert failed[0]["triples"] > 0
        assert proposer.unread[0].startswith("Extraction failed for 1 of 3 chunks (chunk 2)")

    async def test_every_part_that_failed_in_a_chunk_is_in_its_reason(self):
        extraction = _FakeExtraction(type={"Part000": "incomplete"}, relate={1: "incomplete"})

        state = await _run(extraction)

        reason = state.result["failed_chunks"][0]["failure_reason"]
        assert "mentions could not be typed (Part000)" in reason
        assert reason.endswith(f"; Its relationships could not be read: {INCOMPLETE}")

    async def test_a_mention_of_several_chunks_that_could_not_be_typed_fails_one_chunk(self):
        extraction = _FakeExtraction(type={"Gateway": "incomplete"})

        state = await _run(extraction)

        assert "Gateway" not in _typing_triples(state.result["triples"])
        failed = state.result["failed_chunks"]
        assert [c["index"] for c in failed] == [0]  # the chunk it was typed in
        assert "mentions could not be typed (Gateway)" in failed[0]["failure_reason"]

    async def test_a_find_refused_at_the_last_chunk_fails_the_run(self):
        extraction = _FakeExtraction(find={3: "refused"})

        with pytest.raises(ExtractionFailedError) as raised:
            await _run(extraction)

        assert str(raised.value).startswith("Extraction stopped at chunk 3 of 3,")
        assert extraction.typed == []

    async def test_after_a_refused_relate_a_chunk_with_nothing_to_relate_is_not_failed(self):
        # Two chunks of parts, then one that names the gateway only
        filler = "y" * 58 + "."
        text = " ".join([_text(200, every=None)] + [filler] * 95 + ["Gateway"] + [filler] * 5)
        extraction = _FakeExtraction(relate={1: "refused"})

        state = await _run(extraction, text=text)

        assert len(extraction.found) == 3
        assert "Gateway" in _typing_triples(state.result["triples"])
        assert [c["index"] for c in state.result["failed_chunks"]] == [0, 1]

    async def test_a_run_whose_every_relate_failed_completes_with_its_individuals(self):
        extraction = _FakeExtraction(relate={1: "incomplete", 2: "incomplete", 3: "incomplete"})

        state = await _run(extraction)

        assert state.current_status == PipelineRunStatus.COMPLETED
        assert len(state.result["failed_chunks"]) == 3
        assert len(_typing_triples(state.result["triples"])) == 301

    async def test_a_failure_to_recognize_fails_the_run_with_what_it_cost(self):
        extraction = _FakeExtraction(recognize_error=RuntimeError(SQL))

        with pytest.raises(PipelineExecutionError) as raised:
            await _run(extraction)

        assert str(raised.value) == "Recognizing the extracted individuals failed"
        assert raised.value.llm_metadata["tokens_used"] == 3 * 100 + 301 * 10 + 3 * 50


class TestProviderThatRefusesTheRun:
    async def test_a_refused_find_stops_the_run_there(self):
        extraction = _FakeExtraction(find={2: "refused"})

        with pytest.raises(ExtractionFailedError) as raised:
            await _run(extraction)

        assert str(raised.value) == (
            "Extraction stopped at chunk 2 of 3, because every later call would fail the same"
            f" way: {REFUSED}"
        )
        assert len(extraction.found) == 2
        assert extraction.typed == []
        assert raised.value.llm_metadata["tokens_used"] == 140

    async def test_a_refused_typing_call_stops_the_typing_and_the_run(self):
        extraction = _FakeExtraction(type={"Part000": "refused"})

        with pytest.raises(ExtractionFailedError) as raised:
            await _run(extraction)

        assert extraction.typed == ["Part000"]  # the first call is made alone
        assert extraction.related == []
        assert str(raised.value) == (
            "Extraction stopped while typing what the text mentions (1 of 301 asked), because"
            f" every later call would fail the same way: {REFUSED}"
        )
        assert raised.value.llm_metadata["tokens_used"] == 300 + 7

    async def test_a_refusal_in_the_middle_of_typing_makes_no_further_call(self):
        extraction = _FakeExtraction(type={"Part020": "refused"}, type_delay=0.001)

        with pytest.raises(ExtractionFailedError):
            await _run(extraction)

        # Only a call already let in when the refusal came back is still made
        assert len(extraction.typed) <= extraction.typed_at_stop + _TYPING_CONCURRENCY

    async def test_a_refused_relate_costs_the_later_relationships_not_what_was_typed(self):
        extraction = _FakeExtraction(relate={2: "refused"})
        proposer = _Proposer()

        state = await _run(extraction, proposer=proposer)

        assert state.current_status == PipelineRunStatus.COMPLETED
        assert len(extraction.related) == 2  # the third call is never made
        assert len(_typing_triples(state.result["triples"])) == 301
        failed = state.result["failed_chunks"]
        assert [c["index"] for c in failed] == [1, 2]
        assert {c["failure_reason"] for c in failed} == {
            f"Its relationships could not be read: {REFUSED}"
        }
        assert proposer.unread[0].startswith("Extraction failed for 2 of 3 chunks (chunks 2, 3)")


class TestPastedText:
    PASTED = _text(40)

    async def test_pasted_text_is_one_chunk_without_progress(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()

        state = await _orchestrator(extraction, writer).execute(_state(text=self.PASTED))

        assert extraction.found == [self.PASTED]
        assert writer.progress == []
        assert len(_typing_triples(state.result["triples"])) == 41
        metadata = state.result["metadata"]
        assert "chunks" not in metadata
        assert metadata["tokens_used"] == 100 + 41 * 10 + 50
        assert metadata["mentions"]["typed"] == 41
        assert "failed_chunks" not in state.result

    @pytest.mark.parametrize(
        "failing, reason",
        [
            ({"find": {1: "incomplete"}}, INCOMPLETE),
            (
                {"type": {"Part007": "incomplete"}},
                f"1 of its 41 mentions could not be typed (Part007): {INCOMPLETE}",
            ),
            ({"relate": {1: "incomplete"}}, f"Its relationships could not be read: {INCOMPLETE}"),
        ],
    )
    async def test_a_part_that_failed_fails_the_run(self, failing, reason):
        extraction = _FakeExtraction(**failing)

        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(_state(text=self.PASTED))

        assert str(raised.value) == f"Extraction failed: {reason}"
        assert raised.value.llm_metadata["tokens_used"] > 0

    @pytest.mark.parametrize(
        "failing, message",
        [
            ({"find": {1: "refused"}}, f"Extraction failed: {REFUSED}"),
            (
                {"type": {"Part000": "refused"}},
                "Extraction stopped while typing what the text mentions (1 of 41 asked),"
                f" because every later call would fail the same way: {REFUSED}",
            ),
            (
                {"relate": {1: "refused"}},
                f"Extraction failed: Its relationships could not be read: {REFUSED}",
            ),
        ],
    )
    async def test_a_refused_part_fails_the_run_without_speaking_of_chunks(self, failing, message):
        extraction = _FakeExtraction(**failing)

        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(_state(text=self.PASTED))

        assert str(raised.value) == message
        assert raised.value.llm_metadata["tokens_used"] > 0

    async def test_its_warnings_and_metadata_do_not_speak_of_chunks(self):
        state = await _orchestrator(_FakeExtraction()).execute(_state(text=self.PASTED))

        assert state.result["warnings"] == ["a find warning"]
        assert not {"chunks", "source_id", "pages"} & set(state.result["metadata"])


class TestCorporateSuffix:
    TEXT = "Acme sells parts. Acme LLC owns the brand. Part001 is one of them."

    async def test_a_name_and_its_corporate_form_are_typed_apart(self):
        extraction = _FakeExtraction(
            classes={"Acme": "product.product", "Acme LLC": "business.business"}
        )

        state = await _orchestrator(extraction).execute(_state(text=self.TEXT))

        assert sorted(extraction.typed) == ["Acme", "Acme LLC", "Part001"]
        typed = _typing_triples(state.result["triples"])
        assert typed["Acme"]["object"]["label"] == "product.product"
        assert typed["Acme LLC"]["object"]["label"] == "business.business"

    async def test_the_two_forms_with_one_class_are_one_individual(self):
        extraction = _FakeExtraction(
            classes={"Acme": "business.business", "Acme LLC": "business.business"}
        )

        state = await _orchestrator(extraction).execute(_state(text=self.TEXT))

        typed = _typing_triples(state.result["triples"])
        assert sorted(typed) == ["Acme", "Part001"]
        assert len(typed["Acme"]["passages"]) == 2


class TestRecognitionAndPages:
    async def test_the_recognized_triples_are_the_ones_merged(self):
        extraction = _FakeExtraction()

        state = await _run(extraction, source_id="src-1", dataset_id="ds-1")

        assert extraction.recognized_in == ["ds-1"]  # once, over every chunk's triples
        typed = _typing_triples(state.result["triples"])
        assert typed["Gateway"]["subject"]["id"] == "known-Gateway"
        assert all(t["subject"]["id"] == f"known-{label}" for label, t in typed.items())

    async def test_passages_carry_the_page_they_are_on(self):
        state = await _run(_FakeExtraction(), source_id="src-1", page_starts=[0, 9000])

        typed = _typing_triples(state.result["triples"])
        assert typed["Part000"]["passages"][0]["page"] == 1
        assert typed["Part299"]["passages"][0]["page"] == 2


class TestStoppingTheTyping:
    async def test_a_typing_call_that_raises_fails_the_run_and_makes_no_further_call(self):
        extraction = _FakeExtraction(type={"Part020": "raises"}, type_delay=0.001)

        with pytest.raises(PipelineExecutionError) as raised:
            await _run(extraction)

        assert str(raised.value) == "Typing what the text mentions failed"
        assert raised.value.llm_metadata["tokens_used"] >= 300  # the finds, at least
        made = len(extraction.typed)
        assert made <= extraction.typed_at_stop + _TYPING_CONCURRENCY
        await asyncio.sleep(0.05)
        assert len(extraction.typed) == made
        assert extraction.related == []

    async def test_a_cancelled_run_makes_no_further_typing_call(self):
        extraction = _FakeExtraction(type_delay=0.005)
        run = asyncio.ensure_future(_run(extraction))
        while len(extraction.typed) < 10:
            await asyncio.sleep(0.001)

        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run

        made = len(extraction.typed)
        assert made < 301
        await asyncio.sleep(0.05)
        assert len(extraction.typed) == made
        assert extraction.related == []
