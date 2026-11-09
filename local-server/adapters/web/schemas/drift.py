"""Pydantic schemas for re-importing a mirrored taxonomy's source as a drift proposal."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from adapters.web.schemas.ontology import SourceRevisionSchema
from adapters.web.schemas.proposals import ChangeProposalResponse


class DrSpecDriftRequest(BaseModel):
    """Where the DR spec is, and whether to store anything."""

    model_config = ConfigDict(extra="forbid")

    spec_dir: str = Field(
        ...,
        min_length=1,
        description="The DR checkout's spec/ directory on this machine (holds dist/manifest.json)",
    )
    dry_run: bool = Field(True, description="Report the drift only; store nothing")


class DriftEntryResponse(BaseModel):
    """One entity that differs between the taxonomy and its source."""

    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(..., description="taxonomy, scheme, class, property or attribute")
    source_id: str = Field(
        ..., description="Its id in the source (a DR id; an attribute's is '<node id>#<name>')"
    )
    change: str = Field(
        ...,
        description=(
            "create (only in the source), update, move (it changed layer in the source)"
            " or delete (only in the taxonomy)"
        ),
    )
    entity_id: Optional[str] = Field(None, description="The taxonomy's entity (None for a create)")
    fields: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Each differing field's value: {name: {taxonomy, source}}",
    )


class DriftResponse(BaseModel):
    """The drift between a mirrored taxonomy and its source, and its proposal."""

    taxonomy_id: str = Field(..., description="The mirrored taxonomy")
    source_revision: Optional[SourceRevisionSchema] = Field(
        None, description="The source's revision as read"
    )
    dry_run: bool = Field(..., description="Nothing was stored")
    entries: list[DriftEntryResponse] = Field(..., description="What differs, by entity")
    proposal: Optional[ChangeProposalResponse] = Field(
        None,
        description=(
            "The proposal that removes the drift (not stored on a dry run); None when"
            " nothing differs"
        ),
    )
