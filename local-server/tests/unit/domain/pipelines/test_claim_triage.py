"""The claim triage pipeline (#1520), over fake repositories and a fake decision model."""

import asyncio
from types import SimpleNamespace

import pytest

from domain.decision.value_objects import ChoiceQuestion, YesNoQuestion
from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.pipelines.claim_triage import ClaimTriageOrchestrator, ClaimTriageState
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.versioning.claims import (
    Claim,
    ClaimFilter,
    ClaimService,
    ClaimTriage,
    NoteSource,
    Validity,
)
from domain.versioning.proposals import OperationKind, OperationStatus, OperationType
from tests.fakes.fake_claim_repository import FakeClaimRepository
from tests.fakes.fake_decision_model import FakeDecisionModel
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

T = "t"


class FakeDecisionModels:
    def __init__(self, model):
        self.model = model
        self.asked = []

    def get(self, name=None):
        self.asked.append(name)
        return self.model


class RecordingWriter:
    def __init__(self):
        self.running = False
        self.progress = []

    def update_running_status(self, run_id, started_at):
        self.running = True

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))


class FakeProposals:
    """Open proposals with pending class updates, as list_proposals returns them."""

    def __init__(self, *operations):
        self.operations = list(operations)

    def list_proposals(self, taxonomy_id=None, status=None, limit=50, **_):
        return [SimpleNamespace(operations=self.operations)]


def pending_update(target_id, **fields):
    return SimpleNamespace(
        kind=OperationKind.CLASS,
        op=OperationType.UPDATE,
        status=OperationStatus.PENDING,
        target_id=target_id,
        fields=fields,
    )


@pytest.fixture()
def repo():
    repo = FakeOntologyRepository()
    repo.save_taxonomy(Taxonomy(id=T, title="DR", identifier="dr", description="Architecture"))
    repo.save_concept_scheme(ConceptScheme(id="api", taxonomy_id=T, title="API", identifier="api"))
    repo.save_concept_scheme(ConceptScheme(id="biz", taxonomy_id=T, title="Biz", identifier="biz"))
    for cid, scheme, ident, desc in (
        ("op", "api", "api_operation", "One callable endpoint operation"),
        ("ep", "api", "api_endpoint", "A URL path"),
        ("svc", "biz", "business_service", "A business service"),
    ):
        repo.save_class(
            Class(
                id=cid,
                taxonomy_id=T,
                concept_scheme_id=scheme,
                title=ident,
                identifier=ident,
                description=desc,
            )
        )
    repo.save_property_definition(
        PropertyDefinition(
            id="p1",
            identifier="operation_uses_endpoint",
            title="uses",
            domain_class_id="op",
            range_class_id="ep",
            canonical_predicate="uses",
        )
    )
    repo.save_attribute_definition(
        AttributeDefinition(
            id="a1", class_id="op", identifier="method", title="Method", datatype="string"
        )
    )
    return repo


@pytest.fixture()
def claims(repo):
    service = ClaimService(FakeClaimRepository(), repo)

    def claim(key, subject, *affected, text=None, unresolved=()):
        return Claim(
            taxonomy_id=T,
            key=key,
            text=text or f"Claim {key}",
            note_ref=key.split("#")[0],
            note_source=NoteSource.MAINTAINER,
            subject_id=subject,
            affected_ids=list(affected),
            unresolved_refs=list(unresolved),
            proposed_change="Clarify it",
        )

    service.submit(
        T,
        [
            claim("n-op#1", "op", "op", "ep", "p1", "a1", unresolved=["api.gone"]),
            claim("n-op#2", "op", "op"),
            claim("n-svc#1", "svc", "svc"),
        ],
    )
    return service


def make(repo, claims, model, proposals=None, writer=None, config=None):
    return ClaimTriageOrchestrator(
        ontology_repo=repo,
        decision_models=FakeDecisionModels(model),
        claim_service=claims,
        proposal_service=proposals,
        config=config,
        run_id="run-1",
        status_writer=writer,
    )


def run(orchestrator, scope=None, taxonomy_id=T):
    state = ClaimTriageState(
        run_id="run-1",
        pipeline_type=PipelineType.CLAIM_TRIAGE,
        input_data={"taxonomy_id": taxonomy_id, "scope": scope},
    )
    return asyncio.run(orchestrator.execute(state))


