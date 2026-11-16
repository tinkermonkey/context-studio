"""The notes-to-claims pipeline (#1519), over fake repositories and a fake LLM."""

import asyncio
from datetime import datetime, timezone

import pytest

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.notes_to_claims import NotesToClaimsOrchestrator, NotesToClaimsState
from domain.pipelines.notes_to_claims.prompt import parse_split
from domain.pipelines.requested_via import REQUESTED_VIA, RequestedVia
from domain.versioning.claims import (
    Claim,
    ClaimFilter,
    ClaimService,
    ClaimVerdict,
    NoteSource,
)
from domain.versioning.exceptions import ChangeProposalNotFoundError
from domain.versioning.gold import DecisionKind, ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationType,
    ProposalSource,
    ProposedOperation,
)
from tests.fakes.fake_claim_repository import FakeClaimRepository
from tests.fakes.fake_note_splitter import FakeNoteSplitter
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

MODEL = "splitting-model"

T = "t"
WHEN = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def split(text, *affected, category="missing_attribute", change="Add it."):
    return {
        "text": text,
        "category": category,
        "affected_ids": list(affected),
        "proposed_change": change,
    }


class RecordingWriter:
    def __init__(self):
        self.running = False
        self.progress = []

    def update_running_status(self, run_id, started_at):
        self.running = True

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))


class FakeProposals:
    def __init__(self, proposal=None, decisions=()):
        self.proposal = proposal
        self.decisions = list(decisions)
        self.filters = []

    def get(self, proposal_id):
        if self.proposal is None or self.proposal.id != proposal_id:
            raise ChangeProposalNotFoundError(proposal_id)
        return self.proposal

    def list_decisions(self, filters, limit=None, offset=0):
        self.filters.append(filters)
        return [
            d
            for d in self.decisions
            if (filters.proposal_id is None or d.proposal_id == filters.proposal_id)
            and (filters.decided_from is None or d.decided_at >= filters.decided_from)
        ]


@pytest.fixture()
def repo():
    repo = FakeOntologyRepository()
    repo.save_taxonomy(Taxonomy(id=T, title="DR", identifier="dr", description="Architecture"))
    repo.save_taxonomy(Taxonomy(id="t2", title="Other", identifier="other"))
    repo.save_concept_scheme(ConceptScheme(id="api", taxonomy_id=T, title="API", identifier="api"))
    repo.save_concept_scheme(
        ConceptScheme(id="o", taxonomy_id="t2", title="O", identifier="other_scheme")
    )
    for cid, scheme, taxonomy, ident, desc in (
        ("cb", "api", T, "api_callback", "A callback on an operation"),
        ("srv", "api", T, "api_server", "A server"),
        ("pi", "api", T, "api_pathitem", "A path item"),
        ("far", "o", "t2", "far_away", "Elsewhere"),
    ):
        repo.save_class(
            Class(
                id=cid,
                taxonomy_id=taxonomy,
                concept_scheme_id=scheme,
                title=ident.replace("_", " ").title(),
                identifier=ident,
                description=desc,
                distinguish_from=(
                    [{"class_id": "srv", "when": "it names a host"}] if cid == "cb" else []
                ),
                standard_reference="OpenAPI 3.1" if cid == "cb" else None,
            )
        )
    repo.save_property_definition(
        PropertyDefinition(
            id="p-uses",
            identifier="callback_uses_server",
            title="uses",
            domain_class_id="cb",
            range_class_id="srv",
            canonical_predicate="uses",
        )
    )
    repo.save_property_definition(
        PropertyDefinition(
            id="p-agg",
            identifier="pathitem_aggregates_callback",
            title="aggregates",
            domain_class_id="pi",
            range_class_id="cb",
            canonical_predicate="aggregates",
        )
    )
    repo.save_attribute_definition(
        AttributeDefinition(
            id="a-expr",
            class_id="cb",
            identifier="expression",
            title="Expression",
            datatype="string",
            is_required=True,
            description="The runtime expression",
        )
    )
    return repo


@pytest.fixture()
def claims(repo):
    return ClaimService(FakeClaimRepository(), repo)


