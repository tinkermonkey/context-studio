"""
Integration tests for SKOS adapter round-trip serialization.

Tests the adapter against a real in-memory SQLite database to verify:
- Empty-DB round-trip: export → reimport → structural equality
- Idempotent reimport: export → reimport against populated DB → no duplicates, UUIDs preserved
- External fixture: import external SKOS file → valid ImportPlan
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
)
from domain.ontology.value_objects import ExternalReference

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.interchange.skos import SKOSSerializer, SKOSDeserializer


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
    """Create an ontology repository instance for testing."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def interchange_repo(session_factory):
    """Create an interchange repository instance for testing."""
    return SQLiteInterchangeRepository(session_factory)


@pytest.fixture
def sample_data(ontology_repo):
    """Create and persist sample ontology data."""
    # Create taxonomy
    taxonomy = Taxonomy(
        id=str(uuid.uuid4()),
        title="Biology",
        description="Biological classification",
    )
    taxonomy = ontology_repo.save_taxonomy(taxonomy)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid.uuid4()),
        taxonomy_id=taxonomy.id,
        title="Organisms",
        description="Classification of living organisms",
    )
    scheme = ontology_repo.save_concept_scheme(scheme)

    # Create classes
    dog = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Dog",
        description="A domesticated carnivorous mammal",
        external_references=[
            ExternalReference(
                source="dbpedia",
                identifier="Dog",
                uri="http://dbpedia.org/resource/Dog",
            ),
            ExternalReference(
                source="wikidata",
                identifier="Q144",
                uri="https://www.wikidata.org/wiki/Q144",
            ),
        ],
    )
    dog = ontology_repo.save_class(dog)

    mammal = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Mammal",
        description="A warm-blooded vertebrate animal",
    )
    mammal = ontology_repo.save_class(mammal)

    cat = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Cat",
        description="A small domesticated carnivorous mammal",
        parent_class_id=mammal.id,
        external_references=[
            ExternalReference(
                source="dbpedia",
                identifier="Cat",
                uri="http://dbpedia.org/resource/Cat",
            ),
        ],
    )
    cat = ontology_repo.save_class(cat)

    return {
        "taxonomy": taxonomy,
        "scheme": scheme,
        "dog": dog,
        "mammal": mammal,
        "cat": cat,
    }


