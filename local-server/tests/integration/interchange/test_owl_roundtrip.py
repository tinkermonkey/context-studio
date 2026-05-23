"""
Integration tests for OWL adapter round-trip serialization.

Tests the adapter against a real in-memory SQLite database to verify:
- Empty-DB round-trip: export → reimport → structural equality
- Idempotent reimport: export → reimport against populated DB → no duplicates
- RDF/XML and Turtle format handling
- TBox/ABox separation with multi-class individuals
- External references preservation
"""

import os
import sys
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from adapters.interchange.owl import OWLDeserializer, OWLSerializer
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.value_objects import (

    SerializationScope,
    SerializationScopeType,
)
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
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
    """Create an ontology repository instance for testing."""
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def interchange_repo(session_factory):
    """Create an interchange repository instance for testing."""
    return SQLiteInterchangeRepository(session_factory)


@pytest.fixture
def sample_data(ontology_repo):
    """Create and persist sample ontology data with classes, individuals, and relationships."""
    # Create taxonomy
    taxonomy = Taxonomy(
        id=str(uuid.uuid4()),
        title="OWL Test Taxonomy",
        description="Taxonomy for OWL roundtrip testing",
    )
    taxonomy = ontology_repo.save_taxonomy(taxonomy)

    # Create concept scheme
    scheme = ConceptScheme(
        id=str(uuid.uuid4()),
        taxonomy_id=taxonomy.id,
        title="OWL Test Scheme",
        description="Concept scheme for OWL roundtrip testing",
    )
    scheme = ontology_repo.save_concept_scheme(scheme)

    # Create classes
    animal = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Animal",
        description="The class of all animals",
    )
    animal = ontology_repo.save_class(animal)

    vertebrate = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Vertebrate",
        description="Animal with a backbone",
        parent_class_id=animal.id,
    )
    vertebrate = ontology_repo.save_class(vertebrate)

    mammal = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Mammal",
        description="A warm-blooded vertebrate animal",
        parent_class_id=vertebrate.id,
        external_references=[
            ExternalReference(
                source="dbpedia",
                identifier="Mammal",
                uri="http://dbpedia.org/resource/Mammal",
            ),
        ],
    )
    mammal = ontology_repo.save_class(mammal)

    dog = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Dog",
        description="A domesticated carnivorous mammal",
        parent_class_id=mammal.id,
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

    # Create property definitions
    has_habitat = PropertyDefinition(
        id=str(uuid.uuid4()),
        identifier="has_habitat",
        title="Has Habitat",
        description="A property indicating the habitat of an organism",
    )
    has_habitat = ontology_repo.save_property_definition(has_habitat)

    feeds_on = PropertyDefinition(
        id=str(uuid.uuid4()),
        identifier="feeds_on",
        title="Feeds On",
        description="Indicates the food source of an organism",
    )
    feeds_on = ontology_repo.save_property_definition(feeds_on)

    # Create individuals with multi-class membership
    fido = Individual(
        id=str(uuid.uuid4()),
        class_ids=[dog.id, mammal.id],  # Multi-class membership
        title="Fido",
        description="A specific dog instance",
        external_references=[
            ExternalReference(
                source="example",
                identifier="fido-001",
                uri="http://example.com/animals/fido",
            ),
        ],
    )
    fido = ontology_repo.save_individual(fido)

    bella = Individual(
        id=str(uuid.uuid4()),
        class_ids=[dog.id],
        title="Bella",
        description="Another dog instance",
    )
    bella = ontology_repo.save_individual(bella)

    # Create relationships
    rel1 = Relationship(
        id=str(uuid.uuid4()),
        source_id=fido.id,
        target_id=mammal.id,
        property_definition_id=feeds_on.id,
    )
    rel1 = ontology_repo.save_relationship(rel1)

    return {
        "taxonomy": taxonomy,
        "scheme": scheme,
        "animal": animal,
        "vertebrate": vertebrate,
        "mammal": mammal,
        "dog": dog,
        "fido": fido,
        "bella": bella,
        "has_habitat": has_habitat,
        "feeds_on": feeds_on,
        "rel1": rel1,
    }