def make(repo, claims, llm, proposals=None, writer=None, config=None):
    return NotesToClaimsOrchestrator(
        llm_provider=llm,
        ontology_repo=repo,
        claim_service=claims,
        proposal_service=proposals,
        # The run's model is its configuration's: the orchestrator has none of its own
        config={"model": MODEL, **(config or {})},
        run_id="run-1",
        status_writer=writer,
    )


def run(orchestrator, scope, taxonomy_id=T, **input_data):
    state = NotesToClaimsState(
        run_id="run-1",
        pipeline_type=PipelineType.NOTES_TO_CLAIMS,
        input_data={"taxonomy_id": taxonomy_id, "scope": scope, **input_data},
    )
    return asyncio.run(orchestrator.execute(state))


def stored(claims, **filters):
    return {c.key: c for c in claims.list_claims(ClaimFilter(taxonomy_id=T, **filters))}


CALLBACK_NOTE = (
    "The callback's map-key name has no attribute. The 'uses api.server' relationship is dubious."
)


NOTES = {"notes": [{"ref": "node:api.callback", "subject": "api_callback", "text": CALLBACK_NOTE}]}
ONE_CLAIM = {"map-key": [split("api_callback has no attribute.", "api_callback")]}


class TestRunParameters:
    """The split's model, temperature and output limit are the run's."""

    def test_the_configurations_are_used(self, repo, claims):
        llm = FakeNoteSplitter(ONE_CLAIM)

        state = run(make(repo, claims, llm, config={"temperature": 0.2, "max_tokens": 3000}), NOTES)

        (call,) = llm.calls
        assert (call["model"], call["temperature"], call["max_tokens"]) == (MODEL, 0.2, 3000)
        assert state.llm_metadata["model"] == MODEL

    def test_what_the_runs_input_names_wins(self, repo, claims):
        llm = FakeNoteSplitter(ONE_CLAIM)

        state = run(make(repo, claims, llm), NOTES, model="named", temperature=0.5, max_tokens=900)

        (call,) = llm.calls
        assert (call["model"], call["temperature"], call["max_tokens"]) == ("named", 0.5, 900)
        assert state.llm_metadata["model"] == "named"

    def test_no_limit_named_is_the_stages_own(self, repo, claims):
        llm = FakeNoteSplitter(ONE_CLAIM)

        run(make(repo, claims, llm), NOTES)

        assert llm.calls[0]["max_tokens"] == 4000

    def test_it_has_no_model_of_its_own(self, repo, claims):
        orchestrator = NotesToClaimsOrchestrator(
            llm_provider=FakeNoteSplitter(ONE_CLAIM), ontology_repo=repo, claim_service=claims
        )

        with pytest.raises(PipelineInputError, match="model is required"):
            run(orchestrator, NOTES)


