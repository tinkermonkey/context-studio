"""
Integration test (#1365): relationship attributes changed through a proposal on
real SQLite are recorded with their old and new values, and reverting the
proposal restores them atomically.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource
from domain.versioning.proposals import OperationType as T
from tests.integration.versioning.test_proposal_service import parts, session_factory  # noqa: F401


def test_relationship_attribute_changes_revert_atomically(parts):  # noqa: F811
    """An attributes update, a create with attributes and a delete all revert."""
    ontology, repo, change_repo, service = parts
    taxonomy = ontology.create_taxonomy(title="House")
    kinds = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Kinds")
    activity = ontology.create_class(kinds.id, "Activity")
    resource = ontology.create_class(kinds.id, "Resource")
    requires = ontology.create_property_definition(
        "requires",
        "requires",
        external_references=[
            ExternalReference(
                source="house",
                identifier="requires",
                metadata={"edge_properties": ["quantity", "unit", "optional"]},
            )
        ],
    )
    hang = ontology.create_individual(activity.id, "Hang a picture")
    hooks = ontology.create_individual(resource.id, "Picture hooks")
    hammer = ontology.create_individual(resource.id, "Hammer")
    level = ontology.create_individual(resource.id, "Level")
    to_hooks = ontology.create_relationship(
        hang.id, hooks.id, requires.id, attributes={"quantity": 2, "unit": "each"}
    )
    to_level = ontology.create_relationship(
        hang.id, level.id, requires.id, attributes={"optional": True}
    )

    proposal = service.propose(
        taxonomy.id,
        "Kit",
        [
            OperationDraft(
                1, T.UPDATE, K.RELATIONSHIP, to_hooks.id, fields={"attributes": {"quantity": 3}}
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": hang.id,
                    "target_id": hammer.id,
                    "property_definition_id": requires.id,
                    "attributes": {"quantity": 1},
                },
            ),
            OperationDraft(3, T.DELETE, K.RELATIONSHIP, to_level.id),
        ],
        ProposalSource.BUNDLE,
    )
    applied = service.apply(proposal.id, [o.id for o in proposal.operations])
    assert [o.status for o in applied.operations] == [OperationStatus.APPLIED] * 3
    assert repo.get_relationship(to_hooks.id).attributes == {"quantity": 3}
    events = change_repo.get_changes(batch_run_id=proposal.id, limit=None).events
    [update] = [e for e in events if e.entity_id == to_hooks.id]
    assert update.previous_state == {"attributes": {"quantity": 2, "unit": "each"}}
    assert update.new_state == {"attributes": {"quantity": 3}}
    [created] = [e for e in events if e.entity_id == applied.operations[1].result_entity_id]
    assert created.new_state["attributes"] == {"quantity": 1}

    service.revert(proposal.id)

    assert repo.get_relationship(to_hooks.id).attributes == {"quantity": 2, "unit": "each"}
    assert repo.get_relationship(to_level.id).attributes == {"optional": True}
    assert repo.list_relationships(source_id=hang.id, target_id=hammer.id, limit=None) == []