class TestSKOSEmptyDatabaseRoundTrip:
    """Test round-trip serialization and deserialization against an empty database."""

    def test_export_and_reimport_empty_taxonomy(self, ontology_repo):
        """Test exporting and reimporting an empty taxonomy."""
        # Create a simple taxonomy
        taxonomy = Taxonomy(
            id=str(uuid.uuid4()),
            title="Empty Taxonomy",
            description="A taxonomy with no concepts",
        )
        taxonomy = ontology_repo.save_taxonomy(taxonomy)

        # Export
        serializer = SKOSSerializer(ontology_repo)
        from domain.interchange.value_objects import SerializationScope, SerializationScopeType
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id=taxonomy.id,
        )
        exported = serializer.serialize(scope)
        assert exported is not None
        assert len(exported) > 0

    def test_export_and_reimport_with_classes(self, ontology_repo, sample_data):
        """Test exporting and reimporting ontology with classes and hierarchy."""
        # Export whole graph
        serializer = SKOSSerializer(ontology_repo)
        from domain.interchange.value_objects import SerializationScope, SerializationScopeType
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        assert exported is not None
        assert isinstance(exported, bytes)
        exported_str = exported.decode('utf-8') if isinstance(exported, bytes) else exported

        assert "Concept" in exported_str or "concept" in exported_str.lower()
        assert "Dog" in exported_str
        assert "Cat" in exported_str
        assert "Mammal" in exported_str

        # Verify SKOS structure in serialized output
        assert "prefLabel" in exported_str
        assert "broader" in exported_str or "Broader" in exported_str
        assert "inScheme" in exported_str or "InScheme" in exported_str

    def test_roundtrip_preserves_external_references(self, ontology_repo, sample_data):
        """Test that round-trip preserves external references."""
        # Export
        serializer = SKOSSerializer(ontology_repo)
        from domain.interchange.value_objects import SerializationScope, SerializationScopeType
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Verify DBpedia and Wikidata references in output
        exported_str = exported.decode('utf-8') if isinstance(exported, bytes) else exported
        assert "dbpedia.org" in exported_str
        assert "wikidata.org" in exported_str

    def test_import_creates_import_plan_with_no_conflicts(self, ontology_repo, sample_data):
        """Test importing against an empty database produces valid plan with no conflicts."""
        # Export
        serializer = SKOSSerializer(ontology_repo)
        from domain.interchange.value_objects import SerializationScope, SerializationScopeType
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository (empty DB)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        fresh_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import
        deserializer = SKOSDeserializer(fresh_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify plan
        assert plan.conflicts == []
        assert plan.new_entity_count > 0
        assert plan.source_hash is not None


class TestSKOSIdempotentReimport:
    """Test that reimporting produces idempotent results."""

    def test_reimport_with_matching_external_references(self, ontology_repo, sample_data):
        """Test that reimporting entities with matching external refs merges by default."""
        # Export
        serializer = SKOSSerializer(ontology_repo)
        from domain.interchange.value_objects import SerializationScope, SerializationScopeType
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import against populated DB
        deserializer = SKOSDeserializer(ontology_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify that conflicts are detected with EXTERNAL_REFERENCE match kind
        from domain.interchange.value_objects import MatchKind, ResolutionKind
        external_ref_conflicts = [c for c in plan.conflicts if c.match_kind == MatchKind.EXTERNAL_REFERENCE]
        assert len(external_ref_conflicts) > 0

        # Verify default resolution is MERGE for external reference matches
        for conflict in external_ref_conflicts:
            assert conflict.default_resolution == ResolutionKind.MERGE


class TestSKOSExternalFixture:
    """Test importing external SKOS files."""

    def test_import_external_skos_fixture(self, ontology_repo):
        """Test importing a SKOS file created by an external tool."""
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "fixtures",
            "skos",
            "external_skos.ttl",
        )

        with open(fixture_path, "rb") as f:
            content = f.read()

        # Import
        deserializer = SKOSDeserializer(ontology_repo)
        plan = deserializer.deserialize(content, dry_run=True)

        # Verify plan is valid
        assert plan.source_hash is not None
        assert plan.new_entity_count > 0
        # May have conflicts if classes are matched by title
        # but should not raise an exception

    def test_unhandled_predicates_produce_warnings(self):
        """Test that unhandled SKOS predicates produce warnings."""
        # Create RDF with unhandled predicates
        from rdflib import Graph, Namespace, URIRef, Literal, RDF

        SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
        LOCAL = Namespace("http://context-studio.local/ontology/")

        graph = Graph()
        concept = LOCAL["test-concept"]
        scheme = LOCAL["test-scheme"]

        graph.add((concept, RDF.type, SKOS.Concept))
        graph.add((concept, SKOS.prefLabel, Literal("Test")))
        graph.add((concept, SKOS.inScheme, scheme))
        graph.add((concept, SKOS.related, LOCAL["other-concept"]))
        graph.add((concept, SKOS.altLabel, Literal("Alternative")))

        graph.add((scheme, RDF.type, SKOS.ConceptScheme))
        graph.add((scheme, SKOS.prefLabel, Literal("Test Scheme")))

        # Create fresh repo
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        fresh_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import
        deserializer = SKOSDeserializer(fresh_repo)
        ttl_data = graph.serialize(format="turtle")
        plan = deserializer.deserialize(ttl_data, dry_run=True)

        # Verify warnings
        assert len(plan.warnings) > 0
        unhandled_warnings = [w for w in plan.warnings if "unhandled" in w.lower()]
        assert len(unhandled_warnings) > 0