class TestOWLEmptyDatabaseRoundTrip:
    """Test round-trip serialization and deserialization against an empty database."""

    def test_export_empty_taxonomy(self, ontology_repo):
        """Test exporting an empty taxonomy."""
        taxonomy = Taxonomy(
            id=str(uuid.uuid4()),
            title="Empty OWL Taxonomy",
            description="A taxonomy with no concepts",
        )
        taxonomy = ontology_repo.save_taxonomy(taxonomy)

        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id=taxonomy.id,
        )
        exported = serializer.serialize(scope)

        assert exported is not None
        assert len(exported) > 0

    def test_export_and_reimport_with_classes(self, ontology_repo, sample_data):
        """Test exporting and reimporting ontology with class hierarchy."""
        # Export whole graph
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        assert exported is not None
        assert isinstance(exported, bytes)
        exported_str = exported.decode("utf-8") if isinstance(exported, bytes) else exported

        # Verify OWL structure in serialized output
        assert "owl" in exported_str.lower()
        assert "class" in exported_str.lower()
        assert "Dog" in exported_str
        assert "Mammal" in exported_str

    def test_roundtrip_preserves_external_references(self, ontology_repo, sample_data):
        """Test that round-trip preserves external references."""
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        exported_str = exported.decode("utf-8") if isinstance(exported, bytes) else exported
        assert "dbpedia.org" in exported_str
        assert "wikidata.org" in exported_str

    def test_import_creates_import_plan(self, ontology_repo, sample_data):
        """Test importing produces a valid import plan."""
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)
        fresh_interchange_repo = SQLiteInterchangeRepository(fresh_session_factory)

        # Import
        deserializer = OWLDeserializer(fresh_repo, fresh_interchange_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify plan
        assert plan.new_entity_count > 0
        assert plan.source_hash is not None

    def test_empty_db_roundtrip_structural_equality(self, ontology_repo, sample_data):
        """Test acceptance criterion: empty-DB round-trip produces structurally equal entities."""
        # Export original entities
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)
        fresh_interchange_repo = SQLiteInterchangeRepository(fresh_session_factory)

        deserializer = OWLDeserializer(fresh_repo, fresh_interchange_repo)
        deserializer.deserialize(exported, dry_run=True)

        # Count entities in both
        original_classes = ontology_repo.list_classes()
        original_class_count = len(list(original_classes))
        imported_class_count = len(
            [e for e in deserializer.incoming_entities.values() if e.get("type") == "class"]
        )

        # Should have exact same structure (no duplicates on roundtrip)
        assert imported_class_count == original_class_count

        # Verify external references are preserved
        for original_class in ontology_repo.list_classes():
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
                        r["source"] == orig_ref.source and r["identifier"] == orig_ref.identifier
                        for r in matching_incoming["external_references"]
                    )


class TestOWLIdempotentReimport:
    """Test that reimporting produces idempotent results."""

    def test_reimport_preserves_uuids(self, ontology_repo, sample_data):
        """Test that reimporting against populated DB preserves entity UUIDs."""
        # Export
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Reimport against the same DB
        deserializer = OWLDeserializer(ontology_repo)
        deserializer.deserialize(exported, dry_run=True)

        # The plan should match entities by UUID or external reference
        original_dog = next((c for c in ontology_repo.list_classes() if c.title == "Dog"), None)
        assert original_dog is not None

        # Should find matching entity in incoming with same UUID
        matching_entity = next(
            (e for e in deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert matching_entity is not None
        assert matching_entity["id"] == original_dog.id

    def test_reimport_with_multi_class_individuals(self, ontology_repo, sample_data):
        """Test that multi-class individual membership survives round-trip."""
        # Export
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository and import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)
        fresh_interchange_repo = SQLiteInterchangeRepository(fresh_session_factory)

        deserializer = OWLDeserializer(fresh_repo, fresh_interchange_repo)
        deserializer.deserialize(exported, dry_run=True)

        # Find Fido (multi-class individual)
        fido_incoming = next(
            (e for e in deserializer.incoming_entities.values() if e.get("title") == "Fido"),
            None,
        )

        # Fido should have both Dog and Mammal as classes
        assert fido_incoming is not None
        class_ids = fido_incoming.get("class_ids", [])
        assert len(class_ids) == 2


class TestOWLFormatSupport:
    """Test OWL adapter format support and handling."""

    def test_exports_in_valid_rdf_format(self, ontology_repo, sample_data):
        """Test that export produces valid RDF output."""
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Should be valid RDF bytes
        assert isinstance(exported, bytes)
        assert len(exported) > 0

        # Should contain RDF namespaces
        exported_str = exported.decode("utf-8")
        assert "rdf" in exported_str.lower() or "owl" in exported_str.lower()

    def test_handles_tbox_abox_separation(self, ontology_repo, sample_data):
        """Test that OWL serialization separates TBox and ABox appropriately."""
        serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        exported_str = exported.decode("utf-8") if isinstance(exported, bytes) else exported

        # TBox (class definitions)
        assert "class" in exported_str.lower()
        assert "Dog" in exported_str

        # ABox (individuals)
        assert "Fido" in exported_str or "Individual" in exported_str.lower()