class TestSplit:
    def test_client_notes_become_resolved_claims(self, repo, claims):
        llm = FakeNoteSplitter(
            {
                "map-key": [
                    split("api_callback has no attribute for its map-key name.", "api_callback"),
                    split(
                        "The uses relationship from api_callback to api_server is dubious.",
                        "callback_uses_server",
                        "api_callback.expression",
                        "api.callback.uses.api.server",
                        "far_away",
                        category="not_a_category",
                        change="",
                    ),
                ]
            }
        )
        writer = RecordingWriter()
        state = run(
            make(repo, claims, llm, writer=writer),
            {
                "notes": [
                    {"ref": "node:api.callback", "subject": "api_callback", "text": CALLBACK_NOTE}
                ]
            },
        )

        got = stored(claims)
        assert sorted(got) == ["node:api.callback#1", "node:api.callback#2"]
        first, second = got["node:api.callback#1"], got["node:api.callback#2"]
        assert first.text == "api_callback has no attribute for its map-key name."
        assert (first.note_ref, first.note_source) == ("node:api.callback", NoteSource.MAINTAINER)
        assert (first.note_text, first.subject_id) == (CALLBACK_NOTE, "cb")
        assert (first.category_hint, first.proposed_change) == ("missing_attribute", "Add it.")
        assert first.affected_ids == ["cb"] and first.unresolved_refs == []
        assert first.source_run_id == "run-1"
        # Relationship type and attribute by identifier; DR ids and other taxonomies don't resolve
        assert second.affected_ids == ["p-uses", "a-expr"]
        assert second.unresolved_refs == ["api.callback.uses.api.server", "far_away"]
        assert (second.category_hint, second.proposed_change) == (None, None)
        assert state.result["notes"] == 1
        assert state.result["claims"] == 2
        assert state.result["unresolved_refs"] == 2
        assert state.result["status"] == "completed"
        assert state.llm_metadata["tokens_in"] == 100
        assert state.llm_metadata["model"] == MODEL
        assert writer.running and writer.progress == [(0, 1), (1, 1)]

    def test_the_prompt_is_dr_split_notes_with_context_studio_identifiers(self, repo, claims):
        llm = FakeNoteSplitter({"map-key": []})
        run(
            make(repo, claims, llm),
            {"notes": [{"ref": "n", "subject": "cb", "text": CALLBACK_NOTE}]},
        )

        call = llm.calls[0]
        assert "split a maintainer's or reviewer's note into atomic claims" in call["system"]
        assert "- missing_attribute: The type cannot capture" in call["system"]
        assert call["response_format"] == "json"
        user = call["user"]
        assert user.startswith("Note about the class api_callback (scheme api):")
        assert f'"""{CALLBACK_NOTE}"""' in user
        assert "Context (for resolving names only):\nCurrent schema:" in user
        assert "api_callback (Api Callback): A callback on an operation" in user
        assert "  - expression (required): string — The runtime expression" in user
        assert "Distinctions: use api_server when it names a host" in user
        assert "Standard reference: OpenAPI 3.1" in user
        assert "Sibling classes in api: api_server, api_pathitem" in user
        # Outgoing and incoming relationship types, by identifier
        assert "callback_uses_server: api_callback --[uses]--> api_server" in user
        assert "pathitem_aggregates_callback: api_pathitem --[aggregates]--> api_callback" in user

    def test_a_relationship_type_or_no_subject_gets_its_own_context(self, repo, claims):
        llm = FakeNoteSplitter({"rel": [], "general": []})
        run(
            make(repo, claims, llm),
            {
                "notes": [
                    {"ref": "r", "subject": "callback_uses_server", "text": "rel note"},
                    {"ref": "g", "text": "general note"},
                ]
            },
        )

        rel, general = sorted(llm.calls, key=lambda c: c["user"])[::-1]
        assert rel["user"].startswith("Note about the relationship type callback_uses_server:")
        assert "Domain class: api_callback (Api Callback)" in rel["user"]
        assert general["user"].startswith("Note about the DR taxonomy:")
        assert "Schemes:\n  api (API)" in general["user"]

    def test_an_unresolved_subject_is_kept_first_among_unresolved_refs(self, repo, claims):
        llm = FakeNoteSplitter({"x": [split("api_callback lacks x.", "api_callback", "nope")]})
        run(make(repo, claims, llm), {"notes": [{"ref": "n", "subject": "far_away", "text": "x"}]})

        claim = stored(claims)["n#1"]
        assert claim.subject_id is None
        assert claim.unresolved_refs == ["far_away", "nope"]
        assert llm.calls[0]["user"].startswith("Note about the DR taxonomy:")

    def test_empty_notes_are_skipped(self, repo, claims):
        llm = FakeNoteSplitter({"real": [split("A claim.")]})
        state = run(
            make(repo, claims, llm),
            {"notes": [{"ref": "a", "text": "  "}, {"ref": "b", "text": "real note"}]},
        )

        assert len(llm.calls) == 1
        assert sorted(stored(claims)) == ["b#1"]
        assert (state.result["notes"], state.result["empty_notes"]) == (1, 1)
        assert state.result["skipped"] == 0

    def test_a_category_outside_the_configuration_is_dropped(self):
        reply = '{"claims": [{"text": " t ", "category": "x", "affected_ids": [1, "a", " "]}]}'
        claims = parse_split(f"```json\n{reply}\n```", {"y": "Y"})
        assert [(c.text, c.category, c.affected_ids, c.proposed_change) for c in claims] == [
            ("t", None, ["a"], None)
        ]

    @pytest.mark.parametrize(
        "reply, message",
        [
            ("not json", "not JSON"),
            ('{"other": []}', "no claims list"),
            ('{"claims": [{"text": ""}]}', "claim 1 has no text"),
        ],
    )
    def test_a_malformed_reply_is_refused(self, reply, message):
        with pytest.raises(ValueError, match=message):
            parse_split(reply, {"other": "Other"})


