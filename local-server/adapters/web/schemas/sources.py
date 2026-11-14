"""Pydantic schemas for sources: files, web pages and text extraction reads (#1551)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.extraction.sources import (
    Source,
    SourceFailure,
    SourceHeading,
    SourceKind,
    SourceStatus,
)
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.source_extraction import LastExtraction, LastExtractionRun

_DATASET = Field(
    None,
    max_length=255,
    description="The dataset (identifier or id); defaults to the taxonomy's only dataset",
)


class SourceCreateRequest(BaseModel):
    """A web page to fetch (`url`), or pasted text (`title` and `text`)."""

    taxonomy_id: str = Field(..., min_length=1)
    dataset: Optional[str] = _DATASET
    url: Optional[str] = Field(None, description="An http or https page; one page, no crawling")
    title: Optional[str] = Field(None, max_length=500, description="Required with `text`")
    text: Optional[str] = Field(None, description="Pasted text")

    @model_validator(mode="after")
    def _one_kind(self) -> "SourceCreateRequest":
        if (self.url is None) == (self.text is None):
            raise ValueError("Give either `url` or `text`")
        if self.text is not None and not (self.title or "").strip():
            raise ValueError("Pasted text needs a `title`")
        return self


class SourceUploadForm(BaseModel):
    """A file upload (multipart/form-data): PDF, Markdown, HTML or plain text."""

    file: bytes = Field(..., json_schema_extra={"format": "binary"})
    taxonomy_id: str
    dataset: Optional[str] = _DATASET
    title: Optional[str] = Field(None, max_length=500, description="Defaults to the file's own")


class SourceHeadingSchema(BaseModel):
    """A heading in a source's text."""

    start: int = Field(..., description="Character offset in the source text")
    title: str
    level: int = Field(..., description="1 for a top-level heading")

    @classmethod
    def from_domain(cls, heading: SourceHeading) -> "SourceHeadingSchema":
        return cls(start=heading.start, title=heading.title, level=heading.level)


class LastExtractionRunSchema(BaseModel):
    """One run of a source's last extraction."""

    run_id: str
    pipeline: Literal["individual_extraction", "schema_extraction"]
    status: PipelineRunStatus
    items_done: Optional[int] = Field(None, description="Chunks done; null until reported")
    items_total: Optional[int] = Field(None, description="Chunks in all; null until known")
    stage: Optional[str] = Field(
        None,
        description=(
            "The stage the run last reported being in (find_then_type: find_mentions, "
            "type_mention, derive_relationships); null when its implementation reports none"
        ),
    )
    stage_done: Optional[int] = Field(
        None, description="How far through that stage the run is, in what the stage counts"
    )
    stage_total: Optional[int] = Field(None, description="What the stage counts, in all")
    proposal_id: Optional[str] = Field(None, description="The proposal the run produced")
    operations: Optional[int] = Field(None, description="How many operations that proposal has")

    @classmethod
    def from_domain(cls, run: LastExtractionRun) -> "LastExtractionRunSchema":
        return cls(
            run_id=run.run_id,
            pipeline=run.pipeline.value,  # type: ignore[arg-type]
            status=run.status,
            items_done=run.items_done,
            items_total=run.items_total,
            stage=run.stage,
            stage_done=run.stage_done,
            stage_total=run.stage_total,
            proposal_id=run.proposal_id,
            operations=run.operations,
        )


class LastExtractionSchema(BaseModel):
    """The runs a source's most recent extract call started."""

    started_at: datetime
    dataset_id: Optional[str] = None
    runs: list[LastExtractionRunSchema] = Field(
        ..., description="Individual extraction first, then schema extraction when asked for"
    )

    @classmethod
    def from_domain(cls, extraction: LastExtraction) -> "LastExtractionSchema":
        return cls(
            started_at=extraction.started_at,
            dataset_id=extraction.dataset_id,
            runs=[LastExtractionRunSchema.from_domain(run) for run in extraction.runs],
        )


class SourceExtractRequest(BaseModel):
    """Extract a source into proposals."""

    model_config = ConfigDict(populate_by_name=True)

    dataset: str = Field(
        ..., min_length=1, max_length=255, description="The dataset (identifier or id)"
    )
    implementation_id: Optional[str] = Field(
        None,
        max_length=255,
        description=(
            "The individual-extraction implementation that reads the source, one whose"
            " source_configuration is set (GET /api/pipelines/types/individual_extraction/"
            "implementations); default when omitted"
        ),
    )
    configuration_ref: Optional[str] = Field(
        None,
        max_length=255,
        description=(
            "An individual-extraction configuration of the implementation; the"
            " implementation's source_configuration when omitted"
        ),
    )
    pages: Optional[str] = Field(
        None, max_length=200, description='Pages to extract, such as "12-30" or "1-3, 7"'
    )
    schema_: bool = Field(
        False,
        alias="schema",
        description="Also run schema extraction, proposing classes and relationship types",
    )
    skip_boilerplate: bool = Field(
        True,
        description=(
            "Skip warranty, safety, legal and contact sections and copies in other"
            " languages; each run's output lists the skipped_sections"
        ),
    )


class SourceExtractRun(BaseModel):
    """A run an extract call started."""

    run_id: str
    pipeline: Literal["individual_extraction", "schema_extraction"]


class SourceExtractResponse(BaseModel):
    """The runs an extract call started, individual extraction first."""

    runs: list[SourceExtractRun]


class SourceResponse(BaseModel):
    """A source without its text (GET /api/sources/{id}/text returns that)."""

    id: str
    taxonomy_id: str
    dataset_id: str
    kind: SourceKind
    title: str
    origin: Optional[str] = Field(None, description="The URL or file name; null for pasted text")
    content_type: Optional[str] = None
    bytes: int
    pages: int
    chars: int
    page_starts: list[int] = Field(
        ..., description="Character offset where each page starts; page 1 starts at 0"
    )
    headings: list[SourceHeadingSchema]
    status: SourceStatus
    failure: Optional[SourceFailure] = None
    failure_detail: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    removed_at: Optional[datetime] = Field(
        None, description="Set once removed; a removed source still answers for provenance"
    )
    last_extraction: Optional[LastExtractionSchema] = Field(
        None,
        description=(
            "The runs of the most recent extract call, with their progress and proposals;"
            " null when never extracted"
        ),
    )

    @classmethod
    def from_domain(
        cls, source: Source, last_extraction: Optional[LastExtraction] = None
    ) -> "SourceResponse":
        return cls(
            last_extraction=(
                LastExtractionSchema.from_domain(last_extraction) if last_extraction else None
            ),
            id=source.id,
            taxonomy_id=source.taxonomy_id,
            dataset_id=source.dataset_id,
            kind=source.kind,
            title=source.title,
            origin=source.origin,
            content_type=source.content_type,
            bytes=source.bytes,
            pages=source.pages,
            chars=source.chars,
            page_starts=source.page_starts,
            headings=[SourceHeadingSchema.from_domain(h) for h in source.headings],
            status=source.status,
            failure=source.failure,
            failure_detail=source.failure_detail,
            created_at=source.created_at,
            updated_at=source.updated_at,
            removed_at=source.removed_at,
        )


class SourceTextResponse(BaseModel):
    """A source's text: one page, or all of it."""

    source_id: str
    page: Optional[int] = Field(None, description="The page (from 1); null for all the text")
    pages: int
    start: int = Field(..., description="Offset of `text` in the source's whole text")
    end: int
    text: str
