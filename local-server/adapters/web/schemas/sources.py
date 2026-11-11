"""Pydantic schemas for sources: files, web pages and text extraction reads (#1551)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from domain.extraction.sources import (
    Source,
    SourceFailure,
    SourceHeading,
    SourceKind,
    SourceStatus,
)

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

    @classmethod
    def from_domain(cls, source: Source) -> "SourceResponse":
        return cls(
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
