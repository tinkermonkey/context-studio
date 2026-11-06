"""
Unit tests for the schema relationship reflection pipeline (#1410): sorting
questions (a port of DR's sortingQuestions), outcomes, the change plan (a port
of DR's reflect-plan.ts), the proposal operations it becomes, and the
orchestrator end to end on a small House-style taxonomy with a scripted
decision model.
"""

import asyncio
import json
import re

import pytest

from domain.decision.exceptions import DecisionModelUnavailableError, UnknownDecisionModelError
from domain.decision.value_objects import ChoiceAnswer
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.schema_relationship_reflection.drafts import plan_drafts
from domain.pipelines.schema_relationship_reflection.orchestrator import (
    RelationshipReflectionOrchestrator,
    RelationshipReflectionState,
)
from domain.pipelines.schema_relationship_reflection.plan import (
    ALTERNATIVE,
    COMPOUND,
    CONFLICT,
    NO_BETTER,
    REMOVE_DUPLICATE,
    RENAME_PREDICATE,
    REPRODUCED,
    RETARGET,
    REVERSE,
    RankedAnswer,
    Reflection,
    build_plan,
    change_of,
    reflection_outcome,
)
from domain.pipelines.schema_relationship_reflection.questions import (
    PREDICATE_FOR,
    SOURCE_FOR,
    TARGET_FOR,
    RelationshipCatalog,
    Triple,
    first_sentence,
    sorting_questions,
)
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ChangeScope, OperationType, ProposalSource
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


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def house(ontology):
    """Records (task, item, project) and vocabulary (place, resource, tag) schemes."""
    taxonomy = ontology.create_taxonomy(
        title="House", identifier="house", description="A household knowledge graph."
    )
    records = ontology.create_scheme(taxonomy.id, "Records", identifier="records")
    vocab = ontology.create_scheme(taxonomy.id, "Vocabulary", identifier="vocabulary")
    ids = {"taxonomy": taxonomy.id, "records": records.id, "vocabulary": vocab.id}
    for scheme, name, definition in [
        (records, "task", "A piece of work to do. Tasks are filed in projects."),
        (records, "item", "A thing the household owns."),
        (records, "project", "A group of related tasks."),
        (vocab, "place", "Somewhere in the house."),
        (vocab, "resource", "What work needs."),
        (vocab, "tag", "An ad hoc label."),
    ]:
        ids[name] = ontology.create_class(
            scheme.id, name.title(), description=definition, identifier=name
        ).id
    for key, source, predicate, target, meaning in [
        ("task_located_in", "task", "located_in", "place", "Where something happens."),
        ("item_located_in", "item", "located_in", "place", "Where something happens."),
        ("task_requires", "task", "requires", "resource", "What work needs."),
        ("task_in_project", "task", "in_project", "project", "The project a task is in."),
        ("project_part_of", "project", "part_of", "project", "Part to whole."),
        ("place_part_of", "place", "part_of", "place", "Part to whole."),
        ("item_tagged", "item", "tagged", "tag", "A label."),
        ("project_contains_task", "project", "contains", "task", "Whole to part."),
    ]:
        ids[key] = ontology.create_property_definition(
            key,
            f"{source} {predicate} {target}",
            description=meaning,
            canonical_predicate=predicate,
            domain_class_id=ids[source],
            range_class_id=ids[target],
        ).id
    return ids


def catalog_of(repo, house, predicate_catalog=None):
    return RelationshipCatalog.for_taxonomy(repo, house["taxonomy"], predicate_catalog)


def answer(choice, p=0.8, **others):
    probabilities = {choice: p, **others}
    return RankedAnswer.of(choice, probabilities)


def reflection(prop_id, triple, source=None, target=None, predicate=None, p=0.8):
    answers = {
        SOURCE_FOR: answer(source or triple.source, p),
        TARGET_FOR: answer(target or triple.target, p),
        PREDICATE_FOR: answer(predicate or triple.predicate, p),
    }
    outcome, alternatives = reflection_outcome(triple, answers)
    return Reflection(prop_id, triple, answers, {}, outcome, alternatives)


