"""
The REST views of proposals and ontology entities.

The proposal routes, the bundle route and the chat/MCP tools all serialize
through these, so what an agent sees is what the UI sees.
"""

from typing import Any

from pydantic import BaseModel

from adapters.web.schemas.ontology import (
    AttributeDefinitionResponse,
    ClassResponse,
    ConceptSchemeResponse,
    IndividualResponse,
    PropertyDefinitionResponse,
    RelationshipResponse,
    TaxonomyResponse,
)
from adapters.web.schemas.proposals import ChangeProposalResponse
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ChangeProposal

# The REST response each kind is serialized with.
_REST_RESPONSES: dict[type, type[BaseModel]] = {
    Taxonomy: TaxonomyResponse,
    ConceptScheme: ConceptSchemeResponse,
    Class: ClassResponse,
    Individual: IndividualResponse,
    PropertyDefinition: PropertyDefinitionResponse,
    Relationship: RelationshipResponse,
    AttributeDefinition: AttributeDefinitionResponse,
}
# Display-only or bulky REST fields the tools leave out.
_EXCLUDED_REST_FIELDS = {"color", "embedding"}


def proposal_response(
    service: ProposalService, proposal: ChangeProposal, dry_run: bool = False
) -> ChangeProposalResponse:
    """
    The REST view of a proposal: stale flags, in-use blockers and replacement
    checks; for a dry run, each operation's auto-apply eligibility too (see
    ProposalService.auto_apply_operation_ids).
    """
    return ChangeProposalResponse.from_domain(
        proposal,
        service.stale_operation_ids(proposal),
        service.in_use_blockers(proposal),
        service.replacement_checks(proposal),
        service.auto_apply_operation_ids(proposal) if dry_run else None,
        service.type_usage(proposal),
    )


def rest_fields(entity: Any) -> dict[str, Any]:
    """An entity's fields as its REST response returns them, less color and embedding."""
    response = _REST_RESPONSES[type(entity)].model_validate(entity)
    return response.model_dump(mode="json", exclude=_EXCLUDED_REST_FIELDS)