def keys_triaged(claims):
    return sorted(c.key for c in claims.list_claims(ClaimFilter(taxonomy_id=T, triaged=True)))


def model(**kwargs):
    defaults = {
        "choices": {"validity": "real_defect", "category": "type_overlap"},
        "scores": {"severity": 2, "fix_scope": 1},
        "cost_usd": 0.0005,
    }
    return FakeDecisionModel("clef", **{**defaults, **kwargs})


class TestTriage:
    def test_untriaged_claims_get_the_models_answers(self, repo, claims):
        writer = RecordingWriter()
        state = run(make(repo, claims, model(), writer=writer))

        assert keys_triaged(claims) == ["n-op#1", "n-op#2", "n-svc#1"]
        triage = claims.list_claims(ClaimFilter(taxonomy_id=T, keys=("n-op#1",)))[0].triage
        assert triage.validity is Validity.REAL_DEFECT
        assert triage.validity_probabilities["real_defect"] == pytest.approx(0.9)
        assert (triage.category, triage.severity, triage.fix_scope) == ("type_overlap", 2, 1)
        assert triage.addressed_by_proposal is None
        assert (triage.model, triage.run_id, triage.calibrated) == ("clef", "run-1", True)
        assert triage.cost_usd == pytest.approx(0.002)
        assert state.result["claims"] == 3
        assert state.result["validity"] == {"real_defect": 3}
        assert state.llm_metadata["cost_usd"] == pytest.approx(0.006)
        assert writer.running and writer.progress[0] == (0, 3) and writer.progress[-1] == (3, 3)

    def test_a_triaged_claim_is_skipped_by_default(self, repo, claims):
        run(make(repo, claims, model()), ["n-op#1"])
        fake = model()

        state = run(make(repo, claims, fake))

        assert state.result["claims"] == 2
        assert len(fake.calls) == 2

    def test_questions_follow_dr_and_the_configured_categories(self, repo, claims):
        fake = model(choices={"validity": "works_as_designed", "category": "naming"})
        run(
            make(repo, claims, fake, config={"categories": {"naming": "A naming issue"}}),
            ["n-svc#1"],
        )

        _, questions = fake.calls[0]
        assert set(questions) == {"validity", "category", "severity", "fix_scope"}
        assert isinstance(questions["validity"], ChoiceQuestion)
        assert set(questions["validity"].options()) == {v.value for v in Validity}
        assert set(questions["category"].options()) == {"naming"}
        assert len(questions["severity"].levels) == len(questions["fix_scope"].levels) == 4

    def test_the_configured_decision_model_is_used(self, repo, claims):
        models = FakeDecisionModels(model())
        orchestrator = ClaimTriageOrchestrator(
            repo, models, claims, config={"decision_model": "clef-flash"}
        )
        run(orchestrator, ["n-svc#1"])
        assert models.asked == ["clef-flash"]


class TestState:
    def test_the_state_names_the_claim_its_entities_and_the_evidence(self, repo, claims):
        fake = model()
        run(make(repo, claims, fake), ["n-op#1"])

        state, _ = fake.calls[0]
        assert "# Claim about the DR taxonomy" in state
        assert "Subject: api_operation" in state
        assert "Claim: Claim n-op#1" in state
        assert (
            "Affected: api_operation, api_endpoint, operation_uses_endpoint,"
            " api_operation.method" in state
        )
        assert "Also names (not found): api.gone" in state
        assert "Proposed change: Clarify it" in state
        assert "One callable endpoint operation" in state  # the subject's definition, via the pack
        assert "Proposed definition" not in state

    def test_a_pending_definition_is_shown_and_asked_about(self, repo, claims):
        fake = model(p_yes={"addressed_by_proposal": 0.8})
        proposals = FakeProposals(
            pending_update("op", description="An HTTP method on a path"),
            pending_update("svc", title="ignored: not this claim's subject"),
        )

        run(make(repo, claims, fake, proposals), ["n-op#2"])

        state, questions = fake.calls[0]
        assert "# Proposed definition (pending in an open proposal)" in state
        assert "description: An HTTP method on a path" in state
        assert isinstance(questions["addressed_by_proposal"], YesNoQuestion)
        triage = claims.list_claims(ClaimFilter(taxonomy_id=T, keys=("n-op#2",)))[0].triage
        assert triage.addressed_by_proposal == pytest.approx(0.8)

    def test_only_pending_class_updates_count(self, repo, claims):
        fake = model()
        applied = pending_update("op", description="Old")
        applied.status = OperationStatus.APPLIED
        run(make(repo, claims, fake, FakeProposals(applied)), ["n-op#2"])

        _, questions = fake.calls[0]
        assert "addressed_by_proposal" not in questions


