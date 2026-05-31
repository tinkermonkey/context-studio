"""Unit tests for benchmark.canon_metrics."""

from __future__ import annotations

import pytest

from benchmark.canon_metrics import (
    aggregate_canon_metrics,
    compute_color_presence_rate,
    compute_embedding_presence_rate,
    compute_hierarchy_correctness,
    compute_identifier_slug_validity,
    compute_multi_sense_disambiguation_score,
    compute_per_node_type_f1,
    compute_reference_grounding_rate,
)

# Minimal canon fixture matching the structure of datafiles/canon/.../canon.json
_CANON_FIXTURE = {
    "taxonomies": [{"identifier": "tax_a"}],
    "concept_schemes": [{"identifier": "scheme_a"}, {"identifier": "scheme_b"}],
    "class_hierarchy": [
        {"identifier": "root_class", "parent_class_identifier": None},
        {"identifier": "child_a", "parent_class_identifier": "root_class"},
        {"identifier": "child_b", "parent_class_identifier": "root_class"},
        {"identifier": "grandchild", "parent_class_identifier": "child_a"},
    ],
    "property_definitions": [{"identifier": "rel_x"}],
    "cross_paper_resolutions": {
        "service": {"expected_sense_count": 3},
        "context": {"expected_sense_count": 1},
        "leader": {"expected_sense_count": 1},
    },
}


# ---------------------------------------------------------------------------- #
# Per-node-type F1                                                             #
# ---------------------------------------------------------------------------- #


class TestPerNodeTypeF1:
    def test_perfect_recall_and_precision(self):
        out = compute_per_node_type_f1(
            produced_by_type={"class": ["a", "b"], "taxonomy": ["t"]},
            expected_by_type={"class": ["a", "b"], "taxonomy": ["t"]},
        )
        assert out["class"].precision == 1.0
        assert out["class"].recall == 1.0
        assert out["class"].f1 == 1.0
        assert out["taxonomy"].f1 == 1.0

    def test_missing_node_type_returns_zero(self):
        out = compute_per_node_type_f1(
            produced_by_type={"class": ["a"]},
            expected_by_type={"class": ["a"]},
        )
        # Untouched node types still appear with zero counts.
        assert out["individual"].f1 == 0.0
        assert out["individual"].true_positives == 0

    def test_recall_drop_when_expected_missing(self):
        out = compute_per_node_type_f1(
            produced_by_type={"class": ["a"]},
            expected_by_type={"class": ["a", "b", "c"]},
        )
        m = out["class"]
        assert m.precision == 1.0
        assert m.recall == pytest.approx(1 / 3)
        assert m.false_negatives == 2

    def test_precision_drop_when_extra_produced(self):
        out = compute_per_node_type_f1(
            produced_by_type={"class": ["a", "b", "c"]},
            expected_by_type={"class": ["a"]},
        )
        m = out["class"]
        assert m.precision == pytest.approx(1 / 3)
        assert m.recall == 1.0
        assert m.false_positives == 2


# ---------------------------------------------------------------------------- #
# Hierarchy correctness                                                        #
# ---------------------------------------------------------------------------- #


class TestHierarchyCorrectness:
    def test_perfect_match(self):
        produced = {
            "root_class": None,
            "child_a": "root_class",
            "child_b": "root_class",
            "grandchild": "child_a",
        }
        out = compute_hierarchy_correctness(produced, _CANON_FIXTURE)
        assert out["edges_expected"] == 4
        assert out["edges_correct"] == 4
        assert out["ratio"] == 1.0

    def test_wrong_parent_counts_as_incorrect(self):
        produced = {
            "root_class": None,
            "child_a": "root_class",
            "child_b": "root_class",
            "grandchild": "root_class",  # wrong: should be child_a
        }
        out = compute_hierarchy_correctness(produced, _CANON_FIXTURE)
        assert out["edges_correct"] == 3
        assert out["ratio"] == 0.75

    def test_missing_class_counts_as_incorrect(self):
        # grandchild not in produced → its expected edge is uncounted
        produced = {
            "root_class": None,
            "child_a": "root_class",
            "child_b": "root_class",
        }
        out = compute_hierarchy_correctness(produced, _CANON_FIXTURE)
        assert out["edges_correct"] == 3
        assert out["ratio"] == 0.75


# ---------------------------------------------------------------------------- #
# Multi-sense disambiguation                                                   #
# ---------------------------------------------------------------------------- #


class TestMultiSenseDisambiguation:
    def test_perfect_disambiguation(self):
        out = compute_multi_sense_disambiguation_score(
            produced_lexical_senses_by_term={"service": 3, "context": 1, "leader": 1},
            canon=_CANON_FIXTURE,
        )
        assert out["terms_correct"] == 3
        assert out["ratio"] == 1.0

    def test_over_splitting_penalised(self):
        """'context' should produce 1 sense; producing 2 is wrong (over-splitting)."""
        out = compute_multi_sense_disambiguation_score(
            produced_lexical_senses_by_term={"service": 3, "context": 2, "leader": 1},
            canon=_CANON_FIXTURE,
        )
        assert out["per_term"]["context"] is False
        assert out["terms_correct"] == 2
        assert out["ratio"] == pytest.approx(2 / 3)

    def test_under_splitting_penalised(self):
        """'service' should produce 3 senses; producing 1 is wrong (under-splitting)."""
        out = compute_multi_sense_disambiguation_score(
            produced_lexical_senses_by_term={"service": 1, "context": 1, "leader": 1},
            canon=_CANON_FIXTURE,
        )
        assert out["per_term"]["service"] is False
        assert out["terms_correct"] == 2


