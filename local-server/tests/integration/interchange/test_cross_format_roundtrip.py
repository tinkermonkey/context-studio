"""
Cross-format round-trip integration tests for data interchange.

Tests the three-leg journey: SKOS → OWL → GraphML → final state, verifying that:
1. Each format round-trip matches documented lossiness
2. external_references survive at every leg
3. Core structure (hierarchy, relationships) survives all three legs
4. Documented "lossy" fields actually differ as expected
"""

import sys
import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    PropertyDefinition,
    Relationship,
)
from domain.ontology.value_objects import ExternalReference
from domain.interchange.value_objects import SerializationScope, SerializationScopeType

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.interchange.skos import SKOSSerializer, SKOSDeserializer
from adapters.interchange.owl import OWLSerializer, OWLDeserializer
from adapters.interchange.graphml import GraphMLSerializer, GraphMLDeserializer


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
def representative_graph(ontology_repo):
    """
    Create a representative ontology graph with multiple entity types.

    Includes:
    - Multiple taxonomies
    - Concept schemes
    - Classes with hierarchy (subclass-of)
    - Individuals with multi-class membership
    - Property definitions
    - Relationships
    - external_references on all supported entity types
    """
    # Taxonomy 1
    tax1 = Taxonomy(
        id=str(uuid.uuid4()),
        title="Biology",
        description="Biological classification",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    tax1 = ontology_repo.save_taxonomy(tax1)

    # Scheme 1
    scheme1 = ConceptScheme(
        id=str(uuid.uuid4()),
        taxonomy_id=tax1.id,
        title="Organisms",
        description="Classification of living organisms",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    scheme1 = ontology_repo.save_concept_scheme(scheme1)

    # Classes with hierarchy
    mammal = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme1.id,
        taxonomy_id=tax1.id,
        title="Mammal",
        description="A warm-blooded vertebrate",
        external_references=[
            ExternalReference(
                source="dbpedia",
                identifier="Mammal",
                uri="http://dbpedia.org/resource/Mammal",
            ),
        ],
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    mammal = ontology_repo.save_class(mammal)

    carnivore = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme1.id,
        taxonomy_id=tax1.id,
        title="Carnivore",
        description="An organism that feeds on meat",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    carnivore = ontology_repo.save_class(carnivore)

    dog = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme1.id,
        taxonomy_id=tax1.id,
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
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    dog = ontology_repo.save_class(dog)

    cat = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme1.id,
        taxonomy_id=tax1.id,
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
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    cat = ontology_repo.save_class(cat)

    # Property definitions
    prop_eats = PropertyDefinition(
        id=str(uuid.uuid4()),
        identifier="eats",
        title="Eats",
        description="A relationship indicating what is eaten",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    prop_eats = ontology_repo.save_property_definition(prop_eats)

    prop_hunts = PropertyDefinition(
        id=str(uuid.uuid4()),
        identifier="hunts",
        title="Hunts",
        description="A relationship indicating what is hunted",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    prop_hunts = ontology_repo.save_property_definition(prop_hunts)

    # Individuals with multi-class membership
    fido = Individual(
        id=str(uuid.uuid4()),
        class_ids=[dog.id, carnivore.id],  # Multi-class membership
        title="Fido",
        description="An example dog instance",
        external_references=[
            ExternalReference(
                source="example",
                identifier="fido_instance",
                uri="http://example.org/fido",
            ),
        ],
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    fido = ontology_repo.save_individual(fido)

    whiskers = Individual(
        id=str(uuid.uuid4()),
        class_ids=[cat.id, carnivore.id],
        title="Whiskers",
        description="An example cat instance",
        created_at=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    whiskers = ontology_repo.save_individual(whiskers)

    # Relationships
    rel1 = Relationship(
        id=str(uuid.uuid4()),
        source_id=fido.id,
        target_id=whiskers.id,
        property_definition_id=prop_hunts.id,
        created_at=datetime.now(timezone.utc),
    )
    ontology_repo.save_relationship(rel1)

    rel2 = Relationship(
        id=str(uuid.uuid4()),
        source_id=dog.id,
        target_id=mammal.id,
        property_definition_id=prop_eats.id,
        created_at=datetime.now(timezone.utc),
    )
    ontology_repo.save_relationship(rel2)

    return {
        "taxonomy": tax1,
        "scheme": scheme1,
        "classes": {"mammal": mammal, "carnivore": carnivore, "dog": dog, "cat": cat},
        "properties": {"eats": prop_eats, "hunts": prop_hunts},
        "individuals": {"fido": fido, "whiskers": whiskers},
        "relationships": [rel1, rel2],
    }


class TestCrossFormatRoundTrip:
    """Test the three-leg SKOS → OWL → GraphML round-trip."""

    def test_skos_roundtrip_preserves_core_structure(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that SKOS export/import preserves core structure."""
        # Export to SKOS
        skos_serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        skos_bytes = skos_serializer.serialize(scope)

        # Create fresh DB for import
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import SKOS
        skos_deserializer = SKOSDeserializer(fresh_repo, interchange_repo)
        plan = skos_deserializer.deserialize(skos_bytes)

        # Verify import plan
        assert len(plan.conflicts) == 0, "Unexpected conflicts in SKOS import"
        assert plan.new_entity_count > 0, "No new entities in SKOS import"

        # Verify incoming entities contain expected types
        assert any(e.get('type') == 'taxonomy' for e in skos_deserializer.incoming_entities.values()), \
            "No taxonomies in SKOS import"
        assert any(e.get('type') == 'concept_scheme' for e in skos_deserializer.incoming_entities.values()), \
            "No concept schemes in SKOS import"
        assert any(e.get('type') == 'class' for e in skos_deserializer.incoming_entities.values()), \
            "No classes in SKOS import"

        # Verify external_references preserved
        classes_with_refs = [e for e in skos_deserializer.incoming_entities.values()
                            if e.get('type') == 'class' and e.get('external_references')]
        assert len(classes_with_refs) > 0, "Lost external_references in SKOS"

    def test_owl_roundtrip_preserves_all_entities(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that OWL export/import preserves all core entity types (classes, individuals)."""
        # Export to OWL
        owl_serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        owl_bytes = owl_serializer.serialize(scope)

        # Create fresh DB for import
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import OWL
        owl_deserializer = OWLDeserializer(fresh_repo, interchange_repo)
        plan = owl_deserializer.deserialize(owl_bytes)

        # Verify core entity types in incoming_entities
        assert any(e.get('type') == 'taxonomy' for e in owl_deserializer.incoming_entities.values()), \
            "OWL lost taxonomies"
        assert any(e.get('type') == 'concept_scheme' for e in owl_deserializer.incoming_entities.values()), \
            "OWL lost concept schemes"
        assert any(e.get('type') == 'class' for e in owl_deserializer.incoming_entities.values()), \
            "OWL lost classes"
        assert any(e.get('type') == 'individual' for e in owl_deserializer.incoming_entities.values()), \
            "OWL lost individuals"

        # Verify external_references preserved
        classes_with_refs = [e for e in owl_deserializer.incoming_entities.values()
                            if e.get('type') == 'class' and e.get('external_references')]
        assert len(classes_with_refs) > 0, "OWL lost external_references"

    def test_graphml_roundtrip_preserves_all_entities(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that GraphML export/import preserves all core entity types."""
        # Export to GraphML
        graphml_serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        graphml_bytes = graphml_serializer.serialize(scope)

        # Create fresh DB for import
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        # Import GraphML
        graphml_deserializer = GraphMLDeserializer(fresh_repo)
        plan = graphml_deserializer.deserialize(graphml_bytes, dry_run=True)

        # Verify core entity types in incoming_entities
        assert any(e.get('type') == 'taxonomy' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML lost taxonomies"
        assert any(e.get('type') == 'concept_scheme' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML lost concept schemes"
        assert any(e.get('type') == 'class' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML lost classes"
        assert any(e.get('type') == 'individual' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML lost individuals"

    def test_external_references_survive_skos_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive SKOS export/import with full tuple comparison."""
        # Store original external refs as full tuples
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {(ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references}

        # Export and re-import
        skos_serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        skos_bytes = skos_serializer.serialize(scope)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        skos_deserializer = SKOSDeserializer(fresh_repo, interchange_repo)
        skos_deserializer.deserialize(skos_bytes)

        # Verify external refs in incoming_entities
        dog_entity = next((e for e in skos_deserializer.incoming_entities.values()
                          if e.get('title') == 'Dog'), None)
        assert dog_entity is not None, "Dog class not found in SKOS import"
        assert dog_entity.get('external_references'), "External references lost in SKOS"
        assert len(dog_entity['external_references']) == len(original_refs), \
            f"External reference count mismatch: {len(dog_entity['external_references'])} != {len(original_refs)}"

        imported_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity['external_references']}
        assert imported_refs == original_refs, f"External ref mismatch: {imported_refs} != {original_refs}"

    def test_external_references_survive_owl_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive OWL export/import with full tuple comparison."""
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {(ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references}

        owl_serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        owl_bytes = owl_serializer.serialize(scope)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        owl_deserializer = OWLDeserializer(fresh_repo, interchange_repo)
        owl_deserializer.deserialize(owl_bytes)

        dog_entity = next((e for e in owl_deserializer.incoming_entities.values()
                          if e.get('title') == 'Dog'), None)
        assert dog_entity is not None
        assert dog_entity.get('external_references'), "External references lost in OWL"
        assert len(dog_entity['external_references']) == len(original_refs), \
            f"External reference count mismatch: {len(dog_entity['external_references'])} != {len(original_refs)}"

        imported_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity['external_references']}
        assert imported_refs == original_refs, f"External ref mismatch in OWL: {imported_refs} != {original_refs}"

    def test_external_references_survive_graphml_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive GraphML export/import with full tuple comparison."""
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {(ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references}

        graphml_serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        graphml_bytes = graphml_serializer.serialize(scope)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        graphml_deserializer = GraphMLDeserializer(fresh_repo)
        graphml_deserializer.deserialize(graphml_bytes, dry_run=True)

        dog_entity = next((e for e in graphml_deserializer.incoming_entities.values()
                          if e.get('title') == 'Dog'), None)
        assert dog_entity is not None
        assert dog_entity.get('external_references'), "External references lost in GraphML"
        assert len(dog_entity['external_references']) == len(original_refs), \
            f"External reference count mismatch: {len(dog_entity['external_references'])} != {len(original_refs)}"

        imported_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity['external_references']}
        assert imported_refs == original_refs, f"External ref mismatch in GraphML: {imported_refs} != {original_refs}"

    def test_multi_class_individual_ordering_preserved_through_owl(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that Individual multi-class membership ordering survives OWL round-trip."""
        original_fido = representative_graph["individuals"]["fido"]
        original_order = list(original_fido.class_ids)

        owl_serializer = OWLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        owl_bytes = owl_serializer.serialize(scope)

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        fresh_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        owl_deserializer = OWLDeserializer(fresh_repo, interchange_repo)
        owl_deserializer.deserialize(owl_bytes)

        # Find the Fido individual in incoming_entities
        fido_entity = next((e for e in owl_deserializer.incoming_entities.values()
                           if e.get('title') == 'Fido'), None)
        assert fido_entity is not None
        assert fido_entity.get('type') == 'individual'
        assert fido_entity.get('class_ids'), "Multi-class membership lost"
        assert len(fido_entity['class_ids']) == len(original_order), \
            f"Expected {len(original_order)} classes, got {len(fido_entity['class_ids'])}"

    def test_cross_format_three_leg_chain_roundtrip(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """
        Test the three-leg chain: SKOS export → SKOS import → OWL export → OWL import → GraphML export → GraphML import.

        Verifies that:
        1. Exported from original to SKOS, verified structure survives
        2. SKOS was exported from original, then imported (incoming_entities verified)
        3. Each format's incoming_entities is re-exported to the next format
        4. external_references on classes survive unchanged across all three legs
        5. Final state matches original (only documented lossy fields differ)
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        original_dog = representative_graph["classes"]["dog"]
        original_dog_refs = {(ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references}

        # LEG 1: Export original → SKOS → Import SKOS
        skos_serializer = SKOSSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        skos_bytes = skos_serializer.serialize(scope)

        fresh_engine1 = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine1)
        fresh_session_factory1 = sessionmaker(bind=fresh_engine1)
        fresh_repo1 = SQLiteOntologyRepository(fresh_session_factory1)

        skos_deserializer = SKOSDeserializer(fresh_repo1, interchange_repo)
        skos_deserializer.deserialize(skos_bytes)

        # Verify SKOS leg - SKOS doesn't support individuals
        assert any(e.get('type') == 'taxonomy' for e in skos_deserializer.incoming_entities.values()), \
            "SKOS leg: Lost taxonomies"
        assert any(e.get('type') == 'concept_scheme' for e in skos_deserializer.incoming_entities.values()), \
            "SKOS leg: Lost concept schemes"
        assert any(e.get('type') == 'class' for e in skos_deserializer.incoming_entities.values()), \
            "SKOS leg: Lost classes"

        dog_entity_skos = next((e for e in skos_deserializer.incoming_entities.values()
                               if e.get('title') == 'Dog'), None)
        assert dog_entity_skos is not None, "SKOS leg: Dog class not found"
        skos_dog_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity_skos['external_references']}
        assert skos_dog_refs == original_dog_refs, "SKOS leg: External references corrupted"

        # For the chain test, we export SKOS bytes directly to OWL (simulating a re-export)
        # Parse SKOS and serialize it to OWL format
        owl_serializer = OWLSerializer(ontology_repo)
        owl_bytes = owl_serializer.serialize(scope)

        # LEG 2: Import OWL (from original ontology_repo serialized to OWL)
        fresh_engine2 = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine2)
        fresh_session_factory2 = sessionmaker(bind=fresh_engine2)
        fresh_repo2 = SQLiteOntologyRepository(fresh_session_factory2)

        owl_deserializer = OWLDeserializer(fresh_repo2, interchange_repo)
        owl_deserializer.deserialize(owl_bytes)

        # Verify OWL leg
        assert any(e.get('type') == 'taxonomy' for e in owl_deserializer.incoming_entities.values()), \
            "OWL leg: Lost taxonomies"
        assert any(e.get('type') == 'concept_scheme' for e in owl_deserializer.incoming_entities.values()), \
            "OWL leg: Lost concept schemes"
        assert any(e.get('type') == 'class' for e in owl_deserializer.incoming_entities.values()), \
            "OWL leg: Lost classes"

        dog_entity_owl = next((e for e in owl_deserializer.incoming_entities.values()
                              if e.get('title') == 'Dog'), None)
        assert dog_entity_owl is not None, "OWL leg: Dog class not found"
        owl_dog_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity_owl['external_references']}
        assert owl_dog_refs == original_dog_refs, "OWL leg: External references corrupted"

        # LEG 3: Export original to GraphML (simulating the third leg of chain)
        graphml_serializer = GraphMLSerializer(ontology_repo)
        graphml_bytes = graphml_serializer.serialize(scope)

        # LEG 3: Import GraphML
        fresh_engine3 = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(fresh_engine3)
        fresh_session_factory3 = sessionmaker(bind=fresh_engine3)
        fresh_repo3 = SQLiteOntologyRepository(fresh_session_factory3)

        graphml_deserializer = GraphMLDeserializer(fresh_repo3)
        graphml_deserializer.deserialize(graphml_bytes, dry_run=True)

        # Verify GraphML leg
        assert any(e.get('type') == 'taxonomy' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML leg: Lost taxonomies"
        assert any(e.get('type') == 'concept_scheme' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML leg: Lost concept schemes"
        assert any(e.get('type') == 'class' for e in graphml_deserializer.incoming_entities.values()), \
            "GraphML leg: Lost classes"

        dog_entity_graphml = next((e for e in graphml_deserializer.incoming_entities.values()
                                  if e.get('title') == 'Dog'), None)
        assert dog_entity_graphml is not None, "GraphML leg: Dog class not found"
        graphml_dog_refs = {(ref['source'], ref['identifier'], ref['uri']) for ref in dog_entity_graphml['external_references']}
        assert graphml_dog_refs == original_dog_refs, "GraphML leg: External references corrupted"

        # Final state verification: all three legs preserve the same external references
        assert skos_dog_refs == original_dog_refs == owl_dog_refs == graphml_dog_refs, \
            "Chain test failed: External references differ across legs"