# ------------------------------------------------------------------ questions


class TestFirstSentence:
    def test_first_sentence_on_one_line(self):
        assert first_sentence("A room.\n  For  sleeping.") == "A room."

    def test_long_sentence_is_cut_at_a_word(self):
        text = "word " * 60 + "end."
        out = first_sentence(text, limit=30)
        assert out.endswith("...")
        assert len(out) <= 33
        assert not out[:-3].endswith(" ")


class TestSortingQuestions:
    def test_three_choice_questions_with_none(self, repo, house):
        catalog = catalog_of(repo, house)
        sq = sorting_questions(repo.get_property_definition(house["task_located_in"]), catalog)

        assert set(sq.questions) == {SOURCE_FOR, TARGET_FOR, PREDICATE_FOR}
        for question in sq.questions.values():
            assert "none" in question.criteria
        assert sq.triple == Triple("task", "located_in", "place")

    def test_source_candidates_current_then_catalog_then_siblings(self, repo, house):
        catalog = catalog_of(repo, house)
        sq = sorting_questions(repo.get_property_definition(house["task_located_in"]), catalog)

        # task first; item also located_in place (catalog); project is task's sibling
        assert sq.candidates[SOURCE_FOR] == ["task", "item", "project"]
        assert sq.questions[SOURCE_FOR].criteria["task"] == "A piece of work to do."

    def test_target_candidates_and_cap(self, repo, house):
        catalog = catalog_of(repo, house)
        prop = repo.get_property_definition(house["task_located_in"])

        assert sorting_questions(prop, catalog).candidates[TARGET_FOR] == [
            "place",
            "resource",
            "tag",
        ]
        assert sorting_questions(prop, catalog, top=2).candidates[TARGET_FOR] == [
            "place",
            "resource",
        ]

    def test_predicates_current_forward_general_then_reverse(self, repo, house):
        catalog = catalog_of(repo, house)
        sq = sorting_questions(
            repo.get_property_definition(house["task_in_project"]),
            catalog,
            general_predicates=["part_of", "realizes"],
        )

        # realizes is not a predicate of this taxonomy, so it is not offered
        assert sq.candidates[PREDICATE_FOR] == [
            "in_project",
            "part_of",
            "reverse:contains",
            "none",
        ]
        assert (
            sq.questions[PREDICATE_FOR]
            .criteria["reverse:contains"]
            .startswith("the other way round, project contains task")
        )

    def test_predicate_catalog_says_which_predicates_exist(self, repo, house):
        catalog = catalog_of(
            repo,
            house,
            {"in_project": {"description": "Filed in"}, "realizes": {"description": "Makes real"}},
        )
        sq = sorting_questions(
            repo.get_property_definition(house["task_in_project"]),
            catalog,
            general_predicates=["part_of", "realizes"],
        )

        assert sq.candidates[PREDICATE_FOR] == ["in_project", "realizes", "none"]
        assert "Filed in" in sq.questions[PREDICATE_FOR].criteria["in_project"]

    def test_other_taxonomies_are_not_in_the_catalog(self, ontology, repo, house):
        other = ontology.create_taxonomy(title="Other", identifier="other")
        scheme = ontology.create_scheme(other.id, "S")
        stranger = ontology.create_class(scheme.id, "Stranger", identifier="stranger")
        ontology.create_property_definition(
            "stranger_located_in",
            "x",
            canonical_predicate="located_in",
            domain_class_id=stranger.id,
            range_class_id=house["place"],
        )
        catalog = catalog_of(repo, house)
        sq = sorting_questions(repo.get_property_definition(house["task_located_in"]), catalog)

        assert "stranger" not in sq.candidates[SOURCE_FOR]
        assert all(p.id != "stranger_located_in" for p in catalog.relationship_types)


# ------------------------------------------------------------------ outcomes