class TestRerun:
    def test_a_note_split_from_the_same_text_is_skipped(self, repo, claims):
        notes = {"notes": [{"ref": "n", "text": "note"}]}
        llm = FakeNoteSplitter({"note": [split("One."), split("Two.")]})
        run(make(repo, claims, llm), notes)
        before = {k: (c.id, c.text) for k, c in stored(claims).items()}

        state = run(make(repo, claims, llm), notes)

        assert len(llm.calls) == 1
        assert {k: (c.id, c.text) for k, c in stored(claims).items()} == before
        assert (state.result["notes"], state.result["skipped"]) == (0, 1)

    def test_a_note_with_new_text_is_split_again(self, repo, claims):
        run(
            make(repo, claims, FakeNoteSplitter({"old": [split("One."), split("Two.")]})),
            {"notes": [{"ref": "n", "text": "old note"}]},
        )

        state = run(
            make(repo, claims, FakeNoteSplitter({"new": [split("One again.")]})),
            {"notes": [{"ref": "n", "text": "new note"}]},
        )

        got = stored(claims)
        assert sorted(got) == ["n#1"] and got["n#1"].note_text == "new note"
        assert (state.result["skipped"], state.result["claims_removed"]) == (0, 1)

    def test_imported_claims_with_verdicts_are_not_resplit(self, repo, claims):
        """DR's imported claims carry no note text, but their bench-gold verdicts stay."""
        claims.submit(
            T,
            [
                Claim(
                    taxonomy_id=T,
                    key=f"node:api.callback#{n}",
                    text=f"DR wording {n}.",
                    note_ref="node:api.callback",
                    note_source=NoteSource.MAINTAINER,
                )
                for n in (1, 2, 3)
            ],
        )
        gold = ClaimVerdict(validity="real_defect", adjudicated_by="dr-bench-gold")
        claims.set_verdict(stored(claims)["node:api.callback#2"].id, gold)
        llm = FakeNoteSplitter({"note": [split("Other wording 1."), split("Other wording 2.")]})
        notes = {"notes": [{"ref": "node:api.callback", "text": "the note"}]}

        state = run(make(repo, claims, llm), notes)

        got = stored(claims)
        assert llm.calls == [] and state.result["skipped"] == 1
        assert sorted(got) == [f"node:api.callback#{n}" for n in (1, 2, 3)]
        assert got["node:api.callback#2"].verdict == gold

        forced = run(make(repo, claims, llm), {**notes, "force": True})

        assert forced.result["notes"] == 1 and forced.result["claims_removed"] == 1
        assert [c.text for c in stored(claims).values()] == [
            "Other wording 1.",
            "Other wording 2.",
        ]

    def test_a_forced_rerun_keeps_verdicts_of_unchanged_claims_and_drops_vanished_keys(
        self, repo, claims
    ):
        notes = {"notes": [{"ref": "n", "subject": "cb", "text": "note one"}], "force": True}
        first = FakeNoteSplitter(
            {"note one": [split("Same claim."), split("Old wording."), split("Gone later.")]}
        )
        run(make(repo, claims, first), notes)
        verdict = ClaimVerdict(validity="real_defect", adjudicated_by="user")
        for key in ("n#1", "n#2"):
            claims.set_verdict(stored(claims)[key].id, verdict)
        ids = {k: c.id for k, c in stored(claims).items()}

        second = FakeNoteSplitter({"note one": [split("Same claim."), split("New wording.")]})
        state = run(make(repo, claims, second), notes)

        got = stored(claims)
        assert sorted(got) == ["n#1", "n#2"]
        assert got["n#1"].verdict is not None and got["n#1"].id == ids["n#1"]
        assert got["n#2"].verdict is None and got["n#2"].text == "New wording."
        assert (state.result["claims"], state.result["claims_removed"]) == (2, 1)

    def test_a_forced_rerun_with_the_same_split_changes_nothing(self, repo, claims):
        notes = {"notes": [{"ref": "n", "text": "note"}], "force": True}
        llm = FakeNoteSplitter({"note": [split("One."), split("Two.")]})
        run(make(repo, claims, llm), notes)
        before = {k: (c.id, c.text) for k, c in stored(claims).items()}

        state = run(make(repo, claims, llm), notes)

        assert {k: (c.id, c.text) for k, c in stored(claims).items()} == before
        assert state.result["claims_removed"] == 0

    def test_an_empty_split_removes_the_notes_claims(self, repo, claims):
        notes = {"notes": [{"ref": "n", "text": "note"}], "force": True}
        run(make(repo, claims, FakeNoteSplitter({"note": [split("One.")]})), notes)

        state = run(make(repo, claims, FakeNoteSplitter({"note": []})), notes)

        assert stored(claims) == {}
        assert state.result["claims_removed"] == 1

    def test_other_notes_claims_are_untouched(self, repo, claims):
        run(
            make(repo, claims, FakeNoteSplitter({"a": [split("A1.")], "b": [split("B1.")]})),
            {"notes": [{"ref": "a", "text": "a"}, {"ref": "b", "text": "b"}]},
        )
        run(
            make(repo, claims, FakeNoteSplitter({"a": []})),
            {"notes": [{"ref": "a", "text": "a"}], "force": True},
        )
        assert sorted(stored(claims)) == ["b#1"]


