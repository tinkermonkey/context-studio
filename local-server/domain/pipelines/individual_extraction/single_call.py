"""
Single-call individual extraction: the orchestrator.

The same pipeline as FindThenTypeOrchestrator (same inputs, same result, same
proposal), with its individuals found differently:

1. **Find individuals**: one call reads the whole text and lists every
   individual in it with its class, against every class of the ontology with
   its whole definition (domain/extraction/single_call.py). A source too long
   for one call is read in as few sections as fit: runs of its chunks, broken
   at a chunk boundary, of at most SECTION_CHARS characters each (and never
   across a part of the text left out of the chunks), one call each.
2. **Relate**: pass 2, per chunk, between the individuals placed in it: the
   find-then-type relate step, unchanged (the predicates each subject class
   allows; FindThenTypeOrchestrator._relate_and_merge).

An individual is placed in the chunk its passage is in, and in every other
chunk of its section that names it as written, so each chunk's relationships
are read between the individuals it mentions. One with neither (its passage
was not found and no chunk names it as written) goes in the section's first
chunk, without a passage.
The single call gives no confidence: its typing triples carry none.

The call asks for the configuration's ``effort`` ("high" for
extraction-single-call); the relate calls for the model's default. The run's
output limit (64,000 for extraction-single-call) is the single call's; a relate
call may produce at most RELATE_MAX_TOKENS (find-then-type's own limit), or the
run's when that is lower. An answer of the single call cut off at the output
limit is not asked for again: its section fails, saying so.

Failures keep find-then-type's rules: a section whose call failed makes each
of its chunks a failed chunk; the run fails when every section's call failed,
and at once when the provider refuses the model's requests; a pasted text is
one section, and any failure fails its run. Progress is counted in chunks, as
for find-then-type: a chunk is done when its relationships are read. The
stage is find_individuals, counted in sections read, then
derive_relationships, counted in chunks read.
"""

from __future__ import annotations

import asyncio
from typing import Any

from domain.extraction.chunking import Chunk
from domain.extraction.entities import Mention
from domain.extraction.find_then_type import typing_triple
from domain.extraction.prompts import FIND_INDIVIDUALS, SINGLE_CALL_STAGES
from domain.extraction.single_call import name_spans
from domain.pipelines.entities import StageProgress
from domain.pipelines.individual_extraction.find_then_type import FindThenTypeOrchestrator
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionState,
    _failure,
)

# The most characters of text one call reads. The call's answer grows with the
# text: the head-to-head's one call wrote up to 28,700 output tokens, thinking
# included, for its 46,000-character document (relationships included), and a
# configuration may let a call write 64,000. A section of up to this many
# characters so leaves the answer about twice the room it was seen to need.
SECTION_CHARS = 60000

# The most output tokens a relate call may produce: what extraction-find-then-type
# gives its relate calls. The recorded relate calls wrote at most 11,808.
RELATE_MAX_TOKENS = 16000


