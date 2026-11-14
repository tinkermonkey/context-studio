"""
Extract a source into proposals (#1552).

One extract call starts an individual-extraction run over a ready source (and,
with `schema`, a schema-extraction run over the same text) in the background.
Each run reads the source chunk by chunk and ends in one change proposal for
review (see `source_proposals.py`); the runs record the source and the call in
their input_summary, so the source's last extraction can be shown while they
execute.

The REST route and the MCP tool both start extractions through this service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from domain.extraction.chunking import Heading, chunk_text, parse_page_range
from domain.extraction.exceptions import SourceNotReadyError
from domain.extraction.ports import SourceRepository
from domain.extraction.section_filter import NOTHING_LEFT, SKIP_INPUT, skipped_sections
from domain.extraction.sources import Source, SourceStatus
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineRun, PipelineRunStatus, PipelineType, SourceRun
from domain.pipelines.ports import PipelineRunSubmitter, SourceRunReader
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.requested_via import REQUESTED_VIA, RequestedVia, ensure_may_propose_to
from domain.versioning.ports import ChangeProposalRepository

# The individual-extraction implementation a source is extracted with when none is named
DEFAULT_IMPLEMENTATION = "default"
SCHEMA_IMPLEMENTATION = "default"
SCHEMA_CONFIGURATION = "schema-extraction-default"


@dataclass(frozen=True)
class LastExtractionRun:
    """
    One run of a source's last extraction.

    Attributes:
        run_id: The run
        pipeline: individual_extraction or schema_extraction
        status: Where it stands
        items_done, items_total: Chunks done, of how many (None until reported)
        proposal_id: The proposal it produced, once it has
        operations: How many operations that proposal has
    """

    run_id: str
    pipeline: PipelineType
    status: PipelineRunStatus
    items_done: int | None
    items_total: int | None
    proposal_id: str | None
    operations: int | None


@dataclass(frozen=True)
class LastExtraction:
    """
    The runs a source's most recent extract call started.

    Attributes:
        started_at: When the call started them
        dataset_id: The dataset it extracts into
        runs: Its runs, individual extraction first
    """

    started_at: datetime
    dataset_id: str | None
    runs: list[LastExtractionRun]


class SourceExtractionService:
    """Starts extraction runs on sources and reports each source's last extraction."""

    def __init__(
        self,
        sources: SourceRepository,
        ontology_repo: OntologyRepository,
        implementations: PipelineImplementationRegistry,
        configurations: PipelineConfigurationRegistry,
        submitter: PipelineRunSubmitter,
        runs: SourceRunReader,
        proposals: ChangeProposalRepository,
    ) -> None:
        self._sources = sources
        self._repo = ontology_repo
        self._implementations = implementations
        self._configurations = configurations
        self._submitter = submitter
        self._runs = runs
        self._proposals = proposals

    def extract(
        self,
        source_id: str,
        dataset: str,
        configuration_ref: str | None = None,
        pages: str | None = None,
        schema: bool = False,
        requested_via: RequestedVia = RequestedVia.API,
        skip_boilerplate: bool = True,
        implementation_id: str | None = None,
    ) -> list[PipelineRun]:
        """
        Start extracting a source: an individual-extraction run, and with
        `schema` a schema-extraction run too, each ending in its own proposal.

        Args:
            source_id: The source; it must be ready and not removed
            dataset: The dataset of the source's taxonomy the individuals go
                into (identifier or id)
            configuration_ref: The individual-extraction configuration, one of
                the implementation's; the implementation's own for sources
                when omitted. Its model is the run's model.
            pages: A page selection such as "12-30" or "1-3, 7"; all pages
                when omitted
            schema: Also suggest schema changes (classes and relationship types)
            requested_via: The entry point that asked, recorded on the runs
            skip_boilerplate: Leave out the source's warranty, safety, legal and
                contact sections and its copies in other languages (see
                domain/extraction/section_filter.py); false extracts everything
            implementation_id: The individual-extraction implementation that
                reads the source, one that can extract a source; `default`
                when omitted

        Returns:
            The pending runs, individual extraction first

        Raises:
            EntityNotFoundError: If the source, or the named dataset in its
                taxonomy, doesn't exist
            SourceNotReadyError: If the source is fetching, failed or removed
            ValueError: If the page selection is malformed, names pages the
                source lacks or holds no text (or only skipped sections, when
                skip_boilerplate), the implementation isn't an
                individual-extraction implementation that can extract a source,
                or the configuration isn't one of that implementation's
            PipelineInputError: If `schema` is asked of a taxonomy that mirrors
                an external source, other than by its client over MCP
        """
        source = self._ready_source(source_id)
        taxonomy = self._repo.get_taxonomy(source.taxonomy_id)
        if taxonomy is None:
            raise EntityNotFoundError("Taxonomy", source.taxonomy_id)
        dataset_id = self._dataset_id(source.taxonomy_id, dataset)
        pages = self._checked_pages(source, pages)
        if skip_boilerplate:
            self._check_text_left(source, pages)
        implementation_id = implementation_id or DEFAULT_IMPLEMENTATION
        individual_ref = configuration_ref or self._source_configuration(implementation_id)
        individual = self._configurations.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION, implementation_id, individual_ref
        )
        if individual is None:
            raise ValueError(
                f"{individual_ref!r} is not a configuration of the {implementation_id!r}"
                " individual-extraction implementation"
            )
        schema_config = None
        if schema:
            ensure_may_propose_to(taxonomy, {REQUESTED_VIA: requested_via.value})
            schema_config = self._configurations.get_latest(
                PipelineType.SCHEMA_EXTRACTION, SCHEMA_IMPLEMENTATION, SCHEMA_CONFIGURATION
            )
            if schema_config is None:
                raise ValueError(f"No schema-extraction configuration {SCHEMA_CONFIGURATION!r}")

        common: dict[str, Any] = {
            "source_id": source.id,
            "source_title": source.title,
            "dataset_id": dataset_id,
            "page_starts": list(source.page_starts),
            "headings": [
                {"start": h.start, "title": h.title, "level": h.level} for h in source.headings
            ],
            "pages": pages,
            SKIP_INPUT: skip_boilerplate,
            "extraction_id": str(uuid4()),
            # Orders extractions of the same pages, whatever order their runs finish in
            "extraction_started_at": datetime.now(timezone.utc).isoformat(),
            REQUESTED_VIA: requested_via.value,
        }
        runs = [
            self._submitter.submit(
                PipelineType.INDIVIDUAL_EXTRACTION,
                implementation_id,
                individual_ref,
                {
                    **common,
                    "text": source.text,
                    "ontology_id": taxonomy.id,
                    "ontology_name": taxonomy.title,
                    **_model(individual.config),
                },
            )
        ]
        if schema_config is not None:
            runs.append(
                self._submitter.submit(
                    PipelineType.SCHEMA_EXTRACTION,
                    SCHEMA_IMPLEMENTATION,
                    SCHEMA_CONFIGURATION,
                    {
                        **common,
                        "documents": [source.text],
                        "scope": taxonomy.id,
                        "scope_name": taxonomy.title,
                        **_model(schema_config.config),
                    },
                )
            )
        return runs

    def last_extractions(self, source_ids: Sequence[str]) -> dict[str, LastExtraction]:
        """
        Each source's last extraction: the runs of its most recent extract
        call, with the operation count of each run's proposal. Sources never
        extracted are left out. Two queries, whatever the number of sources.
        """
        by_source: dict[str, list[SourceRun]] = {}
        for run in self._runs.list_source_runs(list(source_ids)):
            by_source.setdefault(run.source_id, []).append(run)
        latest: dict[str, list[SourceRun]] = {}
        for source_id, runs in by_source.items():
            newest = max(runs, key=lambda r: r.created_at)
            latest[source_id] = (
                [r for r in runs if r.extraction_id == newest.extraction_id]
                if newest.extraction_id
                else [newest]
            )
        counts = self._proposals.operation_counts(
            [r.proposal_id for runs in latest.values() for r in runs if r.proposal_id]
        )
        order = {PipelineType.INDIVIDUAL_EXTRACTION: 0, PipelineType.SCHEMA_EXTRACTION: 1}
        return {
            source_id: LastExtraction(
                started_at=min(r.created_at for r in runs),
                dataset_id=runs[0].dataset_id,
                runs=[
                    LastExtractionRun(
                        run_id=r.run_id,
                        pipeline=r.pipeline_type,
                        status=r.status,
                        items_done=r.items_done,
                        items_total=r.items_total,
                        proposal_id=r.proposal_id,
                        operations=counts.get(r.proposal_id) if r.proposal_id else None,
                    )
                    for r in sorted(
                        runs, key=lambda r: (order.get(r.pipeline_type, 2), r.created_at)
                    )
                ],
            )
            for source_id, runs in latest.items()
        }

    def _source_configuration(self, implementation_id: str) -> str:
        """
        The configuration an implementation extracts a source with when none is named.

        Raises:
            ValueError: If it isn't an individual-extraction implementation
                that can extract a source
        """
        registered = self._implementations.list_by_type(PipelineType.INDIVIDUAL_EXTRACTION)
        configuration = getattr(registered.get(implementation_id), "SOURCE_CONFIGURATION", None)
        if configuration is None:
            able = sorted(
                impl_id
                for impl_id, impl in registered.items()
                if getattr(impl, "SOURCE_CONFIGURATION", None)
            )
            raise ValueError(
                f"{implementation_id!r} is not an individual-extraction implementation that"
                f" can extract a source (one of: {', '.join(able)})"
            )
        return str(configuration)

    def _ready_source(self, source_id: str) -> Source:
        source = self._sources.get(source_id)
        if source is None:
            raise EntityNotFoundError("Source", source_id)
        if source.removed_at is not None:
            raise SourceNotReadyError(source.id, "removed")
        if source.status is not SourceStatus.READY:
            raise SourceNotReadyError(source.id, source.status.value)
        return source

    def _dataset_id(self, taxonomy_id: str, dataset: str) -> str:
        """A dataset of the taxonomy, named by id or identifier."""
        for candidate in self._repo.list_datasets(taxonomy_id=taxonomy_id):
            if dataset in (candidate.id, candidate.identifier):
                return candidate.id
        raise EntityNotFoundError("Dataset", dataset)

    @staticmethod
    def _check_text_left(source: Source, pages: str | None) -> None:
        """
        Refuse an extraction that would skip every section of the selected pages.

        Raises:
            ValueError: If only skipped sections are left
        """
        skipped = skipped_sections(
            source.text,
            page_starts=source.page_starts,
            headings=[Heading(h.start, h.title, h.level) for h in source.headings],
            pages=pages,
        )
        if skipped and not chunk_text(
            source.text,
            page_starts=source.page_starts,
            pages=pages,
            skip=[(s.start, s.end) for s in skipped],
        ):
            raise ValueError(NOTHING_LEFT)

    @staticmethod
    def _checked_pages(source: Source, pages: str | None) -> str | None:
        """The page selection, checked against the source; None for all of it."""
        if pages is None or not pages.strip():
            return None
        last = max(last for _, last in parse_page_range(pages))
        if last > source.pages:
            noun = "page" if source.pages == 1 else "pages"
            raise ValueError(f"The source has {source.pages} {noun}, not {last}")
        if not chunk_text(source.text, page_starts=source.page_starts, pages=pages):
            raise ValueError(f"Pages {pages} hold no text")
        return normalized_pages(pages)


def normalized_pages(pages: str) -> str:
    """
    A page selection in one spelling, so the same pages always compare equal:
    ranges sorted and merged where they overlap or touch ("3, 1-2" -> "1-3").

    Raises:
        ValueError: If the selection is malformed
    """
    merged: list[list[int]] = []
    for first, last in sorted(parse_page_range(pages)):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return ", ".join(str(first) if first == last else f"{first}-{last}" for first, last in merged)


def _model(config: dict[str, Any]) -> dict[str, Any]:
    """The configuration's model as run input, as the run route takes it."""
    model = config.get("model")
    return {"model": model} if isinstance(model, str) and model else {}