class TestOutcome:
    T = Triple("task", "located_in", "place")

    def test_reproduced(self):
        assert reflection(None, self.T).outcome == REPRODUCED

    def test_no_better_when_an_answer_is_none(self):
        r = reflection(None, self.T, source="none")
        assert (r.outcome, r.alternatives) == (NO_BETTER, ())

    def test_alternative_lists_what_won(self):
        r = reflection(None, self.T, target="tag", predicate="reverse:part_of")
        assert r.outcome == ALTERNATIVE
        assert r.alternatives == ("target=tag", "predicate=reverse:part_of")

    def test_ranked_answer_keeps_one_percent_rounded(self):
        a = RankedAnswer.of("a", {"a": 0.81234, "b": 0.005, "none": 0.18})
        assert a.probabilities == {"a": 0.812, "none": 0.18}
        assert a.top3() == "a (0.81), none (0.18)"


# ------------------------------------------------------------------ plan


class TestChangeKinds:
    T = Triple("task", "located_in", "place")

    def test_rename_predicate(self):
        c = change_of(reflection("p", self.T, predicate="requires", p=0.6), set())
        assert (c.kind, c.replacement, c.p) == (
            RENAME_PREDICATE,
            Triple("task", "requires", "place"),
            0.6,
        )

    def test_remove_duplicate_when_the_renamed_triple_exists(self):
        existing = {Triple("task", "requires", "place")}
        assert change_of(reflection("p", self.T, predicate="requires"), existing).kind == (
            REMOVE_DUPLICATE
        )

    def test_reverse_swaps_ends(self):
        c = change_of(reflection("p", self.T, predicate="reverse:part_of"), set())
        assert (c.kind, c.replacement, c.reversed) == (
            REVERSE,
            Triple("place", "part_of", "task"),
            True,
        )

    def test_retarget(self):
        c = change_of(reflection("p", self.T, source="item"), set())
        assert (c.kind, c.replacement) == (RETARGET, Triple("item", "located_in", "place"))

    def test_compound_takes_the_minimum_p(self):
        r = Reflection(
            "p",
            self.T,
            {
                SOURCE_FOR: answer("item", 0.9),
                TARGET_FOR: answer("place", 0.9),
                PREDICATE_FOR: answer("requires", 0.55),
            },
            {},
            ALTERNATIVE,
            ("source=item", "predicate=requires"),
        )
        c = change_of(r, set())
        assert (c.kind, c.p) == (COMPOUND, 0.55)
        assert c.alternatives == ("source=item|0.90", "predicate=requires|0.55")


class TestPlan:
    A = Triple("task", "located_in", "place")
    B = Triple("item", "located_in", "place")

    def test_only_alternatives_make_rows_highest_p_first(self):
        plan = build_plan(
            [
                reflection("a", self.A, predicate="requires", p=0.6),
                reflection("b", self.B, target="tag", p=0.9),
                reflection("c", Triple("x", "y", "z")),
            ],
            {self.A, self.B},
        )
        assert [(row.property_id, row.kind) for row in plan] == [
            ("b", RETARGET),
            ("a", RENAME_PREDICATE),
        ]

    def test_reflections_about_one_type_disagreeing_are_a_conflict_with_max_p(self):
        plan = build_plan(
            [
                reflection("a", self.A, predicate="requires", p=0.6),
                reflection("a", self.A, target="tag", p=0.7),
            ],
            {self.A},
        )
        assert len(plan) == 1
        assert plan[0].kind == CONFLICT
        assert plan[0].p == 0.7
        assert plan[0].replacement == (
            Triple("task", "requires", "place"),
            Triple("task", "located_in", "tag"),
        )

    def test_agreeing_reflections_take_min_p(self):
        plan = build_plan(
            [
                reflection("a", self.A, predicate="requires", p=0.6),
                reflection("a", self.A, predicate="requires", p=0.8),
            ],
            {self.A},
        )
        assert (plan[0].kind, plan[0].p) == (RENAME_PREDICATE, 0.6)

    def test_replacing_with_a_type_that_is_itself_changed_is_a_conflict(self):
        # A wants to become B; B's own reflection wants B changed
        plan = build_plan(
            [
                reflection("a", self.A, source="item", p=0.8),
                reflection("b", self.B, predicate="requires", p=0.7),
            ],
            {self.A, self.B},
        )
        assert {row.property_id: row.kind for row in plan} == {"a": CONFLICT, "b": CONFLICT}


