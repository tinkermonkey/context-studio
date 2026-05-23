"""
Tests for OWL Adapter fixes from PR review.

Tests the following issues:
- Format detection for RDF/XML (not just Turtle)
- Warnings system for entities without labels
- ValueError for malformed input (not RuntimeError)
- Split mode for TBox/ABox separation
"""

import os
import sys
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from adapters.interchange.owl import OWLDeserializer, OWLSerializer
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.value_objects import (

    MatchKind,
    SerializationScope,
    SerializationScopeType,
)
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    Taxonomy,
)
from domain.ontology.value_objects import ExternalReference


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

local:tax-new a skos:ConceptScheme ;
    skos:prefLabel "New Taxonomy" ;
    skos:definition "A new taxonomy" .

local:scheme-new a skos:ConceptScheme ;
    skos:prefLabel "New Scheme" ;
    skos:definition "A new scheme" ;
    <http://purl.org/dc/terms/isPartOf> local:tax-new .

local:class-new a owl:Class ;
    rdfs:label "New Class" ;
    rdfs:comment "A new class" ;
    skos:inScheme local:scheme-new .
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

    <rdf:Description rdf:about="http://context-studio.local/ontology/tax-xml">
        <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#ConceptScheme"/>
        <skos:prefLabel>XML Taxonomy</skos:prefLabel>
        <skos:definition>A taxonomy in RDF/XML format</skos:definition>
    </rdf:Description>

    <rdf:Description rdf:about="http://context-studio.local/ontology/scheme-xml">
        <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#ConceptScheme"/>
        <skos:prefLabel>XML Scheme</skos:prefLabel>
        <skos:definition>A scheme in RDF/XML format</skos:definition>
        <dct:isPartOf rdf:resource="http://context-studio.local/ontology/tax-xml"/>
    </rdf:Description>

    <rdf:Description rdf:about="http://context-studio.local/ontology/class-xml">
        <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#Class"/>
        <rdfs:label>XML Class</rdfs:label>
        <rdfs:comment>A class in RDF/XML format</rdfs:comment>
        <skos:inScheme rdf:resource="http://context-studio.local/ontology/scheme-xml"/>
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

    def test_warnings_for_dropped_relationships(self, ontology_repo, interchange_repo):
        """Test that warnings are generated when relationships reference missing entities."""
        owl_turtle = b"""
@prefix local: <http://context-studio.local/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .

local:tax-1 a skos:ConceptScheme ;
    skos:prefLabel "Test Taxonomy" .

local:scheme-1 a skos:ConceptScheme ;
    skos:prefLabel "Test Scheme" ;
    dct:isPartOf local:tax-1 .

local:class-1 a owl:Class ;
    rdfs:label "Class 1" ;
    skos:inScheme local:scheme-1 .

local:class-2 a owl:Class ;
    rdfs:label "Class 2" ;
    skos:inScheme local:scheme-1 .

local:prop-1 a owl:ObjectProperty ;
    rdfs:label "has related" .

local:class-1 local:prop-1 local:class-2-no-label .

local:class-2-no-label a owl:Class ;
    skos:inScheme local:scheme-1 .
"""
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)
        plan = deserializer.deserialize(owl_turtle, dry_run=True)

        # Should have warnings about dropped relationships
        warning_text = " ".join(plan.warnings)
        assert (
            "relationship" in warning_text.lower()
            or "not found in entity map" in warning_text.lower()
        )


class TestOWLAdapterErrorHandling:
    """Test error handling in OWL deserializer."""

    def test_malformed_input_raises_valueerror(self, ontology_repo, interchange_repo):
        """Test that malformed input raises ValueError, not RuntimeError."""
        malformed_data = b"This is not valid RDF data at all"

        deserializer = OWLDeserializer(ontology_repo, interchange_repo)

        # Should raise ValueError, not RuntimeError
        with pytest.raises(ValueError) as exc_info:
            deserializer.deserialize(malformed_data, dry_run=True)

        error_msg = str(exc_info.value)
        assert "Failed to parse OWL RDF" in error_msg
        # Verify all format attempts are reported in the error message
        assert "xml:" in error_msg
        assert "turtle:" in error_msg
        assert "json-ld:" in error_msg


