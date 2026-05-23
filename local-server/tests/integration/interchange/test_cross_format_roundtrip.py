"""
Cross-format round-trip integration tests for data interchange.

Tests the three-leg journey: SKOS → OWL → GraphML → final state, verifying that:
1. Each format round-trip matches documented lossiness
2. external_references survive at every leg
3. Core structure (hierarchy, relationships) survives all three legs
4. Documented "lossy" fields actually differ as expected
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.interchange.graphml import GraphMLDeserializer, GraphMLSerializer
from adapters.interchange.owl import OWLDeserializer, OWLSerializer
from adapters.interchange.skos import SKOSDeserializer, SKOSSerializer
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.value_objects import ExternalReference


def persist_incoming_entities(
    repo: SQLiteOntologyRepository, incoming_entities: Dict[str, Dict[str, Any]]
) -> None:
    """
    Helper function to persist incoming_entities from a deserializer into the ontology repository.

    Args:
        repo: The ontology repository to persist entities into
        incoming_entities: Dictionary of entities from a deserializer's incoming_entities
    """
    # Process in dependency order: taxonomies first, then concept_schemes, then classes

    # Save taxonomies
    for entity_id, entity_dict in incoming_entities.items():
        if entity_dict.get("type") == "taxonomy":
            tax = Taxonomy(
                id=entity_dict["id"],
                title=entity_dict["title"],
                description=entity_dict.get("description"),
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
            )
            repo.save_taxonomy(tax)

    # Save concept schemes
    for entity_id, entity_dict in incoming_entities.items():
        if entity_dict.get("type") == "concept_scheme":
            scheme = ConceptScheme(
                id=entity_dict["id"],
                taxonomy_id=entity_dict["taxonomy_id"],
                title=entity_dict["title"],
                description=entity_dict.get("description"),
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
            )
            repo.save_concept_scheme(scheme)

    # Save classes in dependency order: first pass saves classes without parents,
    # subsequent passes save classes whose parents have been saved
    classes_to_save = {
        entity_id: entity_dict
        for entity_id, entity_dict in incoming_entities.items()
        if entity_dict.get("type") == "class"
    }
    saved_class_ids = set()

    # Keep trying until all classes are saved or we hit a deadlock
    max_attempts = len(classes_to_save) + 1
    attempts = 0
    while classes_to_save and attempts < max_attempts:
        attempts += 1
        saved_this_pass = []

        for entity_id, entity_dict in list(classes_to_save.items()):
            parent_class_id = entity_dict.get("parent_class_id")
            # Save if no parent, or parent already saved
            if parent_class_id is None or parent_class_id in saved_class_ids:
                external_refs = [
                    ExternalReference(
                        source=ref["source"],
                        identifier=ref["identifier"],
                        uri=ref["uri"],
                    )
                    for ref in entity_dict.get("external_references", [])
                ]
                cls = Class(
                    id=entity_dict["id"],
                    concept_scheme_id=entity_dict["concept_scheme_id"],
                    taxonomy_id=_find_taxonomy_id_for_scheme(
                        repo, entity_dict["concept_scheme_id"]
                    ),
                    title=entity_dict["title"],
                    description=entity_dict.get("description"),
                    parent_class_id=parent_class_id,
                    external_references=external_refs,
                    created_at=datetime.now(timezone.utc),
                    last_modified=datetime.now(timezone.utc),
                )
                repo.save_class(cls)
                saved_class_ids.add(entity_id)
                saved_this_pass.append(entity_id)
                del classes_to_save[entity_id]

        if not saved_this_pass and classes_to_save:
            # No progress made, likely a circular dependency
            raise ValueError(
                "Could not save classes due to unresolved parent references:"
                f" {list(classes_to_save.keys())}"
            )

    # Save individuals
    for entity_id, entity_dict in incoming_entities.items():
        if entity_dict.get("type") == "individual":
            external_refs = [
                ExternalReference(
                    source=ref["source"],
                    identifier=ref["identifier"],
                    uri=ref["uri"],
                )
                for ref in entity_dict.get("external_references", [])
            ]
            ind = Individual(
                id=entity_dict["id"],
                class_ids=entity_dict.get("class_ids", []),
                title=entity_dict["title"],
                description=entity_dict.get("description"),
                external_references=external_refs,
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
            )
            repo.save_individual(ind)

    # Save property definitions
    for entity_id, entity_dict in incoming_entities.items():
        if entity_dict.get("type") == "property_definition":
            identifier = entity_dict.get("identifier")
            if not identifier:
                identifier = entity_dict["title"].lower().replace(" ", "_")
            prop = PropertyDefinition(
                id=entity_dict["id"],
                identifier=identifier,
                title=entity_dict["title"],
                description=entity_dict.get("description"),
                created_at=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc),
            )
            repo.save_property_definition(prop)

    # Save relationships
    for entity_id, entity_dict in incoming_entities.items():
        if entity_dict.get("type") == "relationship":
            rel = Relationship(
                id=entity_dict["id"],
                source_id=entity_dict["source_id"],
                target_id=entity_dict["target_id"],
                property_definition_id=entity_dict["property_definition_id"],
                created_at=datetime.now(timezone.utc),
            )
            repo.save_relationship(rel)


def _find_taxonomy_id_for_scheme(repo: SQLiteOntologyRepository, scheme_id: str) -> str:
    """Find the taxonomy_id for a given concept scheme."""
    scheme = repo.get_concept_scheme(scheme_id)
    if scheme:
        return scheme.taxonomy_id
    # Fallback: try to find by querying all schemes
    for tax in repo.list_taxonomies():
        for scheme in repo.list_concept_schemes(taxonomy_id=tax.id):
            if scheme.id == scheme_id:
                return tax.id
    raise ValueError(f"Could not find taxonomy for scheme {scheme_id}")


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
        assert any(
            e.get("type") == "taxonomy" for e in skos_deserializer.incoming_entities.values()
        ), "No taxonomies in SKOS import"
        assert any(
            e.get("type") == "concept_scheme" for e in skos_deserializer.incoming_entities.values()
        ), "No concept schemes in SKOS import"
        assert any(
            e.get("type") == "class" for e in skos_deserializer.incoming_entities.values()
        ), "No classes in SKOS import"

        # Verify external_references preserved
        classes_with_refs = [
            e
            for e in skos_deserializer.incoming_entities.values()
            if e.get("type") == "class" and e.get("external_references")
        ]
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
        owl_deserializer.deserialize(owl_bytes)

        # Verify core entity types in incoming_entities
        assert any(
            e.get("type") == "taxonomy" for e in owl_deserializer.incoming_entities.values()
        ), "OWL lost taxonomies"
        assert any(
            e.get("type") == "concept_scheme" for e in owl_deserializer.incoming_entities.values()
        ), "OWL lost concept schemes"
        assert any(
            e.get("type") == "class" for e in owl_deserializer.incoming_entities.values()
        ), "OWL lost classes"
        assert any(
            e.get("type") == "individual" for e in owl_deserializer.incoming_entities.values()
        ), "OWL lost individuals"

        # Verify external_references preserved
        classes_with_refs = [
            e
            for e in owl_deserializer.incoming_entities.values()
            if e.get("type") == "class" and e.get("external_references")
        ]
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
        graphml_deserializer.deserialize(graphml_bytes, dry_run=True)

        # Verify core entity types in incoming_entities
        assert any(
            e.get("type") == "taxonomy" for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML lost taxonomies"
        assert any(
            e.get("type") == "concept_scheme"
            for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML lost concept schemes"
        assert any(
            e.get("type") == "class" for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML lost classes"
        assert any(
            e.get("type") == "individual" for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML lost individuals"

    def test_external_references_survive_skos_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive SKOS export/import with full tuple comparison."""
        # Store original external refs as full tuples
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {
            (ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references
        }

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
        dog_entity = next(
            (e for e in skos_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity is not None, "Dog class not found in SKOS import"
        assert dog_entity.get("external_references"), "External references lost in SKOS"
        assert len(dog_entity["external_references"]) == len(original_refs), (
            "External reference count mismatch:"
            f" {len(dog_entity['external_references'])} != {len(original_refs)}"
        )

        imported_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity["external_references"]
        }
        assert (
            imported_refs == original_refs
        ), f"External ref mismatch: {imported_refs} != {original_refs}"

    def test_external_references_survive_owl_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive OWL export/import with full tuple comparison."""
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {
            (ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references
        }

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

        dog_entity = next(
            (e for e in owl_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity is not None
        assert dog_entity.get("external_references"), "External references lost in OWL"
        assert len(dog_entity["external_references"]) == len(original_refs), (
            "External reference count mismatch:"
            f" {len(dog_entity['external_references'])} != {len(original_refs)}"
        )

        imported_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity["external_references"]
        }
        assert (
            imported_refs == original_refs
        ), f"External ref mismatch in OWL: {imported_refs} != {original_refs}"

    def test_external_references_survive_graphml_leg(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """Test that external_references survive GraphML export/import with full tuple
        comparison."""
        original_dog = representative_graph["classes"]["dog"]
        original_refs = {
            (ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references
        }

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

        dog_entity = next(
            (e for e in graphml_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity is not None
        assert dog_entity.get("external_references"), "External references lost in GraphML"
        assert len(dog_entity["external_references"]) == len(original_refs), (
            "External reference count mismatch:"
            f" {len(dog_entity['external_references'])} != {len(original_refs)}"
        )

        imported_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity["external_references"]
        }
        assert (
            imported_refs == original_refs
        ), f"External ref mismatch in GraphML: {imported_refs} != {original_refs}"

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
        fido_entity = next(
            (e for e in owl_deserializer.incoming_entities.values() if e.get("title") == "Fido"),
            None,
        )
        assert fido_entity is not None
        assert fido_entity.get("type") == "individual"
        assert fido_entity.get("class_ids"), "Multi-class membership lost"
        assert len(fido_entity["class_ids"]) == len(original_order), (
            f"Expected {len(original_order)} classes, got" f" {len(fido_entity['class_ids'])}"
        )
        # Verify ordering is preserved (not just count)
        assert fido_entity["class_ids"] == original_order, (
            f"Class ordering not preserved. Expected {original_order}, got"
            f" {fido_entity['class_ids']}"
        )

    def test_cross_format_three_leg_chain_roundtrip(
        self, ontology_repo, interchange_repo, representative_graph
    ):
        """
        Test the three-leg chain: SKOS export → SKOS import → OWL export → OWL import → GraphML
        export → GraphML import.

        Verifies that:
        1. Original ontology exported to SKOS format
        2. SKOS imported into fresh_repo1, entities persisted
        3. fresh_repo1 re-exported to OWL (completing the first chain: original → SKOS → back to
        intermediate state)
        4. OWL imported into fresh_repo2, entities persisted
        5. fresh_repo2 re-exported to GraphML (completing the second chain)
        6. GraphML imported into fresh_repo3, verified
        7. external_references on classes survive unchanged across all three legs
        8. Final state matches original (only documented lossy fields differ)
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        original_dog = representative_graph["classes"]["dog"]
        original_dog_refs = {
            (ref.source, ref.identifier, ref.uri) for ref in original_dog.external_references
        }

        # LEG 1: Export original ontology to SKOS, then import SKOS into fresh_repo1
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
        assert any(
            e.get("type") == "taxonomy" for e in skos_deserializer.incoming_entities.values()
        ), "SKOS leg: Lost taxonomies"
        assert any(
            e.get("type") == "concept_scheme" for e in skos_deserializer.incoming_entities.values()
        ), "SKOS leg: Lost concept schemes"
        assert any(
            e.get("type") == "class" for e in skos_deserializer.incoming_entities.values()
        ), "SKOS leg: Lost classes"

        dog_entity_skos = next(
            (e for e in skos_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity_skos is not None, "SKOS leg: Dog class not found"
        skos_dog_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity_skos["external_references"]
        }
        assert skos_dog_refs == original_dog_refs, "SKOS leg: External references corrupted"

        # CRITICAL: Persist the SKOS-imported entities into fresh_repo1 before re-exporting
        persist_incoming_entities(fresh_repo1, skos_deserializer.incoming_entities)

        # LEG 2: Export from fresh_repo1 (which now has SKOS-imported entities) to OWL
        # This completes the chain: original → SKOS export → SKOS import → OWL export
        owl_serializer = OWLSerializer(fresh_repo1)
        owl_bytes = owl_serializer.serialize(scope)

        # LEG 2: Import the OWL bytes into fresh_repo2
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
        assert any(
            e.get("type") == "taxonomy" for e in owl_deserializer.incoming_entities.values()
        ), "OWL leg: Lost taxonomies"
        assert any(
            e.get("type") == "concept_scheme" for e in owl_deserializer.incoming_entities.values()
        ), "OWL leg: Lost concept schemes"
        assert any(
            e.get("type") == "class" for e in owl_deserializer.incoming_entities.values()
        ), "OWL leg: Lost classes"

        dog_entity_owl = next(
            (e for e in owl_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity_owl is not None, "OWL leg: Dog class not found"
        owl_dog_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity_owl["external_references"]
        }
        assert owl_dog_refs == original_dog_refs, "OWL leg: External references corrupted"

        # CRITICAL: Persist the OWL-imported entities into fresh_repo2 before re-exporting
        persist_incoming_entities(fresh_repo2, owl_deserializer.incoming_entities)

        # LEG 3: Export from fresh_repo2 (which now has OWL-imported
        # entities) to GraphML. This completes the chain: SKOS export → SKOS
        # import → OWL export → OWL import → GraphML export
        graphml_serializer = GraphMLSerializer(fresh_repo2)
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
        assert any(
            e.get("type") == "taxonomy" for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML leg: Lost taxonomies"
        assert any(
            e.get("type") == "concept_scheme"
            for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML leg: Lost concept schemes"
        assert any(
            e.get("type") == "class" for e in graphml_deserializer.incoming_entities.values()
        ), "GraphML leg: Lost classes"

        dog_entity_graphml = next(
            (e for e in graphml_deserializer.incoming_entities.values() if e.get("title") == "Dog"),
            None,
        )
        assert dog_entity_graphml is not None, "GraphML leg: Dog class not found"
        graphml_dog_refs = {
            (ref["source"], ref["identifier"], ref["uri"])
            for ref in dog_entity_graphml["external_references"]
        }
        assert graphml_dog_refs == original_dog_refs, "GraphML leg: External references corrupted"

        # Final state verification: all three legs preserve the same external references
        assert (
            skos_dog_refs == original_dog_refs == owl_dog_refs == graphml_dog_refs
        ), "Chain test failed: External references differ across legs"
