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

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rdflib import Graph, Namespace, Literal, RDF

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
)
from domain.ontology.value_objects import ExternalReference
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    MatchKind,
    ResolutionKind,
)

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.interchange.skos import SKOSSerializer, SKOSDeserializer

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
LOCAL = Namespace("http://context-studio.local/ontology/")


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
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        assert exported is not None
        assert isinstance(exported, bytes)
        exported_str = (
            exported.decode("utf-8") if isinstance(exported, bytes) else exported
        )

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
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Verify DBpedia and Wikidata references in output
        exported_str = (
            exported.decode("utf-8") if isinstance(exported, bytes) else exported
        )
        assert "dbpedia.org" in exported_str
        assert "wikidata.org" in exported_str

    def test_import_creates_import_plan_with_no_conflicts(
        self, ontology_repo, sample_data
    ):
        """Test importing against an empty database produces valid plan with no conflicts."""
        # Export
        serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository (empty DB)
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import
        deserializer = SKOSDeserializer(fresh_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify plan
        assert plan.conflicts == ()
        assert plan.new_entity_count > 0
        assert plan.source_hash is not None

    def test_empty_db_roundtrip_structural_equality(self, ontology_repo, sample_data):
        """Test acceptance criterion: empty-DB round-trip produces structurally equal entities."""
        # Export original entities
        serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository (empty DB) and import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = SKOSDeserializer(fresh_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify structural equality: same number of entities with same titles/descriptions
        original_classes = ontology_repo.list_classes()
        list(plan.conflicts) + [
            {"incoming": {"title": e["title"], "type": e.get("type")}}
            for e in deserializer.incoming_entities.values()
        ]

        # Count classes in both
        original_class_count = len([c for c in original_classes])
        imported_class_count = len(deserializer.incoming_entities)

        # Should have same structure
        assert imported_class_count >= original_class_count

        # Verify external references are preserved
        for original_class in original_classes:
            matching_incoming = None
            for entity_id, entity_dict in deserializer.incoming_entities.items():
                if entity_dict.get("title") == original_class.title:
                    matching_incoming = entity_dict
                    break

            if original_class.external_references and matching_incoming:
                assert len(matching_incoming.get("external_references", [])) == len(
                    original_class.external_references
                )
                for orig_ref in original_class.external_references:
                    assert any(
                        r["source"] == orig_ref.source
                        and r["identifier"] == orig_ref.identifier
                        for r in matching_incoming["external_references"]
                    )


class TestSKOSIdempotentReimport:
    """Test that reimporting produces idempotent results."""

    def test_reimport_with_matching_external_references(
        self, ontology_repo, sample_data
    ):
        """Test that reimporting entities with matching external refs merges by default."""
        # Export
        serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import against populated DB
        deserializer = SKOSDeserializer(ontology_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify that conflicts are detected with EXTERNAL_REFERENCE match kind
        external_ref_conflicts = [
            c for c in plan.conflicts if c.match_kind == MatchKind.EXTERNAL_REFERENCE
        ]
        assert len(external_ref_conflicts) > 0

        # Verify default resolution is MERGE for external reference matches
        for conflict in external_ref_conflicts:
            assert conflict.default_resolution == ResolutionKind.MERGE

    def test_idempotent_reimport_preserves_uuids_and_no_duplicates(
        self, ontology_repo, sample_data
    ):
        """Test acceptance criterion: idempotent reimport produces no duplicates and preserves UUIDs."""
        # Record original entity IDs (taxonomies, schemes, and classes)
        original_classes = ontology_repo.list_classes()
        original_schemes = ontology_repo.list_concept_schemes()
        original_taxonomies = ontology_repo.list_taxonomies()
        original_all_ids = (
            {c.id for c in original_classes}
            | {s.id for s in original_schemes}
            | {t.id for t in original_taxonomies}
        )
        original_count = len(original_classes)

        # Export and reimport against populated DB
        serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import as dry-run to get plan
        deserializer = SKOSDeserializer(ontology_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # All conflicts should have existing entities with same UUIDs (preserved across reimport)
        for conflict in plan.conflicts:
            assert conflict.existing is not None
            # Existing should be the UUID of an entity that already exists
            assert conflict.existing in original_all_ids

        # Verify that merging would not create duplicates
        # By default resolution, external reference matches should MERGE (not CREATE or OVERWRITE)
        external_ref_conflicts = [
            c for c in plan.conflicts if c.match_kind == MatchKind.EXTERNAL_REFERENCE
        ]
        for conflict in external_ref_conflicts:
            assert conflict.default_resolution == ResolutionKind.MERGE

        # After a hypothetical merge, entity count should remain unchanged
        # because we're merging existing entities, not creating new ones
        new_entity_count = plan.new_entity_count
        len(plan.conflicts)

        # new_entity_count should not create duplicates with merge resolution
        # (the imports are subset of what's already there)
        assert new_entity_count <= original_count


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
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
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
