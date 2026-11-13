"""Unit tests for scoring an extraction run against a benchmark gold extraction."""

import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.integration.pipelines._harness.benchmark import (
    Gold,
    GoldIndividual,
    GoldRelationship,
    Passage,
    Predicted,
    PredictedRelationship,
    benchmark_documents,
    failure_counts,
    load_gold,
    match_individuals,
    mean_metrics,
    name_key,
    predictions_from_triples,
    score,
    validate_gold,
)

COMPONENT = "application.applicationcomponent"
SOFTWARE = "technology.systemsoftware"
GOAL = "motivation.goal"
OUTCOME = "motivation.outcome"


def _gold() -> Gold:
    return Gold(
        document_id="sample",
        individuals=(
            GoldIndividual("gitaly", "Gitaly", COMPONENT, "core", evidence=(Passage(0, 20),)),
            GoldIndividual(
                "redis", "Redis", SOFTWARE, "core", acceptable=frozenset({"data-store.database"})
            ),
            GoldIndividual("runner", "GitLab Runner", COMPONENT, "supporting", aliases=("Runner",)),
            GoldIndividual(
                "goal-speed",
                "Alleviate pressure from Puma",
                GOAL,
                "supporting",
                acceptable=frozenset({OUTCOME}),
                evidence=(Passage(100, 160, "designed to help alleviate pressure from Puma"),),
            ),
        ),
        relationships=(
            GoldRelationship("runner", "uses", "gitaly"),
            GoldRelationship("redis", "serves", "gitaly"),
        ),
        excluded=frozenset({name_key("Bash"), name_key("Zsh")}),
    )


class TestNameKey:
    def test_ignores_case_plurals_and_markdown(self):
        assert name_key("`Runners`") == name_key("runner")
        assert name_key("**GitLab Runner**") == name_key("gitlab runner")

    def test_keeps_different_names_apart(self):
        assert name_key("Redis") != name_key("Redis Exporter")


class TestMatching:
    def test_matches_by_title_or_alias_once(self):
        predicted = [Predicted("runner", (COMPONENT,)), Predicted("GitLab Runners", (COMPONENT,))]
        matches = match_individuals(_gold(), predicted)
        assert {i: g.key for i, g in matches.items()} == {0: "runner"}

    def test_a_second_name_for_a_found_individual_is_a_duplicate_not_an_error(self):
        predicted = [Predicted("runner", (COMPONENT,)), Predicted("GitLab Runners", (COMPONENT,))]
        result = score(_gold(), predicted)
        assert result.duplicates == ["GitLab Runners"]
        assert result.spurious == []
        assert result.metrics["precision"] == 1.0

    def test_statement_matches_by_overlapping_passage(self):
        predicted = [Predicted("Reduce load on the app server", (GOAL,), (Passage(110, 150),))]
        assert match_individuals(_gold(), predicted)[0].key == "goal-speed"

    def test_statement_matches_by_title_drawn_from_its_evidence(self):
        predicted = [Predicted("help alleviate pressure from Puma", (OUTCOME,))]
        assert match_individuals(_gold(), predicted)[0].key == "goal-speed"

    def test_named_thing_does_not_match_a_statement_by_passage(self):
        predicted = [Predicted("Puma", (SOFTWARE,), (Passage(100, 160),))]
        assert match_individuals(_gold(), predicted) == {}