# ------------------------------------------------------------------ drafts


class TestDrafts:
    def test_update_delete_and_scope(self, repo, house):
        catalog = catalog_of(repo, house)
        loc = catalog.triple(repo.get_property_definition(house["task_located_in"]))
        tagged = catalog.triple(repo.get_property_definition(house["item_tagged"]))
        plan = build_plan(
            [
                # rename onto a triple nothing has: an update of the predicate
                reflection(house["task_located_in"], loc, predicate="requires", p=0.7),
                # retarget onto item located_in place, which exists: a delete naming it
                reflection(house["item_tagged"], tagged, predicate="located_in", target="place"),
            ],
            catalog.by_triple,
        )
        drafts = {d.row.property_id: d.draft for d in plan_drafts(plan, catalog)}

        rename = drafts[house["task_located_in"]]
        assert rename.op is OperationType.UPDATE
        assert rename.fields == {"canonical_predicate": "requires"}
        assert rename.claimed_scope is None
        assert rename.probability == 0.7
        evidence = rename.evidence[0]
        assert evidence["plan_kind"] == RENAME_PREDICATE
        assert evidence[PREDICATE_FOR] == "requires (0.70)"
        assert json.loads(evidence["probabilities"])[PREDICATE_FOR] == {"requires": 0.7}

        merge = drafts[house["item_tagged"]]
        assert merge.op is OperationType.DELETE
        assert merge.replacement == house["item_located_in"]
        assert merge.claimed_scope is ChangeScope.BREAKING  # compound

    def test_a_second_update_onto_the_same_new_triple_deletes_naming_the_first(self, repo, house):
        catalog = catalog_of(repo, house)
        task = catalog.triple(repo.get_property_definition(house["task_located_in"]))
        item = catalog.triple(repo.get_property_definition(house["item_located_in"]))
        plan = build_plan(
            [
                reflection(house["task_located_in"], task, source="project", p=0.9),
                reflection(house["item_located_in"], item, source="project", p=0.8),
            ],
            catalog.by_triple,
        )
        drafts = [d.draft for d in plan_drafts(plan, catalog)]

        assert drafts[0].op is OperationType.UPDATE
        assert drafts[0].fields == {"domain_class_id": house["project"]}
        assert drafts[0].claimed_scope is ChangeScope.BREAKING
        assert drafts[1].op is OperationType.DELETE
        assert drafts[1].replacement == house["task_located_in"]

    def test_reverse_swaps_domain_and_range(self, repo, house):
        catalog = catalog_of(repo, house)
        triple = catalog.triple(repo.get_property_definition(house["task_requires"]))
        plan = build_plan(
            [reflection(house["task_requires"], triple, predicate="reverse:part_of")],
            catalog.by_triple,
        )
        (planned,) = plan_drafts(plan, catalog)

        assert planned.draft.fields == {
            "canonical_predicate": "part_of",
            "domain_class_id": house["resource"],
            "range_class_id": house["task"],
        }

    def test_a_self_loop_reversed_onto_itself_proposes_nothing(self, repo, house):
        catalog = catalog_of(repo, house)
        triple = catalog.triple(repo.get_property_definition(house["place_part_of"]))
        plan = build_plan(
            [reflection(house["place_part_of"], triple, predicate="reverse:part_of")],
            catalog.by_triple,
        )
        assert len(plan) == 1
        assert plan_drafts(plan, catalog) == []

    def test_completer_extends_triple_updates(self, repo, house):
        catalog = catalog_of(repo, house)
        triple = catalog.triple(repo.get_property_definition(house["task_located_in"]))
        plan = build_plan(
            [reflection(house["task_located_in"], triple, predicate="requires")],
            catalog.by_triple,
        )
        (planned,) = plan_drafts(
            plan, catalog, complete_fields=lambda target, f: {**f, "identifier": "x"}
        )
        assert planned.draft.fields == {"canonical_predicate": "requires", "identifier": "x"}