class TestOWLAdapterConflictDetection:
    """Test conflict detection in OWL deserializer."""

    def test_conflict_detection_on_reimport(self, ontology_repo, interchange_repo):
        """Test that reimporting the same entities produces conflicts."""
        # Export the existing taxonomy and classes
        serializer = OWLSerializer(ontology_repo, format="turtle", split_mode=False)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported_data = serializer.serialize(scope)

        # Now reimport the exported data against the same populated database
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)
        plan = deserializer.deserialize(exported_data, dry_run=True)

        # Should have conflicts for the existing entities (tax-1, scheme-1, class-1, individual-1)
        assert len(plan.conflicts) > 0, "Expected conflicts when reimporting existing entities"

        # Verify at least one conflict is detected
        conflict_ids = [c.incoming["id"] for c in plan.conflicts]
        # Should detect conflicts for the existing entities
        assert any(cid in conflict_ids for cid in ["tax-1", "scheme-1", "class-1", "individual-1"])

    def test_conflict_cascade_external_reference(
        self, db_engine, session_factory, interchange_repo
    ):
        """Test that external references have priority in conflict detection cascade."""
        repo = SQLiteOntologyRepository(session_factory)

        # First create a taxonomy and concept scheme
        tax = Taxonomy(
            id="tax-ext-ref",
            title="Taxonomy with External References",
            description="Test taxonomy",
            created_at=datetime.now(timezone.utc),
            last_modified=datetime.now(timezone.utc),
        )
        repo.save_taxonomy(tax)

        scheme = ConceptScheme(
            id="scheme-ext-ref",
            taxonomy_id="tax-ext-ref",
            title="Scheme with External References",
            description="Test scheme",
            created_at=datetime.now(timezone.utc),
            last_modified=datetime.now(timezone.utc),
        )
        repo.save_concept_scheme(scheme)

        # Create a class with an external reference
        class_with_ref = Class(
            id="class-ext-ref",
            concept_scheme_id="scheme-ext-ref",
            taxonomy_id="tax-ext-ref",
            title="Class with External Reference",
            description="A class with external reference",
            parent_class_id=None,
            external_references=[
                ExternalReference(
                    source="dbpedia",
                    identifier="Dog",
                    uri="http://dbpedia.org/resource/Dog",
                )
            ],
            created_at=datetime.now(timezone.utc),
            last_modified=datetime.now(timezone.utc),
        )
        repo.save_class(class_with_ref)

        # Create OWL data with a class having the same external reference but different ID
        owl_turtle = b"""
@prefix local: <http://context-studio.local/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

local:class-different-id a owl:Class ;
    rdfs:label "Different Class ID" ;
    owl:sameAs <http://dbpedia.org/resource/Dog> .
"""
        deserializer = OWLDeserializer(repo, interchange_repo)
        plan = deserializer.deserialize(owl_turtle, dry_run=True)

        # Should detect a conflict via external reference
        assert len(plan.conflicts) > 0
        conflict = plan.conflicts[0]
        assert conflict.match_kind == MatchKind.EXTERNAL_REFERENCE


class TestOWLAdapterSplitMode:
    """Test TBox/ABox split mode in OWL serializer."""

    def test_split_mode_excludes_individuals(self, ontology_repo):
        """Test that split mode (TBox-only) excludes individuals."""
        # Create a serializer in split mode
        serializer = OWLSerializer(ontology_repo, format="turtle", split_mode=True)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        # Serialize in split mode
        turtle_bytes = serializer.serialize(scope)
        turtle_str = turtle_bytes.decode("utf-8")

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
        turtle_str = turtle_bytes.decode("utf-8")

        # In normal mode, should include both class and individual
        assert "Test Class" in turtle_str
        assert "Test Individual" in turtle_str
        assert isinstance(turtle_bytes, bytes)
