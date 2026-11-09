"""
Integration tests (#1461): a decided proposal's applied attribute definition
operations on DR node types export in `cs-dr-spec-changes/1`
(`attribute_changes`), keyed by the node's spec node id and the attribute's DR
name, with DR's JSON Schema keywords.

Built on the pinned DR spec snapshot (0.8.4), whose import brings in the
node attributes.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.chat.proposal_tools import build_proposal_tools
from adapters.interchange.dr_spec_changes import spec_changes_for
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import OperationStatus, ProposalSource
from scripts.dr_ontology_loader import DR_SOURCE, DR_TAXONOMY_IDENTIFIER
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import class_by_dr_id

spec_db = plan_tests.spec_db
parts = plan_tests.parts


def propose(repo, proposals, *drafts):
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return proposals.propose(taxonomy.id, "Attribute changes", list(drafts), ProposalSource.MCP)


def apply_all(proposals, proposal):
    applied = proposals.apply(proposal.id, [o.id for o in proposal.operations])
    for operation in applied.operations:
        assert operation.status is OperationStatus.APPLIED, operation.reason
    return applied


def some_attribute(repo, spec_node_id="api.operation"):
    """A DR attribute of the node type."""
    cls = class_by_dr_id(repo, spec_node_id)
    return repo.list_attribute_definitions(class_id=cls.id, limit=None)[0]


def dr_name(attr):
    return next(r.identifier for r in attr.external_references if r.source == DR_SOURCE)


def test_an_attribute_update_proposed_over_mcp_by_id_exports(parts):
    _, repo, proposals = parts
    target = some_attribute(repo)
    (propose_changes, *_) = build_proposal_tools(proposals, ProposalSource.MCP)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    outcome = propose_changes.run(
        {
            "taxonomy_id": taxonomy.id,
            "title": "Require it",
            "operations": [
                {
                    "seq": 1,
                    "op": "update",
                    "kind": "attribute",
                    "target_id": target.id,
                    "fields": {
                        "is_required": not target.is_required,
                        "description": "Updated over MCP.",
                    },
                }
            ],
        }
    )
    assert not outcome.is_error, outcome.content
    proposal = apply_all(proposals, proposals._get(json.loads(outcome.content)["id"]))
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    operation = proposal.operations[0]
    assert document["skipped"] == []
    assert document["attribute_changes"] == [
        {
            "seq": 1,
            "op_id": operation.id,
            "op": "update",
            "spec_node_id": "api.operation",
            "attribute": dr_name(target),
            "identifier": target.identifier,
            "set": {"is_required": not target.is_required, "description": "Updated over MCP."},
            "decided_at": recorded[operation.id].decided_at.isoformat(),
            "decided_by": "user",
        }
    ]


def test_an_update_exports_type_and_enum_and_a_cleared_enum_as_null(parts):
    _, repo, proposals = parts
    target = next(a for a in repo.list_attribute_definitions(limit=None) if a.allowed_values)
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="update",
                kind="attribute",
                target_id=target.id,
                fields={"allowed_values": None, "datatype": "integer"},
            ),
        ),
    )

    (change,) = spec_changes_for(proposal, repo)["attribute_changes"]

    assert change["set"] == {"datatype": "integer", "allowed_values": None}


def test_an_update_of_nothing_dr_holds_is_skipped(parts):
    _, repo, proposals = parts
    target = some_attribute(repo)
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1, op="update", kind="attribute", target_id=target.id, fields={"sort_order": 99}
            ),
        ),
    )

    document = spec_changes_for(proposal, repo)

    assert document["attribute_changes"] == []
    assert document["skipped"][0]["why"] == "it changes nothing DR's spec holds for an attribute"


def test_a_create_exports_its_whole_schema_with_the_reference_extras(parts):
    _, repo, proposals = parts
    operation_class = class_by_dr_id(repo, "api.operation")
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="create",
                kind="attribute",
                fields={
                    "class_id": operation_class.id,
                    "identifier": "timeout_seconds",
                    "title": "timeoutSeconds",
                    "datatype": "number",
                    "description": "How long the operation may take.",
                    "is_required": False,
                    "external_references": [
                        {
                            "source": DR_SOURCE,
                            "identifier": "timeoutSeconds",
                            "metadata": {"schema": {"minimum": 0}},
                        }
                    ],
                },
            ),
        ),
    )

    (change,) = spec_changes_for(proposal, repo)["attribute_changes"]

    assert change["op"] == "create"
    assert change["spec_node_id"] == "api.operation"
    assert change["attribute"] == "timeoutSeconds"
    assert change["identifier"] == "timeout_seconds"
    assert change["set"] == {
        "datatype": "number",
        "is_required": False,
        "description": "How long the operation may take.",
    }
    assert change["schema"] == {"minimum": 0}


def test_a_create_without_a_dr_reference_on_a_dr_node_type_is_refused(parts):
    _, repo, proposals = parts
    operation_class = class_by_dr_id(repo, "api.operation")
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="create",
                kind="attribute",
                fields={
                    "class_id": operation_class.id,
                    "identifier": "nameless",
                    "title": "nameless",
                    "datatype": "string",
                },
            ),
        ),
    )

    with pytest.raises(ValueError, match="without a DR reference"):
        spec_changes_for(proposal, repo)


def test_a_delete_exports_the_attribute_it_removed(parts):
    _, repo, proposals = parts
    target = some_attribute(repo)
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(seq=1, op="delete", kind="attribute", target_id=target.id),
        ),
    )

    (change,) = spec_changes_for(proposal, repo)["attribute_changes"]

    assert change["op"] == "delete"
    assert change["spec_node_id"] == "api.operation"
    assert change["attribute"] == dr_name(target)
    assert change["set"] == {}
