"""
Integration test for end-to-end retrieval behavior (Phase 4).

Validates the embed→search→filter pipeline end-to-end against a real
SqliteSchemaVectorIndex with embedded class definitions, confirming that
a source text about a specific topic retrieves a subset of classes that
includes the classes actually relevant to that topic.
"""

import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.value_objects import ExternalReference
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_extraction_repository import FakeExtractionRepository
from tests.fakes.fake_extraction_run_repo import FakeExtractionRunRepository


class TestRetrievalEndToEnd:
    """Integration tests for _relevant_class_catalog against real schema vector index."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_retrieval.db"
            engine = create_local_db_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)
            yield create_session_factory(engine)

    @pytest.fixture
    def ontology_repo(self, temp_db):
        """Create an ontology repository with real database."""
        return SQLiteOntologyRepository(temp_db)

    @pytest.fixture
    def embedding_service(self):
        """Use a deterministic fake embedding service for predictable test results."""
        return FakeEmbeddingService()

    @pytest.fixture
    def schema_index(self, temp_db, embedding_service):
        """Create a real schema vector index."""
        index = SqliteSchemaVectorIndex(temp_db, embedding_service)
        yield index

    @pytest.fixture
    def extraction_service(self, ontology_repo, embedding_service, schema_index):
        """Create an ExtractionService with real schema index."""
        return ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=embedding_service,
            llm=None,  # Not needed for catalog retrieval
            nlp=None,  # Not needed for catalog retrieval
            reference_sources=[],
            event_publisher=FakeEventPublisher(),
            extraction_repo=FakeExtractionRepository(),
            extraction_run_repo=FakeExtractionRunRepository(),
            schema_index=schema_index,
        )

    def _setup_ontology_with_classes(
        self, ontology_repo: SQLiteOntologyRepository, taxonomy_id: str
    ) -> tuple[Taxonomy, list[Class]]:
        """
        Set up a realistic ontology with domain-specific classes.

        Creates a taxonomy with >50 classes across multiple domains (technology,
        biology, geography) to ensure retrieval is triggered. Returns the taxonomy
        and the list of created classes.
        """
        taxonomy = Taxonomy(
            id=taxonomy_id,
            identifier="test_ontology",
            title="Multi-Domain Test Ontology",
            description="Test ontology with multiple domains for retrieval testing",
        )
        ontology_repo.save_taxonomy(taxonomy)

        scheme = ConceptScheme(
            id=str(uuid4()),
            taxonomy_id=taxonomy_id,
            identifier="main_scheme",
            title="Main Scheme",
            description="Main concept scheme",
        )
        ontology_repo.save_concept_scheme(scheme)

        classes = []

        # Technology domain classes
        tech_classes = [
            ("microservice", "Microservice", "An independently deployable service"),
            (
                "database",
                "Database",
                "A persistent data store for application state",
            ),
            ("api", "API", "Application programming interface for system interaction"),
            ("cache", "Cache", "Fast temporary storage for frequently accessed data"),
            (
                "message_queue",
                "Message Queue",
                "Asynchronous communication system between services",
            ),
            (
                "load_balancer",
                "Load Balancer",
                "Distributes incoming requests across multiple servers",
            ),
            (
                "container",
                "Container",
                "Isolated runtime environment for applications",
            ),
            (
                "service_discovery",
                "Service Discovery",
                "Mechanism to locate services in a distributed system",
            ),
            (
                "circuit_breaker",
                "Circuit Breaker",
                "Pattern for preventing cascading failures in distributed systems",
            ),
            (
                "monitoring",
                "Monitoring",
                "Observability system for tracking application health",
            ),
        ]

        # Biology domain classes
        bio_classes = [
            ("cell", "Cell", "Basic unit of life"),
            ("protein", "Protein", "Organic compound essential for life"),
            ("gene", "Gene", "Unit of heredity"),
            ("enzyme", "Enzyme", "Biological catalyst for chemical reactions"),
            ("dna", "DNA", "Molecule carrying genetic instructions"),
            ("rna", "RNA", "Messenger molecule involved in protein synthesis"),
            ("mitochondria", "Mitochondria", "Cellular powerhouse producing energy"),
            (
                "photosynthesis",
                "Photosynthesis",
                "Process converting light to chemical energy",
            ),
            ("metabolism", "Metabolism", "Chemical processes maintaining life"),
            ("homeostasis", "Homeostasis", "Maintenance of internal stability"),
        ]

        # Geography domain classes
        geo_classes = [
            ("mountain", "Mountain", "Large landform rising above surrounding terrain"),
            ("river", "River", "Large natural stream of water"),
            ("ocean", "Ocean", "Large body of salt water"),
            ("desert", "Desert", "Arid region with minimal precipitation"),
            ("forest", "Forest", "Large area covered with trees"),
            ("glacier", "Glacier", "Large mass of ice moving slowly down mountains"),
            ("plateau", "Plateau", "Elevated flat region"),
            ("valley", "Valley", "Low area between hills or mountains"),
            ("island", "Island", "Land surrounded by water"),
            ("continent", "Continent", "Large landmass on Earth"),
        ]

        # General/unrelated classes (expanded to ensure >50 total)
        other_classes = [
            ("painting", "Painting", "Artwork created with pigments and canvas"),
            ("music", "Music", "Art form based on organized sounds"),
            ("literature", "Literature", "Written works of artistic value"),
            ("architecture", "Architecture", "Science and art of designing buildings"),
            ("sculpture", "Sculpture", "Three-dimensional artwork"),
            ("dance", "Dance", "Art form involving movement"),
            ("photography", "Photography", "Art of capturing light on film or sensor"),
            ("mathematics", "Mathematics", "Study of numbers and abstract structures"),
            ("physics", "Physics", "Study of matter and energy"),
            ("chemistry", "Chemistry", "Study of substances and their reactions"),
            ("history", "History", "Study of past events"),
            ("philosophy", "Philosophy", "Study of fundamental truths"),
            ("sociology", "Sociology", "Study of human society"),
            ("psychology", "Psychology", "Study of human behavior"),
            ("economics", "Economics", "Study of production and consumption"),
            ("law", "Law", "System of rules enforced by government"),
            ("medicine", "Medicine", "Science of healing and health"),
            ("agriculture", "Agriculture", "Cultivation of plants and animals"),
            (
                "engineering",
                "Engineering",
                "Application of science for practical purposes",
            ),
            ("astronomy", "Astronomy", "Study of celestial objects"),
            ("linguistics", "Linguistics", "Study of languages and communication"),
            ("anthropology", "Anthropology", "Study of human cultures"),
            ("geology", "Geology", "Study of rocks and Earth"),
            ("meteorology", "Meteorology", "Study of weather and atmosphere"),
            ("zoology", "Zoology", "Study of animals"),
        ]

        all_class_specs = tech_classes + bio_classes + geo_classes + other_classes

        for identifier, title, description in all_class_specs:
            cls = Class(
                id=str(uuid4()),
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy_id,
                identifier=identifier,
                title=title,
                description=description,
                external_references=[
                    ExternalReference(
                        source="test_ontology",
                        identifier=f"test.{identifier}",
                    )
                ],
            )
            saved_cls = ontology_repo.save_class(cls)
            classes.append(saved_cls)

        return taxonomy, classes

    def test_retrieval_on_large_ontology_returns_subset(
        self, extraction_service, ontology_repo, schema_index
    ):
        """
        Retrieval should return a subset when ontology exceeds skip threshold.

        Sets up an ontology with >50 classes, indexes embeddings, then verifies
        that _relevant_class_catalog returns fewer classes than the full catalog
        when queried with topically relevant text.
        """
        taxonomy_id = str(uuid4())
        taxonomy, all_classes = self._setup_ontology_with_classes(ontology_repo, taxonomy_id)

        # Reindex all embeddings (this embeds all class titles and descriptions)
        reindexed_count = schema_index.reindex_all()
        assert reindexed_count > 50  # Ensure we have enough classes

        # Get full catalog for comparison
        full_catalog = extraction_service._ontology_class_catalog(taxonomy)
        assert len(full_catalog) > 50  # Verify ontology is large enough to trigger retrieval

        # Query with technology-focused text
        tech_source_text = (
            "We have a distributed system with multiple microservices that "
            "communicate via message queues. Each service has its own database. "
            "We use load balancers to distribute traffic and containers for deployment. "
            "We monitor service health using observability systems."
        )

        retrieved_catalog = extraction_service._relevant_class_catalog(tech_source_text, taxonomy)

        # Verify we got a subset (not full catalog)
        assert len(retrieved_catalog) < len(full_catalog)
        # Verify we still got a reasonable number of results
        assert len(retrieved_catalog) >= 5

        # Verify technology-related classes are included
        retrieved_refs = [ref for ref, _ in retrieved_catalog]
        tech_refs = {"test.microservice", "test.database", "test.message_queue"}
        matches = tech_refs & set(retrieved_refs)
        assert len(matches) > 0, "Expected at least some technology classes in retrieval results"

    def test_retrieval_returns_consistent_subset(
        self, extraction_service, ontology_repo, schema_index
    ):
        """
        Retrieval returns a consistent subset for the same query.

        With a deterministic embedding service, the same query should always
        return the same set of results. This validates the retrieval path
        works end-to-end with real schema index and consistent scoring.
        """
        taxonomy_id = str(uuid4())
        taxonomy, all_classes = self._setup_ontology_with_classes(ontology_repo, taxonomy_id)

        # Reindex all embeddings
        schema_index.reindex_all()

        # Query the index twice with the same text
        query_text = "Cells DNA proteins enzymes"
        result1 = extraction_service._relevant_class_catalog(query_text, taxonomy)
        result2 = extraction_service._relevant_class_catalog(query_text, taxonomy)

        # Results should be identical (same order, same classes)
        assert result1 == result2, "Retrieval should be deterministic for same query"

        # Should return a subset, not full catalog
        full_catalog = extraction_service._ontology_class_catalog(taxonomy)
        assert len(result1) < len(
            full_catalog
        ), "Retrieved subset should be smaller than full catalog"

    def test_small_ontology_skips_retrieval(self, extraction_service, ontology_repo, schema_index):
        """
        Small ontologies (≤50 classes) should return full catalog without retrieval.

        When the ontology is at or below the skip threshold, the method should
        return the full catalog directly without calling embed/search.
        """
        taxonomy_id = str(uuid4())
        taxonomy = Taxonomy(
            id=taxonomy_id,
            identifier="small_ontology",
            title="Small Test Ontology",
            description="Small ontology with few classes",
        )
        ontology_repo.save_taxonomy(taxonomy)

        scheme = ConceptScheme(
            id=str(uuid4()),
            taxonomy_id=taxonomy_id,
            identifier="small_scheme",
            title="Small Scheme",
            description="Scheme with few classes",
        )
        ontology_repo.save_concept_scheme(scheme)

        # Create exactly 50 classes (at skip threshold)
        for i in range(50):
            cls = Class(
                id=str(uuid4()),
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy_id,
                identifier=f"class_{i}",
                title=f"Class {i}",
                description=f"Class {i} description",
                external_references=[
                    ExternalReference(
                        source="test",
                        identifier=f"test.class_{i}",
                    )
                ],
            )
            ontology_repo.save_class(cls)

        # Index embeddings
        schema_index.reindex_all()

        # Query - should skip retrieval and return full catalog
        result = extraction_service._relevant_class_catalog("test query", taxonomy)

        # Should return exactly 50 classes without filtering
        assert len(result) == 50

    def test_retrieval_with_large_ontology_uses_schema_index(
        self, extraction_service, ontology_repo, schema_index
    ):
        """
        Retrieval pipeline uses schema index when ontology is large.

        With real schema index, retrieval is exercised (no fallback to full catalog).
        Results are smaller than full catalog and include relevant entries.
        """
        taxonomy_id = str(uuid4())
        taxonomy = Taxonomy(
            id=taxonomy_id,
            identifier="test_ontology",
            title="Test Ontology",
            description="Test ontology",
        )
        ontology_repo.save_taxonomy(taxonomy)

        scheme = ConceptScheme(
            id=str(uuid4()),
            taxonomy_id=taxonomy_id,
            identifier="scheme",
            title="Scheme",
            description="Scheme",
        )
        ontology_repo.save_concept_scheme(scheme)

        # Create >50 classes to trigger retrieval
        for i in range(70):
            cls = Class(
                id=str(uuid4()),
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy_id,
                identifier=f"class_{i}",
                title=f"Class {i}",
                description=f"Class {i} description",
                external_references=[
                    ExternalReference(
                        source="test",
                        identifier=f"test.class_{i}",
                    )
                ],
            )
            ontology_repo.save_class(cls)

        schema_index.reindex_all()

        # Query with relevant text
        query_text = "Class 5 description"
        result = extraction_service._relevant_class_catalog(query_text, taxonomy)

        # Should return retrieved subset
        full_catalog = extraction_service._ontology_class_catalog(taxonomy)
        assert len(result) < len(full_catalog), "Retrieval should return subset"
        # Should include the Class 5 that matches the query
        refs = [ref for ref, _ in result]
        assert "test.class_5" in refs, "Should include matching class in results"

    def test_retrieval_preserves_catalog_format(
        self, extraction_service, ontology_repo, schema_index
    ):
        """
        Retrieved catalog maintains (ref, title) tuple format.

        The format should match _ontology_class_catalog output to ensure
        downstream prompt building remains compatible.
        """
        taxonomy_id = str(uuid4())
        taxonomy, _ = self._setup_ontology_with_classes(ontology_repo, taxonomy_id)

        schema_index.reindex_all()

        # Query with technology text
        source_text = "Microservices and databases with load balancing"
        result = extraction_service._relevant_class_catalog(source_text, taxonomy)

        # Verify format: list of (ref, title) tuples
        assert isinstance(result, list)
        for ref, title in result:
            assert isinstance(ref, str)
            assert isinstance(title, str)
            assert len(ref) > 0
            assert len(title) > 0
            # Refs should look like external references
            assert "." in ref or "_" in ref


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
