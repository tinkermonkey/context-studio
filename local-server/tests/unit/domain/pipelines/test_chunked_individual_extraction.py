"""
Unit tests for chunked individual extraction (#1552).

A source (input with source_id, page_starts, headings or pages) is extracted
chunk by chunk: offsets map back to the whole text, the same triple found in
several chunks merges with every passage, progress is reported per chunk and a
cancelled run stops before its next chunk. Pasted text is extracted in one call.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import asyncio
from dataclasses import dataclass, field

import pytest

from domain.extraction.chunking import Chunk
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineInputError
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


class _FakeExtraction:
    """Extracts one typing triple per 'Name.' sentence of the text it is given."""

    def __init__(self, on_call=None):
        self.calls: list[str] = []
        self._on_call = on_call

    def extract_triples(
        self, text, ontology_id, model, temperature, stage_prompts=None, dataset_id=None
    ):
        self.calls.append(text)
        if self._on_call:
            self._on_call(len(self.calls))
        triples = []
        for sentence in text.split(". "):
            name = sentence.strip().rstrip(".").split(" ")[0]
            if name:
                triples.append(_typing(name, quote=name, start=text.index(name)))
        return _Result(
            triples=triples,
            warnings=[f"saw {len(triples)}"],
            metadata={"model": model, "tokens_used": 10, "duration_ms": 5},
        )


class _StatusWriter:
    def __init__(self):
        self.progress: list[tuple[int, int | None]] = []

    def update_running_status(self, run_id, started_at):
        pass

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))


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


def _orchestrator(extraction, writer=None):
    return IndividualExtractionOrchestrator(
        llm_provider=None, extraction_service=extraction, run_id="run-1", status_writer=writer
    )


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
