"""
Tests for OWL Adapter fixes from PR review.

Tests the following issues:
- Format detection for RDF/XML (not just Turtle)
- Warnings system for entities without labels
- ValueError for malformed input (not RuntimeError)
- Split mode for TBox/ABox separation
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
)
from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.interchange.owl import OWLSerializer, OWLDeserializer


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory for testing."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def ontology_repo(session_factory):
    """Create an ontology repository with test data."""
    repo = SQLiteOntologyRepository(session_factory)

    # Create test taxonomy and classes
    tax = Taxonomy(
        id="tax-1",
        title="Test Taxonomy",
        description="A test taxonomy",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    repo.save_taxonomy(tax)

    scheme = ConceptScheme(
        id="scheme-1",
        taxonomy_id="tax-1",
        title="Test Scheme",
        description="A test concept scheme",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    repo.save_concept_scheme(scheme)

    class_entity = Class(
        id="class-1",
        concept_scheme_id="scheme-1",
        taxonomy_id="tax-1",
        title="Test Class",
        description="A test class",
        parent_class_id=None,
        external_references=[],
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    repo.save_class(class_entity)

    # Create an individual instance of the class
    individual = Individual(
        id="individual-1",
        class_ids=["class-1"],
        title="Test Individual",
        description="An instance of the test class",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    repo.save_individual(individual)

    return repo


@pytest.fixture
def interchange_repo(session_factory):
    """Create an interchange repository for testing."""
    return SQLiteInterchangeRepository(session_factory)


class TestOWLAdapterFormatDetection:
    """Test format detection in OWL deserializer."""

    def test_deserialize_turtle_format(self, ontology_repo, interchange_repo):
        """Test that Turtle format is still supported."""
        owl_turtle = b"""
@prefix local: <http://context-studio.local/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

local:tax-1 a skos:ConceptScheme ;
    skos:prefLabel "Test Taxonomy" ;
    skos:definition "A test taxonomy" .

local:scheme-1 a skos:ConceptScheme ;
    skos:prefLabel "Test Scheme" ;
    skos:definition "A test scheme" ;
    <http://purl.org/dc/terms/isPartOf> local:tax-1 .

local:class-1 a owl:Class ;
    rdfs:label "Test Class" ;
    rdfs:comment "A test class" ;
    skos:inScheme local:scheme-1 .
"""
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)
        plan = deserializer.deserialize(owl_turtle, dry_run=True)

        # Should have parsed successfully
        assert plan.new_entity_count >= 3  # At least taxonomy, scheme, and class
        assert len(plan.warnings) == 0  # No warnings for well-formed data

    def test_deserialize_rdfxml_format(self, ontology_repo, interchange_repo):
        """Test that RDF/XML format is now supported (not just Turtle)."""
        owl_rdfxml = b"""<?xml version="1.0"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:skos="http://www.w3.org/2004/02/skos/core#"
    xmlns:dct="http://purl.org/dc/terms/"
    xmlns:local="http://context-studio.local/ontology/">

    <rdf:Description rdf:about="http://context-studio.local/ontology/tax-1">
        <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#ConceptScheme"/>
        <skos:prefLabel>Test Taxonomy</skos:prefLabel>
        <skos:definition>A test taxonomy</skos:definition>
    </rdf:Description>

    <rdf:Description rdf:about="http://context-studio.local/ontology/scheme-1">
        <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#ConceptScheme"/>
        <skos:prefLabel>Test Scheme</skos:prefLabel>
        <skos:definition>A test scheme</skos:definition>
        <dct:isPartOf rdf:resource="http://context-studio.local/ontology/tax-1"/>
    </rdf:Description>

    <rdf:Description rdf:about="http://context-studio.local/ontology/class-1">
        <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#Class"/>
        <rdfs:label>Test Class</rdfs:label>
        <rdfs:comment>A test class</rdfs:comment>
        <skos:inScheme rdf:resource="http://context-studio.local/ontology/scheme-1"/>
    </rdf:Description>
</rdf:RDF>
"""
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)
        plan = deserializer.deserialize(owl_rdfxml, dry_run=True)

        # Should have parsed successfully
        assert plan.new_entity_count >= 3
        assert len(plan.warnings) == 0


class TestOWLAdapterWarnings:
    """Test warning system in OWL deserializer."""

    def test_warnings_for_entities_without_labels(self, ontology_repo, interchange_repo):
        """Test that warnings are generated for entities without labels."""
        owl_turtle = b"""
@prefix local: <http://context-studio.local/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

local:tax-1 a skos:ConceptScheme .

local:class-1 a owl:Class ;
    skos:inScheme local:scheme-1 .
"""
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)
        plan = deserializer.deserialize(owl_turtle, dry_run=True)

        # Should have warnings about missing labels
        assert len(plan.warnings) > 0
        # Check that warnings mention the missing labels
        warning_text = " ".join(plan.warnings)
        assert "no label" in warning_text.lower()


class TestOWLAdapterErrorHandling:
    """Test error handling in OWL deserializer."""

    def test_malformed_input_raises_valueerror(self, ontology_repo, interchange_repo):
        """Test that malformed input raises ValueError, not RuntimeError."""
        malformed_data = b"This is not valid RDF data at all"

        deserializer = OWLDeserializer(ontology_repo, interchange_repo)

        # Should raise ValueError, not RuntimeError
        with pytest.raises(ValueError) as exc_info:
            deserializer.deserialize(malformed_data, dry_run=True)

        assert "Failed to parse OWL RDF" in str(exc_info.value)


class TestOWLAdapterSplitMode:
    """Test TBox/ABox split mode in OWL serializer."""

    def test_split_mode_excludes_individuals(self, ontology_repo):
        """Test that split mode (TBox-only) excludes individuals."""
        # Create a serializer in split mode
        serializer = OWLSerializer(ontology_repo, format="turtle", split_mode=True)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        # Serialize in split mode
        turtle_bytes = serializer.serialize(scope)
        turtle_str = turtle_bytes.decode('utf-8')

        # In split mode, should not include the individual (by label or NamedIndividual)
        assert "Test Individual" not in turtle_str
        assert "NamedIndividual" not in turtle_str
        # Should still include the class (TBox)
        assert "Test Class" in turtle_str

    def test_non_split_mode_includes_individuals(self, ontology_repo):
        """Test that non-split mode includes all entities including individuals."""
        # Create a serializer without split mode
        serializer = OWLSerializer(ontology_repo, format="turtle", split_mode=False)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        # Serialize in normal mode
        turtle_bytes = serializer.serialize(scope)
        turtle_str = turtle_bytes.decode('utf-8')

        # In normal mode, should include both class and individual
        assert "Test Class" in turtle_str
        assert "Test Individual" in turtle_str
        assert isinstance(turtle_bytes, bytes)