# ------------------------------------------------------------------ orchestrator

_TRIPLE = re.compile(r"The catalog says '(\S+) (\S+) (\S+)'")


class ScriptedModel:
    """
    Answers sorting questions from a script keyed by 'source predicate target':
    {question: option}; unscripted questions choose the current answer.
    """

    def __init__(self, script=None, fail=(), cost=0.001, latency=40.0):
        self.script = script or {}
        self.fail = set(fail)
        self.cost = cost
        self.latency = latency
        self.calls = []

    @property
    def name(self):
        return "scripted"

    @property
    def is_configured(self):
        return True

    def decide(self, state, questions):
        triple = " ".join(_TRIPLE.search(questions[SOURCE_FOR].instructions).groups())
        self.calls.append((triple, state, questions))
        if triple in self.fail:
            raise DecisionModelUnavailableError("down")
        source, predicate, target = triple.split(" ")
        current = {SOURCE_FOR: source, TARGET_FOR: target, PREDICATE_FOR: predicate}
        out = {}
        for name, question in questions.items():
            choice = self.script.get(triple, {}).get(name, current[name])
            options = list(question.options())
            rest = 0.2 / max(1, len(options) - 1)
            out[name] = ChoiceAnswer(
                choice=choice,
                probabilities={o: 0.8 if o == choice else rest for o in options},
                model=self.name,
                latency_ms=self.latency,
                cost_usd=self.cost / 3,
            )
        return out

    async def decide_async(self, state, questions):
        return self.decide(state, questions)


class FakeDecisionModels:
    def __init__(self, model):
        self.model = model
        self.asked = []

    def get(self, name=None):
        self.asked.append(name)
        if name not in (None, "scripted"):
            raise UnknownDecisionModelError(name)
        return self.model

    def describe(self):
        return []


class RecordingWriter:
    def __init__(self):
        self.progress = []
        self.running = False

    def update_running_status(self, run_id, started_at):
        self.running = True
        return True

    def update_progress(self, run_id, items_done, items_total):
        self.progress.append((items_done, items_total))
        return True


@pytest.fixture()
def proposals(ontology, repo):
    return ProposalService(FakeChangeProposalRepository(), ontology, repo, StubRevertService())


def run(orchestrator, taxonomy_id, scope=None):
    state = RelationshipReflectionState(
        run_id="run-1",
        pipeline_type=PipelineType.SCHEMA_RELATIONSHIP_REFLECTION,
        input_data={"taxonomy_id": taxonomy_id, "scope": scope},
    )
    return asyncio.run(orchestrator.execute(state))


def make(repo, proposals, model, writer=None, config=None):
    return RelationshipReflectionOrchestrator(
        ontology_repo=repo,
        decision_models=FakeDecisionModels(model),
        proposal_service=proposals,
        config=config,
        run_id="run-1",
        status_writer=writer,
    )