class TestFailures:
    def test_a_note_that_fails_is_reported_and_keeps_its_claims(self, repo, claims):
        notes = {"notes": [{"ref": "a", "text": "note a"}, {"ref": "b", "text": "note b"}]}
        run(make(repo, claims, FakeNoteSplitter({"a": [split("A1.")], "b": [split("B1.")]})), notes)

        llm = FakeNoteSplitter({"note a": "garbage", "note b": [split("B2.")]})
        state = run(make(repo, claims, llm), {**notes, "force": True})

        got = stored(claims)
        assert sorted(got) == ["a#1", "b#1"]
        assert got["a#1"].text == "A1." and got["b#1"].text == "B2."
        assert state.result["status"] == "completed_with_warnings"
        assert state.result["error_count"] == 1
        assert state.result["errors"][0].startswith("a: the reply is not JSON")
        assert state.parse_warnings[0]["note"] == "a"
        assert state.llm_metadata["failed_requests"] == 1
        # The unusable reply's tokens count too
        assert (state.llm_metadata["requests"], state.llm_metadata["tokens_in"]) == (2, 200)

    @pytest.mark.parametrize(
        "reply, message, tokens",
        [
            ("garbage", "not JSON", (100, 50)),
            (RuntimeError("provider down"), "provider down", (0, 0)),
        ],
    )
    def test_a_run_where_every_note_fails_fails_with_its_cost(
        self, repo, claims, reply, message, tokens
    ):
        llm = FakeNoteSplitter({"note": reply})
        with pytest.raises(PipelineExecutionError, match=message) as raised:
            run(make(repo, claims, llm), {"notes": [{"ref": "n", "text": "note"}]})
        spent = raised.value.llm_metadata
        assert (spent["requests"], spent["failed_requests"]) == (1, 1)
        assert (spent["tokens_in"], spent["tokens_out"]) == tokens