class SingleCallOrchestrator(FindThenTypeOrchestrator):
    """
    Individual extraction that finds and types a text's individuals in one
    call over the whole text, then relates them chunk by chunk.

    Execution, for a source (see the module docstring for the rules):
    - Find the individuals of each section in turn (one section for most
      sources); a cancelled run stops before its next section
    - Place each individual in the chunks that hold its passage or name it
    - Relate the individuals of each chunk in turn, reporting progress
    - Recognize the triples' individuals and merge the triples over the text
    """

    STAGE_PROMPTS = SINGLE_CALL_STAGES

    def _relate_max_tokens(self, state: IndividualExtractionState) -> int | None:
        """RELATE_MAX_TOKENS, or the run's limit when that is lower."""
        if state.max_tokens is None:
            return RELATE_MAX_TOKENS
        return min(state.max_tokens, RELATE_MAX_TOKENS)

    async def _individuals(
        self,
        state: IndividualExtractionState,
        chunks: list[Chunk],
        texts: list[str],
        report: bool,
        spent: list[Any],
        warnings: list[str],
        problems: list[list[tuple[str, Any]]],
    ) -> tuple[list[list[dict[str, Any]]], dict[str, Any]]:
        """
        Find each section's individuals in one call and place them in its chunks.

        Returns:
            (each chunk's typing triples, what the run's metadata says of
            them: ``individuals``)

        Raises:
            ExtractionFailedError: If every section's call failed because an
                LLM response stayed incomplete or the provider did not answer,
                or the provider refused the model's requests
            PipelineExecutionError: If they failed for another reason
        """
        groups = sections(state.source_text, chunks)
        total = len(groups)
        effort = self._config.get("effort")
        if report:
            self._report_progress(0, len(chunks), StageProgress(FIND_INDIVIDUALS, 0, total))
        chunk_triples: list[list[dict[str, Any]]] = [[] for _ in chunks]
        listed = 0
        for number, members in enumerate(groups):
            await asyncio.sleep(0)  # a cancelled run stops here
            start, end = chunks[members[0]].start, chunks[members[-1]].end
            result = self._extraction_service.find_individuals(
                text=state.source_text[start:end],
                ontology_id=state.ontology_id,
                model=state.model,
                temperature=state.temperature,
                stage_prompts=self._stage_prompts,
                max_tokens=state.max_tokens,
                effort=effort,
            )
            spent.append(result)
            where = f"Section {number + 1} of {total}: " if total > 1 else ""
            if result.failure_reason and result.provider_refused:
                raise _failure(
                    [result],
                    (
                        f"Extraction stopped at section {number + 1} of {total}, because every"
                        f" later call would fail the same way: {result.failure_reason}"
                        if total > 1
                        else f"Extraction failed: {result.failure_reason}"
                    ),
                    state.model,
                    spent,
                )
            if result.failure_reason:
                for index in members:
                    problems[index].append((result.failure_reason, result))
            warnings.extend(where + warning for warning in result.warnings)
            listed += len(result.individuals)
            for individual in result.individuals:
                for index, mention in _placements(
                    individual.mention, start, members, chunks, texts
                ):
                    chunk_triples[index].append(typing_triple(mention, individual.class_ref, None))
            if report:
                stage = StageProgress(FIND_INDIVIDUALS, number + 1, total)
                self._report_progress(0, len(chunks), stage)
        if all(problems):
            reason = problems[0][0][0]
            raise _failure(
                [failed for chunk in problems for _, failed in chunk],
                (
                    f"Extraction failed for every section ({total}): {reason}"
                    if total > 1
                    else f"Extraction failed: {reason}"
                ),
                state.model,
                spent,
            )
        return chunk_triples, {"individuals": {"found": listed, "sections": total}}


def sections(text: str, chunks: list[Chunk]) -> list[list[int]]:
    """
    The fewest runs of consecutive chunks (their indexes) that each fit one
    call: at most SECTION_CHARS characters from the first chunk's start to the
    last one's end, and no text but white space between two of its chunks
    (text left out of the chunks, a skipped section, is never read). A chunk
    longer than SECTION_CHARS is a section of its own.
    """
    groups: list[list[int]] = []
    for index, chunk in enumerate(chunks):
        if groups:
            first, last = chunks[groups[-1][0]], chunks[groups[-1][-1]]
            joined = not text[last.end : chunk.start].strip()
            if joined and chunk.end - first.start <= SECTION_CHARS:
                groups[-1].append(index)
                continue
        groups.append([index])
    return groups


def _placements(
    mention: Mention, offset: int, members: list[int], chunks: list[Chunk], texts: list[str]
) -> list[tuple[int, Mention]]:
    """
    The chunks of a section an individual is placed in, each with its passage
    there (offsets into the chunk's text): the chunk its passage is in, and
    every other chunk of the section that names it as written. ``mention`` is
    placed in the section's text, which starts at ``offset`` in the source.
    """
    placed: list[tuple[int, Mention]] = []
    home = None
    if mention.start is not None and mention.end is not None:
        at = offset + mention.start
        home = next((i for i in reversed(members) if chunks[i].start <= at), members[0])
        shift = chunks[home].start - offset
        placed.append(
            (
                home,
                Mention(
                    mention.name,
                    mention.kind,
                    mention.quote,
                    mention.start - shift,
                    mention.end - shift,
                ),
            )
        )
    for index in members:
        if index == home:
            continue
        spans = name_spans(mention.name, texts[index])
        if spans:
            start, end = spans[0]
            quote = texts[index][start:end]
            placed.append((index, Mention(mention.name, mention.kind, quote, start, end)))
    if not placed:
        placed.append((members[0], Mention(mention.name, mention.kind)))
    return sorted(placed, key=lambda place: place[0])
