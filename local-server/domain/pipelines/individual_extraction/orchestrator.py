"""
Individual Extraction pipeline orchestrator.

Wraps Wave A's ExtractionService.extract_triples() as a PipelineOrchestrator,
maintaining backward compatibility with existing extraction logic while
integrating with the new pipeline framework.

Pasted text is extracted in one call, as before. A source (input with
``source_id``, ``page_starts``, ``headings`` or ``pages``) is extracted chunk
by chunk: the chunks are the run's items, and the triples found in each are
merged over the whole source (see chunk_merge.py). Unless ``skip_boilerplate``
is false, a source's warranty, safety, legal and contact sections and its
copies in other languages are left out of the chunks (see
domain/extraction/section_filter.py); the result's ``skipped_sections`` and
``skipped_sections_by_reason`` say what was skipped. A run on a source
(``source_id``) ends in one change proposal of the merged triples when a
proposer is wired (see domain/pipelines/source_proposals.py); the run's
``proposal_id`` names it.

An extraction that fails (for one, an LLM response that stays incomplete) is
never read as "found nothing". Pasted text fails the run. A source carries on
with its other chunks: the result's ``failed_chunks`` lists the chunks that
failed, a warning and the proposal's rationale (or ``no_proposal_reason``) say
so, the run's proposal supersedes no other proposal of the source, and it fails
only when every chunk did. The exception is a failure every later chunk would
meet too (the provider refuses the model's requests: a rejected key, an unknown
model, a rate limit that turned every attempt away): the run stops there and
fails, saying so, with no later chunk tried. A provider failure that outlasts
its retries without being one of those (a server error, a timeout) fails its
chunk only. The error of a run that fails on its
extractions, or on proposing what they found, carries what its model calls cost
(``llm_metadata``). An ontology that doesn't exist is an input error.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from domain.extraction.chunking import Chunk, Heading, chunk_text
from domain.extraction.exceptions import InvalidInputError
from domain.extraction.prompts import INDIVIDUAL_EXTRACTION_STAGES
from domain.extraction.section_filter import (
    NOTHING_LEFT,
    SKIP_INPUT,
    SkippedSection,
    skip_note,
    skip_summary,
    skipped_sections,
)
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import (
    ExtractionFailedError,
    PipelineExecutionError,
    PipelineInputError,
)
from domain.pipelines.individual_extraction.chunk_merge import merge_chunk_triples
from domain.pipelines.orchestration.base import (
    MODEL_REQUIRED,
    PipelineOrchestrator,
    PipelineState,
)
from domain.pipelines.ports import ExtractionPort, LLMProvider, PipelineRunStatusWriter

if TYPE_CHECKING:
    from domain.pipelines.source_proposals import SourceProposer

_logger = logging.getLogger(__name__)

# Input keys that mark the text as a source to extract chunk by chunk
_SOURCE_KEYS = ("source_id", "page_starts", "headings", "pages")


@dataclass
class IndividualExtractionState(PipelineState):
    """
    State for individual extraction pipeline execution.

    Extends PipelineState with fields specific to text extraction.
    """

    source_text: str = ""
    source_text_hash: str = ""
    ontology_id: str = ""
    model: str = ""
    temperature: float = 0.0
    # The most output tokens one model call may produce; None leaves each stage its own limit
    max_tokens: int | None = None
    extracted_triples: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IndividualExtractionOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for individual text extraction operations.

    Wraps ExtractionService.extract_triples() to extract RDF triples from
    text scoped to a specific ontology. This is a minimal-refactoring wrapper
    that maintains Wave A's extraction logic while integrating with the new
    pipeline framework.

    Execution:
    - Validate inputs (text, ontology_id, model, and a source's chunking inputs)
    - Pasted text: call ExtractionService.extract_triples() once
    - A source: call it once per chunk, reporting progress per chunk and
      stopping at the next chunk when the run is cancelled, then merge
    - Populate PipelineRun.output_summary with triples, warnings and metadata
    - A failed extraction fails the run (pasted text, every chunk of a source,
      or a chunk refused as every later one would be) or is reported in
      ``failed_chunks`` (some chunks of a source)
    """

    # The LLM stages and their default prompts (owned by the extraction
    # context); a configuration's ``stage_prompts`` override them.
    STAGE_PROMPTS = INDIVIDUAL_EXTRACTION_STAGES

    # It reads a source chunk by chunk and proposes what it finds
    EXTRACTS_SOURCES = True

    def __init__(
        self,
        llm_provider: LLMProvider,
        extraction_service: ExtractionPort,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
        config: dict[str, Any] | None = None,
        proposer: "SourceProposer | None" = None,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            llm_provider: Port implementation for LLM completions
            extraction_service: Port implementation for extraction logic
            run_id: Pipeline run ID for writing RUNNING status
            status_writer: Optional port for writing run status to persistence
            config: The run's configuration; its ``stage_prompts`` override the
                default stage prompts
            proposer: Proposes a run on a source as one change proposal; without
                one, a source run proposes nothing
        """
        super().__init__(llm_provider, run_id, status_writer)
        self._extraction_service = extraction_service
        self._stage_prompts = (config or {}).get("stage_prompts")
        self._proposer = proposer

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the individual extraction pipeline.

        Args:
            state: IndividualExtractionState with input_data containing:
                - text: Source text to extract from
                - ontology_id: Target ontology identifier
                - model: LLM model name
                - temperature: Sampling temperature (0.0–2.0)
                - max_tokens: The most output tokens one model call may produce
                  (model, temperature and max_tokens are the run's
                  configuration's unless the caller names its own; see
                  domain/pipelines/selection.py)
                - dataset_id: Optional dataset recognition is scoped to
                - source_id, page_starts, headings, pages: Optional; any of
                  them extracts the text chunk by chunk (see the registry's
                  input contract)
                - skip_boilerplate: Optional, true by default; false extracts a
                  source's boilerplate sections and other-language copies too

        Returns:
            Updated IndividualExtractionState with extracted triples and metadata

        Raises:
            PipelineInputError: If required input fields are missing or invalid,
                or no ontology has ontology_id
            ExtractionFailedError: If the extraction failed (pasted text, or
                every chunk of a source) because an LLM response stayed
                incomplete or the provider did not answer, or a source's run
                stopped at a chunk the provider refused as it would every later
                one; the message is the reason
            PipelineExecutionError: If it failed for another reason, or
                anything else fails. The llm_metadata of a failed extraction's
                or a failed proposal's error is what the run's model calls cost
        """
        self._write_running_status()

        # Cast to subclass for type checking
        if not isinstance(state, IndividualExtractionState):
            state = IndividualExtractionState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        # Extract input parameters
        text = state.input_data.get("text", "")
        ontology_id = state.input_data.get("ontology_id", "")
        model = state.input_data.get("model", "")
        temperature = state.input_data.get("temperature") or 0.0
        max_tokens = state.input_data.get("max_tokens")

        # Validate required inputs
        if not text or not text.strip():
            exc = PipelineInputError("text is required and cannot be empty")
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc
        if not ontology_id:
            exc = PipelineInputError("ontology_id is required")
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc
        if not model:
            exc = PipelineInputError(MODEL_REQUIRED)
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc

        is_source = any(state.input_data.get(key) is not None for key in _SOURCE_KEYS)
        page_starts: list[int] = []
        chunks: list[Chunk] = []
        skipped: list[SkippedSection] = []
        if is_source:
            page_starts = _page_starts(state.input_data.get("page_starts"))
            headings = _headings(state.input_data.get("headings"))
            pages = _pages(state.input_data.get("pages"))
            try:
                if _skip_boilerplate(state.input_data):
                    skipped = skipped_sections(
                        text, page_starts=page_starts, headings=headings, pages=pages
                    )
                chunks = chunk_text(
                    text,
                    page_starts=page_starts,
                    headings=headings,
                    pages=pages,
                    skip=[(s.start, s.end) for s in skipped],
                )
            except ValueError as error:
                raise PipelineInputError(str(error)) from error
            if not chunks:
                raise PipelineInputError(
                    NOTHING_LEFT if skipped else "The selected pages hold no text"
                )

        # Update state with input data
        state = replace(
            state,
            source_text=text,
            source_text_hash=hashlib.sha256(text.encode()).hexdigest(),
            ontology_id=ontology_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            current_status=PipelineRunStatus.RUNNING,
        )

        try:
            outcome_keys: dict[str, Any] = {}
            if is_source:
                triples, warnings, metadata, unread = await self._extract_by_chunk(
                    state, chunks, page_starts
                )
                if unread:
                    warnings = [unread, *warnings]
                    outcome_keys = {
                        "failed_chunks": [c for c in metadata["chunks"] if c["failure_reason"]]
                    }
                if skipped:
                    warnings = [skip_note(skipped), *warnings]
                    outcome_keys = {**outcome_keys, **skip_summary(skipped, text, page_starts)}
                if self._proposer is not None and state.input_data.get("source_id"):
                    try:
                        outcome = self._proposer.propose_individuals(
                            state.run_id, state.input_data, triples, unread
                        )
                    except Exception as exc:
                        raise PipelineExecutionError(
                            f"Proposing the extracted candidates failed: {exc}",
                            llm_metadata={k: metadata[k] for k in _SPENT_KEYS},
                        ) from exc
                    warnings = [*warnings, *outcome.warnings]
                    outcome_keys = {**outcome_keys, **outcome.to_json()}
            else:
                triples, warnings, metadata = await self._extract_text(state)

            # Populate result state
            state = replace(
                state,
                extracted_triples=triples,
                warnings=warnings,
                metadata=metadata,
                result={
                    "triples": triples,
                    "warnings": warnings,
                    "metadata": metadata,
                    **outcome_keys,
                },
                current_status=PipelineRunStatus.COMPLETED,
            )

        except PipelineInputError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except InvalidInputError as exc:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise PipelineInputError(str(exc)) from exc
        except PipelineExecutionError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except Exception as exc:
            _logger.error(f"Unexpected error during individual extraction: {exc}", exc_info=True)
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": "Individual extraction encountered an unexpected error"},
            )
            raise PipelineExecutionError(
                "Individual extraction encountered an unexpected error"
            ) from exc

        return state

    async def _extract_text(
        self, state: IndividualExtractionState
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        """
        Extract a pasted text in one call.

        Returns:
            (triples, warnings, metadata)

        Raises:
            ExtractionFailedError: If the extraction failed because an LLM
                response stayed incomplete or the provider did not answer
            PipelineExecutionError: If it failed for another reason
        """
        result = self._extraction_service.extract_triples(
            text=state.source_text,
            ontology_id=state.ontology_id,
            model=state.model,
            temperature=state.temperature,
            stage_prompts=self._stage_prompts,
            dataset_id=state.input_data.get("dataset_id"),
            max_tokens=state.max_tokens,
        )
        if result.failure_reason:
            raise _failure(
                [result], f"Extraction failed: {result.failure_reason}", state.model, [result]
            )
        return result.triples, result.warnings, result.metadata

    async def _extract_by_chunk(
        self, state: IndividualExtractionState, chunks: list[Chunk], page_starts: list[int]
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any], str | None]:
        """
        Extract each chunk in turn, then merge the triples over the whole text.

        Progress is reported per chunk. Each chunk starts at an await, so a
        cancelled run stops before its next chunk. A chunk whose extraction
        failed adds no triples and says why in its summary's failure_reason;
        when it failed as every later chunk would too (the provider refuses the
        model's requests), the run stops there.

        Returns:
            (merged triples, warnings, metadata, a sentence saying which chunks
            failed or None when none did)

        Raises:
            ExtractionFailedError: If the extraction of every chunk failed
                because an LLM response stayed incomplete or the provider did
                not answer, or the provider refused a chunk before the last as
                it would every later one
            PipelineExecutionError: If every chunk failed, some for another reason
        """
        total = len(chunks)
        self._report_progress(0, total)
        chunk_triples: list[tuple[Chunk, list[dict[str, Any]]]] = []
        warnings: list[str] = []
        chunk_summaries: list[dict[str, Any]] = []
        failures: list[tuple[Chunk, Any]] = []
        results: list[Any] = []
        for done, chunk in enumerate(chunks, start=1):
            await asyncio.sleep(0)  # a cancelled run stops here
            result = self._extraction_service.extract_triples(
                text=state.source_text[chunk.start : chunk.end],
                ontology_id=state.ontology_id,
                model=state.model,
                temperature=state.temperature,
                stage_prompts=self._stage_prompts,
                dataset_id=state.input_data.get("dataset_id"),
                max_tokens=state.max_tokens,
            )
            results.append(result)
            if result.failure_reason and result.provider_refused and done < total:
                raise _failure(
                    [result],
                    f"Extraction stopped at chunk {done} of {total}, leaving {total - done}"
                    " untried, because every later chunk would fail the same way:"
                    f" {result.failure_reason}",
                    state.model,
                    results,
                )
            chunk_triples.append((chunk, result.triples))
            if result.failure_reason:
                failures.append((chunk, result))
            warnings.extend(f"Chunk {done} of {total}: {warning}" for warning in result.warnings)
            chunk_summaries.append(
                {
                    "index": chunk.index,
                    "start": chunk.start,
                    "end": chunk.end,
                    "page_first": chunk.page_first,
                    "page_last": chunk.page_last,
                    "heading": chunk.heading,
                    "triples": len(result.triples),
                    "failure_reason": result.failure_reason,
                }
            )
            self._report_progress(done, total)

        if len(failures) == total:
            raise _failure(
                results,
                f"Extraction failed for every chunk ({total}): {failures[0][1].failure_reason}",
                state.model,
                results,
            )

        metadata = {
            **_spent(state.model, results),
            "source_id": state.input_data.get("source_id"),
            "pages": state.input_data.get("pages"),
            "chunks": chunk_summaries,
        }
        unread = _failed_chunks_note(failures, total, state.run_id) if failures else None
        return merge_chunk_triples(chunk_triples, page_starts), warnings, metadata, unread