class TestScope:
    @pytest.mark.parametrize(
        "scope",
        [
            None,
            {},
            [{"ref": "n", "text": "x"}],
            {"notes": [], "since": "2026-01-01"},
            {"notes": [], "extra": 1},
            {"notes": "x"},
            {"notes": [{"text": "x"}]},
            {"notes": [{"ref": "n"}]},
            {"notes": [{"ref": "n", "text": "x", "source": "nobody"}]},
            {"notes": [{"ref": "n", "text": "x"}, {"ref": "n", "text": "y"}]},
            {"notes": [], "force": "yes"},
        ],
    )
    def test_a_bad_scope_is_refused(self, repo, claims, scope):
        with pytest.raises(PipelineInputError):
            run(make(repo, claims, FakeNoteSplitter({})), scope)

    def test_a_reviewer_note_from_a_client(self, repo, claims):
        run(
            make(repo, claims, FakeNoteSplitter({"x": [split("C.")]})),
            {"notes": [{"ref": "n", "text": "x", "source": "reviewer"}]},
        )
        assert stored(claims)["n#1"].note_source is NoteSource.REVIEWER

    def test_unknown_taxonomy_is_refused(self, repo, claims):
        with pytest.raises(PipelineInputError, match="No taxonomy"):
            run(make(repo, claims, FakeNoteSplitter({})), {"notes": []}, taxonomy_id="nope")

    def proposal(self, taxonomy_id=T):
        return ChangeProposal(
            id="prop-1",
            taxonomy_id=taxonomy_id,
            title="Enrich api",
            source=ProposalSource.MCP,
            created_at=WHEN,
            operations=[
                ProposedOperation(
                    id="op-1",
                    seq=1,
                    op=OperationType.UPDATE,
                    kind=OperationKind.CLASS,
                    target_id="cb",
                    fields={
                        "description": "A callback, keyed by its name",
                        "distinguish_from": [{"class_id": "pi", "when": "it is a path"}],
                        "standard_reference": "OpenAPI 3.1 Callback Object",
                    },
                    notes="The map-key name has no attribute.",
                ),
                ProposedOperation(
                    id="op-2",
                    seq=2,
                    op=OperationType.UPDATE,
                    kind=OperationKind.CLASS,
                    target_id="srv",
                    fields={"title": "Server"},
                ),
                ProposedOperation(
                    id="op-3",
                    seq=3,
                    op=OperationType.CREATE,
                    kind=OperationKind.ATTRIBUTE,
                    fields={"class_id": "cb", "identifier": "callback_name", "title": "Name"},
                    notes="Callbacks need a name attribute.",
                ),
                ProposedOperation(
                    id="op-4",
                    seq=4,
                    op=OperationType.CREATE,
                    kind=OperationKind.CLASS,
                    ref="hook",
                    fields={
                        "parent_class_id": "$base",
                        "concept_scheme_id": "api",
                        "title": "Webhook",
                    },
                    notes="Webhooks are a separate type.",
                ),
            ],
        )

    @staticmethod
    def decision(decision_id, reason, decided_at=WHEN, proposal_id="prop-1"):
        return ProposalDecision(
            id=decision_id,
            operation_id="op-2",
            proposal_id=proposal_id,
            taxonomy_id=T,
            seq=2,
            kind=OperationKind.CLASS,
            op=OperationType.UPDATE,
            decision=DecisionKind.REJECTED,
            decided_at=decided_at,
            decided_by="user",
            proposed={"target_id": "srv", "fields": {"title": "Server"}},
            reason=reason,
        )

    def test_a_proposals_operation_notes_and_decision_reasons(self, repo, claims):
        proposals = FakeProposals(
            self.proposal(),
            [self.decision("d-1", "Servers are not titled that way."), self.decision("d-2", None)],
        )
        llm = FakeNoteSplitter(
            {
                "map-key": [split("api_callback has no name attribute.", "api_callback")],
                "titled": [split("api_server's title is wrong.", "api_server")],
                "name attribute": [split("api_callback needs a name.", "api_callback")],
                "Webhooks": [split("Webhooks are separate.")],
            }
        )
        state = run(make(repo, claims, llm, proposals=proposals), {"proposal_id": "prop-1"})

        got = stored(claims)
        assert sorted(got) == ["decision:d-1#1", "op:op-1#1", "op:op-3#1", "op:op-4#1"]
        op_claim, reason_claim = got["op:op-1#1"], got["decision:d-1#1"]
        assert (op_claim.note_source, op_claim.subject_id) == (NoteSource.MAINTAINER, "cb")
        assert op_claim.note_ref == "op:op-1"
        assert (reason_claim.note_source, reason_claim.subject_id) == (NoteSource.REVIEWER, "srv")
        assert reason_claim.note_text == "Servers are not titled that way."
        assert proposals.filters[0].proposal_id == "prop-1"
        op_call = next(c for c in llm.calls if "map-key" in c["user"])
        assert "Proposed definition: A callback, keyed by its name" in op_call["user"]
        assert "Proposed distinctions: use api_pathitem when it is a path" in op_call["user"]
        assert "Proposed standard reference: OpenAPI 3.1 Callback Object" in op_call["user"]
        assert state.result["notes"] == 4
        # A create is about the owner its fields name: the attribute's class, and
        # the class's scheme when its parent is another create's $ref
        assert got["op:op-3#1"].subject_id == "cb"
        attribute_call = next(c for c in llm.calls if "name attribute" in c["user"])
        assert attribute_call["user"].startswith("Note about the class api_callback")
        assert "Proposed new attribute callback_name" in attribute_call["user"]
        assert got["op:op-4#1"].subject_id == "api"
        assert got["op:op-4#1"].unresolved_refs == []
        class_call = next(c for c in llm.calls if "Webhooks" in c["user"])
        assert class_call["user"].startswith("Note about the scheme api:")
        assert "Proposed new class Webhook" in class_call["user"]

    @pytest.mark.parametrize(
        "proposals, message",
        [
            (FakeProposals(), "No proposal"),
            (None, "not available"),
        ],
    )
    def test_a_missing_proposal_is_refused(self, repo, claims, proposals, message):
        with pytest.raises(PipelineInputError, match=message):
            run(make(repo, claims, FakeNoteSplitter({}), proposals=proposals), {"proposal_id": "x"})

    def test_a_proposal_on_another_taxonomy_is_refused(self, repo, claims):
        proposals = FakeProposals(self.proposal(taxonomy_id="t2"))
        with pytest.raises(PipelineInputError, match="another taxonomy"):
            run(
                make(repo, claims, FakeNoteSplitter({}), proposals=proposals),
                {"proposal_id": "prop-1"},
            )

    def test_since_reads_decision_reasons_from_gold(self, repo, claims):
        proposals = FakeProposals(
            decisions=[
                self.decision(
                    "old", "Old reason.", decided_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
                ),
                self.decision("new", "New reason.", proposal_id="prop-9"),
            ]
        )
        llm = FakeNoteSplitter({"New reason": [split("New.")]})
        run(make(repo, claims, llm, proposals=proposals), {"since": "2026-11-01T00:00:00"})

        assert sorted(stored(claims)) == ["decision:new#1"]
        assert proposals.filters[0].taxonomy_id == T
        assert proposals.filters[0].decided_from == datetime(2026, 11, 1, tzinfo=timezone.utc)

    def test_a_bad_since_is_refused(self, repo, claims):
        with pytest.raises(PipelineInputError, match="ISO 8601"):
            run(
                make(repo, claims, FakeNoteSplitter({}), proposals=FakeProposals()),
                {"since": "soon"},
            )


class TestMirroredGuard:
    @pytest.fixture()
    def mirrored(self, repo):
        taxonomy = repo.get_taxonomy(T)
        taxonomy.mirrored = True
        repo.save_taxonomy(taxonomy)
        return repo

    @pytest.mark.parametrize("via", [None, RequestedVia.CHAT, RequestedVia.API])
    def test_a_mirrored_taxonomy_refuses_runs_not_asked_for_over_mcp(self, mirrored, claims, via):
        extra = {REQUESTED_VIA: via.value} if via else {}
        llm = FakeNoteSplitter({"x": [split("C.")]})
        with pytest.raises(PipelineInputError, match="mirrors an external source"):
            run(make(mirrored, claims, llm), {"notes": [{"ref": "n", "text": "x"}]}, **extra)
        assert llm.calls == []

    def test_its_client_may_split_notes_over_mcp(self, mirrored, claims):
        run(
            make(mirrored, claims, FakeNoteSplitter({"x": [split("C.")]})),
            {"notes": [{"ref": "n", "text": "x"}]},
            **{REQUESTED_VIA: RequestedVia.MCP.value},
        )
        assert sorted(stored(claims)) == ["n#1"]
