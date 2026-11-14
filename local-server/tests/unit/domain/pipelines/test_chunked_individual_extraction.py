"""
Unit tests for chunked individual extraction (#1552).

A source (input with source_id, page_starts, headings or pages) is extracted
chunk by chunk: offsets map back to the whole text, the same triple found in
several chunks merges with every passage, progress is reported per chunk and a
cancelled run stops before its next chunk. Pasted text is extracted in one call.
An extraction that fails is never read as "found nothing": it fails the run
(pasted text, or every chunk of a source) or is reported in failed_chunks. A
failure every later chunk would meet too (the provider refuses the run's
requests) stops the run there. A failed run says what its model calls cost.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from domain.extraction.chunking import Chunk
from domain.extraction.exceptions import InvalidInputError
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import (
    ExtractionFailedError,
    PipelineExecutionError,
    PipelineInputError,
)
from domain.pipelines.individual_extraction.chunk_merge import merge_chunk_triples
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)


def _typing(label, class_label="Appliance", quote=None, start=None, confidence=0.8, near=None):
    triple = {
        "subject": {"kind": "individual", "id": "", "label": label},
        "predicate": {"property_definition_id": "", "label": "is_a"},
        "object": {"kind": "class", "id": "", "label": class_label},
        "confidence": confidence,
        "provenance": {
            "quote": quote,
            "start": start,
            "end": start + len(quote) if start is not None and quote else None,
        },
    }
    if near is not None:
        triple["near_matches"] = near
    return triple


def _relation(subject, predicate, obj, quote, start):
    return {
        "subject": {"kind": "individual", "id": "", "label": subject},
        "predicate": {"property_definition_id": "", "label": predicate},
        "object": {"kind": "individual", "id": "", "label": obj},
        "confidence": 0.7,
        "provenance": {"quote": quote, "start": start, "end": start + len(quote)},
    }


class TestMergeChunkTriples:
    def test_offsets_map_to_the_whole_text_and_pages(self):
        chunk = Chunk(index=1, start=1000, end=2000, page_first=3, page_last=4)
        merged = merge_chunk_triples(
            [(chunk, [_typing("Ice maker", quote="ice maker", start=10)])],
            page_starts=[0, 400, 800, 1500],
        )
        assert merged[0]["provenance"] == {"quote": "ice maker", "start": 1010, "end": 1019}
        assert merged[0]["passages"] == [
            {"quote": "ice maker", "start": 1010, "end": 1019, "page": 3}
        ]

    def test_without_page_starts_passages_have_no_page(self):
        chunk = Chunk(index=0, start=0, end=100)
        merged = merge_chunk_triples([(chunk, [_typing("Ice maker", quote="ice", start=4)])])
        assert merged[0]["passages"][0]["page"] is None

    def test_same_individual_in_several_chunks_merges_with_every_passage(self):
        first = Chunk(index=0, start=0, end=500, page_first=1, page_last=1)
        second = Chunk(index=1, start=501, end=1000, page_first=2, page_last=2)
        merged = merge_chunk_triples(
            [
                (
                    first,
                    [
                        _typing("Ice maker", quote="ice maker", start=5, confidence=0.6),
                        _typing("Water filter", quote="filter", start=40),
                    ],
                ),
                (second, [_typing("ice maker ", quote="Ice maker", start=7, confidence=0.9)]),
            ],
            page_starts=[0, 501],
        )
        assert [t["subject"]["label"] for t in merged] == ["Ice maker", "Water filter"]
        ice = merged[0]
        assert ice["confidence"] == 0.9
        assert ice["passages"] == [
            {"quote": "ice maker", "start": 5, "end": 14, "page": 1},
            {"quote": "Ice maker", "start": 508, "end": 517, "page": 2},
        ]
        assert ice["provenance"] == {"quote": "ice maker", "start": 5, "end": 14}

    def test_same_label_of_another_class_stays_separate(self):
        chunk = Chunk(index=0, start=0, end=100)
        merged = merge_chunk_triples(
            [
                (chunk, [_typing("Filter", "Part", "Filter", 0)]),
                (chunk, [_typing("Filter", "Procedure", "Filter", 0)]),
            ]
        )
        assert len(merged) == 2

    def test_duplicate_relationships_merge(self):
        first = Chunk(index=0, start=0, end=100)
        second = Chunk(index=1, start=100, end=200)
        merged = merge_chunk_triples(
            [
                (first, [_relation("Ice maker", "part of", "Freezer", "in the freezer", 3)]),
                (second, [_relation("Ice Maker", "part of", "freezer", "the freezer", 0)]),
            ]
        )
        assert len(merged) == 1
        assert [p["start"] for p in merged[0]["passages"]] == [3, 100]

    def test_unplaced_quote_keeps_null_offsets_and_the_chunk_page(self):
        one_page = Chunk(index=0, start=0, end=100, page_first=2, page_last=2)
        two_pages = Chunk(index=1, start=100, end=300, page_first=2, page_last=3)
        merged = merge_chunk_triples(
            [
                (one_page, [_typing("Door", quote="the door", start=None)]),
                (two_pages, [_typing("Shelf", quote="a shelf", start=None)]),
            ],
            page_starts=[0, 50, 200],
        )
        assert merged[0]["provenance"] == {"quote": "the door", "start": None, "end": None}
        assert merged[0]["passages"] == [
            {"quote": "the door", "start": None, "end": None, "page": 2}
        ]
        assert merged[1]["passages"][0]["page"] is None

    def test_triple_without_a_quote_has_no_passage(self):
        chunk = Chunk(index=0, start=50, end=100)
        merged = merge_chunk_triples([(chunk, [_typing("Door")])])
        assert merged[0]["passages"] == []
        assert merged[0]["provenance"] == {"quote": None, "start": None, "end": None}

    def test_near_matches_union_keeps_the_best_similarity(self):
        chunk = Chunk(index=0, start=0, end=100)
        merged = merge_chunk_triples(
            [
                (
                    chunk,
                    [
                        _typing(
                            "Ice maker",
                            near=[{"entity_id": "a", "label": "Icemaker", "similarity": 0.84}],
                        )
                    ],
                ),
                (chunk, [_typing("Ice maker")]),
                (
                    chunk,
                    [
                        _typing(
                            "Ice maker",
                            near=[
                                {"entity_id": "b", "label": "Ice bin", "similarity": 0.86},
                                {"entity_id": "a", "label": "Icemaker", "similarity": 0.88},
                            ],
                        )
                    ],
                ),
            ]
        )
        assert merged[0]["near_matches"] == [
            {"entity_id": "a", "label": "Icemaker", "similarity": 0.88},
            {"entity_id": "b", "label": "Ice bin", "similarity": 0.86},
        ]

    def test_merged_triple_takes_an_id_found_in_a_later_chunk(self):
        chunk = Chunk(index=0, start=0, end=100)
        later = _relation("Ice maker", "part of", "Freezer", "freezer", 0)
        later["subject"]["id"] = "ice-id"
        later["object"]["id"] = "freezer-id"
        first = _relation("Ice maker", "part of", "Freezer", "the freezer", 10)
        first["object"]["id"] = "kept-id"
        merged = merge_chunk_triples([(chunk, [first]), (chunk, [later])])
        assert merged[0]["subject"]["id"] == "ice-id"
        assert merged[0]["object"]["id"] == "kept-id"

    def test_provenance_is_the_first_placed_passage(self):
        first = Chunk(index=0, start=0, end=100, page_first=1, page_last=1)
        second = Chunk(index=1, start=100, end=200, page_first=2, page_last=2)
        merged = merge_chunk_triples(
            [
                (first, [_typing("Door", quote="a door", start=None)]),
                (second, [_typing("Door", quote="door", start=5)]),
            ],
            page_starts=[0, 100],
        )
        assert merged[0]["provenance"] == {"quote": "door", "start": 105, "end": 109}
        assert merged[0]["passages"][0]["start"] is None  # passages keep their order

    def test_repeated_page_starts_keep_page_numbers(self):
        chunk = Chunk(index=0, start=0, end=34)
        merged = merge_chunk_triples(
            [(chunk, [_typing("Drawer", quote="Drawer", start=21)])],
            page_starts=[0, 10, 21, 21],
        )
        assert merged[0]["passages"][0]["page"] == 4

    def test_input_triples_are_not_modified(self):
        chunk = Chunk(index=0, start=100, end=200)
        triple = _typing("Door", quote="door", start=1)
        merge_chunk_triples([(chunk, [triple])])
        assert triple["provenance"]["start"] == 1
        assert "passages" not in triple


@dataclass
class _Result:
    triples: list
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    failure_reason: str | None = None
    incomplete_response: bool = False
    provider_failed: bool = False
    provider_refused: bool = False


INCOMPLETE = (
    "The LLM response for identify_individuals was still incomplete after 3 attempts:"
    " it holds no complete JSON object (finish_reason=error)"
)


SQL = "(sqlite3.OperationalError) database is locked [SQL: SELECT * FROM ontology_entities]"

REFUSED = "OpenRouter API key is invalid or unauthorized"

UNANSWERED = (
    "The LLM request for identify_individuals still failed after 3 attempts:"
    " OpenRouter API error: 503"
)


class _FakeExtraction:
    """
    Extracts one typing triple per 'Name.' sentence of the text it is given.
    The calls numbered in ``failing`` (from 1) fail instead, as the service
    reports an LLM response that stayed incomplete; those in ``broken`` fail
    for another reason; those in ``refused`` fail as the service reports a
    provider that refuses the model's requests; those in ``unanswered`` fail
    as it reports a provider that did not answer within the attempts.
    """

    def __init__(self, on_call=None, failing=(), finds=True, broken=(), refused=(), unanswered=()):
        self.calls: list[str] = []
        self._on_call = on_call
        self._failing = set(failing)
        self._broken = set(broken)
        self._refused = set(refused)
        self._unanswered = set(unanswered)
        self._finds = finds

    def extract_triples(
        self, text, ontology_id, model, temperature, stage_prompts=None, dataset_id=None
    ):
        self.calls.append(text)
        if self._on_call:
            self._on_call(len(self.calls))
        if len(self.calls) in self._failing:
            return _Result(
                triples=[],
                warnings=[f"Extraction failed: {INCOMPLETE}"],
                metadata={"model": model, "tokens_used": 45, "duration_ms": 5},
                failure_reason=INCOMPLETE,
                incomplete_response=True,
            )
        if len(self.calls) in self._refused:
            return _Result(
                triples=[],
                warnings=[f"Extraction failed: {REFUSED}"],
                metadata={"model": model, "tokens_used": 0, "duration_ms": 2},
                failure_reason=REFUSED,
                provider_failed=True,
                provider_refused=True,
            )
        if len(self.calls) in self._unanswered:
            return _Result(
                triples=[],
                warnings=[f"Extraction failed: {UNANSWERED}"],
                metadata={"model": model, "tokens_used": 0, "duration_ms": 3000},
                failure_reason=UNANSWERED,
                provider_failed=True,
            )
        if len(self.calls) in self._broken:
            return _Result(triples=[], warnings=[f"Extraction failed: {SQL}"], failure_reason=SQL)
        triples = []
        for sentence in text.split(". "):
            name = sentence.strip().rstrip(".").split(" ")[0]
            if name and self._finds:
                triples.append(_typing(name, quote=name, start=text.index(name)))
        return _Result(
            triples=triples,
            warnings=[f"saw {len(triples)}"],
            metadata={"model": model, "tokens_used": 10, "duration_ms": 5},
        )


class _StatusWriter:
    def __init__(self):
        self.progress: list[tuple[int, int | None]] = []
        self.stages: list[tuple[str, int, int]] = []

    def update_running_status(self, run_id, started_at):
        pass

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))

    def update_stage(self, run_id, stage, stage_done, stage_total):
        self.stages.append((stage, stage_done, stage_total))


def _state(**input_data):
    return IndividualExtractionState(
        run_id="run-1",
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={"ontology_id": "onto-1", "model": "m", **input_data},
    )


def _long_text(sentences: int) -> str:
    """Sentences of 60 characters, each starting with a distinct name."""
    names = [f"Part{i:03d}" for i in range(sentences)]
    return " ".join(n + " " + "x" * (60 - len(n) - 2) + "." for n in names)


def _orchestrator(extraction, writer=None, proposer=None):
    return IndividualExtractionOrchestrator(
        llm_provider=None,
        extraction_service=extraction,
        run_id="run-1",
        status_writer=writer,
        proposer=proposer,
    )


class _RecordingProposer:
    """Records what the run proposes and what it says it could not read."""

    def __init__(self):
        self.triples: list = []
        self.unread: list = []

    def propose_individuals(self, run_id, input_data, triples, unread=None):
        self.triples = list(triples)
        self.unread.append(unread)
        return SimpleNamespace(warnings=[], to_json=lambda: {"proposal_id": "prop-1"})


class _UnknownOntology:
    def extract_triples(self, text, ontology_id, **_):
        raise InvalidInputError(f"Ontology {ontology_id} not found")


class TestFailedExtraction:
    async def test_pasted_text_whose_extraction_fails_fails_the_run(self):
        extraction = _FakeExtraction(failing={1})
        with pytest.raises(ExtractionFailedError, match="Extraction failed: The LLM response"):
            await _orchestrator(extraction).execute(_state(text="Door one. Shelf two."))

    @pytest.mark.parametrize(
        "source, broken",
        [({}, {1}), ({"source_id": "src-1"}, {2}), ({"source_id": "s"}, {1, 2, 3})],
    )
    async def test_a_failure_that_is_not_an_incomplete_response_is_not_told_to_the_caller(
        self, source, broken
    ):
        # Its reason may quote an internal error, so the run fails with the plain
        # execution error (whose message the route withholds), never the caller-facing one
        failing = {1, 2, 3} - broken
        extraction = _FakeExtraction(failing=failing, broken=broken)
        with pytest.raises(PipelineExecutionError) as raised:
            await _orchestrator(extraction).execute(_state(text=_long_text(300), **source))
        assert not isinstance(raised.value, ExtractionFailedError)

    @pytest.mark.parametrize("source", [{}, {"source_id": "src-1"}])
    async def test_an_ontology_that_does_not_exist_is_an_input_error(self, source):
        with pytest.raises(PipelineInputError, match="Ontology onto-1 not found"):
            await _orchestrator(_UnknownOntology()).execute(
                _state(text="Door one. Shelf two.", **source)
            )

    async def test_a_failed_chunk_is_reported_and_the_other_chunks_are_kept(self):
        extraction = _FakeExtraction(failing={2})
        writer = _StatusWriter()
        proposer = _RecordingProposer()
        text = _long_text(300)  # 3 chunks

        state = await _orchestrator(extraction, writer, proposer).execute(
            _state(text=text, source_id="src-1")
        )

        assert state.current_status == PipelineRunStatus.COMPLETED
        assert writer.progress == [(0, 3), (1, 3), (2, 3), (3, 3)]
        result = state.result
        chunks = result["metadata"]["chunks"]
        assert [c["failure_reason"] for c in chunks] == [None, INCOMPLETE, None]
        assert result["failed_chunks"] == [chunks[1]]
        assert len(result["triples"]) == chunks[0]["triples"] + chunks[2]["triples"] > 0
        note = result["warnings"][0]
        assert note.startswith("Extraction failed for 1 of 3 chunks (chunk 2), so what")
        assert note.endswith(f"First failure: {INCOMPLETE}")
        assert f"Chunk 2 of 3: Extraction failed: {INCOMPLETE}" in result["warnings"]
        # The proposal is made from what was read, and its rationale says what wasn't
        assert proposer.triples == result["triples"]
        assert proposer.unread == [note]
        assert result["proposal_id"] == "prop-1"

    async def test_an_internal_error_is_not_quoted_in_the_note_or_the_proposal(self):
        # Chunk 2 fails on a database error, chunk 3 on an incomplete response
        extraction = _FakeExtraction(failing={3}, broken={2})
        proposer = _RecordingProposer()

        state = await _orchestrator(extraction, proposer=proposer).execute(
            _state(text=_long_text(300), source_id="src-1")
        )

        result = state.result
        note = result["warnings"][0]
        assert note == (
            "Extraction failed for 2 of 3 chunks (chunks 2, 3), so what they hold is missing."
            " First failure: an internal error, recorded in failed_chunks of run run-1"
        )
        assert proposer.unread == [note]
        # The run's own record keeps the full reasons
        assert [c["failure_reason"] for c in result["failed_chunks"]] == [SQL, INCOMPLETE]

    async def test_a_run_with_no_failed_chunk_reports_none(self):
        proposer = _RecordingProposer()
        state = await _orchestrator(_FakeExtraction(), proposer=proposer).execute(
            _state(text=_long_text(300), source_id="src-1")
        )
        assert "failed_chunks" not in state.result
        assert proposer.unread == [None]

    async def test_a_source_whose_every_chunk_fails_fails_the_run(self):
        extraction = _FakeExtraction(failing={1, 2, 3})
        proposer = _RecordingProposer()
        with pytest.raises(ExtractionFailedError, match=r"every chunk \(3\): The LLM response"):
            await _orchestrator(extraction, proposer=proposer).execute(
                _state(text=_long_text(300), source_id="src-1")
            )
        assert proposer.triples == []


class TestProviderThatRefusesTheRun:
    """A failure every later chunk would meet too stops the run where it is met."""

    @pytest.mark.parametrize("refused_at", [1, 2])
    async def test_a_refusal_stops_the_run_before_the_next_chunk(self, refused_at):
        extraction = _FakeExtraction(refused={refused_at})
        writer = _StatusWriter()
        proposer = _RecordingProposer()

        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction, writer, proposer).execute(
                _state(text=_long_text(300), source_id="src-1")  # 3 chunks
            )

        # No later chunk was tried
        assert len(extraction.calls) == refused_at
        assert str(raised.value) == (
            f"Extraction stopped at chunk {refused_at} of 3, leaving {3 - refused_at} untried,"
            f" because every later chunk would fail the same way: {REFUSED}"
        )
        # Nothing is proposed from a run that stopped
        assert proposer.unread == []
        assert writer.progress[-1] == (refused_at - 1, 3)

    async def test_a_refusal_at_the_last_chunk_keeps_what_the_others_found(self):
        # No chunk is left to spare, so it is a failed chunk like any other
        extraction = _FakeExtraction(refused={3})
        proposer = _RecordingProposer()

        state = await _orchestrator(extraction, proposer=proposer).execute(
            _state(text=_long_text(300), source_id="src-1")
        )

        assert state.current_status == PipelineRunStatus.COMPLETED
        assert [c["failure_reason"] for c in state.result["failed_chunks"]] == [REFUSED]
        # The refusal is written for the caller, so the note quotes it
        assert state.result["warnings"][0].endswith(f"First failure: {REFUSED}")
        assert proposer.unread == [state.result["warnings"][0]]

    async def test_a_source_of_one_chunk_that_is_refused_fails_as_every_chunk(self):
        extraction = _FakeExtraction(refused={1})
        with pytest.raises(ExtractionFailedError, match=rf"every chunk \(1\): {REFUSED}"):
            await _orchestrator(extraction).execute(
                _state(text="Door one. Shelf two.", source_id="src-1")
            )

    async def test_pasted_text_that_is_refused_fails_with_the_reason(self):
        extraction = _FakeExtraction(refused={1})
        with pytest.raises(ExtractionFailedError, match=f"Extraction failed: {REFUSED}"):
            await _orchestrator(extraction).execute(_state(text="Door one. Shelf two."))

    async def test_a_refusal_is_told_to_the_caller_whatever_else_its_result_says(self):
        # Another implementation of the port may mark a refusal without also
        # marking it a provider failure
        class _RefusedOnly:
            def extract_triples(self, text, ontology_id, model, temperature, **_):
                return _Result(triples=[], failure_reason=REFUSED, provider_refused=True)

        with pytest.raises(ExtractionFailedError, match=f"Extraction failed: {REFUSED}"):
            await _orchestrator(_RefusedOnly()).execute(_state(text="Door one. Shelf two."))

    async def test_a_failed_chunk_of_another_kind_does_not_stop_the_run(self):
        extraction = _FakeExtraction(failing={1}, broken={2})
        state = await _orchestrator(extraction).execute(
            _state(text=_long_text(300), source_id="src-1")
        )
        assert len(extraction.calls) == 3
        assert state.current_status == PipelineRunStatus.COMPLETED


class TestProviderThatDidNotAnswer:
    """
    A provider failure that outlasted its retries without being a refusal (a
    server error, a timeout): the caller is told the provider's reason, and the
    run goes on, since the provider may answer for the next chunk.
    """

    async def test_the_chunk_fails_with_its_reason_and_the_run_goes_on(self):
        extraction = _FakeExtraction(unanswered={1})
        proposer = _RecordingProposer()

        state = await _orchestrator(extraction, proposer=proposer).execute(
            _state(text=_long_text(400), source_id="src-1")  # 4 chunks
        )

        assert len(extraction.calls) == 4
        assert state.current_status == PipelineRunStatus.COMPLETED
        assert [c["failure_reason"] for c in state.result["failed_chunks"]] == [UNANSWERED]
        note = state.result["warnings"][0]
        assert note == (
            "Extraction failed for 1 of 4 chunks (chunk 1), so what they hold is missing."
            f" First failure: {UNANSWERED}"
        )
        assert "an internal error" not in note
        assert proposer.unread == [note]

    async def test_pasted_text_fails_with_the_reason(self):
        extraction = _FakeExtraction(unanswered={1})
        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(_state(text="Door one. Shelf two."))
        assert str(raised.value) == f"Extraction failed: {UNANSWERED}"

    async def test_every_chunk_unanswered_fails_the_run_with_the_reason(self):
        extraction = _FakeExtraction(unanswered={1, 2, 3})
        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(_state(text=_long_text(300), source_id="src-1"))
        # Every chunk was tried: none of the failures was one the next would meet
        assert len(extraction.calls) == 3
        assert str(raised.value) == f"Extraction failed for every chunk (3): {UNANSWERED}"

    async def test_an_internal_error_among_them_is_still_not_told(self):
        extraction = _FakeExtraction(unanswered={1, 3}, broken={2})
        with pytest.raises(PipelineExecutionError) as raised:
            await _orchestrator(extraction).execute(_state(text=_long_text(300), source_id="src-1"))
        assert not isinstance(raised.value, ExtractionFailedError)


class TestFailedRunRecordsWhatItCost:
    """The model calls of a failed run are on its error, which the executor records."""

    async def test_pasted_text(self):
        extraction = _FakeExtraction(failing={1})
        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(_state(text="Door one. Shelf two."))
        assert raised.value.llm_metadata == {"model": "m", "tokens_used": 45, "duration_ms": 5}

    async def test_every_chunk_failed(self):
        extraction = _FakeExtraction(failing={1, 3}, broken={2})
        with pytest.raises(PipelineExecutionError) as raised:
            await _orchestrator(extraction).execute(_state(text=_long_text(300), source_id="src-1"))
        # The broken chunk's result has no metadata: it counts as nothing spent
        assert raised.value.llm_metadata == {"model": "m", "tokens_used": 90, "duration_ms": 10}

    async def test_a_stopped_run_counts_the_chunks_it_read_too(self):
        extraction = _FakeExtraction(failing={1}, refused={3})
        with pytest.raises(ExtractionFailedError) as raised:
            await _orchestrator(extraction).execute(
                _state(text=_long_text(400), source_id="src-1")  # 4 chunks
            )
        assert len(extraction.calls) == 3
        # Chunk 1 failed (45), chunk 2 was read (10), chunk 3 was refused (0)
        assert raised.value.llm_metadata == {"model": "m", "tokens_used": 55, "duration_ms": 12}

    async def test_a_run_that_cannot_propose_what_it_read(self):
        class _FailingProposer:
            def propose_individuals(self, run_id, input_data, triples, unread=None):
                raise RuntimeError("the proposal store is closed")

        with pytest.raises(PipelineExecutionError, match="Proposing the extracted") as raised:
            await _orchestrator(_FakeExtraction(), proposer=_FailingProposer()).execute(
                _state(text=_long_text(300), source_id="src-1")
            )
        assert raised.value.llm_metadata == {"model": "m", "tokens_used": 30, "duration_ms": 15}


class TestChunkedOrchestrator:
    async def test_pasted_text_is_extracted_in_one_call(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()
        text = _long_text(200)  # longer than one chunk, but no source inputs
        state = await _orchestrator(extraction, writer).execute(_state(text=text))
        assert extraction.calls == [text]
        assert writer.progress == []
        assert state.result["metadata"] == {"model": "m", "tokens_used": 10, "duration_ms": 5}
        assert "passages" not in state.result["triples"][0]

    async def test_source_is_extracted_chunk_by_chunk_with_progress(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()
        text = _long_text(300)  # 18299 characters -> 3 chunks
        state = await _orchestrator(extraction, writer).execute(
            _state(text=text, source_id="src-1", page_starts=[0, 9000])
        )
        total = len(extraction.calls)
        assert total == 3
        assert writer.progress == [(0, 3), (1, 3), (2, 3), (3, 3)]
        # The two-pass shape reports chunks only: its run has no stage
        assert writer.stages == []
        assert state.current_status == PipelineRunStatus.COMPLETED

        triples = state.result["triples"]
        assert len(triples) == 300
        for triple in triples:
            passage = triple["passages"][0]
            # Offsets index the whole text
            assert text[passage["start"] : passage["end"]] == triple["subject"]["label"]
            assert passage["page"] == (1 if passage["start"] < 9000 else 2)

        metadata = state.result["metadata"]
        assert metadata["source_id"] == "src-1"
        assert metadata["tokens_used"] == 30
        assert metadata["duration_ms"] == 15
        assert [c["index"] for c in metadata["chunks"]] == [0, 1, 2]
        assert sum(c["triples"] for c in metadata["chunks"]) == 300
        assert state.result["warnings"][0].startswith("Chunk 1 of 3: ")

    async def test_short_source_is_one_chunk(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()
        state = await _orchestrator(extraction, writer).execute(
            _state(text="Door one. Shelf two.", source_id="src-1")
        )
        assert len(extraction.calls) == 1
        assert writer.progress == [(0, 1), (1, 1)]
        assert state.result["triples"][1]["passages"][0]["start"] == 10

    async def test_page_range_extracts_only_those_pages(self):
        extraction = _FakeExtraction()
        text = "Door one. Shelf two. Drawer three."
        state = await _orchestrator(extraction).execute(
            _state(text=text, page_starts=[0, 10, 21], pages="2")
        )
        assert extraction.calls == ["Shelf two."]
        assert state.result["triples"][0]["passages"] == [
            {"quote": "Shelf", "start": 10, "end": 15, "page": 2}
        ]
        assert state.result["metadata"]["pages"] == "2"

    async def test_page_range_with_no_text_is_an_input_error(self):
        with pytest.raises(PipelineInputError):
            await _orchestrator(_FakeExtraction()).execute(
                _state(text="Door one.", page_starts=[0], pages="5-9")
            )

    @pytest.mark.parametrize(
        "extra",
        [
            {"pages": "1-2"},  # needs page_starts
            {"page_starts": "0, 10"},
            {"page_starts": [0, -1]},
            {"page_starts": [0, 12, 5]},
            {"headings": [{"title": "No start"}]},
            {"pages": ["1"], "page_starts": [0]},
            {"pages": "two", "page_starts": [0]},
        ],
    )
    async def test_invalid_source_inputs_are_input_errors(self, extra):
        with pytest.raises(PipelineInputError):
            await _orchestrator(_FakeExtraction()).execute(_state(text="Door one.", **extra))

    async def test_cancel_stops_before_the_next_chunk(self):
        task_holder: dict = {}

        def cancel_after_first_chunk(call_number):
            if call_number == 1:
                task_holder["task"].cancel()

        extraction = _FakeExtraction(on_call=cancel_after_first_chunk)
        writer = _StatusWriter()
        orchestrator = _orchestrator(extraction, writer)
        task = asyncio.create_task(
            orchestrator.execute(_state(text=_long_text(300), source_id="src-1"))
        )
        task_holder["task"] = task
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(extraction.calls) == 1
        assert writer.progress == [(0, 3), (1, 3)]


_ENGLISH = (
    "Bracket mounts on the wall with the screws. Anchor goes into the hole before the"
    " screw. Dock snaps onto the bracket when it is level."
)
_FRENCH = (
    "Support se fixe au mur avec les vis. Ancrage va dans le trou pour que le support"
    " tienne. Station se place sur le support et elle est de niveau."
)
_WARRANTY = (
    "LIMITED WARRANTY\nMoen warrants to the original consumer purchaser that this product"
    " is free from defects in workmanship. Proof of purchase is required."
)


class TestSkipBoilerplate:
    """A source's boilerplate and other-language copies are skipped by default (#1575)."""

    def _sheet(self):
        text = "\n\n".join([_ENGLISH, _FRENCH, _WARRANTY])
        starts = [0, len(_ENGLISH) + 2, len(_ENGLISH) + len(_FRENCH) + 4]
        return text, starts

    async def test_french_copy_and_warranty_are_skipped_and_reported(self):
        extraction = _FakeExtraction()
        text, starts = self._sheet()

        state = await _orchestrator(extraction).execute(
            _state(text=text, source_id="src-1", page_starts=starts)
        )

        assert extraction.calls == [_ENGLISH]
        result = state.result
        assert [(s["reason"], s["page_first"]) for s in result["skipped_sections"]] == [
            ("other_language", 2),
            ("warranty", 3),
        ]
        assert result["skipped_sections_by_reason"] == {"other_language": 1, "warranty": 1}
        assert result["warnings"][0].startswith("Skipped 2 sections as boilerplate")
        assert [c["page_first"] for c in result["metadata"]["chunks"]] == [1]

    async def test_skip_boilerplate_false_extracts_everything(self):
        extraction = _FakeExtraction()
        text, starts = self._sheet()

        state = await _orchestrator(extraction).execute(
            _state(text=text, source_id="src-1", page_starts=starts, skip_boilerplate=False)
        )

        read = "".join(extraction.calls)
        assert "Support se fixe" in read and "Moen warrants" in read
        assert "skipped_sections" not in state.result

    async def test_pasted_text_is_never_filtered(self):
        extraction = _FakeExtraction()

        await _orchestrator(extraction).execute(_state(text=_FRENCH))

        assert extraction.calls == [_FRENCH]

    async def test_nothing_left_is_an_input_error_naming_the_switch(self):
        with pytest.raises(PipelineInputError, match="skip_boilerplate"):
            await _orchestrator(_FakeExtraction()).execute(_state(text=_FRENCH, source_id="src-1"))

    async def test_skip_boilerplate_must_be_a_boolean(self):
        with pytest.raises(PipelineInputError, match="skip_boilerplate"):
            await _orchestrator(_FakeExtraction()).execute(
                _state(text=_ENGLISH, source_id="src-1", skip_boilerplate="no")
            )