class TestScope:
    @pytest.mark.parametrize(
        "scope, expected",
        [
            (None, ["n-op#1", "n-op#2", "n-svc#1"]),
            (["n-op#2"], ["n-op#2"]),
            ({"keys": ["n-op#1", "n-svc#1"]}, ["n-op#1", "n-svc#1"]),
            ({"note_ref": "n-op"}, ["n-op#1", "n-op#2"]),
            ({"subject_ids": ["svc"]}, ["n-svc#1"]),
            ({"concept_scheme_id": "api"}, ["n-op#1", "n-op#2"]),
            ({"concept_scheme_id": "api", "subject_ids": ["svc"]}, []),
        ],
    )
    def test_scope(self, repo, claims, scope, expected):
        run(make(repo, claims, model()), scope)
        assert keys_triaged(claims) == expected

    def test_untriaged_combines_with_other_scopes(self, repo, claims):
        run(make(repo, claims, model()), ["n-op#1"])
        fake = model()
        run(make(repo, claims, fake), {"note_ref": "n-op", "untriaged": True})
        assert len(fake.calls) == 1

    @pytest.mark.parametrize(
        "scope, message",
        [
            ("n-op#1", "scope must be"),
            ({"layer": "api"}, "scope must be"),
            ({"keys": "n-op#1"}, "keys must be a list"),
            ({"concept_scheme_id": "nope"}, "No scheme nope"),
        ],
    )
    def test_bad_scope_is_refused(self, repo, claims, scope, message):
        with pytest.raises(PipelineInputError, match=message):
            run(make(repo, claims, model()), scope)

    def test_taxonomy_is_required_and_must_exist(self, repo, claims):
        with pytest.raises(PipelineInputError, match="taxonomy_id"):
            run(make(repo, claims, model()), taxonomy_id="")
        with pytest.raises(PipelineInputError, match="No taxonomy"):
            run(make(repo, claims, model()), taxonomy_id="nope")


class TestFailures:
    def test_a_claim_the_model_fails_on_is_reported(self, repo, claims, monkeypatch):
        fake = model()
        real = fake.decide

        def flaky(state, questions):
            if "n-op#2" in state:
                raise RuntimeError("timed out")
            return real(state, questions)

        monkeypatch.setattr(fake, "decide", flaky)
        state = run(make(repo, claims, fake))

        assert state.result["status"] == "completed_with_warnings"
        assert state.result["claims"] == 2
        assert state.result["errors"] == ["n-op#2: timed out"]
        assert state.parse_warnings[-1] == {
            "stage": "triage",
            "claim": "n-op#2",
            "error": "timed out",
        }
        assert keys_triaged(claims) == ["n-op#1", "n-svc#1"]

    def test_a_run_the_model_answers_none_of_fails(self, repo, claims):
        with pytest.raises(PipelineExecutionError, match="answered none of 3 claims") as caught:
            run(make(repo, claims, model(fail=True)))
        assert caught.value.llm_metadata["failed_requests"] == 3

    def test_no_claims_in_scope_completes_with_nothing(self, repo, claims):
        state = run(make(repo, claims, model()), {"note_ref": "nobody"})
        assert state.result["claims"] == 0


def test_triage_answers_round_to_the_score_scale():
    from domain.pipelines.claim_triage.orchestrator import _level
    from domain.decision.value_objects import ScoreAnswer

    meta = {"model": "m", "latency_ms": 1.0}
    assert _level(ScoreAnswer(score=2.6, **meta)) == 3
    assert _level(ScoreAnswer(score=-0.2, **meta)) == 0
    assert _level(ScoreAnswer(score=None, **meta)) is None
    assert ClaimTriage(validity="judgment_call", model="m", severity=3).severity == 3
