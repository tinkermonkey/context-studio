"""
Find-then-type individual extraction: the orchestrator.

The same pipeline as IndividualExtractionOrchestrator (same inputs, same
result, same proposal), with pass 1 done differently:

1. **Find**: each chunk is read once for what it mentions, typing nothing.
2. **Type**: the mentions are merged over the whole source by their label key
   (labels.LabelKeys, the rule the triples are merged by), and each distinct
   one is typed once, against every class of the ontology with the opening of
   its definition: one class, or none when it is not something to record. An
   individual so has one class however many chunks mention it. A name with a
   corporate suffix is typed apart from the same name without one ("Acme LLC",
   "Acme"): the merge makes them one individual when they get the same class.
   Typing calls run side by side; they share one system prompt, which a
   provider can cache.
3. **Relate**: pass 2, per chunk, between the individuals typed in it.

The result is the triples the two-pass shape gives: a typing triple for each
chunk an individual is mentioned in, and the relationship triples, recognized
against the graph and merged over the source (chunk_merge.py).

Failures keep the rules of the two-pass shape. Nothing that failed reads as
"found nothing":

- a chunk whose find failed is a failed chunk;
- a mention that could not be typed is left out, and the chunk it was typed in
  is a failed chunk whose failure_reason says how many of its mentions could
  not be typed;
- a chunk whose relationships could not be read keeps its individuals and is a
  failed chunk whose failure_reason says so;
- the run fails when every chunk's find failed or every typing call failed,
  and at once when the provider refuses the model's requests while finding or
  typing (every later call would fail the same way). A refusal while relating
  costs the relationships of that chunk and the later ones, not what was typed.
  A run so completes even when every chunk is a failed chunk for its
  relationships: it keeps the individuals;
- a pasted text has no part to carry on with: any of these fails its run.

A run with failed chunks proposes what it has as a partial proposal, which
supersedes no other proposal of the source. Progress is counted in chunks, as
for the two-pass shape: a chunk is done when its relationships are read, so
the count stays at 0 while mentions are found and typed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.chunking import Chunk
from domain.extraction.entities import Mention
from domain.extraction.find_then_type import mention_context, typing_triple
from domain.extraction.prompts import FIND_THEN_TYPE_STAGES
from domain.pipelines.exceptions import PipelineExecutionError
from domain.pipelines.individual_extraction.chunk_merge import merge_chunk_triples
from domain.pipelines.individual_extraction.labels import LabelKeys, has_corporate_suffix
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
    _failure,
    _reason_is_for_caller,
    _spent,
)

_logger = logging.getLogger(__name__)

# Typing calls in flight at once
_TYPING_CONCURRENCY = 6

# Metadata a run on a source has and a run on a pasted text does not
_CHUNKED_ONLY = ("chunks", "source_id", "pages")


@dataclass
class _Candidate:
    """A distinct mention of the source: every place it was found, and its typing."""

    # (index of the chunk among the run's chunks, the mention found there)
    found: list[tuple[int, Mention]] = field(default_factory=list)
    # The typing call's result; None when the call was never made
    typing: Any = None

    @property
    def typed_in(self) -> tuple[int, Mention]:
        """The place it is typed in: the first with a placed passage, else the first."""
        return next((place for place in self.found if place[1].start is not None), self.found[0])


@dataclass
class _ChunkFailure:
    """Why a chunk is a failed chunk, in the shape `_reason_is_for_caller` reads."""

    failure_reason: str
    incomplete_response: bool = False
    provider_failed: bool = False
    provider_refused: bool = False


class FindThenTypeOrchestrator(IndividualExtractionOrchestrator):
    """
    Individual extraction that finds a text's mentions first and types each
    one on its own against the ontology's whole class catalog.

    Execution, for a source (see the module docstring for the failure rules):
    - Find the mentions of each chunk in turn; a cancelled run stops before
      its next chunk
    - Type each distinct mention once, calls side by side
    - Relate the typed individuals of each chunk in turn, reporting progress
    - Recognize the triples' individuals and merge the triples over the text
    """

    STAGE_PROMPTS = FIND_THEN_TYPE_STAGES
    SOURCE_CONFIGURATION = "extraction-find-then-type"

    async def _extract_text(
        self, state: IndividualExtractionState
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        """
        Extract a pasted text as one chunk; a failure of any part fails the run.

        Raises:
            ExtractionFailedError: If a part of the extraction failed because
                an LLM response stayed incomplete or the provider did not answer
            PipelineExecutionError: If it failed for another reason
        """
        whole = Chunk(index=0, start=0, end=len(state.source_text))
        triples, warnings, metadata, failures, spent = await self._find_type_relate(
            state, [whole], [], report=False
        )
        if failures:
            failure = failures[0][1]
            raise _failure(
                [failure], f"Extraction failed: {failure.failure_reason}", state.model, spent
            )
        return triples, warnings, {k: v for k, v in metadata.items() if k not in _CHUNKED_ONLY}

    async def _extract_by_chunk(
        self, state: IndividualExtractionState, chunks: list[Chunk], page_starts: list[int]
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any], str | None]:
        """
        Find, type and relate over a source's chunks, then merge the triples.

        Returns:
            (merged triples, warnings, metadata, a sentence saying which chunks
            failed or None when none did)

        Raises:
            ExtractionFailedError: If every chunk's find or every typing call
                failed because an LLM response stayed incomplete or the
                provider did not answer, or the provider refused the model's
                requests while finding or typing
            PipelineExecutionError: If they failed for another reason, or
                recognizing the individuals failed
        """
        triples, warnings, metadata, failures, _ = await self._find_type_relate(
            state, chunks, page_starts, report=True
        )
        unread = _failed_chunks_note(failures, len(chunks), state.run_id) if failures else None
        return triples, warnings, metadata, unread

    async def _find_type_relate(
        self,
        state: IndividualExtractionState,
        chunks: list[Chunk],
        page_starts: list[int],
        report: bool,
    ) -> tuple[
        list[dict[str, Any]],
        list[str],
        dict[str, Any],
        list[tuple[Chunk, _ChunkFailure]],
        list[Any],
    ]:
        """
        The whole flow over the given chunks. ``report`` is False for a pasted
        text, which is one chunk: no progress is reported, and no message
        speaks of chunks.

        Returns:
            (merged triples, warnings, metadata, the failed chunks with why,
            every call's result for what the run cost)
        """
        service = self._extraction_service
        total = len(chunks)
        texts = [state.source_text[chunk.start : chunk.end] for chunk in chunks]

        def where(index: int) -> str:
            return f"Chunk {index + 1} of {total}: " if report else ""

        if report:
            self._report_progress(0, total)
        spent: list[Any] = []  # every call's result: what the run cost
        warnings: list[str] = []
        # Per chunk, why it is a failed chunk: (reason, the result that failed)
        problems: list[list[tuple[str, Any]]] = [[] for _ in chunks]

        # 1. Find
        found: list[list[Mention]] = []
        for index, text in enumerate(texts):
            await asyncio.sleep(0)  # a cancelled run stops here
            result = service.find_mentions(
                text=text,
                ontology_id=state.ontology_id,
                model=state.model,
                temperature=state.temperature,
                stage_prompts=self._stage_prompts,
            )
            spent.append(result)
            if result.failure_reason and result.provider_refused:
                raise _failure(
                    [result],
                    (
                        f"Extraction stopped at chunk {index + 1} of {total}, because every"
                        f" later call would fail the same way: {result.failure_reason}"
                        if report
                        else f"Extraction failed: {result.failure_reason}"
                    ),
                    state.model,
                    spent,
                )
            if result.failure_reason:
                problems[index].append((result.failure_reason, result))
            warnings.extend(where(index) + w for w in result.warnings)
            found.append(result.mentions)
        if all(problems):
            raise _failure(
                [failed for chunk in problems for _, failed in chunk],
                (
                    f"Extraction failed for every chunk ({total}): {problems[0][0][0]}"
                    if report
                    else f"Extraction failed: {problems[0][0][0]}"
                ),
                state.model,
                spent,
            )

        # 2. Type each distinct mention once
        candidates = _candidates(found)
        try:
            await self._type(state, texts, candidates, spent)
        except Exception as exc:
            raise PipelineExecutionError(
                "Typing what the text mentions failed", llm_metadata=_spent(state.model, spent)
            ) from exc
        asked = [c for c in candidates if c.typing is not None]
        untyped = [c for c in asked if c.typing.failure_reason]
        refused = next((c for c in untyped if c.typing.provider_refused), None)
        if refused is not None:
            raise _failure(
                [refused.typing],
                f"Extraction stopped while typing what the text mentions ({len(asked)} of"
                f" {len(candidates)} asked), because every later call would fail the same"
                f" way: {refused.typing.failure_reason}",
                state.model,
                spent,
            )
        if asked and len(untyped) == len(asked):
            raise _failure(
                [c.typing for c in untyped],
                f"Typing failed for every one of the {len(asked)} mentions:"
                f" {untyped[0].typing.failure_reason}",
                state.model,
                spent,
            )
        for index in range(total):
            here = [c for c in untyped if c.typed_in[0] == index]
            if here:
                of = sum(1 for c in candidates if c.typed_in[0] == index)
                problems[index].append(
                    (
                        f"{len(here)} of its {of} mentions could not be typed"
                        f" ({here[0].typed_in[1].name}): {here[0].typing.failure_reason}",
                        here[0].typing,
                    )
                )

        # The typing triples of each chunk: one per place a typed mention was found
        chunk_triples: list[list[dict[str, Any]]] = [[] for _ in chunks]
        for candidate in candidates:
            typing = candidate.typing
            if typing is None or typing.failure_reason or not typing.class_ref:
                continue
            for index, mention in candidate.found:
                chunk_triples[index].append(
                    typing_triple(mention, typing.class_ref, typing.confidence)
                )

        # 3. Relate, per chunk
        refusal: str | None = None
        for index, text in enumerate(texts):
            await asyncio.sleep(0)  # a cancelled run stops here
            if not _has_relationships_to_read(chunk_triples[index]):
                pass
            elif refusal is None:
                result = service.relate(
                    text=text,
                    typing_triples=chunk_triples[index],
                    ontology_id=state.ontology_id,
                    model=state.model,
                    temperature=state.temperature,
                    stage_prompts=self._stage_prompts,
                )
                spent.append(result)
                warnings.extend(where(index) + w for w in result.warnings)
                if result.failure_reason:
                    problems[index].append(
                        (f"Its relationships could not be read: {result.failure_reason}", result)
                    )
                    if result.provider_refused:
                        refusal = result.failure_reason
                else:
                    chunk_triples[index] = chunk_triples[index] + result.triples
            else:
                # Every later call would fail the same way: none is made
                problems[index].append(
                    (
                        f"Its relationships could not be read: {refusal}",
                        _ChunkFailure(refusal, provider_failed=True, provider_refused=True),
                    )
                )
            if report:
                self._report_progress(index + 1, total)

        # Recognition reads the graph: once, over every chunk's triples
        every_triple = [triple for triples in chunk_triples for triple in triples]
        try:
            recognized = service.recognize(
                every_triple, state.ontology_id, state.input_data.get("dataset_id")
            )
        except Exception as exc:
            raise PipelineExecutionError(
                "Recognizing the extracted individuals failed",
                llm_metadata=_spent(state.model, spent),
            ) from exc
        position = 0
        merged_input: list[tuple[Chunk, list[dict[str, Any]]]] = []
        for chunk, triples in zip(chunks, chunk_triples):
            merged_input.append((chunk, recognized[position : position + len(triples)]))
            position += len(triples)

        failures = [
            (chunk, _chunk_failure(problem)) for chunk, problem in zip(chunks, problems) if problem
        ]
        reasons = {chunk.index: failure.failure_reason for chunk, failure in failures}
        metadata = {
            **_spent(state.model, spent),
            "source_id": state.input_data.get("source_id"),
            "pages": state.input_data.get("pages"),
            "mentions": {
                "found": sum(len(mentions) for mentions in found),
                "distinct": len(candidates),
                "typed": sum(1 for c in asked if c.typing.class_ref),
                "not_recorded": sum(
                    1 for c in asked if not c.typing.failure_reason and not c.typing.class_ref
                ),
                "untyped": len(untyped),
            },
            "chunks": [
                {
                    "index": chunk.index,
                    "start": chunk.start,
                    "end": chunk.end,
                    "page_first": chunk.page_first,
                    "page_last": chunk.page_last,
                    "heading": chunk.heading,
                    "triples": len(triples),
                    "failure_reason": reasons.get(chunk.index),
                }
                for chunk, triples in merged_input
            ],
        }
        return (
            merge_chunk_triples(merged_input, page_starts),
            warnings,
            metadata,
            failures,
            spent,
        )

    async def _type(
        self,
        state: IndividualExtractionState,
        texts: list[str],
        candidates: list[_Candidate],
        spent: list[Any],
    ) -> None:
        """
        Type every candidate, _TYPING_CONCURRENCY calls at a time, each on a
        worker thread (the call reads nothing but its arguments).

        The first call is made alone: it is the one that writes the catalog to
        a provider's cache, which the others then read. Once a call is refused
        as every later one would be, no further call is made: those candidates
        keep ``typing`` None. Every call that was made is added to ``spent``.
        """
        if not candidates:
            return
        prompt = self._extraction_service.typing_prompt(state.ontology_id, self._stage_prompts)
        gate = asyncio.Semaphore(_TYPING_CONCURRENCY)
        stopped = False

        async def type_one(candidate: _Candidate) -> None:
            nonlocal stopped
            index, mention = candidate.typed_in
            async with gate:
                if stopped:
                    return
                candidate.typing = await asyncio.to_thread(
                    self._extraction_service.type_mention,
                    prompt,
                    mention_context(texts[index], mention),
                    mention,
                    state.model,
                    state.temperature,
                )
                spent.append(candidate.typing)
                if candidate.typing.failure_reason and candidate.typing.provider_refused:
                    stopped = True

        await type_one(candidates[0])
        tasks = [asyncio.ensure_future(type_one(candidate)) for candidate in candidates[1:]]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            # A call that raised, or a cancelled run: the calls not yet made are not made
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise


def _candidates(found: list[list[Mention]]) -> list[_Candidate]:
    """
    The distinct mentions of a source, in order of first appearance: mentions
    whose names share a label key are one, whatever their kind, since that is
    how their triples will be merged.

    A name with a corporate suffix is kept apart from the same name without
    one: whether "Wikimedia Enterprise LLC" (a business) and "Wikimedia
    Enterprise" (a product) are one individual depends on the classes they are
    typed with, which the merge of their triples decides (LabelKeys' ``typed``).
    """
    keys = LabelKeys(mention.name for mentions in found for mention in mentions)
    candidates: dict[tuple[str, bool], _Candidate] = {}
    for index, mentions in enumerate(found):
        for mention in mentions:
            key = (keys.key(mention.name), has_corporate_suffix(mention.name))
            candidates.setdefault(key, _Candidate()).found.append((index, mention))
    return list(candidates.values())


def _has_relationships_to_read(typing_triples: list[dict[str, Any]]) -> bool:
    """Whether a chunk's typed individuals are two or more: relate asks nothing for fewer."""
    return len({triple["subject"]["label"] for triple in typing_triples}) > 1


def _chunk_failure(problems: list[tuple[str, Any]]) -> _ChunkFailure:
    """
    A failed chunk's reason, from everything that failed in it. It is written
    for the run's caller only when every part's reason was.
    """
    told = all(_reason_is_for_caller(failed) for _, failed in problems)
    return _ChunkFailure(
        failure_reason="; ".join(reason for reason, _ in problems),
        incomplete_response=told,
    )


def _failed_chunks_note(
    failures: list[tuple[Chunk, _ChunkFailure]], total: int, run_id: str
) -> str:
    """
    A sentence saying which chunks have a part that failed, so what they hold,
    or part of it, is missing. It leads the run's warnings and goes into its
    proposal, so it gives the first failure's reason only when that was written
    for the caller; any other stays in the run's failed_chunks.
    """
    numbers = ", ".join(str(chunk.index + 1) for chunk, _ in failures)
    noun = "chunk" if len(failures) == 1 else "chunks"
    first = failures[0][1]
    reason = (
        first.failure_reason
        if _reason_is_for_caller(first)
        else f"an internal error, recorded in failed_chunks of run {run_id}"
    )
    return (
        f"Extraction failed for {len(failures)} of {total} chunks ({noun} {numbers}), so what"
        f" they hold, or part of it, is missing. First failure: {reason}"
    )
