"""
Unit tests for SingleCallOrchestrator.

The shape finds and types a source's individuals in one call over the whole
text (or over as few sections as fit, for a text too long for one call),
places each individual in the chunks that hold its passage or name it, then
relates the individuals of each chunk with find-then-type's relate step and
hands the triples to the same merge and proposer. Its stages are
find_individuals, counted in sections, and derive_relationships, counted in
chunks. Nothing that failed reads as "found nothing".
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import re
from dataclasses import dataclass, field

import pytest

from domain.extraction.chunking import Chunk, chunk_text
from domain.extraction.entities import FoundIndividual, Mention
from domain.extraction.prompts import SINGLE_CALL_STAGES
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import ExtractionFailedError, PipelineExecutionError
from domain.pipelines.individual_extraction.find_then_type import FindThenTypeOrchestrator
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from domain.pipelines.individual_extraction.single_call import (
    RELATE_MAX_TOKENS,
    SECTION_CHARS,
    SingleCallOrchestrator,
    _placements,
    sections,
)

INCOMPLETE = (
    "The LLM response for find_individuals was still incomplete after 3 attempts:"
    " it holds no complete JSON object (finish_reason=max_tokens)"
)
REFUSED = "The anthropic provider rejected its API key"
SQL = "(sqlite3.OperationalError) database is locked [SQL: SELECT 1]"

_NAME = re.compile(r"\b(?:Part\d{3,4}|Gateway)\b")


@dataclass
class _Result:
    individuals: list = field(default_factory=list)
    triples: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    failure_reason: str | None = None
    incomplete_response: bool = False
    provider_failed: bool = False
    provider_refused: bool = False


def _failed(how):
    spent = {"model": "m", "tokens_used": 40, "duration_ms": 1}
    if how == "incomplete":
        return _Result(metadata=spent, failure_reason=INCOMPLETE, incomplete_response=True)
    if how == "refused":
        return _Result(
            metadata=spent, failure_reason=REFUSED, provider_failed=True, provider_refused=True
        )
    return _Result(metadata=spent, failure_reason=SQL)


class _FakeExtraction:
    """
    The calls of the single-call shape over a text of 'Name xxx.' sentences.

    find_individuals lists each distinct name of the text it is given once,
    typed "app.component", with its first occurrence as its passage ("Gateway"
    with a quote that is not in the text, so it is placed by name only).
    Relate states one relationship between the first two individuals it is
    given. ``find``/``relate``: call number (from 1) -> how that call fails.
    """

    def __init__(self, find=None, relate=None):
        self._find = find or {}
        self._relate = relate or {}
        self.read: list[str] = []
        self.related: list[list[str]] = []
        self.calls: list[dict] = []
        self.relate_limits: list = []

    def find_individuals(
        self,
        text,
        ontology_id,
        model,
        temperature,
        stage_prompts=None,
        max_tokens=None,
        effort=None,
    ):
        self.read.append(text)
        self.calls.append({"max_tokens": max_tokens, "effort": effort, "prompts": stage_prompts})
        how = self._find.get(len(self.read))
        if how:
            return _failed(how)
        found, seen = [], set()
        for match in _NAME.finditer(text):
            name = match.group()
            if name in seen:
                continue
            seen.add(name)
            mention = (
                Mention(name, "thing")
                if name == "Gateway"
                else Mention(name, "thing", name, match.start(), match.end())
            )
            found.append(FoundIndividual(mention, "app.component"))
        return _Result(
            individuals=found,
            warnings=["a find warning"],
            metadata={"model": model, "tokens_used": 1000, "duration_ms": 5},
        )

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
        names = list(dict.fromkeys(t["subject"]["label"] for t in typing_triples))
        self.related.append(names)
        self.relate_limits.append(max_tokens)
        for triple in typing_triples:
            provenance = triple["provenance"]
            if provenance["start"] is not None:
                assert text[provenance["start"] : provenance["end"]] == provenance["quote"]
        how = self._relate.get(len(self.related))
        if how:
            return _failed(how)
        return _Result(
            triples=[
                {
                    "subject": {"kind": "individual", "id": "", "label": names[0]},
                    "predicate": {"property_definition_id": "", "label": "uses"},
                    "object": {"kind": "individual", "id": "", "label": names[1]},
                    "confidence": 0.7,
                    "provenance": {"quote": names[0], "start": 0, "end": len(names[0])},
                }
            ],
            metadata={"model": model, "tokens_used": 50, "duration_ms": 3},
        )

    def recognize(self, triples, ontology_id, dataset_id=None):
        return triples


class _StatusWriter:
    def __init__(self):
        self.writes: list = []

    def update_running_status(self, run_id, started_at):
        pass

    def update_progress(self, run_id, items_done, items_total, stage=None):
        self.writes.append((items_done, items_total, stage.stage, stage.done, stage.total))


def _text(sentences: int) -> str:
    """Sentences of 60 characters, each naming a distinct part; each tenth names the Gateway."""
    out = []
    for i in range(sentences):
        name = f"Part{i:03d}"
        extra = " Gateway" if i % 10 == 0 else ""
        out.append(name + extra + " " + "x" * (60 - len(name) - len(extra) - 2) + ".")
    return " ".join(out)


SOURCE = _text(300)  # 18299 characters -> 3 chunks, one section
LONG = _text(1600)  # 97599 characters -> 13 chunks, two sections


def _state(**input_data):
    return IndividualExtractionState(
        run_id="run-1",
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={"ontology_id": "onto-1", "model": "m", **input_data},
    )


async def _run(extraction, writer=None, text=SOURCE, config=None, **input_data):
    input_data = input_data or {"source_id": "src-1"}
    orchestrator = SingleCallOrchestrator(
        llm_provider=None,
        extraction_service=extraction,
        run_id="run-1",
        status_writer=writer,
        config=config,
    )
    return await orchestrator.execute(_state(text=text, **input_data))


def _typed(result):
    return {
        t["subject"]["label"]: t
        for t in result.result["triples"]
        if t["predicate"]["label"] == "is_a"
    }


class TestSingleCallFlow:
    def test_it_is_find_then_type_with_its_own_find_stage(self):
        assert issubclass(SingleCallOrchestrator, FindThenTypeOrchestrator)
        assert [stage.key for stage in SingleCallOrchestrator.STAGE_PROMPTS] == [
            "find_individuals",
            "derive_relationships",
        ]
        assert SingleCallOrchestrator.STAGE_PROMPTS is SINGLE_CALL_STAGES

    async def test_a_source_that_fits_is_read_in_one_call(self):
        extraction = _FakeExtraction()

        state = await _run(extraction)

        assert extraction.read == [SOURCE[: len(extraction.read[0])]]
        assert len(extraction.read[0]) > 18000
        typed = _typed(state)
        assert len(typed) == 301  # 300 parts and the Gateway
        assert typed["Part005"]["object"]["label"] == "app.component"
        assert typed["Part005"]["confidence"] is None
        assert state.result["metadata"]["individuals"] == {"found": 301, "sections": 1}
        assert state.result["warnings"] == ["a find warning"]

    async def test_the_configuration_s_effort_and_the_run_s_limit_reach_the_call(self):
        extraction = _FakeExtraction()

        await _run(extraction, config={"effort": "high"}, source_id="s", max_tokens=64000)

        assert extraction.calls[0]["effort"] == "high"
        assert extraction.calls[0]["max_tokens"] == 64000
        # The relate calls keep find-then-type's own limit
        assert set(extraction.relate_limits) == {RELATE_MAX_TOKENS} == {16000}

    @pytest.mark.parametrize("limit, related", [(8000, 8000), (None, 16000)])
    async def test_a_relate_call_gets_the_run_s_limit_when_it_is_lower(self, limit, related):
        extraction = _FakeExtraction()

        await _run(extraction, source_id="s", **({"max_tokens": limit} if limit else {}))

        assert extraction.calls[0]["max_tokens"] == limit
        assert set(extraction.relate_limits) == {related}

    async def test_with_no_effort_configured_none_is_asked_for(self):
        extraction = _FakeExtraction()

        await _run(extraction)

        assert extraction.calls[0]["effort"] is None

    async def test_an_individual_is_related_in_every_chunk_that_names_it(self):
        extraction = _FakeExtraction()

        state = await _run(extraction)

        # The Gateway's quote was not placed: it is in each chunk that names it
        chunks = state.result["metadata"]["chunks"]
        assert len(chunks) == 3 and len(extraction.related) == 3
        assert all("Gateway" in names for names in extraction.related)
        gateway = _typed(state)["Gateway"]
        assert len(gateway["passages"]) == 3
        assert all(SOURCE[p["start"] : p["end"]] == "Gateway" for p in gateway["passages"])
        # A part is in the chunk its passage is in, at its place in the source
        part = _typed(state)["Part150"]
        assert [SOURCE[p["start"] : p["end"]] for p in part["passages"]] == ["Part150"]

    async def test_relationships_are_merged_with_the_individuals(self):
        state = await _run(_FakeExtraction())

        assert [t for t in state.result["triples"] if t["predicate"]["label"] == "uses"]

    async def test_stages_are_find_individuals_by_section_then_relationships_by_chunk(self):
        writer = _StatusWriter()

        await _run(_FakeExtraction(), writer)

        assert writer.writes == [
            (0, 3, "find_individuals", 0, 1),
            (0, 3, "find_individuals", 1, 1),
            (0, 3, "derive_relationships", 0, 3),
            (1, 3, "derive_relationships", 1, 3),
            (2, 3, "derive_relationships", 2, 3),
            (3, 3, "derive_relationships", 3, 3),
        ]

    async def test_a_long_source_is_read_in_the_fewest_sections_that_fit(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()

        state = await _run(extraction, writer, text=LONG)

        assert len(extraction.read) == 2
        assert all(len(text) <= SECTION_CHARS for text in extraction.read)
        assert "".join(extraction.read).replace(" ", "") == LONG.replace(" ", "")
        assert [w[2:] for w in writer.writes[:3]] == [
            ("find_individuals", 0, 2),
            ("find_individuals", 1, 2),
            ("find_individuals", 2, 2),
        ]
        assert state.result["metadata"]["individuals"]["sections"] == 2
        assert len(_typed(state)) == 1601
        assert state.result["warnings"][:2] == [
            "Section 1 of 2: a find warning",
            "Section 2 of 2: a find warning",
        ]


class TestSections:
    def _chunks(self, text):
        return chunk_text(text)

    def test_chunks_that_fit_are_one_section(self):
        assert sections(SOURCE, self._chunks(SOURCE)) == [[0, 1, 2]]

    def test_a_section_never_passes_the_limit_and_takes_as_many_chunks_as_fit(self):
        chunks = self._chunks(LONG)

        groups = sections(LONG, chunks)

        assert [i for group in groups for i in group] == list(range(len(chunks)))
        for group in groups:
            assert chunks[group[-1]].end - chunks[group[0]].start <= SECTION_CHARS
        # The fewest: no two neighbouring sections would fit as one
        for left, right in zip(groups, groups[1:]):
            assert chunks[right[0]].end - chunks[left[0]].start > SECTION_CHARS

    def test_text_left_out_of_the_chunks_breaks_a_section(self):
        text = "a" * 100 + "SKIPPED" + "b" * 100
        chunks = [Chunk(index=0, start=0, end=100), Chunk(index=1, start=107, end=207)]

        assert sections(text, chunks) == [[0], [1]]

    def test_white_space_between_chunks_does_not(self):
        text = "a" * 100 + "  \n" + "b" * 100
        chunks = [Chunk(index=0, start=0, end=100), Chunk(index=1, start=103, end=203)]

        assert sections(text, chunks) == [[0, 1]]


class TestFailedSections:
    async def test_a_failed_section_makes_its_chunks_failed_chunks(self):
        state = await _run(_FakeExtraction(find={1: "incomplete"}), text=LONG)

        first, second = sections(LONG, chunk_text(LONG))
        failed = state.result["failed_chunks"]
        assert [c["index"] for c in failed] == first
        assert all(c["failure_reason"] == INCOMPLETE for c in failed)
        assert state.result["warnings"][0].startswith(f"Extraction failed for {len(first)} of")
        # The other section's individuals are kept
        last = state.result["metadata"]["chunks"][second[-1]]
        assert "Part1599" in _typed(state) and last["failure_reason"] is None

    async def test_the_run_fails_when_every_section_failed(self):
        with pytest.raises(ExtractionFailedError) as error:
            await _run(_FakeExtraction(find={1: "incomplete", 2: "incomplete"}), text=LONG)

        assert str(error.value) == f"Extraction failed for every section (2): {INCOMPLETE}"
        assert error.value.llm_metadata["tokens_used"] == 80

    async def test_a_source_of_one_section_that_failed_fails_the_run(self):
        with pytest.raises(ExtractionFailedError, match="^Extraction failed: The LLM response"):
            await _run(_FakeExtraction(find={1: "incomplete"}))

    async def test_a_reason_not_written_for_the_caller_is_not_shown(self):
        with pytest.raises(PipelineExecutionError) as error:
            await _run(_FakeExtraction(find={1: "broken"}))

        assert not isinstance(error.value, ExtractionFailedError)

    async def test_a_refused_call_stops_the_run_there(self):
        extraction = _FakeExtraction(find={1: "refused"})

        with pytest.raises(ExtractionFailedError) as error:
            await _run(extraction, text=LONG)

        assert str(error.value) == (
            "Extraction stopped at section 1 of 2, because every later call would fail the"
            f" same way: {REFUSED}"
        )
        assert len(extraction.read) == 1

    async def test_relationships_that_could_not_be_read_keep_the_individuals(self):
        state = await _run(_FakeExtraction(relate={2: "incomplete"}))

        assert len(_typed(state)) == 301
        assert [c["index"] for c in state.result["failed_chunks"]] == [1]


class TestPastedText:
    async def test_pasted_text_is_one_call_without_progress_or_sections(self):
        extraction = _FakeExtraction()
        writer = _StatusWriter()

        state = await _run(
            extraction, writer, text="Part001 and Part002 talk.", **{"dataset_id": None}
        )

        assert extraction.read == ["Part001 and Part002 talk."]
        assert writer.writes == []
        assert set(_typed(state)) == {"Part001", "Part002"}
        assert state.result["warnings"] == ["a find warning"]
        assert "chunks" not in state.result["metadata"]

    async def test_a_failed_call_fails_the_run(self):
        with pytest.raises(ExtractionFailedError, match="^Extraction failed: "):
            await _run(_FakeExtraction(find={1: "incomplete"}), text="Part001 x.", dataset_id=None)


def test_placements_without_any_passage_go_to_the_first_chunk():

    chunks = [Chunk(index=0, start=0, end=10), Chunk(index=1, start=10, end=20)]
    texts = ["aaaaaaaaaa", "bbbbbbbbbb"]

    placed = _placements(Mention("Nowhere", "thing"), 0, [0, 1], chunks, texts)

    assert placed == [(0, Mention("Nowhere", "thing"))]


def test_a_passage_is_placed_in_its_chunk_with_offsets_into_it():

    chunks = [Chunk(index=0, start=0, end=10), Chunk(index=1, start=10, end=20)]
    texts = ["aaaaaaaaaa", "bbbbFoobbb"]

    placed = _placements(Mention("Foo", "thing", "Foo", 14, 17), 0, [0, 1], chunks, texts)

    assert placed == [(1, Mention("Foo", "thing", "Foo", 4, 7))]
