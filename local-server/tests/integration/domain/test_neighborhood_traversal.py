"""
Integration tests for schema neighborhood traversal.

Tests the SchemaNeighborhoodTraversal utility for extracting class and
property neighborhoods with various levels of context.
"""

import pytest

from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal


@pytest.fixture
def sample_schema(ontology_service):
    """Create a sample schema hierarchy."""
    # Create taxonomy
    taxonomy = ontology_service.create_taxonomy(title="Test Taxonomy", description="Testing")

    # Create concept scheme
    scheme = ontology_service.create_scheme(
        taxonomy_id=taxonomy.id,
        title="Test Scheme",
    )

    # Create parent class
    parent = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Entity",
        description="Base entity class",
    )

    # Create sibling classes
    sibling1 = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Person",
        description="A person entity",
        parent_class_id=parent.id,
    )

    sibling2 = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Organization",
        description="An organization entity",
        parent_class_id=parent.id,
    )

    # Create child class
    child = ontology_service.create_class(
        concept_scheme_id=scheme.id,
        title="Employee",
        description="A person employed by an organization",
        parent_class_id=sibling1.id,
    )

    # Create property definitions
    prop_works_for = ontology_service.create_property_definition(
        identifier="works_for",
        title="Works For",
        description="Relationship between a person and their employer",
    )

    prop_employs = ontology_service.create_property_definition(
        identifier="employs",
        title="Employs",
        description="Relationship between an organization and its employees",
    )

    # Create relationships
    rel1 = ontology_service.create_relationship(
        source_id=sibling1.id,
        target_id=sibling2.id,
        property_definition_id=prop_works_for.id,
    )

    rel2 = ontology_service.create_relationship(
        source_id=sibling2.id,
        target_id=sibling1.id,
        property_definition_id=prop_employs.id,
    )

    return {
        "taxonomy": taxonomy,
        "scheme": scheme,
        "parent": parent,
        "sibling1": sibling1,
        "sibling2": sibling2,
        "child": child,
        "prop_works_for": prop_works_for,
        "prop_employs": prop_employs,
        "rel1": rel1,
        "rel2": rel2,
    }


@pytest.fixture
def traversal(session_factory):
    """Create a traversal instance."""
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    return SchemaNeighborhoodTraversal(ontology_repo=repo)


class TestClassNeighborhood:
    """Tests for class neighborhood extraction."""

    def test_get_parent_class(self, sample_schema, traversal):
        """Should retrieve parent class."""
        parent_id = sample_schema["parent"].id
        sibling_id = sample_schema["sibling1"].id

        neighborhood = traversal.get_class_neighborhood(sibling_id)

        assert neighborhood.parent_class is not None
        assert neighborhood.parent_class.id == parent_id
        assert neighborhood.parent_class.title == "Entity"

    def test_get_sibling_classes(self, sample_schema, traversal):
        """Should retrieve sibling classes."""
        sibling_id = sample_schema["sibling1"].id
        neighborhood = traversal.get_class_neighborhood(sibling_id)

        sibling_ids = {s.id for s in neighborhood.sibling_classes}
        assert sample_schema["sibling2"].id in sibling_ids
        assert len(neighborhood.sibling_classes) >= 1

    def test_get_child_classes(self, sample_schema, traversal):
        """Should retrieve child classes."""
        parent_id = sample_schema["sibling1"].id
        child_id = sample_schema["child"].id

        neighborhood = traversal.get_class_neighborhood(parent_id)

        child_ids = {c.id for c in neighborhood.child_classes}
        assert child_id in child_ids

    def test_get_property_definitions(self, sample_schema, traversal):
        """Should retrieve properties used by the class."""
        person_id = sample_schema["sibling1"].id
        neighborhood = traversal.get_class_neighborhood(person_id)

        prop_ids = {p.id for p in neighborhood.property_definitions}
        # Person class uses the "works_for" property
        assert sample_schema["prop_works_for"].id in prop_ids

    def test_nonexistent_class_raises_error(self, traversal):
        """Should raise ValueError for nonexistent class."""
        with pytest.raises(ValueError, match="Class not found"):
            traversal.get_class_neighborhood("nonexistent")

    def test_isolated_node_with_no_neighborhood(self, ontology_service, traversal):
        """Should handle isolated classes with no neighbors."""
        taxonomy = ontology_service.create_taxonomy(title="Isolated Taxonomy", description="")
        scheme = ontology_service.create_scheme(
            taxonomy_id=taxonomy.id,
            title="Isolated Scheme",
        )
        isolated_class = ontology_service.create_class(
            concept_scheme_id=scheme.id,
            title="Isolated Class",
            description="An isolated class",
        )

        neighborhood = traversal.get_class_neighborhood(isolated_class.id)

        assert neighborhood.parent_class is None
        assert len(neighborhood.sibling_classes) == 0
        assert len(neighborhood.child_classes) == 0


class TestPropertyNeighborhood:
    """Tests for property neighborhood extraction."""

    def test_get_domain_neighborhood(self, sample_schema, traversal):
        """Should retrieve domain class neighborhood."""
        prop_id = sample_schema["prop_works_for"].id
        neighborhood = traversal.get_property_neighborhood(prop_id)

        assert neighborhood.domain_neighborhood is not None
        assert neighborhood.domain_neighborhood.class_label == "Person"

    def test_get_range_neighborhood(self, sample_schema, traversal):
        """Should retrieve range class neighborhood."""
        prop_id = sample_schema["prop_works_for"].id
        neighborhood = traversal.get_property_neighborhood(prop_id)

        assert neighborhood.range_neighborhood is not None
        assert neighborhood.range_neighborhood.class_label == "Organization"

    def test_get_sibling_properties(self, sample_schema, traversal):
        """Should retrieve sibling properties on domain class."""
        prop_id = sample_schema["prop_works_for"].id
        neighborhood = traversal.get_property_neighborhood(prop_id)

        # Person class has prop_works_for, so sibling would be others on Person
        sibling_ids = {p.id for p in neighborhood.sibling_properties}
        # In this schema, Person only has one outgoing property
        assert len(sibling_ids) == 0

    def test_nonexistent_property_raises_error(self, traversal):
        """Should raise ValueError for nonexistent property."""
        with pytest.raises(ValueError, match="Property definition not found"):
            traversal.get_property_neighborhood("nonexistent")
