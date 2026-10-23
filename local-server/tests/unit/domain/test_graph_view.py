"""
Unit tests for GraphAnalysisService.get_graph_view().

The graph view is a labelled read model: classes and individuals assigned to
layers (concept schemes) plus typed edges. These tests use the fake repository
and never touch the graph engine.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from tests.fakes.fake_graph_engine import FakeGraphEngine
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_semantic_query_engine import FakeSemanticQueryEngine


@pytest.fixture
def layered_repository():
    """Two layers in one taxonomy, a schema edge across them, and two individuals."""
    repo = FakeOntologyRepository()
    repo.save_taxonomy(Taxonomy(id="tax", identifier="dr_spec", title="DR"))
    repo.save_concept_scheme(
        ConceptScheme(id="layer_a", taxonomy_id="tax", identifier="business", title="Business")
    )
    repo.save_concept_scheme(
        ConceptScheme(id="layer_b", taxonomy_id="tax", identifier="api", title="API")
    )
    repo.save_class(
        Class(
            id="cls_service",
            concept_scheme_id="layer_a",
            taxonomy_id="tax",
            identifier="business_service",
            title="Business Service",
            description="A service offered",
        )
    )
    repo.save_class(
        Class(
            id="cls_operation",
            concept_scheme_id="layer_b",
            taxonomy_id="tax",
            identifier="api_operation",
            title="Operation",
        )
    )
    repo.save_class(
        Class(
            id="cls_sub",
            concept_scheme_id="layer_a",
            taxonomy_id="tax",
            title="Sub Service",
            parent_class_id="cls_service",
        )
    )
    repo.save_property_definition(
        PropertyDefinition(
            id="prop_realized_by",
            identifier="service_realized_by_operation",
            title="realized by",
            domain_class_id="cls_service",
            range_class_id="cls_operation",
        )
    )
    repo.save_property_definition(
        PropertyDefinition(
            id="prop_dangling",
            identifier="points_at_missing_class",
            title="dangling",
            domain_class_id="cls_service",
            range_class_id="cls_missing",
        )
    )
    repo.save_property_definition(
        PropertyDefinition(id="prop_free", identifier="untyped", title="untyped")
    )
    repo.save_individual(
        Individual(id="ind_checkout", class_ids=["cls_service"], title="Checkout", description="d")
    )
    repo.save_individual(
        Individual(id="ind_post_order", class_ids=["cls_operation", "cls_service"], title="POST")
    )
    repo.save_relationship(
        Relationship(
            id="rel_1",
            source_id="ind_checkout",
            target_id="ind_post_order",
            property_definition_id="prop_realized_by",
        )
    )
    return repo


@pytest.fixture
def service(layered_repository):
    """GraphAnalysisService with fake engines."""
    return GraphAnalysisService(
        repository=layered_repository,
        graph_engine=FakeGraphEngine(),
        query_engine=FakeSemanticQueryEngine(),
    )


class TestGetGraphView:
    """Tests for the graph view read model."""

    def test_layers_and_taxonomies_are_listed(self, service):
        view = service.get_graph_view()
        assert [t.identifier for t in view.taxonomies] == ["dr_spec"]
        assert {layer.id for layer in view.layers} == {"layer_a", "layer_b"}
        assert all(layer.taxonomy_id == "tax" for layer in view.layers)

    def test_nodes_are_classes_and_individuals_only(self, service):
        view = service.get_graph_view()
        types = {n.id: n.node_type for n in view.nodes}
        assert types == {
            "cls_service": "class",
            "cls_operation": "class",
            "cls_sub": "class",
            "ind_checkout": "individual",
            "ind_post_order": "individual",
        }

    def test_class_nodes_carry_layer_and_label(self, service):
        node = next(n for n in service.get_graph_view().nodes if n.id == "cls_service")
        assert node.label == "Business Service"
        assert node.identifier == "business_service"
        assert node.description == "A service offered"
        assert node.concept_scheme_id == "layer_a"
        assert node.taxonomy_id == "tax"
        assert node.class_ids == []

    def test_individual_takes_layer_from_first_class(self, service):
        node = next(n for n in service.get_graph_view().nodes if n.id == "ind_post_order")
        assert node.identifier is None
        assert node.class_ids == ["cls_operation", "cls_service"]
        assert node.concept_scheme_id == "layer_b"
        assert node.taxonomy_id == "tax"

    def test_edge_types(self, service):
        edges = {e.id: e for e in service.get_graph_view().edges}

        assert edges["rel_1"].edge_type == "relationship"
        assert edges["rel_1"].predicate == "realized by"
        assert (edges["rel_1"].source, edges["rel_1"].target) == ("ind_checkout", "ind_post_order")

        assert edges["prop_realized_by"].edge_type == "schema"
        assert (edges["prop_realized_by"].source, edges["prop_realized_by"].target) == (
            "cls_service",
            "cls_operation",
        )

        instance_of = edges["ind_post_order:instance_of:cls_operation"]
        assert instance_of.edge_type == "instance_of"
        assert instance_of.predicate_id is None

        subclass_of = edges["cls_sub:subclass_of:cls_service"]
        assert subclass_of.edge_type == "subclass_of"
        assert subclass_of.target == "cls_service"

    def test_edges_with_missing_endpoints_or_no_range_are_dropped(self, service):
        edge_ids = {e.id for e in service.get_graph_view().edges}
        assert "prop_dangling" not in edge_ids
        assert "prop_free" not in edge_ids
        assert len(edge_ids) == 6  # 1 relationship, 1 schema, 3 instance_of, 1 subclass_of

    def test_edge_ids_are_stable_between_calls(self, service):
        first = [e.id for e in service.get_graph_view().edges]
        second = [e.id for e in service.get_graph_view().edges]
        assert first == second

    def test_empty_repository_returns_empty_view(self):
        service = GraphAnalysisService(
            repository=FakeOntologyRepository(),
            graph_engine=FakeGraphEngine(),
            query_engine=FakeSemanticQueryEngine(),
        )
        view = service.get_graph_view()
        assert (view.taxonomies, view.layers, view.nodes, view.edges) == ([], [], [], [])