class TestScore:
    def test_a_perfect_run_scores_one(self):
        gold = _gold()
        predicted = [Predicted(g.title, (g.class_ref,), g.evidence) for g in gold.individuals]
        relationships = [
            PredictedRelationship("GitLab Runner", "uses", "Gitaly"),
            PredictedRelationship("Redis", "serves", "Gitaly"),
        ]
        result = score(gold, predicted, relationships)
        for name in ("recall", "recall_core", "precision", "typed_f1", "relationship_recall"):
            assert result.metrics[name] == 1.0, name
        assert result.missed == [] and result.spurious == [] and result.mistyped == []

    def test_counts_misses_mistypes_spurious_and_distractors(self):
        predicted = [
            Predicted("Gitaly", (SOFTWARE,)),  # found, wrong type
            Predicted("Redis", ("data-store.database",)),  # found, acceptable type
            Predicted("Bash", (SOFTWARE,)),  # a known distractor
            Predicted("Kubernetes", (SOFTWARE,)),  # matches nothing
        ]
        result = score(_gold(), predicted, [PredictedRelationship("Redis", "serves", "Gitaly")])
        assert result.counts["matched"] == 2
        assert result.metrics["recall"] == 0.5
        assert result.metrics["recall_core"] == 1.0
        assert result.metrics["precision"] == 0.5
        assert result.metrics["type_accuracy"] == 0.5
        assert result.metrics["type_accuracy_exact"] == 0.0
        assert result.metrics["typed_recall"] == 0.25
        assert [m["key"] for m in result.mistyped] == ["gitaly"]
        assert result.excluded_hits == ["Bash"]
        assert [s["title"] for s in result.spurious] == ["Kubernetes"]
        assert {m["key"] for m in result.missed} == {"runner", "goal-speed"}
        assert result.metrics["relationship_recall"] == 0.5
        assert result.metrics["relationship_recall_reachable"] == 1.0
        assert result.missed_relationships == ["GitLab Runner uses Gitaly"]

    def test_an_empty_run_scores_zero_without_dividing_by_zero(self):
        result = score(_gold(), [])
        assert result.metrics["recall"] == 0.0
        assert result.metrics["precision"] == 0.0
        assert result.metrics["typed_f1"] == 0.0

    def test_aggregates_over_documents(self):
        gold = _gold()
        perfect = score(gold, [Predicted(g.title, (g.class_ref,)) for g in gold.individuals])
        empty = score(gold, [])
        assert mean_metrics([perfect, empty])["recall"] == 0.5
        assert mean_metrics([]) == {}
        counts = failure_counts([empty])
        assert counts["missed_core"] == 2 and counts["missed_supporting"] == 2
        assert counts["relationship_missed"] == 2


class TestPredictionsFromTriples:
    def test_typing_triples_become_individuals_and_the_rest_relationships(self):
        triples = [
            {
                "subject": {"kind": "individual", "label": "Gitaly"},
                "predicate": {"label": "is_a"},
                "object": {"kind": "class", "label": "ApplicationComponent", "id": "c1"},
                "provenance": {"text_offset_start": 3, "text_offset_end": 9, "raw": "Gitaly"},
            },
            {
                "subject": {"kind": "individual", "label": "gitaly"},
                "predicate": {"label": "is_a"},
                "object": {"kind": "class", "label": "application.applicationcomponent"},
                "passages": [{"start": 40, "end": 46, "quote": "Gitaly"}],
            },
            {
                "subject": {"kind": "individual", "label": "GitLab Shell"},
                "predicate": {"label": "Uses"},
                "object": {"kind": "individual", "label": "Gitaly"},
            },
        ]
        individuals, relationships = predictions_from_triples(triples, {"c1": COMPONENT})
        assert len(individuals) == 1
        assert individuals[0].title == "Gitaly"
        assert individuals[0].class_refs == (COMPONENT,)
        assert [(p.start, p.end) for p in individuals[0].evidence] == [(3, 9), (40, 46)]
        assert relationships == [PredictedRelationship("GitLab Shell", "uses", "Gitaly")]


class TestGoldFiles:
    """The committed gold files are sound, and each scores perfectly against itself."""

    def test_there_are_benchmark_documents(self):
        assert benchmark_documents()

    @pytest.mark.parametrize("document_id", benchmark_documents())
    def test_gold_file_is_valid(self, document_id):
        assert validate_gold(document_id) == []

    @pytest.mark.parametrize("document_id", benchmark_documents())
    def test_gold_scores_perfectly_against_itself(self, document_id):
        gold = load_gold(document_id)
        titles = {g.key: g.title for g in gold.individuals}
        predicted = [Predicted(g.title, (g.class_ref,), g.evidence) for g in gold.individuals]
        relationships = [
            PredictedRelationship(titles[r.source], r.predicate, titles[r.target])
            for r in gold.relationships
        ]
        result = score(gold, predicted, relationships)
        assert result.missed == []
        assert result.metrics["typed_f1"] == 1.0
        assert result.metrics["relationship_recall"] == 1.0

    @pytest.mark.parametrize("document_id", benchmark_documents())
    def test_aliases_do_not_collide_between_individuals(self, document_id):
        gold = load_gold(document_id)
        owners: dict[str, str] = {}
        for individual in gold.individuals:
            for name in individual.names:
                assert owners.setdefault(name, individual.key) == individual.key, name
