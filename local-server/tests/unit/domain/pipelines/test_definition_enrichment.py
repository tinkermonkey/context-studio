"""
Definition enrichment (#1517): the definition refinement pipeline's scoped mode
asks for each class's operational definition and proposes the changed fields
as one change proposal, over fakes.
"""

import asyncio
import json
import re

import pytest

from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.ports import LLMResponse
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from domain.versioning.exceptions import OperationError, ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationKind, OperationType, ProposalSource
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        result = RevertResult(run_id=run_id, events_reverted=0)
        if on_reverted is not None:
            on_reverted(result)
        return result


class ScriptedLLM:
    """Answers each 'Define this class: <label>' from a script; others fail."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def complete_async(self, system_prompt, user_prompt, model, **kwargs):
        label = re.search(r"Define this class: (\S+)", user_prompt).group(1)
        self.calls.append((label, system_prompt, user_prompt, model, kwargs))
        answer = self.answers[label]
        if isinstance(answer, Exception):
            raise answer
        content = answer if isinstance(answer, str) else json.dumps(answer)
        return LLMResponse(
            content=content,
            tokens_in=100,
            tokens_out=50,
            duration_ms=10.0,
            finish_reason="stop",
            model=model,
        )


class RefusingProposals:
    """Refuses the operations for the given class ids once, then proposes."""

    def __init__(self, proposals, refuse):
        self.proposals = proposals
        self.refuse = set(refuse)
        self.attempts = []

    def propose(self, operations, **kwargs):
        self.attempts.append([o.target_id for o in operations])
        refused = [o for o in operations if o.target_id in self.refuse]
        if refused:
            raise ProposalValidationError(
                [
                    OperationError(seq=o.seq, code="target_not_found", message="gone")
                    for o in refused
                ]
            )
        return self.proposals.propose(operations=operations, **kwargs)


class FailingProposals:
    def propose(self, **kwargs):
        raise RuntimeError("database is locked")


class RecordingWriter:
    def __init__(self):
        self.progress = []

    def update_running_status(self, run_id, started_at):
        return True

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))
        return True


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def proposals(ontology, repo):
    return ProposalService(FakeChangeProposalRepository(), ontology, repo, StubRevertService())


@pytest.fixture()
def dr(ontology):
    taxonomy = ontology.create_taxonomy(title="DR", identifier="dr", description="Architecture.")
    api = ontology.create_scheme(taxonomy.id, "API", identifier="api", description="OpenAPI.")
    biz = ontology.create_scheme(taxonomy.id, "Business", identifier="business")
    return {
        "taxonomy": taxonomy,
        "api": api,
        "operation": ontology.create_class(
            api.id, "Operation", identifier="api_operation", description="An operation."
        ),
        "endpoint": ontology.create_class(
            api.id, "Endpoint", identifier="api_endpoint", description="A URL path."
        ),
        "service": ontology.create_class(biz.id, "Service", identifier="business_service"),
    }


OPERATION_ANSWER = {
    "definition": "An HTTP method on a path that a client calls.",
    "distinguish_from": [
        {"type": "api_endpoint", "when": "it is the path, not the action"},
        {"type": "api_nothing", "when": "never"},
    ],
    "standard_reference": "OpenAPI 3.0 Operation Object",
    "evidence_signals": ["a paths.<path>.<method> entry", " ", "an operationId"],
    "notes": "The method attribute is missing.",
    "confidence": 0.8,
}


def make(repo, proposals, llm, writer=None, config=None):
    return DefinitionRefinementOrchestrator(
        llm_provider=llm,
        traversal=None,
        config=config or {"model": "m"},
        run_id="run-1",
        status_writer=writer,
        ontology_repo=repo,
        proposal_service=proposals,
    )


def run(orchestrator, taxonomy_id, scope=None, **extra):
    state = DefinitionRefinementState(
        run_id="run-1",
        pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
        input_data={"taxonomy_id": taxonomy_id, "scope": scope, **extra},
    )
    return asyncio.run(orchestrator.execute(state))


class TestEnrichment:
    def test_the_changes_become_one_proposal_of_class_updates(self, repo, proposals, dr):
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER})
        writer = RecordingWriter()

        state = run(make(repo, proposals, llm, writer), dr["taxonomy"].id, ["api_operation"])

        proposal = proposals.get(state.result["proposal_id"])
        assert proposal.source is ProposalSource.PIPELINE
        (operation,) = proposal.operations
        assert (operation.op, operation.kind) == (OperationType.UPDATE, OperationKind.CLASS)
        assert operation.target_id == dr["operation"].id
        assert operation.fields == {
            "description": "An HTTP method on a path that a client calls.",
            "distinguish_from": [
                {"class_id": dr["endpoint"].id, "when": "it is the path, not the action"}
            ],
            "standard_reference": "OpenAPI 3.0 Operation Object",
            "evidence_signals": ["a paths.<path>.<method> entry", "an operationId"],
        }
        assert operation.notes == "The method attribute is missing."
        assert operation.probability == pytest.approx(0.8)
        assert state.result["dropped_distinguish"] == ["api_operation -> api_nothing"]
        assert (state.result["classes"], state.result["proposed"]) == (1, 1)
        assert state.llm_metadata["tokens_in"] == 100
        assert writer.progress[0] == (0, 1) and writer.progress[-1] == (1, 1)
        # Nothing changed in the taxonomy itself
        assert repo.get_class(dr["operation"].id).description == "An operation."

    def test_the_prompt_carries_the_scheme_siblings_and_the_class(self, repo, proposals, dr):
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER})
        run(
            make(repo, proposals, llm, config={"model": "m-1"}),
            dr["taxonomy"].id,
            ["api_operation"],
        )

        _, system, user, model, kwargs = llm.calls[0]
        assert "# Scheme: api" in system and "OpenAPI." in system
        assert "- api_endpoint: A URL path." in system
        assert "business_service" not in system  # another scheme's class
        assert "Current definition: An operation." in user
        assert model == "m-1" and kwargs["response_format"] == "json"

    def test_a_class_whose_answer_changes_nothing_is_left_out(self, repo, proposals, dr):
        same = {
            "definition": "A URL path.",
            "distinguish_from": [],
            "standard_reference": None,
            "evidence_signals": [],
            "notes": "",
            "confidence": 0.9,
        }
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER, "api_endpoint": same})

        state = run(make(repo, proposals, llm), dr["taxonomy"].id, "api")

        assert (state.result["proposed"], state.result["unchanged"]) == (1, 1)
        assert len(proposals.get(state.result["proposal_id"]).operations) == 1

    def test_nothing_to_change_makes_no_proposal(self, repo, proposals, dr):
        same = {"definition": "A URL path.", "distinguish_from": [], "evidence_signals": []}
        state = run(
            make(repo, proposals, ScriptedLLM({"api_endpoint": same})),
            dr["taxonomy"].id,
            ["api_endpoint"],
        )
        assert state.result["proposal_id"] is None
        assert proposals.list_proposals() == []

    def test_a_class_without_an_answer_is_reported_and_the_rest_proposed(self, repo, proposals, dr):
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER, "api_endpoint": "not json"})

        state = run(make(repo, proposals, llm), dr["taxonomy"].id, "api")

        assert state.result["status"] == "completed_with_warnings"
        assert state.result["errors"] == ["api_endpoint: the answer is not JSON"]
        assert state.result["proposed"] == 1

    def test_an_answer_adds_to_the_operational_definition_but_never_clears_it(
        self, ontology, repo, proposals, dr
    ):
        ontology.update_class(
            dr["operation"].id,
            distinguish_from=[{"class_id": dr["endpoint"].id, "when": "old"}],
            evidence_signals=["an operationId"],
            standard_reference="OpenAPI 3.0",
        )
        service = ontology.create_class(dr["api"].id, "Webhook", identifier="api_webhook")
        answer = {
            "definition": "An operation.",
            "distinguish_from": [{"type": "api_webhook", "when": "the server calls out"}],
            "standard_reference": None,
            "evidence_signals": [],
        }

        state = run(
            make(repo, proposals, ScriptedLLM({"api_operation": answer})),
            dr["taxonomy"].id,
            ["api_operation"],
        )

        (operation,) = proposals.get(state.result["proposal_id"]).operations
        assert operation.fields == {
            "distinguish_from": [
                {"class_id": dr["endpoint"].id, "when": "old"},
                {"class_id": service.id, "when": "the server calls out"},
            ]
        }

    def test_a_reworded_distinction_replaces_the_one_for_the_same_class(
        self, ontology, repo, proposals, dr
    ):
        ontology.update_class(
            dr["operation"].id, distinguish_from=[{"class_id": dr["endpoint"].id, "when": "old"}]
        )
        answer = {
            "definition": "An operation.",
            "distinguish_from": [{"type": "api_endpoint", "when": "new"}],
        }

        state = run(
            make(repo, proposals, ScriptedLLM({"api_operation": answer})),
            dr["taxonomy"].id,
            ["api_operation"],
        )

        (operation,) = proposals.get(state.result["proposal_id"]).operations
        assert operation.fields == {
            "distinguish_from": [{"class_id": dr["endpoint"].id, "when": "new"}]
        }

    def test_the_prompt_lists_current_fields_and_relationships(self, ontology, repo, proposals, dr):
        ontology.update_class(dr["operation"].id, evidence_signals=["an operationId"])
        ontology.create_property_definition(
            "operation_on",
            "operation on",
            canonical_predicate="on",
            domain_class_id=dr["operation"].id,
            range_class_id=dr["endpoint"].id,
            taxonomy_id=dr["taxonomy"].id,
            create_missing_predicate=True,
        )
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER})

        run(make(repo, proposals, llm), dr["taxonomy"].id, ["api_operation"])

        user = llm.calls[0][2]
        assert "Current evidence_signals: an operationId" in user
        assert "Current distinguish_from: (none)" in user
        assert "(1 outgoing, 0 incoming)" in user
        assert "  api_operation --[on]--> api_endpoint" in user

    def test_refused_operations_are_dropped_and_the_rest_proposed(self, repo, proposals, dr):
        answers = {
            "api_operation": OPERATION_ANSWER,
            "api_endpoint": {"definition": "The path a client addresses."},
        }
        refusing = RefusingProposals(proposals, refuse=[dr["operation"].id])

        state = run(make(repo, refusing, ScriptedLLM(answers)), dr["taxonomy"].id, "api")

        assert len(refusing.attempts) == 2
        assert refusing.attempts[1] == [dr["endpoint"].id]
        (operation,) = proposals.get(state.result["proposal_id"]).operations
        assert operation.seq == 1 and operation.target_id == dr["endpoint"].id
        assert state.result["refused"] == [
            {"class": "api_operation", "error": "target_not_found: gone"}
        ]
        assert state.result["proposed"] == 1

    def test_a_failed_proposal_keeps_what_the_llm_calls_cost(self, repo, proposals, dr):
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER})
        with pytest.raises(PipelineExecutionError, match="database is locked") as raised:
            run(make(repo, FailingProposals(), llm), dr["taxonomy"].id, ["api_operation"])
        assert raised.value.llm_metadata["tokens_in"] == 100

    def test_an_unparseable_answer_is_a_request_not_a_failed_one(self, repo, proposals, dr):
        llm = ScriptedLLM({"api_operation": RuntimeError("down"), "api_endpoint": "not json"})
        with pytest.raises(PipelineExecutionError) as raised:
            run(make(repo, proposals, llm), dr["taxonomy"].id, "api")
        metadata = raised.value.llm_metadata
        assert (metadata["requests"], metadata["failed_requests"]) == (2, 1)
        assert metadata["tokens_in"] == 100

    def test_no_answers_at_all_fails_the_run(self, repo, proposals, dr):
        llm = ScriptedLLM(
            {"api_operation": RuntimeError("down"), "api_endpoint": RuntimeError("down")}
        )
        with pytest.raises(PipelineExecutionError, match="answered none of 2 classes"):
            run(make(repo, proposals, llm), dr["taxonomy"].id, "api")


class TestScope:
    @pytest.mark.parametrize(
        "scope, expected",
        [
            (None, {"api_operation", "api_endpoint", "business_service"}),
            ("api", {"api_operation", "api_endpoint"}),
            ({"concept_scheme_id": "business"}, {"business_service"}),
            (["api_endpoint"], {"api_endpoint"}),
            ({"class_ids": ["api_operation"]}, {"api_operation"}),
        ],
    )
    def test_scope(self, repo, proposals, dr, scope, expected):
        same = {"definition": "", "evidence_signals": []}
        llm = ScriptedLLM({k: same for k in ("api_operation", "api_endpoint", "business_service")})
        run(make(repo, proposals, llm), dr["taxonomy"].id, scope)
        assert {label for label, *_ in llm.calls} == expected

    @pytest.mark.parametrize(
        "scope, message",
        [
            ("nope", "No scheme nope"),
            (["nope"], "No class nope"),
            ({"layer": "api"}, "scope is"),
            (3, "scope is"),
        ],
    )
    def test_a_bad_scope_is_refused(self, repo, proposals, dr, scope, message):
        with pytest.raises(PipelineInputError, match=message):
            run(make(repo, proposals, ScriptedLLM({})), dr["taxonomy"].id, scope)

    def test_a_mirrored_taxonomy_runs_only_for_its_client_over_mcp(
        self, ontology, repo, proposals, dr
    ):
        ontology.set_taxonomy_mirrored(dr["taxonomy"].id, True)
        llm = ScriptedLLM({"api_operation": OPERATION_ANSWER})
        with pytest.raises(PipelineInputError, match="mirrors an external source"):
            run(make(repo, proposals, llm), dr["taxonomy"].id, ["api_operation"])

        state = run(
            make(repo, proposals, llm), dr["taxonomy"].id, ["api_operation"], requested_via="mcp"
        )
        assert state.result["proposal_id"] is not None
