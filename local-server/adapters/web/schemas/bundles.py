"""Pydantic schemas for importing a Context Studio bundle as a change proposal."""

from typing import Optional

from pydantic import BaseModel, Field

from adapters.web.schemas.proposals import ChangeProposalResponse


class BundleKindCounts(BaseModel):
    """What the import plans for one kind of entity."""

    created: int = Field(..., description="Entities the plan creates")
    updated: int = Field(..., description="Entities the plan updates or moves")
    deleted: int = Field(..., description="Entities the plan deletes (these wait for review)")
    unchanged: int = Field(..., description="Entities that already match the bundle")


class BundleImportResponse(BaseModel):
    """The plan for a bundle and the proposal made from it."""

    source: str = Field(..., description="The bundle's source")
    taxonomy_id: Optional[str] = Field(
        None, description="The bundle's taxonomy; None on a dry run that would create it"
    )
    taxonomy_created: bool = Field(
        ..., description="The import created the taxonomy (on a dry run: would create it)"
    )
    dry_run: bool = Field(..., description="Nothing was stored or changed")
    operation_count: int = Field(..., description="How many operations the plan has")
    counts: dict[str, BundleKindCounts] = Field(..., description="Per kind of entity")
    deletes: list[str] = Field(
        default_factory=list, description="The entities the plan deletes, described"
    )
    proposal: Optional[ChangeProposalResponse] = Field(
        None,
        description=(
            "The proposal (not stored on a dry run); None when the workspace already matches"
            " the bundle, or on a dry run that would create the taxonomy"
        ),
    )