class TestOrchestrator:
    def test_scheme_scope_reflects_on_its_types_and_proposes_the_plan(self, repo, house, proposals):
        model = ScriptedModel(
            {
                "task in_project project": {PREDICATE_FOR: "reverse:contains"},
                "task located_in place": {SOURCE_FOR: "none"},
            }
        )
        writer = RecordingWriter()
        state = run(make(repo, proposals, model, writer), house["taxonomy"], "records")
        result = state.result

        assert state.current_status is PipelineRunStatus.COMPLETED
        # records holds task, item, project: 7 of the 8 types have their domain there
        assert result["relationship_types"] == 7
        assert len(model.calls) == 7
        assert result["outcomes"] == {"reproduced": 5, "no_better": 1, "alternative": 1}
        assert writer.running and writer.progress[0] == (0, 7) and writer.progress[-1] == (7, 7)
        # task in_project project reversed is project contains task, which exists
        assert result["plan"][0]["kind"] == REVERSE
        assert result["plan"][0]["replacement"] == ["project contains task"]

        proposal = proposals.get(result["proposal_id"])
        assert proposal.source is ProposalSource.PIPELINE
        assert "scripted" in proposal.source_detail
        (op,) = proposal.operations
        assert op.op is OperationType.DELETE
        assert op.target_id == house["task_in_project"]
        assert op.proposed_replacement_id == house["project_contains_task"]
        assert op.probability == 0.8
        assert any(e.get("label") == "Evidence pack" for e in op.evidence)

    def test_the_state_is_the_summary_evidence_pack(self, repo, house, proposals):
        model = ScriptedModel()
        run(make(repo, proposals, model), house["taxonomy"], [house["task_requires"]])
        _, state, _ = model.calls[0]

        assert state.startswith("Design intent:\n  Taxonomy summary: A household knowledge graph.")
        assert "Charter" not in state
        assert "task --[requires]--> resource" in state

    def test_cost_and_latency_are_recorded(self, repo, house, proposals):
        state = run(make(repo, proposals, ScriptedModel(cost=0.003)), house["taxonomy"])

        meta = state.llm_metadata
        assert meta["decision_model"] == "scripted"
        assert meta["requests"] == 8
        assert meta["cost_usd"] == pytest.approx(0.024)
        assert meta["latency_ms_total"] == pytest.approx(320.0)
        assert meta["latency_ms_mean"] == pytest.approx(40.0)
        assert state.result["cost_usd"] == pytest.approx(0.024)
        assert state.result["proposal_id"] is None  # every type reproduced

    def test_the_default_decision_model_is_asked_unless_configured(self, repo, house, proposals):
        models = FakeDecisionModels(ScriptedModel())
        orchestrator = RelationshipReflectionOrchestrator(repo, models, proposals)
        run(orchestrator, house["taxonomy"], [house["task_requires"]])
        assert models.asked == [None]

        with pytest.raises(UnknownDecisionModelError):
            run(
                make(repo, proposals, ScriptedModel(), config={"decision_model": "missing"}),
                house["taxonomy"],
            )

    def test_a_failed_type_is_reported_and_the_rest_proposed(self, repo, house, proposals):
        model = ScriptedModel(
            {"task requires resource": {TARGET_FOR: "tag"}}, fail={"item tagged tag"}
        )
        result = run(make(repo, proposals, model), house["taxonomy"], "records").result

        assert result["error_count"] == 1
        assert result["errors"][0].startswith("item tagged tag:")
        assert result["operations"] == 1
        (op,) = proposals.get(result["proposal_id"]).operations
        assert op.fields == {"range_class_id": house["tag"]}
        assert op.scope is ChangeScope.BREAKING

    def test_every_type_failing_fails_the_run(self, repo, house, proposals):
        model = ScriptedModel(fail={"task requires resource"})
        with pytest.raises(PipelineExecutionError):
            run(make(repo, proposals, model), house["taxonomy"], [house["task_requires"]])

    def test_scope_errors(self, repo, house, proposals):
        orchestrator = make(repo, proposals, ScriptedModel())
        with pytest.raises(PipelineInputError, match="No scheme"):
            run(orchestrator, house["taxonomy"], "nowhere")
        with pytest.raises(PipelineInputError, match="Not relationship types"):
            run(orchestrator, house["taxonomy"], ["nope"])
        with pytest.raises(PipelineInputError, match="taxonomy_id"):
            run(orchestrator, "")

    def test_scope_by_scheme_id_or_dict(self, repo, house, proposals):
        orchestrator = make(repo, proposals, ScriptedModel())
        by_id = run(orchestrator, house["taxonomy"], {"concept_scheme_id": house["vocabulary"]})
        assert by_id.result["relationship_types"] == 1  # place part_of place
        assert by_id.result["scope"] == {"concept_scheme_id": house["vocabulary"]}