def _failure(
    failed: list[Any], message: str, model: str, results: list[Any]
) -> PipelineExecutionError:
    """
    The error for failed extractions: one whose message its caller is told when
    the reason of every one of them was written for the caller, since any other
    reason may quote an internal error. It carries what the run's extractions
    (``results``: the failed ones and any that were read) cost.
    """
    told = all(_reason_is_for_caller(result) for result in failed)
    error = ExtractionFailedError if told else PipelineExecutionError
    return error(message, llm_metadata=_spent(model, results))


def _reason_is_for_caller(result: Any) -> bool:
    """
    Whether a failed extraction's reason was written for the run's caller: an
    LLM response that stayed incomplete, or an LLM provider that did not answer
    (whether or not it would answer for another text). Any other reason may
    quote an internal error.
    """
    return bool(result.incomplete_response or result.provider_failed or result.provider_refused)


# The keys of a run's metadata that say what its model calls cost
_SPENT_KEYS = ("model", "tokens_used", "duration_ms")


def _spent(model: str, results: list[Any]) -> dict[str, Any]:
    """What the extractions' model calls cost, those of failed extractions too."""
    return {
        "model": model,
        "tokens_used": sum(int(r.metadata.get("tokens_used") or 0) for r in results),
        "duration_ms": sum(int(r.metadata.get("duration_ms") or 0) for r in results),
    }