# ---------------------------------------------------------------------------- #
# Reference grounding rate                                                     #
# ---------------------------------------------------------------------------- #


class TestReferenceGroundingRate:
    def test_perfect_coverage(self):
        out = compute_reference_grounding_rate(
            [{"external_references": [{"source": "dbpedia"}]}] * 3
        )
        assert out["rate"] == 1.0
        assert out["classes_grounded"] == 3

    def test_zero_coverage(self):
        out = compute_reference_grounding_rate(
            [{"external_references": []}, {"external_references": None}, {}]
        )
        assert out["rate"] == 0.0

    def test_partial_coverage(self):
        out = compute_reference_grounding_rate(
            [
                {"external_references": [{"source": "dbpedia"}]},
                {"external_references": []},
                {"external_references": [{"source": "wikidata"}]},
                {"external_references": []},
            ]
        )
        assert out["rate"] == 0.5


# ---------------------------------------------------------------------------- #
# Identifier slug validity                                                     #
# ---------------------------------------------------------------------------- #


class TestIdentifierSlugValidity:
    def test_perfect_validity(self):
        out = compute_identifier_slug_validity(
            ["rest", "microservices_architecture", "crdt"]
        )
        assert out["rate"] == 1.0
        assert out["invalid_examples"] == []

    def test_none_identifier_is_invalid(self):
        out = compute_identifier_slug_validity(["rest", None, "crdt"])
        assert out["rate"] == pytest.approx(2 / 3)
        assert None in out["invalid_examples"]

    def test_uppercase_invalid(self):
        out = compute_identifier_slug_validity(["REST", "rest"])
        assert out["rate"] == 0.5
        assert "REST" in out["invalid_examples"]


# ---------------------------------------------------------------------------- #
# Color presence                                                               #
# ---------------------------------------------------------------------------- #


class TestColorPresenceRate:
    def test_per_node_type_rates(self):
        out = compute_color_presence_rate(
            {
                "taxonomy": ["#2b6cb0"],
                "concept_scheme": ["#3182ce", None, "#805ad5"],
                "class": [None, None, "#abcdef"],
            }
        )
        assert out["taxonomy"]["rate"] == 1.0
        assert out["concept_scheme"]["rate"] == pytest.approx(2 / 3)
        assert out["class"]["rate"] == pytest.approx(1 / 3)

    def test_invalid_format_does_not_count(self):
        out = compute_color_presence_rate({"taxonomy": ["#GGGGGG", "#abcdef"]})
        assert out["taxonomy"]["with_color"] == 1


# ---------------------------------------------------------------------------- #
# Embedding presence                                                           #
# ---------------------------------------------------------------------------- #


class TestEmbeddingPresenceRate:
    def test_perfect_coverage(self):
        out = compute_embedding_presence_rate(
            [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]
        )
        assert out["rate"] == 1.0

    def test_empty_and_none_count_as_missing(self):
        out = compute_embedding_presence_rate(
            [{"embedding": None}, {"embedding": []}, {"embedding": [0.1]}]
        )
        assert out["rate"] == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------- #
# Aggregate                                                                    #
# ---------------------------------------------------------------------------- #


class TestAggregateCanonMetrics:
    def test_aggregate_produces_complete_block(self):
        block = aggregate_canon_metrics(
            produced_by_type={"class": ["root_class", "child_a"]},
            expected_by_type={"class": ["root_class", "child_a", "child_b"]},
            produced_class_parents={"root_class": None, "child_a": "root_class"},
            produced_lexical_senses_by_term={"service": 3, "context": 1, "leader": 1},
            produced_classes=[
                {"external_references": [{"source": "dbpedia"}], "embedding": [0.1]},
                {"external_references": [], "embedding": None},
            ],
            produced_identifiers=["root_class", "child_a"],
            produced_colors_by_type={"class": ["#abcdef", None]},
            canon=_CANON_FIXTURE,
        )

        assert "per_node_type_f1" in block
        assert "avg_node_type_f1" in block
        assert "hierarchy_correctness" in block
        assert "multi_sense_disambiguation" in block
        assert "reference_grounding_rate" in block
        assert "identifier_slug_validity" in block
        assert "color_presence_rate" in block
        assert "embedding_presence_rate" in block

        # Spot-check derived values
        assert block["reference_grounding_rate"]["rate"] == 0.5
        assert block["embedding_presence_rate"]["rate"] == 0.5
        assert block["multi_sense_disambiguation"]["ratio"] == 1.0
        assert block["per_node_type_f1"]["class"]["recall"] == pytest.approx(2 / 3)
