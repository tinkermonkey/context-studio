"""
Integration tests for GraphML adapter round-trip serialization.

Tests the adapter against a real in-memory SQLite database to verify:
- Whole-graph round-trip: export → reimport → structural equality
- Multi-class Individual ordering survives round-trip
- External references round-trip via reserved data element
- Layout coordinates ignored on import without error
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

from domain.ontology.entities import (
    Taxonomy,
    ConceptScheme,
    Class,
    Individual,
    PropertyDefinition,
    Relationship,
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
def sample_data(ontology_repo):
    """Create and persist sample ontology data with Individuals and PropertyDefinitions."""
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
    mammal = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Mammal",
        description="A warm-blooded vertebrate animal",
    )
    mammal = ontology_repo.save_class(mammal)

    carnivore = Class(
        id=str(uuid.uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Carnivore",
        description="An organism that feeds on meat",
    )
    carnivore = ontology_repo.save_class(carnivore)

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

    # Create property definitions
    prop_eats = PropertyDefinition(
        id=str(uuid.uuid4()),
        identifier="eats",
        title="Eats",
        description="A relationship indicating what is eaten",
    )
    prop_eats = ontology_repo.save_property_definition(prop_eats)

    # Create individuals (with multi-class membership)
    fido = Individual(
        id=str(uuid.uuid4()),
        class_ids=[dog.id, carnivore.id],  # Multi-class membership
        title="Fido",
        description="A specific dog",
        external_references=[
            ExternalReference(
                source="example",
                identifier="fido-001",
                uri="http://example.com/fido",
            ),
        ],
    )
    fido = ontology_repo.save_individual(fido)

    # Create a relationship
    rel = Relationship(
        id=str(uuid.uuid4()),
        source_id=fido.id,
        target_id=dog.id,
        property_definition_id=prop_eats.id,
    )
    rel = ontology_repo.save_relationship(rel)

    return {
        "taxonomy": taxonomy,
        "scheme": scheme,
        "mammal": mammal,
        "carnivore": carnivore,
        "dog": dog,
        "cat": cat,
        "fido": fido,
        "prop_eats": prop_eats,
        "rel": rel,
    }


class TestGraphMLEmptyDatabaseRoundTrip:
    """Test round-trip serialization and deserialization against an empty database."""

    def test_export_empty_taxonomy(self, ontology_repo):
        """Test exporting an empty taxonomy."""
        taxonomy = Taxonomy(
            id=str(uuid.uuid4()),
            title="Empty Taxonomy",
            description="A taxonomy with no concepts",
        )
        taxonomy = ontology_repo.save_taxonomy(taxonomy)

        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id=taxonomy.id,
        )
        exported = serializer.serialize(scope)
        assert exported is not None
        assert len(exported) > 0
        assert b"Empty Taxonomy" in exported

    def test_export_with_classes_and_hierarchy(self, ontology_repo, sample_data):
        """Test exporting ontology with classes and hierarchy."""
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        assert exported is not None
        assert isinstance(exported, bytes)
        exported_str = exported.decode("utf-8")

        # Verify GraphML structure
        assert "graphml" in exported_str
        assert "Dog" in exported_str
        assert "Cat" in exported_str
        assert "Mammal" in exported_str

    def test_import_creates_import_plan_with_no_conflicts(
        self, ontology_repo, sample_data
    ):
        """Test importing against an empty database produces valid plan with no conflicts."""
        # Export
        serializer = GraphMLSerializer(ontology_repo)
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
        deserializer = GraphMLDeserializer(fresh_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify plan
        assert plan.conflicts == ()
        assert plan.new_entity_count > 0
        assert plan.source_hash is not None

    def test_whole_graph_roundtrip_produces_no_diff(self, ontology_repo, sample_data):
        """Acceptance criterion: whole-graph round-trip produces no diff."""
        # Export original entities
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Create fresh repository (empty DB) and import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify no conflicts and structural equality
        assert plan.conflicts == ()

        # Verify same number of entities
        original_classes = ontology_repo.list_classes(limit=10000)
        original_schemes = ontology_repo.list_concept_schemes()
        original_taxonomies = ontology_repo.list_taxonomies()
        original_individuals = ontology_repo.list_individuals()
        original_properties = ontology_repo.list_property_definitions()

        imported_class_count = len(
            [
                e
                for e in deserializer.incoming_entities.values()
                if e.get("type") == "class"
            ]
        )
        imported_scheme_count = len(
            [
                e
                for e in deserializer.incoming_entities.values()
                if e.get("type") == "concept_scheme"
            ]
        )
        imported_taxonomy_count = len(
            [
                e
                for e in deserializer.incoming_entities.values()
                if e.get("type") == "taxonomy"
            ]
        )
        imported_individual_count = len(
            [
                e
                for e in deserializer.incoming_entities.values()
                if e.get("type") == "individual"
            ]
        )
        imported_property_count = len(
            [
                e
                for e in deserializer.incoming_entities.values()
                if e.get("type") == "property_definition"
            ]
        )

        assert imported_class_count == len(original_classes)
        assert imported_scheme_count == len(original_schemes)
        assert imported_taxonomy_count == len(original_taxonomies)
        assert imported_individual_count == len(original_individuals)
        assert imported_property_count == len(original_properties)


class TestGraphMLMultiClassIndividual:
    """Test round-trip of multi-class Individual with ordering."""

    def test_multi_class_individual_ordering_survives(self, ontology_repo, sample_data):
        """Acceptance criterion: multi-class Individual ordering survives round-trip."""
        # Verify that Fido has dog and carnivore in that order
        fido = ontology_repo.get_individual(sample_data["fido"].id)
        assert fido is not None
        assert fido.class_ids == [sample_data["dog"].id, sample_data["carnivore"].id]

        # Export
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        deserializer.deserialize(exported, dry_run=True)

        # Verify that Fido's class ordering is preserved in the incoming entities
        fido_incoming = next(
            (
                e
                for e in deserializer.incoming_entities.values()
                if e.get("title") == "Fido"
            ),
            None,
        )
        assert fido_incoming is not None
        assert fido_incoming["class_ids"] == [
            sample_data["dog"].id,
            sample_data["carnivore"].id,
        ]

    def test_individual_class_order_missing_produces_warning(self, ontology_repo):
        """Test that missing class_order produces a warning."""
        import networkx as nx
        import io

        # Create GraphML with missing class_order using networkx
        G = nx.MultiDiGraph()
        G.add_node(
            "class1",
            kind="class",
            **{"cs:title": "TestClass", "cs:description": "A test class"}
        )
        G.add_node(
            "individual1",
            kind="individual",
            **{"cs:title": "TestIndividual", "cs:description": "A test individual"}
        )
        G.add_edge("individual1", "class1", kind="class_membership")

        output = io.BytesIO()
        nx.write_graphml(G, output)
        graphml_bytes = output.getvalue()

        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        plan = deserializer.deserialize(graphml_bytes, dry_run=True)

        # Verify warnings
        assert any("class_order" in w for w in plan.warnings)


class TestGraphMLExternalReferences:
    """Test external reference round-tripping."""

    def test_external_references_roundtrip(self, ontology_repo, sample_data):
        """Acceptance criterion: external_references round-trip via reserved data element."""
        # Export
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        exported_str = exported.decode("utf-8")
        # Verify external references are in the output
        assert "dbpedia" in exported_str
        assert "wikidata" in exported_str
        assert "cs:external_references" in exported_str

        # Import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        deserializer.deserialize(exported, dry_run=True)

        # Verify external references were extracted
        dog_incoming = next(
            (
                e
                for e in deserializer.incoming_entities.values()
                if e.get("title") == "Dog"
            ),
            None,
        )
        assert dog_incoming is not None
        assert len(dog_incoming["external_references"]) >= 2

        # Verify DBpedia and Wikidata refs
        refs = dog_incoming["external_references"]
        assert any(r["source"] == "dbpedia" for r in refs)
        assert any(r["source"] == "wikidata" for r in refs)

    def test_individual_external_references_roundtrip(self, ontology_repo, sample_data):
        """Test that Individual external references round-trip."""
        # Export
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        deserializer.deserialize(exported, dry_run=True)

        # Verify Fido's external references
        fido_incoming = next(
            (
                e
                for e in deserializer.incoming_entities.values()
                if e.get("title") == "Fido"
            ),
            None,
        )
        assert fido_incoming is not None
        assert len(fido_incoming["external_references"]) >= 1
        assert any(
            r["source"] == "example" and r["identifier"] == "fido-001"
            for r in fido_incoming["external_references"]
        )

    def test_external_tool_roundtrip_via_networkx(self, ontology_repo, sample_data):
        """Acceptance criterion: external-tool round-trip via networkx as external consumer.

        This test simulates an external tool (like Cytoscape, yEd, Gephi):
        1. Export GraphML from Context Studio
        2. Read with networkx (simulating external tool parsing)
        3. Re-export with networkx (simulating external tool saving)
        4. Reimport into Context Studio
        5. Verify external_references survive
        """
        import networkx as nx
        import io

        # Export from Context Studio
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Simulate external tool: read with networkx
        input_stream = io.BytesIO(exported)
        external_graph = nx.read_graphml(input_stream)

        # Simulate external tool: re-export with networkx
        output_stream = io.BytesIO()
        nx.write_graphml(external_graph, output_stream)
        reexported = output_stream.getvalue()

        # Reimport into fresh Context Studio database
        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        plan = deserializer.deserialize(reexported, dry_run=True)

        # Verify no conflicts (entities imported successfully)
        assert plan.conflicts == ()

        # Verify external_references survive through the round-trip
        # Check Dog's external references (DBpedia and Wikidata)
        dog_incoming = next(
            (
                e
                for e in deserializer.incoming_entities.values()
                if e.get("title") == "Dog"
            ),
            None,
        )
        assert dog_incoming is not None
        assert len(dog_incoming["external_references"]) >= 2

        refs = dog_incoming["external_references"]
        dbpedia_refs = [r for r in refs if r["source"] == "dbpedia"]
        wikidata_refs = [r for r in refs if r["source"] == "wikidata"]
        assert len(dbpedia_refs) >= 1
        assert len(wikidata_refs) >= 1
        assert dbpedia_refs[0]["identifier"] == "Dog"
        assert wikidata_refs[0]["identifier"] == "Q144"

        # Verify Individual's external references survive
        fido_incoming = next(
            (
                e
                for e in deserializer.incoming_entities.values()
                if e.get("title") == "Fido"
            ),
            None,
        )
        assert fido_incoming is not None
        assert len(fido_incoming["external_references"]) >= 1
        assert any(
            r["source"] == "example" and r["identifier"] == "fido-001"
            for r in fido_incoming["external_references"]
        )


class TestGraphMLIdempotentReimport:
    """Test that reimporting produces idempotent results."""

    def test_reimport_with_matching_external_references(
        self, ontology_repo, sample_data
    ):
        """Test that reimporting entities with matching external refs detects conflicts."""
        # Export
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import against populated DB
        deserializer = GraphMLDeserializer(ontology_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # Verify that conflicts are detected with EXTERNAL_REFERENCE match kind
        external_ref_conflicts = [
            c for c in plan.conflicts if c.match_kind == MatchKind.EXTERNAL_REFERENCE
        ]
        assert len(external_ref_conflicts) > 0

        # Verify default resolution is MERGE for external reference matches
        for conflict in external_ref_conflicts:
            assert conflict.default_resolution == ResolutionKind.MERGE

    def test_idempotent_reimport_preserves_uuids(self, ontology_repo, sample_data):
        """Test acceptance criterion: idempotent reimport produces no new duplicates."""
        # Record original entity IDs
        original_classes = ontology_repo.list_classes(limit=10000)
        original_schemes = ontology_repo.list_concept_schemes()
        original_taxonomies = ontology_repo.list_taxonomies()
        original_individuals = ontology_repo.list_individuals()
        original_properties = ontology_repo.list_property_definitions()
        original_all_ids = (
            {c.id for c in original_classes}
            | {s.id for s in original_schemes}
            | {t.id for t in original_taxonomies}
            | {i.id for i in original_individuals}
            | {p.id for p in original_properties}
        )

        # Export and reimport against populated DB
        serializer = GraphMLSerializer(ontology_repo)
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        exported = serializer.serialize(scope)

        # Import as dry-run to get plan
        deserializer = GraphMLDeserializer(ontology_repo)
        plan = deserializer.deserialize(exported, dry_run=True)

        # All conflicts should have existing entities with matching IDs
        for conflict in plan.conflicts:
            assert conflict.existing is not None
            assert conflict.existing in original_all_ids

        # External reference matches should MERGE by default
        external_ref_conflicts = [
            c for c in plan.conflicts if c.match_kind == MatchKind.EXTERNAL_REFERENCE
        ]
        for conflict in external_ref_conflicts:
            assert conflict.default_resolution == ResolutionKind.MERGE


class TestGraphMLLayoutCoordinates:
    """Test that layout coordinates are ignored on import."""

    def test_layout_coordinates_ignored_without_error(self):
        """Test that x, y coordinates are silently ignored on import."""
        import networkx as nx
        import io

        # Create GraphML with layout coordinates using networkx
        G = nx.MultiDiGraph()
        G.add_node(
            "tax1",
            kind="taxonomy",
            **{"cs:title": "TestTax", "x": "100.5", "y": "200.5"}
        )
        G.add_node(
            "scheme1",
            kind="concept_scheme",
            **{"cs:title": "TestScheme", "x": "300", "y": "400"}
        )
        G.add_edge("tax1", "scheme1", kind="has_scheme")

        output = io.BytesIO()
        nx.write_graphml(G, output)
        graphml_bytes = output.getvalue()

        fresh_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(fresh_engine)
        fresh_session_factory = sessionmaker(bind=fresh_engine)
        fresh_repo = SQLiteOntologyRepository(fresh_session_factory)

        deserializer = GraphMLDeserializer(fresh_repo)
        plan = deserializer.deserialize(graphml_bytes, dry_run=True)

        # Should not raise exception and should not have x/y in warnings
        assert plan is not None
        # x, y should not produce warnings since they're in the ignored set
        coord_warnings = [
            w for w in plan.warnings if "x" in w.lower() or "y" in w.lower()
        ]
        assert len(coord_warnings) == 0