def _failed_chunks_note(failures: list[tuple[Chunk, Any]], total: int, run_id: str) -> str:
    """
    A sentence saying which chunks' extraction failed, so what they hold is
    missing. It leads the run's warnings and goes into its proposal, which
    reviewers and clients read, so it gives the first failure's reason only
    when that was written for the caller: any other reason may quote an
    internal error, and stays in the run's failed_chunks.
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
        f" they hold is missing. First failure: {reason}"
    )


def _page_starts(value: Any) -> list[int]:
    """Validate ``page_starts``: offsets at which each page starts."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(start, int) and not isinstance(start, bool) and start >= 0 for start in value
    ):
        raise PipelineInputError("page_starts must be a list of non-negative character offsets")
    if any(later < earlier for earlier, later in zip(value, value[1:])):
        raise PipelineInputError("page_starts must never decrease")
    return value


def _headings(value: Any) -> list[Heading]:
    """Validate ``headings``: ``[{start, title, level?}]``."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise PipelineInputError("headings must be a list of {start, title, level}")
    headings: list[Heading] = []
    for item in value:
        start = item.get("start") if isinstance(item, dict) else None
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise PipelineInputError("each heading needs a non-negative start offset")
        level = item.get("level")
        headings.append(
            Heading(
                start=start,
                title=str(item.get("title") or ""),
                level=level if isinstance(level, int) else 1,
            )
        )
    return headings


def _skip_boilerplate(input_data: dict[str, Any]) -> bool:
    """Validate ``skip_boilerplate``: true unless given as false."""
    value = input_data.get(SKIP_INPUT)
    if value is None:
        return True
    if not isinstance(value, bool):
        raise PipelineInputError(f"{SKIP_INPUT} must be true or false")
    return value


def _pages(value: Any) -> str | None:
    """Validate ``pages``: a page selection such as "12-30"."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        raise PipelineInputError('pages must be a page range such as "12-30"')
    return value
