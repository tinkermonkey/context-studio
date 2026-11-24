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
from adapters.web.schemas.proposals import ChangeProposalResponse, ProposalLinkResponse
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.versioning.exceptions import ChangeProposalNotFoundError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    ChangeProposal,
    OperationStatus,
    ProposalLinkKind,
    ProposalStatus,
)

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
    service: ProposalService,
    proposal: ChangeProposal,
    dry_run: bool = False,
    with_usage: bool = True,
) -> ChangeProposalResponse:
    """
    The REST view of a proposal: stale flags, in-use blockers, replacement
    checks and domain/range mismatches; for a dry run, each operation's
    auto-apply eligibility too (see ProposalService.auto_apply_operation_ids).
    """
    blockers, usage = service.in_use(proposal, with_usage=with_usage)
    return ChangeProposalResponse.from_domain(
        proposal,
        service.stale_operation_ids(proposal),
        blockers,
        service.replacement_checks(proposal),
        service.auto_apply_operation_ids(proposal) if dry_run else None,
        usage,
        service.dataset_impacts(proposal) if with_usage else None,
        service.alternative_titles(proposal),
        service.domain_range_mismatches(proposal) if with_usage else None,
        links=proposal_links(service, proposal.id),
    )


# A link read from its target's side (#1624)
_INVERSE_KIND = {"supersedes": "superseded_by", "reverses": "reversed_by"}


def proposal_links(service: ProposalService, proposal_id: str) -> list[ProposalLinkResponse]:
    """The proposal's links to other proposals, seen from it, with each other's title and status."""
    links = []
    for link in service.links_of(proposal_id):
        outgoing = link.source_proposal_id == proposal_id
        other_id = link.target_proposal_id if outgoing else link.source_proposal_id
        try:
            other = service.get(other_id)
        except ChangeProposalNotFoundError:
            other = None
        # Seen from the original, its reversal's outcome: how many of the changes it planned
        # were applied ("38 of 41 changes reversed")
        counted = (
            other is not None
            and link.kind is ProposalLinkKind.REVERSES
            and not outgoing
            and other.status is ProposalStatus.DONE
        )
        links.append(
            ProposalLinkResponse(
                kind=link.kind.value if outgoing else _INVERSE_KIND[link.kind.value],
                proposal_id=other_id,
                title=other.title if other else None,
                status=other.status if other else None,
                created_at=link.created_at,
                note=link.note,
                operations_applied=(
                    sum(o.status is OperationStatus.APPLIED for o in other.operations)
                    if counted
                    else None
                ),
                operations_total=len(other.operations) if counted else None,
            )
        )
    return links


def rest_fields(entity: Any) -> dict[str, Any]:
    """An entity's fields as its REST response returns them, less color and embedding."""
    response = _REST_RESPONSES[type(entity)].model_validate(entity)
    return response.model_dump(mode="json", exclude=_EXCLUDED_REST_FIELDS)
